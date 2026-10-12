#!/usr/bin/env python3
"""E153 -- E152's two survivors, tested as a PAIRED contrast and against the muscle objection.

REGISTERED BEFORE THE PAIRED CONTRAST OR THE BAND-RESTRICTED ARM HAS BEEN COMPUTED. Successor to E152.
Cohort, landmarks, windows, comparison-band construction and both controls are E152's, unchanged.

=========================================================================================================
WHY E152'S POSITIVE IS NOT CLAIMED, IN TWO PARTS
=========================================================================================================
E152 reported `rel_gamma` and `spectral_edge_95` keeping D > 0 at the real landmark while a same-limb
pseudo-landmark sat at zero, at BOTH landmarks, with a positive control detected at 9/9 subjects and a
drug-trajectory negative control at +0.0097 and +0.0119.

**OBJECTION 1 -- MY VERDICT RULE, AND IT IS RULE 34 EXACTLY.** Survival was coded as
`real_ci_lo > 0 AND pseudo_ci_lo <= 0`: a placebo compared against an ABSOLUTE THRESHOLD rather than
against the real effect. `rel_gamma` passes it with pseudo point estimates of **+0.6893 and +0.7578**
against reals of +1.5120 and +1.8017 -- intervals that overlap heavily, a placebo that merely INCLUDES
zero rather than sitting at it. `spectral_edge_95` separates properly (+0.1278 / +0.1472 against
+0.5012 / +0.6875), and the difference between those two situations is invisible to the rule as written.
**The correct statistic is the PAIRED per-subject difference `D_real - D_pseudo`**, which E152 never
formed.

**OBJECTION 2 -- THE OLDEST TRAP IN THIS REPOSITORY.** The two survivors are the two most
EMG-susceptible measures in the panel: `rel_gamma` is 30-49.5 Hz, and `spectral_edge_95` is dominated by
high-frequency content. **Muscle tone is coupled to RESPONSIVENESS, not to concentration**, so facial EMG
changing at a behavioural landmark and not at a same-limb pseudo-landmark is precisely the artefact this
project has chased through E43, E71, E107, E111 and E123. A landmark-specific high-frequency jump is what
a jaw does when a subject starts responding.

=========================================================================================================
THE TWO CHANGES
=========================================================================================================
**1. PAIRED CONTRAST.** The primary is now `Delta = mean over subjects of (D_real - D_pseudo)`, formed
within subject before averaging, with the subject bootstrap and sign count on that difference. The
pseudo-landmark is chosen per subject as the SIDE WITH MORE ROOM, fixed before any value is computed, so
the choice cannot follow the data.

**2. A BAND-RESTRICTED ARM, which is the discriminating test.** Every candidate is recomputed from the
spectrum truncated at **30 Hz** -- below the frequency where surface facial EMG contributes materially --
and the whole design is re-run on those. `rel_gamma` does not exist below 30 Hz and is therefore dropped
from that arm by construction, which is the point: if `spectral_edge_95` survives band restriction, the
muscle explanation is bounded; if it does not, the muscle explanation is the parsimonious one.

=========================================================================================================
GATES
=========================================================================================================
G1  MANIFEST, E152's: `(PSEUDO+1)*W` epochs of room either side of each landmark.
G2  POSITIVE CONTROL, on the PAIRED statistic. A synthetic `label + noise` feature must give
    `Delta > 0` with an interval excluding zero -- the paired contrast is a harder test than E152's and a
    control that does not survive it makes every null below unreadable.
G3  DRUG-TRAJECTORY NEGATIVE CONTROL, on the PAIRED statistic: the triangular ramp must give `Delta`
    indistinguishable from zero.
G4  **BAND-RESTRICTION SANITY.** The band-restricted features must still be alive
    (|AUC-0.5| >= 0.10 for conscious vs unconscious). Truncating at 30 Hz removes real signal as well as
    muscle, and a candidate that dies from the truncation cannot be used to argue anything about muscle.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF NOTHING SURVIVES THE PAIRED CONTRAST**, E152 is withdrawn outright and the conclusion returns to
E151's expected one: the frontal spectral family tracks the concentration trajectory and carries no
detectable signature of the behavioural threshold. **This is the expected outcome for `rel_gamma`,
whose pseudo estimate is already half its real one.**

**IF SOMETHING SURVIVES THE PAIRED CONTRAST BUT DIES UNDER BAND RESTRICTION**, the effect is real and it
is muscle -- which is a finding about responsiveness rather than about cortex, and must be reported that
way rather than as a consciousness marker.

**IF SOMETHING SURVIVES BOTH**, it is the first evidence in this project of a sub-30 Hz spectral feature
sensitive to the behavioural threshold rather than to the exposure, and it goes to the 44 OR cases before
it is described further.

**REGISTERED PREDICTION: `rel_gamma` fails the paired contrast; `spectral_edge_95` survives the paired
contrast and DIES under band restriction.** Both halves are unfavourable to this project's interest.

WHAT WAS ALREADY SEEN (rule 41). All of E152's output, quoted above and in its ledger row.

    python bsde/src/bsde/experiments/e153_paired_contrast_and_muscle.py
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import auc_abs, cluster_bootstrap_ci                  # noqa: E402

sys.path.insert(0, HERE)
import e148_roc_concentration_matched_dissociation as E148                     # noqa: E402
from e152_limb_matched_landmark import PSEUDO, W_PRIMARY, d_limb               # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e153_paired_contrast.json")
FULL = os.path.join(RESULTS, "mgh_volunteer_windows.csv")
LT30 = os.path.join(RESULTS, "mgh_volunteer_windows_lt30.csv")
ALIVE_BAR = 0.10


def load_table(path):
    E148.TABLE = path
    return E148.load()


def paired(data, ok, series_of, tag_key, rng, w=W_PRIMARY):
    """Per subject: D at the real landmark minus D at the same-limb pseudo-landmark. Paired, then averaged.

    The pseudo side is chosen per subject as the one with MORE ROOM, decided from the recording geometry
    before any feature value is read, so the choice cannot follow the data."""
    per = {}
    for c in ok:
        d = data[c]
        lm = int(d[tag_key][0])
        n = d["n"]
        side = +1 if (n - 1 - lm) >= lm else -1
        pl = lm + side * PSEUDO * w
        v = series_of(c)
        if pl < w or pl >= n - w:
            per[c] = float("nan")
            continue
        dr, _ = d_limb(v, lm, w, n, rng)
        dp, _ = d_limb(v, pl, w, n, rng)
        per[c] = dr - dp if (math.isfinite(dr) and math.isfinite(dp)) else float("nan")
    vals = np.array([per[c] for c in ok], float)
    good = np.isfinite(vals)
    if good.sum() < 6:
        return None
    lo, hi, _n = cluster_bootstrap_ci(lambda ix, vv=vals[good]: float(np.mean(vv[list(ix)])),
                                      np.arange(int(good.sum())), rng, reps=2000)
    return {"mean_delta": float(np.mean(vals[good])), "ci": [lo, hi],
            "n_pos": int((vals[good] > 0).sum()), "n": int(good.sum()),
            "per_subject": {c: per[c] for c in ok}}


def usable(data):
    need = (PSEUDO + 1) * W_PRIMARY
    return [c for c in sorted(data)
            if len(data[c]["loc"]) == 1 and len(data[c]["roc"]) == 1
            and data[c]["loc"][0] >= need and data[c]["n"] - data[c]["roc"][0] >= need
            and data[c]["roc"][0] - data[c]["loc"][0] >= need]


def alive_features(data, ok, feats):
    out = []
    for f in feats:
        vals = []
        for c in ok:
            d = data[c]
            m = np.isfinite(d["X"][f]) & np.isin(d["label"], (0.0, 1.0))
            if m.sum() > 50 and len(set(d["label"][m])) > 1:
                vals.append(auc_abs(list(d["label"][m]), list(d["X"][f][m])) - 0.5)
        if vals and float(np.mean(vals)) >= ALIVE_BAR:
            out.append(f)
    return out


def run_arm(name, path, rng, out):
    if not os.path.exists(path):
        print(f"{name}: {path} absent -- arm skipped and reported as such")
        out[name] = {"skipped": "table absent"}
        return None
    data = load_table(path)
    ok = usable(data)
    feats = alive_features(data, ok, E148.FEATURES)
    print(f"\n{'=' * 96}\n{name}: {len(ok)} usable volunteers, {len(feats)} alive candidates "
          f"of {len(E148.FEATURES)}")
    arm = {"usable": ok, "alive": feats, "controls": {}, "primary": {}}

    print(f"G2 POSITIVE CONTROL on the PAIRED statistic")
    g2ok = True
    for sig in (0.25, 0.5, 1.0):
        syn = {c: data[c]["label"] + sig * rng.standard_normal(data[c]["n"]) for c in ok}
        for tag, key in (("LOC", "loc"), ("ROC", "roc")):
            r = paired(data, ok, lambda c, s=syn: s[c], key, rng)
            arm["controls"][f"pos_sigma{sig}_{tag}"] = r
            if r:
                print(f"   sigma={sig:<5}{tag}  delta={r['mean_delta']:+.4f} "
                      f"[{r['ci'][0]:+.4f},{r['ci'][1]:+.4f}]  {r['n_pos']}/{r['n']}")
                g2ok &= r["ci"][0] > 0
    print(f"   -> {'PASS' if g2ok else 'FAIL -- the paired contrast cannot see a feature built to be seen'}")

    print(f"G3 DRUG-TRAJECTORY NEGATIVE CONTROL on the PAIRED statistic")
    tri = {}
    for c in ok:
        d = data[c]
        n, mid = d["n"], (int(d["loc"][0]) + int(d["roc"][0])) // 2
        t = np.arange(n, dtype=float)
        tri[c] = np.clip(np.where(t <= mid, t / max(mid, 1), (n - t) / max(n - mid, 1)), 0, 1) \
            + 0.05 * rng.standard_normal(n)
    g3ok = True
    for tag, key in (("LOC", "loc"), ("ROC", "roc")):
        r = paired(data, ok, lambda c, s=tri: s[c], key, rng)
        arm["controls"][f"neg_{tag}"] = r
        if r:
            print(f"   {tag}  delta={r['mean_delta']:+.4f} [{r['ci'][0]:+.4f},{r['ci'][1]:+.4f}]  "
                  f"{r['n_pos']}/{r['n']}")
            g3ok &= r["ci"][0] <= 0 <= r["ci"][1]
    print(f"   -> {'PASS' if g3ok else 'FAIL -- the drug trajectory alone produces a paired effect'}")
    arm["G2_pass"], arm["G3_pass"] = bool(g2ok), bool(g3ok)

    print(f"\n{'candidate':18s} {'lm':4s} {'delta':>9s} {'95% CI':>20s} {'signs':>7s}")
    for f in feats:
        for tag, key in (("LOC", "loc"), ("ROC", "roc")):
            r = paired(data, ok, lambda c, ff=f: data[c]["X"][ff], key, rng)
            if not r:
                continue
            arm["primary"][f"{f}|{tag}"] = r
            print(f"{f:18s} {tag:4s} {r['mean_delta']:+9.4f} "
                  f"[{r['ci'][0]:+7.4f},{r['ci'][1]:+7.4f}] {r['n_pos']:3d}/{r['n']:<3d}")
    arm["survivors"] = [f for f in feats
                        if arm["primary"].get(f"{f}|LOC", {}).get("ci", [-1, 1])[0] > 0
                        and arm["primary"].get(f"{f}|ROC", {}).get("ci", [-1, 1])[0] > 0]
    print(f"   survivors at BOTH landmarks: {arm['survivors'] or 'none'}")
    out[name] = arm
    return arm


def main(argv=None) -> int:
    rng = np.random.default_rng(153)
    out = {"experiment": "E153", "window": W_PRIMARY, "pseudo_offset_windows": PSEUDO}
    full = run_arm("full_spectrum", FULL, rng, out)
    lt30 = run_arm("below_30Hz", LT30, rng, out)

    if not full or not (full["G2_pass"] and full["G3_pass"]):
        verdict = "NO VERDICT -- the full-spectrum arm's controls did not pass"
    elif not full["survivors"]:
        verdict = ("E152 WITHDRAWN -- nothing survives the PAIRED contrast at both landmarks. E152's "
                   "positives were an artefact of comparing a placebo against an absolute threshold "
                   "instead of against the real effect (rule 34). The conclusion returns to E151's "
                   "expected one: the frontal spectral family tracks the concentration trajectory and "
                   "carries no detectable signature of the behavioural threshold crossing.")
    elif lt30 and not lt30.get("skipped") and lt30.get("G2_pass"):
        both = [f for f in full["survivors"] if f in lt30["survivors"]]
        if both:
            verdict = (f"POSITIVE AND NOT MUSCLE -- {', '.join(both)} survive the paired contrast at "
                       f"both landmarks AND below 30 Hz, where surface facial EMG cannot reach. First "
                       f"evidence here of a sub-30 Hz spectral feature sensitive to the behavioural "
                       f"threshold rather than to the exposure. Replicate on the 44 OR cases.")
        else:
            verdict = (f"REAL BUT MUSCLE -- {', '.join(full['survivors'])} survive the paired contrast on "
                       f"the full spectrum and none survives below 30 Hz. The effect is a "
                       f"responsiveness-coupled high-frequency change, i.e. muscle, and must be reported "
                       f"as a finding about behaviour rather than about cortex. Registered prediction "
                       f"confirmed.")
    else:
        verdict = (f"PARTIAL -- {', '.join(full['survivors'])} survive the paired contrast on the full "
                   f"spectrum; the band-restricted arm is unavailable or failed its own controls, so the "
                   f"muscle objection is NOT settled and no claim is made.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
