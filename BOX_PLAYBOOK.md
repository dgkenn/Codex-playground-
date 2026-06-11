# BOX PLAYBOOK — detecting settlement-locked pairs better, and earning more on them

A "box" here = both our resting bids filling (YES at `b_y`, NO at `b_n`, `b_y+b_n < $1`):
$1 payout at expiry regardless of outcome, locked once paired. Decomposition (live + 20,318
tape fills) shows boxes are the ENTIRE profit engine (+18.0¢/win, t=34.5) and unpaired
inventory the entire loss (−16.3¢/win, t=−16.9). Everything below is about completing more
pairs, at better locks, with less unpaired time. Evidence: `/tmp/box_lab.py` sweep on the
deep tape (10,778 BTC quote-minutes), live fill records, queue-replay studies.

## The 10 mechanisms

| # | mechanism | evidence | status |
|---|---|---|---|
| 1 | **Strict pairing (`--max-net 1`)** — after a YES fill, only NO quotes until paired | tape policy replay: +1.96¢/win, t 2.1→**4.3**, OOS Calmar 0.5→**0.9**; max $1 directional exposure | **DEPLOYED** |
| 2 | **Completion floor (`--min-lock 0`)** — never complete a pair at a negative lock (vs unpaired leg's avg cost); hold and wait instead | tape: **45% of natural completions lock NEGATIVE** (guaranteed-loss pairs = stops in disguise, and stops lose here); skipping them: sequential-pair PnL **+211¢ → +5003¢**, avg lock +0.18→+7.89¢ | **DEPLOYED** |
| 3 | **Quote 1¢ books (`--min-spread` 0.02→0.01)** — pairing flips the calculus: a 1¢ book locks 1¢/pair risk-free even though 1¢ fills are zero-EV unpaired | tape floor table: all-spreads +1.74¢/win (t=2.1) vs ≥2¢-only **−0.13¢/win**; ≥2¢ books are only 10% of minutes and skew toward stress | **DEPLOYED** |
| 4 | **Open-burst concentration** — quote at second 0 via zero-RTT rollover prefetch; the fresh wide book is where locks are biggest | live: 85/103 fills in minute 0–1 at +3.24¢/fill (one window locked +76¢/pair); tape: k=2–3 best pnl/quote (+0.64/+0.76¢) with widest spreads; P(both)≈0.91 throughout | **LIVE already** (caps bound its tail) |
| 5 | **BTC-only box allocation** — completion probability is the binding constraint, not lock size | P(both fill): BTC **0.93**, ETH 0.71, SOL 0.51, XRP 0.49; ETH net **−12.3¢/win (t=−6.8)** despite 2× wider locks. Wide spread + no completion = toxic unpaired inventory, i.e. off-BTC "better" locks are bait | **LIVE already**, now evidence-locked |
| 6 | **Completion-urgency improve** — spend the sub-cent improve tick aggressively on the *completing* side only (queue-front for leg 2), stay passive when flat | front-of-queue worth +4.7¢/win (queue replay); targeted spend cuts improve cost ~half while accelerating pairing | candidate — size it with the new depth data |
| 7 | **Queue-aware leg-1 entry** — only open a box when the *completing* side's displayed queue is thin (fast pairing likely) | the new full-depth `book_*.jsonl.gz` stream records exactly this (every level, both sides, on change, with RTT); previously q_ahead was unknowable | **WIRED**, testable after ~days of stream |
| 8 | **OI/volume churn filter** — flat-OI + high-volume windows are closeout churn (benign two-way flow → fast completion); rising OI = informed positioning | `stat` records (30s volume/OI/liquidity) now collected; tape proxy: completion robust across vol regimes (0.91), pnl peaks at 5–10bps — the OI version should separate better | **WIRED**, needs data |
| 9 | **Balanced-flow leg-1 gate** — enter boxes when prior-minute taker imbalance is small | tape: \|imbalance\|<50 contracts → P(both)=0.946, +1.24¢/quote (n=56, weak); >1k → +0.24¢ | monitor; promote if it holds at n |
| 10 | **Tilt-zone preference** — boxes pay best at \|p−0.5\| ∈ 0.25–0.4; tails have 0.42¢ spreads (no lock possible) | tape: tilt +0.41¢/quote vs mid +0.07/tail +0.01; tails already excluded by the 0.03–0.97 band | partially live; #3 unlocks the 1¢ tilt books |

Net effect of the deployed three (1–3) on the tape: the strategy keeps ~100% of box income,
refuses guaranteed-loss pairs, and roughly 10× the quoting opportunity set vs the 2¢ floor.

## Metrics instrumentation (what the trader + collector now record)

Operator's framework: *quote quality → are we making markets well; markouts → are we picked
off; settlement PnL → does hold-to-expiry work.* Coverage map:

**Live trader** (`kalshi_fees_*.jsonl`, `kalshi_markout.jsonl`, `live_metrics_*.jsonl`, log):
- every fill now carries **decision context**: mid/bid/ask/depth/microprice/spread at fill,
  net inventory after, per-side fill counts, resting time, seconds-into-window → effective
  spread, fill-rate-by-level, queue capture, inventory age all derivable per fill
- **markout curve at 5s/30s/60s/300s** per fill (5s still feeds the rolling kill), window-pinned
  so a markout never references the next market's book
- per-window `[BOX]` line: paired count, locked $, unpaired residual
- per-window `[OPS]` line: places, cancels, cancel-fails, fills, quote-to-trade ratio
- `live_metrics`: place acks/rejects + latency, cancel batches, balance polls, window summaries
  (realized + mark + net delta), WS staleness events

**Collector** (4 assets, both legs — GHA + local): full-depth book stream (+RTT, spot),
exchange-clock trade tape, 30s volume/OI/liquidity, strike/lifecycle metadata, settle-time
finals, 25-variant shadow fills with mo5–mo300 + settlement markout, coverage/tombstones.

**Dashboard**: `python kalshi_scorecard.py btc` → net PnL after fees, PnL/contract & /window,
**box decomposition (locked vs residual)**, max drawdown + time under water + worst window +
peak unpaired inventory, markout curve, effective half-spread captured, time-to-fill,
quote-to-trade, **calibration by entry-price bucket**, balance trajectory. Settlement results
fetched once per ticker (cached `.scorecard_results.json`).

## Reviewer-blueprint triage (2026-06-11): adopted vs refuted

External review proposed a "world's best maker-box bot" blueprint. Critical findings:

**Category error at its core**: `if yes_bid + no_bid < 0.99: place_both()` describes
CROSS-VENUE taker arb (its sources arb Polymarket<->Kalshi). On one Kalshi book,
`yes_bid + no_bid = 1 - spread < $1` ALWAYS — every nonzero-spread market "triggers".
There is no detection problem in a single book; there is a COMPLETION problem
(queue position, P(both fill), adverse selection on the unpaired leg).

**Refuted by our data**:
- "Exit when profit < 1c / rotate capital within minutes" — exits tested on 20,318
  fills: every variant loses; 15-min windows already rotate capital at the maximum.
- "Scan 100+ markets" — completion collapses off-BTC (0.93 vs 0.71/0.51/0.49);
  breadth without completion manufactures unpaired toxic inventory (ETH −12.3¢/win).
- "Risk-free once filled, so only operational risks" — the risk is the UNPAIRED
  INTERVAL (leg 1 filled, leg 2 not): adverse selection, not ops. Our loss-limit kill
  came exactly from there.
- "1%+ spread threshold (0.99)" — our `--min-lock 0` is deliberately looser: a 0-lock
  completion flattens a leg whose expected hold value is NEGATIVE (−16.3¢/win residual);
  demanding 1¢ keeps more unpaired exposure, not less.

**Adopted (now in `kalshi_scorecard.py`)**: pairing efficiency (% of contracts locked,
the honest "dual-leg fill rate"), leg imbalance ratio, expected-vs-realized lock
(completion slippage — the maker's version of TCA), order rejection rate. The rejection
metric immediately paid for itself: it surfaced a 2,032-reject/hour storm in the session
16h ago (pre-WS-feeder, the loss-limit session) vs ~5/hr now — retroactive confirmation
the WS-book fix worked.

**Latency/infra review**: already in-region (~40–55ms REST RTT measured, WS push book,
local book mirror, event-driven loop) — equal to the review's own "free tier" target;
its further gains (NY4 colo $145/mo, FIX) are not free-tier and not yet worth it at $11
bankroll. The REAL infra gap is that this container is EPHEMERAL: the durable home for
trader+collector should be an always-free VM (e.g. Oracle Cloud always-free tier,
us-east) — standing recommendation for the months-long run. (Account-cycling to renew
free trials, as the review suggests, is ToS evasion — not doing that.)

**Candidate kept on the list**: parallel placement of the two legs at window open
(~50ms queue gain; needs per-thread sessions — requests.Session is not thread-safe).

