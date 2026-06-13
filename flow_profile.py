"""flow_profile.py -- Counterparty profiling on Kalshi ETH 15-min binary tape.

GOAL: settle the operator's dichotomy -- are takers a sub-population that
consistently WINS (follow) or LOSES (fade)?

Per taker trade P&L to settlement:
  buy YES at p  -> pnl = (res_up - p)      (wins 1-p if up, loses p if down)
  sell YES at p -> pnl = (p - res_up)      (taker sold YES = bought NO)

Trade-level informed-flow features (causal, from trade index i and a short
trailing window of the SAME window's tape, up to and including i):
  size        : trade size (contracts)
  run         : consecutive same-aggressor-side run length ending at i
  intensity   : trades in trailing 10s window
  sweep       : same-side consecutive trades at worsening price ending at i
  roundlot    : trade size is a round lot {1,5,10,25,50,100} (retail tell)
  is_round_px : price is a round 5c level (retail tell)

We split by horizon: settlement is the natural binary outcome, but to test
whether "informed" flow predicts the IMMEDIATE next move we also compute the
mid markout at +5s,+30s,+60s and to-settlement.

IS = first 60% of windows (time-ordered), OOS = last 40%.
"""
from __future__ import annotations
import numpy as np, pandas as pd

ROUND_LOTS = {1, 5, 10, 25, 50, 100}

def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 2: return np.nan
    s = x.std(ddof=1)
    return x.mean() / (s / np.sqrt(len(x))) if s > 1e-12 else np.nan

def sharpe(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 2: return np.nan
    s = x.std(ddof=1)
    return x.mean() / s if s > 1e-12 else np.nan

# ---------------------------------------------------------------
# Build per-trade table with features + multi-horizon outcomes
# ---------------------------------------------------------------
def build_trades(asset='eth'):
    hist = pd.read_parquet(f'/tmp/ev_flow/hist_kalshi_{asset}15m.parquet').set_index('ws')
    tap = pd.read_parquet(f'/tmp/ev_flow/trades_kalshi_{asset}15m.parquet')
    recs = []
    for _, row in tap.iterrows():
        ws = int(row['ws']); res = int(row['res_up'])
        t = np.asarray(row['t'], float); p = np.asarray(row['p'], float)
        sz = np.asarray(row['sz'], float); buy = np.asarray(row['buy'], bool)
        n = len(t)
        if n < 3: continue
        if ws not in hist.index: continue
        h = hist.loc[ws]
        mid = np.asarray(h['mid_path'], float)  # per-minute mid, len ~15
        sgn = np.where(buy, 1, -1)
        # trailing-window features computed in one pass
        # run length ending at i (same side)
        run = np.ones(n, int)
        for i in range(1, n):
            run[i] = run[i-1] + 1 if sgn[i] == sgn[i-1] else 1
        # sweep: same-side consecutive at worsening price ending at i
        sweep = np.zeros(n, int)
        for i in range(1, n):
            if sgn[i] == sgn[i-1]:
                worse = (buy[i] and p[i] > p[i-1] + 1e-9) or ((not buy[i]) and p[i] < p[i-1] - 1e-9)
                sweep[i] = sweep[i-1] + 1 if worse else (sweep[i-1] if sweep[i-1] > 0 else 0)
                if not worse:
                    sweep[i] = 0
            else:
                sweep[i] = 0
        # intensity: # trades in trailing 10s
        intens = np.ones(n, int)
        j = 0
        for i in range(n):
            while t[i] - t[j] > 10.0: j += 1
            intens[i] = i - j + 1
        # round lot
        lots = np.round(sz * 100).astype(int)
        roundlot = np.array([l in ROUND_LOTS for l in lots])
        # round 5c price
        cents = np.round(p * 100).astype(int)
        is_round_px = (cents % 5 == 0)
        # outcome to settlement (per contract)
        pnl_settle = np.where(buy, res - p, p - res)   # signed taker P&L
        # mid markouts: minute index of trade
        rel = (t - ws) / 60.0
        mi = np.clip(rel.astype(int), 0, len(mid) - 1)
        mid_now = mid[mi]
        # markout to settlement implied by mid is just res; markout to next-minute mid:
        mi5 = np.clip(mi + 1, 0, len(mid) - 1)
        mid_next = mid[mi5]
        # signed mid markout (next minute): does mid move in taker's direction?
        mk_next = np.where(buy, mid_next - mid_now, mid_now - mid_next)
        for i in range(n):
            recs.append((ws, res, t[i] - ws, p[i], sz[i], bool(buy[i]),
                         run[i], sweep[i], intens[i], bool(roundlot[i]),
                         bool(is_round_px[i]), pnl_settle[i], mk_next[i]))
    df = pd.DataFrame(recs, columns=['ws', 'res', 'trel', 'p', 'sz', 'buy',
                                     'run', 'sweep', 'intens', 'roundlot',
                                     'round_px', 'pnl', 'mk_next'])
    return df

def split(df):
    wss = np.sort(df['ws'].unique())
    cut = wss[int(len(wss) * 0.6)]
    return df[df['ws'] < cut].copy(), df[df['ws'] >= cut].copy()

def bucket_stats(d, name):
    n = len(d)
    if n == 0: return None
    pnl = d['pnl'].values
    # win-rate vs breakeven: a trade "wins" if pnl>0 (settles its way net of price paid)
    wr = (pnl > 0).mean() * 100
    ev = pnl.mean() * 100  # cents per contract
    sh = sharpe(pnl)
    ts = tstat(pnl)
    mk = d['mk_next'].mean() * 100
    return dict(name=name, n=n, wr=wr, ev=ev, sh=sh, ts=ts, mk_next=mk)

def print_table(rows, title):
    print(f"\n=== {title} ===")
    print(f"{'bucket':<34}{'n':>9}{'win%':>8}{'EV c/ct':>10}{'Sharpe':>9}{'t':>8}{'mk+1m c':>9}")
    print('-' * 87)
    lines = []
    for r in rows:
        if r is None: continue
        line = f"{r['name']:<34}{r['n']:>9}{r['wr']:>8.2f}{r['ev']:>+10.3f}{r['sh']:>+9.3f}{r['ts']:>+8.2f}{r['mk_next']:>+9.3f}"
        print(line); lines.append(line)
    return lines

def main():
    print("Building ETH per-trade table...")
    df = build_trades('eth')
    print(f"Total ETH taker trades: {len(df)}  windows: {df['ws'].nunique()}")
    IS, OOS = split(df)
    print(f"IS trades: {len(IS)}  OOS trades: {len(OOS)}")

    report = []
    report.append(f"Total ETH taker trades: {len(df)}  windows: {df['ws'].nunique()}")
    report.append(f"IS trades: {len(IS)}  OOS trades: {len(OOS)}")

    # ---- TASK 1: aggregate taker outcome ----
    print("\n" + "=" * 87)
    print("TASK 1: AGGREGATE TAKER OUTCOME (do takers win or lose vs spread paid?)")
    for lbl, d in [('ALL IS', IS), ('ALL OOS', OOS)]:
        r = bucket_stats(d, lbl)
        print(f"  {lbl}: n={r['n']} win%={r['wr']:.2f} EV={r['ev']:+.3f}c/ct t={r['ts']:+.2f} "
              f"mid-mk+1m={r['mk_next']:+.3f}c")
        report.append(f"{lbl}: n={r['n']} win%={r['wr']:.2f} EV={r['ev']:+.3f}c/ct t={r['ts']:+.2f} mk+1m={r['mk_next']:+.3f}c")

    # ---- TASK 2: smart vs naive buckets (OOS reported; IS for stability) ----
    def buckets_for(D, tag):
        rows = []
        rows.append(bucket_stats(D, f'[{tag}] all'))
        # INFORMED candidates
        rows.append(bucket_stats(D[D['sweep'] >= 2], f'[{tag}] sweep>=2'))
        rows.append(bucket_stats(D[D['sweep'] >= 3], f'[{tag}] sweep>=3'))
        rows.append(bucket_stats(D[D['run'] >= 4], f'[{tag}] run>=4 (same-side)'))
        rows.append(bucket_stats(D[D['run'] >= 6], f'[{tag}] run>=6'))
        rows.append(bucket_stats(D[D['intens'] >= 5], f'[{tag}] intensity>=5/10s'))
        rows.append(bucket_stats(D[D['intens'] >= 10], f'[{tag}] intensity>=10/10s'))
        rows.append(bucket_stats(D[D['sz'] >= 10], f'[{tag}] size>=10'))
        rows.append(bucket_stats(D[D['sz'] >= 50], f'[{tag}] size>=50'))
        # combined informed
        inf = D[(D['sweep'] >= 2) | (D['run'] >= 5) | (D['intens'] >= 8) | (D['sz'] >= 25)]
        rows.append(bucket_stats(inf, f'[{tag}] INFORMED(any)'))
        # NAIVE candidates
        rows.append(bucket_stats(D[D['round_px']], f'[{tag}] round-5c price'))
        rows.append(bucket_stats(D[D['roundlot']], f'[{tag}] round-lot size'))
        rows.append(bucket_stats(D[D['sz'] <= 1.0], f'[{tag}] size<=1 (tiny)'))
        rows.append(bucket_stats(D[D['sz'] <= 2.0], f'[{tag}] size<=2'))
        naive = D[(D['round_px']) & (D['sz'] <= 2.0) & (D['run'] <= 2) & (D['sweep'] == 0)]
        rows.append(bucket_stats(naive, f'[{tag}] NAIVE(round+tiny+noflow)'))
        return rows

    print("\n" + "=" * 87)
    print("TASK 2: SMART vs NAIVE BUCKETS")
    is_rows = buckets_for(IS, 'IS')
    oos_rows = buckets_for(OOS, 'OOS')
    print_table(is_rows, "IN-SAMPLE buckets")
    l = print_table(oos_rows, "OUT-OF-SAMPLE buckets")
    report.append("\nBUCKET TABLE (header: bucket n win% EV(c/ct) Sharpe t mk+1m):")
    report.append(f"{'bucket':<34}{'n':>9}{'win%':>8}{'EV c/ct':>10}{'Sharpe':>9}{'t':>8}{'mk+1m c':>9}")
    for r in is_rows + oos_rows:
        if r is None: continue
        report.append(f"{r['name']:<34}{r['n']:>9}{r['wr']:>8.2f}{r['ev']:>+10.3f}{r['sh']:>+9.3f}{r['ts']:>+8.2f}{r['mk_next']:>+9.3f}")

    # ---- TASK 3 & 4: cost-adjusted strategy ----
    # crypto taker fee model: Kalshi taker = ceil(M*P*(1-P)) cents, M~0.14 crypto premium.
    # P(1-P) max 0.25 -> ~3.5c worst, ~1-2c typical. Use per-trade fee.
    def taker_fee(p, M=0.14):
        # cents, rounded up to whole cent, min ~0
        import math
        return math.ceil(M * p * (1 - p) * 100) / 100.0
    print("\n" + "=" * 87)
    print("TASK 3/4: COST-ADJUSTED STRATEGIES")

    def strat_follow(D, tag):
        # FOLLOW: trade alongside informed flow (same side as the informed taker).
        # We are also a taker, paying p + taker fee. Net pnl = signed_settle - fee.
        inf = D[(D['sweep'] >= 2) | (D['run'] >= 5) | (D['intens'] >= 8) | (D['sz'] >= 25)].copy()
        if len(inf) == 0: return None
        fee = inf['p'].apply(taker_fee).values
        net = inf['pnl'].values - fee
        return dict(name=f'FOLLOW-informed [{tag}]', n=len(inf),
                    gross=inf['pnl'].mean()*100, fee=fee.mean()*100,
                    ev=net.mean()*100, sh=sharpe(net), ts=tstat(net),
                    wr=(net > 0).mean()*100)

    def strat_fade_taker(D, tag):
        # FADE naive as a TAKER: take the OPPOSITE side of naive flow, pay fee.
        naive = D[(D['round_px']) & (D['sz'] <= 2.0) & (D['run'] <= 2) & (D['sweep'] == 0)].copy()
        if len(naive) == 0: return None
        fee = naive['p'].apply(taker_fee).values
        # opposite side: our pnl = -naive_pnl - fee (we pay the cross too)
        net = -naive['pnl'].values - fee
        return dict(name=f'FADE-naive TAKER [{tag}]', n=len(naive),
                    gross=(-naive['pnl']).mean()*100, fee=fee.mean()*100,
                    ev=net.mean()*100, sh=sharpe(net), ts=tstat(net),
                    wr=(net > 0).mean()*100)

    def strat_fade_maker(D, tag, half_spread=0.01, adverse=True):
        # FADE naive as a MAKER: we provide liquidity to naive takers at our quote.
        # If naive BUYS YES from us, we are SHORT YES at price p (we earn half-spread
        # vs mid but eat adverse selection). Honest fill model: maker captures the
        # naive trade's price; maker pnl = -naive_pnl (mirror) + ~0 maker fee.
        # Adverse-selection caveat handled by the fact that naive_pnl already realized.
        naive = D[(D['round_px']) & (D['sz'] <= 2.0) & (D['run'] <= 2) & (D['sweep'] == 0)].copy()
        if len(naive) == 0: return None
        # maker takes opposite side, NO taker fee, but the price the naive paid
        # includes the spread the MAKER earns -> maker pnl = -naive_pnl already counts it.
        net = -naive['pnl'].values
        return dict(name=f'FADE-naive MAKER [{tag}]', n=len(naive),
                    gross=net.mean()*100, fee=0.0,
                    ev=net.mean()*100, sh=sharpe(net), ts=tstat(net),
                    wr=(net > 0).mean()*100)

    strat_rows = []
    for tag, D in [('IS', IS), ('OOS', OOS)]:
        for fn in (strat_follow, strat_fade_taker, strat_fade_maker):
            r = fn(D, tag)
            if r: strat_rows.append(r)

    print(f"\n{'strategy':<30}{'n':>9}{'gross c':>9}{'fee c':>8}{'NET c':>9}{'Sharpe':>9}{'t':>8}{'win%':>8}")
    print('-' * 90)
    report.append(f"\nSTRATEGIES (gross, fee, NET cents/contract):")
    report.append(f"{'strategy':<30}{'n':>9}{'gross c':>9}{'fee c':>8}{'NET c':>9}{'Sharpe':>9}{'t':>8}{'win%':>8}")
    for r in strat_rows:
        line = f"{r['name']:<30}{r['n']:>9}{r['gross']:>+9.3f}{r['fee']:>8.3f}{r['ev']:>+9.3f}{r['sh']:>+9.3f}{r['ts']:>+8.2f}{r['wr']:>8.2f}"
        print(line); report.append(line)

    with open('/tmp/ev_flow/_flow_out.txt', 'w') as f:
        f.write('\n'.join(report))
    print("\nWrote _flow_out.txt")

if __name__ == '__main__':
    main()
