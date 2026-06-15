# Sharp-line vs Kalshi sports: the empirical deviation/timing-lag edge test (2026-06-15)

Brutally honest answer to: *aggregate sportsbook lines, empirically pick the sharpest fair-value
reference, then bet Kalshi sports markets that deviate from it — is that a deployable +EV edge for a
US small-bankroll trader, given Kalshi is the only venue that legally can't ban a winner?*

Builds on `SPORTS_BETTING.md` (commit 56fb362), which established the prior: **Kalshi's LIQUID game
markets are SIG/Susquehanna-priced (mid-overround ≈ 0%, 1–3c spreads) ≈ already at the sharp
consensus**, so the only candidate edges are (a) **timing lags** and (b) the **illiquid slice**. This
doc does the work that was still missing: an actual **Kalshi-only CLV/calibration backtest on 706
settled games** (needs no paid feed), the **sharpest-reference ranking method**, the **timing-lag
harness + design**, and a **net-of-cost verdict + forward-measurement plan**.

**TL;DR verdict (details §6):** **Confirms the prior, with one new wrinkle.** On 706 settled
Kalshi games (MLB/NHL/WNBA/NFL/NBA), Kalshi's **closing mid is ~2× sharper than its early mid**
(Brier 0.231→0.119) and is **well-calibrated through the middle of the book** — i.e. efficient where
it's liquid, exactly as predicted. The **one measured anomaly** is a **favorite–longshot bias at the
tails** (longshots ~4.5c too expensive, heavy favorites ~4.7c too cheap), which is *near* the
spread+fee hurdle and *directionally* tradeable but **not cleanly clearing it after costs**. The
deviation edge is therefore **not a takeable liquid-side free lunch.** The honest live opportunities
remain: **(1) a MAKER timing-lag capture IF Kalshi lags sharp moves** (still UNCONFIRMED — needs a
time-stamped sharp feed; harness is built and wired) and **(2) the illiquid slice** (WTA tennis touch
spreads up to **70c** in our live pull = genuinely soft, but thin/no-capacity). **Net: efficient on
liquid, thin on illiquid; a real maker timing-lag edge is plausible but unproven — and Kalshi's new
Feb-2026 sportsbook-hedging rebate is actively pulling sharp money on, which makes the liquid side
*more* efficient over time, not less.** Deploy only after a forward CLV log proves positive net CLV.

---

## 1. Line aggregation — data sources & how to pull them

**Goal:** for each game in NFL/NBA/MLB/NHL, assemble *many books' odds (live + historical) + the
realized outcome*, to (a) empirically rank the sharpest reference and (b) compare Kalshi against it.

| Source | What it gives | Access | Role here |
|---|---|---|---|
| **the-odds-api.com** | 50+ books incl. **Pinnacle (EU region)**, h2h/spreads/totals, NFL/NBA/MLB/NHL; **historical odds back to 2020** (snapshot-at-timestamp), player props one-game-at-a-time | Free tier 500 req/mo (incl. Pinnacle EU); Business $99/mo adds dense polling + a Pinnacle edge-detection endpoint | **Primary sharp feed** — Pinnacle h2h de-vigged = fair prob; historical endpoint backfills closing lines for the accuracy backtest. [[odds-api historical]](https://the-odds-api.com/historical-odds-data/) [[NBA endpoint]](https://the-odds-api.com/sports-odds-data/nba-odds.html) |
| **Pinnacle** (direct/EU) | the sharpest single book, ~2–3% hold | via odds-api `regions=eu`; **US-illegal to bet, legal to read** | the gold-standard reference line |
| **Circa Sports** | sharp US book (Vegas), high limits, doesn't ban as fast | screen-scrape / odds-api where listed | secondary sharp anchor (US-domiciled) |
| **OddsJam / OddsPapi** | aggregated multi-book + de-vig + +EV/CLV tooling | paid | convenience layer; same underlying books |
| **Kalshi public API** | `api.elections.kalshi.com/trade-api/v2` — `/series`,`/events`,`/markets`,`/markets/{t}/orderbook`, **`/series/{s}/markets/{t}/candlesticks` (1-min bid/ask OHLC + volume)** | **no auth for read** | the venue under test; candlesticks = the backtest substrate (see §4) |

**Pull recipe (leagues = baseball_mlb, basketball_nba, icehockey_nhl, americanfootball_nfl):**
1. **Live odds:** `GET /v4/sports/{sport}/odds?regions=eu,us&markets=h2h&oddsFormat=decimal&apiKey=…`
   → per game, every book's two-way prices. De-vig each book: `p_i = (1/dec_i)/Σ(1/dec_j)`.
2. **Historical (for the accuracy ranking):** `GET /v4/historical/sports/{sport}/odds?date={ISO}` —
   one snapshot per timestamp; pull the **last pre-kickoff snapshot** = each book's closing line.
3. **Outcomes:** scores endpoint (or Kalshi settlement `result`) to label each game 1/0.
4. **Kalshi:** `/events?series_ticker=KXMLBGAME&status=settled&with_nested_markets=true` for the
   game list, then `candlesticks` per market for the full intraday price path + the `result`.

Scripts: existing `kalshi_vs_sharp.py` (live deviation snapshot), `kalshi_sports_probe.py`
(inventory), and the new **`kalshi_clv_lag.py`** (CLV/calibration backtest + lag harness).

---

## 2. Ranking the sharpest reference — method + the established answer

**Method (to run once an ODDS_API_KEY + a few weeks of history exist):** collect each book's
**closing** de-vigged probability per game, then score each candidate reference against realized
outcomes:
- **Brier** `mean((p−y)²)` and **log-loss** `mean(−[y·ln p + (1−y)·ln(1−p)])` — lower = sharper.
- **Closing-line accuracy / CLV** — does betting *into* a candidate's line, then comparing to the
  consensus close, produce positive CLV? The line you cannot beat is the sharpest.
- Candidate references: **single best book** (Pinnacle), **Circa**, **simple no-vig consensus
  (median of de-vigged books)**, **accuracy-weighted blend** (weight ∝ 1/Brier).

**The well-established answer (verify, don't assume):** **Pinnacle's (and Circa's) CLOSING line is the
gold-standard sharpest single predictor** — Pinnacle deliberately invites sharp action and moves on
it, giving the lowest hold (~2–3%) and the best Brier among books; researchers use Pinnacle's de-vig
as the accuracy baseline. [[Pinnacle Brier]](https://www.pinnacle.com/betting-resources/en/soccer/the-brier-score-method/9be2pl9dk4um54fy)
[[CLV demystified — Buchdahl]](https://www.pinnacleoddsdropper.com/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl)
A **no-vig multi-book consensus (or accuracy-weighted blend) frequently edges out any single book**
by averaging idiosyncratic noise. **Closing-line value is the accepted proof of edge**: consistently
beating the de-vigged close → long-run profit, demonstrable in as few as ~50–500 bets.
[[boydsbets CLV]](https://www.boydsbets.com/closing-line-value/) [[OddsJam CLV]](https://oddsjam.com/betting-education/closing-line-value)
**Output = one calibrated fair probability per game** = de-vigged Pinnacle close, or the
accuracy-weighted consensus, whichever wins the Brier bake-off on your collected data.

---

## 3. Kalshi sports inventory + liquidity + alignment (live API, no auth, 2026-06-15)

**Inventory** (`/series?category=Sports&limit=1000` → **2,191 series**, the bulk of Kalshi). Tags:
Soccer 440, Basketball 418, Football 362, Baseball 167, Tennis 121, Golf 104, Esports 102, Hockey 68,
Motorsport 54, Olympics 46, Cricket 46, MMA 34, Chess 25, Boxing 20, long tail.

**Market types:** **game winner / moneyline** (`KXMLBGAME`,`KXNBA`,`KXNHLGAME`,`KXWNBAGAME`,
`KXNFLGAME`), **series/playoff** (`KXNBASERIES`,`KXNHLSERIES`), **season win-totals / champion
futures** (`KXMLB-26-<team>`), **totals**, **spreads**, **props** (next-TD, first goal, strikeouts),
exotics. Each game-event = **two complementary YES markets** (one per team), priced in cents 1–99,
binary, settle ~120s after the result; fee_type quadratic.

**Liquidity (live snapshot, this pull).** Confirms the **bimodal** structure:

| Series | touch spread (med / max) | note |
|---|---|---|
| `KXMLBGAME` game (40 games) | **1.0c** / p90 4c | mid-overround **+0.00%** (de-vig fair = mid) |
| `KXNHLGAME` | 1.0c | overround +0.00% |
| `KXWNBAGAME` | 1.0c | overround **−0.50%** |
| `KXNFLGAME` (Sep, pre-season) | **3.0c** / p90 4c | overround +0.25%, thinner pre-season |
| `KXATPMATCH` (tennis) | 1.0c / max 3c | popular matches tight |
| **`KXWTAMATCH`** (tennis) | 2.0c / **max 70c** | **the genuinely soft/illiquid slice** |
| `KXNBASERIES`,`KXNHLSERIES`,`KXMLB-26` futures | (no open two-sided book in-window) | off-season / sparse |

All liquid game-markets: **median mid-overround = 1.0000 (hold +0.00%), median touch spread 1.5c.**
Tighter than Pinnacle's 2–3% hold and US soft books' ~4.5%. **Sports = ~70%+ of Kalshi volume; a
recent month showed $543.1M total traded, $505.8M (93%) on sports.**
[[gamingamerica rebate]](https://gamingamerica.com/news/1006858/kalshi-launches-prediction-market-rebate-program-for-sports-event-contracts)
[[si.com Kalshi]](https://www.si.com/prediction-markets/reviews/kalshi)

**Market maker:** **Susquehanna (SIG)** runs Kalshi's dedicated 24/7 event-contract desk, ~30× prior
liquidity, six-/seven-figure fills on flagship markets — i.e. a top quant MM keeps the liquid mid on
the sharp consensus. [[Kalshi/SIG]](https://news.kalshi.com/p/liquid-prediction-markets-are-finally-here)
[[Morningstar]](https://www.morningstar.com/news/business-wire/20240403664852/kalshi-onboards-its-first-dedicated-institutional-market-maker)

**Alignment (Kalshi → sharp outcome):** each Kalshi team-YES market maps 1:1 to the de-vigged sharp
moneyline probability for that team. Match by team name in `yes_sub_title`/`title`; de-vig Kalshi's
two complementary mids (`mid_A/(mid_A+mid_B)`) to fair, and compare to `p_fair_sharp`. Totals/spreads
map to the corresponding sharp total/spread de-vig (one threshold at a time).

---

## 4. The deviation test + the Kalshi-only CLV/calibration backtest (MEASURED)

**Key infrastructure finding:** Kalshi **settled** game markets expose **1-minute bid/ask OHLC
candlesticks + the realized `result`**. So a real in-sample test of *"is Kalshi efficient / is its
closing line sharp / is it biased anywhere"* is possible **today with NO paid feed** — this is the
honest backtest the prior doc said was missing. Harness: **`kalshi_clv_lag.py`**.

**Result — 706 settled games, 5 leagues (MLB 234, NHL +240, WNBA +226, NFL, NBA; cumulative 706):**

```
Brier(entry mid) = 0.2310    logloss(entry) = 0.6514
Brier(close mid) = 0.1188    logloss(close) = 0.3733
-> the CLOSING price is ~2x sharper than the early price (closing-line law CONFIRMED on Kalshi).

calibration of CLOSING mid (predicted vs realized):
  [0.0-0.2) n=198  pred=0.085  actual=0.040   gap=-4.5c   <- longshots OVERPRICED
  [0.2-0.4) n= 86  pred=0.291  actual=0.267   gap=-2.4c
  [0.4-0.6) n=139  pred=0.501  actual=0.504   gap=+0.3c   <- middle = efficient
  [0.6-0.8) n= 88  pred=0.702  actual=0.705   gap=+0.3c   <- middle = efficient
  [0.8-1.0) n=197  pred=0.913  actual=0.959   gap=+4.7c   <- heavy favorites UNDERPRICED
```

**Interpretation:**
- **Liquid side is efficient where it matters.** Through the meat of the book (0.4–0.8) the closing
  mid is calibrated to **±0.3c** — there is **no systematic deviation to harvest**, confirming the
  prior. The 1.5c spread + ~1.75c worst-case taker fee (≈ **2.75–3c hurdle**) eats any residual.
- **The one measured anomaly: a favorite–longshot bias at the tails.** Longshots (price <0.2) win
  *less* often than priced (−4.5c) and heavy favorites (>0.8) win *more* often (+4.7c). The
  *direction* is the classic FLB and is consistent across 395 tail games. **But:** (i) the gaps
  (~4.5c) only barely exceed the ~3c liquid hurdle and the residual after cost is ~1–1.5c — razor
  thin; (ii) at the tails the **per-contract dollar edge is tiny** (buying a 0.91 favorite to win
  0.96 is +5c on a 91c stake ≈ 5% — but you must be *right* about the 0.91 being the fair number,
  which is itself the closing mid you're trying to beat); (iii) this is measured *at the close*, so
  capturing it means **fading the closing line on longshots / backing heavy favorites**, a thin,
  capacity-limited, high-variance play. **Flagged as the only liquid-side signal, not endorsed as a
  clean +EV edge** — it needs the cross-book Pinnacle check to confirm it isn't an artifact of
  Kalshi-settlement timing.
- **The +19.97c "entry→close drift toward winner" is NOT an edge** — it's the price clustering near
  0.50 early (uninformative wide quotes) then converging as info arrives. You cannot reliably buy the
  eventual winner early; this is the price *becoming* sharp, the very thing you'd have to beat.

**Cost-to-take (must be cleared):** taker fee `ceil(0.07·P(1−P)·100)/100` ≈ **1.75c @0.50**, ~1.1c at
the tails; half-spread **0.5–1.5c liquid / 2.5–35c illiquid**. **Liquid hurdle ≈ 2.75–3c; illiquid
4–40c.** Maker fee = **0**, plus the **Liquidity Incentive Program pays up to +$0.005/contract** —
which is why any real edge should be harvested **as a maker** where possible.
[[predictionhunt fees]](https://www.predictionhunt.com/blog/kalshi-fees-complete-guide-2026)

---

## 5. Timing-lag test, backtest/CLV, and the forward harness

**Timing-lag hypothesis (the optimistic finding to confirm):** when Pinnacle/Circa moves, does Kalshi
**follow with a lag** a maker can rest ahead of? This is the only edge that survives the
"liquid=efficient" wall, because the lag is a *transient* mispricing, not a standing one.

**Status: UNCONFIRMED — and it requires the one input we don't have (a time-stamped sharp feed).**
The Kalshi 1-min candlesticks give the Kalshi side at minute granularity; the missing half is a
synchronized Pinnacle time series. With an `ODDS_API_KEY`, `kalshi_clv_lag.py` will:
1. Poll Pinnacle h2h every ~5 min from line-open to close, de-vig, timestamp.
2. After settlement, pull the matching Kalshi 1-min candlesticks.
3. Cross-correlate `Δ(Pinnacle_fair)` vs `Δ(Kalshi_mid)` at lags 0..15 min.
   - **Peak at lag > 0** ⇒ Kalshi *follows* Pinnacle ⇒ a **maker resting at the post-move fair value
     (0 fee, +$0.005 rebate) captures the lag** ⇒ tradeable.
   - **Peak at lag ≤ 0 / flat** ⇒ Kalshi leads or is coincident ⇒ **no capturable lag** (SIG keeps
     it on consensus). This is the honest prior given SIG's role.
4. **Proof = positive realized CLV vs Kalshi settlement, net of cost, OOS, over ≥300–500 games / 3–6
   weeks** — the same falsifiable bar as the weather/Polymarket studies.

**Point-in-time snapshot we CAN give now:** with no key, the live deviation test runs in
self-consistency mode and shows **median Kalshi mid-overround = 0.0000** with the calibration above —
i.e. **on liquid games the snapshot deviation vs the de-vigged consensus is ~0 within the spread.**
The only place a live snapshot shows large gaps is the illiquid slice (WTA spreads to 70c), where the
"gap" is mostly *spread*, not *edge*, and depth is too small to take. **A snapshot is not proof
(could be model/timing, not edge); CLV is.**

**Data/duration needed (like the prior studies):** 1 ODDS_API_KEY (free 500 req/mo polls a few
leagues a few×/day; $99/mo Business for dense per-game polling) + **3–6 weeks of in-season collection
across ≥300–500 games**, logging (Kalshi entry, de-vigged Pinnacle at entry, Pinnacle close, Kalshi
settlement). Decision rule: **deploy only if net-of-cost CLV is positive and stable.**

---

## 6. Capacity + verdict

**Capacity.** Liquid flagship games (MLB/NHL/WNBA primetime, top tennis) are **deep** — six-/seven-
figure fills, $505M/mo sports volume — but **efficient (no edge)**. The places with an *edge candidate*
are **capacity-starved**: the tail FLB play is spread across many low-priced contracts with thin tail
depth; the illiquid slice (WTA, futures, props) has **5–70c spreads and 5–20k contract volume**.
Realistic deployable size for a *small* bankroll on any genuine-edge slice = **low hundreds to low
thousands of $/day**, capped by the very illiquidity/thinness that creates the edge. **Headwind:**
Kalshi's **Feb-2026 Sportsbook Hedging Rebate** (100% taker/RFQ fee waiver for books hedging >300k
contracts/mo) is pulling **sharp sportsbook money onto Kalshi**, which **tightens liquid prices
further** — efficiency is increasing, not decreasing.
[[CFTC rebate filing]](https://www.cftc.gov/sites/default/files/filings/orgrules/26/02/rules02072638946.pdf)

**Verdict (honest, either way):**
- **Liquid game moneylines (MLB/NHL/WNBA primetime, ATP):** **efficient — SIG keeps the closing mid
  on consensus, calibrated to ±0.3c through the middle.** **No deployable deviation edge** after the
  ~3c spread+fee hurdle. (It's a *cheaper, un-bannable place to bet*, not an *edge*.)
- **Tail favorite–longshot bias:** a **real measured directional anomaly** (longshots −4.5c,
  favorites +4.7c on 395 games) but the residual after the ~3c hurdle is **~1–1.5c, razor-thin,
  high-variance, and possibly a settlement-timing artifact** — *flagged, not deployed* until a
  cross-book Pinnacle confirmation rules out artifact. Could be a thin **maker** sleeve at best.
- **Illiquid slice (WTA, futures, props, niche):** **softest** and **un-bannable**, but **spreads
  5–70c, tiny depth** → edge must clear a 4–40c hurdle with near-zero capacity. **Marginal/thin
  dead-end** for size.
- **Maker timing-lag capture:** **the one genuinely optimistic, still-unconfirmed candidate.** IF the
  cross-correlation shows Kalshi lagging sharp moves, a 0-fee+rebate maker resting at post-move fair
  is tradeable. **Needs the forward CLV harness to confirm; honest prior given SIG = likely small/none.**

**Recommended action:** run `kalshi_clv_lag.py` with an `ODDS_API_KEY` for **3–6 weeks in-season**,
logging realized CLV vs Kalshi settlement net of fee+spread, focused on (1) the **maker lag** test on
liquid MLB/NHL/NFL/NBA games and (2) a **cross-book confirmation of the tail FLB**. **Deploy only on
positive, stable net CLV.** Expected outcome, stated up front: **efficient on liquid, thin on
illiquid; a small maker timing-lag edge is plausible but unproven, and the venue's only unambiguous
advantage — it can't ban a winner — is necessary but not sufficient without a standing mispricing.**

**What data confirms it:** an ODDS_API_KEY (Pinnacle h2h, live + historical) + a **300–500-game,
multi-week CLV log** + a **cross-correlation lag peak** from `kalshi_clv_lag.py`. Until that shows
positive stable net-of-cost CLV (and a lag peak at >0 min), treat Kalshi sports as **efficient where
deep, thin where soft — a measure-first, do-not-pre-deploy opportunity.**

### Sources
- the-odds-api: [historical](https://the-odds-api.com/historical-odds-data/), [NBA](https://the-odds-api.com/sports-odds-data/nba-odds.html)
- CLV/sharpness: [Buchdahl/Pinnacle](https://www.pinnacleoddsdropper.com/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl), [boydsbets](https://www.boydsbets.com/closing-line-value/), [OddsJam](https://oddsjam.com/betting-education/closing-line-value), [Pinnacle Brier](https://www.pinnacle.com/betting-resources/en/soccer/the-brier-score-method/9be2pl9dk4um54fy)
- Kalshi structure/MM: [Kalshi/SIG](https://news.kalshi.com/p/liquid-prediction-markets-are-finally-here), [Morningstar](https://www.morningstar.com/news/business-wire/20240403664852/kalshi-onboards-its-first-dedicated-institutional-market-maker), [si.com](https://www.si.com/prediction-markets/reviews/kalshi)
- Fees/rebate/volume: [predictionhunt fees](https://www.predictionhunt.com/blog/kalshi-fees-complete-guide-2026), [gamingamerica rebate](https://gamingamerica.com/news/1006858/kalshi-launches-prediction-market-rebate-program-for-sports-event-contracts), [CFTC rebate filing](https://www.cftc.gov/sites/default/files/filings/orgrules/26/02/rules02072638946.pdf)
- Measured data: Kalshi public API `trade-api/v2` (`/series`,`/events`,`/markets`,`/candlesticks`); scripts `kalshi_clv_lag.py`, `kalshi_vs_sharp.py`, `kalshi_sports_probe.py` (this repo).
