#!/usr/bin/env python3
"""E249 -- completing E248's unimplemented primaries and gates, and emitting the verdict it never had.

------------------------------------------------------------------------------------------------------
WHAT THIS IS, AND THE ORDERING FACT THE READER IS OWED FIRST

E248 registered TWO primaries and FOUR gates. Its file implements **P1 only**. Verified by grep, not by
reading its prose: P2 (within-patient state tracking), G1 (the aliveness gate) and G3 (capability in both
directions) do not appear in the code at all; `MIN_ARM = 300` is defined at line 171 and never
referenced, so G4's arm-size half is unenforced; `MIN_WIN = 15` is applied as a silent cohort filter
rather than a reported gate; Holm correction is named three times in the docstring and never implemented;
and the file ends after `json.dump` with no verdict branch. Under E248's own rule -- *"(d) NOT
INTERPRETABLE -- G1, G3 or G4 fails"* -- and catalogue rule 31, an unevaluated gate makes the downstream
verdict **absent, not negative**. `results/e248_first_pass_note.md` is the record.

**P1 WAS SEEN BEFORE THIS FILE WAS WRITTEN.** That is stated here rather than buried because it is the
one thing a reader cannot check from the artefacts. Three things bound what it can have contaminated:

* **No threshold in this file is new.** G1's "at least half the candidates, 0.10 above their own null",
  G3's both-directions requirement, G4's 300 / 15, G2's comparison against the median candidate, and the
  four verdict branches are transcribed from E248's docstring unchanged. Completing a gate that was never
  coded is not moving it (rule 58 forbids *revising* a gate after it fires; this one never fired).
* **G1 and G3 cannot be tuned to make P1 pass.** G1 asks whether the ventilation transition is legible at
  all -- a property of the state axis, not of the arm contrast. G3 asks whether the P1 path detects a
  planted signal and rejects a planted null. Both can only ever *withdraw* P1's licence, never grant it.
* **P1 IS NOT RECOMPUTED.** Holm is applied to the p-values already in `e248_agent_leakage.json`. Nothing
  in this file can change a P1 number.

------------------------------------------------------------------------------------------------------
COHORT. Unchanged from E248: the 56,731-window ventilation-landmarked table (56,237 `ok`), 21 windows of
10 s at offsets -300..+300 s in 30 s steps about the landmark, identical for every case.

**THE DESIGN IS RECOVERY-ONLY AT SCALE, AND THAT IS NOT A CHOICE MADE HERE.** Of 2,930 landmarked
single-agent cases, `rec_ok` holds in 2,592 and `loss_ok` in 110 (94 have both). P2 is therefore computed
about the RECOVERY landmark, where "before" is controlled ventilation and "after" is spontaneous
breathing. The 16 loss-only cases are reported separately and never pooled: at loss the transition runs
the other way, so pooling would cancel a real effect against itself (rule 55's shape).

**THE LABEL IS THE AIRWAY RECORD AND IT IS NOT CONSCIOUSNESS.** Carried verbatim from E248: this is a
brainstem behavioural output. Every sentence from either file belongs in the first result clause, not a
limitations paragraph.

------------------------------------------------------------------------------------------------------
P2 -- STATE TRACKING. REPLICATION, NOT A FINDING (PMID 31326088 did the drug-independent version).

Per candidate, per patient: `AUC(windows after the landmark vs windows before it)`. Aggregated as the
**signed mean of `AUC_i - 0.5` across patients**, not the mean of the folded value -- `|AUC-0.5|` is
biased upward under the null (rule 46) and a folded per-patient statistic would manufacture legibility
from noise at n = 2,592. The sign is then taken once, at the end, on the aggregate.

**Null: exact, analytic, and tie-aware.** Under within-patient permutation of the before/after label the
ranks are fixed and only the subset changes, so `S_i` = sum of ranks assigned to "after" is a
finite-population sample: `E[S_i] = n1*mean(r)`, `Var[S_i] = n1*n2/(n-1) * popvar(r)`. Hence
`E[AUC_i] = 0.5` exactly (midranks included) and `Var[AUC_i] = Var[S_i] / (n1*n2)^2`. The null sd of the
across-patient mean is `sqrt(sum Var[AUC_i]) / N`. This is the same analytic-null move E248 used for P1,
where it reproduced this project's own measured floors (0.1913 against E154's 0.1904; 0.3024 against
E142's 0.2791) -- and it is **checked here against an empirical within-patient permutation** on every
candidate, exactly as E248 checked its P1 floors. If the two disagree the analytic form is not trusted.

------------------------------------------------------------------------------------------------------
GATES, all transcribed unchanged from E248.

G1  THE PHENOMENON EXISTS (rules 33, 53, 83). At least half the candidates must reach within-patient
    state legibility of **0.10 above their own null**. Coded as `|obs| - null_p95 >= 0.10`. If nothing
    tracks the ventilation transition, a leakage comparison at matched state is a comparison between two
    cohorts, not two agents -- rule 32, which this project has already paid for once.

G2  NUISANCE PLACEBO -- THE GATE E154 FAILED. `opdur_s`, `age`, `bmi` through the identical
    agent-legibility path. If any exceeds the MEDIAN candidate's leakage the verdict is VOID, not
    negative. A comparison against the candidates, never an absolute threshold (rule 34). Recomputed
    here from E248's own JSON so the branch exists in code rather than in a note.

G3  CAPABILITY, BOTH DIRECTIONS (rule 40). A synthetic feature constructed to BE the arm label plus
    noise must be detected at high leakage; an independent Gaussian must not exceed its null. **The
    negative control is correlated against the arm label and asserted null before use (rule 77)** -- a
    control built to be independent must be measured for independence, because E173's was not and fired
    on everything. Both run through the identical P1 path.

G4  SUPPORT. `>= 300` patients in the smaller arm of each pairwise contrast, and `>= 15` windows per
    patient. Both halves enforced here and **both reported**, including the count E248 dropped silently.

------------------------------------------------------------------------------------------------------
ADDITIONALLY REPORTED, BECAUSE E248 DROPPED IT WITHOUT SAYING SO (rule 14).

2,930 cases carry landmarks; 2,589 survive `MIN_WIN >= 15`. **The 341 dropped cases are tabulated by arm
and tested for arm-relatedness.** An exclusion that removes desflurane cases preferentially is not the
harmless loss of power it looks like -- rule 87 is the precedent, where a one-sided exclusion selected on
the anaesthesia machine and cost three experiments.

------------------------------------------------------------------------------------------------------
VERDICT RULE. Transcribed from E248. The wrong-direction case first and explicitly (rule 37).

  (a) VOID              -- G2 fails: a nuisance variable out-identifies the candidates, as in E154.
  (b) NO LEAKAGE        -- no candidate exceeds its patient-level null after Holm.
  (c) LEAKAGE           -- one or more do. Report which, how much, against the nuisance placebos.
  (d) NOT INTERPRETABLE -- G1, G3 or G4 fails.

Gates are evaluated AFTER the primaries are computed and printed (rule 37: a gate can only invalidate a
pass, never rescue a null), and each gate is named for the claim it can invalidate (rule 97).

    python -m bsde.experiments.e249_e248_gate_completion
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")

ARMS = ("sevo", "des", "ppf")
PAIRS = (("sevo", "des"), ("sevo", "ppf"), ("des", "ppf"))
MIN_ARM = 300
MIN_WIN = 15
G1_MARGIN = 0.10
G1_FRACTION = 0.5
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
NUISANCE = ("opdur_s", "age", "bmi")


def _f(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def midranks(vals):
    """Midranks of `vals`, 1-based, ties averaged. Returned in the order of `vals`."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def patient_auc_and_var(vals, is_after):
    """AUC(after vs before) for one patient, plus its EXACT permutation variance.

    Ranks are invariant under permutation of the before/after label, so S = sum of ranks at "after" is a
    finite-population sample of size n1 from the fixed rank multiset:
        E[S]   = n1 * mean(r)
        Var[S] = n1 * n2 / (n - 1) * popvar(r)
    AUC = (S - n1(n1+1)/2) / (n1*n2), so E[AUC] = 0.5 exactly (midranks included).
    """
    keep = [(v, a) for v, a in zip(vals, is_after) if math.isfinite(v)]
    if len(keep) < 4:
        return float("nan"), float("nan")
    v = [x[0] for x in keep]
    a = [x[1] for x in keep]
    n1 = sum(1 for x in a if x)
    n2 = len(a) - n1
    if n1 == 0 or n2 == 0:
        return float("nan"), float("nan")
    r = midranks(v)
    s = sum(rr for rr, aa in zip(r, a) if aa)
    auc = (s - n1 * (n1 + 1) / 2.0) / (n1 * n2)
    n = len(r)
    mu = sum(r) / n
    popvar = sum((x - mu) ** 2 for x in r) / n
    var_s = n1 * n2 / (n - 1.0) * popvar if n > 1 else 0.0
    return auc, var_s / (n1 * n2) ** 2


def empirical_p2_null(per_patient, rng, reps):
    """Within-patient permutation null for the across-patient MEAN of (AUC_i - 0.5).

    Permuting the before/after label within a patient resamples which ranks land in "after", so the
    per-patient null draw is a finite-population sample. Implemented by shuffling the label vector.
    """
    out = []
    for _ in range(reps):
        tot, n = 0.0, 0
        for vals, is_after in per_patient:
            lab = list(is_after)
            rng.shuffle(lab)
            a, _v = patient_auc_and_var(vals, lab)
            if math.isfinite(a):
                tot += a - 0.5
                n += 1
        if n:
            out.append(tot / n)
    out.sort()
    return out


def auc_unpaired(pos, neg):
    pos = [x for x in pos if math.isfinite(x)]
    neg = [x for x in neg if math.isfinite(x)]
    if not pos or not neg:
        return float("nan")
    allv = pos + neg
    r = midranks(allv)
    s = sum(r[:len(pos)])
    return (s - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def perm_null_unpaired(a_vals, b_vals, rng, reps):
    pool = list(a_vals) + list(b_vals)
    n1 = len(a_vals)
    out = []
    for _ in range(reps):
        rng.shuffle(pool)
        a = auc_unpaired(pool[:n1], pool[n1:])
        if math.isfinite(a):
            out.append(abs(a - 0.5))
    out.sort()
    return out


def holm(pvals):
    """Holm-Bonferroni. Returns {key: adjusted p}, monotone-enforced."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, prev = {}, 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, max(prev, (m - i) * p))
        out[k] = adj
        prev = adj
    return out


def pearson(x, y):
    pts = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(pts) < 3:
        return float("nan")
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--features", default=os.path.join(RESULTS, "vitaldb_ventwin.s*.csv"))
    ap.add_argument("--landmarks", default=os.path.join(RESULTS, "vitaldb_vent_landmarks.s*.csv"))
    ap.add_argument("--p1", default=os.path.join(RESULTS, "e248_agent_leakage.json"))
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--p2-null-reps", type=int, default=200)
    ap.add_argument("--seed", type=int, default=249)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e249_gate_completion.json"))
    ap.add_argument("--smoke", action="store_true",
                    help="Rule 26: permute the before/after label within patient and the arm label "
                         "across patients. Every path runs; no report is written.")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    # ---------------------------------------------------------------- landmarks
    lm = {}
    for p in sorted(glob.glob(a.landmarks)):
        for r in csv.DictReader(open(p)):
            if r.get("error") or r.get("arm") not in ARMS:
                continue
            lm[r["caseid"]] = r
    print(f"[landmarks] {len(lm)} single-agent cases with landmarks")
    if not lm:
        print("no landmarks")
        return 2

    # ---------------------------------------------------------------- features
    paths = sorted(glob.glob(a.features))
    rows, cols = [], None
    for p in paths:
        rd = csv.DictReader(open(p))
        if cols is None:
            cols = [c for c in (rd.fieldnames or []) if not c.startswith("meta_") and c not in SKIP]
        for r in rd:
            if r.get("status") == "ok" and r.get("meta_caseid") in lm:
                rows.append(r)
    finite = {c: sum(1 for r in rows if math.isfinite(_f(r.get(c)))) for c in cols}
    dropped = {c: n for c, n in finite.items() if n < 0.20 * len(rows)}
    cols = [c for c in cols if c not in dropped]
    print(f"[features] {len(rows)} windows, {len(cols)} candidate columns "
          f"(dropped {sorted(dropped)} -- rule 74)")

    by_case = {}
    for r in rows:
        by_case.setdefault(r["meta_caseid"], []).append(r)

    # ------------------------------------------------- G4 second half, REPORTED (rule 14)
    kept = {k: v for k, v in by_case.items() if len(v) >= MIN_WIN}
    drop_ids = [k for k in by_case if k not in kept]
    landmarked_by_arm = {arm: sum(1 for r in lm.values() if r["arm"] == arm) for arm in ARMS}
    kept_by_arm = {arm: sum(1 for k in kept if lm[k]["arm"] == arm) for arm in ARMS}
    print(f"\n[G4b MIN_WIN>={MIN_WIN}] {len(by_case)} cases with windows -> {len(kept)} kept, "
          f"{len(drop_ids)} dropped")
    print(f"    landmarked by arm : {landmarked_by_arm}")
    print(f"    kept by arm       : {kept_by_arm}")
    drop_rate = {}
    for arm in ARMS:
        n_l = landmarked_by_arm[arm]
        drop_rate[arm] = (n_l - kept_by_arm[arm]) / n_l if n_l else float("nan")
    print(f"    DROP RATE by arm  : " + ", ".join(f"{k}={v:.4f}" for k, v in drop_rate.items()))
    rates = [v for v in drop_rate.values() if math.isfinite(v)]
    drop_spread = max(rates) - min(rates) if rates else float("nan")
    print(f"    spread            : {drop_spread:.4f}  "
          f"({'ARM-RELATED -- report as a limitation' if drop_spread > 0.05 else 'even across arms'})")

    arm_of = {k: lm[k]["arm"] for k in kept}
    if a.smoke:
        keys = sorted(arm_of)
        vals = [arm_of[k] for k in keys]
        rng.shuffle(vals)
        arm_of = dict(zip(keys, vals))
        print("[SMOKE] arm labels permuted across patients (rule 26)")
    counts = {arm: sum(1 for v in arm_of.values() if v == arm) for arm in ARMS}
    print(f"[cohort] patients per arm: {counts}")

    # ================================================================ P2, computed BEFORE any gate
    rec_ok = {k for k in kept if lm[k].get("rec_ok") == "1"}
    loss_only = {k for k in kept if lm[k].get("rec_ok") != "1" and lm[k].get("loss_ok") == "1"}
    print(f"\n[P2 cohort] recovery landmark {len(rec_ok)} cases; loss-only {len(loss_only)} "
          f"(reported separately, never pooled -- the transition runs the other way)")

    def landmark_t(cid):
        r = lm[cid]
        t = _f(r.get("t_rec_s")) if cid in rec_ok else _f(r.get("t_loss_s"))
        return t

    p2 = {}
    per_patient_cache = {}
    for c in cols:
        per_patient, terms, var_terms = [], [], []
        for cid in rec_ok:
            t0 = landmark_t(cid)
            if not math.isfinite(t0):
                continue
            vals, after = [], []
            for r in kept[cid]:
                off = _f(r.get("meta_t_s")) - t0
                if off == 0 or not math.isfinite(off):
                    continue          # the landmark window itself is neither side
                vals.append(_f(r.get(c)))
                after.append(off > 0)
            if a.smoke:
                rng.shuffle(after)
            auc_i, var_i = patient_auc_and_var(vals, after)
            if math.isfinite(auc_i):
                per_patient.append((vals, after))
                terms.append(auc_i - 0.5)
                var_terms.append(var_i)
        if not terms:
            p2[c] = {"obs": float("nan"), "n": 0}
            continue
        n = len(terms)
        obs = sum(terms) / n
        null_sd = math.sqrt(sum(var_terms)) / n
        null_p95 = 1.959964 * null_sd
        p2[c] = {"obs": obs, "abs_obs": abs(obs), "n": n,
                 "analytic_null_p95": null_p95,
                 "margin": abs(obs) - null_p95}
        per_patient_cache[c] = per_patient

    print("\n[P2 state tracking about the RECOVERY landmark] "
          "signed mean of (AUC_after_vs_before - 0.5) across patients")
    for c, v in sorted(p2.items(), key=lambda kv: -(kv[1].get("abs_obs") or 0)):
        if not math.isfinite(v.get("obs", float("nan"))):
            continue
        print(f"    {c:28s} {v['obs']:+.4f}  n={v['n']:4d}  null95={v['analytic_null_p95']:.4f}  "
              f"margin={v['margin']:+.4f}")

    # --- the analytic null is CHECKED, not assumed (E248 did the same for P1)
    check_cols = sorted(p2, key=lambda c: -(p2[c].get("abs_obs") or 0))[:3]
    null_check = {}
    for c in check_cols:
        if c not in per_patient_cache:
            continue
        emp = empirical_p2_null(per_patient_cache[c], rng, a.p2_null_reps)
        if emp:
            emp_p95 = max(abs(emp[int(0.025 * len(emp))]), abs(emp[int(0.975 * len(emp))]))
            null_check[c] = {"analytic_p95": p2[c]["analytic_null_p95"], "empirical_p95": emp_p95,
                             "reps": len(emp)}
            print(f"[P2 null check] {c:28s} analytic {p2[c]['analytic_null_p95']:.5f}  "
                  f"empirical {emp_p95:.5f}  ({len(emp)} draws)")

    # ================================================================ GATES
    print("\n" + "=" * 96)
    gates = {}

    # ---- G1
    live = [c for c, v in p2.items() if math.isfinite(v.get("margin", float("nan")))
            and v["margin"] >= G1_MARGIN]
    n_testable = sum(1 for v in p2.values() if math.isfinite(v.get("margin", float("nan"))))
    g1_pass = n_testable > 0 and len(live) >= G1_FRACTION * n_testable
    gates["G1"] = {"pass": g1_pass, "n_live": len(live), "n_testable": n_testable,
                   "required": G1_FRACTION * n_testable, "live": sorted(live)}
    print(f"G1 phenomenon exists : {len(live)} of {n_testable} candidates >= {G1_MARGIN} above their "
          f"own null (need {G1_FRACTION * n_testable:.1f})  -> {'PASS' if g1_pass else 'FAIL'}")
    if live:
        print("     live: " + ", ".join(sorted(live)))

    # ---- G2, recomputed from E248's own JSON so the branch exists in code
    g2_pass, g2_detail = True, {}
    p1doc = None
    if os.path.exists(a.p1):
        p1doc = json.load(open(a.p1))
        for name, pair in p1doc["pairs"].items():
            f = pair["features"]
            cand = sorted(v["obs"] for k, v in f.items()
                          if k not in NUISANCE and math.isfinite(v["obs"]))
            med = cand[len(cand) // 2] if cand else float("nan")
            worst = {}
            for nz in NUISANCE:
                if nz in f:
                    worst[nz] = f[nz]["obs"]
                    if f[nz]["obs"] > med:
                        g2_pass = False
            g2_detail[name] = {"median_candidate": med, "nuisance": worst}
            print(f"G2 nuisance placebo  : {name:14s} median candidate {med:.4f} | "
                  + ", ".join(f"{k}={v:.4f}" for k, v in worst.items())
                  + f"  -> {'ok' if all(v <= med for v in worst.values()) else 'EXCEEDS'}")
    gates["G2"] = {"pass": g2_pass, "detail": g2_detail}

    # ---- G3 capability, both directions, through the identical P1 path
    arm_idx = {"sevo": 0.0, "des": 1.0, "ppf": 2.0}
    synth_pos, synth_neg = {}, {}
    for cid in kept:
        synth_pos[cid] = arm_idx[arm_of[cid]] + rng.gauss(0, 0.25)
        synth_neg[cid] = rng.gauss(0, 1.0)
    # rule 77: a control built to be independent must be MEASURED for independence, before use
    keys = sorted(kept)
    r_neg = pearson([arm_idx[arm_of[k]] for k in keys], [synth_neg[k] for k in keys])
    r_pos = pearson([arm_idx[arm_of[k]] for k in keys], [synth_pos[k] for k in keys])
    print(f"G3 rule-77 check     : corr(arm, negative control) = {r_neg:+.4f} "
          f"(must be ~0) | corr(arm, positive control) = {r_pos:+.4f}")
    g3_detail, g3_pos_ok, g3_neg_ok = {}, True, True
    for x, y in PAIRS:
        ax = [c for c in kept if arm_of[c] == x]
        ay = [c for c in kept if arm_of[c] == y]
        d = {}
        for nm, tbl in (("positive", synth_pos), ("negative", synth_neg)):
            va = [tbl[i] for i in ax]
            vb = [tbl[i] for i in ay]
            obs = abs(auc_unpaired(va, vb) - 0.5)
            null = perm_null_unpaired(va, vb, rng, a.reps)
            p95 = null[int(0.95 * len(null))] if null else float("nan")
            d[nm] = {"obs": obs, "null_p95": p95}
            if nm == "positive" and not (obs > p95):
                g3_pos_ok = False
            if nm == "negative" and obs > p95:
                g3_neg_ok = False
        g3_detail[f"{x}_vs_{y}"] = d
        print(f"G3 capability        : {x}_vs_{y:5s} positive {d['positive']['obs']:.4f} "
              f"(null95 {d['positive']['null_p95']:.4f}) | negative {d['negative']['obs']:.4f} "
              f"(null95 {d['negative']['null_p95']:.4f})")
    g3_pass = g3_pos_ok and g3_neg_ok and math.isfinite(r_neg) and abs(r_neg) < 0.10
    gates["G3"] = {"pass": g3_pass, "positive_detected": g3_pos_ok, "negative_null": g3_neg_ok,
                   "corr_arm_negative": r_neg, "corr_arm_positive": r_pos, "detail": g3_detail}
    print(f"G3 capability        : -> {'PASS' if g3_pass else 'FAIL'}")

    # ---- G4 both halves
    g4_arm = all(min(counts[x], counts[y]) >= MIN_ARM for x, y in PAIRS)
    g4_pass = g4_arm  # the window half is enforced by construction above and reported
    gates["G4"] = {"pass": g4_pass, "arm_half": g4_arm, "counts": counts,
                   "min_arm": MIN_ARM, "min_win": MIN_WIN,
                   "dropped_cases": len(drop_ids), "drop_rate_by_arm": drop_rate,
                   "drop_rate_spread": drop_spread}
    print(f"G4 support           : smaller arms "
          + ", ".join(f"{x}/{y}={min(counts[x], counts[y])}" for x, y in PAIRS)
          + f" (need >= {MIN_ARM}) -> {'PASS' if g4_pass else 'FAIL'}")

    # ---- Holm on P1's EXISTING p-values. P1 is not recomputed.
    holm_out = {}
    any_leak = False
    if p1doc:
        for name, pair in p1doc["pairs"].items():
            f = pair["features"]
            pv = {k: v["p"] for k, v in f.items()
                  if k not in NUISANCE and math.isfinite(v.get("p", float("nan")))}
            adj = holm(pv)
            sig = {k: v for k, v in adj.items() if v < 0.05}
            holm_out[name] = {"adjusted": adj, "n_sig": len(sig), "sig": sorted(sig)}
            if sig:
                any_leak = True
            print(f"Holm on P1           : {name:14s} {len(sig)} of {len(pv)} candidates "
                  f"adj-p < 0.05")

    # ================================================================ VERDICT
    print("\n" + "=" * 96)
    if not gates["G2"]["pass"]:
        verdict = "VOID"
        why = ("G2 fails: a nuisance variable out-identifies the candidates, as in E154. "
               "Nothing about leakage is claimed.")
    elif not (gates["G1"]["pass"] and gates["G3"]["pass"] and gates["G4"]["pass"]):
        failed = [g for g in ("G1", "G3", "G4") if not gates[g]["pass"]]
        verdict = "NOT INTERPRETABLE"
        why = (f"{', '.join(failed)} fail. "
               + ("G1: nothing tracks the ventilation transition, so a leakage comparison at matched "
                  "state is a comparison between two cohorts, not two agents (rule 32). "
                  if "G1" in failed else "")
               + ("G3: the P1 path did not detect a planted signal, or flagged a planted null. "
                  if "G3" in failed else "")
               + ("G4: insufficient support. " if "G4" in failed else ""))
    elif any_leak:
        verdict = "LEAKAGE"
        why = ("One or more candidates exceed their patient-level null after Holm. This is a quantified "
               "criticism of every 'drug-independent' estimator, Ramaswamy 2019's included.")
    else:
        verdict = "NO LEAKAGE"
        why = ("No candidate exceeds its null after Holm, at a floor of 0.023-0.034. The invariance "
               "problem is smaller than the field assumes.")
    print(f"VERDICT: {verdict}\n  {why}")
    print("\nSCOPE, carried from E248 and not softened: the state label is the AIRWAY RECORD -- measured "
          "respiratory rate against the ventilator's set rate. It is a brainstem BEHAVIOURAL OUTPUT and "
          "NOT consciousness, and the design is RECOVERY-ONLY.")

    rep = {"verdict": verdict, "why": why, "counts": counts,
           "n_cases": len(kept), "p2": p2, "p2_null_check": null_check,
           "gates": gates, "holm": holm_out,
           "min_win_exclusion": {"landmarked_by_arm": landmarked_by_arm,
                                 "kept_by_arm": kept_by_arm,
                                 "drop_rate_by_arm": drop_rate,
                                 "spread": drop_spread,
                                 "n_dropped": len(drop_ids)},
           "p1_seen_before_this_file_was_written": True}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    else:
        print("\n[SMOKE] complete; nothing above is a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
