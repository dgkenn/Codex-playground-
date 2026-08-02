# Why `multiscale_entropy_slope` collapses on ds006695: a mechanism probe, not a registration

*DIAGNOSTIC ONLY, 2026-08-02. No ledger row, no registration, no change to `bsde/src/bsde/experiments/` or
`bsde/governance/`. Written to explain a result already on the record (E222 +0.0280 [+0.011,+0.049];
E240 +0.0043 [-0.0145,+0.0422]; the within-deposit transport diagnostic in
`PROBE_2026_08_02_SEPARABILITY.md` §15.2, d=+4.4067/AUC 0.998 on sleep_edfx vs d=+0.6928/AUC 0.773 on
ds006695) — not a new claim about either number.*

## 0. Bottom line, stated first

**Reasoning from the code alone points to one bug — and a direct test in §4 shows that bug is NOT
sufficient to explain the collapse.** Read this section together with §6 (the ranked verdict); it would be
misleading on its own.

The scales `multiscale_entropy_slope` uses are counted in SAMPLES, and `sfreq` is deliberately unused (kept
only for API symmetry with the module's other functions). The docstring says so explicitly:

> `"scale" in samples of the coarse-grained series (the standard multiscale-entropy convention counts
> scale in samples, not seconds — `sfreq` is accepted for API consistency with the rest of this module and
> is not otherwise used; nothing here needs a physical time unit)."`

That is true to the Costa et al. (2002) convention taken in isolation, and looks like it should be false as
an assumption once the same feature is compared **across two deposits sampled at different rates**. At
sleep_edfx's 100 Hz the five scales `(1,2,4,8,16)` span coarse-graining windows of **10–160 ms**; at
ds006695's 500 Hz the *same nominal scales* span **2–32 ms** — a fivefold-narrower and much higher-frequency
window at every rung. The project has hit this exact bug class twice before in this same file
(`critical_slowing`'s lag, fixed to be seconds-based; and this function's own *series length*, already fixed
via `max_samples`), and the natural prediction from that history is that this is the third instance and the
cause of the collapse.

**§4 directly tested that prediction — downsampling ds006695's raw signal from 500 Hz to 100 Hz, so the
identical nominal scale ladder now spans the identical physical time window sleep_edfx's does — and
discrimination did NOT recover** (AUC 0.763 native → 0.748 downsampled; |d| 0.913 → 0.916, unchanged within
noise). **The scale-in-samples definition is still a real bug and still worth fixing**, but it is
demonstrated here NOT to be what is suppressing `multiscale_entropy_slope`'s discrimination on ds006695. See
§6 for the ranking this leaves, with channel montage as the best-supported remaining candidate — untested
directly, and reported as a hypothesis, not a finding.

---

## 1. The implementation, quoted exactly

`bsde/src/bsde/candidates/seed.py`, the registered candidate wrapper:

```python
EXPENSIVE_CHANNEL_CAP = 8

def _subset(data):
    import numpy as _np
    d = _np.asarray(data, float)
    return d[:EXPENSIVE_CHANNEL_CAP] if d.shape[0] > EXPENSIVE_CHANNEL_CAP else d

def f_mse_slope(data, ch_names, sfreq, meta=None) -> float:
    from bsde.features.exotic import multiscale_entropy_slope
    import numpy as _np
    v = [multiscale_entropy_slope(ch, sfreq) for ch in _subset(data)]
    v = [x for x in v if _np.isfinite(x)]
    return float(_np.mean(v)) if v else float("nan")
```

`bsde/src/bsde/features/exotic.py`, the function itself (constants and the length/scale/tolerance logic —
quoted, not paraphrased):

```python
def multiscale_entropy_slope(x: np.ndarray, sfreq: float, scales: tuple = (1, 2, 4, 8, 16),
                             m: int = 2, r_frac: float = 0.2, max_samples: int = 4000) -> float:
    """Slope (least squares) of sample entropy against `log2(scale)` across `scales`, `scale` in samples of
    the coarse-grained series (the standard multiscale-entropy convention counts scale in samples, not
    seconds — `sfreq` is accepted for API consistency with the rest of this module and is not otherwise
    used; nothing here needs a physical time unit).
    ...
    """
    x = np.asarray(x, float).ravel()
    if max_samples and x.size > max_samples:
        x = x[:max_samples]
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 50:
        return float("nan")
    sd = x.std()
    if sd <= 0:
        return float("nan")
    r = r_frac * sd
    log2_scales, sampens = [], []
    for s in scales:
        cg = _coarse_grain(x, s)
        if cg.size < m + 2:
            continue
        se = sample_entropy(cg, m=m, r=r)
        if np.isfinite(se):
            log2_scales.append(np.log2(s))
            sampens.append(se)
    if len(sampens) < 2:
        return float("nan")
    A = np.vstack([log2_scales, np.ones(len(log2_scales))]).T
    coef, *_ = np.linalg.lstsq(A, np.array(sampens), rcond=None)
    return float(coef[0])
```

`_coarse_grain` (Costa non-overlapping block average, scale explicitly documented as **samples**):

```python
def _coarse_grain(x: np.ndarray, scale: int) -> np.ndarray:
    """Non-overlapping block-average coarse-graining (Costa et al. 2002), scale in SAMPLES."""
    n = x.size
    n_blocks = n // scale
    if n_blocks < 1:
        return np.array([])
    return x[:n_blocks * scale].reshape(n_blocks, scale).mean(axis=1)
```

`sample_entropy`, showing `m` and `r`:

```python
def sample_entropy(x: np.ndarray, m: int = 2, r: float | None = None, r_frac: float = 0.2) -> float:
    ...
    if r is None:
        sd = x.std()
        if sd <= 0:
            return float("nan")
        r = r_frac * sd
    if r <= 0 or n < m + 2:
        return float("nan")
```

**Exact constants, as they appear in the signatures and are called from `seed.py` (no overrides anywhere in
either compute script — grepped, none found):**

| constant | value | unit |
|---|---|---|
| `scales` | `(1, 2, 4, 8, 16)` | **samples**, not seconds |
| `m` (embedding dimension) | `2` | — |
| `r_frac` | `0.2` | fraction of the ORIGINAL (scale-1) series' own std, held fixed across scales |
| `max_samples` | `4000` | samples, applied by truncating (not resampling) the input BEFORE coarse-graining |
| minimum usable length | `n >= 50` after truncation; `cg.size >= m + 2 = 4` per scale; `>= 2` finite scales required for a slope |
| `sfreq` | accepted, **never used** inside the function body |
| channel handling | first `EXPENSIVE_CHANNEL_CAP = 8` channels, mean of per-channel slopes |

---

## 2. The two deposits' signal properties, asserted from the data and scripts

| property | sleep_edfx (E222) | ds006695 (E240) | source |
|---|---|---|---|
| sampling rate | **100 Hz** | **500 Hz** | `sleep_edfx_five_stage.csv` col `sfreq` (all 710 rows); `ds006695_epoch_index.csv` col `sfreq` (all 1140 rows, single value `{500}`) |
| channel count reaching the feature | **2** (`EEG Fpz-Cz`, `EEG Pz-Oz`, matched by `channel_regex = "^EEG "` in `build_sleep_edfx_labels.py:50`) | **3** (`FP1-AFz`, `FP2-AFz`, `FF` — bipolar frontal derivations, `ds006695_compute_features.py:100`, "verified identical across all 19 subjects") | grep'd from source, confirmed against CSV `n_channels` columns (`{2}` / `{3}`) |
| window/epoch length fetched | **120 s** (`WINDOW_S = 120.0` in `build_sleep_edfx_five_stage.py:41`) = 12,000 samples @ 100 Hz | **30 s** fixed epoch (`EPOCH_SEC = 30` in `ds006695_signal.py:59`) = 15,000 samples @ 500 Hz | `sleep_edfx_five_stage.csv` col `n_samples = 12000` (all rows); `ds006695_signal.py:246` `samples_per_epoch = EPOCH_SEC * srate` |
| samples actually reaching `_coarse_grain` (post `max_samples` truncation) | **4000** (of 12,000; first 4000, i.e. first **40 s** of the 120 s window) | **4000** (of 15,000; first 4000, i.e. first **8 s** of the 30 s epoch) | `max_samples=4000` applied unconditionally before scale 1 in both cases (both raw lengths exceed 4000) |
| filtering recorded in the extraction scripts | none recorded; `read_edf_window_http` reads and scales raw EDF digital values, no bandpass/notch applied by this project's code | none recorded; MAT5/`.fdt` bytes read verbatim, no filter applied by this project's code | grep of `http_edf.py`, `ds006695_signal.py`, `ds006695_compute_features.py` — no filter/bandpass/notch/resample calls found outside the candidate functions themselves |
| stage n used in the transport diagnostic already on record | W 142, N3 141 (one row per subject already — sleep_edfx is not epoch-repeated in the same way) | W 19, N3 19 — **each subject's 12 epochs/stage are AVERAGED (mean) to one value before any effect size is computed** (`PROBE_2026_08_02_SEPARABILITY.md` §15.0: "ds006695's 12 epochs per subject per stage are averaged to one value per subject per stage before any effect size is computed... treating epochs as independent rows would inflate n on a nested, repeated measurement") | `PROBE_2026_08_02_SEPARABILITY.md` §15.0, §15.2 |
| stage n used in THIS probe's direct test (§4) | n/a (sleep_edfx not re-touched here) | **W 76, N3 76** RAW EPOCHS, not subject-averaged (first 4 of 12 epochs/subject × 19 subjects, deterministic slice) — a deliberately noisier, non-aggregated unit of analysis than §15.2's, chosen so the SAME transform (decimate) can be applied to each raw epoch and compared to itself before/after. Native-500Hz numbers in §4 are therefore **not expected to reproduce §15.2's d=0.6928/AUC=0.773 exactly** — they are the epoch-level, non-subject-averaged analogue, reported for internal (before-vs-after) comparison, not as a replacement for the registered subject-level number. | this probe, §4 |

No filter setting is recorded anywhere in this project's own extraction code for either deposit — this
probe cannot assert what hardware/software prefilter, if any, was applied upstream (e.g. an EDF `prefilter`
header field for sleep_edfx was not read by any script here). This is a gap in what can be asserted, not a
finding, and is flagged rather than guessed at (rule 5's discipline applied to absence of information).

---

## 3. The likely culprits, tested rather than reasoned about

### (a) Scale coverage — effective length per scale

`max_samples = 4000` is applied **before** any coarse-graining, and it truncates unconditionally in both
deposits (both raw window/epoch lengths exceed 4000 samples). So the coarse-grained series length at every
scale is **identical in samples between the two deposits**:

| scale (samples) | `n_blocks = 4000 // scale` | sleep_edfx real time / scale | ds006695 real time / scale |
|---:|---:|---:|---:|
| 1 | 4000 | 10 ms | 2 ms |
| 2 | 2000 | 20 ms | 4 ms |
| 4 | 1000 | 40 ms | 8 ms |
| 8 | 500 | 80 ms | 16 ms |
| 16 | 250 | 160 ms | 32 ms |

Every row clears `cg.size >= m + 2 = 4` with enormous headroom in both deposits (250 is the smallest, at
scale 16). **Scale coverage is not the differentiator** — neither deposit runs out of points first, because
both are looking at the same 4000-sample budget. This rules out culprit (a) as stated. What is *not* equal
is how much real time that budget represents: 40 s of a 120 s window at 100 Hz, vs 8 s of a 30 s epoch at
500 Hz — noted here as a secondary asymmetry (§3, closing note) but it is a duration difference, not a
scale-coverage failure.

### (b) Sampling rate — scales in samples, not seconds

Confirmed directly from the docstring and the constant list in §1: `scales=(1,2,4,8,16)` are samples, and
`sfreq` is accepted but structurally unused (`grep sfreq bsde/src/bsde/features/exotic.py` inside this
function's body returns nothing beyond the signature and docstring). Consequently the SAME nominal scale
tuple spans:

- sleep_edfx (100 Hz): **10 ms to 160 ms** — coarse-graining at scale 16 averages 16 consecutive 10 ms
  samples, which is a form of low-pass smoothing that suppresses content above roughly `100/(2·16) ≈ 3 Hz`
  at the top scale and up to Nyquist (50 Hz) at scale 1. The scale ladder therefore sweeps down into the
  **delta/theta range**, exactly where wake-vs-N3 slow-wave content differs most.
- ds006695 (500 Hz): **2 ms to 32 ms** — the same ladder now sweeps `500/(2·16) ≈ 15.6 Hz` up to Nyquist
  (250 Hz). Every rung stays inside the **beta/gamma/high-frequency** range; the ladder never reaches the
  slow-wave band where the wake/N3 contrast is physiologically large.

This is a **5× mismatch in the physical timescale represented by the same nominal `scale`**, and it is
directional in exactly the way needed to explain the collapse: ds006695's higher sampling rate makes the
fixed-in-samples scale ladder examine a frequency band where sleep depth barely modulates signal structure,
while sleep_edfx's ladder (at the same nominal scales) reaches into the band where it modulates it enormously.

This project has already written down the general form of this bug, in the same file, for a different
parameter (`critical_slowing`'s autocorrelation lag) — and has a **regression test that measured the size
of the effect for the closest analogous quantity in this project, at 100 Hz specifically**:

```python
# bsde/tests/test_exotic_features.py:246
def test_critical_slowing_is_invariant_to_sampling_rate():
    """THE REGRESSION THAT MATTERS, and the third instance of one bug class in this project.
    ...
    100 Hz IS IN THIS LIST DELIBERATELY. It is Sleep-EDF's rate, it is the lowest this project reads, and it
    is the case the first fix silently skipped. Measured pre-fix spread across 100-5000 Hz was 0.237
    (100 Hz -> 0.709, everything else -> 0.946 on identical dynamics); post-fix it is 0.018.
    """
```

That is the **same measure family** (an entropy/autocorrelation-style statistic with a samples-based
internal parameter) breaking in the same direction this probe suspects: the 100 Hz case behaved like an
outlier relative to 250/500/5000 Hz on **identical underlying dynamics** (`resample_poly` of one base
series), before the lag was redefined in seconds. `multiscale_entropy_slope`'s scale ladder was never given
that fix. Below is the general code comment for the same bug class:

```python
    # TWO SEPARATE RATE DEFECTS, TWO SEPARATE REMEDIES. This is the THIRD time this project has hit the
    # same bug class (Lempel-Ziv's window in seconds, multiscale entropy's series length, now this), and
    # the first attempt at fixing it conflated the two problems into one resample, which fixed only half.
    #
    # DEFECT 1 -- the lag was lag-1 in SAMPLES, so it measured a different physical interval at every rate:
    #   0.2 ms at ds005620's 5 kHz against 10 ms at Sleep-EDF's 100 Hz. ...
    #   REMEDY: the lag is CS_LAG_S SECONDS, converted to samples per recording. Not a resample -- a
    #   definition.
```

`multiscale_entropy_slope`'s **series length** got this remedy (`max_samples`, deliberately capped to
remove a duration confound). Its **scale ladder** did not: it remains samples-based, which is the standard
literature convention for a *single-deposit* MSE analysis and is exactly the defect this comment describes
for any *cross-rate* comparison. This looked like the leading candidate going into the direct test — **§4
tested it and it did not recover discrimination; see §4's result and §6's ranked verdict for what that
means.**

### (c) Tolerance `r`

`r = r_frac * sd`, computed **once** from the truncated original (scale-1) series' own standard deviation,
then held fixed across all scales (Costa et al. convention, and the project's own compute script says so
explicitly: `"multiscale_entropy_slope's tolerance is 0.2 x the signal's own std, so it is scale-relative
already"`, `ds006695_compute_features.py:34`). This is **scale-relative, not absolute** — it transfers
formally across sampling rates and amplitude scales in the sense that it re-derives itself per recording.
It is not, however, **bandwidth-invariant**: `sd` is computed over whatever frequency content survives into
the first 4000 samples, and a 500 Hz recording's std reflects a wider bandwidth (up to ~250 Hz, minus
whatever anti-alias filter the acquisition hardware applied — not recorded, §2) than a 100 Hz recording's
std (up to 50 Hz). Measured directly on two ds006695 epochs (first 4000 samples, native 500 Hz, three
channels): std = `[44.7, 28.2, 60.4]` µV (wake) and `[23.6, 21.5, 19.7]` µV (N3) — plausible EEG-scale
numbers, not evidence of runaway high-frequency contamination. **Ranked below (b)**: `r` is the right kind
of quantity (self-normalising) and there is no direct evidence here that it is driving the collapse, though
it cannot be fully separated from (b) without a bandwidth-matched comparison this probe did not run.

### (d) Channel count / montage

Sleep_edfx: 2 channels (`Fpz-Cz`, `Pz-Oz`, referential, midline-adjacent to occipital/central regions).
ds006695: 3 channels, all **bipolar frontal** derivations (`FP1-AFz`, `FP2-AFz`, `FF`). Neither exceeds
`EXPENSIVE_CHANNEL_CAP = 8`, so no channel truncation occurs in either deposit — every available channel is
used and averaged. Frontal SITES are not, on prior physiology, a poor place for slow-wave detection (frontal
slow waves are typically prominent in N3) — but a **bipolar derivation between two closely spaced frontal
electrodes** is a different claim from "a frontal site": it subtracts two nearby potentials and so acts as a
spatial high-pass filter on widespread, synchronous activity, which is a mechanism distinct from electrode
placement alone. Not tested directly here (§4 tests sampling rate only, holding montage fixed) — but §6
ranks this the best-supported remaining candidate once §4 refutes (b), precisely because it is the one
difference between the deposits left unaddressed by the direct test.

---

## 4. Direct test: does downsampling ds006695 to 100 Hz recover discrimination?

**Method.** `bsde/results/ds006695_epochs.npz` (regenerated this session, 1140 epochs, 3 channels × 15,000
samples × 500 Hz — asserted non-empty, `n=1140` printed and checked). For each of the 19 subjects, the
first 4 of the 12 available W epochs and the first 4 of the 12 available N3 epochs were selected
(deterministic slice, not cherry-picked) — **n = 76 W epochs, 76 N3 epochs**, both counts asserted non-zero
before proceeding.

For every epoch: (i) computed `multiscale_entropy_slope` at **native 500 Hz** exactly as the registered
candidate does (mean over the 3 channels, default scales/`m`/`r_frac`/`max_samples`); (ii) **decimated the
same raw epoch from 500 Hz to 100 Hz** (factor 5, `scipy.signal.decimate(..., zero_phase=True)` — an 8th-
order Chebyshev-I anti-alias low-pass applied before downsampling, zero-phase; no manual amplitude rescaling
performed anywhere) and recomputed the identical function with the same nominal scales, now representing
100 Hz. **RMS before/after downsampling** was computed as a check on amplitude, not assumed (results below,
raw output in `mse_probe_result.json`).

**Result** (n=76 W, 76 N3 epochs asserted non-empty and fully finite at every stage — printed live during the
run and in `mse_probe_result.json`; the run took 994.3 s):

| | native 500 Hz | downsampled to 100 Hz |
|---|---:|---:|
| n (W finite / total) | 76 / 76 | 76 / 76 |
| n (N3 finite / total) | 76 / 76 | 76 / 76 |
| mean, W | −0.04070 | +0.06651 |
| mean, N3 | +0.04508 | +0.12879 |
| sd, W | 0.09048 | 0.06586 |
| sd, N3 | 0.09729 | 0.07004 |
| Cohen's d (N3−W) | **+0.9131** | **+0.9162** |
| AUC (N3 vs W, N3=positive — matches the sign convention `PROBE_2026_08_02_SEPARABILITY.md` §15.2 uses) | **0.7632** | **0.7483** |
| mean RMS across epochs (raw file units, offset included) | 120.451 | 117.248 |
| RMS ratio (downsampled / native) | — | **0.9734** |

**RMS check.** Decimating 500→100 Hz removed only **2.7 % of RMS** (120.451 → 117.248, raw units, no
manual rescaling anywhere — `scipy.signal.decimate(..., zero_phase=True)` applies its own anti-alias filter
and returns physical-unit samples unchanged in scale). That is itself informative: if ds006695's signal
carried substantial power between 50 and 250 Hz, removing it would have dropped the RMS far more than 2.7 %.
Almost all of this signal's energy already lives below 50 Hz, which argues against culprit (c) (tolerance
`r` inflated by extra high-frequency bandwidth) being a major contributor — there was very little
high-frequency bandwidth to begin with.

**Interpretation — and this REFUTES the leading hypothesis, not confirms it.** The native-rate epoch-level
result (AUC 0.7632) reproduces `PROBE_2026_08_02_SEPARABILITY.md` §15.2's subject-averaged AUC (0.773)
closely, which validates this probe's method against the established number despite using a different, noisier
unit of analysis (76 raw epochs, not 19 subject-level means of 12 epochs each). **But downsampling to 100 Hz
— which fixes BOTH the scale-in-samples/time-window mismatch (culprit b) AND, as a side effect of
`max_samples=4000` no longer truncating a now-3000-sample epoch, increases the real time analysed from 8 s
to the full 30 s epoch — left the effect essentially unchanged: AUC moved from 0.7632 to 0.7483 (slightly
WORSE, not better) and |d| moved from 0.9131 to 0.9162 (unchanged within noise).** If the scale-in-samples
mismatch were the (sole) cause of ds006695's collapse relative to sleep_edfx's near-ceiling AUC 0.998, giving
the identical signal the identical nominal-scale-to-physical-Hz mapping sleep_edfx enjoys — with MORE data,
not less — should have moved discrimination substantially toward sleep_edfx's level. **It did not move at
all in the helpful direction.** Per this project's own rule 17 ("when a fix makes the effect stronger, the
diagnosis was wrong — a refutation, not a refinement"), read in reverse: **when the fix does not make the
effect stronger, the diagnosis is not confirmed, and here it is contradicted.**

---

## 5. Why `whole_head_exponent` did NOT collapse — the structural contrast

`whole_head_exponent` (via `fit_aperiodic` / `welch_psd`, `bsde/src/bsde/features/aperiodic.py`) fits a
log-log slope over frequencies selected as `(freqs >= fit_lo_hz) & (freqs <= fit_hi_hz)` with
**`fit_lo_hz=1.0`, `fit_hi_hz=40.0` — a physical-Hz band**, and `freqs = np.fft.rfftfreq(nper, 1.0/sfreq)` is
computed from the ACTUAL sampling rate. The same 1–40 Hz band is therefore fit regardless of whether the
recording is 100 Hz or 500 Hz — the parameterisation is **frequency-referenced**, not sample-referenced.
`multiscale_entropy_slope`'s scale ladder is the opposite: **sample-referenced**, so the physical band it
sweeps moves with the sampling rate. This is the same distinction the `critical_slowing` code comment in
§3(b) draws between a lag defined in seconds (survives across rates) and one defined in samples (does not).
It is offered here as the structural reason one candidate transported and the other did not, not as a new
measurement.

---

## 6. Ranked verdict

**The direct test in §4 changes this ranking from what §0–§3 predicted.** Reasoning from the code and from
this project's own prior bug history (§3b, §5) made (b) — the scale-in-samples/sampling-rate mismatch — look
like the obvious sufficient cause. **§4 tested it directly and it is not sufficient, and the direction of
the miss (AUC got very slightly worse, not better) is itself informative, not just "no change".**

1. **(b) Sampling rate / samples-vs-seconds scale definition — a REAL definitional bug, DEMONSTRATED
   INSUFFICIENT to explain the collapse.** The scale ladder genuinely is samples-based and genuinely does
   sweep a 5× different physical-time/frequency range at the two deposits' native rates (§3b is still
   correct as a description of the code). But giving ds006695's actual signal the identical nominal-scale-
   to-Hz mapping sleep_edfx enjoys — via downsampling, which ALSO incidentally gave the feature 30 s of
   signal instead of 8 s (§4, the `max_samples` truncation side effect) — left AUC at 0.748 against a
   native 0.763, i.e. **no recovery, arguably a fractional step backward.** Whatever explains ds006695's
   large gap to sleep_edfx's near-ceiling 0.998, it survives correcting the scale-to-Hz mismatch and
   correcting the truncated-duration handicap simultaneously. **This rules (b) out as the (sole or primary)
   explanation for the cross-deposit gap** — it remains worth fixing on its own terms (the same code comment
   and regression test in §3b/§5 apply regardless of what this probe found), but it is not what is making
   `multiscale_entropy_slope` fail specifically on ds006695.
2. **(d) Channel count / montage — UNTESTED BY THIS PROBE, but now the best-supported remaining candidate
   by elimination.** ds006695's 3 channels are all short-distance BIPOLAR frontal derivations
   (`FP1-AFz`, `FP2-AFz`, `FF`); sleep_edfx's 2 channels are REFERENTIAL, one central (`Fpz-Cz`) and one
   occipital (`Pz-Oz`), each referenced against a distant, near-neutral site. A bipolar derivation between
   two closely spaced frontal electrodes subtracts two nearby potentials and so acts as a spatial
   high-pass filter — it preferentially cancels widespread, spatially SYNCHRONOUS activity (exactly what
   large-amplitude N3 slow waves are, physiologically) while a referential montage spanning a much larger
   distance does not cancel it the same way. This would attenuate the very signal multiscale entropy needs
   to detect a state-dependent complexity CHANGE, while leaving a spectral-SLOPE measure like
   `whole_head_exponent` comparatively unaffected — a slope is a property of the spectrum's log-log SHAPE
   and can survive a uniform attenuation of the signal that would blunt an entropy measure's absolute
   sensitivity to synchronous slow-wave structure. This is offered as the mechanistically consistent
   explanation for why `whole_head_exponent` (AUC 1.000, referential-insensitive by construction) and
   `multiscale_entropy_slope` (AUC ~0.75–0.77, well short of sleep_edfx's 0.998) diverge on the SAME
   montage-limited deposit — **but it was not tested directly here** (a direct test would restrict
   sleep_edfx to one channel, or better, compare a bipolar re-derivation of sleep_edfx's own channels
   against its referential form) and is reported as a hypothesis ranked highest by elimination, not as a
   confirmed finding.
3. **(a) Scale coverage — ruled out**, unchanged from §3a: both deposits hit the identical 4000-sample
   `max_samples` budget, so effective coarse-grained length per scale is identical between deposits. Not
   the mechanism.
4. **(c) Tolerance `r` — weakened by the RMS check in §4, not eliminated.** Decimating 500→100 Hz removed
   only 2.7 % of RMS, meaning ds006695's signal was already almost entirely below 50 Hz before downsampling
   — there was very little high-frequency bandwidth for `r`'s std estimate to be inflated by in the first
   place. This makes (c) a weak candidate on its own, independent of (b)'s refutation.

**Honest summary.** The mechanism this probe was built to test — a samples-vs-seconds definitional bug,
which is real and worth fixing regardless — is **demonstrated NOT to be the explanation for ds006695's
collapse**, because correcting it (plus incidentally providing more data) did not recover discrimination.
The most defensible remaining account is channel montage (bipolar frontal vs referential
central/occipital), argued from first principles above and consistent with which candidate (spectral slope)
survived and which (entropy) did not, but **this specific probe did not test montage directly and that
claim should be labelled a hypothesis, not a finding**, until a montage-matched comparison is run.
