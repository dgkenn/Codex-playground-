# Audit: every claim that depends on `alpha_peak_hz_wide` / `relative_alpha_power_iaf` / `_iaf_peak`

*2026-08-02. Record audit only — no analysis run, no registration filed, no ledger row added, no code
changed. Produced in response to E239's own closing sentence: "Adoption requires enumerating every claim
resting on `alpha_peak_hz_wide` and `relative_alpha_power_iaf` first, E233 included (rules 1 and 2)." This
document is that enumeration. It does not recommend adopting or not adopting E239's prominence gate — that
is not this document's call.*

**The defect, restated from E239's ledger row, verbatim:** *"the derived k = 3.5 robust sds, chosen on 200
calibration backgrounds and measured on 200 DISJOINT ones, takes the false-positive rate from 0.915 to
0.0200"* — i.e. the shipped, ungated `_iaf_peak` returns a finite "peak" on signal-free 1/f background in
**91.5 %** of draws (E237's own re-measurement of the same quantity gives **87.5 %**; the two runs used
different calibration/held-out splits and both numbers are quoted verbatim below, attached to the file that
produced each).

**Scope note, established first because it changes the search radius.** `alpha_peak_hz` (no suffix) is a
**different, older candidate** — `f_alpha_peak_hz` at `bsde/src/bsde/candidates/seed.py:197`, the raw PSD
maximum inside a fixed 8–13 Hz box, registered separately at `seed.py:538`. It does **not** call `_iaf_peak`
and does not inherit this defect; it has its own, different, already-documented failure mode (censoring at
the box edge, `test_the_incumbent_peak_estimator_is_WRONG_outside_its_band_not_merely_censored`). Every
result keyed only to bare `alpha_peak_hz` (E155, E156, E161, E165, E169, E193, E213, E45, E54, E57, E44,
E151) is **out of scope for this audit** and is not discussed further below.

---

## 1. Search performed, and what each grep returned

Run from the repo root:

```
grep -rn "alpha_peak_hz_wide"        bsde/src bsde/scripts bsde/docs bsde/governance analysis docs
grep -rn "relative_alpha_power_iaf"  bsde/src bsde/scripts bsde/docs bsde/governance analysis docs
grep -rn "_iaf_peak"                 bsde/src bsde/scripts bsde/docs bsde/governance analysis docs
grep -rn "alpha_peak_hz\b"           bsde/src bsde/scripts bsde/docs bsde/governance analysis docs
```

Results, by directory:

| pattern | `analysis/` | `docs/` (top-level, burst-suppression project) | `bsde/src` | `bsde/scripts` | `bsde/docs` | `bsde/governance/REGISTRATION_LEDGER.jsonl` |
|---|---|---|---|---|---|---|
| `alpha_peak_hz_wide` | **0 hits** | **0 hits** | 6 files | 1 file | 6 files | 2 rows (E237, E239) |
| `relative_alpha_power_iaf` | **0 hits** | **0 hits** | 5 files | 1 file | 5 files | 2 rows (E233, E239) |
| `_iaf_peak` | **0 hits** | **0 hits** | 2 files (definition site + E237's discussion) | 0 | 2 files | 0 (covered by the two rows above, which name the candidates rather than the private function) |
| `alpha_peak_hz\b` (bare) | 0 | 0 | many (separate candidate, out of scope per above) | 0 | several (out of scope, same reason) | several (out of scope) |

**The burst-suppression project (`analysis/`, top-level `docs/`) returns zero hits for all three patterns.**
This defect is entirely contained within `bsde/` — expected, since `_iaf_peak` was added to `bsde`'s own
candidate registry and the two projects do not share code paths (per `CLAUDE.md`'s standing instruction not
to cross-apply findings between the two).

Definition site, confirmed by direct read of `bsde/src/bsde/candidates/seed.py:146-194`:
- `_iaf_peak(data, sfreq)` (line 146) — locates the argmax of the aperiodic-corrected log-residual over a
  5–15 Hz search window, returns NaN if the max sits on either edge of that window.
- `f_alpha_peak_hz_wide` (line 177) — returns `_iaf_peak(data, sfreq)` directly.
- `f_relative_alpha_power_iaf` (line 182) — calls `_iaf_peak`, then computes relative power in
  `[peak-2, peak+2]` Hz; returns NaN if the peak is NaN.

Both are registered at `seed.py:481` and `seed.py:501` respectively.

---

## 2. Registered experiments

Six ledger rows use one or both candidates. All six are quoted from
`bsde/governance/REGISTRATION_LEDGER.jsonl` verbatim (only whitespace/line-wrapping changed for
readability; no words added, removed or reordered).

### E218 — `e218_anchored_alpha_inversion.py`

**Question (verbatim):** *"Does a band ANCHORED to each recording's own alpha peak still invert its
deep-versus-light direction between propofol and sevoflurane, as the fixed 8-13 Hz band does, on the same
cases and the same windows?"*

**Outcome field:** `"gate_failed"`.

**Outcome detail (verbatim, in full):** *"THE FIRST RUN PRINTED 'ANCHORING REMOVES IT' AND IT IS WITHDRAWN.
WITH THE MISSING GATE ADDED THE VERDICT IS NOT INTERPRETABLE. ... G5 now enforces it. ... A REFRAMING THAT
SURVIVES AND CHANGES THE STANDING STORY. Printing the fixed measure's per-arm aliveness shows THE INVERSION
IS ASYMMETRIC: within sevoflurane, deep-above-light is -0.5211 against a floor of 0.2394 and is decisively
alive; within propofol it is +0.2273 against a floor of 0.3182 and is NOT alive. ... P2 ... The uncensored
estimator puts the propofol-minus-sevoflurane peak shift at depth at +1.38 Hz (10.50 vs 9.12) against the
censored estimator's +1.50 Hz (10.00 vs 8.50)."*

**Dependency classification: CORRECTNESS.** E218's own registered primary (whether the anchored measure
*itself* carries depth) already returned DEAD IN BOTH ARMS on the `_iaf_peak`-derived
`relative_alpha_power_iaf` — the file's own G5 gate found the anchored measure's deep-vs-light rate at
**-0.0455** (propofol, floor 0.2727) and **-0.0423** (sevoflurane, floor 0.2113), i.e. it already failed on
its own terms before any prominence question was asked. But the retained P2 (the +1.38 Hz peak-shift-at-depth
number) is a numeric comparison of peak *locations*, and a peak location computed on windows where a
substantial fraction of "peaks" are noise-driven maxima is not a magnitude one can trust at face value — it
depends on the true peak's *value*, not merely its presence, so this is a CORRECTNESS dependency, not merely
an AVAILABILITY one.

### E233 — `e233_band_placement_or_biology.py`

**Question (verbatim):** *"Is the relative_alpha_power reversal a property of the oscillation, or of the
fixed 8-13 Hz window it is measured in?"*

**Outcome field:** `"negative"`.

**Outcome detail excerpt (verbatim):** *"BAND PLACEMENT. The reversal is an artefact of measuring a moving
oscillation through a stationary window ... P1, the same contrast with the band anchored to each recording's
own peak, is +0.0730 [-0.0107, +0.1584] -- it includes zero, and the anchored measure does not clear its
donor null in the sevoflurane arm at all (C = 0.0276 against 0.2715). With anchored alpha substituted the
direction agreement becomes 10 of 10: THE PANEL HAS NO REVERSAL LEFT IN IT. A1 supplies the mechanism the
artefact requires and it is present: the peak location contrast is +0.3070 [+0.2149, +0.3938], driven
entirely by sevoflurane, where the peak falls reliably with dose (mean signed rho -0.3296, C = 0.8204 against
a null of 0.2770) while under propofol it does not move at all (-0.0226, C = 0.0970 against 0.3163, failing
its null)."*

**Dependency classification: CORRECTNESS, and this is the load-bearing row of the whole audit.** The
finding rests on two things computed from `_iaf_peak` output: (1) `relative_alpha_power_iaf` (P1, the
"anchored measure has no reversal" claim) — a *magnitude*, sensitive to whichever spurious frequency the
estimator centred its ±2 Hz window on when no real peak existed; and (2) the peak-location-vs-dose
correlation (A1, mean signed rho -0.3296 vs -0.0226) — a *rank* statistic, which E237 (below) establishes is
robust *where a real peak exists*, but whose robustness to a noise-dominated arm was never separately
checked. This is exactly the ambiguity `NOTE_CHALLENGE_A_REFRAMED.md` calls "the propofol null is defended"
and, per §4 below, that defense itself is not settled.

### E235 — `e235_derived_geometry.py`

**Question (verbatim):** *"Is the panel-wide propofol/sevoflurane magnitude gap explained by sevoflurane
translating the spectrum?"*

**Outcome field:** `"withdrawn"`.

**Outcome detail excerpt (verbatim):** *"THE REGISTERED VERDICT FIRED AND IS WITHDRAWN ON A ROBUSTNESS
CHECK. ... Centre = median alpha_peak_hz_wide across that arm's cases. Shift = half the median within-case
[peak excursion]."* (Centre/shift definitions are quoted from the file's own docstring, referenced at
`e235_derived_geometry.py:205,216`, since the ledger's `outcome_detail` states the numeric geometry —
"centre 9.688 Hz, shift 2.175 Hz down to 7.512 Hz" — without repeating the variable names.)

**Dependency classification: CORRECTNESS, but of the SYNTHETIC calibration parameter only, and the
experiment's own verdict is already withdrawn for an unrelated reason** (a 4-vs-11 threshold confound, not
anything to do with peak validity). `alpha_peak_hz_wide` here supplies only two summary numbers (a median
centre frequency and a median excursion) used to parameterise a *synthetic* signal generator — the panel-wide
result itself is computed on that synthetic signal, not on real per-window peaks. If the true median centre
or excursion is biased by noise-driven "peaks," the synthetic geometry could shift, but the verdict was
withdrawn on other grounds first, so this is low-priority.

### E236 — `e236_translation_vs_frequency.py`

**Question (verbatim):** *"Does sevoflurane's panel-wide advantage track a measure's sensitivity to
spectral translation, or where in the spectrum it looks?"*

**Outcome field:** `"positive"`.

**Outcome detail excerpt (verbatim):** *"TRANSLATION BEATS FREQUENCY RANGE, AND ONLY AS A THRESHOLD CONTRAST
-- both halves registered in advance and both reported. ... P1 = +0.6383, permutation p_hi = 0.0096 ...
READING: the panel-wide magnitude gap is associated with an instrument property rather than being shown to
be pharmacology ... the evidence is a 4-versus-11 contrast and carries only as much mechanistic weight as
four measures can bear."*

**Dependency classification: CORRECTNESS, same mechanism as E235** — E236 reuses E235's derived-geometry
synthetic signals (per `e236_translation_vs_frequency.py:305`, `per.setdefault(row["meta_caseid"], []).append(
_num(row, "alpha_peak_hz_wide"))`, identical extraction pattern to E235). Its own verdict already carries a
stated weakness (4-vs-11 threshold contrast, "only as much mechanistic weight as four measures can bear"),
independent of the peak-correctness question — this experiment's headline is not primarily *about*
`alpha_peak_hz_wide`'s values, it inherits E235's synthetic-geometry parameterisation once removed.

### E237 — `e237_peak_estimator_robustness.py`

**Question (verbatim):** *"Does the aperiodic-fit defect (rule 90) corrupt the peak estimator that E233's
retraction rests on?"*

**Outcome field:** `"positive"`.

**Outcome detail (verbatim, in full):** *"E233 SAFE as registered, with a caveat found by the gates that
matters more than the verdict. ... P1: over 7.5-11.0 Hz the estimator is perfectly monotone, Spearman
+1.0000 with 0 adjacent inversions. P2: bias at the sevoflurane operating point and at the propofol one are
both +0.000, differing by less than the 0.2500 Hz PSD bin. P3: OLS and robust agree to 0.0000 Hz everywhere
in the sweep. So rule 90's defect is real, documented, and INERT for this estimator on this signal class,
and E233's rank statistics are not reordered by it. THE RESULT IS SUSPICIOUSLY PERFECT AND THAT IS ITSELF
INFORMATIVE. ... A follow-up SNR sweep, run immediately, locates the cliff: at oscillation amplitude >= 0.15
both fits are identical and accurate to 0.056 Hz; at 0.08 the error rises to 0.34-0.46 Hz and the two fits
diverge by 0.125 Hz; at 0.04 and below the estimator is reading noise, with errors of 2.0-2.8 Hz. So the
clearance holds WHERE THERE IS A PEAK and says nothing about low-SNR windows. G3 IS THE REAL FINDING AND MY
GATE WAS NEARLY UNFAILABLE. ... Measured properly: on pure 1/f background with no oscillation at all, the
estimator returns a FINITE peak in 87.5 percent of draws. VitalDB's 93 percent peak-detectability rate is
therefore NOT evidence that 93 percent of windows carry a real alpha peak -- it is what this estimator
produces from noise. WHAT THAT DOES AND DOES NOT TOUCH IN E233. The sevoflurane finding survives: a
noise-driven estimator cannot produce a within-case correlation with dose of -0.3296 at consistency 0.8204.
The PROPOFOL NULL becomes ambiguous, because 'the peak does not move' and 'these windows have too little
alpha for the estimator to track anything' are now indistinguishable. Separating them needs a peak
PROMINENCE comparison between the arms, which is the successor."*

**Dependency classification: this experiment IS the correctness/availability finding**, not a claim that
depends on it — it is the source of both numbers (87.5 % / 91.5 %, next entry) that every other row in this
table must now be read against. Its own conclusion about E233: the sevoflurane arm's rank statistic (Spearman
monotone tracking, established elsewhere in the same registered result) is defended by a rank-based argument
this audit classifies as RANK-SAFE per E237's own P1 (monotone where a peak exists); the propofol arm's null
is explicitly left AMBIGUOUS by E237 itself, in E237's own words above.

### E239 — `e239_prominence_gated_peak.py`

**Question (verbatim):** *"Can the peak estimator's 87.5 percent false-positive rate be repaired by a
prominence gate, and at what cost to sensitivity?"*

**Outcome field:** `"positive"`.

**Outcome detail (verbatim, in full):** *"REPAIR VALIDATED ON SYNTHETIC DATA, and the printed verdict
OVERSTATES because P3 was never evaluated -- disclosed here rather than left in the output. What ran and
passed: the derived k = 3.5 robust sds, chosen on 200 calibration backgrounds and measured on 200 DISJOINT
ones, takes the false-positive rate from 0.915 to 0.0200 against a registered 0.05 target. Detection at
amplitude 0.30 stays at 1.000 with accuracy unchanged at 0.056 Hz, and at 0.15 it is still 0.967. Below that
the gate correctly collapses -- 0.325 at amplitude 0.08 and 0.058 at 0.04 -- which is exactly where E237
located the ungated estimator's accuracy cliff, so the gate rejects the regime in which the answer was
already wrong (ungated error there is 2.391 Hz). G1, G2 and G3 all passed. THE DEFECT IN THIS FILE: the
registered branch (c) requires 'P1 <= 0.05 AND P2 >= 0.90 AND P3 shows the predicted stage ordering', and the
code's branch checks only the first two. P3 could not run at all, because the cached sleep_edfx_iaf table
carries the peak but not its prominence, so the file printed the UNGATED per-stage picture instead and the
verdict fired without its third condition. A gate that exists in prose and not in code, for the third time in
this project. The repair is therefore validated on synthetic signals only. The ungated Sleep-EDFx picture is
damning for the incumbent and is worth recording on its own: detection is 0.648 in W and 0.915 in REM against
0.993 in N2 and 0.979 in N3 -- HIGHER in slow-wave sleep than in wakefulness, which is backwards -- and 72.3
percent of N2 detections and 58.3 percent of N3 detections sit in the top 2 Hz of the 5-15 Hz search window
against 12.0 percent in W and 10.8 percent in REM. The estimator is reporting its own window edge where there
is no alpha to find. NOTHING SHIPPED WAS MODIFIED. Adoption requires enumerating every claim resting on
alpha_peak_hz_wide and relative_alpha_power_iaf first, E233 included (rules 1 and 2), and the real-data
control must run before that."*

**Dependency classification: this is the repair validation, not a dependent claim** — it is the second
source experiment (with E237) that every row above must be read against. Its own real-data control (the
Sleep-EDFx per-stage ungated picture) is itself a NEW real-data finding that had never been reported before
this audit's search surfaced it: **detection rate on real Sleep-EDFx recordings is higher in N2/N3 than in
W/REM, and a majority of N2/N3 detections sit in the top 2 Hz of the search window** — independent
corroboration, on real (non-synthetic) EEG, that the estimator manufactures edge-adjacent "peaks" when a
real one is weak or absent.

### Summary table, registered experiments

| id | uses | dependency class | current status w.r.t. gate |
|---|---|---|---|
| E218 | both | CORRECTNESS (peak-shift-at-depth number, P2) | already `gate_failed`/withdrawn on unrelated grounds; the retained P2 number needs re-derivation if reused |
| E233 | both | CORRECTNESS (P1 magnitude + A1 rank-on-noise ambiguity) | **most load-bearing — see §5** |
| E235 | `alpha_peak_hz_wide` (synthetic geometry input) | CORRECTNESS (two summary scalars feeding a synthetic generator) | already `withdrawn` on unrelated grounds (4-vs-11 confound) |
| E236 | `alpha_peak_hz_wide` (inherited from E235) | CORRECTNESS (indirect, via E235's synthetic geometry) | verdict already caveated (4-vs-11); low priority |
| E237 | both (as subject, not dependent) | — (this IS the defect-measuring experiment) | source of record |
| E239 | both (as subject, not dependent) | — (this IS the repair-validating experiment) | source of record |

---

## 3. Cached results tables

Checked by reading each candidate file's header line directly (not assumed from a script). Three tables
carry one or both columns:

| file | exists? | header excerpt (peak-related columns only) |
|---|---|---|
| `bsde/results/sleep_edfx_iaf.csv` | confirmed (124,832 bytes) | `...,alpha_peak_hz_wide,relative_alpha_power_iaf,alpha_peak_hz,relative_alpha_power` |
| `bsde/results/vitaldb_iaf.s0.csv` … `.s3.csv` (4 shards) | confirmed, all four | `...,alpha_peak_hz_wide,relative_alpha_power_iaf,alpha_peak_hz,relative_alpha_power` — also confirmed via each shard's `.manifest.json`, which records a content-hash `"definitions"` block naming both candidates by their registry hash (`alpha_peak_hz_wide: b159af64b3fb1b61:b9934f44c79e4857`, `relative_alpha_power_iaf: f2e65e9293e265f6:b9934f44c79e4857`) |
| `bsde/results/ds006695_features.csv` | confirmed (348,085 bytes) | `subject,stage,epoch_index,t_start_s,alpha_peak_hz,alpha_peak_hz_wide,...,relative_alpha_power,relative_alpha_power_iaf,...` |

No other `.csv` in `bsde/results/` (checked by grepping the header line of every file in that directory)
carries either column.

**`ds006695_features.csv` needs a caveat, not a remediation**: `bsde/docs/DESIGN_2026_08_02_DS006695_CHALLENGE_C.md`
explicitly lists both peak columns under "missingness on columns NOT in the panel (context only)" — quoted
verbatim: *"The two columns with nonzero missingness in the file (`alpha_peak_hz_wide` and
`relative_alpha_power_iaf`) are not in this panel."* That design's own tested panel is
`whole_head_exponent, multiscale_entropy_slope, relative_alpha_power, pac_slow_alpha` — none of which are
peak-derived. **No registered ledger row exists for this design** (confirmed: `grep -c "ds006695"
bsde/governance/REGISTRATION_LEDGER.jsonl` returns 0), so `ds006695_features.csv`'s peak columns are present
in the cache but currently unused by any claim.

---

## 4. Documents that quote a number derived from the peak

### `bsde/docs/NOTE_CHALLENGE_A_REFRAMED.md` — the most exposed document in the audit

Section "FOURTH CORRECTION, AND IT RETRACTS THE FINDING: the reversal is BAND PLACEMENT" quotes, verbatim:

> *"`relative_alpha_power_iaf` (follows the peak) | **+0.0730 [−0.0107, +0.1584]** | **propofol only — fails
> in sevoflurane (0.0276 vs 0.2715)**"*

> *"sevoflurane | **−0.3296** | 0.8204 vs 0.2770 — **clears** ... propofol | −0.0226 | 0.0970 vs 0.3163 —
> **fails**"*

> *"**Sevoflurane slides the alpha peak downward as dose rises. Propofol does not move it.** ... Survives:
> ... sevoflurane produces a measurable, consistent downward shift of the alpha peak that propofol does
> not. That is a statement about an oscillation rather than about a window, and it is what should be carried
> forward."*

A later section, **"The propofol null is defended, 2026-08-02 (E237 and its follow-up)"**, attempts to
resolve exactly the ambiguity E237 raised, quoted verbatim:

> *"Measured directly, using the anchored alpha power already cached as a peak-prominence proxy: ... propofol
> | 114 | 0.1972 [0.1531, 0.2610] | 0.0696 ... sevoflurane | 88 | 0.1906 [0.1330, 0.2318] | 0.0725 ... Cohen's
> d (sevoflurane minus propofol) = −0.3325, arm-permutation |p| = 0.0012. **Propofol windows have MORE power
> at their own peak, not less**, and the two arms' peak-detection failure rates are indistinguishable (0.0696
> vs 0.0725). So the propofol null is not an artefact of absent alpha ... The asymmetry stands: sevoflurane
> slides the alpha peak downward with dose and propofol does not."*

**This is the single number most at risk of reversal in the whole audit — flagged explicitly in §6.** This
section was written (file mtime 17:44:53) *after* E237 (17:42:22, and the section cites E237 by name) but
*before* E239 (18:03:26). It uses "anchored alpha power" (`relative_alpha_power_iaf`) as a **peak-prominence
proxy** to argue the propofol arm's peak is real, not absent. But `relative_alpha_power_iaf` is computed by
first calling `_iaf_peak` to *locate* a peak and only then measuring power around it — if `_iaf_peak` itself
manufactured a spurious location (as it does on 87.5–91.5 % of signal-free draws), the "power at the peak" it
then reports is power measured around an arbitrary point, not evidence the point is real. The document's own
reasoning — "the two arms' peak-detection failure rates are indistinguishable (0.0696 vs 0.0725)" used as
evidence *for* real signal — is the identical logical move E237 itself just refuted one section earlier
("VitalDB's 93 percent peak-detectability rate is therefore NOT evidence that 93 percent of windows carry a
real alpha peak"). **E239's prominence gate — built precisely to settle whether a detected peak is real — was
never applied to this comparison; E239's own ledger row states its real-data (P3) arm could not run at all
because the cached table carries the peak but not its prominence.** This section's conclusion is therefore
**currently unresolved, not confirmed**, by the project's own later finding.

### `bsde/docs/AUDIT_2026_08_02_BAND_DEPENDENCE.md`

Quotes and uses `alpha_peak_hz_wide` / `relative_alpha_power_iaf` only inside a **wholly synthetic**
sensitivity sweep with a planted, always-present oscillation (amplitude 1.2 against a Brownian-ish
background) — confirmed by direct read of its §1 Method section: *"No real data was read, opened, or
referenced anywhere in this audit. Every array is `numpy`-generated."* Relevant quoted rows:

> *"`alpha_peak_hz_wide` | 10.000 | 9.000 | 0.000 | -- (raw diff **-1.000 Hz**) | zero-variance, perfect
> tracking"* (primary pair, in-box)

> *"`alpha_peak_hz_wide` | 8.500 | 7.500 | 0.000 | -- (raw diff **-1.000 Hz**, correctly tracks the edge) |
> zero-variance, perfect tracking"* (edge pair)

> *"`relative_alpha_power_iaf` | -- | -- | 0.0167 | +0.361 | OK"* and *"... 0.0127 | +0.473 | OK"*

**Dependency classification: RANK/SENSITIVITY, not correctness-dependent, and this file is UNAFFECTED by the
gate.** Every synthetic trial injects a real oscillation at amplitude 1.2, which — per E237's own SNR sweep
(accuracy 0.056 Hz at amplitude ≥ 0.15, only degrading below 0.08) — sits comfortably inside the regime where
the estimator is known to be accurate. The audit is measuring *how sensitively the candidate responds to a
real, moving peak*, not whether a peak exists at all; a prominence gate would not change any number in this
file. Its own §7 Limitations section separately (and correctly, on different grounds) flags that
`alpha_peak_hz_wide`/`relative_alpha_power_iaf` were measured by only one synthetic generator, unlike the
older E214 sweep — an orthogonal caveat, not one this audit's gate touches.

### `bsde/docs/PROBE_2026_08_02_SEPARABILITY.md`

§14.3, "THE DECISIVE STEP," quotes and computes real per-window peak-frequency distributions from
`vitaldb_iaf.s0-3.csv` directly (not synthetic):

> *"Missingness (rule 5): **3.7% NaN on both columns (238/6,438)** -- well inside the candidate's own
> registered failure threshold ('NaN on more than a third of windows'), so the estimator declares itself
> alive by its own criterion on this deposit."*

> table: *"overall | 6,200 | 10.50 | 9.00 | 11.50 | 5.25 | 14.75"*, *"propofol (pure arm) | 1,113 | 10.50 |
> 9.75 | 11.50 ..."*, *"sevoflurane (pure arm) | 1,810 | 9.75 | 8.50 | 11.25 ..."*, *"BIS bottom decile
> (<=30.4, deep) | 567 | 9.75 | 8.50 | 11.25 ..."*, *"BIS top decile (>=60.9, light) | 515 | 11.25 | 8.75 |
> 12.75 ..."*

> *"Within this one deposit, peak frequency does move with state in directions broadly consistent with
> E233's underlying premise: deeper anaesthesia (bottom BIS decile) sits half a Hz to a Hz lower than lighter
> anaesthesia (9.75 vs 11.25 median), and sevoflurane's pure-arm median (9.75) sits below propofol's (10.50)
> ..."*

**Dependency classification: CORRECTNESS/AVAILABILITY, both.** The passage explicitly treats a **low NaN
rate (3.7 %)** as evidence the estimator "declares itself alive" — precisely the AVAILABILITY inference
E237/E239 show is unsound (a 3.7 % NaN rate here is entirely consistent with the estimator returning finite
noise-driven values on almost all windows regardless of real alpha content, since even pure background noise
returns finite in 87.5–91.5 % of draws — a NaN rate below 13 % proves nothing). The median-Hz comparisons
across arms and BIS deciles are direct uses of the raw peak *value*, so they are CORRECTNESS-dependent as
well. This section is explicit that it "corroborates the direction without repeating the actual test," so it
was never presented as a standalone registered finding — but it is quoted, in the present tense, as
supporting evidence for E233's mechanism, and it has the same unresolved status as the
NOTE_CHALLENGE_A_REFRAMED passage above.

### `bsde/docs/DESIGN_2026_08_02_DS006695_CHALLENGE_C.md`

Already covered in §3: explicitly **excludes** both columns from its tested panel, quoted verbatim above.
No remediation needed for this document; included here only for completeness per the task's instruction to
check it.

### `bsde/docs/LIT_2026_08_02_ALPHA_PEAK_SHIFT.md` — not in the task's named list, included because it quotes numbers derived from the candidate

This document's §1.2, "The instrument itself has been validated, independently of the real-data result,"
quotes the same AUDIT_2026_08_02_BAND_DEPENDENCE.md synthetic rows above and concludes, verbatim:

> *"This is why the A1 finding uses `alpha_peak_hz_wide` and not the older estimator, and it is why the audit
> treats the instrument as trustworthy for exactly the measurement your prompt describes."*

**This sentence is now stale.** File mtime 17:35:22 — written **before** E237 (17:42:22) existed. "Trustworthy"
was true of the synthetic capability test available at the time (a planted-peak-present test only); it does
not anticipate the false-positive-on-noise finding E237 produced seven minutes later. The document's PART 3
bottom line restates the same claim as established fact: *"the instrument behind it (`alpha_peak_hz_wide`) is
independently validated by a synthetic capability test."* No later revision of this file was found.

### `bsde/docs/NOTE_ALPHA_INSTABILITY.md`

Checked directly: **zero hits** for all four search patterns (`alpha_peak_hz_wide`,
`relative_alpha_power_iaf`, `_iaf_peak`, `alpha_peak_hz`) despite being named in the task and despite
`NOTE_CHALLENGE_A_REFRAMED.md` referring to it ("That sentence, in E229, E232, the second and third
corrections above, and everything in `NOTE_ALPHA_INSTABILITY.md` descended from it, is a statement about band
placement.") — i.e. `NOTE_ALPHA_INSTABILITY.md` is described elsewhere as containing claims *descended from*
the retracted fixed-band alpha reversal, but it does not itself mention either peak-anchored candidate by
name. **Reported exactly as found: this file is unaffected by the gate because it never touches the
gated instrument, though its own subject matter (the pre-E233 `relative_alpha_power` reversal) was already
separately retracted by E233 for a different, already-documented reason.**

### `tests/test_iaf_capability.py` — the capability suite itself

Not a document, but worth recording here because two documents above cite it as validation. Six tests, all
against a **planted, always-present** oscillation; none test a no-signal condition except
`test_no_peak_returns_nan_rather_than_a_band_edge`, which asserts:

```python
got = r.get("alpha_peak_hz_wide").fn(pure, ["a", "b"], SFREQ, {})
assert (not np.isfinite(got)) or (5.0 < got < 15.0)
```

**This assertion cannot fail** — it accepts either NaN or *any* finite value inside the search range, which
is every value the function can ever return. This is the exact rule-40 defect ("a gate that cannot fail is
not a gate") that E237's own ledger row names about its own G3 gate; this pre-existing test in the shipped
suite has the identical shape and has not been changed by E237 or E239.

---

## 5. Ranked remediation list

Ranked by how load-bearing the claim is (how much of the project's standing narrative rests on it), not by
how cheap the fix is, per the task's instruction.

1. **`bsde/docs/NOTE_CHALLENGE_A_REFRAMED.md`, "The propofol null is defended" section.** MUST BE
   RECOMPUTED, not merely re-read. This is the highest-priority item: it is the project's current standing
   position on Challenge A's one surviving alpha finding, it explicitly attempts to close the exact ambiguity
   E237 raised, and it does so using the same ungated instrument E237 showed cannot support that inference.
   Recomputation requires E239's prominence gate applied to real VitalDB windows (P3 of E239, registered but
   never executed because `sleep_edfx_iaf.csv`/`vitaldb_iaf.s*.csv` carry the peak but not its prominence —
   a re-extraction, not a re-read).

2. **E233's ledger row itself (`bsde/results/e233_band_placement_or_biology.json` and the ledger's own
   `outcome_detail`).** MUST BE RECOMPUTED. This is the project's currently-registered explanation for why
   Challenge A's alpha reversal is a band-placement artefact rather than biology. E237 already confirmed the
   sevoflurane arm's rank statistic is safe (monotone tracking where a peak exists); the propofol arm's null
   and the P1 magnitude (`relative_alpha_power_iaf` = +0.0730 [-0.0107, +0.1584]) are exactly what item 1
   above would either confirm or overturn. These two remediation items are the same underlying question asked
   from two documents and should be resolved together, not separately.

3. **`bsde/docs/PROBE_2026_08_02_SEPARABILITY.md` §14.3's per-arm/per-BIS-decile median peak table.** SHOULD
   BE RECOMPUTED if it is to be cited again as corroboration (it is currently used as supporting, not primary,
   evidence for E233's mechanism). Cheaper than items 1–2 since it is a descriptive table, not a registered
   primary, but it repeats the same AVAILABILITY misreading (low NaN rate treated as evidence of real signal)
   and should not be quoted as-is until a prominence-gated version exists.

4. **`bsde/docs/LIT_2026_08_02_ALPHA_PEAK_SHIFT.md` §1.2 and PART 3.** MUST BE RE-READ AND FLAGGED (not
   recomputed — it does not itself compute anything, it cites AUDIT_2026_08_02_BAND_DEPENDENCE.md). Add a
   note that "the instrument itself has been validated" predates E237 and does not cover the false-positive
   finding; the literature-comparison content (Hayashi 2008, Zhang et al. 2022, Shen 2026) is external and
   independent of `_iaf_peak` and is unaffected.

5. **E218's retained P2 number** (+1.38 Hz vs +1.50 Hz peak-shift-at-depth comparison). SHOULD BE
   RE-DERIVED if ever reused — the experiment's own primary already returned `gate_failed`/DEAD IN BOTH ARMS
   on independent grounds, so this is low-urgency unless someone goes back to cite the P2 number in isolation
   (which the ledger row's phrasing — "REPORTED AS REGISTERED WHATEVER P1 GAVE" — makes plausible).

6. **E235/E236's synthetic-geometry input scalars** (median `alpha_peak_hz_wide` centre and excursion used
   to parameterise a signal generator). LOW PRIORITY — RE-READ IS PROBABLY SUFFICIENT. Both experiments'
   headline verdicts are already caveated for an unrelated, larger reason (E235 withdrawn on a 4-vs-11
   threshold confound; E236's own P3 registered exactly that limit). A shift in the two input scalars would
   move the synthetic geometry, not overturn either verdict, which is already reported as weak.

7. **`bsde/docs/AUDIT_2026_08_02_BAND_DEPENDENCE.md`.** UNAFFECTED — no action needed. Confirmed
   synthetic-only, planted-peak-present, inside the SNR regime E237 itself establishes as reliable.

8. **`bsde/docs/DESIGN_2026_08_02_DS006695_CHALLENGE_C.md`.** UNAFFECTED — no action needed. Explicitly
   excludes both columns from its panel; no ledger row exists for it yet regardless.

9. **`bsde/docs/NOTE_ALPHA_INSTABILITY.md`.** UNAFFECTED by this specific gate — confirmed zero references
   to any of the four search patterns, though it should be read alongside item 1–2's resolution since it is
   named elsewhere as the document where the (separately, already-retracted) pre-E233 alpha-reversal claims
   live.

10. **`tests/test_iaf_capability.py::test_no_peak_returns_nan_rather_than_a_band_edge`.** Not a claim, but
    flagged: this shipped test cannot fail (§4) and gives false assurance to any future reader who runs the
    suite and sees it pass. Whether to strengthen it is a code change and outside this audit's scope, but its
    existence should be known to whoever next touches the prominence gate.

---

## 6. Claims that would REVERSE, not merely weaken, if the gate were adopted

Per the task's explicit instruction, flagged separately because these are the ones the audit exists to find.

**(a) `NOTE_CHALLENGE_A_REFRAMED.md`'s "propofol null is defended" conclusion.** The section's own words —
*"Propofol windows have MORE power at their own peak, not less ... the propofol null is not an artefact of
absent alpha ... The asymmetry stands"* — is a claim that the propofol arm's flat peak-vs-dose relationship
reflects real biology (propofol genuinely does not move the alpha peak) rather than measurement failure
(propofol windows have weak enough alpha that the estimator is tracking noise in that arm). **If a
prominence-gated re-analysis found that propofol windows disproportionately fail the k = 3.5 threshold (i.e.
disproportionately lack a real, prominent peak) while sevoflurane windows disproportionately pass it, the
correct reading would invert to "the propofol result is uninterpretable, not null"** — a difference between
"propofol's peak doesn't move" and "we cannot tell whether propofol's peak moves" is not a weaker version of
the same claim, it is the opposite of a positive finding. E239's own real-data control found exactly this
asymmetry-in-kind on a *different* deposit (Sleep-EDFx): detection was *higher*, not lower, in slow-wave
sleep than wakefulness, and concentrated at the search window's own edge — precisely the pattern that would
produce a spurious "peak is stable" reading in whichever arm has the weaker true oscillation. The direction
of that asymmetry for VitalDB's propofol-vs-sevoflurane arms specifically has never been checked.

**(b) E233's overall verdict, "THE PANEL HAS NO REVERSAL LEFT IN IT."** This sentence is the direct
consequence of (a): it depends on the propofol P1 interval (+0.0730 [-0.0107, +0.1584]) being read as "no
effect" rather than "no measurable effect because the instrument had nothing to measure in this arm." If (a)
reverses, E233's "there is no reversal, only band placement" conclusion does not merely weaken — the
question of whether a real biological reversal exists in the propofol arm would be **reopened**, not settled
in either direction, which itself reverses the closed, declarative tone of the current ledger row
("THE PANEL HAS NO REVERSAL LEFT IN IT").

**No other claim in this audit was found to reverse.** Items §5.3, §5.5 and §5.6 would weaken or need
re-scaling at most (their host verdicts are already caveated on independent grounds); items §5.7–§5.9 are
unaffected; item §5.10 is a code defect, not a claim.
