# STRAND DEFENSE — the multilayered playbook (v1, 2026-07-13)

Strands are 86% of P&L variance and 100% of the 20 worst outcomes (mean −45c, tail
−85c; paired boxes are near-riskless, σ 3.9c). Strategy: LAYERED defense — each layer
cuts frequency or depth; no layer may buy risk reduction with paired-box volume (the
EV source). Layers are measured individually AND stacked (forward arms), because they
interact: each upstream layer shrinks the population the next layer sees.

## Layer 0 — PREVENT: don't take strand-prone entries
| control | effect | evidence | status |
|---|---|---|---|
| entry gate (depth/k/sig) | ⚠ L0 study: the depth>=median LOWER bound alone is HARMFUL (retains thick/informed tail) — conflicts with PAIR_GATE's window-level validation; stack test adjudicates | L0 study vs PAIR_GATE | under review |
| late-join cap (open-k-max 9→5) | kills the 1.7x leg-restart strand class | manufactured-population replay: monotone, t≤7.6 (nearly inert on natural corpus — live-architecture specific) | validated, AWAITING WORD |
| **L0 CHAMPION: depth UPPER bound (qdepth<=train-q95) + minute<=7** | 90.5% volume, EV +0.74c (t=1.17 NS); runner-up q80+min5: +1.28c t=1.83 at 67% volume | L0 study, 30 candidates | flagged for forward validation (below t=2) |
| cell veto (worst vol×spread opens) | ❌ DEMOTED: BTC-only day-clustered test = HARMFUL (−0.062c, t=−2.40) — pooled +2.77t was likely multiple-testing artifact | L0 study | forward arm will adjudicate; removed from deploy queue |
| composite entry score | reconfirms C1: test AUC 0.511 ≈ random, loses to hand vetoes at every volume | L0 study | dead |
| C3 depth-share veto (mild, >0.9) | book leaning against completion | +1.42c t=5.15 marginal (replay) | backlog top |

## Layer 1 — SENSE: know a strand is developing
| control | effect | evidence | status |
|---|---|---|---|
| 5s pairing hazard model | P(pair next 5s \| state), AUC 0.909, calibrated | pairalarm study | powers Layer 2; logistic-33 is the deployable form (J) |

## Layer 2 — ACT OPTIMALLY: cut losers early, let pairers breathe
| control | effect | evidence | status |
|---|---|---|---|
| state-dependent stopping | +1.11c/box gate-passed t=2.64; adaptive (cuts runaways ~37s, holds oscillators) | replay, 2x reproduced (sensitivity noted, J) | forward-validating (~Jul 23) |
| fixed-deadline retuning | REJECTED — no constant beats live 120s | sweep 15–300s all NS | dead |
| completion repricing (pay up) | REJECTED — worse than binary stop t=−2.66 | C2 study | dead |

## Layer 3 — DISPOSE CHEAPLY: when you do exit, minimize the give
| control | effect | evidence | status |
|---|---|---|---|
| early-cross > late-force | +1.69c/strand | disposal study | live |
| give-cap 0.25→0.15 | caps tail, mean-flat (15–22c identical) | disposal study | validated, AWAITING WORD |
| maker-out first (rest improve 5–10s before crossing) | saves spread+fee when filled | untested | backlog (F8) |

## Layer 4 — HEDGE THE RESIDUAL: strands that survive Layers 0–3
| control | effect | evidence | status |
|---|---|---|---|
| perp hedge-and-hold (D4) | ❌ DEAD: gamma churn costs $1.03/event median (>max payout), variance UP 20x | 214-strand tick-path study | dead |
| perp hedge-and-WAIT | ❌ DEAD: 0/214 completions after decision point — nothing to wait for | same study | dead |
| H1 uncertainty band | moot for L4 (no hold branch survives); retained as a parameter for any future hold logic | settle-basis measurement | shelved |
| D3 ride-the-winner | ❌ DEAD: theo averages 0.255 AGAINST held side at decision — no winner exists to ride | L4 study, 214 strands | dead |

**LAYER 4 CHAMPION: no action (hold-to-settle under Layer 3's give-cap, as today).**
All 13 hedge variants strictly worse on mean/CVaR/variance (best hedge −1.16 vs −0.45;
independent replication matched base study to 3 decimals). Layer 4 is structurally
empty: once Layers 0–3 have done their jobs, the residual strand is an
adverse-selected position with no cheap insurance — the money is upstream.

## Layer 5 — CONTAIN: portfolio-level backstops (when everything above fails)
| control | effect | status |
|---|---|---|
| strand-scaledown 0.75/0.5/0.25 | shrink after consecutive strands | live |
| per-session loss-limit $6 + sticky kill | bounds a leg | live |
| DAILY aggregate loss-limit **$8** | ✅ L5 CHAMPION (2026-07-13): worst day −$15.68→−$8.75, +$31 saved t=2.97, fires 42% of replay days but 0/33 on sign-flipped positive-mean control (zero tax); honesty cost $0.02 total. Falsification control (strand-count stop) failed exactly as F5 predicted — methodology validated. Re-derive threshold after ~20 live days; $10 = conservative fallback | validated, propose with next live batch |
| $55 balance floor → auto switch-off | bounds the experiment | live (enforced, tested) |
| variance guard (P&L percentiles) + activity guard | alarm on statistical anomaly / silent stall | live, 30-min cadence |

## Deployment sequence (each step data-gated)
1. NOW (validated, one word): late-join cap + give-cap 15c.
2. ~Jul 23 (forward gate): hazard stopping — the Layer 2 core; then thickbook/cell
   vetoes as their forward evidence matures.
3. After D4 study: hedge-and-wait replaces or augments Layer 3 crossing if it wins
   on risk-adjusted terms (honest basis-risk accounting required).
4. Daily aggregate loss-limit: propose with next live change batch.
Measurement: box_shadow runs each layer as an arm + a combined arm; FORWARD_LEDGER
tracks marginal contribution per layer so redundant layers get pruned, not stacked
blindly.
