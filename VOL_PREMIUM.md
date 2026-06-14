# VOL_PREMIUM.md — Volatility Risk Premium (systematic options-income) as a deployable US small-bankroll sleeve

**Question.** The project winner is cross-asset ETF momentum (Sharpe ~0.83, maxDD ~-17%,
long-only, IRA-friendly). The **volatility risk premium (VRP)** — implied vol persistently
above subsequent realized vol, so selling options/vol earns an insurance premium — is a
*different* return stream that pays steadily and crashes occasionally. Is it a genuinely new,
deployable edge at **$1k–$10k** that **diversifies** the momentum winner, or is it dominated
by its left tail?

**VERDICT UP FRONT: PARTIAL ADD, NOT A STANDALONE EDGE.** The VRP is *real* and *persistent*
(VIX averages 19.5 vs subsequent 21-day realized 15.9 → a **+3.7 vol-point premium, positive
83% of months**), and it is **deployable at $1k via 1-share ETFs** (PUTW / XYLD — no options
approval, no per-contract capital needed). **But on its own it is WORSE than the momentum
winner on every risk-adjusted axis**: net Sharpe ~0.49–0.55 (vs 0.83), maxDD **-37% in 2008
and -28% in COVID** — i.e. it eats nearly the *same* equity-crash drawdown as buy-and-hold
while giving up the upside. It does **not** diversify the way a naive "lowly-correlated risk
premium" pitch implies: in monthly returns the put-write proxy correlates **0.83 with SPY**
and **0.33 with momentum**, and crucially it correlates **~1.0 with the market exactly in the
crashes** (its left tail and long-only momentum's are the *same* event). A 70% momentum / 30%
VRP blend lands at Sharpe **0.81** — essentially tied with 100% momentum (0.80) — so the VRP
**adds almost nothing** unless paired with a tail hedge or the trend sleeve as crisis alpha.
**Recommendation: do NOT run VRP as a second standalone edge. If you want it at all, cap it at
~20–30% of the equity sleeve via PUTW, and only inside a portfolio that already owns trend /
long-vol crisis alpha.** A naked cash-secured put program is *not* runnable at $1k–$10k anyway
(one SPY put ≈ $50–60k notional).

---

## Data, window, costs (SCREENS)

- **Source:** yfinance daily. `auto_adjust=True` (ETF series = total return, dividends
  reinvested). Staged at `/tmp/vp_data/` (**NOT committed**). Script: `vol_premium.py`.
- **Series & history:**
  - `^VIX` (implied vol, 1990–) and `SPY`/`^GSPC` (for realized vol & benchmark).
  - **`^PUT`** = CBOE S&P 500 PutWrite index (**1996–**) — the long-history put-write proxy
    that spans 2008. **`^BXM`** = CBOE S&P 500 BuyWrite/covered-call index (**1988–**).
  - **`PUTW`** (PutWrite ETF, 2016–), **`XYLD`** (S&P cov-call, 2013–), **`QYLD`** (NDX
    cov-call, 2013–), **`SVOL`** (short-VIX-futures ETF, 2021–).
  - **`VXX`** (the post-2018 reissue, 2018–) for the real long-vol tail hedge.
- **Window:** full sample per series (VRP characterization 1993–2026; ^BXM from 1988;
  ^PUT from 1996 → spans 2008). ETF results from inception. Crash episodes called out
  individually (2008, 2011, Feb-2018 Volmageddon, 2018-Q4, Mar-2020 COVID, 2022).
- **Costs:** ETF rebalances charged **3 bps/side** spread on traded notional (commission-free).
  Buy-and-hold ETF series carry their own fund-level option-execution costs (in NAV). The
  `^PUT`/`^BXM` indices already embed CBOE's monthly option settlement (no extra cost added).
- **DATA HYGIENE (critical):** Yahoo's `^PUT` series has **two adjacent glitch ticks**
  (2020-03-13 **+35.3%**, 2020-03-16 **-28.4%**) — impossible for a put-write index. They
  ~offset in the *level* path (cumulative return and the 2008 number are fine) but **corrupt
  daily std/skew and grossly flatter any vol-hedge backtest**. We **winsorize `^PUT`/`^BXM`
  daily returns to ±12%** (still admits true crash days like 2008-10-15 −9.4%). All numbers
  below use the cleaned series. **This matters: the uncleaned data showed a fake +2.7 skew for
  a put-writer (should be negative) and inflated the hedge Sharpe.**

---

## 1. VRP characterization — is the premium real, persistent, and how big?

VIX (30-day implied) vs **subsequent** 21-day realized SPY vol, annualized, 1993–2026
(n=8,379 days):

| metric | value |
|---|---|
| mean VIX (implied) | **19.5** vol pts |
| mean subsequent realized (21d) | **15.9** vol pts |
| **mean VRP (IV − RV)** | **+3.67 vol pts** (median +4.38) |
| fraction of days VRP > 0 | **83.3%** |
| 5th-percentile VRP | **−6.0** (realized blew past implied) |
| worst VRP day | **−65.3** (2020-02-19, on the eve of COVID) |
| days with VRP < −10 | 243 (**2.9%**) |

**The premium is real and persistent** — implied overprices realized ~83% of the time by
~3.7 vol points. That is the seller's edge. **But the distribution is the whole story:** the
2.9% of days where realized crushes implied (−10 to −65 vol points) are where a short-vol
position takes catastrophic losses. The VRP's Sharpe is *flattered* by averaging over the
calm 83% and under-weighting the rare −65. **A backtest that smooths the left tail is
worthless** — so the rest of this doc reports the actual crash drawdowns.

---

## 2. Investable proxy performance (full available history, net)

| proxy | window | CAGR | vol | **Sharpe** | Sortino | **maxDD** | skew |
|---|---|---:|---:|---:|---:|---:|---:|
| **^PUT** (CBOE PutWrite) | 1996–2026 | 8.2% | 15% | **0.49** | 0.48 | **−37.1%** | (neg.) |
| **^BXM** (CBOE BuyWrite) | 1988–2026 | 8.7% | 13% | **0.58** | 0.60 | **−40.1%** | −0.62 |
| PUTW (PutWrite ETF) | 2016–2026 | 8.3% | 13% | 0.52 | 0.52 | −28.4% | −1.81 |
| XYLD (S&P cov-call ETF) | 2013–2026 | 8.2% | 14% | 0.52 | 0.55 | −33.5% | −1.07 |
| QYLD (NDX cov-call ETF) | 2013–2026 | 8.3% | 15% | 0.50 | 0.52 | −24.8% | −0.62 |
| **SVOL** (short-VIX-fut ETF) | 2021–2026 | 7.3% | **22%** | **0.28** | 0.33 | −33.5% | +1.7 |
| *SPY (benchmark)* | 1993–2026 | 10.8% | 19% | 0.56 | 0.71 | −55.2% | 0.0 |
| *QQQ (benchmark)* | 1999–2026 | 10.8% | 27% | 0.46 | 0.61 | −83.0% | 0.2 |
| *Momentum winner (proxy)* | 2007–2026 | 10.4% | 11% | **0.80** | 0.91 | **−16.1%** | −0.48 |

**Read:** every VRP proxy clusters at **Sharpe ~0.49–0.58 and CAGR ~8%**, with **maxDD
−25% to −40%**. That is a respectable absolute return stream — but it is **dominated by the
momentum winner (Sharpe 0.80, maxDD −16%)** on risk-adjusted return AND drawdown. The
covered-call/put-write proxies cap the upside (CAGR ~8% vs SPY's 10.8%) while keeping most of
the downside. **SVOL (levered short-VIX-futures) is the worst** — Sharpe 0.28, the highest vol,
and the genuinely dangerous instrument that "blows up" in spikes; **avoid it.**

### Crash behavior (total return / max intra-episode drawdown) — THE BRUTAL BAR

| strategy | 2008 GFC | 2011 | Feb-18 Volmag. | 2018-Q4 | Mar-20 COVID | 2022 bear |
|---|---|---|---|---|---|---|
| **^PUT** | **−24.6% / −37%** | −3% / −15% | −2% / −7% | −11% / −15% | **−18.8% / −28%** | −10% / −16% |
| **^BXM** | **−27.9% / −40%** | −2% / −15% | −1% / −8% | −11% / −15% | −21.7% / −30% | −12% / −18% |
| PUTW | n/a | n/a | −2% / −8% | −12% / −15% | −19.9% / −28% | −11% / −17% |
| XYLD | n/a | n/a | −2% / −9% | −13% / −18% | −21.8% / −34% | −12% / −19% |
| QYLD | n/a | n/a | +2% / −7% | −13% / −19% | −16.4% / −25% | −20% / −24% |
| *SPY* | −43.9% / −55% | −4% / −18% | −2% / −10% | −14% / −19% | −17.2% / −34% | −18% / −25% |

**Honest assessment of the left tail:** put-write/covered-call **did NOT blow up** in 2008 or
COVID the way a *naked, unfunded, leveraged* short-vol book would — being cash-secured and
short ATM (not deep-OTM, not levered) caps the damage. **But it is not a hedge and not
crisis-resilient:** ^PUT lost **−25% in 2008** and **−19% in COVID**, capturing ~60–70% of
SPY's crash while forgoing the rebound (puts get assigned at the worst time, calls cap the
recovery). Feb-2018 "Volmageddon" barely scratched the cash-secured proxies (−2%) — that event
killed *levered* inverse-VIX ETNs (XIV, −96%), **not** ATM put-writers — which is exactly why
**SVOL/short-VIX-futures is the trap and PUTW/XYLD is the survivable form.**

---

## 3. Systematic strategies & the tail hedge

### (a) Cash-secured put writing — proxied by ^PUT / PUTW.
Sells 1-month ATM SPX puts, fully collateralized. Net Sharpe ~0.49–0.52, maxDD −28% (COVID)
to −37% (2008). **Not levered → survives, but no crisis alpha.**

### (b) Covered calls — XYLD (S&P) / QYLD (NDX).
Same VRP harvested on the call side. XYLD ≈ put-write (Sharpe 0.52). QYLD has the highest yield
but the worst 2022 (−20%, tech-heavy). No meaningful edge over (a).

### (c) Put-write + cheap tail hedge — DOES THE HEDGE HELP? **REAL VXX, 2018–2026, net 3bps/side:**

| config | CAGR | vol | **Sharpe** | maxDD | COVID TR / DD | 2022 TR / DD |
|---|---:|---:|---:|---:|---|---|
| PUTW + 0% VXX | 8.3% | 12.7% | **0.52** | −28.4% | −19.9% / −28% | −10.6% / −17% |
| PUTW + 3% VXX | 6.5% | 11.6% | 0.38 | −23.1% | −15.3% / −23% | −10.2% / −16% |
| PUTW + 5% VXX | 5.7% | 10.4% | 0.35 | −19.5% | −12.2% / −20% | −10.0% / −16% |
| PUTW + 10% VXX | 3.9% | 8.6% | 0.19 | −16.6% | **−4.1% / −11%** | −9.3% / −16% |
| PUTW + 15% VXX | 1.9% | 9.3% | −0.02 | −21.6% | **+4.3% / −11%** | −8.7% / −15% |

**Honest finding: a REAL long-vol (VXX) tail hedge REDUCES risk-adjusted return.** It does
exactly what insurance does — cuts the COVID drawdown from −28% to −11% (and at 15% even makes
COVID *positive*), but VXX bleeds ~50–60%/yr in calm markets, so it **drags Sharpe from 0.52
down to 0.19–0.35** and CAGR from 8% to 4%. **You pay more for the hedge in calm years than
you save in crashes.** This is the *opposite* of the seductive "synthetic hedge" backtest
(below) and is why I do not recommend a permanent VXX overlay.

> **Caveat — the synthetic-hedge artifact.** The script also runs a full-sample (1996+)
> *idealized* long-vol model (hedge return = max(0, ΔVIX) − bleed). It shows ^PUT + 10% synVol
> at **Sharpe 2.5, maxDD −13%, +32% in 2008**. **This is NOT tradeable and the high Sharpe is
> an artifact** — it assumes you capture VIX spot moves with a fixed bleed and zero slippage,
> which no real instrument delivers (VXX is the real thing, and it gave Sharpe 0.19). It is
> reported in `vol_premium.py` *only* to illustrate the *direction* (a hedge converts crash
> losses to crash gains); **the verdict rests on the REAL-VXX numbers.**

---

## 4. Small-bankroll feasibility ($1k–$10k)

| approach | min capital | options approval? | runnable at $1–10k? |
|---|---|---|---|
| Naked / cash-secured SPY put | ~**$50–60k** / contract | Yes (Level 2/3) | **NO** |
| Cash-secured QQQ / IWM put | ~$45k / ~$22k | Yes | **NO** (IWM marginal) |
| **PUTW / XYLD / QYLD ETF** | **1 share (~$20–55)** | **No** | **YES — fully** |
| SVOL ETF | 1 share | No | yes, but **don't** (Sharpe 0.28) |
| VXX (hedge leg) | 1 share | No | yes (as small overlay) |

**Concrete:** at $1k–$10k you **cannot** run a real options put-write program — one SPX/SPY
contract is ~$50–60k of collateral; even QQQ is ~$45k and IWM ~$22k, so a single contract
would be 200–600% of the account. **The only deployable form is the ETF wrapper** (PUTW for
put-write, XYLD for covered-call), which is **1-share-deployable (~$20–55), needs no options
approval, and harvests the same VRP** at a ~0.55–0.60% expense ratio (already in the NAV /
Sharpe above). That is the realistic instrument for this operator.

---

## 5. Diversification vs the momentum winner

**Monthly-return correlations** (long common window):

|  | MOM | ^PUT | ^BXM | PUTW | SPY |
|---|---|---|---|---|---|
| **MOM** | 1.00 | **0.33** | 0.29 | 0.42 | 0.39 |
| ^PUT | 0.33 | 1.00 | 0.91 | 0.50 | **0.83** |
| PUTW | 0.42 | 0.50 | 0.48 | 1.00 | 0.52 |

VRP-to-momentum correlation is **0.33** (decent), BUT VRP-to-SPY is **0.83** — and **in the
crashes the correlation goes to ~1.0** (both the put-writer and long-only momentum are short
the same equity tail). So the diversification looks better on paper than it pays in the only
moments that matter.

**Momentum + VRP combos (2007–2026, monthly reset, net):**

| blend | CAGR | vol | **Sharpe** | maxDD | 2008 | COVID | 2022 |
|---|---:|---:|---:|---:|---|---|---|
| 100% MOM (winner) | 10.4% | 11.4% | **0.80** | −16.1% | — | — | — |
| 100% VRP (^PUT) | 7.0% | 14.2% | 0.45 | −37.1% | −24.6% | −18.8% | −9.7% |
| **70 MOM / 30 VRP** | 9.5% | 10.3% | **0.81** | **−15.9%** | +2.4% | −11.5% | −4.5% |
| 60 MOM / 40 VRP | 9.2% | 10.2% | 0.78 | −17.2% | −1.8% | −12.5% | −5.2% |
| 50 MOM / 50 VRP | 8.9% | 10.4% | 0.73 | −20.1% | −5.8% | −13.6% | −5.9% |

**The honest diversification result:** adding VRP to momentum **does not improve Sharpe** —
70/30 ties the standalone winner (0.81 vs 0.80) and beyond ~30% VRP it *degrades* both Sharpe
and maxDD. The reason is the COVID column: every blend with meaningful VRP **deepens the COVID
drawdown** because VRP and long-only momentum both bleed in the same crash. VRP's slightly
lower 2008/2022 contribution (momentum's regime gate was in cash; VRP wasn't) is offset by its
COVID damage. **Conclusion: VRP is a near-neutral add at small weight, a drag at large weight.**

**The only configuration where the combo genuinely wins is with a crisis-alpha third leg.** A
**REAL-VXX three-leg (55 MOM / 35 PUTW / 10 VXX, 2018+)** caps the COVID drawdown to −8% but
costs Sharpe (0.27) due to the VXX bleed — i.e. you buy crash protection by giving up return,
the same trade-off as §3. (The script's full-sample 50/40/10 *synthetic*-vol version shows
Sharpe ~3.0 — **artifact, not tradeable, ignore it.**) The clean takeaway: **the momentum
winner's own 200-day regime gate is already cheaper crash protection than bolting VRP + a
permanent long-vol hedge onto the book.**

---

## 6. VERDICT

**Is the VRP a deployable, worth-adding US small-bankroll edge? — Mostly NO as a standalone;
a small optional satellite at best.**

- **Real & persistent:** yes — +3.7 vol-point premium, positive 83% of months. Genuine edge.
- **Deployable at $1k–$10k:** yes, but **only via ETFs (PUTW / XYLD)** — no options approval,
  1-share-deployable. A real options put-write program needs ~$50k/contract → **not runnable**
  at this size. SVOL/short-VIX-futures → **avoid** (Sharpe 0.28, blow-up risk).
- **Standalone quality:** **net Sharpe ~0.49–0.55, CAGR ~8%, maxDD −28% (COVID) to −37%
  (2008).** Strictly **dominated by the momentum winner** (0.80 / −16%) on both axes.
- **Diversification:** weak where it counts — 0.33 vs momentum but **0.83 vs SPY and ~1.0 in
  crashes.** 70 MOM / 30 VRP ties the winner's Sharpe (0.81) and DD (−16%); more VRP hurts.
- **Tail management:** a *real* VXX hedge cuts crash DD (COVID −28%→−11%) but **lowers Sharpe
  to 0.19–0.35** (you pay more in calm-year bleed than you save) — not worth a permanent
  overlay. The momentum sleeve's regime gate is cheaper crisis protection.

**Recommendation.** **Do not add VRP as a second standalone edge.** If the operator wants
options-income exposure for psychological diversification (a steady-paying, equity-like sleeve
that behaves differently month-to-month), **cap it at ~20–30% of the equity allocation via
PUTW**, run it *inside* the momentum book (whose regime gate provides the crash protection),
and **skip the standalone VXX hedge.** Expected net contribution at 30%: portfolio Sharpe
~0.81 (≈ unchanged), maxDD ~−16% (≈ unchanged), with marginally lower vol. **The VRP's headline
Sharpe is flattered by averaging over the calm 83% of months; the −37% 2008 and −28% COVID
drawdowns are the true cost, and they overlap momentum's worst months — so the diversification
benefit is largely illusory in the crashes that matter.** Momentum remains the project winner;
VRP is, at most, a small optional satellite, not a new edge.
