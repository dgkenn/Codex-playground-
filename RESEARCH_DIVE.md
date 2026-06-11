# Deep research dive — 4 areas, 20 solutions, tested where possible

Literature + data dive across: (1) detecting legs likely to pair, (2) avoiding legs unlikely to
pair, (3) hedging at small size, (4) bet sizing. Plus (5) a directional-signal ensemble (separate
doc, in progress). Each area: 5 cited solutions, mapped to our box-maker, with test status.

## ⭐ TESTED — Bet sizing (the one fully backtested, 20,318 fills, IS/OOS, risk-of-ruin)

| rule | OOS net/win | OOS Calmar | maxDD | **risk of ruin** |
|---|---|---|---|---|
| flat-1 | +0.76¢ | 0.47 | $7.4 | 4.5% |
| **current "kelly" proxy** | **−3.24¢** | −0.66 | $25 | **52%** ⚠️ |
| **R1 half-Kelly (K=2)** | **+3.72¢** | **2.87** | $6.9 | 7.7% |
| R2 completion-weighted Kelly | +1.51¢ | 0.47 | $14.9 | 24% |
| R5 **inventory cap=1 (our clamp)** | +0.69¢ | 0.92 | $3.5 | **0.1%** |

**Verdicts:** (a) **Half-Kelly (K=2) is the growth winner** — best OOS net AND Calmar (2.87, 6× flat),
lower drawdown than flat-1, ruin 7.7%. (b) **Inventory cap=1 (our current clamp) is the
preservation winner** — ruin 0.1%, the lowest. (c) **Aggressive/edge-chasing Kelly is DANGEROUS** —
the "current-kelly" proxy had **52% risk of ruin** and lost OOS. **Action: our live `--size-mode
kelly` upsizes to 2 contracts on "strong edge" — that's the dangerous lever; the clamp bounds it but
we should cap upsizing or move to flat/half-Kelly-within-cap.** (d) completion-weighted Kelly beats
flat on mean but doubles ruin — hold for forward validation, don't deploy on the tiny bankroll.

**Recommended: keep inventory cap=1, size 1 contract base, and only upsize toward half-Kelly when the
edge estimate is BOTH positive and stable — never the raw aggressive Kelly.**

## Area 1 — Detecting legs likely to pair (completion prediction)
Five predictive features to add to the completion model (fit logistic/GBM on "box completed?"):
1. **OFI sign-agreement** (Cont-Kukanov-Stoikov 2014) — do YES-side and NO-side order-flow
   imbalances point the SAME way? Same-direction = momentum = only one leg fills. One-line feature.
2. **Microprice dislocation** (Stoikov 2018) — `|microprice−your_bid|` summed over both legs; high =
   market repricing away = box won't complete.
3. **Queue-ahead ratio** (Huang-Lehalle-Rosenbaum 2015) — your position / same-side depth, both sides;
   the interaction (both queues thin) is the completion signal.
4. **Depth-rebuild rate** (Bechler-Ludkovski 2017) — d(top-5 depth)/dt; draining depth on the
   unfilled side = won't complete.
5. **Survival time-to-fill** (Wallbridge 2024) — conditional fill-time percentile by price×minute;
   if both legs unfilled late in the window, completion probability collapses.

## Area 2 — Avoiding legs unlikely to pair (pre-fill toxicity gates)
Five gates that fire BEFORE the adverse fill (skip/pull the soon-toxic side):
1. **Queue-imbalance one-tick-ahead** (Gould-Bonart 2016) — `|QI|>0.6` predicts the next tick;
   fastest signal, suppress the light side. 
2. **Microprice-vs-mid divergence** (Stoikov) — `(micro−mid)/(spread/2) > 0.3` = imminent move.
3. **Multi-level OFI z-score** (Cont et al.) — `|OFI_z|>2` across 5+ levels = directional pressure.
4. **VPIN gate** (Easley-LdP-O'Hara) — `VPIN>0.70` = toxic regime; already wired (`t13`).
5. **Cancel-side asymmetry** — cancel surge on one side before any price move = informed repositioning.

*Most of these need the full-depth book (microprice, QI, depth-delta) — available in our live book
stream (accumulating) but not the candle tape; VPIN/OFI/flow are tape-testable now.*

## Area 3 — Hedging at small size (the perp doesn't fit; these do)
1. **Cross-strike Kalshi binary** — hedge an "above K" leg with a "below K" binary, same venue, $0.01
   granularity, US-legal. The native small-size hedge.
2. **Correlated-asset binary** — ETH15M/SOL15M (BTC-SOL corr ~0.99); minimum-variance ratio ≈ ρ.
3. **Fractional spot BTC (Coinbase ~$1 min) / IBIT shares** — binary delta is tiny (~$4 notional per
   leg), so micro-spot fits where the perp's $1000 minimum doesn't.
4. **IBIT weekly puts** — only once the book aggregates >$500 net delta (gamma/tail hedge).
5. **Internal book netting** (Siu-Elliott 2023) — net delta across simultaneous legs FIRST; research
   shows single-instrument delta hedge ≈ as good as multi for short tenors. Only ~10-20% of windows
   need an external hedge after netting.

**The standout small-size hedge: cross-strike / correlated-asset binaries — same venue, same tiny
contract size, US-legal — testable on our BTC+ETH+SOL tapes.**

## What's testable next (the user wants everything tested)
- Completion features (Area 1) + toxicity gates (Area 2): the flow/VPIN ones on the tape now; the
  depth ones (microprice/QI) as the live book stream accumulates → fit one completion model, compare
  to the heuristic.
- Hedging (Area 3): backtest cross-strike + ETH/SOL correlated-binary hedges on our multi-asset tapes.
- Sizing: DONE above. Action item: tame the live Kelly upsizing.
