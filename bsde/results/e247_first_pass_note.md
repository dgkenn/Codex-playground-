# E247 — the depth-of-anaesthesia monitor is recording, and silent, through emergence

*2026-08-02. Registered before the run (ledger `E247`, file committed at `8ed6ba36e6`). Outcome logged as
`gate_failed`, which is the registered verdict and a poor description of what happened — see §5.*

---

## 1. What was asked, and what this is not

Challenge C, verbatim: **"seeing a transition before the conventional monitor."** The lead-time half of
that challenge was abandoned earlier the same day on its own pre-committed condition, because the PK/PD
hysteresis literature already compares two indices' equilibration lag head-to-head (PMID 32925339) and
already shows that epoch length alone moves the estimate across BIS's own value (PMID 33415524).

**E247 does not propose a candidate that satisfies Challenge C. It is a finding about the INCUMBENT the
challenge names**, and it must not be written up as a solution to the challenge. No EEG waveform and no
candidate feature was read: the extraction fetches the monitor's two 1 Hz numeric tracks and nothing else.

## 2. The result

**Cohort.** All 5,866 public VitalDB cases carrying `BIS/BIS`, `BIS/SQI` and `BIS/EEG1_WAV` with a sane
`aneend`; 5,619 distinct patients, clustered on `subjectid` because 237 VitalDB cases share a patient.

**P1.** `silent` = the device is emitting samples in the window but not one of them carries a valid
(SQI-positive) index. In `[+300, +600]` s about the landmark, among the 2,128 cases emitting in that
window under **both** landmarks:

| | silent fraction |
|---|---|
| real landmark (`aneend`) | **0.9253** |
| deterministic mid-case placebo landmark | **0.0301** |
| **difference** | **+0.8952 [+0.8821, +0.9081]** |

**The curve, which needs no gate and is the reusable object.** Fraction of cases with a valid index, on
60 s bins, at selected offsets:

| offset (s) | −1770 | −870 | −330 | −150 | +30 | +210 | +390 | +750 |
|---|---|---|---|---|---|---|---|---|
| **valid index, real landmark** | 0.93 | 0.81 | 0.43 | 0.25 | **0.11** | 0.05 | 0.02 | 0.01 |
| device emitting, real landmark | 0.99 | 0.97 | 0.88 | 0.80 | 0.67 | 0.51 | 0.33 | 0.07 |
| **valid index, placebo landmark** | 0.91 | 0.94 | 0.95 | 0.95 | **0.95** | 0.95 | 0.95 | 0.95 |
| device emitting, placebo landmark | 0.98 | 0.99 | 0.99 | 0.99 | 0.99 | 0.99 | 0.99 | 0.99 |

Both curves fall at the real landmark, but **the index fails first and far harder than the recording
ends**. At the charted end of anaesthesia the device is still emitting in 67 % of cases and carries a
usable index in 11 %. At the placebo landmark, inside the same recordings, both are flat across the whole
±1800 s.

**Gates.** G1 passed — reference availability in deep anaesthesia is **0.9440** over 5,804 cases, so the
instrument can see availability and the collapse is not the baseline. G2 passed on sign: +0.8952 /
+0.8976 / +0.8905 at SQI > 0 / ≥ 50 / ≥ 80. G3 passed — 0.9536 of cases admit a valid placebo landmark.
G4 **failed**; see §5.

**A registered prediction that did not hold, recorded because it is worth as much as the gate that
passed.** G2 predicted that stricter SQI thresholds would make the drop *larger*, since they can only
remove valid bins. At SQI ≥ 80 the drop is **smaller** (+0.8905 against +0.8952), because the placebo's
own silent rate rises with the threshold too (0.0301 → 0.0320 → 0.0522) and the difference can therefore
shrink. The gate was on sign and passed; the prediction was separate and failed.

## 3. P2 — under-powered as registered, and therefore not claimed

Among the 2,277 cases emitting in the post-transition window, 170 keep a valid index and 2,107 do not.
Case duration separates them at **SMD +0.3172 [+0.1579, +0.4662]** — the index survives in *longer*
cases — while age (+0.0298), BMI (+0.0019) and ASA (+0.0326) are all null with intervals spanning zero.
By category, the valid fraction is 0.0775 under general anaesthesia, **0 of 66** under spinal, **0 of 17**
under sedation/analgesia, and 0.0519 in emergency cases against 0.0772 in elective.

**None of that is claimed.** The registered floor was 200 cases in each arm and the smaller arm is 170.

## 4. The exclusion, reported per rule 14

P1 uses the 2,277 of 5,866 cases still emitting after the landmark. Against the 3,589 excluded they are
balanced on age (median 59 vs 59), ASA (2 vs 2) and BMI (23.2 vs 23.1) and slightly **shorter** (median
anaesthesia 10,200 s vs 10,980 s). Of the excluded, **3,229 were emitting before the landmark and 1,628
had a valid index there** — so these are cases whose *record* ends, not cases whose monitor never worked.
Of the retained, **2,129 of 2,277 (93.5 %) had a valid index before the landmark.**

That last number is the cleanest way to say the finding: **in the analysis cohort the monitor
demonstrably worked before the transition, and in 92.5 % of those same cases it does not work after,
while still recording.**

## 5. The verdict is NOT INTERPRETABLE, and that is a defect in my registration

G4 bundled two independent support criteria into one gate: "≥ 1,000 cases in P1" **and** "≥ 200 in each
P2 arm". P1's own floor passed at 2,128, more than twice over. P2's arm came in at 170. The single gate
failed, so the file printed **NOT INTERPRETABLE** over a result whose own support criterion passed
comfortably.

**The verdict is reported as registered and the gate has not been split after seeing which half failed**
(rule 58). But a reader who saw only the verdict string would conclude the wrong thing about which claim
the data could not carry, and that is worth stating plainly rather than burying. Catalogue rule **97** is
added: one gate per claim it can invalidate, named for that claim.

What this means concretely: **P1 is supported by every gate that applies to P1 — G1, G2, G3 and its own
1,000-case floor — and P2 is not supported.** The availability finding stands on its own evidence; the
selection finding does not, and needs a successor with an arm-size floor it can meet.

## 6. The limitation that must travel with the number

The real landmark sits **near the end of the recording by construction**, and the placebo sits mid-case.
Conditioning on the device still emitting removes most of that asymmetry — the whole `silent` statistic is
defined only among cases still recording — but not all of it. So the contrast is strictly between *a time
near the end of a record* and *a random time inside one*, and on this deposit those cannot be fully
separated, because anaesthesia end and record end are nearly the same event.

The competing explanation is therefore "signal quality degrades at the end of any recording" rather than
"signal quality degrades at emergence". Two things bear against it and neither is decisive: the
independently documented mechanism is specific to emergence (frontalis EMG returning with muscle tone —
PMIDs 15109199, 16115989, 37756246, all verified), and the decline begins around **−870 s**, well before
the recording starts ending. A deposit where monitoring continues into recovery would settle it; none was
found in a six-archive public sweep.

## 7. Where this leaves the line

The magnitude has never been published, on any deposit, and the selection framing has never been stated —
that was the finding of a dedicated prior-art check before the run, not a hope afterwards. What E247
delivers is the magnitude, on 5,866 public cases, with a placebo landmark that is flat.

**The selection claim is what would make it matter, and it is exactly the half that is not supported.**
A successor should register P2 alone, with a floor it can meet given a valid-index arm of ~170, and should
say in advance that the interesting comparison is categorical (anaesthesia type, emergency status), where
the counts are larger, rather than continuous.

---

## 8. Why there is no E249, and why that is the honest answer

§7 recommends "a successor that registers P2 alone, with a floor it can meet". **I am not writing one, and
the reason is worth stating rather than quietly dropping the recommendation.**

P2's numbers are now known — case duration at SMD +0.3172 [+0.1579, +0.4662], spinal 0 of 66, sedation
0 of 17, emergency 0.0519 against elective 0.0772. A registration written *after* seeing them and run on
*the same rows* would be confirmatory in form and exploratory in fact. That is the precise shape rule 30
and `DISCOVERY_LOOP.md` §2 forbid, and lowering the arm-size floor from 200 to something 170 can clear
would be doing it while looking at the number that failed.

The alternatives were checked and none works:

* **A held-out split of the same deposit** does not help — the pooled result has been seen, so no subset
  of it is naive.
* **The 2,613 mixed-agent VitalDB cases** are not held out; every eligible case was already in E247.
* **Another deposit** is what a confirmatory test needs, and a six-archive public sweep (PhysioNet 712
  projects, OpenNeuro 447 EEG datasets, Zenodo, OSF, Dryad, Figshare) found no fully public deposit
  carrying a conventional monitor's index through a transition at all.

**So P2 is blocked on the same object as the rest of this line: a deposit where monitoring continues into
recovery.** Zenodo `1168447` (Oxford, ultra-slow induction *and* emergence, "data available on request")
is the one candidate found where that is plausible, and confirming P2 is a second reason to want it
beyond settling §6's end-of-record limitation.

Until then P2 stands as it is written above: **reported, labelled descriptive, and not claimed.**
