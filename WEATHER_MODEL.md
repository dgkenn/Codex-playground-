# Weather Fair-Value Model — Calibration & Validation for Kalshi Daily-High Markets

**Date:** 2026-06-14 · **Branch:** `claude/polymarket-bot-live-ready-vw7ut5`
**Question (make-or-break):** Can we build a *provably well-calibrated* probabilistic daily-HIGH
forecast model, validated independently of Kalshi on historical forecast-vs-realized data? If yes,
current Kalshi deviations are tradable NOW (no 30–45-day forward wait); if not, the "edge" is model
error. This is the foundation under `KALSHI_WEATHER.md`'s deferred verdict.

---

## TL;DR — VERDICT

**YES, a well-calibrated next-day fair-value model is achievable** for the center of the
distribution. The winner is **bias-corrected Normal(μ = forecast − bias, σ = per-city/season
historical error)**, σ ≈ **1.1–1.8 °F** (next-day, well-observed stations). On a clean 2025
hold-out (8 cities, 2,920 city-days, 26,280 bracket cells) it is **reliable in the 20–60% range**
(predicted 25%→hit 23%, 45%→hit 49%) with Brier **0.066** and PIT std **0.25** (ideal 0.289 — model
is *marginally too wide*, i.e. mildly under-confident, never over-confident).

**BUT the decisive tail test fails honestly:** the warm-tail / above-mode brackets that
`KALSHI_WEATHER.md` reported Kalshi underprices are **genuinely rare (~1% realized)** and the model
**slightly over-predicts** them (predict 3%→hit 1.7%, predict 8%→hit 2.4%). Worse, at σ≈1.5 °F a
**1 °F forecast error moves the tail probability ~3.3×**. So the model is **not accurate enough to
reliably declare individual tail brackets mispriced** — there, the "edge" is dominated by model
error. **Trade the calibrated center; do not bet the tail off this model.**

Net: weather's *center* is tradable on a calibrated model; the *tail thesis from
`KALSHI_WEATHER.md` does not survive independent calibration.*

---

## 1. Data assembly (no lookahead)

For each of the 8 Kalshi high-temp cities, matched to the **exact settlement station**:

| City | Kalshi series | Settlement station | Truth (IEM ASOS) | Forecast pt (lat,lon) |
|------|---------------|--------------------|------------------|-----------------------|
| NYC | KXHIGHNY | KNYC Central Park | NYC / NY_ASOS | 40.779, −73.969 |
| CHI | KXHIGHCHI | KMDW Midway | MDW / IL_ASOS | 41.786, −87.752 |
| MIA | KXHIGHMIA | KMIA Miami Intl | MIA / FL_ASOS | 25.791, −80.316 |
| AUS | KXHIGHAUS | **KATT Camp Mabry** | ATT / TX_ASOS | 30.321, −97.760 |
| LAX | KXHIGHLAX | KLAX | LAX / CA_ASOS | 33.938, −118.389 |
| PHX | KXHIGHTPHX | KPHX | PHX / AZ_ASOS | 33.428, −112.004 |
| DAL | KXHIGHTDAL | KDFW | DFW / TX_ASOS | 32.898, −97.019 |
| BOS | KXHIGHTBOS | KBOS Logan | BOS / MA_ASOS | 42.361, −71.010 |

- **Forecast (no lookahead):** Open-Meteo **historical-forecast-api** archived operational
  `temperature_2m_max` (`models=gfs_seamless`), 2023-01-01 → 2025-12-31, queried at the settlement
  lat/lon. This is the stored short-range / day-ahead forecast — the lead Kalshi's next-day market
  trades. **1,096 paired days per city.**
- **Realized truth = NWS station daily high**, proxied by **IEM ASOS `max_tmpf`** at the exact
  settlement station. **Critical:** we do NOT use ERA5/Open-Meteo gridded "actuals" as truth — they
  carry a multi-°F urban cool bias (Central Park 2024-06-03: ERA5 85.3 vs station 86; ERA5-LAND
  83.9). IEM ASOS is the obs feed NWS CLI is built from. (Residual caveat: CLI's midnight-LST window
  + rounding can differ from raw ASOS by ≤1 °F; this is the main remaining truth uncertainty.)
- **Lookahead audit:** the archive is a *genuine forecast*, not an analysis copy — hist-forecast vs
  ERA5 analysis differ by sd 1.8 °F (max 4.6 °F) over a test month. See §4 for why the measured σ is
  the *true* error and not artificially deflated.

Raw pulls are cached under `wx_cache/` (git-ignored) so re-runs cost zero API calls.

---

## 2. Candidate models (`wx_fairvalue.py`)

All map a forecast distribution → P(integer high in each Kalshi bracket), integrating the continuous
distribution over **[lo−0.5, hi+0.5]** to honor whole-degree CLI rounding.

- **(a) Normal** `N(μ=forecast−bias, σ)` — σ from per-city/season historical error. Simple, robust.
- **(b) Ensemble** — empirical kernel-smoothed CDF over GEFS members (Open-Meteo ensemble-api).
  **Not viable on the free tier here:** the ensemble archive returns only ~5 usable past days, and
  on that sample GEFS is **badly under-dispersed** — member spread ≈ 1 °F while the ensemble-mean
  error sd is 3–8 °F. Raw ensemble would be *over-confident*; it loses to (a). Kept in code with a
  Normal fallback, but **not the recommended engine.**
- **(c) Skew-Normal** `bias-corrected + skew` — to test the "warm tail is fatter" story. On the
  hold-out it is **statistically indistinguishable** from bias-corrected Normal (Brier 0.0653 vs
  0.0654); the skew adds nothing measurable. The warm tail is not fat enough to matter.

---

## 3. Calibration validation (hold-out: train 2023–24, test 2025)

26,280 bracket cells on the 2,920-day hold-out.

| Model | Brier | LogLoss | CRPS (°F) | PIT mean | PIT std |
|-------|------:|--------:|----------:|---------:|--------:|
| Normal, fixed σ | 0.0660 | 0.2058 | 0.750 | 0.473 | 0.250 |
| **Normal, seasonal σ** | **0.0654** | **0.2037** | **0.738** | 0.472 | 0.255 |
| Skew-Normal, seasonal | 0.0653 | 0.2037 | 0.738 | 0.472 | 0.255 |

(ideal PIT: mean 0.5, std 0.289). PIT std < 0.289 ⇒ the model is **slightly over-dispersed /
under-confident** — the *safe* direction (it never claims more certainty than warranted).

**Reliability diagram — bias-corrected seasonal Normal (predicted → realized hit-rate):**

```
  pred ~ 1%   -> hit  0.8%   (n=18148)
  pred ~15%   -> hit  9.8%   (n=1950)   <- mild over-prediction of low-prob bins
  pred ~25%   -> hit 22.2%   (n=1566)   <- well calibrated
  pred ~35%   -> hit 40.4%   (n=1604)   <- well calibrated (slightly under-confident)
  pred ~45%   -> hit 49.3%   (n=1963)   <- well calibrated
  pred ~54%   -> hit 59.1%   (n=783)    <- modal bin under-confident
  pred ~63%   -> hit 58.6%   (n=222)
  pred ~71%   -> hit 79.5%   (n=44)
```

**The 20–60% band — where most tradable bracket probabilities live — is genuinely calibrated.**

**Per-city next-day forecast error & calibration:**

| City | bias (fc−act) | σ (°F) | MAE (°F) | Brier (test) | PIT std |
|------|--------------:|-------:|---------:|-------------:|--------:|
| NYC | −0.29 | 1.65 | 1.31 | 0.0725 | 0.238 |
| CHI | −1.29 | 1.66 | 1.59 | 0.0711 | 0.254 |
| MIA | −1.49 | 1.39 | 1.66 | 0.0644 | 0.225 |
| AUS | −1.79 | 1.55 | 1.96 | 0.0699 | 0.254 |
| LAX | −0.44 | 1.12 | 0.93 | 0.0544 | 0.245 |
| PHX | −1.94 | 1.31 | 2.11 | 0.0582 | 0.211 |
| DAL | −0.29 | 1.49 | 1.12 | 0.0637 | 0.236 |
| BOS | +0.17 | 1.75 | 1.32 | 0.0741 | 0.266 |

**Bias correction is essential:** Open-Meteo/GFS runs systematically **cold by 1.3–1.9 °F** at
inland/desert stations (CHI, MIA, AUS, PHX). Uncorrected, the model would mis-place the whole ladder.

**Seasonal σ (the bracket-width driver):**

| City | warm MJJAS | cool NDJFM |
|------|-----------:|-----------:|
| NYC | 1.46 | 1.50 | CHI | 1.39 | 1.80 | MIA | 1.49 | 1.10 | AUS | 1.39 | 1.57 |
| LAX | 0.89 | 1.31 | PHX | 1.18 | 1.24 | DAL | 1.21 | 1.49 | BOS | 1.77 | 1.52 |

---

## 4. Is the measured σ ≈ 1.5 °F real, or lookahead-deflated?

The literature day-ahead max-temp σ is often quoted ~2–4 °F, so a measured ~1.5 °F invites suspicion.
**Stress test (inflate σ and re-check calibration):**

| σ scaling | Brier | PIT std | reliability symptom |
|-----------|------:|--------:|---------------------|
| **×1.0 (measured)** | **0.0660** | **0.250** | best; ~calibrated |
| ×1.5 | 0.0720 | 0.194 | predict 34%→hit 50%: **under-confident** |
| ×2.0 (~3 °F) | 0.0783 | 0.156 | predict 33%→hit 61%: **badly under-confident** |

**Inflating σ destroys calibration** (PIT collapses to over-dispersion; predictions become far too
low). If the true error were 3 °F, the measured-σ model would be *over-confident* on the hold-out —
it is the opposite. This **rules out gross lookahead**: the archive's short-range skill is the true
next-day skill for these dense-observation stations. The ~2–4 °F figure applies to harder
regimes/stations and longer leads; for these 8 well-observed metros, day-ahead σ genuinely is
~1.1–1.8 °F. (Honest residual: the archive may favor the morning-of run, a slightly shorter lead than
a prior-evening Kalshi entry — treat σ as a mild lower bound and widen ~10–20% if entering >24 h out.)

---

## 5. THE DECISIVE TEST — can the model call the tail brackets Kalshi reportedly misprices?

`KALSHI_WEATHER.md` claimed the **bin-above-mode + warm tail** are underpriced by Kalshi. Testing the
model's reliability **restricted to above-mode/warm brackets** (lower edge ≥ μ+2 °F) on the hold-out:

```
  pred  0-2%  -> hit  0.1%   (n=8152)
  pred  2-5%  -> hit  1.7%   (n=687)    <- model OVER-predicts
  pred  5-10% -> hit  2.4%   (n=329)    <- model OVER-predicts
  pred 10-20% -> hit  8.4%   (n=1053)   <- model OVER-predicts
```

Pooled: warm-tail/above-mode mean predicted **2.0%** vs actual hit **1.1%**.

**Two killers for the tail thesis:**
1. **Direction is wrong / negligible.** The model *over*-predicts these brackets, so it would NOT
   systematically flag Kalshi as underpricing them — if anything the opposite. The earlier snapshot
   "edge" was the un-bias-corrected, fixed-σ Normal being wrong, not Kalshi.
2. **Fragility.** At σ=1.5 °F, **P(high ≥ μ+3) = 4.8%, but a 1 °F-too-cold forecast →15.9% (3.3×).**
   Tail probabilities are dominated by sub-degree forecast/bias error and the IEM-vs-CLI truth
   ambiguity. **No model at this σ can reliably adjudicate a 2–5% tail bracket vs Kalshi.**

**Edge-detection reliability (honest):** the model resolves *center* brackets (20–60%) to within a
few points and can flag a genuinely mispriced **modal/near-modal** bracket. It **cannot** reliably
flag a tail bracket — there, predicted vs realized diverge by 2–3× and a 1 °F nudge flips the call.

---

## 6. Reusable fair-value engine (`wx_fairvalue.py`)

```python
from wx_fairvalue import STATIONS, fair_value, FairValueParams, standard_brackets

# calibrated per-city params from §3 (bias subtracted from forecast; sigma = residual error)
params = FairValueParams(bias=-1.29, sigma=1.66, model='normal')   # e.g. CHI
brs    = [(None,73),(74,75),(76,77),(78,79),(80,81),(82,83),(84,85),(86,None)]
probs  = fair_value(brs, forecast_high=78.0, params=params)        # P per bracket, rounding-correct
```

- `fair_value(...)` is the single entry point the trading layer calls.
- `normal_probs / ensemble_probs / skewt_probs` are the three candidates (ensemble keeps a Normal
  fallback for thin member counts).
- `STATIONS` carries the exact Kalshi settlement station + truth source per city.
- **Recommended config: `model='normal'`, per-city `bias` and seasonal `sigma` from §3.**

`wx_calibrate.py` reproduces the entire dataset, metrics, and the decisive test from scratch
(cached).

---

## 7. Verdict & how to use it

- **Calibrated model achievable?** **Yes** — bias-corrected seasonal Normal, σ 1.1–1.8 °F next-day,
  reliable across 20–60% on an independent 2025 hold-out (Brier 0.066, PIT std 0.25). Ensemble (b)
  is *not* usable on the free tier (under-dispersed, thin archive); skew (c) adds nothing.
- **Next-day σ per city (°F):** NYC 1.65, CHI 1.66, MIA 1.39, AUS 1.55, LAX 1.12, PHX 1.31,
  DAL 1.49, BOS 1.75. Always apply the per-city cold-bias correction (−1.3 to −1.9 °F inland).
- **Tradable where?** The **center** — a calibrated edge vs a mispriced modal/near-modal Kalshi
  bracket is real and detectable. **Not the tail:** the warm-tail/above-mode brackets are ~1%
  events, the model over-predicts them, and a 1 °F error swings them 3×; there the "edge" is model
  error. **The `KALSHI_WEATHER.md` tail thesis does not survive independent calibration.**
- **No-lookahead:** uses only the archived forecast available at trade time; truth is station obs,
  never ERA5. Widen σ ~10–20% if entering >24 h before the local day.

### Sources / window
- Window: forecasts 2023-01-01 → 2025-12-31 (1,096 days/city), hold-out 2025; 8 cities.
- Open-Meteo historical-forecast-api (`models=gfs_seamless`, daily `temperature_2m_max`),
  ensemble-api (GEFS, ~92-day archive), archive-api (ERA5, used only for the lookahead audit).
- IEM ASOS daily summary (`mesonet.agron.iastate.edu/api/1/daily.json`) — realized station highs.
- Kalshi settlement station mapping cross-checked vs `KALSHI_WEATHER.md` (Austin = Camp Mabry/KATT).

### Files (this work)
- `wx_fairvalue.py` — reusable calibrated fair-value engine (the trading layer calls `fair_value`).
- `wx_calibrate.py` — dataset assembly + calibration validation (reproduces all metrics above).
- `wx_cache/` — cached raw pulls (git-ignored; do not commit).

### SCREENS / caveats
- IEM ASOS `max_tmpf` ≈ but not identical to the NWS CLI midnight-LST high (≤1 °F / rounding) — the
  dominant residual truth uncertainty, and exactly why tail-bracket calls are unreliable.
- hist-forecast archive lead may be ~morning-of (slightly shorter than a prior-evening entry); σ is a
  mild lower bound.
- GEFS ensemble archive on the free tier is too thin (≈5 days) and under-dispersed for calibration.
- Calibration is for the listed 8 dense-observation metros; sparser stations will have larger σ.
