# Racial bias in routine potassium measurement: a distinct, hemolysis-associated pseudohyperkalemia

**Source data:** MIMIC-IV paired chemistry–blood-gas draws (`potassium_rigor.py`, n=20,200 pairs); ECG
corroboration from MIMIC-IV-ECG (184,000 of ~800,000 waveforms extracted; `extract_ecg.py`, `ecg_link.py`).
This document isolates the potassium finding from its companion sodium/chloride/calcium work
(`docs/REAL_RESULTS_SODIUM_RACE_BIAS.md`), because the two biases run in **opposite directions** and arise
from **different physical mechanisms**.

## Abstract

Routinely-reported chemistry (serum) potassium reads systematically **higher** than simultaneously-drawn
blood-gas (whole-blood) potassium, and the excess is significantly larger in Black patients: a racial
K-bias differential of **+0.124 mEq/L (z = +9.2)** that survives adjustment for creatinine, age, and true
(blood-gas) potassium (**+0.122, z = +8.8**) and a tight 10-minute pairing window (**+0.125, z = +7.3**).
The clinical consequence is **false hyperkalemia**: among patients whose true (blood-gas) potassium is
normal (3.5–5.0 mEq/L), a Black patient's chemistry potassium is flagged ≥5.5 mEq/L in **13.5%** of draws
versus **6.3%** in White patients — an adjusted odds ratio of **2.36 (95% CI 2.01–2.76, z = +10.6)**,
subject-clustered. Masked (missed) *true* hyperkalemia is **not** elevated in Black patients — the
disparity is in false alarms, not in missed lethal hyperkalemia. Unlike the companion sodium/chloride/
calcium findings, this bias is **uncorrelated with the plasma-protein pathway** (r = −0.19 with the sodium
protein-bias) and runs in the **opposite sign** from what protein-exclusion would predict, pointing instead
to a pre-analytic, hemolysis-type mechanism. A quantitative ECG hyperkalemia signature partially
corroborates that false-flagged events are physiologically spurious. Because potassium is among the
most-ordered chemistry tests and false hyperkalemia triggers active treatment, this is plausibly the
highest immediate-harm finding in this research program — but several links in the harm chain remain
untested and are stated as open below.

## 1. The finding

| quantity | value | z |
|---|---|---|
| Racial K-bias differential (chem − blood-gas K, BLACK vs WHITE) | **+0.124 mEq/L** | **+9.2** |
| ...adjusted for creatinine, age, true (blood-gas) K | +0.122 mEq/L | +8.8 |
| ...restricted to a tight ≤10-min pairing window | +0.125 mEq/L | +7.3 |

The direction is opposite to sodium and chloride: those read **falsely low** in Black patients (protein
water-displacement); potassium reads **falsely high**. The effect is not explained by chronic kidney
disease (creatinine-adjusted) or by the time gap between the two draws (10-minute window).

## 2. Clinical consequence: false hyperkalemia

Restricting to patients whose **true (blood-gas) potassium is normal** (3.5–5.0 mEq/L) isolates
misclassification from real physiology. Among these patients:

| group | false hyperkalemia (chem ≥ 5.5 at true-normal K) |
|---|---|
| BLACK | **13.5%** |
| WHITE | **6.3%** |
| adjusted OR (BLACK), subject-clustered | **2.36 (95% CI 2.01–2.76, z = +10.6)** |

A Black patient with a genuinely normal potassium is more than **twice as likely** to have that potassium
misreported as dangerously high. Critically, **masked true hyperkalemia is not elevated** in Black
patients — this is a false-alarm disparity, not an under-detection disparity. That asymmetry matters for
framing: the harm this finding implies is over-treatment, not missed lethal hyperkalemia.

## 3. Mechanism: distinct from the sodium/globulin pathway

The companion sodium, chloride, and calcium biases documented in `REAL_RESULTS_SODIUM_RACE_BIAS.md` are all
driven by one mechanism — elevated plasma globulins/immunoglobulins (higher in non-white populations)
displacing plasma water on indirect-ISE assays (Na, Cl fall) or binding calcium (total Ca rises). Three
observations rule this pathway out for potassium:

1. **Uncorrelated with the sodium protein-bias.** The K-bias correlates with the Na protein-bias at
   **r = −0.19** — essentially unrelated, and if anything weakly opposite.
2. **Wrong sign for protein exclusion.** If elevated globulin were displacing plasma water the way it does
   for sodium and chloride, chemistry potassium should read **low**, not high. It reads **high**.
3. **Direction matches pre-analytic hemolysis, not protein chemistry.** Potassium is the electrolyte most
   sensitive to red-cell/platelet lysis and clotting-related release during and after a venous draw
   (a serum-vs-whole-blood pseudohyperkalemia). Blood-gas potassium — drawn from an arterial line, run
   whole-blood, direct-ISE, essentially immediately — is not exposed to that artifact and is the better
   estimate of true potassium.

The working hypothesis is therefore **pre-analytic: hemolysis, clotting, platelet release, or transport
delay** in the venous chemistry sample, occurring more often in Black patients — plausibly reflecting
**draw-difficulty, vascular-access, or specimen-transport factors** (structural care-delivery variables)
rather than any patient physiology or protein chemistry. This is stated as the leading hypothesis, not a
confirmed mechanism (see Limitations).

The general phenomenon that indirect-ISE methods can show electrolyte discrepancies for potassium as well
as sodium and chloride is separately described in the analytic-methods literature, though there it is
attributed to protein/lipid exclusion and is "rarely clinically significant" for K
([J Lab Physicians](https://jlabphy.org/discrepancies-in-electrolyte-measurements-by-direct-and-indirect-ion-selective-electrodes-due-to-interferences-by-proteins-and-lipids/)).
That mechanism is the wrong sign and magnitude for what is observed here (see point 2 above), which is why
this finding is presented as mechanistically distinct — a pre-analytic/hemolysis artifact, not a
protein-exclusion artifact.

## 4. ECG corroboration (partial, honestly bounded)

A quantitative hyperkalemia ECG signature (`potassium_ecg.py`-style analysis, 184,000 extracted ECGs)
provides independent physiological support that the false-flagged events are spurious. Comparing ECGs
linked to **true** hyperkalemia (blood-gas confirmed) against ECGs linked to **false** hyperkalemia
(chemistry-flagged, blood-gas normal):

| ECG feature | true hyperkalemia | false hyperkalemia |
|---|---|---|
| wide QRS (>110 ms) | **27.4%** | 17.6% |
| long PR (>200 ms) | 13.5% | 7.7% |
| **P-wave loss** | **24.5%** | **8.8%** |
| QTc | 446 ms | 452 ms (shorter) |

True hyperkalemia shows substantially more of the classic electrophysiologic signature (wide QRS, long PR,
P-wave loss) than false hyperkalemia does. Because false-hyperkalemia events lack the electrical changes
that real hyperkalemia produces, the ECG **supports** the interpretation that they are pseudo-events rather
than true (if transient) hyperkalemia. The separation is real but **modest**, which matches prior
literature: ECG is intrinsically an insensitive arbiter of hyperkalemia, especially in chronic/CKD
patients ([LITFL](https://litfl.com/hyperkalaemia-ecg-library/)). An earlier attempt using the ECG
machine's categorical "peaked-T/hyperkalemia" diagnostic statement was uninformative — it fires in only
**0.5%** of true hyperkalemia (and 0% of false hyperkalemia) — too insensitive at that resolution to
arbitrate; the quantitative wide-QRS/PR/P-wave measures above are what carry the (partial) corroboration.
A full re-extraction of the 800k-ECG set with raw T-wave amplitude would sharpen this further but has not
been completed.

## 5. Why this may be the highest-impact finding in the research program

Potassium is among the most frequently ordered chemistry tests in acute care, and a chemistry-flagged
hyperkalemia routinely triggers **active emergency treatment**: insulin/dextrose (risk: hypoglycemia),
IV calcium, sodium polystyrene sulfonate/kayexalate (risk: colonic necrosis), urgent dialysis, continuous
ECG monitoring, and delays to other care while the "emergency" is worked up. A **2.36×** excess of false
alarms in Black patients — landing on a lab drawn essentially universally in hospitalized patients — is a
large, concrete, and directly actionable patient-safety disparity. The proposed fix is **method/process
level**: confirm chemistry-flagged hyperkalemia with a blood-gas/whole-blood potassium before treating, and
address specimen-handling factors (draw technique, tourniquet time, transport time) that predispose to
hemolysis — not a race-based clinical rule.

## 6. Honest limitations

- **The hemolysis mechanism is a hypothesis, not a confirmed measurement.** No free-hemoglobin or LDH
  hemolysis index was available in this dataset to directly test it; the case for pre-analytic hemolysis
  rests on the sign/mechanism exclusion argument in Section 3 (wrong direction and no correlation with the
  protein pathway), not on a direct biomarker.
- **The harm chain is not yet fully tested.** The proposed downstream cascade — false hyperkalemia →
  treatment (insulin/dextrose, kayexalate, dialysis) → treatment-attributable harm (e.g., hypoglycemia from
  insulin/dextrose given for a pseudo-event) — has not been analyzed end-to-end in this dataset. This
  document reports the measurement bias and the misclassification consequence, which are validated; the
  treatment-harm linkage is a proposed next step, not a demonstrated result.
- **Masked true hyperkalemia is not elevated.** To be clear about what is *not* shown: this is not a
  finding about missed, dangerous hyperkalemia in Black patients. The harm implied here is iatrogenic
  (treating a false positive), not a failure to detect real hyperkalemia.
- **ECG corroboration is partial.** The quantitative ECG separation between true and false hyperkalemia is
  real but modest, consistent with the broader literature that ECG is not a sensitive hyperkalemia
  detector; it should be read as directionally supportive, not as a decisive arbiter.
- **Single-center.** As with the companion sodium finding, this analysis is drawn from one hospital system
  (MIMIC-IV); whether the same racial differential in pre-analytic hemolysis/handling generalizes to other
  hospitals and phlebotomy practices has not been tested here.
