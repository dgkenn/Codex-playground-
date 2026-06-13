# XRP 15-min Kalshi binary — exploitability battery

**Verdict: NOT EXPLOITABLE.** XRP hits the same efficiency + adverse-selection wall as ETH,
and its ~2x-wider spread makes it strictly worse, not better. The hypothesis that the
thinnest/most-retail market would be the most mispriced is **rejected**: the XRP mid is a
well-calibrated probability (beats spot-GBM/BS fair on Brier and log-loss, shows
near-martingale/over-efficient mean-reverting mid changes), the favorite-longshot bias is
smaller than the spread, the two-sided box is sharply -EV from adverse selection, and every
taker and maker rule tested is negative net of cost IS **and** OOS. Do not deploy.

Data: 739 hist windows / 736 with fills, ~10.1k maker fills, k=2..12. IS = first 60% of
windows, OOS = last 40%. Fee band modeled at taker M=0.07 (standard) and M=0.14 (crypto
premium); maker ~0. Fee = ceil(M·P·(1−P)·100)/100 per contract.

---

## 1. Efficiency (decisive) — the XRP mid is an efficient probability

Per-minute mid (k2–12, 8,115 obs) vs a spot-GBM/Black-Scholes fair value (drift 0, σ from the
prior-60-min spot path, strike = spot at window open):

| metric | XRP mid | XRP BS-fair | ETH mid | ETH BS-fair |
|---|---|---|---|---|
| Brier (lower=better) | **0.1438** | 0.1528 | **0.1413** | 0.1493 |
| Log-loss | **0.4392** | 0.4655 | **0.4289** | 0.4533 |

- **The XRP mid BEATS the BS fair value** (Brier 0.1438 < 0.1528; gap +0.0090 — the mid is
  *more* informative than the model, essentially identical to the ETH result, gap +0.0079).
  The market mid is not the thing that is wrong.
- **Martingale test:** mean lag-1 autocorrelation of per-minute mid changes = **−0.050
  (t=−4.27, n=738 windows)**. Slightly negative (micro mean-reversion / discreteness), i.e.
  the mid is at-or-past-martingale efficient — there is no momentum to ride. ETH was −0.046
  (t=−7.30); XRP is the same regime.
- **|mid − BS| = 6.5c mean / 4.8c median.** This gap is BS *model* error, not a mid error:
  trading toward the BS fair (Section 4) loses at every threshold. Because the mid already
  beats BS on Brier, the gap is the model being wrong, not the market.

**XRP is NOT less efficient than ETH.** It is the opening the strategy needed and it is not there.

## 2. Favorite-longshot calibration

Price-bucket mid vs realized win-rate (k2–12):

| bucket | n | mean mid | realized | bias (real−mid) |
|---|---|---|---|---|
| 0.0–0.1 | 1364 | 0.038 | 0.038 | +0.0c |
| 0.2–0.3 | 736 | 0.248 | 0.226 | −2.3c |
| 0.3–0.4 | 724 | 0.349 | 0.309 | −4.0c |
| 0.5–0.6 | 685 | 0.546 | 0.504 | −4.2c |
| 0.6–0.7 | 693 | 0.649 | 0.620 | −2.8c |
| 0.7–0.8 | 637 | 0.748 | 0.765 | +1.6c |
| 0.8–0.9 | 661 | 0.851 | 0.873 | +2.1c |
| 0.9–1.0 | 1115 | 0.960 | 0.962 | +0.2c |

- Max |bias| = **4.2c** (mid 0.546 → realized 0.504, mild over-pricing of near-coin-flips).
- **The biggest bias (4.2c) is roughly equal to the XRP spread (4.07c) and below
  spread+fee (~6c at M=0.14).** Not tradeable. The biases are mid-range, not in the tails,
  so there is no classic longshot bias to fade with a tail-priced contract either.

## 3. Box / maker adverse selection

| metric | value |
|---|---|
| P0 always-pair box, IS | **−15.0c/window** (t=−10.1), strand 62.6% |
| P0 always-pair box, OOS | **−14.7c/window** (t=−7.6), strand 57.6% |
| Per maker-fill settle (held to settlement) | mean −1.29c, median −5.0c |
| Half-spread captured at entry | ~2.16c |
| Completed-box margin | mean −1.66c, median +2.0c, win% 63.2, n=3851 |

The two-sided box is **strongly negative** and worse than ETH's: the wide 4c spread *looks*
like more half-spread to capture, but it exists precisely because the book is thin and
adversely selected. Per-fill settle (−1.29c mean, −5.0c median) is well below the ~2.16c
half-spread, i.e. **adverse selection more than eats the wider spread**. Strand rate is
57–63% (vs the wider, deeper books), so half the legs end up naked and lose the direction.
A wider spread on XRP is a symptom of toxicity, not free edge.

## 4. Best +EV attempt (net of spread + fee, IS/OOS)

**Taker rules** (cross to take a directional leg; net of crossed spread + fee). All negative:

| rule (M=0.07 / M=0.14) | IS net/tr | OOS net/tr | OOS Sh | OOS t |
|---|---|---|---|---|
| take favorite p≥0.65 | −6.7 / −7.6c | −6.3 / −7.3c | −0.17 | −6.1 |
| take favorite p≥0.80 | −5.7 / −6.4c | −5.7 / −6.3c | −0.20 | −5.4 |
| take longshot p≤0.20 | −5.3 / −6.0c | −3.6 / −4.3c | −0.11 | −3.5 |
| take with-flow | −8.9 / −10.1c | −7.6 / −8.8c | −0.19 | −7.2 |
| take momentum (sig>5bp) | −8.7 / −9.7c | −5.6 / −6.8c | −0.14 | −4.8 |
| take all (baseline) | −7.7 / −8.9c | −6.6 / −7.9c | −0.16 | −10.5 |

**Mid-vs-BS-fair gap trade** (buy YES when BS_fair − ask > thr; buy NO when bid − BS_fair > thr —
the |mid−BS|=6.5c gap is the only structural "edge" candidate that exceeds the spread):

| gap_thr | IS net/tr | OOS net/tr (M=0.07) | OOS t |
|---|---|---|---|
| 0.02 | −4.9c | −4.3c | −4.9 |
| 0.06 | −5.7c | −2.1c | −1.8 |
| 0.10 | −6.3c | −0.2c | −0.1 |

Negative at every threshold IS and OOS; converges to ~0 only as volume → 0. This confirms the
gap is **BS misspecification, not mid mispricing** — exactly why the mid wins the Brier.

**Maker rules** (single-sided, fee~0, held to settlement). All negative or noise:

| rule | IS net/fill | OOS net/fill | OOS Sh | OOS t |
|---|---|---|---|---|
| maker all legs | −1.52c | −0.98c | −0.02 | −1.6 |
| maker favorite p≥0.65 | −0.68c | −0.94c | −0.03 | −0.9 |
| maker low-tox (tox<0.45) | **−3.85c** | **+0.70c** | +0.02 | +0.5 |
| maker tight-spread ≤2c | −1.64c | −1.73c | −0.05 | −1.6 |

The only non-negative cell — low-tox maker OOS +0.70c — is **noise**: IS was −3.85c (t=−2.92),
the OOS sign flips, t=+0.54, and the OOS bootstrap 95% CI is **[−1.76c, +3.38c]** (spans 0).
Identical to the ETH toxicity-gated maker finding (adverse selection eats the half-spread at
every gate).

## 5. Verdict

**No exploitable edge on the XRP 15-min binary after costs.** Structural reason:

1. **The mid is an efficient probability** — it beats a spot-GBM fair value on Brier/log-loss
   and is at-or-past-martingale; there is nothing for a taker to correct.
2. **Favorite-longshot bias (≤4.2c) ≤ spread (4.07c) < spread+fee.** Any taker edge is
   inside the cost band.
3. **The wide spread is adverse-selection compensation, not free maker edge** — per-fill
   settle (−1.29c) is below the half-spread, strands run 57–63%, the box is −15c/window.
4. **Every taker rule is sharply −EV** (−2c to −10c/trade, OOS t −2 to −10) and the only
   positive maker cell fails IS/OOS sign and bootstrap.

XRP is *worse* than ETH for us, not better: same efficiency, same 0/1-payoff adverse selection,
plus a 2x-wider spread. **Same wall.** No exact +EV rule to state.

*Backtests SCREEN only; forward-validation on live XRP tape (book queue position, real fill
latency, true crypto fee multiplier) would still be required before any deployment — but there
is no positive screen to forward-validate here.*
