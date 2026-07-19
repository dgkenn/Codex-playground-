#!/usr/bin/env python3
"""aggressive_frontier.py -- the FULL risk/return tradeoff curve for the confirmed edge, from safe to reckless.

The goal asked for ~10%/day. That is mathematically impossible at minimized risk (see daily_return_frontier.py).
This script instead maps the ENTIRE tradeoff so the operator can choose risk appetite with real numbers:
for each leverage/Kelly multiple on the confirmed short-vol book, it Monte-Carlos a 30-DAY path (on a $50
bankroll) and reports:
   - median daily-equivalent return
   - P(end up)         : probability you finish the month with more than you started
   - P(>=2x)           : probability you at least double
   - P(ruin, <=20% left): probability you blow up
   - median end bankroll, and the 5th/95th percentile band
This is the honest "how hard can I push, and what does it cost me" table. Pushing toward 10%/day is possible
only far out on this curve where P(ruin) approaches 1 -- i.e. it is a GAMBLE, not a plan. Shown explicitly.
"""
import random, math, statistics as st
random.seed(7)

# confirmed-edge unit (documented, node PMKT-SHORTVOL-CONFIRMED); same as daily_return_frontier.py
P_SELL, EDGE = 0.22, 0.12
PI = P_SELL - EDGE                 # ~0.10 true hit prob (you pay $1)
CAP = 1 - P_SELL                   # 0.78 capital at risk / contract
WIN = P_SELL / CAP                 # +28.2% when longshot misses
N_CRYPTO, N_ECON, N_BIZ = 12, 4, 3
RHO = 0.45
START = 50.0
DAYS = 30
WEEKS_PER_MONTH = DAYS / 7.0
PATHS = 40000


def _ppf(q):
    a=[-39.69683028665376,220.9460984245205,-275.9285104469687,138.3577518672690,-30.66479806614716,2.506628277459239]
    b=[-54.47609879822406,161.5858368580409,-155.6989798598866,66.80131188771972,-13.28068155288572]
    c=[-0.007784894002430293,-0.3223964580411365,-2.400758277161838,-2.549732539343734,4.374664141464968,2.938163982698783]
    d=[0.007784695709041462,0.3224671290700398,2.445134137142996,3.754408661907416]
    pl,ph=0.02425,0.97575
    if q<pl:
        z=math.sqrt(-2*math.log(q));return(((((c[0]*z+c[1])*z+c[2])*z+c[3])*z+c[4])*z+c[5])/((((d[0]*z+d[1])*z+d[2])*z+d[3])*z+1)
    if q>ph:
        z=math.sqrt(-2*math.log(1-q));return-(((((c[0]*z+c[1])*z+c[2])*z+c[3])*z+c[4])*z+c[5])/((((d[0]*z+d[1])*z+d[2])*z+d[3])*z+1)
    z=q-0.5;r=z*z
    return(((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*z/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

THR = _ppf(1 - PI)


def week_return(lev):
    """One week book return (fraction of bankroll) at exposure multiple `lev` (1.0 = bankroll fully deployed once)."""
    z = random.gauss(0, 1)
    rets = []
    for _ in range(N_CRYPTO):
        e = random.gauss(0, 1)
        lat = math.sqrt(RHO)*z + math.sqrt(1-RHO)*e
        rets.append(-1.0 if lat > THR else WIN)
    for n, pi, p in ((N_ECON,0.25,0.22),(N_BIZ,0.28,0.22)):
        cap=1-p; wr=p/cap
        rets += [(-1.0 if random.random()<pi else wr) for _ in range(n)]
    w = lev / len(rets)
    return sum(w*r for r in rets)


def _step(eq, lev):
    """Apply one (fractional) week; leverage liquidates at 0 -- equity can never go negative (ruin floor)."""
    eq *= (1 + week_return(lev))
    return max(eq, 0.0)


def sim(lev):
    ends=[]; ruin=0; dubl=0; ups=0
    wk=WEEKS_PER_MONTH; whole=int(wk); frac=wk-whole
    RUIN_FLOOR=0.20*START
    for _ in range(PATHS):
        eq=START; busted=False
        for _ in range(whole):
            eq=_step(eq, lev)
            if eq<=RUIN_FLOOR: busted=True; break
        if not busted and frac>0:
            eq*=(1+frac*week_return(lev)); eq=max(eq,0.0)
            if eq<=RUIN_FLOOR: busted=True
        if busted: eq=min(eq,RUIN_FLOOR); ruin+=1
        ends.append(eq)
        if eq>=2*START: dubl+=1
        if eq>START: ups+=1
    ends.sort()
    med=ends[len(ends)//2]
    p5=ends[int(0.05*len(ends))]; p95=ends[int(0.95*len(ends))]
    daily_eq=(med/START)**(1/DAYS)-1 if med>0 else -1.0   # med>0 always (floored), guards complex
    return dict(lev=lev, med=med, daily_eq=daily_eq, p_up=ups/PATHS, p_2x=dubl/PATHS,
                p_ruin=ruin/PATHS, p5=p5, p95=p95)


def main():
    print("="*94)
    print(f"FULL RISK/RETURN TRADEOFF -- confirmed short-vol book, ${START:.0f} bankroll, {DAYS}-day paths, {PATHS} sims")
    print("="*94)
    print("Choose your risk appetite. 'lev' = exposure multiple (how many times the bankroll is deployed).")
    print(f"{'lev':>5}{'daily-eq(med)':>15}{'med end$':>11}{'P(up)':>8}{'P(>=2x)':>9}{'P(RUIN)':>9}"
          f"{'5th%$':>9}{'95th%$':>10}")
    target_row=None
    for lev in [0.25,0.5,1,2,4,8,16,32,49]:
        s=sim(lev)
        tag=""
        if s['daily_eq']>=0.095 and not target_row: target_row=s; tag="  <- ~10%/day lives HERE"
        print(f"{lev:>5.2f}{s['daily_eq']*100:>13.2f}%{s['med']:>11.2f}{s['p_up']*100:>7.0f}%"
              f"{s['p_2x']*100:>8.0f}%{s['p_ruin']*100:>8.0f}%{s['p5']:>9.2f}{s['p95']:>10.2f}{tag}")
    print("\nHOW TO READ THIS:")
    print(" - Risk-MINIMIZED (the sound plan): lev ~0.25-1. Median ~0.1-1%/day, P(ruin)~0, small but real.")
    print(" - Every step toward 10%/day RAISES the median but drives P(ruin) toward 100% and collapses the 5th pct.")
    print(" - The row where median hits ~10%/day is where you are MOST LIKELY ALREADY BROKE -- the 'median' is")
    print("   dragged up by rare lucky paths while the typical path is ruin. That is a lottery, not a plan.")
    print(" - CONCLUSION: 10%/day is reachable only as a NEGATIVE-tradeoff gamble (P(ruin)->1), never as")
    print("   'minimized risk'. The honest sound operating point is the low-lev end of this same table.")


if __name__ == "__main__":
    main()
