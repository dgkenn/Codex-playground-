# ds004541: our extraction uses 62 channels where the deposit declares 58 EEG

*Found 2026-08-02 by diffing two sources for the same quantity (catalogue rule 20). **This document was
rewritten after the first version overstated the problem** — see "What this is NOT" below. Every fact here
was verified by Opus against the EDF header and the deposit's own channels file, read directly.*

## What is actually in the file

| source | value |
|---|---|
| the EDF itself, sub-02 and sub-07 (identical) | **70 signals**: 62 at 1000 Hz, plus VEOG, HEOG, EKG, EMG, Trigger, `EDF Annotations`, M1, M2 |
| deposit's `channels.tsv` | **59 rows: 58 typed `EEG`, 1 typed `TRIG`** |
| our extraction | **62** channels on all 124 rows |

Our loader (`bsde/src/bsde/ingestion/ds004541.py:49`) selects by a **negative** regex:

```python
EEG_ONLY = r"^(?!VEOG|HEOG|EKG|EMG|Trigger|EDF |M1|M2)"
```

which yields 62 = **54** of the deposit's 58 declared EEG channels (M1 and M2, the mastoids, are dropped)
**plus 6 electrodes the deposit does not list in `channels.tsv` at all**: `F11`, `F12`, `FT11`, `FT12`
(inferior temporal) and `Cb1`, `Cb2` (cerebellar).

## What this is NOT — a correction to the first version of this note

The first version of this document, and the summary I gave with it, said three channels "the deposit does
not label EEG" had entered the panel and called it *"the same failure mode that withdrew E204."*
**That was wrong and it overstated the problem.** E204's defect was an `EDF Annotations` channel entering
the panel and truncating every window through its different sampling rate. Here the loader **explicitly
excludes** `EDF Annotations`, the trigger, and all of EOG, ECG and EMG. Nothing non-neural is in the panel
and no sampling-rate truncation is possible — all 62 are at 1000 Hz.

## What the real issue is, and how much it matters

Two mismatches with the deposit's own declaration, both mild:

1. **Six extra scalp/cerebellar electrodes** are included that the deposit does not declare. `Cb1`/`Cb2`
   are the ones worth caring about — cerebellar sites are close to neck musculature and are a known route
   for EMG contamination into a whole-head average.
2. **The two mastoids are dropped**, which is a defensible choice and not a defect.

So `whole_head_exponent` on ds004541 is an average over a slightly different electrode set than the deposit
declares, weighted marginally toward inferior and cerebellar sites. That is a real inconsistency and it is
**not** grounds for withdrawing anything.

## The general lesson, which is the part worth keeping

**The selection is an exclusion list, and catalogue rule 70 is exactly about that**: a rule that names what
a channel may not be only excludes what someone thought of, so any electrode nobody anticipated is admitted
by default. The deposit ships a `channels.tsv` with a `type` column — an explicit statement of what each
channel *is*. **Selecting on `type == "EEG"` enumerates what is allowed and removes the judgement
entirely.** That is the fix, it generalises to every BIDS deposit this project touches, and it should be
applied to the shared loader rather than to this one file (rule 74).

## Reach

`E217` used ds004541 as one of four deposits; its per-feature effects there are computed on this electrode
set. `E217`'s verdict was NOT INTERPRETABLE for an unrelated reason. The ds004541 feasibility probe that
refused the deposit for Challenge C used `spectral_edge_95` from the same table; the refusal is not near
the boundary (−0.0170 against a floor of 0.1561) and six electrodes will not move it. **No result is
withdrawn on this.** Nothing in the VitalDB, HEEDB, capslpdb or ds005620 lines is affected — separate
loaders, separate channel handling.
