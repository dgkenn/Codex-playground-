# Other longshot-MAKER venues + the Kalshi new-listing timing angle — VERDICT (2026-06-21)

**Scope.** Two questions, one brutal bar:
1. Are there OTHER US-retail event/prediction venues where the validated structure holds — a *patient retail
   MAKER* is the structural liquidity provider harvesting *recreational longshot* flow on a *thin, uncontested,
   cleanly-settling, legally-accessible* book? (The Kalshi edge: sell overpriced YES longshots p∈[0.05,0.15) on
   zero-maker-fee soft series; +~5¢/contract net, capacity-capped ~$30–150/mo — `KALSHI_MAKER_VERDICT.md`,
   `KALSHI_LONGSHOT_OPT.md`.)
2. Is the maker/longshot premium **RICHEST in the first hours of a newly-listed Kalshi soft market** (before
   recreational flow and any competing maker arrive)?

**Bottom line up front.**
- **No new venue clears the bar as an *additional, distinct* longshot-maker pond.** The 2026 prediction-market
  build-out (ForecastEx, Rothera, Polymarket-US/QCEX, DKeX/Railbird, Novig, ProphetX) is real and CFTC-regulated,
  but every one fails the structure on at least one binding axis: it is **macro/efficiently-priced** (ForecastEx,
  CME), **pro-market-maker-seeded by design** (Rothera=Susquehanna, DKeX/FanDuel=Flutter, Novig/ProphetX=third-
  party MMs — they *engineered* a pro LP into the order book, which is exactly the "uncontested" axis the Kalshi
  edge depends on *not* having), **sports-only** (Novig, ProphetX, DKeX — the weakest-bias category per
  `KALSHI_MAKER_RANK.md`), or **winding-down / fee-killed / capped** (PredictIt). **Polymarket-US** is the closest
  structural twin (CLOB, fee-free maker limit orders, maker-rebate program, retail-seeded liquidity) and is the
  *only* genuine "run the same playbook on a second pond" candidate — but on a different (crypto-wallet/USDC)
  rail, and its long-tail soft books are an untested open item, not a validated edge.
- **The new-listing timing angle is HALF-right but not separately tradable.** Measured on Kalshi's public API
  (`kalshi_newlisting_edge.py`), the *per-contract* longshot premium IS modestly richer in the first hours
  (first <6h **+7.9¢/ct** vs ≥6h +3.3¢/ct, a +4.6¢ lift) — but **only ~0.9% of harvestable flow trades in the
  first 2h and ~1.8% in the first 6h**, so there is essentially nothing to fill: the richest-per-contract window
  and the fillable window do not coincide. On the *spread* side, a newly-listed soft market is **not a
  wide-spread opportunity** — it is either an EMPTY book (thin series: no recreational taker yet to lift your
  quote) or an ALREADY-TIGHT book (active series: a competing maker / Kalshi's LP program is resting at a 1–2¢
  touch within ~2h of open). So "be the *first* maker on a fresh listing" is not a separable edge. The real,
  deployable timing tilt is the one the project already had — **fill early *in market life* (first day or two,
  ≥50% life remaining)** (`KALSHI_LONGSHOT_OPT.md`, +1.3¢): it both raises per-contract edge and dodges toxic
  settlement-loaded flow, and (unlike "first hours") it is where ~34% of flow by 24h actually lives.

---

## 1. The venue table (structure-fit scoring)

Each venue scored 1–5 (5 = matches the winning Kalshi structure) on the five load-bearing axes:

- **REC** = recreational counterparty flow (uninformed longshot lottery buyers to sell to)
- **UNC** = uncontested book (NO designated/pro market maker seeded into the LP role)
- **MAKE** = retail MAKER access (you can rest a passive limit order and be a liquidity provider, ideally fee-free)
- **ACC** = accessible & legal to a US retail trader, clean rail
- **SETL** = clean, mechanical settlement (binary, objective)

| Venue (2026) | Distinct pond? | REC | UNC | MAKE | ACC | SETL | Cap/notes | Fit |
|---|---|--|--|--|--|--|---|--|
| **Kalshi soft series** (baseline) | yes | 4 | 4 | 5 | 5 | 5 | the validated edge; ~$30–150/mo | **REF** |
| **Polymarket-US (QCEX/QCX)** | **yes** (USDC rail) | 4 | 3 | **5** | 3 | 5 | CLOB, fee-free maker, maker-rebate 20–25%; soft long-tail UNTESTED | **3.5** |
| **ForecastEx (IBKR)** | yes | **1** | 3 | 4 | 4 | 5 | macro-only (Fed/CPI/GDP/climate), efficient; +~3.1–3.8% coupon; $0.01 embedded fee | **2.0** |
| **Rothera (Robinhood×Susquehanna)** | yes | 4 | **1** | 3 | 4 | 5 | **Susquehanna seeds liquidity by design**; sports/macro; fees ≤1¢ | **2.0** |
| **CME / Cboe / Schwab event** | yes | 2 | 1 | 2 | 3 | 5 | exchange-MM ecosystem; macro/crypto/S&P binaries | **1.8** |
| **DKeX / Railbird (DraftKings)** | yes | 4 | **1** | 4 | 4 | 5 | sports-only; maker fee $0.0025; **MM program seeded** | **2.2** |
| **FanDuel Predicts (×CME)** | no (CME-routed) | 4 | 1 | 2 | 4 | 5 | **Flutter acts as MM**; sports | **1.6** |
| **Novig** | yes | 4 | 2 | **4** | 3 | 5 | **sports-only**; P2P, "pays you to post"; Novig MMs thin books 1–4%; ex-sweepstakes→CFTC | **2.6** |
| **ProphetX** | yes | 4 | 2 | 4 | 3 | 5 | **sports-only**; P2P, third-party MMs, RFQ parlays; launched 6/18/26 | **2.4** |
| **PredictIt** | yes | 4 | 4 | 4 | 3 | 4 | **DEAD for this: 10%+5% fees, $850 cap, can't list new mkts at full capacity, legal limbo** | **1.5** |

**Reading the table.** The two attractive axes (REC + MAKE) are common — the 2026 venues all court recreational
flow and most pay makers. The structure breaks on **UNC** and category:
- Every *new* well-capitalized venue **engineered a professional market maker into the book** (Susquehanna→Rothera,
  Flutter→FanDuel, third-party MMs→Novig/ProphetX/DKeX). That is the opposite of the Kalshi soft-series condition
  the edge exploits: **the harvest works on Kalshi precisely because the soft long tail is too thin for a pro MM
  to bother seeding.** A venue that *guarantees* a pro LP at the touch has already taken the spread you wanted.
- The sports-native venues (Novig, ProphetX, DKeX, FanDuel) are **sports-only** — the weakest favorite-longshot
  bias and lowest softness in the project's own ranking (`KALSHI_MAKER_RANK.md`: Sports |bias| 8.0pp, bottom of
  the list), with the most informed/sharp counterparty flow. Wrong category even before the pro-MM problem.
- **ForecastEx / CME** are macro/efficiently-priced (this independently re-confirms `NICHE_SCAN.md`'s
  "ForecastEx = a cheap *expression* venue, not an edge"). The ~3.1–3.8% IBKR incentive coupon is a real carry
  perk for *holding* collateral, but it is a risk-free-rate pass-through, not a longshot-maker alpha.

---

## 2. The ONE real candidate: Polymarket-US (QCEX) — qualified, not validated

Polymarket reopened to US retail in beta (Nov 2025) on its CFTC-licensed **QCX/QCEX** exchange+clearinghouse
($112M acquisition). Structurally it is the closest twin to the Kalshi edge:

- **Central limit order book**, retail can rest passive limit orders, **maker limit orders are fee-free**, plus a
  **Liquidity Rewards / Maker Rebates program (20–25% of taker fees)** — i.e. they *pay* you to be the maker. This
  is the same "patient retail maker = structural LP" role, with a *better* incentive than Kalshi (rebate on top of
  spread).
- Liquidity is **retail/maker-seeded, not a single designated MM** (UNC=3, better than the pro-seeded venues; but
  Polymarket's headline markets attract sophisticated/whale flow, so it is more contested than Kalshi's sleepy soft
  long tail — hence 3, not 4).

**Why it is only a *qualified* candidate, not a validated edge:**
- **The long-tail soft-market longshot bias on Polymarket is UNTESTED here.** The Kalshi edge is a *measured*
  +5¢/contract on settled soft binaries. Polymarket's structure permits the same play, but whether its
  recreational longshots are *overpriced to the same degree* (vs. its more crypto-native, arguably sharper user
  base) is an open empirical question — it must be measured on QCEX settled markets before any capital, exactly as
  the Kalshi edge was.
- **Different rail / access friction (ACC=3):** US relaunch is beta/geofenced rollout; USDC-on-chain
  collateralization vs. Kalshi's USD ACH — operationally a separate integration, KYC, and tax surface.
- **Same capacity ceiling logic applies:** the bias is biggest where books are thinnest, so even if it replicates,
  it is another small, flow-capped sleeve — a *second pond of the same size class*, not a scale unlock.

**Verdict on Polymarket-US:** the only "run the validated playbook on a second venue" worth a measurement pass.
Not a new edge — a *portability test* of the existing one. Recommend: collect QCEX settled soft-market trades, run
the identical SELL_YES p∈[0.05,0.15) realized-P&L-to-settlement metric, event-clustered, before deploying a cent.

---

## 3. The Kalshi new-listing timing angle — TESTED: half-right per-contract, not separately tradable

**Hypothesis:** the maker/longshot premium is richest in the first *hours* of a newly-listed soft market — wider
spreads, mispriced initial quotes, no competing maker yet.

**Script:** `kalshi_newlisting_edge.py` (Kalshi public API, no auth, 0.4s rate-limit). Two tests:
(A) cross-sectional **book-state & touch spread by absolute age** on currently-open soft markets (via the
`/markets/{ticker}/orderbook` endpoint — note the bulk `/markets?status=open` list returns `yes_bid/yes_ask/volume`
as `null`, so the orderbook endpoint is required); (B) historical **realized SELL_YES harvest P&L bucketed by
hours-since-open** on settled soft markets (same metric as the validated edge, event-clustered z).

### (A) Book-state by age — the decisive structural finding

Snapshot of 294 open soft markets (273 in the zero-maker-fee `quadratic` universe), book state by age:

| age | n | empty% | 1-sided% | 2-sided% | median spread (2-sided) |
|---|--:|--:|--:|--:|--:|
| 0–2h | 18 | 0% | 11% | **89%** | **1.00c** |
| 6–24h | 7 | 0% | 0% | 100% | 8.00c |
| 1–3d | 18 | 0% | 44% | 56% | 1.00c |
| 3–7d | 9 | 0% | 0% | 100% | 89.00c |
| >7d | 221 | 0% | 29% | 71% | 5.00c |

Spread in the longshot mid region (mid ∈ [0.03,0.20)), two-sided books only:

| age | n | median spread | mean spread |
|---|--:|--:|--:|
| **0–2h** | 5 | **2.00c** | 2.80c |
| 6–24h | 2 | 8.00c | 8.00c |
| 1–3d | 4 | 1.00c | 1.25c |
| 3–7d | 2 | 16.00c | 9.00c |
| **>7d** | 56 | **5.00c** | 5.43c |

**The first-hours book is NOT wider — it is already populated and tight.** In the 0–2h bucket, 89% of markets
already have a two-sided book at a **1.0c median touch** (and a 2.0c median spread in the longshot region) — a
competing maker is *already* resting at the touch within two hours of listing. The longshot-region spread at 0–2h
(2.0c) is *tighter* than the mature >7d cohort (5.0c), the exact opposite of the hypothesis. (Caveat: per-bucket
n is small and this 25-series/category snapshot survivorship-tilts toward the more-active series; the
complementary failure mode — thin series whose books are *empty* for hours/days — is shown by the probes below.
Both modes kill the hypothesis.)

**Qualitative probes that frame the table:**
- A Climate market (`KXLOWTDEN-26JUN22`) that opened ~2h before probe had a **completely empty order book** — no
  YES bids, no NO bids, zero volume, zero open interest. Repeated across a 60+ market sample of thin soft series:
  the first hours of a thinly-followed soft listing are **empty, not wide.**
- Conversely, an *active* soft series (`KXHIGHNY`, NYC high-temp) had **two-sided 1–3¢ touches at longshot prices
  within 2h of open** — a competing maker (Kalshi's own LP program / a bot) is already resting at the touch. There
  is **no fat new-listing spread to capture** there either.

**Interpretation.** The two states a new soft listing can be in are both bad for the hypothesis:
1. **Empty book** (thin series) → there is literally no recreational *taker* present to lift your resting longshot
   offer. A wide nominal spread with no flow is a *phantom* premium: you can rest a quote, but nothing fills. The
   harvest needs a counterparty, and the recreational flow has not arrived.
2. **Already-tight book** (active series) → a competing maker has already collapsed the touch to 1–3¢ within
   hours. No first-mover spread advantage; you join a queue at a thin edge.

### (B) Realized harvest P&L by hours-since-open — confirmatory

Settled zero-fee soft markets (Climate/Econ/SciTech/Entertainment), 6,488 SELL_YES fills in p∈[0.05,0.15),
realized maker P&L to settlement, bucketed by **absolute hours since `open_time`**, event-clustered z:

| age at fill | n_fills | n_events | contracts | VW net P&L/ct | clustered z |
|---|--:|--:|--:|--:|--:|
| 0–2h | 69 | 9 | 2,080 | **+7.30c** | +15.8 |
| 2–6h | 73 | 10 | 2,085 | **+8.52c** | +20.1 |
| 6–24h | 1,689 | 15 | 73,744 | +8.26c | +4.3 |
| 1–3d | 3,912 | 12 | 121,172 | +6.97c | +5.1 |
| 3–7d | 56 | 2 | 2,024 | +9.68c | +12.6 |
| >7d | 689 | 5 | 27,021 | −26.81c | −1.4 (n=5, a longshot hit — noise) |

Contrast: **first <6h = +7.91c/ct (z=18.0, but only 12 events / 4,165 contracts)** vs **≥6h = +3.34c/ct
(z=0.6, 223,961 contracts)** → a +4.57c per-contract lift early. **BUT flow share: <2h = 0.9%, <6h = 1.8%,
<24h = 34.2% of all harvestable contracts.**

**Interpretation — the honest, nuanced read (this is where the hypothesis is *half* right):**
- **Per contract, the early fills ARE richer:** first <6h = +7.91c/ct vs ≥6h = +3.34c/ct (+4.57c lift). The
  longshots that *do* trade in the first hours settle in the maker's favor at least as often as later ones — the
  hypothesis's premise ("mispriced initial quotes, no competing maker collapsing it yet") has *some* support in
  the per-contract number.
- **But the capacity in that window is essentially zero:** only **0.9% of harvestable contracts trade in the
  first 2h, 1.8% in the first 6h.** The first-6h cells are 9–12 events / ~4k contracts — too thin to bank and
  *far* too thin to matter to a $/month figure. The fillable flow lives at **6–24h (34% cumulative) and 1–3d**,
  which is *also* richly positive (+7–8c) — so the realistic harvest is "early in life" (first day or two), NOT
  "first hours." The richest *per-contract* corner and the *fillable* corner do not coincide.
- The >7d −26.81c cell is 5 events with a longshot that hit — small-sample noise, not a real late-life sign flip.

**Net of (A) and (B): "be the FIRST maker on a fresh listing" is not a real, separable edge.** The first hours
carry a slightly richer per-contract longshot premium but ~0% of the capturable flow, and on populated books a
competing maker is already at a 1–2c touch within 2h (test A). The deployable timing statement is the one the
project already had — **fill early *in market life* (first day or two, ≥50% life remaining), which both raises the
per-contract edge and dodges toxic settlement-loaded flow** — and it is a quality/variance tilt, *not* a capacity
unlock and *not* a fresh-listing land-grab.

### Reconciling with the existing "early-life lift"

`KALSHI_LONGSHOT_OPT.md` found a **+1.3¢ lift for filling when ≥50% of market *life* remains**. That is NOT the
new-listing hypothesis and does not support it:
- "≥50% of life remaining" is a **fraction-of-total-life** filter — for a 2-week market that is the first 7 *days*,
  not the first *hours*. Its mechanism is **avoiding toxic end-of-life informed flow** (the settlement-loaded,
  adverse 55–65% of volume), not capturing a fat fresh-listing quote.
- The new-listing (first-*hours*) window is, if anything, *worse*: it has the *least* flow (so the lowest fill
  rate / capacity) and, where flow exists, an already-competing maker. The clean fills are early *relative to
  settlement*, but spread across the whole pre-settlement life — not concentrated in hour 1.

**There is no "be the first maker on a new soft listing" edge.** Being first buys you an empty book, not a premium.

---

## 4. RANKED VERDICT — additional opportunities, honest

1. **Polymarket-US (QCEX)** — *qualified candidate, measure before trusting.* The only venue whose structure
   genuinely matches (CLOB, fee-free + rebated retail maker, retail-seeded liquidity). It is a **portability test
   of the existing Kalshi edge onto a second pond**, not a new edge. Long-tail soft-longshot overpricing is
   unmeasured and the user base is plausibly sharper; access is beta/geofenced on a USDC rail. Worth one
   measurement pass with the identical metric; same ~small, flow-capped capacity class if it replicates.
2. **Novig / ProphetX** — *watch, structurally wrong category.* P2P, maker-paid, no house — the most Kalshi-like
   *mechanics* of the new sports venues — but **sports-only** (weakest bias, sharpest flow) and seeded with
   third-party MMs. Re-examine only if either lists non-sports soft contracts; then run the Pinnacle-CLV / bias
   test first (per `NICHE_SCAN.md`'s watch-item).
3. **ForecastEx (IBKR)** — *not an edge; a cheap macro expression venue + a risk-free coupon.* Efficiently-priced
   macro, no recreational longshot tail. The ~3.1–3.8% incentive coupon is a real carry on held collateral but is
   rate pass-through, not maker alpha. Re-confirms `NICHE_SCAN.md`.
4. **Rothera / DKeX / FanDuel / CME / Cboe-Schwab** — *Kalshi-rebranded for this purpose or pro-MM-contested.*
   Every one engineered a professional market maker (Susquehanna / Flutter / exchange MMs) into the book by
   design, which removes the *uncontested* condition the harvest depends on. FanDuel routes to CME (not even a
   distinct pond). Sports-heavy. **No retail longshot-maker edge.**
5. **PredictIt** — *DEAD for this purpose.* 10% profit + 5% withdrawal fees, $850/market cap, cannot list new
   markets at full capacity, ongoing legal limbo. Retail-ideal structure, friction-killed (re-confirms
   `NICHE_SCAN.md`).

**New-listing timing angle:** **half-right, not separately tradable.** The per-contract longshot premium is
modestly richer in the first hours (+7.9¢ <6h vs +3.3¢ ≥6h), but only ~1.8% of harvestable flow trades there, and
on populated books a competing maker is already at a 1–2¢ touch within 2h. The richest-per-contract window and the
fillable window don't coincide. The deployable timing tilt is the previously-documented early-*in-life* (≥50%
life-remaining, first day or two — where ~34% of flow lives by 24h) anti-toxicity filter, **not** a fresh-listing
land-grab.

**Net:** the validated longshot-maker harvest remains a **single-pond (Kalshi soft series), ~$30–150/mo,
flow-capped** edge. The only honest expansion is to **measure whether it ports to Polymarket-US/QCEX**; everything
else in the 2026 venue boom is macro-efficient, sports-only, pro-MM-seeded, or winding down.

---

## Sources
- ForecastEx / IBKR: https://www.interactivebrokers.com/campus/trading-lessons/trading-forecast-ex-event-contracts/ ·
  https://marketmath.io/platforms/forecastex · https://www.financemagnates.com/forex/interactive-brokers-bundles-kalshi-cme-forecastex-in-unified-event-trading-push/ ·
  incentive coupon ~3.1–3.8% APY: https://forecasttrader.interactivebrokers.com/en/home.php
- Robinhood / Rothera (Susquehanna): https://cryptobriefing.com/robinhood-world-cup-rothera-prediction-markets/ ·
  https://www.casino.org/news/robinhood-moving-some-world-cup-trading-to-its-own-prediction-market-away-from-kalshi/ ·
  https://finance.yahoo.com/markets/options/articles/robinhoods-prediction-market-push-why-130400265.html
- CME / Cboe / Schwab event contracts: https://www.cmegroup.com/markets/prediction-markets.html ·
  https://bitcoinworld.co.in/charles-schwab-sp500-event-options/
- Polymarket-US / QCEX: https://www.prnewswire.com/news-releases/polymarket-acquires-cftc-licensed-exchange-and-clearinghouse-qcex-for-112-million-302509626.html ·
  https://www.coindesk.com/policy/2025/09/03/u-s-cftc-gives-go-ahead-for-polymarket-s-new-exchange-qcx ·
  maker/CLOB/rewards: https://docs.polymarket.com/market-makers/overview · https://help.polymarket.com/en/articles/13364466-liquidity-rewards
- DKeX / Railbird (DraftKings): https://www.financemagnates.com/fintech/draftkings-moves-deeper-into-prediction-markets-with-dkex-cftc-filings/ ·
  https://www.flushdraw.net/news/draftkings-files-six-cftc-contracts-for-dkex-its-in-house-prediction-market-exchange-goes-live-today/
- Novig (CFTC DCM, P2P, pays makers): https://www.cnbc.com/2026/06/16/novig-wins-cftc-approval-as-competition-intensifies-in-sports-prediction-markets.html ·
  https://www.legalsportsreport.com/prediction-markets/novig-promo-code/
- ProphetX (CFTC DCM/DCO, sports-only, third-party MMs): https://www.covers.com/industry/prophetx-launches-prediction-markets-in-us-one-week-after-cftc-approval-june-18-2026 ·
  https://www.sportico.com/business/sports-betting/2026/prophetx-prediction-market-affiliated-trading-arms-1234909865/
- PredictIt (fees/cap/status): https://predscope.com/guide/predictit · https://tech-insider.org/prediction-markets/platforms/predictit-review/
- Kalshi public API (book-state/spread/harvest by age): https://api.elections.kalshi.com/trade-api/v2 (`/markets`,
  `/markets/{ticker}/orderbook`, `/markets/trades`) — this repo's `kalshi_newlisting_edge.py`
