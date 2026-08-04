"""E117 -- Does E116's SECOND AXIS relate to behavioural responsiveness beyond arousal?

REGISTERED BEFORE ANY CHENNU FEATURE IS CORRELATED WITH ANY BEHAVIOUR. Existing tables only. The feature
groups and their signs are taken from E116, which was computed on a DIFFERENT deposit (Sleep-EDFx) and a
different state set (sleep stages), so nothing here is fitted to chennu.

=========================================================================================================
WHY THIS IS THE EXPERIMENT
=========================================================================================================
E116 gave Challenge A its first controlled positive: **two state-carrying axes**, surviving a one-axis
control, a two-axis power control, an arch control (one latent axis with 35 % of features non-monotone in
it) and a null-calibration gate. The two axes are carried by disjoint measures:

    component 1 -- AROUSAL, monotone: W +0.514, N1 +0.323, REM +0.134, N2 -0.221, N3 -0.751.
        Loads on whole_head_exponent (-2.949), critical_slowing_ar1 (-2.876),
        multiscale_entropy_slope (-2.861), spectral_edge_95 (+2.787).
    component 2 -- NON-MONOTONE, low at BOTH ends: W -0.717, N1 +0.408, REM +0.362, N2 +0.279, N3 -0.332.
        Loads on exponent_high (+2.132), relative_alpha_power (+1.729), pac_slow_alpha (-1.161),
        relative_delta_power (-1.054), and near ZERO on lempel_ziv and exponent_low.

**A second axis of a measure inventory is a fact about measures. It becomes a fact about brains only if it
predicts something outside the EEG.** Every deposit this project has used lacks that -- which is why
Challenge A kept reducing to "is measure X redundant". chennu does not: it carries **`n_correct_of_40`,
reaction time and plasma propofol concentration** at four graded propofol sedation levels in 20 subjects,
with complete coverage (80 of 80 rows).

Behavioural responsiveness under sedation is the closest thing to an outcome about consciousness that this
project can reach. It is not a measure of experience -- an unresponsive patient may be conscious, which is
the whole premise of covert-consciousness work -- and that limit is restated in the scope note.

=========================================================================================================
ESTIMAND
=========================================================================================================
Per subject, across that subject's four sedation levels, everything z-scored WITHIN SUBJECT (rule 57).

Two scores are built from E116's feature groups using its loading SIGNS only -- not its magnitudes, which
are in sleep-stage units and have no reason to transfer:

    comp1 = -z(whole_head_exponent) - z(critical_slowing_ar1) - z(multiscale_entropy_slope)
            + z(spectral_edge_95)                                   higher = more aroused
    comp2 = +z(exponent_high) + z(relative_alpha_power) - z(pac_slow_alpha) - z(relative_delta_power)

    P  partial spearman( comp2 , n_correct | comp1 ), pooled over within-subject-standardised rows,
       SUBJECT-clustered bootstrap.
    And symmetrically partial spearman( comp1 , n_correct | comp2 ). **Both always reported** -- reporting
    only the one that works is the selective import rule 59 was earned on.

VERDICT, wrong direction FIRST (rule 37) -- and the wrong direction is the one that costs the finding:

    (a) comp2's interval INCLUDES 0 while comp1's excludes it -> **THE SECOND AXIS IS BEHAVIOURALLY
        SILENT.** It is a real second dimension of the measure inventory and it says nothing about
        responsiveness. E116 stands as a fact about measures and stops there.
    (b) BOTH include 0 -> ABSENT via G3: if arousal itself does not predict responsiveness under propofol,
        the transfer or the cohort is broken and nothing is interpretable.
    (c) BOTH exclude 0 -> the second axis carries behavioural information INDEPENDENT of arousal. The
        first result in this project that is about something outside the EEG.
    (d) comp2 excludes 0 and comp1 does not -> UNEXPECTED AND SUSPICIOUS. Arousal not predicting
        responsiveness while a non-monotone axis does would more likely mean the comp1 sign transfer
        failed than that arousal is irrelevant; read G6 before anything else.

PREDICTED: (a) at ~45 %, (c) at ~35 %, (b) at ~15 %, (d) at ~5 %. **(a) leads deliberately.** Behaviour
under sedation is largely a function of depth, and a non-monotone axis has no obvious reason to add to it;
saying so first stops a null being written up as expected and a positive being written up as inevitable.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 15 subjects with >= 3 sedation levels, all eight features and the behaviour finite.
    G2  BEHAVIOUR MUST VARY WITHIN SUBJECT. `n_correct_of_40` spans 0-40 across the cohort, but a subject
        whose score is constant across levels contributes nothing and is dropped; the count is reported.
    G3  POSITIVE CONTROL / THE INCUMBENT IS ALIVE (E33/E61). `comp1` must predict `n_correct`. If arousal
        does not predict responsiveness in a graded propofol study, the transfer or the cohort is broken
        and the verdict is ABSENT rather than a null (rule 31).
    G4  BEYOND DRUG, NOT ONLY BEYOND AROUSAL. The primary is re-run with plasma propofol concentration
        added to the control set. A critic's first move is "it just tracks the drug", and the answer has
        to be computed rather than asserted (rule 54: a named confound needs a line of code).
    G5  THE TWO SCORES MUST NOT BE THE SAME SCORE (rule 60). |spearman(comp1, comp2)| < 0.90 in chennu,
        else the partials are unstable and neither means anything.
    G6  THE SIGN TRANSFER MUST HAVE WORKED. `comp1` was given its signs by a sleep analysis; it must fall
        as anaesthetic depth rises. **If it does not, the a priori construction did not transfer to this
        deposit and the whole design is ABSENT** -- the gate that distinguishes a genuine out-of-sample
        transfer from a coincidence.
        **DEPTH IS PLASMA PROPOFOL, NOT THE LEVEL INDEX, AND THE FIRST DRAFT GOT THIS WRONG.** chennu's
        four levels are baseline / mild / moderate / RECOVERY: median plasma propofol runs
        **0 -> 438 -> 803 -> 276 ug/L** and median n_correct runs 39 -> 37.5 -> 35 -> 38. Level 4 is
        LIGHTER than level 3, so ordering by the level index is not ordering by depth and the first run's
        G6 failure (-0.2396) was measuring that mislabelling rather than a failed transfer. The gate now
        uses the recorded concentration, which is objective and monotone in depth by construction.

PLACEBO, gating: `n_correct` permuted ACROSS LEVELS WITHIN SUBJECT, 2000 draws -- preserving each
subject's set of behavioural scores and destroying only their alignment to state. Primary read FIRST
(rule 48).

SCOPE. chennu propofol sedation, 20 subjects, 4 levels. **`n_correct_of_40` is behavioural
RESPONSIVENESS, not experience**: an unresponsive person may be conscious, which is the premise of the
covert-consciousness literature this project cannot yet reach. A positive result would say the second axis
carries information about responsiveness beyond arousal ON THIS DEPOSIT, and nothing here detects or
measures consciousness.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "chennu_features_v3.csv")
OUT = os.path.join(RESULTS, "e117_second_axis_and_behaviour.json")

# E116's feature groups and loading SIGNS -- derived on Sleep-EDFx, not fitted here
COMP1 = {"whole_head_exponent": -1.0, "critical_slowing_ar1": -1.0,
         "multiscale_entropy_slope": -1.0, "spectral_edge_95": +1.0}
COMP2 = {"exponent_high": +1.0, "relative_alpha_power": +1.0,
         "pac_slow_alpha": -1.0, "relative_delta_power": -1.0}
BEHAVIOUR = "meta_n_correct_of_40"
DRUG = "meta_plasma_propofol_ug_per_L"
LEVEL = "meta_sedation_level"
MIN_SUBJECTS, MIN_LEVELS = 15, 3
ESCAPE_MAX = 0.90
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _rank(x):
    return np.argsort(np.argsort(np.asarray(x, float))).astype(float)


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.ptp(x[ok]) <= 0 or np.ptp(y[ok]) <= 0:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def partial_spearman(x, y, Z):
    x, y, Z = np.asarray(x, float), np.asarray(y, float), np.asarray(Z, float)
    if Z.ndim == 1:
        Z = Z.reshape(-1, 1)
    ok = np.isfinite(x) & np.isfinite(y) & np.all(np.isfinite(Z), axis=1)
    if ok.sum() < Z.shape[1] + 6:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    RZ = np.column_stack([np.ones(ok.sum())] + [_rank(Z[ok, j]) for j in range(Z.shape[1])])
    bx, *_ = np.linalg.lstsq(RZ, rx, rcond=None)
    by, *_ = np.linalg.lstsq(RZ, ry, rcond=None)
    ex, ey = rx - RZ @ bx, ry - RZ @ by
    d = float(np.sqrt((ex ** 2).sum() * (ey ** 2).sum()))
    return float((ex * ey).sum() / d) if d > 1e-12 else float("nan")


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE}")
        return 2
    per = defaultdict(list)
    for r in csv.DictReader(open(TABLE, newline="")):
        if r.get("status") != "ok":
            continue
        per[r["subject"]].append(r)

    feats = list(COMP1) + list(COMP2)
    subj, c1, c2, beh, drug, lvl = [], [], [], [], [], []
    dropped_const = 0
    for s, rows in per.items():
        M = np.array([[_f(r.get(f, "")) for f in feats] for r in rows], float)
        b = np.array([_f(r.get(BEHAVIOUR, "")) for r in rows], float)
        d = np.array([_f(r.get(DRUG, "")) for r in rows], float)
        L = np.array([_f(r.get(LEVEL, "")) for r in rows], float)
        ok = np.isfinite(M).all(axis=1) & np.isfinite(b)
        if ok.sum() < MIN_LEVELS:
            continue
        M, b, d, L = M[ok], b[ok], d[ok], L[ok]
        if np.ptp(b) <= 0:
            dropped_const += 1
            continue
        sd = M.std(axis=0)
        if np.any(sd <= 0):
            continue
        Z = (M - M.mean(axis=0)) / sd
        w1 = np.array([COMP1.get(f, 0.0) for f in feats])
        w2 = np.array([COMP2.get(f, 0.0) for f in feats])
        for i in range(Z.shape[0]):
            subj.append(s); c1.append(float(Z[i] @ w1)); c2.append(float(Z[i] @ w2))
            beh.append(float(b[i])); drug.append(float(d[i])); lvl.append(float(L[i]))
    subj = np.array(subj); c1 = np.array(c1); c2 = np.array(c2)
    beh = np.array(beh); drug = np.array(drug); lvl = np.array(lvl)
    usubs = sorted(set(subj))
    res = {"n_rows": int(c1.size), "n_subjects": len(usubs),
           "dropped_constant_behaviour": dropped_const, "gates": {}}
    print(f"{len(per)} subjects in the table; {len(usubs)} contribute {c1.size} rows; "
          f"{dropped_const} dropped for constant behaviour")
    res["gates"]["G1_pass"] = bool(len(usubs) >= MIN_SUBJECTS)
    res["gates"]["G2_dropped"] = dropped_const
    print(f"G1 coverage   {len(usubs)} >= {MIN_SUBJECTS}  "
          f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    esc = spearman(c1, c2)
    res["gates"]["G5_rho_comp1_comp2"] = esc
    res["gates"]["G5_pass"] = bool(np.isfinite(esc) and abs(esc) < ESCAPE_MAX)
    print(f"G5 separation rho(comp1, comp2) = {esc:+.4f}  "
          f"{'PASS' if res['gates']['G5_pass'] else 'FAIL'}")

    # G6 -- did the sleep-derived signs transfer? comp1 must fall as sedation deepens
    transfer = spearman(c1, -drug)
    res["gates"]["G6_rho_comp1_vs_lower_propofol"] = transfer
    res["gates"]["G6_rho_comp1_vs_level_index"] = spearman(c1, -lvl)
    res["gates"]["G6_pass"] = bool(np.isfinite(transfer) and transfer > 0)
    print(f"G6 transfer   comp1 vs LOWER plasma propofol = {transfer:+.4f}  "
          f"{'PASS -- the sleep-derived arousal signs transfer' if res['gates']['G6_pass'] else 'FAIL'}")

    rng = np.random.default_rng(SEED)

    def cluster_boot(fn):
        out = []
        for _ in range(REPS):
            pick = rng.choice(usubs, size=len(usubs), replace=True)
            idx = np.concatenate([np.flatnonzero(subj == s) for s in pick])
            out.append(fn(idx))
        return ci(out)

    g3 = partial_spearman(c1, beh, c2)
    g3_lo, g3_hi = cluster_boot(lambda i: partial_spearman(c1[i], beh[i], c2[i]))
    res["gates"]["G3"] = {"rho": g3, "lo": g3_lo, "hi": g3_hi,
                          "pass": bool(np.isfinite(g3_lo) and not (g3_lo <= 0.0 <= g3_hi))}
    print(f"G3 incumbent  partial(comp1, n_correct | comp2) = {g3:+.4f} [{g3_lo:+.4f}, {g3_hi:+.4f}]  "
          f"{'PASS' if res['gates']['G3']['pass'] else 'FAIL -- arousal does not predict responsiveness'}")

    p = partial_spearman(c2, beh, c1)
    p_lo, p_hi = cluster_boot(lambda i: partial_spearman(c2[i], beh[i], c1[i]))
    res["primary"] = {"rho": p, "lo": p_lo, "hi": p_hi}
    print(f"\nP  partial(comp2, n_correct | comp1) = {p:+.4f} [{p_lo:+.4f}, {p_hi:+.4f}]")

    Zd = np.column_stack([c1, drug])
    pd_ = partial_spearman(c2, beh, Zd)
    pd_lo, pd_hi = cluster_boot(lambda i: partial_spearman(c2[i], beh[i], Zd[i]))
    res["gates"]["G4"] = {"rho": pd_, "lo": pd_lo, "hi": pd_hi,
                          "pass": bool(np.isfinite(pd_lo) and not (pd_lo <= 0.0 <= pd_hi)
                                       and (pd_ * p) > 0)}
    print(f"G4 beyond drug  partial(comp2, n_correct | comp1 AND plasma propofol) = {pd_:+.4f} "
          f"[{pd_lo:+.4f}, {pd_hi:+.4f}]  "
          f"{'survives' if res['gates']['G4']['pass'] else 'DOES NOT SURVIVE'}")

    pl = []
    for _ in range(PLACEBO_DRAWS):
        bp = beh.copy()
        for s in usubs:
            m = np.flatnonzero(subj == s)
            bp[m] = beh[m][rng.permutation(m.size)]
        v = partial_spearman(c2, bp, c1)
        if np.isfinite(v):
            pl.append(v)
    q_lo, q_hi = ci(pl)
    inside = bool(np.isfinite(q_lo) and q_lo <= p <= q_hi)
    res["placebo"] = {"lo": q_lo, "hi": q_hi, "inside": inside}
    print(f"PLACEBO behaviour permuted within subject: [{q_lo:+.4f}, {q_hi:+.4f}]  "
          f"real {'INSIDE' if inside else 'outside'}")

    excl = bool(np.isfinite(p_lo) and not (p_lo <= 0.0 <= p_hi) and not inside)
    if not (res["gates"]["G1_pass"] and res["gates"]["G5_pass"] and res["gates"]["G6_pass"]):
        v = ("ABSENT -- a precondition failed: coverage, the two scores being the same score, or the "
             "sleep-derived signs failing to transfer to this deposit. Nothing was tested (rule 31).")
    elif not res["gates"]["G3"]["pass"] and not excl:
        v = ("ABSENT -- arousal itself does not predict behavioural responsiveness here, so the cohort or "
             "the transfer is broken and a null about the second axis would be uninterpretable "
             "(rule 31).")
    elif not excl:
        v = (f"**THE SECOND AXIS IS BEHAVIOURALLY SILENT.** comp2 carries no information about "
             f"responsiveness beyond arousal ({p:+.4f} [{p_lo:+.4f}, {p_hi:+.4f}]) while comp1 does "
             f"({g3:+.4f} [{g3_lo:+.4f}, {g3_hi:+.4f}]). E116's second axis is a real second dimension of "
             f"the MEASURE INVENTORY and stops there; it is not shown to be a fact about brains. The "
             f"placebo is not informative here (rule 48).")
    elif not res["gates"]["G3"]["pass"]:
        v = (f"UNEXPECTED AND SUSPICIOUS -- comp2 predicts responsiveness ({p:+.4f}) while comp1 does not "
             f"({g3:+.4f}). Arousal failing to predict responsiveness under graded propofol is more "
             f"likely a failed sign transfer than a fact about the brain; G6 returned {transfer:+.4f} and "
             f"should be read before anything else.")
    elif not res["gates"]["G4"]["pass"]:
        v = (f"BEYOND AROUSAL BUT NOT BEYOND DRUG -- comp2 adds to responsiveness over comp1 ({p:+.4f} "
             f"[{p_lo:+.4f}, {p_hi:+.4f}]) but not once plasma propofol is also controlled ({pd_:+.4f} "
             f"[{pd_lo:+.4f}, {pd_hi:+.4f}]). What it carries is drug exposure the arousal score misses, "
             f"which is a pharmacological finding and not a second dimension of state.")
    else:
        v = (f"**THE SECOND AXIS CARRIES BEHAVIOURAL INFORMATION INDEPENDENT OF AROUSAL.** "
             f"partial(comp2, n_correct | comp1) = {p:+.4f} [{p_lo:+.4f}, {p_hi:+.4f}], surviving "
             f"additional control for plasma propofol ({pd_:+.4f} [{pd_lo:+.4f}, {pd_hi:+.4f}]) and "
             f"outside its within-subject placebo. The feature groups and their signs came from E116 on a "
             f"DIFFERENT deposit and a different state set, so this is an out-of-sample transfer. "
             f"**SCOPE: n_correct_of_40 is behavioural RESPONSIVENESS, not experience -- an unresponsive "
             f"person may be conscious -- and nothing here detects or measures consciousness.**")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
