"""E122 stage 2 -- the registered placebo for P1, which GATES the verdict (rule 34).

P1 came back with the deposit's own EEG index adding to every rung of the pharmacology ladder:

    L0 -0.2738 [-0.4119, -0.1191]   L1 -0.3063 [-0.4043, -0.1843]   L2 -0.1236 [-0.1871, -0.0586]
    L3 -0.1178 [-0.1810, -0.0463]   L4 -0.0952 [-0.1437, -0.0407]

(negative helps). E122's registration names one alternative explanation and one destruction for it:

    "a pharmacology model that misfits the shape of the trajectory leaves a residual with a time trend,
     and any EEG measure that also drifts with time would predict it without carrying any state
     information (rule 64)."

    "Each EEG series is CIRCULARLY TIME-SHIFTED within its own recording by a random offset of at least
     120 s. That preserves the marginal distribution, the autocorrelation, and any within-recording time
     trend, and destroys only the instantaneous correspondence with MOAA/S."

Rule 55: confirm the primary statistic is a function of what the placebo alters. It is -- the increment is
computed from row-wise correspondence between the EEG column and MOAA/S, and a circular shift changes
exactly that while leaving every marginal property intact.

Rule 37 (fifth occurrence): the comparison is against the placebo's DISTRIBUTION, never its mean.
Rule 48: the primary's interval is read FIRST; all five rungs exclude zero, so the placebo is informative
rather than being asked to validate a null.

ONE DEPARTURE FROM THE REGISTRATION, STATED RATHER THAN QUIET. The registration says 200 draws; each draw
costs a full out-of-bag bootstrap at every rung, so 200 x 5 x 400 replicates is about a hundred times the
cost of P1 itself and will not run. This uses `--draws` draws at `--reps` replicates, with the real
increment RE-COMPUTED at the same `--reps` so the comparison is like-for-like. Fewer replicates per draw
widens the placebo distribution, which makes the gate HARDER to pass, not easier -- the safe direction,
and the only one that needs no permission (rule 37's fifth entry made the same point about tightening
after a pass).

    python bsde/src/bsde/experiments/e122_placebo.py --draws 100 --reps 60
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e122_placebo.json")
MIN_SHIFT_S = 120.0
SEED = 1220


def main(argv=None) -> int:
    import numpy as np
    from bsde.verifier.stats import oob_regression_increment, spearman
    import e122_pharmacology_residual as E

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--draws", type=int, default=100)
    ap.add_argument("--reps", type=int, default=60)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    by, cands, off, cov, dose = E.load()
    kept, _dropped = E.build(by, cands, off, cov, dose)
    recs = sorted(kept)
    rng = np.random.default_rng(SEED)

    def err(t, p):
        r = spearman(t, p)
        return 1.0 - r if np.isfinite(r) else float("nan")

    base = {L: E.stack(kept, recs, lambda d, L=L: d["pk"][L]) for L in E.RUNGS}
    inc_cols = np.vstack([kept[r]["inc"] for r in recs])

    def shifted_inc(rng):
        """Circularly rotate the incumbent columns within each recording by >= MIN_SHIFT_S."""
        out = []
        for rec in recs:
            d = kept[rec]
            n = d["y"].size
            span = float(d["t"][-1] - d["t"][0]) if n > 1 else 0.0
            step = span / max(1, n - 1) if span > 0 else 1.0
            lo = max(1, min(int(np.ceil(MIN_SHIFT_S / max(step, 1e-9))), max(1, n - 1)))
            k = int(rng.integers(lo, n)) if n > lo else lo
            out.append(np.roll(d["inc"], k, axis=0))
        return np.vstack(out)

    res = {"draws": a.draws, "reps": a.reps, "n_recordings": len(recs), "rungs": {}}
    for L in E.RUNGS:
        Xa, y, s = base[L]
        real_m, real_lo, real_hi, _ = oob_regression_increment(
            Xa, np.hstack([Xa, inc_cols]), y, s, np.random.default_rng(SEED + L),
            stat=err, reps=a.reps)
        draws = []
        for j in range(a.draws):
            Xb = np.hstack([Xa, shifted_inc(np.random.default_rng(SEED + 1000 * (L + 1) + j))])
            m, _lo, _hi, _n = oob_regression_increment(
                Xa, Xb, y, s, np.random.default_rng(SEED + L), stat=err, reps=a.reps)
            if np.isfinite(m):
                draws.append(float(m))
        d = np.asarray(draws, float)
        # The increment is negative when the addition HELPS, so "at least as extreme" means at least as
        # NEGATIVE. A two-sided test would be the wrong question here: the claim is directional and the
        # verdict branch that matters is whether a fake alignment reproduces a HELPFUL increment.
        frac = float(np.mean(d <= real_m)) if d.size else float("nan")
        res["rungs"][f"L{L}"] = {
            "real_mean": real_m, "real_lo": real_lo, "real_hi": real_hi,
            "placebo_n": int(d.size),
            "placebo_mean": float(d.mean()) if d.size else float("nan"),
            "placebo_p2.5": float(np.quantile(d, 0.025)) if d.size else float("nan"),
            "placebo_p97.5": float(np.quantile(d, 0.975)) if d.size else float("nan"),
            "frac_placebo_at_least_as_helpful": frac,
            "beats_placebo": bool(np.isfinite(frac) and frac <= 0.05)}
        print(f"L{L}: real {real_m:+.4f} [{real_lo:+.4f}, {real_hi:+.4f}]   "
              f"placebo mean {res['rungs'][f'L{L}']['placebo_mean']:+.4f} "
              f"[{res['rungs'][f'L{L}']['placebo_p2.5']:+.4f}, "
              f"{res['rungs'][f'L{L}']['placebo_p97.5']:+.4f}]   "
              f"frac<=real {frac:.3f}  {'BEATS' if res['rungs'][f'L{L}']['beats_placebo'] else 'FAILS'}",
              flush=True)

    all_beat = all(v["beats_placebo"] for v in res["rungs"].values())
    all_neg = all(v["real_hi"] < 0 for v in res["rungs"].values())
    if not all_neg:
        res["verdict"] = ("NOT INFORMATIVE (rule 48) -- at least one rung's re-computed primary no longer "
                          "excludes zero at this replicate count, so there is no real effect for a fake "
                          "alignment to fail to reproduce.")
    elif all_beat:
        res["verdict"] = ("ADDS -- the deposit's own EEG index carries sedation depth that a complete "
                          "propofol exposure model cannot predict, at EVERY rung of the ladder, and a "
                          "circular within-recording time shift does not reproduce it. The alternative "
                          "the placebo was built to kill -- that a misfitted trajectory leaves a time "
                          "trend any drifting measure would track -- is refuted.")
    else:
        failing = [k for k, v in res["rungs"].items() if not v["beats_placebo"]]
        res["verdict"] = (f"WITHDRAWN AT {', '.join(failing)} -- a circular time shift reproduces the "
                          "increment there, so at those rungs the association is with position in time "
                          "rather than with sedation state. The conjunction across all five rungs was "
                          "registered, so one failure refuses the whole claim.")
    json.dump(res, open(a.out, "w"), indent=1)
    print("\nVERDICT:", res["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
