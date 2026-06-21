# Longshot-maker harvest — OPTIMIZED strategy (consolidated) 2026-06-21

Synthesis of the optimization sweep (goal: "make it the best strategy it can be"). Three workstreams —
edge segmentation (`KALSHI_LONGSHOT_OPT.md`), execution (`KALSHI_LONGSHOT_EXEC.md`), and the box A/B
counterparty-avoidance transfer (`KALSHI_LONGSHOT_ABXFER.md`) — all point the same way. Baked into
`kalshi_longshot_bot.py`.

## The optimized rule (one line)
Be the maker who **sells overpriced YES longshots** (rest a NO bid AT the touch) in the band **p ∈ [0.05, 0.15)**
on **zero-maker-fee** soft series (prefer Entertainment / Sci&Tech / Climate), **only in the first ~half of a
market's life**, **dodging informed flow**, **holding to settlement** but **taking profit if YES halves** and
**never stop-lossing**.

## Edge, honestly stated
- **Naive baseline:** +0.97c/contract (the whole [0.02,0.20] band, all timing) — and that "17σ" was clustered
  by FILL; the correct **event-clustered** significance is far lower (the right unit, since fills within an
  event are not independent).
- **Optimized band p∈[0.05,0.15):** **net +5.45c/contract, event-clustered 95% CI [+3.2c, +7.7c]** — ~3–5×.
  Replicates BH-significantly across 4 categories (+4.0–7.6c) AND a held-out event split (z 2.4 / 9.6).
- **+ Execution timing** (first-half only): the deep value is in the early/mid market; the final third is
  NEGATIVE (−1.6 to −3.1c). Filling early adds ~+0.8–1.3c and cuts the negative skew.
- **+ Counterparty-avoidance gates** (A/B transfer): filtering toxic fills added +0.4–2.9c/fill in the box;
  porting take-tail-trim + one-sided-flow gate (wired) should add on top and may re-open higher bands.
- **Realistic target after optimization: ~+5–7c/contract** in the core band, lower variance (only ~9% of
  events lose), with the toxicity gates as additional upside still to be A/B-validated forward.

## The config (in `kalshi_longshot_bot.py`, all env-tunable)
| Knob | Optimized default | Source |
|---|---|---|
| Price band | `LONGSHOT_BAND_LO=0.05 / HI=0.15` | OPT — sweet spot; <0.05 thin, ≥0.15 no edge |
| Categories | Entertainment, Sci&Tech, Climate, (Politics untestable) | OPT — BH-significant cells |
| Life gate | `LONGSHOT_MAX_LIFE_FRAC=0.50` (first half only) | OPT (+1.3c) + EXEC (late third −) |
| Placement | rest AT the NO touch, never improve | EXEC — improving costs −1.8c (queue front-run) |
| Flow guard | `flow_toxic`: skip large takes (>100) + one-sided YES-buy | ABXFER (box t33/t32) |
| Hold/exit | hold to settle; take profit if YES ≤ 0.5×fill; NEVER stop-loss | EXEC (+1.1c; stops realize −22 to −27c) |
| Cadence | re-quote ~5 min | EXEC — touch near-static, no fast pickoff |
| Sizing | tiny clips, per-theme cap, diversify across uncorrelated events | RISK (negative skew) |

## What optimization did and did NOT change
- **DID:** ~3–5× the per-contract edge (+0.97c → ~+5c core), much lower variance, removed the negative late-third
  band, added toxic-flow filtering. The strategy is materially better and safer.
- **DID NOT:** raise capacity. The richer band holds only ~21% of low-band flow; **the ~$30–150/mo ceiling
  stands.** This is an edge-QUALITY optimization, not a capacity unlock, and **not** a path to $500/mo (that
  remains the portfolio route, `PROJECT_VERDICT.md`).

## Remaining upside (next, A/B'd forward on the paper-track, net of adverse selection)
1. **VPIN open-gate** (port `box_policy_ab._vpin`) — the biggest unported counterparty-avoidance lever.
2. **Toxicity-conditioned exit** (refit the box tox model on Kalshi fills) — box's single biggest lever (+2.1c).
3. **Face-contrarian candidate ranking** — prefer FOMO-bought longshots, skip informed ones.
Validate each as a paper-track A/B variant vs the current optimized baseline before going live.
