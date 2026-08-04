# E246 — the verdict printed as registered, and it is uninterpretable. The defect is mine.

*2026-08-02. Registered before the run (ledger `E246`, file committed at `dd8a7308ae`). Outcome logged as
`gate_failed`. This note exists because a correction that is not auditable is not a correction.*

---

## What was asked

Challenge C, verbatim: **"seeing a transition before the conventional monitor."** E246 was the first
experiment in the project to test that claim in its own units — seconds — rather than as a
discrimination contrast. Its contribution was never "an index leads BIS", which is published; it was the
**ablation** that removes the two trivial ways to lead a monitor (be less smoothed; be more
trigger-happy). A prior-art check via E-utilities, with the three load-bearing records verified against
retrieved esummary/efetch output, confirmed that ablation is absent from the anaesthesia depth-index
literature and standard one field over, in seizure detection.

That gap is real and the ablation is still worth doing. **The cohort could not support the test.**

## What the run returned

Primary, `whole_head_exponent`, median per-case lead over BIS (positive = candidate first):

| rung | candidate smoothing | n | median lead | 95 % CI |
|---|---|---|---|---|
| L0 | none | 46 | +0.0 s | [−50.0, +10.0] |
| **L\*** | **BIS's measured window (90 s, from the withdrawn estimate — see below)** | **46** | **+20.0 s** | **[−30.0, +30.0]** |
| L2 | 2× that | 46 | +10.0 s | [−20.0, +50.0] |

**ABSENT** under the registered rule. The `ARTEFACT` branch did not fire, because there was no lead at
L0 either — there was nothing for matched smoothing to take away.

| gate | value | |
|---|---|---|
| G1 incumbent alive | BIS detects within ±300 s of `aneend` in **0.343** of 134 usable cases | **FAIL** |
| G2 false-alarm match | BIS **0.000**, candidate **0.0448**, ratio ∞ | **FAIL** |
| G3 capability, both directions | planted +60 s → **+60.0**; planted −60 s → **−60.0** | PASS |
| G4 support | 46 ≥ 40 | PASS |

Placebo P1 (case-mismatched pairing) was evaluable at 200 draws with 0.13 of draws reaching the observed
value, and is correctly marked **NOT INFORMATIVE** — the primary did not exclude zero, so there was no
effect for a fake pairing to fail to reproduce (rule 48). P2 was **NOT EVALUABLE**, exactly as declared
in advance: the extraction covers only ±600 s, so a displaced landmark loses its test span.

## Why G1 failed, measured

Cases carrying **any finite BIS**, and any finite `whole_head_exponent`, in 200 s bins from `aneend`:

| bin (s) | [−600,−400) | [−400,−200) | [−200,0) | [0,+200) | [+200,+400) | [+400,+600) |
|---|---|---|---|---|---|---|
| **BIS** | 130 | 120 | 73 | **33** | **14** | **5** |
| **EEG measure** | 134 | 134 | 134 | 134 | 121 | 71 |

BIS detection times, over 134 usable cases: **46 within ±300 s, 0 outside ±300 s, 88 never.** It is not
that BIS is late. For most cases the monitor has no opinion about the transition at all.

> **CORRECTION, made the same day, to the reason.** This note first said *"the sensor comes off before
> emergence completes"*. That is wrong, and the data to refute it was already in hand. Re-measured over
> all 245 extracted cases, separating *the device still emitting samples* from *the device emitting a
> VALID reading* (BIS emits a literal 0.0 with the index unavailable, so validity is a positive test):
>
> | bin (s) | [−600,−400) | [−400,−200) | [−200,0) | [0,+200) | [+200,+400) | [+400,+600) |
> |---|---|---|---|---|---|---|
> | device emitting | 238 | 228 | 214 | 169 | 121 | 71 |
> | **BIS valid (>0)** | **171** | **126** | **76** | **33** | **14** | **5** |
> | EEG feature computable | 238 | 228 | 214 | 169 | 121 | 71 |
>
> The emitting count and the EEG count are **identical in every bin** — they are the same sensor and the
> same recording. So the strip is still on and still delivering EEG while the index reads invalid: at the
> charted end of anaesthesia only **33 of 169** cases (19.5 %) carry a valid index, and by +400–600 s
> only **5 of 71** (7.0 %). **The monitor is not removed; it declares its own output unusable**, which is
> the documented frontalis-EMG contamination mechanism (PMIDs 16115989, 15109199 and 37756246, all three verified) arriving
> exactly when muscle tone returns. The two readings have different consequences and only one of them is
> true.

## The defect, stated plainly

Both facts that sink this design are written, in plain English, in the module docstring of the adapter
that produced the data — `bsde/src/bsde/ingestion/vitaldb.py`:

> *"the EEG runs past `aneend` and the BIS strip does not"*

> *"`aneend` is not the moment of emergence; it lags it … **windows must be labelled by BIS, not by their
> sign relative to `aneend`**"*

An earlier session wrote those sentences after making and correcting the same mistake. I registered a
design landmarked on `aneend`, against BIS, without reading them. The run then re-measured the same fact
at higher resolution and called it a finding.

So the ABSENT verdict is reported **as registered and not re-run under a changed rule** (rule 58), and it
carries no information about the briefed challenge: it is a null measured against an incumbent that is
absent from the window, on a landmark documented in advance as mis-specified. Catalogue rule **96** is
added for this.

Note also what G3 does and does not buy. The capability gate recovered a planted ±60 s lead **exactly**,
in both directions. The instrument works. That is not a licence, and it did not stop the experiment being
unanswerable — a working instrument pointed at an absent incumbent still returns a number.

## Two things survive the retraction, and both are worth keeping

**1. BIS's effective smoothing window, measured from its own output: 47.6 s (IQR 27.3–74.4, n = 109
cases) — an UPPER BOUND.** Estimated as the integrated autocorrelation time of the 1 Hz BIS trace during
deep anaesthesia, per case, pooled as a median.

> **Corrected after the run.** The figure first written here was **78.7 s**, from a lag-1 AR(1) fit. A
> capability check against a KNOWN rectangular moving average on white noise (rules 23 and 40) shows that
> estimator is biased high by about 2× — true windows of 15 / 30 / 60 / 120 s come back as 28.9 / 59.3 /
> 114.3 / NaN, while the integrated-autocorrelation estimator returns 15.2 / 30.7 / 62.7 / 118.7. The
> AR(1) form is exact only for a series that really is AR(1), and a moving-averaged one is not. **78.7 s
> is withdrawn; 47.6 s replaces it.** E246's L\* rung was consequently set from a window about twice too
> long, which does not change its verdict — that was uninterpretable for the larger reason above — but is
> recorded because the rung was mis-set. It is an upper bound in either case: the displayed index carries
> the device's smoothing *and* the physiology's own autocorrelation, and no estimator on the output alone
> can separate them.

The published literature measures each monitor's **delay** by replaying identical EEG through the devices
— 14–155 s across four papers (PMIDs 16508396, 19648154, 22584557, 32040794) — but not its **averaging
window**, and not from the monitor's own output on ordinary clinical cases. 47.6 s sits inside that delay
range, which is the external consistency check one would want. This is a small, checkable, reusable
number, it now has a capability test behind it, and nothing about E246's failure touches it.

**2. A common z-threshold does NOT equalise two detectors' operating points, and G2 says by how much.**
BIS's held-out baseline false-alarm rate is **0.000**; the candidate's, at the identical threshold, grid
and baseline, is **0.0448**. BIS in deep anaesthesia is far more stable than any EEG summary of the same
signal. Any future matched-false-alarm design must calibrate **per detector to a common measured rate**,
not to a common z. That is a real constraint on the ablation and it was found by building the gate.

## Descriptive screen — reported, not promotable

Four columns returned intervals excluding zero and **all four LAG BIS**: `relative_delta_power`
−135 s [−180, −105], `lempel_ziv` −100 [−170, −25], `exponent_low` −95 [−150, −10], `spectral_entropy`
−95 [−120, −15]. Under the registration these cannot be promoted in the primary's place, and there is a
concrete reason not to want to: the z-threshold detector silently drops cases where a measure never
fires, `n` ranges 40–46 across columns, and that exclusion is therefore outcome-related (rule 14).

## What this means for Challenge C — re-scoped, not stopped

The temporal claim is not answerable against BIS on VitalDB **as landmarked here**, and *more cases will
not change that* — the availability curve above is a property of every case, not of `n`. Two changes are
needed together, and each is an instrument change rather than a threshold change:

1. **A landmark that is neither BIS nor the EEG.** Rule 86 prefers an **exposure** over an observation,
   and VitalDB carries one continuously: the anaesthetic drug record (effect-site concentration, infusion
   rate, end-tidal agent). "The agent was switched off" is precisely timed, independent of both
   instruments, and present for the whole case.
2. **Restriction to the stratum where the incumbent is actually present through the transition** — with
   the exclusion reported and checked for outcome-relatedness, since it plainly is one. At present that
   stratum is 14 cases of 134 at +200–400 s. Reaching 40 needs roughly 400 cases and reaching 100 needs
   roughly 1,000, so the cohort expansion now in progress is what makes the restricted design possible.
   **The expansion is not a fix for the defect above; it is a precondition for the successor.**
