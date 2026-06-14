#!/usr/bin/env python3
"""pmkt_touch_leadlag.py -- TOUCH-DEPTH-aware preliminary lead-lag screen.

Complements pmkt_leadlag.py (which loads up_mid over the FULL history and runs the
HAC incremental regression vs Kalshi). This script focuses on the EXECUTABLE TOUCH
fields (up_tbsz/up_tasz/down_tbsz/down_tasz) that only exist after commit 3098ba4,
to answer two things the older harness ignores:

  (A) CAPACITY: real executable touch-size distribution (contracts and $), vs the
      reward-farm level SUM (up_bsz) -- is Polymarket deep enough for a $100-$10k book?
  (B) TOUCH-WINDOW lead-lag of Polymarket implied prob vs BTC SPOT (the Kalshi settle
      index, read straight from ticks_kalshi_btc15m field[2]), restricted to the period
      where touch data actually exists. Cross-corr + HAC incremental regression.

Spot is taken from Kalshi ticks (field[2]); no external API needed. Single session of
data as of 2026-06-14, so all numbers are IN-SAMPLE / one regime -- screening only.

    python pmkt_touch_leadlag.py [pmkt_glob_dir] [kalshi_ticks_dir]
"""
import sys, gzip, json, glob, os
import numpy as np
from datetime import datetime

STEP = 5  # grid seconds


def load_pmkt_touch(d):
    P = []
    for f in sorted(glob.glob(os.path.join(d, "**", "pmkt_btc_updown_*.jsonl.gz"), recursive=True)):
        for line in gzip.open(f, "rt"):
            if "up_tbsz" not in line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("up_bid") is None or r.get("up_ask") is None:
                continue
            P.append(r)
    return P


def load_spot(d, t0, t1):
    K = []
    for f in glob.glob(os.path.join(d, "ticks_kalshi_btc15m_*.jsonl.gz")):
        for line in gzip.open(f, "rt"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("role") != "up":
                continue
            ws = r["ws"]
            for tk in r.get("ticks", []):
                if tk[2] is None:
                    continue
                ta = ws + tk[0]
                if t0 - 60 <= ta <= t1 + 60:
                    K.append((ta, float(tk[2]), float(tk[3]) if tk[3] is not None else np.nan))
    K.sort()
    return (np.array([x[0] for x in K]), np.array([x[1] for x in K]), np.array([x[2] for x in K]))


def ffill(t, v, grid):
    o = np.full(len(grid), np.nan); j = 0; last = np.nan
    for i, x in enumerate(grid):
        while j < len(t) and t[j] <= x:
            last = v[j]; j += 1
        o[i] = last
    return o


def xcorr(a, b, L):
    out = {}
    for k in range(-L, L + 1):
        if k >= 0:
            x, y = a[:len(a) - k], b[k:]
        else:
            x, y = a[-k:], b[:len(b) + k]
        m = np.isfinite(x) & np.isfinite(y)
        out[k] = float(np.corrcoef(x[m], y[m])[0, 1]) if (m.sum() > 10 and np.std(x[m]) > 0 and np.std(y[m]) > 0) else float("nan")
    return out


def hac(y, X, L=10):
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtXi = np.linalg.pinv(X.T @ X)
    S = e[:, None] * X
    meat = S.T @ S
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = S[l:].T @ S[:-l]
        meat += w * (G + G.T)
    cov = XtXi @ meat @ XtXi
    se = np.sqrt(np.diag(cov))
    ss = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (e @ e) / ss if ss > 0 else float("nan")
    return b, b / se, r2


def main():
    pdir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pmdata"
    kdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/kdata"
    P = load_pmkt_touch(pdir)
    if not P:
        print("NO touch records (need data after commit 3098ba4).")
        return
    pt = np.array([r["t"] for r in P])
    slugs = sorted(set(r["slug"] for r in P))
    t0, t1 = pt.min(), pt.max()

    print("=" * 66)
    print("A. CAPACITY -- executable touch depth")
    print("=" * 66)
    print("touch snapshots=%d  windows=%d  span=%.2fh  days=%s" % (
        len(P), len(slugs), (t1 - t0) / 3600,
        sorted(set(datetime.utcfromtimestamp(t).date().isoformat() for t in pt))))
    gaps = np.diff(np.sort(pt))
    print("median poll gap=%.2fs  gaps>30s=%d (continuity within session)" % (np.median(gaps), int((gaps > 30).sum())))
    tb = np.array([r["up_tbsz"] for r in P]); ta = np.array([r["up_tasz"] for r in P])
    dtb = np.array([r["down_tbsz"] for r in P]); dta = np.array([r["down_tasz"] for r in P])
    allt = np.concatenate([tb, ta, dtb, dta]); allt = allt[allt > 0]
    prob = np.array([(r["up_bid"] + r["up_ask"]) / 2 for r in P])
    sumb = np.array([r["up_bsz"] for r in P])
    print("touch size (contracts) pooled, >0  n=%d : p05=%.0f p25=%.0f p50=%.0f p75=%.0f p95=%.0f p99=%.0f max=%.0f" % (
        len(allt), *[np.percentile(allt, p) for p in (5, 25, 50, 75, 95, 99)], allt.max()))
    dollar = np.concatenate([ta * prob, dta * (1 - prob)]); dollar = dollar[dollar > 0]
    print("executable $ to lift ask touch: median=$%.0f p95=$%.0f max=$%.0f" % (
        np.median(dollar), np.percentile(dollar, 95), dollar.max()))
    print("level-SUM up_bsz median=%.0f -> touch is ~%.0fx smaller than the reward-farm sum" % (
        np.median(sumb), np.median(sumb) / max(np.median(tb[tb > 0]), 1)))
    print("spread mean=%.1f cents  prob mean=%.3f sd=%.3f" % (
        100 * np.mean([r["up_ask"] - r["up_bid"] for r in P]), prob.mean(), prob.std()))

    # ---- B. touch-window lead-lag vs spot ----
    st, ssp, smid = load_spot(kdir, t0, t1)
    grid = np.arange(t0, t1, STEP)
    pg = ffill(pt, prob, grid)
    sg = ffill(st, ssp, grid)
    m = np.isfinite(pg) & np.isfinite(sg)
    print("\n" + "=" * 66)
    print("B. LEAD-LAG -- Polymarket prob vs BTC spot (touch window only)")
    print("=" * 66)
    print("grid pts=%d valid=%d  spot ticks=%d" % (len(grid), int(m.sum()), len(st)))
    dp = np.diff(pg); sr = np.diff(sg) / sg[:-1]
    vm = m[1:] & m[:-1]
    dp = np.where(vm, dp, np.nan); sr = np.where(vm, sr, np.nan)
    xc = xcorr(dp, sr, 6)
    print("xcorr(poly_dprob[t], spot_ret[t+k])  k>0 => POLY LEADS spot (5s steps):")
    for k in sorted(xc):
        print("  %+4ds: %s" % (k * STEP, ("%.3f" % xc[k]) if np.isfinite(xc[k]) else "nan"))

    print("\n" + "=" * 66)
    print("C. INCREMENTAL -- next-move spot ~ spot_mom + poly_dev + poly_dmom (HAC)")
    print("=" * 66)
    for H in (1, 2, 6):
        n = len(sg)
        fut = np.full(n, np.nan); fut[:-H] = (sg[H:] - sg[:-H]) / sg[:-H]
        mom = np.full(n, np.nan); mom[H:] = (sg[H:] - sg[:-H]) / sg[:-H]
        pdev = pg - 0.5
        pmom = np.full(n, np.nan); pmom[1:] = np.diff(pg)
        mm = m & np.isfinite(fut) & np.isfinite(mom) & np.isfinite(pmom)
        X = np.column_stack([np.ones(int(mm.sum())), mom[mm], pdev[mm], pmom[mm]])
        b, t, r2 = hac(fut[mm], X, L=10)
        print("H=%d (%ds ahead) n=%d R2=%.4f  HAC t: spot_mom=%+.2f poly_dev=%+.2f poly_dmom=%+.2f" % (
            H, H * STEP, int(mm.sum()), r2, t[1], t[2], t[3]))
    print("\nCAVEAT: single ~2.1h session, 26 windows, one regime, IN-SAMPLE. Autocorrelated")
    print("5s grid; HAC mitigates but cannot create independent N. Treat as a screen only.")


if __name__ == "__main__":
    main()
