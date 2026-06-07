"""Gate on ROADMAP #4 (reviewer's challenge): the frictionless hedge harvested a +$7/window
adverse-selection DRIFT with perfect hindsight of the within-window path. Predictive
repricing can only capture it if that drift is PREDICTABLE FROM QUOTE-TIME-OBSERVABLE
features -- a perfect hedge harvesting a drift != a model forecasting it.

Per fill, the directional P&L its added exposure incurs to resolution (what the hedge removes):
    drift_i = maker_d_delta_i * (resolved_up - p_up_at_fill_i)        (Up-equiv units)
maker_d_delta: taker BUY of a token => maker SELLS it. drift<0 = adverse (the move went
against the exposure the fill added). Question: do quote-time features
    {fair_edge, BTC momentum over prior 30s, tau, signed size}
predict drift_i's sign? If corr ~0.02 (like the retired fill-selection signal), #4 inherits
the same weak-signal problem and captures ~0 of the $2k ceiling.

    python drift_predict.py
"""
from __future__ import annotations

import numpy as np

from fairvalue import fair_up, realized_vol_per_s
from fv_analysis import load_spot, load_trades


def main():
    ts_ms, px = load_spot(); sigma = realized_vol_per_s(px, 1.0)
    allt = load_trades()
    win = allt.win.to_numpy(); t_ms = allt.t_ms.to_numpy(np.int64)
    tok_u = (allt.tok.to_numpy() == "U"); sells = (allt.side.to_numpy() == "BUY")
    price = allt.price.to_numpy(float); size = allt["size"].to_numpy(float)
    res = allt.res.to_numpy(float); wend = allt.wend.to_numpy(float)

    s0 = px[np.clip(np.searchsorted(ts_ms, win.astype(np.int64) * 1000, "right") - 1, 0, len(px) - 1)]
    st = px[np.clip(np.searchsorted(ts_ms, t_ms, "right") - 1, 0, len(px) - 1)]
    st_30 = px[np.clip(np.searchsorted(ts_ms, t_ms - 30_000, "right") - 1, 0, len(px) - 1)]
    tau = np.maximum(wend - t_ms / 1000.0, 0.0)
    keep = (tau > 0) & (tau <= 900)
    fu = fair_up(st, s0, sigma, np.maximum(tau, 1.0))
    fair_tok = np.where(tok_u, fu, 1.0 - fu)

    # maker exposure added by the fill (Up-equivalent), and its drift to resolution
    d_delta = np.where(tok_u, np.where(sells, -size, size), np.where(sells, size, -size))
    drift = d_delta * (res - fu)                                  # >0 favorable, <0 adverse

    # quote-time-observable features
    fair_edge = np.where(sells, price - fair_tok, fair_tok - price)
    momentum = np.log(st / st_30)                                 # BTC 30s return
    # NOTE: only EXOGENOUS quote-time predictors -- a forecast a repricing model could act on.
    # signed_size (=d_delta) is excluded: drift is defined proportional to it, so it would
    # inflate R^2 mechanically (it's the position, not a forecast).
    feats = {"fair_edge": fair_edge, "momentum30s": momentum, "tau": tau}

    m = keep & np.isfinite(drift) & np.isfinite(momentum)
    drift = drift[m]
    print(f"fills={m.sum():,}  mean drift={drift.mean():+.5f}/fill "
          f"(sum={drift.sum():+,.0f} ~ the hedge's frictionless harvest)  std={drift.std():.4f}")
    print("\n[quote-time predictability of per-fill drift]  corr ~0.02 => unpredictable => #4 ~useless")
    print(f"  {'feature':>14} {'corr(feat,drift)':>17} {'sign-agree%':>12}")
    X = []
    for name, f in feats.items():
        f = f[m]
        c = np.corrcoef(f, drift)[0, 1]
        # sign agreement of a 1-feature predictor (does sign(feat-centered) match sign(drift)?)
        fc = f - np.median(f)
        agree = np.mean(np.sign(fc) == np.sign(drift))
        print(f"  {name:>14} {c:>17.4f} {agree:>11.1%}")
        X.append((f - f.mean()) / (f.std() + 1e-12))
    # multivariate OLS R^2 (best linear quote-time predictor)
    X = np.column_stack([np.ones(m.sum())] + X)
    y = drift
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    ss_res = np.sum((y - yhat) ** 2); ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    # clean monotonicity check: mean drift in the top vs bottom decile of the OLS prediction.
    # if the predictor worked, top-decile drift >> bottom-decile drift.
    q = np.argsort(yhat); n = len(yhat); dlo = y[q[:n // 10]].mean(); dhi = y[q[-n // 10:]].mean()
    print(f"\n  multivariate OLS R^2 = {r2:.4f}  (best quote-time linear predictor of drift)")
    print(f"  corr(OLS prediction, drift) = {np.corrcoef(yhat, y)[0,1]:.4f}")
    print(f"  mean drift: bottom-pred-decile={dlo:+.4f}  top-pred-decile={dhi:+.4f}  "
          f"(spread={dhi-dlo:+.4f}; ~0 => no usable separation)")
    print("\nVERDICT gate for #4: R^2~0 and corr~0 => the drift is NOT quote-time PREDICTABLE, so "
          "#4 cannot PRE-POSITION against it (inherits the weak-signal problem that retired "
          "fill-selection). #4's only remaining channel is the LATENCY RACE -- react to a "
          "CONTEMPORANEOUS spot move faster than the taker (not a forecast) -- which only the live "
          "reprice_log can score, against a <=$2k ceiling and the queue-position cost of cancelling.")


if __name__ == "__main__":
    main()
