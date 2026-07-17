# Conditional Longshot Short-Vol Edge — Sub-Slice Hunt

**Goal:** Find an entry-time selector that isolates a *much* more overpriced
sub-population of far-OTM weekly BTC/ETH longshots (target: 2x+ the edge, still
positive at realistic YES-buy-volume-weighted fills, surviving out-of-sample).

**Data:** `scratchpad/advsel_rows.json` — 601 settled markets, entry YES-mid in
[0.15, 0.30], 49 ISO-weeks. Seller PnL/contract = `(entry − half_spread) − yes_win`,
zero fee. **TRAIN = first 60% of weeks (29 wks, 413 mkts); TEST = last 40% (20 wks,
188 mkts).** t-stats are **week-clustered** (cluster-robust SE, G/(G−1) corrected).
`eq` = equal-weight; `bv` = YES-buy-shares-weighted (the realistic-fill metric —
you fill in proportion to how much YES buying there is).

## Baseline (unconditional)

| slice | n | eq mean | eq t | bv mean | bv t | worst wk (eq) |
|---|---|---|---|---|---|---|
| ALL   | 601 | +10.57c | 4.27 | +11.97c | 4.62 | −43.5c |
| TRAIN | 413 | +10.50c | 3.19 | +11.57c | 3.54 | −43.5c |
| TEST  | 188 | +10.71c | 3.17 | +13.27c | 4.36 | −30.5c |

The unconditional short is strong and stable in both splits, at both weightings.
Note **bv > eq** already (+12.0 vs +10.6 all-sample): the higher-demand markets are
*slightly* more overpriced, and buy-vol weighting captures that automatically — so
a demand-conditioning rule must beat +12.0c, not +10.6c, to add anything.

## Rules tried: 25 (multiple-testing count)

- Retail-demand intensity (hi/lo terciles, thresholds from TRAIN only):
  `yes_buy_shares`, `yes_buy_dollars`, `n_yes_buy`, `volume`, `buy_frac`(=buy$/volume)
- Entry sub-band / moneyness: 0.15–0.20, 0.20–0.25, 0.25–0.30, deep(<0.225), shallow(≥0.225)
- Resolution day-of-week (Mon–Sun, from `end`)
- Interactions: hi-demand × deep-OTM, hi-demand × shallow

## Full per-rule table (sorted by TRAIN buy-vol mean)

Values in cents. `lift bv` = TRAIN bv mean − TRAIN baseline bv (+11.57c).

| rule | TRAIN eq (t) | TRAIN bv (t) | lift bv | TEST eq (t) | TEST bv (t) |
|---|---|---|---|---|---|
| resolves_Wed          | +13.0 (3.1) | +16.0 (3.8) | **+4.4** | +6.8 (1.0) | +7.9 (0.8) |
| resolves_Mon          | +9.1 (1.5)  | +14.9 (3.4) | +3.3 | +4.7 (0.5) | +10.8 (1.8) |
| resolves_Sat          | +10.0 (1.6) | +14.2 (2.3) | +2.7 | +10.5 (1.3)| +8.4 (1.1) |
| entry_0.20-0.25       | +9.8 (2.0)  | +14.2 (4.0) | +2.7 | +7.6 (1.5) | +10.3 (1.4) |
| resolves_Tue          | +12.9 (2.7) | +14.2 (3.4) | +2.6 | +10.4 (1.3)| +17.8 (6.4) |
| n_yes_buy_LOW(≤7)     | +9.4 (2.4)  | +13.8 (3.6) | +2.2 | +12.3 (2.0)| +18.3 (7.1) |
| n_yes_buy_HIGH(≥21)   | +15.6 (7.6) | +13.4 (4.0) | +1.8 | +8.9 (2.1) | +12.6 (3.7) |
| entry_0.15-0.20       | +11.2 (5.6) | +12.9 (6.4) | +1.3 | +9.1 (2.1) | +12.6 (4.0) |
| hi_dollars_AND_deep   | +8.9 (2.4)  | +12.7 (6.0) | +1.1 | +6.7 (1.1) | +11.6 (2.7) |
| hi_shares_AND_deep    | +9.8 (2.7)  | +12.6 (5.9) | +1.0 | +9.5 (1.7) | +12.8 (3.3) |
| buy_frac_LOW          | +8.6 (2.0)  | +12.2 (2.8) | +0.6 | +10.5 (3.0)| +12.9 (3.8) |
| entry_deep<0.225      | +9.0 (3.2)  | +12.1 (5.7) | +0.5 | +8.4 (2.1) | +11.2 (3.0) |
| resolves_Sun          | +11.4 (2.0) | +12.0 (1.8) | +0.4 | +16.5 (4.4)| +17.6 (9.5) |
| yes_buy_shares_HIGH   | +11.3 (3.5) | +11.4 (3.4) | −0.1 | +14.6 (3.3)| +15.2 (4.9) |
| yes_buy_dollars_HIGH  | +11.1 (2.9) | +11.4 (3.2) | −0.2 | +12.7 (2.7)| +14.3 (4.4) |
| buy_frac_HIGH         | +11.5 (2.3) | +11.2 (2.7) | −0.4 | +16.1 (3.1)| +17.4 (10.7) |
| entry_shallow≥0.225   | +12.4 (2.8) | +10.9 (1.7) | −0.6 | +13.8 (3.0)| +18.7 (5.2) |
| volume_HIGH           | +10.3 (3.1) | +10.2 (2.1) | −1.4 | +5.6 (1.0) | +9.8 (2.0) |
| hi_shares_AND_shallow | +13.2 (2.4) | +9.9 (1.3)  | −1.7 | +26.6 (38)*| +26.7 (35)* |
| yes_buy_dollars_LOW   | +7.7 (1.7)  | +8.3 (1.5)  | −3.2 | +11.6 (3.7)| +12.0 (3.8) |
| yes_buy_shares_LOW    | +7.8 (1.8)  | +7.8 (1.3)  | −3.8 | +12.0 (3.9)| +12.7 (3.8) |
| resolves_Thu          | +9.8 (1.6)  | +7.5 (0.7)  | −4.1 | +16.8 (3.6)| +17.2 (3.2) |
| entry_0.25-0.30       | +10.4 (1.9) | +7.1 (0.8)  | −4.5 | +16.6 (3.3)| +18.6 (4.1) |
| resolves_Fri          | +7.9 (1.4)  | +5.5 (0.7)  | −6.1 | +9.7 (1.4) | +14.1 (1.9) |
| volume_LOW            | +11.1 (1.8) | +4.6 (0.5)  | −7.0 | +11.7 (3.3)| +15.4 (5.2) |

*hi_shares_AND_shallow TEST n=10 — the huge t is a degenerate small-cluster artifact, ignore.*

## Disciplined single selection (pick on TRAIN, evaluate ONCE on TEST)

Rule: max TRAIN buy-vol mean among rules with `bv_t > 2` and `n ≥ 40`.
→ **SELECTED = `resolves_Wed`.**

| | n | eq mean (t) | bv mean (t) | worst wk |
|---|---|---|---|---|
| TRAIN | 62 | +13.0c (3.1) | +16.0c (3.8) | −85.2c |
| TEST  | 29 | +6.8c (1.0)  | +7.9c (0.8)  | −85.7c |

**TEST lift vs baseline: eq −3.9c, bv −5.4c.** The selected rule does not just fail
to add edge OOS — it is *worse* than the unconditional baseline out of sample, and
its worst week (−85c) is roughly **2x the tail** of the unconditional short (−43c).
The disciplined pick is a clean rejection.

## Overfitting diagnostics

**The TEST winners are the TRAIN losers.** Top-5 rules by TEST buy-vol EV and the
TRAIN lift that would have gotten them selected:

| rule | TEST bv | TRAIN bv lift |
|---|---|---|
| hi_shares_AND_shallow | +26.7c | −1.7c (n=10, junk) |
| entry_shallow≥0.225   | +18.7c | −0.6c |
| entry_0.25-0.30       | +18.6c | −4.5c |
| n_yes_buy_LOW         | +18.3c | +2.2c |
| resolves_Tue          | +17.8c | +2.6c |

The two strongest TEST slices (`entry_shallow`, `entry_0.25-0.30`) were among the
*worst* TRAIN slices. This is textbook noise: nothing you could have selected in
TRAIN predicts the TEST ranking.

**Consistency scan** (TRAIN bv-lift > +1c AND TEST bv > baseline_test) returns just
two survivors: `resolves_Tue` (+2.6c / +4.5c) and `n_yes_buy_LOW` (+2.2c / +5.0c).
Neither is credible:
- Both sit in heavily multiple-tested families. `resolves_Tue` is 1 of 7 DOW buckets,
  and the *strongest* TRAIN DOW (Wed) died OOS — cherry-picking the survivor across a
  noisy 7-way split. For `n_yes_buy`, **both** the LOW and HIGH terciles "beat" baseline
  in TRAIN, which means the split isn't isolating a monotone signal — it's the middle
  tercile that happens to be low. Not a mechanism.
- TEST n is tiny (27 and 25 markets) — the large TEST t-stats are cluster-fragile.
- **Neither reaches the 2x-edge bar.** Best consistent TRAIN lift is +2.6c over an
  +11.6c baseline ≈ **1.2x**, nowhere near the 2x target.

**Retail-demand hypothesis — rejected at realistic fills.** The premise ("more
lottery buying = more overpriced = sell those") does not hold on the buy-vol metric
that matters. `yes_buy_shares_HIGH` / `yes_buy_dollars_HIGH` / `buy_frac_HIGH` all sit
at or *below* baseline buy-vol EV in TRAIN (lift −0.1 to −0.4c). The equal-weight
"overpricing" of high-demand slices (+11–15c eq) is an illusion created by tiny
markets you can't actually fill; once you weight by fillable YES-buy volume it
collapses to baseline. Low-demand slices are worse still (`yes_buy_shares_LOW` bv
+7.8c, lift −3.8c). The modest real effect — bigger-demand markets a touch more
overpriced — is already baked into the unconditional bv baseline (+12.0 vs +10.6c).

**Tail.** Every narrow slice concentrates blow-up risk: the selected `resolves_Wed`
worst week is −85c vs −43c unconditional. A higher-variance slice with no EV lift is
strictly worse.

## VERDICT

**No.** There is no materially-higher-EV conditional slice that clears the bar
(≈2x edge, positive at YES-buy-volume-weighted fills, surviving OOS). Across 25
rules: the disciplined single pick (`resolves_Wed`) *loses* −5.4c bv vs baseline
out-of-sample with double the tail; the demand-intensity hypothesis is null-to-negative
at realistic fills; and the only rules positive in both splits deliver ~1.2x (not 2x),
live in multiple-tested families, and rest on 25-market TEST samples. The TEST ranking
is uncorrelated with anything selectable in TRAIN — the signature of a pure
conditioning-search null.

**Trade the unconditional short** (~+12c/contract buy-vol-weighted, week-clustered
t≈4.6, worst week −43c). Slicing adds degrees of freedom, fatter tails, and thinner
fills without adding out-of-sample EV. Candidate #7 (conditioning) is dead.

*Artifacts: `longshot_conditional.py`, `scratchpad/longshot_cond_out.json`.*
