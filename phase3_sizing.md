# K-WX bet-sizing optimization (small bankroll)

Monte Carlo (`kwx_sizing.py`) over the REAL 1,698 deployable per-fire outcomes (config margin1/sustain3,
price<99¢), including the actual −1.0/−0.77 losses, with realism the naive backtest lacks:
- **21% unfillable** fires (empty book at the fire instant — Tier-1 S3),
- **latency haircut** (price/PnL taken 5 min after the cross → mean +0.161/ct, vs +0.207 at 0 min),
- a **2%/day synthetic "heat-dome contagion" day** where every fire loses — a stressor for the correlated
  tail the benign 65-day history (0 net-negative days) cannot show.

## The key finding: the PER-FIRE CAP is the dominant risk lever (not Kelly fraction)
$50 bankroll, 60-day runs × 4,000 trials, 5-min latency:

| per-fire cap | median $50→ | 5th-pct | ruin% | net-loss% |
|---|---|---|---|---|
| **5%** | **$1,494** | **$956** | **~0%** | **0%** |
| 10% | $1,706 | $974 | 4.6% | 2.9% |
| 20% | $1,758 | **−$1** (WIPED) | 9.1% | 7.9% |

Loosening the per-fire cap from 5%→20% buys ~+17% median growth but takes ruin from ~0 to ~9% and can wipe
the account on a single contagion day. **Not worth it.** Kelly fraction (0.05→1.0) barely moves the result
once the 5% cap binds. So the optimum is a *tight cap*, not aggressive Kelly.

## Recommended sizing (frozen into `kwx_runner.py`)
- **Quarter-Kelly** (`KELLY_FRAC=0.25`) × **5% hard per-fire cap** (`PER_FIRE_CAP=0.05`) × **17.5% per-city
  daily cap** × per-station derate (Phoenix ×0.25 & margin 3; KLAX/KMIA/KPHL/KSEA ×0.5 & margin 2).
- On $50 this means ~$1–2.50 risked per fire (1–5 contracts; cheaper/bigger-gap fires get more; Phoenix →1).
- Result: ruin ≈ 0, 5th-percentile stays well above the starting stake, ~20% drawdowns are normal.

## Honest read on the return
In-sim median growth is strong (~5–6%/day at 5-min latency, higher at 2-min) BUT:
- It is **optimistic** — it assumes the backtested edge holds on live fills; only the forward paper gate
  (`kwx_forward.py`) can confirm live==tested. Treat ~5%/day as a hypothesis, not a promise.
- It does **not reliably hit 10%/day** at realistic latency; ~5–6%/day is the honest median. 10%/day needs
  either the optimistic 2-min feed *and* everything going right, or stacking another orthogonal edge.
- Growth is depth/fill-limited: the $50→~$1,500 plateau over 60 days reflects the ~$1–1.6k/week capacity
  ceiling, not edge decay. Beyond a few hundred dollars, absolute growth flattens.

## Bottom line
On $50: size at **quarter-Kelly with a hard 5% per-fire cap** — that keeps ruin ≈ 0 while capturing nearly
all the achievable growth. The cap, not the Kelly fraction, is what protects you. Confirm the assumed edge
on the forward paper gate before scaling the bankroll.
