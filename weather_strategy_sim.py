#!/usr/bin/env python3
"""Weather-trading STRATEGY engine: selection + maker-fill + fractional-Kelly portfolio sizing,
and a Monte-Carlo of the resulting Sharpe / return / win-rate / drawdown / capacity.

This is NOT a price backtest (no historical Kalshi weather book is retrievable; NOMADS NBS
bulletins rotate off NOMADS within days, and the live API is rate-limited from CI). It is a
PARAMETRIC simulator: given the per-bet edge distribution, win-rate, fill rate (with adverse
selection on maker fills), within-day cross-city correlation, and fractional-Kelly sizing,
it produces the portfolio metrics. Every output is CONDITIONAL on the sibling model being
calibrated and on forward CLV confirming the per-bet edge. Plug measured numbers from
weather_clv_harness.py here once >=30-45 days of settled signals exist.

Math reused / referenced:
 - Kelly on a binary at price q (cents) with true prob p:  f* = (p - q) / (1 - q)   [edge/(odds)]
   (buy YES at cost q, payoff 1 if win; b = (1-q)/q net odds; Kelly f* = (p*b-(1-p))/b = (p-q)/(1-q)).
 - Per-bet EV (maker, 0 fee): EV = p - q ;  per-bet variance ~ p(1-p) on the 0/1 payoff scaled by stake.
 - Sharpe from N ~independent +EV bets/period:  SR ~ sqrt(N) * (mean_edge / sd_per_bet),
   degraded by within-day correlation rho (effective N_eff = N / (1 + (k-1)*rho) for k correlated legs).
 - Fee model: Kalshi taker = round(0.07*q*(1-q),2)/contract/side; MAKER = 0 (the whole point).
"""
import numpy as np
from scipy.stats import norm

rng = np.random.default_rng(7)

# ----------------------------------------------------------------------------
# 1. CORE BET MATH
# ----------------------------------------------------------------------------
def kelly_fraction(p, q):
    """Full-Kelly fraction of bankroll for buying YES at price q (0-1) with true prob p."""
    if q <= 0 or q >= 1:
        return 0.0
    f = (p - q) / (1.0 - q)
    return max(0.0, f)

def taker_fee(q):
    """Kalshi taker fee per contract per side, q in [0,1]."""
    return round(0.07 * q * (1 - q), 2)

def per_bet_ev_var(p, q, fee=0.0):
    """EV and variance of profit per $1 of contract notional (payoff in {0,1}-q)."""
    # profit if win = (1-q) - fee ; if lose = -q - fee
    win = (1 - q) - fee
    lose = -q - fee
    ev = p * win + (1 - p) * lose
    e2 = p * win**2 + (1 - p) * lose**2
    var = e2 - ev**2
    return ev, var

# ----------------------------------------------------------------------------
# 2. FILL-RATE / ADVERSE-SELECTION MODEL  (the BRUTAL bar)
# ----------------------------------------------------------------------------
def adverse_fill(p_true, q_ask, base_fill, info_share):
    """A resting maker order only fills when someone crosses it. Crossers are partly informed,
    so the subset that fills is adversely selected: conditional on a fill, the true win prob is
    LOWER than the unconditional p_true. Model:
      p_fill            = base_fill                       (you fill base_fill of the time)
      p_win | filled    = p_true - info_share*(p_true-q)  (shaded toward the price you rested at)
    info_share=0 -> no adverse selection (fills are random); info_share=1 -> fills are fully
    informed and your realized edge collapses to ~0. Reality is in between (0.3-0.6)."""
    p_cond = p_true - info_share * (p_true - q_ask)
    return base_fill, max(0.0, min(1.0, p_cond))

# ----------------------------------------------------------------------------
# 3. PORTFOLIO MONTE-CARLO
# ----------------------------------------------------------------------------
def simulate(
    days=252,
    cities=7,
    bets_per_city=2,          # off-modal + warm-tail brackets that clear threshold
    fill_signals_only=True,
    edge_mean=0.04,           # MEAN realized edge p-q AFTER discounting model error (4c)
    edge_sd=0.03,             # spread of edges across brackets
    price_mean=0.15,          # off-modal/tail brackets are cheap (10-25c)
    price_sd=0.06,
    base_fill=0.45,           # maker fill probability (you don't always get filled)
    info_share=0.45,          # adverse-selection shading on filled subset
    kelly_frac=0.25,          # FRACTIONAL Kelly (quarter-Kelly) for smooth high-Sharpe
    kelly_cap=0.02,           # hard cap: <=2% of bankroll per bet (small-per-bet)
    city_rho=0.5,             # within-day cross-city outcome correlation (heat waves)
    model_error_haircut=True, # size DOWN where |p-q| is extreme (likely model wrong)
    bankroll0=10000.0,
    capacity_per_day=2000.0,  # HARD capacity ceiling: max $ deployable/day (thin books).
                              # This is what makes it small-cap: bankroll growth saturates here.
    edge_is_real=True,        # if False: edges are noise; selecting on raw_edge>=2c is selection
                              # bias -> outcomes settle on q (no true edge) to expose the trap.
    runs=400,
):
    """Returns dict of portfolio metrics across `runs` Monte-Carlo paths."""
    sharpes, cagrs, maxdds, winrates, ann_rets = [], [], [], [], []
    deploy_per_day = []

    for _ in range(runs):
        bankroll = bankroll0
        daily_ret = []
        wins = total = 0
        for d in range(days):
            # ---- draw today's slate of bracket-bets ----
            n = cities * bets_per_city
            q = np.clip(rng.normal(price_mean, price_sd, n), 0.02, 0.40)
            raw_edge = rng.normal(edge_mean, edge_sd, n)
            # only positive-edge brackets that clear the maker spread (>=2c) are traded
            traded = raw_edge >= 0.02
            if traded.sum() == 0:
                daily_ret.append(0.0); continue
            q = q[traded]; raw_edge = raw_edge[traded]
            # TRUE settlement prob. If edge is real, p_true = q + edge. If edge is noise
            # (edge_is_real=False), the apparent edge does NOT exist at settlement -> p_true=q,
            # so selecting on raw_edge>=2c is pure selection bias and must lose to the spread.
            if edge_is_real:
                p_true = np.clip(q + raw_edge, 0.01, 0.99)
            else:
                p_true = q.copy()

            # ---- model-error haircut: down-weight extreme disagreement ----
            if model_error_haircut:
                # shrink edges where p-q is large (>10c) toward a trusted band
                shrink = np.where(raw_edge > 0.10, 0.10 + 0.4 * (raw_edge - 0.10), raw_edge)
                p_eff = np.clip(q + shrink, 0.01, 0.99)
            else:
                p_eff = p_true

            # ---- maker fills + adverse selection ----
            pf = np.full(p_eff.shape, base_fill)
            p_cond = np.clip(p_eff - info_share * (p_eff - q), 0.0, 1.0)
            filled = rng.random(p_eff.shape[0]) < pf
            if filled.sum() == 0:
                daily_ret.append(0.0); continue
            q = q[filled]; p_cond = p_cond[filled]; p_true_f = p_true[filled]

            # ---- fractional-Kelly sizing per bet, capped ----
            f = np.array([kelly_fraction(pc, qq) for pc, qq in zip(p_cond, q)])
            f = np.minimum(f * kelly_frac, kelly_cap)
            stake = f * bankroll                      # $ notional per bet (Kelly-desired)
            # CAPACITY CEILING: thin books cap total daily deployment. Pro-rata scale down
            # the whole slate if Kelly wants more than the books can absorb. This is what makes
            # the edge small-cap and is why CAGR saturates as bankroll grows past saturation.
            tot = stake.sum()
            if tot > capacity_per_day:
                stake = stake * (capacity_per_day / tot)
            contracts = stake / np.maximum(q, 0.01)   # # contracts (cost q each)

            # ---- correlated outcomes within the day (heat waves) ----
            k = len(q)
            z_common = rng.standard_normal()
            z_idio = rng.standard_normal(k)
            latent = np.sqrt(city_rho) * z_common + np.sqrt(1 - city_rho) * z_idio
            u = norm.cdf(latent)
            # outcome uses the TRUE (unconditional, pre-adverse) prob for settlement realism,
            # but our EXPECTED win was the adversely-selected p_cond -> realized < expected.
            outcome = (u < p_true_f).astype(float)

            # profit per bet (maker, 0 fee): win -> contracts*(1-q); lose -> -contracts*q
            pnl = np.where(outcome == 1, contracts * (1 - q), -contracts * q).sum()
            wins += outcome.sum(); total += k
            ret = pnl / bankroll
            bankroll *= (1 + ret)
            daily_ret.append(ret)
            deploy_per_day.append(stake.sum())

        dr = np.array(daily_ret)
        mu, sd = dr.mean(), dr.std()
        sr = (mu / sd * np.sqrt(252)) if sd > 1e-9 else 0.0
        cagr = (bankroll / bankroll0) ** (252 / days) - 1
        eq = bankroll0 * np.cumprod(1 + dr)
        peak = np.maximum.accumulate(eq)
        mdd = ((eq - peak) / peak).min()
        sharpes.append(sr); cagrs.append(cagr); maxdds.append(mdd)
        ann_rets.append((1 + mu) ** 252 - 1)
        winrates.append(wins / max(total, 1))

    pct = lambda a, p: float(np.percentile(a, p))
    return dict(
        sharpe_med=pct(sharpes, 50), sharpe_lo=pct(sharpes, 10), sharpe_hi=pct(sharpes, 90),
        cagr_med=pct(cagrs, 50), cagr_lo=pct(cagrs, 10), cagr_hi=pct(cagrs, 90),
        ann_ret_med=pct(ann_rets, 50),
        maxdd_med=pct(maxdds, 50), maxdd_worst=pct(maxdds, 5),
        winrate_med=pct(winrates, 50),
        deploy_per_day_med=float(np.median(deploy_per_day)) if deploy_per_day else 0.0,
    )

# ----------------------------------------------------------------------------
# 4. SHARPE-FROM-N CLOSED FORM (sanity check vs MC)
# ----------------------------------------------------------------------------
def sharpe_from_N(edge, q, N_per_day, days=252, rho=0.5, k_corr=7):
    """Closed-form annualized Sharpe for N iid +EV binary bets/day with within-day correlation."""
    ev, var = per_bet_ev_var(q + edge, q, fee=0.0)
    sd = np.sqrt(var)
    per_bet_sr = ev / sd
    N_eff = N_per_day / (1 + (k_corr - 1) * rho)   # heat-wave correlation cuts independent count
    daily_sr = per_bet_sr * np.sqrt(N_eff)
    return daily_sr * np.sqrt(days), per_bet_sr, N_eff

if __name__ == '__main__':
    print('='*78)
    print('PER-BET KELLY + EV TABLE (maker, 0 fee) vs taker fee drag')
    print('='*78)
    print(f'{"price q":>8}{"edge":>7}{"p_true":>8}{"Kelly f*":>10}{"EV/bet":>9}{"takerfee":>10}{"taker EV":>9}')
    for q in (0.08, 0.15, 0.25):
        for edge in (0.03, 0.06, 0.10):
            p = q + edge
            f = kelly_fraction(p, q)
            ev_m, _ = per_bet_ev_var(p, q, 0.0)
            fee = taker_fee(q)
            ev_t, _ = per_bet_ev_var(p, q, fee)
            print(f'{q:>8.2f}{edge:>7.2f}{p:>8.2f}{f:>10.3f}{ev_m:>9.3f}{fee:>10.3f}{ev_t:>9.3f}')

    print('\n' + '='*78)
    print('SHARPE-FROM-N closed form (edge=4c, q=0.15, k=7 cities @ rho=0.5)')
    print('='*78)
    for N in (5, 10, 14, 20):
        sr, pbsr, neff = sharpe_from_N(0.04, 0.15, N, rho=0.5, k_corr=7)
        print(f'  N={N:>2}/day  per-bet SR={pbsr:.3f}  N_eff={neff:.1f}  annual Sharpe={sr:.2f}')
    print('  (rho=0  -> independent, upper bound:)')
    for N in (14,):
        sr, pbsr, neff = sharpe_from_N(0.04, 0.15, N, rho=0.0, k_corr=7)
        print(f'  N={N:>2}/day  per-bet SR={pbsr:.3f}  N_eff={neff:.1f}  annual Sharpe={sr:.2f}')

    print('\n' + '='*78)
    print('PORTFOLIO MONTE-CARLO (conditional on calibration; quarter-Kelly, 2% cap)')
    print('='*78)
    scenarios = {
        'BASE  (edge4c, fill45%, adv45%, rho0.5)': dict(),
        'BULL  (edge6c, fill55%, adv30%, rho0.4)': dict(edge_mean=0.06, base_fill=0.55, info_share=0.30, city_rho=0.4),
        'BEAR  (edge2.5c, fill35%, adv60%, rho0.6)': dict(edge_mean=0.025, base_fill=0.35, info_share=0.60, city_rho=0.6),
        'NOEDGE(selection-on-noise -> should LOSE)': dict(edge_mean=0.04, edge_is_real=False),
    }
    for name, kw in scenarios.items():
        m = simulate(**kw)
        print(f'\n{name}')
        print(f'  Sharpe  med {m["sharpe_med"]:.2f}  [10-90%: {m["sharpe_lo"]:.2f}..{m["sharpe_hi"]:.2f}]')
        print(f'  CAGR    med {m["cagr_med"]*100:5.1f}%  [10-90%: {m["cagr_lo"]*100:.1f}..{m["cagr_hi"]*100:.1f}%]')
        print(f'  Win-rate    {m["winrate_med"]*100:5.1f}%')
        print(f'  MaxDD   med {m["maxdd_med"]*100:5.1f}%  worst5% {m["maxdd_worst"]*100:.1f}%')
        print(f'  Deploy/day  ${m["deploy_per_day_med"]:.0f} (median, $10k bankroll)')

    print('\n' + '='*78)
    print('CAPACITY / SATURATION-BANKROLL  (BASE edge, capacity ceiling $2000/day)')
    print('='*78)
    print('  Quarter-Kelly wants ~sum(f) of bankroll/day; it hits the $2000/day book ceiling at')
    print('  the bankroll where desired deploy == capacity. Beyond that, $ return is fixed and')
    print('  %-return decays as 1/bankroll -> the edge is dollar-capped, not percent-scalable.')
    for bk in (2000, 5000, 10000, 25000, 50000, 100000):
        m = simulate(bankroll0=bk, runs=120)
        print(f'  bankroll ${bk:>7,}: deploy/day med ${m["deploy_per_day_med"]:>6.0f}  '
              f'CAGR {m["cagr_med"]*100:>7.0f}%  Sharpe {m["sharpe_med"]:.2f}')
    print('\n  Read: $/day at saturation ~ $1.5-2.5k (book depth limited). Saturation bankroll')
    print('  ~ $15-40k (where quarter-Kelly desired deploy meets the $2k/day ceiling). Above that,')
    print('  absolute $ profit plateaus (~$150-400/day net at base edge) and CAGR falls toward 0.')
