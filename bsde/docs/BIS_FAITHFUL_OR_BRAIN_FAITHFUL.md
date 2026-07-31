# Should the computable comparator reproduce BIS, or reproduce what BIS is trying to measure?

*Decision written 2026-07-31, after E58. It closes the third item left open under QUEUE.md Q22, which asked
whether "closer to BIS is better" should be the default and said the answer had to be decided explicitly
rather than defaulted into.*

---

## The question, and why it is not rhetorical

Q22 exists because BIS is the incumbent Challenge C needs and it only exists where a monitor recorded it.
E26, E34 and E37 all fell back on SEF95 as a proxy and scoped themselves "never ahead of BIS". E58 built the
computable stand-in and measured it.

The obvious success criterion for such a thing is agreement with the device. **That criterion is wrong at the
top of the scale, and this project has the measurements to say so rather than assert it.**

---

## What is actually known, with the source of each number

| finding | measurement | where |
|---|---|---|
| Every VitalDB window at BIS ≥ 80 is a facial-EMG artefact | the experiment closed at its gate on this | **E22** |
| Re-measured independently inside E58's own analysis set | **98.2 %** of the 168 BIS ≥ 80 windows exceed E46's artefact threshold (`meta_emg` ≥ 32.3); median EMG **48.6** vs **26.8** in [40,60); median SQI **69.9** vs **93.7** | **E58** |
| The [60,80) band is partly contaminated too | **35.0 %** above the same threshold, 468 windows | **E58** |
| The target band is clean | **4.6 %** above threshold, 2,879 windows | **E58** |
| A from-scratch index reproduces BIS well inside the target band | median \|err\| **3.47**, against Lee et al.'s **4.1** on their own development data | **E58** |
| …and cannot reproduce it at the top | median \|err\| **29.84** at BIS ≥ 80; handing the model the device's own EMG channel recovers **5.1** units and no more | **E58** |

Two further results stop this from collapsing into "BIS is a muscle detector", which it is not:

* **E43 refuted exactly that claim, in the opposite direction.** At matched conditioning,
  `partial(BIS, EMG | spectral state) = +0.165` against `partial(spectral state, EMG | BIS) = −0.262` —
  asymmetry **−0.0967 [−0.1798, −0.0100]**, and an independent EMG estimate agrees at **−0.2120
  [−0.2889, −0.1286]**. **The broadband spectral measure is MORE muscle-associated than BIS**, which is
  physically sensible: an aperiodic exponent fitted across a band that includes 20–45 Hz is fitted straight
  through where surface EMG lives, while BIS carries explicit EMG-suppression processing.
* **E46 arm B shows what happens when muscle genuinely spikes.** Selecting on EMG's top decile rather than
  on BIS, BIS is the LEAST steady of seven measures (|Δ| **3.922**, against `lempel_ziv` at **1.576**).

Put together, and the combination is not obvious: **BIS's EMG suppression works well enough that at matched
state it is cleaner than a broadband slope — and when muscle genuinely spikes, BIS is the measure that moves
most.** The BIS ≥ 80 population is precisely the muscle-spike population. There is no contradiction; the
suppression has an operating range and those windows are outside it.

---

## The decision

**The comparator is BIS-faithful where BIS is measuring brain, and explicitly refuses elsewhere. It is not
made faithful to BIS's artefact behaviour, at any price.**

Concretely, and these are binding on every downstream use:

1. **Report in [40,60) with ±3.47, and in [0,40) with ±4.76.** Both bands are >94 % clean by the EMG
   criterion and both fidelities are measured, not assumed. *(The [0,40) figure was 5.48 when this document
   was written; E60's two-stage model improved it to 4.76 — and made [40,60) worse, 3.47 → 3.91, which is
   why the deliverable uses the one-stage fit in the target band and the two-stage fit below it. Quoting a
   single model for both bands would misreport one of them.)*
   **Exclude windows the monitor itself flags.** E60 found the [0,20) sub-band carries median |err| 39.96
   under both models and median **SQI 5.1 of 100** — the device reporting a value it declares unreliable.
   `meta_sqi` shipped in the same table from the start and no experiment had used it.
2. **Refuse above 60.** [60,80) is 35 % contaminated and [80,100) is 98.2 %. A predicted value landing there
   is returned as *out of validated range*, not as a number with a wide error bar — a wide error bar invites
   use, and the failure there is not noise but a different signal being measured.
3. **Do not train toward the top of the scale.** Any fit that improves agreement at BIS ≥ 80 is, on this
   evidence, fitting facial EMG. *(This clause originally aimed Q22's open two-stage model at [60,80) "at
   most". **E60 redirected it again, to [0,40), and ran it there** — [60,80) is itself 35 % contaminated,
   and the rule in this document, applied consistently, leaves only the two clean bands. E60 found a real
   gain in [0,40), −0.635 [−1.035, −0.203], against a flat random-partition placebo. Its [60,101)
   improvement of 11.50 → 9.50 is descriptive and **is not claimed**, for exactly the reason in this
   clause.)*
4. **Where a light-end reading is genuinely needed, BIS is not the reference.** VitalDB structurally contains
   no awake-under-monitor windows — the strip goes on after induction and comes off around emergence — so
   this is not a sampling shortfall that more VitalDB cases would fix.

---

## What this costs, stated plainly

It costs the light end of Challenge C. A comparator that refuses above BIS 60 cannot be used to ask whether a
candidate sees emergence coming, on this deposit, at all. That is a real loss and it is not being minimised
here — but the alternative is a comparator that appears to work at the light end by reproducing muscle, and a
Challenge C result built on that would be worse than no result, because it would look like a success.

The honest replacement is a deposit that carries EEG through induction or emergence with a state label that
is not the monitor's own output. **DOSE-I is that deposit** — 171 recordings, per-second MOAA/S and SOC,
566 transitions, raw 125 Hz EEG — and it carries no branded index, which is what makes its label independent.
The cost of this decision is therefore a redirection rather than a dead end.

---

## What would overturn this

* A measurement showing the BIS ≥ 80 windows are NOT predominantly artefact on some other deposit. The
  claim here is about VitalDB, where it has been measured twice by different routes (E22, E58); it is not a
  claim about BIS in general, and BIS monitors in a setting with less facial EMG may behave differently.
* An EMG-suppression stage in our own index that recovers the [80,100) band without also fitting the
  artefact — testable, because a suppression stage that works should improve agreement in that band while
  leaving [40,60) unchanged, and one that is merely fitting muscle will move both.
