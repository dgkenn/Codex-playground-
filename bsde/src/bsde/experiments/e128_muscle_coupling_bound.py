"""E128 -- HOW MUCH within-stage submental-to-EEG coupling is there at all, and what does that bound?

REGISTERED BEFORE THE BOUNDING STATISTIC HAS BEEN COMPUTED. The extraction is E123's, already committed
and unchanged; what has been run on it is E123's own registered primary and its disclosed diagnostic, both
quoted below rather than recomputed silently.

=========================================================================================================
WHY THIS IS A DIFFERENT QUESTION, NOT E123 WITH A FRIENDLIER GATE
=========================================================================================================
E123 asked "is time-irreversibility muscle?" and returned NOT INTERPRETABLE, because its positive control
did not fire: `exponent_high` gave a within-block partial rho of -0.0286 [-0.1429, +0.0286] against
submental EMG with the sleep stage held fixed. The control was chosen because **E43 established on
VitalDB that a broadband 20-40 Hz slope is MORE muscle-associated than BIS** -- and that did not transfer
to Sleep-EDFx's Fpz-Cz and Pz-Oz derivations, which are a long way from the chin.

**Changing the control to make the same hypothesis testable would be goalpost-moving (rule 58).** So the
question changes instead, and it changes to the one the failure actually licenses.

E123's disclosed diagnostic established that the DESIGN is not the problem. Running the identical
statistic on `emg_median` and `emg_p90` -- both computed from the SAME submental channel as `emg_mean`,
so they must covary with it -- returns **+0.8857** and **+0.8286** against a permutation band of
[-0.0857, +0.0857]. The estimator has roughly ten times the resolution needed.

That combination is a MEASUREMENT, not a failure: within a fixed sleep stage, submental tone varies enough
to be read at rho 0.89, and no EEG measure tested follows it. **The quantity that statement supports is an
UPPER BOUND on within-stage submental-to-EEG coupling**, and a bound is what E107 and E111 actually need:

    E107 attributed 81 % of its REM placement to muscle by residualising on submental EMG.
    E111 showed the same adjustment removes 121.3 % in the 0.5-12 Hz band -- over-adjustment, because
         submental EMG is itself a state variable (rule 13's collider shape), and returned ABSENT.

Neither could say how much coupling there IS. If the within-stage bound is small, the across-stage
"removal" cannot have been contamination and must have been state co-variation -- which converts E111's
diagnosis from an inference into a measurement.

=========================================================================================================
DESIGN
=========================================================================================================
UNIT: E123's, unchanged -- one (subject, stage) block, six adjacent 120 s windows, stages W/N2/N3/REM,
partial Spearman of each measure against `emg_mean` with the window index removed from both.

    P1  THE BOUND. For each EEG measure m, the within-block partial rho against `emg_mean`, with a
        cluster-bootstrap interval over subjects. The reported quantity is the interval's WIDEST
        ENDPOINT IN ABSOLUTE VALUE -- i.e. the largest coupling the data does not exclude. Measures:
        `irr3`, `irr4`, `incr_asym`, `exponent_high`.

    P2  THE RATIO THAT MAKES THE BOUND MEAN SOMETHING. Bound(m) divided by the SAME statistic for
        `emg_median`, which is a second summary of the identical channel and therefore an estimate of the
        ceiling this design can register. A bound of 0.14 is uninformative on its own and highly
        informative at 16 % of a demonstrated 0.89.

GATES

    G1  COVERAGE: E123's, >= 60 blocks over >= 30 subjects. (E123 had 486 over 130.)
    G2  THE CEILING MUST BE DEMONSTRATED ON THESE BLOCKS, NOT ASSUMED. `emg_median` and `emg_p90` must
        each return a partial rho whose interval excludes zero and exceeds +0.5. This is the gate E123
        should have had: a positive control drawn from the SAME channel as the predictor cannot fail for
        reasons of montage or distance, so it measures the estimator rather than a physiological
        hypothesis. **It is not the hypothesis's own control** -- it cannot make a muscle association
        appear -- so using it does not move any goalpost.
    G3  NO N1 ROWS (the extractor excluded N1; their presence would mean the wrong file was read).

PLACEBO: the EMG window order is permuted within each block, 500 draws, as in E123. Here it establishes
the FLOOR -- the coupling this design registers from nothing -- and the bound is only meaningful if the
null band is narrow relative to the ceiling. Compared against the distribution, not the mean (rule 37).

VERDICT, and note this experiment has NO favourable direction, which is deliberate:

    (a) G2 fails -> ABSENT. The ceiling is not demonstrated and no bound can be stated.
    (b) bound for every irreversibility measure is a SMALL FRACTION of the ceiling -> WITHIN-STAGE
        COUPLING IS BOUNDED SMALL. E107's across-stage EMG association cannot then be contamination, and
        E111's over-adjustment diagnosis is confirmed by measurement.
    (c) bound is a LARGE fraction of the ceiling -> the data does not exclude substantial coupling, the
        bound is uninformative, and E107's muscle attribution remains open. **This is a real possible
        outcome and it is not a failure of the experiment** -- an uninformative bound honestly reported
        is the correct result when the data cannot do better.

There is no branch in which irreversibility is shown to BE muscle, because a within-stage null cannot show
that. This experiment can only bound, and saying so in advance is what stops the bound being read as a
refutation later (rule 31's habit).

SCOPE. Two bipolar EEG derivations far from the chin, a 1 Hz submental EMG ENVELOPE, and stages scored
FROM the EEG. A bound on submental coupling in Fpz-Cz/Pz-Oz says nothing about frontalis or temporalis
muscle in a frontal montage -- which is precisely why E43's VitalDB result did not transfer, and the same
caution applies in reverse to anything concluded here.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
TABLE = os.path.join(RESULTS, "sleep_edfx_within_stage.csv")
OUT = os.path.join(RESULTS, "e128_muscle_coupling_bound.json")

MEASURES = ("irr3", "irr4", "incr_asym", "exponent_high")
CEILING = ("emg_median", "emg_p90")
EMG = "emg_mean"
N_WINDOWS = 6
MIN_BLOCKS = 60
MIN_SUBJECTS = 30
CEILING_FLOOR = 0.5
PLACEBO_DRAWS = 500
SEED = 128


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load_blocks(table=TABLE):
    """E123's loader, extended to carry the ceiling columns. De-duplicates across shards (rule 56)."""
    import numpy as np
    root, ext = os.path.splitext(table)
    seen, rows = set(), []
    for p in [table] + sorted(glob.glob(f"{root}.s*{ext}")):
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p, newline="")):
            if r.get("status") != "ok":
                continue
            k = (r["subject"], r["label"], r.get("window_index"))
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    by = {}
    for r in rows:
        by.setdefault((r["subject"], r["label"]), []).append(r)
    out, labels = [], {r["label"] for r in rows}
    for (subj, lab), rr in sorted(by.items()):
        if len(rr) != N_WINDOWS:
            continue
        rr.sort(key=lambda r: int(r["window_index"]))
        d = {"subject": subj, "label": lab, "idx": [int(r["window_index"]) for r in rr],
             EMG: [_f(r[EMG]) for r in rr]}
        for c in MEASURES + CEILING:
            d[c] = [_f(r.get(c, "")) for r in rr]
        if np.isfinite(d[EMG]).all():
            out.append(d)
    return out, labels


def main(argv=None) -> int:
    import numpy as np
    from bsde.verifier.stats import cluster_bootstrap_ci
    import e123_within_stage_muscle as E123

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)

    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E128", "A",
            "How much within-stage submental-to-EEG coupling is there at all, and what does that bound?",
            "sleep-edfx",
            "widest absolute endpoint of the within-block partial rho against emg_mean, expressed as a "
            "fraction of the same statistic for emg_median (the demonstrated ceiling)",
            ["G1 coverage >=60 blocks over >=30 subjects",
             "G2 ceiling DEMONSTRATED on these blocks: emg_median and emg_p90 both above +0.5 with "
             "intervals excluding zero",
             "G3 no N1 rows"],
            "permute the EMG window order within each block, 500 draws -- establishes the FLOOR",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E123",
            instrument_changed="THE QUESTION, not the gate: E123 asked whether irreversibility IS muscle "
                               "and its control did not transfer from VitalDB; this asks how large the "
                               "coupling could be, using a control drawn from the same channel as the "
                               "predictor, which cannot make an association appear")
        print("registered E128")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    if a.register_only:
        return 0

    blocks, labels = load_blocks()
    subjects = sorted({b["subject"] for b in blocks})
    gates = {"G1_blocks": len(blocks), "G1_subjects": len(subjects),
             "G1_pass": len(blocks) >= MIN_BLOCKS and len(subjects) >= MIN_SUBJECTS,
             "G3_labels": sorted(labels), "G3_pass": "N1" not in labels}
    print(f"G1 {len(blocks)} blocks over {len(subjects)} subjects  "
          f"{'PASS' if gates['G1_pass'] else 'FAIL'}")
    if not (gates["G1_pass"] and gates["G3_pass"]):
        json.dump({"gates": gates, "verdict": "REFUSED: coverage or stage composition"},
                  open(a.out, "w"), indent=1)
        return 0

    def summarise(measure):
        v, s = E123.stat_over_blocks(blocks, measure)
        if v.size < MIN_BLOCKS:
            return None
        med = float(np.median(v))
        lo, hi, _ = cluster_bootstrap_ci(lambda i: float(np.median(v[i])), s,
                                         np.random.default_rng(SEED + 1), reps=2000)
        return {"n_blocks": int(v.size), "median": med, "lo": float(lo), "hi": float(hi),
                "bound": float(max(abs(lo), abs(hi)))}

    ceil = {c: summarise(c) for c in CEILING}
    gates["G2_ceiling"] = ceil
    gates["G2_pass"] = bool(all(
        c and np.isfinite(c["lo"]) and c["lo"] > CEILING_FLOOR for c in ceil.values()))
    for c, v in ceil.items():
        print(f"G2 ceiling {c:12s} {v['median']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}]")
    print(f"G2 {'PASS' if gates['G2_pass'] else 'FAIL'}")

    if not gates["G2_pass"]:
        json.dump({"gates": gates,
                   "verdict": "(a) ABSENT -- the ceiling is not demonstrated on these blocks, so no bound "
                              "can be stated and nothing follows about irreversibility."},
                  open(a.out, "w"), indent=1)
        print("\nVERDICT: (a) ABSENT -- ceiling not demonstrated")
        return 0

    ceiling_value = float(np.mean([c["bound"] for c in ceil.values()]))
    primary = {m: summarise(m) for m in MEASURES}
    for m, v in primary.items():
        if v:
            v["fraction_of_ceiling"] = v["bound"] / ceiling_value
            print(f"P1 {m:15s} {v['median']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}]  "
                  f"bound {v['bound']:.4f} = {100 * v['fraction_of_ceiling']:.1f}% of ceiling "
                  f"{ceiling_value:.4f}")

    rng = np.random.default_rng(SEED + 2)
    floor_draws = []
    for _ in range(a.placebo_draws):
        perm = [rng.permutation(N_WINDOWS) for _ in blocks]
        v, _s = E123.stat_over_blocks(blocks, MEASURES[0], perm=perm)
        if v.size:
            floor_draws.append(float(np.median(v)))
    fd = np.asarray(floor_draws, float)
    floor = {"n": int(fd.size),
             "p2.5": float(np.quantile(fd, .025)) if fd.size else float("nan"),
             "p97.5": float(np.quantile(fd, .975)) if fd.size else float("nan")}
    floor_width = max(abs(floor["p2.5"]), abs(floor["p97.5"])) if fd.size else float("nan")
    print(f"FLOOR permuted EMG order: [{floor['p2.5']:+.4f}, {floor['p97.5']:+.4f}] "
          f"-> null band {floor_width:.4f}, {100 * floor_width / ceiling_value:.1f}% of ceiling")

    irr = [primary[m] for m in ("irr3", "irr4", "incr_asym") if primary[m]]
    worst = max(v["fraction_of_ceiling"] for v in irr) if irr else float("nan")
    if worst < 0.25:
        verdict = (f"(b) WITHIN-STAGE COUPLING IS BOUNDED SMALL -- the largest coupling the data does not "
                   f"exclude, for any irreversibility estimator, is {100 * worst:.1f}% of the "
                   f"{ceiling_value:.4f} ceiling demonstrated on the SAME blocks with a second summary of "
                   "the SAME submental channel. With the sleep stage held fixed, submental tone varies "
                   "enough to be read at that ceiling and irreversibility does not follow it. "
                   "CONSEQUENCE: E107's across-stage EMG association cannot have been contamination in "
                   "these derivations, so it was state co-variation -- which converts E111's "
                   "over-adjustment diagnosis from an inference into a measurement. "
                   "This does NOT show irreversibility is muscle-free in a frontal montage; see scope.")
    else:
        verdict = (f"(c) THE BOUND IS UNINFORMATIVE -- the data does not exclude coupling up to "
                   f"{100 * worst:.1f}% of the demonstrated ceiling for at least one irreversibility "
                   "estimator, so E107's muscle attribution remains open. Reported as the correct result "
                   "when the data cannot do better, not as a failure.")

    res = {"gates": gates, "ceiling_value": ceiling_value, "P1_bounds": primary,
           "floor": floor, "floor_fraction_of_ceiling": floor_width / ceiling_value,
           "verdict": verdict}
    json.dump(res, open(a.out, "w"), indent=1)
    print("\nVERDICT:", verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
