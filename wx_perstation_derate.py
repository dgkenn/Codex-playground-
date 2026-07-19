#!/usr/bin/env python3
"""wx_perstation_derate.py -- should the per-station margin DERATES be softened? (they may sacrifice EV)

WHY THIS EXISTS: kwx_runner carries per-station derates (currently KPHX: margin 1->2F and size x0.5;
historically also KLAX/KMIA/KPHL/KSEA at 2F) because Track B's per-station worst-offender table showed
those stations with the highest obs-vs-CLI lock-failure. BUT that table was computed for the RAW1MIN
candidate (unfiltered, sustain=1) -- dominated by 1-min glitches that the deployed rule (glitch filter +
sustain=3) removes. The cushion study (wx_subdegree_cushion / wx_cushion_optimize) showed small-cushion
margin=1 fires carry ~3x the EV, so if a station is safe at margin=1 UNDER THE DEPLOYED RULE, its derate
is over-conservative and costs real EV. This script re-measures the per-station lock-failure for the
DEPLOYED candidate (glitch + sustain3, via phase2_trackB_tail.sustained_max_k(k=3) -- the validated
implementation, NOT kwx_runner.sustained_extreme) against the official NWS CLI daily max (the settlement
truth), multi-year, and renders a PASS/FAIL verdict per derated station.

METHOD (identical to phase2_trackB_tail section 6, but for the deployed rule):
  - Data: IEM ASOS 1-minute obs + IEM-parsed NWS CLI daily climate reports, all ~20 bot stations,
    years 2021-2026 (reusing phase2_trackB_tail's fetch + .tailrisk_cache compact per-day cache, so a
    re-run after the cache exists touches IEM only for missing station-years).
  - near_money synthetic strike ladder {C-3..C+1} anchored on the day's official CLI high C (no
    historical KXHIGH listings exist pre-2026; see phase2_trackB_tail's DESIGN NOTE -- a stated modeling
    choice, unbiased-forecast proxy).
  - lock-failure: fired (candidate's sustained day value >= K+margin) AND K >= C (strike settles NO).
  - Wilson 95% CI on each station's conditional lock-failure rate: small-n honesty -- a station with
    2/50 must not be judged by its 4% point estimate alone.

PRE-REGISTERED RELAXATION BAR (set before looking at the numbers): a station's derate may be relaxed
ONLY if its sustain3 margin=1 lock-failure rate's Wilson-95 UPPER bound is <= the all-station pooled
rate + 1 percentage point. Rationale: "upper bound" charges the station for its own sample size (a
noisy station cannot pass on luck), and "pooled + 1pp" means we only relax stations that are
statistically indistinguishable from the fleet the base margin was validated on. Failing the bar is a
fully acceptable outcome -- the derate simply stays.

KNOWN CAVEAT (inherited from phase2_trackB_tail): fires on different rungs of the same station-day are
correlated (one hot day can fail C and C+1 together), so the per-rung Wilson CI is somewhat optimistic
about n. We therefore ALSO report the ladder-independent day-level ATM failure rate (did the sustained
value clear C+margin at all) as a cross-check; the bar itself is applied to the per-rung rate because
that is the exact statistic the derates were originally set from (apples-to-apples).

Outputs (committed as evidence): wx_perstation_derate_results.json + wx_perstation_derate_results.md
"""
import json, math, os, sys, time
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kalshi_weather_nowcast as base          # noqa: E402  (CITY_CONFIG via p2.station_offset_map)
import kalshi_wx_settlement_basis as basis     # noqa: E402  (CLI fetch/cache -- settlement truth)
import phase2_trackB_tail as p2                # noqa: E402  (fetch, cache, sustained_max_k -- the validated sustain impl)

LADDER = [-3, -2, -1, 0, 1]                    # near_money, matches phase2_trackB_tail section 6
MARGINS = (1, 2, 3)
DERATED_NOW = {"KPHX"}                          # stations kwx_runner currently derates (margin and/or size)
DERATED_HIST = {"KPHX", "KLAX", "KMIA", "KPHL", "KSEA"}  # the original raw1min-era derate set (for context)
BAR_EXTRA_PP = 1.0                              # relaxation bar: Wilson-95 upper <= pooled rate + this many pp
Z95 = 1.959963985

OUT_JSON = os.path.join(HERE, "wx_perstation_derate_results.json")
OUT_MD = os.path.join(HERE, "wx_perstation_derate_results.md")


def wilson_ci(k, n, z=Z95):
    """Two-sided Wilson score interval (lo, hi) for a binomial proportion k/n. Reuses the same algebra
    as base.wilson_upper_bound (which this must agree with on the upper side) but returns both bounds,
    because the report shows the full CI, not only the worst case."""
    if n <= 0:
        return None, None
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return max(0.0, (center - half) / denom), min(1.0, (center + half) / denom)


def build_cache():
    """Ensure the multi-year compact per-day cache exists for every bot station x year. Reuses
    phase2_trackB_tail.process_station_year (which fetches IEM ASOS-1min + METAR once per missing
    station-year, reduces to ~200B/day records, and caches to .tailrisk_cache/) -- so IEM request
    volume is one-time and moderate; subsequent runs are disk-only."""
    stmap = p2.station_offset_map()
    stations = sorted(stmap.keys())
    print(f"[cache] stations ({len(stations)}): {stations}")
    print(f"[cache] years: {p2.YEARS}")
    for st in stations:
        cli = {}
        for yr in p2.YEARS:
            try:
                cli.update(basis.fetch_cli_year(st, yr))
            except Exception as e:
                print(f"  [warn] CLI {st} {yr} failed: {e}", file=sys.stderr)
        for yr in p2.YEARS:
            try:
                p2.process_station_year(st, yr, stmap[st]["offset"], cli)
            except Exception as e:
                print(f"  [warn] obs {st} {yr} failed: {e}", file=sys.stderr)
    return stations


def load_all_records():
    """(station, record) pairs from the compact cache -- same shape phase2_trackB_tail aggregates."""
    import glob as _glob
    out = []
    for fp in sorted(_glob.glob(os.path.join(p2.CACHE_DIR, "daily_*.json"))):
        stn = os.path.basename(fp).split("_")[1]
        with open(fp) as f:
            for rec in json.load(f):
                out.append((stn, rec))
    return out


def compute(records, field):
    """Per-station aggregation for one candidate field of the compact records.
    Rung-level (the statistic the derates were set from): for each margin, count fires
    (value >= K+margin over the near_money ladder) and lock-failures (fired AND K >= C).
    Day-level cross-check: count eligible days and ATM-failure days (value >= C+margin),
    which needs no ladder-width assumption."""
    agg = defaultdict(lambda: {
        "rung": {m: {"fired": 0, "fail": 0} for m in MARGINS},
        "day": {m: {"days": 0, "fail_days": 0} for m in MARGINS},
        "years": set(),
    })
    nrec = 0
    for stn, rec in records:
        C = rec.get("cli_high")
        v = rec.get(field)
        if C is None or v is None:
            continue
        try:
            C = int(round(C))
        except Exception:
            continue
        nrec += 1
        a = agg[stn]
        a["years"].add(rec["date"][:4])
        for m in MARGINS:
            a["day"][m]["days"] += 1
            if v >= C + m:
                a["day"][m]["fail_days"] += 1
            for off in LADDER:
                K = C + off
                if v >= K + m:
                    a["rung"][m]["fired"] += 1
                    if K >= C:
                        a["rung"][m]["fail"] += 1
    return agg, nrec


def rate(d):
    return d["fail"] / d["fired"] if d["fired"] else None


def main():
    t0 = time.time()
    print("=== wx_perstation_derate: per-station lock-failure UNDER THE DEPLOYED RULE (glitch+sustain3) ===")
    build_cache()
    records = load_all_records()
    print(f"[data] compact station-day records loaded: {len(records)}")

    sus, nrec_s = compute(records, "sustain3_max")     # DEPLOYED rule (sustained_max_k(k=3) at cache-build time)
    raw, _ = compute(records, "raw_max")               # what the original derates were set from (context)
    stations = sorted(sus.keys())
    print(f"[data] station-days with CLI truth + sustain3 value: {nrec_s} across {len(stations)} stations")

    # Pooled all-station sustain3 margin=1 rate -> the relaxation bar (pre-registered above).
    pool_fired = sum(sus[st]["rung"][1]["fired"] for st in stations)
    pool_fail = sum(sus[st]["rung"][1]["fail"] for st in stations)
    pooled = pool_fail / pool_fired if pool_fired else None
    bar = (pooled + BAR_EXTRA_PP / 100.0) if pooled is not None else None

    rows = []
    for st in stations:
        r1 = sus[st]["rung"][1]
        lo, hi = wilson_ci(r1["fail"], r1["fired"])
        day1 = sus[st]["day"][1]
        raw1 = raw.get(st, {"rung": {1: {"fired": 0, "fail": 0}}})["rung"][1]
        verdict = None
        if bar is not None and hi is not None:
            verdict = "PASS" if hi <= bar else "FAIL"
        rows.append({
            "station": st,
            "years": sorted(sus[st]["years"]),
            "sustain3_m1": {"fired": r1["fired"], "fail": r1["fail"], "rate": rate(r1),
                             "wilson95_lo": lo, "wilson95_hi": hi},
            "sustain3_m2": {"fired": sus[st]["rung"][2]["fired"], "fail": sus[st]["rung"][2]["fail"],
                             "rate": rate(sus[st]["rung"][2])},
            "sustain3_m3": {"fired": sus[st]["rung"][3]["fired"], "fail": sus[st]["rung"][3]["fail"],
                             "rate": rate(sus[st]["rung"][3])},
            "day_atm_m1": {"days": day1["days"], "fail_days": day1["fail_days"],
                            "rate": day1["fail_days"] / day1["days"] if day1["days"] else None},
            "raw1min_m1": {"fired": raw1["fired"], "fail": raw1["fail"], "rate": rate(raw1)},
            "derated_now": st in DERATED_NOW,
            "derated_historically": st in DERATED_HIST,
            "verdict_vs_bar": verdict,
        })
    rows.sort(key=lambda r: -(r["sustain3_m1"]["rate"] or 0))

    result = {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "method": "near_money ladder {C-3..C+1} on official CLI high C; deployed rule = glitch filter + "
                   "phase2_trackB_tail.sustained_max_k(k=3); lock-failure = fired AND K >= C; "
                   "Wilson 95% CI per station",
        "years_requested": p2.YEARS,
        "n_station_day_records": nrec_s,
        "relaxation_bar": {
            "rule": "Wilson-95 UPPER bound of station sustain3 m1 rate <= pooled all-station m1 rate + 1pp",
            "pooled_m1_fired": pool_fired, "pooled_m1_fail": pool_fail,
            "pooled_m1_rate": pooled, "bar": bar,
        },
        "stations": rows,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=1)

    # ---------------- markdown report ----------------
    def pct(x, nd=2):
        return f"{100*x:.{nd}f}%" if x is not None else "n/a"

    L = []
    L.append("# Per-Station Derate Re-Measurement (deployed rule: glitch + sustain3)\n\n")
    L.append(f"Run date: {result['run_utc']}\n\n")
    L.append("Re-measures each station's obs-vs-CLI lock-failure under the DEPLOYED detection rule "
             "(glitch filter + 3-minute sustain, `phase2_trackB_tail.sustained_max_k(k=3)`) against the "
             "official NWS CLI daily max, multi-year, all seasons. The existing per-station derates were "
             "set from the RAW-1-minute failure mode, which the deployed rule filters out; margin=1 fires "
             "carry ~3x EV, so an unnecessary derate costs real money.\n\n")
    L.append(f"**Coverage:** {len(stations)} stations, years requested {p2.YEARS}, "
             f"{nrec_s} station-days with both CLI truth and sustain3 obs value.\n\n")
    L.append("**Pre-registered relaxation bar:** a derate may be relaxed only if the station's sustain3 "
             "margin=1 lock-failure Wilson-95 UPPER bound is <= the pooled all-station margin=1 rate + 1pp. "
             f"Pooled rate = {pool_fail}/{pool_fired} = **{pct(pooled)}** -> bar = **{pct(bar)}**.\n\n")
    L.append("| station | m1 fired | m1 fail | m1 rate | Wilson-95 CI | m2 rate | day-ATM m1 | raw1min m1 "
             "(derates' origin) | derate now | verdict vs bar |\n")
    L.append("|---|---|---|---|---|---|---|---|---|---|\n")
    for r in rows:
        s1 = r["sustain3_m1"]
        ci = (f"[{pct(s1['wilson95_lo'])}, {pct(s1['wilson95_hi'])}]"
              if s1["wilson95_hi"] is not None else "n/a")
        dr = "KPHX 2F, x0.5" if r["station"] in DERATED_NOW else ("(was 2F)" if r["station"] in DERATED_HIST else "-")
        L.append(f"| {r['station']} | {s1['fired']} | {s1['fail']} | {pct(s1['rate'])} | {ci} | "
                 f"{pct(r['sustain3_m2']['rate'])} | {pct(r['day_atm_m1']['rate'])} | "
                 f"{pct(r['raw1min_m1']['rate'], 1)} | {dr} | {r['verdict_vs_bar']} |\n")

    L.append("\n## Verdicts for derated stations\n\n")
    for r in rows:
        if r["station"] in DERATED_HIST:
            s1 = r["sustain3_m1"]
            tag = "CURRENTLY DERATED" if r["station"] in DERATED_NOW else "historically derated, since reverted"
            L.append(f"- **{r['station']}** ({tag}): sustain3 m1 = {s1['fail']}/{s1['fired']} = "
                     f"{pct(s1['rate'])}, Wilson-95 upper {pct(s1['wilson95_hi'])} vs bar {pct(bar)} -> "
                     f"**{r['verdict_vs_bar']}**\n")
    L.append("\nA FAIL means the derate stays (evidence-only outcome). A PASS licenses relaxing that "
             "station's `STATION_MARGIN`/`STATION_SIZE_MULT` in kwx_runner.py, citing these numbers.\n")
    L.append("\nCaveat: per-rung fires on the same station-day are correlated, so per-rung Wilson CIs are "
             "mildly optimistic about effective n; the ladder-independent day-ATM column is the "
             "cross-check. The bar uses the per-rung statistic because the derates were set from it "
             "(apples-to-apples).\n")
    with open(OUT_MD, "w") as f:
        f.writelines(L)

    print(f"\nwrote {OUT_JSON}\nwrote {OUT_MD}")
    print(f"pooled sustain3 m1 rate {pct(pooled)}  -> bar {pct(bar)}")
    for r in rows:
        if r["station"] in DERATED_HIST:
            print(f"  {r['station']}: m1 {pct(r['sustain3_m1']['rate'])} "
                  f"(Wilson95 hi {pct(r['sustain3_m1']['wilson95_hi'])}) -> {r['verdict_vs_bar']}")
    print(f"done in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
