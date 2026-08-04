#!/usr/bin/env python3
"""E245 -- E244 re-run with a placebo that can fire at a ceiling and that matches the decision.

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E244. One instrument change: the placebo. The primary, the gates, the gap statistic and
the 0.05 bar are E244's verbatim.

WHY E244 WAS WITHDRAWN. Its placebo drew a random threshold from the source's observed range and asked
`mean(rand >= acc) < 0.05`. `whole_head_exponent` transported at accuracy **1.0000** -- the maximum the
statistic can take -- against a placebo MEAN of 0.6091, and was recorded as FAILING, because every
random draw landing in the target's separation gap ties with 1.0000 and counts as `>=`. The test could
not pass for a perfect classifier: the better the transport, the more certain the refusal. That is rule
37's operator family arriving at a boundary, and it is now catalogue rule 94.

THE DEEPER ERROR SURVIVES FIXING THE OPERATOR, WHICH IS WHY THE PLACEBO IS REPLACED RATHER THAN
REPAIRED. A random-threshold placebo asks whether the fitted threshold is SPECIAL. Deployment asks
whether it WORKS at the target. Those come apart exactly when the classes separate well: if many
thresholds succeed, transport is EASIER, and a specialness placebo reads that abundance as weak
evidence (rule 55 -- the placebo must be able to change the statistic it is a placebo for, and must be
about the same claim).

THE REPLACEMENT. The SOURCE'S CLASS LABELS are permuted, the threshold is refitted on the permuted
source, and that threshold is transported to the target exactly as the real one is. This destroys the
source's class information while preserving the source's distribution, the target, the fitting
procedure and the whole pipeline -- so it isolates precisely what transport is supposed to carry. A
real transported accuracy that a label-permuted source can match is not carrying class information
across the deposits. The comparison is against the placebo DISTRIBUTION's 95th percentile rather than
an equality test, so a ceiling-valued statistic is not defeated by ties (rule 94).

ORIGINAL E244 QUESTION, unchanged: which measures transport a decision THRESHOLD between deposits?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E244 by an instrument change: the estimand becomes threshold transportability, applied to
every shared measure and both directions rather than to one measure in one direction.

WHY THE PREVIOUS METRIC HAS TO BE REPLACED. Challenge D has been scored throughout
`PROBE_2026_08_02_SEPARABILITY.md` by a DISTRIBUTIONAL TRANSPORT RATIO -- the between-deposit shift of a
state divided by the within-deposit effect size. E243 showed that statistic is real and not
decision-relevant. `whole_head_exponent` fails it (means and ranges differ substantially between
Sleep-EDFx and ds006695; ratio 0.211 at the wake anchor and 0.478 at the N3 anchor) and yet Sleep-EDFx's
own threshold, 1.6965, applied untouched to ds006695 classifies wake versus N3 at accuracy **1.0000** --
because the threshold lands inside the target's separation gap, between max wake +1.6708 and min N3
+1.9042. Calibration made it WORSE at every k (OFFSET 0.686-0.727, OFFSET+SCALE 0.953-0.973), and even a
target-native threshold from 4 labelled target subjects reached only 0.9688.

**A measure can fail the ratio and transport perfectly**, because classification needs both deposits'
separations to straddle a common value, not their means to agree. Every conclusion in sections 7, 11, 12
and 15 rests on the ratio, so the ranking has to be redone against the thing that actually matters.

WHAT IS COMPUTED. For every measure present in both deposits, and for BOTH directions of transfer:

  source threshold  -- the value maximising balanced wake-versus-N3 accuracy on the SOURCE subjects
  transported acc   -- that threshold applied untouched to the TARGET subjects
  target ceiling    -- the target's own best achievable balanced accuracy, its within-deposit limit
  transport gap     -- ceiling minus transported accuracy, in accuracy points

The gap is the quantity Challenge D should have been ranking by from the start: how much decision
performance is lost by importing a threshold rather than learning one. A measure with a large
distributional shift and a zero gap is deployable; one with a small shift and a large gap is not.

DIRECTION IS TESTED BOTH WAYS BECAUSE TRANSFER NEED NOT BE SYMMETRIC. E243 tested Sleep-EDFx (141
subjects) to ds006695 (19) only. A threshold estimated on 141 subjects and applied to 19 is a different
proposition from the reverse, and reporting one as "transport" would hide that.

PRIMARIES.

  P1  the transport gap per measure per direction, ranked.
  P2  the count of measures whose gap is at or below 0.05 in BOTH directions -- the ones that would
      actually deploy.
  P3  the Spearman correlation, across measures, between the OLD distributional ratio and the NEW
      transport gap. If the two ranked measures the same way the replacement changes nothing and this
      file is redundant; E243 predicts they do not agree, and P3 measures by how little.

GATES, each able to go either way (rules 40 and 81).

  G1  EACH DIRECTION NEEDS A LIVE SOURCE. The source threshold must achieve better than chance on its
      own subjects, else it is not a threshold and transporting it means nothing (rule 53).
  G2  THE TARGET MUST HAVE A CEILING ABOVE CHANCE for the measure, else a small gap is two failures
      agreeing and not transport. Measures failing this in a direction are REPORTED as unevaluable in
      that direction, not scored (rule 74).
  G3  CAPABILITY, both directions, on synthetic deposits whose answer is known by construction: two
      sites drawn from the SAME distribution must give a gap near zero, and two whose separations do NOT
      overlap must give a large gap. If the statistic cannot tell those apart it cannot rank anything.
  G4  COVERAGE. At least 10 subjects per deposit carrying both states, and at least 8 shared measures,
      or P3's correlation is computed on too few points to read.

PLACEBO. The source threshold is replaced by one drawn uniformly from the source's own observed range.
A random threshold from the right range inherits the measure's scale and nothing about where the
classes divide, so it is the destruction that matches this estimand (rule 55; a covariate permutation
could not touch it, which is how E230 and E231 died). A measure whose real transported accuracy does not
beat its own random-threshold distribution has not demonstrated transport, whatever its gap.

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37).

  (a) The old ratio and the new gap correlate NEGATIVELY across measures -> WRONG DIRECTION: the ratio
      was not merely uninformative but anti-informative, and every Challenge D ranking built on it was
      worse than random. Reported with the correlation.
  (b) P2 is zero -> NOTHING DEPLOYS. No measure transports a threshold in both directions, and Challenge
      D's problem is real even under the corrected metric.
  (c) P2 is at least one AND the ratio-versus-gap correlation is weak -> THE METRIC WAS WRONG AND THE
      ANSWER CHANGES. The measures that deploy are named, and the ratio-based ranking is withdrawn.
  (d) P2 is at least one AND the two metrics agree strongly -> THE RANKING SURVIVES ITS METRIC. E243 was
      a special case rather than a general correction, and the earlier sections stand.

  Gating, applied AFTER the primaries because a gate can only invalidate a pass and never rescue a null
  (rule 37): G3 or G4 failing -> NOT INTERPRETABLE. A measure failing G1 or G2 in a direction is dropped
  from that direction with the reason printed.

SCOPE. Two sleep deposits and one state contrast (W versus N3). ds006695 is a 3-channel forehead montage
with 19 subjects against Sleep-EDFx's 2-channel with 141; the project's own deposit probe records that
this makes some measures arguably different measurements in each, and a gap measured here is not a
general deployability figure. Subject-level means are used throughout, because 19 subjects and not 1140
epochs is the independent unit (rule 69).

INCUMBENT (rule 45): the distributional transport ratio from the separability probe, which the new
statistic must be shown to disagree with -- otherwise the replacement is cosmetic (rule 60).

    python bsde/src/bsde/experiments/e245_threshold_transport_v2.py
"""
from __future__ import annotations

import collections
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

SLEEP = "bsde/results/sleep_edfx_five_stage.csv"
DS = "bsde/results/ds006695_features.csv"
OUT = "bsde/results/e245_threshold_transport_v2.json"
MIN_SUBJECTS = 10
MIN_MEASURES = 8
GAP_OK = 0.05
N_PLACEBO = 500
SEED = 20260802
SKIP = ("recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq",
        "n_samples", "stage", "epoch_index", "t_start_s", "label", "url", "start_seconds",
        "window_s", "__subj__")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def load(path, subj_of, stage_of):
    import numpy as np
    from bsde.verifier.stats import read_rows
    rows, _ = read_rows(path)
    cols = [k for k in rows[0] if k not in SKIP and not k.startswith("meta_")]
    d = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    for r in rows:
        s, st = subj_of(r), stage_of(r)
        for c in cols:
            v = _f(r.get(c))
            if np.isfinite(v):
                d[c][s][st].append(v)
    out = {}
    for c in cols:
        per = {}
        for s, st in d[c].items():
            if "W" in st and "N3" in st:
                per[s] = (float(np.mean(st["W"])), float(np.mean(st["N3"])))
        if per:
            out[c] = per
    return out


def best_threshold(w, n):
    """Threshold maximising BALANCED accuracy, and that accuracy."""
    import numpy as np
    lo, hi = min(w.min(), n.min()), max(w.max(), n.max())
    grid = np.linspace(lo, hi, 2001)
    # direction is chosen by the data: N3 may be above or below W depending on the measure
    up = [float(np.mean(w < t) / 2 + np.mean(n >= t) / 2) for t in grid]
    dn = [float(np.mean(w >= t) / 2 + np.mean(n < t) / 2) for t in grid]
    iu, idn = int(np.argmax(up)), int(np.argmax(dn))
    if up[iu] >= dn[idn]:
        return float(grid[iu]), float(up[iu]), +1
    return float(grid[idn]), float(dn[idn]), -1


def apply_threshold(w, n, thr, sign):
    import numpy as np
    if sign > 0:
        return float(np.mean(w < thr) / 2 + np.mean(n >= thr) / 2)
    return float(np.mean(w >= thr) / 2 + np.mean(n < thr) / 2)


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import spearman
    rng = np.random.default_rng(SEED)

    A = load(SLEEP, lambda r: r["recording_id"].split("@")[0][:6],
             lambda r: r["recording_id"].split("@")[-1])
    B = load(DS, lambda r: r["subject"], lambda r: r["stage"])
    shared = sorted(set(A) & set(B))
    print(f"sleep_edfx measures {len(A)}, ds006695 measures {len(B)}, SHARED {len(shared)}")
    nA = len({s for c in A for s in A[c]})
    nB = len({s for c in B for s in B[c]})
    print(f"subjects with both W and N3: sleep_edfx {nA}, ds006695 {nB}")
    g4 = nA >= MIN_SUBJECTS and nB >= MIN_SUBJECTS and len(shared) >= MIN_MEASURES
    print(f"G4 coverage: {'PASS' if g4 else 'FAIL'}")

    # ---- G3 capability on synthetic sites ------------------------------------------------------------
    def gap_for(wa, na, wb, nb):
        thr, sacc, sign = best_threshold(wa, na)
        _t, ceil, _s = best_threshold(wb, nb)
        return ceil - apply_threshold(wb, nb, thr, sign), sacc, ceil

    same_w, same_n = rng.normal(0, 1, 300), rng.normal(3, 1, 300)
    g_same, _, _ = gap_for(same_w, same_n, rng.normal(0, 1, 300), rng.normal(3, 1, 300))
    g_disj, _, _ = gap_for(same_w, same_n, rng.normal(20, 1, 300), rng.normal(23, 1, 300))
    g3 = abs(g_same) < 0.05 and g_disj > 0.3
    print(f"G3 capability: same-distribution sites give gap {g_same:+.4f}, non-overlapping sites "
          f"{g_disj:+.4f} -> {'PASS' if g3 else 'FAIL'}")

    res, dropped = {}, {}
    for c in shared:
        res[c] = {}
        for lab, (src, tgt) in (("sleep_edfx->ds006695", (A, B)), ("ds006695->sleep_edfx", (B, A))):
            sw = np.asarray([src[c][s][0] for s in src[c]], float)
            sn = np.asarray([src[c][s][1] for s in src[c]], float)
            tw = np.asarray([tgt[c][s][0] for s in tgt[c]], float)
            tn = np.asarray([tgt[c][s][1] for s in tgt[c]], float)
            if min(len(sw), len(tw)) < MIN_SUBJECTS or np.std(np.r_[sw, sn]) <= 0:
                dropped.setdefault(c, []).append(f"{lab}: too few subjects or constant")
                continue
            thr, sacc, sign = best_threshold(sw, sn)
            _t, ceil, _s = best_threshold(tw, tn)
            acc = apply_threshold(tw, tn, thr, sign)
            if sacc <= 0.55:
                dropped.setdefault(c, []).append(f"{lab}: G1 source not alive ({sacc:.3f})")
                continue
            if ceil <= 0.55:
                dropped.setdefault(c, []).append(f"{lab}: G2 target has no ceiling ({ceil:.3f})")
                continue
            # PLACEBO: permute the SOURCE's class labels, refit, transport. Destroys the source's class
            # information and nothing else -- not a random threshold, which tests specialness rather
            # than transport (rule 94).
            pooled = np.r_[sw, sn]
            rand = []
            for _ in range(N_PLACEBO):
                q = rng.permutation(len(pooled))
                pw, pn = pooled[q[:len(sw)]], pooled[q[len(sw):]]
                pthr, _pa, psign = best_threshold(pw, pn)
                rand.append(apply_threshold(tw, tn, pthr, psign))
            rand = np.asarray(rand, float)
            res[c][lab] = {"source_acc": sacc, "threshold": thr, "sign": sign,
                           "target_ceiling": ceil, "transported_acc": acc, "gap": ceil - acc,
                           "placebo_mean": float(rand.mean()),
                           "placebo_p95": float(np.percentile(rand, 95)),
                           "beats_placebo": bool(acc > float(np.percentile(rand, 95)))}
    print()
    print(f"{'measure':28s}{'gap A->B':>10}{'gap B->A':>10}{'acc A->B':>10}{'acc B->A':>10}{'both<=.05':>11}")
    both_ok = []
    for c in shared:
        f = res[c].get("sleep_edfx->ds006695")
        b = res[c].get("ds006695->sleep_edfx")
        if not f or not b:
            continue
        ok = f["gap"] <= GAP_OK and b["gap"] <= GAP_OK and f["beats_placebo"] and b["beats_placebo"]
        if ok:
            both_ok.append(c)
        print(f"{c:28s}{f['gap']:10.4f}{b['gap']:10.4f}{f['transported_acc']:10.4f}"
              f"{b['transported_acc']:10.4f}{'YES' if ok else '':>11}")
    print(f"\nDROPPED (rule 74): {dropped if dropped else 'none'}")
    print(f"P2 measures transporting a threshold in BOTH directions and beating their placebo: "
          f"{len(both_ok)} -- {both_ok}")

    # ---- P3 does the new statistic disagree with the old ratio? ---------------------------------------
    ev = [c for c in shared if res[c].get("sleep_edfx->ds006695")]
    ratio, gap = [], []
    for c in ev:
        aw = np.asarray([A[c][s][0] for s in A[c]], float)
        an = np.asarray([A[c][s][1] for s in A[c]], float)
        bw = np.asarray([B[c][s][0] for s in B[c]], float)
        bn = np.asarray([B[c][s][1] for s in B[c]], float)
        da = (an.mean() - aw.mean()) / np.sqrt((aw.var(ddof=1) + an.var(ddof=1)) / 2)
        db = (bn.mean() - bw.mean()) / np.sqrt((bw.var(ddof=1) + bn.var(ddof=1)) / 2)
        shift = (bw.mean() - aw.mean()) / np.sqrt((aw.var(ddof=1) + bw.var(ddof=1)) / 2)
        den = np.mean([abs(da), abs(db)])
        if den > 0:
            ratio.append(abs(shift) / den)
            gap.append(res[c]["sleep_edfx->ds006695"]["gap"])
    p3 = float(spearman(ratio, gap)) if len(ratio) >= 5 else float("nan")
    print(f"P3 Spearman(old distributional ratio, new transport gap) over {len(ratio)} measures = "
          f"{p3:+.4f}")

    if np.isfinite(p3) and p3 < -0.3:
        verdict = (f"WRONG DIRECTION -- the old ratio correlates NEGATIVELY with the transport gap "
                   f"({p3:+.4f}), so it was anti-informative and every Challenge D ranking built on it "
                   "was worse than useless")
    elif not both_ok:
        verdict = ("NOTHING DEPLOYS -- no measure transports a threshold in both directions while "
                   "beating its own random-threshold placebo; Challenge D's problem is real under the "
                   "corrected metric too")
    elif np.isfinite(p3) and abs(p3) < 0.4:
        verdict = (f"THE METRIC WAS WRONG AND THE ANSWER CHANGES -- {len(both_ok)} measures transport a "
                   f"threshold in both directions ({', '.join(both_ok)}), and the old ratio barely "
                   f"predicts the new gap (Spearman {p3:+.4f}); the ratio-based ranking is withdrawn")
    else:
        verdict = (f"THE RANKING SURVIVES ITS METRIC -- {len(both_ok)} measures deploy and the two "
                   f"statistics agree (Spearman {p3:+.4f}); E243 was a special case, not a general "
                   "correction")
    if not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; the gap statistic cannot separate identical sites from disjoint ones"
    elif not g4:
        verdict = "NOT INTERPRETABLE -- G4 coverage failed"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"shared": shared, "results": res, "dropped": dropped, "both_ok": both_ok,
                   "p3_ratio_vs_gap": p3, "n_subjects": {"sleep_edfx": nA, "ds006695": nB},
                   "capability": {"same_sites_gap": g_same, "disjoint_sites_gap": g_disj},
                   "gates": {"G3": bool(g3), "G4": bool(g4)}, "verdict": verdict, "seed": SEED},
                  fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
