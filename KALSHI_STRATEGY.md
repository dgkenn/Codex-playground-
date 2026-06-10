# The best Kalshi 15-min strategy — the full search, the metrics, the verdict

**Search scope on ALL available data** (30 days of real trade tape + 1-min books, ~1,170
windows/asset; deep candle history; PM/Kalshi cross-venue join):

| family | tested | result |
|---|---|---|
| Directional (taker) | 36 feature×time tests (`directional_deep.py`) | **null** — 0 clear; consistent with the 12k-window PM null |
| Maker: placement×gate×timing×band | 312 configs on the real tape (`kalshi_opt.py`) | positive but uncertified (below) |
| Cross-venue PM↔Kalshi | settlement agreement, divergence, locks, lead-lag (`xvenue.py`) | real signal, execution-caveated (below) |

## The verdict: BTC-only, sub-cent-improved, spot-gated passive maker

**`improve(0.1¢) + sided past-spot gate (~8bps/3min) + minutes 2–13, BTC only`** is the best
strategy the data supports — and the data's honest power limit must be stated with it:

- Every fill model agrees on the SIGNS: front-of-queue capture is positive (+2.6 to +6¢/win OOS),
  back-of-queue is ruinous (−8 to −47¢), the gate adds value at every depth, alts are negative even
  at the front (ETH −4.5¢ gated/front; thin books have no benign traffic — **BTC-only**).
- The full METRICS battery on the tape-replay winner (FULL sample): net +2.3¢/win (t=2.1), PF 1.22,
  win% 73, MC-bootstrap 98.6% positive, Calmar 4.8 — but **OOS alone: t≈0.7–1.6, Calmar 1.3,
  PF 1.10**. Param-sensitivity is flat (theta 10/12/14 → +1.2/+1.6/+1.8¢: no cliff).
- **Iteration stop-rule applied**: after 312-config selection, the best OOS t is ~1.1 — *lower* than
  the simple pre-registered gate (t=1.6). That is the signature of selection pressure on 30 days of
  data, not of a better strategy waiting deeper in the grid. Tuning further on this tape would be
  curve-fitting; METRICS.md's own discipline (judge OOS, freeze params, confirm prospectively)
  says stop here.
- **What certifies it**: the live shadow A/B (`kalshi_collect.py`, running the full 25-gate roster
  with rebate=0) — the same instrument that certified the PM edge. At 96 windows/day the OOS power
  that took the tape 30 days accrues in ~2 weeks, with REAL queue traffic instead of a fill model.
  Promotion rule: a gate beats the roster on Calmar IS+OOS in the shadow data → it becomes
  `kalshi_trader --gate` default.

## The high-potential overlay: cross-venue (PM ↔ Kalshi)

Same windows trade on both venues. Measured (`xvenue.py` + honest re-test on executable PM books):
- **Settlement basis risk is real**: 6.8% of windows resolve DIFFERENTLY (median |move| 2.3bps in
  those windows vs 10.7 normally — coin-flip windows where Chainlink/Binance vs CF Benchmarks
  diverge). Any cross-venue position carries this tail (a disagreeing box pays $2 or $0).
- **Divergence is large and persistent** (mean ~9¢ between PM prints and Kalshi mid), but most of it
  is PM print staleness (PM converges to Kalshi at corr +0.79 — Kalshi leads). With REAL PM books
  (our collector's 1s ticks, Jun 7–10 overlap): locks net of both fees + worsened prices still
  appear in **31.6% of minute-slots at +4.0¢ average** — but candle closes carry no size (dust-quote
  inflation risk), legs need near-simultaneous execution, and the disagreement tail concentrates
  exactly where locks do (p≈0.5).
- **Deployable expression**: not the taker box — the **maker overlay**: use the other venue's book
  as a fair-value input to the Kalshi gate (fee-free, no simultaneity, basis risk only on net
  inventory). Requires two-venue collection: `kalshi_collect` should also poll the PM book
  (4 cheap REST calls) and record `pm_mid` per tick — wired as the next collector iteration.

## Why this is "the best" and what would change it
Everything else tested is either null (direction — twice, two venues, 13k windows), negative
(joining deep queues; alt assets), or dominated (ungated vs gated at every depth). The two live
unknowns that could upgrade the answer: real queue-traffic share (A/B measures it) and the
cross-venue overlay (needs the two-venue tape). Re-run the search as data grows:
`python kalshi_opt.py btc` · `python xvenue.py` · `python directional_deep.py hist_kalshi_btc15m.parquet`.
