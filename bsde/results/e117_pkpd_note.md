# Is E117 using proper propofol PK/PD modelling? No — and here is what that does and does not cost

Raised by the investigator, 2026-08-01. Diagnostic only (rule 41); no registered result is changed.

## What each experiment actually uses

| experiment | deposit | drug variable | what it is |
|---|---|---|---|
| **E117** | chennu | `plasma_propofol_ug_per_L` | **measured blood-plasma assay (Cp)**, used raw — no PK model, no effect-site compartment, no `ke0` |
| E110, E112, E118, E113 | VitalDB | `ppf_ce` | `Orchestra/PPF20_CE` — **effect-site concentration (Ce)** computed by the TCI pump's own three-compartment PK + effect-site model |

So the criticism lands on **E117 alone**. Every VitalDB experiment in this project is already on effect-site
concentration, because the infusion pump publishes it.

## Why it is a real concern in principle

EEG effect tracks **Ce**, not Cp, and the two are separated by a hysteresis with propofol
`t½ke0 ≈ 1.5–2.7 min` depending on model (Schnider `ke0` 0.456/min, Marsh 0.26/min). During **washout Ce
exceeds Cp**, so a recovery measurement looks lighter by plasma than the brain actually is. chennu's level
4 *is* a washout — median Cp 276 µg/L, sitting between baseline (0) and mild (438) — and it is **25 % of
the rows**. If E117's G6 inversion lived there, PK/PD modelling could plausibly have rescued it.

## It does not live there

| G6 variant | ρ(comp1, −depth) |
|---|---|
| all four levels, depth = Cp (as E117 ran it) | **−0.3646** |
| **ascending levels 1–3 only**, where TCI is at steady state and Cp ≈ Ce | **−0.3611** |
| ascending levels 1–3, ordered by level index instead of any concentration | **−0.3767** |

Essentially unchanged. And the level means show why:

| level | Cp µg/L | comp1 | comp2 | n_correct |
|---|---|---|---|---|
| 1 baseline | 0.0 | **−2.140** | −2.037 | 39.0 |
| 2 mild | 438.0 | +0.960 | +0.703 | 37.5 |
| 3 moderate | 803.0 | **+1.486** | +1.295 | 35.0 |
| 4 recovery (washout) | 276.5 | −0.305 | +0.040 | 38.0 |

**comp1 rises monotonically from baseline through moderate.** The inversion is in the ascending,
near-equilibrium arm — exactly where plasma and effect site are closest — not at the recovery point where
hysteresis acts. Better PK/PD modelling would move level 4 and change nothing about the failure.

**E117's conclusion stands: the sleep-derived arousal combination genuinely runs backwards under propofol.**

## What a proper model would need, and whether this deposit supports it

A Marsh or Schnider three-compartment PK plus an effect-site compartment requires the **infusion history**
(rates and times) and **demographics** (weight, age, height, sex). The extracted chennu tables carry four
label fields only — `sedation_level`, `plasma_propofol_ug_per_L`, `mean_reaction_time_ms`,
`n_correct_of_40` — so **Ce is not identifiable from what has been pulled**. Whether `datainfo.mat` holds
TCI targets, infusion timings or demographics has not been checked and is the one thing worth checking
before concluding it is impossible.

## One thing the diagnostic surfaced that is not about PK at all

`comp1` and `comp2` have nearly identical level profiles here (−2.140/+0.960/+1.486/−0.305 against
−2.037/+0.703/+1.295/+0.040), yet their pooled within-subject correlation is only **+0.0393** (E117's G5).
The two combinations agree on the average trajectory and disagree per subject, which means large
between-subject heterogeneity in how the levels are expressed. That was not the question asked and is
noted because it will matter to any successor deriving axes inside chennu.
