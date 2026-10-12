#!/usr/bin/env python3
"""E67 -- Challenge A. Does a measure move the SAME WAY when consciousness falls with a drug and without one?

REGISTERED BEFORE ANY WITHIN-SUBJECT EFFECT HAS BEEN COMPUTED IN EITHER ARM. What has been read of these
three tables is their structure only -- column names, label vocabularies, subject counts, and the fact that
sleep stage is encoded in the `recording_id` suffix. No feature value has been related to any state label.

=========================================================================================================
WHY THIS EXISTS, AND WHY IT NEEDS NO SECOND DRUG
=========================================================================================================
Challenge A wants a measure that tracks STATE while carrying little DRUG identity. Q26 closed the direct
route on VitalDB: thirteen measures across five families failed to separate propofol from sevoflurane at
matched depth, for three separately measured reasons. Q27's ketamine deposit is behind an anti-scraping
wall and Q29's sleep-deprivation cohort is still extracting.

**But the acceptance condition can be tested with a drug arm and a NO-DRUG arm, and both have been sitting
in `results/` all along.** Natural N3 sleep is a loss of consciousness with no pharmacology whatsoever.
Propofol sedation is a loss of consciousness with pharmacology. Both are available WITHIN SUBJECT:

    NO-DRUG   Sleep-EDFx, W vs N3, same subject same night, 142 subjects
    DRUG      ds005620, task-awake vs task-sed, same subject, 21 subjects (propofol)
    DRUG-2    ds004541, baseline vs post-LOC epochs, same subject, 8 subjects (general anaesthesia)

**THE PRIMARY IS SIGN AGREEMENT, NOT MAGNITUDE, AND THAT IS A DELIBERATE LIMITATION.** The two arms are not
depth-matched -- N3 is not the same depth as propofol sedation, and neither is calibrated against the
other -- so a magnitude ratio would confound "carries drug information" with "one arm went deeper". A SIGN
is invariant to depth as long as the effect is monotone in depth, which is what makes it the statistic this
comparison can actually support. Error-catalogue rule 16 read forwards: when two arms of the same test
disagree in sign, the definition is doing the work rather than the biology.

  A measure that moves the SAME way in both arms is tracking something both states share -- reduced
  consciousness -- which is what Challenge A asks for.
  A measure that REVERSES is telling you about the drug, not the state, however well it performs inside
  either arm alone.

=========================================================================================================
DESIGN
=========================================================================================================
FEATURES. The intersection all three tables carry: `lempel_ziv`, `relative_alpha_power`,
`relative_delta_power`, `spectral_edge_95`, `spectral_entropy`, `whole_head_exponent`. Fixed here; the
richer 13-feature set exists on Sleep-EDFx and ds004541 but not on ds005620, and using different feature
sets per arm would make the arms incomparable.

EFFECT PER ARM. Within-subject paired difference (unconscious minus conscious), summarised as Cohen's
**d_z** with a subject-clustered bootstrap. Paired by construction in every arm -- same subject, same
night or same session.

  G1 ALIVENESS GATE (rule 53), evaluated FIRST and per feature. **Both arms must show a non-null effect**,
  i.e. each arm's d_z interval must exclude zero. If a feature does not move in one of the arms, its sign
  there is a coin flip and agreement or disagreement means nothing. A feature failing G1 is reported as
  UNTESTABLE, never as agreeing.

  PRIMARY   per surviving feature, do the DRUG and NO-DRUG arms agree in sign? Reported per feature and as
            a count. The interesting object is the LIST, not a single number: Challenge A needs to know
            WHICH measures survive, not how many.

  P1 REPLICATION  the same sign comparison against DRUG-2 (ds004541, general anaesthesia rather than
            sedation). A feature that agrees with one drug arm and disagrees with the other has not passed
            anything, and n = 8 means this arm can only ever be corroborative.

  P2 PLACEBO  the within-subject pairing broken -- each subject's unconscious value paired against a
            DIFFERENT subject's conscious value, same arm, 200 draws. This destroys the paired structure
            while preserving both marginal distributions, so it measures how often sign agreement arises
            from the group means alone. **A comparison against the real result, never a threshold**
            (rule 34).

VERDICT RULE, wrong direction first.

  (a) ALL REVERSE     -- every surviving feature disagrees in sign. Everything this project measures is
                         reading pharmacology rather than state, and Challenge A has no candidate here.
  (b) NONE TESTABLE   -- G1 removes every feature.
  (c) NOT INFORMATIVE -- the broken-pairing placebo reproduces the agreement rate.
  (d) SPLIT           -- some agree and some reverse. **This is the informative outcome and the one the
                         design is built for**: the agreeing subset is Challenge A's candidate list and
                         the reversing subset is a list of measures that must never be described as
                         consciousness markers.
  (e) ALL AGREE       -- every surviving feature agrees. Weaker evidence than it looks: it would mean the
                         comparison does not discriminate between candidates, and the honest reading is
                         that sign agreement is too permissive a test rather than that everything passed.

WHAT NO OUTCOME LICENCES. Sign agreement is a NECESSARY condition, not a sufficient one. A measure that
agrees here has not been shown to carry little drug identity -- only that it does not reverse. And neither
arm's cohort is matched to the other on age, montage or device, so E53's cross-deposit floor applies to
anything except the sign.

    python -m bsde.experiments.e67_drug_vs_drugfree_sign
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e67_drug_vs_drugfree_sign.json")

FEATURES = ["lempel_ziv", "relative_alpha_power", "relative_delta_power",
            "spectral_edge_95", "spectral_entropy", "whole_head_exponent"]
REPS = 2000
PLACEBO_DRAWS = 200
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _pairs(rows, subj_key, is_conscious, is_unconscious):
    """subject -> (conscious value, unconscious value) per feature, medians within each side."""
    acc = defaultdict(lambda: defaultdict(lambda: ([], [])))
    for r in rows:
        s = subj_key(r)
        if not s:
            continue
        c, u = is_conscious(r), is_unconscious(r)
        if not (c or u):
            continue
        for f in FEATURES:
            v = _f(r.get(f, ""))
            if np.isfinite(v):
                acc[f][s][0 if c else 1].append(v)
    out = {}
    for f, per in acc.items():
        pr = [(np.median(a), np.median(b)) for a, b in per.values() if a and b]
        out[f] = (np.array([p[0] for p in pr]), np.array([p[1] for p in pr]))
    return out


def _dz(c, u, rng, reps=REPS):
    """Cohen's d_z for the paired difference (unconscious minus conscious), with a subject bootstrap."""
    d = u - c
    d = d[np.isfinite(d)]
    if d.size < 5 or d.std(ddof=1) < 1e-12:
        return float("nan"), float("nan"), float("nan"), int(d.size)
    point = float(d.mean() / d.std(ddof=1))
    vals = []
    for _ in range(reps):
        b = d[rng.integers(0, d.size, d.size)]
        if b.std(ddof=1) > 1e-12:
            vals.append(b.mean() / b.std(ddof=1))
    v = np.sort(vals)
    return point, float(np.quantile(v, .025)), float(np.quantile(v, .975)), int(d.size)


def load_arms():
    sleep = list(csv.DictReader(open(os.path.join(RESULTS, "sleep_edfx_five_stage.csv"), newline="")))
    ds56 = list(csv.DictReader(open(os.path.join(RESULTS, "ds005620_features.csv"), newline="")))
    ds45 = list(csv.DictReader(open(os.path.join(RESULTS, "ds004541_v2.csv"), newline="")))
    arms = {}
    arms["NO-DRUG (sleep W->N3)"] = _pairs(
        sleep, lambda r: r.get("subject", ""),
        lambda r: r["recording_id"].endswith("@W"),
        lambda r: r["recording_id"].endswith("@N3"))
    arms["DRUG (ds005620 propofol)"] = _pairs(
        ds56, lambda r: r.get("subject", ""),
        lambda r: r.get("meta_task", "") == "awake",
        lambda r: r.get("meta_task", "").startswith("sed"))
    arms["DRUG-2 (ds004541 GA)"] = _pairs(
        ds45, lambda r: r.get("subject", ""),
        lambda r: "@baseline" in r["recording_id"] or "@start-" in r["recording_id"],
        lambda r: "@loc" in r["recording_id"] or "@post" in r["recording_id"])
    return arms


def main() -> int:
    arms = load_arms()
    rng = np.random.default_rng(SEED)
    eff = {}
    print(f"{'arm':<28s} {'feature':<24s} {'n':>4s} {'d_z':>8s} {'95% CI':>20s}")
    for name, per in arms.items():
        eff[name] = {}
        for f in FEATURES:
            c, u = per.get(f, (np.array([]), np.array([])))
            pt, lo, hi, n = _dz(c, u, np.random.default_rng(SEED))
            eff[name][f] = {"d_z": pt, "lo": lo, "hi": hi, "n": n}
            ci = f"[{lo:+.3f}, {hi:+.3f}]" if np.isfinite(lo) else "        --"
            print(f"{name:<28s} {f:<24s} {n:>4d} {pt:>8.3f} {ci:>20s}")
        print()

    NO, DR, D2 = list(arms)
    res = {"effects": eff, "features": {}}
    print(f"{'feature':<24s} {'no-drug':>10s} {'drug':>10s} {'G1':>6s} {'sign':>10s} {'drug-2':>10s}")
    agree, reverse, untestable = [], [], []
    for f in FEATURES:
        a, b, c2 = eff[NO][f], eff[DR][f], eff[D2][f]
        alive = all(np.isfinite(x["lo"]) and (x["lo"] > 0 or x["hi"] < 0) for x in (a, b))
        s = "--"
        if alive:
            same = np.sign(a["d_z"]) == np.sign(b["d_z"])
            s = "AGREE" if same else "REVERSE"
            (agree if same else reverse).append(f)
        else:
            untestable.append(f)
        d2s = ("--" if not np.isfinite(c2["lo"]) or not (c2["lo"] > 0 or c2["hi"] < 0)
               else ("agree" if np.sign(c2["d_z"]) == np.sign(a["d_z"]) else "reverse"))
        print(f"{f:<24s} {a['d_z']:>10.3f} {b['d_z']:>10.3f} {'ok' if alive else 'FAIL':>6s} "
              f"{s:>10s} {d2s:>10s}")
        res["features"][f] = {"alive": bool(alive), "sign": s, "drug2": d2s}

    # P2 placebo: break the within-subject pairing in BOTH arms, recompute the agreement rate.
    rp = np.random.default_rng(SEED + 1)
    hits = []
    for _ in range(PLACEBO_DRAWS):
        n_ag = 0
        for f in agree + reverse:
            sg = []
            for nm in (NO, DR):
                c, u = arms[nm][f]
                pt, lo, hi, _ = _dz(c[rp.permutation(len(c))], u, np.random.default_rng(SEED), reps=200)
                sg.append(np.sign(pt))
            n_ag += int(sg[0] == sg[1])
        hits.append(n_ag)
    plac = float(np.mean(hits)) / max(1, len(agree + reverse))
    real = len(agree) / max(1, len(agree + reverse))
    print(f"\nPRIMARY  sign agreement on {len(agree + reverse)} testable features: "
          f"{len(agree)} AGREE, {len(reverse)} REVERSE  (rate {real:.3f})")
    print(f"P2 PLACEBO  pairing broken, mean agreement rate = {plac:.3f} "
          f"({PLACEBO_DRAWS} draws)")
    if untestable:
        print(f"G1 removed (not moving in at least one arm): {untestable}")

    if not (agree or reverse):
        verdict = ("NONE TESTABLE -- G1 removed every feature: nothing moves in both arms, so no sign "
                   "can be compared. Rule 53.")
    elif not agree:
        verdict = ("ALL REVERSE -- every testable feature moves the OPPOSITE way when consciousness falls "
                   "with a drug versus without one. Everything measured here is reading pharmacology "
                   "rather than state, and Challenge A has no candidate in this feature set.")
    elif plac >= real:
        verdict = ("NOT INFORMATIVE -- breaking the within-subject pairing reproduces the agreement rate, "
                   "so the agreement comes from the group means rather than from paired structure.")
    elif not reverse:
        verdict = ("ALL AGREE -- every testable feature agrees in sign. This is WEAKER than it looks: a "
                   "test nothing fails does not discriminate between candidates (rule 49), and the honest "
                   "reading is that sign agreement is too permissive rather than that everything passed.")
    else:
        verdict = (f"SPLIT -- {agree} agree in sign across drug and drug-free loss of consciousness; "
                   f"{reverse} REVERSE. The reversing set must never be described as consciousness "
                   f"markers: within either arm alone they would look fine. The agreeing set is Challenge "
                   f"A's candidate list, subject to sign agreement being NECESSARY and not sufficient.")
    print(f"\nVERDICT: {verdict}")
    res.update({"agree": agree, "reverse": reverse, "untestable": untestable,
                "agreement_rate": real, "placebo_rate": plac, "verdict": verdict})
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
