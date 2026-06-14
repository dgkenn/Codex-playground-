"""RISK OVERLAYS for the deployable LONG-ONLY US-spot momentum sleeve.

Builds on the locked base (MOM_LONGONLY.md, commit 78d934e):
  top-15 deep USD-spot universe, risk-adjusted 10d momentum (ret/vol), hold top-5 EW
  (rest USDC cash), weekly, partial-rebalance 0.7, BTC>=100d-MA gate -> fully to cash.
  40 bps RT taker fee (charged cost_bps/2 per unit |dw|, same convention as mlo_backtest).

This module REUSES mlo_backtest's data loader, signal, liquidity screen and gate. It adds
a single configurable overlay backtest so each risk lever can be toggled independently and
stacked, plus a study harness. NO refit of the base signal/cadence -- overlay params are
chosen IS-only and stress-tested on the recent 12mo HARD holdout (REC12) and full cycle.

Overlays implemented (all optional):
 1. VOL-TARGETING: scale total invested exposure to target annualized portfolio vol,
    using trailing realized vol of the *selected book*. de-levers (more cash) on vol spikes.
 2. ABSOLUTE / DUAL MOMENTUM: hold a top-ranked coin only if its OWN trailing return
    (lb-day) exceeds a threshold (0, or BTC's own return) -> can go fully to cash in a
    falling tape even when BTC is still > MA.
 3. FASTER / TIERED DE-RISK: combine the slow BTC>=100dMA gate with a fast BTC>=fast_ma
    gate. Binary (off when fast fails) OR tiered (halve exposure when fast fails).
 4. CONCENTRATION: k hold-count and per-name weight cap.
 5. PER-POSITION TRAILING STOP / TIME STOP: walk daily inside each weekly hold; if a
    name draws down stop_pct from its in-trade high, move that name to cash until next rebal.

Survivorship: Coinbase serves only listed pairs -> UP bias. SCREENS. Window stated.
"""
import numpy as np
import pandas as pd
import mlo_backtest as mb


def realized_book_vol(px, names, weights, t, lb_vol=20):
    """Annualized realized vol of the equal/weighted book over trailing lb_vol days."""
    p = px[names].loc[:t].tail(lb_vol + 1)
    if len(p) < lb_vol // 2:
        return None
    dret = p.pct_change().dropna(how="all")
    if dret.empty:
        return None
    w = weights.reindex(names).fillna(0.0).values
    sw = w.sum()
    if sw <= 0:
        return None
    w = w / sw
    port_d = (dret[names].fillna(0.0).values * w).sum(axis=1)
    sd = np.std(port_d)
    return sd * np.sqrt(365.0)


def own_return(px, sym, t, lb):
    p = px[sym].loc[:t].dropna()
    if len(p) < lb + 1:
        return np.nan
    return float(p.iloc[-1] / p.iloc[-1 - lb] - 1.0)


def backtest_risk(px, vol, lb=10, top_n=15, k=5, hold_days=7,
                  cost_bps=40.0, partial=0.7, gate_ma=100, univ_pool=None,
                  # --- overlays ---
                  vol_target=None, vol_lb=20, max_lev=1.0,
                  abs_mom=False, abs_thresh=0.0, abs_vs_btc=False,
                  fast_ma=None, fast_mode="binary",  # 'binary' or 'tier'
                  tier_frac=0.5,
                  name_cap=None,
                  stop_pct=None, time_stop_days=None):
    """Long-only weekly momentum with stackable risk overlays. Returns per-rebalance DataFrame.

    Overlay semantics:
      vol_target: annualized target (e.g. 0.40). Scales invested exposure by
                  min(max_lev, vol_target / realized_book_vol). De-levers on vol spikes.
      abs_mom: keep a selected name only if its own lb-return > abs_thresh
               (or > BTC own lb-return if abs_vs_btc). Cash if all fail.
      fast_ma: faster BTC MA gate stacked on slow gate_ma. binary -> cash when BTC<fast_ma;
               tier -> multiply exposure by tier_frac when BTC<fast_ma.
      name_cap: max weight per name (e.g. 0.30); excess redistributed... simplest: cap then
                renormalize to keep invested fraction (cap reduces concentration).
      stop_pct: per-name intra-week trailing stop from in-trade high (e.g. 0.15) -> that name
                to cash for the rest of the week.
      time_stop_days: if a name's price < its entry price for the whole window by day d, exit.
                      (kept simple: exit name to cash if down > 0 at end-of-period midpoint check)
    """
    dates = px.index
    rb = dates[::hold_days]
    recs = []
    cur_w = None
    for i in range(len(rb) - 1):
        t, nxt = rb[i], rb[i + 1]
        univ = mb.liquid_universe(vol, t, top_n)
        if univ_pool is not None:
            univ = [u for u in univ if u in univ_pool]
        if len(univ) < 4:
            continue
        gated_off = (gate_ma is not None) and (not mb.btc_above_ma(px, t, gate_ma))
        sig = mb.sig_riskadj(px, t, lb)
        if sig is None:
            continue
        s = sig.reindex(univ).dropna()
        if len(s) < 4:
            continue
        if isinstance(k, float) and 0 < k <= 1:
            n_hold = max(1, int(round(len(s) * k)))
        else:
            n_hold = int(k)
        n_hold = min(n_hold, len(s))

        if gated_off:
            tw = pd.Series(0.0, index=s.index)
            held = []
        else:
            longs = list(s.sort_values().index[-n_hold:])
            # absolute / dual momentum filter
            if abs_mom:
                btc_r = own_return(px, "BTC", t, lb) if abs_vs_btc else None
                kept = []
                for nm in longs:
                    r = own_return(px, nm, t, lb)
                    if np.isnan(r):
                        continue
                    thr = btc_r if abs_vs_btc and btc_r is not None else abs_thresh
                    if r > thr:
                        kept.append(nm)
                longs = kept
            held = longs
            tw = pd.Series(0.0, index=s.index)
            if len(longs) > 0:
                w_each = 1.0 / n_hold  # keep sizing relative to target k -> shortfall goes to cash
                for nm in longs:
                    tw[nm] = w_each
                # name cap
                if name_cap is not None:
                    tw = tw.clip(upper=name_cap)

        # ---- exposure scaling (vol target + fast gate tier) ----
        scale = 1.0
        if vol_target is not None and len(held) > 0:
            rv = realized_book_vol(px, held, tw, t, lb_vol=vol_lb)
            if rv is not None and rv > 0:
                scale *= min(max_lev, vol_target / rv)
        if fast_ma is not None and not gated_off:
            fast_off = not mb.btc_above_ma(px, t, fast_ma)
            if fast_off:
                if fast_mode == "binary":
                    scale = 0.0
                elif fast_mode == "tier":
                    scale *= tier_frac
        tw = tw * scale

        # partial move toward target
        if cur_w is None:
            new_w = tw.copy()
        else:
            idx = tw.index.union(cur_w.index)
            a = cur_w.reindex(idx).fillna(0.0)
            b = tw.reindex(idx).fillna(0.0)
            new_w = a + partial * (b - a)

        # turnover
        if cur_w is None:
            dchg = new_w.abs()
        else:
            idx = new_w.index.union(cur_w.index)
            dchg = (new_w.reindex(idx).fillna(0.0) - cur_w.reindex(idx).fillna(0.0)).abs()
        turnover = float(dchg.sum())
        cost = turnover * (cost_bps / 2.0) / 1e4

        # ---- realized forward return, with optional per-name trailing/time stop ----
        if stop_pct is None and time_stop_days is None:
            fwd = (px.loc[nxt] / px.loc[t] - 1.0).reindex(new_w.index)
            gross = float((new_w * fwd).sum(skipna=True))
            stop_cost = 0.0
        else:
            # walk daily within (t, nxt]; per held name track in-trade high; if dd from high
            # exceeds stop_pct, realize the loss at that point and hold cash for the remainder.
            window = px.loc[t:nxt]
            gross = 0.0
            stop_cost = 0.0
            for nm in new_w.index:
                w = new_w[nm]
                if w == 0 or pd.isna(w):
                    continue
                series = window[nm].dropna()
                if len(series) < 2:
                    continue
                entry = series.iloc[0]
                path = series / entry  # cumulative multiple
                high = path.cummax()
                ddp = path / high - 1.0
                exit_mult = path.iloc[-1]  # default: hold to end
                stopped = False
                if stop_pct is not None:
                    hit = ddp[ddp <= -stop_pct]
                    if len(hit) > 0:
                        # exit at first stop breach (use that day's multiple)
                        first_day = hit.index[0]
                        exit_mult = path.loc[first_day]
                        stopped = True
                if (not stopped) and time_stop_days is not None:
                    # time stop: if not above entry by time_stop_days, exit at that point
                    if len(path) > time_stop_days and path.iloc[time_stop_days] <= 1.0:
                        exit_mult = path.iloc[time_stop_days]
                        stopped = True
                gross += w * (exit_mult - 1.0)
                if stopped:
                    stop_cost += w * (cost_bps / 2.0) / 1e4  # extra exit fee

        recs.append({"date": nxt, "gross": gross, "net": gross - cost - stop_cost,
                     "turnover": turnover, "cost": cost,
                     "invested": float(new_w.clip(lower=0).sum()), "gated": gated_off})
        cur_w = new_w
    return pd.DataFrame(recs).set_index("date") if recs else pd.DataFrame()


# ---- reporting helpers ----
def line(tag, rep):
    out = [f"{tag:28s}"]
    for w in ["FULL", "REC12", "PREV12"]:
        s = rep[w]
        out.append(f"{w}: Sh{s['sharpe']:+.2f} r{s['ann_ret']:+.0%} dd{s['maxdd']:+.0%}")
    return "  ".join(out)


def report(px, vol, pool, **kw):
    bt = backtest_risk(px, vol, univ_pool=pool, **kw)
    if bt.empty:
        return None, None
    return bt, mb.window_report(bt)


if __name__ == "__main__":
    px, vol = mb.load_spot()
    pool = list(px.columns)
    _, base = report(px, vol, pool, lb=10, top_n=15, k=5, cost_bps=40, partial=0.7, gate_ma=100)
    print(line("BASE k5 gate100", base))
