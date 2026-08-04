# Challenge C's successor: the landmark becomes the drug record

*2026-08-02, written after E246 and before any successor is registered. Rule 41: the feasibility probe
runs first, the registration second. **Nothing here is registered yet** — this records what was verified
and what the design will be, so that the registration cannot quietly acquire a cohort choice it did not
declare.*

---

## Why the landmark has to change

E246 landmarked on `aneend` and compared against BIS. Both halves failed together: the monitor declares
its own index invalid through most of emergence — while the sensor stays attached and keeps delivering
EEG — so BIS never reacts, and `aneend` is a charted administrative time that the adapter's own docstring
already flagged as lagging the physiological event. Detail in
`bsde/results/e246_first_pass_note.md`.

Catalogue rule **86** says what to reach for instead: prefer an **exposure** — a drug record, a dose, a
time — over an **observation**, because an observation shares method variance with whatever other
observation you compare it against. VitalDB carries an exposure continuously, and it is the machine's own
computation rather than anyone's judgement.

## What is actually there — counted, not assumed

Retrieved from `https://api.vitaldb.net/trks` and `/cases` with `urllib` and parsed directly (never
WebFetch — rules 25 and 39), decompressing the gzip the API returns regardless of `Accept-Encoding`.
`/cases`: **6,388 rows x 74 columns**. `/trks`: **486,449 rows**.

| track | cases, within the 5,871 that carry `BIS/EEG1_WAV` |
|---|---|
| `Primus/MAC` | **5,837** |
| `BIS/BIS` | 5,867 |
| `BIS/SQI` | 5,867 |
| `Orchestra/RFTN20_CE` (remifentanil, effect-site) | 4,503 |
| `Primus/EXP_SEVO` | 3,351 |
| `Orchestra/PPF20_CE` (propofol TCI, effect-site) | 3,344 |
| `Primus/EXP_DES` | 1,891 |

**EEG + MAC + BIS + SQI together: 5,833 cases.** The exposure landmark exists at scale, on essentially
the whole eligible deposit, and it needs no waveform fetch to read.

`Primus/MAC` is the anaesthesia machine's minimum-alveolar-concentration figure, computed from end-tidal
agent. It is independent of BIS, independent of the EEG, present for the whole case, and it moves when
someone turns the vaporiser off. **The landmark is the final descent of MAC toward zero** — the moment
the agent stops being delivered — with the exact threshold and the crossing rule to be derived from the
observed distribution rather than picked as a round number (rule 63), and written down before the run.

## What this does NOT do — stated here so it cannot be quietly assumed later

**It does not unblock Challenge A.** Challenge A needs *loss and recovery* against a state label that is
neither the monitor nor the drug. A pharmacological landmark is not a behavioural consciousness
assessment, and `aneend` is an administrative timestamp — catalogue rule 7 is explicit that billing and
charting tables see acts, not decisions. Noted because the temptation is obvious and because this
project has already had one episode of challenge drift: the presence of sevoflurane (3,351), desflurane
(1,891) and propofol TCI (3,344) arms means VitalDB *could* support an across-agent contrast if a valid
state label ever appeared, and that is a reason to keep the deposit in view, not a reason to reopen A.
**Challenge A stays blocked on the investigator**, as recorded in
`DECISIONS_2026_08_02_LINES_AND_BLOCKERS.md`.

## The three changes the successor carries, each an instrument change

1. **Landmark = the MAC descent**, not `aneend`. An exposure, per rule 86.
2. **Cohort restricted to cases where the incumbent is present through the transition**, with the
   exclusion reported and tested for outcome-relatedness (rule 14 — it plainly is one). The
   monitor-availability probe now running over all 5,866 eligible cases sizes that stratum; the
   restriction rule is written from its output *before* the primary is computed, and the probe reads
   only the two 1 Hz numeric tracks so it can never see a candidate.
3. **Matched false-alarm rate calibrated per detector**, to a common *measured* rate, not to a common z.
   E246's G2 measured BIS's held-out baseline false-alarm rate at **0.000** against the candidate's
   **0.0448** at an identical threshold. BIS in deep anaesthesia is far more stable than any EEG summary
   of the same signal, so a shared threshold is not a shared operating point, and the ablation that is
   the whole point of this line depends on getting that right.

## What carries over unchanged

The **capability gate** — plant a known ±60 s lead and require the estimator to recover it — passed
exactly in both directions in E246 (+60.0 and −60.0) and is reused verbatim. A second capability check,
added after E246 ran, applies the same discipline to the *smoothing-window estimator itself*: pushing
white noise through a KNOWN rectangular moving average and requiring the estimate back. It refuted the
lag-1 AR(1) form E246 used (biased high by ~2×) and licensed the integrated-autocorrelation form, moving
BIS's measured window from a withdrawn 78.7 s to **47.6 s (IQR 27.3–74.4, n = 109), an upper bound**. The
successor takes the corrected estimator and the test that certifies it.

Carried over too: the **P1 placebo**, case-mismatched pairing, which is rule 82's move — the control
object already exists in the deposit, so nothing has to be synthesised and nothing has to be argued about
what the synthesis preserved.

And so does the contribution. The prior-art check stands: the anaesthesia depth-index literature measures
each monitor's raw latency (PMIDs 16508396, 19648154, 22584557, 32040794) and never equalises smoothing
or the operating point, while the seizure-detection literature treats matched-false-alarm-rate lead time
as a norm (PMIDs 29873826, 18827312 — both verified against retrieved records). **The ablation is still
the paper.** E246 failed to reach it; it did not show it was not worth reaching.

---

## The abstract, written before the experiment (investigator's standing rule)

**The one sentence the line would license if it succeeded completely:**

> *A spectral measure of the raw EEG reacts to anaesthetic washout a median of N seconds before BIS does,
> and the lead survives equalising the two detectors' smoothing windows and their false-alarm rates — so
> it reflects information the monitor does not have, not a shorter filter set more loosely.*

**Draft abstract.** *Background.* Depth-of-anaesthesia indices are known to lag the EEG they are computed
from, by 14–155 s depending on device and direction. Claims that a research measure "leads" a monitor are
routinely made without controlling the two ways a detector can lead trivially: a shorter averaging window,
and a threshold closer to baseline. In seizure detection, reporting lead time at a matched false-alarm
rate is standard; in anaesthesia depth monitoring it has never been done. *Methods.* In N publicly
available intraoperative cases (VitalDB), we timed the reaction of a raw-EEG spectral measure and of BIS
to a landmark taken from neither instrument: the anaesthesia machine's own MAC record, at the final
descent when the vaporiser is switched off. We measured BIS's effective averaging window from its own
1 Hz output and smoothed the candidate up to it, and we calibrated both detectors to a common measured
false-alarm rate on a held-out pre-transition baseline. Analysis was restricted to cases where the monitor
remained attached through the transition, an exclusion we report and test for bias. *Results.* [N]
*Conclusions.* [N]

**What this is worth, stated honestly rather than optimistically.** If it works, this is a good methods
paper in a monitoring journal — it would change how index-comparison claims are reported, and the
matched-false-alarm-rate requirement generalises to every future comparison of this kind. **It is not a
high-impact discovery**, and it should not be described as one. A lead of tens of seconds at emergence has
a real but modest clinical reading.

**The strongest single result the line can produce is arguably not the lead at all.** It is the
availability finding, which is already measured and does not depend on E247 succeeding: over 134 cases,
BIS carries a valid reading in 33 / 14 / 5 cases across the three 200 s bins after the charted end of
anaesthesia, while the raw EEG carries one in 134 / 121 / 71. Measured across all 245 extracted cases and
separating *emitting* from *valid*: the device is still emitting in 169 / 121 / 71 and reads valid in
33 / 14 / 5. **The conventional monitor is present and declaring itself unusable through the period it
exists to monitor.** That is a claim about clinical practice and about every study
that has used intraoperative BIS as a reference, it needs no candidate measure at all, and the probes now
running extend it from 134 cases to ~5,800. If E247's primary returns ABSENT, this survives it.

**A pre-committed stop.** If the prior-art check now running establishes that PK/PD hysteresis (`ke0`,
effect-site equilibration) is already the standard framework for "which index reacts to agent change
sooner", and that two indices' equilibration constants have already been compared head-to-head on the
same patients, then the lead question is answered in a better-established language than ours and **the
lead half of this line stops**. The availability half does not depend on it and continues either way.

---

## THE PRE-COMMITTED STOP FIRES. The lead half of Challenge C is abandoned.

*Written immediately after the prior-art check returned, honouring the condition set above rather than
reinterpreting it. Three records verified by Opus against retrieved efetch output, not taken from the
subagent.*

The condition was: *"if PK/PD hysteresis is already the standard framework for 'which index reacts to
agent change sooner', and two indices' equilibration constants have already been compared head-to-head on
the same patients, then the lead half of this line stops."* **Both halves are established.**

**PMID 32925339** — Sahinovic et al., *Anesthesia and Analgesia* 2020, "Influence of an
'Electroencephalogram-Based' Monitor Choice on the Delay Between the Predicted Propofol Effect-Site
Concentration and the Measured Drug Effect." Verified from the abstract: *"we measured the influence of
EEG-based monitor choice, namely Bispectral index (BIS) versus qCON index (qCON) monitor, on propofol PD
hysteresis"*, in 165 patients. That is a head-to-head comparison of two EEG indices' lag on the same
patients. (The subagent reported 49 s vs 53 s; that figure is from full text and is **not** independently
verified here, so it is not quoted as a number — the design is what fires the stop, not the value.)

**PMID 33415524** — Kim et al., *J Pharmacokinet Pharmacodyn* 2021, "Do epoch lengths of hypnotic depth
indicators affect estimated of blood-brain equilibration rate constants of propofol?" Verified verbatim
from the abstract: equilibration half-lives for approximate entropy at epoch lengths of 2 / 10 / 30 / 60 s
are **4.31 / 3.96 / 5.78 / 6.54 min**, against **5.09 min** for BIS, in 63 volunteers.

**PMID 15220769** — Vanluchene et al., *Anesthesiology* 2004, fits pharmacodynamic models for state
entropy, response entropy, AAI and BIS against the same calculated effect-site propofol concentration.

### Why this is a stop and not a refinement

The T1 trivial explanation — *an index leads because it is less smoothed* — is **not an insight this
project would be contributing. It was published with numbers in 2021.** Kim et al. varied nothing but the
epoch length and moved the estimated equilibration half-life by more than 50 %, spanning BIS's own value.
Against that, "we matched the smoothing and the lead survived" is a careful implementation of a control
the field already knows it needs, not a new idea about how to compare monitors.

And the ke0 framework asks the question better. Fitting each index's equilibration constant against a
pharmacokinetic reference is a continuous, model-based estimate that uses the whole trajectory; a
z-threshold crossing time is a single-point statistic that discards it. **When a better-established
instrument for a question already exists, building a cruder one and defending it is not a contribution.**

The matched-**false-alarm-rate** half (T2) does remain absent from this literature, and that absence is
real. But without a lead result to demonstrate it on, it is a methodological comment rather than a paper,
and it is not worth the extraction it would need.

### The synthesis worth keeping, which is a negative result with positive value

**E246's null is what the published PK/PD literature predicts.** Kim's numbers put BIS's equilibration
half-life (5.09 min) squarely inside the range an entropy-family measure takes across epoch lengths
(3.96–6.54 min). If the indices' equilibration constants are that close and the epoch dominates, then a
raw-EEG measure should NOT lead BIS by much once the windows are comparable — which is exactly what E246
measured: **+0.0 s unsmoothed and +20.0 s [−30.0, +30.0] at matched smoothing.** E246 was uninterpretable
on its own terms because its incumbent was absent from the window, and it is worth recording that its
point estimates nonetheless land where prior work says they should.

### What continues

Only the **availability finding**, which was flagged above as not depending on the lead and which needs no
candidate measure at all. Its own prior-art check is running. If that check returns "already known and
quantified", **Challenge C stops entirely** and the honest statement is that the briefed question is
answered — negatively, and by other people — for the deposits available under a public-data constraint.

The MAC landmark probe now running is **not wasted**: the withdrawal-shape distribution it measures is
what any future exposure-landmarked design on this deposit would need, and it costs one small numeric
track per case. It is allowed to finish and its output is kept. Nothing further is registered on it.
