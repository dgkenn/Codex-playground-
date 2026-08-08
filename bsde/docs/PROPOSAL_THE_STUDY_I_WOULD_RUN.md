# The study I would run, and the one I would run first

*2026-08-07. Written after ~40 registered experiments this session across VitalDB, Krause, Sleep-EDFx and
the project's own register. Every design constraint below is derived from something that actually failed,
with the experiment named.*

---

## A. The scientific study: **reported experience, responsiveness, and drug — separated in the same people**

### The question

Brief 01 asks to separate arousal, cognitive-processing capacity, command-following and behavioural
output. Every experiment in this programme has measured **one arousal axis**, because no cohort it could
reach dissociates them. The single design that came closest (E321) worked only because Krause happens to
contain natural sleep *and* anaesthesia in the same 18 patients — and it still had to use **REM as a
proxy for conscious experience without a report**, which is an inference from the literature, not a
measurement.

### What the cohort must contain, and why each element is forced

| element | why, with the experiment that forced it |
|---|---|
| **Serial awakenings with experience reports** in both sleep and anaesthesia | E321/E322: REM-as-proxy is the weakest link. Without reports, "conscious" is assumed. |
| **Two mechanistically distinct anaesthetics** (e.g. propofol + dexmedetomidine) | E299: the entire VitalDB depth gradient was carried by one drug-class contrast. One agent cannot separate drug from state. |
| **Natural sleep in the same subjects** | E306: the no-drug placebo is what licensed the drug interpretation. Between-subject controls cannot do this. |
| **A graded behavioural scale (MOAA/S or OAA/S) scored independently of the EEG** | E295/E302: every depth axis available to us was either EEG-derived (circular) or drug concentration (failed its own validity check at ρ = −0.05 against BIS). |
| **High-density scalp EEG** | E322 and E248: `uce_v1` and four connectivity measures are uncomputable on 2 channels; the flagship candidate has *never* been evaluated on a dissociation contrast. |
| **A muscle channel** | E322: the EEG-derived muscle proxies point the *opposite way* to real submental EMG in REM (+1.27 vs −0.33). Without a real channel you cannot tell muscle from cortex. |

### The design

Healthy volunteers, within-subject, three sessions:

1. **Full-night PSG** with serial awakenings (~15–20 per subject) and immediate experience reports.
2. **Propofol** sedation, stepped to unresponsiveness, with serial awakenings and reports at each level.
3. **Dexmedetomidine**, same protocol, order counterbalanced.

Yielding, per subject, a 2×2 that has never existed in one cohort: **{responsive, unresponsive} ×
{experience reported, none}**, crossed with **{no drug, drug A, drug B}**.

### Sample size, from measured quantities rather than convention

E321's within-patient dissociation on 18 patients gave z-differences of +1.79 to +2.01 with sign-flip
p ≈ 0.002. The binding constraint is not subjects but **awakenings per subject**: E323 failed because 13
patients × 5 coarse labels could not support a multi-measure comparison, and E322 showed a contrast
passed by 13 of 16 measures is uninformative. **~40 subjects × ~15 awakenings each** puts the
unresponsive-with-experience cell — the rare and decisive one — at a usable size, and that cell's
prevalence is the number the pilot must establish first.

### What it would settle

Whether **any** measure tracks reported experience independently of responsiveness and of drug identity.
A positive names the first genuine cognitive-processing marker. **A negative is equally publishable and
this programme's own evidence leans that way**: E322 found 13 of 16 measures "dissociate" REM from N3, so
most of what looks like a consciousness signal is sleep-stage physiology.

### Why it is not incremental

The serial-awakening paradigm exists for sleep. Anaesthesia awakening studies exist (ds005620, whose
report labels were never deposited — Q11). **Nobody has run both, in the same subjects, with two drugs
and a muscle channel.** That is the gap, and it is an acquisition problem, not an analysis problem.

---

## B. The study I would run **first**, because it is tractable now

**A multi-site register of pre-registered biomarker experiments.**

E330/E331 measured, on 225 registrations: **24.0 %** died on machinery before testing their hypothesis;
the true positive rate was **31.6 %** against the 100 % a positives-only literature implies; and **29.6 %
of machinery failures were the analyst's own apparatus** rather than the data.

Those numbers have one fatal weakness: **n = 1 programme, one analyst lineage.** They are not a sample of
anything.

**The study:** recruit 4–6 labs doing EEG/biomarker discovery to keep an append-only register for 12
months — each design records its primary, gates, placebo and incumbent *before* running, and an outcome
after. Nothing else changes about how they work. Then report the machinery-failure rate, the positive
rate, the analyst-defect fraction and the qualification rate among positives, across labs.

**Why this first:** it needs no new data collection, no ethics beyond consent to share metadata, no
patients, and it produces a quantity **no published literature can contain** — because the register is
the only place a dead experiment survives. It also directly serves the BSDE brief, whose stated asset is
the *verifier*, not any biomarker.

**The honest risk:** labs may decline, because the output is unflattering by construction. A pilot with
two friendly groups would establish whether the rates are anywhere near ours before anyone commits.

---

## Which I would choose

**B first, A as the flagship.** B is cheap, fast, needs nothing I do not already have a working method
for, and converts this session's most novel result from an anecdote into evidence. A is the science that
matters and is a multi-year acquisition programme.

**What I would not do is another analysis of VitalDB or Krause.** Three designs on Krause in one session
each returned a statistic that could not beat its own control (E320, E323) or was passed by nearly
everything (E322). The binding constraint has been a cohort for some time, and the register now
quantifies how often continuing past that point produces a refusal rather than a result.
