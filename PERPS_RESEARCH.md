# PERPS_RESEARCH.md — can crypto perpetual futures make money for us?

**Date:** 2026-07-12. **Scope:** the operator can now trade crypto perps (long/short, leverage,
stop-loss/take-profit) alongside the validated Kalshi 15-min maker-box bot (~$50 live, 32-day
forward edge). Question: (1) is delta-neutral funding carry viable, (2) is directional/systematic
perp trading viable, (3) can perps hedge the box bot's inventory and let its size caps rise. This
is a desk-evidence survey (WebSearch/WebFetch + this repo's own prior live-tested findings) — no
new code, no live capital moved. It reuses and extends two prior scoping docs already in this repo
(`CRYPTO_FUNDING.md`, `PERP_HEDGE.md`) rather than re-deriving them from scratch; both are cited
inline and their numbers are load-bearing here.

---

## VERDICTS (read this section first)

| Angle | Verdict | Why |
|---|---|---|
| **1. Funding-rate carry (delta-neutral)** | **NOT-VIABLE at $50–$10k. VIABLE-AT-~$280K–$1M scale** (or opportunistically at smaller scale only during hot-regime spikes, with active monitoring) | Net carry after realistic costs is ~1–3.5%/yr in a calm regime (this repo's own 94-day screen) — a $500 account earns **~1–5 cents/day**. Matching the box's ~$27/day needs six-to-seven-figure capital. Regime spikes (Jan 2026: ~70% APR observed) can close some of that gap opportunistically, but only for capital that can tolerate two-legged operational risk and active exit management — not a "set and forget" retail sleeve. |
| **2. Directional/systematic (trend, mean-reversion, breakout)** | **NOT-VIABLE for a small retail account** | Published evidence: 74–89% of retail leveraged accounts lose money under the one regime with mandatory disclosure (EU ESMA, CFD/forex — the closest regulated analogue to crypto perps, since the US has no equivalent crypto-perp retail-loss disclosure yet); crypto-specific retail loss estimates run similar-to-worse (~84% lose money in year one per market surveys). Academic time-series-momentum has a real, positive-after-cost edge on liquid futures generally (Moskowitz/Ooi/Pedersen: Sharpe ~1.0 pre-cost across 58 markets) and crypto-specific TSMOM papers replicate a *weaker* version of it post-cost — but that edge accrues to disciplined, fully-costed, unlevered-to-modestly-levered systematic execution, not to a small account layering leverage + stop-loss/take-profit heuristics on top, which the evidence (below) shows *destroys* expectancy via forced-exit and liquidation risk. |
| **3. Perp hedge for the MM bot's inventory** | **NOT-VIABLE at current $50–500 scale. VIABLE-AT-~$10K+ bankroll** (when `--max-net` scales past ~6–7 contracts) | This repo already answered this for Kalshi's own BTCPERP (`PERP_HEDGE.md`): min tradeable size is 0.01 BTC (~$638 notional at today's BTC price), 10× the bot's actual unpaired-leg exposure. **New finding here: every other US-regulated venue has the same floor** — Coinbase's "nano" BTC perp, the smallest retail crypto-perp contract that exists in the US market, is *also* 0.01 BTC (~$638). There is no smaller US-legal contract to route around this with. Fees are not the blocker (Coinbase taker 0.03% ≈ $0.19/trade) — **lot-size granularity is**, and it's structural, not a venue-shopping problem. |

**Bottom line for a $50–$500 account: don't build any of the three now.** Carry and directional
both lose to (or barely clear) the cost of trying; the hedge idea is mechanically blocked by
contract-size floors common to every US-legal venue, not a fixable implementation detail. The
one actionable trigger is bankroll-linked: re-screen the hedge (not carry, not directional) once
the box's own scale gates (`SCALE_GATE.md`) put `--max-net` at 6–7+ contracts, which the box's own
pre-registered stages put at roughly the **$1,000–$10,000 bankroll stage**, not before.

---

## 1. Funding-rate carry — supporting evidence

### 1.1 What this repo already measured (reused, not re-derived)
`CRYPTO_FUNDING.md` (2026-06-14) ran a 94-day OKX screen (2026-03-12→06-14, 283 funding payments,
8 assets) — the longest window OKX's public API exposes. Key numbers, reused here:
- Mean annualized funding: BTC 1.54%, ETH 2.05%, basket (8 assets) 1.92% gross; DOGE was the best
  single asset at 3.99%; SOL was net *negative* (−0.84%) over the window.
- After a realistic round-trip cost (12–32 bps for the 4-fill delta-neutral open/close), net
  annualized carry was **~0.3–2.8%** per asset, **basket ~0.68–1.46%** depending on execution
  quality (maker vs taker).
- Funding is *persistent* (autocorr 0.26–0.55, same-sign-next-period 62–71%) — favors buy-and-hold,
  actively *punishes* churn: threshold/cross-sectional rotation strategies backtested to **−75% to
  −91%/yr** because turnover costs dominate the tiny per-period edge (0.13–0.36 bps per 8h vs.
  12–32 bps per round trip).
- Capacity is not the constraint (OKX BTC-USDT-SWAP OI ≈ $2B) — **the rate is**. To match the box's
  ~$27/day needs **~$1M at the basket rate or ~$280K at the best-single-asset (DOGE) rate**.

### 1.2 What changed since that screen: confirmed hot-regime spike, and the venue landscape
- A newer snapshot (Jan 2026, CoinGlass-style aggregate) shows BTC funding at **+0.51% per 8h
  period (~70.2% APR)** — a "hot" regime an order of magnitude above the 94-day calm screen ([Bitcoin
  Funding Rate — CoinGlass](https://www.coinglass.com/FundingRate/BTC)). This matches the repo's
  own caveat that 2024–2025-style bull regimes ran "8–20%+ annualized," and confirms funding
  *does* spike well above the calm-regime baseline — but spikes are not the base rate, they compress
  as soon as a trade gets crowded, and a small account has no edge in timing entry/exit around them
  better than the market. At a **$10,000** account, even the spike rate is only ≈$19/day gross
  before costs and monitoring overhead — real money, but it requires active two-leg risk management
  the calm-regime numbers say isn't rewarded most of the time.
- **US-retail venue landscape shifted materially in 2026.** Historically the deep, liquid perp
  venues (Binance, Bybit, OKX) are geo-blocked for US persons (confirmed directly against OKX/dYdX
  in the original screen). That changed in 2026: the CFTC issued a coordinated framework on
  **2026-05-29** clearing the way for CFTC-regulated US perpetual futures — approving a bitcoin
  perp for listing on a registered exchange (Kalshi's, per `PERP_HEDGE.md`) and issuing no-action
  relief letting registered FCMs intermediate access to *offshore* perp venues for US retail
  ([Katten: "Perpetual Futures Come Onshore"](https://katten.com/perpetual-futures-come-onshore-the-cftcs-new-regulatory-framework);
  [CoinDesk, 2026-05-28](https://www.coindesk.com/policy/2026/05/28/u-s-cftc-opens-crypto-perp-door-with-approval-of-first-regulated-firm)).
  Two brokers went live fast: **Coinbase Financial Markets** launched CFTC-regulated
  "US Perpetual-Style Futures" for US retail on **2025-07-21**, up to 10x intraday leverage
  ([Coinbase blog](https://www.coinbase.com/blog/perpetual-futures-have-arrived-in-the-us);
  [Coinbase learn](https://www.coinbase.com/learn/futures/us-perpetual-style-futures-101)); **Kraken**
  followed with CFTC-regulated US perps on **2026-06-15** via its Bitnomial-cleared derivatives
  arm, covering 9 assets (BTC, ETH, SOL, XRP, ADA, LINK, DOGE, LTC, AVAX), min intraday margin as
  low as $25 ([Kraken blog](https://blog.kraken.com/product/kraken-derivatives/announcing-cftc-regulated-us-perps);
  [CoinDesk, 2026-06-15](https://www.coindesk.com/markets/2026/06/15/kraken-debuts-u-s-perpetual-futures-as-crypto-derivatives-move-onshore)).
  Crypto.com's US perp status could not be confirmed either way from public sources as of this
  screen — treat as unavailable until verified. This is good news for *reachability* (no more
  geo-blocking workaround needed) but doesn't change the rate math in §1.1 — it just means the
  carry trade, if pursued, no longer requires an offshore-KYC venue.

### 1.3 Margin/liquidation mechanics of the short leg
The short-perp leg is the one that can blow up a nominally "delta-neutral" carry position: if spot
collateral sits separately from perp margin, an adverse move against the short can trigger
liquidation on the perp leg alone, breaking delta-neutrality and realizing a loss that can exceed
weeks of accumulated funding in a single candle (see §4 liquidation math — the mechanics are
identical to the directional case, just on the short side). `CRYPTO_FUNDING.md` already flagged
this as the "hidden cost the table doesn't show" and recommended ≤2–3x leverage with active margin
top-ups if the carry trade is ever built — which itself adds the latency-sensitivity the "slow
trade" framing claims to avoid.

### 1.4 Verdict detail
**NOT-VIABLE at $50–$10k** (cents to ~$1/day). **VIABLE-AT-~$280K (best asset) to ~$1M (basket)**
to clear the box's own $27/day bar on a sustained basis; a $10k account can occasionally clear a
meaningful fraction of that during confirmed hot-funding regimes, but that's regime-timing risk on
top of two-leg operational risk, not a durable edge — this repo's own turnover backtests
(−75% to −91%/yr for any dynamic/threshold variant) say attempts to actively time entries/exits
around the spikes are net-negative after costs. **Do not build.**

---

## 2. Directional / systematic perp trading — supporting evidence

### 2.1 Base rate: how many retail leveraged traders make money
There is no US-mandated crypto-perp-specific retail P&L disclosure (unlike EU CFDs), so the closest
regulated analogue is ESMA's CFD/leveraged-FX intervention, which is directly on-point for
leverage+funding+stop-out mechanics even though the underlying differs:
- **ESMA (EU regulator) found 74–89% of retail CFD accounts lose money**, with average losses per
  client of €1,600–€29,000 — the finding that drove the EU's 2018 leverage caps (30:1 major FX down
  to 2:1 crypto) and mandatory "X% of retail accounts lose money" risk warnings
  ([ESMA product-intervention notice](https://www.esma.europa.eu/sites/default/files/library/2018-esma35-43-1397_cfd_renewal_decision_notice_en.pdf)).
- Crypto-market-specific surveys report similarly poor retail outcomes: **~84% of retail crypto
  traders lose money in their first year**, ~58% of new traders lose "almost all" of their starting
  capital in year one ([NFTevening summary of trader-survey data](https://nftevening.com/84-percent-of-retail-crypto-traders-lose-money-in-their-first-year/)).
  These are market-survey, not audited-exchange-disclosure numbers — treat as directionally
  consistent with ESMA's regulated figure, not as independently rigorous.
- The **2026-06-15 CFTC framework** that opened US perps to retail did **not** come with a
  disclosure regime as strict as ESMA's — meaning the practical guardrails that (partially) protect
  EU retail from the worst outcomes are not yet mirrored in the new US-legal venues.

### 2.2 What the academic literature actually supports
- **Time-series momentum (TSMOM)** is a real, replicated anomaly: Moskowitz, Ooi & Pedersen (2012,
  JFE) found a 12-month-lookback TSMOM strategy across 58 liquid futures markets produced an
  annualized **Sharpe ≈1.0 before costs** — the foundational result, not crypto-specific.
- Crypto-specific replications are weaker after realistic frictions: an SSRN paper (Han, Kang, Ryu,
  *"Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market... under Realistic
  Assumptions"*) and related work find **time-series momentum survives cost-adjustment better than
  cross-sectional momentum does** in crypto, but "when appropriately assessed... many momentum
  portfolios are liquidated and many with statistically significant returns earn insignificant
  profits" once transaction costs and daily rebalancing frictions are modeled
  ([SSRN 4675565](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565)). Net: **the edge is
  real but thin and cost-sensitive**, consistent with the general finding (Harvey, Liu & Zhu 2016)
  that most published factor edges shrink hard under realistic implementation costs.
- None of this literature layers **retail leverage + stop-loss/take-profit heuristics + a
  <$1,000 account** on top of the base signal — which is precisely the layer that the retail-loss
  statistics above say is where the expectancy goes negative (forced exits at the worst time,
  liquidation before the signal plays out, funding drag compounding against a levered directional
  book).

### 2.3 What leverage + stop-loss/take-profit does to expectancy — evidence, not folklore
- **Stop-loss rules have a documented *negative* marginal effect on expected return** relative to
  buy-and-hold in the general finance literature: "strong evidence shows stop-loss rules have a
  negative marginal impact on the expected return of a buy-and-hold portfolio strategy... tight
  stop-loss strategies underperform buy-and-hold in a mean-variance framework due to high trading
  costs" ([Acar & Toffel, actuaries.org.uk](https://www.actuaries.org.uk/system/files/documents/pdf/stop-loss-and-investment-returns.pdf)).
  A backtest survey of 64 strategy variants found only **48% had positive expectancy** even with
  stop-loss/take-profit management applied — i.e. the exit rule doesn't reliably rescue a mediocre
  entry signal.
- **This repo's own live-tested finding agrees directionally**: on the maker-box bot,
  `CLAUDE.md` states plainly — *"Stop-loss exits LOSE (tested on 20,318 fills); risk control is
  SIZE/pairing, never exits."* That's a different instrument (binary options, not perps) but the
  mechanism generalizes: an exit rule triggered by adverse short-term price action tends to crystallize
  losses at the point of maximum noise, not signal.
- **Leverage amplifies the same effect and adds a hard floor (liquidation) that a stop-loss doesn't
  even reach in time during fast moves.** The 2025-10-10 crash liquidated **>$19B / 1.6M traders in
  ~24h**, and **~87% of the liquidated positions were longs** — i.e. the crowd's directional bet,
  not a minority mistake, got wiped by a single macro headline (100% China tariff threat)
  ([CoinDesk market spotlight](https://www.coindesk.com/research/market-spotlight-the-19-billion-liquidation-that-shook-crypto);
  [CNBC, 2025-10-22](https://www.cnbc.com/2025/10/22/the-biggest-crypto-wipeout-was-led-not-by-bitcoin-but-much-smaller-tokens-heres-what-happened.html)).
  A retail account running any leverage above ~2–3x on a directional book would very plausibly not
  have survived that day regardless of signal quality.

### 2.4 Verdict detail
**NOT-VIABLE for a small retail account.** The one real, replicated edge (TSMOM) is thin
post-cost even in the academic literature and says nothing about surviving retail-scale leverage;
the retail base rate (70–89% lose money under every disclosure regime that measures it) already
prices in whatever informal edge most participants think they have; and both the general
stop-loss/take-profit literature and this repo's own tested result agree exit-rule overlays don't
fix a marginal edge, they just relocate when the loss gets realized. **Do not build.**

---

## 3. Perp hedge for the maker-box bot's inventory — supporting evidence

### 3.1 The bot's actual inventory delta
Per `PERP_HEDGE.md` (this repo, prior scoping): the box bot's unpaired leg — the residual exposure
when a YES or NO fill isn't matched by its pair before window close — has a payout capped at $1 per
contract, with `--max-net 1` (strict pairing clamp) meaning at most one unpaired contract of the
current deployed size is ever outstanding. The dollar delta of that exposure is small: the prior
backtest's own delta-neutral hedge ratio implied roughly **~$100 of BTC notional** would
appropriately hedge one unpaired contract (h≈100 in the backtest's units), and the realized
unpaired-leg loss scale in practice is sub-dollar to a few dollars per incident.

### 3.2 The minimum tradeable perp size, checked across every reachable US venue
- **Kalshi's own BTCPERP** (already live-tested against our real API keys, per `PERP_HEDGE.md`):
  `contract_size` = 0.01 BTC, fractional trading disabled. At the BTC price when that doc was
  written (~$100K) that was ~$1,000 notional — "10–1000× too large" to hedge a $1 leg.
- **Re-checked today (2026-07-12) at the current BTC price** (spot ≈ **$63,808**, live Crypto.com
  ticker): 0.01 BTC ≈ **$638** notional. Lower BTC price narrows the mismatch somewhat but the
  structural gap remains — $638 of minimum tradeable hedge vs. a ~$100 (backtest-implied) to
  low-single-dollars (realized) actual exposure is still a **6–13× over-hedge** on a single
  unpaired contract.
- **Coinbase's "nano" BTC perpetual future — the smallest retail crypto-perp contract available in
  the US market — is *also* 0.01 BTC** (≈$638 notional today), 0% maker / 0.03% taker fee
  ([Coinbase contract specs, via search aggregation of Coinbase/Tradovate/NinjaTrader contract-spec
  pages](https://help.coinbase.com/en/derivatives/perpetual-style-futures/contract-specifications)).
  This is the load-bearing new finding: **it is not a Kalshi-specific limitation** — the entire
  current landscape of US-regulated, CFTC-cleared crypto perps (Kalshi, Coinbase, and by extension
  Kraken's newly-launched Bitnomial-cleared contracts, whose exact multiplier wasn't published in
  public docs at time of writing but which target the same institutional-scale audience) is sized
  for accounts an order of magnitude larger than a $50–$500 bot.
- **Fees are not the binding constraint.** Coinbase taker fee on one nano-BTC trade ≈ $0.19 (0.03%
  of $638) — trivial next to the $100 notional the hedge is meant to offset. The blocker is pure
  **lot-size granularity**: you cannot buy 1/6th of a nano contract, so the smallest possible hedge
  action already over-hedges by 6-13x, which is exactly the concentrated directional bet the bot's
  own `--max-net 1` clamp exists to prevent (per `PERP_HEDGE.md`'s original conclusion — reconfirmed
  here across venues, not just Kalshi's).

### 3.3 At what scale does this flip
`PERP_HEDGE.md` and `SCALE_GATE.md` (this repo's own pre-registered bankroll-scaling gates) already
converge on an answer: aggregate net-unpaired delta needs to reach roughly the size of one nano
contract (~0.01 BTC, ~$638 today) before a single perp contract is an *appropriately*, not
*over*-sized hedge. `SCALE_GATE.md`'s own capital stages put `--max-net` (and clip size) increases
on a path from 1→2→4+ contracts per leg as bankroll crosses **$100 → $1,000 → beyond**, each gated
on ≥14 days of live positive P&L and zero kill-switch trips — not a fixed timeline. Extrapolating
that stepwise growth, aggregate net-unpaired delta of ~$638 (needing ~6–7 concurrent unpaired
contracts at $1 max payout each, i.e. `--max-net` in the 6–7 range) plausibly arrives somewhere in
the **$1,000–$10,000 bankroll stage**, consistent with `PERP_HEDGE.md`'s own "~$10k+ of capital"
estimate. This is a re-confirmation, not a new number — but it now holds across the full set of
reachable US venues, not just Kalshi's, which forecloses "just use a different, smaller-lot venue"
as a workaround.

### 3.4 Verdict detail
**NOT-VIABLE now (structural lot-size floor common to every venue, not a fee or access problem).
VIABLE-AT-~$10K+ bankroll**, i.e. gated on the box bot's own `SCALE_GATE.md` progression reaching
`--max-net` ≈ 6–7, which is itself gated on ≥14 days of clean live performance at each step. No
new capital or urgency argument changes this — it's mechanically downstream of the box bot's own
already-pre-registered growth path.

---

## 4. Risk detail (liquidation math, funding flips, venue risk)

### 4.1 Liquidation math
Standard isolated-margin formula: `Liquidation price (long) = Entry × (1 − 1/leverage + maintenance
margin rate)`. Worked example at 10x, 5% maintenance margin, BTC entry $63,808: liquidation ≈
$63,808 × (1 − 0.10 + 0.05) = $63,808 × 0.95 ≈ **$60,618** — a **~5% adverse move** wipes the
position. At 20x the cushion narrows to ~5% before maintenance margin even enters; at 40x it's
~2.5% ([liquidation-mechanics summaries, aggregated across BingX/BTCC/KuCoin/Bybit help docs](https://bingx.com/en/learn/article/what-is-liquidation-in-crypto-futures-trading-how-to-calculate-liquidation-price)).
BTC's realized daily volatility is commonly 2–4%, but tail days regularly exceed 10% (the
2025-10-10 event moved BTC to $106,560 intraday amid a market-wide 43% OI contraction). **At 10x+,
a single ordinary-tail day can liquidate; at 2–3x, cushion is 33–50%, survivable through most
single-day moves but not guaranteed through a cascade like October 2025.**

### 4.2 Funding-rate regime flips
SOL funding went net-negative (−0.84% annualized) over this repo's own 94-day screen while every
other tracked asset stayed positive — direct evidence that "funding always favors the short" is
not a safe assumption asset-by-asset, and a held short-perp carry position can start *paying*
funding without warning, eroding the position exactly when it's least actively monitored (see
`CRYPTO_FUNDING.md` §Task 1/3).

### 4.3 Venue risk
The entire "US-legal" perp landscape used in this analysis (Kalshi BTCPERP, Coinbase Financial
Markets, Kraken/Bitnomial) is **less than 13 months old** as of this writing (Coinbase since
2025-07-21, the CFTC framework since 2026-05-29, Kraken since 2026-06-15) — there is no multi-year
track record of these specific US-regulated products surviving a full stress cycle the way, e.g.,
CME's regulated futures have. Treat operational/venue risk as elevated relative to the box bot's
Kalshi counterparty, which this operator has already live-tested.

---

## RECOMMENDATION

**Build nothing perp-related right now.** All three angles fail the same test this project already
applies to everything else: does the edge clear costs with a margin big enough to survive being
wrong about the exact numbers? Carry and directional both fail on rate/expectancy; the hedge fails
on a structural, venue-independent lot-size floor.

**What (if anything) to revisit, and when:**
1. **MM-hedge (highest-value angle, per the operator's own framing) — re-screen only when
   `SCALE_GATE.md`'s own bankroll-growth path pushes `--max-net` past ~6–7** (their own pre-registered
   $1,000–$10,000 capital stages). At that point, re-run this exact §3 calculation with the
   then-current BTC price and then-current bot inventory stats — don't assume the ~$638/6-7x numbers
   here still hold; BTC price and the bot's realized unpaired-rate both move.
2. **Carry — do not build a dedicated sleeve.** If ever revisited, the trigger should be data, not
   time: a confirmed multi-week funding regime running persistently >20% annualized (vs. the
   observed 1.5–4% calm baseline), *and* capital ≥$50-100K to make the $/day meaningful — not before.
3. **Directional — do not build.** No evidence threshold identified here would flip this verdict for
   a sub-five-figure account; the retail base rate and the leverage/liquidation mechanics are
   structural, not a signal-quality problem this bot's edge-detection approach would fix.

**Pre-registered forward bar, if any perp sleeve is ever built** (mirroring this repo's own
discipline in `SCALE_GATE.md`/`promotion_check.py` — freeze the bar *before* the data that will be
judged against it exists):
- **≥14 consecutive forward UTC calendar days** of paired variant-vs-baseline (or vs. a
  cash/no-hedge baseline) data, no cherry-picked start date.
- **Day-clustered t ≥ 3** on the daily mean of variant-minus-baseline net P&L, one observation per
  day (this repo's existing `MIN_DAYS=14` / day-clustered-t bar in `promotion_check.py`, reused
  verbatim rather than inventing a laxer crypto-perp-specific standard).
- **Zero kill-switch-equivalent events** in that window (for perps: zero liquidations, zero
  forced-exit stop-outs) — a single liquidation should reset the clock the same way a loss-limit
  trip resets `SCALE_GATE.md`'s clock today.
- **Costs modeled from realized fills, not assumed bps** — this survey used 12–32 bps round-trip
  estimates and 0–0.03% Coinbase quotes; a real pilot must confirm actual fill quality before
  trusting any of the net numbers above.
- **No size-up within 48h of any adverse event**, and every step gated one variable at a time —
  the same never-rules `SCALE_GATE.md` already applies to the box bot's own scaling.

## Sources
- [ESMA CFD/binary-options product-intervention notice (74–89% retail loss rate)](https://www.esma.europa.eu/sites/default/files/library/2018-esma35-43-1397_cfd_renewal_decision_notice_en.pdf)
- [84% of retail crypto traders lose money in year one — trader-survey summary](https://nftevening.com/84-percent-of-retail-crypto-traders-lose-money-in-their-first-year/)
- [Moskowitz/Ooi/Pedersen TSMOM foundational result — summary](https://quantdecoded.com/en/trend-following-the-case-for-time-series-momentum)
- [Time-series/cross-sectional momentum in crypto under realistic assumptions (SSRN 4675565)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565)
- [Stop-loss rules have negative marginal effect on expected return (Acar & Toffel)](https://www.actuaries.org.uk/system/files/documents/pdf/stop-loss-and-investment-returns.pdf)
- [2025-10-10 $19B liquidation event, 87% long-side — CoinDesk market spotlight](https://www.coindesk.com/research/market-spotlight-the-19-billion-liquidation-that-shook-crypto)
- [2025-10-10 event details — CNBC, 2025-10-22](https://www.cnbc.com/2025/10/22/the-biggest-crypto-wipeout-was-led-not-by-bitcoin-but-much-smaller-tokens-heres-what-happened.html)
- [CFTC clears path for onshore crypto perpetual futures, 2026-05-29 — Katten](https://katten.com/perpetual-futures-come-onshore-the-cftcs-new-regulatory-framework)
- [CFTC approval details — CoinDesk, 2026-05-28](https://www.coindesk.com/policy/2026/05/28/u-s-cftc-opens-crypto-perp-door-with-approval-of-first-regulated-firm)
- [Coinbase US Perpetual-Style Futures launch, 2025-07-21](https://www.coinbase.com/blog/perpetual-futures-have-arrived-in-the-us)
- [Coinbase contract specifications (nano BTC = 0.01 BTC)](https://help.coinbase.com/en/derivatives/perpetual-style-futures/contract-specifications)
- [Kraken US perpetual futures launch, 2026-06-15](https://blog.kraken.com/product/kraken-derivatives/announcing-cftc-regulated-us-perps)
- [Kraken US perps — CoinDesk, 2026-06-15](https://www.coindesk.com/markets/2026/06/15/kraken-debuts-u-s-perpetual-futures-as-crypto-derivatives-move-onshore)
- [BTC funding rate ~70.2% APR snapshot, Jan 2026 — CoinGlass](https://www.coinglass.com/FundingRate/BTC)
- [Liquidation price mechanics and leverage-cushion examples](https://bingx.com/en/learn/article/what-is-liquidation-in-crypto-futures-trading-how-to-calculate-liquidation-price)
- Live BTC/USDT price used for notional recalculation: Crypto.com Exchange ticker, 2026-07-12, spot $63,808.
- This repo, reused directly: `CRYPTO_FUNDING.md` (2026-06-14 funding-carry screen), `PERP_HEDGE.md`
  (Kalshi BTCPERP feasibility scoping), `SCALE_GATE.md` (bankroll/size-up gates), `CLAUDE.md`
  (stop-loss-loses finding), `promotion_check.py` (day-clustered t≥3 / MIN_DAYS=14 bar).
