# DESIGN 2026-08-02 — Challenge C on ds006695 (forehead-patch sleep staging)

**STATUS: DESIGN ONLY. Not registered.** No entry has been written to
`bsde/governance/REGISTRATION_LEDGER.jsonl`, no experiment file exists under
`bsde/src/bsde/experiments/`, and no statistic involving the `stage` column of
`bsde/results/ds006695_features.csv` or `bsde/results/ds006695_epoch_index.csv` has been computed anywhere
in the preparation of this document. See §0 for exactly what was and was not inspected.

**Why this document exists at all.** `ds006695` is the only deposit in this project whose candidate columns
have never been correlated with its own label — every other Challenge C deposit (`ds005620`, `capslpdb`,
`sleep_edfx`) has already been swept, in some cases more than once (E222, E223). That makes it the one clean
confirmatory test this programme has left, and a single exploratory correlation burns it permanently. The
design below is meant to be complete enough to become a registration verbatim, with nothing about the gates,
the primary statistic, or the verdict rule left to be decided after looking at the data.

---

## 0. Transparency: exactly what was inspected to write this document, and what was not

**Inspected:**
- Column names of `bsde/results/ds006695_features.csv` (28 columns: 4 index columns + 24 candidates).
- Per-candidate **missingness**, i.e. `count(value == "") / n_rows`, over the **539** rows written so far
  (the file is still being extracted; see §5). No stage information entered this computation — it is a
  count over the whole file.
- Row counts **per subject** and **per (subject, stage) cell** in both the epoch-index file and the
  features file. This is a *completeness* check — does the file contain the number of rows its own design
  promises? — not a comparison of any candidate's values across stages. `stage` is used here only as a
  grouping key for counting rows, never paired with a candidate value.
- The candidate registry (`bsde/src/bsde/candidates/seed.py`, `registry.py`): declared `min_channels` and
  `required_regions` for all 24 candidates, and the source of `f_lrtc_alpha`, `lrtc_envelope`,
  `f_pac_slow_alpha`, `f_icoh_alpha`, `f_wpli_alpha` to determine which candidates are mechanically
  computable on this deposit's montage and epoch length.
- `bsde/scripts/ds006695_compute_features.py`'s own docstring and validation code, which documents the
  montage (`FP1-AFz`, `FP2-AFz`, `FF`, 500 Hz, all three channels frontal bipolar derivations), the units
  investigation, and which candidates are structurally unable to run on this montage.
- Prior Challenge C experiments on other deposits (E222, E223) and `bsde/docs/NOTE_HEADROOM_NORMALISATION.md`,
  for methodology and incumbent precedent — none of which touches this deposit's data.
- `bsde/docs/PROBE_2026_08_02_DEPOSITS.md` for what this deposit *is* (OpenNeuro, forehead-patch, 19
  subjects, 5-level AASM hypnogram from `EEG.VisualHypnogram`) and the project's own prior warning that its
  three forehead channels make `whole_head_exponent` **"a different measurement, not the same one
  elsewhere."**

**Not inspected, anywhere, by anyone, in preparing this document:**
- Any mean, median, correlation, rank statistic, or model fit relating any candidate column's *values* to
  the `stage` column.
- The `EEG.VisualHypnogram` source data or any other raw label file.
- Any per-stage summary of any candidate (e.g. "what does `whole_head_exponent` look like in N3").

If this design is approved, the experiment script must be written and run without any exploratory step
between now and the registered analysis — the point of this document is that there is nothing left to look
at first.

---

## 1. Question

**Does the Challenge C candidate panel (`whole_head_exponent`, `multiscale_entropy_slope`,
`relative_alpha_power`, `pac_slow_alpha`) add sleep-depth discrimination beyond a named incumbent
(`spectral_edge_95`), before and after adjusting for a muscle-tone proxy (`emg_index`), on `ds006695`'s
19-subject forehead-patch cohort — and does that addition survive a label-permutation placebo built to be
able to destroy it?**

This is the third leg of the same replication chain E222 ran on `sleep_edfx` and E223 probed on the same
deposit's unexposed columns: identical incumbent, identical artefact adjuster, identical candidate panel,
so that a result here is directly comparable to the existing table in `NOTE_HEADROOM_NORMALISATION.md`
rather than a new, incommensurable number.

---

## 2. Cohort and what this deposit actually is

| property | value | source |
|---|---|---|
| subjects | 19 (`sub-101, 102, 104…126`, non-contiguous numbering) | epoch-index file, row-count check |
| design | 5 stages (W, N1, N2, N3, REM) × exactly 12 epochs/subject/stage = 60 rows/subject, 1140 rows total | epoch-index file, verified: every subject has exactly 60 rows |
| montage | 3 channels, **all frontal**: `FP1-AFz`, `FP2-AFz`, `FF` — a forehead sensor patch, not a clinical 10-20 PSG montage | `ds006695_compute_features.py` docstring, cross-checked against all 19 subjects' metadata |
| sampling rate | 500 Hz, uniform across all subjects | same |
| epoch length | 15,000 samples = **30 s** per epoch (standard AASM epoch length) | `data.shape == (3, 15000)` at 500 Hz |
| label | 5-level AASM hypnogram, `EEG.VisualHypnogram`, embedded in the source EEGLAB `.set` struct — **almost certainly scored from a richer clinical montage than these 3 exported channels**, i.e. an independent instrument from the candidate panel (this is favourable: see §8) | `PROBE_2026_08_02_DEPOSITS.md`; not independently verified here |
| licence | CC0 | same probe doc |

**Why frontal-only is not fatal for this design, but is not free either.** AASM N3 scoring is itself defined
on frontal slow-wave activity, so a frontal-only montage is a reasonable vantage for the incumbent
(`spectral_edge_95`) and for `relative_alpha_power`/`relative_delta_power`-type measures. It is a *worse*
vantage for alpha specifically, which is canonically parieto-occipital and eyes-closed — `relative_alpha_power`
on this deposit measures a weaker, more anterior version of the phenomenon than on a full-montage deposit.
State this as an interpretive caveat on that one candidate, not a disqualification.

---

## 3. Candidate availability — what runs here and what does not, and why

The full registry has 24 candidates. Five are **structurally infeasible** on this deposit and must not be
computed, let alone tested, regardless of what the features file happens to contain for them:

| candidate | declared requirement | this deposit | verdict |
|---|---|---|---|
| `icoh_alpha` | `min_channels = 8` | 3 channels | **EXCLUDED — connectivity measure, insufficient channels.** With only 3 electrodes the function still *runs* (it does not enforce its own precondition — confirmed in the extraction script's own validation section) but returns a mean over at most 3 channel pairs, which is not what the candidate was declared to measure. |
| `wpli_alpha` | `min_channels = 8` | 3 channels | **EXCLUDED — same reason.** |
| `spatial_participation_ratio` | `min_channels = 4` | 3 channels | **EXCLUDED — topography-adjacent measure.** Participation ratio over a 3×3 channel covariance matrix is bounded above by 3 and has essentially no dynamic range; it is a degenerate quantity here, not merely an under-powered one. |
| `uce_v1` | `min_channels = 4`, requires named `frontal` **and** `posterior` regions | 3 channels, all named-frontal bipolar derivations — **no posterior channel exists on this montage at all** | **EXCLUDED — confirmed all-NaN in the 539 rows already written, and mechanically guaranteed to be all-NaN in the remaining 601: this montage cannot supply a posterior region under any circumstances.** This is worth stating loudly given UCE is BSDE's flagship candidate: this deposit cannot test it, full stop, not "results pending." |
| `lrtc_alpha` | needs ≥ `4 × max_scale_s × sfreq` samples; falls back to a shrunk scale only if the shrunk range is within a factor of `MAX_SCALE_SHRINK = 2` of the requested 20 s, i.e. needs ≥ 10 s at reduced resolution | 30 s epochs at 500 Hz = 15,000 samples; `shrunk = max(4.0, 15000/2000) = 7.5 s`, which is **below** the 10 s floor (`20/MAX_SCALE_SHRINK`) | **EXCLUDED — confirmed all-NaN in the 539 rows already written, and mechanically guaranteed to be all-NaN for every remaining epoch: the guard in `lrtc_envelope` refuses on every 30 s epoch this deposit can ever produce, by construction.** This is not a missingness problem to work around; the candidate cannot be computed on this deposit's epoch length at all. |

Both `uce_v1` and `lrtc_alpha`'s all-NaN status was verified from the code path that produces them, not
merely observed as 100 % missing in a partial file — the partial-file observation and the code-path
derivation agree, which is the confirmation rule 5 asks for (empty is not evidence of absence until the
filter is shown incapable of matching anything — here, shown incapable *by the arithmetic*, not merely by
one sample).

**Nineteen candidates remain mechanically computable** (`min_channels = 1`, no region requirement):
`alpha_peak_hz`, `alpha_peak_hz_wide`, `critical_slowing_ar1`, `emg_beta_gamma_fraction`, `emg_index`,
`emg_kurtosis`, `exponent_gamma`, `exponent_high`, `exponent_low`, `lempel_ziv`, `multiscale_entropy_slope`,
`pac_slow_alpha`, `relative_alpha_power`, `relative_alpha_power_iaf`, `relative_delta_power`,
`relative_theta_power`, `spectral_edge_95`, `spectral_entropy`, `whole_head_exponent`.

**This design tests only four of those nineteen**, for a reason that is a scope choice and not a further
feasibility limitation: the four are exactly E222's standing positive result
(`whole_head_exponent` +0.0542 [+0.030, +0.082], `multiscale_entropy_slope` +0.0280 [+0.011, +0.049],
both muscle-adjusted on `sleep_edfx`) plus the two other columns E222 carried alongside them
(`relative_alpha_power`, `pac_slow_alpha`), so that a result here slots directly into the existing
cross-deposit table rather than creating a new, first-time claim on fifteen untested columns at once. Using
the remaining fifteen to assemble a *different* hypothesis after seeing this deposit's numbers would be
exactly the by-product-hypothesis mistake E223 was built to correct (rule 47) — if any of them are wanted as
candidates later, that is a new, separately pre-registered design.

**Panel for this design:**

| role | column |
|---|---|
| incumbent | `spectral_edge_95` |
| artefact / muscle proxy | `emg_index` |
| candidates | `whole_head_exponent`, `multiscale_entropy_slope`, `relative_alpha_power`, `pac_slow_alpha` |
| negative control | one `rng.normal()` column, generated at run time, never read from the file |

Current missingness on exactly these six roles, over the 539 rows written so far: **0.000 for all six**
(`spectral_edge_95`, `emg_index`, `whole_head_exponent`, `multiscale_entropy_slope`, `relative_alpha_power`,
`pac_slow_alpha`). The two columns with nonzero missingness in the file (`alpha_peak_hz_wide` and
`relative_alpha_power_iaf`, both 11.7 %) are not in this panel.

---

## 4. Incumbent: named, and the gate that checks it is alive on THIS cohort

**Incumbent: `spectral_edge_95`.** Chosen for direct comparability with E222 and E223, which used it as the
incumbent for the same 4-level ordered sleep ladder on `sleep_edfx`, not because its strength here is
assumed — that is exactly what G2 (below) checks, freshly, on this deposit, before any candidate's increment
is read (rule 45 names it, rule 53 requires it be checked alive here rather than inherited).

**Muscle / EMG confound: `emg_index`.** Per E222's established method, every increment in this design is
computed **twice** — once over baseline `[spectral_edge_95]`, once over baseline
`[spectral_edge_95, emg_index]` — and the muscle-adjusted number is the one the verdict is built on (rule
54: the confound-handling line of code, not a caveat). **`emg_index` is known to be a weak proxy**: E69
showed it fails to detect REM atonia, and E71 found it correlates with a true submental EMG channel at only
ρ = 0.20 pooled / 0.30 within-subject on a deposit that has one. `ds006695` has no true EMG channel at all —
these are 3 EEG-derivation channels, not a PSG montage with chin EMG — so `emg_index` here is doing
double duty as a crude proxy for a signal this deposit cannot measure directly. **What this can and cannot
support:** surviving muscle-adjustment with `emg_index` supports "not driven by the muscle contamination
this weak proxy can see"; it cannot support "cortical" or "not muscle-driven" in any stronger sense, and the
write-up must say so every time, not once in a footnote.

---

## 5. Feasibility numbers computable without touching the label

| quantity | value |
|---|---|
| n subjects (full design) | 19 |
| n subjects with COMPLETE feature rows as of this writing | 9 (`sub-101,102,104,105,106,107,109,110,111`), + 1 partial (`sub-112`, 39/60 rows, its N2 cell at 3/12) |
| n rows written / planned | 539 / 1140 |
| epochs per (subject, stage) cell, by design | exactly 12, verified in the epoch-index file for all 19 subjects and in every completed cell of the features file so far |
| candidates structurally infeasible | 5 of 24 (`icoh_alpha`, `wpli_alpha`, `spatial_participation_ratio`, `uce_v1`, `lrtc_alpha`) |
| candidates in this design's tested panel | 4 (`whole_head_exponent`, `multiscale_entropy_slope`, `relative_alpha_power`, `pac_slow_alpha`) |
| missingness on the 6 panel-relevant columns, current 539 rows | 0.000 for all six |
| missingness on columns NOT in the panel (context only) | `alpha_peak_hz_wide` 11.7 %, `relative_alpha_power_iaf` 11.7 %, `uce_v1` 100 %, `lrtc_alpha` 100 % |

**Precondition to running this design: the features file must reach all 1140 rows, with every
(subject, stage) cell at exactly 12, before the registered analysis executes.** If it is run before that —
which this document explicitly advises against — the correct action is to restrict to subjects whose 60
rows are all present, report the excluded subjects and the reason (rule 14), and treat the result as
provisional pending the full cohort, never as final.

---

## 6. Primary statistic

Out-of-fold **Spearman rank correlation** between a ridge-regression prediction and the 4-level ordered
ladder (`W=0, N1=1, N2=2, N3=3`; **REM excluded from the primary ladder and reserved for the placebo/rung
diagnostic in §7**, exactly as E222 treats it), using `bsde.verifier.stats.grouped_cv_predict` so that
**subjects are held out whole** (rule 69 — the epoch is not the independent unit, the subject is; n = 19,
not n = 912 ladder-only epoch-rows).

```
increment(base, add) = spearman(cv_predict(X[:, base + add]), y) - spearman(cv_predict(X[:, base]), y)
```

computed for `base = [spectral_edge_95]` ("plain") and `base = [spectral_edge_95, emg_index]`
("muscle-adjusted"), for each of the four candidates plus the noise control, exactly as `increment()` in
E222 already implements it (importable, not reimplemented).

**Cross-validation folds: `folds = n_subjects` (leave-one-subject-out), not the default `folds=5`.** This is
a registered deviation from E222/E223, which used the default 5-fold grouping appropriate to their 100+ and
142-subject cohorts. With only 19 subjects, `folds=5` would hold out ~4 subjects per fold on ~15 training
subjects — workable, but LOSO uses the maximum available training data per held-out subject, which matters
more at this scale, and every fold still has far more training rows (≥ 18 × 48 = 864 ladder rows) than the
`X.shape[1] + 2` (≤ 4) `grouped_cv_predict` requires to fit. This is the rule-63 case where a threshold
*can* be derived from the machinery (the fold count is bounded below only by that `+2` requirement, which
LOSO satisfies with enormous headroom) rather than fixed by convention.

**Headroom, reported beside every increment (per `NOTE_HEADROOM_NORMALISATION.md`):**
`headroom = 1 − |out-of-fold incumbent-alone Spearman|`, i.e. `1 − |a|` where `a` is the "plain" baseline-only
term already computed inside `increment()`. Report each candidate's muscle-adjusted increment **both** in
raw Spearman units and as a percentage of headroom, so this deposit's numbers sit in the same table as
`ds005620` (headroom 0.79), `capslpdb` (0.34) and `sleep_edfx` (0.155) rather than requiring a new,
incommensurable reading.

**Uncertainty: subject-block bootstrap**, resampling the 19 subjects with replacement (all of that
subject's rows travel together), N_BOOT ≥ 2000, seed derived from a fixed `SEED = 20260802` as in E222/E223.
**Known resolution limit, stated up front rather than discovered after a boundary result (rule 85):** with
only 19 independent units, the CI's exclusion of zero can turn on a small number of bootstrap draws landing
one way or the other; if the printed one-sided fraction (fraction of bootstrap draws with the "wrong" sign)
falls between 0.03 and 0.07, the run must be **repeated at ≥ 3 additional seeds** before the verdict is
written down, and the fraction — not just the interval endpoints — must be reported (rule 46).

**No cross-candidate rank correlation will be computed** — e.g. correlating each candidate's increment size
against its REM-rung distance from the artefact channel, or against anything else, across the four (or
five, with the noise control) tested columns. **Rule 89** is explicit that a rank correlation across a
handful of measures can be entirely a zero-versus-nonzero split, invisible to leave-one-out, and that the
diagnostic that catches it (drop the whole near-zero group) needs more than four or five points to be
worth running at all. With only four real candidates this design has no such comparison to make and does
not attempt one; each candidate's verdict is read independently.

---

## 7. Gates

Each gate below is stated with **the input that should make it fail** and **the input that should make it
pass** (rules 40 and 81), so the gate's own capability is checked before it is trusted.

**G1 — COVERAGE.** `n_subjects == 19` (or, if a documented shortfall is accepted per §5, `n_subjects >= 17`
— a **stated convention**, not derived, scaled down from E222/E223's 100-subject conventions for this
deposit's much smaller fixed roster) **and** every one of the 6 panel-relevant columns has zero missing
values on the retained rows.
  - *Should FAIL on:* today's actual partial file (10 of 19 subjects present, one incomplete) — 10 < 17.
    This is not hypothetical; it is the file's current state, and running the check against it now (as a
    dry run of the gate's code, never as the registered result) is a legitimate way to confirm G1 can fail.
  - *Should PASS on:* the completed 1140-row file with every cell at 12 — expected once extraction finishes,
    per the epoch-index design and the compute script's own cell-count validation.

**G2 — INCUMBENT ALIVE.** Recomputed here, not inherited from E222/E223 (rule 53). Raw Spearman
`rho(spectral_edge_95, ladder)` against the 95th percentile of `|rho|` under 2000 **within-subject** label
permutations (each subject's own 48 ladder-labels shuffled among themselves, preserving the balanced 12-per-
stage design and every subject's marginal). `PASS` iff `|rho| >` that percentile.
  - *Should FAIL on:* the incumbent column replaced by `rng.normal()` — no association survives within-subject
    permutation by construction.
  - *Should PASS on:* the incumbent column replaced by `ladder + rng.normal(scale=0.05)` — near-perfect
    association trivially clears any permutation floor.

**G3 — NEGATIVE CONTROL.** The i.i.d. noise column's muscle-adjusted call (§8) must be `ABSENT` or
`PLACEBO-INDISTINGUISHABLE`, never `REPLICATES` or `MUSCLE-DEPENDENT`.
  - *Should FAIL on:* a synthetic "noise" column constructed as `ladder + rng.normal(scale=0.2)` substituted
    in — deliberately given real signal, to confirm the gate actually notices when a column *does* add.
  - *Should PASS on:* genuine `rng.normal()` with no relation to anything.

**G4 — MUSCLE ADJUSTMENT IS CODE, NOT CAVEAT.** Every increment is computed over both
`[spectral_edge_95]` and `[spectral_edge_95, emg_index]` baselines; the verdict (§8) is built on the second.
This is a structural requirement on the analysis script rather than a pass/fail check with its own
threshold — verified by inspecting that both baseline arms are present in the output, not by a numeric gate.

**G5 — REM RUNG (secondary diagnostic, not a primary gate).** For each of the 6 panel columns, locate the
median REM value on that column's own W→N3 ladder (linear interpolation against the four stage medians, as
E222 implements). REM has the lowest muscle tone of any stage but sits mid-depth, so a column whose REM rung
lands near `emg_index`'s rung is muscle-flavoured; report this beside each candidate's verdict, but it does
not by itself change the verdict — it is context for reading a `MUSCLE-DEPENDENT` or borderline call, exactly
as in E222.

---

## 8. Placebo (rule 55 / rule 88 compliant)

**What must NOT be used, and why**, learned at cost twice already in this project: a covariate-permutation
placebo (permuting rows of `emg_index` while holding the ladder label fixed, or anything of that shape)
tests only whether the *matching/adjustment procedure* manufactured the result — it cannot touch a
genuine between-condition contrast, because the contrast itself (here, the ladder label) is untouched by
permuting a covariate (rule 88, E230/E231). The estimand here is "does this column predict the ladder
label", so the only destruction that can move the *primary statistic itself* is permuting the **label**.

**Placebo P1 — within-subject label permutation on the full increment, not merely on the incumbent's raw
correlation.** For each of 2000 draws, shuffle each subject's own 48 ladder-labels among themselves
(identical scheme to G2, extended from "does the incumbent survive" to "does the *increment* survive"),
recompute the muscle-adjusted increment for each candidate against the shuffled labels, and build the
resulting null distribution. **This placebo can and does change the primary**: it operates directly on `y`,
which both the "plain" and "muscle-adjusted" terms of `increment()` depend on, so a candidate carrying no
real signal about the ladder has its increment driven toward the permutation-null's own spread, and a
candidate that does carry signal will exceed it. Compare the **observed** muscle-adjusted increment against
this null's 95th percentile.

**Per rule 48, this placebo is evaluated only when the primary already excludes zero on the positive side.**
If the muscle-adjusted CI includes zero, there is no real effect for the placebo to fail to reproduce, and
running it would print a misleadingly reassuring "cleared" or "not cleared" over nothing (rule 48's
degenerate case) — the verdict rule in §9 encodes this ordering explicitly.

---

## 9. Verdict rule — wrong-direction case first (rule 37), all branches enumerated

**Per-candidate call**, evaluated only after G1–G3 pass (else the whole run is `NOT INTERPRETABLE`, §9's
top branch):

```
if muscle_adjusted.ci_hi < 0:
    call = REVERSED                      # wrong-direction case FIRST, regardless of anything else
elif muscle_adjusted.ci_lo > 0:
    if observed_increment <= placebo_null_p95:
        call = PLACEBO-INDISTINGUISHABLE  # looks positive, does not clear its own label-permutation null
    else:
        call = REPLICATES
elif plain.ci_lo > 0:                     # muscle-adjusted spans zero, but plain (no emg_index) did not
    call = MUSCLE-DEPENDENT
else:
    call = ABSENT                         # muscle-adjusted spans zero; placebo not evaluated (rule 48)
```

**Aggregate verdict across the four-candidate panel**, same ordering discipline:

1. **NOT INTERPRETABLE** — G1, G2, or G3 fails. (Also applies if extraction is incomplete and this design
   is run anyway without the documented-shortfall procedure in §5.)
2. **REVERSED** — any candidate calls `REVERSED`. Reported and named; never read as partial support for
   anything.
3. **REPLICATES** — at least one candidate calls `REPLICATES` (and none calls `REVERSED`). Report headroom
   share alongside, per §6, so it slots into the existing cross-deposit table.
4. **NOT DISTINGUISHABLE FROM CHANCE** — at least one candidate calls `PLACEBO-INDISTINGUISHABLE` and none
   calls `REPLICATES` or `REVERSED`. This is its own outcome, not folded into `ABSENT`: it means the
   increment looked positive on this bootstrap but did not clear a null built specifically to be able to
   erase it — worth recording separately per rule 46's spirit (report the near-miss, don't collapse it into
   a plain negative).
5. **MUSCLE-DEPENDENT** — at least one candidate calls `MUSCLE-DEPENDENT` and none of 2–4 apply.
6. **ABSENT** — none of the above; no candidate shows any positive signal with or without muscle in the
   baseline.

**Registered prediction, stated before any data is touched:** given (a) the incumbent's likely strength on a
frontal, high-quality forehead-patch signal (plausibly closer to `sleep_edfx`'s 0.845 than to `ds005620`'s
0.209 — pure speculation, not a claim), (b) the small headroom that would leave for any candidate to add
(E223's lesson: a strong incumbent squeezes every increment toward zero regardless of truth), and (c) only
19 subjects driving a noisy bootstrap, **the most likely outcomes are `ABSENT` or `NOT DISTINGUISHABLE FROM
CHANCE`, with `REPLICATES` a real but less probable possibility** — the reverse of E222's registered
expectation, because this design starts from a position of lower power, not higher confidence.

---

## 10. Scope limits, stated where a reader would rely on them (rule 3)

- **This is a replication of the CANDIDATES, not of `whole_head_exponent` as measured elsewhere.**
  `PROBE_2026_08_02_DEPOSITS.md` already flagged this: three forehead channels make `whole_head_exponent`
  here **"a different measurement, not the same one"** as on a full-montage deposit. A `REPLICATES` verdict
  supports "an aperiodic-exponent-shaped quantity computed on a forehead patch adds to spectral edge
  frequency here"; it does not by itself strengthen the claim that the *same* whole-head measurement
  transports across montages.
- **`emg_index` is a weak muscle proxy on a deposit with no true EMG channel at all** (§4). Surviving G4
  rules out contamination this specific weak proxy can detect; it does not establish a candidate is
  "cortical."
- **`relative_alpha_power` is measured on an anterior-only montage**, a worse vantage for a canonically
  posterior rhythm than on a full 10-20 deposit; a null here is weaker evidence against the candidate than a
  null on a deposit with occipital coverage would be.
- **No formal multiple-comparison correction is applied across the four tested candidates**, consistent
  with E222/E223's precedent; a single candidate clearing at nominal 95 % among four tests is weaker
  evidence than the same clearance would be as a single pre-specified test, and the write-up must say which
  candidate(s) cleared and how many were tested, not just report the aggregate verdict.
- **The label's own provenance is not independently verified here.** `EEG.VisualHypnogram` is assumed to
  come from a richer clinical montage than the 3 exported channels (favourable — an independent scoring
  instrument, not a rule-86 shared-observer risk) but this was not directly confirmed against the dataset's
  own documentation before writing this design, and should be checked when the experiment is actually
  written.
- **19 subjects is a small, fixed, already-known roster** — there is no larger cohort to draw from on this
  deposit, unlike `sleep_edfx`'s 142 or `capslpdb`'s 108. Any single-seed boundary result must be treated
  per rule 85 (§6) before being written up as a verdict.

---

## 11. Recommendation and things that would make me advise against running it

**Run it once the features file reaches 1140 rows with every cell at 12** (currently 539/1140, §5) — the
design is complete and there is nothing left to decide first.

**Flags that argue for caution, stated honestly rather than after a disappointing result:**

1. **Power is genuinely low.** 19 subjects, and — per E223's own lesson on this exact incumbent family — a
   strong incumbent leaves almost no headroom for anything to add (`sleep_edfx`'s eight unexposed columns
   all took under 6.5 % of a 0.155 headroom). If `spectral_edge_95` is similarly strong here, this design
   may be underpowered to detect even a real effect of the size E222 found, and an `ABSENT` or `NOT
   DISTINGUISHABLE FROM CHANCE` verdict would not be strong evidence against the candidates — it would need
   to be reported as such, not oversold as a third independent null.
2. **The bootstrap CI will be coarse at n = 19.** Expect to need the ≥3-seed reseed check (§6, rule 85) more
   often than E222 or E223 did at their much larger n.
3. **A `REPLICATES` verdict here cannot be read as confirming `whole_head_exponent` itself** — see §10's
   first scope limit. If the investigator's interest is specifically in validating that measurement across
   montages, this deposit answers a narrower question than it might look like it answers.
4. **If extraction stalls or fails for specific subjects** (as opposed to simply being incomplete), that is
   worth diagnosing before running the confirmatory test — a systematic per-subject failure could itself be
   outcome-related (rule 14) in ways a clean "still being written" is not.

None of these is a reason to abandon the design — they are reasons to report a null, if one comes back,
as **a null under low power**, and to report `REPLICATES`, if one comes back, with the scope limits of
§10 attached rather than as an unqualified third replication.
