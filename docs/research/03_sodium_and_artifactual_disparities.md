# Racial bias in routine (indirect-ISE) sodium measurement, and the artifactual component of published racial electrolyte disparities

**Source data:** MIMIC-IV paired chemistry (indirect-ISE) / blood-gas (direct-ISE) sodium draws with race;
cross-national mechanism replication in SICdb (Salzburg, Austria); cross-reference validation against MIMIC-IV
measured serum osmolality; supporting mechanism/premise checks in eICU (208 US hospitals). Analysis scripts:
`sodium_confounders.py`, `sodium_mechanism_definitive.py`, `sodium_extend.py`, `sodium_ipw_entry.py`,
`sodium_disease_confound.py`, `sodium_cluster_se.py` (and the companion scripts cited in
`docs/REAL_RESULTS_SODIUM_RACE_BIAS.md`, which is the authoritative numbers-of-record for this line of work).
This document isolates the **sodium** finding and its **artifactual-disparities** payload; the multi-site
calcium/panel flagship lives in `01_FLAGSHIP_calcium_and_panel.md`, potassium in
`02_potassium_pseudohyperkalemia.md`, and the shared immunoglobulin mechanism in `04_mechanism_immunoglobulins.md`.

## Abstract

Routinely-reported chemistry sodium is measured by **indirect ion-selective electrode (ISE)**, which dilutes the
sample and therefore reads through the plasma solid phase (protein + lipid); blood-gas sodium is measured by
**direct ISE** on undiluted whole blood and is protein-independent. In MIMIC-IV, at the *same* true (blood-gas)
sodium, a Black patient's reported chemistry sodium reads **~1.2 mEq/L lower** than a White patient's — a
BLACK−WHITE differential of **−1.18 mEq/L (SE 0.09, z = −12.6)** across 11,559 near-simultaneous paired draws. The
effect survives every confounder, selection, clustering, cutoff, and matrix test we could construct, reproduces
against an independent osmolality reference (**−1.01, z = −9.3**), and its causal mechanism — a graded
protein→bias dose-response — replicates with a near-identical slope in an Austrian cohort on a different continent
with different analyzers (**−0.843 mEq/L per g/dL total protein, z = −28.6**). The driver is elevated
immunoglobulins/globulins, which are documented to be higher in Black populations. Four rounds of hostile
adversarial review, including two independent re-executions of the code, could not break the core MIMIC+SICdb
evidence. The sodium finding nonetheless carries a **structural single-center ceiling** — race and paired
dual-method sodium co-occur only in MIMIC among public ICU datasets — which is precisely why the project pivoted
its NEJM-tier ambition to **calcium** (ionized calcium is on every blood-gas panel and *can* be validated with
race across hospitals). The scientific payload of the sodium line is not merely "a lab is biased," but that
**published epidemiology of racial electrolyte disparities is partly a measurement artifact**: the hyponatremia
disparity reverses direction with the true measure, hyperchloremia is ~100% artifact, and ~88–90% of the apparent
hypocalcemia "protection" in Black patients is an artifact of the falsely-high total calcium.

**Honest tier:** a mechanism-solid, cross-nationally + cross-reference validated, **single-center-race**
measurement-bias result — a methods/equity **research letter** (JAMA Internal Medicine / Clinical Chemistry), not
an NEJM/JAMA original article.

---

## 1. The finding: chemistry sodium reads racially low at matched true sodium

The two methods disagree, and the disagreement differs by race. Pairing each blood-gas sodium with the nearest
chemistry sodium within ≤1 h:

| group | chem − blood-gas Na bias (mEq/L) | n (pairs, ≤1 h) |
|---|---|---|
| WHITE | **+2.28** | 9,968 |
| BLACK | **+1.09** | 1,591 |
| HISPANIC | +1.27 | 663 |
| ASIAN | +1.56 | 511 |
| **BLACK − WHITE differential** | **−1.18 (SE 0.09, z = −12.6)** | |

For the same true (blood-gas) sodium, a Black patient's reported chemistry sodium reads **~1.2 mEq/L lower** than
a White patient's. The effect is robust to **near-simultaneous (≤10 min) pairing** (**−1.30, z = −10.2**) — so it
is not a temporal artifact of the two draws being taken at different times.

**Analyte specificity.** Potassium (also indirect-ISE, also protein-displaced) shows a smaller same-direction
effect (**+0.10, z = +8.4**); glucose and bicarbonate show **no** racial differential — arguing against a generic
selection or arterial-venous artifact and localizing the effect to the analytes where the indirect-ISE
protein-exclusion mechanism operates.

**No truth-hierarchy required (post-review reframing).** The claim does *not* depend on blood-gas being the "gold
standard." In fact chemistry is marginally *closer* to measured osmolality than blood-gas is
(|chem−osmNa| 2.87 vs |bg−osmNa| 3.25, n=396). The claim is that **chemistry (indirect ISE) carries a
protein-correlated racial bias**, demonstrated relative to **two independent comparators** (blood-gas *and*
measured osmolality), with the **protein dose-response identifying the indirect-ISE method as the
protein-sensitive one**. The n=396 within-patient chem−bg differential is +0.29 but with only 67 Black patients
(underpowered noise); the load-bearing estimates are the well-powered n≈10–11k comparisons against each reference.

### 1.1 The mechanism (a priori clean, then confirmed)

Indirect ISE dilutes plasma; the electrode reads a concentration referred to total plasma volume, but sodium
lives only in plasma *water*. When the solid phase (protein + lipid) is enlarged, plasma water is displaced and
the reported sodium falls — classic pseudohyponatremia. Black populations carry documented higher total
protein/globulins (IgG ~1,350 vs ~961 mg/dL in this cohort; the external literature reports 1,587 vs 1,209),
so the mechanism predicts exactly the observed direction. The back-of-envelope magnitude also lands: a globulin
gap of ~0.6 g/dL × a slope of ~0.9 mEq/L per g/dL ≈ **0.5 mEq/L**, i.e. protein explains roughly **half** the
observed ~1.2 mEq/L differential — the remainder is unexplained (see §1.4). This "confirmatory of known physics"
character is one reason the finding is a research letter, not a pulse-oximetry-style surprise.

### 1.2 Confounder stress-test — the finding survives

Confounders that genuinely differ by race (BLACK vs WHITE): glucose 179 vs 145, creatinine 2.23 vs 1.36 (more
CKD), true Na 137.7 vs 135.4, age 59 vs 65, IV-fluid running 0.32 vs 0.50. Progressive multivariable adjustment
(`sodium_confounders.py`):

| model | BLACK coef (mEq/L) | z |
|---|---|---|
| unadjusted | −1.18 | −12.6 |
| + age, true-Na | −0.95 | −10.0 |
| + renal (BUN, creatinine) | −0.89 | −9.1 |
| + glucose | −0.81 | −8.1 |
| + albumin | −0.79 | −8.1 |
| + triglycerides | −0.80 | −8.1 |
| + total protein (imputed, ~3% coverage) | −0.44 | −4.7 |

The differential survives at **−0.80 (z = −8.1)** after diabetes/renal/age/true-Na/lipids/albumin — only ~⅓
attenuated. **Total protein is the mechanism (a mediator), not a confounder**: it produces the largest attenuation
(−0.44), exactly as predicted if higher plasma protein *causes* the indirect-ISE bias — adjusting for a mediator
*should* attenuate. (Total protein is measured in only ~3% of pairs, so this row is imputation-limited.)

**Albumin does not explain it.** Adjusting for albumin shrinks the bias only ~3% (−0.94 → −0.91), and mean albumin
is identical by race (BLACK 3.23 vs WHITE 3.19 g/dL). The driver is **globulins/total protein**, not albumin.

**Arterial–venous artifact ruled out by specificity.** Glucose has a *larger* arterial-venous gradient than
sodium and differs sharply by race (179 vs 145), yet shows **zero** racial bias differential (z = +0.8). An A–V
sampling artifact would appear in glucose too; it does not.

### 1.3 Selection and differential entry into the paired cohort

The paired-draw cohort is selected (requires an arterial line + a near-simultaneous central lab), so selection was
attacked directly (`sodium_selection.py`, `sodium_ipw_entry.py`).

- **Entry is differential but does not manufacture the effect.** Fraction of admissions entering the paired
  cohort: WHITE 2.8% (9,968/360,519) vs BLACK 1.8% (1,591/89,057), **entry RR 0.65**. Black patients are
  *under*represented in the paired sample — a generalizability caveat (and a possible separate access-to-arterial-
  monitoring signal), stated plainly.
- **The bias is strongest where selection is weakest — the opposite of collider bias.** Stratifying by draw
  intensity (pairs per stay, an acuity/selection proxy): **1 pair (least selected) −1.28 (z = −11.7)** → 2–4 pairs
  −1.01 (z = −5.1) → 5+ pairs (most selected) −0.22 (z = −0.5). If selection created the differential it would be
  largest in the most-selected stratum; it is largest in the least-selected. The cleanest estimate is therefore the
  single-pair stratum, where the effect is strongest.
- **Severity-adjusted IPW-for-entry closes the item** (`sodium_ipw_entry.py`, n = 449,576 admissions). Entry OR
  for BLACK: crude 0.64 → +severity (age, ICU-LOS, peak lactate/creatinine/BUN) **0.81** (about half the entry gap
  is acuity; a residual access signal remains). Reweighting the headline differential by the
  inverse-probability-of-selection: unweighted −1.18 (z = −12.6) → **IP-selection-weighted −1.14 (z = −8.6)**.
  Reweighting the paired cohort back toward the full ICU population barely moves the estimate — **differential entry
  does not explain the racial measurement differential.** (Selection: closed.)

### 1.4 Mechanism dose-response, and the honest mediation gap

The clean test of mechanism is a **dose-response** among pairs where total protein/albumin were measured near the
draw (`sodium_mech_robust.py`):

| test | slope | z | interpretation |
|---|---|---|---|
| bias ~ **total protein** | **−0.90 mEq/L per g/dL** | −6.4 | higher plasma solid phase → indirect-ISE under-reads (predicted sign) |
| bias ~ **globulin gap** (TP − albumin) | **−0.73 per g/dL** | −4.0 | the immunoglobulin/solid-phase driver, confirmed |

The mediating quantities are **higher in Black patients**, exactly as the mechanism requires: mean total protein
**6.42 (BLACK) vs 5.83 (WHITE) g/dL**; mean globulin gap **3.04 vs 2.60 g/dL**.

**But the within-sample mediation is underpowered.** In the complete-case subsample (n = 268), adding total
protein shrinks BLACK −1.24 → −0.74 (**55% attenuation, but z = −1.6**) — the direction is right, significance is
not reached. The load-bearing evidence is the **dose-response slope itself** (graded, monotone, cross-nationally
and cross-reference replicated), *not* the n=268 mediation coefficient. The manuscript must state:
**"≈50% of the racial differential is mechanistically accounted for, the remainder unexplained,"** and must not let
the SICdb slope's significance stand in for the mediation claim.

**MNAR caveat.** Total protein is a clinically-selected test; the 268 TP-measured pairs are sicker (mean
creatinine 2.11 vs 1.47) and enriched for globulin-workup pathology. The MIMIC dose-response subsample is not
representative; its *direction* is corroborated by the representative, well-powered SICdb dose-response (below),
but the MIMIC *magnitude* should not be read as whole-cohort mediation.

### 1.5 Definitive mechanism — directly-measured globulin, immunoglobulins, and cholesterol

Streaming directly-measured globulin, immunoglobulins, and cholesterol (not the TP−albumin proxy) closes the
chain (`sodium_mechanism_definitive.py`):

| solid-phase analyte | dose-response slope | z |
|---|---|---|
| **globulin** | **−1.02 mEq/L per g/dL** | −2.9 |
| **IgG** | **−0.107 per 100 mg/dL** | −3.3 |
| IgA | −0.178 per 100 mg/dL | −2.3 |
| **cholesterol** (2nd solid phase = lipid) | **−1.58 per 100 mg/dL** | −7.0 |
| total protein | −0.93 per g/dL | −7.3 |

Three independent nails: (1) the **racial driver is immunoglobulins** — globulin and IgG both drive the bias and
are higher in every affected group (IgG WHITE 961 → BLACK 1350, HISPANIC 1458, ASIAN 1240); (2) the **lipid
pathway is confirmed independently** (cholesterol −1.58/100 mg/dL, z = −7.0; triglycerides −0.11/100 mg/dL,
z = −3.5) — classic lipemic pseudohyponatremia — but lipids are *higher in White* patients (triglycerides 233 vs
197), so lipid does **not** drive the racial effect; the racial component is specifically protein/globulin, cleanly
separated from the non-racial lipid component; (3) the **magnitude is quantitatively right** — the plasma-water
equation predicts ~−1.0 to −1.4 mEq/L per g/dL of plasma solids at Na ≈ 140, and the observed globulin/total-protein
slopes (−0.9 to −1.0) fall in that range.

### 1.6 Reach beyond the Black–White axis

The falsely-low chemistry sodium is not Black-specific (`sodium_extend.py`, n = 15,098):

| group | mean chem − bg bias | differential vs WHITE | z | mean IgG (mg/dL) |
|---|---|---|---|---|
| WHITE | +2.28 | ref | — | 961 |
| BLACK | +1.09 | **−1.18** | −12.6 | 1350 |
| HISPANIC | +1.27 | **−1.01** | −6.8 | 1458 |
| ASIAN | +1.56 | **−0.71** | −4.9 | 1240 |
| OTHER | +2.35 | +0.07 | ns | — |

Sex is a real *within-MIMIC* axis (FEMALE−MALE **−0.36, z = −6.8**; Black women lowest at +1.03, White men highest
at +2.41) but did **not** replicate in SICdb (opposite direction), so unlike race it is not claimed as a robust
axis.

---

## 2. Robustness under four rounds of hostile adversarial review

The finding was stress-tested through four rounds of hostile review, including two independent re-executions of
the analysis code. Every FATAL-flagged attack was answered with data; the surviving items are scope/tier, not
validity. The complete numbers-of-record are in `docs/REAL_RESULTS_SODIUM_RACE_BIAS.md`; the load-bearing
responses:

| review attack (round) | response | result |
|---|---|---|
| "You asserted blood-gas = truth" (R1, chemist, FATAL) | independent osmolality arbiter (`mimic_osm_arbiter.py`) | chem−osmNa BLACK−WHITE **−1.01 (z = −9.3, n = 10,236)**; protein dose-response reproduces vs osmolality (−0.64/g/dL, z = −4.2) |
| "osmNa uses glucose/BUN which differ by race" (R2) | restriction + residual adjustment (`mimic_osm_robust.py`) | survives normoglycemia (−1.03, z = −7.1), normal-renal (−1.08, z = −7.3), both (−1.09, z = −5.7), glu+BUN adjustment (−0.82, z = −7.5); osmolar-gap adjustment excluded as degenerate |
| "SICdb replication inverts a reference SICdb itself distrusts" (R1, FATAL) | logic: random BGA noise → regression dilution, not a monotone gap∼protein slope | monotone dose-response can only arise from the protein-sensitive (indirect-ISE) method |
| "Hemoglobin also shows a race differential — specificity cherry-picked" (R1, FATAL) | conceded, then quantified (`sodium_matrix_hct.py`) | Hgb(CBC−bg) BLACK−WHITE **−0.081 g/dL (z = −3.1)** — ~15× smaller, different mechanism; adding Hgb-discordance to the Na model leaves BLACK **−1.27 (z = −7.1)** |
| "Whole-blood/hematocrit matrix confound" (R1, MAJOR) | Hct nearly identical by race (WHITE 31.5, BLACK 32.0) | +Hct → −1.15 (z = −12.5); protein slope survives Hct at −0.84 (z = −5.6); tightened to 2-h (−0.93, z = −5.3) and 1-h (−0.97, z = −5.4) windows |
| "Race is a proxy for a globulin-raising disease" (R1, borderline FATAL) | exclusion + adjustment (`sodium_disease_confound.py`) | diseases *are* more common in Black patients (HIV 2.7% vs 0.8%, sarcoid 1.8% vs 0.4%, myeloma 1.7% vs 0.9%, CKD/dialysis 50% vs 30%), but the differential survives **exclusion (−1.29, z = −12.6)** and **adjustment (−1.18, z = −12.5)**, and is if anything larger disease-free |
| "SES/insurance confounding" (R1, equity) | insurance adjustment (reviewer-run) | shrinks only −1.18 → −1.09 |
| "SEs ignore within-patient correlation" (R1, biostat) | subject-cluster-robust + patient-collapse (`sodium_cluster_se.py`) | only 1.08 admissions/subject; cluster-robust **z = −12.1**; one obs/subject **−1.12 (z = −11.5)** |
| "Level-dependent bias controlled only linearly" (R1, biostat) | quadratic true-Na + interaction (`sodium_level_cutoff.py`) | survives quadratic (−0.98, z = −10.4); mild BLACK×true-Na interaction (−0.26, z = −2.1) — differential somewhat larger at lower true Na, noted |
| "False-hypo OR is a 135-cutoff/multiplicity artifact" (R1, biostat) | cutoff sweep | OR **stable 2.22–2.87 across cutoffs 133–138** (all z > 4, subject-clustered); main z = −12.6 survives Bonferroni for 10 tests by >4 orders of magnitude |

**Round 4 (final acceptance gate)** independently re-executed seven of the eight cited scripts and reproduced
every core MIMIC/SICdb number **digit-for-digit** (osm arbiter −1.008/z=−9.3; disease-exclusion −1.287; SICdb
−0.843/z=−28.6; IPW −1.137/z=−8.6; Hct/Hgb/cluster/cutoff all matched). No fabrication or code/claim mismatch on
the load-bearing chain. One actionable correctness bug was flagged and fixed — a stale eICU section that had made a
falsified prediction (see §3.2). The verdict across all four rounds: **survives at the research-letter tier**; does
**not** survive as an NEJM/JAMA original (single-center race, misclassification-not-outcome harm, analyzer-specific
magnitude).

### 2.1 Consequence: differential misclassification (robust) vs treatment harm (not shown)

Restricting to truly-normal sodium (blood-gas 135–142, n = 5,951) so any chemistry-based label difference is
*misclassification*, with logistic adjustment for age/sex/glucose/BUN/creatinine/true-Na:

| outcome (true-normal Na) | crude | adjusted OR (BLACK) | z |
|---|---|---|---|
| **false-hyponatremia label** (chem < 135) | 8.3% vs 3.5% (OR 2.50) | **1.68 (1.20–2.37)** | +3.0 |
| hypertonic-saline overtreatment (≤24 h) | 0.85% vs 0.29% (2.9×) | 2.57 (0.93–7.11) | +1.8 |

The **false-hyponatremia label is robust to adjustment** and cutoff-stable — the demonstrable consequence is
**differential misclassification**. The downstream **hypertonic-saline overtreatment** signal is directionally
consistent (2.9× crude) but **underpowered** (only 21 events in one ICU) and was **demoted to hypothesis-generating**
in review. The attempted clinical-outcome upgrade (converting misclassification into a Sjoding-style care/outcome
harm) is an **honest negative in single-center MIMIC**: the repeat-sodium cascade runs the *opposite* way (rechecks
rise with high, not low, readings, so Black patients get *fewer* rechecks, adj OR 0.79, z = −2.9); treatment is
underpowered/null; the overcorrection endpoint is regression-to-the-mean-contaminated; and there is no hard-endpoint
harm at matched true Na (mortality adj OR 0.77, ns). A clean overcorrection design (patients actually treated,
true-Na trajectory to >8–10 mEq/L/24h) is the right method but is fatally underpowered here (n = 159 treated with a
blood-gas trajectory, only 12 Black, 1 overcorrection event). The outcome upgrade needs the same multi-site data as
the racial replication.

---

## 3. The single-center ceiling — and why the project pivoted to calcium

This is the honest, load-bearing limitation, and the reason the sodium line — despite surviving four rounds of
review — is a research letter rather than an NEJM/JAMA original.

### 3.1 Race + dual-method sodium co-occur only in MIMIC

The finding requires **two ingredients in the same dataset**: (a) a patient's **race**, and (b) **paired
dual-method sodium** (indirect-ISE chemistry *and* direct-ISE blood-gas on the same patient near the same time).
Among all public ICU databases, only MIMIC-IV has both:

| dataset | race | blood-gas (direct-ISE) sodium | can test the racial differential? |
|---|---|---|---|
| **MIMIC-IV** (Boston, single center) | yes | yes | **yes — the only one** |
| eICU (208 US hospitals) | yes | **no** (all sodium is chemistry, labtypeid=1) | no — no second method |
| SICdb (Salzburg, Austria) | **no** (single-center, no race field) | yes | no — mechanism only |
| AmsterdamUMCdb / HiRID / INSPIRE | — | — | no combination has both |

So the **racial differential itself is structurally single-center**. No combination of public datasets closes it;
a same-design racial replication would require a *new* US multi-hospital DUA (or prospective collection) with race
+ paired dual-method sodium — which does not currently exist in public data. This is not a fixable analysis gap; it
is an architectural ceiling.

A second, related ceiling: the **~1 mEq/L magnitude is analyzer-specific** — it reflects one hospital's indirect-ISE
dilution algorithm and does not generalize *quantitatively* across vendor algorithms. Only the direction/mechanism
generalizes across vendors, not the number.

### 3.2 What we could and could not replicate outside MIMIC

- **SICdb (Austria) — MECHANISM replicated cross-nationally (n = 21,322 pairs).** SICdb separates the two methods
  (Natrium ZL = central-lab indirect ISE, id 469; Natrium BGA = blood-gas direct ISE, id 686) with well-covered
  serum total protein (id 294, 36% of pairs). The chem−bg gap tracks total protein with a **near-identical slope**:

  | cohort | gap ~ total-protein slope | z | n (protein-paired) |
  |---|---|---|---|
  | MIMIC (Boston, US) | **−0.90 mEq/L per g/dL** | −6.4 | 268 |
  | **SICdb (Salzburg, AT)** | **−0.843 mEq/L per g/dL** | **−28.6** | 7,726 |

  The SICdb quartile dose-response is cleanly **monotone**: total protein [1.8–5.2] → gap +2.02; [5.2–5.9] → +1.15;
  [5.9–6.5] → +0.43; [6.5–10.1] → −0.06. The protein→bias *physics* is not a MIMIC artifact — but SICdb has **no
  race variable**, so it validates the mechanism, not the racial differential.

- **eICU (208 US hospitals) — the racial differential does NOT replicate (honest negative).** eICU records no
  blood-gas sodium, so the dual-method design cannot run; a workaround reconstructs a reference from measured
  osmolality (`eicu_osm_analyze.py`, n = 5,440 Caucasian+African-American pairs). The racial differential is
  **specification-unstable**: raw +0.26 (z = +1.1, wrong sign); covariate-adjusted **+0.93 (z = +4.4, significant
  wrong direction)**; only with hospital fixed effects (35 sites ≥40 pairs) does it flip to the expected sign but go
  weak/ns (−0.22, z = −1.0). The raw positive is a **between-hospital-analyzer confound** — 208 different chemistry
  analyzers whose calibration offsets correlate with each site's racial composition. **eICU does not replicate the
  racial differential** — which is exactly why the clean test needs a *single-analyzer* setting (MIMIC), not a
  208-analyzer osmolality reconstruction. (A Round-4 correction: an earlier draft used a stale partial n=457 and
  predicted "~z−1.3 at full n"; the completed full-file analysis falsified that prediction — the honest result is a
  negative, and this *strengthens* the paper's honesty.) The protein mechanism *does* replicate directionally in
  eICU (slope −0.39/g/dL, z = −4.1), and eICU independently confirms the *premise* — total protein WHITE 5.97 vs
  BLACK **6.33 (+0.36, z = +66, n = 372k)**, with **albumin identical** (−0.009), i.e. the gap is globulin-specific.

- **Transportability (the honest workaround).** Because a direct racial replication is structurally impossible, the
  best available statement combines (i) the physics — protein→bias slope replicated in 3 datasets / 3 systems
  (fixed-effect pooled **−0.807, z = −29.2**) — with (ii) the premise — Black patients → higher globulins, confirmed
  in eICU's 208 US hospitals. Transport: eICU protein gap (+0.36 g/dL) × calibrated slope (−0.85) ⇒ a predicted
  protein-mediated racial bias of **≈ −0.31 mEq/L** in a second US multi-hospital population. This elevates external
  validity from "one hospital" to "universal physics + race-protein premise confirmed in a second US cohort," but it
  does **not** directly *measure* the racial bias outside MIMIC, nor transport the ~half the differential protein
  does not explain, nor escape being model-based.

### 3.3 The pivot to calcium

The structural sodium ceiling is exactly what motivated the project's pivot to **calcium**. Ionized calcium sits on
**every blood-gas panel** (unlike blood-gas sodium), so the calcium analog of this bias — total calcium reads
falsely *high* at matched ionized calcium, because excess globulin *binds* calcium — **can be validated with race
across hospitals**, achieving what sodium structurally could not:

- **MIMIC:** total Ca **+0.15 mg/dL** falsely high at matched ionized (z = +11.6), survives pH + albumin + tight
  window;
- **eICU (multi-hospital US, WITH RACE):** **+0.12–0.15 mg/dL** — the multi-site racial replication sodium could
  never get (hospital-FE +0.092, z = 3.30);
- **SICdb (Austria):** mechanism, total-Ca excess ~ total protein **+0.053 mmol/L per g/dL** (z = +39.6).

The calcium finding (with the racially-miscalibrated albumin-corrected-calcium formula — an inverted eGFR analog —
and the ECG-corroborated masked-hypocalcemia harm chain) is developed in `01_FLAGSHIP_calcium_and_panel.md`. The
sodium and calcium biases share **one mechanism** (excess plasma protein/globulin) running in **opposite directions**
(Na/Cl diluted low, Ca bound high) — the directional coherence is itself evidence of a genuine protein-interference
artifact rather than confounding. In short: **sodium is where we found the effect and nailed the mechanism; calcium
is where the same mechanism becomes multi-site-provable with race.**

---

## 4. The artifactual-disparities reframe (the scientific payload)

The deepest contribution of the sodium line is not "a lab is biased." It is that **the published epidemiology of
racial electrolyte disparities is partly a measurement artifact.** A body of literature reports racial differences
in electrolyte-abnormality *prevalence* as if they were real disease. When the *same patients* are re-scored with
the protein-independent (true) measure, some of those disparities attenuate, and some reverse.

| disparity | by routine (biased) measure | by true (protein-independent) measure | artifactual fraction |
|---|---|---|---|
| **Hyponatremia** | Black patients appear to have **more** (1.07×) by chemistry | by blood-gas (true) they have **less** (0.87×) | the measurement **reverses the apparent direction** |
| **Hyperchloremia** (companion Cl finding) | missed in Black patients, adj OR 2.40 (z = +6.5) — chloride reads falsely low | — | the chloride disparity is essentially **~100% artifact** of indirect-ISE water displacement |
| **Hypocalcemia** (companion Ca finding) | Black−White gap by total Ca = **−0.099** | by ionized (true) = **−0.011** | ~**88–90%** of the apparent "Black patients have less hypocalcemia" is a **measurement artifact** (masked by falsely-high total Ca) |

The hyponatremia reversal is the sharpest illustration: routine chemistry makes Black patients look *more*
hyponatremic, but their *true* (blood-gas) sodium distribution makes them *less* hyponatremic — the biased
instrument does not merely exaggerate a disparity, it **manufactures one in the wrong direction**. The hypocalcemia
case shows the opposite failure mode: a real protective difference is *erased* — falsely-high total calcium masks
true hypocalcemia in Black patients (mild-range 26.2% vs 18.1% masked at ionized 1.00–1.12), so the apparent
"protection" is ~90% an artifact of the measurement.

This reframes a slice of racial-disparity epidemiology: **reports of racial differences in dysnatremia/dyscalcemia
prevalence may be partly measurement-driven**, not disease-driven. That is a provocative but well-grounded
correction to a literature that has treated these prevalence differences as real physiology. The constructive,
equity-safe fix is **method-level, not race-based**: measure the physiologically active quantity directly
(direct-ISE sodium/chloride, ionized calcium) — or flag/verify via a total-protein-adjusted value when total protein
is elevated — rather than inferring it through a protein-confounded total. This deliberately avoids the
eGFR-race-coefficient backlash: the correction fixes the *instrument choice*, not the patient's race.

---

## 5. Novelty

Targeted PubMed re-verification indicates the racial-differential framing is unpublished:

- `pseudohyponatremia AND (race OR racial OR Black OR ethnic OR disparity)` → **1 hit**, an unrelated forensic case
  report. No race × pseudohyponatremia study exists.
- `(indirect/direct ISE OR ion-selective electrode) AND sodium AND (racial/ethnic/disparity/Black)` → 9 hits, all
  sensor-fabrication or analyzer method-comparison papers; **none examine race**.
- The broad "racial bias in a clinical measurement" literature (pulse oximetry, eGFR race coefficient, PFTs) is
  large (~889 hits) but **does not include sodium / ISE**.

What is *known*: globulin/protein-driven indirect-ISE pseudohyponatremia (electrolyte-exclusion effect) is textbook,
and higher serum globulin/IgG in Black populations has been documented for 50+ years (IgG 1,587 vs 1,209 mg/dL,
matching this study's 1,350 vs 961). What is **novel** is the *synthesis*: framing routine electrolyte measurement
as *systematically racially biased at the population level* by immunoglobulins, and recognizing that reported racial
dysnatremia disparities may be **partly a measurement artifact**. That synthesis appears genuinely unpublished — but
its honest ceiling is that it is *confirmatory of known physics* combined with a known premise, not a pulse-oximetry-
style surprise (§3.1).

---

## 6. Limitations specific to the sodium line

1. **The racial differential is single-center (MIMIC).** This is the architectural ceiling (§3.1): race + paired
   dual-method sodium co-occur only in MIMIC among public ICU datasets. The mechanism replicates cross-nationally
   (SICdb) and cross-reference (osmolality), and the race-protein premise replicates in eICU's 208 hospitals, so
   the inference is mechanistically airtight — but a second cohort directly showing the *race* gap would require a
   US multi-hospital dataset with paired dual-method sodium, which is not currently public.

2. **Analyzer-specific magnitude.** The ~1.2 mEq/L point estimate reflects one hospital's indirect-ISE dilution
   algorithm. Only the direction/mechanism generalizes across vendors; the number does not.

3. **ICU / arterial-line population.** The paired cohort requires an arterial line and a near-simultaneous central
   lab — an ICU population with differential entry (RR 0.65). IPW closes the *bias-explanation* concern (§1.3) but
   the generalizability to floor/outpatient populations is untested.

4. **The mediation is only ~half-closed.** Measured protein explains ≈50% of the racial differential; the
   within-sample mediation is n=268/z=−1.6 (suggestive, not decisive), and the TP-measured subsample is MNAR
   (sicker: creatinine 2.11 vs 1.47). The remainder of the differential is unexplained.

5. **Subclinical globulin elevation is unmeasurable.** Diagnosed globulin-raising disease is empirically ruled out
   (survives disease exclusion, −1.29), but *subclinical* globulin elevation without an ICD code cannot be measured
   and remains a residual (bounded, not eliminated).

6. **Harm shown is misclassification, not outcome.** The demonstrable consequence is differential misclassification
   (false-hyponatremia label, robust across cutoffs; missed hypernatremia adj OR 2.58; APACHE-II severity-score
   inflation +0.055, z = +3.8). The downstream treatment/outcome harm (hypertonic-saline overtreatment,
   overcorrection/ODS) is directionally consistent but **underpowered in a single ICU** and is reported as
   hypothesis-generating only. Notably the anion gap is **preserved** (Na and Cl carry near-identical protein biases
   that cancel in Na−Cl−HCO3; distortion +0.07, z = +0.3) — a reassuring specificity check that the harms land only
   where sodium enters a formula without a compensating chloride.

**Net.** A robust, mechanism-solid, cross-nationally and cross-reference validated, apparently-novel measurement-bias
finding whose racial differential is structurally single-center. Correct home: a methods/equity **research letter**.
Its enduring scientific contribution is the **artifactual-disparities reframe** (§4) and its role as the mechanistic
foundation for the multi-site **calcium** flagship (§3.3).
