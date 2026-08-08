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
