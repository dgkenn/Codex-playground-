"""E110 -- E109 found a DISCORDANCE. Against an independent anchor, WHICH reading degrades with age?

REGISTERED BEFORE ANY FIDELITY STATISTIC IS COMPUTED. Existing tables only; a join probe was run first
(rule 41) and found 247 cases joinable between `vitaldb_grid*.csv` and `vitaldb_agents.csv`, of which
**100 carry >= 10 windows with MAC** (volatile) and **142 with propofol effect-site concentration** (TIVA).

=========================================================================================================
WHAT E109 LEFT OPEN, IN ITS OWN WORDS
=========================================================================================================
E109 measured that the within-case agreement between BIS and the aperiodic exponent DEGRADES with age --
+0.2592 [+0.1367, +0.3761] over 240 cases, surviving both attenuation routes and the exclusion of
paediatric cases, outside a placebo of [-0.1292, +0.1210]. Its verdict named the limit explicitly: **"THIS
IS A STATEMENT ABOUT DISCORDANCE AND NOT ABOUT WHICH READING IS CORRECT: this deposit contains no
ground-truth depth, and nothing here shows the exponent is right where BIS is not."**

Two readings disagreeing tells you nothing about which one moved. **This experiment supplies the third
measurement that can tell them apart**, and it is not an EEG measurement at all: the anaesthetic
concentration recorded by the vaporiser and the infusion pump.

=========================================================================================================
THE ESTIMAND
=========================================================================================================
Per case, within case, across windows, each reading's FIDELITY to the drug -- signed so that both are
positive when the reading tracks the drug correctly, which avoids folding a statistic and the upward bias
that comes with it (rule 46):

    fid_BIS = - spearman( meta_bis , drug )          BIS falls as drug rises
    fid_exp = + spearman( whole_head_exponent , drug )   the exponent rises as drug rises

    delta_c = fid_exp - fid_BIS

    P  spearman( delta_c , age ) across cases, in EACH ARM SEPARATELY, case bootstrap, 4000 reps.

TWO ARMS, AND THEY ARE THE INTERNAL REPLICATION. `mac` for volatile cases and `ppf_ce` for TIVA cases are
different drugs, different delivery, different pharmacokinetics and largely different patients. **A result
that appears in one arm and not the other is not a result about age.** The conjunction rule is fixed here:

VERDICT, wrong direction FIRST (rule 37) -- and the wrong direction is the one against the project's own
interest, so it is named first for that reason:

    (a) both arms NEGATIVE with at least one interval excluding 0 -> THE EXPONENT IS THE ONE DEGRADING.
        E109's discordance is our measure failing in older patients, not BIS. This would make the
        self-computed index LESS usable with age and must print as that.
    (b) arms point in OPPOSITE directions with both intervals excluding 0 -> CONTRADICTORY. The effect is
        drug-class-specific and not an age effect; withdrawn.
    (c) neither interval excludes 0 -> NO ATTRIBUTION. E109's discordance stands and this experiment does
        not say which reading moved. A clean and expected outcome, not a disappointment.
    (d) both arms POSITIVE, exactly one interval excluding 0 -> PARTIAL. Reported as suggestive and
        explicitly NOT as an attribution.
    (e) both arms POSITIVE with BOTH intervals excluding 0 -> BIS IS THE ONE DEGRADING, replicated across
        two independent drug classes.

PREDICTED: (c) at ~40 %, (e) at ~25 %, (d) at ~25 %, (a) at ~8 %, (b) at ~2 %.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 50 cases per arm with >= 10 windows and drug, BIS and exponent each varying within
        case (rule 32).
    G2  THE ANCHOR MUST BE ALIVE, and BOTH readings must be alive against it (the E33/E61 rule). Median
        `fid_BIS` and median `fid_exp` must each be positive in each arm. **If only one reading tracks the
        drug, `delta_c` is a comparison between a live measure and a dead one rather than a comparison of
        two fidelities, and the verdict must say so instead of reporting a difference.**
    G3  ATTENUATION, carried from E109 where it was the whole methodological risk. The primary is re-run
        as a partial given the within-case SD of the drug, of BIS and of the exponent, plus
        `log(n_windows)`. All four routes attenuate a within-case correlation toward zero, and if any of
        them tracks age the difference statistic moves for a purely statistical reason. Failure withdraws.
    G4  AGE SPAN. Each arm must span a real age range; an arm confined to one decade cannot measure an age
        gradient no matter how many cases it holds.

**THE CONFOUND THAT CANNOT BE ADJUSTED AWAY, AND WHICH DIRECTION IT PUSHES.** Anaesthetic dosing is partly
BIS-GUIDED: the anaesthetist sees the number and turns the dial. That feedback loop inflates
`spearman(BIS, drug)` -- BIS looks like a better predictor of the drug because the drug was partly set by
BIS. There is no way to remove it from this deposit, and conditioning on anything downstream of it would
be a collider (rule 13). **It biases AGAINST outcome (e) and in favour of (a)**, so a finding that BIS
degrades with age is CONSERVATIVE under it, while a finding that the exponent degrades is not and would
need this raised immediately. Written here, before the result, so it cannot be selected afterwards
(rule 54: a confound named in the registration is not thereby controlled -- this one is named precisely
because it CANNOT be, and the direction is what makes the naming useful).

PLACEBO: age shuffled across cases within arm, 2000 draws. Primary read FIRST (rule 48).

SCOPE. VitalDB, single-channel BIS-module EEG. "Fidelity" is a within-case rank correlation with a
recorded drug concentration and is not an accuracy against depth of anaesthesia -- drug concentration is
an exposure, not a state. Nothing here concerns consciousness.
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e110_which_reading_degrades.json")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
TABLES = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
    glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))

ARMS = (("volatile", "mac"), ("tiva", "ppf_ce"))
MIN_WINDOWS, MIN_CASES = 10, 50
MIN_AGE_SPAN = 30.0
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


def build():
    """case -> list of (bis, exponent, drug_mac, drug_ppf, age)."""
    ag = defaultdict(dict)
    for r in csv.DictReader(open(AGENTS, newline="")):
        t = _f(r.get("t_s"))
        if math.isfinite(t):
            ag[r["caseid"]][round(t, 1)] = r
    per = defaultdict(list)
    seen = set()
    for tb in TABLES:
        if not os.path.exists(tb):
            continue
        for r in csv.DictReader(open(tb, newline="")):
            c, t = r.get("meta_caseid"), _f(r.get("meta_t_s"))
            if not c or not math.isfinite(t):
                continue
            key = (c, round(t, 1))
            if key in seen:
                continue
            seen.add(key)
            a = ag.get(c, {}).get(round(t, 1))
            if a is None:
                continue
            b, e, age = _f(r.get("meta_bis")), _f(r.get("whole_head_exponent")), _f(r.get("meta_age"))
            if not (math.isfinite(b) and b > 0 and math.isfinite(e) and math.isfinite(age)):
                continue
            per[c].append((b, e, _f(a.get("mac")), _f(a.get("ppf_ce")), age))
    return per


def arm_stats(per, col):
    """Per case: fid_BIS, fid_exp, delta, age, and the attenuation covariates."""
    out = []
    for c, v in per.items():
        arr = np.array(v, float)
        b, e, age = arr[:, 0], arr[:, 1], arr[0, 4]
        d = arr[:, col]
        ok = np.isfinite(d) & (d > 0) & np.isfinite(b) & np.isfinite(e)
        if ok.sum() < MIN_WINDOWS:
            continue
        b, e, d = b[ok], e[ok], d[ok]
        if np.ptp(b) <= 0 or np.ptp(e) <= 0 or np.ptp(d) <= 0:
            continue
        fb, fe = -spearman(b, d), spearman(e, d)
        if not (np.isfinite(fb) and np.isfinite(fe)):
            continue
        out.append({"case": c, "fid_bis": fb, "fid_exp": fe, "delta": fe - fb, "age": age,
                    "sd_drug": float(d.std()), "sd_bis": float(b.std()), "sd_exp": float(e.std()),
                    "n": int(ok.sum())})
    return out


def main() -> int:
    if not os.path.exists(AGENTS) or not any(os.path.exists(t) for t in TABLES):
        print("ABSENT: missing vitaldb_agents.csv or vitaldb_grid table")
        return 2
    per = build()
    res = {"n_cases_joined": len(per), "arms": {}}
    print(f"{len(per)} cases joined between the grid and the agent tracks")

    rng = np.random.default_rng(SEED)
    verdicts = {}
    for name, col_name in ARMS:
        col = 2 if col_name == "mac" else 3
        rows = arm_stats(per, col)
        n = len(rows)
        delta = np.array([r["delta"] for r in rows])
        age = np.array([r["age"] for r in rows])
        fb = np.array([r["fid_bis"] for r in rows])
        fe = np.array([r["fid_exp"] for r in rows])
        A = {"n_cases": n, "drug": col_name}
        print(f"\n=== ARM {name} (drug = {col_name}) : {n} cases ===")
        A["G1_pass"] = bool(n >= MIN_CASES)
        print(f"G1 coverage   {n} >= {MIN_CASES}  {'PASS' if A['G1_pass'] else 'FAIL'}")
        if n < 10:
            res["arms"][name] = A
            verdicts[name] = None
            continue
        A["G2_median_fid_bis"] = float(np.median(fb))
        A["G2_median_fid_exp"] = float(np.median(fe))
        A["G2_pass"] = bool(np.median(fb) > 0 and np.median(fe) > 0)
        print(f"G2 anchor     median fidelity  BIS {np.median(fb):+.4f}   exponent "
              f"{np.median(fe):+.4f}   {'PASS' if A['G2_pass'] else 'FAIL -- one reading is dead'}")
        span = float(np.ptp(age))
        A["G4_age_span"] = span
        A["G4_pass"] = bool(span >= MIN_AGE_SPAN)
        print(f"G4 age span   {span:.1f} years  {'PASS' if A['G4_pass'] else 'FAIL'}")

        point = spearman(delta, age)
        lo, hi = ci([spearman(delta[i], age[i]) for i in (rng.integers(0, n, n) for _ in range(REPS))])
        A["primary"] = {"rho": point, "lo": lo, "hi": hi}
        print(f"P  spearman(delta = fid_exp - fid_BIS, age) = {point:+.4f} [{lo:+.4f}, {hi:+.4f}]")
        print("   (POSITIVE = the exponent's advantage grows with age, i.e. BIS is the one degrading)")

        Z = np.column_stack([[r["sd_drug"] for r in rows], [r["sd_bis"] for r in rows],
                             [r["sd_exp"] for r in rows], np.log([r["n"] for r in rows])])
        pr = partial_spearman(delta, age, Z)
        pr_lo, pr_hi = ci([partial_spearman(delta[i], age[i], Z[i])
                           for i in (rng.integers(0, n, n) for _ in range(REPS))])
        A["G3"] = {"partial": pr, "lo": pr_lo, "hi": pr_hi,
                   "pass": bool(np.isfinite(pr_lo) and (pr * point) > 0
                                and not (pr_lo <= 0.0 <= pr_hi))}
        print(f"G3 attenuation  partial given 3 spreads and log n: {pr:+.4f} [{pr_lo:+.4f}, {pr_hi:+.4f}]"
              f"  {'survives' if A['G3']['pass'] else 'DOES NOT SURVIVE'}")

        pl = [spearman(delta, age[rng.permutation(n)]) for _ in range(PLACEBO_DRAWS)]
        p_lo, p_hi = ci(pl)
        inside = bool(np.isfinite(p_lo) and p_lo <= point <= p_hi)
        A["placebo"] = {"lo": p_lo, "hi": p_hi, "inside": inside}
        print(f"PLACEBO age shuffled: [{p_lo:+.4f}, {p_hi:+.4f}]  "
              f"real {'INSIDE' if inside else 'outside'}")

        interval_excludes = bool(np.isfinite(lo) and not (lo <= 0.0 <= hi) and not inside)
        gates_ok = bool(A["G1_pass"] and A["G2_pass"] and A["G4_pass"] and A["G3"]["pass"])
        A["interval_excludes_zero"] = interval_excludes
        A["gates_ok"] = gates_ok
        verdicts[name] = (point, interval_excludes and gates_ok, interval_excludes, gates_ok,
                          A["G2_pass"])
        res["arms"][name] = A

    vals = [v for v in verdicts.values() if v is not None]
    # a gate failure and an interval containing zero are DIFFERENT reasons and must print differently
    dead = [n for n, v in verdicts.items() if v is not None and not v[4]]
    blocked = [n for n, v in verdicts.items()
               if v is not None and v[2] and not v[1]]        # interval excluded 0 but gates failed
    if len(vals) < 2:
        v = "ABSENT -- fewer than two usable arms, so the internal replication is not available."
    else:
        signs = [np.sign(p) for p, _, _, _, _ in vals]
        excls = [e for _, e, _, _, _ in vals]
        if all(excls) and signs[0] != signs[1]:
            v = ("CONTRADICTORY -- the two drug classes point in OPPOSITE directions with both intervals "
                 "excluding zero, so this is drug-class-specific and not an age effect. Withdrawn.")
        elif all(s < 0 for s in signs) and any(excls):
            v = ("THE EXPONENT IS THE ONE DEGRADING -- E109's discordance is our measure failing in older "
                 "patients, not BIS. The self-computed index becomes LESS usable with age. NOTE: the "
                 "BIS-guided-dosing feedback loop biases TOWARD this outcome and cannot be adjusted away, "
                 "so it must be raised immediately with this result.")
        elif all(s > 0 for s in signs) and all(excls):
            v = ("BIS IS THE ONE DEGRADING, replicated across two independent drug classes. Against an "
                 "anchor recorded by the vaporiser and the infusion pump -- not by the EEG -- the "
                 "exponent's fidelity advantage over BIS grows with patient age. The BIS-guided-dosing "
                 "feedback loop biases AGAINST this outcome, so it is conservative under the one confound "
                 "that cannot be removed.")
        elif all(s > 0 for s in signs) and any(excls):
            v = ("PARTIAL -- both arms point the same way but only one interval excludes zero. Suggestive "
                 "and explicitly NOT an attribution; the conjunction rule was fixed before the run.")
        elif blocked:
            v = (f"NO ATTRIBUTION, AND THE REASON IS A GATE, NOT A NULL. The {', '.join(blocked)} arm's "
                 f"interval DOES exclude zero, but its gates failed, so the estimate is not "
                 f"interpretable as an attribution (rule 31).")
        else:
            v = ("NO ATTRIBUTION -- no arm's interval excludes zero with its gates intact. E109's "
                 "discordance STANDS and this experiment does not say which reading moved. Named in "
                 "advance as the most likely outcome. The placebo is not informative here (rule 48).")
    if dead:
        v += (" | **SUBSTANTIVE FINDING FROM G2, and it is larger than the primary**: in the "
              + ", ".join(dead) + " arm the APERIODIC EXPONENT DOES NOT TRACK THE DRUG AT ALL "
              + "(median fidelity "
              + ", ".join(f"{res['arms'][n]['G2_median_fid_exp']:+.4f}" for n in dead)
              + f") while BIS does ("
              + ", ".join(f"{res['arms'][n]['G2_median_fid_bis']:+.4f}" for n in dead)
              + "). A difference of fidelities between a live reading and a dead one is not a comparison "
                "of two readings, which is why the gate refuses it -- but the dead reading is itself the "
                "result and must be reported as one.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
