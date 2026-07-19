#!/usr/bin/env python3
"""wx_perstation_derate.py -- should the per-station margin DERATES be softened? (they may sacrifice EV)

kwx_runner raises the clearance margin on 5 stations (KPHX->3F, KLAX/KMIA/KPHL/KSEA->2F) because Track B's
per-station worst-offender table showed them with the highest obs-vs-CLI lock-failure. BUT that table was
computed for the RAW1MIN candidate (unfiltered, sustain=1) -- dominated by 1-min glitches that the deployed
rule (glitch + sustain=3) removes. The cushion study showed small-cushion (margin=1) fires carry ~3x the EV,
so if these stations are safe at margin=1 UNDER THE DEPLOYED RULE, the derate is over-conservative and costs
real EV. This recomputes the per-station lock-failure for the DEPLOYED candidate (sustain3_max) from the
Track B multi-year cache, so the derate can be judged on the rule we actually run.

lock-failure = fired (sustained value >= strike+margin) AND strike >= CLI_high (settles NO). near_money ladder
{C-3..C+1} anchored on the day's official CLI high C, matching phase2_trackB_tail section 6.
"""
import json, glob, os
from collections import defaultdict

LADDER = [-3, -2, -1, 0, 1]
DERATED = {"KPHX", "KLAX", "KMIA", "KPHL", "KSEA"}
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tailrisk_cache")


def compute(field):
    agg = defaultdict(lambda: {m: {"fired": 0, "fail": 0} for m in (1, 2, 3)})
    nrec = 0
    for fp in glob.glob(os.path.join(CACHE, "daily_*.json")):
        stn = os.path.basename(fp).split("_")[1]
        for rec in json.load(open(fp)):
            C = rec.get("cli_high"); v = rec.get(field)
            if C is None or v is None:
                continue
            try:
                C = int(round(C))
            except Exception:
                continue
            nrec += 1
            for m in (1, 2, 3):
                for off in LADDER:
                    K = C + off
                    if v >= K + m:
                        agg[stn][m]["fired"] += 1
                        if K >= C:
                            agg[stn][m]["fail"] += 1
    return agg, nrec


def rate(d):
    return 100.0 * d["fail"] / d["fired"] if d["fired"] else None


def main():
    agg, nrec = compute("sustain3_max")
    print(f"Per-station lock-failure | DEPLOYED rule glitch+sustain3 | near_money ladder | multi-year | recs={nrec}\n")
    print(f"{'station':>8}{'m1_fired':>9}{'m1_fail%':>9}{'m2_fail%':>9}{'m3_fail%':>9}   note")
    rows = sorted(agg.items(), key=lambda kv: -(rate(kv[1][1]) or 0))
    for stn, d in rows:
        r = [rate(d[m]) for m in (1, 2, 3)]
        s = [f"{x:.2f}" if x is not None else "n/a" for x in r]
        note = "<-- currently derated" if stn in DERATED else ""
        print(f"{stn:>8}{d[1]['fired']:>9}{s[0]:>9}{s[1]:>9}{s[2]:>9}   {note}")
    print("\ncompare to RAW1MIN (unfiltered) margin=1 per-station, which is what the derates were set from:")
    raw, _ = compute("raw_max")
    for stn in ["KPHX", "KLAX", "KMIA", "KPHL", "KSEA"]:
        r1s = rate(raw[stn][1]); r1d = rate(agg[stn][1])
        print(f"  {stn}: raw1min m1 {r1s:.1f}%  ->  glitch+sustain3 m1 {r1d:.2f}%  "
              f"({r1s/max(r1d,0.01):.0f}x lower with the deployed filter)")


if __name__ == "__main__":
    main()
