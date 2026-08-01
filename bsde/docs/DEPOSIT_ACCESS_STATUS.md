# Track F — deposit access, measured 2026-08-03

*Every line below is a MEASURED response code, not a documentation claim. No credential appears in this
file or anywhere else in the repository.*

## What was resolved

**PhysioNet credentials work.** A Django session login (`POST /login/` with the CSRF token) succeeds and
returns a session cookie; an open project (`mimic-iv-demo`) fetches at HTTP 200 through it. The account is
valid.

**HTTP Basic auth does NOT work against PhysioNet file paths** — it returns 403, the same code as no auth
at all, which is why `CREDENTIALS.md`'s 2026-07-28 test read as a credential failure. It was a *mechanism*
failure. File access needs the session cookie. `~/.netrc` alone is therefore not sufficient for
`/files/…`; anything fetching DUA-gated PhysioNet data must log in first.

**A stale version path masquerades as a permission denial.** `sicdb/1.0.6/` returns 403 while
`sicdb/1.0.8/` returns 200 with the full file list. Both are listed on the project page. **Check the
current version before concluding a project is inaccessible** — the two failures are indistinguishable by
status code.

## Per-database status

| deposit | status | note |
|---|---|---|
| **SICdb 1.0.8** | **ACCESSIBLE** | `cases`, `medication`, `laboratory`, `data_float_h`, `data_range`, `data_ref`, `d_references`, `Documentation.pdf` |
| **HiRID 1.1.1** | **ACCESSIBLE** (corrected — see below) | 16.8 GB: `raw_stage/`, `merged_stage/`, `imputed_stage/`, `reference_data.tar.gz`, `schemata.pdf` |
| **eICU-CRD** | files section visible | v2.0, not yet fetch-tested |
| **MIMIC-IV** | files section visible | v0.3–2.0, not yet fetch-tested |
| **AmsterdamUMCdb** | **404 on PhysioNet** | not hosted under that slug; it is distributed elsewhere |
| **BDSP (HEEDB, I-CARE)** | **WORKING** | `sts get-caller-identity` → `arn:aws:iam::281627750420:root` via the `~/.aws/credentials` profile. The env vars being UNSET is the correct state (rule 36) |

## What SICdb is and is not good for

**It has:** ICU-scale n, a drug administration table, laboratory values, high-resolution physiology,
**RASS** (Richmond Agitation-Sedation Scale — a clinician-assigned, NON-EEG state measure), and mortality.

**It does not have EEG.** So it does **not** solve E130's blocker, which was stated as *an assayed or
pump-reported concentration, a non-EEG state measure, and ≥ 60 subjects — with EEG*. E130 had EEG and
n = 20; SICdb has n in the thousands and no EEG. The gap is unchanged and should not be reported as closed.

**What it does unlock, and it is not small:**

1. **The pharmacology arm at scale.** How much RASS variance does sedative exposure explain, at ICU n?
   That number is the *ceiling* the residual framing assumes exists — E122 measured it at out-of-bag
   rho 0.4595 on 94 DOSE-I recordings, and nothing has ever checked whether that generalises. If sedative
   exposure explains far more or far less of a sedation scale at scale, the whole residual argument
   recalibrates.
2. **Challenge E's outcome layer**, with mortality on a cohort that also has the drug record.
3. **A transport test for Challenge D** — the DOSE-I pharmacology model carried to a different population,
   different drugs, different scale, against a different sedation scale. That is exactly the forward
   prediction D was told to make rather than retrodict.

## EEG deposits — read from the overview pages, not inferred (added after investigator correction)

The first pass concluded "SICdb has no EEG" from a keyword scan of a landing page. That was inference, not
reading. The overviews were then read in full, and PhysioNet's 427-project index enumerated: **32 projects
are EEG / sedation / consciousness relevant.** The conclusion held but is now evidenced — SICdb's overview
describes raw signal data with no EEG; HiRID and eICU-CRD mention neither EEG nor waveforms anywhere.

**The deposit E130 needs exists, and it is identified.**

| deposit | has | status |
|---|---|---|
| **`eeg-gaba-anesthesia`** | **64-channel whole-head EEG (BrainVision) AND `propofolConcentration_*.csv` — the effect-site concentration** | **403 — credentialing/DUA needed** |
| `propofol-anesthesia-dynamics` | `LOC_ROC.csv` — loss/return of consciousness annotated from **a button-pressing task**, TCI protocol, ~3 h per subject, HRV + EDA per subject | ACCESSIBLE — but **no EEG**, autonomic only |
| `multimodal-surgery-anesthesia` | 101 surgeries, 18,582 minutes, 49,878 nociceptive events, `OR_data.mat` | ACCESSIBLE — EEG content not yet confirmed |
| `eeg-power-anesthesia` | multitaper spectra under GABAergic unconsciousness | not yet checked |

**`eeg-gaba-anesthesia` is the one that matters.** E130's blocker was stated as *an assayed or
pump-reported concentration, a non-EEG state measure, and ≥ 60 subjects, with EEG* — and this deposit
carries the first and the third of those from the same group (MGH) whose companion deposit supplies a
behavioural LOC/ROC annotation. It is 403 for the same reason HiRID is: **account credentialing**, not a
password.

That converts the credentialing action from a speculative "might unlock something" into a named target.

## The AWS route — diagnosed 2026-08-03, and it is TWO gates not one

PhysioNet's "Access via AWS" panel names the identity it grants to:

    Account 281627750420   User arn:aws:iam::281627750420:user/physionet-user

**Gate 1 — wrong principal.** The credentials in `~/.aws/credentials` resolve to
`arn:aws:iam::281627750420:root`, the account ROOT. PhysioNet grants to the IAM USER
`physionet-user`. A cross-account bucket policy naming a user ARN does not match root, so these keys
cannot pick up PhysioNet's grant no matter which bucket is tried. The IAM user **does exist in the account
and already has two access keys** — they are simply not the ones on disk.

**Gate 2 — credentialed projects are not in the open mirror.** `s3://physionet-open/` lists **250**
top-level projects and is readable now. `sleep-edfx` and `eegmmidb` are there (both already used by this
project). But `eeg-gaba-anesthesia`, `multimodal-surgery-anesthesia` and `propofol-anesthesia-dynamics`
are **absent** — consistent with `CREDENTIALS.md`'s 2026-07-28 note that credentialed projects are not
mirrored to the open bucket. Fixing gate 1 alone will not reveal them; the per-project DUA still has to be
signed, after which PhysioNet grants the registered identity access to the restricted location.

`physionet-restricted` and `physionet-credentialed` do not exist as bucket names; `s3://physionet/` exists
and returns AccessDenied.

**What this means practically.** The HTTPS session route already works for anything the account is
approved for, and it found `multimodal-surgery-anesthesia` and `propofol-anesthesia-dynamics` open while
`eeg-gaba-anesthesia` is 403. So the S3 route is not currently a way around the 403 — **the 403 is the DUA,
not the transport.** Fixing the AWS identity is worth doing for bulk transfer speed once a DUA is signed,
not as a means of obtaining access.

**Action, and it is deliberately not taken here.** Access keys for `physionet-user` could be created from
root, but minting AWS credentials is a security-sensitive, outward-facing action and is left to the
investigator. Either use that user's existing keys, or create a key for it and place it in the environment
settings as `BDSP_AWS_ACCESS_KEY_ID` / `BDSP_AWS_SECRET_ACCESS_KEY`.

## CORRECTION 2026-08-03 — HiRID was never restricted, and I made the same error twice

The table above originally read **HiRID: RESTRICTED, credentialing/DUA required**. That was wrong.
`https://physionet.org/files/hirid/1.1.1/` returns **HTTP 200** with the full directory listing, and has
throughout.

**How the error was made.** Two inferences, no measurement:

1. `hirid/1.1.1/RECORDS` returned **404** — and I read that as a permissions signal. It is a path error:
   HiRID has no `RECORDS` file. Its top level is `raw_stage/`, `merged_stage/`, `imputed_stage/`,
   `reference_data.tar.gz`, `schemata.pdf`.
2. The project landing page contains the words *"you must be a credentialed user"* and *"sign the data
   use agreement"* — **generic descriptive boilerplate present on every restricted-class project page,
   whether or not THIS account is approved.** I keyword-matched it and called the deposit restricted.

**This is the second time in one day** the same mistake was made — the first was concluding "SICdb has no
EEG" from a landing-page keyword scan. The investigator corrected that one explicitly. The rule that
follows, and it is not subtle: **a project's ACCESS STATUS is a property of the account, and the only way
to read it is to request a file and look at the status code.** Landing-page text describes the project
class, not the grant.

A third failure mode also went into that wrong call, and it is now recorded in the list above: the
username does NOT matter. `dgkenn@bu.edu` and `deankennedy` both authenticate and both return HTTP 200
for the same path (1047 bytes each). PhysioNet accepts either for the web session.

**So four things return an unhelpful status and only one of them is a real denial:** wrong path (404),
stale version (403), HTTP Basic instead of a session (403), and an actual missing DUA (403). Only a
directory listing on the current version, through a session, distinguishes them.

**Still genuinely 403:** `eeg-gaba-anesthesia/1.0.0/`. That is consistent with the grant notice reading
*"You have been granted access for a specific project"* — HiRID, specifically. `eeg-gaba-anesthesia`
needs its own access request, and it remains the deposit E130 requires.

## HiRID's contents — and rule 5, caught in the act (2026-08-03)

HiRID 1.1.1 is accessible (16.8 GB). `reference_data.tar.gz` is only 316 KB and carries
`hirid_variable_reference.csv`, 712 variables across two source tables, `Observation` and `Pharma`.

| what | HiRID variable |
|---|---|
| state measure | **Richmond agitation-sedation scale** (Observation, ordinal) |
| propofol | **`Disoprivan 1%`, `Disoprivan 2%`, `Disoprivan 2% BOLUS`, `Disoprivan BOLUS 2% 20mg/ml`** |
| midazolam | `Dormicum` Perfusor / Bolus / inj / Tbl |
| dexmedetomidine | `Dexdor Inf. Lsg` |
| opioids | Fentanyl inj / Bolus / PCA, Sufentanyl Perfusor |

**A search for "propofol" returns ZERO hits.** Bern is a German-speaking hospital and the pharmacy
vocabulary is trade names. Reporting that zero would have excluded an entire cohort from Challenge D on
the strength of an unvalidated search string — which is **rule 5** verbatim: *empty is not evidence of
absence until the filter has been shown capable of matching something.* The filter here could not match
anything, because the word does not occur in the deposit.

This is the third instance in one day of concluding from something not verified — "SICdb has no EEG" from
a landing-page keyword scan, "HiRID is RESTRICTED" from landing-page boilerplate, and now "HiRID has no
propofol" from a generic-name search in a trade-name vocabulary. **The common shape is asserting a
NEGATIVE from a search whose sensitivity was never established.** Every one was caught, two of them by the
investigator, and the cost each time would have been discarding a usable deposit.

**HiRID carries BOTH infusion and bolus propofol**, which no other cohort here does. That makes a genuine
three-rung transport ladder for Challenge D:

| cohort | dosing | drugs | scale | timescale | setting |
|---|---|---|---|---|---|
| DOSE-I | bolus only | propofol alone | MOAA/S 1-5 | minutes | endoscopy suite |
| **HiRID** | **bolus AND infusion** | multi | RASS | days | Swiss ICU |
| MIMIC-IV | infusion | multi | RASS | days | US ICU |

`exposure_basis` already sums bolus and infusion contributions exactly in one call, so HiRID needs no new
kinetics — it exercises the path built for VitalDB and never yet used on a cohort that has both.

## Actions

**Needs the investigator:** HiRID requires PhysioNet *credentialing* (CITI training plus a credentialing
application) and then a signed DUA per project. That is an account-level status on physionet.org, not
something a password unlocks. Worth confirming which projects the account is already approved for before
any is planned on.

**Needs no one:** SICdb is fetchable now.

**Security note.** The credentials were supplied in a chat transcript. They are written only to `~/.netrc`
at mode 600, outside the repository, and appear in no committed file. **The password should be rotated**,
because a transcript is not a secret store. The durable place for these is the Claude Code web
environment's environment-variable settings, per `CREDENTIALS.md`.

---

## eeg-power-anesthesia 1.0.0 — what it can and cannot host (measured 2026-08-01, E148–E158)

Extracted in full: 44 OR cases and 10 volunteers, 144,242 epochs of per-2 s spectral features, plus the
deposit's own `Volunteer_CNN/btlncks.feather` (46,948 windows × 1,280 MobileNet bottlenecks).

**The volunteer arm hosts behavioural-landmark designs; the OR arm cannot.** Every volunteer has exactly
one behavioural LOC and one behavioural ROC, defined by response probability to click and verbal cues
crossing 5 %, with 18–67 min of drug-free baseline. **In the OR arm, 0 of 44 cases have a conscious epoch
adjacent to an unconscious one** — the median gap between the last conscious and the first unconscious
epoch is **286 epochs (10 min)**, range 31–1051, because the deposit labels the whole induction-to-surgery
window `NaN` on the stated grounds that the true LOC is unknowable retrospectively. So any design that
needs the two states to be adjacent in time — E148's concentration-matching, E151/E152/E153's landmark
jump — **is confined to ten subjects and cannot be replicated inside this deposit.** That is the binding
limit on the alpha-peak result, not the statistics.

**The OR arm's strength is the agent contrast and the quality series**, and its trap is case length:
`rx_sorted_case_ids.yml` gives pure_propofol 27, mixed 16, **pure_sevo 1** (there is no sevoflurane-alone
arm), and sevoflurane cases are nearly twice as long — median 1,740 good-quality unconscious epochs
against 900 — which E154 measured identifying the agent at |AUC−0.5| = **0.3771**, above every feature but
one. Any OR design must hold case length constant by construction, as E155 does with a fixed 300-epoch
summary window.

**ds004541 carries `meta_loc_s` and `meta_roc_s`** and is therefore the only other deposit here with
landmark times — but it has **7 subjects and 101 epoch-level rows**, roughly 14 per subject, so it cannot
support a jump statistic either.

**Consequence for Challenge A.** The recovery clause is testable on exactly ten subjects anywhere this
project can reach, and no second cohort exists for it. The Turku/Kallionpää request (within-subject LOR
*and* ROR at constant dosing) is now supported by three independent structural findings rather than one.

---

## OpenNeuro, surveyed exhaustively (2026-08-01) — there is no disorders-of-consciousness EEG deposit

`PROGRAMME_ROADMAP.md` item F says *"we are bounded by deposits, not by ideas, and the boundary has never
been mapped."* This maps one edge of it.

**Method.** Every dataset on OpenNeuro was enumerated through the GraphQL API and parsed directly —
never a WebFetch summary of a listing, which fabricated a file manifest for this project once (rule 39).
Machine-readable output in `results/openneuro_eeg_survey.json`, so the claim is auditable rather than
recalled.

**Result.** **1,834 datasets scanned; 517 carry EEG or iEEG; 36 match a deliberately broad keyword set**
(consciousness, coma, vegetative, unresponsive, minimally conscious, anaesthesia/anesthesia, sedation,
propofol, sevoflurane, ketamine, dexmedetomidine, command, motor imagery, brain injury, hypnosis, xenon,
nitrous, sleep, arousal).

**Not one of the 36 is a disorders-of-consciousness cohort.** No coma, no unresponsive wakefulness, no
minimally conscious state, no locked-in syndrome, no command-following in brain-injured patients. The
36 are sleep deposits, epilepsy iEEG, motor-imagery BCI in healthy volunteers, and three anaesthesia
recordings:

| accession | n | what it is | status here |
|---|---|---|---|
| `ds005620` | 21 | repeated awakening, complexity measures | already extracted and used (E15, E103, E153 lineage) |
| `ds004541` | 8 | EEG-fNIRS under general anaesthesia | already extracted and used (E19, E20) |
| `ds003380` | **1** | corticothalamic communication under gradual isoflurane | one subject |

The largest motor-imagery deposits are `ds005342` (32) and `ds008446` (20) — healthy volunteers, the same
proxy relationship `CHALLENGE_DEFINITIONS_CORRECTION.md` flagged as never having been justified.

**What this changes.** Two blocked data requests stop being *one option among several* and become **the
only route**:

* **Challenge B** needs command-following in brain-injured patients. **BATH-01632** (UWS 14 / LIS 11 /
  MCS 17 / able-bodied 2), requested 2026-07-30, is the pre-registered target of E18 and there is no
  public substitute.
* **Challenge A** needs two anaesthetics with loss *and* recovery in the same subjects. **Turku /
  Kallionpää** is the drafted request, and the MGH volunteer cohort's ten subjects remain the only
  behavioural LOC/ROC data reachable at all.

**Limit of the survey, stated rather than left implicit.** The keyword match runs over each dataset's
`Name` and its task labels, not its README or its participants file. A DoC deposit whose title avoids
every one of those eighteen terms would be missed. The claim is therefore "OpenNeuro's titles and task
labels contain no DoC EEG cohort", which is weaker than "OpenNeuro contains none" and is what the method
supports.
