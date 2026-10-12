"""E123 -- Does time-irreversibility move with submental muscle tone WHEN THE SLEEP STAGE IS HELD FIXED?

REGISTERED BEFORE `sleep_edfx_within_stage.csv` EXISTS. The extractor was committed in the previous commit
and launched; no window of it has been read against this question.

=========================================================================================================
WHY
=========================================================================================================
E107 is this project's strongest single-axis result and its most fragile attribution. A measure that is
PROVABLY orthogonal to the entire power spectrum -- time reversal leaves the autocovariance, and therefore
every spectral summary, exactly unchanged -- places REM at position **+0.9974** on the wake-to-N3 axis
against the aperiodic exponent's +0.4788, with P1 = +1.4539 [+1.0166, +2.2259] over 90 subjects. Its G5
then reported that residualising on submental EMG removes **81 %** of that, and concluded the measure was
reading muscle WAVEFORM SHAPE, since the permutation form cannot read amplitude.

**E111 refuted the method, not the finding.** The same adjustment removes **121.3 %** of the effect in the
0.5-12 Hz band -- more than all of it, which is over-adjustment, not contamination. Submental EMG amplitude
is a state variable: it falls monotonically from wake to N3 and sits at its floor in REM (E100 measured
REM's EMG position at +1.094). Regressing a state-tracking measure on another state-tracking measure
removes state, which is rule 13. E111 therefore returned ABSENT and wrote down what a successor needs:

    "a muscle control that is not a within-subject regression on a state-tracking variable ... or a
     within-STAGE contrast where EMG varies but state does not."

**Inside one contiguous block of one scored stage, there is no state variance to remove.** Whatever
covariation remains between irreversibility and submental tone is muscle, and whatever does not is not.
This is the same question E107 and E111 asked with an instrument that cannot commit their error
(rule 58's successor requirement: change the instrument, never the threshold).

=========================================================================================================
DESIGN
=========================================================================================================
UNIT. One (subject, stage) block, six adjacent 120 s windows tiled outward from the block centre. Stages
W, N2, N3 and REM; N1 excluded before any data was seen because only 16 subjects hold a 720 s N1 block
against 128/137/94/133 for the others.

THE STATISTIC IS PARTIALLED ON WINDOW ORDER, and that is not optional. The six windows are consecutive in
time, and both muscle tone and any electrode-drift-driven measure trend within a block. A raw within-block
correlation would confound "moves with muscle" with "both drift", which is rule 64's shape one level down.
So both series are residualised on the window index (0..5) inside the block, and the statistic is the
Spearman correlation of the residuals.

    P1  Median over blocks of within-block partial Spearman(`irr3`, `emg_mean` | window index).
        Cluster-bootstrap CI over SUBJECTS, since a subject contributes up to four blocks.

    P2  The same for `irr4` and for `incr_asym`. E111 found the two irreversibility estimators DISAGREED
        in the low band (`incr_asym` null at +0.0534 [-0.1283, +0.2666] while the permutation forms were
        positive), and said that disagreement was worth a successor's attention. This is it.

GATES, before the primary is read.

    G1  COVERAGE. >= 60 blocks with all six windows `ok` and finite `irr3` and `emg_mean`, over >= 30
        subjects.

    G2  THE POSITIVE CONTROL MUST FIRE, AND IT DOUBLES AS THE DYNAMIC-RANGE GATE. `exponent_high` (the
        20-40 Hz log-log slope) must show a within-block partial correlation with `emg_mean` whose
        interval excludes zero. E43 established that a broadband slope through this band is MORE
        muscle-associated than BIS, so it is the measure that must move if within-block EMG varies enough
        to be detectable at all.

        **This is deliberately how the dynamic-range question is asked, rather than by a threshold on the
        within-block EMG range.** Rule 63: a gate picked as a round number measures the round number. A
        demonstrated positive control measures what the machinery can actually achieve on these blocks.

        The interval is required to EXCLUDE ZERO -- two-sided (rule 37, third occurrence: a placebo or a
        control can fire in either direction and one name must not do two jobs). The DIRECTION is a
        separate and narrower question, recorded here as a prediction rather than as a gate: muscle adds
        broadband high-frequency power, which flattens the 20-40 Hz spectrum, so `exponent_high` should
        DECREASE as `emg_mean` rises -- a NEGATIVE partial correlation. A positive one would mean the
        control does not behave as the muscle account requires and the design's premise is wrong; that is
        reported, not absorbed.

    G3  N1 ABSENT. The table must contain no N1 rows. A stage excluded in the extractor and then present
        in the analysis would mean the wrong file was loaded.

PLACEBO, and it gates the verdict (rule 34). The window ORDER of `emg_mean` is permuted inside each block,
the identical statistic is recomputed, and this is repeated 500 times. The comparison is against the
placebo's DISTRIBUTION, never its mean (rule 37, fifth occurrence: a mean placebo is a point with no width
and every real value differs from it). It is the right destruction for this estimand because it removes
exactly the window-to-window correspondence between muscle and measure while preserving both marginal
distributions, both within-block trends after partialling, the block sizes and the subject clustering
(rule 55: confirm the primary statistic is a function of what the placebo alters -- a within-block rank
correlation manifestly is).

Rule 48: if P1's interval INCLUDES zero, the placebo is NOT INFORMATIVE and must say so rather than print
a pass. The primary is evaluated first.

VERDICT, wrong direction FIRST and by name (rule 37, fourth occurrence -- "excludes the null" and
"supports the hypothesis" are different questions, and a confidence interval only answers the first):

    (a) G2 fails                      -> NOT INTERPRETABLE. Either within-block EMG does not vary enough to
                                         be read, or the control does not behave as muscle. Nothing can be
                                         concluded about irreversibility either way, and in particular a
                                         null P1 must NOT be reported as "irreversibility is not muscle".
    (b) P1 excludes zero POSITIVE      -> IRREVERSIBILITY IS MUSCLE-ASSOCIATED, and E107's G5 attribution
                                         survives on an instrument that cannot over-adjust. This is the
                                         direction that WEAKENS E107's headline claim, and it is enumerated
                                         first among the informative branches on purpose.
    (c) P1 excludes zero NEGATIVE      -> ASSOCIATED IN THE WRONG DIRECTION. More muscle, LESS
                                         irreversibility. This does not support the muscle account -- it
                                         refutes it while still excluding the null -- and it must not be
                                         filed as (b). E43's fourth occurrence exists because exactly this
                                         case went unenumerated.
    (d) P1 includes zero, G2 passed    -> NOT MUSCLE. With the stage held fixed and the control
                                         demonstrated live on the same blocks, irreversibility does not
                                         track submental tone. E107's REM placement then needs a
                                         non-muscle explanation.

CALIBRATION, recorded before the run: (b) ~45 %, (d) ~35 %, (a) ~15 %, (c) ~5 %.

SCOPE. Sleep-EDFx cassette recordings, two bipolar EEG derivations (Fpz-Cz, Pz-Oz) and a 1 Hz submental
EMG ENVELOPE -- so "muscle" here means submental tone, not any other muscle group, and the EMG channel
supports an amplitude summary and nothing spectral. Stage labels are scored FROM the EEG, so holding stage
fixed also holds fixed whatever the scorer used; that is a feature for this design (it is what makes the
state constant) and a limit on any claim beyond it. A null here says irreversibility does not track
submental tone WITHIN a stage; it does not say the between-stage association E107 measured is unreal.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
TABLE = os.path.join(RESULTS, "sleep_edfx_within_stage.csv")
OUT = os.path.join(RESULTS, "e123_within_stage_muscle.json")

MEASURES = ("irr3", "irr4", "incr_asym")
CONTROL = "exponent_high"
EMG = "emg_mean"
N_WINDOWS = 6
MIN_BLOCKS = 60
MIN_SUBJECTS = 30
PLACEBO_DRAWS = 500
SEED = 123


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def partial_spearman_on_index(a, b, idx):
    """Spearman between `a` and `b` after removing a linear trend in `idx` from each.

    Six points, so a linear detrend costs two degrees of freedom and leaves four. That is deliberate: the
    alternative -- ranking against the index and partialling in rank space -- would leave the statistic
    defined on three effective points, and the point of the partialling is to remove drift, which is a
    trend in the VALUES rather than in their ranks."""
    import numpy as np
    from bsde.verifier.stats import spearman
    a, b, idx = np.asarray(a, float), np.asarray(b, float), np.asarray(idx, float)
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        return float("nan")
    if np.unique(a).size < 3 or np.unique(b).size < 3:
        return float("nan")
    X = np.column_stack([np.ones_like(idx), idx])
    ra = a - X @ np.linalg.lstsq(X, a, rcond=None)[0]
    rb = b - X @ np.linalg.lstsq(X, b, rcond=None)[0]
    return spearman(ra, rb)


def blocks_from(table):
    """Read the unsharded table and every shard of it as one set, keyed on (subject, stage).

    The extraction runs in six shards writing to `...s<k>.csv`, and an earlier unsharded partial run wrote
    to the base path. Rule 56: de-duplicate on the key rather than assuming one writer -- a subject-stage
    present in two files is taken once, not twice."""
    import glob
    import numpy as np
    root, ext = os.path.splitext(table)
    rows, seen = [], set()
    for p in [table] + sorted(glob.glob(f"{root}.s*{ext}")):
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p, newline="")):
            k = (r["subject"], r["label"], r.get("window_index"))
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    by = {}
    for r in rows:
        if r.get("status") != "ok":
            continue
        by.setdefault((r["subject"], r["label"]), []).append(r)
    out = []
    for (subj, lab), rr in sorted(by.items()):
        if len(rr) != N_WINDOWS:
            continue
        rr.sort(key=lambda r: int(r["window_index"]))
        d = {"subject": subj, "label": lab, "idx": [int(r["window_index"]) for r in rr],
             EMG: [_f(r[EMG]) for r in rr]}
        for m in MEASURES + (CONTROL,):
            d[m] = [_f(r[m]) for r in rr]
        if not np.isfinite(d[EMG]).all():
            continue
        out.append(d)
    return out, len({r["label"] for r in rows})


def stat_over_blocks(blocks, measure, emg_key=EMG, perm=None):
    import numpy as np
    vals, subj = [], []
    for i, b in enumerate(blocks):
        e = b[emg_key]
        if perm is not None:
            e = [e[j] for j in perm[i]]
        v = partial_spearman_on_index(b[measure], e, b["idx"])
        if np.isfinite(v):
            vals.append(v); subj.append(b["subject"])
    return np.asarray(vals), np.asarray(subj)


def main(argv=None) -> int:
    import numpy as np
    from bsde.verifier.stats import cluster_bootstrap_ci

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", default=TABLE)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)

    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E123", "A",
            "Does time-irreversibility move with submental muscle tone when the sleep stage is held fixed?",
            "sleep-edfx",
            "median within-block partial spearman(irr3, emg_mean | window index), cluster CI over subjects",
            ["G1 coverage >=60 blocks over >=30 subjects",
             "G2 positive control exponent_high fires (doubles as the dynamic-range gate)",
             "G3 no N1 rows"],
            "permute the EMG window order within each block, 500 draws, compare against the DISTRIBUTION",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E111",
            instrument_changed="the CONTROL: a within-stage contrast where EMG varies and state does not, "
                               "replacing a within-subject regression on a state-tracking variable")
        print("registered E123")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    if a.register_only:
        return 0

    if not os.path.exists(a.table):
        print(f"{a.table} does not exist yet -- extraction still running")
        return 0

    blocks, _ = blocks_from(a.table)
    labels = sorted({b["label"] for b in blocks})
    subjects = sorted({b["subject"] for b in blocks})
    rng = np.random.default_rng(SEED)

    gates = {"G1_blocks": len(blocks), "G1_subjects": len(subjects),
             "G1_pass": len(blocks) >= MIN_BLOCKS and len(subjects) >= MIN_SUBJECTS,
             "G3_labels": labels, "G3_pass": "N1" not in labels,
             "blocks_per_stage": {l: sum(1 for b in blocks if b["label"] == l) for l in labels}}

    if not gates["G1_pass"]:
        json.dump({"gates": gates, "verdict": "REFUSED: coverage"}, open(a.out, "w"), indent=1)
        print(json.dumps(gates, indent=1))
        return 0

    def summarise(measure):
        v, s = stat_over_blocks(blocks, measure)
        if v.size < MIN_BLOCKS:
            return {"n_blocks": int(v.size), "median": float("nan"),
                    "lo": float("nan"), "hi": float("nan")}
        med = float(np.median(v))
        lo, hi, n_ok = cluster_bootstrap_ci(lambda idx: float(np.median(v[idx])), s,
                                            np.random.default_rng(SEED + 1), reps=2000)
        return {"n_blocks": int(v.size), "median": med, "lo": float(lo), "hi": float(hi),
                "n_boot_ok": int(n_ok)}

    ctrl = summarise(CONTROL)
    gates["G2_positive_control"] = ctrl
    gates["G2_pass"] = bool(np.isfinite(ctrl["lo"]) and (ctrl["lo"] > 0 or ctrl["hi"] < 0))
    gates["G2_direction_as_predicted"] = bool(np.isfinite(ctrl["hi"]) and ctrl["hi"] < 0)

    primary = {m: summarise(m) for m in MEASURES}

    # ---- placebo: permute the EMG window order inside each block ------------------------------------
    placebo = {}
    for m in (CONTROL,) + MEASURES:
        draws = []
        for _ in range(a.placebo_draws):
            perm = [rng.permutation(N_WINDOWS) for _ in blocks]
            v, _s = stat_over_blocks(blocks, m, perm=perm)
            if v.size:
                draws.append(float(np.median(v)))
        d = np.asarray(draws, float)
        real = (ctrl if m == CONTROL else primary[m])["median"]
        placebo[m] = {"n_draws": int(d.size), "mean": float(d.mean()) if d.size else float("nan"),
                      "p2.5": float(np.quantile(d, 0.025)) if d.size else float("nan"),
                      "p97.5": float(np.quantile(d, 0.975)) if d.size else float("nan"),
                      "frac_draws_at_least_as_extreme":
                          float(np.mean(np.abs(d) >= abs(real))) if d.size and np.isfinite(real)
                          else float("nan")}

    p = primary["irr3"]
    beats_placebo = bool(np.isfinite(placebo["irr3"]["frac_draws_at_least_as_extreme"])
                         and placebo["irr3"]["frac_draws_at_least_as_extreme"] <= 0.05)

    if not gates["G2_pass"]:
        verdict = ("(a) NOT INTERPRETABLE -- the positive control did not fire "
                   f"({CONTROL} partial rho {ctrl['median']:+.4f} [{ctrl['lo']:+.4f}, {ctrl['hi']:+.4f}]). "
                   "Either within-block submental tone does not vary enough to be read, or the control "
                   "does not behave as the muscle account requires. NOTHING follows about "
                   "irreversibility, and in particular a null primary here is NOT evidence that "
                   "irreversibility is muscle-free.")
    elif not np.isfinite(p["lo"]):
        verdict = "(a) NOT INTERPRETABLE -- the primary could not be estimated."
    elif p["lo"] > 0:
        verdict = (f"(b) MUSCLE-ASSOCIATED -- irr3 partial rho {p['median']:+.4f} "
                   f"[{p['lo']:+.4f}, {p['hi']:+.4f}] with the stage held fixed"
                   + (", and it beats the permutation placebo." if beats_placebo else
                      ", but it does NOT beat the permutation placebo, so it is withdrawn."))
    elif p["hi"] < 0:
        verdict = (f"(c) ASSOCIATED IN THE WRONG DIRECTION -- irr3 partial rho {p['median']:+.4f} "
                   f"[{p['lo']:+.4f}, {p['hi']:+.4f}]. More submental tone goes with LESS "
                   "irreversibility. This excludes the null and REFUTES the muscle account rather than "
                   "supporting it; it must not be filed as muscle contamination.")
    else:
        verdict = (f"(d) NOT MUSCLE -- irr3 partial rho {p['median']:+.4f} "
                   f"[{p['lo']:+.4f}, {p['hi']:+.4f}] includes zero while the positive control fired at "
                   f"{ctrl['median']:+.4f} [{ctrl['lo']:+.4f}, {ctrl['hi']:+.4f}] on the SAME blocks. "
                   "With the stage held fixed, irreversibility does not track submental tone, so E107's "
                   "REM placement needs a non-muscle explanation. The placebo is NOT INFORMATIVE here "
                   "(rule 48): there is no real effect for a fake ordering to fail to reproduce.")

    out = {"gates": gates, "primary": primary, "placebo": placebo, "verdict": verdict}
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
