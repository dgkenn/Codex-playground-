# Literature check — Challenge A, agent-invariant loss/recovery tracking

*2026-08-02. Scope: literature only. No analysis, no registration, no data work performed.*

**Question tested:** does prior art already establish "a single EEG measure tracks loss and recovery of
consciousness equally well under intravenous and inhaled anaesthesia while carrying minimal information
about which agent is in use"?

**Method:** all citations below were retrieved and verified via NCBI E-utilities (`esearch` + `efetch`,
`curl`/`urllib` against `eutils.ncbi.nlm.nih.gov`, plain HTTP, no WebFetch of any bibliographic record —
per repo rules 25/39). Every quote is copied verbatim from the E-utilities `abstract` return. Raw
query/response logs are in `/tmp/claude-…/scratchpad/lit/` (ephemeral; not archived — the PMIDs and quotes
below are the durable record).

---

## (a) One-line verdict

**PARTIALLY.** The *failure* half of the question — that today's commercial scalar indices are NOT
agent-invariant, and are known to break on specific agents — is extensively documented. The *minimisation*
half — an EEG measure explicitly built or trained to carry **minimal drug-identity information**, as a
first-class objective rather than a post-hoc agreement check — was not found anywhere in the literature
searched. Nobody appears to have asked the adversarial question. See (c).

---

## (b) Per-item evidence

### 1. Agent-invariance claims by existing monitors — what is claimed, what is shown, where it breaks

**BIS is explicitly documented, in a clinical review, to fail on the classic problem agents.**
Johansen JW, "Update on bispectral index monitoring", *Best Pract Res Clin Anaesthesiol* 2006 (PMID
**16634416**):

> "Some limitations exist to the use of BIS and it is not useful for some individual hypnotic agents
> (ketamine, dexmedetomidine, nitrous oxide, xenon, opioids)."

That is a named list of exactly the failure agents the task asked me to check, from a review, not a single
trial.

**Ketamine — BIS/Entropy move the WRONG direction (paradoxical rise under deepening hypnosis).**
Hans P et al., "Comparative effects of ketamine on Bispectral Index and spectral entropy of the
electroencephalogram under sevoflurane anaesthesia", *Br J Anaesth* 2005 (PMID **15591328**):

> "Ketamine administered under sevoflurane anaesthesia causes a significant increase in BIS, RE and SE
> without modification of the RE-SE gradient. This increase is paradoxical in that it is associated with a
> deepening level of hypnosis." — maximum relative increase 29.4% (BIS), 42.2% (RE), 41.6% (SE) from a
> stable sevoflurane baseline.

Consistent single-line report: Roffey P et al., "Ketamine interferes with bispectral index monitoring in
cardiac patients undergoing cardiopulmonary bypass", *J Cardiothorac Vasc Anesth* 2000 (PMID **10972626**).

**Nitrous oxide — BIS is blind to it even though the raw EEG changes.**
Rampil IJ et al., "Bispectral EEG index during nitrous oxide administration", *Anesthesiology* 1998
(PMID **9743404**), in 13 healthy volunteers up to 50% N₂O:

> "N2O (50%) increased theta, beta, 40–50 Hz, and 70–110 Hz band powers. BIS and spectral edge frequency
> during 50% N2O/O2 did not differ significantly from baseline values... Despite changes in the lower and
> higher frequency ranges of EEG activity, the BIS did not change, which is consistent with its design
> objective as a specific measure of hypnosis."

Note the last clause is the *authors'* framing (BIS was designed to ignore N₂O-type spectral change) — that
is itself evidence against the idea that agent-invariance and behavioural fidelity are the same goal: BIS
is invariant to N₂O by construction/scope, not because it tracks N₂O's (weak, real) hypnotic effect.

**Xenon — the opposite failure mode: BIS tracks it fine, but disagrees with Entropy, and one head-to-head
paper on this exact question was later retracted.**
Laitio RM et al., "Bispectral index, entropy, and quantitative electroencephalogram during single-agent
xenon anesthesia", *Anesthesiology* 2008 (PMID **18156883**), 17 healthy subjects:

> "BIS, State Entropy, and Response Entropy demonstrated low prediction probability values at loss of
> response (0.455, 0.656, and 0.619) but 1 min after that the values were high... Xenon-induced changes in
> electroencephalogram closely resemble those induced by propofol."

So BIS/Entropy lag at the loss transition under xenon but converge afterward, and the underlying EEG
resembles propofol's — a rare piece of *positive* cross-agent evidence. Contrast Hirota K, "Special cases:
ketamine, nitrous oxide and xenon", *Best Pract Res Clin Anaesthesiol* 2006 (PMID **16634415**):

> "Ketamine and nitrous oxide do not per se decrease the bispectral index. However, xenon decreases the
> bispectral index in a concentration-dependent manner... anaesthetic depth monitors fail to describe
> consciousness accurately when ketamine and nitrous oxide are used."

**Flag, not evidence:** Höcker J et al., "Differences between bispectral index and spectral entropy during
xenon anaesthesia: a comparison with propofol anaesthesia", *Anaesthesia* 2010 (PMID **20412149**) reported
BIS/Entropy divergence specifically under xenon vs propofol — **this article was RETRACTED** in 2014
(retraction notice PMID **24932466**, *Anaesthesia* 2014;69(6):654). I did not rely on its findings and flag
it so nobody downstream cites it. The retraction notice itself gives no reason in the abstract; only that it
retracts the 2010 article.

**Dexmedetomidine — BIS's discrimination is preserved but its operating point shifts, and the underlying EEG
differs from propofol's even at matched sedation depth.**
Chen Z et al., "Effects of dexmedetomidine on performance of bispectral index as an indicator of loss of
consciousness during propofol administration", *Swiss Med Wkly* 2013 (PMID **23519436**):

> "The ability of BIS to predict LOC is not influenced by dexmedetomidine during propofol administration,
> but BIS values are enhanced at the time of LOC." — BIS50 71.1–71.4 with dexmedetomidine pretreatment
> vs 63.2 without.

More fundamentally, Xi C et al., "Different effects of propofol and dexmedetomidine sedation on
electroencephalogram patterns", *PLoS One* 2018 (PMID **29920532**), 20-channel EEG, crossover design:

> "dexmedetomidine decreased the global alpha/beta/gamma power, whereas propofol decreased the alpha power
> in the occipital area and increased the global spindle/beta/gamma power... The transition of topographic
> alpha/spindle/beta power distribution from moderate sedation to deep sedation completely differed between
> these two agents... Differences in EEG dynamics at the same sedation level might account for differences
> in the BIS value and reflect the different sedation mechanisms."

**Entropy — the same caveat, stated in review form.**
Bein B, "Entropy", *Best Pract Res Clin Anaesthesiol* 2006 (PMID **16634417**):

> "Entropy guidance may not be used during ketamine or nitrous oxide administration, since there is no
> reliable correlation to the patient's state of consciousness."

**PSI (Sedline) — a documented case where PSI, specifically, fails on ketamine where a competitor index
(qCON) does not.**
Christenson C et al., "Comparison of the Conox (qCON) and Sedline (PSI) depth of anaesthesia indices to
predict the hypnotic effect during desflurane general anaesthesia with ketamine", *J Clin Monit Comput*
2021 (PMID **33211251**):

> "During desflurane anesthesia the qCON index did not change significantly after ketamine administration,
> qCON (before = 33(4), after = 30(17); Wilcoxon, p = 0.89), while the PSI experienced a significant
> increase, PSI (before = 31(6), after = 39(16), Wilcoxon, p = 0.013)."

This is direct evidence that "agent-invariance" is not a monolithic property of processed-EEG indices in
general — it is index-specific and drug-combination-specific, and two commercial indices disagree with each
other about which agent combinations they are robust to.

**Under a single "easy" agent (sevoflurane alone), BIS and PSI DO agree closely** — Soehle M et al.,
"Comparison between bispectral index and patient state index as measures of the electroencephalographic
effects of sevoflurane", *Anesthesiology* 2008 (PMID **18946290**):

> "despite major differences in their algorithms and minor differences in their dose-response relations,
> both PSI and BIS predicted depth of sevoflurane anesthesia equally well" (Pk 0.80 vs 0.79; r² between the
> two indices = 0.75).

**Even on identical EEG input, five commercial monitors disagree with each other,** independent of which
drug produced the signal — Hight D et al., "Five commercial 'depth of anaesthesia' monitors provide
discordant clinical recommendations in response to identical emergence-like EEG signals", *Br J Anaesth*
2023 (PMID **36894408**):

> "Of the 52 cases, only 16 (31%) showed concordance between all five monitors [BIS, Entropy-SE, Narcotrend,
> qCON, Sedline]... That two-thirds of cases showed discordant recommendations given identical EEG data...
> emphasizes the importance of personalised EEG interpretation."

This is not an agent-invariance failure per se (same EEG signal fed to all five), but it bounds how much
weight any single index's "agreement across agents" claim can bear: the indices do not even agree with each
other on the same input.

**A 2026 multivariate re-analysis shows the underlying feature space is NOT agent-invariant, even though the
commercial scalar indices built on top of it are marketed as such.** Shen P et al., "Divergent periodic and
aperiodic EEG signatures of Propofol versus sevoflurane anesthesia", *Front Med (Lausanne)* 2026 (PMID
**42131603**), 44 patients (propofol n=27, sevoflurane n=17), subject-independent cross-validation, 17
spectral/aperiodic features:

> "Current clinical anesthesia monitors often utilize drug-invariant indices that simplify cortical
> dynamics, potentially overlooking pharmacological nuances... The multivariate model achieved high
> discriminatory performance with a rigorous subject-level accuracy of 91.43%... theta-to-alpha ratio and
> alpha peak frequency were identified as the primary differentiators... alpha peak frequency 8.78 Hz
> [sevoflurane] vs. 10.88 Hz [propofol]."

This paper explicitly names "drug-invariant indices" as the status quo and argues against pursuing them
further, in the opposite direction from Challenge A's brief — see (c).

### 2. Is "minimise drug identity" ever an articulated design criterion?

**The closest analogue found is PSI's original validation paper**, and it is explicitly a *consistency*
(agreement) framing, not a minimisation framing. Prichep LS et al., "The Patient State Index as an
indicator of the level of hypnosis under general anaesthesia", *Br J Anaesth* 2004 (PMID **14742326**), 176
patients, induction with etomidate/propofol/thiopental, maintenance with isoflurane/desflurane/
sevoflurane/TIVA-propofol/N₂O-narcotics:

> "The PSI is comprised of quantitative features of the EEG (QEEG) that display clear differences between
> hypnotic states, **but consistency across anaesthetic agents within the state**... Regression analysis for
> prediction of arousal level using PSI was found to be highly significant for the combination of all
> anaesthetics, and for the individual anaesthetics."

This is a real prior attempt at the same *goal* (a state signal that reads the same across several agent
classes) but it is validated by pooled and per-agent regression fit — i.e., the same "does it agree" logic
the task brief explicitly warns against ("a prior session inverted this and spent its effort measuring how
much drug-identity information the panel carries"). I found no paper that instead poses agent-identity
recovery as an adversarial or information-theoretic objective to be minimised during construction or
training of the index.

**Searches that returned nothing on PubMed/MEDLINE**, tried under multiple phrasings (all zero hits):
`domain adversarial EEG anesthesia depth agent invariant`; `adversarial invariant representation learning
physiological signal domain generalization drug`; `universal anesthetic depth index cross-drug EEG
biomarker`; `invariant risk minimization physiological signal confound`; `confound removal classifier EEG
drug identity anesthesia`; `mutual information minimization confound biomarker neuroimaging`; `anesthetic
agent classification EEG machine learning propofol sevoflurane discriminate`. The two hits for `gradient
reversal domain adaptation EEG` (PMID 41437701, 40871851) are EEG emotion-recognition and generic EEG
classification papers with no anaesthesia or agent-identity content.

**Caveat on this null result, stated plainly rather than left implicit:** PubMed/MEDLINE indexes clinical
and biomedical-engineering journals, not ML methods venues (NeurIPS/ICML/arXiv), where a paper doing
gradient-reversal or mutual-information-minimisation on anaesthesia EEG specifically for agent-invariance
would most plausibly appear if it exists. No tool available to me in this task searches arXiv or Google
Scholar in a way compliant with rule 25/39 (verified retrieval, not a WebFetch summary), so **this is an
absence-of-evidence-in-PubMed finding, not a proven absence in the ML literature at large.** I flag this
as a genuine gap in my search rather than papering over it.

### 3. Loss and recovery specifically — neural inertia / hysteresis

**Established, cross-species, not agent-specific to propofol.** Friedman EB et al., "A conserved
behavioral state barrier impedes transitions between anesthetic-induced unconsciousness and wakefulness:
evidence for neural inertia", *PLoS One* 2010 (PMID **20689589**) — the foundational Kelz-lab paper:

> "the forward and reverse paths through which anesthetic-induced unconsciousness arises and dissipates are
> not identical. Instead they exhibit hysteresis that is not fully explained by pharmacokinetics as
> previously thought... We demonstrate that such a barrier separates wakeful and anesthetized states for
> multiple anesthetics in both flies and mice."

**Established in humans, with an explicit statement that induction and emergence are not symmetric.**
Warnaby CE et al., "Investigation of Slow-wave Activity Saturation during Surgical Anesthesia Reveals a
Signature of Neural Inertia in Humans", *Anesthesiology* 2017 (PMID **28665814**), 393 EEG datasets:

> "it is clear that induction and emergence from anesthesia are not symmetrically reversible processes...
> Slow-wave activity saturation occurs for different anesthetics and when opioids and muscle relaxants are
> used during surgery... A signature for neural inertia in humans is the maintenance of slow-wave activity
> even in the presence of very-low hypnotic concentrations during emergence."

Review confirming the clinical observation across TIVA practice: Sepúlveda PO et al., "Neural inertia and
differences between loss of and recovery from consciousness during total intravenous anaesthesia: a
narrative review", *Anaesthesia* 2019 (PMID **30835820**) — "the calculated effect-site concentration at
loss of consciousness is usually higher than the concentration at emergence."

**What this means for Challenge A:** hysteresis between loss and recovery is well-established, but I found
**no paper claiming any measure tracks it symmetrically ACROSS agents** — every neural-inertia paper above
characterises hysteresis *within* one anaesthetic or compares magnitudes across a few, not a candidate that
was built to reproduce the same loss/recovery signature under (say) both propofol and sevoflurane. So this
body of work is prior art for "loss ≠ recovery, and any candidate must handle both" (acceptance half 1's
premise), but it is not prior art for a candidate that has been shown to do this across agents. If anything
it raises the bar: an agent-invariant candidate has to reproduce an effect that is itself agent-dependent
in magnitude.

### 4. Machine-learning depth indices trained explicitly for agent-invariance

No PubMed-indexed paper doing this was found — see the null search list under item 2. The one clearly
on-topic recent paper, Shen et al. 2026 (PMID 42131603, quoted above), goes the opposite direction: it
uses a conventional multivariate/SHAP panel to show agent identity IS highly recoverable (91.43%
subject-independent accuracy from spectral+aperiodic features) and argues explicitly **for** "agent-specific,
multidimensional monitoring protocols" rather than for agent-invariant ones. That is a useful empirical
anchor even though its conclusion runs counter to Challenge A's goal: it is the first number I found for
"how much agent-identity information does an ordinary EEG feature panel carry" (91.43%, n=44, 2 agents),
which is a baseline a minimisation objective would need to beat down, not a demonstration that it can be
beaten down.

---

## (c) Which half is novel, which is prior art (PARTIALLY — the detail)

**Prior art:**
- That today's commercial scalar indices (BIS, Entropy) are *not* uniformly agent-invariant, and fail in
  specific, well-characterised ways on ketamine, nitrous oxide, dexmedetomidine and (with caveats) xenon —
  extensively documented across two decades of trials and two contemporaneous reviews (PMID 16634416,
  16634417, 16634415).
- That loss and recovery are asymmetric (neural inertia / hysteresis) — established in animals and humans,
  independent of agent (PMID 20689589, 28665814, 30835820). A candidate that only fits a dose-response curve
  and not a transition is answering a premise the field already knows is wrong.
- That a *consistency-across-agents* design goal has been pursued before, at least once, explicitly, for a
  commercial index (PSI, PMID 14742326) — validated the way the prior session in this project mistakenly
  treated as the whole task: pooled/per-agent regression agreement.

**Novel, as far as this search reached:**
- The **adversarial/minimisation framing itself** — building or scoring a candidate against how LITTLE
  agent-identity information it retains, as a first-class quantity to be minimised, rather than testing
  agreement after the fact. Nothing in the clinical/EEG anaesthesia literature indexed by PubMed does this
  (searched seven ways, zero hits; ML-methods venues outside PubMed's coverage are an acknowledged gap, not
  a checked negative).
- A **quantified baseline for how much agent-identity information an ordinary EEG feature panel carries**
  now exists (91.43%, Shen 2026) as a number to try to beat down — nobody has framed it as a bar to clear
  in the invariance direction; the paper that produced it argues for embracing the opposite.
- Reproducing the **hysteresis loop itself** (not just steady-state values) equivalently across two or more
  agent classes has, as far as this search found, never been attempted, let alone shown.

---

## (d) Can a project with two anaesthetic arms in one registry deposit say anything new?

This project's own dataset brief (`bsde/docs/BRIEF_02_DATASET_STRATEGY.md`) identifies VitalDB as the
candidate large-scale two-arm deposit — 6,388 surgical cases with both propofol and volatile-agent
(sevoflurane) exposure recorded, explicitly flagged there for "Propofol-versus-sevoflurane analyses." The
same document states plainly, in its own words, what VitalDB **cannot** do: **"VitalDB generally does not
provide precise behavioral consciousness testing throughout surgery. Surgical timestamps or BIS values must
not be treated as perfect awareness labels."**

Given that, and given the evidence above, an honest answer has three parts, stated as my own assessment
(not sourced from the literature above):

1. **A two-arm agreement analysis on VitalDB alone — "does my candidate correlate similarly under
   propofol and sevoflurane" — would not say anything the field does not already have.** Prichep 2004
   validated PSI-style consistency across *five or six* agent classes with per-agent regression; Soehle 2008
   did a tight single-agent (sevoflurane) head-to-head against BIS. Two arms, correlational, is a weaker
   design than what already exists in print, not a stronger one, and per rule 45 above needs a named
   incumbent (BIS, on the same cohort, is the obvious one) or it proves nothing.
2. **What VitalDB's two arms COULD say something new about is exactly the untested half: agent-identity
   minimisation as an explicit criterion**, because nobody appears to have registered that objective before.
   A design that (i) fits a state-tracking target using both arms pooled, (ii) explicitly and separately
   scores how much a classifier can recover agent identity from the candidate's representation (with the
   91.43%-style panel-level number as a concrete floor to beat), and (iii) reports the two as a genuine
   trade-off curve rather than a single agreement statistic, would be doing something this search did not
   find anywhere in the literature — clinical or (as far as reachable) ML.
3. **The behavioural-label caveat is the load-bearing risk**, per rule 86 in this project's own catalogue:
   if "loss/recovery" in a VitalDB-based design is operationalised from BIS or from surgical/anaesthesia
   record timestamps rather than a true behavioural assessment, the design risks testing whether a
   candidate can reproduce BIS's own agent-dependent quirks (documented at length above) rather than
   testing consciousness transitions themselves — the exact same trap rule 86 describes for GCS-motor and
   RASS, one level removed. Whichever dataset is chosen for the actual Challenge A registration, this
   should be checked explicitly before the design is written, not discovered afterward.

---

## What was searched and not found (for the record)

No PubMed-indexed paper was found that: (i) states "minimise drug-identity information" or an equivalent
information-theoretic framing as a design objective for an anaesthesia depth-of-consciousness measure;
(ii) applies domain-adversarial training, gradient reversal, or mutual-information minimisation to
anaesthesia EEG specifically to suppress agent-identifiability; (iii) demonstrates any single measure
tracking BOTH the loss transition AND the recovery transition with matched fidelity across two or more
anaesthetic agent classes in one cohort. Absence limited to PubMed/MEDLINE coverage; ML-methods-venue
literature (arXiv/NeurIPS/ICML) was not reachable with the citation-verification tools available for this
task and is an acknowledged gap rather than a checked negative.
