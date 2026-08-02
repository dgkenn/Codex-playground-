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
