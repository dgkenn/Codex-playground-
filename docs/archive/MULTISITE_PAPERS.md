# Two multi-site papers (MIMIC-IV + SICdb [+ eICU where possible])

Data assembled: MIMIC-IV (US academic, ~65k ICU), SICdb v1.0.8 (Austria, ~27k ICU, access CONFIRMED under
`deankennedy`, files downloading), eICU (US, 208 hospitals) — scripts present, not yet downloaded.
**eICU cannot supply the cross-method Hb instrument** (its lab table has a single 'Hgb', no separate blood-gas
Hb), so Paper #1 is **MIMIC + SICdb** (2 countries); eICU can still contribute vitals to Paper #3.

## Paper #1 (flagship swing) — Resolve the open acute-MI transfusion question with a cross-site IV
**Why it's high-impact:** MINT (NEJM 2023) left MI+anemia transfusion **unresolved** (liberal-favoring trend,
RR 1.16, p=0.07). Our clean cross-method Hb instrument APPLIES (MI patients aren't actively bleeding → no drift),
and pooling MIMIC + SICdb powers the subgroup MINT couldn't. A quasi-experimental IV that **triangulates** the
RCT is a genuinely novel line of evidence on an open, timely, practice-relevant question.
- MIMIC MI arm (done): n=766, LATE −0.18 (protective, liberal-favoring direction), CI incl 0 (underpowered).
- SICdb MI arm (pending laboratory download): stratify `cases.ICD10Main` on I21/I22; same cross-method
  instrument (289 CBC-Hb vs 658 BGA-Hb, RBC DrugID 2046).
- Pool the two-site IV → the headline: does transfusion reduce death/MI in anemic MI? (Confirm/refute MINT.)
- Gates enforced identically per site: first-stage sign+F, NC (unrelated-treatment), balance, cross-method σ.
**Ceiling:** JAMA/Lancet-tier IF the pooled instrument is valid and resolves the direction. Fallback = the
methods companion below.

## Paper #3 (higher ceiling, confounded-observational) — Multi-site MAP-target (SEPSISPAM) titration
**Why it's high-impact:** SEPSISPAM's 65-vs-80-85 MAP question is unsettled; chronic-HTN AKI benefit is the
open subgroup. Cross-national observational triangulation of the titration target is topical.
**Honest ceiling caveat:** there is **no valid instrument** for a continuously-titrated MAP target (achieved MAP
is confounded-by-health — the same wall as glucose dose-intensity). So this is a rigor-battery ADJUSTED
OBSERVATIONAL analysis (naive → severity-adjusted → modifiable-hypotension-burden → negative-control), reported
as **hypothesis-consistent, not causal** — powerful as a cross-site convergent signal motivating a trial, not as
a causal claim.

### MIMIC arm result (`sepsispam_mimic.py`, run)
Septic-shock cohort n=1,106 (MAP series + pressor). 28-day mortality: naive achieved-MAP −0.075/+10mmHg
(confounded) → adjusts toward 0 (**null overall, consistent with SEPSISPAM**). Modifiable analysis: hypotension
burden below 65 predicts worse outcome (+0.010/mmHg·min), and the **65–85 MAP band carries residual AKI risk the
65 target misses**: adj band coef **+0.0053 (SE 0.0031)** overall and **+0.0064 (SE 0.0036) in the chronic-HTN
subgroup (n=699)** — the hypothesis-consistent direction (SEPSISPAM found higher MAP reduced AKI/RRT in chronic
hypertensives). Borderline (~1.7σ), single-site; cross-site SICdb replication is the value-add.
- SICdb MAP arm (pending): SICdb continuous MAP is in `data_float_h.csv.gz` (+ `data_ref.csv.gz` signal map) —
  download after `laboratory` finishes (sequential, to avoid proxy corruption); rerun the same battery.

## Companion methods paper (bankable fallback)
"A self-diagnosing framework for causal inference from reflexive lab-triggered treatments — cross-site
validated." The cross-method Hb transfusion recovery replicated MIMIC↔SICdb, the gate battery, the honest
analyte scope map. Shares all machinery with #1; publishable even if #1's pooled instrument stays underpowered.

## Execution order
1. Finish SICdb `laboratory` (running, `getlab_zz.sh`) → run `sicdb_crossmethod.py` → **first cross-site
   replication** (base transfusion, all-comers) = the foundation for #1 and the methods paper.
2. Add MI stratification (SICdb `ICD10Main` I21/I22) → pool with MIMIC MI → Paper #1 headline.
3. Download SICdb `data_float_h` + `data_ref` → SICdb MAP battery → Paper #3 cross-site.
