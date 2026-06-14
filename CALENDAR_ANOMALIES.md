# Calendar / Seasonal Anomalies as Timing Overlays — mostly DECAYED; honest near-null

**Question.** Do documented US-equity *calendar / seasonal* anomalies (a different effect from the
project's momentum / trend-following risk premia — pure **timing**, not a risk premium) survive
**recently**, **net of cost**, and **past a multiple-testing bar**, such that they could be a cheap
US-legal small-bankroll **timing overlay** on the equity sleeve and **add to the momentum+TF book**?

**VERDICT UP FRONT: NO deployable calendar overlay. Honest near-null.** Of 8 anomalies tested on 3
ETFs, the historically real ones (turn-of-month, Halloween) have **decayed below significance in
2016-2026**, and the only effect that clears a per-ticker multiple-testing bar recently
(**pre-holiday**, SPY recent t=3.62) is invested **only ~2.7% of days** — as an overlay it earns
~1% CAGR net of 3 bps and dies to ~0 at 10 bps. Nothing clears the cross-ticker Bonferroni bar.
None of them diversify the momentum+TF book: the only overlay that ~matches buy-and-hold (a
turn-of-month leverage tilt) is **0.87 correlated to SPY** — it is just timing beta, not a new
return stream. **Do not deploy a calendar overlay. Keep the equity sleeve as buy-and-hold / the
momentum book.**

---

## Data, window, costs (SCREENS)

- **Source:** yfinance daily **adjusted** closes (`auto_adjust=True` => total return). SPY (from
  1993-02), QQQ (1999-03), IWM (2000-05). Staged at `/tmp/cal_data/prices.csv` (NOT committed).
- **Window:** full sample per ticker -> 2026-06-12. **Recent-decade OOS holdout: 2016-01-01 ->
  2026-06.**
- **Costs:** commission-free ETFs; **spread charged per side** on every overlay entry/exit, swept
  at **0 / 3 / 10 bps** (3 bps = the project's `ETF_MOMENTUM` convention). A timing overlay that
  toggles in/out of the market trades a *lot*, so cost sensitivity is the make-or-break axis.
- **Stat:** Newey-West (5-lag) t-stat on the **mean daily simple return** inside each window vs all
  other days. Overlay backtests report CAGR / Sharpe / maxDD net of cost vs buy-and-hold (BH).
- **FOMC calendar:** scheduled announcement dates **hardcoded 2010-2026** (8/yr; 2nd-day statement
  release; emergency 2020 cuts excluded). Pre-FOMC window = the single trading day *before* the
  announcement (t-1), per Lucca-Moench (2015).
- **Script:** `calendar_anomalies.py`. All numbers below are reproducible from it.

## Multiple-testing bar (state it before reading the table)

Testing **8 anomalies** guarantees ~1 looks "significant" at p<0.05 by chance. Bonferroni for one
family of 8 ⇒ need **p<0.0063, i.e. |t|>2.73**. Run across **3 ETFs (24 tests)** ⇒ need
**|t|>3.08**. I apply the **|t|>2.73 (single-ticker) / >3.08 (cross-ticker)** bar to the
**recent-decade** number — full-sample significance is the thing post-publication decay erodes, so
it does not count.

---

## Results — full sample vs recent decade (mean daily excess, bps; NW t-stat)

**SPY** (1993-2026; BH full Sharpe 0.65, recent 0.87):

| anomaly | full mean(bps) | full t | recent mean(bps) | recent t | recent verdict |
|---|---|---|---|---|---|
| 1. Pre-FOMC (t-1) | 7.4 | 0.76 | 16.2 | **1.87** | not significant; n=83 |
| 2. Turn-of-month (-1..+3) | 7.7 | **2.86** | 6.2 | 1.47 | **DECAYED** |
| 3. Halloween (Nov-Apr) | 6.0 | **3.64** | 6.2 | 1.91 | **DECAYED** below bar |
| 4a. Monday | 5.6 | 2.04 | 8.4 | 1.66 | not significant |
| 4b. Pre-holiday (gap>=4d) | 10.0 | 1.90 | 20.7 | **3.62** | clears single-ticker bar |
| 5a. Santa (last5+first2) | 11.6 | 2.11 | 6.2 | 0.81 | dead |
| 5b. January | 3.9 | 1.00 | 7.3 | 1.13 | dead |
| 5c. End-of-quarter (last3) | -1.6 | -0.32 | 5.1 | 0.60 | dead |

**QQQ** (recent t): pre-FOMC 1.80, TOM 1.68, Halloween 1.91, Monday **2.26**, pre-holiday 2.36,
Santa -0.04, Jan 1.37, EOQ 0.36.
**IWM** (recent t): pre-FOMC 1.10, TOM 0.25, Halloween 1.04, Monday 1.35, pre-holiday **2.95**,
Santa 0.36, Jan 0.55, EOQ 0.96.

**Reading the table against the bar:** in the recent decade, **only pre-holiday on SPY (3.62)
clears |t|>2.73**, and pre-holiday on IWM (2.95) and QQQ (2.36) corroborate it — but **none clear
the cross-ticker |t|>3.08**. Every other anomaly is below 2.73 on every ticker recently.

---

## Per-anomaly honest read

1. **Pre-FOMC drift (Lucca-Moench 2015).** Reportedly decayed/reversed after publication.
   Here it is *still positive* recently (SPY +16 bps, t=1.87; QQQ +24 bps) — it did **not** reverse
   — but it is **not significant** at any sane bar and is invested only ~1.6-3% of days. As an
   overlay (long only on t-1, cash else): SPY recent Sharpe 0.47 at 0 bps, **0.29 at 3 bps,
   negative at 10 bps**. It trades 16x/yr for ~1 day each — costs eat it. **Not deployable.**

2. **Turn-of-month (-1..+3).** The textbook "captures most of the month's return" claim is
   **busted recently**: full t=2.86 (real historically) but recent t=1.47. And the cumulative
   check is damning — TOM's 19% of days produced **+209% vs +2968% all-days** full sample and
   **+33% vs +330%** recently, i.e. TOM is now a *minority* of the month's return, not the bulk.
   As a cash-out overlay it returns 2-3% CAGR (Sharpe 0.31-0.40 net) — **strictly worse than BH**.

3. **Halloween / Sell-in-May (Nov-Apr).** The most statistically robust *full-sample* effect
   (t=3.64) and the only one consistently positive across all 3 ETFs — but recent t=1.91, **below
   the 2.73 bar**. As the classic "invested Nov-Apr, cash May-Oct" overlay: recent **Sharpe 0.53
   vs BH 0.87** — you give up half a Sharpe point and half the return to sit out summers that, this
   decade, were *not* bad enough to justify it. **Not deployable; it underperforms BH.**

4. **Day-of-week / pre-holiday.** Monday is **dead** (recent t 1.66/2.26/1.35 — noise after MT).
   **Pre-holiday** is the lone recent survivor by t-stat (SPY 3.62, IWM 2.95, QQQ 2.36) — a real,
   cross-ticker, recent effect. **But** it is invested only **2.7% of days**; as a long-only overlay
   it earns ~1% CAGR (Sharpe 0.53 net 3 bps, ~0 at 10 bps). There is too little time-in-market to
   matter to a bankroll, and the 22 holidays/yr × in/out toggling makes it cost-fragile.

5. **Santa / January / end-of-quarter.** All **dead** recently (recent |t| < 1.4 everywhere,
   several negative). Santa was real-ish full sample (SPY t=2.11) and is now noise.

---

## Deployability — does the best survivor beat buy-and-hold or add to the book?

**Standalone overlays on SPY (net of cost):** every in-window/cash-out overlay **loses to
buy-and-hold** on Sharpe in the recent decade (TOM 0.31, Halloween 0.53, pre-FOMC 0.29, pre-holiday
0.53 — all < BH 0.87), because they sit in cash 50-98% of the time and the market drifts up. The
only form that ~ties BH is a **leverage tilt** (TOM 1.5x / 0.5x): recent CAGR 9.6%, **Sharpe 0.73
vs BH 0.87** at 3 bps — *still below BH*, and it is **0.87 correlated to SPY daily** — it is just
**timing beta** (lever the equity sleeve), not a new uncorrelated return stream.

**Would it add to the momentum+TF book (`PORTFOLIO_COMBINED`)?** No. The combined book is the
ETF-momentum winner (Sharpe ~0.83) + an inverse-ETF TF crisis sleeve. A calendar overlay would
have to be either (a) a new uncorrelated stream — but the only one near-deployable (TOM-tilt) is
0.87-correlated to SPY, i.e. **redundant with the long-equity beta the momentum book already
carries**; or (b) big enough to matter — but pre-holiday/pre-FOMC are invested 2-3% of days and net
~1% CAGR, **too small to move a book**. There is no diversification and no size. **Adds nothing.**

---

## VERDICT

- **No deployable calendar timing overlay.** Honest near-null — the expected outcome for the poster
  child of data-mining and post-publication decay.
- **Decayed below the multiple-testing bar (recent t < 2.73):** turn-of-month, Halloween,
  Monday, Santa, January, end-of-quarter. The old "TOM captures the whole month" and
  "Sell-in-May" rules **no longer pay** net of cost — both **underperform buy-and-hold** as overlays.
- **Did NOT reverse but still insignificant:** pre-FOMC drift (still +16/+24 bps recently but
  t<1.9 and cost-fragile at ~1.6% of days).
- **Lone recent survivor by t-stat:** **pre-holiday** (SPY 3.62 / IWM 2.95 / QQQ 2.36) — real and
  cross-ticker, but invested only 2.7% of days ⇒ ~1% CAGR net, dies at 10 bps ⇒ **not deployable
  and not material.** It does *not* clear the cross-ticker Bonferroni bar (|t|>3.08).
- **Adds to the momentum+TF book? No** — redundant (timing beta, 0.87 corr to SPY) and/or too small.
- **Rule:** keep the equity sleeve as the momentum book / buy-and-hold; **do not** add a calendar
  timing overlay. The one defensible micro-use, if any, is *not trading into the market on a
  pre-FOMC or pre-holiday close to avoid a known weak day* — a cost-avoidance footnote, not an edge.
