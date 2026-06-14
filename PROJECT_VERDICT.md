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

## SPORTS BETTING — same wall (access / efficiency), no money-printer
`SPORTS_BETTING.md` (`56fb362`): US soft sportsbooks have a real +EV signal (few % ROI vs Pinnacle fair)
but BAN/limit winners in weeks; Pinnacle/Betfair don't ban but are US-illegal -> ACCESS is the wall.
Kalshi sports ESCAPES the queue-death (slow taker buy-and-hold, exchange can't ban a winner) BUT its
liquid games are EFFICIENT (Susquehanna-priced, ~0% overround, 1-3c spreads -> no edge after the hurdle);
only the illiquid slice (futures/props/minor leagues) is soft, and it's THIN (5-10c spreads, tiny
capacity) -- marginal, unproven. Needs a Pinnacle feed + 300-500 games of net-of-fee CLV to settle.

## THE META-PATTERN (the real finding)
Every MICROSTRUCTURE / MISPRICING edge here dies to the SAME wall -- ACCESS or EFFICIENCY, never signal:
box (last-in-queue latency), fair-value (efficient), L/S momentum (perps US-inaccessible), sports (books
ban / sharp venues illegal / Kalshi-liquid efficient / Kalshi-illiquid thin). Wherever a market is deep &
accessible it is efficient; wherever it is soft it is access-gated or too thin. The ONE survivor --
long-only momentum -- survives precisely because it is NOT a pick-off edge: it is a BEHAVIORAL RISK-
PREMIUM (trend) that needs no speed and no gated venue. LESSON: for a US retail small bankroll, the
deployable edges are SYSTEMATIC RISK-PREMIA, not speed/mispricing plays.

## CLOSED PATHS (do not relitigate)
Funding carry (~1%/yr net, too small), mean-reversion/stat-arb (sub-our-latency, fee-eaten), ETH/SOL/XRP
boxes (-EV), multi-factor blends (momentum-alone wins), Polymarket TRADING (US-illegal; kept only as a
read-only signal that matures passively in the collector), sports value-betting on soft books (banned).

## BOTTOM LINE  (the deployable recommendation)
- **WINNER: cross-asset ETF MOMENTUM** (`ETF_MOMENTUM.md`, `e3e2d57`) — the best deployable edge for a
  US small bankroll, decisively better than every crypto path. Config: ~30-ETF cross-asset universe
  (US sectors + size/style + intl/country + bonds/gold/commodities/REITs), 6-month RISK-ADJUSTED
  (return/vol) cross-sectional momentum, top K=5 equal-weight, dual/absolute (>cash) filter + SPY>200d-MA
  regime gate, MONTHLY partial-rebalance (~1/3 toward target). Net **CAGR ~8-9%, Sharpe ~0.80-0.83,
  maxDD ~-17%**; robust on the never-tuned 2016-2026 holdout (0.81) and through 2008 (-8.6% vs SPY -55%)
  & 2022 (~flat). Fully US-legal in any commission-free brokerage, IRA-able (NO short-term-gains drag),
  $1k-deployable, no access/latency wall, survives 10bps costs (Sharpe 0.65).
  - **Optional crypto sleeve, the RIGHT way:** add crypto-proxy ETFs (IBIT/MSTR/COIN/GBTC) as high-beta
    members -> CAGR 8.9%->14.5%, Sharpe 0.81->0.98 for ~2pp more DD (the gates only hold them while
    risk-on). This is how crypto belongs in the book — not as a standalone box or a perp L/S we can't access.
  - **Honest caveat:** it does NOT out-RETURN a raw equity bull (2016-26 SPY/60-40 beat it on CAGR); its
    value is crash-robust, risk-managed, TAX-EFFICIENT equity-like return — the right profile for a small
    bankroll that can't survive a -55% hold.
- **Crypto-native long-only momentum** (`MOM_LONGONLY.md`/`MOM_LO_RISK.md`) is +EV (~Sharpe 0.5-0.7) but
  its full-cycle drawdown is IRREDUCIBLE (~-45%; no overlay fixes it OOS, only sizing) and it carries a
  US short-term-gains tax drag (weekly turnover). Dominated by the ETF form; keep only as the crypto-proxy
  members inside the ETF framework.
- **The Kalshi maker-box — the original project core — is structurally negative** at our cloud infra
  (last-in-queue behind a co-located mechanical MM; no lever cuts strand <5%). Run only minimally for the
  live A/B of today's fixes, then OFF unless it surprises positive.
- **Path to deployment:** lock the ETF spec, build a monthly paper-trading harness to accumulate a real
  forward track (target rolling Sharpe >=0.6 over 3-6mo), then size SMALL with real money. The outcome
  distribution + concrete %-of-bankroll sizing is under study (MOM_OUTCOME_DIST.md / ETF deploy spec).
