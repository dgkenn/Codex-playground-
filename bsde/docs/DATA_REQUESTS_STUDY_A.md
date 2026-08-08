# Study A: the three asks, in order of cost to the person being asked

*Each is a request for something that already exists. None requires new data collection by the recipient.
Ordered after the 2026-08-07 prior-art correction: the Casey/Sanders cohort is Study A's actual design and
displaces the others to supporting roles.*

---

## 0. **THE PRIORITY** — Casey/Sanders UNCONSCIOUS cohort (NCT03284307)

**This is Study A's cohort, already collected.** Requesting it replaces a multi-year acquisition
programme with an analysis.

**What, verified from the trial registry and the MEDLINE record rather than from a summary:**

| | |
|---|---|
| trial | **NCT03284307** — "UNderstanding CONSciousness Connectedness and Intraoperative Unresponsiveness" |
| status | **COMPLETED 2020-03-12** |
| enrolment | **35 (actual)** |
| paper | Casey CP et al., *Br J Anaesth* 2022 — **PMID 35148892**, PMC9428919 |
| design | dexmedetomidine / propofol / natural sleep, high-density EEG, **serial awakenings** classifying disconnected consciousness vs unconsciousness in the preceding 20 s |
| sponsor | University of Wisconsin–Madison |
| PI | Robert A. Pearce |
| corresponding author | Robert D. Sanders, `robert.sanders@sydney.edu.au` (Sydney) |
| **IPD sharing statement** | **empty — no declared plan.** So this is a request, not a download. |

**What to ask for, smallest first.** Per subject, per awakening: the state classification (connected /
disconnected / unconscious), the drug or sleep condition, the behavioural score, and the pre-awakening
EEG epoch. Derived per-epoch features would be enough for the analysis below and are a far smaller ask
than raw hd-EEG.

**What we would do with it that they did not.** Their own validation is the opening:

* source-localised SVM signatures fall **0.999 → 0.743** (disconnection) and **0.972 → 0.622**
  (unconsciousness) from derivation to validation;
* their pre-registered primary, occipital delta, **fails outright at AUC 0.512** on sleep/propofol.

An SVM over source-localised activity cannot say *which* named measures fail or why. The head-to-head of
interpretable candidates with the **drug check as a primary** — E321's contribution, that delta separates
REM from N3 as strongly as complexity does and would pass as a consciousness measure if the drug arm were
absent — is not what their analysis asked.

**The honest limitation to acknowledge in the request.** 35 subjects across three conditions is roughly
12 per arm, which is very likely why the validation AUCs fell so far. A re-analysis inherits that, and
should be framed as *which measure classes fail and why*, not as a better classifier.

---

## 1. ds005620 awakening reports — the cheapest ask in the programme, and now the most important

**What.** OpenNeuro `ds005620` is a repeated-awakening propofol sedation study in healthy volunteers, up
to 3 awakenings per subject. `task-sed2` is documented in the deposit's own README as *"One-minute
resting EEG recorded just before an awakening"* — so **every awakening has a matched, clean,
pre-awakening minute of resting EEG, and it is already public and already downloaded here**
(`ds005620_features.csv`, 202 recordings, 21 subjects).

**What is missing.** `participants.tsv` gives an `awakenings` count per subject and nothing about what was
reported. There is no `_beh` file and no phenotype directory. **The EEG for the dissociation is public and
the label is not.**

**The ask.** One table: per subject, per awakening, whether an experience was reported, and ideally a
content class. No raw data transfer, no identifiers, healthy volunteers.

**Why it is now the priority.** Study A's feasibility turns on the report prevalence `p` under
anaesthesia, which nobody has published. **These 21 subjects × up to 3 awakenings would estimate it
directly**, and would convert Study A's sizing from a guess into a calculation.

Contacts listed in the deposit README: Imad J. Bajwa, Bjørn E. Juel.

## 2. Turku / Kallionpää — the two-agent within-subject cohort

**What.** Kallionpää et al., *Br J Anaesth* 2020 (**PMID 32773216**, NCT01889004): 64-channel EEG, 47
healthy volunteers on dexmedetomidine (n = 23) or propofol (n = 24), **within-subject loss and return of
responsiveness at constant dosing** — the design that separates state from drug concentration.

**Why.** Every depth axis available to this project was either EEG-derived (circular; E295) or a drug
concentration that failed its own validity check (E302, ρ = −0.05 against BIS). Constant-concentration
transitions dissolve that problem: the drug is held fixed while the state changes.

**Limitation to state in the ask.** Arms are between-subject for drug, so this supplies a within-subject
*state* contrast at fixed concentration — the more important half — not a within-patient two-agent
contrast.

## 3. Krause / Banks — raw traces for the cohort we already analyse

**What.** The Zenodo package (10.5281/zenodo.15497531) ships derived per-electrode features and **no raw
continuous iEEG**. Every number in E305, E306, E307, E321 and E323 comes from the depositors' pipeline.

**Why it matters.** Catalogue rule 23: self-written code and self-written tests share blind spots, and an
independent re-implementation is what catches them. **That check is currently unavailable** for the only
cohort in which this project has found a genuine arousal/processing dissociation. Raw traces additionally
require a University of Iowa DUA.

**The ask is the smaller one first**: confirmation of exactly how `NmlzCmplx` and `EffDim` are computed,
sufficient to re-implement them, before requesting traces.
