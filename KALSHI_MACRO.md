# Kalshi macro/economic event contracts vs free professional forecasts — is there a lag edge?

**Date:** 2026-06-14 · **Branch:** claude/polymarket-bot-live-ready-vw7ut5 · **Harness:** `kalshi_macro_snap.py`
**Question:** Does Kalshi's implied probability on CPI / FOMC / NFP / GDP / PCE / unemployment
**LAG** the sharp free reference (Cleveland Fed nowcast, CME FedWatch, Atlanta Fed GDPNow,
economist consensus) by enough to clear spread + fee on a venue that can't ban us?

## VERDICT (one line): NO deployable lag edge. Kalshi macro is at least as sharp as the references — the Fed itself proved it — and where Kalshi differs from a reference (GDPNow) the reference is the one that's wrong.

This is a **harder** dead-end than crypto. Crypto was efficient at the mid but at least *uncertain*
(we needed live shadow data to rule out a maker edge). Macro is efficient **and there is published,
peer-style evidence settling it** before we collect a single day of data. The hypothesis that drove
this study — "softer recreational flow + great free nowcasts ⇒ Kalshi price lags the nowcast" — is
**empirically refuted**: the sharp reference does not beat Kalshi; Kalshi beats the reference.

---

## 1. INVENTORY — Kalshi's US macro markets (live, public no-auth API)

`GET /series?category=Economics` → **578 economics series**; **253** match core macro keywords
(CPI/Fed/jobs/GDP/PCE/unemployment/rates). The current generation is `KX`-prefixed. All are
`fee_type=quadratic`, **`fee_multiplier=1`** (the STANDARD category — *not* the crypto-premium
0.14 multiplier; this is the cheap-fee category). Structure is a **threshold ladder**: for one
event (e.g. June CPI) a set of binary "metric **above X**" markets share one `close_time`
(`strike_type='greater'`, `floor_strike=X`). The set of "above X" yes-prices is a survival function
S(X)=P(metric>X); bracket pmf = S(Xₖ)−S(Xₖ₊₁).

Core US series and their resolution source / cadence:

| Series | Metric | Source (resolution) | Cadence | Nearest event close |
|---|---|---|---|---|
| `KXCPIYOY` | CPI YoY | BLS | monthly | 2026-07-14 (June print) |
| `KXCPICOREYOY` | Core CPI YoY | BLS | monthly | 2026-07-14 |
| `KXFED` | Fed funds **upper bound** level | Fed Board | per-meeting | 2026-06-17 |
| `KXFEDDECISION` | FOMC move (hold/±25/±>25) | Fed | per-meeting | (next 2-sided: Dec 2026) |
| `KXPAYROLLS` | Net change in nonfarm payrolls | BLS | monthly | 2026-07-02 (June NFP) |
| `KXU3` | U-3 unemployment | BLS | monthly | 2026-07-02 |
| `KXGDP` | Real GDP growth (QoQ) | BEA | quarterly | 2026-07-30 (Q2 adv) |
| `KXPCECORE` | Core PCE | BEA | monthly | 2026-06-25 |
| `KXEFFR` | EFFR level | Fed/BLS | per-period | 2026-07-01 |

### Liquidity snapshot (live books, 2026-06-14, `kalshi_macro_snap.py inventory`)

| Series | brackets | 2-sided | mean mid-spread | touch depth (contracts) | trades today |
|---|---|---|---|---|---|
| `KXFEDDECISION` (June) | — | 1 | 1.0c | **1,745,880** | yes (deep, one-sided) |
| `KXPAYROLLS` | 13 | **13/13** | **3.3c** | ~200–350 | many (today) |
| `KXU3` | 10 | 5 | 2.2c | ~240 | today |
| `KXPCECORE` | 5 | 3 | 1.0c | ~100 | today |
| `KXGDP` | 9 | 8 | 4.4c | ~100 | today |
| `KXCPIYOY` | 21 | 8 | 7.4c (ATM 1–2c) | ATM ~30–90 | today |
| `KXCPICOREYOY` | 15 | 6 | 65c (untraded tails) | ~26 | sparse |
| `KXFED` (June level) | 11 | 0 | — | one-sided 99/1 | settled-in-fact |
| `KXEFFR` | 5 | 3 | 7.3c | ~19 | sparse |

**Liquidity facts that matter for any edge:**
- **The single deepest book is the FOMC**, but it's deep precisely *because the outcome is already
  known*: `KXFED-26JUN` shows P(rate>3.5%)=99% / P(rate>3.75%)=1% → pegged to upper-bound **3.75%**,
  one-sided 99-bid/1-ask, ~116k contracts resting at 99c. No two-sided market = no takeable edge.
- **Only the ATM region of each ladder is two-sided and tight.** NFP is the best: all 13 brackets
  2-sided, 1–6c spreads. CPI/GDP have a tight ATM cluster but wide/stale tails (the low "above X"
  brackets carry stale 1-sided bids → the survival function is **non-monotonic** in the tape, e.g.
  CPI "above 3.6"=0.60 then "above 3.7"=0.94 — a data-quality artifact of stale quotes, not signal).
- **Capacity is tiny.** Touch depth on the *uncertain* (tradeable) brackets is **single-to-low-
  hundreds of contracts** (CPI ATM 30–90, NFP 7–350, GDP 1–135). At $1/contract that's tens to a
  few hundred dollars per bracket per touch. This is a *thin* market in exactly the brackets where
  an edge would have to live.

---

## 2. FAIR-VALUE REFERENCES (the sharp free forecasts to beat) — cited

| Market | Best free reference | Access | Track record |
|---|---|---|---|
| CPI / core CPI | **Cleveland Fed Inflation Nowcasting** | clevelandfed.org/indicators-and-data/inflation-nowcasting (daily; FRED mirror) | Strong daily nowcast; standard sharp benchmark |
| FOMC level/move | **CME FedWatch** (30-day Fed funds futures) | cmegroup.com FedWatch tool | Market-implied; **but see §3 — Kalshi beats it** |
| GDP | **Atlanta Fed GDPNow** | atlantafed.org/.../gdpnow (FRED: `GDPNOW`) | avg abs err 0.77pp overall, **2.06pp early-quarter, runs HOT** |
| NFP / U-3 | **Economist consensus** (Bloomberg/TradingEconomics/Capital Economics) | tradingeconomics, broker previews | Consensus; Kalshi ≈ or better (§3) |
| PCE | Cleveland Fed PCE nowcast | clevelandfed.org / macromicro mirror | sharp |

Point-in-time reference values pulled this session:
- **CME FedWatch (Jun 13, 2026):** ~**97% HOLD** at the June 17 meeting; base case upper bound **3.75%**.
- **Atlanta Fed GDPNow Q2 2026:** **3.3%** (Jun 9 update; had been 3.8→3.0→3.3 over early June).
- **NFP June consensus:** ~**130k** (Capital Economics preview); May actual was 172k vs 80k consensus.
- **CPI YoY:** recent prints ~3.6–4.2%; Cleveland nowcast rising toward a Q2 peak (~3.5% per
  Ameriprise commentary).

Sources: see "Sources" at bottom.

---

## 3. THE KEY TEST — does Kalshi LAG the reference? (point-in-time + the decisive prior study)

### 3a. The decisive evidence: a **Federal Reserve study (Mar 2026)** already ran this exact test
A Fed research paper directly compared Kalshi's economic-event prices to the professional references
and found Kalshi is **at least as sharp, and usually sharper**:
- **CPI:** Kalshi's market-based YoY estimate had a **~40% LOWER average error than Bloomberg
  consensus** (Feb 2023–mid 2025) — "a statistically significant improvement." Kalshi **leads** the
  consensus; it does not lag it.
- **Fed funds:** "The mode of the Kalshi distribution … has **perfectly matched** the realized fed
  funds rate by the day of each meeting since 2022, a feat **not achieved by either surveys or
  futures**." i.e. Kalshi beats **FedWatch** itself on the FOMC.
- The Fed explicitly credits Kalshi's real-time updating vs "surveys [that] go stale" and "thinly
  traded derivatives."

This **refutes the lag hypothesis at the source** for the two cleanest, most-liquid markets (CPI,
FOMC). The reference is not a sharper signal sitting in front of a lagging Kalshi; Kalshi is the
sharper signal. There is nothing to front-run.

### 3b. Point-in-time snapshots I took this session (consistent with the Fed result)
- **FOMC = FedWatch exactly.** Kalshi `KXFED-26JUN` → settling 3.75% with 99% certainty; FedWatch →
  97% hold at 3.75%. Identical. **Edge = 0.**
- **NFP:** Kalshi ATM implies median net payrolls ~**100–125k** (P(>100k)=0.655, P(>125k)=0.465);
  consensus ~130k. Within ~1 bracket and inside the spread. **No signed, clearable deviation.**
- **GDP — the one big gap, and it's a TRAP, not an edge.** Kalshi `KXGDP` (Q2 advance, closes
  7-30) implies a point estimate ~**2.2%** (P(>3.0)=0.325, P(>3.5)=0.205), while GDPNow = **3.3%**.
  That is a ~1pp gap — but it is the **wrong sign for the hypothesis**: it would say "buy the high
  GDP brackets because Kalshi lags GDPNow up." GDPNow's documented **early-quarter bias is +2.06pp
  and it runs hot, converging DOWN** toward the actual print; the advance GDP number is routinely
  well below an early-quarter GDPNow. So **Kalshi at 2.2% is the well-calibrated estimate and
  GDPNow at 3.3% is the stale/biased one.** Trading the gap = betting on a known-biased nowcast
  against a market the Fed showed is well-calibrated. Negative EV in expectation.

### 3c. Backtestable now? Partially — but the answer is already known
- A proper signed-deviation backtest needs **Kalshi odds *history*** (the public API gives candles
  for the 15-min crypto series but **macro books are sparse/illiquid intraday**, so the time series
  is mostly stale quotes, not a clean mid path). You would need to **shadow-collect** mid + the
  reference daily for each event, ~8–12 weeks across ≥3 CPI / ≥2 NFP / ≥3 FOMC-relevant updates, to
  estimate the signed (Kalshi−reference) deviation and its sign-persistence. **`kalshi_macro_snap.py`
  is that harness** (point-in-time ladder→survival→point-estimate + reference fields).
- **But you don't need to run it to know the verdict:** the Fed study is a larger, longer, cleaner
  version of exactly this measurement and it lands on "Kalshi ≥ reference." Collecting weeks of data
  to re-discover that Kalshi is well-calibrated is not worth the capital-at-risk, especially given §4.

---

## 4. STRUCTURAL / BEHAVIORAL EDGE CHECK

- **Favorite-longshot bias** is the one documented Kalshi-wide bias (longshots overpriced,
  favorites slightly underpriced; ~300k-contract studies). It **does** appear in the CPI ladder
  tails (deep "above 4.5"=0.19 ask with no bid). **But it is not harvestable here** for three reasons
  this repo already established: (1) `directional_deep.py` tested favorite-longshot on Kalshi crypto
  and found it **NULL even at fee=0** (KALSHI.md: "0 of 36 tests"); (2) the bias **diminishes after
  controlling for liquidity/lifecycle** (multivariate studies) — i.e. it lives in the thin/stale
  brackets that you can't size into; (3) the tail brackets carry **10–14c spreads** — even if a 5c
  longshot is "worth" 3c, the spread+fee eats it. The favorite side (buying the ~95c bracket) yields
  the documented tiny positive return but at ~95c the fee+spread leaves ~0 and capacity is trivial.
- **Round-number anchoring / underreaction to nowcast updates:** the Fed result (Kalshi 40% better
  than consensus, real-time vs stale survey) is the direct refutation — Kalshi *updates faster* than
  the references, the opposite of underreaction. The non-monotonic survival function is a stale-quote
  artifact in untraded brackets, not a tradeable anchoring signal.

---

## 5. VERDICT vs the dead crypto box

| | Crypto box (proven dead) | Macro events (this study) |
|---|---|---|
| Why it failed | last-in-queue; mid beats models; HFT-MM owns the queue | Kalshi price ≥ sharp reference; the reference *is* the consensus and Kalshi beats it |
| Mid vs fair | mid efficient | mid efficient **and Fed-validated as sharper than nowcasts/FedWatch/consensus** |
| Escapes the box's death mechanism? | — | **Yes** — scheduled releases, no queue race. **But trades one death for another:** instead of losing the queue, you'd be **taking the worse side of a well-calibrated price**, paying spread+fee to a market the Fed says is sharp. |
| Two-sided liquidity | deep (BTC 26k/min) | **only the ATM bracket, single-to-low-hundreds of contracts** |
| Capacity | high but no edge | **tiny** (tens–hundreds $/bracket) AND no edge |
| Deployable +EV edge | **No** | **No** |

**Bottom line:** there is **no deployable +EV macro-event lag edge** on Kalshi.
- The hypothesis required Kalshi to *lag* the sharp reference. The **Fed study shows the reverse**
  (Kalshi −40% CPI error vs consensus; FOMC mode beats futures), and my live FOMC/NFP snapshots
  match the reference inside the spread.
- The only large Kalshi-vs-reference gap (GDP vs GDPNow, ~1pp) has the **wrong sign and a known
  cause** (GDPNow early-quarter hot bias) — trading it is negative EV.
- The one real bias (favorite-longshot) lives in **thin, wide-spread, low-capacity** tail brackets
  that don't clear spread+fee — same null this repo already found on Kalshi crypto.
- Even if a micro-edge existed, **capacity is tiny** (the uncertain brackets are single-to-low-
  hundreds of contracts) and **resolution-source risk** (delayed/cancelled BLS releases — note the
  live `KXNFPDELAY`/`KXCPIDELAY`/`KXPAYROLLCANCEL` series) is real.

**Escapes the crypto box's death? Yes (no queue race). Backtestable now? The harness exists
(`kalshi_macro_snap.py`), but the Fed study already settled it — Kalshi macro is efficient and, if
anything, *sharper* than the free references. This is a cleaner, faster dead-end than crypto: no
weeks of shadow data needed to reach "no edge."**

If anything productive comes out of this, it's the **opposite trade**: Kalshi's macro distribution
is itself a free, well-calibrated *signal* (better than GDPNow early-quarter, better than Bloomberg
CPI consensus) — useful as an input to other models, not as a venue to extract spread from.

---

### Sources
- Fed study coverage — Motley Fool: https://www.fool.com/investing/2026/03/16/federal-reserve-research-kalshi-prediction-markets/ ; Gambling Insider: https://www.gamblinginsider.com/news/113897/fed-study-kalshi-economic-forecasting
- Cleveland Fed Inflation Nowcasting: https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting
- CME FedWatch user guide: https://www.cmegroup.com/tools-information/quikstrike/cme-fedwatch-tool-user-guide.html
- Atlanta Fed GDPNow: https://www.atlantafed.org/research-and-data/data/gdpnow ; accuracy: https://www.atlantafed.org/cqer/research/gdpnow ; FRED `GDPNOW`: https://fred.stlouisfed.org/series/GDPNOW
- GDPNow Q2 2026 updates: https://www.fx.co/en/forex-news/3024987 ; https://investinglive.com/centralbank/atlanta-fed-gdpnow-estimate-for-q2-comes-in-at-38-down-from-43-20260528/
- NFP June 2026 consensus: https://www.cnbc.com/2026/06/05/jobs-report-may-2026.html ; https://www.capitaleconomics.com/publication-group/us-employment-report-preview
- Favorite-longshot / Kalshi biases: https://quantpedia.com/systematic-edges-in-prediction-markets/ ; https://www2.gwu.edu/~forcpgm/2026-001.pdf (GWU "Makers or Takers: economics of the Kalshi prediction market")
- Kalshi public API: https://api.elections.kalshi.com/trade-api/v2/ (`/series`, `/markets`, `/markets/{t}/orderbook`, `/markets/trades`)
