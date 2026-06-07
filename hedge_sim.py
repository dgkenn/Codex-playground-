"""ROADMAP #1: delta-hedge the maker's residual inventory with a BTC perp.

Thesis: edge is per-share -> P&L is volume-bound; the brake on raising the inventory cap is
the directional variance of leftover inventory held to a binary resolution. Our event is a
function of a TRADABLE underlying, so we *can* delta-hedge -- IF the variance is directional
and hedgeable. This backtests it on btc.npz + the trade tape, window-Sharpe (n FIXED).

THE INSTRUMENT FIGHTS BACK (this is theory, not a bug): a binary's gamma DIVERGES at expiry.
As sigma*sqrt(tau)->0 the spot->prob map becomes a vertical wall; a few-$ BTC wiggle flips the
target delta across its whole range, so naive continuous hedging rebalances thousands of times
chasing a singularity (the first cut's $276k perp fees = the math working as designed). A
binary cannot be dynamically replicated near resolution -- discrete hedging of a discontinuous
payoff has IRREDUCIBLE variance there, no friction needed (market incompleteness). So:

ARMS (all on the SKEWED skew=0.25 position the live strategy actually carries):
  (A) no hedge                          -- baseline; MUST reproduce the known capped P&L
  (B) hedge everything (tau_freeze=0)   -- the divergent disaster, for contrast
  (C) hedge mid-window, FREEZE the hedge in the final tau_freeze s -- swept; let the small
      binary residual ride to settlement (cap already keeps it small)
each in FRICTIONLESS (continuous, no fee -- upper bound) and PRACTICAL (band + perp fee +
funding) form. Also run the surface on the NO-SKEW book, where directional variance exists,
to expose the reducible-mid / irreducible-tail structure the gamma theory predicts.

PRE-REGISTERED PREDICTION: on the already-skewed book NO tau_freeze beats no-hedge -- skew has
already harvested the mid-window directional variance (no-skew frictionless cut std only 0.6%
@cap50). The hedge's domain opens only if skew is removed, and then ideal-hedge merely recovers
the skewed baseline. Expect: skew DOMINATES hedging at this scale; the hedge is irreducibly
useless near expiry and (on the skewed book) redundant mid-window.

    python hedge_sim.py
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

import fees
from fairvalue import realized_vol_per_s
from fv_analysis import load_spot, load_trades

REBATE_RATE = 0.07
PERP_FEE_BPS = 4.0            # perp taker fee per rebalance leg (~Hyperliquid/Binance)
FUND_BPS_8H = 1.0            # perp funding ~0.01%/8h (negligible at a 15m hold; included for honesty)
BAND_NOTIONAL = 25.0        # $ move in target before we rebalance the perp
TAU_DENOM_FLOOR = 1.0       # s; only to keep the delta formula finite, NOT a hedge freeze


def replay(g, cap, skew_frac):
    """Capped 2-sided maker over one window's (time-sorted) fills. skew_frac<1 = deployed
    inventory skew (refuse the leaning side past skew_frac*cap); >=1 = no skew."""
    tok = g["tok"]; side = g["side"]; price = g["price"]; size = g["size"]; t_ms = g["t_ms"]
    delta = cash = reb = up_inv = dn_inv = 0.0
    skew = skew_frac * cap
    ts, ups, dns = [], [], []
    for i in range(len(price)):
        is_up = (tok[i] == "U"); sells = (side[i] == "BUY"); sz = size[i]
        d_delta = (-sz if sells else sz) if is_up else (sz if sells else -sz)
        if abs(delta) >= skew and delta * d_delta > 0:
            ts.append(t_ms[i]); ups.append(up_inv); dns.append(dn_inv); continue
        if abs(delta + d_delta) > cap:
            room = max(0.0, cap - abs(delta)) if (delta + d_delta) * d_delta > 0 else sz
            fill = min(sz, room)
        else:
            fill = sz
        if fill <= 0:
            ts.append(t_ms[i]); ups.append(up_inv); dns.append(dn_inv); continue
        sign = 1.0 if sells else -1.0
        cash += sign * price[i] * fill
        if is_up:
            up_inv += (-fill if sells else fill)
        else:
            dn_inv += (-fill if sells else fill)
        delta += (d_delta / sz) * fill
        reb += fees.maker_rebate(price[i], rate=REBATE_RATE) * fill
        ts.append(t_ms[i]); ups.append(up_inv); dns.append(dn_inv)
    return cash, reb, ts, ups, dns, up_inv, dn_inv


def window_targets(ws, wend, s0, fill_t_ms, up_traj, dn_traj, ts_ms, px, sigma):
    """Per-second causal target perp holding (BTC) and the spot path. target_k uses spot_k;
    P&L over [k,k+1] = H_k * (spot_{k+1}-spot_k)  (no peeking)."""
    lo = np.searchsorted(ts_ms, ws * 1000, "left"); hi = np.searchsorted(ts_ms, wend * 1000, "right")
    if hi - lo < 2:
        return None
    spot = px[lo:hi]; st_ms = ts_ms[lo:hi]
    ft = np.asarray(fill_t_ms, dtype=np.int64)
    idx = np.searchsorted(ft, st_ms, "right") - 1
    up = np.where(idx >= 0, np.asarray(up_traj)[np.clip(idx, 0, len(up_traj) - 1)], 0.0)
    dn = np.where(idx >= 0, np.asarray(dn_traj)[np.clip(idx, 0, len(dn_traj) - 1)], 0.0)
    tau = wend - st_ms / 1000.0
    denom = sigma * np.sqrt(np.maximum(tau, TAU_DENOM_FLOOR))
    z = np.log(spot / s0) / denom
    target = -(up - dn) * norm.pdf(z) / (spot * denom)          # delta = up - dn
    return spot, tau, target


def apply_hedge(spot, tau, target, tau_freeze, band, fee_bps):
    """Return (ideal_pnl, practical_pnl, perp_fee, n_rebal). Freeze (target=0) inside
    tau_freeze s of expiry. ideal = frictionless continuous; practical = band+fee+funding."""
    t = np.where(tau >= tau_freeze, target, 0.0)
    dS = np.diff(spot)
    ideal = float(np.sum(t[:-1] * dS))
    H = 0.0; prac = 0.0; fee = 0.0; n = 0; fund = 0.0
    per_s_fund = FUND_BPS_8H / 1e4 / (8 * 3600)
    for k in range(len(spot) - 1):
        if abs(t[k] - H) * spot[k] > band:
            fee += abs(t[k] - H) * spot[k] * fee_bps / 1e4; H = t[k]; n += 1
        prac += H * dS[k]
        fund += abs(H) * spot[k] * per_s_fund
    return ideal, prac - fund, fee, n


def sh(a):
    a = np.asarray(a, float); m, s = a.mean(), a.std(ddof=1)
    return (m / s if s > 0 else np.nan), m, s


def main():
    ts_ms, px = load_spot(); sigma = realized_vol_per_s(px, 1.0)
    allt = load_trades().sort_values(["win", "t_ms"])
    res = dict(zip(allt.win, allt.res)); wend = dict(zip(allt.win, allt.wend))
    cols = {c: allt[c].to_numpy() for c in ("win", "tok", "side", "price", "size", "t_ms")}
    wins = allt.win.to_numpy(); order = np.arange(len(wins))
    bounds = {w: (order[wins == w][0], order[wins == w][-1] + 1) for w in np.unique(wins)}
    print(f"windows={len(bounds)} sigma={sigma:.3e} | perp_fee={PERP_FEE_BPS}bps "
          f"band=${BAND_NOTIONAL} funding={FUND_BPS_8H}bps/8h")

    def precompute(cap, skew_frac):
        wd = []
        for w, (a, b) in bounds.items():
            g = {k: cols[k][a:b] for k in cols}
            cash, reb, ts, ups, dns, upf, dnf = replay(g, cap, skew_frac)
            r = res[w]; maker = cash + upf * r + dnf * (1 - r) + reb
            s0 = float(px[np.clip(np.searchsorted(ts_ms, int(w) * 1000, "right") - 1, 0, len(px) - 1)])
            tg = window_targets(int(w), int(wend[w]), s0, ts, ups, dns, ts_ms, px, sigma)
            wd.append((maker, tg))
        return wd

    def arm(wd, tau_freeze):
        unh, idl, prc, ftot, rebs = [], [], [], 0.0, []
        for maker, tg in wd:
            if tg is None:
                unh.append(maker); idl.append(maker); prc.append(maker); continue
            spot, tau, target = tg
            ip, pp, fee, n = apply_hedge(spot, tau, target, tau_freeze, BAND_NOTIONAL, PERP_FEE_BPS)
            unh.append(maker); idl.append(maker + ip); prc.append(maker + pp - fee)
            ftot += fee; rebs.append(n)
        return unh, idl, prc, ftot, np.array(rebs)

    for skew_frac, label in [(0.25, "SKEWED (deployed skew=0.25)"), (1e9, "NO-SKEW (take all in cap)")]:
        print(f"\n===== {label} =====")
        for cap in ([50, 100, 200] if skew_frac < 1 else [100, 400]):
            wd = precompute(cap, skew_frac)
            Su, mu, su = sh([m for m, _ in wd])
            print(f" cap={cap}: BASELINE no-hedge  Sharpe={Su:+.3f} mean=${mu:.2f} std=${su:.2f} "
                  f"$tot=${sum(m for m,_ in wd):,.0f}")
            print(f"   {'arm':>22} {'ideal Sh':>9} {'prac Sh':>8} {'ideal std':>9} {'prac std':>9} "
                  f"{'prac $tot':>10} {'fees$':>8} {'reb/w med':>9} {'p90':>5} {'max':>6}")
            for tf in [0, 60, 120, 180, 300]:
                unh, idl, prc, ftot, rebs = arm(wd, tf)
                Si, _, sti = sh(idl); Sp, _, stp = sh(prc)
                name = "B hedge-all" if tf == 0 else f"C freeze<{tf}s"
                med = int(np.median(rebs)) if len(rebs) else 0
                p90 = int(np.percentile(rebs, 90)) if len(rebs) else 0
                mx = int(rebs.max()) if len(rebs) else 0
                print(f"   {name:>22} {Si:>9.3f} {Sp:>8.3f} {sti:>9.2f} {stp:>9.2f} "
                      f"{np.sum(prc):>10,.0f} {ftot:>8,.0f} {med:>9} {p90:>5} {mx:>6}")


if __name__ == "__main__":
    main()
