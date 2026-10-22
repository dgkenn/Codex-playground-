"""Export readiness cases from the Python engine (authoritative) for tests/readiness-parity.mjs.

Run from marathon/tools:  python3 tests/gen_readiness_vectors.py
The inputs are generated here from a fixed seed and written WITH the outputs, because the JS side
has no other way to get the same random histories.
"""
import json, math, random, sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
from marathon_engine.readiness import NightSummary, daily_readiness  # noqa: E402
from marathon_engine.signal_quality import clean_intervals, rmssd  # noqa: E402

rng = random.Random(20261022)
cases = []
for k in range(40):
    start = date(2026, 6, 1)
    n_days = rng.choice([5, 20, 45, 70])
    base_ln = math.log(rng.uniform(25, 80))
    drift = rng.choice([0.0, -0.02, 0.015, -0.05])
    rows = []
    for d in range(n_days):
        if rng.random() < 0.15:
            continue                                   # a missed morning
        ln = base_ln + drift * max(0, d - n_days + 10) + rng.gauss(0, 0.12)
        row = {"day": (start + timedelta(days=d)).isoformat(),
               "hrvMs": round(math.exp(ln), 1),
               "restingHr": round(rng.gauss(60, 3) + (4 if drift < -0.03 and d > n_days - 4 else 0), 1),
               "cleanCount": rng.choice([300, 300, 300, 200]),
               "artifactFraction": rng.choice([0.01, 0.02, 0.03, 0.08]),
               "source": "verity_ppi_rmssd", "posture": "supine"}
        if rng.random() < 0.5:
            row["sleepMin"] = rng.choice([330, 400, 450, 480])
        if rng.random() < 0.3:
            row["soreness"] = rng.randint(1, 7); row["fatigue"] = rng.randint(1, 7)
        if rng.random() < 0.1:
            row["motivation"] = rng.randint(1, 3)
        if rng.random() < 0.03:
            row["illness"] = True
        rows.append(row)
    if not rows:
        continue
    nights = [NightSummary(day=date.fromisoformat(r["day"]), hrv_ms=r["hrvMs"], resting_hr=r["restingHr"],
                           clean_interval_count=r["cleanCount"], artifact_fraction=r["artifactFraction"],
                           hrv_source=r["source"], hrv_posture=r["posture"],
                           total_sleep_min=r.get("sleepMin"), soreness_1_7=r.get("soreness"),
                           fatigue_1_7=r.get("fatigue"), motivation_1_7=r.get("motivation"),
                           illness=r.get("illness", False)) for r in rows]
    r = daily_readiness(nights)
    cases.append({"nights": rows, "expect": {
        "band": r.band, "action": r.action, "score": r.score, "hrvStatus": r.hrv_status,
        "rollingLn": r.rolling_ln_hrv, "override": r.override_reason,
        "baselineN": r.baseline.n_nights if r.baseline else None,
        "flags": sorted(f["flag"] for f in r.flags)}})

beats = [rng.choice([900, 950, 1000, 1050]) + rng.randint(-30, 30) for _ in range(400)]
beats[50] = 2000; beats[51] = 400; beats[120] = 3000
blockers = [rng.random() < 0.03 for _ in beats]
clean, counts = clean_intervals(beats, blockers=blockers)
out = {"cases": cases, "beats": {"intervals": beats, "blockers": blockers,
                                  "counts": counts, "rmssd": rmssd(clean)}}
Path(__file__).with_name("readiness_vectors.json").write_text(json.dumps(out, indent=0))
print(f"{len(cases)} cases; bands: {sorted(set(c['expect']['band'] for c in cases))}")
