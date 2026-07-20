# WX-DIRECTIONAL — Kalshi Weather-Market Directional/Timing Sleeve: Kill Report

**Status: NULL RESULT. No edge survived the funnel. Zero specs activated, zero to forward-paper.**

Scope: eight pre-registered specs across four rounds, testing whether *timing/directional*
signals on Kalshi's 20 `KXHIGH*` daily-high-temperature markets (market-calibration fades,
forecast-revision events, thin-book mispricing, intraday nowcast lag, order-flow drift, ladder
arbitrage, salience anchoring, climatology mispricing, upwind-advection model bias) can beat
market price + fees. All backtests used the same shared preflight: full settled-market census
(8,040 markets, 20 series, `status=settled`) plus hourly candlesticks (`period_interval=60`)
pulled from Kalshi's public v2 REST API, no auth, cached once and reused across sibling agents.
Fee = `ceil(7·p·(1-p))/100` charged at the crossing price (ask on buys, bid on sells), never mid.
Chronological TRAIN/TEST split (first 60% / last 40% of settlement dates, per series); TEST
touched at most once per spec, per pre-registration.

Market history available this run: **67 distinct settlement dates** (2026-05-13 .. 2026-07-18),
entirely within one warm season. This shallow, single-season history is the load-bearing
constraint behind several of the kills below — flagged per-spec, not glossed over.

---

## What was tested, and why each one died

### SPEC 1 — Horizon-conditional calibration fade
**Verdict: INSUFFICIENT** (no read either way). Idea: at H=2h before close, extreme quoted
probabilities (p≥0.85) are overconfident relative to an isotonic fit trained on the same
horizon, so fade them. TEST primary leg produced only **n=17 entries over 10 city-days**,
against a pre-registered floor of ≥200 entries / ≥40 city-days. Sub-floor numbers *looked*
strongly negative (win rate 17.6% vs 21.7% breakeven, t=-11.5) but the pre-registration
explicitly forbids reading a verdict off an underpowered sample — reported INSUFFICIENT, not
FAIL. A secondary H=20h leg (logged only, not gating) showed 91% win rate / n=55, encouraging
but far too small and not part of the activation bar. **Would reopen if:** market history grows
enough that 2h-before-close crossings with spread ≤0.10 occur ≥200 times over ≥40 days — likely
needs several more months of KXHIGH listings, not a redesign.

### SPEC 2 — MOS run-to-run forecast-revision jump fade
**Verdict: KILL.** Idea: large jumps between consecutive MOS/NBS forecast runs are followed by
predictable market drift the quote hasn't caught up to. TEST holdout n=815 (468 city-days,
comfortably clearing the n-floor): mean EV/contract **-$0.0255** (t=-3.16, p=0.0016) — a clean,
statistically decisive loss, not a null. Critically, the event-vs-control comparison
(`event_minus_control_ev = -0.00033` pooled, -$0.00009 for GFS, -$0.00062 for NBS) showed the
"revision jump" condition performed **no better than the unconditional control** of trading the
same tickets without the jump trigger — i.e., the signal carries zero incremental information
over just buying longshot brackets in general (which itself loses money to the vig, as SPEC 2b
and the market-efficiency baseline elsewhere in this project also found). Per-model split (GFS,
NBS) both individually negative and both statistically significant. **Would reopen only if** a
materially different revision-magnitude/threshold construction produced a positive
event-minus-control gap on fresh data — not attempted here per no-retuning-after-TEST rule.

### SPEC 3 (labeled "1b" pre-registration, "thin-book longshot fade")
**Verdict: INSUFFICIENT.** Idea: fade extreme quotes in thin, low-volume rungs where the touch
price is noisy. TEST produced **n=84 qualifying trades over 75 city-days**, against a
pre-registered floor of ≥300 entries — the thin-liquidity filter that defines the strategy is
itself the reason too few trades qualify. No directional read taken. **Would reopen if** history
depth (or a looser thinness filter, pre-registered before the next TEST read) pushes qualifying
volume past 300.

### SPEC 4 — Intraday realized-trajectory nowcast lag
**Verdict: FAIL**, decisively, on a fully-powered sample (n=2,109 entries, 539 city-days — the
largest TEST set of any spec here). Idea: compare running max-so-far against an empirical
"remaining rise" distribution (R = daily_max − running_max(T), fit per city×season on TRAIN) to
catch cases the market hasn't priced in yet. Every pre-registered pass bar failed: day-clustered
t=-4.05 (strongly negative, not just insignificant), Wilson-LB win rate 16.7% vs 21.7% breakeven,
mean EV -$0.0273/contract, and the placebo control (T=10, meant to confirm the edge is
observation-accumulation-driven) actually did *worse* on the main leg's manipulation, contradicting
the hypothesized mechanism rather than merely failing to support it. Root cause dug into and
confirmed: TRAIN (spring/early summer) and TEST (full summer) sit in different parts of a single
uninterrupted warm-season warming trend; the R-distribution is fit as one static, unconditional
curve over TRAIN and doesn't track the seasonal drift into TEST, producing a non-monotonic,
sometimes-inverted calibration curve out of sample. **Would reopen if** ≥1 full year of history
(both warm and cool season, multiple warm-season cycles) let R be conditioned on
within-season position rather than pooled flat — the current 67-day, single-season dataset cannot
distinguish "no exploitable lag" from "naive unconditional pooling can't survive a warming trend,"
though the non-monotonicity of the TEST calibration curve suggests the pooling design itself, not
just data volume, is the weak point.

### SPEC 5 — Early-session order-flow imbalance drift
**Verdict: FAIL**, fully powered (TEST n=525, 317 city-days). Idea: unanimous-direction
volume-weighted order flow in the first N hours after market open predicts continuation. Frozen
cell (chosen on TRAIN day-clustered t, before TEST read): N=6 hours, 90th-percentile threshold —
the *least bad* of 9 TRAIN grid cells, all 9 of which were already negative-EV on TRAIN (no
overfit risk; there was nothing positive to overfit to). TEST: Wilson-LB win rate 75.4% vs 82.1%
breakeven, mean EV -$0.0233/contract, t=-1.81 (misses the ≥2.0 bar), robustness check (drop
top-5 winners) still negative. Mechanism: entries fire mostly at rich prices (mean $0.80, often
$0.95+) because a 6-hour unanimous-flow signal mostly triggers on brackets the market has
already nearly resolved — thin margin for error at those prices. Worse, the minority "yes"-side
subset (I>0, betting continuation upward) was actively anti-predictive: 28.9% win rate, i.e.
short-window order flow in these thin single-city books reverses more than it continues, matching
the spec's own pre-registered null hypothesis ("flow is 1-2 opportunistic orders, not
information"). **Would reopen only with a different signal construction** (not this spec as
specified); the sign and magnitude are consistent enough across TRAIN and TEST that more data
alone is unlikely to flip it.

### SPEC 6 — Ladder internal-consistency arbitrage
**Verdict: FAIL**, and INSUFFICIENT on top of that (TEST n=110, below the 200 floor, though
city-days cleared at 98/40). Idea: when a ladder's summed quoted probabilities across
mutually-exclusive rungs deviate from 1 ("completeness" violations) or a rung's price stays
stale after price-relevant movement ("stale-rung"), trade the correction. Every bar that *could*
be computed still failed independently of the n shortfall: win rate 10.0% (Wilson-LB 5.7% vs a
>50% pass bar), day-clustered t=-2.28, and — the most diagnostic number — **fill rate only 19.7%**
(pre-registered floor 60%): of 559 flagged completeness violations, ~80% evaporated within one
hour, meaning the "mispricing" is mostly quote staleness/thin-book noise at the edges of the
spread, not a durable arbitrage. The minority that *did* fill still lost money on both
completeness sub-signals (0% win rate each) — consistent with paying the full bid-ask spread on
every leg of a multi-leg basket trade, which is exactly what the fee/crossing-price convention
charges for. The stale-rung sub-signal fared oppositely (87% fill rate, durable) but flipped sign
TRAIN(+1.26t, not significant)→TEST(-1.52t) on only n=20/32 — underpowered, flagged as the
weakest link, not confidently dead. Exhaustiveness sanity check passed (1,340/1,340 ladders had
exactly one rung settle YES), so the failure isn't a data-integrity artifact.

### SPEC 7 — Salient-threshold (round-number) anchoring bias
**Verdict: NO-SIGNAL, self-killed on TRAIN per pre-registration; TEST never opened.** Idea:
rungs at psychologically salient strikes (multiples of 10) get mispriced relative to non-salient
neighbors. Only 2 of 5 pre-registered price bins ever reached the ≥20-sample floor per (bin,
salience) cell (95 salient TRAIN snapshots total, thinly split across 5 bins), and only 1 of
those 2 cleared the |gap|≥0.04 threshold — short of the required 3-of-5 sign-agreement bar, which
was structurally unreachable from this TRAIN slice. No threshold was loosened after seeing the
table. **Honest caveat carried in the original report:** the `MIN_GROUP_N=20` floor was the
analyst's own pre-fixed choice, not pinned by the spec text; a looser (still pre-registerable)
floor might have made 2-3 more bins eligible. Reported as NO-SIGNAL-as-coded, not proof the effect
doesn't exist.

### SPEC R4-1 — Climatological bracket-skew mispricing at long lead
**Verdict: FAIL, self-killed at preflight, before TRAIN or TEST.** Idea: at long lead times
(close-120h/-72h/-48h), pure climatology should price brackets better than the market when no
live forecast is yet informative. Preflight coverage census (the spec's own pre-registered
fallback ladder) found **0 TRAIN city-days with a two-sided quote at all three candidate
horizons** (120h, 72h, 48h; bar was ≥40 each). Root cause, verified directly against the settled-
market data: KXHIGH markets uniformly open only **39-42 hours before close** across all 8,040
settled markets (min/max checked directly) — there is no quote of any kind, let alone
two-sided, at close-48h, because the market doesn't exist yet at that lead. The spec's core
premise (a genuinely long-lead, forecast-independent signal) cannot be tested on this instrument
as currently listed. **Would reopen only if** Kalshi starts listing these markets further ahead
of settlement — not a data-volume problem, a market-structure ceiling.

### SPEC R4-2 — Upwind-advection model-bias lead
**Verdict: FAIL, self-killed at TRAIN, before TEST.** Idea: a NBS/MOS forecast-bias signal at an
upwind station (matched by distance/bearing/record-length rule) should lead the same bias
arriving at the target city. TRAIN theta scan (556 points) found **zero thresholds** where the
fee-inclusive Wilson-95%-lower-bound win rate cleared breakeven — best point still 10.9 points
short (11.5% vs 22.4% breakeven at n=25); the bulk of the scan was far worse. Independently fatal
even had TRAIN passed: the pooled TEST window only has 27 distinct settlement dates, below the
pre-registered ≥40 floor (structural, given the 67-day total market history). Diagnosed root
cause: OLS beta on the upwind anomaly came out ≈0.026 (no real relationship) because the signal
as literally specified — "upwind high-so-far since local midnight" vs "upwind full-day NBS
forecast high," both read as written — compares a partial day's running max against a full day's
forecast max at a snapshot taken *before* the upwind station's own diurnal peak on most days
(98.96% of 1,059 triggers were negative by a mean of -15.1F). That's a mechanical timing artifact
dominating the data, not evidence against advection-driven bias per se; a same-timescale
redesign (partial-day-consistent forecast benchmark) was explicitly out of scope under the
no-retuning-after-data rule and is flagged for whoever specs the next round. Additional structural
note: 3 of 20 target cities (Seattle, SF, LA) have zero upwind-pairing candidates at all — the
required distance/bearing window is open Pacific Ocean, no ASOS station exists there, and no
amount of relaxed history/threshold criteria fixes it.

### Rejected pre-round (never backtested — reasoned out before spending API budget)
- **2b — LAV drift:** same forecast-revision-event mechanism class as SPEC 2, redundant; SPEC 2's
  event-vs-control result (≈0 incremental EV over the unconditional control) already answers the
  underlying question for this class of "revision event" signal.
- **3a — Multi-model blend:** rejected as the lowest-independence angle — it's forecast-vs-market
  with better post-processing, the same axis a prior WEATHER-EDGE decision (2026-07-17,
  315 city-days) already killed for beating market-implied skill.

---

## Score of the funnel

| # | Spec | TEST n | City-days | Verdict | Where it died |
|---|------|--------|-----------|---------|----------------|
| 1 | Horizon calibration fade | 17 | 10 | INSUFFICIENT | n-floor (need ≥200/≥40) |
| 2 | MOS revision-jump fade | 815 | 468 | **KILL** | event-vs-control ≈0; EV -$0.0255, t=-3.16 |
| 3 | Thin-book longshot fade | 84 | 75 | INSUFFICIENT | n-floor (need ≥300) |
| 4 | Intraday nowcast lag | 2,109 | 539 | **FAIL** | t=-4.05; season-drift in unconditional R fit |
| 5 | Order-flow imbalance drift | 525 | 317 | **FAIL** | t=-1.81; rich entry prices, contrarian yes-side |
| 6 | Ladder consistency arb | 110 | 98 | **FAIL**+INSUFFICIENT | fill rate 19.7% (need ≥60%); spread artifact |
| 7 | Salient-threshold anchoring | 0 (TRAIN self-kill) | — | NO-SIGNAL | TRAIN bin-eligibility floor unreachable |
| R4-1 | Climatology at long lead | 0 (preflight self-kill) | — | **FAIL** | market never lists that far ahead (39-42h ceiling) |
| R4-2 | Upwind-advection bias | 0 (TRAIN self-kill) | — | **FAIL** | 0/556 theta cleared breakeven; timing-artifact signal |

Two fully-powered, statistically decisive kills (SPEC 4, SPEC 5); two more FAILs on smaller-but-
still-diagnostic samples (SPEC 6's fill-rate mechanism, SPEC 2's event-vs-control null); three
specs never reached a directional read at all, each for a *different*, verified structural reason
(SPEC 1/3: shallow market history, not enough qualifying entries yet; SPEC 7: thin salient-rung
population; R4-1: market microstructure ceiling on lead time; R4-2: TRAIN self-kill by design).
No spec was killed by researcher discretion after seeing TEST — every kill or self-kill traces to
a bar fixed before that spec's TEST (or in R4-1/R4-2/7's case, before TRAIN) was read.

## What would reopen which idea

- **More calendar history (the dominant blocker for 4 of 9 specs — 1, 3, 7, R4-2's TEST-floor
  leg):** KXHIGH markets have only 67 distinct settlement dates as of this run, all one warm
  season. Several specs are underpowered or single-season-confounded purely because the market
  family is young, not because the underlying idea was tested and failed. Re-run SPEC 1, 3, 7 and
  the TEST leg of R4-2 once ≥1 year of history exists (ideally spanning a full cool season too, to
  let SPEC 4's season-conditional R-distribution redesign be tried honestly).
- **R4-1 only reopens if Kalshi changes how far ahead it lists these markets** — no amount of
  waiting fixes a 39-42h open-to-close structural ceiling against a 48h+ signal design.
- **R4-2 needs a same-timescale signal redesign** (partial-day upwind observation vs a
  partial-day-consistent forecast benchmark, not the full-day MOS high) before it's a fair test of
  the advection-bias hypothesis at all; the current FAIL is measuring a timing artifact more than
  the hypothesis.
- **SPEC 2, 4, 5, 6 are confidently dead as specified** on samples large enough to trust the sign;
  reopening any of them would require a materially different signal construction, not more data
  or retuning.

## What this NULL result implies for the capacity model

Across every spec that reached a statistically meaningful sample (SPECs 2, 4, 5, 6 — combined
TEST n well over 3,500 entries, hundreds of city-days, multiple independent mechanisms: forecast-
revision events, nowcast trajectory, order flow, ladder cross-rung consistency), **none beat
market price plus Kalshi's fee schedule**, and where a mechanism was diagnosable, the market's
apparent "error" resolved into either (a) no information beyond an unconditional control (SPEC 2),
(b) a static model failing to track real seasonal drift the market itself was implicitly pricing
correctly (SPEC 4), (c) genuinely noisy/reversal-prone thin-book flow rather than momentum
(SPEC 5), or (d) a bid-ask-spread artifact that evaporates within an hour rather than a durable
cross-rung mispricing (SPEC 6). This is consistent with Kalshi's `KXHIGH` weather markets being
reasonably efficient against the specific timing/directional mechanisms tested here, at the fee
levels charged, over the history available. It does **not** rule out (a) edges at longer market
history/deeper liquidity than exists today, (b) edges in mechanisms not yet tried, or (c) edges
that require beating raw forecast skill rather than market price — the latter axis was
deliberately excluded from this round (SPEC 3a) because a prior WEATHER-EDGE decision already
found the market prices at least as well as available forecast skill on that axis. Net
recommendation for the capacity model: **do not allocate to a directional/timing sleeve on
KXHIGH markets on current evidence; revisit specs 1/3/7/R4-2 once market history is deeper, and
treat SPECs 2/4/5/6 as closed unless a genuinely different signal is proposed.**
