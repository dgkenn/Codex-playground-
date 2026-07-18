#!/usr/bin/env python3
"""wx_halflife_segments.py -- WHERE does the profit gap persist longest? (expand the effective half-life)

The nowcast edge's enemy is repricing speed: once a rung locks, the ask decays toward 99c with a ~3.3-min
POOLED half-life, so a slow feed arrives after the gap is gone. But 3.3 min is an average over very different
fires -- some reprice in <1 min (dead on arrival), others stay wide for 10-30+ min. If we can identify the
SEGMENTS where the gap persists (slow repricing), we concentrate capital there and become far less
latency-bound -- which both raises capacity and reduces the value of paying for a 1-min feed.

Per deployable fire (config 1_3, exec<0.99) we have decay_gap_by_min {0,1,2,5,10,30,60}. We measure, per fire:
  - retention@t = gap(t)/gap(0)             (1.0 = untouched; 0 = fully repriced)  -- robust, no fit
  - half_life   = ln2 / -slope of ln gap    (log-linear fit; capped; 'persistent' if gap barely decays)
and aggregate by segment (family, rung type, entry price, book depth, hour-of-day, city, cushion) to rank
where the window is WIDEST. Output: the segments to prefer, and how much longer their half-life is vs pooled.

Usage: python wx_halflife_segments.py
"""
import json, os, math, statistics as st
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_trackA_results_raw.json")
MINS = [0, 1, 2, 5, 10, 30, 60]
HL_CAP = 60.0   # cap fitted half-life (a barely-decaying gap -> 'persistent', capped here for medians)


def _cushion(rec):
    hi = 0
    for m in (1, 2, 3):
        if rec["cells"].get(f"{m}_3", {}).get("fired"):
            hi = m
    return hi


def half_life(decay):
    """Fit ln(gap(t)) = a - (ln2/HL) t over available t with gap>0. Returns (hl_capped, retention5, retention10,
    still_open5). None if no real initial gap."""
    d = {int(k): v for k, v in decay.items() if v is not None}
    g0 = d.get(0)
    if not g0 or g0 < 0.03:
        return None
    ret5 = (d.get(5, 0.0) / g0) if g0 else 0.0
    ret10 = (d.get(10, 0.0) / g0) if g0 else 0.0
    still5 = 1.0 if d.get(5, 0.0) > 0.5 * g0 else 0.0
    pts = [(t, d[t]) for t in MINS if t in d and d[t] > 0.01]
    if len(pts) < 2:
        hl = HL_CAP if ret5 >= 0.5 else 0.5      # gap gone fast -> tiny HL; gap held -> persistent
        return hl, ret5, ret10, still5
    ts = np.array([p[0] for p in pts], float)
    y = np.log(np.array([p[1] for p in pts], float))
    slope = np.polyfit(ts, y, 1)[0]
    if slope >= -1e-6:
        hl = HL_CAP                              # not decaying -> persistent gap (the good case)
    else:
        hl = min(HL_CAP, math.log(2) / (-slope))
    return hl, ret5, ret10, still5


def load():
    raw = json.load(open(RAW))
    fires = []
    for r in raw:
        c = r["cells"].get("1_3")
        if not c or not c.get("fired") or not c.get("exec_price") or c["exec_price"] >= 0.99:
            continue
        hl = half_life(c.get("decay_gap_by_min", {}))
        if hl is None:
            continue
        hlv, ret5, ret10, still5 = hl
        try:
            hour = int(c["t_star"][11:13])
        except Exception:
            hour = -1
        fires.append({
            "family": r["family"], "station": r["station"], "series": r["series"],
            "rung": r.get("rung_group", "?"), "price": c["exec_price"],
            "vol": c.get("volume_at_exec") or 0.0, "oi": c.get("oi_at_exec") or 0.0,
            "hour": hour, "cushion": _cushion(r),
            "hl": hlv, "ret5": ret5, "ret10": ret10, "still5": still5,
        })
    return fires


def _bucket(v, edges):
    for i, e in enumerate(edges):
        if v < e:
            return i
    return len(edges)


def report_segment(fires, name, keyfn, order=None):
    grp = defaultdict(list)
    for f in fires:
        grp[keyfn(f)].append(f)
    rows = []
    for k, v in grp.items():
        if len(v) < 15:
            continue
        rows.append((k, len(v), st.median([f["hl"] for f in v]),
                     st.mean([f["ret5"] for f in v]), st.mean([f["still5"] for f in v])))
    rows.sort(key=lambda r: -r[2])   # longest median half-life first
    if not rows:
        return
    print(f"\n=== {name} (ranked by median half-life; higher = slower repricing = wider window) ===")
    print(f"{'segment':>22}{'n':>6}{'medHL(min)':>12}{'ret@5':>8}{'open@5%':>9}")
    for k, n, hl, ret5, still in rows:
        print(f"{str(k):>22}{n:>6}{hl:>12.1f}{ret5:>8.2f}{100*still:>8.0f}%")


def main():
    fires = load()
    pooled_hl = st.median([f["hl"] for f in fires])
    print(f"profit-gap half-life segmentation | {len(fires)} deployable fires | POOLED median HL = {pooled_hl:.1f} min")
    print(f"pooled: mean retention@5min = {st.mean([f['ret5'] for f in fires]):.2f}, "
          f"still-open@5min = {100*st.mean([f['still5'] for f in fires]):.0f}%")

    report_segment(fires, "FAMILY", lambda f: f["family"])
    report_segment(fires, "RUNG TYPE", lambda f: f["rung"])
    report_segment(fires, "ENTRY PRICE", lambda f: ["<0.60", "0.60-0.75", "0.75-0.85", "0.85-0.95", "0.95+"][
        _bucket(f["price"], [0.60, 0.75, 0.85, 0.95])])
    report_segment(fires, "BOOK DEPTH (vol@exec)", lambda f: ["<50", "50-200", "200-1k", "1k+"][
        _bucket(f["vol"], [50, 200, 1000])])
    report_segment(fires, "OPEN INTEREST", lambda f: ["<500", "500-2k", "2k-5k", "5k+"][
        _bucket(f["oi"], [500, 2000, 5000])])
    report_segment(fires, "HOUR OF DAY (UTC)", lambda f: f["hour"])
    report_segment(fires, "CUSHION (degF over strike)", lambda f: f["cushion"])
    report_segment(fires, "CITY (station)", lambda f: f["station"])

    # actionable summary: the top persistent segment vs pooled
    print("\nread: prefer high-medHL / high-open@5% segments -- there the gap survives the feed latency, so we "
          "capture more EV per fire and depend less on a 1-min feed. Low-medHL segments are the 'dead on arrival' "
          "fires a slow feed can never catch; deprioritize or require a faster feed for those.")


if __name__ == "__main__":
    main()
