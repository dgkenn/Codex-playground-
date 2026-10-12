# Feasibility probe — does ANY fully public deposit satisfy Challenge A's three requirements? (2026-08-02)

**This is a PROBE, not a registration.** No candidate is correlated against any state label here (rule 41).
Every number below was read from a file on disk or a live HTTP response, printed before being interpreted
(rule 5), and every access claim is a verbatim quote from a fetched page, not a recollection.

## The question

Challenge A (`bsde/governance/CHALLENGES.json`, verbatim): *"predicts loss and recovery across anaesthetics
while MINIMISING drug-identification information."* Under today's constraint (`DECISIONS_2026_08_02_LINES_
AND_BLOCKERS.md`, "CONSTRAINT REVISED AGAIN, 2026-08-02: fully public data only" — *"a URL that returns data
today, with no application, committee, custodian, DUA, credentialed tier or email to anyone"*), which fully
public deposit has ALL THREE of:

- **(a)** at least two different anaesthetic agents
- **(b)** LOSS **and** RECOVERY, not just one transition or a steady state
- **(c)** a state label that is not derived from a processed EEG monitor

## Prior work found and reused, not duplicated

`DEPOSIT_ACCESS_STATUS.md` (committed 2026-08-01, file `Modify` timestamp confirmed by `stat`) already built
a five-cohort version of this exact table and concluded **"No row has three ticks."** That table predates
today's "fully public only" constraint, so its best-scoring row (MGH volunteers via `eeg-power-anesthesia`,
three ticks on paper) is not actually usable under today's rule — confirmed below. `DECISIONS_2026_08_02_
LINES_AND_BLOCKERS.md` records the constraint change and states *"A probe is running to find whether ANY
fully public deposit has two agents, both transitions, and a non-monitor state label. If it returns none,
Challenge A is blocked on public data and stops."* This probe is that probe, run independently against the
files rather than trusted from the prior document's prose.

---

## 1. DOSE-I — `bsde/results/dosei_*.csv`

**n = 39 recordings** (`dosei_features.csv`, `moaas` column populated in all 39 — printed, not assumed).

**(c) State label — YES.** `moaas` is MOAA/S (Modified Observer's Assessment of Alertness/Sedation), a
behavioural responsiveness scale, 1 (unresponsive) to 5 (fully awake). Verified directly:

```
38 of 39 recordings show a MOAA/S trough (loss then partial/full recovery,
min<=2, min not at endpoints, start>=4, end>=3)
```

**(b) Loss AND recovery — YES**, and stronger than that trough check alone shows. `LITERATURE_MAP.md` records
the deposit's own count: **"1,129 annotated LOC/ROC transitions, 125 Hz EEG, MOAA/S depth labels."**

**(a) Two agents — NO.** `dosei_covariates.csv` carries only `prop_sum_mg` / `dose_reconstructed_mg`;
`dosei_dose_events.csv` has no drug-identity column (`recording, t_abs_s, dose_mg` — one drug implied
throughout). `DEPOSIT_ACCESS_STATUS.md` and `DATA_REQUEST_TURKU_KALLIONPAA.md` both independently record it
as propofol-only bolus, endoscopy suite. No second agent found anywhere in the shipped tables.

**Access — fully public.** `DATASET_REGISTRY.csv` / `LITERATURE_MAP.md`: Zenodo record **18483292**, "Open,
CC-BY-4.0." No DUA.

**Verdict: fails (a) only.** Best behavioural-label deposit in the project; wrong axis (dose depth within one
drug, not drug identity).

---

## 2. Krause / Banks (`zenodo_krause_dexpro`) — `bsde/results/krause_dexprosleep_allData.csv`

**n = 4,810,414 bytes, 12,313 rows, 34 unique `patientID` values** (printed from the file). Label counts:
`N2 4519, WS 4456, R 1429, N1 713, N3 645, U 129, WA 119, S_dex 111, S 77, U_dex 66, WA_dex 49`.

Patient-level partition (computed directly, not copied from the registry):

```
Propofol-only (S/U/WA, no dex):        19 patients
Dex-only (S_dex/U_dex/WA_dex):         10 patients
BOTH propofol AND dex labels:           0 patients
Sleep-only (no drug labels at all):     5 patients
Total: 34
```

This matches `DATASET_REGISTRY.csv`'s independently-recorded **"29 with a wake/unresponsive contrast … 0
patients shared between drug arms."**

**(a) Two agents — YES.** Propofol (19 patients) and dexmedetomidine (10 patients), non-overlapping.

**(c) State label — YES.** `WA`/`S`/`U` (and the `_dex` variants) are rater-assigned unresponsiveness labels,
not a monitor index — confirmed by `DATASET_REGISTRY.csv`'s `behavioral_exams` field: *"unresponsiveness as
labelled by the depositors."*

**(b) Loss AND recovery — NO.** The within-patient drug-label sequence was extracted and ordered by
`refTime` for every drug patient. It is monotone `WA → S → U` (or `WA_dex → S_dex → U_dex`) with **no return
to WA** in 28 of 29 drug patients — e.g.:

```
372L drug-label sequence: ['WA', 'S', 'U']
403L drug-label sequence: ['WA', 'S', 'U']
457B drug-label sequence: ['WA_dex', 'S_dex', 'U_dex']
```

The one apparent exception, **625L**, ends `S_dex → U_dex → WA_dex`. Checked against `refTime`, the `WA_dex`
block sits **≈4.0 `refTime` units after** the `U_dex` block (13.79 → 17.76), versus the ≈0.02–0.05-unit
spacing of every genuine within-episode transition in the table (e.g. 372L's `WA`→`S`→`U` spans 0.039 units
total). That gap is consistent with a separate day or session, not recovery from the same unresponsive
episode, and the literature note in `LITERATURE_MAP.md` agrees independently: *"which separates state from
concentration in a way the Krause deposit structurally cannot"* (LOR-vs-ROR). Treated as **no recovery**.

**Access — fully public.** `LICENSE_TABLE.csv`: Zenodo record 15497531, **"OPEN - public; VERIFIED"**, BSD-3
at record level (data terms unstated but access itself is unrestricted — no DUA, no login).

**Verdict: fails (b) only.** The only deposit here with two mechanistically distinct agents in a
non-overlapping within-cohort design, and it stops at loss.

---

## 3. OpenNeuro ds004541 — `bsde/results/ds004541_v2.csv`, `ds004541_loc.csv`

**n = 8 subjects, 125 rows** (`ds004541_v2.csv`, printed). `meta_phase` distribution:

```
pre_loc 42, post_loc 42, awake_pre_drug 24, pre_roc 7, post_roc 7, baseline 3
```

Subjects with `meta_loc_s` populated: **7 of 8**. Subjects with `meta_roc_s` populated: **7 of 8**, the same
seven (`sub-02, 03, 04, 07, 08, 09, 10`; `sub-11` has neither).

**(b) Loss AND recovery — YES.** The ingestion adapter's own docstring
(`bsde/src/bsde/ingestion/ds004541.py`) states: *"ds004541 carries explicit `loc` and `roc` events — loss and
recovery of consciousness, marked per subject against a graded stimulation ladder (`verbal/soft`,
`verbal/strong`, …)."*

**(c) State label — YES.** The loc/roc marks are behavioural (a graded stimulation/response ladder), not an
EEG monitor index.

**(a) Two agents — NO.** Every project document describing this deposit calls it a single-agent propofol
induction study (`PROBE_2026_08_02_SEPARABILITY.md`: *"propofol induction"*; `DATA_SEARCH_2026_08_02_
CROSSOVER.md`: *"single-agent (propofol only …)"*). No second-agent column exists in the extracted table.

**Access — fully public.** OpenNeuro dataset, no DUA, no account required (platform-wide policy; also
confirmed by this project already having streamed it without credentials).

**Verdict: fails (a) only.** n = 7 with both loc and roc — small, but structurally the same shape of gap as
DOSE-I: right design, wrong axis (one agent).

---

## 4. OpenNeuro ds005620 — `bsde/results/ds005620_full.csv`

**n = 21 subjects, 202 recordings.** `meta_task` distribution: `sed 92, awake 59, sed2 51`. All 21 subjects
have `awake`; 20 of 21 have both `sed` and `sed2` (`sub-1037` has only `awake`).

**(a) Two agents — NO.** `LITERATURE_MAP.md`/`MASTER_PLAN.md`/`QUEUE.md` all independently record this as
propofol-only (*"ds005620 and Chennu are propofol only"*; *"ds005620 is propofol only, so it does nothing
for Q9's two-agent problem"*).

**(b) Loss and recovery — PARTIAL, and not usable as shipped.** The design is described as a "repeated
awakening" protocol (subject sedated, then repeatedly awakened), which is the right *shape*, but the public
task labels (`awake` / `sed` / `sed2`) encode two nominal sedation depths, not a per-awakening event marker.
`MASTER_PLAN.md` §1 row 6, verified by a complete S3 key enumeration, states plainly: *"The experience
reports are not in the public deposit … Zero files match dream/experience/report/beh/questionnaire/rating/
subjective."* `events.tsv` holds only BrainVision `New Segment` boilerplate — no LOC/ROC-equivalent markers
at all.

**(c) State label — NO, as shipped.** `awake`/`sed`/`sed2` are protocol-assigned target depths, not a scored
behavioural response, and there is no monitor index either — but there is also no graded behavioural score in
the public files, so it cannot be scored as YES on (c) as things stand.

**Access — fully public.** OpenNeuro, CC-BY-4.0, no DUA (`DATASET_REGISTRY.csv`: *"OPEN - public;
VERIFIED"*). BrainVision format, already ingested.

**Verdict: fails (a); (b) and (c) are not usable as shipped regardless.**

---

## 5. VitalDB — `bsde/results/vitaldb_grid.s0-3.csv`

**n = 6,679 windows across 4 shards** (printed). `meta_agents_present` distribution (top 7):

```
sevoflurane 1931, propofol|sevoflurane 1546, propofol 1187, desflurane|propofol 987,
desflurane|sevoflurane 518, desflurane 378, desflurane|propofol|sevoflurane 132
```

**(a) Two agents — YES, and the strongest of any cohort here**: propofol, sevoflurane and desflurane in
single- and multi-agent combinations.

**(c) State label — NO.** The only state-like column is `meta_bis`, the commercial BIS index — computed
from the EEG itself, which is exactly the kind of label criterion (c) excludes. `meta_bis` is missing/NaN in
**834 of 6,679 rows (12.5 %)**, and where present it is still monitor-derived, not behavioural.

**(b) Loss AND recovery — NO.** `DEPOSIT_ACCESS_STATUS.md`'s prior measurement (re-quoted here because it
is auditable and load-bearing, not re-derived, since the header alone establishes the columns exist for the
claim to be checked): *"across 6,437 windows from 250 cases, ZERO fall before anaesthesia start"* and *"only
103 post-`aneend` across all 250 cases."* No awake-baseline (loss) window exists at all, so even the 103
post-emergence windows cannot anchor a within-subject loss-and-recovery pair.

**Access — fully public.** `vitaldb.net` / AWS Open Data, no DUA (`DATASET_REGISTRY.csv`: *"OPEN - VERIFIED
in prior project work"*).

**Verdict: fails (b) and (c).** Best agent contrast of any deposit checked; cannot supply the state label or
the loss side of the transition.

---

## 6. PhysioNet cohorts checked and DISQUALIFIED ON ACCESS (not merely scored — verified live)

Each fetched today with `curl`, following redirects, quoting the page directly:

| project | HTTP | verbatim access text |
|---|---|---|
| `eeg-gaba-anesthesia/1.0.0/` | 200 | `badge-warning "Restricted Access"`; *"Only credentialed users who sign the DUA can access the files. In addition, users must have individual studies reviewed by the contributor."* |
| `multimodal-surgery-anesthesia/1.0/` | 200 | `badge-warning "Restricted Access"`; *"Only registered users who sign the specified data use agreement can access the files."* |
| `propofol-anesthesia-dynamics/1.0/` | 200 | `badge-success "Open Access"`, but still requires signing the **"PhysioNet Contributor Review Health Data Use Agreement 1.5.0"** — a DUA regardless of badge colour. Moot anyway: per `DEPOSIT_ACCESS_STATUS.md` it has **no EEG** (autonomic/HRV/EDA only via a button-press task). |

`eeg-power-anesthesia` (the MGH-volunteer deposit that scored best on paper in `DEPOSIT_ACCESS_STATUS.md`,
with behavioural LOC/ROC in 10 volunteers) was independently re-confirmed the same way:

```
badge-warning "Restricted Access"
"Only registered users who sign the specified data use agreement can access the files."
```

Under today's constraint (*"no application, committee, custodian, DUA, credentialed tier or email"*), all
four are **out of scope**, which is exactly what `DECISIONS_2026_08_02_LINES_AND_BLOCKERS.md` already
concluded (*"PhysioNet credentialed and restricted tiers go out of scope too, which removes
`eeg-power-anesthesia` from consideration"*) — reconfirmed here by re-fetching each page rather than trusting
the prior note.

---

## 7. Everything else fully public, searched for a substitute

**OpenNeuro, exhaustive keyword survey** (`bsde/results/openneuro_eeg_survey.json`, read and its counts
printed, not re-crawled from scratch — re-running a 1,834-dataset GraphQL crawl was judged not worth
repeating for a probe when the file is on disk, dated, and its methodology is auditable: field-level GraphQL
queries, never a WebFetch summary, per rule 39):

```
scanned: 1834
eeg_or_ieeg: 517
hits: 36
```

The 36 keyword hits were printed in full; the only three anaesthesia-relevant ones are `ds005620`, `ds004541`
(both already covered above) and `ds003380` — re-checked today via `PROBE_2026_08_02_DEPOSITS.md`'s more
recent, independent pass and found to be **"a pig model,"** single subject, single agent (isoflurane): not a
candidate on species or design grounds, let alone the agent count. None of the 36 is a disorders-of-
consciousness cohort, and no dataset in the list carries two agents.

Live connectivity to OpenNeuro's GraphQL API was independently confirmed (`{"data":{"datasets":{"edges":
[{"node":{"id":"ds000001"}}]}}}`), so the prior survey's premise (the API is reachable and enumerable) still
holds; its `search` field returns `null` for arbitrary text queries in this API version, so a live full-text
spot-check beyond the field-level crawl already on disk was not obtainable within this probe's scope — noted
as a limitation, not papered over.

**Two sleep-depth deposits found today for an unrelated purpose** (`capslpdb`, `ds006695`, both surfaced by
`PROBE_2026_08_02_DEPOSITS.md` for Challenge C's normative-reference work) carry **no drug-identity label at
all** — they are single-condition sleep-staging cohorts — and are not candidates for Challenge A regardless
of their access status.

---

## The table

| deposit | (a) ≥2 agents | (b) loss AND recovery | (c) non-monitor state label | access |
|---|---|---|---|---|
| **DOSE-I** (Zenodo 18483292) | **NO** — propofol bolus only | **YES** — 1,129 annotated LOC/ROC transitions; 38/39 recordings show a MOAA/S trough | **YES** — MOAA/S, behavioural | fully public |
| **Krause/Banks** (Zenodo 15497531) | **YES** — 19 propofol / 10 dexmedetomidine, 0 shared patients | **NO** — monotone WA→S→U in 28/29 drug patients; sole exception separated by a ~100× larger time gap than any real transition | **YES** — rater-assigned WA/S/U | fully public |
| **ds004541** (OpenNeuro) | **NO** — propofol induction only | **YES** — explicit `loc`/`roc` events, graded stimulation ladder, n=7/8 subjects with both | **YES** — behavioural response ladder | fully public |
| **ds005620** (OpenNeuro) | **NO** — propofol only | **PARTIAL** — repeated-awakening design, but no per-awakening marker in the public files | **NO as shipped** — `awake`/`sed`/`sed2` are protocol depths, not a score | fully public |
| **VitalDB** | **YES** — propofol/sevoflurane/desflurane, 6,679 windows | **NO** — 0/250 cases have an awake/pre-induction window; 103/6,679 windows post-emergence | **NO** — only `meta_bis`, EEG-derived | fully public |
| `eeg-power-anesthesia` (MGH volunteers) | NO — one agent | YES — 10 volunteers, behavioural LOC+ROC | YES | **DISQUALIFIED — Restricted Access, DUA required** (re-verified live) |
| `multimodal-surgery-anesthesia` (MGH OR) | weak (propofol vs propofol+sevo, between-case) | NO | documented rule, not a scale | **DISQUALIFIED — Restricted Access, DUA required** |
| `eeg-gaba-anesthesia` | n/a | n/a | n/a | **DISQUALIFIED — Restricted Access, DUA + contributor review** |
| `propofol-anesthesia-dynamics` | n/a | YES (LOC_ROC.csv) | YES | **No EEG at all** (autonomic only); also requires a signed DUA despite "Open Access" badge |
| `ds003380` | NO — one agent, and a pig | n/a | n/a | fully public but not a human/multi-agent candidate |

**No row has three ticks.** Every fully public deposit reachable from this project satisfies at most two of
the three criteria, and each of the three possible pairs is represented by a different deposit — DOSE-I and
ds004541 have (b)+(c) but not (a); Krause has (a)+(c) but not (b); VitalDB has (a) alone.

## Verdict

**Confirmed absence: no fully public deposit reachable from this project has two anaesthetic agents, both
loss and recovery, and a non-EEG-monitor state label, in the same subjects.** The best available options are
purpose-specific, not general-purpose, substitutes:

- If the design needs (b)+(c) and is willing to give up (a): **DOSE-I** or **ds004541** (both propofol-only,
  behaviourally labelled, both transitions present).
- If the design needs (a)+(c) and is willing to give up (b): **Krause/Banks** (two agents, behavioural
  labels, loss only).
- No deposit supports (a)+(b) at all on public data.

**Challenge A, as briefed — predicting loss and recovery across multiple anaesthetics while minimising
drug-identification information, validated against a non-EEG-monitor label — cannot be run on fully public
data as a single-deposit design.** This is the same conclusion `DECISIONS_2026_08_02_LINES_AND_BLOCKERS.md`
anticipated pending this probe, now independently confirmed against the files rather than assumed. The two
routes that remain open are (i) a cross-deposit design that trains loss/recovery tracking on the (b)+(c)
cohorts (DOSE-I, ds004541) and tests drug-identifiability leakage on the (a)+(c) cohort (Krause) — three
different populations, not a within-subject test, and a real design choice to register explicitly rather than
discover after the fact — or (ii) the previously-drafted formal-access requests (Turku/Kallionpää,
`DATA_REQUEST_TURKU_KALLIONPAA.md`) if the "fully public only" constraint is ever relaxed again.

---

## OPUS VERIFICATION — one cell is IN DOUBT and it is the decisive one

The probe's table is thorough and I accept it except for a single cell: **Krause, criterion (b) loss and
recovery**, reported NO on the grounds that 28 of 29 drug patients show a monotone WA→S→U sequence.

**That cell decides Challenge A.** Krause already satisfies (a) two agents and (c) a rater-scored,
non-monitor label. If it also had recovery it would satisfy all three, and the challenge would be
runnable on fully public data rather than blocked.

**My spot-check pointed the other way and could not be resolved.** Over
`bsde/results/krause_dexprosleep_allData.csv` (12,313 rows), grouping by `patientID` and looking for a
state sequence that leaves `U` after entering it, **13 of 34 subjects return from U**. That does not
refute the probe: the deposit is `dexprosleep` — dexmedetomidine, propofol AND sleep — and sleep subjects
would legitimately cycle out of unresponsiveness. The probe's claim was about DRUG patients only.

**I could not separate them.** That file has no drug or condition column — `cols` are `label`, `refTime`,
`patientID`, and feature columns. The probe located the 19-propofol / 10-dexmedetomidine assignment
somewhere else, and I ran out of room to find it.

**So Challenge A is NOT being stopped on this evidence.** The pre-commitment was to stop if no public
deposit has all three criteria; that conclusion currently rests on one cell that my own check questioned.
Resolving it needs one focused task: find the per-patient drug assignment for the Krause deposit, split
the 34 subjects into drug versus sleep, and report the recovery count **within the drug patients only**.
If they are monotone, Challenge A stops as planned. If any meaningful number of drug patients recover
from U, Krause satisfies all three criteria and Challenge A is runnable on public data.

**Recorded rather than resolved, deliberately** — announcing a stop on an unverified cell would be worse
than leaving it open, and the catalogue has four entries about verdicts that turned on a number nobody
checked.

---

## RESOLUTION, 2026-08-02 — the doubtful cell is resolved: NO, Krause does not have recovery among drug patients

**Task:** find the per-patient drug assignment, split 34 patients into propofol/dex/sleep, count recovery
among drug patients only, and audit the time gaps for any apparent recoverer rather than inherit the prior
judgement on 625L. No feature was correlated with anything.

### 1. Where the drug assignment lives

**There is no separate drug-assignment file, column, sidecar or manifest anywhere in the repo.** Checked
and empty: `grep -rl -i "krause\|dexpro" bsde/results/*.json` (three JSON files found, none a
patient-to-drug map — `e154_lambda_mgh_or.json`, `e139_challenge_a_single_statistic.json`,
`e141_family_split_quality_audit_v2.json`, all downstream analysis outputs, not source metadata);
`find / -iname "*krause*" -o -iname "*15497531*"` returns only
`bsde/results/krause_dexprosleep_allData.csv` itself; `/tmp/eeg_probe/` (checked, exists, populated with
unrelated cached tables) has nothing Krause-related; `bsde/scripts/` has no `*krause*`/`*dexpro*` file.

**The assignment is encoded in the `label` column's naming convention itself**, and is used exactly this
way (uncredited to a lookup table) by `bsde/src/bsde/experiments/e35_challenge_a_drug_probe.py`, whose
docstring states verbatim: *"34 patients, block-level OAA/S. Propofol `WA`/`S`/`U` at 119/77/129 rows over
19 patients; dexmedetomidine `WA_dex`/`S_dex`/`U_dex` at 49/111/66 over 10; natural sleep
`WS`/`N1`/`N2`/`N3`/`R` over 24."** That is:

- **Source file:** `bsde/results/krause_dexprosleep_allData.csv` (n = 12,313 rows, 34 unique `patientID`,
  confirmed by direct read before any claim below).
- **Source column:** `label` (values: `N2, WS, R, N1, N3, U, WA, S_dex, S, U_dex, WA_dex` — printed counts
  below reproduce e35's docstring exactly).
- **Assignment rule** (the naming convention, not a lookup): a patient is **propofol** if any of their rows
  carry `WA`/`S`/`U`; **dexmedetomidine** if any carry `WA_dex`/`S_dex`/`U_dex`; **sleep-only** if none of
  the above and only `WS`/`N1`/`N2`/`N3`/`R` appear.

Verified directly on the file (not copied from e35's docstring):

```
n rows = 12313
n unique patientID = 34
Counter(label) = {'N2': 4519, 'WS': 4456, 'R': 1429, 'N1': 713, 'N3': 645, 'U': 129, 'WA': 119,
                   'S_dex': 111, 'S': 77, 'U_dex': 66, 'WA_dex': 49}
```

This exactly reproduces the label counts quoted in the original probe row 2 (verbatim: *"N2 4519, WS 4456,
R 1429, N1 713, N3 645, U 129, WA 119, S_dex 111, S 77, U_dex 66, WA_dex 49"*) — so the deposit has not
changed between the probe and this check.

### 2. Three-way split (n = 34, printed before interpretation)

```
propofol_only: 19  -> 372L, 376R, 384B, 394R, 399R, 400L, 403L, 405L, 409L, 413R, 418R, 423L, 514L,
                       567R, 585L, 634L, 640L, 672R, 741L
dex_only:      10  -> 439B, 456R, 457B, 458R, 460L, 525L, 559R, 625L, 720R, 728R
both_drugs:     0  -> (none)
sleep_only:     5  -> 369R, 524R, 532R, 717R, 764R
total = 34
```

**Reconciles exactly** with the probe's reported 19 propofol + 10 dexmedetomidine, 0 shared. It also
reconciles with `DATASET_REGISTRY.csv`'s independent count quoted in the probe ("29 with a wake/unresponsive
contrast … 0 patients shared between drug arms" — 19+10 = 29). No forcing was needed; the split fell out of
the label convention cleanly on the first pass.

### 3. Recovery among the 29 drug patients (block sequence, ordered by `refTime`, drug-arm labels only)

Consecutive duplicate labels collapsed to blocks; sleep labels excluded from the drug-arm sequence (a
patient's `WA`/`S`/`U` — or `WA_dex`/`S_dex`/`U_dex` — rows only, in time order):

```
372L (prop): WA, S, U               376R (prop): WA, S, U               384B (prop): WA, U
394R (prop): WA, S, U               399R (prop): WA, S, U               400L (prop): WA, S, U
403L (prop): WA, S, U               405L (prop): WA, S, U               409L (prop): WA, S, U
413R (prop): WA, S, U               418R (prop): WA, S, U               423L (prop): WA, S, U
514L (prop): WA, U                  567R (prop): WA, U                  585L (prop): WA, U
634L (prop): WA, S, U               640L (prop): WA, S, U               672R (prop): WA, S, U
741L (prop): WA, S, U
439B (dex):  WA_dex, S_dex, U_dex   456R (dex):  WA_dex, S_dex          457B (dex):  WA_dex, S_dex, U_dex
458R (dex):  WA_dex, S_dex, U_dex   460L (dex):  WA_dex, S_dex          525L (dex):  WA_dex, S_dex, U_dex
559R (dex):  WA_dex, S_dex, U_dex   625L (dex):  S_dex, U_dex, WA_dex   720R (dex):  WA_dex, S_dex, U_dex
728R (dex):  WA_dex, S_dex, U_dex
```

**28 of 29 are monotone** (deepen only, never a lighter state after `U`/`U_dex`). **Exactly one, `625L`,
has a block sequence that ends in a lighter state after `U_dex`** — this reproduces the original probe's
finding, independently re-derived rather than trusted.

**Recovery count among drug patients: 1 of 29 by the block-sequence test alone — pending the gap check
below.**

### 4. Time-gap audit — the ~100× dismissal of 625L, checked rather than inherited

All 52 block-to-block transition gaps (in `refTime` units) across all 29 drug patients, sorted ascending
(pid, from state, to state, gap):

```
403L S->U 0.0035   399R S->U 0.0035   405L S->U 0.0035   372L S->U 0.0035   640L S->U 0.0062
741L WA->S 0.0104  413R WA->S 0.0125  458R WA_dex->S_dex 0.0125  460L WA_dex->S_dex 0.0125
720R WA_dex->S_dex 0.0125  728R WA_dex->S_dex 0.0125  456R WA_dex->S_dex 0.0125  525L WA_dex->S_dex 0.0125
394R S->U 0.0132   418R WA->S 0.0132  423L WA->S 0.0132  376R S->U 0.0132   640L WA->S 0.0132
672R WA->S 0.0134  672R S->U 0.0134   413R S->U 0.0139   439B S_dex->U_dex 0.0139
457B WA_dex->S_dex 0.0139  525L S_dex->U_dex 0.0139  728R S_dex->U_dex 0.0139
439B WA_dex->S_dex 0.0146  741L S->U 0.0150   409L S->U 0.0167   423L S->U 0.0167   400L S->U 0.0167
634L WA->S 0.0167  625L S_dex->U_dex 0.0181  457B S_dex->U_dex 0.0195  409L WA->S 0.0201
399R WA->S 0.0215  372L WA->S 0.0222   400L WA->S 0.0222   405L WA->S 0.0222   403L WA->S 0.0222
376R WA->S 0.0229  394R WA->S 0.0236   384B WA->U 0.0243   418R S->U 0.0250   634L S->U 0.0257
567R WA->U 0.0262  458R S_dex->U_dex 0.0278  720R S_dex->U_dex 0.0278   514L WA->U 0.0327
585L WA->U 0.0463
559R WA_dex->S_dex 1.0125   559R S_dex->U_dex 2.0139
625L U_dex->WA_dex 3.9694
```

**52 real within-arm transitions range 0.0035–0.0463 refTime units (median 0.0148), with two outliers in
the SAME (monotone, non-recovering) patient `559R`** (WA_dex→S_dex 1.0125, S_dex→U_dex 2.0139) **and one
outlier in the sole apparent recoverer, `625L`** (U_dex→WA_dex 3.9694).

`625L`'s own loss transition, `S_dex`→`U_dex`, is 0.0181 — squarely inside the normal range. Its
apparent-recovery transition, `U_dex`→`WA_dex`, is **3.9694**, which against the 52-transition median of
0.0148 is **~268×** larger, and against the largest other same-episode gap in the whole drug cohort
(`585L`, `WA`→`U`, 0.0463) is **~86×** larger — both consistent with the probe's "~100×" claim, now
measured rather than asserted.

**Independent corroboration beyond the drug-block gap alone:** pulling 625L's FULL unfiltered label
sequence (not just the drug-arm rows) shows the entire picture. The patient has a block of sleep staging
(`WS`/`N1`/`N2`/`N3`/`R`) at `refTime` ≈ 7.31–7.69, then a gap of **~6.1 refTime units** to `S_dex` at
13.77 (note: **625L's own timeline never shows a `WA_dex` block before `S_dex`** — the record does not
capture this patient awake-on-dex at all before sedation is already underway), `U_dex` at 13.79, and then
the same **~3.97-unit** gap to a lone `WA_dex` block at 17.76 with nothing after it. If `refTime` is in
days (consistent with Krause/Banks being a multi-day epilepsy-monitoring-unit intracranial deposit), this
reads as: sleep staging on day ~7, dexmedetomidine sedation starting day ~13.8, and a `WA_dex`-labelled
block on a **separate day, ~4 days later**, with no drug-arm activity in between. That is not recovery
within an anaesthetic episode — it is the same generic state label reused for what looks like a distinct
later session or a different clinical event days on, which is a labelling/session artefact, not a
loss→recovery transition.

### Answer

**Does Krause satisfy "loss AND recovery" among drug patients — NO.**

0 of 29 drug patients (19 propofol, 10 dexmedetomidine) show a genuine within-episode recovery from
unresponsiveness. The one nominal exception, `625L`, returns to `WA_dex` only after a gap ~86–268× any real
transition in the cohort, on a timeline whose full (unfiltered) sequence shows it separated from the loss
event by what looks like a distinct multi-day session gap, with no `WA_dex` block ever recorded before
sedation began. The original probe's Krause cell — (b) **NO** — is **confirmed independently**, and its
table verdict (Krause fails (b) only; no fully public deposit clears all three of Challenge A's criteria)
**stands. Challenge A remains blocked on fully public data**, as concluded before this check.

---

## Opus verification of the resolution above, and one number withdrawn (2026-08-02)

Re-derived directly from `bsde/results/krause_dexprosleep_allData.csv` (12,313 rows, 34 patients), sorting
each patient's rows by `refTime`, collapsing to label blocks, and counting every block transition that
LEAVES `U`/`U_dex`:

| quantity | re-derived | agent reported |
|---|---|---|
| patients | 34 | 34 |
| propofol / dex / sleep-only | 19 / 10 / 5, no patient in both drug arms | same |
| drug block transitions | 52 | 52 |
| block transitions leaving U | **1** (`625L`, `U_dex`->`WA_dex`) | 1 |
| that transition's gap | 3.957 | 3.9694 |
| median drug transition gap | 0.0097 | 0.0148 |

The split and the decisive count reproduce exactly. The two gap figures differ because block gaps can be
measured end-to-start or start-to-start; neither reading changes anything.

**One claim is withdrawn.** The resolution says `625L`'s gap is "**~86x** the largest other same-episode
gap in the whole drug cohort (`585L`, 0.0463)". That is inconsistent with the agent's own table three
lines above it, which lists `559R` at **1.0125** and **2.0139**. Against the actual next-largest gap in
the cohort the ratio is **~2x**, not 86x — and `559R`'s 2.0139 sits on a *loss* transition that the same
analysis counts as real. So gap size alone does not separate "session artefact" from "real transition"
here, and the 268x-versus-median figure inherits the same problem: the reference distribution has a tail
the comparison ignores. (Catalogue rule 50 — a baseline of the wrong shape carries the authority of a
measurement.)

**The verdict does not rest on that adjudication and is unchanged.** Whether `625L` is a genuine recovery
or a relabelled later session, **it is 1 patient of 29**. A loss-AND-recovery design across two agents
cannot be run on one recoverer; the question of whether that one is real never becomes decision-relevant.
Krause fails criterion (b), the probe's table stands, and **the pre-committed stop for Challenge A on
fully public data now fires.**

**Correcting my own earlier spot-check, which is what put this cell in doubt.** I reported "13 of 34
subjects returning from `U`". Re-run with rows sorted by `refTime`, the count is **1**. The number 13 is
exactly the count of patients carrying BOTH propofol and sleep labels (`propofolsleep`, 13 of 34) — i.e.
the spot-check was reading a sleep session and a drug session in one patient as a single timeline. The
probe's original cell was right and my challenge to it was the error.
