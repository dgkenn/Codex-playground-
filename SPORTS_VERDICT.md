# Sports betting — consolidated verdict (2026-06-15)

Synthesis of the full sports research program (8 rounds): line-value (SHARP_VS_KALSHI), promo extraction,
props, cross-book/Kalshi arb, live/steam, niche-sport modeling, + the can't-ban-exchange + timing-lag
collector. The question throughout: a deployable +EV sports edge for a US small-bankroll, cloud operator.

## Scorecard
| Angle | Verdict | Realistic $ |
|---|---|---|
| **Promo / bonus extraction** (matched betting) | ★ **THE deployable win** | **$1–5k one-time** + ~$100–300/mo decaying |
| Sharp-line vs Kalshi deviation | Liquid Kalshi is SIG-sharp (calibrated ±0.3c); deviation < spread | ~0 on liquid |
| **Kalshi maker TIMING-LAG** | **Unconfirmed — collector armed** (add ODDS_API_KEY) | TBD; the one live experiment |
| Player props | Walled on books (8–15% vig, $250 limits, fastest limiting); Kalshi lists props (can't-ban) but thin | forward CLV test only |
| Cross-book arb | Real (1–3%) but fast-closing + arbers limited in weeks | a few hundred $/mo, decaying |
| Kalshi-vs-book arb | Divergence usually < Kalshi fee + book vig on liquid; can't-ban leg helps structurally but thin | marginal |
| Live / in-game / steam | **Dead** — latency-walled (cloud is slowest node) + limiting-walled, same as the crypto box | 0 |
| Niche-sport modeling | Real edge ~2–5% gross (darts best; esports lower-tier; TT fixing-contaminated) but tiny limits + fast limiting | few hundred $/mo grind |

## The one thing actually worth doing: PROMO EXTRACTION
The single net-positive, deployable sports play (SPORTS_PROMO_EV.md). It works because the edge is a
customer-acquisition SUBSIDY, not a mispricing you must out-sharp: sign-up bonuses / bonus bets / profit
boosts convert to ~70–80c/$ guaranteed via hedging. **~$1–5k one-time** across all books in your state
(~$150–400/hr of effort), then **~$100–300/mo** reloads/boosts while accounts survive — DECAYING, because
books limit promo-takers within days-to-weeks. **Kalshi / Novig / ProphetX solve the can't-ban HEDGE leg**
(the blocker our line-value studies hit). Not a $500/mo annuity, but real, accessible, low-risk cash for a
small bankroll. Do this; bank the one-time haul; treat reloads as depleting side income.

## Why everything else fails (the three universal walls)
1. **Limits + fast limiting** (the decisive wall): soft books limit winners within hours-to-weeks — MA
   regulator data shows winners cut to as little as **$3.63** on props; CLV (beating the close) is the #1
   limiting trigger. So even a real % edge can't be scaled into dollars on soft books.
2. **Efficiency / thinness on can't-ban venues**: Kalshi (and exchanges) are SIG-priced and efficient on
   anything liquid (deviation < spread+fee), and genuinely soft only where they're too THIN for capacity.
   The eternal soft↔thin / deep↔efficient wall.
3. **Latency** (for live/steam): a seconds-latency cloud bot is the slowest node — structurally dead, same
   as the Kalshi crypto box (last-in-queue behind a co-located MM / faster bettors).
Plus: soft NICHE markets carry HIGHER vig (6–15%) and the LOWEST limits, and modeling them needs real work.

## The one live experiment: Kalshi maker timing-lag
Unconfirmed but not refuted: does Kalshi follow a sharp line move with a lag a 0-fee MAKER can capture? The
collector is built and no-ops safely until you add a (free) ODDS_API_KEY secret (SPORTS_CLV_SETUP.md), then
auto-logs Pinnacle-vs-Kalshi to gha-data/sports_clv/; kalshi_clv_lag.py runs the cross-correlation once
~300–500 games accrue. Deploy only on positive, stable net-of-cost CLV. Headwind: Kalshi's sportsbook-hedging
rebate is pulling sharp money on (rising efficiency over time).

## Kalshi's real structural role in sports
Not as a place to find soft lines (it's SIG-efficient), but as the **can't-ban, US-legal EXCHANGE leg**:
(a) the hedge venue for converting sportsbook promo bonus bets, and (b) the maker venue for the timing-lag
experiment. That is the genuine, durable contribution of the prediction-market venue to a sports strategy.

## BOTTOM LINE
Sports does NOT change the project's core answer (a systematic risk-premium portfolio — START_HERE.md /
PROJECT_VERDICT.md). But it adds one genuinely useful, do-it-now play: **promo extraction for a ~$1–5k
one-time bankroll boost** (hedged on Kalshi), plus **one armed forward experiment** (the Kalshi maker
timing-lag, pending your odds-API key). Line-value, props, arb, live, and niche modeling are all real-but-
walled (limits/efficiency/latency) — not deployable income for a small cloud operator.
