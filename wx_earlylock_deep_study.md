# EARLY-LOCK fleet deep study (settlement-truth-corrected, post-adversarial-review) — 2026-07-20

## Verdict

**No decision-grade positive-EV cell exists for the EARLY-LOCK tail-capture idea, and neither of the two
overconfident stories that preceded this doc is right.** The first fleet aggregate concluded "every cell is
negative — cheap tails are adverse-selected, the market is right, this is a loss leader"; that conclusion was
itself broken by an outcome-truth bug (chunk_1, the largest single contributor to the headline cell, was
scored against strict IEM `final > strike` instead of its own recorded Kalshi settlement, silently flipping 22
real wins — all boundary cases where `final == strike` and the NO-side cap-only rung the study actually traded
pays on `final >= strike` — into recorded losses). Rescoring with settlement truth uniformly flips the sign of
9 of 36 primary grid cells from negative to positive, including the headline cell (**+1.43c/contract**, was
−8.78c) and the best n≥5 cell (**+2.52c/contract**, was −7.16c). But none of these corrected positive point
estimates is statistically distinguishable from zero: day-clustered |t| runs **0.28–1.6**, far short of the
**≈3.11** bar a proper Bonferroni correction demands across the 27 effectively-distinct grid cells actually
being mined here, and the headline cell's sign is not even stable within its own sample (+9.6c in the first
half of the window, −8.1c in the second). **The honest verdict is "EV consistent with zero — do not deploy,"
not "proven negative" (the original claim) and not "proven positive" (what a naive re-score would wrongly
conclude).**

## Verified numbers (reproduced by `wx_earlylock_deep_study.py` from the committed `wx_earlylock_deep_data.json`)

Sample frame: 20 `kwx_runner.CITY` stations, HIGH+LOW, 65 LST days (2026-05-15..2026-07-18), per-day
leave-one-out climatology recomputed in-window (independently re-verified leakage-clean — see Caveats §5).
29,995 LOO signal-fire events (16 fully-enumerated stations); 2,521 matched a real single-sided ("tail") Kalshi
rung, the doc-canonical bet.

| quantity | value |
|---|---|
| Headline cell (th=0.95, delay=+0, cap=97c) | n=49, win 85.7% (42/49), **taker EV +1.43c** [95% CI −11.0,+8.6], day-clustered t=0.28 |
| Best n≥5 primary cell (th=0.95, delay=+0, cap=93c) | n=31, win 80.7% (25/31), **taker EV +2.52c** [95% CI −14.4,+12.7], day-clustered t=0.35 |
| Positive point-EV primary cells (of 36, n≥5) | 9 — all at threshold 0.95 (8 cells) plus one at 0.97/delay+15/cap97 |
| Secondary pool (tail+bracket, not decision-grade — see below) best cell, settlement-corrected | n=186, win 80.6%, **taker EV +4.04c**, day-clustered (147 clusters) t=1.60 |
| Bonferroni bar for significance | |t| or |z| ≥ **3.11** (27 effectively distinct cells: the 95c/95.3c caps are byte-identical since Kalshi asks are integer cents, so 36 nominal cells collapse to 27) |
| Temporal split of headline cell at 2026-06-16 | early: n=25, win 96.0% (24/25), EV **+9.60c** — late: n=24, win 75.0% (18/24), EV **−8.08c** |
| Deployed mechanical-lock baseline (yardstick, not re-derived here) | taker EV ≈ +1.1c/contract, ~98c entry, ~99.6% win |
| chunk_1 settlement-vs-IEM disagreement (the bug) | 22 of 1,741 settled rows — 100% in the direction win(settlement)=True / cleared(IEM)=False |

Every number above is reproduced live by `wx_earlylock_deep_study.py` against the committed dataset — run it,
it prints the full 36-row grid plus every table in this doc.

## Policy / parameter recommendation

**Do not add the EARLY-LOCK tail-capture strategy to the deployed mechanical-lock bot.** Not because it is
proven to lose (the original claim was wrong), but because there is no cell — in either pool, at any
(threshold, delay, cap) combination — whose edge clears ordinary significance after accounting for the fact
that 27 cells were mined to find it. The single best-looking cell (+2.52c, best n≥5) is a 0.35-sigma result
picked out of 27 look; it is not evidence of an edge.

If this is ever revisited, the concrete next step is **not** another backtest cut of the same 65-day window —
it is a forward paper shadow-arm using the same gating machinery the deployed strategy already validated
against (`kwx_paper_gate.py`'s PASS bar: win≥99%, EV/ct≥+0.12, day-clustered t≥3, n≥30 settled fires), with
outcome truth taken from Kalshi settlement uniformly for every leg (never the IEM-extreme-vs-strike comparison
that caused this study's central bug). Expected time-to-gate at the observed ~1.4 tail-eligible signals/day
(fleet-wide, cap 93–97c, threshold 0.95) is on the order of 3 weeks to accumulate n=30 — not itself
prohibitive, but pointless to start without first fixing the outcome-truth pipeline end to end.

## What the verifier panel killed, and why

| # | claim in the pre-review aggregate | verifier verdict | disposition here |
|---|---|---|---|
| 1 | "Every (threshold×delay×cap) cell with n≥5 shows a NEGATIVE point-estimate taker EV" / "tail-only best cells are 6–9c worse than deploy-baseline" / "adverse selection on cheap tails, loss leader" (billed as the single most important finding) | **[FATAL]** — outcome-truth bug: chunk_1's 1,741 settled matched rows all carry an authoritative Kalshi `win` field, but the original aggregator scored them with strict IEM `final > strike` instead, silently mixing two outcome definitions across chunks (2/3 used settlement, chunk_1 used IEM). 22 settled rows disagree, all in the direction that flips a loss to a win. Live-verified 3 of them directly against the Kalshi API. | **Killed as stated.** Rescored with settlement truth: headline cell +1.43c (was −8.78c), best n≥5 cell +2.52c (was −7.16c), 9/36 cells flip positive. Corrected grid ships in this doc/dataset; the "uniformly negative" and "loss leader" framing is removed. |
| 2 | (implicit, after fix) "there is a decision-grade positive-EV cell" | **[MAJOR]** — even corrected, no cell clears significance: best cluster |t|≈0.3–0.5, headline |t|=0.28, secondary-pool best |t|≈0.8–1.6, all far under the ≈3.1 Bonferroni bar for the 27 effectively distinct cells actually being mined (no multiplicity correction was applied in the original aggregate). Headline cell is temporally unstable: +9.6c first half of the window, −8.1c second half. | **Reframed, not resurrected.** Verdict changed from "uniformly negative" to "consistent with zero, not decision-grade" — see Verdict above. This is the headline of this document. |
| 3 | "This pool is the doc-canonical actual tradeable single-sided Kalshi rung... every event a valid, correctly-sided tail match" | **[MAJOR]** — 2,422 of 2,521 tail-pool rows (96%) are NO-side purchases against cap-only rungs, not the documented buy-YES-on-a-floor-rung tail bet; only 99 rows (46 from chunk_0/4's narrow direct-YES matcher, 53 from chunk_1/3's yes-side tail rows) are the literal doc-canonical bet. Economically near-equivalent EXCEPT at the exact boundary (`final==strike`) — the same boundary the FATAL bug mishandled. | **Disclosed, not fixed** (fixing would mean discarding 96% of the pool and losing all power). Reported here as a caveat: the corrected numbers above describe "buy the cheap side of a single-sided rung, NO included," not narrowly "buy YES on the floor." |
| 4 | leakage from the frozen `_earlylock_climatology.json` fit window overlapping the eval window | **[MINOR]** — checked adversarially and **survived**: all five harvesters recompute per-day leave-one-out climatology in-window; the frozen fixed-climatology JSON is never loaded by any of them (verified by grep across the harvest scripts — only docstring mentions). Residual: in-window LOO still grants each eval day up to ~2 months of *future* days via the LOO pool, plus disclosed synoptic day-to-day autocorrelation across heat waves — both bias toward optimism, meaning the null/negative conclusion is if anything conservative, but the +1.4..+2.5c point estimates above should be discounted further, not taken at face value. | **Carried forward as a caveat**, not corrected (no clean fix available without re-harvesting on a true walk-forward window, out of scope here). |
| 5 | 8.33% match rate / 1.45 signals-day availability stats | **[MINOR]** — the 29,995-signal denominator is built over a synthetic, outcome-anchored strike universe (`round(realized final extreme) + fixed offsets`), not the real Kalshi ladder, so match-rate/availability percentages are an artifact of the enumeration band. | **Disclosed as a caveat**; does not affect any EV cell (those require a real matched rung, independent of the enumeration band), only the "how often would this fire" framing. |

## Exact activation conditions (staged gate — mirrors `kwx_paper_gate.py`'s PASS-bar pattern)

```
GATE: add EARLY-LOCK tail-capture as a strategy alongside the deployed mechanical-lock bot
STATUS: ❌ NOT ACTIVATED (backtest EV statistically indistinguishable from zero after correction)

PASS requires ALL of:
  - forward (not backtest) paper fires: n >= 30 settled
  - forward day-clustered t >= 3.0            (kwx_paper_gate.py's own bar; this backtest's best is 0.35)
  - forward taker EV/ct >= +1.1c              (>= deployed baseline, not just >= 0)
  - outcome truth = Kalshi settlement uniformly for every leg, INCLUDING NO-side cap-only rungs
    (never IEM final-extreme-vs-strike — that substitution is what produced the FATAL bug here)
  - sign stable across a temporal split of the forward sample
    (this backtest's headline cell failed this: +9.6c early half vs -8.1c late half)

Context, not a gating criterion: at the only threshold with any positive cells (0.95), tail-eligible
signals fire at ~1.4/day fleet-wide (16 fully-enumerated stations, cap 93-97c, delay 0-5min) -- so
accumulating n=30 forward fires would take roughly 3 weeks once a shadow arm is running. Not
deployment-blocking by itself; simply means don't expect the gate to fill fast.

NEXT STEP IF REVISITED: stand up a forward-paper shadow arm reusing kwx_paper_gate.py's existing
settle/report loop, NOT another backtest slice of this same 65-day window.
```

## Caveats carried into this document

1. **Tail-pool composition** (table row 3 above): 96% of the "tail" pool is a NO-side purchase against a
   cap-only rung, not literally "buy YES on the floor" as documented. Near-equivalent in expectation except at
   the exact `final == strike` boundary.
2. **Leakage residual** (table row 4): per-day LOO is leakage-free by construction but not immune to
   day-to-day synoptic autocorrelation across a multi-day heat wave — a known, disclosed, mild optimism source
   inherited from the original study, biasing this document's numbers slightly positive, not negative.
3. **Small n throughout**: even the largest primary cell (n=49) is thin for a Wilson CI; every headline number
   above ships with its CI/t for exactly this reason — read the point estimates as suggestive, not as evidence.
4. **Bracket-NO pool (secondary)** answers a structurally different question ("final NOT in [floor,cap]") than
   the intended single-sided tail bet and is reported for context only, never as the primary answer.
5. This document does not re-query Kalshi's settlement endpoint live (the FATAL-bug fix reuses chunk_1's
   already-fetched `win` field, which the panel spot-verified live against 3 tickers); no new network calls
   were made building this document, consistent with economy-mode call-volume sharing.

## Reproducing this document

```
python3 wx_earlylock_deep_study.py            # prints every table above
python3 wx_earlylock_deep_study.py --json      # same tables as machine-readable JSON
```

Reads only the committed `wx_earlylock_deep_data.json` (event-level rows for the 5,415 matched signal events
across all 5 fleet harvester chunks, plus sample-frame summary counts) — no network calls, no dependency on
the raw scratch chunk caches (which stay out of git). Does not import, call, or modify `kwx_runner.py`,
`kwx_paper_gate.py`, `kalshi_exec.py`, or `kwx_daily_digest.py`.
