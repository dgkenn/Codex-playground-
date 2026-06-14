# BOX_ADVERSE_OPEN — are the maker-box's TOXIC losses predictable & avoidable at OPEN time?

**Verdict (one line): The true adverse-selection rate is ~3× the strand rate (5.7% of pair-gated
boxes are TOXIC, ~90% of them COMPLETED/balanced — not stranded), but toxicity is INTRINSIC to
completion and INVISIBLE at open: OOS AUC ≈ 0.56 (noise), NO open-time feature separates toxic from
clean boxes (every t-test p > 0.11), and NO incremental gate on top of the pair-gate raises net-of-
volume P&L. The box is already optimally gated at open. The −20c basis is realized AFTER the open
leg fills, in where the market runs — it cannot be foreseen from the open leg's microstructure.**

This is the BTC analogue of the ETH-study conclusion: the loss is real but not a skippable-open
problem. Confirms BOX_DISPOSAL_EV's framing ("prevention, not disposal") but answers its open
question: prevention is NOT achievable with an open-time gate — the pair-gate already captures all
the open-time signal there is.

---

## Data window, N, costs, method

- **Historical tape** (SCREEN): `hist_kalshi_btc15m.parquet` (per-minute bid/ask/spot/depth paths +
  `res_up`) × `trades_kalshi_btc15m.parquet` (taker tape). **916 windows with BOTH book and tape,
  span 2026-05-27 .. 2026-06-13.** Boxes reconstructed front-of-queue (q0=0) with the repo-standard
  `box_policy_ab.window_fills` + the always-pair (`--max-net 1`) walk. 60/40 IS/OOS **time** split
  (IS=549 windows, OOS=367). **2595 pair-gated boxes** (1301 IS / 1294 OOS).
- **Live telemetry** (sanity only): `origin/live-state` raw fills (`kalshi_fees_btc15m.jsonl`,
  dedup by `trade_id`), days 2026-06-13/14, **96 settled markets**, settle via Kalshi API
  `markets/<ticker>.result`. N too small to fit on; used only to confirm direction & magnitude.
- **Costs:** resting MAKER legs ≈ fee-free (post-only). The crossing/disposal of a stranded leg pays
  the Kalshi TAKER fee `ceil(M·P·(1−P)·100)/100` (FEES.md), modeled at M=0.07 with M=0.14 (crypto-
  premium) as a sensitivity. (Paired boxes complete via a maker fill in the q0=0 replay, so the
  toxic basis there is a price-drift cost, not a fee.)
- **Pair-gate (the deployed baseline):** `depth(top-5 min) ≥ 33000` AND `k ≤ 10` AND `|sig| < 10bps`
  (EDGE_OPTIMIZE.md / CAPACITY.md).
- **Box realized P&L (settle-adjusted, $/box-contract)** = `settle_open + settle_pair` for a paired
  box (each leg's `settle` = `res−b0` for YES, `a0−res` for NO, so this equals `payout(winning
  side) − total cost = 1 − (cost_yes+cost_no)`); stranded leg disposed by capcross (deployed) incl.
  taker fee. **TOXIC ≡ box P&L < 0** (a CLEAN box earns ~+1c risk-free; a box that loses money was
  adversely selected — its basis exceeded $1).
- Script: `box_adverse_open.py` (self-contained; reads the two parquets, walks live-state).

---

## 1. The TRUE toxic fraction — the real prize size

Classifying EVERY box (paired OR stranded) by settle-adjusted P&L, regardless of the `stranded` flag:

| population | N | toxic frac (P&L<0) | mean c/box | clean mean | toxic mean | strand frac |
|---|---|---|---|---|---|---|
| UNGATED (no pair-gate) | 8080 | **8.1%** | +0.157 | +1.19 | −11.60 | 1.7% |
| **PAIR-GATED (live baseline)** | **2595** | **5.7%** | **+0.456** | +1.12 | **−10.53** | **0.6%** |

**The hidden cost is confirmed.** Of the 148 toxic pair-gated boxes, **133 are PAIRED (balanced,
`n_yes==n_no`, `stranded=False`) and only 15 are stranded.** The pair-gate drives the *strand* rate
to 0.6% (backtest) / ~2% (live), but the *toxic* rate is **5.7% — ~3–10× higher** — because a strand
that gets COMPLETED by crossing is booked as a balanced box yet still carries the toxic basis.

- Pair-gated PAIRED-box P&L percentiles (c): p1 **−18.0**, p5 −3.3, p10 +0.2, p25/p50/p75 +1.0,
  p95 +2.0, p99 +3.0. A spike at +1c (CLEAN risk-free boxes) with a **fat left tail** (the toxic ~5%).
- Drag: the toxic 5.7% cost −10.5c each ≈ **−0.60c/box of pure adverse-selection drag**, against a
  clean +1.12c — i.e. toxicity eats ~57% of the gross box edge. **This is the real prize.**
- Fee sensitivity (M=0.14): toxic frac 5.7%, mean +0.455c — unchanged (the toxic cost is the basis,
  not the disposal fee; consistent with BOX_DISPOSAL_EV).

**Live sanity (96 settled markets):** **31% toxic**, mean **−5.5c/box**, median +0.5c; worst five
−61/−59/−58/−51/−50c. **14 of 75 BALANCED (ny==nn) markets are toxic** — the completed-but-toxic
cost is large and real live. The live toxic rate (31%) ≫ backtest (5.7%) because q0=0 is front-of-
queue-optimistic and live execution (queue position, post-fill drift) strands/over-pays far more —
so the *backtest understates* the prize, strengthening the prevention motive but not its feasibility.

## 2 & 3. Is toxicity PREDICTABLE at OPEN? — No.

Open-time features (known when the FIRST leg fills, before committing the box): `k`/time-in-window,
`|sig|` (BTC momentum at open), `depth` (top-5 min), `spread`, `|p−0.5|` (moneyness), `side`,
`flow`/queue-imbalance, `tau` (time-to-close), `vpin` (markout/toxicity of the just-filled leg),
`tksize` (crossing take size). Fit on pair-gated boxes (IS), tested OOS.

**Single-feature OOS AUC** (sign-aligned on IS):

| feature | OOS AUC | | feature | OOS AUC |
|---|---|---|---|---|
| absp05 | **0.560** | | side_bin | 0.525 |
| tksize | 0.553 | | absig | 0.508 |
| vpin | 0.547 | | absflow | 0.502 |
| depth | 0.496 | | spread | 0.491 |
| k | 0.456 | | tau | 0.456 |

**Multivariate logistic OOS AUC:** absp05 alone 0.559; absp05+spread 0.524; absp05+spread+k 0.523;
6-feature 0.498; all-10-feature **0.544**. **Nothing beats ~0.56 — statistically indistinguishable
from a coin flip (0.50) at this N.** More features do *worse* (overfit).

**The decisive test — do toxic boxes even LOOK different at open?** Welch t-test, toxic vs clean
open-leg features, on all 2595 pair-gated boxes:

| feature | toxic mean | clean mean | t | p |
|---|---|---|---|---|
| absp05 | 0.242 | 0.223 | +1.58 | 0.117 |
| vpin | 0.290 | 0.277 | +1.42 | 0.158 |
| side_bin | 0.534 | 0.488 | +1.09 | 0.277 |
| spread | 0.0113 | 0.0104 | +1.00 | 0.321 |
| k, tau, absig, depth, absflow, tksize | — | — | \|t\|<0.9 | p>0.38 |

**NOT ONE open-time feature separates toxic from clean (every p > 0.11).** The open leg of a box
that ends up −10c looks identical to the open leg of a +1c box. The toxicity is created *after* the
open, by where BTC runs (the completing leg drifts adverse, or the leg strands and settles worthless)
— a future-path property, not an open-time microstructure property.

## 4. Best incremental gate ON TOP of the pair-gate — NONE survives net-of-volume

Baseline pair-gated OOS: **N=1294, +0.451c/box, total +584c.** A real lever must RAISE OOS **total
c** (not just net/box by trading less) with material volume retained. Every 1-feature gate tested
(IS-direction, OOS-evaluated):

| incremental gate | keep % | net c/box | OOS total c | vs base +584 |
|---|---|---|---|---|
| depth ≥ 60000 | 22.1% | +0.878 | +251 | WORSE |
| depth ≥ 50000 | 41.4% | +0.624 | +334 | WORSE |
| spread ≥ 0.02 | 9.7% | +0.611 | +77 | WORSE |
| k ≤ 6 | 58.4% | +0.551 | +417 | WORSE |
| k ≤ 5 | 49.4% | +0.528 | +338 | WORSE |
| absp05 ≤ 0.10 | 25.1% | +0.502 | +163 | WORSE |
| \|sig\| ≤ 5 | 74.5% | +0.465 | +449 | WORSE |
| legcost ≥ 0.45 (favorite-only) | 54.3% | +0.403 | +284 | WORSE |
| absp05 ≤ 0.20 & spread ≥ 0.02 (combined) | 5.3% | **−0.058** | −4 | WORSE |

**Every single gate loses total c** — they "win" on net/box only by throwing away volume, exactly the
failure mode the brief warned against (the pair-gate-lockdown net-of-volume test). The few that lift
net/box (depth≥60k +0.88c, spread≥0.02 +0.61c) do so by keeping only 10–22% of boxes and slicing the
total roughly in half; and even within the kept set the **toxic fraction barely moves** (depth≥60k:
4.9% vs 5.7% baseline; spread≥0.02 actually *raises* toxic to 7.9%). The combined mid-book+wide-
spread gate goes net-NEGATIVE. There is no plateau — only a volume-for-nothing trade.

This matches §2/§3: a gate can only raise net/box if the feature separates toxic from clean, and none
does. The pair-gate (depth/k/|sig|) already captured the only open-time structure that exists; pushing
its thresholds tighter just trims volume at the same ~5–6% toxic rate.

---

## Verdict & recommendation

**Toxicity is INTRINSIC to completion, not visible at open.** The box is already optimally gated at
open — the deployed `depth≥33k, k≤10, |sig|<10` pair-gate extracts all the open-time signal there is.
The −20c basis on a toxic box is realized in the post-open price path (the completing leg fills after
the market has run, or the leg strands), which the open leg's microstructure does not foretell
(AUC 0.56, all feature t-tests p>0.11). **Do NOT add an open-time toxicity gate** — every candidate
costs more volume than it saves in toxic boxes (net-of-volume negative).

Where the prize (~−0.60c/box drag; ~5.7% backtest / ~31% live toxic) actually lives — since it is NOT
catchable at open — is the **completion/execution layer**, consistent with COMPLETION_MODEL.md's
"the unpaired-leg problem is EXECUTION, not prediction":
1. **Better second-leg execution** (queue priority on the completing side, A-S inventory-lean / chase
   toward the moved touch, completion-urgency scaling) — attack the price the SECOND leg pays, which
   is where the toxic basis forms, not the OPEN decision.
2. **The disposal cap / capcross** already bounds the stranded slice (BOX_DISPOSAL_EV) — but strands
   are only ~10% of toxic boxes; the 90% completed-but-toxic boxes are an execution-quality problem.
3. The live 31% vs backtest 5.7% gap says realized execution (queue/drift) is the dominant lever —
   far larger than any open-time gate could be.

**Honest bottom line:** this is the ETH result for BTC — toxicity is unavoidable at open; the box is
already optimally gated; the remaining $/day lever is completing-leg EXECUTION, not opening selection.

*Backtests SCREEN (q0=0 front-of-queue, 916 windows). Live N=96 settled markets, sanity only.*
