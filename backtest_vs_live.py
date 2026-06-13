"""backtest_vs_live.py -- SCREEN (NOT a deploy certificate).

Scores every TRIAL on the deep historical BTC tape vs BOTH P0 and live_current, split IS(first 60%)
/ OOS(last 40%), reusing box_policy_ab's REAL window_fills + TRIALS (no reimplementation).

CRITICAL CAVEAT: these trials were data-mined from this same historical tape, so the IN-SAMPLE
t-stat is inflated by selection bias (t02 was +2.79 in-sample/early then COLLAPSED to +0.09 forward).
So:
  * tL_IS  (vs live, in-sample)      -> mostly overfit; a high value alone means nothing.
  * tL_OOS (vs live, out-of-sample)  -> the trustworthy signal: ranks which trials are worth the
                                        forward wait. Still NOT the deploy bar (forward data decides).
A trial with tL_IS high but tL_OOS low is the overfit signature -- skip it. A trial strong on
tL_OOS is a promote-soon candidate to confirm on forward data, not an auto-deploy.
"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
import numpy as np
import pandas as pd
import box_policy_ab as B

h = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
t = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")
common = sorted(set(h.index) & set(t.index))
nodepth = np.full(15, np.nan)

rows = []
for ws in common:
    hr = h.loc[ws]; tr = t.loc[ws]
    bid = np.asarray(hr["bid_path"], float); ask = np.asarray(hr["ask_path"], float)
    spot = np.asarray(hr["spot_path"], float); res = int(hr["res_up"])
    tape = (np.asarray(tr["t"], float), np.asarray(tr["p"], float),
            np.asarray(tr["sz"], float), np.asarray(tr["buy"]).astype(bool))
    try:
        fills = B.window_fills(ws, res, bid, ask, spot, nodepth, tape)
    except Exception:
        continue
    if not fills:
        continue
    td = {}
    for name, fn in B.TRIALS.items():
        try:
            td[name] = fn(fills)
        except Exception:
            td[name] = np.nan
    rows.append({"ws": ws, "p0": B.pol_p0(fills), "trials": td})

rows.sort(key=lambda r: r["ws"])
n = len(rows); cut = int(n * 0.6)
ism = np.arange(n) < cut; oosm = ~ism
p0 = np.array([r["p0"] for r in rows])
live = np.array([r["trials"].get("live_current", np.nan) for r in rows])


def col(name):
    return np.array([r["trials"].get(name, np.nan) for r in rows])


def tt(a, b, mask):
    m = mask & ~np.isnan(a) & ~np.isnan(b)
    if m.sum() < 8:
        return float("nan"), int(m.sum()), float("nan")
    d = a[m] - b[m]
    return B.tstat(d), int(m.sum()), d.mean() * 100.0


print(f"windows={n} (IS {cut} / OOS {n - cut})  |  baseline live_current = P0 + t36")
print("SCREEN ONLY -- trials mined from this tape; tL_OOS ranks 'worth the forward wait', NOT deploy.\n")
res = []
for name in sorted(B.TRIALS):
    if name == "live_current":
        continue
    a = col(name)
    tLo, no, eLo = tt(a, live, oosm)
    tLi, _, _ = tt(a, live, ism)
    tPo, _, _ = tt(a, p0, oosm)
    res.append((name, tLo, eLo, tLi, tPo, no))
res.sort(key=lambda x: -(x[1] if not np.isnan(x[1]) else -99))
print(f"{'trial':<26}{'tL_OOS':>8}{'eL_OOS c':>10}{'tL_IS':>8}{'tP0_OOS':>9}{'nOOS':>6}  flag")
for name, tLo, eLo, tLi, tPo, no in res:
    flag = ""
    if not np.isnan(tLi) and not np.isnan(tLo):
        if tLi > 2 and tLo < 1:
            flag = "OVERFIT (IS-only)"
        elif tLo > 2 and eLo > 0:
            flag = "OOS-robust -> watch fwd"
    print(f"{name:<26}{tLo:>+8.2f}{eLo:>+10.3f}{tLi:>+8.2f}{tPo:>+9.2f}{no:>6}  {flag}")
