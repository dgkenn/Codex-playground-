#!/usr/bin/env python3
"""Sharpe-optimal bet sizing for the longshot-maker harvest (optimized band p in [0.05,0.15)).
Per contract: buy NO at n~0.90; NO-WIN payoff +(1-n)=+0.111 on collateral, LOSE -n=-1.0 (lose the
whole collateral); NO-win prob w solved from the validated net edge +5.45c/contract. Negative skew.
Model a portfolio of T uncorrelated event-THEMES x b bets/theme, with a small per-theme CORRELATED
'macro blowup' (one surprise sinks every longshot in that theme at once -- the only real risk). Sweep
leverage L (fraction of bankroll deployed) and #themes; report annualized Sharpe/Sortino/maxDD/P(ruin)/
CAGR. Shows: (1) Sharpe is ~scale-invariant in L -> sizing doesn't set Sharpe; DIVERSIFICATION does
(Sharpe ~ sqrt(independent themes)); (2) L sets GROWTH & RUIN -> fractional-Kelly is the right scale.
"""
import random, statistics, math
random.seed(1)
N_EDGE = 0.0545           # validated net $/contract in [0.05,0.15)
NPRICE = 0.90             # NO entry (yes mid ~0.10)
WIN = (1 - NPRICE) / NPRICE     # +return on collateral if NO wins  (+0.111)
LOSE = -1.0                     # lose the whole collateral if the longshot hits
# solve NO-win prob from edge: w*WIN + (1-w)*LOSE = N_EDGE/NPRICE  (edge as return on collateral)
er = N_EDGE / NPRICE
w = (er - LOSE) / (WIN - LOSE)
THEME_BLOWUP = 0.010      # prob a whole theme's longshots get hit together (correlated macro shock)
CYCLES_PER_YEAR = 12      # ~monthly settlement cycles

def sim_cycle(themes, bets_per_theme, L):
    """One settlement cycle. Equal-weight: each bet collateral = L/total_bets of bankroll.
    Returns portfolio return (fraction of bankroll)."""
    total = themes * bets_per_theme
    f = L / total
    r = 0.0
    for _ in range(themes):
        blown = random.random() < THEME_BLOWUP
        for _ in range(bets_per_theme):
            if blown or random.random() > w:    # this longshot HIT -> we lose collateral
                r += f * LOSE
            else:
                r += f * WIN
    return r

def stats(themes, bets_per_theme, L, paths=4000):
    cyc = []
    ruin = 0
    for _ in range(paths):
        eq = 1.0; peak = 1.0; mdd = 0.0; rs = []
        for _ in range(CYCLES_PER_YEAR):
            rr = sim_cycle(themes, bets_per_theme, L)
            eq *= (1 + rr); rs.append(rr)
            peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak)
            if eq <= 0.0: ruin += 1; break
        cyc.extend(rs)
        # store annual for CAGR/maxdd via path
        if not hasattr(stats, "_p"): stats._p = []
    m = statistics.mean(cyc); sd = statistics.pstdev(cyc)
    downside = statistics.pstdev([min(0, x) for x in cyc]) or 1e-9
    sharpe = (m / sd) * math.sqrt(CYCLES_PER_YEAR) if sd else 0
    sortino = (m / downside) * math.sqrt(CYCLES_PER_YEAR) if downside else 0
    cagr = (1 + m) ** CYCLES_PER_YEAR - 1
    return sharpe, sortino, cagr, ruin / paths

print(f"per-bet: NO-win prob w={w:.3f}, win +{WIN*100:.1f}% / lose {LOSE*100:.0f}% on collateral; "
      f"theme-blowup p={THEME_BLOWUP}\n")
print("(A) DIVERSIFICATION is the Sharpe lever (fix L=0.5, 1 bet/theme, vary #independent themes):")
print(f"{'themes':>7} {'Sharpe':>7} {'Sortino':>8} {'CAGR':>7} {'P(ruin)':>8}")
for T in (5, 20, 50, 100, 200, 400):
    sh, so, cg, ru = stats(T, 1, 0.5)
    print(f"{T:>7} {sh:>7.2f} {so:>8.2f} {cg*100:>6.0f}% {ru*100:>7.1f}%")
print("\n(B) Sharpe is ~SCALE-INVARIANT in leverage L (fix 100 themes); L sets GROWTH & RUIN, not Sharpe:")
print(f"{'L':>5} {'Sharpe':>7} {'Sortino':>8} {'CAGR':>7} {'P(ruin)':>8}")
for L in (0.1, 0.25, 0.5, 1.0, 2.0):
    sh, so, cg, ru = stats(100, 1, L)
    print(f"{L:>5} {sh:>7.2f} {so:>8.2f} {cg*100:>6.0f}% {ru*100:>7.1f}%")
print("\n(C) CORRELATION kills Sharpe (fix L=0.5, 100 total bets, vary bets-per-theme = clustering):")
print(f"{'themes x b':>11} {'Sharpe':>7} {'Sortino':>8} {'CAGR':>7}")
for T, b in ((100,1),(50,2),(20,5),(10,10),(4,25)):
    sh, so, cg, ru = stats(T, b, 0.5)
    print(f"{T:>4}x{b:<5} {sh:>7.2f} {so:>8.2f} {cg*100:>6.0f}%")
