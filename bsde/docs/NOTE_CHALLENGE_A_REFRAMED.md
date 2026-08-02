# Challenge A reframed: it was never an alpha story, and it may not be a biology story

*2026-08-02. Supersedes the framing in `NOTE_ALPHA_INSTABILITY.md`, which is left intact as the record of
how the question was arrived at. All numbers recomputed by Opus against the raw source.*

## The scan that should have been run first

Every Challenge A experiment in this programme has asked about `relative_alpha_power`, because that is
where the effect was first noticed. **Nobody asked whether the effect is specific to it.** It is not.

Within-case median Spearman between each feature and that case's own drug concentration, by arm — a
statistic that never crosses a patient boundary, uses no depth anchor, and involves no BIS:

| feature | propofol | sevoflurane | difference |
|---|---|---|---|
| `exponent_low` | +0.0222 | **+0.5061** | +0.4838 |
| `multiscale_entropy_slope` | +0.1321 | **+0.5515** | +0.4194 |
| `alpha_peak_hz` | +0.0703 | **−0.3475** | −0.4178 |
| `spectral_edge_95` | −0.0628 | **−0.4496** | −0.3868 |
| **`relative_alpha_power`** | **+0.0960** | **−0.2778** | **−0.3737** |
| `critical_slowing_ar1` | +0.1504 | **+0.5147** | +0.3643 |
| `emg_beta_gamma_fraction` | −0.0709 | −0.4185 | −0.3476 |
| `relative_delta_power` | +0.0978 | +0.3577 | +0.2599 |
| `spectral_entropy` | −0.0845 | −0.3370 | −0.2524 |
| `whole_head_exponent` | +0.0836 | +0.3353 | +0.2517 |
| `relative_theta_power` | +0.1034 | +0.2999 | +0.1965 |
| … 6 more, all \|difference\| < 0.11 | | | |

**`relative_alpha_power` ranks 5 of 17** on the size of the asymmetry — the 76.5th percentile. Four features
show a larger one, and eleven show a substantial one.

## What the table actually says

Read the **propofol column**: every one of seventeen features sits between −0.26 and +0.15. Read the
**sevoflurane column**: values reach ±0.55. The finding is not that alpha behaves differently between
agents. It is:

> **Within a case, EEG features track sevoflurane concentration and do not track propofol concentration —
> across essentially the whole panel.**

That is one fact about the exposure variable, not seventeen facts about seventeen measures, and it is far
more parsimonious than any of the six mechanisms tested and refuted so far.

## The most likely explanation is provenance, not biology

The two exposures are not the same kind of quantity, and the repo's own extraction documents say so:

| arm | variable | what it is |
|---|---|---|
| propofol | `Orchestra/PPF20_CE` | **the infusion pump's own MODELLED effect-site concentration** — a deterministic function of the infusion history through a PK model |
| sevoflurane | `Primus/EXP_SEVO` | **a MEASURED end-tidal gas concentration** |

A modelled concentration cannot carry information the model does not have. It is smooth by construction and
contains no physiology beyond what the infusion record implies. A measured gas concentration carries real
breath-to-breath variation, and that variation is coupled to the patient's actual state.

**Two independent observations already in hand fit this and nothing else needs to be invoked.** The two
exposures have *identical* within-case variability — coefficient of variation 0.341 against 0.355, interval
spanning zero — so this is not about how much the dose moved. And each exposure's ability to track its own
depth index differs in the same direction: within-case rho against BIS is **−0.3359 for propofol Ce** and
**−0.4973 for sevoflurane end-tidal**. The propofol exposure is simply the weaker instrument.

## What this does to the earlier work

* **The "alpha instability" framing is superseded.** Alpha is one of eleven features showing the same thing
  and it is not the largest. Every experiment that treated alpha as the object of study — E213, E214, E216,
  E218 — was investigating a general property through one arbitrary window on it. Their verdicts stand;
  their framing does not.
* **The six refuted mechanisms are refuted for a better reason than they were.** Band placement, burst
  suppression, age, dose range, co-medication and non-equipotence were all tested as explanations of an
  *alpha* effect. None of them could ever have explained an effect that appears in seventeen measures at
  once, including muscle and complexity measures with no band structure at all.
* **E220's identifiability result is unaffected and remains the strongest methodological finding.** The
  agent main effect is not identifiable when each patient receives one agent, whatever the feature.

## The falsifiable prediction, and it is cheap

If provenance is the cause, then **a propofol exposure that is MEASURED rather than modelled should track
the EEG as well as sevoflurane's does.** VitalDB does not carry measured plasma propofol. Two routes exist:

1. **A deposit with measured propofol concentrations.** Chennu's cohort carries `meta_plasma_propofol` —
   an assayed concentration, not a pump model — and this programme has already used it. On that deposit the
   prediction is that within-case tracking is comparable to sevoflurane's here.
2. **Degrade the sevoflurane exposure to match.** Replace measured end-tidal with a *modelled* volatile
   concentration derived from the same record and re-run. If the asymmetry shrinks, provenance is doing the
   work.

Route 2 is the stronger test because it changes only the instrument, and it needs no new data.
