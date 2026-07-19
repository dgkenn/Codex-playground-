#!/usr/bin/env python3
"""daily_return_frontier.py -- statistically-sound reality-check on the "~10%/day, minimized risk" goal.

Builds the ACHIEVABLE daily-return frontier from the program's ONE confirmed edge (Polymarket weekly
crypto-longshot short-vol premium) plus the stacked sleeves, using a correlation-aware Monte Carlo, and
solves exactly what "10%/day" would demand. No live capital; PROPOSE-ONLY analysis.

Edge mechanics (documented, node PMKT-SHORTVOL-CONFIRMED):
  Sell a far-OTM weekly "BTC/ETH above $X" YES longshot at price p in [0.15,0.30] (== buy NO at 1-p).
  Capital at risk per contract = (1-p). Outcome per contract on capital:
     YES resolves FALSE (longshot misses, prob 1-pi): return = +p/(1-p)
     YES resolves TRUE  (longshot hits,  prob   pi):  return = -1.0   (total loss of that stake)
  Documented mean PnL/contract ~ +0.12 (price minus true prob, p - pi ~ 0.12), t=4.6 in recompute.
  => the seller wins the small amount often, loses the whole stake rarely: a SHORT-VOL / lottery premium
     with a FAT LEFT TAIL. Crypto longshots are CORRELATED (one big rally makes many pay at once) -> the
     Monte Carlo uses a shared market factor, which is the honest driver of tail risk.

We simulate a diversified weekly book (crypto short-vol + ~uncorrelated econ/biz sleeves), report the
weekly & daily-equivalent return distribution, drawdown and RUIN probability at several sizing fractions,
then solve for the leverage needed to hit 10%/day and report the ruin that leverage implies.
"""
import random, math, statistics as st

random.seed(12345)  # deterministic (Date/random restrictions don't apply to plain scripts, but fix seed anyway)

# ---- edge parameters (from DECISION_MAP confirmed nodes; conservative/base case) ----
P_SELL      = 0.22     # avg longshot sell price (band [0.15,0.30]); capital at risk = 1-p
EDGE_PER_CT = 0.12     # documented mean PnL/contract (p - pi). forward may be thinner -> sensitivity below
# implied true hit prob pi = p - edge:
PI_HIT      = P_SELL - EDGE_PER_CT           # ~0.10 true prob the longshot hits (you pay $1)
CAP         = 1.0 - P_SELL                    # capital at risk per contract (buy NO at 1-p)
WIN_RET     = P_SELL / CAP                    # return on capital when longshot misses (+)
LOSS_RET    = -1.0                            # return on capital when longshot hits (total loss of stake)

# book structure
N_CRYPTO    = 12       # ~independent-ISH crypto longshot positions available per week (capacity-limited)
N_ECON      = 4        # macro-release bucket sells (uncorrelated w/ crypto, -0.01)
N_BIZ       = 3        # business/company longshots (marginal, uncorr +0.07)
RHO_CRYPTO  = 0.45     # within-crypto correlation via a shared BTC/ETH factor (the honest tail driver)
WEEKS       = 100_000  # Monte Carlo paths


def crypto_week():
    """One week of crypto longshot outcomes with a shared market factor (correlated hits)."""
    # shared latent: a big up-move raises ALL longshots' hit prob together
    z = random.gauss(0, 1)
    rets = []
    for _ in range(N_CRYPTO):
        e = random.gauss(0, 1)
        latent = math.sqrt(RHO_CRYPTO) * z + math.sqrt(1 - RHO_CRYPTO) * e
        # map latent to a hit with marginal prob PI_HIT (Gaussian-copula threshold)
        hit = latent > _norm_ppf(1 - PI_HIT)
        rets.append(LOSS_RET if hit else WIN_RET)
    return rets


def indep_week(n, pi, p):
    cap = 1 - p
    wr = p / cap
    return [(-1.0 if random.random() < pi else wr) for _ in range(n)]


def _norm_ppf(q):
    # Acklam's inverse-normal approximation (no scipy)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if q < pl:
        z = math.sqrt(-2 * math.log(q)); return (((((c[0]*z+c[1])*z+c[2])*z+c[3])*z+c[4])*z+c[5]) / ((((d[0]*z+d[1])*z+d[2])*z+d[3])*z+1)
    if q > ph:
        z = math.sqrt(-2 * math.log(1-q)); return -(((((c[0]*z+c[1])*z+c[2])*z+c[3])*z+c[4])*z+c[5]) / ((((d[0]*z+d[1])*z+d[2])*z+d[3])*z+1)
    z = q - 0.5; r = z*z
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*z / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def sim_book(kelly_frac):
    """Return list of weekly book returns (fraction of bankroll) at a given sizing fraction.
    Equal risk-weight across all positions; kelly_frac scales total exposure (1.0 = full bankroll deployed)."""
    weekly = []
    for _ in range(WEEKS):
        rets = crypto_week() + indep_week(N_ECON, 0.25, 0.22) + indep_week(N_BIZ, 0.28, 0.22)
        n = len(rets)
        # each position gets kelly_frac/n of bankroll as capital at risk
        w = kelly_frac / n
        weekly.append(sum(w * r for r in rets))
    return weekly


def path_stats(weekly, label, n_weeks_path=52, paths=20000):
    """Compound weekly returns into paths; report drawdown + ruin."""
    mean_w = st.mean(weekly)
    sd_w = st.pstdev(weekly)
    daily_eq = (1 + mean_w) ** (1/7) - 1 if mean_w > -1 else float('nan')
    # ruin / drawdown via resampled compounding paths
    ruin = 0; maxdds = []
    for _ in range(paths):
        eq = 1.0; peak = 1.0; dd = 0.0; busted = False
        for _ in range(n_weeks_path):
            eq *= (1 + random.choice(weekly))
            if eq <= 0.02:  # <=2% of bankroll = practical ruin
                busted = True; break
            peak = max(peak, eq); dd = max(dd, 1 - eq/peak)
        ruin += busted; maxdds.append(dd if not busted else 1.0)
    return dict(label=label, mean_w=mean_w, sd_w=sd_w, daily_eq=daily_eq,
                sharpe_w=mean_w/sd_w if sd_w else float('nan'),
                ann_sharpe=(mean_w/sd_w*math.sqrt(52)) if sd_w else float('nan'),
                ruin=ruin/paths, med_maxdd=st.median(maxdds))


def main():
    print("="*88)
    print("REALITY-CHECK: '~10%/day, minimized risk, statistically sound' vs the confirmed edge")
    print("="*88)
    print(f"\nEdge unit (documented): sell weekly longshot @ p={P_SELL:.2f}, true hit pi={PI_HIT:.2f}, "
          f"edge={EDGE_PER_CT:+.2f}/ct")
    print(f"  per-contract on capital({CAP:.2f}):  miss(+{WIN_RET*100:.0f}%) w.p.{1-PI_HIT:.2f}   "
          f"hit({LOSS_RET*100:.0f}%) w.p.{PI_HIT:.2f}")
    print(f"  book: {N_CRYPTO} crypto (rho={RHO_CRYPTO}) + {N_ECON} econ + {N_BIZ} biz = "
          f"{N_CRYPTO+N_ECON+N_BIZ} positions/week")

    print("\n--- (1) COMPOUNDING REDUCTIO: what 10%/day IS ---")
    for horizon, days in [("1 week", 7), ("1 month", 30), ("1 year", 365)]:
        g = 1.10 ** days
        print(f"  10%/day compounded over {horizon:8}: x{g:,.4g}   ($50 -> ${50*g:,.4g})")
    print("  => 10%/day for a year turns $50 into ~1000x world GDP. No edge scales; this rate cannot exist.")

    print("\n--- (2) ACHIEVABLE FRONTIER: diversified book at several sizing fractions ---")
    print(f"{'sizing':>10}{'wk mean':>10}{'wk sd':>9}{'day-eq':>9}{'wk Sharpe':>11}{'annSharpe':>11}"
          f"{'52wk ruin':>11}{'med maxDD':>11}")
    results = {}
    for kf in [0.10, 0.25, 0.50, 1.00]:
        w = sim_book(kf)
        s = path_stats(w, f"kelly={kf}")
        results[kf] = s
        print(f"{kf:>10.2f}{s['mean_w']*100:>9.2f}%{s['sd_w']*100:>8.2f}%{s['daily_eq']*100:>8.2f}%"
              f"{s['sharpe_w']:>11.2f}{s['ann_sharpe']:>11.2f}{s['ruin']*100:>10.1f}%{s['med_maxdd']*100:>10.1f}%")

    print("\n--- (3) WHAT 10%/DAY DEMANDS (solve for leverage) ---")
    target_daily = 0.10
    target_weekly = (1 + target_daily) ** 7 - 1
    base = results[0.25]  # a sane risk-minimizing sizing
    lev_needed = target_weekly / base['mean_w'] if base['mean_w'] > 0 else float('inf')
    print(f"  target 10%/day = {target_weekly*100:.1f}%/week compounded.")
    print(f"  at risk-minimizing sizing (kelly=0.25) the book earns {base['mean_w']*100:.2f}%/week")
    print(f"  => leverage needed ~ {lev_needed:.1f}x. Simulating that leverage:")
    w_lev = sim_book(0.25 * lev_needed)
    s_lev = path_stats(w_lev, "10%/day-levered")
    print(f"     levered book: wk mean {s_lev['mean_w']*100:+.1f}%  day-eq {s_lev['daily_eq']*100:+.2f}%  "
          f"52wk RUIN {s_lev['ruin']*100:.0f}%  med maxDD {s_lev['med_maxdd']*100:.0f}%")
    print("     (max loss per position is -100% of its stake; leverage that targets 10%/day makes a single")
    print("      correlated bad week -- several longshots hitting together -- a bankroll-ending event.)")

    print("\n--- (4) VERDICT ---")
    best_sound = max((s for kf, s in results.items() if s['ruin'] < 0.01),
                     key=lambda s: s['daily_eq'], default=None)
    if best_sound:
        print(f"  Max STATISTICALLY-SOUND daily-equivalent (ruin<1% over a year): "
              f"~{best_sound['daily_eq']*100:.2f}%/day  ({best_sound['label']}, "
              f"{best_sound['mean_w']*100:.1f}%/wk, annSharpe {best_sound['ann_sharpe']:.1f}).")
    print("  10%/day at minimized risk is INFEASIBLE: it is ~{:.0f}x the sound book's daily rate and requires"
          .format(target_daily / (best_sound['daily_eq'] if best_sound else 0.01)))
    print("  ruinous leverage. The sound plan targets the FRONTIER above, not 10%/day.")
    print("  NB: even these figures assume the backtest edge holds forward at size; forward gates will")
    print("  confirm/haircut it. Correlation (rho) and thinner forward edge only LOWER the sound rate.")


if __name__ == "__main__":
    main()
