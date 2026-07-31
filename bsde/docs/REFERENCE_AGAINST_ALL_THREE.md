# Using the conditional reference to attack all three challenges

*Written 2026-07-31. The arithmetic in §3 is computed here and verified against its closed form.*

---

## The unifying observation

**All three challenges ask for a measure that means the same thing in different people. Every experiment
this project has run normalises within cohort, which structurally cannot answer that question.**

E39 could not combine `ds004541` and `chennu` into one estimate. E36's legibilities are relative to the
Krause deposit and cannot be carried anywhere. E41's correlations are within eegmmidb. Each is a
*relative* statement, and three relative statements do not compose into an absolute one.

A frozen conditional reference is the first object in this project that would let a number computed in one
place be compared to a number computed in another. That is not a marginal improvement to any single
experiment — it changes what kind of claim is expressible.

---

## 1. Challenge A — it is an EQUIVALENCE question and we have been testing it with DISCRIMINATION statistics

**The blocker as recorded:** every reachable deposit has its two agents in disjoint patients, so agent
identity is confounded with patient identity, electrode type and data quality (E36's structural limit).

**But there is a second problem underneath it that the reference fixes, and it is arguably the deeper one.**
Challenge A asks for a representation that *"predicts loss and recovery of responsiveness across
anaesthetics while minimising drug-identification information."* Every test of that so far — E21, E22, E25,
E29, E35, E36 — has asked **"can a classifier tell the two agents apart?"** and answered with an AUC.

That is a discrimination statistic, and it has the wrong null. Failing to reject "the agents are
distinguishable" is not evidence that they are equivalent; with 10 dexmedetomidine patients, almost nothing
would be distinguishable. **The acceptance condition is an equivalence claim and it needs an equivalence
test — which requires a common absolute scale, because "these two land in the same place" is meaningless on
a within-cohort z-score.**

**What the reference makes possible.** Express each patient's state as displacement from their own
covariate-predicted normal. Then the question becomes: *does propofol at matched unresponsiveness produce
the same displacement as dexmedetomidine, to within a pre-declared margin?* That is a TOST/equivalence
design with a stated indifference bound, and it can **succeed** rather than merely fail to fail.

**It also weakens the confound.** The nesting E36 could not escape is "drug arm inside patient identity".
A conditional reference removes the part of patient identity that age, sex, comorbidity and medication
predict. It does not remove electrode type — intracranial coverage is not covariate-predictable — so the
Krause deposit stays compromised. **The design needs the Turku cohort** (Kallionpää 2020, within-subject
LOR/ROR at constant dosing), which is already a drafted request.

**Concrete next step:** pre-register the equivalence bound *before* any two-agent data arrives. What
displacement difference would we accept as "the same"? Declaring that in advance is the whole discipline,
and it is free to do now.

> ### DONE, AND THE ANSWER IS NEGATIVE — E49, 2026-07-31
>
> The bound was derived from data containing **no drug contrast at all**: two independent studies of the
> *same* agent have a drug difference of exactly zero, so their disagreement is the floor any two-drug
> comparison must clear. chennu and ds005620 are both propofol.
>
> **Zero of eight features are resolvable.** The two propofol studies disagree about the awake→sedated
> displacement by as much as the displacement itself, so a cross-deposit two-drug comparison cannot
> separate drug from deposit **at any sample size**. Worse than a power problem: the sign FLIPS between
> the two studies for `whole_head_exponent` (−0.351 vs +1.005), `relative_alpha_power` (−0.433 vs +0.994),
> `uce_v1` (−0.221 vs +0.996), `spectral_edge_95` and `wpli_alpha`. Only `lempel_ziv` agrees in sign
> across all three deposits.
>
> **So the paragraph above is answered and the optimism in it is withdrawn.** The equivalence framing is
> still the right one — it is the only design that can *succeed* rather than merely fail to fail — but it
> **cannot be run on disjoint deposits**. It requires two agents inside one study. That is exactly the
> Turku/Kallionpää request (within-subject LOR/ROR at constant dosing), which is now the single blocking
> dependency for Challenge A rather than one option among several.
>
> **A partial reprieve, registered but not yet tested (E50).** The sign flips may be an artefact of the
> broadband fit rather than genuine study disagreement: on chennu's dose–response, `exponent_low` tracks
> plasma propofol at ρ = −0.810 and `exponent_high` at ρ = +0.710, while the 1–45 Hz mixture of the two
> retains ρ = −0.130. If E49 is re-run on the sub-bands and they agree in sign where broadband flipped,
> the floor shrinks and part of this verdict is recoverable. **Do not assume that outcome** — the
> prediction is registered precisely so it can fail.

## 2. Challenge B — the reference raises the correlation by a factor we can compute in advance

**The blocker as recorded:** E38 measured the label's reliability at r_sb = 0.2918, capping any predictor
at ρ ≈ 0.54; E41's minimum detectable effect was 0.272 and the incumbent-strength expectation 0.286. A
margin of 0.014.

**The reference attacks the other half of the attenuation product, which E38 never measured.** E38
characterised the *label*. Nobody has characterised the *predictor*. If part of the resting exponent's
between-subject variance is covariate-predictable nuisance — variance that cannot correlate with BCI
ability because it is age and comorbidity — then it dilutes the correlation, and removing it raises the
correlation without recruiting anyone.

**The gain has a closed form**, verified here against simulation to three decimals:

> **r rises by 1 / sqrt(1 − R²_covariates)**

| R² explained by covariates | observable ρ from E41's 0.286 | SE at n = 104 |
|---|---|---|
| 0.0 | 0.286 | 2.96 |
| 0.1 | 0.301 | 3.13 |
| 0.2 | 0.320 | 3.33 |
| 0.3 | **0.342** | **3.58** |
| 0.4 | **0.369** | **3.89** |

> ### MEASURED 2026-07-31 (E54, 745 healthy adults) — AND THE GAIN FOR CHALLENGE B IS ZERO
>
> **`lrtc_alpha`, which IS Challenge B's marker, has R² = 0.0003 [0.0003, 0.0121] on age and sex.
> Gain = 1.000.** The table below forecast 1.05–1.29 from R² of 0.1–0.4; the measured value is three
> orders of magnitude below the bottom of that range. **The conditional reference buys Challenge B
> nothing**, and this section's mechanism is refuted by the very regression it nominated for the job.
>
> The reference is not useless — it is useless *here*. For the normative scale itself the best candidate,
> `exponent_low_robust`, reaches R² = 0.147 (gain 1.083) and also carries the highest five-year ICC
> (0.841, E45), so it remains the right measure to build on. But the Challenge B argument below should be
> read as withdrawn rather than pending.
>
> Two caveats that do not rescue it: these deposits carry no comorbidity or medication, so a HEEDB
> reference could explain more; and the gain was always conditional on the covariate variance being
> unrelated to the outcome, which no cohort here can test.

**And that R² is exactly what Q16's step-4 regression measures.** So the reference work forecasts the
Challenge B gain *before* a single new subject is recruited — the same regression that can kill the
reference idea also sizes its benefit. That is an unusually efficient dependency and it should be exploited.

**One condition that must be checked, not assumed.** The gain holds only if the covariate variance is
unrelated to the outcome. If age predicts BCI ability too, then residualising the predictor on age removes
real signal along with nuisance. **Testable directly: regress the label on age and sex first.** If they
predict it, the covariates must be adjusted on both sides rather than removed from one.

**Where this composes.** eegmmidb ships no demographics at all — E28 names that as its largest weakness —
so the adjustment cannot be applied there. **Stieger 2021 (Q14) carries age, sex and handedness in every
session's metadata.** Q14 and Q16 were queued independently and turn out to be the two halves of one plan.

## 3. Challenge C — the reference gives a referenced measure the one thing the monitor structurally cannot have

**The blocker as recorded:** three instruments, three verdicts, all above chance and none above the
incumbent (E26, E34, E37). E40 then showed the information-horizon question cannot even be posed on DOSE-I.

**Why "above chance, never above the incumbent" might be a reference problem rather than a feature
problem.** Candidate and incumbent are both raw values dominated by the same between-subject variance. If
that variance is largely covariate-predictable, both are diluted by the same nuisance and their *difference*
is exactly where it would be hidden. Removing it from the candidate and not from the incumbent is not
cheating — it is the asymmetry that is available.

**And it is available because BIS has no reference.** BIS targets 40–60 for everyone: a fixed band, no age
term, no comorbidity term, no medication term. **A conditional reference gives a per-patient expectation,
which a fixed target cannot express.** The prior work's own age-stratified depth targets — 1.03 SD in
teenagers rising monotonically to 2.76 SD in octogenarians — are a crude version of exactly this, arrived at
empirically. A covariate model generalises it and makes it principled.

**This is also the challenge where the prior work's strongest claim lives and where our own experiments have
never tested the same comparator.** E26/E34/E37 all measure against SEF95 and explicitly scope themselves
*"never ahead of BIS"*. The lightening-detection claim is against real BIS, on VitalDB, where BIS is
recorded — and `vitaldb_grid.csv` carries `meta_bis`, `meta_emg` and `meta_sqi` on 250 cases with the EMG
proxies already registered.

**Concrete next step, and it is the cheapest of the three:** test whether BIS/candidate discordance
concentrates where the EMG proxies are elevated. Data is local, no new access, and a confirmed EMG failure
mode would make the discordance a finding about BIS rather than a disagreement between two imperfect
instruments.

---

## 4. The risks, in the order they would sink this

**(a) Extrapolation outside the reference's support — the one that would actually kill it.** The reference
is built from **awake routine clinical EEG**. Anaesthesia, coma and DoC sit far outside that state range,
and a covariate model extrapolated beyond its support is dangerous.

The defence is real but must be stated precisely rather than assumed: **the reference supplies the origin
and the scale, not the trajectory.** We are not asking the model to predict what a propofol brain looks
like; we are measuring displacement *from* a well-estimated normal point, in units of that population's
residual spread. That is interpolation in the covariate space (age, sex, comorbidity all lie inside the
reference's range) and extrapolation only along the state axis, which is the axis being measured rather
than modelled. **If a reviewer pushes on one thing, it will be this, and the answer above should be
rehearsed.**

**(b) Montage and hardware transfer.** A reference from 19-channel clinical EEG applied to a 4-channel BIS
strip or a 2-electrode forehead patch. What makes it plausible is the prior work's own delocalization
result — 91 % of the information from a single electrode — and the forward model explaining 99 % of the
frontal-posterior reduction by volume conduction. **That evidence should be re-derived on our own data
before being relied on**, not cited.

**(c) The covariates explain nothing.** Q16 step 4 kills the idea for the price of one regression, and that
is the outcome to want early.

> **Sharpened 2026-07-31, and the risk is now specific rather than generic.** PMID 42294963 reports that a
> theta/alpha ratio corrected for the aperiodic component is **age-independent (r = 0.000)** in a normative
> cohort of 587 adults. R² ≈ 0 means gain ≈ 1, i.e. **no Challenge B benefit at all** for any measure
> engineered that way. Our two carried measures may sit on opposite sides of this — the raw exponent is
> strongly age-dependent, `lempel_ziv` is uncharacterised. **Run the step-4 regression separately for
> `exponent_low` and `lempel_ziv` and do not pool them**, or a pooled R² will hide the case where the gain
> is real for one and zero for the other. See `EXISTING_NORMATIVE_MODELS.md` §3(b).

**(d) The wake AND eye-state detector becomes part of the frozen object.** 94.8 % of strict-normal
recordings contain sleep, so vigilance must be resolved in-signal — **and eye state with it, since it moves
the exponent by d = −0.761 (PMID 42395346) and HEEDB does not record it.** Whatever detector does that is
permanently baked into the reference and must be versioned, hashed and validated like a candidate —
including against the recording-level `awake`/`n1`/`n2` flags as a coarse check.

---

## 5. What to do, in order

1. **Q16 step 4 — the regression.** It kills the idea cheaply if R² is trivial, and if it is not, it
   simultaneously sizes the Challenge B gain via 1/sqrt(1−R²). Highest information per unit of effort of
   anything currently queued.
2. **Challenge C's EMG-discordance test.** Data local, no new access, tests the prior work's strongest
   claim against the comparator our own experiments never used.
3. **Pre-register Challenge A's equivalence bound.** Free, and it is the step that converts a challenge we
   keep failing into one that can be passed.
4. **Check whether age and sex predict the BCI label** before assuming the Challenge B gain is real.
5. **Only then** freeze the reference and re-express one existing result on it.

**The honest summary.** The reference does not make any of the three challenges easy. What it does is
change Challenge A from a question we cannot pass into one we can, give Challenge B a computable gain that
costs no new subjects, and give Challenge C the one structural advantage over a fixed-target monitor that
is actually available. Three different mechanisms, one object — which is what makes it worth building
properly rather than quickly.
