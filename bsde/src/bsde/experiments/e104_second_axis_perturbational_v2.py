"""E104 -- E103 re-run with the spectral estimate FIXED. Same question, same primary, same gates.

=========================================================================================================
WHAT CHANGED, AND WHY IT IS AN INSTRUMENT AND NOT A GOALPOST
=========================================================================================================
E103 returned ABSENT at G4: its positive control failed. `spont_exponent` separated awake from sedated at
d_z **-0.4765** -- the RIGHT direction, sedated higher -- against a Gaussian 95th of 0.5982 over 14
subjects, so it did not clear, and the design correctly refused to emit a verdict on the primary (rule 31).

**The cause was a bug in the extractor, and it is identifiable without reference to any outcome.** The v1
extractor concatenated ~46 pre-pulse segments of 0.4 s each and then ran Welch with a **1.0 s window**, so
every window straddled ~2.5 segment boundaries and each boundary injected a broadband step. A Welch window
longer than the segment it is cut from is wrong whatever the answer would have been. Rule 27 -- a mask
that compresses out bad samples glues time together -- and rule 66, which was written from this: it
applies to the frequency domain too, because a power spectrum is not an order-free summary of the samples
handed to it.

**The diagnostic that proved it is external to the primary.** On the SAME deposit and the SAME subjects,
the existing non-TMS extraction separates awake from sedated at d_z **-0.9909** over 20 subjects against a
Gaussian 95th of 0.4858 -- it clears comfortably. So the deposit supports the known effect and the v1
extraction did not measure it.

v2 transforms each inter-pulse interval on its OWN contiguous samples, keeping 0.5 s clear of each pulse,
and averages only the resulting POWER SPECTRA. No window ever spans a discontinuity. `n_spont_seg` records
how many intervals contributed, so the estimate cannot look denser than it is.

WHAT DID NOT CHANGE, and this is the point of writing E104 this way: **the analysis is not re-implemented.**
This file sets the input table and the output path on E103's module and calls E103's `main()`. The
primary, the residualisation, all five gates, both placebos, the burn-in exclusions and every threshold
are the same object in memory, so there is no possibility of a quantity drifting between the two runs
(rule 20: when two scripts compute the same quantity, diff them -- here they cannot differ, because there
is only one).

E103's ABSENT verdict stands as logged. This is a successor, not a correction of the record.

=========================================================================================================
WHAT E103 ESTABLISHED THAT STILL HOLDS -- carried forward because it was measured, not assumed
=========================================================================================================
    G2 PASSED: a perturbational response WAS measured, real-minus-sham evoked RMS +4.1139
       [+0.0910, +9.4649]. This was the gate the feasibility note demanded before any extraction.
    G3 PASSED on all three statistics: n_pulses +0.4762 [-0.1667, +1.2143], iti_median -0.0012
       [-0.0356, +0.0327], det_separation +103.98 [-411.42, +629.40]. The detector was not behaving
       differently in the two arms.
    Extraction drop-out was balanced: `too_few_pulses` in 1 of 17 awake and 1 of 38 sedated (rule 14).

None of those depend on the spectral estimate, so none of them are re-litigated by v2 -- but all of them
are recomputed by this run and will be re-read from its own output, not quoted from E103's.

PREDICTED, unchanged from E103 and stated before this run: a second axis is detected, at roughly 40 %.
The prediction is NOT revised upward on the strength of having found a bug -- the bug affected the
positive control, and a positive control passing says nothing about whether the primary will.
"""
from __future__ import annotations

import os

from bsde.experiments import e103_second_axis_perturbational as e103

RESULTS = e103.RESULTS


def main() -> int:
    e103.TABLE = os.path.join(RESULTS, "ds005620_perturbation_v2.csv")
    e103.OUT = os.path.join(RESULTS, "e104_second_axis_perturbational_v2.json")
    print("E104 = E103's analysis, unchanged, on the v2 extraction "
          "(inter-pulse PSDs averaged, never concatenated)")
    print(f"  table {os.path.basename(e103.TABLE)}   out {os.path.basename(e103.OUT)}\n")
    return e103.main()


if __name__ == "__main__":
    raise SystemExit(main())
