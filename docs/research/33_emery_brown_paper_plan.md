# Target paper + end-to-end workflow — Emery N. Brown lab (anesthesia + EEG)

**Goal:** produce a rigorous, interpretable anesthesia-EEG paper in Brown's exact methodological idiom (multitaper
spectral analysis, state-space models, empirical-Bayes individualization), on a substrate large enough to be novel,
with a clinical bridge only *we* can add — then invite Brown as senior advisor. Feasibility is **proven** (below).

## 0. Why this fits Brown, and why it's reachable (feasibility PROVEN this session)
Brown's program: the neurophysiology of anesthetic-induced brain states, tracked with *principled, interpretable*
EEG markers (frontal alpha + slow oscillation under propofol; burst-suppression probability; multitaper spectra) —
explicitly **against** black-box indices (BIS). His landmark clinical result: **anesthetic frontal-alpha power
declines with age** (Purdon et al., BJA 2015, n≈155). His vision: **individualized, EEG-guided anesthetic dosing**.

**Substrate check (RAN this session, case 1, General anesthesia):** VitalDB raw EEG is 128 Hz µV-scale; a DPSS
multitaper spectrogram (NW=3, K=5, 4 s windows) cleanly recovers the signature — **alpha power rises 24.2→29.2 dB
awake→maintenance**, strong slow-oscillation power, burst suppression detectable. **All CPU** — Brown's methods are
classical DSP, so the "EEG is GPU-gated" wall from earlier this session does NOT apply here.

**Assets confirmed in VitalDB (case counts):** raw EEG ch1+ch2 (5,871), **propofol TCI effect-site conc Ce (3,511)**
— an *independent, directly-logged* dose reference, no PK modeling needed — plasma conc (3,511), sevoflurane
exp/MAC (3,687/6,338), BIS/SR/SEF (5,569), arterial MBP (3,724) + cuff MBP (5,763), age/sex/ASA, mortality/ICU.
This is Purdon-2015's design at **~23–40× scale**, with drug concentration and hemodynamic outcomes his studies lacked.

## 1. Idea brainstorm (ranked: Brown-fit × novelty/gap × our-data × CPU-feasible × tier)
| # | Idea | Brown-fit | Gap / novelty | Tier | Notes |
|---|---|---|---|---|---|
| **L** | **Individualized anesthetic EEG sensitivity: age×sex dose–response of the frontal-alpha/slow-oscillation signature, and its coupling to burst suppression + intraoperative hypotension, at scale** | ★★★★★ | Extends Purdon-2015 40×, adds sex, Ce dose–response, and a hemodynamic bridge nobody has done | **High (Anesthesiology/BJA; bridge could push higher)** | **LEAD** — his method + his finding + our C8 hemodynamics edge |
| 2 | Principled multitaper state marker vs BIS: does interpretable spectral power track Ce and predict BS/hypotension better than the proprietary index? | ★★★★★ | His anti-BIS thesis, quantified at scale | Mid-high | Slightly "expected" from his group; fold in as an *aim* of L |
| 3 | Propofol vs sevoflurane oscillatory signatures across the lifespan (alpha coherence, PAC) | ★★★★ | Drug-specific dynamics at scale | Mid | Descriptive; fold in as L's drug-comparison aim |
| 4 | Burst-suppression susceptibility: who suppresses (age, dose, frailty) and the hemodynamic/outcome cost | ★★★★★ | His BS metabolic model + our hypotension work | Mid-high | Fold in as L's Aim 2 |
| 5 | State-space tracking of emergence dynamics; prolonged-emergence prediction | ★★★★ | His state-space methods | Mid | Good follow-up paper, not lead |
| 6 | Phase–amplitude coupling (slow-oscillation phase ↔ alpha amplitude) as an age/depth marker | ★★★★ | A signature Brown/Purdon emphasize; PAC breakdown with age | Mid-high | Strong secondary marker inside L |

**Lead paper (L), one sentence:** *In 3,500+ propofol-TCI and 3,700+ sevoflurane cases, the frontal-alpha and
slow-oscillation power of the maintenance EEG follows an age- and sex-dependent effect-site dose–response; an
empirical-Bayes per-patient "anesthetic sensitivity" derived from that curve predicts intraoperative burst
suppression and arterial hypotension — providing a principled, individualized alternative to fixed dosing and BIS.*

Why L wins: (a) it is **Brown's method and his headline finding**, so he is the natural advisor; (b) the
**hemodynamic bridge is our unique edge** (we hardened the cuff-vs-arterial hypotension work, C8) — combining EEG
over-sedation with measured hypotension is genuinely new and only we are positioned to do it well; (c) fully
CPU-feasible and the data exists; (d) three clean aims that each stand alone.

**Three aims:**
- **Aim 1 (replicate + extend):** multitaper dose–response of alpha & slow power vs propofol Ce (and sevo MAC),
  as a function of age and sex. Decisive-first: *if the age→alpha decline does not replicate Purdon-2015, stop.*
- **Aim 2 (individualize):** empirical-Bayes/mixed-effects per-patient sensitivity (random slope of alpha power on
  Ce); characterize its distribution and predictors; show it predicts **burst suppression** (detected from RAW EEG,
  not BIS/SR — see lesson on circularity).
- **Aim 3 (bridge, our edge):** does an EEG "over-sedation" phenotype (high slow/suppression *relative to Ce and
  age*) **precede** intraoperative hypotension (arterial MBP<65), by temporal precedence + competing-risks survival?

## 2. End-to-end statistical work (everything, in order)
**Signal processing (per case, CPU batch):**
- Preprocess: 0.5–40 Hz bandpass, 60 Hz notch, re-reference ch1–ch2, robust artifact rejection (amplitude/gradient),
  EMG index from 30–45 Hz (VitalDB also logs BIS/EMG) to flag contamination.
- **Multitaper spectrogram** (DPSS, NW=3–4, K=5–7, 2–4 s windows, 50% overlap) → time–frequency power.
- Markers per epoch: absolute + relative **alpha (8–12)**, **slow/delta (0.5–4)**, theta, beta; **alpha peak
  frequency**; **spectral edge freq 95%**; **occupancy** (Purdon "spectrogram phenotype"); **α–δ phase–amplitude
  coupling** (modulation index); **inter-channel coherence** (ch1–ch2).
- **Burst suppression from RAW EEG** (envelope threshold + minimum-duration rule → BSAR), and **burst-suppression
  probability (BSP)** via a state-space (binomial) smoother — Brown's method. *Do NOT use BIS/SR as the BS label*
  (same-device circularity — our BIS lesson); use BIS/SR only as an external concurrent-validity check.
- Dose alignment: join propofol **Ce** (TCI, independent reference) or sevo end-tidal/MAC to each epoch; restrict to
  steady-state maintenance (exclude induction/emergence transitions) for the dose–response.

**Modeling:**
- **Aim 1:** hierarchical/linear mixed-effects: `alpha_power ~ ns(Ce) * (age + sex) + covariates + (1+Ce | patient)`;
  spline or sigmoid Emax dose–response; age as continuous + decade strata; report the age×Ce interaction (the
  Purdon extension). Sevoflurane parallel model. Multitaper CIs via jackknife-over-tapers.
- **Aim 2:** empirical-Bayes/BLUP per-patient random slope = "propofol sensitivity"; describe distribution; regress
  sensitivity on age/sex/ASA/BMI; logistic model sensitivity→P(burst suppression); calibration + discrimination.
- **Aim 3 (bridge):** define EEG over-sedation residual = observed slow/BSP minus age-and-Ce-predicted; **Cox /
  competing-risks** for time-to-first-hypotension (arterial MBP<65) with the EEG residual as time-varying covariate;
  **temporal precedence** (EEG residual in window t predicts hypotension in t+Δ, not vice versa — cross-lagged);
  landmark analysis to avoid immortal-time bias.
- Sensitivity/robustness: alternative band definitions, window lengths, BS thresholds; drug-subgroup (TIVA vs
  volatile); surgery-type adjustment; multiple-comparison control (hierarchical FDR across markers).

## 3. Adversarial testing (apply this session's hard-won lessons)
- **Decisive-first gate:** run the Aim-1 age→alpha replication on a 300-case pilot *before* any build-out; if it
  doesn't replicate Purdon-2015, stop or pivot. (Lesson: run the make-or-break test first.)
- **Circularity check** (BIS lesson): BS and "depth" markers derived from RAW EEG, independent of BIS/SR; report
  agreement with BIS/SR as *external* validity only.
- **EMG/artifact confound:** re-run excluding high-EMG epochs; show alpha/slow results are not muscle artifact.
- **Reverse causation (Aim 3):** hypotension→cerebral hypoperfusion→EEG slowing is the alternative to EEG→
  over-sedation→hypotension. Adjudicate by temporal precedence, cross-lagged models, and restricting to
  drug-bolus-driven EEG changes (dose is exogenous). This is the death-anchored-style decisive test for Aim 3.
- **Confounder calibration** (triage lesson): verify the EEG marker is not just a proxy for baseline severity/ASA —
  condition on a hard, less-biasable node; show the marker adds beyond age+ASA+Ce.
- **Single-center external validity:** VitalDB is SNUH (one center). Plan an external replication cohort
  (BIS-VITAL / MOABB / a second intraop-EEG set, or a held-out surgical-service split) — flag as the #1 limitation
  and address it, exactly as external replication was the gate in our ED work.
- **Sonnet adversarial panel** (below): 3 independent reviewers attack anchor fairness, artifact, reverse causation,
  and novelty vs Purdon/Akeju before we commit.

## 4. Workflow orchestration — sonnet subagents, token-conscious
Principle: **heavy work is CPU batch jobs (cheap), not agent tokens.** Sonnet subagents *orchestrate, QC, and
adversarially review*; they return compact structured summaries, never raw EEG. Opus (lead) does study design,
the hard statistical judgment, and synthesis. Token budget target: keep agent tokens for reasoning, push all
per-case number-crunching into deterministic scripts.

- **Phase 0 (DONE):** substrate feasibility ✓ (this doc).
- **Phase 1 — cohort + acquisition (1 sonnet orchestrator):** build the case table (propofol-TCI vs sevo, has EEG+Ce
  +hemodynamics+outcomes+age/sex); write the batch downloader (VitalDB API, streaming, disk-sparing). Returns a
  cohort manifest + counts, not data.
- **Phase 2 — feature extraction (batch job + 1 sonnet QC):** one deterministic multitaper script over all cases in
  parallel (CPU); a sonnet QC agent audits distributions, artifact rates, and flags bad cases. Output: one compact
  per-case feature table (~50 markers × N cases).
- **Phase 3 — modeling (opus + 1 sonnet runner):** opus specifies the mixed-effects/EB/Cox models; a sonnet runner
  executes pre-specified fits and returns coefficient tables + diagnostics.
- **Phase 4 — adversarial panel (3 sonnet reviewers, parallel):** anchor fairness / artifact / reverse-causation /
  novelty attacks; each returns ≤400-word structured critique. Opus adjudicates; findings become robustness analyses.
- **Phase 5 — manuscript (opus + docx skill):** methods, figures (multitaper spectrograms by age decade; dose–
  response surfaces; sensitivity distribution; survival curves), TRIPOD/repro appendix.
Use the **Workflow tool** for Phase 2 (fan-out over case batches) and Phase 4 (parallel reviewers); everything else
is sequential agents. Estimated agent-token footprint is small because the numeric work is in scripts.

## 5. What to send Brown
A 1-page concept memo + the pilot Aim-1 figure (age×Ce alpha-power surface at 40× his sample) + the pre-registered
analysis plan (this doc). The ask: senior advisor on an already-executed, rigorously-designed extension of his own
BJA-2015 finding into individualized, hemodynamically-linked dosing. Lead with the pilot replication — it proves we
can execute end-to-end in his idiom.

## 6. Milestones / go-no-go
1. **Pilot (300 cases):** Aim-1 age→alpha replication. GO iff the age×alpha decline reproduces (decisive-first gate).
2. Full cohort feature extraction + Aim 1/2 at scale.
3. Aim 3 hemodynamic bridge + temporal-precedence adjudication.
4. Adversarial panel + robustness; external-validity plan.
5. Manuscript + concept memo to Brown.

## PIVOT (user steer): HEEDB = discovery, VitalDB = external validation, multi-site
Design locked: **discover** the iatrogenic-vs-pathological burst-suppression finding in **HEEDB** (ICU cEEG/LTM,
where drug-induced AND pathological BS coexist, with the ATC medication linkage to separate them + DateOfDeath),
**externally validate** the drug-induced/benign arm in **VitalDB** (intraop BS is ~purely drug-induced, with logged
propofol Ce), across a **different setting (OR vs ICU) and country** — plus HEEDB multi-site (S0001/S0002/I000x)
cross-site replication. Spans Brown (anesthesia) + Westover (ICU).

### VitalDB validation-arm pilot — pipeline PROVEN (40 propofol-TCI cases, open data)
Burst suppression detected from RAW EEG (0.1s frames, p2p<8µV, runs≥0.5s; NOT BIS/SR — avoids same-device
circularity). Results: BS is detectable and common in elective TIVA (85% of cases show some suppression; median
maintenance burden 1.5%, p90 20%). In-hospital mortality ~0 (elective surgery) → confirms VitalDB's role as the
**benign drug-induced reference** (drug-induced BS at depth carries near-zero mortality); the pathological-BS
mortality contrast must come from HEEDB. MODELING NOTE: peak-Ce↔BS correlation weak (−0.10) at this crude level —
BS depends on Ce *relative to age/individual sensitivity* and on Ce-at-onset, not peak Ce; the real analysis needs
the age×Ce sensitivity model (Aim-1 machinery), not a raw Ce correlation. Cohort available: **3,344 VitalDB cases
with EEG + propofol Ce + mortality**. Pipeline: `analysis/vitaldb_bs_pilot.py`.

### GATE: HEEDB discovery arm needs explicit PII/DUA authorization (per docs/HEEDB_UNLOCK.md)
Pulling HEEDB moves regulated credentialed data; awaiting user authorization. On authorization: compute only
de-identified derived features + aggregate stats (no PII in outputs/commits). Decisive-first test once unlocked:
among BS-containing EEGs, does sedative-attributable (drug-induced) BS have markedly LOWER mortality than
non-drug (pathological) BS at matched BS burden/BSP? If yes → "BS is a marker of its cause, not intrinsically
harmful" (the ENGAGES-debate resolution) and the design is alive.
