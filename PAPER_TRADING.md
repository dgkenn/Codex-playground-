# Paper-trading candidate: inventory-capped 2-sided maker (rebate farming)

## Strategy
On Polymarket **BTC 15-minute Up/Down** markets, continuously **quote both the Up and
Down tokens** at/near the touch (provide liquidity, never cross). Maintain a **net
inventory cap** in Up-equivalent units (long Up = +1, long Down = −1, since Up+Down=1):
when a fill would push |net delta| past the cap, **withdraw/skew the breaching side**
(quote only the inventory-reducing side). Hold residual inventory to the 15-min
resolution (residual is bounded by the cap).

Recommended start: **cap ≈ 50 with inventory skew 0.25** (refined optimum — see below).

### Refinement (tested): tight inventory cap removes rebate-dependence
A **tight** cap makes the trading edge positive *before* any rebate (pure vig capture with
minimal directional risk), with near-zero drawdown:

| cap | gross-only t (OOS) | net+rebate t (OOS) | maxDD |
|---|---|---|---|
| 10 | +10.6 (5.9) | 24.0 (13.3) | \$0 |
| 20 | +7.1 (4.1) | 21.4 (11.9) | \$1 |
| 25 | +5.8 (3.3) | 19.9 (11.0) | \$11 |
| 75 | +1.5 (1.5) | 13.3 (8.0) | \$82 |

**Zero-rebate stress (cap=25): gross-only +0.00019/sh, t=5.8, OOS t=3.3 — survives with the
rebate OFF.** So the rebate is no longer a single point of failure; it ~triples the return on
top of a positive gross. Tighter cap = higher Sharpe + gross-robust + smaller \$; looser cap
= more \$ but rebate-dependent. Start tight (cap≈20), scale the cap only after live fills
confirm the gross holds. Adjacent ideas tested and REJECTED: per-quote size limits and
stop-quoting-late both reduced the edge (the 2-sided vig scales with captured volume).

## Why it works (and the honest source of the edge)
- **Makers pay 0 fees and earn a ~20% rebate** of the taker fees their liquidity
  generates (crypto). Takers pay 0.07·p·(1−p).
- Quoting **both sides** is naturally delta-hedged on matched flow (the ~2–3c
  overround is captured risk-free); the **inventory cap** bounds the directional risk
  from imbalanced/informed flow.
- **The net edge IS the rebate.** Backtest decomposition (cap=100): gross trading
  PnL ≈ **+0.00007/share (t=0.81, breakeven)**; the rebate turns it to **+0.00098/share
  net (t=12.2)**. It is a market-neutral *yield* strategy, not directional alpha.

## Backtest evidence (Apr 14–16 2026, 288 windows; extended set confirming)
| cap | net/share | t | IS / OOS t |
|---|---|---|---|
| 25 | +0.00066 | +19.2 | 23.1 / 10.6 |
| 100 | +0.00098 | +12.2 | 12.2 / 7.4 |
| 400 | +0.00133 | +7.7 | 5.7 / 5.4 |
- Robust: positive & significant **out-of-sample**, and survives a **50% rebate
  haircut** (cap=100 OOS t=4.3). Model is counterparty to *all* realized flow, i.e.
  worst-case adverse selection — gross is conservatively estimated.

## What paper trading must measure (the live unknowns the backtest CANNOT settle)
1. **Fill rate / queue position** — backtest assumes you are the counterparty to flow;
   live you capture only a fraction. Log fills vs quotes-posted and queue depth.
2. **Realized rebate** — the 20% is a pool split pro-rata among makers; measure the
   actual rebate/USDC received vs taker fees your fills generated.
3. **Adverse-selection weighting** — do you get filled *more* on the toxic side than
   the proportional model assumes? Track per-fill 30s markout.
4. **Gross PnL must stay ≈ 0** — there is **no cushion**; if gross goes meaningfully
   negative, the rebate won't cover it.

## Risks / boundaries
- Edge is **policy-dependent** (Polymarket can change the rebate) — single point of failure.
- **Capacity** limited by captured volume (tight cap → small \$, high Sharpe).
- Requires **low-latency quoting** to win the queue; otherwise fill rate (and rebate) collapse.
- Not directional alpha — do not expect it to survive without the rebate.

## Go/no-go for live capital
Deploy tiny → if paper shows gross ≈ 0 (or better), realized rebate ≥ ~50% of model,
and fill rate sufficient for positive net → scale cautiously. If gross is materially
negative or rebate << model → stop.

### Config frontier (skew=risk knob, cap=size knob; all gross-only CIs >0)
| config | net OOS t | net 95% CI | maxDD |
|---|---|---|---|
| cap=20 skew=1.0 | 11.5 | [.00055,.00066] | $1 |
| **cap=50 skew=0.25 (start)** | 11.0 | [.00087,.00105] | $7 |
| cap=100 skew=0.15 (scale) | 10.8 | [.00111,.00136] | $0 |
Edge is gross-positive WITHOUT the rebate across all (rebate-independent). $ scales with
captured volume (queue-dependent): ~$1.2k/day at 10% capture, tiny at $100. Flow-filter and
near-0.5 price-filter were tested and REJECTED (hurt net).
