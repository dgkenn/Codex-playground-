# CORRECTION — the three challenges, as actually briefed

*2026-08-03. Raised by the investigator, who was right. My working characterisation had drifted from the
briefs, and recent commits carry the wrong labels. This file is the authoritative restatement; the source
is `UCE_AND_THE_THREE_CHALLENGES.md`, quoted verbatim.*

## What the challenges actually are

| | **as briefed (verbatim)** | what I had been calling it |
|---|---|---|
| **A** | *"predicts loss and recovery across anaesthetics while MINIMISING drug-identification information"* | "discover something new about consciousness on EEG" |
| **B** | *"spontaneous EEG predicting command-following"* | "network measures predicting BCI performance" |
| **C** | *"seeing a transition before the conventional monitor"* | "clinical/comparator work on anaesthesia depth" |

## Why the drift matters, and it is not cosmetic

**Challenge A is a DISSOCIATION requirement, not a discovery brief.** The acceptance condition has two
halves and I was only ever testing one: a candidate must track loss and recovery of consciousness *across
different anaesthetic agents* **while carrying as little drug-identity information as possible**. E05 asked
exactly this and returned indeterminate-but-favourable, with a statistic `S` that is positive when a
candidate follows behavioural STATE and negative when it follows the DRUG.

Consequences for the recent record:

* **E122** (the EEG carries state a complete pharmacology model cannot predict) is **Challenge A**
  evidence, not Challenge C. It is the first half of the acceptance condition.
* **E113** (agent class) and **E120** (opioid exposure) are the **second half** — they are
  drug-identification audits, which is precisely what A asks a candidate to minimise.
* **E109** (BIS's age discordance) speaks to A's cross-population validity.
* The whole irreversibility line (E107 → E133 → E138) was scored against *sleep stage*, which is neither
  loss-and-recovery nor across-anaesthetics. **It was never a Challenge A test at all.** Its subsumption
  result stands as a measurement claim about the power spectrum and says nothing about A.

**Challenge B is COMMAND-FOLLOWING — the covert-consciousness problem — not BCI aptitude.** E41 measured
it directly on 104 subjects with a pre-registered power calculation:

| measure | ρ with motor-imagery ability | 95 % CI |
|---|---|---|
| `relative_alpha_power` (the incumbent) | **+0.2018** | [+0.0050, +0.3857] |
| `uce_v1` | +0.0853 | [−0.1066, +0.2651] |
| `whole_head_exponent` | +0.0490 | [−0.1322, +0.2430] |

Consequences:

* The entire Stieger → eegmmidb → Dreyer line (E86, E106, E114, E124, E125, E129, E131, E132, E134) works
  **motor-imagery ability in healthy volunteers as a PROXY for command-following capacity**. That proxy
  relationship was never stated, never justified, and never tested.
* **Whether BCI aptitude in a healthy volunteer transfers to command-following in a brain-injured patient
  is itself a transport question** — and this session's repeated finding is that transport fails more
  often than it holds. So the proxy is not merely unvalidated; the programme's own central result argues
  against assuming it.
* `relative_alpha_power` at +0.2018 is the **real** Challenge B incumbent. E134 established that nothing
  we built beats the SMR predictor on the proxy; nothing has been tested against this on the target.

## What this does to the "are A and B solved?" answer

Both still unsolved, but for better reasons than I gave:

* **A** has a live candidate line and a defined acceptance condition (`S` positive: follows state, not
  drug) that has never been tested head-on since E05's indeterminate result. E122 supplies the
  state-tracking half and E113/E120 supply the drug-audit half; **they have never been combined into the
  single statistic the brief asks for.** That is the obvious next experiment and it needs no new data.
* **B** has a real incumbent on the real target (`relative_alpha_power`, +0.2018, n = 104) and our
  measures were null against it. The proxy work is not wasted — E129's replication of Blankertz and
  E131's disjoint-predictor finding are genuine — but it is evidence about BCI aptitude, and the brief
  asks about command-following.

## Standing instruction

Every registration must state which challenge it serves **using the verbatim definition above**, and any
experiment scored against sleep stage, BCI accuracy, or a single anaesthetic is not by itself a test of A
or B and must say so.
