# STRAND DEFENSE — the multilayered playbook (v1, 2026-07-13)

Strands are 86% of P&L variance and 100% of the 20 worst outcomes (mean −45c, tail
−85c; paired boxes are near-riskless, σ 3.9c). Strategy: LAYERED defense — each layer
cuts frequency or depth; no layer may buy risk reduction with paired-box volume (the
EV source). Layers are measured individually AND stacked (forward arms), because they
interact: each upstream layer shrinks the population the next layer sees.

## Layer −1 — CALENDAR/REGIME (researched 2026-07-13): NO deployable rule
6 candidates, 9 cells, macro dates verified against BLS/BEA/Fed primary sources.
Well-powered clean nulls: macro event days (MDE 1.58c), weekends (MDE 1.28c),
trailing-vol and prior-day-return regimes (sign flips train→test). One watch item:
Friday ~19-22 UTC POSITIVE anomaly (EV t=+3.03, 5/5 Fridays agree, survives 6
robustness checks) — but n=5 and 1-of-9-cells multiple-testing exposure → track
~8-10 more Fridays, no action (and it's positive: nothing to defend against).
Champion: trade the calendar flat, as today.

## Layer 0 — PREVENT: don't take strand-prone entries
| control | effect | evidence | status |
|---|---|---|---|
| entry gate (depth/k/sig) | ⚠ L0 study: the depth>=median LOWER bound alone is HARMFUL (retains thick/informed tail) — conflicts with PAIR_GATE's window-level validation; stack test adjudicates | L0 study vs PAIR_GATE | under review |
| late-join cap (open-k-max 9→5) | kills the 1.7x leg-restart strand class | manufactured-population replay: monotone, t≤7.6 (nearly inert on natural corpus — live-architecture specific) | validated, AWAITING WORD |
| **L0 CHAMPION: depth UPPER bound (qdepth<=train-q95) + minute<=7** | 90.5% volume, EV +0.74c (t=1.17 NS); runner-up q80+min5: +1.28c t=1.83 at 67% volume | L0 study, 30 candidates | flagged for forward validation (below t=2) |
| cell veto (worst vol×spread opens) | ❌ DEMOTED: BTC-only day-clustered test = HARMFUL (−0.062c, t=−2.40) — pooled +2.77t was likely multiple-testing artifact | L0 study | forward arm will adjudicate; removed from deploy queue |
| composite entry score | reconfirms C1: test AUC 0.511 ≈ random, loses to hand vetoes at every volume | L0 study | dead |
| C3 depth-share veto (mild, >0.9) | book leaning against completion | +1.42c t=5.15 marginal (replay) | backlog top |

## Layer 0.5 — QUOTE CONSTRUCTION (researched 2026-07-13): JOIN survives
5 structural variants replayed (harness reproduced the 214-strand baseline exactly).
THEO-anchored quoting ❌ decisively dead (−0.85c t=−4.66, strand +2.16pp t=6.74).
BACK-1c ❌ falsifies "backing off is safer" — deeper-sweep fills are MORE toxic.
IMPROVE-1c ❌ flat-to-worse. ASYM (join predicted-completing side, back the other,
from pre-fill book thinness) 🟡 only candidate beating JOIN in BOTH halves on EV
(+0.37c), strand (−0.64pp) AND markout — but sub-t=2: forward-arm candidate, not
deployment. Champion: JOIN (status quo).

## Layer 1 — SENSE: know a strand is developing
| control | effect | evidence | status |
|---|---|---|---|
| 5s pairing hazard model | P(pair next 5s \| state), AUC 0.909, calibrated | pairalarm study | powers Layer 2 |
| **L1 CHAMPION: UNCERTAINTY-LCB** (7-model bootstrap ensemble; wait_edge uses hazard LOWER confidence bound — conservative when unsure) | gate-passed +1.150c t=2.81 (vs baseline +1.110c t=2.64); all 7 challengers clustered near baseline = sensor near ceiling | L1 study, fixed-pipeline money metric | deployable numpy form verified: logit-LCB gate +1.081c t=2.56 |

## Layer 1.5 — PRE-FILL WITHDRAWAL (researched 2026-07-13): ❌ CLOSED
0/18 arms significant. The finding: median danger-signal lead time before a fill is
1.2 SECONDS — one tick. There is no 'before' to defend in; pulls avoid fills that
would have paired 90-95% of the time and replacements are statistically identical.
Completes the epistemic trio (C1 at-fill ceiling, sweep-fill null, B1 null): the
strand information does not exist until AFTER the fill — which is exactly why
Layer 2 post-fill stopping is where all the money is.

## Layer 2 — ACT OPTIMALLY: cut losers early, let pairers breathe
| control | effect | evidence | status |
|---|---|---|---|
| state-dependent stopping (incumbent) | +1.11c/box gate-passed t=2.64 | replay, 2x reproduced | forward-validating (~Jul 23) |
| **L2 CHAMPION: 2-step lookahead** w2 = hz·(dist+fee) − (1−hz)·E[dca] + (1−hz)·wait_edge(s+5), κ=−0.5c | gate +1.176c t=2.82, capture 29.2%, false-fire 0.802 (better than incumbent on all three) | L2 study, 10 candidates; near-miss: join-aware κ (+1.130c t=2.25, false-fire slightly over bar) | forward-test alongside incumbent |
| dca cost model replacement | ❌ tested and worse (corr 0.132 HGB-mean stands) — NOT the weak link | L2 study | dead |
| hazard-floor AND-gate | ❌ degenerates to incumbent (wait_edge already embeds hazard) | L2 study | dead |
| fixed-deadline retuning | REJECTED — no constant beats live 120s | sweep 15–300s all NS | dead |
| completion repricing (pay up) | REJECTED — worse than binary stop t=−2.66 | C2 study | dead |

## Layer 3 — DISPOSE CHEAPLY: when you do exit, minimize the give
| control | effect | evidence | status |
|---|---|---|---|
| early-cross > late-force | +1.69c/strand | disposal study | live |
| give-cap 0.25→0.15 | caps tail, mean-flat (15–22c identical) | disposal study | validated, AWAITING WORD |
| maker-out first (rest improve 5–10s before crossing) | ❌ DEAD on the hard-strand population: fill rate only 12-14% while forced-hold fallbacks (give grows past cap while waiting) climb 3-6x faster and cost ~90c each; test t=−3.9 to −7.6 across ALL wait-based mechanics (spread-wait, two-tranche, completion-race, adaptive cap all rejected) | L3 study, 214 strands | dead |

**LAYER 3 CHAMPION: INCUMBENT — cross immediately at decision, ask+fee, give-cap 15c.**
99% of strands cross at s=0 for mean give ~3.4c; there is almost nothing left to
optimize. Stranded legs settle ITM only 0.9% of the time (near-total toxicity) —
every second of waiting is exposure to a ~90c forced-hold tail. Give-cap resweep
reconfirms 15c (18c 'improvement' = n=1, t=1.00).

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

## STACK TEST VERDICT (2026-07-13, engine reproduced all layer studies bit-for-bit)
STACK-FULL vs current live policy (BTC, test days, day-clustered):
EV/window −4.34c→−3.28c (Δ+1.47c, t=2.84) · strand 6.73%→2.14% · CVaR5 −55.6c→−27.1c
· variance −59% · worst day −$10.98→−$7.09 · holds on per-retained-window AND per-day
EV (not a volume-cut mirage).
LOO ablations (the point of the exercise):
- L2 2-step stopping is the engine of the stack.
- L0 contributes ~0 EV inside the stack but carries tail protection.
- ⚠ L1-LCB and L3-cap15 have NEGATIVE marginal inside the stack — the base sensor
  and the live 25c cap each beat their 'champions' once L2 is present (cap15
  converts ~17/983 borderline crosses into forced holds = near-total losers).
  Champions-in-isolation ≠ champions-in-stack.
- L5 dormant on the stack's own path (0/13 days) — correct backstop behavior.
DEPLOYMENT PATH: ✅ WIRED (161cd2e73 on bot branch, 2026-07-13): STACK-FULL +
STACK-LEAN forward arms live in box_shadow; box_shadow_report.py computes the
per-arm RISK benchmark table (variance, CVaR5, worst day, day-Sharpe, max DD,
day-clustered deltas) for the daily ledger. LEAKAGE AUDIT: the L2 2-step replay
DID use realized next-step state (confirmed leakage); the honest expectation
version scores gate +1.128c t=3.04 (vs leaky +1.176c t=2.82, gap only 0.048c) —
the edge SURVIVES delooking, and the arms embed the honest coefficients. L1-LCB
deployable ensemble verified (+1.083c t=2.57). Fidelity: zero legacy-field
mismatches; new arms sane.
Promote whichever wins the forward gate (~10 days). Give-cap 15c REMOVED from the
awaiting-word queue pending forward adjudication (stack evidence now contradicts
its isolation evidence). Late-join cap unaffected (live-architecture fix, outside
this replay's scope) — still validated, still awaiting word.

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
