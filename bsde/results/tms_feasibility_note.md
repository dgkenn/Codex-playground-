# Feasibility probe: is a perturbational (TMS-EEG) line possible on ds005620?

**Rule 41 probe, not a registered experiment.** No state contrast was computed and no candidate was
scored. This decides only whether the perturbational line can be attempted at all, and on what terms.

## Why it was asked

Challenge A's experiments to date have been validation-shaped — "is measure X confounded?" — whose best
outcome is a licence, never a discovery. The session's own results converge on a single statement:
**everything measured so far is one axis.** `uce_v1` is the whole-head exponent restated; E92 found no
decoupling between two regions; E73/E86's network measures reduce to mean connectivity; E93/E95/E100 all
order on arousal. The discovery question is whether a *second* axis exists and whether it tracks
experience rather than arousal. Perturbational complexity (Casali et al. 2013, PMID 23946194) is the
best-established candidate for such an axis, and ds005620 carries an entirely unused TMS arm: 385
`acq-tms` keys, both `task-awake` and `task-sed` **within subject**, 17 subjects, 5,000 Hz, 62–64
channels, ~600 s recordings.

## What was checked, and what four diagnostics cost

Subject `sub-1016`, one awake and one sedated recording, pulses read from `events.tsv` (`R128`).

| # | check | result | reading |
|---|---|---|---|
| 1 | evoked amplitude vs pre-pulse baseline | every post-pulse window **below** baseline (0.07–0.32×) | suspicious, not a negative — a real pulse dominates by orders of magnitude |
| 2 | per-epoch baseline correction; across-epoch variance | artefact present at **121,210×** baseline, but peaking at **−69.6 ms** (awake) and **+88.8 ms** (sed) | artefact is real; the first probe's baseline was inflated by between-channel DC |
| 2 | identical consecutive samples, ±10 ms vs −300..−50 ms | 0.1935 vs 0.1950 | **data is not artefact-removed** |
| 3 | `.vmrk` vs `events.tsv` | agree to **0.2 ms** | markers self-consistent — and this is not validation (rule 65) |
| 3 | detector stability | **n = 15** identically at 0.30, 0.10 and 0.03 × max | the detector finds the pulses and nothing else |
| 4 | read integrity | `MULTIPLEXED`, exact byte count, shape 64×150000 | the read is correct |
| 4 | marker vs detected intervals | vmrk 1.983/1.736/2.109/1.725 s; detected 2.299/1.803/1.720/2.037 s | **two independent ~2 s trains** |
| 5 | max\|diff\| at markers vs at 200 random points | markers at **percentile 49.5** (awake) / **53.5** (sed); **0/15** and **0/14** above the 95th | the markers do not index the artefact |
| 5 | max\|diff\| at detected events | 18,805 / 23,049 µV/sample vs 10.5 / 13.0 at markers | the pulses are ~1,800× separated from background |

## Verdict

**FEASIBLE, but only with data-driven pulse detection.** The shipped event timing is unusable for this
recording; the pulses themselves are among the easiest events to detect in any EEG deposit, sitting three
orders of magnitude above the background with a stable inter-pulse interval of ~1.9–2.0 s.

## What this does NOT establish, and must travel with any use of it

1. **Two recordings in one subject.** Whether the marker fault is deposit-wide, per-run, or confined to
   `sub-1016` is unknown. Any registered experiment must gate on the marker–signal agreement measured
   **per recording**, and use detection rather than markers regardless.
2. **Detection is not free of selection.** A slew-based detector will fail differently in a sedated
   recording (larger slow waves, different background) than in an awake one. Any state contrast built on
   it must show the detected pulse *count* and *interval distribution* match between arms, or the contrast
   is between two detection rates wearing the name of a brain difference. This is rule 32's shape: the
   availability of a measurement defines a stratum.
3. **The artefact is severe and includes cranial muscle in the first ~30 ms.** A perturbational measure
   still needs a mandatory gate showing the evoked response survives past the artefact window — nothing
   here tests that, because nothing here was correctly epoched yet.
4. **No response has been demonstrated.** Every amplitude reported above is from epochs aligned to the
   *wrong* times. The awake-vs-sedated question is untouched.
