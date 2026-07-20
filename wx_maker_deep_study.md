# wx_maker_deep_study — K-WX post-lock maker (resting-order) deep study, verdict + reproducible harness

Date: 2026-07-20. Scope: a hypothetical strategy layered on top of the deployed taker bot (`kwx_runner.py`)
that, instead of buying YES at the ask right after mechanical lock, rests a passive YES limit bid at
93/95/97c and waits to be filled at a better price ("post-lock" arm), or rests one *before* lock while the
rung is still approaching its strike ("pre-lock" arm). A 5-agent harvest fleet backtested both arms against
65 days x 20 stations (2026-05-15..2026-07-18) of real Kalshi trade-tape + IEM ASOS-1min data. A verifier
panel then live-audited the result against real 1-minute candlesticks. **This document reports the panel's
verdict, not the original harvest's headline** — the headline does not survive.

## Verdict

**REFUTED on the headline. Live 1-minute candlestick audit shows the post-lock "resting maker bid" premise
is false for the large majority of the flagship P=93 cell: the best ask at the simulated placement time was
already at or below 93c, so a real limit order there would have crossed the spread and filled *immediately
as a taker order*, not rested. Those are the deployed taker bot's own trades, relabeled at an artificial
maker price — not a distinct edge. Do not deploy the post-lock maker strategy as studied.**

The naive headline claimed **+7.00c/contract, n=22.5 fills, 0% adverse selection (Wilson 95% CI [0%,
14.6%]), t=6.22 (p<0.0001)** on the post-lock P=93 cell. Correcting for marketability (post-only:
ask must exceed the bid price at placement, or the order is a taker fill, not a maker fill) collapses that
to **n=2 confirmed genuine maker fills** (+1 possible, unresolved), all wins, **+14 to +21 cents gross over
the entire 65-day x 20-station frame**, with a Wilson 95% CI on adverse selection of **[0%, 65.8%]** at
n=2 — too wide to distinguish from noise. The **per-fill payout is unchanged** (+7.00c/contract when a
genuine fill does happen, $0 maker fee, confirmed by three independent sources — see Section 4) — what
collapsed is *how often it happens*, from a claimed ~39% fill rate down to an estimated 3-5% restable-bid
rate among the naive candidates, most of which never even qualify as maker orders in the first place.

## 1. Verified numbers

| | naive (as-harvested, REFUTED) | verified strict (panel recount) |
|---|---|---|
| scope | post-lock, P=93c, 16/20 stations | post-lock, P=93c, flagship cell only |
| bids simulated | 58 | 58 (same denominator) |
| restable bids (ask > 93c at placement) | *not checked* | 5-8 |
| genuine maker fills | 22.5 (claimed) | **2 confirmed, +1 possible** |
| adverse selection | 0/22.5, Wilson 95% CI [0%, 14.6%] | 0/2, Wilson 95% CI **[0%, 65.8%]** (0/3 if 3rd confirms: [0%, 56.2%]) |
| net EV, per genuine fill | +7.00c/contract | **+7.00c/contract (unchanged)** |
| gross total, full 65-day x 20-station frame | +157.5c (claimed) | **+14 to +21c** |
| day-clustered t-test | t=6.22, n=32 station-days, p<0.0001 | **not meaningful** — see Section 3, finding F/M1: the test variable cannot be negative by construction, so significance proves fills occurred, not edge |

The two confirmed genuine fills (live-audited against real 1-minute candlesticks + trade tape):

| station | ticker | ask at placement | fill print | delay after lock | result |
|---|---|---|---|---|---|
| KPHL | KXHIGHPHIL-26JUN22-T93 | 95c | 91c | +50s | win |
| KHOU | KXLOWTHOU-26MAY19-T73 | 96c | (confirmed <93c) | +199s | win |

One additional candidate (KSFO, KXHIGHTSFO-26JUL14-T81, ask=100c at placement) is restable in principle but
its fill status could not be recovered from the harvest's chunk_3 aggregates — carried as *possible, not
confirmed*.

**Pre-lock arm**: naive EV was deeply negative (-55c to -69c/contract, 66-72% adverse selection, n=150-221
fills/cell) across every (P, D) combination tested. The panel found this arm suffers the *same*
marketability flaw — a bid placed while the rung is still 1-2°F from its strike would typically cross a much
lower ask and fill near-instantly at that ask, not at the quoted P — so **no magnitude in the pre-lock grid
should be trusted or reused**. The **sign** (net-negative) is judged plausible to survive: even an
execution-realistic version of "buy in early, before the market has repriced" is not expected to beat
"buy at mechanical lock," because pre-lock the outcome is not yet decided. Treat pre-lock as **confirmed-bad
by direction, unverified by magnitude** — not as a cell worth any further tuning.

Reproduce every number above: `python wx_maker_deep_study.py` (prints both tables) or
`python wx_maker_deep_study.py --selftest` (14 internal consistency checks, also wired into
`kwx_selftest.py`).

## 2. Policy / parameter recommendation

**Do not deploy.** No code in this repo is changed by this study (`kwx_runner.py`, `kwx_paper_gate.py`,
`kalshi_exec.py`, `kwx_daily_digest.py` are untouched, per instruction). Specifically:

- **Post-lock resting maker bids (P=93/95/97c): do not add as a supplement.** The corrected edge (+7.00c
  per genuine fill) is real *when a fill is genuinely a maker fill*, but converts only ~2-3 times across the
  entire 65-day x 20-station sample — an economically negligible ~$0.002-0.003/day at 1-contract size, and
  statistically indistinguishable from a 0-56%-adverse-selection strategy at this n. There is nothing here
  that clears any reasonable bar for capital allocation.
- **Pre-lock resting bids at any tested P: do not deploy in any form.** Confirmed-bad by sign; the specific
  magnitudes reported are not to be used for sizing.
- **The existing deployed taker strategy in `kwx_runner.py` is unaffected by this study** — this was always
  a study of a *hypothetical alternative/supplement*, not a review of the live strategy. The comparison in
  the original harvest's Section 6 ("maker vs. taker") is now moot: 80-90% of the "maker" fills it counted
  were the taker strategy's own opportunities, so no independent maker-vs-taker EV comparison exists.

## 3. What the verifier panel killed, and why

**FATAL — marketability never checked (this is the load-bearing defect).** The fill simulator treated every
hypothetical bid as though it were already resting in the book at placement, without ever checking whether
the prevailing best ask was already at or below the bid price. A limit YES buy at 93c against an ask of,
say, 47c (real example: `KXHIGHDEN-26JUL08-T93`) does not rest — it executes immediately as a taker order at
the ask. Live 1-minute candlestick audit of all 32 chunk_4 post-lock P=93 bids found **26/32 had best ask
<= 93c at placement**, plus corroborating examples at KSFO (asks 73c and 89c) and KBOS (fill printed 34s
post-lock, consistent with an instant cross, not a multi-minute rest). These are the deployed taker bot's
own trade opportunities, counted a second time under an artificial maker label.

**FATAL — the strict recompute.** Applying a post-only filter (ask > P required at placement) to the
flagship cell drops it from 58 naive bids / 22.5 claimed fills to 5-8 restable candidates / 2-3 confirmed
genuine fills. The naive n=22.5-fill, tight-CI result does not survive at any n this small.

**MAJOR — the 0% adverse selection is near-tautological.** Every post-lock bid sits on a market whose
outcome is already mechanically decided at placement (lock, by definition, is the moment the obs stream
crosses the strike) — so a payout variable that is either 0 or +7 by construction cannot go negative, and a
t-test on it (t=6.22) only proves "some fills occurred," not that the strategy has edge. The one real loss
channel this sample never captures — a Kalshi settlement/CLI mismatch against the ASOS-1min feed, estimated
breakeven failure rate ~7% at P=93 — is unsampled at only ~23 independent events.

**MAJOR — triple counting.** A single trade print below 93c simultaneously satisfies the P=93, 95, and 97
fill conditions, so the "0/69 fills lost" figure in the naive report is really ~23-24 independent events
counted three times. Per-P confidence intervals (as reported) are the internally-consistent numbers for that
flawed model; the pooled "69" framing is not.

**MAJOR — fill size / capacity ignored.** The naive simulator credits a full 1-contract fill on any
qualifying print regardless of size. Two of the 18 audited chunk_4 P=93 fills came from dust-sized prints
(0.01 and 0.10 contracts) — real market capacity on 7/18 filled events was only 1-13 contracts total. The
naive report's bankroll extrapolations ($50 bankroll -> 53 contracts/bid, +$1.28/day) exceed what several of
the contributing events could actually have filled.

**MAJOR — zero-latency look-ahead.** Bids were "placed" at the ASOS-1min observation's valid timestamp with
0 seconds of latency; 10/18 chunk_4 P=93 fills occur under 2 minutes after lock (minimum 4.4s). ASOS-1min
data is not published at its valid time in real time — these fills would be uncapturable live even setting
the marketability flaw aside.

**MAJOR — the same marketability flaw contaminates the pre-lock grid** (see Section 1's pre-lock note).

**MINOR — confirmed OK.** Two of the harvest's methodological choices were independently re-verified live
and hold up: `taker_side` semantics (a `taker_side="no"` print is genuinely a fill against a resting YES
bid — confirmed on every audited print), and the 50%-credit haircut for ambiguous (`price==P`) fills, which
turned out to affect only 1 of 17.5 chunk_4 P=93 fills — barely load-bearing either way. Aggregation
arithmetic across the 5 harvest chunks is also clean: an independent re-merge reproduces every naive
grand-table row exactly (2,022 bids, 1,178 fills, 168 station-cells). **The defect is entirely in the fill
model's marketability assumption, not in the data pipeline or the summation.**

## 4. Fee rule (unaffected by the above, independently triple-verified)

Maker (resting) fills on every `KXHIGH*`/`KXLOWT*` weather ticker pay **$0.00** trading fee — confirmed via
(1) live `GET /series/{ticker}` returning `fee_type=quadratic` (not `quadratic_with_maker_fees`) on 5
sampled series, (2) an in-repo prior study (`archive/code/kalshi_maker_rebate.py`) that live-probed all 196
Kalshi series and found only 3 non-weather series charge a maker fee, and (3) Kalshi's published fee-schedule
text (maker fee = 25% of the taker fee, opt-in per series). This part of the study is solid and is why the
per-fill payout (+7.00c/contract on a genuine P=93 win) is unaffected by the marketability correction — only
the *frequency* of genuine fills was wrong.

## 5. Exact conditions under which this strategy activates (staged gate, mirrors `KWX_DEPLOY.md`)

This strategy does **not** activate today. Nothing in this PR changes deployed behavior. If a future PR
wants to reopen the question:

**Stage 0 — Fix the simulator, do not reuse this data for sizing.**
1. Enforce `ask_c_at_placement > P` (post-only check) before crediting any hypothetical fill as a maker
   fill, using the same live-candlestick method the panel used — applied to the *full* 58-bid post-lock set
   across all 16 stations (this study's panel only fully audited the 32-bid chunk_4 slice) and to the entire
   pre-lock grid, not reused from this document's naive table.
2. Replace 0-second look-ahead with realistic latency (>=60-90s after an observation's valid time, matching
   the fastest real-time feed actually available to `kwx_runner.py`).
3. Cap simulated fill size at each print's real `count_fp`; filter `is_block_trade=true` prints out of the
   eligible set (confirmed not to have contaminated the flagship cell's 18 audited prints, but the classifier
   is wrong in principle and should not be reused as-is).

**Stage 1 — Paper.** Run the corrected post-only maker logic as a passive, additive layer inside the
existing paper harness for >=4-6 weeks, accumulating toward n>=30 independently-verified genuine maker fills
(current: 2-3). Below n=30 no CI here is tight enough to act on — this mirrors the existing paper-gate bar
in `KWX_DEPLOY.md` ("live == tested... n>=~30 clustered").

**Stage 2 — Paper gate.** Advance only once the corrected live-paper post-lock fills replicate a positive
net EV with a Wilson 95% CI on adverse selection that excludes >30%, at n>=30 station-day-clustered
observations.

**Stage 3 — $10 canary.** Identical structure to `KWX_DEPLOY.md`'s existing canary stage (1-contract floor
at $10 bankroll), deployed strictly as a supplement layered on top of the already-live taker strategy, sized
so its rare fills cannot materially move the daily risk budget.

**No stage above is authorized by this PR.** This PR adds documentation and a read-only reproduction
harness only — see the no-touch list at the top of Section 2.

## 6. Files in this PR

- `wx_maker_deep_study.md` — this document.
- `wx_maker_deep_study.py` — reproducible, read-only harness. Loads `wx_maker_deep_data.json`, prints the
  naive (refuted) table, the panel's strict recount, and the verdict; `--selftest` runs 14 internal
  consistency checks (also invoked by `kwx_selftest.py`).
- `wx_maker_deep_data.json` — compact (~18KB) committed dataset: the naive grand table (kept as the audited
  artifact, not as a usable result), the panel's findings (FATAL/MAJOR/MINOR, verbatim substance), the
  strict-recount event list (the 2 confirmed + 1 possible genuine maker fills with ticker/ask/fill/delay
  detail), and the recommendation. The raw harvest caches (`scratchpad/deep/maker/chunk_*.json`,
  `aggregate.json`, ~600KB of per-event rows and harvest scripts) are **not** committed — they were scratch
  working data for the harvest fleet, superseded by this compact, audited file.
