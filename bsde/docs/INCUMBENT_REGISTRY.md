# Incumbent registry — what the literature already claims, per challenge

*Track G of `PROGRAMME_ROADMAP.md`. Opened 2026-08-03. **Every future registration must clear the
comparators listed here for its challenge, or state why the comparator does not apply.***

## Why this file exists

E129 cost us a finding we already owned. `alpha_prom` — this project's own registry column — sat in
`dreyer_graph.csv` predicting BCI performance at **+0.3710 [+0.1709, +0.5512]**, and no experiment ever
correlated it with the outcome, because every registration pointed at `ge_norm`. Rule 45 says name the
incumbent. It was applied religiously to *outcomes* (E33's "the incumbent must be alive", E84's
PE31/SEF95 baseline, E122's G3) and **never once to predictor families**.

Blankertz, Hannivoort and Proekt & Kelz were each found by accident while looking for something else. Done
deliberately, they would have been found first — and Hannivoort in particular turned out to be
implementable straight from its abstract.

Every PMID below is verified from the MEDLINE record via E-utilities, never from a summary (rule 25).

---

## Status legend

| status | meaning |
|---|---|
| **TESTED** | implemented and run against our outcome; result linked |
| **IMPLEMENTABLE** | parameters/definition recoverable from what is quoted; not yet run |
| **BLOCKED** | needs data or a definition we cannot reach; blocker named |
| **N/A** | cannot apply to any deposit we hold; reason named |

---

## Challenge A — measures claimed to index consciousness / state

| PMID | source | claim | status |
|---|---|---|---|
| 27717082 | Casarotto, Ann Neurol 2016;80:718-729 | **PCI** — an *independently validated* index of brain complexity stratifying unresponsive patients | **BLOCKED** — needs TMS-EEG. ds005620 was extracted (E103–E105) and the perturbational line closed: the response was measurable and bought nothing over spontaneous measures |
| 33260944 | Sinitsyn, Brain Sci 2020;10 | PCI for detecting potential for consciousness in unresponsive patients | **BLOCKED** — same |
| 36630828 | Dong, Comput Biol Med 2023;153:106480 | integrated-information index over multichannel EEG across anaesthetic states | **IMPLEMENTABLE?** — needs the definition checked; `uce_v1` in our registry is an IIT-adjacent candidate and has never been compared to it |

**Our standing measures**: `whole_head_exponent`, `exponent_high/low`, `lempel_ziv`, `irr3/irr4`,
`incr_asym`, `uce_v1`, `pac_slow_alpha`, `spatial_participation_ratio`.

**Gap identified by this sweep:** we have never compared any of our complexity measures against a
*published, independently validated* complexity index. PCI is blocked by modality, but Dong 2023 may not
be. That is the first Challenge A action item from track G.

---

## Challenge B — predictors of BCI performance

| PMID | source | claim | status |
|---|---|---|---|
| 20303409 | Blankertz, Neuroimage 2010;51:1303-9 | **SMR predictor**, r = 0.53, N = 80, two-minute eyes-open rest, two Laplacian channels | **TESTED** — E129 replicated on Dreyer at **+0.4440 [+0.2480, +0.6104]** against an attenuated expectation of +0.4183. E131: does NOT work in Stieger (+0.0747, excludes Dreyer's value) |
| 40127541 | Marissens Cueva, J Neural Eng 2025;22(2) | **median nerve stimulation** ERD minimum, rho = −0.71 with MI-BCI accuracy | **BLOCKED** — requires MNS during recording; no deposit we hold has it |
| 40172828 | Li, Neurosci Bull 2025;41:1198-1212 | personalised MI-ability predictor from **multi-frequency** EEG features | **IMPLEMENTABLE?** — definition not yet checked; directly relevant since our tested predictors are single-band |
| 30728772 | Rimbert, Front Hum Neurosci 2018;12:529 | a **subjective questionnaire** as a BCI performance predictor | **IMPLEMENTABLE on Dreyer** — the deposit ships personality, mental-rotation, mood and motivation columns in `Perfomances.csv` and **we have never touched them** |
| 31417382 | Won, Front Hum Neurosci 2019;13:261 | P300-speller predictor from RSVP multi-feature | **N/A** — different BCI paradigm |

**The finding this sweep produces immediately:** Dreyer's own `Perfomances.csv` carries demographic,
personality, cognitive and motivational columns that we parsed past to reach `Perf_RUN_3..6`. Rimbert 2018
claims a questionnaire predicts BCI performance. **We hold both the questionnaire and the outcome and have
never put them together.** That is exactly the E129 mistake repeating, caught this time before it cost
anything.

---

## Challenge C — depth-of-anaesthesia indices

| PMID | source | claim | status |
|---|---|---|---|
| 27106965 | Hannivoort, Br J Anaesth 2016;116:624-31 | **triple interaction model** sevo+propofol+remifentanil → PTOL/NSRI | **TESTED** — implemented in `bsde/pkpd/interaction.py`, 11 tests; used as E126's P2 |
| 15166553 | Bouillon, Anesthesiology 2004;100:1353-72 | propofol–remifentanil response surface for hypnosis, BIS, approximate entropy | **IMPLEMENTABLE** — used to validate our interaction form (remifentanil alone has no effect); the **approximate-entropy** arm is a comparator we have never run |
| 1588504 | Varvel, J Pharmacokinet Biopharm 1992;20:63-94 | MDPE / MDAPE / wobble / divergence | **TESTED** — `PK_VALIDATION_NOTE.md` |
| 33081972 | Proekt & Kelz, Br J Anaesth 2021;126:265-278 | hysteresis is **not identifiable** from equilibration models alone | **TESTED** — shaped E126/E127; E127 found confounding by indication instead |
| 28489797 | Wang, Medicine 2017;96:e6895 | a published propofol–remifentanil surface predicts **poorly** out of population | **TESTED as a caveat** — carried with every use of Hannivoort |
| 30721296 | Wildes (ENGAGES), JAMA 2019 | EEG-guided anaesthesia did **not** reduce delirium: 26.0 % vs 23.0 %, +3.0 % [−2.0, +8.0] — while halving suppression time | **frames Challenge E** |
| 42016204 | Liu, Ther Clin Risk Manag 2026;22:593667 | **qCON / qNOX** guided sedation during GI endoscopy | **IMPLEMENTABLE?** — same procedure type as DOSE-I; definitions proprietary, needs checking |
| 41907336 / 41254981 | Shiraishi 2026; Jildenstål 2026 | **Patient State Index (PSi)** | **BLOCKED** — proprietary, no open definition |
| 42300957 | Schneider, Paediatr Anaesth 2026 | **Narcotrend** index vs a paediatric sedation scale | **BLOCKED** — proprietary |

**Our tested comparator on DOSE-I** is the deposit's own shipped `PE31`/`SEF95`, which E84 established as
live (baseline out-of-bag rho +0.3310) and E122 showed adds to pharmacology at every rung — while none of
our 27 candidates added anything over it.

---

## Action items produced by this sweep, in priority order

1. **Dreyer's questionnaire columns vs online performance** (Challenge B). Data entirely in hand, outcome
   already parsed, incumbent published (Rimbert 2018). This is the E129 mistake caught before it costs.
2. **Bouillon's approximate entropy** as a Challenge C comparator — a published EEG measure with a
   response surface fitted to it, which we have never run against ours.
3. **Dong 2023's integrated-information index** vs our `uce_v1` (Challenge A) — the first comparison of
   our complexity measures against a published one.
4. Confirm whether **qCON/qNOX** have any open definition; if not, mark BLOCKED permanently and stop
   returning to it.

**Standing rule from here:** a registration whose challenge has an untested **IMPLEMENTABLE** row in this
table must say why that comparator was not used.
