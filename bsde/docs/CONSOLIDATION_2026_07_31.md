# Consolidation round: the constraint set, the literature against it, and what to build next

*Written 2026-07-31 after E58–E63, following the ten-result cadence in `CLAUDE.md`. Every number is from
this repository's registered experiments or from a MEDLINE record fetched with `curl` through E-utilities
and parsed from XML (rules 25, 39 — never a fetch-tool summary).*

**The one-sentence result of this round:** all three challenges point at the same missing measure family —
**inter-channel phase / connectivity** — and the deposit that can supply it was here all along.

---

## 1. The constraint set

### Challenge A — a marker that tracks state while carrying no drug identity

| | constraint | source |
|---|---|---|
| **A1** | Every reachable deposit has its agents in **disjoint patients**. No within-subject two-drug data. | E30, E61, Q9 |
| **A2** | **Inter-channel phase coupling (wPLI) leaks little drug identity** (\|AUC−0.5\| 0.000–0.128); power and complexity leak 0.217–0.368. Unique maximum of all 495 partitions, p = 0.002. | E35, E36 |
| **A3** | At matched BIS, propofol vs sevoflurane is **not legible from any of nine WITHIN-channel measures** — and no family clears its own permutation null. | E61 |
| **A4** | Arms disagree in **sign** between propofol-without-opioid and volatiles-with (rule 16). | E30 |
| **A5** | The deflationary explanation for A2 — phase measures leak less because they are artefact-robust — is **untested**. | E39 (absent) |
| **A6** | `exponent_low` and `exponent_high` point in **opposite directions**; the whole-band fit averages them to nothing. | E50, E52 |

### Challenge B — spontaneous EEG predicting command-following

| | constraint | source |
|---|---|---|
| **B1** | eegmmidb label reliability r_sb = **0.2918** [0.1163, 0.4345] → attenuation ceiling **0.5402**. | E38 |
| **B2** | `uce_v1` ρ = +0.0853 [−0.1066, +0.2651]; incumbent `relative_alpha_power` +0.2018 [+0.0050, +0.3857]; MDE 0.272 at n = 104. | E41 |
| **B3** | Attenuation **neither demonstrated nor refuted** — underpowered. | E56 |
| **B4** | Stieger **cannot** test `lrtc_alpha`: trial-epoched, and `lrtc_envelope` now refuses rather than shrinking its scale range. | Q14 |
| **B5** | Age and sex explain little between-subject variance; a conditional reference buys Challenge B nothing. | E54 |
| **B6** | **Every Challenge B candidate tested here has been an amplitude summary.** | E28, E41, E42 |

### Challenge C — seeing a transition before the monitor

| | constraint | source |
|---|---|---|
| **C1** | Nothing sees the transition ahead of the incumbent; the information-horizon question **cannot be asked on DOSE-I at all**. | E26, E27, E34, E37, E40 |
| **C2** | At matched state BIS is **less** muscle-associated than a broadband slope — asymmetry −0.0967 [−0.1798, −0.0100]. The proposed EMG mechanism is refuted in the opposite direction. | E43 |
| **C3** | Under matched muscle exposure `lempel_ziv` is steadiest (1.576) and **BIS is least steady** (3.922); `spectral_edge_95` refuted. | E46 arm B |
| **C4** | The BIS-like index is usable only in **[20,60)** — refuse below 20 (84.4 % fail SQI) and above 60 (35–98 % EMG artefact). | E58, E60, E62 |
| **C5** | VitalDB has no awake-under-monitor windows; DOSE-I has the transition but no branded index. | E22, Q22 |
| **C6** | BIS 40–60 means a **different EEG state at different ages**. | E55 |

### Cross-cutting

**X1** eye state is first-order (E44) · **X2** `lempel_ziv` is a state measure, not a trait (E45) ·
**X3** the pipeline is calibrated, aperiodic correction harmonises but costs signal, and a cross-deposit
floor is real (E47, E48, E51, E53) · **X4** most of `bis_sfs`'s agreement with an independent SFS is shared
with a pure **power** ratio: −0.5875 → **−0.2706** when PowerFastSlow is partialled out (E59).

---

## 2. The literature, fetched and verified

| ref | what it establishes | why it matters here |
|---|---|---|
| **PMID 25233374** — Akeju et al., *Anesthesiology* 2014, "Effects of sevoflurane and propofol on frontal electroencephalogram power and coherence" | n = 30 vs 30, **age- and sex-matched, sole agent for maintenance**. Alpha power and coherence are essentially the same for both drugs (peak coherence **0.73 ± 0.1** vs **0.71 ± 0.1**, both ~10 Hz); slow oscillations show **"no significant difference in power or coherence"**. The one discriminator is a **sevoflurane theta coherence signature** — peak **4.9 ± 0.6 Hz**, coherence **0.58 ± 0.1**. | **Corroborates A3 and identifies exactly what A3 was missing.** Our null on nine amplitude/within-channel measures is what this paper predicts. The measure that separates the drugs is an **inter-channel phase** quantity in **theta** — a family and band we have never computed on VitalDB. |
| **PMID 26529439** — *J Neural Eng* 2015, "Efficient resting-state EEG network facilitates motor imagery performance" | Mean functional connectivity, node degree, edge strength, clustering coefficient, and local/global efficiency all **positively** correlate with MI classification accuracy; characteristic path length **negatively**. A regression on efficiency measures predicts accuracy. | Directly attacks **B6**. Every predictor here is multi-channel network; none is a band power. |
| **PMID 37759889** — *Brain Sci* 2023, "Predicting Motor Imagery BCI Performance Based on EEG Microstate Analysis" | Resting microstate predictor reaches **AUC 0.83**, **+17.9 % over a spectral entropy predictor**, n = 28. | A named incumbent-beating result in the family we have not tested (rule 45). |
| **PMID 38986469** — *J Neural Eng* 2024, "Connectivity study on resting-state EEG between motor imagery BCI-literate and BCI-illiterate groups" | Three large public datasets, **three functional and three effective connectivity metrics**, graph measures; the paper's whole point is that **metric choice and frequency band change the answer**. | Warns against picking one connectivity metric and one band and calling the result general — which is the mistake **A2** is at risk of, since E36 tested wPLI in alpha only. |

---

## 3. Candidates, each against the full constraint set

### C1 — The missing family: inter-channel phase / connectivity  *(rank 1)*

**Explains:** A2 (it *is* the family that leaked least), A3 (E61 tested only *within*-channel phase, so the
family E36 identified was never testable on VitalDB), B6 (every B candidate has been an amplitude summary),
C3 (no connectivity measure appeared in E46's muscle-robustness ranking at all).

**Struggles with:** X4 — our one nominally-phase measure turned out to be substantially power, so a "phase"
label guarantees nothing. And A5 still stands: the deflationary explanation for A2 is untested, so a
connectivity win could be artefact-robustness rather than drug-invariance.

**Falsifiable prediction:** on VitalDB's **two** EEG channels, **theta inter-channel coherence separates
propofol from sevoflurane at matched BIS, above its own permutation null, while alpha power does not.**

### C2 — E36 and Akeju are not in conflict; the split is BAND- and METRIC-specific  *(rank 1, same experiment)*

E36 tested **alpha wPLI**. Akeju's discriminator is **theta coherence**. Coherence is amplitude-contaminated;
wPLI is not. So drug identity may live in theta phase while state lives in alpha phase, and a measure can be
drug-invariant in one band while the drug signature sits in another.

**Falsifiable prediction, and it can fail three distinguishable ways:** theta coherence leaks drug identity
while alpha wPLI does not (**reconciliation**); *both* leak (**E36's split is not band-general and is false
here**); *neither* leaks (**Akeju does not replicate on this deposit and the line closes**).

### C3 — Challenge B's bottleneck is the measure FAMILY, not only the label  *(rank 3, after E63)*

E38/E41/E56 framed B as label precision. The literature says the predictors that work are network measures.
Both can be true: a weak amplitude marker read through a noisy label.

**Struggles with:** Stieger's task-free segment is a **2 s pre-cue window inside a task block**, not the
resting recording every one of L2–L4 used.

**Falsifiable prediction:** with the ceiling measured by E63, a connectivity/efficiency predictor beats
`relative_alpha_power` on Stieger by more than the incumbent's own CI width.

### C4 — "Phase" measures in this repo may not be measuring phase  *(RUN, result below)*

Checked immediately on existing tables, 5,525 SQI-clean windows:

| measure | ρ with `spectral_edge_95` | its ρ with BIS | partialled on `spectral_edge_95` |
|---|---|---|---|
| `bis_sfs` | **−0.687** | −0.320 | **−0.174** |
| `pac_slow_alpha` | +0.091 | −0.112 | −0.150 |

**CONFIRMED for `bis_sfs`, REFUTED for `pac_slow_alpha`.** Half of `bis_sfs`'s relation to BIS is a spectral
edge in disguise, corroborating X4 from a second direction. `pac_slow_alpha` is a genuine phase measure — it
simply carries almost no state information (E61 state \|AUC−0.5\| = 0.0044). **So the caution is per-measure,
not a law**, and it fixes a design choice below: compute **coherence AND wPLI**, because the pair separates
"phase" from "power dressed as phase", and only the pair can test Akeju and E36 at once.

---

## 4. What was verified before committing to any of it

`BIS/EEG1_WAV` and `BIS/EEG2_WAV` are present on **250 of 250** grid cases, and EEG2 carries real signal
(case 1: 1,477,268 samples, 100 % finite, sd 87.69 µV). **The second channel was available from the start;
the adapter simply returned one.** Nothing about the disjoint-patient constraint A1 changes — this is still
a between-subject contrast — but the family the whole programme points at becomes computable today, on a
deposit already extracted, with no new access.

---

## 5. Ranked queue out of this round

1. **Two-channel VitalDB extraction, then the theta-coherence / alpha-wPLI fork (C1 + C2).** Tests a
   published finding on an independent deposit, resolves an internal tension, and can fail three ways.
2. **E63 when the Stieger extraction finishes** — the Challenge B ceiling, already registered.
3. **A connectivity predictor on Stieger's 62 channels (C3)**, with `relative_alpha_power` as the named
   incumbent and E63's ceiling in the header.
4. **A5 remains open and now matters more.** If connectivity wins anywhere, E39's untested deflationary
   explanation becomes the first thing a reviewer will raise.
