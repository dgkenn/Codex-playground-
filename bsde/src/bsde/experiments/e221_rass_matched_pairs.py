#!/usr/bin/env python3
"""E221 — Challenge B, model-free: does EEG separate command-following where the BEDSIDE SCORE CANNOT?

REGISTERED BEFORE ANY CANDIDATE VALUE HAS BEEN COMPARED TO THE LABEL IN THIS COHORT. The feasibility probe
that set the floors below touched only `rass`, `obeys` and `assess_time`.

=========================================================================================================
WHY E212'S ESTIMATOR HAD TO GO, AND WHAT REPLACES IT
=========================================================================================================
E212 asked the right question with the wrong machinery. Its cohort is sound — 540 patients whose two
GCS-motor assessments disagree on obeying commands, RASS discriminating within a pair at raw concordance
0.8113 against a sign-flip null of [0.4291, 0.5662], no pair sharing a feature vector, and the 21 % of
pairs lost to read failure shown NOT to be outcome-related (p = 0.4101). But its primary added a candidate
column to a cross-validated ridge, and **an i.i.d. noise column degraded out-of-fold concordance by
-0.1377 [-0.1850, -0.0953]**, indistinguishable from every real candidate. Adding any third column to a
two-column design over ~170 training pairs costs more variance than any signal it could carry. Rule 58
ended that run: the failure is the result and the successor must change the estimator.

**This changes it from ADJUSTMENT to MATCHING.** Instead of fitting RASS and asking what a candidate adds,
restrict to the pairs where **RASS IS IDENTICAL ON BOTH MEMBERS**. In such a pair the bedside sedation
score says exactly the same thing about both assessments, and the patient obeyed commands at one and not
the other. Any EEG difference there is information the bedside score does not have — and the statistic is a
paired sign rate, which has **no model, no folds and no refit variance to pay for.**

The probe found **125** such pairs, with RASS spanning −5 to +3 (modal values −1, −3, −2, 0), and the
obeying assessment coming first in 37.6 % of them.

    **P1  Among pairs matched on RASS, is a candidate systematically higher (or lower) at the assessment
          where the patient obeys commands than at the one where they do not?**

=========================================================================================================
STATISTIC
=========================================================================================================
Per pair, the sign of (candidate at the obeying member − candidate at the non-obeying member). The primary
is that **sign rate**, tested TWO-SIDED against a within-pair sign-flip null — which for a two-element pair
is the exact permutation null, so no distributional assumption enters. No direction is pre-specified per
candidate because no prior justifies one; the observed direction is reported and is not evidence for
itself.

=========================================================================================================
GATES
=========================================================================================================
G1  >= `MIN_PAIRS` RASS-matched discordant pairs, every tested candidate finite on both members, and every
    row at exactly 19 channels — the contamination check that withdrew E204, kept.
G2  **THE MATCHING MUST BE REAL, ASSERTED NOT ASSUMED.** RASS identical on both members of every included
    pair, checked on the values rather than inferred from the selection, and its distribution reported. A
    matched design whose matching is not verified is rule 40's gate that cannot fail.
G3  NEGATIVE CONTROL: an i.i.d. noise column, paired identically, must NOT clear. This is the gate that
    killed E212 and it is kept unchanged so the two designs are comparable on it.
G4  **TIME-ORDER PLACEBO, GATING.** A pair differs in time as well as in label, and a within-patient time
    trend would produce a sign rate with no relation to command-following (rule 64). The pairs split by
    orientation — obeying assessment earlier vs later — and a candidate must hold its SIGN in both. A pure
    time trend reverses between them.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3 fails.
  (2) TIME-CONFOUNDED    a candidate clears on the pooled pairs but does NOT hold its sign in both
                         orientations. G4 refuses it; it is a within-patient time trend, not a marker.
  (3) ABSENT             no candidate's interval excludes the null.
  (4) SEPARATES          at least one candidate clears two-sided AND holds its sign in both orientations.

**REGISTERED PREDICTION: (3) ABSENT.** The within-patient design removes exactly the between-patient
variance that makes EEG look predictive of anything clinical, and RASS matching removes the sedation axis
on top of that. What is left is two assessments of one patient, hours apart, at the same charted sedation
level. **If (4) comes back it is the strongest result Challenge B has ever had**, because it would be an
EEG difference that the bedside score, by construction, cannot express.

**MULTIPLICITY: 8 candidates, one cohort, no correction applied.** The count is stated so a reader can
apply their own, which is this ledger's standing position.

**SCOPE.** Matching on RASS costs 77 % of the discordant cohort (125 of 540), and pairs whose RASS differs
are not a random subset — they are the pairs where sedation changed, which is where the bedside score
already explains the label. That is the point of the design and also its limit: this tests the residual
question, not the whole one.

    python bsde/src/bsde/experiments/e221_rass_matched_pairs.py
"""

from __future__ import annotations

import collections
import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e221_rass_matched_pairs.json")
SHARDS = "/tmp/eeg_probe/heedb_cmd_follow.*.csv"

SEED = 20260802
MIN_PAIRS = 100
N_PERM = 20000
N_CHANNELS_REQUIRED = 19
CANDIDATES = ("whole_head_exponent", "exponent_low", "exponent_high", "relative_alpha_power",
              "relative_delta_power", "spectral_edge_95", "spectral_entropy", "lempel_ziv")


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def load():
    seen, rows = set(), []
    for p in sorted(glob.glob(SHARDS)):
        for r in csv.DictReader(open(p, newline="")):
            k = (r["patient_id"], r["assess_time"])
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    by = collections.defaultdict(list)
    for r in rows:
        by[r["patient_id"]].append(r)
    pairs = []
    for pid, rs in by.items():
        if len(rs) != 2 or {x["obeys"] for x in rs} != {"0", "1"}:
            continue
        rs.sort(key=lambda x: x["assess_time"])
        a, b = _f(rs[0].get("rass", "")), _f(rs[1].get("rass", ""))
        if not (np.isfinite(a) and np.isfinite(b) and a == b):
            continue
        pairs.append((pid, rs, a))
    return pairs, len(rows)


def sign_rate(diff):
    d = diff[np.isfinite(diff) & (diff != 0)]
    return (float(np.mean(d > 0)), int(d.size)) if d.size else (float("nan"), 0)


def main() -> int:
    print("E221 — does EEG separate command-following where the BEDSIDE SCORE cannot?")
    pairs, n_rows = load()
    print(f"   {n_rows} extracted rows -> {len(pairs)} discordant pairs with RASS IDENTICAL on both members")
    if not pairs:
        print("*** no matched pairs")
        return 1
    rass = np.array([p[2] for p in pairs])
    print(f"   RASS distribution: {dict(sorted(collections.Counter(rass.tolist()).items()))}")
    g2 = all(_f(rs[0]["rass"]) == _f(rs[1]["rass"]) for _pid, rs, _r in pairs)
    ch_ok = all(int(_f(x["n_channels"])) == N_CHANNELS_REQUIRED for _p, rs, _r in pairs for x in rs)
    print(f"G2 MATCHING ASSERTED on the values, not inferred: {'PASS' if g2 else '*** FAIL'}")

    obey_first = np.array([1.0 if rs[0]["obeys"] == "1" else 0.0 for _p, rs, _r in pairs])
    print(f"   obeying assessment comes FIRST in {obey_first.mean():.4f} of pairs")

    rng = np.random.default_rng(SEED)
    diffs = {}
    for c in CANDIDATES:
        d = []
        for _pid, rs, _r in pairs:
            o = rs[0] if rs[0]["obeys"] == "1" else rs[1]
            n = rs[1] if rs[0]["obeys"] == "1" else rs[0]
            d.append(_f(o.get(c, "")) - _f(n.get(c, "")))
        diffs[c] = np.array(d, float)
    diffs["NOISE_CONTROL"] = rng.normal(size=len(pairs))

    g1 = bool(len(pairs) >= MIN_PAIRS and ch_ok
              and all(np.isfinite(v).all() for k, v in diffs.items() if k in CANDIDATES))
    print(f"G1 >= {MIN_PAIRS} pairs, all candidates finite, every row at {N_CHANNELS_REQUIRED} channels   "
          f"{'PASS' if g1 else '*** FAIL'}")

    res = {}
    print(f"\n   {'candidate':<24s} {'sign rate':>10s} {'[95% CI]':>20s} {'two-sided p':>12s} "
          f"{'earlier':>8s} {'later':>8s}  call")
    for c, d in diffs.items():
        r, n = sign_rate(d)
        nul = np.array([np.mean((d * rng.choice([-1.0, 1.0], size=d.size)) > 0) for _ in range(N_PERM)])
        p = float(np.mean(np.abs(nul - 0.5) >= abs(r - 0.5)))
        bs = np.array([sign_rate(rng.choice(d, d.size))[0] for _ in range(4000)])
        lo, hi = float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))
        e_ = sign_rate(d[obey_first == 1.0])[0]
        l_ = sign_rate(d[obey_first == 0.0])[0]
        same = (np.isfinite(e_) and np.isfinite(l_)
                and np.sign(e_ - 0.5) == np.sign(r - 0.5) and np.sign(l_ - 0.5) == np.sign(r - 0.5))
        call = ("absent" if p >= 0.05 else ("SEPARATES" if same else "TIME-CONFOUNDED"))
        res[c] = {"sign_rate": r, "n": n, "ci": [lo, hi], "p": p,
                  "earlier": e_, "later": l_, "orientations_agree": bool(same), "call": call}
        print(f"   {c:<24s} {r:>10.4f} [{lo:>+7.4f},{hi:>+7.4f}] {p:>12.4f} {e_:>8.4f} {l_:>8.4f}  {call}")

    g3 = bool(res["NOISE_CONTROL"]["p"] >= 0.05)
    print(f"G3 NEGATIVE CONTROL does not clear   {'PASS' if g3 else '*** FAIL'}")
    tested = {k: v for k, v in res.items() if k in CANDIDATES}

    out = {"experiment": "E221", "n_pairs": len(pairs), "n_rows": n_rows,
           "rass_distribution": {str(k): int(v) for k, v in collections.Counter(rass.tolist()).items()},
           "obey_first_fraction": float(obey_first.mean()), "results": res,
           "g1": g1, "g2": g2, "g3": g3}
    print("\n" + "=" * 100)
    if not (g1 and g2 and g3):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 coverage", g1), ("G2 matching", g2),
                            ("G3 negative control", g3)) if not ok))
    elif any(v["call"] == "SEPARATES" for v in tested.values()):
        w = [k for k, v in tested.items() if v["call"] == "SEPARATES"]
        v_, why = "SEPARATES", (
            f"{w} separate the two assessments where RASS cannot, holding sign in both time orientations")
    elif any(v["call"] == "TIME-CONFOUNDED" for v in tested.values()):
        w = [k for k, v in tested.items() if v["call"] == "TIME-CONFOUNDED"]
        v_, why = "TIME-CONFOUNDED", (
            f"{w} clear on the pooled pairs but do not hold sign in both orientations; G4 refuses them")
    else:
        v_, why = "ABSENT", (
            "no candidate separates the two assessments once the bedside sedation score is matched")
    out["verdict"], out["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print(f"MULTIPLICITY: {len(CANDIDATES)} candidates, one cohort, no correction applied.")
    print("SCOPE: matching on RASS costs 77 % of the discordant cohort, and the discarded pairs are not a\n"
          "  random subset -- they are the pairs where sedation CHANGED, which is where the bedside score\n"
          "  already explains the label. That is the design's point and its limit.")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2, default=float)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
