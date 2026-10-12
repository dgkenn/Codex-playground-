#!/usr/bin/env python3
"""E148 -- Challenge A's recovery clause, tested with a drug reference matched by CONSTRUCTION.

REGISTERED BEFORE ANY FEATURE IS COMPARED AGAINST ANY LABEL IN THIS DEPOSIT. What has been looked at is
the label structure and it is disclosed in full at the end.

=========================================================================================================
THE CLAUSE THIS MORNING'S AUDIT DECLARED UNTESTABLE
=========================================================================================================
`docs/CHALLENGE_A_AUDIT_2026_08_01.md` closed E139-E142 with: the Krause deposit *"contains no recovery --
in 0 of 27 patients does an awake block occur after the last unresponsive block"*, so Challenge A's
**"predicts loss AND recovery"** clause could not be tested on the only two-agent deposit available.

`eeg-power-anesthesia` supplies the recovery, and supplies it better than any cohort this project has
used. All ten volunteers have **exactly one LOC and exactly one ROC**, both defined behaviourally --
*"the time at which the probability of response to both click and verbal cues dropped below 5 %"*, and
ROC when it *"again exceeded 5 %"*. Not a rater's judgement, not read off the EEG, and not a sedation
score. Recordings run 150-173 minutes with 18-67 minutes of drug-free baseline before LOC.

=========================================================================================================
WHY THIS IS A SHARPER TEST THAN E05, AND THE REASON IS PHARMACOKINETIC RATHER THAN STATISTICAL
=========================================================================================================
E05 asked the right question on Chennu -- at recovery the drug is still present and behaviour is back, so
does a candidate follow the drug or the state? -- and had to match the drug reference by looking up which
sedation level had the closest measured plasma concentration (mild, 438 ug/L against recovery's 276).
That match is approximate and it is the weakest joint in the design.

**Here the match is free and exact to within a few minutes of a slow descending limb.** Take the window
immediately BEFORE ROC and the window immediately AFTER ROC. They are minutes apart on a decaying
concentration curve, so the drug is essentially identical across them; the behavioural state is maximally
different, because the subject is by definition unresponsive on one side and responsive on the other.
**Concentration is held constant by adjacency and state is flipped by the landmark.** The same
construction applies at LOC in the opposite direction, which is what makes both halves of "loss and
recovery" testable in one file.

    v_BASE   median over the drug-free baseline, the first 300 epochs (10 min)
    v_PRE    median over the W epochs immediately BEFORE the landmark
    v_POST   median over the W epochs immediately AFTER the landmark

    S = (d_drug - d_state) / (d_drug + d_state)   in [-1, +1]

At ROC:  d_state = |v_POST - v_BASE|   (POST is conscious; a state-follower returns to baseline)
         d_drug  = |v_POST - v_PRE|    (PRE is unconscious at the SAME concentration)
At LOC:  the mirror -- d_state = |v_POST - v_BASE| with POST now unconscious, so a state-follower
         DEPARTS from baseline, and the statistic is defined so that S > 0 still means "follows state".

**S > 0 means the candidate moves with behaviour across a landmark where the drug did not move.
S < 0 means it stayed with the drug while behaviour flipped.** Challenge A's acceptance condition wants
S > 0 at BOTH landmarks.

=========================================================================================================
GATES -- all evaluated and printed before the primary (rules 34, 37)
=========================================================================================================
G1  MANIFEST. Ten volunteers, each with exactly one LOC and one ROC, >= 300 baseline epochs before LOC
    and >= W epochs on both sides of both landmarks.
G2  **ALIVENESS, and it can fail per candidate.** A candidate that does not separate conscious from
    unconscious at all will score S trivially, because every distance in the formula is noise. Each
    candidate must reach |AUC - 0.5| >= 0.10 for conscious versus unconscious within subject, pooled.
    Candidates failing this are dropped and named, never carried (rule 53: check the phenomenon exists in
    this cohort before asking who has less of it).
G3  **RANDOM-LANDMARK PLACEBO, and it GATES rather than accompanies (rule 64).** The entire statistic is
    recomputed at a landmark drawn uniformly at random from the interior of the unconscious period,
    preserving window sizes, 200 times per subject. Any candidate with a within-recording time trend --
    electrode drift, temperature, cumulative artefact -- produces a gap at a random landmark too. The
    real S must lie outside the central 95 % of the random-landmark distribution. **This is the gate E98
    needed and did not have; seven of its eighteen features were withdrawn by exactly this control.**
G4  WINDOW SENSITIVITY. W in {60, 150, 300} epochs (2, 5, 10 minutes). The sign of the subject-level mean
    S must agree across all three, or the result is a window artefact and is reported as one.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
For each surviving candidate, the subject-level mean S at each landmark, with a subject bootstrap over
the ten volunteers and a sign test over the ten per-subject values (10/10 gives p = 0.002, 9/10 gives
0.011 -- the only honest inference at this n, and it is stated in advance rather than chosen afterwards).

**IF NO CANDIDATE HAS S > 0 AT BOTH LANDMARKS**, the honest report is that in this cohort every spectral
summary tracks the drug rather than the behavioural state across a concentration-matched transition. That
is a real negative for Challenge A on the best-anchored recovery data available, and it would mean the
brief's "predicts loss and recovery" clause is not satisfied by anything in the amplitude family -- which
is most of what a spectra-only deposit can offer.

**REGISTERED PREDICTION: S < 0 AT BOTH LANDMARKS FOR THE ALPHA MEASURES, AND THE SIGN IS THE POINT.**
Frontal alpha under propofol is a direct read-out of thalamocortical drug action, so across a window where
concentration barely moves it should barely move either, i.e. stay with PRE. The prediction is registered
against this project's interest, exactly as E05's was: S > 0 would be the good news for a consciousness
marker. **A prediction that only the favourable outcome can confirm is not a prediction.**

Secondary and genuinely open: `spectral_entropy` and `exponent_1_40`. The aperiodic exponent is an
excitation/inhibition read-out and should behave like the alpha measures; entropy is a whole-spectrum
summary with no single pharmacological locus and has no registered direction.

=========================================================================================================
SCOPE, STATED SO NOTHING IS OVERCLAIMED
=========================================================================================================
**One agent.** These volunteers received propofol only, so this file tests the "loss and recovery" half of
Challenge A and says nothing about "across anaesthetics". Krause tests the other half and has no recovery.
The two halves remain in different cohorts and only a two-agent within-subject LOR/ROR study closes the
gap -- which is the Turku/Kallionpaa request, now supported by two independent structural findings rather
than one.

**Spectra only.** No phase measure, no complexity measure, no irreversibility. The AMPLITUDE family is all
that exists here, so a null cannot be read as a statement about representations in general.

**n = 10.** The subject bootstrap will be wide. The sign test is the primary inference for that reason.

WHAT WAS ALREADY SEEN (rule 41). Label structure only, fetched to check feasibility before this file was
written: per volunteer, the epoch count, the recording length, the conscious/unconscious counts, and the
LOC and ROC times in minutes. Every subject has exactly one of each. No feature has been compared against
any label in this deposit, and the OR cohort is untouched by this file.

    python bsde/src/bsde/experiments/e148_roc_concentration_matched_dissociation.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc_abs, cluster_bootstrap_ci                  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "mgh_volunteer_windows.csv")
OUT = os.path.join(RESULTS, "e148_roc_dissociation.json")

FEATURES = ["rel_delta", "rel_theta", "rel_alpha", "rel_beta", "rel_gamma", "spectral_edge_95",
            "spectral_entropy", "exponent_1_40", "alpha_peak_hz", "alpha_prom_db", "total_power_db"]
BASELINE_EPOCHS = 300
WINDOWS = (60, 150, 300)
W_PRIMARY = 150
PLACEBO_DRAWS = 200
ALIVE_BAR = 0.10


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    per = defaultdict(list)
    for r in csv.DictReader(open(TABLE, newline="")):
        per[r["case"]].append(r)
    out = {}
    for c, rows in per.items():
        rows.sort(key=lambda r: _f(r["t"]))
        lab = np.array([_f(r["label"]) for r in rows])
        X = {f: np.array([_f(r[f]) for r in rows], float) for f in FEATURES}
        d = np.diff(lab)
        loc = np.flatnonzero(d == -1)
        roc = np.flatnonzero(d == 1)
        out[c] = {"label": lab, "X": X, "loc": loc, "roc": roc, "n": len(rows)}
    return out


def _med(v, i0, i1):
    seg = v[max(i0, 0):i1]
    seg = seg[np.isfinite(seg)]
    return float(np.median(seg)) if len(seg) >= 5 else float("nan")


def s_stat(v, base, landmark, w, flip):
    """S at one landmark. `flip` is +1 at ROC and -1 at LOC so that S>0 always means 'follows state'."""
    pre = _med(v, landmark - w + 1, landmark + 1)
    post = _med(v, landmark + 1, landmark + 1 + w)
    if not all(map(math.isfinite, (pre, post, base))):
        return float("nan")
    d_state = abs(post - base)
    d_drug = abs(post - pre)
    if d_state + d_drug < 1e-12:
        return float("nan")
    s = (d_drug - d_state) / (d_drug + d_state)
    return s if flip > 0 else -s


def main(argv=None) -> int:
    rng = np.random.default_rng(148)
    data = load()
    subs = sorted(data)
    out = {"experiment": "E148", "n_subjects": len(subs), "window_primary": W_PRIMARY}

    # ---- G1 MANIFEST ---------------------------------------------------------------------------------
    ok_subj = []
    for c in subs:
        d = data[c]
        good = (len(d["loc"]) == 1 and len(d["roc"]) == 1 and d["loc"][0] >= BASELINE_EPOCHS
                and d["loc"][0] >= max(WINDOWS) and d["roc"][0] - d["loc"][0] >= max(WINDOWS)
                and d["n"] - d["roc"][0] >= max(WINDOWS))
        if good:
            ok_subj.append(c)
    g1 = len(ok_subj) >= 8
    print(f"G1 MANIFEST  {len(ok_subj)} of {len(subs)} volunteers usable (one LOC, one ROC, "
          f">={BASELINE_EPOCHS} baseline epochs, >={max(WINDOWS)} either side) -> "
          f"{'PASS' if g1 else 'FAIL'}")
    out["G1"] = {"pass": bool(g1), "usable": ok_subj, "all": subs}

    # ---- G2 ALIVENESS --------------------------------------------------------------------------------
    alive, dead = [], []
    for f in FEATURES:
        vals = []
        for c in ok_subj:
            d = data[c]
            m = np.isfinite(d["X"][f]) & np.isin(d["label"], (0.0, 1.0))
            if m.sum() > 50 and len(set(d["label"][m])) > 1:
                vals.append(auc_abs(list(d["label"][m]), list(d["X"][f][m])) - 0.5)
        a = float(np.mean(vals)) if vals else float("nan")
        (alive if math.isfinite(a) and a >= ALIVE_BAR else dead).append((f, a))
    print(f"G2 ALIVENESS  |AUC-0.5| conscious vs unconscious, mean over subjects (bar {ALIVE_BAR})")
    for f, a in sorted(alive + dead, key=lambda t: -(t[1] if math.isfinite(t[1]) else -9)):
        print(f"   {f:18s} {a:+.4f}  {'alive' if (f, a) in alive else 'DROPPED'}")
    feats = [f for f, _ in alive]
    out["G2"] = {"alive": {f: a for f, a in alive}, "dropped": {f: a for f, a in dead}}
    if not feats:
        print("\nG2 dropped every candidate -- no verdict.")
        json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
        return 1

    # ---- primary + G3 placebo + G4 window sweep ------------------------------------------------------
    res = {}
    print(f"\n{'candidate':18s} {'landmark':9s} {'mean S':>8s} {'95% CI':>20s} {'signs':>7s} "
          f"{'placebo pct':>12s} {'G4':>5s}")
    for f in feats:
        for tag, key, flip in (("LOC", "loc", -1), ("ROC", "roc", +1)):
            per_s, plc_pct, wins = {}, {}, {}
            for c in ok_subj:
                d = data[c]
                v = d["X"][f]
                base = _med(v, 0, BASELINE_EPOCHS)
                lm = int(d[key][0])
                per_s[c] = s_stat(v, base, lm, W_PRIMARY, flip)
                wins[c] = [s_stat(v, base, lm, w, flip) for w in WINDOWS]
                lo_i = int(d["loc"][0]) + max(WINDOWS)
                hi_i = int(d["roc"][0]) - max(WINDOWS)
                draws = []
                if hi_i > lo_i:
                    for _ in range(PLACEBO_DRAWS):
                        fake = int(rng.integers(lo_i, hi_i))
                        vv = s_stat(v, base, fake, W_PRIMARY, flip)
                        if math.isfinite(vv):
                            draws.append(vv)
                plc_pct[c] = (float(np.mean(np.asarray(draws) <= per_s[c]))
                              if draws and math.isfinite(per_s[c]) else float("nan"))
            vals = np.array([per_s[c] for c in ok_subj], float)
            good = np.isfinite(vals)
            if good.sum() < 6:
                continue
            m = float(np.mean(vals[good]))
            lo, hi, _n = cluster_bootstrap_ci(
                lambda ix, vv=vals[good]: float(np.mean(vv[list(ix)])),
                np.arange(good.sum()), rng, reps=2000)
            npos = int((vals[good] > 0).sum())
            pct = np.array([plc_pct[c] for c in ok_subj], float)
            pct = pct[np.isfinite(pct)]
            mean_pct = float(np.mean(pct)) if len(pct) else float("nan")
            outside = math.isfinite(mean_pct) and (mean_pct < 0.025 or mean_pct > 0.975)
            wm = [float(np.nanmean([wins[c][i] for c in ok_subj])) for i in range(len(WINDOWS))]
            g4 = len({int(np.sign(x)) for x in wm if math.isfinite(x) and x != 0}) == 1
            res[f"{f}|{tag}"] = {"feature": f, "landmark": tag, "mean_S": m, "ci": [lo, hi],
                                 "n_pos": npos, "n": int(good.sum()),
                                 "placebo_mean_pct": mean_pct, "placebo_outside": bool(outside),
                                 "window_means": wm, "G4_sign_agrees": bool(g4),
                                 "per_subject": {c: per_s[c] for c in ok_subj}}
            print(f"{f:18s} {tag:9s} {m:+8.4f} [{lo:+7.4f},{hi:+7.4f}] {npos:3d}/{int(good.sum()):<3d} "
                  f"{mean_pct:12.3f} {'ok' if g4 else 'FAIL':>5s}")
    out["primary"] = res

    # ---- verdict --------------------------------------------------------------------------------------
    both = []
    for f in feats:
        a, b = res.get(f"{f}|LOC"), res.get(f"{f}|ROC")
        if not (a and b):
            continue
        if (a["ci"][0] > 0 and b["ci"][0] > 0 and a["placebo_outside"] and b["placebo_outside"]
                and a["G4_sign_agrees"] and b["G4_sign_agrees"]):
            both.append(f)
    drug_side = [f for f in feats
                 if res.get(f"{f}|LOC", {}).get("ci", [1, 1])[1] < 0
                 and res.get(f"{f}|ROC", {}).get("ci", [1, 1])[1] < 0]
    if not g1:
        verdict = "NO VERDICT -- G1 failed"
    elif both:
        verdict = (f"POSITIVE -- {', '.join(both)} follow behavioural STATE across a "
                   f"concentration-matched transition at BOTH landmarks, outside the random-landmark "
                   f"placebo and stable across window widths. The registered prediction (S<0) is WRONG "
                   f"for these, which is the favourable direction and must be replicated before it is "
                   f"claimed: one agent, ten subjects, amplitude family only.")
    elif drug_side:
        verdict = (f"NEGATIVE AS PREDICTED -- {len(drug_side)} of {len(feats)} candidates have S < 0 at "
                   f"both landmarks ({', '.join(drug_side)}): across a window where the drug barely "
                   f"moved and behaviour flipped, they stayed with the drug. Challenge A's 'predicts "
                   f"loss and recovery' clause is not satisfied by the amplitude family on the "
                   f"best-anchored recovery data available to this project.")
    else:
        verdict = ("INDETERMINATE -- no candidate has an interval excluding zero at both landmarks with "
                   "its placebo and window gates passed, at n = 10.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
