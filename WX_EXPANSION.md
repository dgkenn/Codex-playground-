# WX_EXPANSION — generalizing the K-WX mechanical-lock edge across Kalshi (recon, 2026-07-20)

## Thesis

K-WX's one confirmed edge (`KWX_DEPLOY.md`) is not really "about weather": it is about a specific
Kalshi *product shape* — a ladder market whose strike is a period extremum (max/min/threshold) of a
**continuously-observable public data stream**, that **settles/closes early the instant the extremum
mechanically clears the strike** (an irreversible, monotone crossing), on an underlying where the
public feed reliably **leads** Kalshi's own repricing by a nontrivial window. Weather happens to have
all three properties (station reports are periodic and public, a daily max/min is a one-way ratchet,
and Kalshi's retail flow reprices slower than the feed). The question this recon answers: **does any
other Kalshi product category share the same three properties well enough to be a second sleeve?**

This is a scan, not a backtest: read the public catalog for candidate shapes, pull real settled-market
history for a sample of each candidate family, and measure the same four things K-WX's own validation
measured — (1) is the lock independently detectable from a public feed, (2) how long is the lag from
lock to the market's own ask reaching ≈99¢, (3) is that lag window actually capturable (real ask ≤98¢,
real traded depth) and what's the net EV/contract after the `ceil(7·p·(1-p))/100` taker fee, (4) how
often does a capturable lock happen (events/day). Pre-registered bar for "promising": ≥0.5 capturable
events/day, mean net EV ≥ +$0.05/ct, and observer latency measurably faster than the lag.

## Catalog census

Two independent enumeration passes against `GET /trade-api/v2/series` (public, no auth):

- **Agent A** (category sweep): 5,198 series returned; category breakdown — Sports 961, Entertainment
  965, Politics 920, Elections 702, Economics 347, Financials 327, Mentions 255, Climate and Weather
  185, Crypto 149, Science and Technology 127, Companies 65, World 66, Health 62, Commodities 33,
  Social 27, Transportation 7.
- **Agent B** (ticker-name sweep, L–Z after stripping the `KX` prefix): 6,802 series in that half of
  the alphabet, keyword-filtered on MAX/MIN/HIGH/LOW/TOUCH/RANGE/RECORD/CLINCH/ELIMINAT/PLAYOFF/
  UNDEFEATED/SEASON, cross-checked against `strike_type`/`floor_strike`/`close_time` on a sample.

Combined finding: the "ladder + early-settlement-on-irreversible-lock" mechanism is a **generic Kalshi
product template**, not unique to weather — it is confirmed structurally identical (or ticker-naming-
analogous) for commodity price ladders (WTI/nat-gas), altcoin period-max/ATH ladders, FX pair ladders,
Treasury-yield touch markets, precious-metal year-end levels, equity-index ladders, and TSA-checkpoint
counts, plus a structurally different but same-*test* discrete-event class (sports cumulative stats,
clinch/elimination/undefeated trackers, live "word said" mention markets, earthquake magnitude,
FDA-approval-date markets). Ten ranked candidates came out of the ticker-name sweep (`catalog_b.json`);
explicitly ruled out at the catalog stage: TSA counts (batch daily reveal, no gradual approach) and
anything resolved by a single instantaneous announcement (Fed decisions, CEO changes) — these are
"mechanically decided by public data" but fail the *gradual, continuously-observable approach*
requirement that makes the lag window exist at all.

Six families were selected for real measurement (mix of the strongest ladder candidates and the
discrete-event class), each on live settled-market history pulled from the public API:

| # | Family | Tickers sampled | Settled n |
|---|---|---|---|
| 1 | Sports cumulative in-game totals | KXBUNDESLIGATOTAL, KXCOPADOBRASILTOTAL, KXIPLFOUR | 147 (70 YES) |
| 2 | Live "word said" mentions | KXEARNINGSMENTION*, KXGUTFELDMENTION | 240 (118 YES / 122 NO) |
| 3 | Earthquake magnitude-by-date | KXEARTHQUAKE, KXEARTHQUAKEM, KXEARTHQUAKECALIFORNIA | 26 (2 real events) |
| 4 | Commodity period-high/low ladders | KXWTIMAX/MIN/MAXM/MINM, KXNGASMAX/MIN/W/NGAS | 144 (49 early crossings) |
| 5 | Crypto period-high/low/ATH ladders | KXXRPMAXMON/KXSOLMAXMON/KXDOGEMAXMON/KXHYPEMAXMON/KXBNBMAXMON/KXZECMAXMON (proxy — literal KXSOLMAXY/KXXRPMAXY/KXXRPATH/KXLTCMAXY are dead, 0 volume) | 39 |
| 6 | FDA drug-approval-date | KXFDAAPPROVE + 13 sibling series | 15 (2 real events) |

## Per-family measurements (worker pass, provenance in `scratchpad/expand/fam*/results.md`)

### Family 1 — Sports cumulative totals (soccer/cricket) — **NOT PROMISING**
Detectable via ESPN's free public goal-timestamp API. Lag from goal to Kalshi ask≥99¢: **median 0.0s**
(74% resolve within the same 1-min candle), mean 117.6s (n=50) — quotes catch up almost as fast as the
lock appears. Only 13/50 (26%) had a ≥60s ask≤98¢ window; mean net EV **+$0.0296/ct** (below the
$0.05 bar). Frequency 0.50–0.81/day (market-level, 16-day season-finale-dense sample) — passes on
frequency alone. **Fails on EV and on latency** (median lag ≈ 0, i.e. no exploitable margin): live
scoreboards are watched by fast bots, so the mechanical-lock *shape* is real but the window is usually
zero.

### Family 2 — Live "word said" mentions (earnings calls, Gutfeld) — **PROMISING, then WEAKENED on audit**
Worker's raw numbers (hindsight-selected, best-price-in-run-up entry): 53/118 YES markets capturable,
mean net EV **+$0.316/ct** (median +$0.31), median lag 480s, frequency 0.946/day sampled (56-day, 18
events). Worker's own flagged reversal-risk finding: 1/30 NO-resolved sample had ask run to $1.00 and
still settle NO.

**Judge's adversarial re-audit found two compounding look-ahead flaws** (full detail in the judge
verdict, archived below):
1. `entry_price = MIN ask over the whole run-up`, computed only on markets that resolved YES, with
   P(win)=1 assumed. Without an independent decidability signal, buying at the market's own historical
   low print is just buying its own price mid-move — true EV at a 0.67 average entry with no edge
   signal is ≈ −fee, not +$0.32.
2. The "ask≥98¢" lock detector **conditions on the answer**: re-checking `reversal_check.json` shows
   **29/30 NO-resolved markets also had max_ask ≥0.98** (mostly resting $1.00 dust asks) — "ask reaches
   98¢" is book shape, not a lock signal. Only the **bid** discriminates: 1/30 NO markets had a
   sustained bid ≥0.90 (false-lock rate q≈3–4% at a bid-confirmed 0.90 gate); most NO markets ran bids
   to only 0.5–0.84 before collapsing, so mid-price entries are heavily contaminated by reversible
   markets.

Corrected, confirm-gated EV (enter at max(observed entry, 0.90) only on a sustained bid, q=4% false-lock
haircut): **≈ +$0.05/ct** — 6x below the naive claim, sitting exactly at the pre-registered bar, and
still contingent on transcript-feed latency that was never independently measured (no live
transcript/caption source was available in this Kalshi-API-only run). At 0.95–0.98¢ entries the
corrected EV goes to ≈$0 or negative. The 0.946/day frequency and ~3.3% false-lock rate are genuine
measurements that survive audit; "depth 37.2 median" in the worker's numbers is entry-candle *volume*,
not order-book depth, and was not re-verified.

**Verdict: PROMISING-WEAKENED.** Real signal, real frequency, but the deployable edge is ~1/6 of the
initial claim and unvalidated on the load-bearing latency assumption.

### Family 3 — Earthquake magnitude-by-date — **NOT PROMISING**
Product line is 10 weeks old; only 2 independent real M6.8+ quakes have ever crossed a strike (n=26
settled markets total, structurally can't reach n≥30 soon). USGS auto-magnitude is revised for 10–60+
min after origin — the market and the public feed largely **converge together**, not one leading the
other; one rung (May-69) oscillated 36–87¢ for 50+ min, proof the public estimate itself hadn't settled
during the nominal "post-decidability" window. Frequency 0.077/day — fails the bar by ~6–7x, consistent
with known global M≥6.8 seismicity (~30–40/yr). Nominal EV on the 3 capturable instances is high
(+$0.29 to +$0.79/ct) but reflects genuine magnitude uncertainty being priced, not a lag being
exploited.

### Family 4 — Commodity period-high/low ladders (WTI, NGAS) — **NOT PROMISING (frequency)**
Real, well-understood mechanism: `rules_primary` on every market names the exact deciding feed (WTI:
ICE front-month settle print, proxied via free Yahoo `CL=F`; NGAS: EIA daily Henry Hub *spot*, proxied
via free FRED `DHHNGSP` — an initial pass wrongly used NGAS futures and got nonsense multi-hundred-day
"lags" until `rules_primary` was re-read). 37/41 clean early-crossing markets had a real ask≤98¢
window; mean net EV **+$0.171/ct** (WTI +$0.177, NGAS +$0.136). Judge's secondary audit: the WTI
~7–8h median lag is largely **Kalshi's own posted next-day-10am settlement timer plus the pre-settle
time before the daily ICE print even publishes (~14:30 ET)**, not pure market slowness — so the EV
figure is real but overstated as a *live-capture* number. Frequency is the decisive failure either
way: 0.038/day full-history (2022–2026), 0.169/day even in the most volatile recent year — fails the
0.5/day bar by 3–13x.

### Family 5 — Crypto period-high/low/ATH ladders (thin altcoins) — **NOT PROMISING**
The literally-named tickers (`KXSOLMAXY`, `KXXRPMAXY`, `KXXRPATH`, `KXLTCMAXY`) are dead (0 settled, 0
volume); proxied with the structurally identical monthly sibling family (`KXXRPMAXMON` etc., 39 settled
YES markets, 6 tickers). Only 7/39 (18%) had a genuine ≥60s ask≤98¢ window ending pre-close; mean net
EV **+$0.0414/ct** (below bar). `can_close_early: true` means these markets often reprice to certainty
**more than an hour before official close** (46% of sample), collapsing the very lag the thesis needs.
Capturable frequency ≈0.10/day — fails the bar by 5x.

### Family 6 — FDA drug-approval-date markets — **NOT PROMISING**
Real settlement history is thin by construction: 15 settled markets collapse to **2** independent
real-world approval events (each drug's approval settles multiple rungs at once). FDA's public record
publishes only a *date*, not a timestamp — there is no independent minute-resolution feed to race
against the market, unlike weather (METAR), earthquakes (USGS), or commodity settle prints. Verified
capturable fraction: **0/2**. Frequency 0.030/day — fails the bar by ~17x, decisive on its own
regardless of the (unverifiable) EV question.

## Judge's corrected ranked capacity table

Same conservative-capacity convention as `wx_path_to_4k.py` (`DEPTH_CAP=25`/fire, day-clustered
frequency, measured events only — no un-audited extrapolation credited to the headline numbers):

| Rank | Family | Verdict | Corrected EV/ct | Freq (ev/day) | Defensible $/mo | Speculative ceiling |
|---|---|---|---|---|---|---|
| 1 | 2. Mentions (KXEARNINGSMENTION*, KXGUTFELDMENTION) | PROMISING-WEAKENED | +$0.05 confirm-gated (vs claimed +$0.316) | 0.95 sampled (13/56 days active) | **~$18/mo** | ~$140/mo if ×8 sibling-series extrapolation AND a transcript feed validates |
| 2 | 4. WTI/NGAS period ladders | NOT (freq fail 3–13x; mechanism real) | +$0.17 nominal, overstated by settle-print look-ahead | 0.038 hist / 0.169 (2026) | ~$3.5–20/mo | ~$40/mo if metal/FX siblings added (unmeasured) |
| 3 | 1. Soccer/cricket totals | NOT (0s median lag; EV $0.03 < bar) | $0.0296, likely uncapturable live | 0.5–0.81 | ~$16/mo nominal, ~$0 live-realistic | — |
| 4 | 5. Altcoin MAX ladders | NOT | $0.0414 | 0.10 capturable | ~$3/mo | — |
| 5 | 3. Earthquakes | NOT | reflects magnitude uncertainty, not lag | 0.077 | ~$0 defensible | — |
| 6 | 6. FDA approvals | NOT (17x freq fail; no minute-resolution feed) | 0/2 verified capturable | 0.030 | $0 | — |

**Sum of all six families' defensible capacity: ~$20–60/mo** — noise next to the weather sleeve's
path-to-$4k (`wx_path_to_4k.py`, conservative $1.3k/mo at $10k bankroll). The structural conclusion:
weather remains the unique sleeve because its bottleneck is the **feed** (periodic station-report
cadence gives a genuine, measurable lead). Every audited non-weather family's bottleneck is instead
either **attention** — fast bots have already closed the window (Family 1) — or **event scarcity**
(Families 3, 4, 6), or the "lock" isn't actually irreversible on inspection (Family 2's adjudication
risk, Family 5's early-close collapsing the lag).

## Next-step plan for the top family (Family 2 — Mentions), staged like `KWX_DEPLOY.md`

No family earns a full backtest-and-paper harness today. Family 2 earns a cheap, **gated measurement
pre-step only** — do not build a runner or size a sleeve until it passes.

### Stage 0 — Measurement pre-step (est. 1–2 sessions, no capital, no infra)
1. Stand up one free live transcript/caption source (earnings-call webcast closed captions, or
   Gutfeld! closed captions) and measure **feed-vs-Kalshi-bid latency** on 5–10 *live* upcoming events
   — the load-bearing, still-unmeasured claim (does the transcript genuinely lead the market's bid, and
   by how much?).
2. Expand the NO-side false-lock sample from 30 to the full 122 to tighten the q(bid≥0.90) estimate
   (currently 1/30, wide interval).
3. Re-derive the corrected EV using the wider sample and the measured (not assumed) feed lead time.

**Gate to Stage 1 (backtest spec)**: proceed only if the transcript/caption feed leads the bid run-up
by **>2 minutes** at prices **≤0.90**, AND **q(bid≥0.90 false-lock) stays ≤5%** on the full 122-market
NO sample. If either fails, archive the family — the "1–2 min transcript-processing lag +
adjudication-ambiguity" combination described in the fam2 writeup makes this structurally worse than
weather's clean thermometer-crossing, and a bigger sample won't fix a latency deficit or an inherent
adjudication tail.

### Stage 1 — Backtest spec (only if Stage 0 gates pass)
Mirror `KWX_DEPLOY.md`'s frozen-params approach: define entry rule as *bid confirmation* (sustained
bid ≥0.90 for N seconds, analogous to K-WX's glitch/sustain gate), not "ask ≤98¢" (which the audit
showed is not discriminating). Walk-forward across the full 379-series Mentions category (this recon
only sampled 48/379, 18 with settled history) — the honest full-family frequency and EV are unknown
until that expansion runs. Depth cap should use real entry-candle *traded* volume, not resting-quote
depth (the worker's "37.2 median" figure was volume, already the right proxy, but should be validated
against actual book depth at fire time the way `wx_book_snapshots.jsonl` does for weather).

### Stage 2 — Paper harness (only after Stage 1 backtest clears the same bar `KWX_DEPLOY.md` used:
n≥30 clustered fires, live==tested win rate and EV) — build a forward-settle loop analogous to
`kwx_forward.py`, but keyed to transcript/caption events instead of METAR polls. Do not size real
capital before a paper gate shows live matches backtest, exactly as the weather sleeve requires before
its own $10 canary.

### Everything else
Archive families 1, 3, 5, 6 outright (frequency or EV/latency fail is structural, not a sampling
artifact that more data would fix). Leave a **passive quarterly re-scan** of Family 4's sibling metals
ladders (silver, copper, gold — unmeasured in this pass) as the only other open thread, since the
mechanism there is real and only frequency is currently the blocker; a broader commodity set could in
principle clear 0.5/day where WTI/NGAS alone do not.

## Provenance

- Judge's full adversarial verdict text (fee-math, look-ahead, and lock-detector re-derivations) is
  preserved verbatim in this branch's session log; the numeric corrections above are taken directly
  from it.
- Worker measurement artifacts: `scratchpad/expand/fam{1,2,3,4,5,6}/results.md` (per-family writeups
  quoted/summarized above), `.../fam2/analysis2.json`, `.../fam2/reversal_check.json` (the 29/30
  NO-side max_ask≥0.98 finding), `.../fam2/analyze2.py` (the `entry_price = MIN ask` look-ahead line),
  `.../fam4/analyze1.py` + `.../fam4/lag_analysis.json` (settle-print look-ahead), `.../fam1/
  analysis_results.json`.
- Catalog census: `scratchpad/expand/catalog_a.json` (category sweep, 5,198 series), `.../catalog_b.json`
  (ticker-name sweep, L–Z, 6,802 series, 10 ranked candidates).
- Capacity-model conventions (fee formula, `DEPTH_CAP=25`, day-clustering) inherited from
  `p4k_params.json` / `wx_path_to_4k.py`. The new `added_markets_kalshi` sleeve in `p4k_params.json`
  carries the judge's conservative per-family numbers above; like `added_markets_polymarket` it is
  excluded from the headline capacity curve (its gate is not time-accruable — it requires an actual
  completed backtest+paper harness per family, not elapsed calendar time) and is reported separately
  by `wx_path_to_4k.py`.
