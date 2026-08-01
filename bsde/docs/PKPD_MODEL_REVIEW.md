# A comprehensive pharmacological exposure model — verified review, feasibility, and two blockers

Requested by the investigator, 2026-08-01, and broadened at their request to cover **synergy, clearance,
uptake and body composition**. Every citation confirmed from its own MEDLINE record via NCBI E-utilities
(rule 25); every availability figure pulled from the VitalDB open API with `urllib` and parsed directly
(rule 39). Nothing here is from a summariser.

---

## 1. The core model stack

The field moved off single-population models (Marsh, Schnider, Minto) to **general-purpose allometric
models** covering neonates to elderly, lean to obese, volunteers to patients in one parameter set.

| role | model | record |
|---|---|---|
| **Propofol PK/PD** | Eleveld, *…for broad application in anaesthesia and sedation* | **PMID 29661412**, Br J Anaesth 2018;120:942–959 |
| — corrigendum, **must be applied** | Eleveld | **PMID 30032904**, Br J Anaesth 2018 Aug |
| **Remifentanil PK/PD** | Eleveld, *An Allometric Model of Remifentanil PK/PD* | **PMID 28509794**, Anesthesiology 2017 |
| — TCI-compatible variant | Eleveld | **PMID 32654750**, Br J Anaesth 2020 |
| **Interaction framework** | Minto, *Response surface model for anesthetic drug interactions* | **PMID 10839909**, Anesthesiology 2000 |
| **Interaction measured ON BIS AND THE EEG** | Bouillon | **PMID 15166553**, Anesthesiology 2004 |
| **Age-adjusted MAC** | Mapleson meta-analysis | **PMID 8777094**, Br J Anaesth 1996 |
| — iso-MAC charts | Nickalls & Mapleson | **PMID 12878613**, Br J Anaesth 2003 |
| **Cross-agent common potency scale** | Hannivoort, NSRI | **PMID 27106965**, Br J Anaesth 2016 |
| prospective evaluation of Eleveld | Driesens | **PMID 41982180**, Eur J Anaesthesiol 2026 |

Bouillon is load-bearing here: it is the study that measured the propofol–remifentanil interaction **on BIS
and the EEG**, not on a clinical endpoint — which is what "having the EEG track it" requires.

---

## 2. The broader mechanisms, one by one

### 2.1 Reduced clearance

| mechanism | literature | VitalDB support |
|---|---|---|
| **Low cardiac output** — propofol is a high-extraction, **perfusion-limited** drug, so clearance falls with CO and concentration rises | Allegaert PBPK across ages **PMID 36145705**; Bienert, CO influence on propofol **and fentanyl** in aortic surgery **PMID 32840723**; Savoca, closed-loop **PMID 32155533** | **No direct CO measurement.** Proxies only: vasopressor use (ephedrine 42 %, phenylephrine 19 %, epinephrine 3 % of cases), arterial pressure waveform, HR |
| **Haemorrhage / hypovolaemia** — reduced central volume, higher peak concentration | De Paepe, hypovolaemia effect on propofol PK **and the EEG effect** — **PMID 11149444** | `intraop_ebl` (52 % of cases, median 150 mL), `intraop_rbc` (17 %), crystalloid (80 %), colloid (21 %) |
| **Hepatic impairment** | Chi, TCI models in hepatic insufficiency **PMID 30269150** | `preop_ast`, `preop_alt`, `preop_pt` — **but see §4** |
| **Renal impairment** | Pitsiu, remifentanil **and its acid metabolite** in renal impairment **PMID 14766712** | `preop_cr`, `preop_bun`. Note: remifentanil is esterase-metabolised, so renal failure spares the parent drug and accumulates the metabolite — a distinction worth keeping |
| **Hypothermia** | **Bartošová 2026, *Deep hypothermia reduces the predictive accuracy of the Eleveld propofol model*, PMID 42140058**; Leslie, mild hypothermia alters propofol PK **PMID 7726398** | Temperature tracks exist in VitalDB; not yet extracted |

The hypothermia paper is worth singling out because it is a documented failure mode **of the exact model
being proposed**, published this year.

### 2.2 Reduced/altered uptake and distribution

| mechanism | literature | VitalDB support |
|---|---|---|
| **Body composition, obesity, lean body mass** | Friesen, LBW scalar in morbid obesity **PMID 31109706**; Dong, obesity alters **both PK and PD** **PMID 27481855** | weight, height, BMI at **100 %** coverage. Cohort is lean: BMI ≥ 30 in **4.1 %**, BMI < 18.5 in **7.7 %** — so obesity scaling matters less here than the literature implies, and underweight matters more |
| **Protein binding** — propofol is ~98 % albumin-bound; free drug drives effect | binding-site work **PMID 28917201**; albumin modulates propofol channel effects **PMID 27164421**. **No clinical PK/PD model that takes albumin as a covariate was found** | `preop_alb` present — **but see §4** |
| **Volatile uptake** (CO, alveolar ventilation, blood:gas coefficient) | Peyton, gas-phase diffusion is not rate-limiting **PMID 35503977** | **This problem is bypassed**: VitalDB records `EXP_SEVO` / `EXP_DES` — measured end-tidal, i.e. alveolar — so no uptake model is needed to reach effect site |

### 2.3 Synergy

Established, and parameterised on the EEG: **propofol–remifentanil** (Minto **PMID 10839909**, Bouillon
**PMID 15166553**), and cross-agent potency on one scale (Hannivoort **PMID 27106965**).

**A validated general interaction surface for three or more drugs does not appear to exist.** A targeted
search for triple/multi-drug interaction models returned nothing usable. The practical route is therefore
to map every agent onto a **common potency scale** (MAC-equivalents or NSRI) and combine additively there,
with a Minto surface only for the propofol–opioid pair where a measured surface exists. That is a real
limitation of the literature, not of the data, and it should be stated in any output rather than papered
over with a bespoke multi-drug model this project invents.

---

## 3. A scoping correction to E120

E120 recorded, correctly for its own 250-case subset, that there was *no midazolam and no vecuronium*.
**Across the full 6,388-case VitalDB cohort that is false**, and any expansion must handle:

| agent | cases | % | median dose |
|---|---|---|---|
| **fentanyl** — a second opioid, entirely unhandled | 1,024 | **16 %** | 100 µg |
| midazolam | 423 | 7 % | 100 mg⁽*⁾ |
| vecuronium | 941 | 15 % | 80 mg⁽*⁾ |
| propofol bolus | 2,060 | 32 % | 100 mg⁽*⁾ |
| rocuronium | 5,159 | 81 % | 70 mg |

⁽*⁾ These medians are implausible for midazolam (100 mg) and suggest the dose columns carry mixed units
or mixed meanings — the same problem as §4 and it must be resolved before use.

**Fentanyl is the substantive gap**: it is a long-acting opioid given in 16 % of cases, it is not on the
TCI pump so has no `Ce` track, and reaching an effect-site concentration for it requires a PK model driven
by bolus dose and timing. E120's opioid audit covered remifentanil only.

---

## 4. **BLOCKER: ~15 % of the preop labs are not usable as recorded**

A plausibility audit (rule 6 — check a column before designing around it) of the covariates a clearance
model needs:

| field | n | outside plausible range | what the outliers look like |
|---|---|---|---|
| `preop_alb` | 6,021 | **15.1 %** | values 0.6–1.1 "g/dL" — incompatible with life |
| `preop_k` | 5,767 | **14.8 %** | 31, 32, 125, 129 — these are **sodium** values |
| `preop_na` | 5,815 | **15.5 %** | 19.7, 20.5, 22.8 — these look like BUN or CO₂ |
| `preop_ast` | 6,019 | **15.2 %** | 1.8–2.4 U/L |
| `preop_gluc` | 5,955 | **14.3 %** | 3.0–3.4 — that is **mmol/L**, i.e. SI units mixed with conventional |
| `preop_cr` | 6,017 | 6.1 % | mostly extreme-but-possible |
| `preop_hb`, `preop_alt`, `preop_bun` | — | 0.1–0.3 % | clean |

The consistent ~15 % rate across five different fields, and the SI-versus-conventional glucose signature,
point to **mixed units and/or row-level column misalignment in a subset of records** rather than to genuine
outliers. Used naively, a patient recorded at "albumin 0.6" would be modelled as profoundly
hypoalbuminaemic, its free propofol fraction inflated several-fold, and the EEG asked to track a fabricated
exposure.

**No clearance covariate may be used until this is resolved** — by unit detection per row, by
cross-field consistency checks, or by dropping the affected records and reporting how many.

---

## 5. Build order, with the gate that decides whether any of it is worth having

1. **Clean the covariates** (§4). Report the discard count. This comes first because everything downstream
   inherits it.
2. **Extract**: `PPF20_RATE`, `PPF20_VOL`, `RFTN20_RATE`, `EXP_SEVO`, `EXP_DES`, temperature, and the six
   demographic fields. One pass; all confirmed present.
3. **Implement Eleveld propofol** (29661412 **+ corrigendum 30032904**) and **Eleveld remifentanil**
   (28509794).
4. **VALIDATION GATE, and it must pass before anything is trusted: reproduce the pump's own `PPF20_CE`
   from `PPF20_RATE` alone**, on the 3,511 cases carrying both. The pump computed its value independently,
   so this is a genuine external check on the implementation rather than a self-consistency test.
5. **Volatiles**: end-tidal → effect site with a first-order lag, then age-adjusted MAC fractions.
6. **Combine** on a common potency scale, with a Minto/Bouillon surface for the propofol–opioid pair only,
   and state plainly that no validated ≥3-drug surface exists.
7. **Then, and only then**, the question actually asked: does the EEG track a properly modelled combined
   effect-site exposure better than it tracks any single agent? E110 and E112 answered a weaker version
   (the exponent does not track propofol; a 20–40 Hz slope partly does), and E120 showed that adding
   remifentanil as a *covariate* changes nothing. None of them used a PK/PD model, and none could.

**What this will not deliver.** Cardiac output is not measured, so the single strongest clearance modifier
for propofol enters only as a vasopressor-use proxy. Free drug fraction has no validated clinical model to
plug albumin into even once the data is clean. And a three-drug interaction surface does not exist to be
implemented. A model built here will be more complete than what this project has used so far and still not
comprehensive, and saying which is which is part of the deliverable.
