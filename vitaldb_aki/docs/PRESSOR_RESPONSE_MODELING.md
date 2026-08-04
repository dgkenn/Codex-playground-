# Pressor-responsiveness modeling -- confounder-controlled (pivot #1)

Estimates A-line pressor responsiveness (dMAP per unit dose) with every relevant confounder controlled, to verify there is a TRUE between-patient vasoreactivity signal for a waveform model to predict -- not just confounding by baseline state, body size, drift, anaesthetic depth or preload. Events: cache/pressor_response_events_v2.csv.

- Clean up-titration events (isolated, no concurrent fluid): **397** over **72** cases (total steps extracted 898).

## Titration-by-indication (the core threat)
- {'corr_dosestep_vs_basemap': -0.332, 'corr_dosestep_vs_preMAPslope': -0.311, 'median_basemap_up_titration': 66.8, 'median_basemap_down_titration': 80.6, 'interpretation': 'closed-loop confounding present (titrate UP when MAP low/falling) -> raw event-anchored dMAP is reverse-confounded; valid responsiveness needs conditioning on base_map+pre_slope (done in the adjusted model) or a stable-epoch dose-requirement estimand'}
  Clinicians titrate in a CLOSED LOOP off the MAP they see, so a raw post-step dMAP is reverse-confounded (dose up *because* MAP is low/falling). This is why the naive within slope can be negative; the adjusted model below conditions on base MAP + pre-step slope to break the loop.

## Responsiveness estimates, naive -> fully controlled
- **(a) Raw between-patient** dMAP/dose (CONFOUNDED): median 3.125, SD 2220.135.
- **(b) Within-patient FE slope** (detrended; removes ALL stable patient confounding): 0.5035 CI [-1.8904, 0.7233] (n_obs 397, cases 72).
- **(d) Within-patient + full covariate adjustment** (base MAP/dose, HR, CVP, BIS/MAC/propofol/remi change, step index, time): dose-coef -0.1339 (retains -0.27 of the unadjusted within slope).
- **(e) Between-patient residual** (per-case adjusted slopes, >= 3 events/case): {'n_cases': 54, 'median': 1.1669, 'iqr': [-24.5449, 73.7356], 'sd_between_patient': 161.0649, 'frac_blunted_or_negative': 0.463}.

## Falsification / construct validity
- **Down-titration negative control:** {'n': 361, 'median_dmap_detrend': -0.81, 'expected': 'negative (MAP falls when pressor reduced)', 'pass': True}.
- Anaesthetic-depth change is included as a within covariate (d): the dose effect is the part of dMAP NOT explained by a simultaneous BIS/MAC/propofol/remi shift.

## Verdict
NO-GO / WEAK -- after full confounder adjustment the within-patient dose-response or its between-patient variance collapses; raw responsiveness was largely confounding, leaving little independent signal for a waveform model. Adjusted dose-coef retains -27% of the unadjusted within slope.

## Honest caveats
- **Dose units:** Orchestra RATE is device units (mL/h); absolute ug/kg/min needs the per-case drug concentration, which VitalDB does not expose. The WITHIN-patient slope is valid (concentration constant within a case); BETWEEN-patient absolute responsiveness assumes comparable concentration -> headline restricted to within-patient + per-kg step.
- **Confounding by indication remains** for the raw estimate; the within-patient design + covariate adjustment is the mitigation, not a randomised dose.
- **Single-centre (SNUH/VitalDB);** external replication required.
- This is the responder-LABEL validation; the waveform predictor itself (does pre-step morphology predict the per-case adjusted slope?) is the next, GPU-optional build.
