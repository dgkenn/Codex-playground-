# FINALITY-NO + WHOLE-LADDER — pre-registered spec (REGISTERED 2026-10-27, before any outcome is read)

Companion to `TERMINAL_FINALITY_SPEC.md`, which tests FINAL-**YES** on bracket rungs. This spec tests
the two shapes that spec deliberately left out, both of which the deployed rule also cannot express.

## Part 1 — FINAL-NO by never-arrival

A bracket `[lo, hi]` settles NO two ways:
- **overshoot** — the extreme went past `hi`. The deployed rule CAN lock this (cap-overshoot). Not retested.
- **never arrived** — the extreme stayed short of `lo`. The deployed rule has **no code path for this**.

Measured motivation: of the 40 highest-net capturable markets in `edge_sizing_v2.json`,
**22 settled NO, 19 of them brackets, with nets up to 85c**.

**Why this may beat FINAL-YES:** locking YES needs the extreme to land *inside* a narrow bracket — a
precise condition. Never-arrival needs only a *wide gap*. If the running max is 85°F at 16:00 local
and the rung is `[92,93]`, no precision is required. Wider target, more robust inference, same
latency tolerance.

**Signal (obs-only).** At observation time `t` with running extreme `E(t)`, declare **FINAL-NO** on
rung `[lo, hi]` at the first `t` satisfying all of:
1. **Gap**: for HIGH markets `E(t) <= lo - G`; for LOW markets `E(t) >= hi + G`
2. **Reversed and held**: the series has moved away from `E(t)` by `R` and held `H` consecutive obs
3. **Terminal window**: `t` within `W` minutes of `close_time`

Grid (frozen): `G ∈ {2, 4, 6}` °F · `R ∈ {2, 4}` °F · `H = 3` · `W ∈ {60, 120}` min → **12 cells**.
Primary cell declared now: `G=4, R=2, H=3, W=120`.

**Entry.** A FINAL-NO fire always buys **NO**, so its executable cost is **`100 − yes_bid`** — never
`100 − yes_ask` (that is the NO bid, unfillable by a buyer). First candle at/after signal with cost
≤98c and fee-inclusive net > 0. No qualifying minute ⇒ UNTRADEABLE, counted, never back-filled.

## Part 2 — Whole-ladder pricing from one inference

Once the extreme is final, **every rung on that city-day is simultaneously determined**: exactly one
wins, all others lose. The deployed bot has always fired per-rung. A single finality inference prices
the entire ladder.

This is the only hypothesis in the program that could change the **size** of the answer rather than
its sign. Capacity is the binding limit on everything measured so far ($15–75/mo), and a
one-inference-many-rungs structure multiplies fires per signal.

**Measurement.** On each city-day where either finality signal fires, evaluate **every** rung on that
event's ladder: the determined winner (buy YES at `yes_ask`) and every determined loser (buy NO at
`100 − yes_bid`), each gated on the ≤98c + positive-net test independently. Report:
- fires per city-day (the multiplier), and total per-day net
- whether per-rung EV **degrades** as the ladder widens (adverse selection concentrating in the rungs
  nearest the extreme is the expected failure mode — report EV by |distance from extreme| in rungs)
- the correlation structure: all rungs on one day share one inference, so **one wrong inference loses
  the whole day's basket.** Day-clustered statistics are therefore mandatory and the cluster is the
  city-day, not the fire.

## Shared data and mechanics (all verified available)

- Universe: settled `KXHIGH*`/`KXLOWT*` rungs with official `result` and candlestick coverage,
  closing 2026-05-23 .. 2026-10-20.
- Outcome: Kalshi official `result` field ONLY.
- Obs: IEM `asos1min.py`, routine `asos.py` (`report_type=3&report_type=4`) as disclosed fallback.
- Prices: Kalshi 1-minute candlesticks. Fee `ceil(7·p·(1−p))` cents at the crossing price.
- Latency arms `L ∈ {0, 10, 20}` min added to every signal timestamp. **`L=10` is the deployable
  arm** (IEM archive publishes 22–34h late; a live bot runs MADIS ~10 min).
- Reuse `edge_sizing_v2.normalize()` for candlestick parsing. Do NOT reuse `kwx_lock_rule.py` logic.

## PASS / KILL — frozen now

Bonferroni across **both parts**: Part 1 has 12 cells × 3 arms = 36; Part 2 adds 3 arms = 3; total
**39 comparisons**. Two-sided α = 0.05/39 = 0.00128 ⇒ bar is the exact Student-t quantile at
p=0.99936 on realised df (≈3.5 at df 60–120). **Signed** t: a negative t clearing the magnitude is
evidence for KILL, never PASS.

**Part 1 PASS** requires ALL, in the `L=10` arm, in ≥1 cell:
1. false-lock rate ≤ 2% with Wilson 95% upper ≤ 5%
2. volume-weighted fee-inclusive EV ≥ **+2.0c/contract**
3. signed day-clustered t ≥ the exact Bonferroni bar
4. n ≥ 100 priced fires across ≥ 40 distinct days and ≥ 10 stations
5. untradeable fraction ≤ 70%

**Part 2 PASS** requires Part 1 or `TERMINAL_FINALITY_SPEC` to pass, AND: mean fires per signalling
city-day ≥ 3, AND per-day net EV ≥ +4.0c, AND day-clustered t over city-days ≥ the Bonferroni bar.

**KILL** if: false-lock > 5% in the primary cell; or the `L=10` best one-sided 97.9% upper bound on
EV < +0.5c; or every EV>0 cell misses its n floor. Otherwise INSUFFICIENT.

## Sanity anchors (each must hold or the result is void)

- **(a) Oracle subset** — fired rungs must be a subset of `edge_sizing_v2.json`'s capturable set on
  the overlapping window. Firing where the oracle says nothing was buyable ⇒ price join is broken.
- **(b) No look-ahead** — the signal must read only obs timestamped `< t`. "Reversed and held" must be
  evaluated on a prefix, never the full series. Assert in code; show a worked example.
- **(c) Monotonicity** — running max non-decreasing, running min non-increasing within the local day.
- **(d) Overshoot separation** — Part 1 must report never-arrival and overshoot fires separately.
  Overshoot is already covered by the deployed rule; mixing them would overstate the new finding.

No bar in this document may move after 2026-10-27. A PASS is necessary-but-not-sufficient; the only
permitted next step is a separately-registered 1-contract live canary.
