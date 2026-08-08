# Tier 0/1 targets found by applying `SOP_DATA_ACQUISITION.md` — no email required

*2026-08-07, immediately after writing the SOP. Found by enumerating what is reachable rather than by
chasing a specific paper. Reachability was **measured**, not assumed.*

---

## Reachability from this environment, measured

| repository | status |
|---|---|
| Zenodo, PhysioNet, DANDI, figshare, Dryad, NEMAR, OpenNeuro, NCBI E-utilities | **reachable (HTTP 200)** |
| **NSRR (`sleepdata.org`)** | **NOT reachable — TLS failure through the agent proxy** |
| OSF API (`api.osf.io`) | not reachable |

**NSRR being unreachable is an environment limit, not a project one.** It holds tens of thousands of
scored PSGs with EMG and remains the single highest-value Tier 1 target for any session or machine that
can reach it. Recorded so it is not silently forgotten.

---

## 1. `eeg-power-anesthesia` — PhysioNet, **restricted (credentialed, form-based)**

> *Multitaper spectra recorded during GABAergic anesthetic unconsciousness.* EEG multitaper spectra and
> associated **conscious/unconscious labels** for **10 healthy volunteers undergoing stereotyped
> anaesthetic administration and direct monitoring of subject responsiveness**, and **44 patients** in an
> operating-room context, divided into **propofol alone (TIVA)** and **sevoflurane alone or sevoflurane
> following a propofol induction**.

**This is an independent test cohort for both of this project's live claims, and it needs a form rather
than a person's goodwill.**

* **For the state-dependent leakage line** — it has the propofol-versus-sevoflurane contrast in an OR
  population *with* conscious/unconscious labels. Our claim is that agent identity is large at
  maintenance and small near emergence; this cohort can be split by its own labels rather than by a
  ventilatory landmark, which removes the weakest part of our design.
* **For the arousal/processing line** — "direct monitoring of subject responsiveness" in the 10
  volunteers is the behavioural axis this project has never had on scalp EEG.

**Known limitation before requesting:** the deposit is **multitaper spectra, not raw traces**. Complexity
and entropy measures (`NmlzCmplx`, `lempel_ziv`, `multiscale_entropy_slope`) **cannot be computed from a
spectrum**, so the arousal/processing head-to-head is only partly runnable. Spectral candidates and the
leakage analysis are fully runnable. Say this in the application rather than discovering it after.

**Access route:** PhysioNet credentialed access — CITI training plus a signed DUA. **The session-start
hook reports `PhysioNet: no credentials` and names the environment variables (`PHYSIONET_USER`,
`PHYSIONET_PASSWORD`).** That is an investigator action of the form-filling kind, not an email.

## 2. `propofol-anesthesia-dynamics` — PhysioNet, **Open**

Nine healthy volunteers, computer-controlled propofol, **behavioural responsiveness** plus autonomic
indices (HRV, electrodermal). **Open access, downloadable now.**

Value is narrower: it is an autonomic dataset, so it does not carry the EEG this project needs. It is
worth holding as a **behavioural-axis reference** — the timing and structure of responsiveness testing
during a controlled propofol induction — and for a sanity check that our landmark definitions resemble
what a purpose-built protocol does.

## 3. `eda-rest-sedation` — PhysioNet, **Open**

11 awake + 11 propofol-sedated volunteers, electrodermal only. No EEG. Recorded for completeness; not a
target.

---

## What this changes about the plan

`DATA_REQUESTS_STUDY_A.md` currently leads with three **Tier 4** asks (Casey/Sanders, ds005620, Turku),
all of which depend on someone replying to email. **They are now demoted below the Tier 1 route above.**
The Casey cohort remains the ideal object and the request should still go out — but the SOP's rule is
that no study may depend on it, and `eeg-power-anesthesia` gives an independent cohort that depends only
on paperwork.

**The next action is credentialing, not correspondence.**


---

## MEASURED ACCESS STATE, 2026-08-07 — what is blocked and exactly what unblocks it

Tested from this environment rather than assumed:

| target | route | result |
|---|---|---|
| `propofol-anesthesia-dynamics` (open) | `https://physionet.org/files/.../1.0/` | **200 — downloadable now** |
| `eeg-power-anesthesia` (restricted) | same | **403 — credentials required** |
| `s3://physionet-open/...`, `s3://physionet-restricted/...` | unsigned boto3 | **wrong bucket names / NoSuchBucket** |
| AWS CLI | `aws` | **not installed**; `boto3` installs fine |
| `scripts/bdsp_bootstrap.sh` | — | **"AWS: no working credentials", "PhysioNet: no credentials"** |

**The investigator has registered an AWS identity with PhysioNet**
(`arn:aws:iam::281627750420:user/physionet-user`). **That identity's keys are not present in this
environment**, so the S3 route cannot be used from here yet.

### What to set, in the Claude Code web environment's environment-variable settings

Either route works; the first is simpler and needs no bucket discovery.

1. **HTTPS (recommended):** `PHYSIONET_USER`, `PHYSIONET_PASSWORD`. `bdsp_bootstrap.sh` already probes for
   exactly these two and reports them missing. Files then come from
   `https://physionet.org/files/eeg-power-anesthesia/1.0.0/` with HTTP basic auth.
2. **S3:** the access key and secret for `physionet-user` in account `281627750420`. **The bucket name
   must be read off the project's own Files page**, which is itself behind the 403 — so route 1 has to
   work first, or the URI has to be supplied. Guessing bucket names failed and should not be repeated.

**Note the existing trap (catalogue rule 36):** this sandbox injects placeholder
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` that outrank profile credentials and produce 403s that look
like expiry. Anything touching S3 must run through `scripts/heedb_run.sh`.

### What was obtained now, and its honest value

`propofol-anesthesia-dynamics` (open, 9 volunteers) is **autonomic only — EDA and HRV, no EEG.** Its
landmark structure was read: per-subject `LOC` and `ROC` as single behavioural instants (S1: 3625.32 s and
10920.93 s) with ~10 stepped infusion events spanning ~2 h.

**Value: a design reference, not data.** It shows what a purpose-built protocol treats as a landmark — a
behavioural instant at response cessation — against our ventilation rule's 120 s sustain. That is a
comparison worth making in a methods section and it is **not** a validation of our landmark, because the
cohorts, drugs and measurement acts differ.
