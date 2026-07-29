# S3 — ForecastEx Daily Temperature: **KILL** (2026-07-29)

Pre-registered spec S3, executed on the frozen bars and adversarially verified.
**Verdict: KILL — upheld and strengthened.** ForecastEx Daily Temperature is dead for the mechanical-lock
mechanism on **two independent pre-registered grounds**.

Window 2026-02-17..2026-07-26 (temperature contracts did not exist before 2026-02-17 — measured, not
assumed). 9 stations: LAX LAS LGA SEA SFO MIA PHX MDW AUS. **8,646 resolvable locks.**

Reproduce: `venue_expansion/spec_S3_B.py`; records in `out/spec_S3_B.json`, method in `out/spec_S3_B.md`.

---

## The two kills

### 1. Settlement basis is unsound — 190 false locks (2.20%)

| | measured | bar |
|---|---:|---|
| False locks | **190 / 8,646** | ≤1 |
| Rate | 2.198% | — |
| Wilson one-sided UB (z=2.128) | **2.559%** | ≤2.5% ❌ |

Also trips the hard pre-registered kill: *">4 false locks — basis to WU settlement unsound, stop
pricing, publish the basis failure."*

**Mechanism, and it is structural rather than a bug:** ForecastEx settles on Weather Underground's
**METAR-sourced** daily extreme — a 5-minute-averaged value at routine (~hourly + SPECI) cadence.
The signal reads IEM's **true 1-minute** ASOS record. Genuinely sustained 2–4°F excursions lasting a
few minutes are **structurally invisible to settlement**. ForecastEx's own NTM_2026-45 confirms the
METAR sourcing.

Worked case re-derived end-to-end from raw files: `UHLGA_061226_95`, KLGA 2026-06-12 — the 1-minute
archive shows 96/98/98/99/98/96°F across 20:53–20:58Z (a genuine sustain-3 clear of 95+1), while the
venue's own settlement ladder puts the official high at exactly **94°F**, and the tape never priced
YES above 12c all day. The market was right and the 1-minute feed was "right" about a different
quantity.

Broad-based across every station (AUS 1.07% → PHX 4.64%), so not one bad sensor. Monotone in lock
cushion: 2°F → 183/7,615 false; 3°F → 10/481; 4°F → 2/245; **0 false at every cushion ≥5°F.**

### 2. Where the basis holds, the fee kills it

The cushion table suggests an obvious escape — demand ≥5°F cushion, where false locks vanish. **It
closes off**, and this is the elegant part of the negative. High cushion means the excursion is
obvious, which means the market has already repriced. Decomposing the 2,854 priced fires by first
fill:

| population | n | clusters | win | mean net EV | clustered t |
|---|---:|---:|---:|---:|---:|
| fill ≥98c (tape agrees the lock is confirmed) | 1,006 | 643 | 99.9% | **−0.571c** | **−5.66** |
| fill ≥95c | — | — | — | +0.066c | 0.81 |
| fill <80c (tape disagrees) | 750 | — | 83.1% | +28.41c | — |

At fill ≥98c the one-sided 98.33% **upper** bound is **−0.357c**, below the +0.2c threshold — so the
spec's own symmetric EV kill fires **independently**, on exactly the death the hypothesis
pre-identified.

**And the headline number was population mixing, not an edge.** The build reported +9.20c/contract at
t=15.42, which is implausibly large. **81.2% of all P&L comes from the 26.3% of fires printing below
80c** — precisely where the venue's market flatly disagrees the contract is locked, and which win only
83.1% of the time. That is a *directional bet that a 1-minute spike foreshadows the official record*,
which is not the registered mechanism and is not a mechanical lock. Both builds and the verifier agree
it must not be treated as a survivor.

**Caveat I want stated precisely:** the −0.571c at fill ≥98c includes the spec's **frozen 1c slippage
penalty** on top of the 1c fee. Without that penalty it would be about +0.43c. The penalty was
pre-registered as the conservatism substitute for an unavailable order book, so it cannot be dropped
after the fact — but the EV leg does materially depend on it. **The basis kill (leg 1) does not depend
on it at all**, so the KILL stands regardless.

---

## Correcting something I told you

Before launching, I pushed back on the sweep agent's claim that ForecastEx's flat $0.01 fee was
disqualifying "because it doesn't shrink as p→1", and pointed out that Kalshi's `ceil(7p(1−p))` is
also 1c above ~83c — so at 95–99c both venues charge exactly 1 cent.

**The comparison was right; the conclusion I drew from it was wrong.** The fee is not *worse* than
Kalshi's, but it is still fatal in absolute terms: a lock bought at ≥98c has ≤2c of gross premium, and
1c fee + 1c pre-registered slippage consumes all of it. "Not worse than Kalshi" is not the same as
"survivable", and I conflated the two. The right instruction — measure it, don't assume — is the one
that produced the answer.

---

## Verification quality

The reconciler found Build A had stalled in phase 2 (a genuine non-result, correctly self-labelled
THIN, not a disagreement), so **it wrote a third fully independent build** rather than let Build B
stand unreplicated. Build C reproduces Build B **to every reported digit**: 8,646 locks, 190 false,
Wilson UB 2.5589%, 2,854 priced, 1,028 station-day clusters, +9.1969c, t=15.416, 66.991% untradeable.

Where the two builds *did* overlap — the station set and inclusion guard — they agree exactly, digit
for digit, including `KBKF` (Denver = Buckley SFB, **not** KDEN) failing with 0 obs across all 160
days because it is absent from IEM's 1-minute network.

Checks that came back clean: settlement provenance (venue's own `prices/` file, `open_interest==0`
final rows — **not** the provisional trading-day mark, which would have been an exact replay of the
paper-trader audit's Bug 2), side/cost accounting (Bug 1 absent), look-ahead, timezone/date alignment
(the pairs-file-date trap handled; a midnight-boundary test shows local-hour-0 false-lock rate *below*
the average, where a bug would push it far above), fee math, and statistics re-derived from scratch.

**A trap the verifier hit and Build B had already closed:** 7 tickers carry an early
`open_interest==0` row with a *non-binary* provisional settlement price. `open_interest==0` alone is
not a sufficient settlement marker on this venue. The verifier's first pass omitted the
`settlement_price ∈ {0,1}` guard and manufactured 7 spurious false locks; it converged to B's exact
190/8,646 after adding it. B had it right.

## Required disclosures (both builds omitted these)

1. **IEM asos1min publishes 22–34h late** — this is a backtest-only feed, so none of the sub-80c
   fast-tape capture is live-realizable from this source (GROUNDING non-negotiable #5).
2. Both builds applied an **unregistered per-station-day filter** dropping 99 of 1,440 station-days
   with <100 one-minute observations. It conditions on observations only, never on price or outcome,
   so it cannot bias the EV sign — but it was not in the frozen spec.
3. `spec_S3_B.md` claims per-fire records are in `spec_S3_B.json`; they are not (summaries only).

---

## Graveyard row

| # | Strategy | Study | Verdict | Key Number | Mechanism That Killed It |
|---|---|---|---|---|---|
| 38 | ForecastEx (IBKR/CFTC, US-legal) daily-temperature mechanical lock | `S3_FORECASTEX.md` | **CONFIRMED KILL** (two independent pre-registered grounds; three builds, one adversarial) | 190/8,646 false locks (2.198%, Wilson UB 2.559% vs ≤2.5% bar); at fill≥98c mean net EV −0.571c/ct, clustered t=−5.66, one-sided UB −0.357c < +0.2c | **Settlement-basis mismatch**: WU settles on 5-min-averaged METAR at routine cadence, the signal reads true 1-min ASOS, so real sustained 2–4°F excursions are invisible to settlement (0 false locks only at cushion ≥5°F — where the market has already repriced to ≥98c). **And there the flat 1c fee + 1c slippage exceeds the ≤2c lock premium.** Headline +9.20c/t=15.4 was population mixing: 81.2% of P&L from the 26.3% of fires below 80c, i.e. an unregistered directional bet winning only 83.1% |

## What this closes

The US-legal venue axis is now closed for this mechanism. `venues_us.json` established that
Polymarket US does not list weather, Novig/ProphetX are sports-only, Sporttrade is shut, and CME is
monthly index products through institutional brokers. ForecastEx was the one structurally-matching,
legally-reachable candidate, and it is dead — **not on access or liquidity, but because its
settlement source is coarser than any feed that could beat it.**

That generalizes beyond this venue: any market settling on a **METAR-derived** daily extreme is
unbeatable by a finer-than-METAR feed, because the extra resolution measures something the settlement
never records. Worth carrying into any future weather venue as a preflight check — *what exactly does
settlement average, and at what cadence* — before any data work.
