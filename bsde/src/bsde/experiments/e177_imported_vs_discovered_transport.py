#!/usr/bin/env python3
"""E177 — the FORWARD test of the transport rule that replaced the one E160 refuted.

REGISTERED BEFORE ANY CORRELATION IN THIS FILE HAS BEEN COMPUTED.

=========================================================================================================
WHY THIS EXISTS, AND WHY IT HAS TO BE FORWARD
=========================================================================================================
`PROGRAMME_ROADMAP.md` used to assert: *"transport succeeds when the construct matches and fails when it
does not, and construct match is specifiable in advance."* `CHALLENGE_D_PREREGISTRATION.md` committed that
prediction forward, and **E160/E162 refuted it** — a pharmacokinetic ladder built for bolus propofol in
day-case endoscopy transports essentially intact to multi-drug infusion in ICU patients over days.

Sorting the same observations by outcome gave a different split, recorded in the roadmap as a
RETRODICTION over five observations and explicitly not citable:

| transported | did not transport |
|---|---|
| the DOSE-I exposure ladder to MIMIC-IV (E160, E162) | `ge_norm` / `iaf`, Stieger to eegmmidb and Dreyer (E124, E125, E131) |
| Blankertz 2010's SMR predictor, eegmmidb to Dreyer (E129) | E43's muscle association across montages (E123) |
| | per-patient PK parameters (cross-patient MDAPE 54.9 %) |

**Both survivors were specified OUTSIDE the cohort they were then tested in; every failure was selected
inside its own.** That is winner's curse, not construct mismatch. `CLAUDE.md`'s cadence section is explicit
that a retrodiction is worth little until it makes a falsifiable forward prediction, and the programme has
now been burned once by promoting exactly this kind of pattern. **So it gets one prediction, in advance,
on a cell nobody has looked at.**

=========================================================================================================
THE PREDICTION, WRITTEN BEFORE THE RUN
=========================================================================================================
On eegmmidb — 104 subjects, held fixed for all three arms, same rows, same estimator, same gates:

    IMPORTED     `alpha_prom`, the sensorimotor-rhythm amplitude predictor from Blankertz et al. 2010,
                 specified on a different cohort entirely and replicated by E129 on Dreyer's 87 subjects.
                 **PREDICTED TO CARRY.**
    DISCOVERED   `ge_norm` and `iaf`, both selected INSIDE Stieger by E86 and E106.
                 **PREDICTED NOT TO CARRY.**

`ge_norm` in eegmmidb is already known negative (E124), so it contributes retrodiction, not evidence.
**The forward content of this file is `alpha_prom`**, which has never been scored on this deposit: E129
tested it on Dreyer, E131 on Stieger. That single cell is what the rule stakes itself on, and the
head-to-head on identical rows and one estimator is new for all three.

DIRECTIONS ARE DECLARED IN ADVANCE AND ONE-SIDED, because every one of these measures has a published or
recorded sign. Blankertz 2010: a LARGER resting sensorimotor rhythm goes with BETTER BCI control. E86 and
E106 on Stieger: HIGHER `ge_norm` and HIGHER `iaf` with better control. A result in the opposite direction
is not a partial success and is enumerated separately.

=========================================================================================================
THE LABEL, AND THE GATE THAT DECIDES WHETHER ANY OF THIS MEANS ANYTHING
=========================================================================================================
Two labels ship with this deposit and they are NOT interchangeable. `imagery_auc` is a band-power decoder;
`csp_auc` is the CSP decoder E124 built specifically because the first one was too weak to support a
conclusion. Both are scored, and **the primary is whichever clears G1** — declared this way in advance
rather than chosen afterwards, with the rule being: if both clear, the CSP label is primary because E124
established it; if only one clears, that one; if neither, the file reports ABSENT.

G1  **THE LABEL MUST BE ALIVE (rule 53 / E33 / E61).** Its across-subject spread must exceed what its own
    per-subject permutation null produces — a label whose between-subject variance is all estimation noise
    cannot be predicted by anything, and a null against it would be uninterpretable rather than negative.
    Measured as: the observed variance of the label across subjects against the variance expected from the
    per-subject permutation nulls the deposit already ships (`perm_null_mean`, `n_trials`).
G2  **COVERAGE**: >= 60 subjects with a graph row, a label row and a finite value for all three measures.
G3  **THE NULL IS MEASURED, NOT ASSUMED**: every p-value comes from permuting the label across SUBJECTS,
    2,000 draws, and the same machinery scores all three arms so no arm gets a different test.

=========================================================================================================
VERDICT — THE REFUTING AND UNINFORMATIVE CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1 or G2 fails. No arm is read.
  (2) REFUTED            a DISCOVERED measure carries and the IMPORTED one does not. The winner's-curse
                         reading is wrong and must be struck from the roadmap, which is where it currently
                         sits labelled as not-yet-citable.
  (3) BOTH CARRY         no discrimination: origin does not predict transport here.
  (4) NEITHER CARRIES    the imported measure fails too. The rule survives only in the weak sense that its
                         negative half held, and its positive half is unsupported — reported as a failure
                         of the prediction, because "carries" was predicted and did not happen.
  (5) SUPPORTED          `alpha_prom` carries in its published direction and neither Stieger-discovered
                         measure does. One forward success; the rule may then be cited ONCE, with the
                         count of forward tests attached.

**No branch here promotes the rule to a finding.** Five retrodictions and one forward success is one
forward success, and the file says so in its own output.

    python bsde/src/bsde/experiments/e177_imported_vs_discovered_transport.py
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

from bsde.verifier.stats import spearman                                        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e177_imported_vs_discovered_transport.json")
SEED = 20260801

GRAPH = os.path.join(RESULTS, "eegmmidb_graph.csv")
LABELS = {"csp_auc": os.path.join(RESULTS, "eegmmidb_csp_label.csv"),
          "imagery_auc": os.path.join(RESULTS, "eegmmidb_bci.csv")}

ARMS = {
    "alpha_prom": {"origin": "IMPORTED", "direction": +1,
                   "source": "Blankertz et al. 2010; replicated by E129 on Dreyer's 87 subjects"},
    "ge_norm": {"origin": "DISCOVERED", "direction": +1,
                "source": "selected inside Stieger by E86; already negative here at E124"},
    "iaf": {"origin": "DISCOVERED", "direction": +1,
            "source": "selected inside Stieger by E106"},
}
PRIMARY_ARM = "alpha_prom"
MIN_SUBJECTS = 60
PERMS = 2000
ALPHA = 0.05


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    per = defaultdict(list)
    for r in csv.DictReader(open(GRAPH, newline="")):
        if r.get("status") != "ok":
            continue
        per[r["subject"]].append(r)
    feats = {}
    for s, rs in per.items():
        d = {}
        for c in ARMS:
            v = [_f(r.get(c, "")) for r in rs]
            v = [x for x in v if math.isfinite(x)]
            d[c] = float(np.median(v)) if v else float("nan")
        feats[s] = d
    labels = {}
    for name, path in LABELS.items():
        if not os.path.exists(path):
            continue
        col = {}
        for r in csv.DictReader(open(path, newline="")):
            if r.get("status") != "ok":
                continue
            col[r["subject"]] = {"y": _f(r.get(name, "")),
                                 "null_mean": _f(r.get("perm_null_mean", "")),
                                 "n_trials": _f(r.get("n_trials", ""))}
        labels[name] = col
    return feats, labels


def label_alive(col):
    """Is the label's between-subject spread bigger than per-subject estimation noise?

    A per-subject AUC over `n` trials has a null sd of roughly sqrt((n+1)/(12 * n1 * n0)) under
    exchangeability; with a balanced split that is about sqrt(1/(3n)). If the observed across-subject
    variance does not exceed that, the label is noise and nothing can predict it (rule 53).
    """
    ys = np.asarray([v["y"] for v in col.values() if math.isfinite(v["y"])], float)
    ns = np.asarray([v["n_trials"] for v in col.values() if math.isfinite(v["y"])], float)
    if ys.size < 10:
        return {"n": int(ys.size), "pass": False, "why": "too few subjects"}
    noise_var = float(np.mean(1.0 / (3.0 * np.clip(ns, 4, None))))
    obs_var = float(np.var(ys, ddof=1))
    ratio = obs_var / noise_var if noise_var > 0 else float("nan")
    return {"n": int(ys.size), "observed_var": obs_var, "noise_var": noise_var,
            "ratio": ratio, "mean": float(ys.mean()), "sd": float(ys.std(ddof=1)),
            "pass": bool(np.isfinite(ratio) and ratio > 1.5),
            "why": "observed between-subject variance must exceed 1.5x per-subject estimation noise"}


def score(x, y, direction, rng, reps=PERMS):
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < MIN_SUBJECTS:
        return {"n": int(ok.sum()), "rho": float("nan"), "p": float("nan")}
    r = spearman(list(x[ok]), list(y[ok]))
    nulls = []
    for _ in range(reps):
        v = spearman(list(x[ok]), list(rng.permutation(y[ok])))
        if math.isfinite(v):
            nulls.append(v)
    n = np.asarray(nulls)
    p = float((n >= r).mean()) if direction > 0 else float((n <= r).mean())
    return {"n": int(ok.sum()), "rho": float(r), "p_one_sided": p,
            "null_p95": float(np.quantile(n, 0.95)), "null_p05": float(np.quantile(n, 0.05))}


def main() -> int:
    print("E177 — forward test: does an IMPORTED predictor transport where DISCOVERED ones do not?")
    feats, labels = load()
    res = {"experiment": "E177", "arms": {a: ARMS[a] for a in ARMS}, "n_feature_subjects": len(feats)}
    if not feats or not labels:
        print("ABSENT — the graph table or a label table is missing.")
        json.dump(res, open(OUT, "w"), indent=2)
        return 2

    print("\nG1 LABEL ALIVENESS")
    alive = {}
    for name, col in labels.items():
        a = label_alive(col)
        alive[name] = a
        print(f"   {name:<12s} n={a['n']:<4d} sd {a.get('sd', float('nan')):.4f}  "
              f"observed var {a.get('observed_var', float('nan')):.5f} vs estimation noise "
              f"{a.get('noise_var', float('nan')):.5f}  ratio {a.get('ratio', float('nan')):.2f}   "
              f"{'PASS' if a['pass'] else '*** FAIL'}")
    res["G1"] = alive
    live = [n for n in ("csp_auc", "imagery_auc") if alive.get(n, {}).get("pass")]
    if not live:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = ("neither label's between-subject spread exceeds per-subject estimation noise; "
                      "there is nothing for any predictor to predict (rule 53)")
        print("\nVERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1
    primary_label = "csp_auc" if "csp_auc" in live else live[0]
    print(f"   primary label: {primary_label} (declared rule: CSP if it clears, else whichever does)")
    res["primary_label"] = primary_label

    res["results"] = {}
    for name in live:
        col = labels[name]
        subs = sorted(set(feats) & set(col))
        y = np.asarray([col[s]["y"] for s in subs], float)
        block = {}
        print(f"\n   --- label {name}: {len(subs)} subjects with both a graph row and a label")
        print(f"   {'measure':<12s} {'origin':<11s} {'n':>4s} {'rho':>8s} {'p(1-sided)':>11s} "
              f"{'null p95':>9s}  carries?")
        for a, meta in ARMS.items():
            x = np.asarray([feats[s][a] for s in subs], float)
            r = score(x, y, meta["direction"], np.random.default_rng(SEED + hash(a) % 1000))
            carries = bool(np.isfinite(r.get("p_one_sided", np.nan))
                           and r["p_one_sided"] <= ALPHA)
            r["carries"] = carries
            r["origin"] = meta["origin"]
            block[a] = r
            print(f"   {a:<12s} {meta['origin']:<11s} {r['n']:>4d} {r['rho']:>+8.4f} "
                  f"{r.get('p_one_sided', float('nan')):>11.4f} "
                  f"{r.get('null_p95', float('nan')):>+9.4f}  {'YES' if carries else 'no'}")
        res["results"][name] = block

    prim = res["results"][primary_label]
    imported = prim[PRIMARY_ARM]["carries"]
    discovered = [a for a, m in ARMS.items() if m["origin"] == "DISCOVERED" and prim[a]["carries"]]
    n_missing = sum(1 for a in ARMS if prim[a]["n"] < MIN_SUBJECTS)
    if n_missing:
        v, why = "NOT-INTERPRETABLE", f"{n_missing} arm(s) fall below {MIN_SUBJECTS} joined subjects"
    elif discovered and not imported:
        v, why = "REFUTED", (f"the Stieger-discovered {discovered} carry here and the imported "
                             f"{PRIMARY_ARM} does not: origin does not predict transport, and the "
                             "winner's-curse reading must be struck from PROGRAMME_ROADMAP.md")
    elif imported and discovered:
        v, why = "BOTH-CARRY", ("origin does not discriminate on this cohort pair; the rule makes no "
                                "useful prediction here")
    elif not imported and not discovered:
        v, why = "NEITHER-CARRIES", (f"{PRIMARY_ARM} was PREDICTED to carry and does not, so the "
                                     "prediction failed; only the rule's negative half held, which the "
                                     "existing retrodictions already supplied")
    else:
        v, why = "SUPPORTED", (f"{PRIMARY_ARM} carries in Blankertz's published direction and neither "
                               "Stieger-discovered measure does. This is ONE forward success against five "
                               "retrodictions, and the rule may be cited only with that count attached")
    res["verdict"], res["why"] = v, why
    res["forward_tests_so_far"] = 1
    print(f"\nVERDICT {v} — {why}")
    print("   forward tests of this rule to date: 1")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
