# Audit: which BSDE candidates are vulnerable to the band-placement artefact E233 found in `relative_alpha_power`?

*2026-08-02. A reading audit (every registered candidate's frequency handling, classified and quoted) plus a
measurement audit (translation sensitivity on synthetic signals, >=8 seeds, two shift configurations). No
real data touched anywhere in this file's production — every number below comes from `numpy`-generated
signals. Not an experiment, not a registration, not a ledger row.*

---

## 0. Why this exists

E233 (`bsde/src/bsde/experiments/e233_band_placement_or_biology.py`) found that Challenge A's headline
alpha reversal is a band-placement artefact. `relative_alpha_power` is power in a **fixed 8-13 Hz window**
divided by total power. Sevoflurane slides the alpha peak downward with dose; propofol does not move it
much. A stationary box reads a moving peak as a change in power. Anchoring the band to each recording's own
peak (`relative_alpha_power_iaf`) collapsed the propofol/sevoflurane contrast from **+0.3673 [+0.2754,
+0.4584]** to **+0.0730 [-0.0107, +0.1584]** — an interval that now includes zero — on the identical 201
cases (`bsde/results/e233_band_placement_or_biology.json`).

`relative_alpha_power` is one candidate out of 24. Nobody had checked which of the other 23 share the same
structural vulnerability. This audit does that: read every candidate's frequency handling (§2), reason from
the code what a 1 Hz downward spectral shift should do to it (§2, third column), measure it on synthetic
signals (§3), and flag every place the reasoning and the measurement disagree (§5) — because a candidate
predicted invariant that turns out sensitive is the one finding this audit exists to surface.

**This is not the first time this project has asked this question.** `E214_frequency_sensitivity_transport`
already ran an independent synthetic sweep (7-12 Hz, 19-channel network, a different generator entirely) and
found that a feature's synthetic frequency-shift sensitivity `S` predicts its real propofol/sevoflurane
transport failure on VitalDB (rho = 0.5706, 95.83th percentile of a permutation null, verdict **FREQUENCY
PREDICTS TRANSPORT** — flagged in `E216` as weak, not robust to dropping any single feature). That result
already lives in `bsde/results/e214_frequency_sensitivity_transport.json`. This audit reproduces the shape
of that finding on an independently-built generator (§4 checks the two against each other point by point),
extends it to `alpha_peak_hz_wide` and `relative_alpha_power_iaf`, which post-date E214 and were never
measured this way, and adds what E214's aggregate correlation could not: a per-candidate code classification
with quoted lines, and a decomposition of *why* — in-box shift versus box-edge-crossing shift, which turn out
to behave completely differently for the same candidate.

---

## 1. Method

**Signal.** Reused verbatim from `tests/test_iaf_capability.py::_signal` (loaded by file path, not
reimplemented): two channels, 128 Hz, 30 s, each channel a Brownian-ish background
(`cumsum(N(0,1)) * 0.4`) plus a 1.2-amplitude sinusoid at a known frequency `f0` with an independent random
phase per channel. `tests/test_iaf_capability.py::_registry` was reused to build the exact same candidate
registry E233's own capability gate runs against.

**Two shift pairs**, both a 1 Hz downward shift, because a single generic pair cannot separate "sensitive
because the peak crosses a box edge" from "sensitive for some other reason":

- **PRIMARY, 10.0 -> 9.0 Hz** — the literal instruction, both frequencies inside the fixed 8-13 Hz alpha
  box.
- **EDGE, 8.5 -> 7.5 Hz** — the same 1 Hz shift, positioned to cross the alpha box's own 8 Hz lower edge —
  the configuration E233 actually implicates, and the one none of E233's own gates individually isolate.

**Seeds.** 12 (`seed = 100 + s`, `s` in 0..11, matching the test module's own seed convention), exceeding the
required 8. Every candidate was evaluated at both `f0` values on the **same 12 seeds**, so the background
noise realisation is shared between the base and shifted condition (paired design).

**Translation sensitivity.** For each candidate and each pair: `mean_base`, `sd_base` over the 12 base-`f0`
values; `mean_shift`, `sd_shift` over the 12 shifted-`f0` values; `pooled_sd = sqrt(mean(sd_base^2,
sd_shift^2))`; **sensitivity = (mean_shift - mean_base) / pooled_sd** — a Cohen's-d-style effect size: how
many of the candidate's own natural seed-to-seed standard deviations the 1 Hz shift moves it. Two
degenerate cases are reported separately rather than forced into this ratio: **zero pooled SD** (both
conditions perfectly deterministic across seeds — this happens for the two peak-*frequency* estimators,
which is a property of correctly tracking a bin-aligned test frequency, not a defect) is reported as a raw
Hz difference; **all-NaN at the standard 30 s duration** (`lrtc_alpha` only — its DFA scale requirement
needs roughly 80 s at 128 Hz, see §3.1) triggered a documented, disclosed extension to 100 s, used only to
obtain *any* measurement, never to change a verdict for a candidate that was already measurable.

**Compliance with the audit's hard rules.** `n` is printed and asserted non-empty at every stage: candidate
count (`n candidates registered: 24`, asserted `> 0`), seed count (12, `>= 8` required), and per-candidate
finite-value counts before any statistic is computed. Zero candidates raised an exception in either pair (no
`fn()` call failed) — this is stated explicitly because the instructions require a raised exception to be
reported, not dropped, and there was none to report. One candidate (`uce_v1`) initially returned all-NaN
because the test signal's channel names (`"a"`, `"b"`) do not match the frontal/posterior 10-20 names
`uce_v1` requires (`bsde/src/bsde/candidates/uce_v1.py::FRONTAL_CH`/`POSTERIOR_CH`); channel names were
changed to `["F3", "O1"]` for every candidate (no other candidate reads channel identity, so this does not
touch their numbers) and `uce_v1` became measurable. This is disclosed rather than silently fixed because it
changes what "all-NaN" would have meant for one named candidate.

**No real data was read, opened, or referenced anywhere in this audit.** Every array is `numpy`-generated.

---

## 2. Classification: every registered candidate's frequency handling

Source: `bsde/src/bsde/candidates/seed.py` (registration + adapters), plus the feature modules it calls
(`aperiodic.py`, `spectral.py`, `exotic.py`, `emg.py`, `connectivity.py`). 24 candidates are registered by
`seed_registry()`; all 24 are covered.

Categories: **(a) FIXED-BAND** — hard-coded frequency limits; **(b) PEAK-ANCHORED** — the window follows a
measured peak; **(c) BROADBAND/FREQUENCY-FREE** — no frequency window, or a window spanning virtually the
whole usable spectrum; **(d) SPECTRAL-SHAPE** — a slope/edge/percentile that moves *with* a shifting
spectrum rather than sitting in a stationary box.

### 2.1 The aperiodic-exponent family

| candidate | quoted code | class | reasoning: 1 Hz downward shift of the whole spectrum |
|---|---|---|---|
| `whole_head_exponent` | `seed.py:80-90` — `def _exponents(data, sfreq, lo: float = 1.0, hi: float = 40.0, ...)`: `fit_aperiodic(f, p, lo, hi, "loglog_robust")` | **(a) FIXED-BAND** (1.0-40.0 Hz fit range, hardcoded default) | A robust (peak-suppressing) log-log slope over 1-40 Hz. The oscillator sits well inside this huge range regardless of the shift, and `loglog_robust` iteratively drops the largest positive residuals — i.e. it is designed to suppress exactly the bias a moving peak would introduce. **Reasoned: LOW sensitivity.** |
| `uce_v1` | `seed.py:110-126` — `f_uce_v1` calls `regional_exponents(_exponents(data, sfreq), ch_names)`, the *same* `_exponents` as above (1.0-40.0 Hz, `loglog_robust`), then `0.696*z(frontal) + 0.718*z(posterior)` | **(a) FIXED-BAND** (identical exponent machinery to `whole_head_exponent`) | Same fit, same range, same robust mode, applied per-region then combined. **Reasoned: LOW sensitivity, and it should track `whole_head_exponent` almost exactly** (the project's own note: r=0.9952 on real EEG). |
| `exponent_gamma` | `seed.py:286-301` — `f_exponent_gamma`: `_exponents(data, sfreq, lo=50.0, hi=90.0)` | **(a) FIXED-BAND** (50-90 Hz, explicit hardcoded override) | 50-90 Hz is far above any 7-10 Hz alpha-range oscillator; a 1 Hz shift there has nothing to touch. **Reasoned: ~ZERO sensitivity for THIS test's frequencies** (by construction of the test, not because the candidate is safe in general — a shift affecting 50-90 Hz content would matter to it). |
| `exponent_low` | `seed.py:803-824` registers `_f_subband("exponent_low")` -> `exotic.py:277-297 subband_exponents()`: `fit_aperiodic(freqs, psd, fit_lo_hz=1.0, fit_hi_hz=20.0)` **with no `mode` argument** | **(a) FIXED-BAND** (1-20 Hz) | 1-20 Hz fully contains the 7-10 Hz test oscillator regardless of the shift, so band *width* alone predicts low sensitivity, same reasoning as `whole_head_exponent`. **Reasoned: LOW-to-moderate sensitivity.** **But note the code difference flagged in §5: this call omits `mode`, so `fit_aperiodic`'s default (`aperiodic.py:48-49`, `mode: str = "loglog_ols"`) is plain OLS — the peak-BIASED fit, not the peak-suppressing robust fit `whole_head_exponent` explicitly requests.** |
| `exponent_high` | same registration loop, `fit_aperiodic(freqs, psd, fit_lo_hz=20.0, fit_hi_hz=40.0)`, same missing `mode` | **(a) FIXED-BAND** (20-40 Hz) | 20-40 Hz is far above the 7-10 Hz test oscillator. **Reasoned: ~ZERO sensitivity for THIS test's frequencies**, same caveat about plain OLS as `exponent_low`. |

### 2.2 The alpha-box family (the one E233 already found reverses)

| candidate | quoted code | class | reasoning |
|---|---|---|---|
| `relative_alpha_power` | `seed.py:129-138 _band("alpha")` -> `spectral.py:20-26 BANDS = {"alpha": (8.0, 13.0), ...}`, `relative_band_power(f, p, lo, hi)` | **(a) FIXED-BAND** (8.0-13.0 Hz, over 1-45 Hz total) | Inside the box, a 1 Hz shift barely changes the integral. **Crossing the 8 Hz edge, the entire oscillator's power leaves the numerator** while the denominator (1-45 Hz total) is unaffected — a catastrophic, non-linear collapse. **Reasoned: LOW sensitivity for an in-box shift, CATASTROPHIC for an edge-crossing shift** — this is E233's own finding, restated as a prediction to be re-measured independently below. |
| `relative_theta_power` | `seed.py:521-535 _band("theta")` -> `BANDS["theta"] = (4.0, 8.0)` | **(a) FIXED-BAND** (4.0-8.0 Hz) | The mirror image of `relative_alpha_power`: a peak sliding down across 8 Hz **enters** this box rather than leaving one. **Reasoned: LOW in-box, CATASTROPHIC (rising) at the same 8 Hz edge, in the OPPOSITE direction to `relative_alpha_power`.** This directly bears on `relative_theta_power`'s own registration note, which reports it "markedly HIGHER when sevoflurane was co-administered" (E157/E156) and calls that a suspected pharmacological signature — see §6. |
| `relative_delta_power` | `seed.py:553-564 _band("delta")` -> `BANDS["delta"] = (1.0, 4.0)` | **(a) FIXED-BAND** (1.0-4.0 Hz) | Neither test frequency (7-10 Hz) is anywhere near this box. **Reasoned: ~ZERO sensitivity for THIS test.** |
| `alpha_peak_hz` | `seed.py:197-212`: `lo, hi = BANDS["alpha"]`; `m = (f>=lo)&(f<=hi)`; `f[m][argmax(p[m])]` — raw PSD maximum, **no aperiodic correction**, searched only inside 8-13 Hz | **(a) FIXED-BAND** (it "sounds" like a frequency estimate, but the vulnerability is a box-censoring one, and the project's own `tests/test_iaf_capability.py::test_the_incumbent_peak_estimator_is_WRONG_outside_its_band_not_merely_censored` already documents that it returns an interior value, not an edge, for any true peak outside 8-13 Hz) | In-box shifts should track correctly (raw PSD max at a strong, isolated peak is unbiased). **Once the true peak exits 8-13 Hz the estimator cannot report it and returns something else inside the box** — documented in the project's own capability test as "WRONG, not merely censored." **Reasoned: tracks correctly in-box, returns a wrong-but-plausible number at the edge (not simply flat).** |
| `alpha_peak_hz_wide` | `seed.py:141-179`: `PEAK_SEARCH_LO=5.0, PEAK_SEARCH_HI=15.0`; peak located on the **aperiodic-corrected residual** over 5-15 Hz; edge maxima return NaN | **(b) PEAK-ANCHORED** | The whole point of this candidate is to track the true peak wherever it is inside 5-15 Hz. **Reasoned: should track the shift almost exactly, in-box and at the 8 Hz edge alike**, since 8 Hz is deep inside its 5-15 Hz search range and carries no special status for it. |
| `relative_alpha_power_iaf` | `seed.py:182-194`: `IAF_HALFWIDTH_HZ=2.0`; `pk = _iaf_peak(...)`; `relative_band_power(f, p, pk-2, pk+2)` | **(b) PEAK-ANCHORED** | The band re-centres on the peak every time, so the numerator should represent "the oscillation" regardless of where it sits. **Reasoned: LOW sensitivity, in-box and at the edge alike** — this is E233's own instrument and its whole design intent. |

### 2.3 Spectral-shape measures (fixed *total* range, but not a narrow box)

| candidate | quoted code | class | reasoning |
|---|---|---|---|
| `spectral_edge_95` | `seed.py:215-218` -> `spectral.py:53-83 spectral_edge(freqs, psd, pct=95.0, lo_hz=1.0, hi_hz=45.0)` — frequency below which 95% of 1-45 Hz cumulative power lies | **(d) SPECTRAL-SHAPE** — this is the audit's named trap: "sounds band-limited and is a percentile" | A percentile of the cumulative power curve is a *statistic of the whole distribution*, not a box a peak can leave. **Reasoned: it should move roughly WITH the shift** (some fraction of 1 Hz, depending on how much of the total variance the oscillator carries and where in the cumulative curve it sits) — a smooth dependency, not a box-edge catastrophe. |
| `spectral_entropy` | `seed.py:221-224` -> `spectral.py:91-113 spectral_entropy(freqs, psd, lo_hz=1.0, hi_hz=45.0)` — Shannon entropy of the normalised 1-45 Hz power distribution | **(d) SPECTRAL-SHAPE** | Moving a narrowband peak changes how concentrated the spectrum is, which is exactly what entropy measures. **Reasoned: moderate, smooth sensitivity**, not a box-edge catastrophe (there is no box). |

### 2.4 Broadband / frequency-free measures

| candidate | quoted code | class | reasoning |
|---|---|---|---|
| `lempel_ziv` | `seed.py:328-371`: `LZIV_TARGET_HZ=100.0`; LZ76 complexity computed on **fixed 10 s time-domain windows** after decimation, no PSD step anywhere | **(c) BROADBAND/FREQUENCY-FREE** | A time-domain complexity count of the raw (decimated) waveform. **Reasoned: LOW sensitivity** — the waveform's overall complexity should depend only weakly on whether its embedded oscillation is at 9 or 10 Hz. |
| `multiscale_entropy_slope` | `exotic.py:156-207`: sample entropy across coarse-graining `scales` (in **samples**), no frequency-domain step | **(c) BROADBAND/FREQUENCY-FREE** | Same reasoning as `lempel_ziv`: a time-domain irregularity measure. **Reasoned: LOW sensitivity.** |
| `spatial_participation_ratio` | `exotic.py:47-83`: eigenvalues of the raw multichannel covariance matrix, no PSD, no frequency at all | **(c) BROADBAND/FREQUENCY-FREE** | Purely a spatial-covariance statistic. **Reasoned: ~ZERO sensitivity to a frequency shift** (both channels' oscillator amplitude is unchanged; only its frequency moves). |
| `emg_kurtosis` | `emg.py:66-87`: excess kurtosis of the **raw time series**, no PSD, no band at all | **(c) BROADBAND/FREQUENCY-FREE** | A distributional-shape statistic of the raw waveform. **Reasoned: ~ZERO sensitivity.** |
| `critical_slowing_ar1` | `exotic.py:316-397 critical_slowing(x, sfreq, env_band=(1.0, 45.0), ...)`; lag-1 autocorrelation of the **Hilbert envelope of the 1-45 Hz broadband signal**, at a fixed `CS_LAG_S=0.02` s | **(c) BROADBAND/FREQUENCY-FREE** — `env_band` covers virtually the entire usable spectrum (1-45 Hz), so this is not a box a peak can leave in the sense §2.2's candidates are | The band spans nearly the whole recorded spectrum, so there is no edge for either test frequency (7-10 Hz) to cross. **Reasoned: LOW sensitivity** — same logic as `whole_head_exponent`'s wide fit range. **This prediction is WRONG; see §5, the headline finding of this audit.** |

### 2.5 Fixed-band measures outside the alpha box (EMG, PAC, connectivity)

| candidate | quoted code | class | reasoning |
|---|---|---|---|
| `emg_beta_gamma_fraction` | `emg.py:42-63`: `EMG_BAND=(20.0,45.0)`, `TOTAL_BAND=(1.0,45.0)`; `relative_band_power(f,p,20,45,1,45)` | **(a) FIXED-BAND** (20.0-45.0 Hz) | Neither test frequency (7-10 Hz) is near this box. **Reasoned: ~ZERO sensitivity for THIS test** (would matter for a shift that actually crossed 20 Hz). |
| `emg_index` | `emg.py:90-110`: mean of `emg_beta_gamma_fraction` (fixed-band, above) and `emg_kurtosis` (broadband, §2.4), each rescaled | **MIXED** (fixed-band + broadband composite; reported here under FIXED-BAND for the "exactly one category" requirement, since one of its two ingredients is) | Both ingredients are reasoned above to be ~zero for this test's frequencies. **Reasoned: ~ZERO sensitivity.** |
| `pac_slow_alpha` | `exotic.py:228-270 phase_amplitude_coupling(x, sfreq, phase_band=(0.5,2.0), amp_band=(8.0,13.0), ...)` — Tort modulation index, **both bands hardcoded** | **(a) FIXED-BAND** (amplitude band 8.0-13.0 Hz, same box as `relative_alpha_power`) | The amplitude band is the *identical* 8-13 Hz box. **Reasoned: LOW in-box, sensitive at the 8 Hz edge**, same logic as `relative_alpha_power` — moving the carrier oscillation out of the amplitude band should sharply change how much "alpha amplitude" there is left to couple to slow phase. |
| `lrtc_alpha` | `seed.py:374-382 f_lrtc_alpha`: `lrtc_envelope(ch, sfreq, band=(8.0, 13.0))` — DFA of the **Hilbert envelope of a signal bandpassed to 8-13 Hz** | **(a) FIXED-BAND** (8.0-13.0 Hz, explicit hardcoded override of `lrtc_envelope`'s own default, which is also `(8.0,13.0)` — `exotic.py:469-470`) | In-box, the envelope should reflect the oscillation's own persistence. **Once the oscillation exits the passband, the "envelope" is filtered near-silence/background leakage** and DFA on it is measuring something structurally different. **Reasoned: LOW in-box, potentially large and possibly SIGN-REVERSING at the 8 Hz edge**, because DFA of near-silence is not a smooth extrapolation of DFA of a real oscillation's envelope. |
| `icoh_alpha` | `seed.py:385-396`: `imag_coherence(d[i], d[j], sfreq, 8.0, 13.0)` — fixed 8-13 Hz cross-spectrum band | **(a) FIXED-BAND** (8.0-13.0 Hz) | Same box as `relative_alpha_power`. In-box, two channels sharing an oscillator at a fixed phase offset should show real, stable imaginary coherence. **Once the oscillation exits 8-13 Hz, the band contains only whatever residual coupling the background happens to have there** (near-zero for uncorrelated backgrounds). **Reasoned: LOW in-box, large drop at the 8 Hz edge.** |
| `wpli_alpha` | `seed.py:399-410`: `wpli(d[i], d[j], sfreq, 8.0, 13.0)` — same fixed 8-13 Hz band, debiased weighted phase-lag index | **(a) FIXED-BAND** (8.0-13.0 Hz) | Identical reasoning to `icoh_alpha`: a genuine, consistent phase relationship inside the box in-box; largely gone once the oscillator leaves it. **Reasoned: LOW in-box, large drop at the 8 Hz edge.** |

**Tally: 15 of 24 candidates are FIXED-BAND (`whole_head_exponent`, `uce_v1`, `exponent_gamma`,
`exponent_low`, `exponent_high`, `relative_alpha_power`, `relative_theta_power`, `relative_delta_power`,
`alpha_peak_hz`, `emg_beta_gamma_fraction`, `emg_index` [mixed, one ingredient fixed-band], `pac_slow_alpha`,
`lrtc_alpha`, `icoh_alpha`, `wpli_alpha`), 2 are PEAK-ANCHORED (`alpha_peak_hz_wide`,
`relative_alpha_power_iaf`), 5 are BROADBAND/FREQUENCY-FREE (`lempel_ziv`, `multiscale_entropy_slope`,
`spatial_participation_ratio`, `emg_kurtosis`, `critical_slowing_ar1`), and 2 are SPECTRAL-SHAPE
(`spectral_edge_95`, `spectral_entropy`).** Five-eighths of the registry sits in the fixed-band category.

---

## 3. Measurement

Full console output and the raw per-seed values for all 24 candidates x 2 pairs are preserved in this
session's scratch directory (`measure_translation_sensitivity.py` and `audit_sensitivity_raw.json`); the
tables below carry every number needed to check the classification and ranking claims.

### 3.1 One candidate needed a documented duration extension

`lrtc_alpha` returned all-NaN for all 12 seeds at both `f0` values at the standard 30 s duration. This is
arithmetic, not a bug: `lrtc_envelope`'s DFA scale range defaults to `max_scale_s=20.0`
(`exotic.py:469-470`), and its own guard (`exotic.py:501-505`) refuses when the recording is shorter than
roughly `4 x max_scale_s` (~80 s at any rate) *and* shrinking the top scale would change the scale range by
more than a factor of `MAX_SCALE_SHRINK=2` (`exotic.py:463-466`). A 30 s signal fails both conditions.
Per §1's disclosed rule, `lrtc_alpha` alone was re-measured at 100 s; every other candidate's numbers below
are at the standard 30 s.

### 3.2 Primary pair (10.0 -> 9.0 Hz, both inside the fixed alpha box)

| candidate | mean_base | mean_shift | sd_base | sensitivity | status |
|---|---:|---:|---:|---:|---|
| `critical_slowing_ar1` | 0.4681 | 0.5427 | 0.0131 | **+5.999** | OK |
| `lrtc_alpha` (100 s) | 0.5786 | 0.6108 | 0.0180 | **+0.990** | OK (extended) |
| `exponent_low` | 1.9274 | 1.9621 | 0.0385 | **+0.902** | OK |
| `spectral_edge_95` | 10.5068 | 9.9787 | 0.1085 | **-1.631** | OK |
| `multiscale_entropy_slope` | -- | -- | 0.0208 | +0.299 | OK |
| `wpli_alpha` | 0.9142 | 0.9202 | 0.0437 | +0.132 | OK |
| `lempel_ziv` | -- | -- | 0.0441 | -0.139 | OK |
| `pac_slow_alpha` | 0.000173 | 0.000167 | 5.4e-5 | -0.120 | OK |
| `spectral_entropy` | -- | -- | 0.0080 | -0.125 | OK |
| `uce_v1` | -- | -- | 0.0620 | +0.034 | OK |
| `whole_head_exponent` | -- | -- | 0.0440 | +0.034 | OK |
| `relative_delta_power` | -- | -- | 0.0222 | -0.003 | OK |
| `relative_alpha_power` | 0.4358 | 0.4358 | 0.0169 | **+0.002** | OK |
| `relative_theta_power` | 0.0757 | 0.0758 | 0.0053 | +0.005 | OK |
| `emg_beta_gamma_fraction` | -- | -- | 0.0010 | +0.002 | OK |
| `icoh_alpha` | 0.6703 | 0.6688 | 0.2109 | -0.007 | OK |
| `spatial_participation_ratio` | -- | -- | 0.1461 | +0.001 | OK |
| `emg_index` | -- | -- | 0.0898 | +0.000 | OK |
| `exponent_high` | -- | -- | 0.1153 | +0.000 | OK |
| `exponent_gamma` | -- | -- | 0.8734 | -0.000 | OK |
| `emg_kurtosis` | -- | -- | 0.3922 | -0.001 | OK |
| `relative_alpha_power_iaf` | -- | -- | 0.0167 | +0.361 | OK |
| `alpha_peak_hz` | 10.000 | 9.000 | 0.000 | -- (raw diff **-1.000 Hz**) | zero-variance, perfect tracking |
| `alpha_peak_hz_wide` | 10.000 | 9.000 | 0.000 | -- (raw diff **-1.000 Hz**) | zero-variance, perfect tracking |

### 3.3 Edge pair (8.5 -> 7.5 Hz, crosses the alpha box's own 8 Hz lower edge)

| candidate | mean_base | mean_shift | sd_base | sensitivity | status |
|---|---:|---:|---:|---:|---|
| **`relative_alpha_power`** | 0.4336 | 0.0284 | 0.0124 | **-45.518** | OK — reproduces E233's collapse |
| **`relative_theta_power`** | 0.0761 | 0.4793 | 0.0062 | **+27.353** | OK — the mirror-image entry into theta |
| `critical_slowing_ar1` | 0.5772 | 0.6403 | 0.0139 | **+5.230** | OK |
| `lrtc_alpha` (100 s) | 0.6398 | 0.5154 | 0.0254 | **-4.113** | OK (extended) |
| `wpli_alpha` | 0.9236 | 0.5743 | 0.0430 | **-3.799** | OK |
| `pac_slow_alpha` | 0.000167 | 0.001356 | 6.9e-05 | **+3.713** | OK |
| `icoh_alpha` | 0.6672 | 0.4891 | 0.2116 | **-0.956** | OK |
| `exponent_low` | 1.9793 | 2.0137 | 0.0384 | +0.895 | OK |
| `multiscale_entropy_slope` | -- | -- | 0.0246 | +0.258 | OK |
| `lempel_ziv` | -- | -- | 0.0434 | -0.209 | OK |
| `spectral_entropy` | -- | -- | 0.0091 | -0.108 | OK |
| `relative_delta_power` | -- | -- | 0.0178 | +0.093 | OK |
| `emg_beta_gamma_fraction` | -- | -- | 0.0012 | +0.070 | OK |
| `spectral_edge_95` | 10.0153 | 10.0502 | 0.5445 | +0.065 | OK |
| `whole_head_exponent` | -- | -- | 0.0451 | -0.060 | OK |
| `uce_v1` | -- | -- | 0.0636 | -0.058 | OK |
| `relative_alpha_power_iaf` | -- | -- | 0.0127 | +0.473 | OK |
| `emg_index` / `exponent_high` / `exponent_gamma` / `spatial_participation_ratio` / `emg_kurtosis` | -- | -- | -- | ~0.000 each | OK |
| `alpha_peak_hz` | 8.500 | 8.625 | 0.000 (0.687 shift) | +0.257 (small raw diff, `0.125 Hz` against a true `1.000 Hz` move) | OK — **wrong, not merely flat, per §2.2** |
| `alpha_peak_hz_wide` | 8.500 | 7.500 | 0.000 | -- (raw diff **-1.000 Hz**, correctly tracks the edge) | zero-variance, perfect tracking |

Zero candidates raised an exception in either pair. Zero remained NaN once `lrtc_alpha`'s documented
extension is applied.

---

## 4. Cross-check against E214's independent measurement

`bsde/results/e214_frequency_sensitivity_transport.json` measured `S = |Spearman(f0, value)|` for every
candidate registered at the time, sweeping `f0` continuously over 7.0-12.0 Hz on a completely different
19-channel synthetic generator (shared + independent 1/f^1.5 pink components, `OSC_FRACTION=0.35`). Its top
of the ranking:

| rank | candidate | E214's S | this audit's max\|sensitivity\| (primary/edge) |
|---|---|---:|---:|
| 1 | `critical_slowing_ar1` | 0.9960 | **5.999 / 5.230** |
| 1= | `spectral_edge_95` | 0.9960 | 1.631 / 0.065 |
| 3 | `exponent_low` | 0.9957 | 0.902 / 0.895 |
| 4 | `alpha_peak_hz` | 0.9909 | (tracks in-box, wrong at edge) |
| 5 | `lempel_ziv` | 0.9243 | 0.139 / 0.209 |
| 6 | `multiscale_entropy_slope` | 0.9170 | 0.299 / 0.258 |
| 7 | `relative_theta_power` | 0.7779 | 0.005 / **27.353** |
| 8 | `pac_slow_alpha` | 0.7203 | 0.120 / 3.713 |
| 9 | `relative_alpha_power` | 0.6657 | 0.002 / **45.518** |
| 10 | `whole_head_exponent` | 0.4653 | 0.034 / 0.060 |
| 11 | `icoh_alpha` | 0.4102 | 0.007 / 0.956 |
| 12 | `wpli_alpha` | 0.3785 | 0.132 / 3.799 |
| 13 | `lrtc_alpha` | 0.1881 | 0.990 / 4.113 |
| 14 | `exponent_gamma` | 0.1205 | ~0 / ~0 |
| 15 | `spectral_entropy` | 0.0840 | 0.125 / 0.108 |
| 16-21 | (`emg_index`, `emg_kurtosis`, `relative_delta_power`, `spatial_participation_ratio`, `emg_beta_gamma_fraction`, `exponent_high`) | 0.067 down to 0.0045 | ~0 each |
| -- | `uce_v1` | excluded (not computable on E214's channel names) | 0.034 / 0.058 |
| -- | `alpha_peak_hz_wide`, `relative_alpha_power_iaf` | not registered yet when E214 ran | 0.361-0.473 (or perfect Hz tracking) |

**The two measurements agree on the headline finding and disagree usefully on one thing.** Both
independently rank `critical_slowing_ar1` as extremely frequency-sensitive — this is now a **twice-measured,
independently-generated result**, not an artefact of one synthetic generator's quirks. Both rank
`exponent_low` and `spectral_edge_95` high and the alpha-box family (`relative_alpha_power`,
`relative_theta_power`, `pac_slow_alpha`) as *conditionally* high (E214's continuous 7-12 Hz sweep crosses
the 8 Hz edge, so its aggregate `S` for these three is dominated by exactly the edge-crossing behaviour this
audit's EDGE pair isolates directly).

**Where they diverge is informative, not contradictory: `lempel_ziv` and `multiscale_entropy_slope` score
very high on E214's `S` (0.9243, 0.9170) but only moderate on this audit's per-Hz effect size (0.14-0.21,
0.26-0.30).** The two statistics answer different questions. `S = |Spearman(f0, value)|` measures
**monotonic consistency across a 5 Hz sweep** — it is scale-free, so a small but perfectly consistent drift
scores nearly as high as a large one. This audit's `sensitivity` measures a **magnitude, normalised by
noise, for one specific 1 Hz step**. A time-domain complexity measure can move smoothly and consistently in
one direction across a wide sweep (high `S`) while any single 1 Hz step within it is modest relative to
seed noise (moderate `sensitivity`). Both are real properties and neither supersedes the other; a full risk
assessment for these two candidates should use both.

---

## 5. Where reasoning (§2) and measurement (§3) disagree — reported loudly, per instruction

**(1) `critical_slowing_ar1` — predicted LOW (broadband, `env_band=(1.0,45.0)` spans virtually the whole
usable spectrum), measured HIGHEST in the entire panel (+5.999 / +5.230), and independently confirmed as
the single most sensitive candidate on a completely different generator (E214, S=0.9960, tied for #1).**
This is the most valuable finding in this audit, precisely because "broadband, therefore translation
invariant" is exactly the intuition that failed. The mechanism is not band placement in the §2.2 sense —
there is no box to leave — but the underlying statistic (lag-1 autocorrelation of the broadband Hilbert
envelope at a fixed 20 ms lag) is evidently very sensitive to the exact carrier frequency of a narrowband
oscillation riding on the background, which changes the beating/interference structure the envelope
exhibits at that specific lag. **The category "no frequency window" does not imply "insensitive to
frequency"; this audit's own §2 reasoning conflated the two, and the measurement is what caught it.**

**(2) `exponent_low` / `exponent_high` — predicted the SAME risk tier as `whole_head_exponent`/
`exponent_gamma` (all four are FIXED-BAND aperiodic exponents, and the test frequencies sit fully inside all
four fit ranges), but `exponent_low` measures ~26x more sensitive than `whole_head_exponent` (0.902 against
0.034) despite an equally wide, equally test-frequency-enclosing fit range.** Traced to a genuine code-level
cause, not a band-width difference: `_exponents()` (used by `whole_head_exponent`, `uce_v1`,
`exponent_gamma`) explicitly passes `mode="loglog_robust"` (`seed.py:87`); `subband_exponents()` (used by
`exponent_low`/`exponent_high`, `exotic.py:295-296`) calls `fit_aperiodic` **with no `mode` argument at
all**, silently taking `aperiodic.py:48-49`'s default, `mode: str = "loglog_ols"` — the plain, **peak-biased**
fit the module's own docstring warns against (`aperiodic.py:3-11`: *"A plain OLS fit is biased by any
oscillatory peak inside that range: alpha power sitting on the line pulls the slope"*). This is a second,
independent finding beyond the audit's scope as originally framed, and it is reported here because it
directly explains a ranking result: **`exponent_low` and `exponent_high` are not more translation-sensitive
because their band is narrower or better-placed to catch the test oscillator — they are more sensitive
because they use a fitting method the rest of the exponent family deliberately avoids for this exact
reason.**

**(3) `relative_alpha_power` / `relative_theta_power` — predicted catastrophic sensitivity at the 8 Hz edge,
confirmed spectacularly (-45.518 / +27.353), reproducing E233's finding independently.** Not a disagreement,
but worth stating plainly: `relative_theta_power`'s registration note (`seed.py:521-535`) reports it
"markedly HIGHER when sevoflurane was co-administered" (E157, MGH OR cohort) and frames that as a
**suspected pharmacological signature**. This audit's edge measurement shows the *identical* box-crossing
arithmetic that E233 found for alpha — a peak sliding down out of the alpha box necessarily raises theta's
share of a fixed total, with no drug-specific mechanism required. **`relative_theta_power`'s E157 finding is
now a second candidate for the same band-placement artefact, not yet tested the way E233 tested alpha's.**
See §6.

**(4) `alpha_peak_hz` at the edge — a small measured `sensitivity` score (+0.257) understates what is
actually wrong.** The raw numbers (`mean_base=8.500`, `mean_shift=8.625`) show the estimator barely moves at
all when the true peak moves a full 1 Hz below the box — but not because it is *insensitive*: because it is
**censored and returns a plausible-looking wrong number close to the band edge**, exactly as
`tests/test_iaf_capability.py::test_the_incumbent_peak_estimator_is_WRONG_outside_its_band_not_merely_censored`
already documents. A low sensitivity SCORE here is not evidence of safety; §2's classification (FIXED-BAND,
not PEAK-ANCHORED) is the one that should be trusted, and the score is flagged so a reader does not read
"0.257" as "low risk."

**No candidate reasoned to be FIXED-BAND-and-therefore-high-risk came back measured as safe.** Every
FIXED-BAND candidate whose test frequencies straddled its own box edge (the alpha-box family: `alpha_power`,
`theta_power`, `pac_slow_alpha`, `lrtc_alpha`, `icoh_alpha`, `wpli_alpha`) showed a large edge-pair
sensitivity (|value| from 0.956 to 45.518); the reasoning under-predicted magnitude in no case examined.

---

## 6. Ranked list and what it says about this project's own results

Ranked by `max(|primary sensitivity|, |edge sensitivity|)` (peak-frequency estimators excluded from this
sequence and discussed separately at the end, since they are not ratio measures and "sensitivity" is the
wrong unit for them):

1. **`relative_alpha_power`** — 45.518 (edge). Already corrected: E233.
2. **`relative_theta_power`** — 27.353 (edge). **Not yet corrected** — see below.
3. **`critical_slowing_ar1`** — 5.999 (primary). Not band-placement in the box sense; a genuine, unexplained
   frequency dependency of the envelope-autocorrelation statistic itself. Not yet used in any registered
   Challenge A/B/C result as far as this audit checked; worth an aliveness check before it is.
4. **`lrtc_alpha`** — 4.113 (edge). Used in E42 ("`lrtc_refined_marker`") for Challenge B.
5. **`wpli_alpha`** — 3.799 (edge). Used in the connectivity family: E39 (`wpli_artefact_robustness`), E73
   (`challenge_b_connectivity`).
6. **`pac_slow_alpha`** — 3.713 (edge). Any propofol phase-amplitude-coupling claim using this candidate
   inherits the same 8 Hz-edge risk as `relative_alpha_power` directly, since it shares that exact band as
   its amplitude window.
7. **`spectral_edge_95`** — 1.631 (primary). A commercial-monitor-style incumbent used as a comparator
   alongside the connectivity/exponent panel in E39, E42 and E73 (confirmed by grep, not by filename alone);
   moderate, smooth sensitivity, not yet implicated in a reversal but not negligible either.
8. **`icoh_alpha`** — 0.956 (edge). Same connectivity family as `wpli_alpha`.
9. **`exponent_low`** — 0.902 (both pairs, essentially identical). Colombo et al. band-split replication
   candidate (E52 `subband_sign_agreement`) — carries BOTH the fixed-band risk and the plain-OLS risk
   flagged in §5(2).
10. **`relative_alpha_power_iaf`** — 0.473 (edge), 0.361 (primary). The lowest sensitivity of any candidate
    that actually *touches* the alpha band (all five other alpha-box candidates above rank 0.956 or
    higher), and roughly two orders of magnitude below the fixed measure it replaces at the edge (0.473
    against 45.518) — consistent with E233's own finding that anchoring collapses but does not fully zero
    out the contrast. It ranks ahead of 12 of the other 23 candidates, including several that were reasoned
    (§2) to be low-risk for structural reasons (no alpha-band content at all): anchoring narrows the
    vulnerability substantially, it does not make this candidate as translation-invariant as a genuinely
    frequency-free measure, and that should be stated honestly alongside any future claim built on it.
11. **`multiscale_entropy_slope`** — 0.299 (primary). Low by this audit's local-step metric, but E214's
    `S=0.9170` says its cross-sweep monotonic dependency is high; see §4's reconciliation.
12. **`lempel_ziv`** — 0.209 (edge). Same reconciliation as above (E214 `S=0.9243`).
13-17. `spectral_entropy` (0.125), `relative_delta_power` (0.093), `emg_beta_gamma_fraction` (0.070),
    `whole_head_exponent` (0.060), `uce_v1` (0.058) — all under 0.13, low risk by both measurements.
18-22. `emg_kurtosis` (0.001), `spatial_participation_ratio` (0.001), `exponent_gamma` (~0.000),
    `exponent_high` (~0.000), `emg_index` (~0.000) — approximately zero by both measurements, for this
    test's frequencies.

Reported separately, in Hz rather than as a ratio: `alpha_peak_hz_wide` tracks the true peak exactly (raw
difference -1.000 Hz) at both the in-box and edge-crossing pair, essentially zero seed noise. `alpha_peak_hz`
tracks correctly in-box (raw difference -1.000 Hz) but is **WRONG, not merely insensitive**, at the edge
(raw difference only +0.125 Hz for a true 1.000 Hz move, landing on an interior value near the band floor
rather than either the old or new true peak) — the failure mode is exactly the one the project's own
`tests/test_iaf_capability.py::test_the_incumbent_peak_estimator_is_WRONG_outside_its_band_not_merely_censored`
already documents, reproduced here from a fresh, independent run.

**Concretely, which of this project's own results are most at risk:**

- **`relative_theta_power`'s E157 sevoflurane co-administration finding (signed AUC 0.9457, described as
  "markedly HIGHER") is a strong candidate for the same artefact E233 already found in `relative_alpha_power`
  — same box, same edge, opposite (and mechanically necessary) direction.** It has not yet been through
  E233's own treatment (an anchored-band counterpart, an arm-label placebo). This is this audit's single
  most concrete, actionable recommendation.
- **Any Challenge A/B finding built on `wpli_alpha`, `icoh_alpha`, `lrtc_alpha` or `pac_slow_alpha`** shares
  `relative_alpha_power`'s exact 8-13 Hz box and is exposed to the same agent-dependent-peak-location
  mechanism. This includes the connectivity-family experiments (E39, E73) and the Challenge B LRTC candidate
  (E42).
- **`exponent_low`/`exponent_high`'s replication of Colombo et al.'s band-split finding (E52) carries a
  second, independent risk** (the plain-OLS peak bias, §5(2)) on top of the ordinary fixed-band risk, and
  should be re-run with `mode="loglog_robust"` before being read as a clean replication.
- **`critical_slowing_ar1` is not currently implicated in any specific registered claim this audit checked**,
  but given it is the single most translation-sensitive candidate in the entire registry by two independent
  measurements, any future use of it against a cross-agent or cross-deposit contrast should be treated with
  the same suspicion `relative_alpha_power` earned, and probably more.
- **E214/E216's own "FREQUENCY PREDICTS TRANSPORT" finding (rho=0.5706, 95.83th percentile) is corroborated,
  not merely repeated**, by an independently-built generator arriving at the same top-ranked candidates. Its
  own stated weakness (not robust to dropping any single feature) is a separate, real caveat this audit does
  not resolve.

---

## 7. Limitations

- Both shift pairs used one synthetic generator (a Brownian-ish 1/f^2-like background plus one narrowband
  sinusoid); E214 used a different one (network of 1/f^1.5 components). Where the two agree, that is
  meaningful triangulation; where a candidate was only measured by one of them (e.g. `alpha_peak_hz_wide`,
  `relative_alpha_power_iaf`, both post-dating E214), the single-generator caveat applies as stated in
  E214's own scope note: *"a low S is weak evidence of invariance, whereas a high S is strong evidence of
  sensitivity."* The same asymmetry applies to this audit's `sensitivity` score.
- The EDGE pair (8.5 -> 7.5 Hz) was chosen to cross the specific 8 Hz alpha lower edge because that is the
  configuration E233 found in real VitalDB data; it does not exercise the 13 Hz alpha upper edge, the 4 Hz
  theta/delta edge, or the 20 Hz/40 Hz exponent sub-band edges, each of which would need its own targeted
  pair to characterise with the same rigor this file gives the 8 Hz edge.
- Two channels with an independent random phase offset per channel is sufficient to exercise the connectivity
  candidates' fixed-band machinery (a real, consistent cross-channel phase relationship exists at the test
  oscillator's frequency) but is not a claim about real montage or volume-conduction structure.
- This is a synthetic audit. It establishes *capability* (what a candidate's code does to a signal whose true
  peak is known), not that any specific published result in this project's ledger is wrong — E233 already
  established that for `relative_alpha_power` on real data; the other candidates flagged here need their own
  E233-style real-data test before a correction is warranted.

---

## OPUS VERIFICATION, 2026-08-02 — the estimator defect is real, and the docstring asserts the invariant the code breaks

Checked against the source rather than against the audit's report of it.

`bsde/src/bsde/features/aperiodic.py:48` — the default is **`mode: str = "loglog_ols"`**.

```
bsde/src/bsde/features/exotic.py:295   low  = fit_aperiodic(freqs, psd, fit_lo_hz=1.0,  fit_hi_hz=20.0)
bsde/src/bsde/features/exotic.py:296   high = fit_aperiodic(freqs, psd, fit_lo_hz=20.0, fit_hi_hz=40.0)
bsde/src/bsde/candidates/seed.py:87    out.append(fit_aperiodic(f, p, lo, hi, "loglog_robust")["exponent"])
bsde/src/bsde/candidates/seed.py:166   ap = fit_aperiodic(f, p, fit_lo_hz=1.0, fit_hi_hz=45.0)
```

So `exponent_low` and `exponent_high` are fitted by **plain OLS**, while the `whole_head_exponent` /
`exponent_gamma` family is fitted **robustly**. Over 1–20 Hz an OLS log-log fit is pulled by the alpha
peak, which is exactly why `exponent_low` measures as far more translation-sensitive than
`whole_head_exponent` despite an equally wide fixed band. **`seed.py:166` shares the defect and it is the
more consequential instance**: that is `alpha_peak_hz_wide`'s own aperiodic fit, and the peak is found as
a residual *after* subtracting it — so a peak-biased baseline flattens the very residual the peak search
depends on. Every peak-anchored result today, E233 included, rests on that line.

**The docstring at `seed.py:290` asserts the invariant the code breaks**, in terms that leave no room for
reading this as an intentional choice:

> *"Deliberately identical machinery to `_exponents`, differing only in the band, so any difference from
> `exponent_high` reflects the spectrum and not the estimator (the same discipline `subband_exponents`
> states for the 1-20/20-40 split)."*

`subband_exponents` does not state that discipline; it silently takes a different one.

**NOT FIXED HERE, deliberately.** Changing the estimator changes every result computed with these
columns — E52 exists specifically to compare subband exponents across pipelines and would have to be
re-derived, not merely re-run (rules 1 and 2). The correction belongs in a registered experiment that
enumerates the downstream claims first. What is recorded now is that the inconsistency exists, where it
is, and that it reaches `alpha_peak_hz_wide`.
