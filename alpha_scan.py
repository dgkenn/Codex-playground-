"""Directional-alpha scan: does any decision-time feature predict the market's ERROR
(resolved_up - token_price), out-of-sample, window-clustered?

Discipline (to avoid the regime-confound traps we keep hitting):
- TARGET = residual = resolved_up - up_mid  (predicting resolved_up itself is trivial: the price
  already does that; alpha is predicting where the PRICE is wrong).
- Unit = window (one obs/window). OOS split by TIME (train early, test late) -- no peeking.
- Report a tradeable read: a maker would SKEW toward the predicted side (fee-free); a taker needs
  the predicted edge to beat the 0.07 fee (~0.0175/sh). We report both.

    python alpha_scan.py
"""
from __future__ import annotations
import glob, json
import numpy as np


def load_windows():
    W = []
    for f in glob.glob("gha_data/ticks_r*.jsonl"):
        for ln in open(f):
            ln = ln.strip()
            if not ln:
                continue
            try:
                w = json.loads(ln)
            except Exception:
                continue
            ts = w.get("ticks") or []
            if len(ts) < 20 or "res_up" not in w:
                continue
            t = np.array([a[0] for a in ts]); mid = np.array([a[1] for a in ts]); sp = np.array([a[2] for a in ts])
            n = len(ts); h = n // 2                      # mid-window snapshot (decision time)
            feats = {
                "ws": w["ws"], "res_up": w["res_up"],
                "up_mid": float(mid[h]),                 # token implied prob at snapshot
                "btc_mom": float((sp[h] - sp[0]) / sp[0]) if sp[0] else 0.0,   # BTC move since open
                "btc_recent": float(sp[h] - sp[max(0, h - 15)]),              # recent ~15-tick BTC move
                "tok_mom": float(mid[h] - mid[0]),       # token move since open (reversion/momentum)
            }
            W.append(feats)
    W.sort(key=lambda r: r["ws"])
    return W


def corr(x, y):
    x = np.array(x); y = np.array(y)
    if x.std() == 0 or y.std() == 0 or len(x) < 4:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def main():
    W = load_windows()
    print(f"settled tick-windows: {len(W)}")
    if len(W) < 12:
        print("too few windows for an OOS directional test (need ~30+); inconclusive."); return
    resid = np.array([w["res_up"] - w["up_mid"] for w in W])   # the market's ERROR (what alpha must predict)
    print(f"mean residual (resolved_up - price) = {resid.mean():+.4f}  (calibration; ~0 = well-priced)\n")
    feats = ["btc_mom", "btc_recent", "tok_mom", "up_mid"]
    print("pooled corr(feature, residual)  [does the feature predict the market's error?]")
    for k in feats:
        print(f"  {k:11}: {corr([w[k] for w in W], resid):+.3f}")

    # OOS: fit sign on train (first 70%), test on last 30%. Strategy: bet the side the feature favors;
    # P&L per window (maker, fee-free) = sign(feat-centered)*residual ; taker subtracts the fee.
    cut = int(len(W) * 0.7)
    tr, te = W[:cut], W[cut:]
    print(f"\nOOS (train {len(tr)} early / test {len(te)} late):")
    print(f"  {'feature':11} {'train corr':>10} {'test corr':>10} {'test maker P&L/win':>18} {'test taker(>fee)':>16}")
    FEE = 0.0175
    for k in feats:
        if k == "up_mid":
            continue
        xtr = np.array([w[k] for w in tr]); rtr = np.array([w["res_up"] - w["up_mid"] for w in tr])
        xte = np.array([w[k] for w in te]); rte = np.array([w["res_up"] - w["up_mid"] for w in te])
        ctr = corr(xtr, rtr); cte = corr(xte, rte)
        thr = np.median(xtr)
        sgn = np.sign(ctr) if ctr == ctr else 0          # direction learned on TRAIN only
        # bet: when feature is above its train-median, go long Up if sgn>0 (etc.); P&L = bet*residual
        bet = sgn * np.sign(xte - thr)
        maker_pnl = float(np.mean(bet * rte)) if len(rte) else float("nan")
        taker_pnl = float(np.mean(bet * rte - np.abs(bet) * FEE)) if len(rte) else float("nan")
        print(f"  {k:11} {ctr:>+10.3f} {cte:>+10.3f} {maker_pnl:>+18.4f} {taker_pnl:>+16.4f}")
    print("\nRead: a candidate needs SAME-SIGN train & test corr AND positive test maker P&L (ideally taker too),")
    print("not just a nice pooled number. n is small -> treat any hit as a hypothesis to confirm live, not proof.")


if __name__ == "__main__":
    main()
