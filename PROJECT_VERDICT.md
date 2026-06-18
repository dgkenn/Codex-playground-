# Project verdict — what is and isn't profitable here (2026-06-14)

Brutally honest synthesis after the full research program (20+ agent studies, live trading, deep
backtests). Goal throughout: a profitable, scalable strategy at a SMALL bankroll. This is the map.

> ## 🔄 "TRADABLE KALSHI STACK" — UPDATED 2026-06-19: a real but TINY-CAPACITY edge found (supersedes the negative below)
> The "RESOLVED NEGATIVE" call below tested only the **taker** side. Correct pushback (*a low-volume market
> can't be fully efficient*) prompted a 4-stream **maker**-side test (`KALSHI_MAKER_VERDICT.md`). Result: a real,
> +EV, queue-independent, **maker-fee-free** edge DOES exist — **sell overpriced longshots (maker NO, p<0.20) on
> soft zero-maker-fee categories**: +0.97¢/contract at ~17σ net of adverse selection AND fee (263k real fills),
> no fast-pickoff toxicity, bias generalizes across categories (Politics/Science/Climate/Entertainment).
> **BUT it is capacity-capped at ~$30–150/month** (`KALSHI_MAKER_CAPACITY.md`): soft books turn over only
> ~$300–800 notional/market in 3–4-contract nibbles, flow-capped (more bankroll doesn't help), negative skew.
> **So: a tradable Kalshi stack EXISTS, but it's a small automated income stream (~$30–150/mo), not a path to
> $500/mo and it does not scale.** The favorite-longshot tension is fundamental — the bias is biggest exactly
> where the books are thinnest. Deploy only if ~$30–150/mo of uncorrelated +EV income justifies the build.

> ## 🔒 "TRADABLE KALSHI STACK" — earlier NEGATIVE (taker-only; superseded above)
> A dedicated push to build a tradable Kalshi stack tested every positive-prior candidate to ground:
> maker box (queue-dead, −$3/day live), 15m directional taker (efficient <1min; 5,749 windows),
> signal ensemble (worse than the mid), **Polymarket→Kalshi lead-lag** (real vs spot at HAC t+27 but
> only **0.064¢ vs Kalshi's mid**, ~40× below the 2–3¢ taker cost — `PMKT_LEADLAG.md` §5), macro
> (efficient — `KALSHI_MACRO.md`), sports (±0.3¢ calibrated), weather (calibrated), and the
> **favorite-longshot value edge** on soft markets via candlestick mid-life prices (`KALSHI_FAVLONG_SCAN.md`:
> taker-side null). **This negative held for the TAKER side; the MAKER side (above) found the real pocket.**
> The deployable answer for the $500/mo objective still remains the PORTFOLIO route (final-answer section below);
> the maker longshot harvest is a small additive income stream, not a replacement.

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

## SPORTS BETTING — exhaustively mapped (8 studies); promo extraction is the only deployable win
Consolidated verdict: **`SPORTS_VERDICT.md`**. The full sweep — game lines (`SPORTS_BETTING.md`),
exchanges (`SPORTS_EXCHANGE.md`), props (`SPORTS_PROPS.md`), live/steam (`SPORTS_LIVE_STEAM.md`),
niche-sport modeling (`SPORTS_NICHE_MODEL.md`), cross-book + Kalshi arbitrage (`SPORTS_ARB.md`),
Kalshi calibration (`SHARP_VS_KALSHI.md`), and promo EV (`SPORTS_PROMO_EV.md`):

- **Game lines:** soft books carry a real few-% +EV signal vs Pinnacle fair but BAN/limit winners in
  weeks; Pinnacle/Betfair don't ban but are US-illegal. Kalshi escapes the ban (can't-ban exchange) but
  its liquid games are SIG-priced/efficient (~0% overround, calibrated +-0.3c over 706 games) -> no edge.
- **Props / niche sports (table tennis, esports, darts, MMA, KBO/NPB, WNBA):** softness is REAL and data
  is free, but the SAME three facts that make them soft kill deployment -- vig 2-3x higher (8-15%), limits
  $50-500, and prop/niche winners get limited FASTEST. Documented niche ROI ~10-13% is tipster-self-
  reported; in illiquid markets CLV itself stops predicting profit (Unabated; ATP counter-case +8.9% ROI
  at -0.2% CLV). Real edge, un-deployable shape: tiny capacity + a real modeling grind.
- **Arbitrage:** cross-book sure-betting is real but self-terminating (>98% of arbs <1.2%, ~13s windows,
  arbers limited in days). Kalshi-vs-book never locks (liquid Kalshi==sharp + 4.5-10% book vig => sum>1
  unless the book line is stale, which is exactly what gets you limited). Grading-mismatch breaks "locks."
- **THE ONE DEPLOYABLE PLAY: promo / bonus extraction** (`SPORTS_PROMO_EV.md`) -- ~$1-5k one-time, decaying;
  hedge the bannable-book leg on Kalshi (can't-ban rail). Not recurring income, but real and accessible.
- **One armed forward experiment:** Kalshi maker timing-lag (`kalshi_clv_lag.py` / `sports_clv_collect.py`),
  no-ops until a free `ODDS_API_KEY` GitHub secret is added.

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

## ===== FINAL ANSWER (the goal: "$500/month trading from a small bankroll") =====
**$500/MONTH IS A BANKROLL-SIZE PROBLEM, NOT A STRATEGY PROBLEM** (`INCOME_500_REALITY.md`, `945f828`):
- At safe ~8.5% returns, $500/mo ($6k/yr) needs **~$70k** (mean) / **~$165k** (to survive a bad-luck year).
- Forcing it from $5k = **120%/yr** -> only leveraged crypto-trend can target it: 2x/3x/4x median CAGR
  ~8%/-25%/-61%, worst-5% DD near -100%. **Ruin is the base case.** With $500/mo WITHDRAWALS, P(survive 3yr)
  = ~1% @ $5k, 24% @ $10k, 89% @ $25k, ~100% only @ ~$60k.
- **No shortcut edge exists** -- every high-return-on-small-capital play here is dead/walled/capacity-capped
  (Kalshi box=queue-dead, sports=banned, fair-value=efficient, weather=thin/unproven). Small-capacity edges
  pay small dollars; scalable edges are low-% and need a big base. That is THE finding of this whole project.
- **THE REAL PATH:** treat a small account as a GROWTH engine (don't withdraw), CONTRIBUTE monthly, compound
  the ~10-15% edge to the ~$70k base, THEN draw $500/mo at a safe ~10%. From $10k + $1k/mo @ ~10% -> ~$70k in
  ~4yr (+$2k/mo -> ~2yr). The trading edge is the ~10% finisher; CONTRIBUTIONS + TIME are the real lever.

## THE BEST DEPLOYABLE PORTFOLIO (regime-robust, refined)
**A TREND-OVERLAID ALL-WEATHER PORTFOLIO** (`REGIME_ROBUSTNESS.md` `959984e` + `FINAL_PORTFOLIO.md` `eea3225`):
a Permanent-Portfolio-style base (stocks / long-Treasuries / gold / cash) with a 6-12m TIME-SERIES TREND
filter that parks each FALLING sleeve in cash. Long-history (1972-2023) Sharpe **1.4-1.5 vs pure PP 1.25**,
drawdown HALVED, 2022 loss -13%->-4%, robust across the 1970s bond bear + stagflation + 2008 + 2022.
- WHY over pure PP: PP's edge is partly a 2007-24 negative-correlation + one-time-gold artifact; 2022
  (stocks+bonds down together) is its kryptonite. The trend overlay is the regime INSURANCE that fixes it.
- Over 2007-2026 specifically, the equivalent winner is 70% PP-core + 30% active momentum+trend satellite
  (Sharpe 1.14 / maxDD -11.9%, beats pure PP 1.07 and pure active 0.92 on BOTH axes). Same idea: all-weather
  base + trend/momentum discipline. US-legal, IRA-able (tax-efficient), fractional-share-deployable from ~$500.
- Crypto, if wanted: <=5% trend-timed BTC/ETH via IBIT/ETHA (>=200d SMA) in an IRA -- never buy-and-hold.
- Lazy near-equivalent: pure Permanent Portfolio, quarterly (Sharpe ~1.07, zero effort) -- fine if you won't
  run the trend overlay, but accept the 2022-type vulnerability.
- Stocks do NOT predict bitcoin (`STOCKS_PREDICT_BTC.md` `0a7459e`): all 17 candidates null on the
  overnight-gap test; BTC leads its proxies. No equity->BTC timing edge.

## HIGH-RISK, DATA-INFORMED (only for DISPROPORTIONATE +EV upside)
For a high-risk-tolerant investor, the smart structure is CONVEXITY (bounded downside, asymmetric +EV
upside), NOT leverage:
- **CONVEX BARBELL (`CONVEX_ASYMMETRY.md` `a7e44f6`): 20-30% trend-timed CRYPTO BASKET (BTC+ETH+SOL, each
  held only >200d SMA else cash, via IBIT/ETHA spot ETFs in an IRA) + 80-70% trend-overlaid all-weather
  base.** The basket is the rare positive-SKEW (1.45) AND +EV object -- tail ratio 2.83, Omega 3.20, the
  trend exit MANUFACTURES the convexity (buy-hold DD -83%->-58%, skew 0.62->1.45). At 20%: blend CAGR
  12.6%, maxDD -21%, Sharpe at its 1.15 peak. Pure-slice 5yr from $5k: P(2x)=46%, P(5x)=23%, p95~$112k vs
  p5~$671 (lose the slice ~1-in-5) -- but at the 20% barbell with contributions, **P(total ruin)~=0** (base
  + contributions floor it). Honest: short ~1-cycle crypto sample, right tail haircut (OOS tail 2.8->1.66).
- **LEVERAGE (`LEVERAGE_GROWTH.md` `129b082`): modest only, and barely worth it if contributing.** The
  trend-overlaid book's halved -10% DD gives headroom; DD-budget (not Kelly) caps ~2.2-2.45x (CAGR ~15%,
  maxDD -35%, no ruin -- trend de-risks to cash). BUT with $5k+$500/mo, 2.2x cuts median years-to-$70k only
  8.5->7.2y (~1.3y) for a 1-in-11 >50% DD -- contributions dominate. Recommend **1.25-1.5x or 1x if
  contributing** (margin taxable, or 1.5x-LETF SSO/UBT/UGL in an IRA). Leverage matters only for a
  no-contribution lump sum.
- **KEY: do NOT lever crypto.** The trend gate amplifies leverage's right tail but CANNOT cap its left tail
  (weekly lag vs fast crypto crashes): 2x/3x trend-gated crypto = -93%/-99% DD. Diversifying ENTRIES
  (the basket) is how you take crypto risk; LEVERING is how you blow up. Naive 3x-LETF, OTM-call-buying,
  alt buy-hold all REJECTED as negative-EV / uncapped-left-tail.

## BOTTOM LINE  (how we got here -- the full map)
- **THE HUMBLING HEADLINE (`STATIC_ALLOCATION.md`, `1085652`): a DEAD-SIMPLE STATIC PORTFOLIO BEATS the
  active book on risk-adjusted return.** Permanent Portfolio (25% each SPY/TLT/GLD/cash) Sharpe **0.93**
  and inverse-vol risk-parity **0.84** vs the active momentum+TF book **0.81** (full sample); OOS 2016-26:
  **PP 1.06 / RP 1.05 / 60-40 0.91** vs active **0.91**. The active book's Sharpe margin is NEGATIVE in- and
  out-of-sample; PP even beat it in the GFC (-3.8% vs -10.7%) and COVID (-6.4% vs -13.3%). The active
  book's ONLY genuine edge is ~4-5pp shallower maxDD (-13.6% vs PP -18%) + 2022-robustness. **For a US
  small bankroll, the complexity is NOT worth it for most people: hold an unlevered Permanent Portfolio
  or risk-parity (Sharpe ~0.9-1.0, ZERO effort, IRA-able).** Run the active book ONLY if you specifically
  want the shallower drawdown AND will tolerate monthly effort + trailing every bull market. (Caveat both
  ways: statics rode a 17-yr bond+gold tailwind that may not repeat; 2022 is where the momentum book's
  rotation-out-of-falling-assets shines -- its strongest forward argument. Levering a static to match the
  active book's return is WORSE risk-adjusted, so that's not the answer either.)
- **WINNER (active edge, if you want one): cross-asset ETF MOMENTUM** (`ETF_MOMENTUM.md`, `e3e2d57`) — the best deployable ACTIVE edge for a
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
- **DEPLOYABLE NOW** (`ETF_DEPLOY.md` + `etf_momentum_live.py`, `1cf9cef`): the harness RUNS on live
  yfinance data and outputs this month's target portfolio (2026-06-12, regime ON: 20% each DBC/USO/XLE/
  MTUM/XLB). Outcome dist $1k/2yr: median $1,123, p5 $931, p95 $1,375 (much tighter than crypto's
  $519/$5,384 -- lower return, far lower risk). Sizing off the ~18% historical maxDD: ~28% of NW at a 5%
  loss tolerance; start $500-1k until the paper track clears the go-live bar (rolling Sharpe >=0.6, 3-6mo).
  Runbook + inert monthly `etf-paper.yml.sample` shipped.
- **Crypto outcome dist** (`MOM_OUTCOME_DIST.md`, `1e7f0e4`): the crypto sleeve underperforms simply
  HOLDING BTC on ~62% of 2yr paths and has P(>30% DD)~74% -> crypto belongs only as gated proxy-ETF
  members inside the ETF book, not a standalone sleeve.
- **Remaining gap before real $1k:** whole-share/cash-drag at small size (a 20% slot ~$200 < 1 share of
  MTUM ~$220) -> needs fractional shares or a small-bankroll execution adjustment (final study).
- **Crypto, if you want it** (`BTC_TREND_TIMING.md`, `7342b13`): TREND-TIME BTC/ETH (>=200d SMA, weekly
  check) via IBIT/ETHA in an IRA -- Sharpe 0.97->1.1-1.3, recent maxDD -77%->-26/-36% with higher CAGR;
  do NOT buy-and-hold (its -80% crashes). Redundant with the book's crypto-proxy members -- pick one,
  size small. Standalone crypto momentum loses to BTC-hold 62% of paths (don't bother).
- **Kalshi WEATHER -- RESOLVED, NO CONFIRMED EDGE** (`KALSHI_WEATHER.md` `304643b` -> `WEATHER_STRATEGY.md`
  `8593554` -> `WEATHER_MODEL.md` `4c46444`): the warm-tail "underpricing" thesis was MODEL ERROR, not market
  mispricing. Independent calibration (bias-corrected Normal, sigma~1.1-1.75F/city, validated on 2025
  ASOS hold-out, Brier 0.066) is reliable ONLY for the CENTER (20-60% brackets) -- but the center is
  Kalshi-EFFICIENT (1-3c). The TAIL (where Kalshi deviates) is ~1% events the model OVER-predicts (1F error
  -> 3.3x tail-prob swing) = not callable. Pincer: model-reliable where Kalshi-efficient; Kalshi-deviates
  where model-unreliable. The Sharpe~3 strategy sim was CONDITIONAL on calibrating the traded (tail)
  brackets, which fails -> its own no-edge case (loses money) is the real one. Same shape as the crypto
  fair-value null. kalshi-weather.yml keeps collecting as a cheap passive final check (could surface
  center mispricing), but the prior is now strongly NEGATIVE. Do not deploy.
- **REBALANCE-CADENCE WIN** (`GLOBAL_ALLWEATHER.md` `d6980e1`): for the all-weather base, REBALANCE ANNUALLY
  (not monthly): turnover -75%, Sharpe 0.94->1.17, maxDD -9.6%->-7.8% (rebalancing less lets the trend run;
  quarterly is a trap), optional 10-20% no-trade band for taxable accounts. Global diversification REJECTED
  (US PP + trend overlay wins; simpler is better). Net: the base is higher-Sharpe AND lower-effort/tax.
- **RESEARCH ENDPOINT (honest):** the edge space is exhaustively mapped. The brutal conclusion is that for
  a US small bankroll, the best risk-adjusted, zero-effort answer is a SIMPLE STATIC PORTFOLIO; the active
  momentum+trend book buys only a modest drawdown reduction for real ongoing effort. Further backtesting
  adds nothing. The genuinely-useful remaining moves are OPERATIONAL: (a) just deploy a Permanent
  Portfolio / risk-parity (the default), (b) optionally paper-track the active book 3-6mo if you want the
  DD edge, (c) optionally start the Kalshi-weather CLV collection. Not more edge-hunting.
