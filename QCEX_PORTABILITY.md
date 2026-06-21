# QCEX / Polymarket-US PORTABILITY TEST — does the Kalshi longshot-maker edge port to pond #2?

**Date:** 2026-06-21 **Probe:** `qcex_longshot_probe.py` (OFFSHORE Polymarket Gamma+CLOB as proxy)
**Tests:** the validated Kalshi rule — be the maker who **SELLS overpriced YES longshots in p∈[0.05,0.15)**
(`KALSHI_LONGSHOT_OPT.md`: **+5.45¢/contract, event-clustered 95% CI [+3.2¢,+7.7¢]**) — against
Polymarket-US/QCEX as a candidate second small uncontested pond.

## BLUF (brutally honest)

1. **QCEX / Polymarket-US IS live for US retail** (waitlist dropped May 2026; iOS; legal in 40+ states) —
   **BUT its market-data/order API is GATED** (application + sandbox + production credentials via
   `onboarding@polymarket.us` / `docs.polymarket.us`). There is **no open public QCEX CLOB/REST/GraphQL**
   to hit today, and **Polymarket-US is NOT available in Massachusetts** (the user's state, bu.edu/Boston).
   **The user CANNOT deploy a bot on QCEX right now** — both on access (no public maker API) and on
   geography (MA excluded).
2. **The fee tailwind partially eroded.** Makers still pay **zero** fees and get a **20–25% taker-fee
   rebate**, which is *better* than Kalshi — but on **2026-03-30 Polymarket added taker fees to nearly every
   category** (Weather, Tech, Economics, Politics, Crypto, Sports...); only **Geopolitics** is fully free.
   This makes the venue *less* of a free-money soft pond than `MAKER_VENUES.md` assumed.
3. **The bias does NOT port on the offshore proxy.** Pooled over two independent 2-week windows
   (n=59 fills / 48 events in core band), the identical SELL_YES metric gives **−5.51¢/contract,
   event-clustered z=−0.82, 95% CI [−13.2¢, +5.4¢]** — i.e. **wrong-signed central estimate and
   indistinguishable from zero**, NOT the +5.45¢ Kalshi edge. The offshore long-tail is, if anything,
   mildly *under*-priced (sharper base).
4. **The result is unstable** (a few longshot hits flip the sign across adjacent windows), and the **only**
   sub-pocket that replicates the Kalshi overpricing is **sports (+7.28¢, z=1.85)** — which is the
   *weakest* Kalshi category and the most pro-MM-saturated (DraftKings/Novig/ProphetX).
5. **Verdict: QCEX is NOT a viable pond #2 today.** Not deployable (no public maker API + MA-excluded), and
   the portability evidence is null-to-negative on the soft long tail. Realistic **$/month from QCEX = $0**
   until access opens AND a forward measurement on QCEX's *own* settled books shows the bias.

---

## STEP 1 — ACCESS STATUS (with citations)

### Is Polymarket-US / QCEX live for US retail?
**Yes, live but limited.** Polymarket acquired the holding company of **QCX LLC** (CFTC-licensed Designated
Contract Market) + **QC Clearing LLC** clearinghouse (together "QCEX") for **$112M** (closed mid-2025); the
CFTC issued a no-action letter / approval Sept 2025, an **Amended Order of Designation** (Jan–Mar 2026)
enabling **intermediated access via FCMs**, USD custody, and Part-16 reporting. QCX now operates as
**"Polymarket US."** Re-opened in beta **Nov 12 2025**; **waitlist dropped May 2026**, now **open on iOS**
(Android/web pending); intended to list products **no earlier than April 9 2026**. Legal in **40+ states**;
**excluded:** AZ, IL, MA, MD, MI, MT, NJ, NV, OH (MN ban effective Aug 1 2026).
- The **offshore** site `polymarket.com` is **geoblocked for US IPs**; the US site (`polymarketexchange.com`)
  is a **separate, geofenced** platform with full KYC and **USD via FCMs** (not the crypto/USDC rail).

> **Access reality for THIS user:** Boston (MA) is on the exclusion list → **cannot legally trade
> Polymarket-US at all** as of June 2026, independent of the API question.

### Is there a PUBLIC API for QCEX? — **NO (gated).**
The Polymarket-US developer page states **"API access requires an application process"**, **sandbox
integration testing**, and issuance of **production API credentials** by contacting `onboarding@polymarket.us`
(docs at `docs.polymarket.us`). It is for **"participants and technology partners,"** not an open public
retail endpoint. **QCEX does NOT share the public offshore infra** (`gamma-api.polymarket.com` /
`clob.polymarket.com`) for trading — those serve the geoblocked offshore venue. A retail bot maker has **no
documented public CLOB/REST/GraphQL** on QCEX today.

### Fee schedule & maker access (verified — partly contradicts the old MAKER_VENUES.md)
Polymarket's **2026-03-30** fee change (applies to the shared product line; QCEX mirrors Polymarket products):
- **Variance fee formula:** `fee = shares × feeRate × p × (1−p)` (Bernoulli variance; peaks at p=0.5, →0 at
  the extremes — so longshot fees are small but non-zero).
- **feeRate by category:** Crypto 0.072 · Economics/Culture/Weather/Other 0.05 · Finance/Politics/Mentions/
  **Tech 0.04** · **Sports 0.03** · **Geopolitics 0.0 (only free category)**.
- **MAKERS PAY ZERO fees** in every category, **plus a daily USDC maker rebate** = **20% (Crypto) / 25%
  (other) of taker fees collected**. ⇒ On the **maker SELL-YES side the gross = net** (no fee drag), and the
  rebate is *upside vs Kalshi*. The old doc's "fee-free + rebated retail maker" is **confirmed for makers**,
  but its implied "soft/free pond" framing is **weakened**: takers are now charged in almost all categories
  (incl. Weather/Tech, the rich Kalshi cells), which raises spreads and competition for the maker queue.

**Net access reality:** QCEX is a real, regulated, maker-friendly CLOB **on paper**, but (a) no public maker
API, (b) MA-excluded for this user, (c) fee-free-everywhere assumption no longer holds.

---

## STEP 2 — MEASURE THE BIAS (offshore proxy, identical metric, EVENT-clustered)

**Why proxy:** No public QCEX API → measured the long-tail overpricing on the **offshore** public CLOB+Gamma
(`clob.polymarket.com` `/prices-history`, `gamma-api.polymarket.com` `/markets closed=true`), the same
order-book engine and product line QCEX mirrors. **CAVEAT: the offshore base (crypto-native, no KYC) may be
SHARPER/different than the KYC'd, FCM-intermediated, USD-rail QCEX base — treat this as forward-looking, not
deployable.**

**Metric — IDENTICAL to `kalshi_longshot_opt.py`:** SELL_YES, `pnl/contract = pre-settle_price − settle`
(settle=1 if YES resolved), **maker fee = 0** (so net=gross), pre-settlement price = median traded YES price
in a clean window (skip final 12h, mirroring the Kalshi "fill early" finding), binned by the **same bands**,
**significance EVENT-CLUSTERED** on `events[0].id` (the Becker lesson — markets in one event share one
outcome). **Data constraint:** Polymarket **purges CLOB price history ~2 weeks after resolution**, so only
recently-resolved markets are measurable → the retrievable settled sample is **small** (this is itself a
finding about the proxy's limits).

### Band-by-band, POOLED across two independent windows (May 20–Jun 5 + Jun 5–21 2026), deduped

| band (YES price) | n_fills | n_events | avg price | realized YES-rate | SELL_YES ¢/ct | clustered z |
|---|---:|---:|---:|---:|---:|---:|
| **[0.05,0.15) (CORE)** | **59** | **48** | **0.097** | **0.153** | **−5.51¢** | **−0.82** |

**Core-band 95% CI (event-clustered): [−13.2¢, +5.4¢] — straddles zero.**
Realized YES-rate (0.153) **exceeds** the price (0.097) → on the pooled proxy these longshots were if anything
**UNDER-priced**, the *opposite* of Kalshi's overpricing. **The +5.45¢ Kalshi edge does not appear.**

### The instability (why this is null, not a clean negative)
Two adjacent 2-week windows, same metric, **opposite signs** — driven entirely by whether a handful of
longshots happened to hit:

| window | core n_evt | realized YES-rate | SELL_YES ¢/ct | z | sign |
|---|---:|---:|---:|---:|:--|
| May 20 – Jun 5 | 22 | 0.037 | **+6.72¢** | +3.59 | matches Kalshi |
| Jun 5 – Jun 21 | 29 | 0.242 | **−14.94¢** | −1.55 | wrong-signed |

With only ~25 events/window and the long tail's heavy negative skew (one 0.10 longshot that resolves YES =
−90¢), the retrievable offshore sample is **far too small to bank either direction** — the very capacity/skew
problem flagged on Kalshi, worse here because history purges fast.

### Category split, pooled, longshot band [0.02,0.20) (event-clustered)

| bucket | n_fills | n_events | avg price | realized YES | SELL_YES ¢/ct | z |
|---|---:|---:|---:|---:|---:|---:|
| **sports** | 24 | 24 | 0.114 | **0.042** | **+7.28¢** | +1.85 |
| non-sports | 92 | 64 | 0.103 | 0.163 | **−5.97¢** | −1.59 |

**The ONLY pocket that replicates the Kalshi overpricing is sports** — which is the **weakest** Kalshi
category (`KALSHI_MAKER_RANK.md`) and the **most pro-MM-saturated** offshore/onshore venue (DraftKings DKeX,
Novig, ProphetX). The **non-sports** soft long tail (the categories where Kalshi's edge actually lives:
Entertainment/Sci-Tech/Climate/Econ) is **mildly under-priced** here — consistent with a **sharper offshore
base**. So even taken at face value, the proxy says: *the part that ports is the part we don't want; the part
we want doesn't port.*

---

## STEP 3 — VERDICT: does the edge port?

| dimension | Kalshi (validated) | Polymarket-US/QCEX (this test) |
|---|---|---|
| Core-band SELL_YES net | **+5.45¢/ct**, CI [+3.2,+7.7] | **−5.51¢/ct (proxy)**, CI [−13.2,+5.4] — **null/wrong-signed** |
| Sign stability | replicates across 4 cats + held-out fold | **flips sign** across adjacent 2-wk windows |
| Where it shows up | Entertainment/Sci-Tech/Climate (soft) | **only sports** (weakest cat, MM-saturated) |
| Maker fee | 0 on `quadratic` soft | **0 + 20–25% rebate** (BETTER) — but takers now charged in most cats |
| Capacity ($/mo) | $30–150, flow-capped | **untestable** — offshore history purges; QCEX books unmeasurable (no API) |
| US-retail access | full (ACH/USD) | **NOT for this user**: MA-excluded **and** no public maker API |
| Deployable today? | YES | **NO** |

**Does it port? — On the available evidence, NO.** The fee/rebate structure is genuinely *better* than Kalshi
(makers free + rebated), so **IF the overpricing existed the net edge would beat Kalshi's** — but the
overpricing **isn't there** on the offshore proxy for the soft (non-sports) long tail. The central estimate
is wrong-signed and the CI includes zero; the only positive pocket (sports) is the category we explicitly
avoid. The most likely true state: **the Polymarket base is sharper on the soft long tail than Kalshi's**, so
the favorite-longshot overpricing that Kalshi rec-flow creates is smaller/absent/locally inverted here.

**Capacity / $ per month:** **$0 deployable.** Even setting the bias aside, (a) there is no public QCEX maker
API to rest passive longshot NO-bids programmatically, and (b) the offshore proxy's settled-history purge
means we cannot even *size* the long-tail liquidity historically. Forward, IF QCEX opens a public maker API
AND a measurement on *its own* settled books shows the bias, the structure (maker-free + rebate, retail-seeded
CLOB) would put it in the *same small, flow-capped class* as Kalshi (~$30–150/mo) — **a second pond of the
same size, not a scale unlock** — but that is conditional and currently unsupported by data.

**Is QCEX pond #2? — NO, not now.** It fails on **access** (no public maker API; MA-excluded), fails the
**portability measurement** (null/wrong-signed on the soft tail; only sports ports, and sports is out), and
the **fee-free-pond premise is partly gone** (takers now charged in nearly all categories). It remains the
**structurally closest twin** and the **only** venue worth re-testing later — but as a **forward option,
conditional on (1) a public QCEX maker API, (2) the user being in a permitted state, and (3) a fresh
measurement on QCEX's OWN settled soft books** — not a deployable pond today. The $500/mo multi-pond target
gets **no contribution from QCEX** at present.

### Honest caveats on the proxy
- **Small n** (core 59 fills / 48 events pooled): underpowered; CIs wide; one window flips sign.
- **Offshore ≠ QCEX base:** QCEX is KYC'd/FCM/USD — plausibly sharper *or* (if it draws fresh US rec money)
  softer; unknown until measurable. This is a **directional caution, not a quantified QCEX result**.
- **History purge** biases the sample toward very recent, sports/Fed-heavy resolutions (June 2026 World Cup +
  Fed-decision dominated) — not the Entertainment/Sci-Tech mix where Kalshi's edge is richest. The soft-cat
  comparison is therefore *suggestive*, and the cleanest statement is: **no evidence the edge ports; some
  evidence the soft tail is sharper here.**

---

## Sources (URLs)
- CFTC approval / QCEX acquisition: https://www.coindesk.com/policy/2025/09/03/u-s-cftc-gives-go-ahead-for-polymarkets-new-exchange-qcx ·
  https://www.prnewswire.com/news-releases/polymarket-acquires-cftc-licensed-exchange-and-clearinghouse-qcex-for-112-million-302509626.html
- Amended Order / intermediated FCM access: https://www.prnewswire.com/news-releases/polymarket-receives-cftc-approval-of-amended-order-of-designation-enabling-intermediated-us-market-access-302625833.html ·
  https://www.cftc.gov/media/12806/Polymarket%20US%20Amended%20Order%20of%20Designation/download · CFTC DCM filing: https://www.cftc.gov/IndustryOversight/IndustryFilings/TradingOrganizations/49571
- Polymarket-US exchange site / rulebook / developer onboarding: https://www.polymarketexchange.com/ ·
  https://polymarketexchange.com/files/legal/Polymarket%20US%20Rulebook%20(2026.04.21).pdf ·
  Liquidity Provider Program: https://www.polymarketexchange.com/files/notices/Liquidity%20Provider%20Program%20(2026.03.03).pdf
- Live status / state availability (June 2026): https://startpolymarket.com/countries/united-states/ ·
  https://oddsassist.com/prediction-markets/polymarket-us-states/ · https://en.wikipedia.org/wiki/Polymarket
- Fee schedule (Mar 2026 variance fees, maker=0 + rebate): https://medium.com/coinmonks/polymarket-just-changed-its-fees-heres-what-bot-traders-need-to-know-c11132e55d5c ·
  CLOB/maker docs: https://docs.polymarket.com/developers/CLOB/introduction · https://docs.polymarket.com/market-makers/overview ·
  https://help.polymarket.com/en/articles/13364466-liquidity-rewards
- Proxy data APIs used by the probe: https://gamma-api.polymarket.com (`/markets`) · https://clob.polymarket.com (`/prices-history`, `/book`)
```
```
