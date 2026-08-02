# Challenge C's successor: the landmark becomes the drug record

*2026-08-02, written after E246 and before any successor is registered. Rule 41: the feasibility probe
runs first, the registration second. **Nothing here is registered yet** — this records what was verified
and what the design will be, so that the registration cannot quietly acquire a cohort choice it did not
declare.*

---

## Why the landmark has to change

E246 landmarked on `aneend` and compared against BIS. Both halves failed together: the sensor comes off
before emergence completes, so BIS never reacts, and `aneend` is a charted administrative time that the
adapter's own docstring already flagged as lagging the physiological event. Detail in
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
exactly in both directions in E246 (+60.0 and −60.0) and is reused verbatim. So is the **P1 placebo**,
case-mismatched pairing, which is rule 82's move: the control object already exists in the deposit, so
nothing has to be synthesised and nothing has to be argued about what the synthesis preserved.

And so does the contribution. The prior-art check stands: the anaesthesia depth-index literature measures
each monitor's raw latency (PMIDs 16508396, 19648154, 22584557, 32040794) and never equalises smoothing
or the operating point, while the seizure-detection literature treats matched-false-alarm-rate lead time
as a norm (PMIDs 29873826, 18827312 — both verified against retrieved records). **The ablation is still
the paper.** E246 failed to reach it; it did not show it was not worth reaching.
