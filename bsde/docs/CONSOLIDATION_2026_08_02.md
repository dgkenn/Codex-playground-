# Consolidation — E186 to E204

*Written at the ten-result cadence, which was overdue: 19 registrations since the last one, 17 with
outcomes. Every number here is from the ledger or a result JSON, not from memory.*

    positive 3 | negative 3 | absent 3 | gate_failed 7 | closed 1 | still registered 2

Seven gate failures out of seventeen is the headline about the *process*, not a complaint about it. Six of
the seven were machinery — a gate that could not pass, a control that lacked its property, a statistic
measuring the wrong thing — and each was diagnosed rather than worked around. The catalogue gained seven
rules (section K).

---

## 1. Challenge C — four experiments to learn that we were measuring a proxy

**The question throughout:** is E150's MOAA/S increment explained by a candidate's own trend and
autocorrelation, or does it need the candidate's alignment with *this* patient's state?

| | placebo | preservation gate | outcome |
|---|---|---|---|
| E187 | IAAFT | absolute tolerance 0.05 | refused 3 of 11 |
| E189 | IAAFT | vs surrogate-vs-surrogate | refused **all 11 plus both controls** |
| E190 | circular shift (preservation is a *theorem*) | same | refused **all 11 plus both controls** |
| E191 | both | **none — measured the false-positive rate directly** | answered it |

E190 is what identified the defect as structural. A circular shift multiplies the DFT by a unit-modulus
phase factor, so the periodogram is preserved *exactly*, and the gate refused it anyway. The reason is
arithmetic: **a surrogate-versus-surrogate reference cancels any bias the surrogates share**, because both
sides carry it, while real-versus-surrogate carries it once. Any family with a downward autocorrelation
bias fails at every sample size (**catalogue rule 80**).

E191 dropped the proxy and measured what it stood for — the fraction of pure-noise AR(1) columns that beat
their own placebo at a 5 % bar, on a ladder spanning the real candidates' measured autocorrelation
(0.678–0.955). That is **catalogue rule 79**, and it is the most transferable thing this session produced.

**Then the answer reversed on resolution, and the reversal was predicted before the data.** At n = 20 both
families looked broken; at n = 60 (E197) they are at nominal:

    rung             0.00    0.50    0.80    0.95    0.99      pooled <= 0.95
    iaaft            0.067   0.083   0.017   0.000   0.033(G4)  0.042 [0.023, 0.075]
    circular shift   0.067   0.100   0.017   0.000   0.067      0.046 [0.026, 0.080]
    donor            0.067   0.067   0.017   0.017   0.050(G4)  0.042 [0.023, 0.075]

At n = 20 the Wilson bound crosses nominal between 2 hits and 3, so adjacent integers gave opposite
verdicts (**catalogue rule 85**). E191's and E194's refusals were logged *as* Monte Carlo artefacts at the
time they were logged, on the arithmetic alone — which is the one thing that makes the reversal readable
rather than embarrassing.

**E197 returned FAMILIES AGREE** — the registered prediction. All three families hold nominal at every
rung bracketing the real candidates, and **no pair has non-overlapping Wilson intervals at any rung**, so
the E191 split was a threshold artefact and the registered DISAGREE branch, which required separated
intervals, correctly did not fire. Rung 0.99 is refused for two families at G4 (their surrogates stop
decorrelating, rho 0.358 and 0.325) rather than on its rate, so only `bis_rbr` is unlicensed.

**The conditional secondary, declared at registration, can now be read.** Of the ten jointly licensed
candidates, **eight survive at fraction 0.0000** — surrogate means +0.0005 to +0.0051 against real
increments to −0.0333 — and **five of those are non-muscle**:

    multiscale_entropy_slope  −0.02769      whole_head_exponent  −0.01664
    relative_alpha_power      −0.03331      wpli_theta           −0.00828
    pac_slow_alpha            −0.00157

Two withdraw (`wpli_delta` 0.0550, `wpli_alpha_2ch` 0.0850) and `bis_rbr` is unlicensed. **E187's own
verdict stays NOT-INTERPRETABLE as registered** — it is not overturned, it is bypassed: what E197 licenses
is the *method*, and E187's gate was measuring a proxy that rule 80 shows could only ever fail.

That is Challenge C's first licensed incremental result on DOSE-I, and it cost four experiments to reach
because the first three were gating on the wrong quantity.

**The other lasting product is E194's placebo**, which needs no preservation gate because nothing is
altered: a real contiguous block of the same measure from a different patient (**catalogue rule 82**). It
passes aliveness at 0.0000 and decorrelates at rho 0.056, better than either surrogate family.

---

## 2. Challenge A — a positive, a correction to it, and an honest close

The chain is best read as one measurement rather than five experiments.

| | cohort | what it established |
|---|---|---|
| E186 | VitalDB, 115 cases | **individual non-leakage does not compose** |
| E193 | MGH, 39 cases | the null repair is large; its own new gate fired, and the fault was the gate |
| E195 | — | closed unrun, superseded before executing |
| E196 | MGH | CONSTRUCTED, with the agent demonstrably legible |
| E200 | MGH | the *plain* fit is not special; lambda = 2 is, at 0.0235 |
| E202/E203 | VitalDB, 115 cases | lambda = 2 does **not** confirm: 0.0555 |

**E186's negative is the one worth carrying forward.** Three depth axes, all below their permutation
floors — so on that criterion every arm passes. The matched-strength control separates them: the
all-feature and leaking-feature axes leak less than ~92 % of 2,000 random axes of the same depth strength
(0.0888, 0.0785), while the axis built from E161's *individually non-leaking* features leaks less than only
39 % (0.6092) **and carries the least depth**. Selecting features for individual non-leakage cost signal
and bought nothing.

**E196's positive is real and was mis-describable.** Every gate passed, including a negative capability
gate proving the success rule can fail, and G1b refuted my own registered prediction — the arm is
recoverable from the raw eleven-feature block at k-NN |AUC−0.5| = **+0.4343** against a floor of +0.2429,
where E154 had measured the *median single feature* at 0.1000. Univariate weakness is not multivariate
absence.

But the success rule also fires at **lambda = 0**, and E200's matched-strength control showed the plain
depth fit sits at the **32nd percentile** of matched random axes. So "a depth axis already discards the
agent" is refuted; what is true is narrower — an adversarial objective finds directions chance directions
do not.

**And its size was inflated.** Four lambdas were tested and one cleared (corrected ≈ 0.094) with a
non-monotone profile. Tested as a single pre-registered number on an independent cohort, lambda = 2 gives
0.0553 / 0.0562 / 0.0550 at a 40,000-axis pool — above the bar. **The adversarial term helps on both
cohorts (0.3247 → 0.0235 MGH; 0.0944 → 0.0555 VitalDB); the honest estimate is the smaller one.**

**Bound, measured rather than assumed:** the two reachable cohorts fail for opposite reasons. VitalDB has
the agent contrast and a BIS-derived depth axis that E93 measured saturating; MGH has a behavioural
loss-of-consciousness label and 39 cases. Neither is fixable by analysis.

---

## 3. Challenge B — three independent failures, then a real label

**The pre-cue alpha effect is finished.** E172 found it; E174 did not reproduce it on held-out sessions;
E188 (Dreyer 2023, 72 subjects, 3,544 pairs, decoder alive at AUC 0.639, **real EMG channels null at
p = 0.972**) returned ABSENT in both arms; E201 (continuous pursuit, aliveness established) returned
ABSENT at 0.5134 [0.4850, 0.5406], p = 0.3425. One secondary cleared BH **pointing the wrong way** —
`relative_alpha_power` 0.5396 there against 0.4841 on Stieger. Three independent tests; it holds only in
its discovery deposit.

**Two gate failures that were mine, and both were instructive.** E192 and E199 refused the
continuous-pursuit cohort on `vel_alignment` — the cosine to the *current* target direction — while the
BCI was working the whole time. The reference that settles it was in the deposit from the start: each
session ships a `Chance` run, and my member regex required two uppercase letters. Against it, **26 of 28
subjects track better than their own chance run** (0.4771 vs 0.5864).

**And the actual unblock.** The blocker was never a dataset, it was a label. The GCS motor subscore's top
level is literally *"obeys commands"*, and HEEDB has it. The full extraction has now landed:

    15,444,620 consciousness-assessment rows
     3,000,737 GCS BEST MOTOR RESPONSE rows over **31,897 patients**
               obeys rate **0.767** — minority class 23.3 %, against E204's 15 % floor
        25,653 patients with BOTH a motor score and RASS (the incumbent E204 needs)
       127,728 timestamped recordings over 49,088 patients
        ~31,900 patients with BOTH a label and a recording

That is roughly a thousandfold more command-following labels than Chennu's 32-patient cohort, which was
the only public alternative and is committee-gated. E204 is registered with sedation as the **incumbent**
rather than a caveat, patient-level clustering, and the CMD-shaped question declared as a conditional
secondary.

**Machinery verified on permuted labels** (rule 26), so the registered verdict stays clean for the complete
table. On 327 partial rows over 184 patients every path executes, the feature finite-rate is 1.000, RASS
spans the full clinical range −5 to +3, `minutes_before` is exactly 6.00 for every row — G5 holding by
construction rather than by assertion — and the permuted-label increment straddles zero at
−0.0113 [−0.1602, +0.1612].

**Operational, for whoever runs it next.** The four shards each hold ~2.6 GB after parsing the label
table, leaving ~4 GB free; that is the peak, but it rules out anything else memory-heavy running
concurrently. Pre-filtering the label CSV to patients that have recordings would remove the constraint.
Yield is 0.59 rows per patient, so the complete table should be ~19,000 assessments.

---

## 4. Challenge D — one clean positive

**E198: DEPTH RESOLVES.** Adjacent-stratum resolution out of 3, against a floor measured by within-subject
stage permutation (p95 = 0.00): R_AWAKE **2**, R_SPAN **3**, R_SPAN_DEEP **3**. R_AWAKE fails because N2
and N3 are *identical* on it — deep-end spread exactly 0.0000.

E95 had refused R_SPAN_DEEP at an extreme-percentile fraction of 0.0705 against a round 0.05, while R_SPAN
— which resolves every pair — sits at 0.2028, four times the refused threshold. **The proxy and the
quantity that matters disagreed on E95's own published numbers.**

The recommendation is **R_SPAN, not the deepest reference**, because depth is not free: awake-end spread
falls 0.7674 → 0.5223 → 0.4746 while deep-end spread rises 0.0000 → 0.0559 → 0.1142 (rule 52). Transport
improves too (0.0419 vs 0.0651), so resolution was not bought with transportability. **This supersedes
E91's recommendation**, which was scored on a binary contrast where saturation is free.

---

## 5. What the next session should do first

1. **Done** — E197 returned FAMILIES AGREE and E187's table is licensed for ten candidates, eight
   surviving, five of them non-muscle. Challenge C's open question is now *replication*, not licensing:
   the five non-muscle survivors have been tested on one deposit with one placebo family.
2. **Run E204** once `/tmp/eeg_probe/heedb_cmd_follow.s*.csv` has accumulated. Registered before the data;
   the prediction is ADDS at 0.02–0.06 AUC, and a null would be a serious negative rather than a quiet one.
3. **Do not re-run the Challenge A sweep.** E203 closed it. A successor needs a *cohort*, not another
   estimator — specifically one with both an agent contrast and a non-circular depth label, which neither
   reachable cohort has.
4. **The extractions are ephemeral.** `/tmp` was rolled back mid-session and everything in it was rebuilt
   from scratch; nothing in git was lost, which is rule 38 working as intended. Budget for rebuilding.
