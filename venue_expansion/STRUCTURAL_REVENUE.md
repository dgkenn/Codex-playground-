# STRUCTURAL_REVENUE — what the verified stack can actually earn (2026-07-30)

Four Sonnet sweep tracks + Fable review gate (citation spot-checks, net arithmetic vs a ~4%
parked-cash baseline, risk-in-disguise screen). Artifacts: `out/rev_kalshi_programs.json`,
`out/rev_forecastex.json`, `out/rev_crossvenue.json`, `out/rev_stack_product.json`.

Framing: after 42/42 statistical kills, the remaining monetizable object is **contractual revenue**
— money paid by documented program terms — with the stack minimizing the cost of collecting it.
The review's discipline: anything below parked-cash yield is dead; anything whose "revenue" is
redistributed trading risk must carry the measured fill-cost bound.

---

## Killed on arithmetic (before spending anything)

| line | verified fact | why dead |
|---|---|---|
| ForecastEx incentive coupon (Rule 612(c), CFTC-filed rulebook, newly mined from the S3 bucket) | Coupon = (EFFR − 50bp)/2, floor 0 → **1.565%** min at today's 3.63% EFFR | Below parked cash (3.9% T-bill / ~3.1–4.3% IBKR) at every holding period, before the $0.02/pair fee (466-day breakeven). One worker reported it as "$391–1,565/yr high-confidence" — that was gross-vs-net; the review caught it |
| Kalshi APY (3.25% on cash + open positions, verified live, $250 min) | DOCUMENTED | −$5 to −$10/mo vs T-bill at $10k standalone. Survives **only** as a carry offset for capital already parked at Kalshi for another reason |
| Polymarket maker rebate (25%) + liquidity rewards | real | US-person geo-block — non-deployable, stated plainly |
| ProphetX liquidity rewards (~$2k/day pool reported) | both cited sources 403'd | UNVERIFIED — cannot be ranked until a primary source is read; sports-only regardless |
| Selling raw archive access | six comparables priced | dead end: incumbent data products sit on a free CC-BY archive; one paid comparable's own traction widget shows zero on every metric |

## The ranked survivors

**1. Kalshi Liquidity Incentive Program — the single live candidate, with a clock on it.**
Verified live: $10–$1,000/day reward pools, **presence-based per-second scoring** (order size ×
proximity to touch — *not* fill-based), US-eligible, no approval gate, MM-agreement holders
excluded (we are not one). Net at $1–5k capital: **−$100 to +$300/mo — sign genuinely unknown**,
because two load-bearing parameters are unverified: the pool share a small quoter actually gets,
and the proximity discount (if off-touch orders score ~0, you're forced to the touch, where the
measured fill P&L sits at the pessimistic −8.81c/ct bound — the reward would be partly
redistributed short-vol risk). **Newly discovered hard deadline: the program window ends
2026-09-01.** The runway itself is the scarce resource.

**2. Graveyard publication.** The 42 adversarially-verified kill reports as a research publication
(free + small paid tier; $20/mo comparable weakly corroborated). Realistic ~$0–100/mo. The only
line with **no counterparty, no capital, no program-expiry risk, and no way to go net-negative**;
2–5h/mo, content already exists.

**3. Settlement-truth audit engagements.** $0–500/mo, demand unproven, tooling exists. Below #2
because it requires finding buyers rather than shipping existing content.

## The review's recommended next action (operator decision — real money, small)

A **2-week de minimis LIP pilot**: minimum-size, distance-laddered resting quotes in 3–5 markets,
≤$1,000 collateral, measuring three numbers no document will reveal:
(a) actual daily score share and $ payout at known size/distance;
(b) fill rate on resting orders;
(c) realized per-fill adverse-selection cost vs the −8.81c/ct measured bound.

Pre-registered falsifiers, each cheap and fast:
1. First weekly payout < realized fill losses (net-negative even with the 3.25% APY offset) → dead in ~7 days.
2. Proximity discount zeroes off-touch orders → forced at-touch quoting at the pessimistic fill
   bound → dead on the first adverse fill cluster.
3. Kalshi lets the program lapse 2026-09-01 with no successor → dead by calendar, zero effort.

If falsified → fall back to #2 (ship the graveyard publication; ~$0 cost, no expiry).

## Honest ceiling

Even the best case here is **hundreds per month, not thousands** — reward pools are shared,
capital yields are anchored to short rates, and the publication market is niche. Nothing in this
document changes the program's core finding; it changes what kind of number the revenue is
(documented terms + one measurable unknown, instead of a statistical edge that 42 studies failed
to find).
