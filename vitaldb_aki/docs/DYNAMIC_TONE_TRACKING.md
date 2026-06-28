> **PENDING CIRCULARITY CHECK (decisive).** This dynamic result validated against EV1000/SVR, which EV1000 computes by PULSE-CONTOUR analysis of the SAME arterial waveform (FloTrac). The within-case signal is carried almost entirely by the **diastolic/MAP form factor** -- exactly the kind of waveform feature FloTrac uses to derive SVR -- so the tracking may be partly CIRCULAR, and the MAP+HR partial does NOT rule this out. The result only SURVIVES hostile review if it ALSO holds against SVR from an INDEPENDENT CO source (Vigilance thermodilution / CardioQ Doppler) -- see docs/INDEPENDENT_SVR_VALIDATION.md (in progress). Until then, treat the within-case tracking as PROMISING-BUT-UNCONFIRMED.

# Dynamic within-case vascular-tone tracking from the arterial waveform

**Read this section first.** This is a *feasibility / proof-of-concept* analysis on
a **seeded N=50 sample** (39 usable) of one single-centre database (VitalDB / SNUH).
It is a **physiologic measurement-validation** study (waveform tone vs a reference
SVR) — there is **no AKI outcome and no leakage firewall** here; everything is read
inside the intraop window. The numbers below are *hypothesis-confirming on a pilot
sample*, not a powered multi-centre validation. Treat them as "the dynamic signal is
real and worth a full run / external replication", not as a finished claim.

Run: `python vitaldb_aki/analysis/dynamic_tone_tracking.py [--n 50] [--window 180]`
(seed 20260626; `--n` / `DTT_N` and `--window` / `DTT_WINDOW` are knobs to scale).
Outputs: `cache/dynamic_tone_tracking_results.json`,
`cache/dynamic_tone_tracking_percase.csv`, this file.

---

## The pivot

The **static** cross-sectional finding (one waveform-tone value vs one measured SVRI
per case, Spearman r ~ 0.49 *across patients*) is defensible but modest and carries
all the between-patient confounding (body size, baseline tone, device calibration).

The **dynamic** question is sharper and more defensible:

> Within a single operation, does the arterial-waveform tone index **track the
> measured SVR as it changes over time** — and does it track SVR *changes* **beyond
> pressure (MAP) and beyond flow (HR)**?

A within-case temporal correlation makes each case its own control and removes ALL
between-patient confounding. If the waveform tracks within-case SVR beyond MAP+HR,
that is **real tone sensing** — the basis for a "real-time A-line vascular-tone /
vasoplegia monitor with no cardiac-output device" (early distributive-shock /
post-CPB vasoplegia / anaphylaxis detection from a line every OR already has).

## Method (one paragraph)

Cohort = caseids with **both** `SNUADC/ART` (500 Hz) **and** a measured `EV1000/SVR`
(or `EV1000/SVRI`) track, from `cache/trks.csv` (248 such cases; a seeded sample of 50
is taken here). Per case we download ART + SVR + `Solar8000/ART_MBP` (numeric MAP),
**purge the big SNUADC waveform after each case** to bound disk, and carve the intraop
window into fixed **3-min windows**. Per window we reuse `features/aline_morphology`'s
per-beat machinery (`detect_beats`, `collect_vascular_cycles`, `tau_decay_for_beat`,
`aug_index_for_beat`) to get **tau** (diastolic decay R·C), **diastolic/MAP** form
factor, **AIx**, and **HR**; we take the **median measured SVR** and **median MAP** in
the window. A window needs ≥8 physiologic beats and ≥2 SVR samples; a case needs ≥5
usable windows. We then compute, *within each case across its windows*: raw Spearman of
each tone feature vs SVR, a composite **tone index = −z(tau) − z(dia/MAP) − z(AIx)**
(higher = more vasoplegic → expect **negative** r with SVR), and **partial** Spearman of
tone vs SVR **given MAP** and **given MAP+HR**. We aggregate the per-case r's (median,
IQR, % tracking, sign test + Wilcoxon vs 0).

## Feasibility confirmed

39/50 sampled cases were usable (11 lost to transient empty ART downloads under shared
bandwidth, not to a method problem — see Limitations). Usable cases had **median 86
windows/case** (range 5–161) — i.e. a long, dense within-case time series. Measured SVR
showed real within-case dynamic range (median CV ~0.18; ranges e.g. 335→4238).

## Results (N = 39 usable cases, 3-min windows)

### A. Raw within-case tracking (median Spearman r across cases)

| feature vs measured SVR | median r | IQR | % cases tracking | Wilcoxon p (≠0) |
|---|---|---|---|---|
| **diastolic/MAP form factor** | **+0.56** | [+0.27, +0.65] | **74 %** (38/39 +) | 3e-10 |
| composite tone index *(expect −)* | **−0.32** | [−0.58, −0.18] | 51 % (32/39 −) | 1e-07 |
| tau (diastolic decay) | +0.10 | [−0.20, +0.52] | 49 % | 0.09 (n.s.) |
| AIx (augmentation index) | −0.14 | [−0.35, +0.11] | 46 % | 0.07 (n.s.) |
| *[context]* MAP vs SVR | +0.42 | [+0.11, +0.60] | 67 % | 1e-04 |
| *[context]* HR vs SVR | −0.27 | [−0.50, +0.09] | 59 % | 0.003 |

The **diastolic/MAP form factor is the standout single feature**: it rises with
vasoconstriction and tracks within-case SVR at **median r = +0.56**, the *same*
direction in **38 of 39** cases. tau and AIx are noisy on raw ART and do **not**
individually track within-case (the static between-patient tau signal does not survive
the within-case decomposition — an honest negative). The composite tone index is
negative as pre-specified (it negates dia/MAP), median r = −0.32.

### B. The defensible-impact test — partial within-case correlation

Does the waveform track SVR **at matched pressure** (given MAP), and **at matched
pressure and flow** (given MAP+HR)? This removes the trivial MAP→SVR and HR→CO→SVR
paths.

| partial within-case r | median r | IQR | % tracking | sign / Wilcoxon p |
|---|---|---|---|---|
| **dia/MAP vs SVR \| MAP** | **+0.58** | [+0.39, +0.68] | **82 %** (37/39 +) | 2e-10 |
| **dia/MAP vs SVR \| MAP, HR** | **+0.57** | [+0.31, +0.68] | **79 %** (35/39 +) | 2e-08 |
| composite tone vs SVR \| MAP *(expect −)* | **−0.36** | [−0.51, −0.12] | 56 % (31/39 −) | 9e-07 |
| **composite tone vs SVR \| MAP, HR** *(expect −)* | **−0.33** | [−0.45, −0.20] | 56 % (**35/39 −**) | **3e-07** |

**This is the headline.** The diastolic/MAP form factor tracks within-case SVR almost
**undiminished** after controlling for MAP **and** HR (r +0.56 raw → +0.57 partial),
shifted from zero in the same direction in 35–37 of 39 cases (Wilcoxon p ≤ 2e-8). The
composite tone index likewise stays robustly negative given MAP+HR (median −0.33,
35/39 cases negative, p = 3e-7). So the arterial waveform tracks SVR **changes** that
are **not explained by pressure or by heart rate** — exactly the signal a tone monitor
would need.

### C. Event illustration

35 of 39 usable cases contained a "large within-case SVR drop" (peak→subsequent-trough
≥ 50 % of the case's SVR range — a candidate vasoplegic episode). In **28 of those 35**
(80 %) the composite tone index moved **concordantly** (rose as SVR fell). This is an
illustration, not a detector evaluation (no labelled vasoplegia events), but it shows
the within-case tracking holds across the very excursions a monitor would target.

## Verdict

**Yes — the arterial waveform dynamically tracks vascular tone within a case, and it
tracks SVR changes beyond pressure and beyond flow.** The diastolic/MAP form factor is
the carrier: it tracks within-case measured SVR at median r ≈ +0.56 and, critically,
that tracking **survives partialling out MAP and HR almost intact** (median r ≈ +0.57,
≈ 35–37 of 39 cases same-direction, Wilcoxon p ≤ 2e-8). The composite tone index shows
the same within-case story in the pre-specified negative direction (median partial
r ≈ −0.33 given MAP+HR, p = 3e-7).

This **supports** the high-impact claim that a standard arterial line — **with no
cardiac-output monitor** — carries a real-time vascular-tone signal, and that the
signal is *not* just a re-expression of the measured pressure or heart rate. It is the
more-defensible upgrade of the static r ≈ 0.49: between-patient confounding is removed
by design, and the partial-given-MAP+HR result closes the "it's just pressure/flow"
objection.

**Caveats on the carrier:** the *single-feature* tau and AIx tracking did **not**
survive the within-case decomposition (honest negative) — the dynamic signal lives
almost entirely in the **diastolic/MAP form factor**, a simple, robust, well-understood
quantity (low diastolic runoff relative to MAP = vasodilation). That is arguably a
*strength* (simple, interpretable, no fragile beat-fitting), but the "tau/AIx tone
index" framing from the static analysis is **not** what drives the dynamic result.

## Honest limitations (do not omit when reporting)

1. **Single centre, EV1000 subset.** SNUH / VitalDB only; only the ~248 cases with an
   EV1000 SVR monitor — a sicker, monitored sub-population, not representative.
   External replication (e.g. a second site / device) is required before any monitor
   claim.
2. **The reference SVR is CO-derived and device-filtered.** EV1000 SVR = 80·(MAP−CVP)/CO
   with an internal smoothing/averaging window, so it can **lag** true tone by tens of
   seconds and shares MAP in its own numerator — which can *inflate* a raw MAP-vs-SVR
   correlation and means our "given MAP" partial is, if anything, **conservative** for
   the waveform but **lenient** in absolute terms. We report the partial precisely to
   blunt this.
3. **N is a 50-case pilot (39 usable).** Adequate to establish the effect and its
   direction with very small p-values, but the per-case r distribution is wide
   (dia/MAP IQR [+0.27,+0.65]); a minority of cases track weakly or in reverse. `--n`
   scales to the full 248 when the ART-download bottleneck clears.
4. **11/50 cases were lost to transient empty ART downloads** (shared proxy bandwidth
   with the concurrent vaso-val extraction), not to physiology. They were silently
   skipped (honest-missing), so the usable set is a convenience subset; a clean re-run
   (idle bandwidth, or an ART-download retry) should recover most of them and should be
   done before the full-N report.
5. **Windowing is a choice.** 3-min windows / ≥8 beats / median SVR are reasonable but
   unvalidated; window length trades temporal resolution against per-window beat count
   and SVR-sample count. Sensitivity to window length is not yet characterised.
6. **Tone index composition.** The pre-specified composite leans on dia/MAP because
   tau/AIx are noisy on raw ART; the headline therefore rests mainly on one feature.
   Reporting the single-feature dia/MAP result directly (as we do) is the cleaner claim.
7. **No labelled vasoplegia events.** The event illustration (C) uses an SVR-drop
   heuristic, not adjudicated distributive-shock episodes, so it cannot speak to
   detection sensitivity/lead-time/specificity — that needs a labelled event set.
