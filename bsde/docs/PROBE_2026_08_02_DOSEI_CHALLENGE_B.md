# PROBE 2026-08-02 — DOSE-I as a Challenge B escape from rule 86 (recon only, no design registered)

*Reconnaissance only. No experiment, registration or ledger row was written. All numbers below were computed
directly from the cached CSVs in `bsde/results/` on 2026-08-02 with pandas 3.0.5, or read verbatim from
`bsde/src/bsde/pkpd/propofol.py`, `bsde/docs/MASTER_PLAN.md`, `bsde/docs/QUEUE.md`, `bsde/scripts/extract_dosei_features.py`
and `bsde/src/bsde/experiments/e122_pharmacology_residual.py`. Nothing was downloaded; nothing in
`bsde/src/bsde/experiments/` or `bsde/governance/` was touched.*

**Bottom line up front:** the cache supports a within-recording, exposure-adjusted test relating spontaneous
EEG to MOAA/S beyond a propofol-exposure incumbent, **and this exact test has already been run** — E122
(`bsde/src/bsde/experiments/e122_pharmacology_residual.py`, ledger row `E122`, outcome `positive`, filed under
**Challenge C**, not B). Registering a "Challenge B" successor here needs to be explicit about (a) what is
actually new relative to E122, and (b) that MOAA/S is a graded **responsiveness/sedation-depth** scale, not
the CRS-R-style command-following label Challenge B was defined around (`docs/QUEUE.md` Q7, Q12, Q14). The
binding constraint is not data coverage — coverage is excellent — it is construct match to "command-following."

---

## 1. Columns, and where MOAA/S lives

**`bsde/results/dosei_features.csv`** — 10,898 rows × 35 columns, 39 recordings, 5 s stride:
```
recording, t_s, soc, moaas, propofol, their_sef95, their_pe31, n_finite,
critical_slowing_ar1, emg_beta_gamma_fraction, emg_index, emg_kurtosis,
exponent_gamma, exponent_high, exponent_low, lempel_ziv, multiscale_entropy_slope,
pac_slow_alpha, relative_alpha_power, relative_delta_power, spectral_edge_95,
spectral_entropy, whole_head_exponent, bis_rbr, bis_bsr, bis_quazi, bis_sfs,
coherence_delta, coherence_theta, coherence_alpha, coherence_beta,
wpli_delta, wpli_theta, wpli_alpha_2ch, wpli_beta
```
**`moaas` is the MOAA/S score, per 5 s window, already present as a plain column** — no join needed. `soc`
is the binary state-of-consciousness flag (E122's docstring and QUEUE.md report it agrees with `MOAAS > 1`
on 95.6 % of samples on average, 98.0 % at the median — i.e. it is the same construct scored a second way,
not an independent one, per rule 19).

**`bsde/results/dosei_covariates.csv`** — 171 rows × 23 columns, one row per recording (no MOAA/S here; it is
a per-recording table of static/PD covariates and dose summaries):
```
recording, age, sex, height_cm, weight_kg, bmi, asa,
chronic_bblocker, chronic_opioids, chronic_neuroleptics, chronic_benzodiazepines, chronic_antiepileptics,
cond_ohs, cond_sas, cond_ohe, cond_chf,
care_type, endoscopy_type, prop_sum_mg, dose_reconstructed_mg, dose_complete, record_len_s, para
```
`bsde/results/dosei_holdout_features.csv` (18,918 rows × 37 columns, 62 recordings, adds `endoscopy` and
`ecg_hr`) is a **disjoint** recording set from `dosei_features.csv` — verified, 0 recordings overlap between
the two feature files.

---

## 2. MOAA/S distribution — the binding number

```
dosei_features.csv       (39 recordings, 10,898 windows)
  moaas=1: 5,229   moaas=2: 1,501   moaas=3: 1,550   moaas=4: 1,357   moaas=5: 1,261

dosei_holdout_features.csv (62 recordings, 18,918 windows)
  moaas=1: 13,207  moaas=2: 745    moaas=3: 1,862   moaas=4: 1,400   moaas=5: 1,704
```
**No `moaas = 0` appears anywhere in either file.** Per `docs/QUEUE.md`'s own earlier scan this is a deposit
property, not a filtering artefact: the deepest level ever charted is 1 ("responds only after painful
stimulus"), consistent with procedural sedation rather than general anaesthesia to the point of no response.

**Per-recording endpoint coverage (THE BINDING NUMBER):**
```
                          n recordings   has moaas=5   has moaas=1   has BOTH
dosei_features.csv             39            39            39           39   (100 %)
dosei_holdout_features.csv     62            62            62           62   (100 %)
combined                       101           101           101          101  (100 %)
```
**Every single one of the 101 recordings that carry extracted EEG features spans the full range from fully
alert (5) down to the deepest charted level (1).** This is exactly what a within-recording contrast needs,
and it is not a marginal result — it is 101 of 101, not 90-something of 101.

The per-recording MOAA/S trajectory changes in steps, not continuously: median 12 value-changes per
recording (range 5–36), and the median gap between successive changes is 60 s (IQR 30–105 s, full range
5–1,790 s) — consistent with a clinician re-scoring roughly every 1–2 minutes and the value being held
constant between assessments, not with a synthetic or fully continuous instrument.

---

## 3. Timing of MOAA/S relative to EEG windows

**There is no separate assessment-timestamp file — MOAA/S is not sparse in the cache.** Both `moaas` and
the EEG feature columns are drawn from the same deposit-provided per-recording file inside
`dosei_pEEG.zip` (`pEEG/pEEG/<rec>_pEEG.csv`), which ships MOAA/S **already at 1 Hz resolution** alongside
the raw-derived spectral columns (`SEF95`, `PE31`, etc.) and `Propofol`. Verified directly by unzipping and
reading `10-013_pEEG.csv`: its own `Time` column is 1 Hz and `MOAAS`/`SOC` are populated on every row from
the first sample. `extract_dosei_features.py`'s docstring states the feature window is **"the same causal
windows as `extract_dosei_sfs.py`: `WINDOW_S` seconds ENDING at each depositor timestamp"** — so by
construction every extracted EEG window uses only samples at or before its own `t_s`, and `moaas` at that
same `t_s` comes from the identical source row. **The gap between an "assessment" and its paired EEG window
is therefore 0 by construction, in the cache's own units** — both files are sampled at 5 s stride
(`dosei_features.csv`, `dosei_holdout_features.csv`, `dosei_window_control.csv` all step in exactly 5 s
increments, verified) drawn from the deposit's 1 Hz track.

**What this does NOT tell you, and the cache cannot answer:** whether the depositor's own 1 Hz `MOAAS`
column is a true 1 Hz assessment (implausible — MOAA/S requires a clinician to stimulate the patient) or a
forward-fill of sparse bedside scorings onto a continuous grid (far more likely, and consistent with the
observed step function: median hold time 60 s between changes). If it is forward-filled (last observation
carried forward), pairing EEG-window-ending-at-`t_s` with `moaas`-at-`t_s` is causal and safe. If any part of
it were back-filled from a *later* assessment, that would be look-ahead. **This cannot be determined from
the CSVs alone — it requires the DOSE-I methods paper/documentation, which is not in this repo.** Flag this
explicitly in any registration rather than assuming LOCF.

`dosei_clock_offsets.csv` (97 recordings, `offset_s` 0–2,323 s, 77 distinct values, matched rows 89–721 per
recording) is **not** about assessment timing — it recovers the offset between the *dose event* log's
absolute clock (`dosei_dose_events.csv`'s `t_abs_s`) and the pEEG file's own `t_s` axis, fitted by matching
reconstructed cumulative dose against the file's `Propofol` column, `PE31`, `SEF95`, `MOAAS` and `SOC`
jointly (per E122's docstring: recovers 221/221 dose events versus 14/221 assuming zero offset). It is the
join key needed for item 4 below, not a timestamp for MOAA/S itself.

---

## 4. The propofol exposure record

**`dosei_dose_events.csv`** — 2,095 rows × 3 columns (`recording, t_abs_s, dose_mg`), 171 of 171 recordings
represented. **Bolus only, no infusion segments** — every `dose_mg` value is a multiple of 10 mg (distinct
values: {10, 20, 30, 40, 50}), matching `propofol.py`'s docstring verbatim: *"DOSE-I... its dose column is
administration in multiples of 10 mg, and the reconstructed total matches the deposit's own `PROP_sum`
exactly in 168 of 171 recordings, so no infusion is hiding in it."* Verified independently here: **168 of
171** recordings have `prop_sum_mg == dose_reconstructed_mg` exactly; the 3 mismatches (`10-003`, `10-014`,
`10-017`) are exactly the 3 recordings flagged `dose_complete = 0` in `dosei_covariates.csv`.

- **Events per recording:** median **12**, mean 12.25, range **1–28** (n = 171).
- **Cumulative dose per recording:** median **230 mg**, range **40–540 mg** (n = 171).
- **A cumulative-dose-to-date covariate is directly buildable per EEG window**, and more: `propofol.py`
  implements a full exponential-basis PK ladder (L0 cumulative mg → L1 single exponential → L2 an 8-rate
  basis spanning half-lives 0.5–64 min, verified against an independent ODE solver at R² = 1.000000/0.999894
  → L3 allometric scaling → L4 plus PD covariates), already used and validated in E122. Nothing here needs
  to be rebuilt.
- **Exclusions already established and reusable:** `para == 1` (2 of 171 recordings — propofol
  extravasation, dose overstates delivered drug) and `dose_complete == 0` (3 of 171 — 30–40 mg given outside
  the pEEG recording window). Reproduced here: of the 97 feature-bearing recordings that also have a
  recovered clock offset, exactly **3** are excluded by `dose_complete == 0` and **0** by `para` (the 2
  `para == 1` recordings do not overlap the feature-bearing set), leaving a cohort of **94 recordings** —
  matching E122's reported cohort of 94 recordings exactly.

---

## 5. Look-ahead-free pairing

Because the EEG feature window is defined to **end at** its own `t_s` (never straddle or look past it), and
`moaas` at that same `t_s` comes from the same source row, **every one of the 29,816 combined feature rows
(10,898 + 18,918) is already a same-timestamp, backward-looking-EEG pairing by construction** — there is no
"future EEG" being used to predict a past assessment. The open question is not whether the EEG looks ahead
of `t_s` (it does not, verified from the extractor's own window definition) but whether the **label itself**
(`moaas` at `t_s`) reflects information from strictly at-or-before `t_s`, which per item 3 cannot be settled
from the cache and must be declared as an assumption (most likely LOCF, unverified) in any registration.

If a stricter rule is wanted — pairing only at moments where `moaas` demonstrably reflects a **recent**
assessment (i.e., near a value-change, not deep into a long constant stretch) — 498 value-change events
across the two feature files supply exactly the windows nearest an actual re-scoring; the rest are
long-duration carries of an old value, which is conservative (biases toward stale rather than look-ahead
information) rather than dangerous.

---

## 6. Channels, sampling rate, durations, column health

- **Channels:** 2, fronto-temporal (`Intellivue/EEG_1`, `Intellivue/EEG_2`) — confirmed in
  `extract_dosei_features.py`'s `raw_two()` and module docstring ("DOSE-I is two-channel fronto-temporal").
- **Sampling rate:** 125 Hz (`SFREQ = 125.0` in `extract_dosei_sfs.py`, imported by the features extractor).
- **Recording durations (`record_len_s`, n = 171):** median **1,562 s (26.0 min)**, mean 1,653 s, range
  **399–4,250 s** (6.7–70.8 min).
- **Column health, checked per rule 74 (all-NaN or constant → must be excluded with a reason):**
  - `dosei_features.csv` and `dosei_holdout_features.csv`: **no all-NaN, no constant column** among any of
    the 35/37 numeric columns — every one has ≥ 2 distinct finite values.
  - `dosei_covariates.csv`: **two constant columns**, both must be dropped and stated, not fitted:
    `chronic_benzodiazepines` (constant 0, 171/171 finite — already noted and dropped in E122) and
    **`cond_ohs`** (obesity-hypoventilation syndrome flag, constant 0, 171/171 finite — **not** mentioned in
    E122's docstring; a genuinely new finding from this probe, cheap to have missed since E122 only dropped
    the one it happened to check).
  - **Near-constant but not literally constant (report, do not treat as informative without care):**
    `bis_bsr` is 0 in 99.2 % of `dosei_features` windows (10,810/10,898) and 99.4 % of holdout windows; the
    non-zero values are all small (max well under 0.05 in the sampled head). `bis_quazi` is 0 in ~96 % of
    windows in both files. This reproduces MASTER_PLAN §9.36's E77 finding that these BIS subparameters are
    sparse, low-amplitude, and fire mostly at zero — a known property, not a data-quality defect specific to
    this probe.
  - `n_finite` (fraction of finite samples contributing to a window) is exactly 1.0 in ~95–96 % of windows
    in both files and dips as low as ~0.96 for the rest — no window is entirely missing.

---

## 7. What would BLOCK a Challenge B design here — stated plainly

1. **MOAA/S is not a command-following label in the sense Challenge B was defined around.** `docs/QUEUE.md`
   Q7/Q12/Q14 define Challenge B against CRS-R-style command following (Chennu 2014's `Command Following
   (CRS-R)` / `Command Following (fMRI)` columns) or the Stieger BCI motor-imagery deposit. MOAA/S is a
   graded **arousal/responsiveness-to-stimulus** scale (name called → louder call → mild prod/shake → pain),
   scored by a clinician who **must actively stimulate the patient to score it** (E122's own docstring: "a
   scale scored by a clinician who must stimulate the patient to score it — which perturbs the arousal being
   measured in the direction that flatters any EEG measure"). That is a related but **not identical**
   construct to CRS-R command following, and a registration must say explicitly which claim it is making —
   "responsiveness/depth" (which this deposit answers well, per E122) or "command-following" (which it does
   not test in the strict sense used elsewhere in this project).
2. **The pharmacology-adjusted design proposed here has already been run, under Challenge C, and is
   positive.** E122 (`bsde/src/bsde/experiments/e122_pharmacology_residual.py`, `outcome: positive`) tests
   exactly "does EEG add to a complete propofol PK/PD exposure model in predicting MOAA/S," on 94
   recordings / 25,102 windows, with the deposit's own PE31/SEF95 adding at all five rungs of the exposure
   ladder, gated against a circular-shift placebo distribution and a Gaussian negative control. A
   Challenge-B-framed successor needs to state precisely what is new relative to E122 — e.g., a binary
   responsive/unresponsive contrast rather than continuous MOAA/S regression, a different candidate family,
   or a stricter within-recording matched design — or it is a re-labelling of an existing result, which rule
   59 warns against doing silently.
3. **Same-observer/same-moment concern (rule 86), assessed rather than assumed:** unlike RASS/GCS-motor
   (two clinician *observations* of the same construct family, hence shared method variance), here one side
   of the contrast (`dose_mg` at `t_abs_s`) is an **administered intervention record** (a syringe/pump
   event), not an observation of patient state, while MOAA/S is a behavioural rating. Even in the worst case
   that the same clinician both pushed the bolus and scored the response — plausible in single-provider
   procedural sedation, and **not verifiable from this cache** — the two measurements are different in kind
   (an act versus a judgment), which is a real, structural improvement over the RASS/GCS-motor failure mode.
   **This repo has no information on staffing/workflow at the DOSE-I site, so "were dosing and scoring done
   by the same person at the same moment" cannot be answered from the data — say so rather than assume
   either way.**
4. **The label-forward-fill direction (item 3/5) is unverified.** If DOSE-I's own MOAA/S track were ever
   back-filled from a later assessment, any "predicts an imminent change" framing would be look-ahead-tainted
   even though the EEG window itself is causal. A responsiveness-*level* regression (as E122 registered) is
   much less exposed to this than a *transition-prediction* framing (as E33/E34/E37/E40 all discovered the
   hard way on this same deposit, all failing at "no information earlier than the incumbent").
5. **No EMG/muscle channel exists** (QUEUE.md Q1: "No dedicated EMG... the check that killed E22 cannot be
   run here in its strong form"). `emg_index`/`emg_kurtosis`/`emg_beta_gamma_fraction` are proxy bands, not a
   channel, so muscle-artefact attribution for any candidate will be weaker evidence than on deposits that
   ship a real EMG lead (as several of the error-catalogue rules for this project require checking).
6. **Scope is narrow and already stated project-wide:** one site, one drug (propofol mono-sedation, no
   co-titrated opioid or benzodiazepine — `chronic_benzodiazepines` is literally constant 0), procedural
   endoscopy sedation, 2-channel fronto-temporal montage. Any positive result here is a claim about this
   population and modality, not a general command-following claim, exactly as E122 already scoped its own
   result.

**Feasibility verdict:** a within-recording, exposure-adjusted regression of MOAA/S on EEG, controlling for
a full propofol PK/PD ladder, is straightforwardly feasible on this cache — the coverage numbers (101/101
recordings spanning the full MOAA/S range, 94/97 surviving pre-specified exclusions, a validated 1 Hz dose
record) are as clean as this project's data gets. **The binding constraint is not data availability; it is
construct match.** MOAA/S buys escape from rule 86's *shared-observer* problem (the incumbent is a drug
record, not a second clinician rating) but it does **not**, by itself, buy the "command-following" construct
Challenge B was named for — that would need to be argued explicitly, or the design re-scoped and stated as a
responsiveness/depth question (which is what E122 already answered, positively, under Challenge C).
