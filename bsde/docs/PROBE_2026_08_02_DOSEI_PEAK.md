# FEASIBILITY PROBE — can DOSE-I replicate E242's propofol peak-vs-exposure null?

*2026-08-02. No registration, no ledger row. Coverage and capability check only (catalogue rule 41), run
BEFORE any registration. No new data was downloaded to produce this document — every number below comes
from files already in `bsde/results/` or from code already in the repo.*

**VERDICT: FEASIBLE. Binding constraint: `alpha_peak_hz_wide` and `prominence` are not yet computed for
DOSE-I and require one re-extraction pass that streams raw EEG from a remote Zenodo `data.zip` per
recording (proven reachable — it is exactly how `dosei_features.csv` itself was built) — not a download of
anything new, and not a blocker, but real work that has not been done yet. Everything else (window count,
dose axis, clock alignment, PSD resolution) already clears E242's floors.**

---

## 1. What is cached — asserted by reading each file, not inferred from its name

| file | exists | rows (excl. header) | distinct `recording` | columns |
|---|---|---|---|---|
| `dosei_features.csv` | yes | 10,898 | 39 | `recording,t_s,soc,moaas,propofol,their_sef95,their_pe31,n_finite,critical_slowing_ar1,emg_beta_gamma_fraction,emg_index,emg_kurtosis,exponent_gamma,exponent_high,exponent_low,lempel_ziv,multiscale_entropy_slope,pac_slow_alpha,relative_alpha_power,relative_delta_power,spectral_edge_95,spectral_entropy,whole_head_exponent,bis_rbr,bis_bsr,bis_quazi,bis_sfs,coherence_delta,coherence_theta,coherence_alpha,coherence_beta,wpli_delta,wpli_theta,wpli_alpha_2ch,wpli_beta` |
| `dosei_covariates.csv` | yes | 171 | 171 | `recording,age,sex,height_cm,weight_kg,bmi,asa,chronic_bblocker,chronic_opioids,chronic_neuroleptics,chronic_benzodiazepines,chronic_antiepileptics,cond_ohs,cond_sas,cond_ohe,cond_chf,care_type,endoscopy_type,prop_sum_mg,dose_reconstructed_mg,dose_complete,record_len_s,para` |
| `dosei_dose_events.csv` | yes | 2,095 | 171 | `recording,t_abs_s,dose_mg` |
| `dosei_clock_offsets.csv` | yes | 97 | 97 | `recording,offset_s,matched,n_rows` |
| `dosei_holdout_features.csv` | yes | 18,918 | 62 | same schema as `dosei_features.csv` plus `endoscopy,ecg_hr` |
| `dosei_pEEG.zip` | yes | 171 per-recording CSVs + 1 parameter-description file (174 zip entries incl. 2 directory entries), 28.7 MB | 171 | see §3 — **this is NOT raw EEG** |

`dosei_features.csv` (39 recordings) and `dosei_holdout_features.csv` (62 recordings) are disjoint —
0 overlap — so the two together cover 101 distinct recordings out of the deposit's 171.

## 2. Is there a window-resolution dose axis?

**Yes, and it is already fully built, validated, and cached — no new extraction needed for this part.**

- `dosei_dose_events.csv`: 2,095 bolus events over 171 recordings, all reconstructed from the
  depositor's 1 Hz `Propofol` column (documented in `pEEG_parameter_description.txt` as "administration in
  multiples of 10 mg"). Per-recording event counts, restricted to the **97 recordings this probe certifies
  as usable** (§ below): min 3, median 11, max 28 — none has ≤1 event.
- **Clock alignment is the gate that matters, and it is already solved.** `dosei_features.csv`'s `t_s` is
  elapsed seconds from the first raw EEG sample; `dosei_dose_events.csv`'s `t_abs_s` is seconds since a
  shared de-identified epoch. `dosei_clock_offsets.csv` carries the per-recording offset connecting the
  two, recovered by exhaustive search against the depositor's own four-tuple series
  (`PE31,SEF95,MOAAS,SOC`) and independently checked against the dose column itself
  (`build_dosei_pkpd_inputs.py::check_alignment`, which the build log records as 100% agreement). It
  covers 97 of the 101 recordings that have EEG features at all (39/39 of `dosei_features.csv`, 58/62 of
  `dosei_holdout_features.csv` — missing `10-212, 10-216, 10-219, 10-224`, whose best shift reproduced
  <99% of rows and which the build script itself marks `UNDETERMINED`).
- **`bsde/src/bsde/pkpd/propofol.py` already implements the applicable rung.** DOSE-I is bolus-only — the
  module's own docstring states "DOSE-I records… administration in multiples of 10 mg… so no infusion is
  hiding in it" (168/171 recordings reproduce the deposit's own `PROP_sum` exactly) — so `infusion_basis()`
  does not apply. The applicable functions are `cumulative()` (rung L0, cumulative mg or mg/kg to date) and
  `basis()` (rung L2, the fixed exponential-decay grid, half-lives 0.5–64 min), fed `dose_times_s` /
  `dose_mg` from `dosei_dose_events.csv` and `eval_times_s` = each feature window's `t_s + offset_s`. Both
  produce a genuinely continuous per-window value: `cumulative()` steps up at each bolus and holds;
  `basis()` decays smoothly between boluses, so even a recording with only 3 sparse boluses yields a
  value that varies at every one of its 89–832 windows, not just at the bolus seconds. `weight_kg` (for L0
  per-kg or the allometric L3 rung) is populated for all 171 recordings, range 34–165 kg, 65 distinct
  values — not constant (rule 74).
- **This is compute-only on cached tables.** No S3, no Zenodo fetch, no download is needed to build the
  exposure axis — everything it needs is already sitting in `bsde/results/`.

## 3. Are the peak columns present?

**No — checked directly, not inferred.** `alpha_peak_hz_wide` and `prominence` appear in neither
`dosei_features.csv` nor `dosei_holdout_features.csv`, nor in any other `dosei_*` file in
`bsde/results/` (`dosei_pe_check.csv`, `dosei_pe_variants.csv`, `dosei_sfs_check.csv`,
`dosei_window_control.csv`, `dosei_holdout_comparators.csv` — none carries either column; a
`grep -l "alpha_peak\|prominence" bsde/results/*.csv` matches only VitalDB and Sleep-EDFx files).

**What a recompute costs, checked against the actual pipeline rather than assumed:**

- `dosei_pEEG.zip` is **not raw EEG.** Its 171 per-recording CSVs are the *depositor's own device-derived,
  1 Hz monitor parameters* — verified by reading a sample file (`10-013_pEEG.csv`, 1,590 rows = ~26.5 min
  at 1 Hz): columns are `abs_delta1…abs_gamma, rel_*, sync_*, MF, SEF95, WSMF*, PE31, PE32, SFS, CFS, PFS,
  Intellivue/ECG_HR, Propofol, MOAAS, SOC, Endoscopy` — no `EEG_1`/`EEG_2` waveform column. There is
  nothing to run a PSD on in this file.
- **The raw 2-channel, 125 Hz waveform lives in a separate remote Zenodo object**
  (`https://zenodo.org/records/18483292/files/data.zip?download=1`, 724 MB, never downloaded whole),
  streamed member-by-member (~4 MB compressed per recording) over HTTP Range requests by
  `bsde.ingestion.remote_zip.RemoteZip` — this is the exact mechanism `extract_dosei_features.py` and
  `extract_dosei_sfs.py` already use to build the cached `dosei_features.csv`/`dosei_holdout_features.csv`
  themselves (`raw_two()` reads `Intellivue/EEG_1`/`Intellivue/EEG_2`). **Reachability is therefore already
  proven, not hypothetical** — the very tables in §1 were computed this way.
- Recompute path: `peak_and_prominence(data, sfreq)`, in `bsde/scripts/extract_vitaldb_prominence.py`
  (copied verbatim from `e239_prominence_gated_peak.py`, rule 20), returns `(alpha_peak_hz_wide,
  prominence)` from one `_mean_psd` call per window and needs no new implementation — only a DOSE-I
  extraction script analogous to the existing `extract_dosei_features.py` / `extract_vitaldb_prominence.py`
  / `extract_sleep_edfx_prominence.py`, wired to stream the same 97–101 recordings already used for the
  other DOSE-I features. Cost: one RemoteZip pass per recording, same order of magnitude as the extraction
  that already produced `dosei_features.csv`/`dosei_holdout_features.csv` (101 recordings, 615–4,250 s
  each, median duration 1,439 s / ~24 min) — a re-run, not a new capability.

## 4. The binding constraint: window length and PSD bin width

- DOSE-I's window is `WINDOW_S = 30.0` s (`extract_dosei_features.py`), stride 5 s, sampling 125 Hz —
  Nyquist 62.5 Hz, comfortably above the 5–15 Hz peak-search band.
- **The PSD itself is not estimated over the full 30 s window at once.** Every spectral candidate,
  including the shipped `peak_and_prominence`, goes through `bsde.features.aperiodic.welch_psd` via
  `bsde.candidates.seed._mean_psd`, whose **default `window_s = 4.0` s** is used unchanged by both the
  DOSE-I extraction and by `extract_vitaldb_prominence.py` — no override in either. Welch bin width is
  `1 / window_s`, independent of sampling rate, so DOSE-I's bins are **0.25 Hz — identical to VitalDB's
  measured 0.25 Hz (E237).** There is no resolution mismatch to state or correct for; a DOSE-I recompute
  would be estimated at the same frequency granularity as the deposit E242 already used.

## 5. Explicit answer

**Yes — a within-recording peak-frequency-versus-propofol-exposure correlation can be computed on
DOSE-I**, on **97 recordings** (39 from `dosei_features.csv` + 58 from `dosei_holdout_features.csv`,
excluding the 4 recordings whose clock offset could not be determined at ≥99% agreement), each carrying
**89–832 EEG windows** (min 89, p25 187, median 266, p75 361, max 832 — every one clears E242's floor of
10 by a wide margin) and **3–28 dose events** (median 11) from which a continuously varying exposure value
(cumulative dose or PK-decay Ce) is computable at every window via code already in the repo. Of the 97,
0 carry the `PARA` extravasation exclusion E122 uses, and 3 have `dose_complete = 0` (reconstructed dose
does not match the deposit's own `PROP_sum` exactly) — a defensible further exclusion leaving 94, still
far above E242's 20-cases-per-arm floor.

**What stands between "feasible" and "run":** `alpha_peak_hz_wide` and `prominence` do not exist yet for
DOSE-I and must be computed by streaming the raw 125 Hz waveform from the remote `data.zip` through the
already-written `peak_and_prominence` function — the same operation, on the same 97–101 recordings, that
already produced every other DOSE-I feature in `bsde/results/`. This is real, non-trivial work (a
RemoteZip pass per recording) but it is a re-run of a proven pipeline, not a new capability, and needs no
new download beyond what building `dosei_features.csv` already required.

## Citation check (rule 25/39 — verified via NCBI E-utilities `esummary`, not WebFetch)

PMID 18431119, queried directly against `eutils.ncbi.nlm.nih.gov`: Hayashi K, Sawa T, Matsuura M.
"Anesthesia depth-dependent features of electroencephalographic bicoherence spectrum during sevoflurane
anesthesia." *Anesthesiology* 2008;108(5):841-50. doi:10.1097/ALN.0b013e31816bbd9b. Author list, journal,
year, volume/issue/pages match the citation already used in `e242_cross_arm_matched.py`'s docstring; this
probe did not re-derive or re-check the specific frequency numbers (11.0→9.8→8.7 Hz) quoted there, which
predate this probe and were not touched by it.
