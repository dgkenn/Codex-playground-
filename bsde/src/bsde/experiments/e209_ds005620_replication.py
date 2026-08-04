#!/usr/bin/env python3
"""E209 — Challenge C's licensed survivors on a THIRD deposit, with the feasibility probe run FIRST.

REGISTERED BEFORE ANY ds005620 INCREMENT HAS BEEN COMPUTED. The probe below touched no survivor feature.

=========================================================================================================
WHY A THIRD DEPOSIT, AND WHY THIS ONE
=========================================================================================================
E197 licensed the DOSE-I result: eight of ten jointly licensed candidates survive their placebo at
fraction 0.0000, five of them non-muscle. That is one deposit, one label, one incumbent.

**E208 tried Chennu and burned it.** Its incumbent was dead there — `spectral_edge_95` predicts Chennu's
sedation level at out-of-fold rho +0.0349 against a within-subject permutation floor of +0.1511 — so the
verdict was NOT INTERPRETABLE. Worse for future use: I had already computed and seen the secondary
plasma-propofol arm, where all four tested candidates were absent. Chennu can no longer be registered as
a fresh test of these candidates by anyone, and E208's ledger row says so.

**The lesson applied here: the feasibility probe runs BEFORE the registration** (rule 41), it touches no
candidate, and it reports numbers without choosing thresholds. On ds005620, over 202 recordings and 21
subjects with an ordered three-level task label (awake < sed < sed2, n = 59 / 92 / 51), the within-subject
rank correlation with the label is:

    exponent_high +0.5885 | exponent_gamma +0.4579 | uce_v1 +0.4446 | wpli_alpha +0.3540
    lempel_ziv +0.3483 | emg_beta_gamma_fraction -0.3328 | **spectral_edge_95 -0.2301** | ...

=========================================================================================================
THE INCUMBENT IS CHOSEN BY A RULE, NOT BY ITS RANK
=========================================================================================================
`spectral_edge_95`, because DOSE-I's incumbent was PE31+SEF95 and SEF95 is the component this deposit
shares — the same pre-specified rule E208 used, applied before its probe value was known to matter.

**It is deliberately not the strongest.** `exponent_high` correlates at +0.5885, more than twice as
strongly, and choosing it would be selecting the incumbent on the probe — which sets an unfairly high bar
and is exactly the selection rule 49 forbids. It is also near-collinear with `whole_head_exponent`, which
is one of the candidates, so it would half-test a candidate against itself.

=========================================================================================================
WHAT CHANGES FROM E208, AND WHAT DOES NOT
=========================================================================================================
Changed: the deposit and the label. Unchanged: the estimator, the leave-one-SUBJECT-out folds, the
subject-level bootstrap, the within-subject permutation null, the direction rule, and the gate structure.
`wpli_theta` is again absent from this deposit's panel and is again NOT tested, recorded rather than
dropped (rule 14).

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails.
  (2) REVERSED            one or more candidates clear zero on the NEGATIVE side. Not support.
  (3) ABSENT              no candidate's interval excludes zero above it.
  (4) PARTIAL             some but not all replicate.
  (5) REPLICATES          all tested candidates clear.

**REGISTERED PREDICTION: (3) ABSENT.** This is a change from E208's prediction of PARTIAL and the reason
is evidence rather than mood: Chennu's plasma-propofol arm, which I have seen and which is unlicensed,
put all four candidates at increments of -0.0252 to +0.0005 with every interval straddling zero. Two
deposits agreeing on absence would say the DOSE-I result is deposit-specific — which, after four
experiments to license it, is the most important thing this file could return.

=========================================================================================================
=========================================================================================================
WHAT IS BEING REPLICATED, AND WHY IT IS NOW WORTH REPLICATING
=========================================================================================================
E187 measured, on DOSE-I, whether eleven candidates add to a validated depth incumbent for predicting
MOAA/S beyond each candidate's own trend and autocorrelation. Its verdict was NOT INTERPRETABLE and stayed
that way through E189, E190 and E194 — four experiments that all gated on whether a surrogate PRESERVES
the autocorrelation, which catalogue rule 80 shows could only ever fail.

**E197 licensed the method by measuring the thing the gate was a proxy for**: the false-positive rate of
each placebo family on an AR(1) ladder spanning the real candidates' own autocorrelation. All three
families hold nominal, no pair of intervals separates at any rung, and ten candidates are jointly
licensed. Eight survive at fraction 0.0000, five of them non-muscle:

    multiscale_entropy_slope  -0.02769      whole_head_exponent  -0.01664
    relative_alpha_power      -0.03331      wpli_theta           -0.00828
    pac_slow_alpha            -0.00157

**That is one deposit, one label and one incumbent.** This file asks whether it happens again somewhere
else, which is the only question left that the DOSE-I data cannot answer about itself.

=========================================================================================================
THE DEPOSIT, AND WHAT IT CHANGES ON PURPOSE
=========================================================================================================
Chennu's propofol sedation cohort: **20 subjects x 4 sedation levels = 80 recordings**, all status `ok`,
with `meta_sedation_level` (1-4) and — the part that matters — **`meta_plasma_propofol_ug_per_L` populated
for all 80**.

Four of the five non-muscle survivors are computable here under the same names, from the same feature
code. `wpli_theta` is NOT in this deposit's panel (it carries `wpli_alpha` instead) and is therefore
**not tested**, stated here rather than quietly dropped (rule 14).

**Two incumbents, both declared in advance, because they answer different questions and catalogue rule 86
was written this session about exactly this choice.**

    ARM 1 (PRIMARY)   incumbent = `spectral_edge_95`. DOSE-I's incumbent was PE31+SEF95; SEF95 is the
                      component this deposit shares, so this is the closest available match to the
                      thing the original increment was measured over.
    ARM 2 (SECONDARY) incumbent = **plasma propofol concentration** — an EXPOSURE, not another EEG
                      readout and not a co-measured bedside observation. Rule 86 records that an
                      incumbent sharing a measurement act with the outcome sets a bar nothing external
                      can clear; a drug concentration shares nothing with a sedation score except the
                      patient.

Both are reported. The PRIMARY is arm 1 and is fixed here so that a later preference cannot decide it.

=========================================================================================================
THE UNIT IS THE SUBJECT, AND THE DESIGN IS WITHIN-SUBJECT
=========================================================================================================
Twenty subjects each contribute four levels, so rows are nested and the effective n is 20, not 80. Rule 69
measured a row-level null inflating significance 178-fold on another deposit. Here: subjects are held out
whole by leave-one-subject-out, and the null permutes the sedation level **within subject**, which
destroys the ordering while preserving each subject's own four values and every between-subject
difference.

    **P1  the out-of-fold Spearman increment**: rho(predicted, true sedation level) with the candidate in
          the design, minus the same quantity without it, subjects held out whole.

=========================================================================================================
GATES
=========================================================================================================
G1  20 subjects x 4 levels present and every candidate finite on all 80 rows.
G2  **THE INCUMBENT MUST BE ALIVE** in the arm being read: `spectral_edge_95` must predict sedation level
    above its own within-subject permutation floor. E33 wrote this rule and E61 failed to carry it across.
G3  a negative control: an i.i.d. noise column must NOT add, at the same estimator and folds.
G4  **DIRECTION IS FIXED IN ADVANCE.** On DOSE-I every one of the five survivors had a NEGATIVE increment
    in the error metric, i.e. each IMPROVED prediction. Here the metric is a correlation, so replication
    means a POSITIVE increment. A candidate that clears the interval on the WRONG side is a REVERSAL and
    is enumerated as its own verdict, never counted as support (rule 37, whose fourth occurrence was a
    refutation printed as a confirmation).

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails.
  (2) REVERSED            one or more candidates clear zero on the NEGATIVE side. Not support.
  (3) ABSENT              no candidate's interval excludes zero above it.
  (4) PARTIAL             some but not all of the four replicate.
  (5) REPLICATES          all four tested candidates clear.

**REGISTERED PREDICTION: (4) PARTIAL, with `relative_alpha_power` and `whole_head_exponent` clearing and
`pac_slow_alpha` not.** Reasoning: on DOSE-I `pac_slow_alpha`'s increment was -0.00157, the smallest of
the five and an order of magnitude below `relative_alpha_power`'s -0.03331, so it has the least to
survive a change of deposit, label and incumbent. `multiscale_entropy_slope` is the one I genuinely
cannot call. **A (3) ABSENT would say the DOSE-I result is deposit-specific**, which after E197's four
experiments to license it would be the most important thing this file could return.

    python bsde/src/bsde/experiments/e208_chennu_replication.py
"""

from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import spearman                                       # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "ds005620_full.csv")
OUT = os.path.join(RESULTS, "e209_ds005620_replication.json")
SEED = 20260802

# The five non-muscle survivors E197 licensed on DOSE-I. `wpli_theta` is absent from this deposit's panel
# and is NOT tested; recorded here so the exclusion is visible rather than silent (rule 14).
DOSEI_SURVIVORS = {"multiscale_entropy_slope": -0.02769, "relative_alpha_power": -0.03331,
                   "whole_head_exponent": -0.01664, "wpli_theta": -0.00828,
                   "pac_slow_alpha": -0.00157}
INCUMBENT_PRIMARY = "spectral_edge_95"
INCUMBENT_SECONDARY = ""
PERMS = 1000
BOOT = 2000
ALPHA = 0.05


def _f(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


ORDER = {"awake": 0.0, "sed": 1.0, "sed2": 2.0}


def load():
    """ds005620: the ordered task label, parsed as a BIDS ENTITY rather than substring-matched.

    Rule 61 was written about this exact deposit: E87 assigned states by testing whether a token appeared
    anywhere in the recording id, and `rest` matched `acq-rest` inside a sedated recording. `meta_task` is
    the parsed entity, and its counts (59 / 92 / 51) are asserted below.
    """
    rows = [r for r in csv.DictReader(open(TABLE)) if (r.get("meta_task") or "") in ORDER]
    subj = np.array([r["subject"] for r in rows])
    lvl = np.array([ORDER[r["meta_task"]] for r in rows], float)
    return rows, subj, lvl


def loo_predict(X, y, subj, seed=0):
    """Leave-one-SUBJECT-out ridge prediction of the level. Subjects are the unit (rule 69)."""
    pred = np.full(len(y), np.nan)
    us = np.unique(subj)
    for u in us:
        te = subj == u
        tr = ~te
        A = np.c_[np.ones(tr.sum()), X[tr]]
        B = np.c_[np.ones(te.sum()), X[te]]
        lam = 1e-3 * A.shape[0]
        try:
            w = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ y[tr])
        except np.linalg.LinAlgError:
            continue
        pred[te] = B @ w
    return pred


def score(X, y, subj):
    p = loo_predict(X, y, subj)
    m = np.isfinite(p) & np.isfinite(y)
    if m.sum() < 10:
        return float("nan")
    r = spearman(list(p[m]), list(y[m]))
    return float(r) if np.isfinite(r) else float("nan")


def within_subject_permute(y, subj, rng):
    out = y.copy()
    for u in np.unique(subj):
        m = subj == u
        out[m] = rng.permutation(y[m])
    return out


def increment(base, cand, y, subj, boot=BOOT, seed=SEED):
    """Increment in out-of-fold Spearman, with a SUBJECT-level bootstrap interval."""
    a = score(base, y, subj)
    b = score(np.c_[base, cand], y, subj)
    obs = b - a
    us = np.unique(subj)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(boot):
        pick = rng.choice(us, size=us.size, replace=True)
        idx = np.concatenate([np.flatnonzero(subj == u) for u in pick])
        s2 = np.concatenate([[f"{i}"] * int((subj == u).sum()) for i, u in enumerate(pick)])
        va = score(base[idx], y[idx], s2)
        vb = score(np.c_[base[idx], cand[idx]], y[idx], s2)
        if np.isfinite(va) and np.isfinite(vb):
            vals.append(vb - va)
    lo, hi = ((float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975)))
              if len(vals) > 50 else (float("nan"), float("nan")))
    return float(obs), lo, hi, float(a), float(b)


def main() -> int:
    print("E208 — do Challenge C's licensed survivors replicate on Chennu's propofol cohort?")
    rows, subj, lvl = load()
    res = {"experiment": "E209", "n_rows": len(rows), "n_subjects": int(np.unique(subj).size),
           "dosei_survivors": DOSEI_SURVIVORS, "primary_incumbent": INCUMBENT_PRIMARY}
    # A column that EXISTS but has no finite values is not in the deposit in any usable sense.
    # `pac_slow_alpha` is present as a header here and empty in all 202 rows -- rule 6, check a column is
    # populated before designing around it, and rule 74, put the guard where every caller gets it.
    def _usable(c):
        if c not in (rows[0] if rows else {}):
            return False
        v = np.array([_f(r.get(c, "")) for r in rows])
        return bool(np.isfinite(v).sum() >= 0.9 * len(v))

    tested = [c for c in DOSEI_SURVIVORS if _usable(c)]
    absent = [c for c in DOSEI_SURVIVORS if c not in tested]
    res["tested"], res["not_in_deposit"] = tested, absent
    print(f"   {len(rows)} rows, {np.unique(subj).size} subjects, levels "
          f"{sorted(set(lvl.tolist()))}")
    print(f"   testing {len(tested)} of {len(DOSEI_SURVIVORS)} survivors; NOT in this deposit: "
          f"{absent or 'none'}")

    F = {c: np.array([_f(r[c]) for r in rows]) for c in tested}
    inc_p = np.array([_f(r[INCUMBENT_PRIMARY]) for r in rows])
    import collections as _c
    counts = _c.Counter(lvl.tolist())
    g1 = bool(len(rows) >= 150 and np.unique(subj).size >= 15 and len(counts) == 3
              and all(np.isfinite(v).all() for v in F.values()) and np.isfinite(inc_p).all())
    print(f"   label counts (awake/sed/sed2): "
          f"{[int(counts.get(float(k), 0)) for k in (0, 1, 2)]}")
    print(f"   G1 {'PASS' if g1 else '*** FAIL'}")
    res["g1"] = g1

    base_p = inc_p[:, None]
    a_only = score(base_p, lvl, subj)
    rng = np.random.default_rng(SEED + 5)
    nul = []
    for _ in range(PERMS // 5):
        yp = within_subject_permute(lvl, subj, rng)
        v = score(base_p, yp, subj)
        if np.isfinite(v):
            nul.append(v)
    f95 = float(np.quantile(nul, 0.95)) if nul else float("nan")
    g2 = bool(np.isfinite(a_only) and a_only > f95)
    print(f"   G2 INCUMBENT ALIVE: {INCUMBENT_PRIMARY} out-of-fold rho {a_only:+.4f} vs "
          f"within-subject permutation p95 {f95:+.4f}   {'PASS' if g2 else '*** FAIL'}")
    res["g2"] = {"incumbent_rho": a_only, "null_p95": f95, "pass": g2}

    noise = np.random.default_rng(SEED + 7).normal(size=(len(rows), 1))
    ni, nlo, nhi, _a, _b = increment(base_p, noise, lvl, subj)
    g3 = bool(not (np.isfinite(nlo) and nlo > 0))
    print(f"   G3 negative control: noise increment {ni:+.4f} [{nlo:+.4f}, {nhi:+.4f}]   "
          f"{'PASS' if g3 else '*** FAIL'}")
    res["g3"] = {"increment": ni, "ci": [nlo, nhi], "pass": g3}

    for tag, base in (("primary/spectral_edge_95", base_p),):
        print(f"\n   [{tag}]  {'candidate':<26s} {'increment':>10s} {'[95% CI]':>22s}  call")
        tab = {}
        for c in tested:
            obs, lo, hi, a_, b_ = increment(base, F[c][:, None], lvl, subj)
            call = ("REVERSED" if np.isfinite(hi) and hi < 0 else
                    "replicates" if np.isfinite(lo) and lo > 0 else "absent")
            tab[c] = {"increment": obs, "ci": [lo, hi], "base_rho": a_, "with_rho": b_,
                      "call": call, "dosei": DOSEI_SURVIVORS[c]}
            print(f"   [{tag}]  {c:<26s} {obs:>+10.4f} [{lo:>+9.4f}, {hi:>+9.4f}]  {call}",
                  flush=True)
        res[f"arm_{tag.split('/')[0]}"] = tab

    prim = res["arm_primary"]
    rev = [c for c, v in prim.items() if v["call"] == "REVERSED"]
    rep = [c for c, v in prim.items() if v["call"] == "replicates"]
    print("\n" + "=" * 100)
    if not (g1 and g2 and g3):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 cohort", g1), ("G2 incumbent alive", g2),
                            ("G3 negative control", g3)) if not ok))
    elif rev:
        v_, why = "REVERSED", (f"{rev} clear zero on the NEGATIVE side, the opposite of the DOSE-I "
                               "direction. This is not support and must never be reported as such")
    elif not rep:
        v_, why = "ABSENT", (f"no candidate's interval excludes zero above it on {len(rows)} rows over "
                             f"{np.unique(subj).size} subjects; the DOSE-I result is deposit-specific so "
                             "far as this cohort can say")
    elif len(rep) < len(tested):
        v_, why = "PARTIAL", (f"{len(rep)} of {len(tested)} tested survivors replicate: {rep}; "
                              f"the rest are absent")
    else:
        v_, why = "REPLICATES", f"all {len(tested)} tested survivors replicate: {rep}"
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print(f"SCOPE: {absent or 'nothing'} could not be tested -- not in this deposit's panel. There is\n"
          "  NO secondary arm here: E208 was compromised by my having computed one before gating it,\n"
          "  and this file has a single pre-declared incumbent chosen by rule rather than by rank.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
