# Project verdict — what is and isn't profitable here (2026-06-14)

Brutally honest synthesis after the full research program (20+ agent studies, live trading, deep
backtests). Goal throughout: a profitable, scalable strategy at a SMALL bankroll. This is the map.

## THE MAKER-BOX (Kalshi BTC 15-min + hourly KXBTCD) — STRUCTURALLY DEAD at our infra/bankroll
The core product. The edge is REAL but un-capturable from where we sit.
- **Clean box is +EV (+0.69c/box)**: rest buy-YES + buy-NO at ATM, both fill -> lock the spread.
- **But strands kill it.** A leg fills, the other doesn't (or completes at a high chase price); the
  unpaired leg settles worthless ~100% (adversely selected). Live strand 18-22% vs **4.4% break-even**.
- **Strand is caused by QUEUE POSITION**, and it is structural (`QUEUE_TIMING.md`, `bc2ff3a`):
  - We rest a median 1.37s = one full MM heartbeat; only 7.7% of fills are front-instant.
  - The dominant ladder market-maker reprices on a mechanical 1.20s heartbeat = our own poll cadence,
    and the touch reprices within one snapshot of a spot move. The sub-1.2s window we'd need to land
    front-of-queue is below our cloud react + order-ack latency (~27ms+ on GitHub Actions vs a
    co-located MM). We fill LAST, exactly when the touch is moving (diverging-touch markout −4.01c).
- **Every lever to cut strand <5% was tested and FAILED:**
  - Per-open gating — toxicity is unpredictable at open (OOS AUC 0.56). `BOX_ADVERSE_OPEN.md`.
  - Window/regime selection — strand is regime-invariant; deeper/active books strand MORE (queue
    contention), floor ~12%. `BOX_REGIME.md`.
  - Queue-timing (heartbeat-anticipation requote) — even the q0->0 upper bound only reaches 7.1-9.6%,
    never <4.4%; real latency -> back toward 22%. `QUEUE_TIMING.md`.
  - Improve-tick (pay 1 tick to jump queue) — costs 1c/box > the 0.69c edge. Net negative.
- **Sizing verdict** (`BOX_SIZING_ALLOC.md`): negative-EV on the live distribution; growth-optimal size
  = minimum; book saturates ~$500 capital at ~$2-10/day GROSS *only if* strand were <5% (it isn't).
- **The completion fixes shipped today** (`--post-complete-freeze`, give-cap 0.25, max-net hardening)
  are LOSS-MITIGATION — they bound the strand COST and kill over-fill residuals, but they do NOT change
  queue position, so they make the box "less negative," not positive. The live A/B (live_gate, ~1-4
  days) is the final empirical check; theory says it stays negative.
- **Only conceivable revival = different INFRASTRUCTURE** (a persistent, low-latency, co-located box
  near Kalshi/AWS us-east). Not worth it for a ~$2-10/day ceiling, and beating a co-located mechanical
  MM as retail is unlikely. NOT recommended.
- KXBTCD hourly (`KXBTCD_DEPLOY.md`) is the SAME microstructure / same queue problem — not an
  independent win; inherits the same death. ETH/SOL/XRP boxes were already closed (-EV at completion).

## FAIR-VALUE TAKER (directional / mispricing) — DEAD (price is efficient)
`BINARY_FAIRVAL.md` (`0befe66`): the Kalshi BTC binary price is EFFICIENT vs spot. The mid is a BETTER
probability estimate than a no-lookahead GBM digital (OOS Brier 0.140 vs 0.150). A taker loses
−2.2 to −4.1c/contract at every threshold/tau/price-band. No favorite-longshot bias to harvest. The
deep-BTC work already showed spot mid is the sufficient statistic (no lead-lag). Directional edge = nil.

## CROSS-SECTIONAL MOMENTUM — the ONE real edge, but capital- and access-constrained
`MOMENTUM_SPEC.md` (`99120fe`): risk-adjusted ~10d momentum, top-15 liquid USDT perps, equal-weight
dollar-neutral, weekly, partial-0.7, BTC-trend-gated. Forward Sharpe ~1.0 (maxDD ~13-15% gated).
- **Unlike the box, it has NO latency/queue problem** (weekly rebalance, taker, seconds latency is fine
  — a cloud bot runs it perfectly). It SCALES with capital and is genuinely +EV OOS.
- **Two real constraints:** (1) capacity saturates ~$1-3M (irrelevant at a small bankroll — it just
  makes smaller absolute $); (2) the dollar-neutral version needs PERPS to short the bottom quantile,
  and US persons can't cleanly access offshore perps (OKX/Binance/Bybit/dYdX geoblocked) — the same
  legal wall as Polymarket. => The deployable question is a LONG-ONLY, US-spot-accessible version
  (under research: MOM_LONGONLY.md).

## CLOSED PATHS (do not relitigate)
Funding carry (~1%/yr net, too small), mean-reversion/stat-arb (sub-our-latency, fee-eaten), ETH/SOL/XRP
boxes (-EV), multi-factor blends (momentum-alone wins), Polymarket TRADING (US-illegal; kept only as a
read-only signal that matures passively in the collector).

## BOTTOM LINE
- **The Kalshi maker-box — the project's core — is structurally negative at our cloud infra/bankroll.**
  No software lever overcomes being last-in-queue behind a co-located mechanical MM. Recommend running
  it only minimally (live A/B of today's fixes) then OFF unless the A/B surprises positive.
- **The only genuinely +EV, scalable, latency-insensitive edge is cross-sectional momentum** — but its
  full form needs perps US persons can't access. The live question is whether a LONG-ONLY, US-spot
  (Coinbase/Kraken) version retains enough edge. THAT is the path worth pursuing for a US small bankroll.
- Honest truth: there may be no high-$/day small-bankroll edge here; the realistic prize is a modest
  (~10-18%/yr) long-only momentum sleeve that GROWS with capital, not a cash-printing box.
