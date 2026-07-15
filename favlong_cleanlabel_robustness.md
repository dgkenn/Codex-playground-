# FAVLONG clean-label robustness / integrity check

**Node:** FAVLONG-CLEANLABEL-ROBUST (2026-07-15). Offline re-score on cached windows
(`/tmp/favlong_cache/win_{btc,eth,sol}.pkl`). Train ≤ 2026-06-30, Test > 2026-06-30.
Nothing live touched; lead re-verifies independently.

## Verdict: **FAVLONG-INFLATED**

The validated FAVLONG edge is **materially a selection artifact of the clean-label filter**.
The honest deployable OOS number is:

| model | deployable OOS pooled day-clustered t | mean $/ct | clears fee & t≥2? |
|---|---|---|---|
| **calibrated (baseline/logndrift/iso, edge0.03)** | **+1.87** | **+$0.0177/ct** | **NO** |
| raw-tuned (baseline/arith/σ0.8, edge0.03) | +0.87 | +$0.0076/ct | NO |

Neither clears the charter gate (t≥2). The apparent OOS edge (raw 3.97, calibrated 5.74)
was ~2–4 t-units of look-ahead injected by the `if out_proxy != outcome: continue` drop.

---

## 1. Re-score WITHOUT the clean-label drop (outcome = market terminal, all windows)

Reproduction of the published clean-label numbers is exact (raw 3.97, calibrated 5.74),
so the harness is faithful. Removing only the illegal `out_proxy != outcome` drop:

| set | RAW-tuned t / $ct | CALIBRATED t / $ct |
|---|---|---|
| OOS **clean-label** (published) | **+3.97** / +$0.0332 | **+5.74** / +$0.0513 |
| OOS **ALL windows** (deployable) | **+0.87** / +$0.0076 | **+1.87** / +$0.0177 |
| OOS **dropped windows only** | **−7.16** / −$0.1956 | **−8.46** / −$0.2246 |
| TRAIN clean-label | +4.35 / +$0.0308 | +4.03 / +$0.0365 |
| TRAIN ALL windows (in-sample deployable) | −0.09 / −$0.0006 | **−0.34 / −$0.0028** |

**How much survives:** raw t 3.97 → 0.87 (mean −77%); calibrated t 5.74 → 1.87 (mean −65%).
Damningly, even **in-sample** (TRAIN) the honest deployable edge is ~0 / slightly negative for
both models — there is no edge to deploy, in or out of sample, once the filter is removed.

## 2. Quantify the selection

- **Drop fraction is small (~7%)** but the dropped windows are catastrophic:
  OOS total windows reaching the decision gate = 3,390; dropped (proxy≠market) = **235 (6.9%)**,
  kept = 3,155 (93.1%). Train drop = 6.6%.
- **Edge is entirely concentrated in the kept subset:** dropped-window trades realize
  **−$0.196/ct (raw, t=−7.16)** / **−$0.225/ct (calibrated, t=−8.46)** vs. kept +$0.033/+$0.051.
  Not uniform → pure selection artifact.
- **Mechanism of the leak.** `out_proxy = sign(final_spot − open_spot)`; the market terminal
  outcome agrees with it **93.1%** of the time (the sibling finding of ~90.3% using spot@720).
  FAVLONG trades directionally on spot@720 vs the open-spot proxy strike, so the ~7% of windows
  where the terminal settlement *contradicts* the near-final spot direction are exactly the trades
  most likely to lose — and the clean-label filter deletes them by peeking at the terminal label.
  A live trader at t=720 cannot know which bucket a window lands in. Removing 7% of windows swings
  the raw mean +$0.033 → +$0.008 and t 3.97 → 0.87 because those 7% carry ~−20c/ct.
- Dropped losers span the whole book (OOS calibrated: 37 trades <0.15, 49 in 0.15–0.40,
  40 in 0.40–0.60, 72 ≥0.60; winrates 0.03–0.20) — not a removable sub-region.

## 3. Deployable version (trade every window passing decision-time gates)

Decision-time gates actually coded = decision_t=720, τ≥30, valid spot/bid/ask/σ, model-edge>0.03.
(There is **no** ATM/price-band gate in the scored code; I tested adding one.) Settling every gated
trade against the true market terminal, net Kalshi fee:

**Deployable OOS = calibrated t=+1.87, mean $+0.0177/ct (raw t=+0.87, $+0.0076/ct). Does NOT clear t≥2.**

Per-asset OOS (deployable, calibrated clean-label-fit map): btc t=+2.19, eth t=+1.10, sol t=−0.16.
Only btc is individually positive-significant; the cross-asset replication that justified pooling
does **not** survive.

**No legitimate price band rescues it** (calibrated, all windows, decision-time entry-price band):

| band | t | $/ct |
|---|---|---|
| none (all prices) | +1.87 | +$0.0177 |
| price ≥ 0.40 | +0.70 | +$0.0091 |
| favorite ≥ 0.60 | +0.66 | +$0.0087 |
| ATM-fav 0.40–0.90 | +0.32 | +$0.0054 |
| ATM 0.30–0.70 | −0.04 | −$0.0010 |
| deep-underdog < 0.15 | +1.93 | +$0.0254 |

The mechanism report's "favorite ≥ 0.60 OOS t=2.24" was itself computed on the clean-label subset
and is **also inflated**: the honest favorite-band deployable is t≈0.66. The only band still near
t≈1.9 is deep-underdog <0.15 — which the same report explicitly labelled a null (OOS t~1.0); that
is noise, not a rescue.

## 4. Isotonic leak check

- **Yes, the isotonic map is fit on clean-label-selected rows.** `favlong_model_v2.window_rows`
  and `favlong_forward.fit_isotonic_map_archive` both apply the `out_proxy != outcome` drop before
  collecting (fair, outcome) pairs, so the calibration is trained on the same selected population.
- **Refitting the map on ALL train windows (no selection) does not help:** deployable OOS
  t=+1.80, $+0.0152/ct (vs +1.87 with the selected-fit map). The calibration is a *second-order*
  issue; the leak is the **settlement selection**, not the map. Even the clean-label-scored number
  is barely changed by the honest map (5.74 → 5.81), confirming the map itself is not the inflator.
- **No forward leak in the map (confirmed as before):** the map is fit strictly on train
  (≤2026-06-30) for the OOS test here, and on archive (≤2026-07-14) for the persisted
  `favlong_isotonic_map.json` used only on forward days (>2026-07-14). Fit is train/archive-only,
  applied unchanged — no forward-data contamination. The forward-leak audit stands; the problem is
  the label-selection leak, which is orthogonal and present in both raw and calibrated paths.

## 5. Reconciliation with capacity / mechanism findings

- `favlong_capacity_sizing.md` uses "honest forward prior ~4c/ct, t=5.74 OOS" — that is the
  **clean-label-inflated** figure. The honest deployable is ~1.8c/ct (calibrated) with t<2, i.e.
  roughly half the assumed edge and not statistically distinguishable from cost. The capacity
  conclusion ("marginal at $500, viable at $5000") should be re-derived at ~1.8c/ct **and only if**
  a deployable edge can be re-established at all — currently it cannot.
- `favlong_mechanism_report.md` already flagged (line 30) "the headline number appears overstated
  relative to what the clean-label taker captures," but every table in it ("clean-label filter on")
  was computed on the selected subset, so its favorite/wide-book/regime edges inherit the same
  inflation. The wide-book (+3.6c/ct) and favorite-band results are not trustworthy as deployable
  numbers without re-running on all windows with market-terminal settlement.

## Bottom line

FAVLONG's validated edge does **not** survive removal of the clean-label selection. The honest,
deployable out-of-sample edge is **calibrated t=+1.87, $+0.0177/ct** (raw t=+0.87, $+0.0076/ct) —
below the t≥2 charter gate, and ~0/negative in-sample. FAVLONG should be treated as **not a
validated deployable edge** until a version that trades every decision-time-gated window and
settles against the true terminal can independently clear the forward gate.

_Method: `favlong_model_v2.model_fair` reused verbatim for fair-values; only the `out_proxy != outcome`
drop toggled. Pooled per-(asset,day) day-clustered t, +Kalshi fee 0.07·p·(1−p). btc/eth/sol; XRP excluded as before._
