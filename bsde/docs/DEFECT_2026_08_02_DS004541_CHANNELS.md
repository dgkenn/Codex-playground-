# ds004541: our extraction used 62 channels where the deposit declares 58 EEG

*Found 2026-08-02 by diffing two sources for the same quantity (catalogue rule 20). Verified by Opus
against the BIDS sidecar and the channels file directly, not via a summary.*

## The discrepancy

| source | value |
|---|---|
| our extraction, `bsde/results/ds004541_v2.csv` | `n_channels = 62` on **all 124** `status=ok` rows |
| deposit's `sub-02_ses-01_task-anesthesia_eeg.json` | `EEGChannelCount: 58`, `TriggerChannelCount: 1` |
| deposit's `sub-02_ses-01_task-anesthesia_channels.tsv` | **59 rows: 58 of type `EEG`, 1 of type `TRIG`** |

So the extractor took **62** signals from a file the deposit describes as carrying **58 EEG channels plus
one trigger**. At least three channels entered the panel that the deposit does not label as EEG, and the
trigger channel is a candidate for one of them.

## Why this matters and how far it reaches

This is the failure that withdrew **E204**: an `EDF Annotations` channel passed the good-channel test
(its standard deviation was 0.08, not zero) and its different sampling rate silently truncated every
window. The fix there was to select channels by **exact case-insensitive membership of the 10-20 set**
rather than by a variance heuristic — catalogue rule 61 — and the same fix has not been applied to this
deposit's loader.

**Reach.** Every ds004541 number this programme has produced was computed on the 62-channel panel:

* **E217** used ds004541 as one of four deposits. Its per-feature deep-minus-light effects for that
  deposit are affected. E217's verdict was NOT INTERPRETABLE for an unrelated reason (chennu's aliveness
  gate), and the arm it reported without chennu still includes ds004541, so those numbers inherit this.
* The **ds004541 feasibility probe** that refused the deposit as a Challenge C cohort used
  `spectral_edge_95` from the same table. The refusal is unlikely to reverse — the incumbent's correlation
  with the deposit's own depth label was −0.0170 against a permutation floor of 0.1561, nowhere near the
  boundary — but the number itself is computed on the wrong channel set and should be recomputed if the
  deposit is ever reconsidered.

## What is NOT affected

Nothing in Challenge A's VitalDB line, Challenge B's HEEDB line, Challenge D's capslpdb line, or E209's
ds005620 replication. Those deposits have their own loaders and their own channel counts, and the E204 fix
was applied to the HEEDB one.

## The fix, not yet applied

Re-extract ds004541 selecting channels by `channels.tsv` type == `EEG`, which the deposit ships and which
removes all judgement from the selection. Until then, treat every ds004541 figure as provisional and do not
use the deposit in a new registration.
