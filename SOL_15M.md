# SOL 15-min binary — exploitability battery

**Verdict: NOT exploitable for us.** SOL hits the same efficiency + adverse-selection wall as ETH.
The SOL binary mid is an efficient probability estimate (beats a BS fair value, near-martingale),
the maker box is sharply -EV (adverse selection on the 0/1 payoff), and the one taker region with
the right-signed favorite bias (mid∈[0.90,0.97)) is **not IS/OOS stable** — its apparent OOS edge
is concentrated in 3 of 4 sequential quartiles with one strongly negative quartile, i.e. regime
exposure (a longshot-short tail profile), not a repeatable mispricing. Do not deploy.

Data: SOL 833 common windows, 832 with maker fills, ~591k tape trades. P(up)=0.475. Mean quoted
spread ≈ 3.0c (vs ETH ≈ 1.8c — SOL is indeed thinner/wider, as hypothesized). IS = first 60% of
windows (sequential), OOS = last 40%. Costs modeled: taker pays crossed half-spread (in the ask/bid)
**plus** Kalshi taker fee = ceil(M·P(1−P)·100)/100 with M∈{0.07, 0.14} (crypto-premium band);
maker fee ≈ 0.

---

## 1. EFFICIENCY (the decisive test) — SOL mid is efficient

Mid evaluated at decision minutes k∈[2,12], n=7,763 observations. BS fair value = driftless GBM
P(spot_end > spot_open) using per-minute realized vol from the prior-60-min spot history.

| metric | SOL mid | SOL BS-fair | ETH mid | ETH BS-fair |
|---|---|---|---|---|
| Brier | **0.160** | 0.203 | 0.165 | 0.194 |
| LogLoss | **0.483** | 0.601 | 0.498 | 0.580 |

The SOL mid **beats** the spot-GBM/BS fair value on both Brier and log-loss by a wide margin — the
mid is a *better* probability estimate than a model built on the spot path. There is no fair-value
gap for a taker to harvest; any model-vs-mid disagreement is the model being wrong, not the mid.

**Martingale test:** lag-1 autocorrelation of within-window mid changes = **−0.068 (t=−5.27)**
(ETH: −0.029, t=−3.79). It is statistically nonzero but economically tiny and **negative** (mid
changes slightly *reverse*, the opposite sign of overreaction-momentum). To monetize a −0.068 AC you
must trade against the change and capture more than the 3c spread + fee on each reversal — the
reversal magnitude is < 0.1c, two orders of magnitude too small. SOL is, like ETH, a near-martingale
that tracks spot informationally. **SOL is NOT less efficient than ETH** — it is marginally less
efficient on the Brier gap but the gap is on the wrong (model-loses) side and the AC is the wrong sign.

## 2. FAVORITE-LONGSHOT calibration (mid bucket → realized win rate)

| mid bucket | n | avg_mid | realized | gap (real−mid) |
|---|---|---|---|---|
| [0.00,0.05) | 293 | 0.039 | 0.024 | −0.015 |
| [0.05,0.15) | 945 | 0.095 | 0.070 | −0.025 |
| [0.15,0.25) | 855 | 0.197 | 0.184 | −0.013 |
| [0.25,0.35) | 747 | 0.296 | 0.296 | −0.001 |
| [0.35,0.45) | 777 | 0.400 | 0.390 | −0.010 |
| [0.45,0.55) | 697 | 0.497 | 0.465 | −0.032 |
| [0.55,0.65) | 783 | 0.598 | 0.564 | −0.034 |
| [0.65,0.75) | 699 | 0.697 | 0.677 | −0.021 |
| [0.75,0.85) | 771 | 0.798 | 0.795 | −0.003 |
| [0.85,0.95) | 920 | 0.902 | 0.928 | **+0.027** |
| [0.95,1.00) | 276 | 0.961 | 0.993 | **+0.032** |

Unlike ETH (whose bias had the *wrong* sign), SOL shows a **right-signed favorite bias at the
extreme**: deep favorites (mid≥0.85) realize ~3pp **above** their quoted price, i.e. near-certainties
are slightly underpriced. Mid-range YES (0.45–0.65) is overpriced by ~3pp. The extreme-favorite gap
(~3pp) is the only region where the gap is both right-signed and comparable to costs, so it is the
single most promising taker candidate (Test 4).

## 3. BOX / MAKER adverse selection — sharply −EV (same wall as ETH)

P0 always-pair two-sided maker box on the SOL tape (maker fee ≈ 0):

| | completed boxes | mean box margin | strand rate | mean strand settle | per-window net | t |
|---|---|---|---|---|---|---|
| IS | 2,668 | −2.23c | 56.7% | −11.50c | **−18.42c** | −13.6 |
| OOS | 1,941 | −1.56c | 58.6% | −8.02c | **−13.78c** | −8.3 |

The two-sided box is **strongly negative** and the strand (unpaired leg held to a 0/1 settlement)
is the killer: ~57–59% of windows strand a leg, and stranded legs settle at −8 to −11.5c on average —
classic adverse selection on the binary payoff. A wider SOL spread does **not** leave net maker edge;
it comes with a thinner book that strands more often and worse. The maker-favorite variant (rest a
YES bid in the favorite zone, hold to settle, fee≈0) is flat-to-negative everywhere and never
significant (best OOS +0.35c, t=0.32). Maker is dead.

## 4. BEST +EV ATTEMPT — extreme-favorite taker, mid∈[0.90,0.97)

The only candidate that clears costs in any half: buy YES at the ask when mid∈[0.90,0.97), pay
half-spread + taker fee, hold to settlement.

| M | set | n | net/trade | Sharpe | t | win% | avg ask |
|---|---|---|---|---|---|---|---|
| 0.07 | IS | 449 | +0.63c | +0.035 | +0.75 | — | 0.950 |
| 0.07 | OOS | 294 | **+2.32c** | +0.165 | **+2.83** | — | 0.946 |
| 0.14 | IS | 449 | +0.50c | +0.028 | +0.59 | — | 0.950 |
| 0.14 | OOS | 294 | **+2.16c** | +0.153 | **+2.63** | — | 0.946 |

OOS looks attractive (+2.3c, t=2.8) but **IS is flat (t≈0.7)** — a real structural edge appears in
both halves. Sequential-quartile decomposition (M=0.07) exposes the artifact:

| quartile | n | net/trade | t | win% |
|---|---|---|---|---|
| Q1 | 173 | +1.93c | +1.70 | 97.7% |
| Q2 | 172 | +3.32c | +5.49 | 99.4% |
| Q3 | 221 | **−2.76c** | −1.66 | 93.2% |
| Q4 | 177 | +3.79c | +6.39 | 99.4% |
| FULL | 743 | +1.30c | +2.15 | — |

At M=0.14 the full-sample t drops to 1.92 and a single bad quartile (Q3) still dominates. This is the
signature of a **longshot-short / pick-up-pennies tail trade**: 97–99% win rate selling near-certain
favorites, where the profit is just the periodic absence of the tail and the one negative quartile is
the tail arriving. It is regime exposure to "SOL doesn't reverse in the final minutes," not a
repeatable mispricing. The per-band fill count (~2 windows worth of fills in a narrow 7c band) is
thin, the result is not robust to the cost band, and one of four time-blocks is sharply negative.
**Not deployable.**

## 5. VERDICT

**SOL 15-min is NOT exploitable for us — same efficiency + adverse-selection wall as ETH.**

Structural reasons:
1. **Mid is efficient.** Beats a BS/GBM fair value (Brier 0.160 < 0.203, LogLoss 0.483 < 0.601) and
   is a near-martingale (lag-1 AC −0.068, t=−5.27, but economically negligible and wrong-signed for
   momentum). No fair-value gap and no overreaction to fade larger than the ~3c spread + fee.
2. **Maker is adversely selected.** Two-sided box −13.8c/window OOS (t=−8.3); 59% strand rate with
   stranded legs settling −8c. The wider SOL spread is offset by a thinner book — no net maker edge.
3. **The one right-signed taker bias (extreme favorite) is not IS/OOS stable.** OOS +2.3c (t=2.8) but
   IS flat (t=0.7), and 1 of 4 sequential quartiles is −2.76c. It is a tail/regime trade, not an edge.

No deployable rule. SOL being thinner/more-retail did **not** break the efficiency wall — the mid
stays well-calibrated and the costs (3c spread + premium taker fee) exceed every measured edge that
is stable across both data halves.

*Note: all results are backtest SCREENS on reconstructed maker fills + touch-crossing taker fills.
The favorite-taker negative quartile in particular argues against any forward deployment; this would
require forward paper-validation before risking capital, and the IS/OOS instability says it would not
survive.*
