# Risk overlays for the long-only US-spot momentum sleeve — can the drawdown be cut without gutting the edge? (2026-06-14)

**Question.** The deployable long-only sleeve (MOM_LONGONLY.md, commit 78d934e) earns net
~25-30%/yr in up-regimes (forward Sharpe ~0.4-0.6) but carries a **−40% to −60% full-cycle
high-water-mark drawdown** — its one binding weakness and the thing that makes it hard to actually
hold at a small bankroll. This study tests **risk overlays** that target DD reduction *while
preserving Sharpe/return*. The base signal/cadence/gate are NOT re-searched.

**TL;DR verdict.** **The drawdown is the price of the edge.** Of the five overlay families
tested, **none improves return-per-unit-DD or Sharpe robustly out-of-sample.** Absolute/dual
momentum, faster/tiered de-risk gates, and per-position stops all **whipsaw the recent edge away**
(REC12 Sharpe falls). Vol-targeting *does* cut absolute DD cleanly at flat Sharpe — but it is
**indistinguishable from (slightly worse than) just sizing the sleeve smaller with a constant
fraction**; it adds no efficiency. The honest answer: **DD can only be reduced by holding less,
which scales return down one-for-one.** You can get recent-regime maxDD <30% (even <20%) at the
base Sharpe by downsizing, and the noisier **k=3** variant lifts REC12 Sharpe to ~0.70 — but
**full-cycle maxDD <30% is unreachable without cutting full-cycle return from ~71% to ~22%.**

---

## METHOD / BAR

- **Engine:** `mlo_risk.py` (reuses `mlo_backtest.py` data loader, signal, liquidity screen,
  gate). One configurable overlay backtest; each lever toggles independently and stacks.
  Study driver: `mlo_risk_study.py`. With all overlays off it **reproduces the base exactly**
  (FULL +1.12/+71%/−66%, REC12 +0.55/+27%/−28%).
- **Base (held fixed):** top-15 deep USD-spot (Coinbase daily, 2019-01-01→2026-06-14),
  risk-adjusted 10d momentum (ret/vol), top-5 EW + USDC cash, weekly, partial 0.7,
  BTC≥100d-MA gate → fully to cash.
- **Costs:** realistic US-spot taker **40 bps RT** (charged cost_bps/2 per unit |Δw|; stops
  charge an extra exit fee).
- **Windows:** **FULL** = full cycle 2019→2026; **REC12** = recent-12mo HARD holdout (the
  binding bar); **PREV12** = independent 24→12mo slice. Overlay params chosen IS-only and judged
  on REC12 + full-cycle, demanding a **plateau, not a spike**.
- **The brutal bar:** an overlay must improve **return/DD or Sharpe OOS, robustly across its
  parameter** — not merely lower vol (no Sharpe gain) or churn the edge away (worse net).
- **SCREENS:** Coinbase serves only currently-listed pairs → dead alts missing → **survivorship
  UP bias**. Single venue, single signal, ~7yr / ~53 weekly obs in REC12 → small-sample. Results
  are upper bounds; discount for decay.

---

## 1. VOL-TARGETING — cuts absolute DD at flat Sharpe, but it is just "size smaller"

Scale invested exposure by `min(max_lev, vol_target / realized_book_vol)` (trailing 20d book vol).

| Config | FULL Sh / ret / vol / maxDD | REC12 Sh / ret / maxDD | PREV12 Sh / ret / maxDD |
|---|---|---|---|
| BASE (no target) | +1.12 / +71% / 64% / **−66%** | +0.55 / +27% / **−28%** | +0.82 / +68% / −33% |
| vol_target 30% | +1.02 / +31% / 30% / −46% | +0.52 / +13% / **−16%** | +0.63 / +26% / −21% |
| vol_target 40% | +1.04 / +40% / 39% / −53% | +0.52 / +17% / −21% | +0.63 / +35% / −27% |
| vol_target 50% | +1.06 / +49% / 47% / −57% | +0.55 / +22% / −25% | +0.66 / +44% / −30% |
| vol_target 60% | +1.08 / +56% / 56% / −61% | +0.58 / +26% / −28% | +0.68 / +49% / −31% |

Smooth plateau across 30-60% and across vol_lb 10/20/30 (robust, not a spike). DD falls
monotonically as the target tightens, Sharpe stays ~flat (+0.52 to +0.58 REC12). **So far it
looks like a DD win.** But the brutal bar asks for **return/DD efficiency**, and there it fails:

| | REC12 ret/|DD| | FULL ret/|DD| |
|---|---|---|
| BASE | **0.96** | **1.08** |
| vol_target 30% | 0.82 | 0.67 |

The ratio gets *worse* — DD is given up only in proportion to the return surrendered.

**Decisive test — dynamic vol-target vs static constant downsizing (matched full-sample vol 30%):**

| | FULL Sh / ret / maxDD | REC12 Sh / ret / maxDD |
|---|---|---|
| STATIC const-scale (c=0.47) | **+1.12 / +34% / −38%** | **+0.55 / +13% / −14%** |
| DYNAMIC vol-target 30% | +1.02 / +31% / −46% | +0.52 / +13% / −16% |

**Static downsizing dominates dynamic vol-targeting on every metric** (same vol, better Sharpe,
better DD). The vol-scaler lags the realized-vol spike and chases its own tail, costing a little.
**Verdict: vol-targeting earns no place — its only effect (lower absolute DD) is achieved more
cheaply by just holding a constant smaller fraction.**

---

## 2. ABSOLUTE / DUAL MOMENTUM — FAILS the binding holdout (whipsaws the recent edge)

Hold a top-ranked name only if its OWN trailing 10d return exceeds a threshold (0 / 2% / 5%), or
exceeds BTC's own 10d return (dual).

| Config | FULL Sh / ret / maxDD | REC12 Sh / ret / maxDD | PREV12 Sh |
|---|---|---|---|
| BASE | +1.12 / +71% / −66% | **+0.55 / +27% / −28%** | +0.82 |
| own > 0% | +1.15 / +64% / −55% | **+0.35** / +15% / −33% | +1.11 |
| own > 2% | +1.14 / +59% / −52% | +0.35 / +14% / −33% | +1.04 |
| own > 5% | +1.06 / +50% / −48% | **−0.04** / −2% / −34% | +1.08 |
| own > BTC (dual) | +0.94 / +45% / −69% | +0.54 / +23% / −28% | +1.02 |

The absolute filter improves FULL DD modestly and lifts PREV12 — but on the **REC12 hard
holdout it cuts Sharpe (0.55→0.35) and *worsens* DD (−28→−33)**, and the dual variant is neutral
at best. In the 2024-25 chop, "wait for your own name to turn positive" sells the bottom and buys
the bounce late. **This confirms the warning that own-equity / own-return streak timing fails for
this momentum book — it is rejected for long-only too.** Not a DD lever.

---

## 3. FASTER / TIERED DE-RISK — FAILS the holdout (fast gate whipsaws)

Stack a fast BTC≥(20/30/50)d-MA gate on the slow 100d gate: binary (→cash) or tiered (→×0.5).

| Config | FULL Sh / maxDD | REC12 Sh / ret / maxDD | PREV12 Sh |
|---|---|---|---|
| BASE | +1.12 / −66% | **+0.55 / +27% / −28%** | +0.82 |
| +fast<20 binary | +1.03 / −48% | +0.02 / +1% / −31% | +0.84 |
| +fast<30 binary | +1.14 / −48% | **−0.07** / −3% / −34% | +0.88 |
| +fast<50 binary | +1.18 / −53% | +0.27 / +12% / −29% | +0.78 |
| +fast<20 tier0.5 | +1.11 / −55% | +0.33 / +14% / −29% | +0.84 |
| +fast<50 tier0.5 | +1.16 / −57% | +0.42 / +20% / −28% | +0.80 |

Binary fast gates **destroy REC12 Sharpe** (down to ~0 or negative); tiered de-risk is less
destructive but still leaves every config **below the base REC12 Sharpe with no DD-per-return
gain**. The fast signal flips in and out of the 2024-25 chop and bleeds the edge. The slow
100d gate is already the robust knee (per the base study); a faster overlay does not beat it.
**Tiered beats binary (scale-out > binary), but neither earns its place.** Rejected.

---

## 4. CONCENTRATION — not a DD lever; k=3 is a (noisy) RETURN lever; caps are inert

| Config | FULL Sh / ret / maxDD | REC12 Sh / ret / maxDD | PREV12 Sh |
|---|---|---|---|
| k=2 | +1.17 / — / −69% | +0.61 / +32% / −31% | — |
| **k=3** | +1.12 / +78% / −67% | **+0.70 / +37% / −27%** | +0.63 |
| k=4 | +1.09 / — / −69% | +0.48 / +24% / −27% | — |
| k=5 (BASE) | +1.12 / +71% / −66% | +0.55 / +27% / −28% | +0.82 |
| k=6 | +1.07 / — / −65% | +0.67 / +32% / −23% | — |
| k=7 | +1.00 / +61% / −66% | +0.53 / +24% / −23% | +0.66 |
| k=10 | +0.96 / +58% / −65% | +0.26 / +11% / −24% | +0.36 |
| per-name cap 25/30/40% @k5 | +1.12 / +71% / −66% | +0.55 / +27% / −28% | +0.82 |

- **Diversifying UP (k7→k10) trims REC12 DD a few points but kills Sharpe** (k10: REC12 0.26) —
  a bad trade. The single-name DD contribution is small relative to the systematic crypto-beta
  DD; spreading wider just dilutes the signal. **Concentration is not the DD driver.**
- **Per-name caps are completely inert** — top-5 EW already caps each name at 0.20, below any
  tested cap. Nothing to redistribute.
- **k=3 lifts REC12 Sharpe (0.55→0.70) and return (+27→+37%)** at similar DD — but the k-curve
  is **bumpy** (k=4 dips to 0.48, PREV12 for k=3 is only 0.63 vs base 0.82). It is a real but
  **noisy return lever, not a robust DD reduction**; the base study deliberately chose k=5 for
  small-size diversification. Use k=3 only if you accept higher single-name noise.

---

## 5. PER-POSITION TRAILING / TIME STOP — whipsaws the edge away

Walk daily inside each weekly hold; exit a name to cash if it draws down `stop_pct` from its
in-trade high (trailing) or is below entry after `d` days (time).

| Config | FULL Sh / maxDD | REC12 Sh / ret / maxDD | PREV12 Sh |
|---|---|---|---|
| BASE | +1.12 / −66% | **+0.55 / +27% / −28%** | +0.82 |
| trail 10% | +0.93 / −67% | +0.13 / +6% / −31% | +0.82 |
| trail 15% | +0.97 / −70% | +0.42 / +21% / −32% | +0.74 |
| trail 20% | +1.10 / −66% | +0.50 / +25% / −30% | +0.76 |
| trail 25% | +1.10 / −67% | +0.46 / +23% / −30% | +0.80 |
| time stop 3d | +1.09 / −61% | +0.18 / +9% / −27% | +0.86 |
| time stop 5d | +1.17 / −59% | +0.33 / +16% / −25% | +0.77 |

Tight stops (10-15%) **gut REC12 Sharpe**; loose stops (20-25%) are nearly inert (rarely hit) and
still don't help DD. Time stops hurt. **Stops do not cut tail DD — they churn the edge.**
Rejected — exactly the whipsaw failure mode the bar warned against.

---

## 6. BEST COMBINED CONFIG — downsizing is the only honest DD control

Since every *dynamic* overlay fails the brutal bar, the only thing that reduces DD without
destroying Sharpe is **holding a constant smaller fraction** (the rest in extra cash). Optionally
combine with **k=3** for its modest REC12 Sharpe lift.

**Static downsize family on base k=5 (Sharpe invariant; DD and return scale together):**

| Target vol | scale c | FULL Sh / ret / maxDD | REC12 Sh / ret / maxDD |
|---|---|---|---|
| 50% | 0.79 | +1.12 / +56% / −56% | +0.55 / +21% / −22% |
| 40% | 0.63 | +1.12 / +45% / −47% | +0.55 / +17% / −18% |
| 30% | 0.47 | +1.12 / +34% / −38% | +0.55 / +13% / −14% |
| 25% | 0.39 | +1.12 / +28% / **−32%** | +0.55 / +10% / **−11%** |
| 20% | 0.31 | +1.12 / +22% / **−26%** | +0.55 / +8% / −9% |

**BEST RISK-MANAGED CONFIG: base k=3, statically scaled to ~40% target vol (c≈0.57):**

| Window | Sharpe | ann ret | vol | maxDD |
|---|---|---|---|---|
| FULL (full cycle) | **+1.12** | +45% | 40% | **−45%** |
| REC12 (recent holdout) | **+0.70** | +21% | 31% | **−16%** |
| PREV12 | +0.64 | +26% | 40% | −21% |

vs base k=5 full-size (FULL +1.12/+71%/−66%, REC12 +0.55/+27%/−28%): **recent-regime maxDD cut
from −28% to −16% and REC12 Sharpe lifted to +0.70**, at the cost of ~⅓ of the gross return
(the downsizing). **Recent-regime target (Sharpe ≥0.6, maxDD <30%) is achieved.**

**Full-cycle target (maxDD <30%) is NOT reachable without gutting return:** the only way to get
FULL maxDD under 30% is to downsize to ~20% target vol (c≈0.31), which cuts full-cycle return
from ~71% to ~22%. That is the brutal-bar definition of trading return for DD with no efficiency
gain.

---

## VERDICT — DD is the price of the edge

**The full-cycle drawdown of the long-only momentum sleeve is essentially irreducible without
sizing it down.** None of the five overlay families — vol-targeting, absolute/dual momentum,
faster/tiered de-risk, concentration, per-position stops — improves **return-per-DD or Sharpe
robustly out-of-sample**:

- **Absolute/dual momentum, faster gates, and stops all FAIL the REC12 holdout** — they whipsaw
  the recent edge away (Sharpe drops), confirming that own-return / fast-trend / stop timing does
  not work for this book any better than the regime study found for L/S.
- **Vol-targeting cuts absolute DD at flat Sharpe, but is strictly dominated by static
  downsizing** — it adds no efficiency, only complexity.
- **Concentration is not a DD driver** (single-name DD is small vs systematic crypto-beta DD);
  caps are inert; **k=3 is a noisy return/Sharpe lever, not a DD fix.**

**Achievable risk-managed sleeve:** run **base k=3** (or k=5 for diversification) and **size the
whole sleeve to your DD tolerance via a constant scale** — the rest in cash. This delivers, on
the recent hard holdout, **Sharpe ≈0.70 (k=3) / 0.55 (k=5) with maxDD ≈ −16% at ~40% target vol,
or −11% at ~25% target vol** — meeting *recent-regime* Sharpe ≥0.6, maxDD <30%. But across a
**full bear cycle the maxDD is still ~−45% at that size**, and pushing full-cycle DD under 30%
requires shrinking return roughly proportionally (to ~22% from ~71%).

**Bottom line: the sleeve is inherently volatile and must be sized small.** There is no clever
overlay that buys you a better Sharpe-per-DD; the regime gate (already in the base) did the one
thing that works — it caps the catastrophic bear. Beyond that, **the deep high-water-mark
drawdown is the cost of having no short leg, and the only honest control is position size.**
Discount the headline Sharpe to **forward ~0.4-0.6** for decay + survivorship, and size the
sleeve so that a −45% full-cycle paper drawdown is tolerable at your bankroll.
