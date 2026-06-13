# Cross-Asset Relative Value on Kalshi 15-min Crypto Binaries (BTC/ETH/SOL/XRP)

**Verdict: NEGATIVE.** No positive-EV cross-asset relative-value strategy survives multi-leg
taker costs. The common factor is overwhelmingly strong (BTC-led, PC1 = 77% of settlement
variance), but the alt binaries **already fully price that common factor** — the cross-asset
signal adds ~0 incremental AUC over each target's own binary mid, so there is no residual
divergence to capture. The only marginally-positive sleeve (ETH) is entirely the fee: it is
+1.5c/contract at the std fee (M=0.07) and collapses to +0.1c, t=0.1 at the crypto fee (M=0.14).

Harness: `xasset_relval.py`. Data: `hist_kalshi_{asset}15m.parquet` (per-window `res_up`,
`mid/bid/ask_path[15]`, `spot_path[15]`, `spot_prev`). IS = first 60% of each pair's common
windows (chronological), OOS = last 40%. Backtests SCREEN only; any survivor would need forward
paper validation. All metrics OOS unless noted.

Window coverage: BTC 2534, ETH 2402, SOL 835, XRP 739. SOL/XRP only exist from 2026-05-24.
4-way common windows = 112 (small — used for co-movement). Pairwise BTC∩target is larger
(BTC∩ETH 1426, BTC∩SOL 472, BTC∩XRP 443) and is used for the lead-lag / strategy tests.

---

## Task 1 — Co-movement / basket (4-way common, n=112)

Marginal P(up): BTC 0.482, ETH 0.402, SOL 0.429, XRP 0.384.

Pairwise settlement correlation (phi on 0/1 outcomes):

|       | BTC | ETH | SOL | XRP |
|-------|-----|-----|-----|-----|
| BTC   | 1.00| 0.70| 0.75| 0.67|
| ETH   | 0.70| 1.00| 0.69| 0.59|
| SOL   | 0.75| 0.69| 1.00| 0.73|
| XRP   | 0.67| 0.59| 0.73| 1.00|

Breadth (# of 4 assets up): 0-up 43.8%, 1-up 10.7%, 2-up 4.5%, 3-up 14.3%, 4-up 26.8%.
**All-same-direction = 70.5%** vs ~12.5% under independence.

Common factor: P(alt up | BTC up) vs P(alt up | BTC down):
- ETH: 0.759 vs 0.069 (lift +0.690)
- SOL: 0.815 vs 0.069 (lift +0.746)
- XRP: 0.722 vs 0.069 (lift +0.653)

PC1 of the settlement covariance explains **77%** of variance. The four 15-min binaries are a
tightly-coupled basket with a dominant, clearly BTC-led common factor. This is the necessary
precondition for relative value — and also the reason it fails (below).

---

## Task 2 — Incremental AUC of cross-asset signal over target's own mid (OOS)

At minute k, predict target settlement from: target binary mid; + target's own spot move to k;
+ BTC spot move to k; + basket (other-alt) move to k; + all. Logistic combine, evaluated OOS.
delta-AUC vs `AUC_mid` is the question — does any cross-asset feature beat what the binary already prices?

| target | k  | n    | AUC_mid | +own_mv | +BTC  | +basket | +all  |
|--------|----|------|---------|---------|-------|---------|-------|
| eth    | 5  | 368  | 0.835   | 0.831   | 0.826 | 0.828   | 0.834 |
| eth    | 8  | 367  | 0.925   | 0.924   | 0.919 | 0.921   | 0.927 |
| eth    | 10 | 368  | 0.952   | 0.951   | 0.949 | 0.949   | 0.951 |
| sol    | 5  | 150  | 0.835   | 0.819   | 0.814 | 0.819   | 0.821 |
| sol    | 8  | 150  | 0.896   | 0.878   | 0.879 | 0.873   | 0.879 |
| sol    | 10 | 150  | 0.926   | 0.905   | 0.913 | 0.907   | 0.909 |
| xrp    | 5  | 152  | 0.819   | 0.824   | 0.816 | 0.821   | 0.833 |
| xrp    | 8  | 151  | 0.878   | 0.878   | 0.867 | 0.872   | 0.878 |
| xrp    | 10 | 152  | 0.929   | 0.926   | 0.926 | 0.929   | 0.924 |

**Decisive finding:** the target's own binary mid is already a near-ceiling predictor (AUC
0.82–0.95). Adding BTC, the basket, or even the target's own raw spot move yields **delta-AUC
≈ 0** (mostly 0 to −0.02, occasional +0.01 noise; xrp k=5 +all = +0.014 is within sampling
error at n=152). Contrary to the hypothesis that thinner names (SOL/XRP) lag, the cross-asset
basket adds nothing there either — those binaries also already embed the common factor. This
matches the prior ETH-alone result (BTC added zero) and extends it to SOL/XRP.

---

## Task 3 — Relative-mispricing strategy (basket-implied fair vs alt binary mid)

Rule tested: at minute k ∈ {4,6,8,10}, estimate the alt's fair P(up) from a logistic of
{own spot move, BTC move, basket move} fit on IS; if `fair − mid` exceeds threshold `thr`,
take the cheap side as a TAKER (buy YES at ask / buy NO at 1−bid). Settle to `res_up`.
Net P&L = `(payoff − entry) − taker_fee(entry)`; the cross-to-touch (ask/bid) already embeds the
spread. EV in cents/contract.

**Fee M=0.07 (std):**

| target | thr  | IS n | IS EV/c | OOS n | OOS EV/c | OOS Sh | win%  | t     |
|--------|------|------|---------|-------|----------|--------|-------|-------|
| eth    | 0.05 | 169  | +7.07   | 1043  | +0.82    | +0.021 | 68.7% | +0.69 |
| eth    | 0.10 | 103  | +9.29   | 690   | +1.54    | +0.037 | 67.0% | +0.97 |
| eth    | 0.15 | 53   | +13.37  | 457   | +1.50    | +0.034 | 64.6% | +0.73 |
| sol    | 0.05 | 544  | −3.48   | 340   | −5.36    | −0.132 | 50.9% | −2.44 |
| sol    | 0.10 | 300  | −3.34   | 172   | −9.04    | −0.216 | 43.0% | −2.84 |
| sol    | 0.15 | 158  | −5.23   | 77    | −11.46   | −0.255 | 41.6% | −2.23 |
| xrp    | 0.05 | 510  | −2.82   | 360   | −2.54    | −0.064 | 57.5% | −1.21 |
| xrp    | 0.10 | 305  | −3.15   | 183   | +0.67    | +0.015 | 59.0% | +0.21 |
| xrp    | 0.15 | 158  | −1.36   | 96    | −1.80    | −0.039 | 55.2% | −0.38 |

**Fee M=0.14 (crypto premium):**

| target | thr  | IS n | IS EV/c | OOS n | OOS EV/c | OOS Sh | win%  | t     |
|--------|------|------|---------|-------|----------|--------|-------|-------|
| eth    | 0.05 | 169  | +5.80   | 1043  | −0.36    | −0.009 | 68.7% | −0.30 |
| eth    | 0.10 | 103  | +7.87   | 690   | +0.18    | +0.004 | 67.0% | +0.11 |
| eth    | 0.15 | 53   | +11.86  | 457   | +0.08    | +0.002 | 64.6% | +0.04 |
| sol    | 0.05 | 544  | −4.58   | 340   | −6.60    | −0.163 | 50.9% | −3.00 |
| sol    | 0.10 | 300  | −4.44   | 172   | −10.42   | −0.249 | 43.0% | −3.27 |
| sol    | 0.15 | 158  | −6.28   | 77    | −12.94   | −0.288 | 41.6% | −2.52 |
| xrp    | 0.05 | 510  | −4.00   | 360   | −3.72    | −0.093 | 57.5% | −1.77 |
| xrp    | 0.10 | 305  | −4.35   | 183   | −0.65    | −0.015 | 59.0% | −0.20 |
| xrp    | 0.15 | 158  | −2.59   | 96    | −3.22    | −0.070 | 55.2% | −0.69 |

Interpretation:
- **ETH** is the only sleeve with positive OOS EV at the std fee (+1.5c, t≈0.7–1.0 — already
  not significant). At the crypto fee it falls to +0.08–0.18c, t≈0.0–0.1, Sharpe ≈ 0. The entire
  margin was the fee differential, i.e. there is no signal, only mid≈fair plus noise. A
  market-neutral 2-leg version would pay this cost twice and be solidly negative.
- **SOL** is strongly negative IS and OOS (−6 to −13c, t = −2.5 to −3.3). The logistic "fair"
  diverges from mid only where the mid is *right* and the model is wrong — adverse selection on
  the thin name.
- **XRP** is negative-to-flat everywhere; the single +0.67c cell (M=0.07, thr=0.10) sign-flips
  to −0.65c at the crypto fee. Noise.

Cost reference: a single-leg crypto taker pays ceil(0.14·p(1−p)·100)/100 ≈ 0.03–0.04/contract
plus ~1c spread cross ≈ **0.04–0.05/contract**; a 2-leg market-neutral relval pays ~0.08–0.10.
Task 2 shows the predictive divergence beyond mid is ~0, so there is nothing to clear that cost.

---

## Task 4 — Pairs (BTC lead → alt follower not yet repriced), fee M=0.14

Signal: at minute k, if BTC moved >`btc_thr` bps since open while the alt's own move lagged
(<½ of BTC's) and the alt binary mid was still cheap (<0.55 for up), take the alt YES as a taker
(symmetric for down). Net of fee+spread.

| pair      | btc_thr | IS n | IS EV   | OOS n | OOS EV  | OOS Sh | win%  | t     |
|-----------|---------|------|---------|-------|---------|--------|-------|-------|
| BTC→eth   | 10      | 18   | −10.94  | 52    | −18.65  | −0.441 | 28.8% | −3.18 |
| BTC→eth   | 20      | 3    | −1.00   | 9     | −12.53  | −0.279 | 33.3% | −0.84 |
| BTC→sol   | 10      | 28   | −5.29   | 26    | +1.00   | +0.021 | 46.2% | +0.10 |
| BTC→sol   | 20      | 5    | +11.00  | 6     | −28.67  | −0.721 | 16.7% | −1.77 |
| BTC→xrp   | 10      | 37   | −10.35  | 29    | +7.03   | +0.149 | 55.2% | +0.80 |
| BTC→xrp   | 20      | 6    | −17.50  | 7     | +25.00  | +0.634 | 71.4% | +1.68 |

No tradeable pair. BTC→ETH is strongly negative and significant (t=−3.2): when BTC has already
moved and ETH "hasn't repriced," ETH genuinely is going the other way — the binary was right.
BTC→XRP at thr=20 (+25c, t=1.68) is on **n=7** OOS trades with IS −17.5c — pure small-sample
noise, sign-unstable across thresholds. Higher thresholds starve to <10 trades.

---

## Verdict & structural reason

**There is no positive-EV cross-asset relative-value strategy on the 15-min alts after multi-leg
costs.** The reason is structural, not a tuning failure:

1. The basket is extremely tightly coupled (PC1 = 77%, all-same-direction 70.5%, BTC→alt lift
   ≈ +0.7) — so a relative-value premise is plausible.
2. But Task 2 shows each alt's **own binary mid already prices that common factor to AUC
   0.82–0.95, with delta-AUC ≈ 0 from BTC/basket**. The market makers quoting the alt binaries
   evidently watch BTC; the common factor is already in the price. There is **no residual
   divergence** between an alt's binary and the basket-implied fair beyond noise.
3. Whatever tiny divergences exist are **smaller than the multi-leg taker cost** (~0.04–0.05/leg
   crypto, ~0.08–0.10 for a 2-leg neutral trade). The one positive sleeve (ETH) is positive only
   by exactly the fee and vanishes at the crypto premium (t≈0); SOL is adversely selected and
   significantly negative; XRP and all pairs are noise.

This is consistent with the prior single-asset results: the mids are efficient and BTC adds zero
incrementally. The cross-asset structure does not rescue it — the binaries collectively reflect
the same common factor with no exploitable lag at the minute resolution available here.

**Forward validation:** none of the above clears the bar, so nothing is promoted. If re-tested
later with more SOL/XRP history, the gate is delta-AUC > 0 OOS *and* OOS EV/contract > the modeled
multi-leg cost with t > 2 — neither was met here.
