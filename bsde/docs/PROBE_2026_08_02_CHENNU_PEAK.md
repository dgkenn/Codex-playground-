# Feasibility probe — can Chennu propofol replicate E242's propofol-half claim?

*2026-08-02. Coverage/capability check only (catalogue rule 41), run BEFORE any registration. No
candidate was correlated with any dose or state label. No file under `bsde/src/bsde/experiments/` or
`bsde/governance/` was touched. No ledger row was written.*

**VERDICT, first: NOT FEASIBLE on the cached tables, and NOT FEASIBLE to make feasible from this
sandbox. Binding constraint: the deposit stores one row per recording (one feature value per
subject-per-sedation-level, 4 points per subject), not per-window, so there is no within-subject
*window* series to correlate against dose — and a recompute at higher time resolution requires
`api.repository.cam.ac.uk`, which is confirmed unreachable from here (Q20, and reconfirmed live
today).**

---

## 1. What is cached

`bsde/results/` contains, asserted by direct read, not inferred from filenames:

| file | rows (data, excl. header) | n subjects | status |
|---|---|---|---|
| `chennu_features.csv` (v1) | 80 | 20 | all `ok` |
| `chennu_features_v2.csv` | 80 | 20 | all `ok` |
| `chennu_features_v3.csv` | 80 | 20 | all `ok` |
| `chennu_labels.csv` | 80 (+ 8 comment lines) | 20 | — |

All three feature tables are keyed `recording_id` and have **exactly 4 rows per subject** (20 subjects
× 4 sedation levels = 80; verified by `uniq -c` on the `subject` column). **One row = one recording =
one sedation level for one subject** — there is no per-window or per-epoch table.

Columns (v3, the richest): `recording_id, dataset, subject, status, error, n_channels, sfreq,
n_samples, meta_sedation_level, meta_plasma_propofol_ug_per_L, meta_mean_reaction_time_ms,
meta_n_correct_of_40, critical_slowing_ar1, emg_beta_gamma_fraction, emg_index, emg_kurtosis,
exponent_high, exponent_low, lempel_ziv, multiscale_entropy_slope, pac_slow_alpha,
relative_alpha_power, relative_delta_power, spatial_participation_ratio, spectral_edge_95,
spectral_entropy, uce_v1, whole_head_exponent, wpli_alpha`.

`n_channels=91`, `sfreq=250`, `n_samples=10000` (constant across all 80 rows — 10,000/250 = 40 s of
data actually read per recording, not the deposit's full ~7 minutes; see §3). v1 additionally carries
`meta_n_epochs_used`, constant at **4** across all 80 rows — no all-NaN or constant-but-informative
columns found beyond this declared constant, which the adapter's docstring explains (see §3).

## 2. Is there a graded propofol exposure, and is it a dose or a response?

`chennu_labels.csv`'s own header comment (quoted verbatim):

> `# sedation_level: 1 = baseline, 2 = mild sedation, 3 = moderate sedation, 4 = recovery`
> `# plasma_propofol_ug_per_L: concentration of propofol MEASURED IN BLOOD PLASMA at that level`
> `# NONE of these is scored from the EEG -- contrast with Sleep-EDF (MASTER_PLAN section 9.6).`

`MASTER_PLAN.md` §9.8 confirms independently: *"propofol concentration MEASURED IN BLOOD PLASMA
(µg/L)... None of these is scored from the EEG."*

This **is a dose** (a measured exposure), not a response/sedation-score in the sense rule 86 warns
about — it is a blood assay, not a co-measured bedside observation. It does vary within subject and is
**not monotonic with sedation level**: subject `02`'s four values are 0, 204, 506, 299 µg/L (level 4,
"recovery," sits between levels 2 and 3, not above them); subject `03`'s are 0, 246, 689, 224. So dose
genuinely varies across a subject's 4 recordings, in the units E242 needs.

**But the graded variable exists at exactly 4 distinct values per subject** — one per recording — not
as a continuum sampled many times. `meta_sedation_level` is an ordinal category (1–4) and
`meta_plasma_propofol_ug_per_L` is the one continuous dose readout; both are recording-level constants,
not window-level.

## 3. Are `alpha_peak_hz_wide` and `prominence` present?

**No.** Grepped every `chennu_*` file in `bsde/results/` and the ingestion/extraction code: neither
column name appears anywhere in `chennu_features.csv`, `_v2`, `_v3`, or `chennu_irreversibility.s{0-3}.csv`.
Those two columns exist only for `vitaldb_prominence.s*.csv`, `sleep_edfx_prominence.csv`,
`ds006695_features.csv` and the experiments built on them (`e233`, `e239`, `e241`, `e242`, `e235`,
`e236`, `e237`, `e218`, `e131`) — never for chennu. Confirmed by filename, not assumed from naming.

**What a recompute would cost, and what stops it:**

- The adapter (`bsde/src/bsde/ingestion/chennu.py`) streams `.set`/`.fdt` EEGLAB pairs directly out of a
  **3.69 GB remote ZIP** at `api.repository.cam.ac.uk/server/api/core/bitstreams/e94a6722-.../content`
  via HTTP range requests — no full download, no auth. Deposit: 20 subjects × 4 conditions, **~7
  minutes per recording**, 91 channels, 0.5–45 Hz filtered, 10 s epochs, average-referenced.
- **The cached tables only ever read the first 4 of those ~42 possible 10 s epochs per recording**
  (`n_epochs: int = 4` default in `chennu.py`, docstring: *"the `.fdt` layout is column-major... so the
  FIRST `n_epochs` epochs are a contiguous PREFIX of the file... that is what makes reading a handful of
  epochs out of a large member cheap"*). So even the existing extraction is a 40 s prefix per
  recording, not the full ~7 minutes, and the code aggregates that prefix into **one row**, not one row
  per epoch.
- **Access is currently blocked from this sandbox.** `docs/QUEUE.md` Q20 (2026-07-31), quoted verbatim:
  *"`api.repository.cam.ac.uk` fails TLS with 'Hostname mismatch, certificate is not valid for
  api.repository.cam.ac.uk' under both `curl --cacert /root/.ccr/ca-bundle.crt` and Python with
  `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` set. It is host-specific, not a proxy misconfiguration... So the
  existing `chennu_features_v3.csv` cannot be regenerated in this sandbox."* Re-tested live today
  (2026-08-02): `curl --cacert /root/.ccr/ca-bundle.crt https://api.repository.cam.ac.uk/...` through the
  proxy completes the CONNECT tunnel and TLS ClientHello, then **hangs to timeout (15 s)** rather than
  completing the handshake — a different symptom (timeout vs. immediate cert-mismatch) but the same
  practical outcome: **unreachable from this sandbox, now as in Q20.**
- Even granting access, recomputing per-epoch peak/prominence at all 42 available epochs (rather than
  the current 4) would still leave only **4 distinct dose values per subject** — see §4 — so it would
  not by itself solve the within-subject correlation's real limitation.

## 4. Windows per subject

**Not 10+; there is no within-level window series at all in the cached tables.** Each subject
contributes exactly **4 data points**, one per sedation level, each already a single aggregated feature
value over a 40 s prefix. A within-subject Spearman(peak, dose) computed on the cached tables would be
a correlation over **n = 4 points, one of which (level 4 / recovery) is often not monotonically ordered
in dose relative to level 3** (§2) — this is a rank correlation with 4! = 24 possible orderings, so its
own resolution is extremely coarse (E208, which already ran a within-subject design on this exact
deposit for a different outcome, treats subjects as the unit precisely because of this: "Twenty
subjects each contribute four levels, so rows are nested and the effective n is 20, not 80" — and that
was for predicting the ordinal sedation level, not for a peak-vs-continuous-dose correlation, which is
a harder target with the same n).

Recomputing more epochs per recording (up to ~42 rather than 4) would raise the *window* count within
each of the 4 levels, but would not raise the number of **distinct dose values** above 4 per subject —
plasma propofol concentration was measured once per level, not continuously. So even an unblocked
recompute caps the within-subject dose-correlation design at 4 distinct x-values per subject, an order
of magnitude below E242's own floor of "at least 10 windows per case after restriction" (E242 G2).

## 5. The killer question

**Can a within-subject peak-vs-DOSE correlation be computed on this deposit at all, and at what n?**

**No, not at anything resembling E242's design.** Two independent, compounding reasons:

1. The cached tables (the only thing accessible right now) have **no peak/prominence columns**, and
   recomputing them requires re-running the chennu adapter against a host that is **currently
   unreachable from this sandbox** (confirmed both in `docs/QUEUE.md` Q20 and by a fresh connection
   attempt today).
2. Even if that access were restored, the deposit's own design caps the within-subject dose axis at
   **4 distinct values per subject** (one per sedation level) — nowhere near E242's "≥10 windows per
   case" floor, and Spearman over 4 points is not a design any gate in this project's catalogue would
   license (rule 46/85: a statistic with this few achievable values cannot be resolved by more
   replicates, because the granularity is in the data, not the estimator).

---

## Verdict

**NOT FEASIBLE.**

**Binding constraint:** Chennu ships one aggregated feature row per (subject × sedation level) — never
per window — so there are only 4 distinct dose observations per subject regardless of extraction
effort, and the columns E242 needs (`alpha_peak_hz_wide`, `prominence`) do not exist in any cached
table and cannot currently be computed at all, because the only source (`api.repository.cam.ac.uk`) is
unreachable from this sandbox (re-verified today, consistent with `docs/QUEUE.md` Q20). Both
constraints are independently fatal; either alone would already make this infeasible as a within-subject
peak-versus-dose replication of E242's propofol-half claim.
