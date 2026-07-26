# Gap analysis: this project versus something ready to put in front of Emery Brown

**Written 2026-07-26.** The audience is not a generic reviewer. It is a specific one who has spent fifteen years
publishing on burst suppression, built the standard method for quantifying it, and proposed the mechanistic
theory of what causes it. That changes what "ready" means, and most of the gaps below exist because the project
was built without reading him.

---

## 0. The finding, as it currently stands

Within the ERC-ESICM "highly malignant" EEG category after cardiac arrest, quantitative suppression burden
measured at the index recording stratifies three-day mortality **29.5 % → 73.1 %**, adds **+0.068** CV AUC over
the category (registered threshold +0.03), and replicates cross-hospital (0.679 / 0.669). Burden behaves like a
**fixed quantity measured with error**, not a reversible state. Three open questions were pursued to closure:
withdrawal-vs-refractory-shock is **unanswerable in this data source** (four instruments, one root cause);
structural-vs-reversible is **closed → structural**; positive tissue-level identification is **not established**.

---

## 1. TIER 1 — gaps that would sink the work with this reader specifically

### G1. The project cites none of Brown's burst-suppression work. Zero of five key papers.

Verified by grep across `docs/`: no mention of PMIDs 22323592, 24018288, 34177731, 25565990, 36343241. This is
not a referencing oversight. Each one bears directly on a load-bearing claim:

| PMID | What it is | Why it matters here |
|---|---|---|
| **22323592** (PNAS 2012) | *A neurophysiological-metabolic model for burst suppression* | The mechanistic theory of what burst suppression **is**. Our Q2/Q3 are about exactly that and never engage it |
| **24018288** (J Neural Eng 2013) | *Burst suppression probability algorithms: state-space methods* | The principled estimator. Ours is the method this paper was written to replace |
| **34177731** (Front Psychol 2021) | *Etiology of Burst Suppression EEG Patterns* | **Our project's founding question**, reviewed by his own group |
| **25565990** (2014) | Propofol and sevoflurane induce **distinct** BS patterns | Our morphology-differs-by-cause result, already established in animals |
| **36343241** (PNAS 2022) | Protective down-regulated states in the human brain | Burst suppression as potentially **protective**, which cuts against a purely prognostic framing |

### G2. Our burden estimator is precisely the method his 2013 paper criticises — quoted verbatim from MEDLINE:

> "Although thresholding and segmentation algorithms readily identify burst suppression periods, analysis
> algorithms require long intervals of data to characterize burst suppression at a given time and **provide no
> framework for statistical inference**."

Ours is a threshold (5 µV) plus segmentation (≥0.5 s runs), reduced to a ratio, and then **maximised over four
2-minute windows** — 8 minutes sampled from recordings that are often many hours. It has no per-recording
uncertainty, no time resolution, and no inferential framework. He will identify this immediately.

**What closing it looks like:** implement the **burst suppression probability (BSP)** — binomial observation
process, Gaussian random-walk state equation, EM estimation — giving an instantaneous probability with credible
intervals, and show the headline result holds under it.

### G3. No mechanistic interpretation, in a project whose whole selling point is interpretability.

Brown's model says burst suppression arises when **reduced cerebral metabolic rate** meets the stabilising
properties of **ATP-gated potassium channels**. Our Q2 result — that burden behaves like a fixed quantity —
is currently reported as a statistical property with no physiological reading.

**This is the largest missed opportunity in the project, not just a gap.** The two results fit together: if
burden indexes cerebral metabolic rate, then it is reversible when the cause is anaesthetic or hypothermic
(rate suppressed in living tissue) and **irreversible when the cause is neuronal death** (rate low because the
tissue is gone). Our finding would then be a clinical extension of his model into the post-anoxic setting rather
than a contradiction of it. That is a conversation with his theory, which is what makes work interesting to the
person who proposed it.

---

## 2. TIER 2 — statistical rigour, for a reader who is a statistician first

| gap | current state | what it should be |
|---|---|---|
| **G4** | **Linear probability models** throughout, for binary outcomes | Logistic (or complementary log-log); LPM predictions can leave [0,1] and the error structure is wrong |
| **G5** | No **calibration** anywhere — discrimination (AUC) only | Calibration slope/intercept, or a calibration plot. A well-discriminating, badly-calibrated score is not usable |
| **G6** | Outcome is binarised at 3/30/180 days | Time-to-event with **competing risks**; death is a time, and binarising discards it |
| **G7** | Patients contribute multiple recordings; no clustering adjustment | Cluster-robust or mixed effects |
| **G8** | Morphology increment **+0.041 has no confidence interval**, unlike every other headline number | Bootstrap CI |

---

## 3. TIER 3 — measurement validity

| gap | current state |
|---|---|
| **G9** | Burden has **never been validated against the clinician burst-suppression label in this repo's record**. A 0.829 AUC appears in a code comment in `heedb_bs_quantify.py` with no reproducible analysis behind it |
| **G10** | **8 minutes sampled** per recording, and burden taken as the **max** across 4 windows. Within-recording stability is unquantified — we do not know the measurement error of our own exposure, which Q2's entire conclusion depends on |
| **G11** | The **5 µV** threshold is not justified or sensitivity-tested on HEEDB (the existing threshold sweep is from a different VitalDB study) |
| **G12** | Reactivity is unavailable, so the Westhall category is reproduced without its nonreactive arm — **already disclosed**, and correctly |

**G10 deserves emphasis.** Q2 concluded "burden behaves like a fixed quantity measured with error" and the
central evidence was that averaging two readings beats the most recent. The size of that measurement error is
never estimated. It is directly estimable from the four within-recording windows we already compute.

---

## 4. TIER 4 — external validity

| gap | state |
|---|---|
| **G13** | Cross-**site**, not cross-**system**: both hospitals share a health system, reporting infrastructure, and clinician pool. TUH is in the pre-registration and **unused** for this analysis |
| **G14** | No prospective validation — **unfixable here**, correctly disclosed |
| **G15** | Every patient has an ascertained death; the outcome is *how soon*, not *whether* — **disclosed** |
| **G16** | Withdrawal cannot be separated from biological death in the 3-day window — **now established by four failed instruments rather than asserted** |

---

## 5. TIER 5 — presentation

| gap | state |
|---|---|
| **G17** | **No figures.** Not one. A quintile plot, a calibration plot and a cross-hospital ROC are the minimum |
| **G18** | Findings are spread across a ledger (309 results), a main-result document, and a lessons file. **No single manuscript-style document** |
| **G19** | No pre-registration/analysis-plan document distinguishing pre-specified from exploratory analyses, in a project that has genuinely done both |

---

## 6. Priority order for closing

Ranked by (damage if unaddressed) × (feasibility now):

1. **G9** — validate burden against the clinician label. Cheapest credibility per unit effort; without it the exposure is unvalidated.
2. **G10** — estimate within-recording measurement error from the four windows. Q2's conclusion rests on it.
3. **G4, G5, G8** — logistic model, calibration, bootstrap CI on the morphology increment.
4. **G1, G3** — engage Brown's literature and reinterpret Q2/Q3 in terms of cerebral metabolic rate.
5. **G2** — implement the BSP state-space estimator and re-run the headline under it.
6. **G6, G7** — survival with competing risks; clustering.
7. **G17, G18** — figures and a single manuscript document.
8. **G13** — TUH external replication. Largest scientific gain, largest cost.

**Honest note on what cannot be closed.** G14 (prospective validation) and G16 (withdrawal separation) are
properties of the data, not of the effort available. They belong in the limitations section permanently, and
the work should be presented as *"information present in the recording"* rather than as a clinical tool —
which is what the main result already says.
