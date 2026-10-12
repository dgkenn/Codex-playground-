#!/usr/bin/env python3
"""E219 — do Challenge C's survivors replicate on capslpdb, a cohort whose incumbent was probed FIRST?

REGISTERED AFTER A RULE-41 FEASIBILITY PROBE AND BEFORE ANY CANDIDATE WAS CORRELATED WITH THE LABEL.

=========================================================================================================
WHY THIS DEPOSIT, AND WHY THE PROBE CAME FIRST
=========================================================================================================
Challenge C has lost two candidate replication cohorts this session, both to the same gate:

    chennu     E208 died on it (incumbent out-of-fold rho +0.0349 against a permutation p95 of +0.1511)
               and E217 independently found **0 of 16** features in the shared panel detect its own
               sedation contrast. Two estimands, one answer.
    ds004541   refused by a probe BEFORE anything was spent: the declared incumbent predicts that
               deposit's own depth label at Spearman -0.0170 against a within-subject permutation p95 of
               0.1561. No candidate column was ever correlated there, so it stays clean.

capslpdb was probed the same way, first, touching only the incumbent:

    **Spearman(spectral_edge_95, ordered sleep stage) = -0.6644**, against a WITHIN-RECORD stage
    permutation p95 of **0.1009** over 86 records and 344 record-stage points. A 6.6-fold margin.

The incumbent is not merely alive here, it is the strongest it has been on any deposit in this programme.

    **P1  Do the DOSE-I survivors add to that incumbent on a fifth deposit -- a clinical sleep cohort of
          108 subjects across eight diagnostic groups, none of them in any previous analysis?**

=========================================================================================================
WHAT CAN AND CANNOT BE TESTED HERE (rule 14 — scope stated before the run)
=========================================================================================================
Of the five DOSE-I survivors, **two are testable**: `whole_head_exponent` and `relative_alpha_power`.
`wpli_theta` and `pac_slow_alpha` are not in this deposit's panel at all, and `multiscale_entropy_slope`
was deliberately left out of the extraction: measured on one real 13-channel 512 Hz epoch from this
deposit it costs 14.42 s against 0.08 s for the aperiodic exponent, **88 % of the whole panel**, and the
extractor records that. It is available behind a second pass and is not in this one.

**THE PREDICTION IS INHERITED FROM E209 AND IS GENUINELY FORWARD.** On ds005620, `whole_head_exponent`
replicated (+0.2133 [+0.0976, +0.3363]) and `relative_alpha_power` did NOT (+0.0978 [-0.0405, +0.2334]).
The same split is predicted here. That is falsifiable in both directions and was written before either
candidate touched this deposit's label.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 40 records carrying all four ladder levels AND a positive alignment control, every tested candidate
    finite.
G2  THE INCUMBENT MUST BE ALIVE (rule 53) — recomputed here, not taken from the probe.
G3  NEGATIVE CONTROL: an i.i.d. noise column must NOT add.
G4  DIRECTION FIXED IN ADVANCE: replication means a POSITIVE increment. Clearing on the wrong side is
    REVERSED and is never support (rule 37).

**THE ALIGNMENT CONTROL IS A GATE, NOT AN ASSUMPTION.** The scoring is wall-clock text and the signal is
an EDF with its own start time. Records whose delta-in-deep-sleep control is non-positive are excluded and
counted — 20 of 106 here — because a scrambled alignment would scramble the label.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails.
  (2) REVERSED            a candidate's interval excludes zero on the NEGATIVE side. Never support.
  (3) ABSENT              every interval includes zero.
  (4) PARTIAL             some replicate and some do not.
  (5) BOTH REPLICATE      every tested candidate's interval excludes zero on the positive side.

**REGISTERED PREDICTION: (4) PARTIAL — `whole_head_exponent` replicates and `relative_alpha_power` does
not**, inherited from E209. **If `relative_alpha_power` replicates here it is the more interesting
outcome**, because this session has spent four experiments on why that measure is unstable and a clean
replication on a fifth deposit would constrain every one of them.

**SCOPE.** The label is a sleep ladder, not sedation, so this replicates the CANDIDATES rather than the
exact estimand — the same caveat E209 carries. The montage is clinical bipolar PSG, and E215 has just shown
that the aperiodic exponent's percentile COORDINATE does not transport to this deposit; that is a different
quantity from the raw feature's association with stage, which is what is tested here, but it is a reason
for caution about the exponent specifically.

    python bsde/src/bsde/experiments/e219_capslpdb_replication.py
"""

from __future__ import annotations

import collections
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import spearman, read_rows, grouped_cv_predict        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e219_capslpdb_replication.json")
SHARDS = os.path.join(RESULTS, "capslpdb_stages.s*.csv")

SEED = 20260802
LADDER = {"W": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 3}
INCUMBENT = "spectral_edge_95"
CANDIDATES = ("whole_head_exponent", "relative_alpha_power")
ABSENT_FROM_PANEL = ("wpli_theta", "pac_slow_alpha", "multiscale_entropy_slope")
MIN_RECORDS = 40
N_BOOT = 2000
N_PERM = 2000


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def load():
    seen, rows, dropped = set(), [], 0
    for p in sorted(glob.glob(SHARDS)):
        r, d = read_rows(p)
        dropped += d
        for x in r:
            k = (x.get("record"), x.get("stage"))
            if not x.get("stage") or k in seen:
                continue
            seen.add(k)
            rows.append(x)
    by = collections.defaultdict(dict)
    ctrl = {}
    for x in rows:
        if x["stage"] not in LADDER:
            continue
        lv = LADDER[x["stage"]]
        by[x["record"]].setdefault(lv, []).append(x)
        ctrl[x["record"]] = _f(x.get("delta_ratio_deep_minus_wake", ""))
    good = [r for r in by if ctrl.get(r, float("nan")) > 0 and set(by[r]) >= {0, 1, 2, 3}]
    cols = [INCUMBENT, *CANDIDATES]
    lab, rec, X = [], [], []
    for r in sorted(good):
        for lv, xs in sorted(by[r].items()):
            v = [np.nanmean([_f(x.get(c, "")) for x in xs]) for c in cols]
            if not all(np.isfinite(v)):
                continue
            lab.append(float(lv))
            rec.append(r)
            X.append(v)
    return (np.array(X, float), np.array(lab, float), np.array(rec),
            len(by), len(good), dropped, cols)


def increment(X, y, rec, base_idx, add_idx, seed):
    r0 = np.random.default_rng(seed)
    a = spearman(list(grouped_cv_predict(X[:, base_idx], y, rec, r0)), list(y))
    r1 = np.random.default_rng(seed)
    b = spearman(list(grouped_cv_predict(X[:, base_idx + add_idx], y, rec, r1)), list(y))
    return b - a


def main() -> int:
    print("E219 — do Challenge C's survivors replicate on capslpdb?")
    X, y, rec, n_all, n_good, dropped_hdr, cols = load()
    recs = sorted(set(rec.tolist()))
    print(f"   {n_all} records with stages, {n_good} passing the alignment control AND carrying all four "
          f"ladder levels, {len(recs)} usable")
    print(f"   {X.shape[0]} record-stage points; {dropped_hdr} shard-header artefact rows dropped")
    print(f"   NOT TESTABLE on this deposit's panel: {', '.join(ABSENT_FROM_PANEL)}")
    g1 = bool(len(recs) >= MIN_RECORDS and np.isfinite(X).all())
    print(f"G1 COVERAGE >= {MIN_RECORDS} records   {'PASS' if g1 else '*** FAIL'}")

    rho = spearman(list(X[:, 0]), list(y))
    rng = np.random.default_rng(SEED)
    nul = []
    for _ in range(N_PERM):
        p = y.copy()
        for s in recs:
            m = rec == s
            p[m] = rng.permutation(p[m])
        nul.append(abs(spearman(list(X[:, 0]), list(p))))
    p95 = float(np.quantile(nul, 0.95))
    g2 = bool(abs(rho) > p95)
    print(f"G2 INCUMBENT ALIVE  {INCUMBENT} rho {rho:+.4f} vs within-record permutation p95 {p95:.4f}   "
          f"{'PASS' if g2 else '*** FAIL'}")

    noise = rng.normal(size=(X.shape[0], 1))
    Xn = np.column_stack([X, noise])
    res, calls = {}, {}
    print(f"\n   {'candidate':<24s} {'increment':>10s} {'[95% CI]':>24s}  call")
    for k, name in enumerate([*CANDIDATES, "NOISE_CONTROL"]):
        add = [1 + k] if name != "NOISE_CONTROL" else [Xn.shape[1] - 1]
        d = increment(Xn, y, rec, [0], add, SEED + 1)
        boot = []
        for b in range(N_BOOT):
            g = np.random.default_rng(SEED + 700 + b)
            pick = np.concatenate([np.flatnonzero(rec == s)
                                   for s in g.choice(recs, size=len(recs), replace=True)])
            try:
                boot.append(increment(Xn[pick], y[pick], rec[pick], [0], add, SEED + 1))
            except Exception:
                pass
        boot = np.array([x for x in boot if np.isfinite(x)])
        lo, hi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
        call = "REPLICATES" if lo > 0 else ("REVERSED" if hi < 0 else "absent")
        res[name] = {"increment": d, "ci": [lo, hi], "call": call}
        calls[name] = call
        print(f"   {name:<24s} {d:>+10.4f} [{lo:>+10.4f}, {hi:>+10.4f}]  {call}")

    g3 = bool(res["NOISE_CONTROL"]["call"] == "absent")
    print(f"G3 NEGATIVE CONTROL does not add   {'PASS' if g3 else '*** FAIL'}")

    out = {"experiment": "E219", "n_records": len(recs), "n_points": int(X.shape[0]),
           "n_records_all": n_all, "incumbent_rho": rho, "incumbent_floor": p95,
           "not_testable": list(ABSENT_FROM_PANEL), "results": res,
           "g1": g1, "g2": g2, "g3": g3}
    tested = {k: v for k, v in calls.items() if k != "NOISE_CONTROL"}
    print("\n" + "=" * 100)
    if not (g1 and g2 and g3):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 coverage", g1), ("G2 incumbent alive", g2),
                            ("G3 negative control", g3)) if not ok))
    elif any(c == "REVERSED" for c in tested.values()):
        v_, why = "REVERSED", (
            f"{[k for k, c in tested.items() if c == 'REVERSED']} clear on the NEGATIVE side. A negative "
            "increment is not support in any form")
    elif all(c == "REPLICATES" for c in tested.values()):
        v_, why = "BOTH REPLICATE", f"every tested survivor adds to the incumbent: {tested}"
    elif any(c == "REPLICATES" for c in tested.values()):
        v_, why = "PARTIAL", (
            f"{[k for k, c in tested.items() if c == 'REPLICATES']} replicate and "
            f"{[k for k, c in tested.items() if c == 'absent']} do not, on a fifth deposit")
    else:
        v_, why = "ABSENT", "no tested survivor adds to the incumbent on this deposit"
    out["verdict"], out["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print(f"SCOPE: the label is a SLEEP ladder, not sedation, so this replicates the CANDIDATES rather\n"
          f"  than the exact estimand. {', '.join(ABSENT_FROM_PANEL)} could not be tested. The montage is\n"
          f"  clinical bipolar PSG and E215 has just shown the exponent's percentile COORDINATE does not\n"
          f"  transport here -- a different quantity from what is tested, but a reason for caution.")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2, default=float)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
