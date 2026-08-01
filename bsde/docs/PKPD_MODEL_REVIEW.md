# A comprehensive PK/PD model for the anaesthetic exposure — verified review and feasibility

Requested by the investigator, 2026-08-01, after the E117 plasma-vs-effect-site question. Every citation
below was confirmed from its own MEDLINE record via NCBI E-utilities, not from a summariser (rule 25, and
rule 39 for the track/clinical listings, which were pulled with `urllib` + gzip and parsed directly).

---

## 1. What the literature has converged on

The field moved away from single-population models (Marsh, Schnider, Minto) toward **general-purpose
allometric models** that cover neonates to the elderly, lean to obese, healthy volunteers to patients, in
one parameter set. For an exposure model that must apply across a whole surgical cohort, that is the
relevant class.

| role | model | record |
|---|---|---|
| **Propofol PK/PD — the comprehensive one** | Eleveld et al., *Pharmacokinetic-pharmacodynamic model for propofol for broad application in anaesthesia and sedation* | **PMID 29661412**, Br J Anaesth 2018 May, 120: 942–959 |
| — its corrigendum, which an implementation MUST apply | Eleveld et al. | **PMID 30032904**, Br J Anaesth 2018 Aug |
| **Remifentanil PK/PD** | Eleveld et al., *An Allometric Model of Remifentanil Pharmacokinetics and Pharmacodynamics* | **PMID 28509794**, Anesthesiology 2017 Jun |
| — TCI-compatible variant | Eleveld et al., *Target-controlled-infusion models for remifentanil dosing consistent with approved recommendations* | **PMID 32654750**, Br J Anaesth 2020 Oct |
| **Drug–drug interaction framework** | Minto et al., *Response surface model for anesthetic drug interactions* | **PMID 10839909**, Anesthesiology 2000 Jun |
| **Propofol–remifentanil interaction measured ON BIS AND EEG** | Bouillon et al. | **PMID 15166553**, Anesthesiology 2004 Jun |
| **Age-adjusted MAC for volatiles** | Mapleson, *Effect of age on MAC in humans: a meta-analysis* | **PMID 8777094**, Br J Anaesth 1996 Feb |
| — iso-MAC charts | Nickalls & Mapleson | **PMID 12878613**, Br J Anaesth 2003 Aug |
| **Cross-agent potency on a common scale** | Hannivoort et al., *…noxious stimulation response index as general indicators of the anaesthetic potency of sevoflurane, propofol…* | **PMID 27106965**, Br J Anaesth 2016 May |
| prospective clinical evaluation of Eleveld propofol | Driesens et al. | **PMID 41982180**, Eur J Anaesthesiol 2026 |
| legacy models, for comparison only | Schnider **PMID 9605675** / **PMID 10360845**; Minto **PMID 9009935** / **PMID 9009936** | |

**The recommended stack:** Eleveld propofol (29661412 + corrigendum 30032904) and Eleveld remifentanil
(28509794) to get each drug's effect-site concentration from the infusion record, combined through a Minto
response surface (10839909) parameterised for the EEG endpoint by Bouillon (15166553), with volatiles
brought onto a common scale by age-adjusted MAC (8777094 / 12878613) or the Hannivoort potency index
(27106965).

Bouillon is the load-bearing one for this project: it is the paper that measured the propofol–remifentanil
interaction **on BIS and on the EEG specifically**, rather than on a clinical endpoint, which is exactly
what "having the EEG track that" requires.

---

## 2. Feasibility — VitalDB records everything the model needs

Pulled from the open API (`api.vitaldb.net/trks`, 486,450 rows over 196 distinct tracks;
`api.vitaldb.net/cases`, 74 columns over 6,389 cases):

| requirement | track / field | cases |
|---|---|---|
| propofol infusion **rate** | `Orchestra/PPF20_RATE` | 3,512 |
| propofol cumulative **volume** | `Orchestra/PPF20_VOL` | 3,512 |
| propofol pump Cp / Ce / target | `Orchestra/PPF20_CP` / `_CE` / `_CT` | 3,511 |
| remifentanil rate / Ce / target | `Orchestra/RFTN20_RATE` / `_CE` / `_CT` | 4,771–4,773 |
| **end-tidal sevoflurane** | `Primus/EXP_SEVO` | 3,687 |
| **end-tidal desflurane** | `Primus/EXP_DES` | 2,046 |
| monitor MAC | `Primus/MAC` | 6,338 |
| BIS / EMG / SQI | `BIS/BIS`, `BIS/EMG`, `BIS/SQI` | 5,867 / 5,577 / 5,867 |
| **age, sex, height, weight, BMI, ASA** | clinical table | 6,389 |

**Every covariate the Eleveld models require is present**, and the infusion rate and cumulative volume mean
Ce does not have to be taken on trust from the pump — it can be computed independently, with any model,
and the pump's own value used as a cross-check.

---

## 3. A second exposure mis-specification, found by this probe

The E117 question was plasma versus effect site. The same probe surfaced its twin on the volatile side:

> **This project has been using `Primus/INSP_SEVO` and `INSP_DES` — INSPIRED concentration — when
> `EXP_SEVO` and `EXP_DES` are recorded in exactly the same 3,687 and 2,046 cases.**

Inspired concentration is the fresh gas delivered to the circuit. **End-tidal** approximates alveolar and
therefore arterial and effect-site concentration, and is what MAC is defined on. Inspired leads end-tidal
substantially during induction, emergence and any vaporiser change — precisely the periods E102 and E109
care about — and the gap depends on fresh gas flow and circuit volume, which are not recorded.

This affects the volatile arm of **E110, E112, E113, E118 and E120**. It is cheap to fix — one extra track
in `join_vitaldb_agents.py` — and unlike the chennu plasma issue it is fixable with data already published.

---

## 4. Scope of the build, stated honestly

Implementing this is not a small job and should not be presented as one:

1. **Extraction** — add `PPF20_RATE`, `PPF20_VOL`, `RFTN20_RATE`, `EXP_SEVO`, `EXP_DES` and the six
   demographic fields. Straightforward; one pass.
2. **Eleveld propofol PK/PD** — three-compartment ODE with allometric and maturation covariates, plus an
   effect-site compartment with a BIS-derived `ke0`. **The 2018 corrigendum must be applied**; a model
   implemented from the original paper alone is wrong.
3. **Eleveld remifentanil** — same shape, different covariates.
4. **Volatiles** — end-tidal to effect site with a first-order lag, then age-adjusted MAC fractions.
5. **Interaction** — Minto response surface, Bouillon's EEG parameterisation, producing a single
   predicted-effect scalar.
6. **Validation before use, and this is the part that decides whether any of it is worth having.** The
   implementation must reproduce the pump's own `PPF20_CE` from `PPF20_RATE` alone, on cases where both
   exist, before it is trusted anywhere. That is a genuine external check — the pump computed its value
   independently — and it is the first gate any successor should write.

Only then does the question the investigator actually asked become answerable: **does the EEG track a
properly modelled combined effect-site exposure better than it tracks any single agent?** E110 and E112
answered a weaker version of that (the exponent does not track propofol; a 20–40 Hz slope partly does) and
E120 showed adding remifentanil as a covariate changes nothing. Neither used a real PK/PD model, and
neither could.
