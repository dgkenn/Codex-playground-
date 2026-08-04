# sleep_edfx as a Challenge C cohort: incumbent overwhelmingly alive, artefact gradient severe

*Rule-41 feasibility probe, 2026-08-02, run before any registration. **No candidate column was correlated
with the label.** Every number below was recomputed by Opus against the raw table; a delegated agent
produced them first and agreed.*

## Why it is available at all

Challenge C has now lost three candidate cohorts — chennu (dead incumbent, twice, on two estimands),
ds004541 (dead incumbent, refused before anything was spent) — and found capslpdb's candidates redundant
rather than absent. `sleep_edfx` has never been used for Challenge C. It has been this programme's
**Challenge D evaluation ladder** (E198, E211), which is a different question and a different estimand, and
its candidate columns have never been correlated with a Challenge C label.

## What the probe found

| quantity | value |
|---|---|
| rows | 709, zero shard-header artefacts |
| subjects | 142, **all 142 carrying all four ordered stages** |
| ordered-ladder points (REM excluded, not ordered on this ladder) | 567 |
| **incumbent** Spearman(`spectral_edge_95`, ordered stage) | **−0.8461** |
| within-subject permutation null, 95th percentile of \|rho\| | **0.0890** |
| incumbent alive? | **YES, by a factor of 9.5** |
| median within-subject Spearman | −1.000, with 139 of 142 subjects matching the pooled sign |

That is the strongest incumbent this programme has measured on any deposit — stronger than capslpdb's
−0.6644 and far beyond chennu's +0.0349 and ds004541's −0.0170, both of which were refusals.

Four of the five DOSE-I survivors are present: `multiscale_entropy_slope`, `whole_head_exponent`,
`relative_alpha_power`, `pac_slow_alpha`. **`wpli_theta` is absent**, as it was on every other deposit.
Notably `multiscale_entropy_slope` IS here, which capslpdb's fast extraction had to omit for cost — so this
deposit can test the one survivor capslpdb could not.

`uce_v1` is **0 % finite** — an entirely empty column, which the shared screen would drop and which is
recorded here so nobody reads a p-value off it (rules 6, 74).

## The blocker, and it is serious

    **Spearman(`emg_index`, ordered stage) = −0.6542**

Muscle tone tracks the sleep ladder almost as strongly as the incumbent does, and in the same direction.
That is rule 41's artefact check firing hard, and it is not surprising physiologically — muscle tone falls
with sleep depth, which is why submental EMG is part of standard sleep scoring. But it means **any candidate
with muscle sensitivity will appear to track the ladder for reasons that have nothing to do with cortical
state**, and this deposit is 2 channels at 100 Hz, so there is no spatial handle to separate them.

This is the same hazard rule 57 records: an amplitude in arbitrary units is not a magnitude, and
`emg_index` was already shown by E69 to fail at detecting REM atonia, so it is a weak proxy and cannot
simply be regressed out.

## Verdict on feasibility

**The deposit is usable and it is not clean.** The incumbent is alive by a wide margin, the coverage is
complete, and it carries the one survivor capslpdb could not test. But a registration here **must** carry an
EMG gate that is more than a caveat (rule 54 — a confound named in the registration is not thereby
controlled): either a candidate-by-candidate muscle-attribution arm, or restriction to the stage pairs where
the EMG gradient is flat, with the choice stated in advance and a line of code behind it.

**One further caution.** REM is present with 142 subjects and is deliberately excluded from the ladder
because it is not ordered against N1-N3 on this measure. It is, however, the natural placebo for a muscle
confound — REM has the lowest muscle tone of any stage and sits in the middle of the depth ordering — and a
successor should use it as one rather than discarding it.
