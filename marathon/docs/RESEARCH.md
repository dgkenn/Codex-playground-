# Evidence base

Six parallel literature reviews, each then attacked by a separate fact-checker whose only job was to
find the wrong parts. **34 of 41 claims in one dossier and 23 of 33 in another came back wrong or
overstated.** That hit rate is the reason this document exists in this form: the corrections are more
useful than the original findings, and several of them changed the code.

Every row below is the *post-correction* version. Where a claim did not survive, it is listed under
"What we threw out" rather than quietly dropped, because knowing which plausible-sounding numbers are
wrong is worth as much as knowing the right ones.

Confidence labels: **[strong]** multiple trials or a meta-analysis; **[moderate]** a single trial or
consistent observational data; **[heuristic]** convention with a sound mechanism but no direct trial.

---

## 1. Prescribing intensity

| Finding | Number | Confidence | Where it lives |
|---|---|---|---|
| HRmax from age | Tanaka: `208 − 0.7 × age` → **187 bpm** at 30. SEE ≈ 7 bpm, individual error up to 20 bpm | [strong] for the population, **[weak] for you** | `physiology.hr_max_estimate` |
| Zones on HR *reserve*, not %HRmax | Karvonen. %HRmax and %HRR diverge most at the low end — exactly where a beginner trains | [strong] | `physiology.five_zone_model` |
| Daniels VDOT from a race result | `VO2 = −4.60 + 0.182258v + 0.000104v²`; `%max = 0.8 + 0.1894393e^(−0.012778t) + 0.2989558e^(−0.1932605t)` | [strong] | `physiology.vdot_from_race` |
| Training paces as fixed %VDOT anchors | E ≈ 0.57–0.625, M ≈ 0.78, T ≈ 0.88, I ≈ 0.97, R ≈ 1.075 | [strong] | `physiology._PACE_FAMILIES` |
| Polarised distribution | ~80% of *time* below LT1. Esteve-Lanao 2007 (*JSCR* 21:943, n=12): low-intensity group improved a 10.4 km run more (−157 s vs −122 s) | [moderate] | `plan` intensity design |
| Talk test approximates VT1 | The first stage where speech becomes effortful. Persinger 2004 | [moderate] | `assessment.lt_speed_from_talk_test` |

**The calibration bug this caught.** Daniels *describes* Easy as "59–74% of VO2max", but his printed
pace table for VDOT 50 says 5:35–6:04/km — which back-solves to about 57–62.5%. Taking the prose
literally puts the fast end of "easy" at **4:54/km, faster than his own marathon pace**. The app
would have prescribed a tempo run every time it said "easy". `test_easy_pace_is_never_faster_than_marathon_pace`
now pins this permanently.

**A second one the checker caught:** a draft had threshold pace at 98% of VDOT. That is *interval*
pace. Shipping it would have turned every tempo run into a VO2max session.

**The VDOT floor.** Daniels' tables start around VDOT 30. Your submaximal seed comes out near 22,
where the formulas extrapolate to an "easy" pace of 10:48/km — slower than a brisk walk. That is not
physiology, it is a quadratic outside its fitted range. So below 30 the app prescribes from the
**HR/speed line your own ramp test measured** (7:25–8:26/km for easy) and switches to VDOT
automatically once a real time trial lifts you past the floor.

---

## 2. Readiness and HRV-guided training

| Finding | Number | Confidence | Where |
|---|---|---|---|
| HRV-guided beats a fixed plan | Vesterinen 2016, *MSSE* 48(7):1347–1354, n=40: **13.2 vs 17.7 hard sessions**, 3000 m improved **2.1% vs 1.1%** — better results from *fewer* hard sessions | [moderate] | `readiness` |
| Confirmed in cyclists | Javaloyes 2019, *IJSPP* 14(1):23–32, n=17, vs traditional periodisation | [moderate] | — |
| Use the 7-day rolling mean, not today's value | Plews 2013 | [strong] | `readiness._rolling_mean_ln` |
| Compute on the log scale | HRV is log-normal, so mean/SD/band must all be on lnRMSSD | [strong] | `NightSummary.ln_hrv` |
| Artifact tolerance for RMSSD | **<5%** rejected beats. RMSSD is the most artifact-sensitive time-domain index | [strong] | `MAX_ARTIFACT_FRACTION` |
| Malik criterion | Reject an interval >20% different from the last accepted one | [strong] | `signal_quality.clean_intervals` |
| Sleep and injury | Milewski 2014, *J Pediatr Orthop* 34(2):129–133, **n=112 adolescents**: <8 h ≈ 1.7× injury risk | [weak transfer] | `SLEEP_FLOOR_MIN` |

**The statistical error we avoided.** A ±0.5 SD band contains only ~38% of *individual* daily
readings, so applying it to today's number flags 3 days in 5 — useless. But the standard error of a
**7-day mean** is `SD/√7 ≈ 0.38 SD`, so the same band is ±1.3 SE and contains ~80%. The band is
therefore applied to the rolling mean, never to a single day. This is a real distinction that a
naive implementation gets wrong and then blames on the sensor.

**Two misattributions corrected.** The 0.5 multiplier is **not** Hopkins' smallest worthwhile change
(that is 0.2 × *between*-subject SD) — it comes from Plews/Buchheit practice on within-individual SD.
And Kiviniemi 2007 is routinely cited as the origin of this rule but used high-frequency R-R power
with a mean−1SD reference, not lnRMSSD with a symmetric band.

**The invented band we deleted.** A draft had a "supercompensated → add an extra hard session" state.
No such band exists in any of the anchor studies: they prescribed hard work when HRV was *within or
above* the range and easy/rest only when below. So `primed` and `normal` now map to the **same
action**. Above-band is informative to see and never authorises extra load — the asymmetry is
deliberate, because the cost of a wrong upgrade is a lost week and the cost of a wrongly easy day is
one easy day.

**The Eight Sleep problem, stated plainly.** The pod is under-mattress ballistocardiography, not PPG,
and its HRV output is not independently validated — community reverse-engineering suggests only heart
rate has been checked. Worse, **HealthKit exposes only SDNN** (`heartRateVariabilitySDNN`); there is
no RMSSD type and no beat-interval type, and SDNN cannot be converted to RMSSD. Since device, posture
and window length each shift lnRMSSD by more than the band being detected, `hrv_baseline` now
**refuses to mix sources** and keeps one series per `(source, posture)` pair. Your Polar-derived
RMSSD from the SleepController is the authoritative series; anything from Apple Health is a separate
one with its own baseline.

---

## 3. Load, and what the numbers can't see

| Finding | Number | Confidence | Where |
|---|---|---|---|
| Banister TRIMP | `duration × ΔHR × 0.64 × e^(1.92ΔHR)` (men) | [strong] | `load.trimp_banister` |
| Convexity matters | 30 min @ 170 + 30 min @ 110 ≫ 60 min @ 140. Use segments, not session means | [strong] | `trimp_banister_series` |
| Monotony / strain | `mean/SD` of daily load; strain = weekly load × monotony; >2.0 flags | [moderate] | `load.monotony_strain` |
| ACWR, EWMA form | λ = 2/(n+1), 7 and 28 days (Williams 2017) | [contested] | `load.acwr` |
| Strength training prevents injury | Lauersen 2018, *BJSM* 52:1557: **RR 0.338** (95% CI 0.238–0.480), 6 RCTs, 7,738 participants | [strong] | 2 sessions/week, always |
| Strength improves economy | Blagrove 2018, *Sports Med* 48:1117 | [moderate] | — |

**ACWR is a speed limit, not a risk score.** Impellizzeri 2020 (*BJSM* 54:1073) and 2021 show the
"sweet spot" analyses suffer from mathematical coupling — the acute load sits in both numerator and
denominator — and Wang 2020 failed to replicate the injury relationship. So the app uses it to cap
how fast the plan may *add* load and never claims it predicts injury. `ACWR_CAUTION` says so in the
code, and it is surfaced to you whenever the ratio triggers a cut.

That same coupling defeated my first implementation: cutting to `chronic × 1.30` didn't cut anything,
because a big spike inflates `chronic` enough that the "target" landed above the volume being
reduced. It now scales by `1.30 / ratio`, which only uses the ratio and is immune.

**The 10% rule has never been supported by a trial.** Buist 2008 (*AJSM* 36:33) randomised novices to
graded vs standard progression and found **no difference** in injury rate. A cap is still imposed,
because "no evidence 10% helps" is not "evidence 40% is safe", and the failure mode being guarded
against is slow to appear and slow to heal.

**Garmin-RUNSAFE, framed correctly.** 5,205 runners, 588,071 sessions: hazard is elevated for a
single run exceeding the previous 30 days' longest, and rises continuously from the *smallest*
progression band upward. The authors use this to argue there is **no safe threshold** — a draft of
this research inverted that into "risk rises once you exceed 10%", i.e. turned a paper debunking the
10% rule into support for it. `safety.single_run_progression` returns a graded caution with no
pass/fail line.

### Bone is the blind spot

The most important thing the review surfaced is something the engine originally had *no model for at
all*. TRIMP, ACWR, HRV and readiness are all cardiovascular or autonomic. **Bone appears in none of
them.** Bone remodels over months while aerobic fitness improves in two to three weeks, and that gap
is the mechanism: you can be green every single morning and still be twelve weeks into building a
tibial stress fracture. Novice bone stress injuries cluster in the first few months of running.

`safety.bone_load` now tracks this separately, and for the first ~20 weeks it argues for frequency
over session length, varied surfaces, and treating focal bone pain as a stop rather than a niggle.

---

## 4. Structuring the plan

| Finding | Number | Confidence | Where |
|---|---|---|---|
| Taper | Bosquet 2007, *MSSE* 39:1358: **2 weeks, 41–60% volume cut, intensity and frequency maintained** | [strong] | `plan.taper_weeks` |
| Long run ceiling | Daniels: the **lesser** of 25% of weekly volume (30% under 40 km/wk) or **150 minutes** | [moderate] | `LONG_RUN_MAX_MIN` |
| Riegel | `T2 = T1 × (D2/D1)^1.06`, valid ~3.5–230 min | [strong] | `physiology.riegel_predict` |
| Riegel over-predicts for novices | Vickers & Vertosick 2016, n=2,303 recreational runners: over-predicts the marathon by **10–20 min**; best-fit recreational exponent ≈1.07–1.08 | [moderate] | `RIEGEL_NOVICE_EXPONENT = 1.15` |
| Run-walk for beginners | Galloway's own chart is finer-grained than the versions circulating online (12:00/mi = 2:1, 10:00 = 3:1, 9:00 = 4:1) | [heuristic] | `_RUN_WALK_LADDER` |
| 3 runs/week can work | Furman FIRST (Pierce, Murr & Moss): 3 quality runs + 2 cross-training maintained or improved performance | [moderate] | the whole schedule shape |
| In-race carbohydrate | 30–60 g/h; **≥90 g/h from ~2.5 h** using multiple transportable carbohydrates, ratio **~1:0.8** glucose:fructose (superseding the older 2:1) | [strong] | long-run fuelling cues |
| Caffeine | 3–6 mg/kg, 30–60 min pre-race | [strong] | `safety.hydration_plan` |

**The long-run cap was wrong and biased long.** I had used 180 minutes on the strength of the
widely-repeated "3 hours" convention. Daniels' actual limit is **150 minutes** — my number exceeded
his by 20%, in exactly the population least able to absorb the extra half hour. Now 150 min
everywhere, with 165 min allowed only for the biggest peak-phase rehearsal runs, and the share rule
tightens from 30% to 25% once weekly volume passes 40 km.

**Where we deliberately stay more conservative than the correction.** Vickers suggests a recreational
exponent of ~1.07–1.08 for half→marathon. The app uses **1.15** from 5K→marathon, because
extrapolating across that much larger distance ratio for someone with no endurance base is a
different and much less reliable problem. An over-optimistic marathon prediction is the mechanism by
which first-timers blow up at 30 km, so the error is deliberately pointed the safe way. In practice
the app shows no marathon prediction at all until you have raced a half — nothing is predicted beyond
2.5× the longest distance actually covered.

**The strength protocol we refused.** A draft prescribed 3–6 reps at 80–90% 1RM plus weekly
plyometrics from the end of phase 1, citing Blagrove. Those protocols were run in *trained runners
with lifting backgrounds*. Prescribing near-maximal loads (and implicit 1RM testing) is a well-known
injury mechanism in the untrained. You already lift, which resolves this differently: the app adds
running-specific work at 8–12 reps to your existing sessions rather than prescribing a new programme.

---

## 5. The sensor

| Finding | Detail | Where |
|---|---|---|
| PMD service UUIDs | `FB005C80/81/82-02E7-F387-1CAD-8ACD2D8DF0C8` | `PolarPMD.swift` |
| PPI sample layout | 6 bytes: `hr:u8, ppi:u16LE, error:u16LE, flags` — bit0 blocker, bit1 skin contact | `parsePpiFrame` |
| **Verity has no RR in 0x2A37** | Unlike the H10, beat intervals come **only** via PMD/PPI | forces the two-mode design |
| **PPI throttles HR to 5 s** | With PPI enabled, HR updates every ~5 s; first PPI batch takes ~25 s | forces the two-mode design |
| CHANNELS is 1 byte | Not uint16. Encoding it wide misaligns every following TLV | `PmdSetting.fieldSize` |
| Compression is bit 7 only | Low 7 bits are an independent raw-layout id; 0x02 means 24-bit *raw* | `parseAccFrame` |
| SDK mode destroys HR and PPI | Never enabled; no opcode for it exists in the codec | file header |
| HealthKit HRV is SDNN only | No RMSSD, no beat intervals | `hrv_source` tagging |

**The architectural flaw this caught.** My first `VeritySensor` enabled PPI during runs. Since PPI
drops HR updates to every 5 seconds, every real-time decision would have been made on heart-rate data
5 seconds stale — a meaningful fraction of the 45-second HR time constant the controller is built
around. The app would have *appeared* to work. It now has two explicit modes: `.run` uses the standard
HR service at ~1 Hz plus ACC for cadence and does not start PPI at all; `.rest` uses PPI for overnight
and orthostatic HRV, where a 5-second update costs nothing.

This is confirmed by your own `polar_pmd.py`, which already records `PPI_HR_UPDATE_S = 5.0`.

**Cadence lock-on** is the failure mode worth the most engineering. The PPG algorithm latches onto
step frequency and reports a rock-steady, physiologically plausible "heart rate" that is actually your
cadence — and because it has *lower* variance than real data, any smoothness-based quality check
prefers it. The only reliable detector compares HR against cadence, which is why the app streams the
accelerometer rather than just heart rate.

---

## 6. Real-time control

| Finding | Number | Where |
|---|---|---|
| HR responds as first-order + dead time | τ ≈ 30–60 s, dead time a few seconds | `TAU_HR = 45` |
| Control on predicted steady state | `HR_ss = HR + τ·dHR/dt` | `predict_steady_state_hr` |
| Feedforward gain from the athlete | `Δspeed = ΔHR / slope`, slope in bpm per km/h from the ramp | `speed_correction` |
| Grade cost | Minetti 2002: `Cr = 155.4i⁵ − 30.4i⁴ − 43.3i³ + 46.3i² + 19.5i + 3.6` | `minetti_cost` |
| Aerobic decoupling | Friel: <5% means genuinely aerobic | `decoupling` |
| Cue fatigue | Event-triggered cues, not continuous narration | `CueScheduler` |

Why not a PID loop on heart rate: the HR you can see belongs to the speed you were running half a
minute ago, so a controller that reacts to it chases its own tail — slow down, HR keeps rising, slow
down again, end up walking, HR drops below target, speed up, repeat. Three mechanisms fix it: lead
compensation, a feedforward gain taken from *your own* ramp slope rather than a guessed constant, and
a deadband plus confirmation window plus rate limiting. `test_controller_does_not_oscillate` simulates
an obedient runner with a realistic first-order HR response and asserts convergence in ≤6 cues over
20 minutes.

The Minetti polynomial's minimum is at a **downhill** grade near −10%, not at zero — gentle downhill
running is genuinely cheaper than flat, which is why naive distance-only pacing punishes hills twice.

---

## What we threw out

Claims that came back fabricated or badly wrong, listed so they don't creep back in:

- **A polarised-training subgroup finding** that the advantage "washes out beyond 12 weeks" — the
  cited review's studies were *all* 4–13 weeks and it contains no duration subgroup analysis.
- **"Injured runners averaged 31.6% ± 3.1% weekly increases vs 22.1% ± 2.1%"** — the real SDs are
  ±63.1% and ±62.1%, P = .07, *not significant*. The quoted SDs were off by ~20×, which turned a null
  result into a headline.
- **"1 in 8 (14.3%)"** — 1/8 is 12.5%. Arithmetically impossible figures in a cited result.
- **Vesterinen 2016 in *Scand J Med Sci Sports*** with n≈108 — wrong journal, wrong sample size; that
  PMID is a different paper entirely.
- **Milewski n=160 with "65% vs 31% injured"** — n was 112 and that percentage pair is not in the paper.
- **A composite readiness z-score** with weights summing to 1 and ±0.5 thresholds — a weighted sum of
  correlated z-scores does not have SD 1 (typically 0.5–0.7), so the thresholds would fire far less
  often than intended. It also had a double-negated sign on resting HR.
- **Pfitzinger 18/55 details** — long runs start at 15 mi and peak at 22 mi with three 20-milers, it
  already contains midweek medium-long runs and 2+ quality sessions, and no prior marathon is required.
- **Galloway ratios** transcribed from a third-party site rather than his own chart.

## What we deliberately did not build

- **Cadence targets.** The "180 spm" figure is a misreading of Daniels' observation of *elites at race
  pace*. What has evidence is a **relative** +5–10% increase from a runner's own baseline reducing
  per-step load (Heiderscheit 2011, *MSSE* 43:296) — which is why the app records cadence at each
  speed during the ramp and never displays a target.
- **Shoe prescription by foot type.** Repeatedly falsified.
- **A single-day HRV gate.** Statistically unsound, as above.
- **Any streak mechanism.** See `APP_LANDSCAPE.md`.
