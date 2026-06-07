"""TIER 1 confirmatory test (pre-registered, one shot, in the CAPPED real strategy).

fv_analysis.py (uncapped per-fill discriminator) showed the spot fair value is only
adversely predictive in ONE regime: EXTREME edge AND NEAR expiry (decile 0, fair_edge
< ~-0.10, settles -0.027/sh). Mid-window moderate-edge fills mean-revert and settle
positive, so a flat gate cuts good flow. Theory agrees (Chakraborty-Kearns: a passive
maker is long within-window mean reversion; adverse selection bites only when the move
is INFORMATIVE -- i.e. late, when little time remains to revert).

PRE-REGISTERED RULE (no further tuning): in the capped inventory-skew maker, SKIP a
fill only if  fair_edge < -E_X  AND  tau < TAU_X.  E_X=0.10, TAU_X=120s, chosen from the
decile-0 boundary, NOT swept. Metric: per-window $ P&L (capped) -> window Sharpe (mean/
std over n windows, FIXED regardless of skips, so no n-reduction tax). Report IS/OOS
halves. Accept the result either way; if it does not beat baseline OOS, retire gating
and keep fair value for live predictive-repricing / sizing only.

    python fv_confirm.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import fees
from fairvalue import fair_up, realized_vol_per_s
from fv_analysis import load_spot, load_trades, build

REBATE_RATE = 0.07
E_X, TAU_X = 0.10, 120.0


def capped_window_pnl(allt, ts_ms, px, sigma, cap, skip_adverse):
    """Sequential capped 2-sided maker per window; returns {win: abs $ P&L}.
    skip_adverse=True applies the pre-registered near-expiry extreme-edge skip."""
    win = allt.win.to_numpy(); t_ms = allt.t_ms.to_numpy(np.int64)
    tok_u = (allt.tok.to_numpy() == "U"); sells = (allt.side.to_numpy() == "BUY")
    price = allt.price.to_numpy(float); size = allt["size"].to_numpy(float)
    res = allt.res.to_numpy(float); wend = allt.wend.to_numpy(float)
    s0 = px[np.clip(np.searchsorted(ts_ms, win.astype(np.int64) * 1000, "right") - 1, 0, len(px) - 1)]
    st = px[np.clip(np.searchsorted(ts_ms, t_ms, "right") - 1, 0, len(px) - 1)]
    tau = np.maximum(wend - t_ms / 1000.0, 0.0)
    fu = fair_up(st, s0, sigma, tau)
    fair_tok = np.where(tok_u, fu, 1.0 - fu)
    fair_edge = np.where(sells, price - fair_tok, fair_tok - price)
    # cap is PATH-DEPENDENT: must replay fills in (window, time) order, not file order.
    order = np.lexsort((t_ms, win))
    out = {}
    cur = None; delta = cash = reb = up_inv = dn_inv = 0.0; r = 0.0
    for i in order:
        w = win[i]
        if w != cur:
            if cur is not None:
                out[cur] = cash + up_inv * r + dn_inv * (1 - r) + reb
            cur = w; delta = cash = reb = up_inv = dn_inv = 0.0; r = res[i]
            if not (0 <= tau[i] <= 900) and tau[i] > 900:
                pass
        if not (0 <= tau[i] <= 900):
            continue
        if skip_adverse and fair_edge[i] < -E_X and tau[i] < TAU_X:
            continue
        sz = size[i]
        if tok_u[i]:
            d_delta = -sz if sells[i] else sz
        else:
            d_delta = sz if sells[i] else -sz
        if abs(delta + d_delta) > cap:
            room = max(0.0, cap - abs(delta)) if (delta + d_delta) * d_delta > 0 else sz
            fill = min(sz, room)
        else:
            fill = sz
        if fill <= 0:
            continue
        sign = 1.0 if sells[i] else -1.0
        cash += sign * price[i] * fill
        if tok_u[i]:
            up_inv += (-fill if sells[i] else fill)
        else:
            dn_inv += (-fill if sells[i] else fill)
        delta += (d_delta / sz) * fill
        reb += fees.maker_rebate(price[i], rate=REBATE_RATE) * fill
    if cur is not None:
        out[cur] = cash + up_inv * r + dn_inv * (1 - r) + reb
    return out


def sh(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    m, s = a.mean(), a.std(ddof=1)
    return len(a), m, s, (m / s if s > 0 else np.nan)


def line(tag, pnl_by_win, wins):
    a = np.array([pnl_by_win[w] for w in wins if w in pnl_by_win])
    n, m, s, S = sh(a)
    print(f"    {tag:24}: windows={n} mean=${m:+.3f}/win std={s:.3f} Sharpe={S:+.3f} total=${a.sum():+,.0f}")
    return S


def main():
    ts_ms, px = load_spot(); sigma = realized_vol_per_s(px, 1.0)
    allt = load_trades()
    wins = sorted(allt.win.unique()); med = np.median(wins)
    IS = [w for w in wins if w < med]; OOS = [w for w in wins if w >= med]
    print(f"pre-registered: skip if fair_edge<-{E_X} AND tau<{TAU_X}s | windows={len(wins)} "
          f"IS={len(IS)} OOS={len(OOS)}  (capped real strategy)")
    for cap in [50, 100]:
        print(f"cap={cap}")
        base = capped_window_pnl(allt, ts_ms, px, sigma, cap, skip_adverse=False)
        adv = capped_window_pnl(allt, ts_ms, px, sigma, cap, skip_adverse=True)
        print("  ALL:")
        b = line("baseline", base, wins); g = line("near-expiry skip", adv, wins)
        print("  IS:"); line("baseline", base, IS); line("near-expiry skip", adv, IS)
        print("  OOS:"); bo = line("baseline", base, OOS); go = line("near-expiry skip", adv, OOS)
        print(f"  -> verdict cap={cap}: OOS Sharpe {bo:+.3f} -> {go:+.3f} "
              f"({'IMPROVES' if go > bo else 'no improvement'})")


if __name__ == "__main__":
    main()
