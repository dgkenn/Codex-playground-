# ETH-NATIVE Optimized Box Stack — Verdict

**Question tested:** Can the ETH 15-min crypto box be made net-PROFITABLE with a stack
optimized *specifically for ETH* (not the BTC-tuned ladder) — by (a) predicting & avoiding
the toxic negative-margin tail AT ENTRY and (b) aggressively cutting the unpaired leg?

**Verdict: NO. The toxic tail is INTRINSIC to completion (adverse selection), not predictable
at entry. The wide boxes cannot be harvested. The prior "ETH box is -EV" verdict STANDS.**
The only configurations that turn positive OOS do so by bolting a *directional ETH-perp bet*
onto the strand (a free leverage knob, not box arbitrage) — they are not deployable as box edge.

Method: IS = first 60%, OOS = last 40% of ETH 15-min windows (2,384 windows; 16,640 completed
boxes). Harness: `ladder_baseline_study.py` + `box_policy_ab.py`. Code: `eth_native_study.py`
(decomposition + entry classifier), `eth_native_stack.py` (stack sweep + thin-book + verdict).

---

## TASK 1 — Margin distribution: confirmed WIDE-positive with a TOXIC NEGATIVE TAIL

Completed-box lock margin (naked always-pair), ALL windows, n=16,640:

| stat | value |
|---|---|
| mean | **-1.11c** |
| median | **+1.00c** |
| std | 8.77c |
| neg-margin fraction | **24.6%** |
| positive fraction | 75.4% |
| p1 / p5 / p10 | -36.2c / -19.0c / -12.0c |
| p25 / p50 / p75 | +0.0c / +1.0c / +3.0c |
| p90 / p95 / p99 | +4.0c / +4.4c / +14.0c |

Confirmed: a tight WIDE-positive body (75% of boxes positive, median +1c, capped near +4c)
dragged negative by a fat left tail (p5 = -19c, p1 = -36c). Strand rate **40.7%** (OOS 38.1%).
The mean is negative *entirely because the toxic tail is much fatter than the positive body is
tall* — the upside is bounded (you can only lock the spread), the downside is not.

**Where the toxicity lives (entry-knowable slices, mean margin / neg%):**

| slice | n | mean | neg% | median |
|---|---|---|---|---|
| wide spread (>=2c) | 9,871 | -1.13c | 27.5% | +2.0c |
| wide spread (>=3c) | 5,706 | -0.84c | 28.1% | +3.0c |
| early k<5 | 6,086 | -1.38c | 26.6% | +1.0c |
| mid k5-9 | 7,909 | -1.43c | 26.9% | +1.0c |
| **late k>9** | 2,645 | **+0.44c** | 12.9% | +2.0c |
| non-fav <=0.70 | 7,197 | -2.24c | 27.6% | +1.0c |
| deep-fav >0.80 | 5,976 | **+0.40c** | 19.7% | +1.0c |

ETH's edge structure is INVERTED vs BTC (as the prior found): the only non-toxic slices are
**late-slot k>9 (+0.44c)** and **deep-favorite >0.80 (+0.40c)**. But note: *wider spread does
NOT mean cleaner* — wide boxes have HIGHER neg% (27.5% vs 20.3% for thin). The "wide boxes"
the hypothesis wants to harvest are exactly the *more* adversely-selected ones.

Toxic-vs-clean entry-feature separation is real but weak (|t|): depth -13.2, k -13.1,
tau +13.1, absdev/favp -13.0 — all of which say the same thing: *cheap, early, deep-book legs
that paired quickly*. These are correlates of "the box completed", which is the problem (Task 2).

---

## TASK 2 — Predictability at entry: the CRUX. Toxicity is NOT separable.

Entry-time classifier (GBM 200×depth-3 and logit) on 13 decision-time features
(spread, |dev|, favp, sig, |sig|, flow, |flow|, k, tau, vpin, depth, window |sig|, side),
label = 1 if completed box margin < 0. Fit on IS, evaluated on OOS:

| model | IS-AUC | **OOS-AUC** |
|---|---|---|
| GBM | 0.735 | **0.619** |
| Logit | 0.592 | **0.600** |

OOS-AUC ≈ 0.60 — barely above coin-flip. The IS→OOS collapse (0.735→0.619) is mostly
overfitting. **Toxicity is essentially NOT predictable at entry.**

The decisive evidence is the gate-calibration curve (OOS, keep boxes with predicted
P(toxic) ≤ threshold):

| keep threshold | boxes kept | keep % | mean margin | neg% |
|---|---|---|---|---|
| 1.00 (no gate) | 6,663 | 100% | -1.43c | 25.2% |
| 0.30 | 4,779 | 71.7% | -0.98c | 22.3% |
| 0.25 | 3,292 | 49.4% | -0.63c | 19.1% |
| **0.20** | 1,813 | **27.2%** | **-0.07c** | 14.1% |

Even after discarding **73% of all volume** to keep only the boxes the model is most confident
are clean, the surviving mean is **-0.07c** (still ~breakeven, still 14% toxic). You cannot get
to a *positive* mean at any threshold by gating at entry. This is the adverse-selection core:
**a box completes (both legs fill) PRECISELY when price ran far enough to fill the second leg —
the negative margin is a consequence of completion and is only knowable after the fact.** The
features that flag toxicity are the same ones that flag "this box will complete", so gating them
out just stops you from boxing at all. Hypothesis branch (a) FAILS.

---

## TASK 3 — ETH-native stack: best achievable (sweep ON ETH; fit IS, eval OOS)

P0 naked baseline: IS -10.18c (t=-15.0), OOS **-13.15c** (t=-15.5) per window. (Per-*window*
P0 is far worse than per-*box* mean because a window can fire many boxes + carries strand loss.)

**Positive-slice exploitation + ETH-tuned strand handling, OOS, box-completion only (no perp):**

| policy | net | Sharpe | t | win% | box/win | strand% |
|---|---|---|---|---|---|---|
| late-slot k>=10 | -2.14c | -0.148 | -4.58 | 41.3 | 1.51 | 24.0 |
| deep-fav >=0.85 | -1.01c | -0.094 | -2.91 | 49.9 | 2.86 | 32.8 |
| **k>=10 & fav>=0.80 & sell-cheap** | **-0.86c** | -0.091 | -2.80 | 39.8 | 1.03 | 20.5 |
| k>=11 & fav>=0.85 (max-purity) | -0.38c | -0.052 | -1.60 | 29.0 | 0.54 | 13.6 |
| GBM gate ≤0.20 & sell-cheap | -2.28c | -0.145 | -4.48 | 52.7 | 2.92 | 34.4 |

Sell-cheap thresholds (0.30/0.40/0.50) made **zero** difference on the favorable slice — those
deep-favorite legs never strand below 0.30, so there is nothing to cut. **Every pure
box-completion stack is negative OOS.** The most "purified" stack (k>=11 & fav>=0.85) reaches
only -0.38c at 0.54 box/win — trading almost nothing, and still losing.

**IS/OOS stability:** the best stacks straddle zero IS (+0.03c to +0.34c) and go negative OOS
(-0.38c to -0.86c). No stack is positive in BOTH halves. The tiny IS positives are noise.

### The perp-hedge "win" is a directional bet, not box edge

The ONLY way anything goes positive OOS is the cross-asset/perp hedge on the strand. Sweeping
the hedge size `h` (cents of ETH-perp delta per 1% move) exposes it as a pure leverage knob:

| h | NAKED book net / CVaR95 | SLICE (k>=10&fav>=0.80) net / Sharpe / t / CVaR95 |
|---|---|---|
| 0 (box only) | -13.15c / 79c | -0.85c / -0.081 / -2.49 / 27c |
| 150 | -8.96c / 81c | +0.93c / +0.076 / +2.35 / 29c |
| 300 | -4.77c / 99c | +2.71c / +0.139 / +4.29 / 37c |
| 600 | +3.60c / 148c | +6.26c / +0.166 / +5.13 / 59c |

Net rises **monotonically with h while CVaR rises in lockstep** — even the *naked* book turns
positive at h=600. That is the signature of a directional ETH-perp position whose expected
return scales with size, NOT of strand risk-reduction (which would saturate). The "edge" is
`sgn·h·r`: you short perp on a YES strand and ETH happened to drift favorably across this OOS
window. Funding, basis, and the perp's own variance are NOT in these numbers. Tuning `h` to a
positive t-stat is curve-fitting a momentum trade onto the box. It is not box arbitrage and is
not deployable as such.

---

## TASK 4 — Thin-book volume: even ignoring the above, there is no deployable volume

The only stacks that approach breakeven on box-completion alone do so by trading almost nothing:

- **k>=11 & fav>=0.85** (least-bad pure stack): **0.54 box/win** vs ~0.62 boxes/win completed by
  P0 — i.e. it suppresses ~13% of an already-thin opportunity set, leaving ~515 boxes over the
  whole 954-window OOS period, and STILL nets -0.38c (t=-1.60).
- ETH books are wide-spread and already conditional on a resting taker filling both legs; the
  gates compound that scarcity. A policy that is "near zero" only by boxing 0.5×/window is not
  deployable — it cannot cover infra/latency overhead and has no statistical edge (|t|<2).

A "positive" reading requires the perp overlay (Task 3), which trades the same ~1 box/win but
imports unmodeled directional risk. There is no regime where ETH delivers both positive
box-edge AND meaningful, defensible volume.

---

## TASK 5 — VERDICT

| | IS | OOS |
|---|---|---|
| P0 naked | -10.18c, Sharpe -0.397, t=-15.0 | **-13.15c, Sharpe -0.502, t=-15.5** |
| Best pure-box stack (k>=11 & fav>=0.85 & sc0.40) | -0.06c, t=-0.27 | **-0.38c, Sharpe -0.052, t=-1.60, 0.54 box/win, CVaR95 16.9c, PF 0.70, win 29%** |

**ETH boxes cannot be made net-positive and deployable by an ETH-native stack.** Reasons,
precisely:

1. **The toxic tail is intrinsic to completion, not gateable at entry.** Entry classifier
   OOS-AUC = 0.60; the best achievable surviving mean after gating 73% of volume is -0.07c.
   A box completes *because* price ran adversely — the loss is a consequence of the fill, not a
   predictable property of the entry. Hypothesis branch (a) fails.

2. **Cutting the unpaired leg does not help the harvestable slice.** On ETH's only clean slices
   (late-slot, deep-favorite) the strands are not cheap long-shots, so sell-cheap does nothing
   (-0.86c with or without it). Hypothesis branch (b) fails for box arbitrage.

3. **The wide boxes are MORE adversely selected, not less.** Wide-spread boxes carry higher
   neg% (27.5% vs 20.3%). The very thing the hypothesis wanted to exploit is the source of the
   tail.

4. **The only positive numbers come from a directional ETH-perp overlay** whose return scales
   one-for-one with leverage `h` (and with CVaR) — a momentum bet, not box edge, with unmodeled
   funding/basis. Not deployable as box arbitrage.

**Recommendation:** Do NOT deploy ETH boxes (native or laddered). Keep ETH box expansion CLOSED,
consistent with the prior verdict. If the operator wants the perp signal, it must be specced and
risk-budgeted as a *standalone directional ETH-perp strategy* with explicit funding/basis costs
and a leverage cap — evaluated on its own Sharpe, not laundered through a box that loses money.

*Backtests SCREEN only; any deployment requires forward (paper) validation. These results are a
single 60/40 IS/OOS split on historical ETH 15-min Kalshi tape with idealized box mechanics.*
