"""eth_toxmaker_study.py -- Toxicity-gated ONE-SIDED maker on Kalshi ETH 15-min binary.

GOAL: earn the bid-ask spread from UNINFORMED taker flow while AVOIDING informed/toxic flow.

FILL MODEL (conservative, from box_policy_ab.window_fills):
- A maker fill = a resting quote at the touch (b0 for a bid / a0 for an ask) and a taker
  TRADES THROUGH it (price crosses our level with size). We only count a fill when a taker
  actually trades at/through our price in the NEXT 1-2 minutes (q0=0 => front-of-queue, the
  OPTIMISTIC fill assumption; see caveats). One-sided => we open a single directional leg and
  do NOT pair it (no box). The leg's to-settlement value is f['settle'] (= res - b0 for a YES
  buy, a0 - res for a NO/YES-sell). Spread capture is BAKED IN: settle = E[res]-price, and if
  the mid were efficient E[settle]=+half-spread. Adverse selection shows up as E[res|fill]<mid.
- Exit alternatives: HOLD to settle (f['settle']); FLATTEN ~1min later at touch (f['exit']);
  STOP if adverse (sell at exit only when sig adverse).

Maker fee on Kalshi crypto 15m ~ $0 (rounds to zero) => no fee drag, unlike takers.

We measure, per toxicity bucket and per gate:
  EV/fill (cents), Sharpe (per-fill), win rate, #fills, IS/OOS split (first 60% / last 40%),
  t-stat vs zero. We are explicit that optimistic (front-queue) fills can manufacture edge.

Writes findings to stdout; ETH_TOXMAKER.md is authored from these numbers.
"""
from __future__ import annotations
import sys; sys.path.insert(0, '/tmp/ev_toxmaker')
import numpy as np, pandas as pd
from ladder_baseline_study import load_parquet_windows

np.seterr(all='ignore')


def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 4: return float('nan')
    s = x.std(ddof=1)
    return x.mean() / (s / np.sqrt(len(x))) if s > 1e-12 else float('nan')


def sharpe(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 4: return float('nan')
    s = x.std(ddof=1)
    return x.mean() / s if s > 1e-12 else float('nan')


def summ(vals, label='', exitcol='settle'):
    v = np.asarray(vals, float); v = v[~np.isnan(v)]
    if len(v) == 0:
        return dict(label=label, n=0, ev=float('nan'), sh=float('nan'),
                    wr=float('nan'), t=float('nan'))
    return dict(label=label, n=len(v), ev=v.mean()*100, sh=sharpe(v),
                wr=(v > 0).mean()*100, t=tstat(v))


def fmt(d):
    return (f"{d['label']:<34} n={d['n']:>6}  EV/fill={d['ev']:>+7.3f}c  "
            f"Sh={d['sh']:>+6.3f}  win={d['wr']:>5.1f}%  t={d['t']:>+6.2f}")


def load_df(asset):
    fills, ws = load_parquet_windows(asset)
    rows = []
    for w in ws:
        for f in fills[w]:
            d = dict(f)
            d['ws'] = w
            rows.append(d)
    df = pd.DataFrame(rows)
    # YES-equivalent price for the leg, |edge from 0.5|
    df['p_yeq'] = np.where(df.side == 'bid', df.p, 1.0 - df.p)
    df['abs_p05'] = (df.p_yeq - 0.5).abs()
    df['fav'] = df.p_yeq > 0.5      # leg is on the FAVORED side
    df['vpin'] = df.vpin.fillna(df.vpin.median())
    df['absflow'] = df.flow.abs()
    df['abssig'] = df.sig.abs()
    return df, ws


def is_oos_mask(df, ws):
    cut = ws[int(len(ws) * 0.6)]
    return df.ws < cut


def main():
    print("=" * 90)
    print("ETH TOXICITY-GATED ONE-SIDED MAKER STUDY")
    print("=" * 90)
    df, ws = load_df('eth')
    df['is_is'] = is_oos_mask(df, ws)
    cut_ws = ws[int(len(ws) * 0.6)]
    print(f"\nTotal fills={len(df)}  windows={len(ws)}  IS_fills={df.is_is.sum()}  OOS_fills={(~df.is_is).sum()}")
    print(f"mean spread={df.spread.mean()*100:.2f}c  half-spread={df.spread.mean()*50:.2f}c  "
          f"mean settle={df.settle.mean()*100:+.3f}c")

    # ---- BASELINE: ungated one-sided maker, hold-to-settle ----
    print("\n" + "=" * 90)
    print("TASK 0 -- BASELINE ungated one-sided maker (hold to settle), all flow")
    print("=" * 90)
    for lbl, mask in [("ALL fills", df.index >= 0),
                      ("BID (buy YES)", df.side == 'bid'),
                      ("ASK (sell YES/buy NO)", df.side == 'ask'),
                      ("FAVORED side (p_yeq>0.5)", df.fav),
                      ("UNDERDOG side (p_yeq<0.5)", ~df.fav)]:
        print("  " + fmt(summ(df[mask].settle, lbl)))

    # ---- TASK 1: flow toxicity decomposition ----
    print("\n" + "=" * 90)
    print("TASK 1 -- FLOW TOXICITY DECOMPOSITION (hold-to-settle EV per fill by bucket)")
    print("=" * 90)
    for gatecol, qs, name in [
        ('vpin', [0, .25, .5, .75, 1.0], 'VPIN'),
        ('absflow', [0, .25, .5, .75, 1.0], '|flow| (taker imbalance)'),
        ('abssig', [0, .25, .5, .75, 1.0], '|sig| (spot move bps)'),
        ('tksize', [0, .25, .5, .75, 1.0], 'taker size'),
    ]:
        print(f"\n  -- bucket by {name} (quartiles) --")
        edges = df[gatecol].quantile(qs).values
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            m = (df[gatecol] >= lo) & (df[gatecol] <= hi if i == len(edges) - 2 else df[gatecol] < hi)
            print("    " + fmt(summ(df[m].settle, f"Q{i+1} [{lo:.3g},{hi:.3g}]")))

    # ---- TASK 2: toxicity-gated maker sweep (hold-to-settle) ----
    print("\n" + "=" * 90)
    print("TASK 2 -- TOXICITY-GATED MAKER SWEEP (ACCEPT only LOW-toxicity fills)")
    print("        side x gate x threshold ; metric = EV/fill on the ACCEPTED fills (hold settle)")
    print("=" * 90)
    sides = {"both": df.index >= 0, "favored": df.fav, "underdog": ~df.fav,
             "bid": df.side == 'bid', "ask": df.side == 'ask'}
    gates = {
        "vpin<=": ('vpin', [0.30, 0.35, 0.40, 0.45], 'le'),
        "|flow|<=": ('absflow', [100, 250, 500, 1000], 'le'),
        "|sig|<=": ('abssig', [2, 4, 8, 16], 'le'),
        "tksize<=": ('tksize', [3, 5, 10, 20], 'le'),
    }
    best = []
    for sname, smask in sides.items():
        for gname, (col, thrs, _) in gates.items():
            for thr in thrs:
                m = smask & (df[col] <= thr)
                d = summ(df[m].settle, f"{sname} | {gname}{thr}")
                if d['n'] >= 200:
                    best.append(d)
    best.sort(key=lambda d: -d['ev'])
    print("\n  TOP 15 by EV/fill (n>=200):")
    for d in best[:15]:
        print("    " + fmt(d))
    print("\n  BOTTOM 5 (most toxic accepted):")
    for d in best[-5:]:
        print("    " + fmt(d))

    # ---- TASK 3: inventory / exit comparison on a promising gate ----
    print("\n" + "=" * 90)
    print("TASK 3 -- INVENTORY / EXIT comparison (hold vs flatten vs stop-if-adverse)")
    print("=" * 90)
    # pick the best gate from task2 (re-evaluate exits)
    def eval_exits(mask, label):
        sub = df[mask]
        hold = sub.settle.values
        flat = sub.exit.values
        # stop-if-adverse: if pre-fill spot move adverse to our side (sig>0), flatten; else hold
        stop = np.where(sub.sig.values > 0, sub.exit.values, sub.settle.values)
        print(f"\n  [{label}]  n={len(sub)}")
        print("    " + fmt(summ(hold, "HOLD to settle")))
        print("    " + fmt(summ(flat, "FLATTEN at touch (~1min)")))
        print("    " + fmt(summ(stop, "STOP if sig adverse else hold")))
    # candidate gates
    eval_exits(df.index >= 0, "ALL flow (ungated)")
    if best:
        topd = best[0]
        # reconstruct top mask
        sname, rest = topd['label'].split(' | ')
        gname = rest.rstrip('0123456789.')
        thr = float(rest[len(gname):])
        smask = sides[sname]; col = gates[gname][0]
        eval_exits(smask & (df[col] <= thr), f"BEST gate: {topd['label']}")

    # ---- TASK 4: time / regime ----
    print("\n" + "=" * 90)
    print("TASK 4 -- TIME / REGIME (where is uninformed flow concentrated?)")
    print("=" * 90)
    print("\n  -- by k-slot (minute) hold-to-settle EV --")
    for k in range(2, 13):
        m = df.k == k
        if m.sum() >= 100:
            print("    " + fmt(summ(df[m].settle, f"k={k}")))
    print("\n  -- by hour-of-day (UTC) --")
    df['hour'] = pd.to_datetime(df.ws, unit='s', utc=True).dt.hour
    hr = df.groupby('hour').settle.agg(['mean', 'count'])
    hr['ev_c'] = hr['mean'] * 100
    hr = hr.sort_values('ev_c', ascending=False)
    print("    Top 6 hours by EV/fill:")
    for h, row in hr.head(6).iterrows():
        print(f"      hour={int(h):02d}UTC  EV/fill={row.ev_c:+.3f}c  n={int(row['count'])}")
    print("    Bottom 4 hours:")
    for h, row in hr.tail(4).iterrows():
        print(f"      hour={int(h):02d}UTC  EV/fill={row.ev_c:+.3f}c  n={int(row['count'])}")

    # ---- TASK 5: VERDICT -- best rule with IS/OOS stability ----
    print("\n" + "=" * 90)
    print("TASK 5 -- VERDICT: candidate rules IS vs OOS (the honesty check)")
    print("=" * 90)
    # Evaluate a handful of leading candidate rules on IS and OOS separately for the SAME rule.
    candidates = {
        "ungated both (hold)": (df.index >= 0, 'settle'),
        "ask-only (hold)": (df.side == 'ask', 'settle'),
        "favored (hold)": (df.fav, 'settle'),
        "favored & vpin<=.40 (hold)": (df.fav & (df.vpin <= .40), 'settle'),
        "ask & vpin<=.40 (hold)": ((df.side == 'ask') & (df.vpin <= .40), 'settle'),
        "ask & |flow|<=250 (hold)": ((df.side == 'ask') & (df.absflow <= 250), 'settle'),
        "ask & |sig|<=4 (hold)": ((df.side == 'ask') & (df.abssig <= 4), 'settle'),
        "favored & |sig|<=4 (hold)": (df.fav & (df.abssig <= 4), 'settle'),
        "favored & |sig|<=4 (flatten)": (df.fav & (df.abssig <= 4), 'exit'),
        "ask & |flow|<=250 (flatten)": ((df.side == 'ask') & (df.absflow <= 250), 'exit'),
    }
    print(f"\n  {'rule':<32} {'IS EV/Sh/n/t':>30}    {'OOS EV/Sh/n/t':>30}")
    print("  " + "-" * 96)
    for name, (mask, ecol) in candidates.items():
        sub_is = df[mask & df.is_is]; sub_oos = df[mask & ~df.is_is]
        di = summ(sub_is[ecol], 'IS'); do = summ(sub_oos[ecol], 'OOS')
        print(f"  {name:<32} {di['ev']:>+6.3f}c/{di['sh']:>+5.2f}/{di['n']:>5}/{di['t']:>+4.1f}"
              f"    {do['ev']:>+6.3f}c/{do['sh']:>+5.2f}/{do['n']:>5}/{do['t']:>+4.1f}")

    print("\nDONE.")


if __name__ == '__main__':
    main()
