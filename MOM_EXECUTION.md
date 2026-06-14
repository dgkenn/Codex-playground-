# Cross-Sectional Crypto Momentum — EXECUTION COST, TURNOVER & CAPACITY

**Date:** 2026-06-14 · **Branch:** claude/polymarket-bot-live-ready-vw7ut5
**Scope (per task split):** execution realism only — rebalance-frequency sweep, turnover
reduction, live perp-book cost model, capacity curve, maker-vs-taker. Signal/universe search
NOT redone (owned by sibling `MOM_SIGNAL.md`). Risk overlays owned by `MOMENTUM_DEPLOY.md`.

## TL;DR — VERDICT

The ~1.0–1.5 OOS Sharpe is real at *small* size but **dies fast with AUM, and the binding
constraint is the thin-book alts inside the top-15, not the cost bar.**

- **Best cadence = WEEKLY, unambiguously.** Daily/2x-week get eaten by turnover×frequency;
  biweekly/monthly lose the recent edge (the 10d signal decays). Weekly is the cost/decay sweet spot.
- **Realistic small-size cost is ~23 bps round-trip per unit turnover, NOT 7–12 bps.** That
  headline only holds for BTC/ETH-style fills; an equal-weight top-15 book forces equal dollars
  into NEAR/TON/FIL/ADA whose live spreads alone are 5–9 bps. Cost is dominated by the thin alts.
- **Capacity (live walk-the-book): net Sharpe HALVES at ~$3.4M AUM, hits ZERO at ~$6M** for the
  raw weekly book. **Turnover reduction (partial-rebalance 0.7) pushes this to halve@~$4.5M,
  zero@~$7.8M** — ~30% more capacity — and *improves* the robust independent-window Sharpe.
- **Maker execution is a marginal help only (~1–2 bps saved on liquid coins).** Adverse selection
  + non-fill chase erode most of it at weekly cadence. Plan to be a taker; treat maker as a small bonus.
- **Deployable size: ~$1–3M.** At $1M the edge is ~90% intact; at $3M it is roughly halved; do not
  exceed ~$5M on this top-15 perp universe. This corroborates the sibling deploy spec ($3–6M) from
  an independent, live-order-book direction.

---

## Window, universe & cost assumptions

| | |
|---|---|
| **OHLCV** | OKX daily candles (`1Dutc`), 2020-01-01 → 2026-06-13 (`mom_data.parquet`, sibling). |
| **Signal (locked)** | risk-adjusted 10d momentum (ret/trailing-vol), top-15 liquid USDT perps, dollar-neutral long-top-30%/short-bottom-30%, equal-weight. |
| **Holdout** | **REC12** = recent 12mo (headline) · **PREV12** = prior independent 12mo · OOS18 = last 18mo. Sharpe annualized ×√(365/hold_days). |
| **Live books** | OKX public `/market/books` (400 levels), 5 snapshots ×4s avg, 2026-06-14. Size in contracts → USD = price×size×ctVal. Walk-the-book per side; floor = ½ spread. |
| **Funding** | OKX `funding-rate-history` (recent ~100 events/coin), netted into the dollar-neutral book. |
| **Cost (freq sweep)** | flat 10 bps round-trip / unit \|Δw\| (mid of the 7–12bps bar). **Capacity section replaces this with the live book curve + 5 bps taker.** |
| **Bar** | cloud bot, seconds latency, NOT HFT — a book snapshot ≈ what we'd hit. Backtests SCREEN. |

Survivorship caveat inherited from sibling: OKX serves only currently-listed instruments →
absolute Sharpe is biased **up**; treat REC12 2.0+ as optimistic, forward ~1.0–1.5.

---

## 1. Rebalance-frequency sweep

riskadj-10d, top-15, equal-wt, 30% tails, 10 bps RT/unit turnover. Turnover is **per rebalance**.

| cadence | turn/rebal | gross REC12 | **net REC12** | net OOS18 | net PREV12 | ann REC12 |
|---|---|---|---|---|---|---|
| daily | 1.05 | 1.15 | 0.20 | -0.87 | -0.59 | +8% |
| 2x-week | 1.72 | 1.88 | 1.35 | -0.08 | -0.25 | +50% |
| **weekly** | **2.43** | **2.62** | **2.31** | **1.16** | **1.37** | **+82%** |
| biweekly | 2.93 | 0.41 | 0.23 | 0.91 | 2.35 | +10% |
| monthly | 3.09 | 1.37 | 1.29 | 0.77 | 0.45 | +54% |

**Reads.**
- **Daily is dead.** Per-rebalance turnover looks low (1.05) but it rebalances ~52×/yr more often
  → ~5× the annual churn; the 10d signal barely refreshes day-to-day, so it pays cost for noise.
  Gross 1.15 → net 0.20 is almost pure cost erosion.
- **2x-week** keeps gross but net REC12 drops to 1.35 and both independent windows go negative — not robust.
- **Weekly is the sweet spot**: highest net REC12 (2.31), and the only cadence positive on **both**
  independent windows (OOS18 +1.16, PREV12 +1.37). Turnover 2.43 is the signal's natural churn rate.
- **Biweekly/monthly**: signal decays past ~7–10d hold, so gross collapses (biweekly gross 0.41).
  Monthly partially recovers but its windows disagree (REC12 1.29 vs PREV12 0.45) — not stable.

**Cost/decay sweet spot = WEEKLY.** Faster = cost-dominated; slower = signal-decay-dominated.

---

## 2. Turnover reduction (weekly base; turn 2.43, REC12 2.31, PREV12 1.37, OOS18 1.16)

| method | turn | net REC12 | net PREV12 | net OOS18 |
|---|---|---|---|---|
| baseline | 2.43 | 2.31 | 1.37 | 1.16 |
| no-trade band 0.07 | 2.16 | 1.45 | **1.76** | 0.63 |
| no-trade band 0.13 | 2.14 | 1.45 | **1.76** | 0.63 |
| no-trade band 0.20 | 1.77 | 1.40 | 0.70 | 0.05 |
| EMA smooth α=0.6 | 1.98 | 1.36 | **1.84** | 1.16 |
| EMA smooth α=0.4 | 1.63 | 0.80 | 0.60 | 0.34 |
| **partial 0.5** | **1.24** | 1.15 | 1.57 | 0.95 |
| **partial 0.7** | **1.74** | **1.58** | **1.61** | 1.02 |
| band0.13 + EMA0.5 | 1.58 | 0.73 | 1.76 | 0.72 |
| band0.13 + partial0.7 | 1.63 | 0.71 | 1.58 | 0.50 |

**Reads (honest).**
- The baseline REC12 of 2.31 is a **high-variance favorable window** — every turnover-reduction
  method lowers it, which tells you part of that 2.31 is luck the raw signal happened to nail.
- The right way to judge is the **independent PREV12 window**: there, *every* mild-reduction method
  **improves** on baseline (1.37 → 1.6–1.8). So turnover reduction is genuinely net-positive on
  out-of-sample-robust terms; it trades a bit of the lucky-window peak for stability + lower cost.
- **partial-rebalance 0.7 is the standout** — trade only 70% of the gap to target each week:
  turnover 2.43 → 1.74 (**−28%**), REC12 1.58, PREV12 1.61 (both solid). It is the only method that
  cuts turnover materially *and* holds both windows up.
- **EMA α=0.6** is the runner-up (turn −18%, PREV12 1.84, OOS18 unchanged at 1.16).
- No-trade bands cut turnover and lift PREV12 but hurt OOS18; aggressive combos (band+EMA, band+partial)
  over-smooth and kill REC12. **Don't stack them.** Pick ONE mild lever: partial 0.7.

**Net-Sharpe improvement:** on the robust window, partial-0.7 raises PREV12 from 1.37 to 1.61
(+0.24) while cutting turnover 28%; the cost saving is the bigger prize and shows up as capacity (§4).

---

## 3. Realistic cost model from LIVE OKX perp order books

Walk-the-book **one-way slippage (bps vs mid, avg of buy & sell)** to trade a given USD notional in
a single coin, OKX live 2026-06-14 (5-snapshot avg, 400 levels), floored at ½ spread:

| coin | spread bps | $10k | $50k | $100k | $500k | $1M | $5M |
|---|---|---|---|---|---|---|---|
| BTC | 0.02 | 0.0 | 0.0 | 0.0 | 0.3 | 0.7 | 3.0 |
| ETH | 0.06 | 0.0 | 0.0 | 0.0 | 0.4 | 0.8 | 3.1 |
| SOL | 1.48 | 0.9 | 1.0 | 1.3 | 3.0 | 5.3 | 25.7 |
| DOGE | 1.16 | 0.6 | 0.9 | 1.3 | 3.6 | 7.1 | 31.6 |
| XRP | 8.81 | 4.4 | 4.4 | 4.4 | 6.1 | 9.7 | 34.2 |
| NEAR | 4.81 | 3.9 | 7.0 | 10.6 | 46.9 | 128.2 | 399.9 |
| SUI | 1.33 | 1.5 | 3.0 | 4.1 | 12.1 | 26.7 | 113.7 |
| TON | 5.84 | 5.9 | 12.7 | 19.7 | 106.0 | 369.9 | 471.8 |
| BNB | 1.66 | 1.0 | 1.8 | 2.5 | 6.7 | 11.1 | 96.4 |
| ADA | 6.01 | 3.0 | 5.2 | 7.4 | 26.5 | 65.8 | 443.2 |
| FIL | 1.32 | 2.7 | 6.3 | 9.9 | 43.2 | 151.5 | 158.9 |
| BCH | 4.97 | 3.5 | 6.2 | 8.4 | 30.2 | 83.9 | 413.1 |
| LINK | 1.28 | 1.0 | 2.7 | 4.5 | 14.4 | 32.5 | 167.3 |
| XLM | 0.55 | 2.4 | 5.4 | 8.2 | 36.2 | 74.2 | 74.2 |
| LTC | 2.27 | 2.3 | 4.4 | 6.4 | 18.6 | 38.6 | 246.0 |

Plus **5 bps taker fee** one-way (OKX perp). Funding-while-holding on the dollar-neutral book =
**−0.9%/yr** in the current snapshot (TON/BCH carry negative funding; the long-momentum leg pays
slightly more than the short leg receives) — a small drag, effectively a wash, consistent with sibling.

**The decisive point:** BTC/ETH are essentially free (<1 bp to $500k). But the equal-weight top-15
puts the *same dollar* into TON (19.7 bps @ $100k), NEAR (10.6), FIL (9.9), ADA (7.4), XLM (8.2).
The book-weighted **average RT cost at small size is ~23 bps**, not 7–12. The thin alts set the price.
Top-of-book USD depth ranges from ~$130k (BTC/ETH) down to **$0.4k–$3k (XLM, SUI, FIL, LTC, TON)** —
the alts have paper-thin tops and you walk many levels for even $50k.

---

## 4. Capacity curve — net REC12 Sharpe vs AUM (weekly, live-book cost + funding)

Per-coin traded notional per rebalance = AUM × \|Δweight\|. Equal-weight top-15/30% ⇒ each leg
≈ 0.20 of one side; gross book = 2×AUM.

| AUM | avg RT cost (bps) | net REC12 Sharpe | ann REC12 |
|---|---|---|---|
| $10k | 23.5 | 2.05 | +73% |
| $100k | 24.2 | 2.03 | +72% |
| $500k | 26.3 | 1.96 | +70% |
| **$1M** | 29.1 | **1.88** | +67% |
| $2.5M | 43.9 | 1.42 | +50% |
| **$3.4M** | ~55 | **~1.03 (HALF)** | — |
| $5M | 73.7 | 0.31 | +11% |
| **$6.0M** | ~90 | **~0.00 (ZERO)** | — |
| $10M | 112.7 | -1.26 | -45% |
| $25M | 128.4 | -1.87 | -66% |
| $50M+ | 158+ | deeply negative | — |

- **Small-size REC12 Sharpe ≈ 2.05** (≈1.0–1.5 forward after survivorship discount).
- **Halves at ~$3.4M; zero at ~$6.0M.** By $10M the strategy is a money-loser purely on slippage.

### Per-coin binding capacity (AUM where a full 0.20-weight entry costs >15 bps one-way)

| coin | cap | coin | cap | coin | cap |
|---|---|---|---|---|---|
| BTC | $630M | ETH | $374M | SOL | $15.5M |
| DOGE | $11.0M | XRP | $9.8M | BNB | $6.9M |
| LINK | $2.6M | LTC | $1.9M | ADA | $1.4M |
| BCH | $1.4M | XLM | $1.1M | NEAR | $0.9M |
| FIL | $0.9M | SUI | $3.1M | **TON** | **$0.3M** |

**TON ($0.3M), NEAR/FIL ($0.9M), XLM ($1.1M), ADA/BCH ($1.4M) bind the book.** These are exactly
the small-cap perps with shallow books — the thin-universe constraint the task flagged. BTC/ETH
could absorb hundreds of millions, but a *dollar-neutral cross-sectional* book must trade all 15.

### Does turnover reduction buy capacity? (YES)

| config | turn | small REC12 | PREV12 | halves @ | zero @ |
|---|---|---|---|---|---|
| baseline | 2.43 | 2.05 | 1.15 | $3.4M | $6.0M |
| **partial 0.7** | 1.74 | 1.34 | **1.41** | **$4.5M** | **$7.8M** |
| EMA 0.6 | 1.98 | 1.15 | 1.67 | $3.1M | $5.0M |
| band 0.13 | 2.14 | 1.22 | 1.55 | $2.6M | $4.2M |

**partial-0.7 extends capacity ~30%** (halve $3.4M→$4.5M, zero $6.0M→$7.8M) by churning less
notional through the thin alts, while raising the robust PREV12 Sharpe. EMA/band trim turnover but
their REC12 erosion offsets the cost saving, so they don't extend the *zero* point as well. **Use
partial-rebalance 0.7 as the standing execution policy** — it is both the turnover and capacity winner.

---

## 5. Maker vs taker (weekly cadence)

Rest a limit at the touch instead of crossing. Model: maker captures the half-spread + saved taker
fee, minus fill-probability-weighted adverse selection (signal-driven: the coin you want to buy
tends to keep rising) and a non-fill **chase** penalty (miss → take later, worse).

| coin | spread | taker one-way | maker effective | saving | p_fill |
|---|---|---|---|---|---|
| BTC | 0.02 | 5.0 | 3.8 | +1.2 | 0.60 |
| ETH | 0.06 | 5.0 | 3.8 | +1.2 | 0.60 |
| SOL | 1.48 | 6.3 | 4.8 | +1.5 | 0.60 |
| XRP | 8.81 | 9.4 | 9.3 | +0.2 | 0.45 |
| ADA | 6.01 | 12.4 | 10.3 | +2.1 | 0.45 |
| TON | 5.84 | 24.8 | 17.0 | +7.7 | 0.45 |

**Reads.** On liquid coins (BTC/ETH/SOL) maker saves only ~1–2 bps — the spread is already near
zero, so there's little to capture, and adverse selection eats the rest. On thin alts the headline
saving looks bigger (TON +7.7) but fill probability is lower (~0.45) and a missed rebalance on a
momentum name is costly (you chase a moving price). **Conclusion: maker is a marginal optimisation,
not a capacity unlock.** Plan as a taker (the §3/§4 cost model assumes taker). A *passive-first,
cross-after-T-seconds* execution that posts at the touch and chases unfilled remainder can shave
maybe 1–3 bps RT on average — worth doing, worth ~$0.5–1M of extra effective capacity, but it does
NOT change the order of magnitude. Adverse selection + non-fill force the taker for the bulk.

---

## DEPLOYABLE-SIZE RECOMMENDATION

| Parameter | Value |
|---|---|
| **Cadence** | **WEEKLY** (cost/decay sweet spot; daily cost-dead, biweekly+ signal-decayed) |
| **Execution policy** | **Partial-rebalance 0.7** (trade 70% of gap to target) — cuts turnover 28%, raises robust Sharpe, +30% capacity. Optionally EMA-0.6 smoothing as an alternative. |
| **Order type** | Taker baseline; passive-first-then-chase to shave ~1–3 bps. Do NOT rely on maker fills. |
| **Cost to budget** | **~23–30 bps RT/unit turnover at ≤$1M** (thin-alt-dominated), NOT 7–12. Alarm if realized >40 bps. |
| **Deployable AUM** | **$1–3M.** At $1M edge ~90% intact (Sharpe ~1.9 small / ~1.0–1.5 forward); **edge halves at ~$3.4M (raw) / ~$4.5M (partial-0.7)**; **hard-cap ~$5M.** Zero by ~$6–8M. |
| **Binding constraint** | thin-book alts inside top-15 (TON $0.3M, NEAR/FIL $0.9M, XLM/ADA/BCH ~$1–1.4M) — not the cost bar, not BTC/ETH. |

**Forward expectation at $1M, weekly, partial-0.7, taker, live-book cost:** net Sharpe ~1.0–1.5
(survivorship-discounted), ann ~50–70% at small size scaling down with AUM per the curve. **The
~1.0–1.5 OOS Sharpe survives only at ≤~$3M; beyond that, thin-alt slippage halves it.**

## Files
- `mom_exec_fetch.py` — live OKX perp book (walk-the-book) + funding fetcher (→ /tmp/exec_data, non-repo).
- `mom_exec.py` — rebalance-frequency sweep + turnover-reduction engine (bands/EMA/partial), reuses sibling `mom_backtest.py`.
- `mom_capacity.py` — live-book cost-vs-size model, capacity curve (net Sharpe vs AUM), per-coin binding caps, maker/taker.
- Data parquet/JSON staged to `/tmp/exec_data` and `/tmp/mom_signal` — NOT committed.
