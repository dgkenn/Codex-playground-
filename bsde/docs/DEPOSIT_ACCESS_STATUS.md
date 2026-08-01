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
| **HiRID** | **RESTRICTED** | landing page 200, but flagged *credentialed user / data use agreement required*. Versions 1.0, 1.1, 1.1.1 |
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
