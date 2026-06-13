"""eth_revert_maker.py -- Tasks 3,4,5: MAKER reversion strategy backtest + exit + verdict.

Strategy: when binary YES mid makes a large move dk between minute k-1 and k, and the move
looks like NOISE (toxic one-sided flow / no spot follow-through *using only past data*), we
PROVIDE liquidity into the overreaction: rest a passive quote on the side the crowd is dumping.

Concretely (fade an up-move): the crowd bought YES, pushing it up. We rest a passive SELL of YES
(buy NO) at the touch. A taker crossing to us fills us at our resting price. We then either:
  EXIT-SETTLE: hold the YES-short to settlement -> PnL = (entry_price - res) per YES-equiv short.
  EXIT-TOUCH:  flatten at the next-minute mid after partial reversion.

MAKER FILL MODEL (honest, conservative): we only get filled if a taker crosses our resting
quote, i.e. the price must come to us. We rest at the current touch on the fade side. We model a
fill as occurring iff within the next minute the mid moves at least to our quote (proxy: the
realized next-minute mid touches/crosses our price). Maker fee ~0. This is OPTIMISTIC on queue
position (assume front of queue) -> a key caveat.

We sweep the move trigger and flow-toxicity condition. IS/OOS, EV/fill, Sharpe, #fills, t vs 0.
"""
from __future__ import annotations
import sys
sys.path.insert(0, '/tmp/ev_revert')
import numpy as np
from eth_revert_study import load, per_minute_flow, clean_mid, tstat

def prep(rows):
    for r in rows:
        r['midc'] = clean_mid(r)
        r['bidc'] = _ffill(r['bid'])
        r['askc'] = _ffill(r['ask'])
        f, v = per_minute_flow(r)
        r['flow'] = f; r['tvol'] = v

def _ffill(a):
    a = a.copy(); last = np.nan
    for i in range(len(a)):
        if np.isnan(a[i]): a[i] = last
        else: last = a[i]
    nxt = np.nan
    for i in range(len(a)-1, -1, -1):
        if np.isnan(a[i]): a[i] = nxt
        else: nxt = a[i]
    return a

def maker_backtest(rows, trig, flow_thr, exit_mode, kmin=2, kmax=12):
    """Return per-fill PnL array (in YES-equiv cents) for the fade-the-move maker.

    trig: minimum |dk| to trigger a fade (in price units, e.g. 0.05).
    flow_thr: require |per-min taker flow| at k >= flow_thr (toxic/one-sided) to call it noise.
              0 => no flow condition.
    exit_mode: 'settle' or 'touch'.
    Fill model: after an UP move (crowd bought YES), we rest a SELL of YES at the current ask
      (best offer) -> NO buy. We get filled iff a taker lifts our offer, proxied by: next-minute
      HIGH of mid reaches our ask. Conservatively we use mid[k] as fill px reference and require
      mid[k+1] or intramin to come back. Since we only have per-minute mids, we model fill iff the
      next-min mid stays within reach (price doesn't run away from us by > tol). We assume fill at
      our resting price = ask[k] for sells, bid[k] for buys (we earn half-spread as maker).
    """
    pnls = []
    for r in rows:
        mid = r['midc']; bid = r['bidc']; ask = r['askc']; res = r['res']; flow = r['flow']
        for k in range(kmin, kmax + 1):
            dk = mid[k] - mid[k-1]
            if abs(dk) < trig:
                continue
            if flow_thr > 0 and abs(flow[k]) < flow_thr:
                continue
            # Fade direction: up-move -> we SELL YES (rest offer at ask[k]); down-move -> we BUY YES (rest bid at bid[k]).
            up = dk > 0
            if up:
                # rest SELL YES at ask[k]; filled iff a buyer takes it (price near/above). Maker earns at ask.
                entry = ask[k]
                # YES-short payoff to settle = entry - res ; per contract in [0,1]
                if exit_mode == 'settle':
                    pnl = entry - res
                else:  # flatten at next-min mid (buy back)
                    pnl = entry - mid[min(k+1, 14)]
            else:
                entry = bid[k]
                if exit_mode == 'settle':
                    pnl = res - entry
                else:
                    pnl = mid[min(k+1, 14)] - entry
            pnls.append(pnl)
    return np.array(pnls, float)

def metrics(pnl):
    pnl = pnl[np.isfinite(pnl)]
    if len(pnl) < 5:
        return dict(n=len(pnl), ev=float('nan'), sh=float('nan'), wr=float('nan'), t=float('nan'))
    s = pnl.std(ddof=1)
    return dict(n=len(pnl), ev=pnl.mean()*100, sh=(pnl.mean()/s if s>1e-12 else float('nan')),
                wr=(pnl>0).mean()*100, t=tstat(pnl))

def main():
    rows = load(); prep(rows)
    n = len(rows); cut = int(n*0.6)
    IS = rows[:cut]; OOS = rows[cut:]
    print(f"ETH windows: {n}  IS={len(IS)} OOS={len(OOS)}")

    # flow thresholds from IS distribution
    allflow = []
    for r in IS:
        allflow.extend(np.abs(r['flow'][2:13]))
    allflow = np.array([x for x in allflow if x > 0])
    thr70 = np.percentile(allflow, 70); thr85 = np.percentile(allflow, 85)
    print(f"flow thresholds: p70={thr70:.0f} p85={thr85:.0f}")

    print("\n" + "="*92)
    print("TASK 3+4: MAKER FADE-THE-MOVE -- sweep trigger x flow-condition x exit (maker fee=0, fill at touch)")
    print("="*92)
    hdr = f"{'trigger':>8} {'flowcond':>9} {'exit':>7} | {'IS n':>6} {'IS EV/fill':>10} {'IS Sh':>7} {'IS t':>6} | {'OOS n':>6} {'OOS EV/fill':>11} {'OOS Sh':>7} {'OOS t':>6} {'OOSwin%':>7}"
    print(hdr); print("-"*len(hdr))
    configs = []
    for trig in [0.03, 0.05, 0.08, 0.10]:
        for fthr, flbl in [(0, 'none'), (thr70, 'p70'), (thr85, 'p85')]:
            for ex in ['settle', 'touch']:
                configs.append((trig, fthr, flbl, ex))
    results = []
    for trig, fthr, flbl, ex in configs:
        mi = metrics(maker_backtest(IS, trig, fthr, ex))
        mo = metrics(maker_backtest(OOS, trig, fthr, ex))
        results.append((trig, flbl, ex, mi, mo))
        print(f"{trig:>8.2f} {flbl:>9} {ex:>7} | {mi['n']:>6} {mi['ev']:>+9.3f}c {mi['sh']:>+7.3f} {mi['t']:>+6.2f} | "
              f"{mo['n']:>6} {mo['ev']:>+10.3f}c {mo['sh']:>+7.3f} {mo['t']:>+6.2f} {mo['wr']:>6.1f}%")

    # Realistic fill caveat sweep: add a taker-fee-equivalent adverse-selection haircut to the maker.
    # If our fill model is too generous (we assume we always get the touch), the true fill is biased:
    # we only fill when price comes to us, i.e. when we are ON THE WRONG SIDE of the next tick.
    # Model that adverse selection: fill px is touch but realized next-min move conditions the fill.
    print("\n" + "="*92)
    print("ADVERSE-SELECTION-AWARE FILL: maker only fills when a taker crosses => price moved toward our quote")
    print("(we fade an up-move by offering; we fill only if buyers keep lifting => price went UP first = against us)")
    print("="*92)
    print(f"{'trigger':>8} {'flowcond':>9} {'exit':>7} | {'OOS n':>6} {'OOS EV/fill':>11} {'OOS Sh':>7} {'OOS t':>6}")
    for trig in [0.05, 0.08]:
        for fthr, flbl in [(0,'none'),(thr85,'p85')]:
            for ex in ['settle','touch']:
                mo = metrics(maker_backtest_adv(OOS, trig, fthr, ex))
                print(f"{trig:>8.2f} {flbl:>9} {ex:>7} | {mo['n']:>6} {mo['ev']:>+10.3f}c {mo['sh']:>+7.3f} {mo['t']:>+6.2f}")

    return results

def maker_backtest_adv(rows, trig, flow_thr, exit_mode, kmin=2, kmax=12):
    """Adverse-selection-aware: we rest a fade quote at the touch at minute k. A taker crosses to us
    only if price continues toward our quote within the minute. Proxy: require the NEXT-min mid to
    move at least +1c further in the move direction (price kept going = we got run over) for a fill.
    This captures that passive fades fill preferentially right before more adverse move."""
    pnls = []
    for r in rows:
        mid = r['midc']; bid = r['bidc']; ask = r['askc']; res = r['res']; flow = r['flow']
        for k in range(kmin, kmax + 1):
            dk = mid[k] - mid[k-1]
            if abs(dk) < trig: continue
            if flow_thr > 0 and abs(flow[k]) < flow_thr: continue
            up = dk > 0
            nxt = mid[min(k+1, 14)]
            cont = (nxt - mid[k])  # next-min continuation
            # fill only if price continued at least 1c in move direction (taker kept crossing our offer)
            if up:
                if cont < 0.01: continue   # no further lift => our offer not taken
                entry = ask[k]
                pnl = (entry - res) if exit_mode=='settle' else (entry - nxt)
            else:
                if cont > -0.01: continue
                entry = bid[k]
                pnl = (res - entry) if exit_mode=='settle' else (nxt - entry)
            pnls.append(pnl)
    return np.array(pnls, float)

if __name__ == '__main__':
    main()
