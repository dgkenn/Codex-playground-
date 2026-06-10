"""metrics_hypo.py -- test the hypotheses METRICS.md generates, on the full fill tape.

METRICS.md (extended battery, insight 4) says: "Inventory drives drawdown -- av_stoikov (most
inventory) has the worst Ulcer/TUW; the tight-inventory gates the lowest. The fix is TIGHT INVENTORY."
And the OOS leaderboard's #2 Calmar is micro_skew15 (165) -- the tight-skew treatment was never
combined with the deployed ufat gate. ufat_band's 5x drawdown (Calmar 3.9 vs 8.8) is directional
tail inventory -- the hedge was refuted as a fix; tight skew is the remaining candidate.

H1: ufat + tighter inventory skew  -> higher Calmar at small net cost (better risk-adjusted than ufat).
H2: ufat_band + tighter skew       -> tames the drawdown that made it lose the risk-adjusted contest.
H3: regime filter (PAST-window spot vol; honest) -> skip the most volatile quartile of windows.

Method: sequential REPLAY of the baseline tape per (asset,ws): walk fills in time order, track
Up-equivalent inventory d; a fill on side `dir` is BLOCKED when dir*d >= skew_lim (the same rule the
engine's skew_block applies at 12.5 = 0.25*cap), kept fills update d and score mo_res*sz + rebate.
This approximates mechanics (a dropped fill can't change others' queue), the same approximation class
as every keep/drop study here -- so winners get wired as SHADOW A/B variants, not silent defaults.

Protocol: folds A+B select, untouched holdout C confirms; paired per-window tests vs ufat @ skew 12.5;
full risk lens (net, MDD, Calmar, max|inventory|).   python metrics_hypo.py
"""
from __future__ import annotations

import glob
import json
import re
from collections import defaultdict

import numpy as np
from dataio import jl_glob, jl_open

try:
    import fees
    REB = lambda p: float(fees.maker_rebate(p, rate=0.07))
except Exception:
    REB = lambda p: 0.25 * 0.07 * p * (1 - p)
MICRO_MARGIN = 0.002


def load():
    """Baseline fills grouped per (asset, ws), time-ordered; plus a per-(asset,ws) PAST-window
    realized spot vol (honest regime feature: the PREVIOUS window's vol, known at window open)."""
    fills = defaultdict(list)
    spot_obs = defaultdict(list)                 # (asset, ws) -> [spot...] for vol
    for fp in jl_glob("gha_data/fills_*.jsonl"):
        m = re.search(r"fills_([a-z]+)\d+m_", fp)
        asset = m.group(1) if m else "btc"
        for ln in jl_open(fp):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("spot") and r.get("ws"):
                spot_obs[(asset, r["ws"])].append((r.get("t", 0), r["spot"]))
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("mo_res") is not None:
                fills[(asset, r["ws"])].append(r)
    for k in fills:
        fills[k].sort(key=lambda r: r.get("t", 0))
    vol = {}
    for (asset, ws), pts in spot_obs.items():
        pts.sort()
        px = np.array([s for _, s in pts], dtype=float)
        if len(px) >= 10 and px[0] > 0:
            lr = np.diff(np.log(px))
            vol[(asset, ws)] = float(np.std(lr) * np.sqrt(len(lr)))   # window-total log-vol proxy
    prev_vol = {}
    for (asset, ws) in fills:
        pv = vol.get((asset, ws - 900))
        prev_vol[(asset, ws)] = pv               # None = unknown -> never filtered (honest default)
    return fills, prev_vol, vol


def tox(r):
    t = r.get("tox")
    if t is not None:
        return t
    mp = r.get("micro")
    return 0.0 if mp is None else ((mp - r["p"]) if r["side"] == "ASK" else (r["p"] - mp))


def gate_ufat(r):
    m = r.get("mid") or r["p"]
    return tox(r) <= MICRO_MARGIN * 4.0 * m * (1 - m)


def gate_band(r):
    m = r.get("mid") or r["p"]
    return gate_ufat(r) and not (0.30 <= m < 0.55)


def fill_dir(r):
    """+1 = gains Up-equivalent exposure (BUY up / SELL down), -1 = the reverse."""
    return 1.0 if ((r["side"] == "BID") == bool(r.get("up", 1))) else -1.0


def replay_window(rows, gate, skew_lim):
    """Sequential skew-constrained replay. Returns (net, max_abs_delta)."""
    d = 0.0; net = 0.0; mx = 0.0
    for r in rows:
        if not gate(r):
            continue
        di = fill_dir(r)
        if di * d >= skew_lim:                   # the engine's skew_block rule, tighter limit
            continue
        d += di * r["sz"]
        mx = max(mx, abs(d))
        net += r["mo_res"] * r["sz"] + REB(r["p"]) * r["sz"]
    return net, mx


def calmar(nets):
    cum = np.cumsum(nets)
    mdd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0
    tot = float(cum[-1]) if len(cum) else 0.0
    return (tot / mdd) if mdd > 1e-9 else (float("inf") if tot > 0 else 0.0), mdd


def paired_t(d):
    d = np.asarray(d, dtype=float)
    if len(d) < 5 or d.std(ddof=1) == 0:
        return float("nan")
    return float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))))


def main():
    fills, prev_vol, vol = load()
    keys = sorted(fills, key=lambda k: (k[1], k[0]))          # time-ordered (ws, asset)
    uniq_ws = sorted({ws for _, ws in keys})
    ca, cb = uniq_ws[int(len(uniq_ws) * 0.4)], uniq_ws[int(len(uniq_ws) * 0.7)]
    sel = [k for k in keys if k[1] < cb]                      # folds A+B
    hold = [k for k in keys if k[1] >= cb]                    # holdout C
    print(f"{sum(len(v) for v in fills.values())} fills | {len(keys)} (asset,ws) windows | "
          f"select={len(sel)} holdout={len(hold)}\n")

    vq = np.percentile([v for v in vol.values()], 75) if vol else float("inf")

    def evaluate(gate, skew_lim, regime=False, label=""):
        nets = {}
        mxs = []
        for k in keys:
            if regime and prev_vol.get(k) is not None and prev_vol[k] > vq:
                nets[k] = 0.0                                  # sat out the volatile window
                continue
            n, mx = replay_window(fills[k], gate, skew_lim)
            nets[k] = n; mxs.append(mx)
        s = np.array([nets[k] for k in sel]); h = np.array([nets[k] for k in hold])
        cal_s, mdd_s = calmar(s); cal_h, mdd_h = calmar(h)
        return {"label": label, "nets": nets,
                "sel_net": s.mean(), "sel_cal": cal_s, "sel_mdd": mdd_s,
                "hold_net": h.mean(), "hold_cal": cal_h, "hold_mdd": mdd_h,
                "max_inv": (np.mean(mxs) if mxs else 0.0)}

    ref = evaluate(gate_ufat, 12.5, label="ufat skew12.5 (deployed)")
    grid = []
    for skew in (12.5, 10.0, 7.5, 5.0, 2.5):
        grid.append(evaluate(gate_ufat, skew, label=f"ufat skew{skew:g}"))
        grid.append(evaluate(gate_band, skew, label=f"ufat_band skew{skew:g}"))
    grid.append(evaluate(gate_ufat, 12.5, regime=True, label="ufat + calm-regime (prev-win vol<p75)"))

    print(f"{'config':>38} | {'SEL net/w':>9} {'SEL Cal':>8} {'MDD':>6} | "
          f"{'HOLD net/w':>10} {'HOLD Cal':>8} {'MDD':>6} | {'pairT(hold)':>11} {'avg max|inv|':>12}")
    print("-" * 124)
    for g in grid:
        d_hold = np.array([g["nets"][k] - ref["nets"][k] for k in hold])
        pt = paired_t(d_hold)
        tag = " <-- ref" if g["label"].endswith("(deployed)") else ""
        print(f"{g['label']:>38} | {g['sel_net']:>+9.2f} {g['sel_cal']:>8.1f} {g['sel_mdd']:>6.0f} | "
              f"{g['hold_net']:>+10.2f} {g['hold_cal']:>8.1f} {g['hold_mdd']:>6.0f} | "
              f"{pt:>+11.1f} {g['max_inv']:>12.1f}{tag}")

    print("\nRead: H1/H2 hold only if a tighter-skew row beats the ref on HOLDOUT Calmar without a")
    print("meaningful net give-up (paired t on net shows the cost); H3 holds only if the regime row's")
    print("holdout Calmar beats ref. Winners get wired as SHADOW A/B variants (this replay approximates")
    print("queue mechanics; prospective confirmation before any deployed-default change).")


if __name__ == "__main__":
    main()
