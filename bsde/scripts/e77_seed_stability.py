"""Rule-46 follow-up to E77: is `bis_rbr`'s MUSCLE-ATTRIBUTED verdict a property of the RNG seed?

E77 as registered used 200 subject-bootstrap resamples. `bis_rbr` came back A = +0.102 [+0.027, +0.191]
with 2 of 200 resamples on the wrong side of zero, giving a two-sided resample-level p of 0.0200 against a
Benjamini-Hochberg threshold of 0.0250. **The margin between the p and its threshold is smaller than the
Monte Carlo granularity of a 200-resample bootstrap (0.005 per resample), so by rule 46 the binary is not
yet distinguishable from noise.**

Rule 46 also says what is and is not a legitimate response: raising the replicate count is legitimate
precisely because it changes no threshold, no cohort and no horizon. Nothing else here moves. The
attribution statistic, the covariate, the contrast, the subject set and the BH threshold are E77's.

This re-runs the bootstrap for the two tested features at three seeds and 600 resamples each, and prints
the per-seed verdict. A verdict that moves across seeds is SEED-UNSTABLE and must be reported that way
rather than as whichever seed was run first.

    python bsde/scripts/e77_seed_stability.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.experiments.e69_rem_dissociation import STAGES                            # noqa: E402
from bsde.experiments.e72_muscle_audit_corrected import transformed_emg             # noqa: E402
from bsde.experiments.e77_bis_rbr_muscle_control import (BOOT_A_PLACEBO, EMG,        # noqa: E402
                                                         SUBPARAMS, TESTED, _f,
                                                         boot_A, load_table, verdict)

OUT = os.path.join(HERE, "..", "results", "e77_seed_stability.json")
SEEDS = (20260731 + 5, 20260731 + 105, 20260731 + 205)
REPS = 600


def main() -> int:
    sub_tab = load_table(SUBPARAMS, TESTED)
    emg = {r["recording_id"]: _f(r["emg_mean"]) for r in csv.DictReader(open(EMG, newline=""))}
    subs = sorted(s for s, d in sub_tab.items()
                  if all(st in d for st in STAGES)
                  and all(f"{s}@{st}" in emg and np.isfinite(emg[f"{s}@{st}"]) for st in STAGES))
    M = transformed_emg(emg, subs)
    print(f"{len(subs)} subjects, {REPS} resamples, {BOOT_A_PLACEBO} placebo draws per resample")

    out = {"n_subjects": len(subs), "reps": REPS, "features": {}}
    for f in TESTED:
        E = {st: np.array([sub_tab[s][st][f] for s in subs]) for st in STAGES}
        per = {}
        for s in SEEDS:
            lo, hi, frac = boot_A(E, M, subs, s, reps=REPS)
            p = 2 * min(frac, 1 - frac)
            v = verdict((lo + hi) / 2.0, lo, hi)
            per[s] = {"lo": lo, "hi": hi, "frac_wrong_side": frac, "two_sided_p": p, "verdict": v}
            print(f"    {f:10s} seed {s}  [{lo:+.4f}, {hi:+.4f}]  p {p:.4f}  {v}")
        vs = {d["verdict"] for d in per.values()}
        stable = len(vs) == 1
        out["features"][f] = {"per_seed": per, "stable": stable,
                              "verdict": list(vs)[0] if stable else "SEED-UNSTABLE"}
        print(f"    {f:10s} -> {'STABLE ' + list(vs)[0] if stable else 'SEED-UNSTABLE ' + str(sorted(vs))}")

    json.dump(out, open(os.path.abspath(OUT), "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
