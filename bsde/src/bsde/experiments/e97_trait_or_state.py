"""E97 -- Is `ge_norm` a TRAIT or a STATE? The question that decides what E86's D1-only result means.

REGISTERED BEFORE ANY RELIABILITY IS COMPUTED. Feasibility probed first (rule 41): all 62 Stieger subjects
carry >= 2 sessions, 186 sessions in total. No feature has been related to any accuracy here.

=========================================================================================================
WHY THIS DECIDES E86
=========================================================================================================
E86 gave Challenge B its first primary to clear its gates: `ge_norm` at D1 rho +0.307 [+0.049, +0.534]
between subjects, outside its placebo -- **and D2, the consecutive-session change design, is null**
(+0.120 [-0.073, +0.310]). I filed that as a qualification, on the precedent that E73 refused to promote
`wpli_alpha_clustering` for the same D1-only pattern.

**That precedent may be wrong, and the difference is testable.** A between-subject association with a null
change-score is what a stable CONFOUND looks like -- and it is equally what a genuine TRAIT predictor looks
like. If a measure does not vary within a person across sessions, its change score is noise by
construction and D2 cannot be positive no matter how real D1 is. E45 established the distinction matters
in this project by finding `lempel_ziv` is a state rather than a trait.

So: **if `ge_norm` is trait-like, D2's null is expected and E86's qualification 3 dissolves. If it is
state-like, D2's null is evidence against D1 and the qualification stands.** Nobody has measured the
reliability of any FEATURE here; E68 measured it for the labels.

=========================================================================================================
PRIMARY -- a comparison, not a threshold (rule 63)
=========================================================================================================
    P  ICC(2,1) of `ge_norm` across sessions within subject, with a subject bootstrap. **The verdict is
       whether it lies closer to the TRAIT control or to the STATE control**, both computed on the same
       sessions by the same estimator. No absolute ICC cut-off is used, because any such cut-off would be
       a convention and rule 63 was earned twice today by exactly that.

CONTROLS, bracketing the estimator (the E72 pattern):
    C+  `iaf` -- individual alpha frequency. Among the most reliable EEG measures known and a textbook
        trait; if it does not come back high, the estimator is broken and nothing below is interpretable.
    C-  a per-session Gaussian draw. Must come back at ~0.

VERDICT, wrong direction first (rule 37):
    (a) ICC below the noise control      -> NOT-COMPUTABLE, the estimator is misbehaving.
    (b) closer to the noise control      -> STATE-LIKE. D2's null is evidence against D1 and E86's
                                            qualification 3 STANDS.
    (c) closer to the trait control      -> TRAIT-LIKE. D2's null is expected by construction, E86's
                                            qualification 3 DISSOLVES, and -- symmetrically -- E73's
                                            refusal of `wpli_alpha_clustering` must be revisited on the
                                            same grounds rather than left as a precedent that suited us.

PREDICTED: TRAIT-LIKE, and stated knowing it is the outcome that helps E86 -- which is why the trait
control exists and why the reciprocal obligation to revisit E73 is written into the verdict.

GATES: G1 >= 40 subjects with >= 2 sessions. G2 the trait control's ICC must exceed the noise control's,
else the estimator cannot tell them apart and no feature can be placed between them.

SCOPE. Reliability is not validity: a perfectly reliable measure can be reliably irrelevant. This decides
only how D2's null should be read.

    python -m bsde.experiments.e97_trait_or_state
"""
from __future__ import annotations
import csv, json, os, sys
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

OUT = os.path.join(RESULTS, "e97_trait_or_state.json")
PRIMARY = "ge_norm"
FEATURES = ["ge_norm", "cl_norm", "modularity", "iaf", "alpha_prom", "ge", "deg", "smallworld"]
TRAIT_CTRL, NOISE_CTRL = "iaf", "_CTRL_noise"
MIN_SUBJECTS = 40
REPS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def icc21(groups):
    """ICC(2,1) from a one-way decomposition: between-subject variance over total.

    Unbalanced designs are handled by the standard k0 correction, so subjects contributing two sessions
    and subjects contributing three are not silently weighted as if equal.
    """
    groups = [np.asarray(g, float) for g in groups if np.isfinite(g).sum() >= 2]
    groups = [g[np.isfinite(g)] for g in groups]
    if len(groups) < 5:
        return float("nan")
    n = len(groups)
    ns = np.array([g.size for g in groups], float)
    grand = np.concatenate(groups).mean()
    msb = float(np.sum(ns * (np.array([g.mean() for g in groups]) - grand) ** 2) / (n - 1))
    within = np.concatenate([(g - g.mean()) ** 2 for g in groups])
    dfw = float(np.sum(ns) - n)
    msw = float(within.sum() / dfw) if dfw > 0 else float("nan")
    k0 = float((np.sum(ns) - np.sum(ns ** 2) / np.sum(ns)) / (n - 1))
    if not np.isfinite(msw) or k0 <= 0:
        return float("nan")
    num = msb - msw
    den = msb + (k0 - 1) * msw
    return float(num / den) if den > 1e-12 else float("nan")


def boot_icc(groups, seed, reps=REPS):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        idx = rng.integers(0, len(groups), len(groups))
        v = icc21([groups[i] for i in idx])
        if np.isfinite(v):
            out.append(v)
    if len(out) < 50:
        return float("nan"), float("nan")
    out = np.sort(out)
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))


def main() -> int:
    per = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(RESULTS, "stieger_graph62.csv"), newline="")):
        per[r["subject"]][int(r["session"])] = r
    subs = [s for s, v in per.items() if len(v) >= 2]
    res = {"gates": {"G1_subjects": len(subs), "G1_pass": bool(len(subs) >= MIN_SUBJECTS)}, "icc": {}}
    print(f"{len(per)} subjects, {sum(len(v) for v in per.values())} sessions; "
          f"{len(subs)} with >= 2 sessions")
    print(f"G1 coverage   {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    if not res["gates"]["G1_pass"]:
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    print(f"\n{'feature':<16s} {'ICC(2,1)':>9s} {'95% CI':>20s}")
    for f in FEATURES + [NOISE_CTRL]:
        groups = []
        for s in subs:
            if f == NOISE_CTRL:
                groups.append(rng.normal(size=len(per[s])))
            else:
                groups.append(np.array([_f(per[s][k].get(f, "")) for k in sorted(per[s])]))
        v = icc21(groups)
        lo, hi = boot_icc(groups, SEED + 1)
        res["icc"][f] = {"icc": v, "lo": lo, "hi": hi}
        tag = ("  <-PRIMARY" if f == PRIMARY else
               "  (trait control)" if f == TRAIT_CTRL else
               "  (noise control)" if f == NOISE_CTRL else "")
        print(f"{f:<16s} {v:+9.4f} [{lo:+8.4f}, {hi:+8.4f}]{tag}")

    t, nz, p = (res["icc"][TRAIT_CTRL]["icc"], res["icc"][NOISE_CTRL]["icc"], res["icc"][PRIMARY]["icc"])
    g2 = bool(np.isfinite(t) and np.isfinite(nz) and t > nz)
    res["gates"]["G2_pass"] = g2
    print(f"\nG2 bracket    trait {t:+.4f} > noise {nz:+.4f}   {'PASS' if g2 else 'FAIL'}")
    if not g2:
        print("GATE FAILED -- the estimator cannot separate its own controls. ABSENT (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    if not np.isfinite(p) or p < nz:
        v = "NOT-COMPUTABLE -- the primary's ICC is below the noise control; the estimator is misbehaving."
    elif abs(p - t) < abs(p - nz):
        v = (f"TRAIT-LIKE -- `{PRIMARY}` ICC {p:+.4f} lies closer to the trait control ({t:+.4f}) than to "
             f"the noise control ({nz:+.4f}). **D2's null in E86 is expected by construction** -- a measure "
             f"that does not vary within a person cannot produce a positive change-score correlation -- so "
             f"E86's qualification 3 DISSOLVES. The reciprocal obligation written into this registration "
             f"applies: E73's refusal of `wpli_alpha_clustering` on the same D1-only grounds must be "
             f"revisited, not left standing because it suited us.")
    else:
        v = (f"STATE-LIKE -- `{PRIMARY}` ICC {p:+.4f} lies closer to the noise control ({nz:+.4f}) than to "
             f"the trait control ({t:+.4f}). D2's null is evidence AGAINST D1 and E86's qualification 3 "
             f"STANDS.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
