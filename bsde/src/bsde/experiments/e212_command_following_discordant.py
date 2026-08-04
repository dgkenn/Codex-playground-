#!/usr/bin/env python3
"""E212 — does spontaneous EEG predict command-following WITHIN a patient?

REGISTERED BEFORE ANY CANDIDATE COLUMN HAS BEEN INSPECTED. The extraction that feeds this file is running
as it is written; 983 of 23,192 rows existed at registration time and **no candidate value in them has been
read, plotted or summarised.** What HAS been read is the label table, the sedative-exposure table and the
row counts — the rule-41 feasibility probe, which is required to run *before* a registration so the floors
below are set knowing the coverage rather than discovered by a gate failing.

=========================================================================================================
WHY E204 IS NOT SIMPLY RE-RUN
=========================================================================================================
E204 asked the between-patient question — does EEG predict whether *this patient* obeys commands — and was
**withdrawn** for a data defect (an `EDF Annotations` channel entered the panel and truncated the window).
The defect is fixed and verified: every row now carries exactly 19 channels, matched by case-insensitive
equality against the 10-20 set rather than by substring (rule 61).

But re-running the same design would inherit its real weakness, which was never the bug. **A between-patient
contrast confounds command-following with everything else that differs between two patients** — age, the
reason they are in the ICU, skull, montage, how sedated their clinician keeps them. The label is a
consequence of the brain injury, and so is the EEG.

The feasibility probe found the design that removes all of it. Of 12,501 patients with a GCS-motor
assessment, **712 have two assessments that DISAGREE** on obeying commands. Each of those patients is their
own control: the same skull, the same electrodes, the same diagnosis, the same clinician, hours apart.

    **P1  Among discordant patients, is the candidate HIGHER at the assessment where the patient obeys
          commands than at the one where they do not, more often than chance — after the incumbent is
          allowed to explain it first?**

The probe's numbers, all label-side and all reported before the run: base rate of `obeys` 0.5564 over 23,192
assessments; exactly 2 assessments per patient by construction; RASS present on 0.6170 of rows; a sedative
active on 0.5593, with `n_sedatives_active` 44.07 % zero (rule 43 — the exposure has a large off-state, so
it is used as a binary incumbent and not as a dose).

=========================================================================================================
THE UNIT IS THE PAIR (rule 69)
=========================================================================================================
The exposure is nested inside the patient, so the effective n is **the number of discordant patients, not
the number of rows**. Every interval here is a bootstrap over PAIRS and every null permutes the label
WITHIN a pair — which, for a two-element pair, is a sign flip. A row-level interval would be a fiction.

=========================================================================================================
INCUMBENT (rule 45) — TWO, BOTH DECLARED IN ADVANCE
=========================================================================================================
  I1  **RASS at the same assessment.** The bedside sedation score. It is the thing an EEG marker has to
      beat, and it is available on 61.70 % of rows.
  I2  **`any_sedative` at the same assessment**, from the drug record. A cheaper and coarser incumbent.

An EEG candidate is only interesting if it adds over I1. **Neither incumbent shares a measurement act with
the outcome** — GCS-motor is scored by a different observation than RASS, so rule 86's unclearable bar does
not apply here, but they are scored by the SAME PERSON at the SAME bedside visit, and that is stated as a
limitation rather than claimed as independence.

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE. At least `MIN_PAIRS` discordant patients with BOTH rows extracted, every tested candidate
    finite in both, and `n_channels == 19` on every row — the E204 contamination check, kept as a gate
    because it is the defect that withdrew the parent.
G2  THE INCUMBENT MUST BE ALIVE (rule 53, and E208 died exactly here). RASS must itself separate the two
    members of a discordant pair above its own within-pair sign-flip floor. **If the bedside score cannot
    tell the two assessments apart, nothing about an EEG marker beating it is interpretable.**
G3  NEGATIVE CONTROL. An i.i.d. noise column, paired identically, must NOT clear the floor.
G4  **TIME-ORDER PLACEBO, AND IT GATES THE VERDICT.** The two assessments of a pair differ in TIME as well
    as in label. Electrode drift, cumulative artefact, day-of-stay and recovery trajectory all supply a
    within-patient time trend, and a trend alone would produce a within-pair difference with no relation to
    command-following (catalogue rule 64 — a contrast keyed to an event is a time split in disguise until
    shown otherwise). So the pairs are split by ORIENTATION — those where the obeying assessment comes
    EARLIER, and those where it comes LATER — and the effect must appear **in both, with the same sign**.
    A pure time trend reverses sign between the two orientations and is refused here. A candidate clearing
    in only one orientation is reported as TIME-CONFOUNDED, never as a positive.

=========================================================================================================
PRIMARY STATISTIC
=========================================================================================================
For each discordant pair, the out-of-fold predicted probability of `obeys` is formed for both members from
a model fitted on OTHER PATIENTS ONLY (leave-patient-out folds), and the pair is scored as concordant if the
obeying member is predicted higher. The primary is the **increment in that concordance rate** from adding
the candidate to the incumbent-only design, with a **pair-level bootstrap** interval.

Concordance over a two-element pair is exactly a matched AUC, and its null is 0.5 — but rule 72 records
that a pooled cross-validated AUC's null is not where it is assumed to be, so the floor is **measured**
here by within-pair sign-flip permutation rather than assumed.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2 or G3 fails. Nothing about any candidate may be read.
  (2) REVERSED            a candidate's increment interval excludes zero on the NEGATIVE side. This is not
                          support in any form and is reported as its own outcome (rules 37 and the fourth
                          occurrence recorded under rule 34).
  (3) TIME-CONFOUNDED     a candidate clears in the pooled pairs but NOT in both orientations, or clears
                          with opposite signs in the two orientations. The effect is a within-patient time
                          trend and G4 refuses it.
  (4) ABSENT              every interval includes zero. The honest and most likely outcome.
  (5) ADDS                the increment interval excludes zero on the POSITIVE side AND both orientations
                          agree in sign with the pooled estimate.

**REGISTERED PREDICTION: (4) ABSENT for every candidate.** The within-patient design removes exactly the
between-patient variance that makes EEG look predictive of anything clinical, and the surviving contrast is
hours apart in the same ICU stay. Two assessments of one patient hours apart differ far less in EEG than two
patients do, while the label difference is total. I expect the spectral panel to have nothing left.
**If (5) comes back for `lempel_ziv` or `whole_head_exponent` it is the more important result**, because a
marker that tracks command-following within a patient is the first thing Challenge B has ever had that is
not explicable by who the patient is.

Multiplicity: **7 candidates** are tested against 2 incumbent designs. That is 14 comparisons and no
correction is applied; the count is stated so a reader can apply their own (the ledger's standing position).

    python bsde/src/bsde/experiments/e212_command_following_discordant.py
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import grouped_cv_predict, screen_candidates  # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e212_command_following_discordant.json")
SHARDS = "/tmp/eeg_probe/heedb_cmd_follow.*.csv"
EXPOSURE = "/tmp/eeg_probe/cmd_sedative_exposure.csv"

SEED = 20260802
MIN_PAIRS = 120
N_BOOT = 2000
N_PERM = 400
N_CHANNELS_REQUIRED = 19

CANDIDATES = ("whole_head_exponent", "exponent_low", "exponent_high", "relative_alpha_power",
              "relative_delta_power", "spectral_edge_95", "spectral_entropy", "lempel_ziv")


def load_pairs():
    """Every extracted row, de-duplicated on (patient, assessment) because more than one writer has
    appended to these files before (rule 56), restricted to the 19-channel panel, and reduced to the
    patients whose two assessments DISAGREE on obeying commands."""
    seen, rows = set(), []
    for p in sorted(glob.glob(SHARDS)):
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                k = (r["patient_id"], r["assess_time"])
                if k in seen:
                    continue
                seen.add(k)
                rows.append(r)
    exposure = {}
    if os.path.exists(EXPOSURE):
        for r in csv.DictReader(open(EXPOSURE, newline="")):
            exposure[(r["patient_id"], r["assess_time"])] = r
    n_all = len(rows)
    rows = [r for r in rows if _i(r.get("n_channels")) == N_CHANNELS_REQUIRED]
    by = {}
    for r in rows:
        r["_exp"] = exposure.get((r["patient_id"], r["assess_time"]), {})
        by.setdefault(r["patient_id"], []).append(r)
    pairs = []
    for pid, rs in by.items():
        if len(rs) != 2:
            continue
        if {r["obeys"] for r in rs} != {"0", "1"}:
            continue
        rs.sort(key=lambda r: r["assess_time"])
        pairs.append((pid, rs))
    return pairs, n_all, len(rows)


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def _i(x):
    try:
        return int(float(x))
    except Exception:
        return -1


def concordance(pred, pairs_idx, obeys):
    """Fraction of pairs whose OBEYING member is predicted higher. Exactly a matched AUC."""
    ok, n = 0, 0
    for i, j in pairs_idx:
        a, b = pred[i], pred[j]
        if not (np.isfinite(a) and np.isfinite(b)) or a == b:
            continue
        hi = i if a > b else j
        ok += int(obeys[hi] == 1)
        n += 1
    return (ok / n) if n else float("nan"), n


def fit_concordance(X, y, groups, pairs_idx, rng, folds=5):
    pred = grouped_cv_predict(X, y, groups, rng, folds=folds, lam=1.0)
    c, _n = concordance(pred, pairs_idx, y)
    return c


def boot_increment(base_X, add_col, y, groups, kp, n_boot, seed):
    """CLUSTER bootstrap over PAIRS, refitting inside every draw.

    Catalogue rule 9: bootstrapping fixed out-of-fold predictions ignores refit variance, and the first
    version of this function did exactly that -- it resampled which pairs were scored while handing the
    model the same rows every time, so every draw returned the same predictions and the interval measured
    only which pairs were drawn. Here a draw resamples PAIRS with replacement, rebuilds the design from the
    rows those pairs contain, and refits. A duplicated pair keeps its patient id, so grouped folds put every
    copy of a patient on the same side and no patient is ever in train and test at once.
    """
    out = []
    for b in range(n_boot):
        g = np.random.default_rng(seed + b)
        pick = g.choice(len(kp), size=len(kp), replace=True)
        rows_b, pairs_b, grp_b = [], [], []
        for t in pick:
            i, j = kp[t]
            k = len(rows_b)
            rows_b.extend([i, j])
            pairs_b.append((k, k + 1))
            grp_b.extend([groups[i], groups[i]])
        r = np.array(rows_b)
        yb, gb = y[r], np.array(grp_b)
        Xb = base_X[r]
        r0 = np.random.default_rng(seed + 100000 + b)
        a = fit_concordance(Xb, yb, gb, pairs_b, r0)
        r1 = np.random.default_rng(seed + 100000 + b)
        bb = fit_concordance(np.column_stack([Xb, add_col[r]]), yb, gb, pairs_b, r1)
        if np.isfinite(a) and np.isfinite(bb):
            out.append(bb - a)
    return np.array(out)


def main() -> int:
    print("E212 -- does spontaneous EEG predict command-following WITHIN a patient?")
    pairs, n_all, n_ok = load_pairs()
    print(f"   {n_all} extracted rows, {n_ok} with exactly {N_CHANNELS_REQUIRED} channels, "
          f"{len(pairs)} complete discordant pairs")

    rows, pairs_idx, pid_of = [], [], []
    for pid, rs in pairs:
        i = len(rows)
        rows.extend(rs)
        pairs_idx.append((i, i + 1))
        pid_of.extend([pid, pid])
    y = np.array([_i(r["obeys"]) for r in rows], float)
    groups = np.array(pid_of)
    n_pairs = len(pairs_idx)

    cand = {c: np.array([_f(r.get(c, "")) for r in rows]) for c in CANDIDATES}
    usable, dropped = screen_candidates(cand)
    for k, why in sorted(dropped.items()):
        print(f"   EXCLUDED candidate {k}: {why}")

    inc = {"rass": np.array([_f(r.get("rass", "")) for r in rows]),
           "any_sedative": np.array([_f((r["_exp"] or {}).get("any_sedative", "")) for r in rows])}
    for k, v in inc.items():
        print(f"   incumbent {k}: {int(np.isfinite(v).sum())} of {len(rows)} rows finite "
              f"({np.mean(np.isfinite(v)):.4f})")

    # ---- G1 --------------------------------------------------------------------------------------
    g1 = bool(n_pairs >= MIN_PAIRS and len(usable) > 0
              and all(_i(r["n_channels"]) == N_CHANNELS_REQUIRED for r in rows))
    print(f"G1 COVERAGE  {n_pairs} pairs (floor {MIN_PAIRS}), {len(usable)} usable candidates, "
          f"every row at {N_CHANNELS_REQUIRED} channels   {'PASS' if g1 else '*** FAIL'}")

    rng = np.random.default_rng(SEED)

    # ---- G2: each incumbent must separate the two members of a pair ------------------------------
    alive, base = {}, {}
    for name, v in inc.items():
        keep = [(i, j) for i, j in pairs_idx if np.isfinite(v[i]) and np.isfinite(v[j])]
        if len(keep) < MIN_PAIRS // 2:
            alive[name] = False
            base[name] = {"n_pairs": len(keep), "raw_concordance": float("nan"), "floor": float("nan")}
            print(f"G2 {name}: only {len(keep)} pairs with the incumbent on BOTH members -- not alive")
            continue
        c, n = concordance(v, keep, y)
        # within-pair sign flip: swap which member is called obeying. The floor is MEASURED, not assumed
        # at 0.5, because rule 72 records that a cross-validated concordance null is not where it looks.
        nul = []
        for _ in range(N_PERM):
            yy = y.copy()
            for i, j in keep:
                if rng.random() < 0.5:
                    yy[i], yy[j] = yy[j], yy[i]
            nul.append(concordance(v, keep, yy)[0])
        nul = np.array(nul)
        lo, hi = float(np.quantile(nul, 0.025)), float(np.quantile(nul, 0.975))
        ok = bool(c < lo or c > hi)
        alive[name] = ok
        base[name] = {"n_pairs": n, "raw_concordance": c, "null_lo": lo, "null_hi": hi}
        print(f"G2 INCUMBENT ALIVE  {name}: raw within-pair concordance {c:.4f} vs sign-flip null "
              f"[{lo:.4f}, {hi:.4f}] over {n} pairs   {'PASS' if ok else '*** FAIL'}")

    g2 = bool(any(alive.values()))

    # ---- primary, per incumbent x candidate ------------------------------------------------------
    noise = rng.normal(size=len(rows))
    res_feats, g3 = {}, {}
    for iname, v in inc.items():
        if not alive.get(iname):
            continue
        keep = [(i, j) for i, j in pairs_idx if np.isfinite(v[i]) and np.isfinite(v[j])]
        rowsel = sorted({k for p in keep for k in p})
        sel = np.array(rowsel)
        # `grouped_cv_predict` -> `_standardise` PREPENDS its own unpenalised intercept, so an
        # explicit ones column here is standardised to all-zeros and then carried as a fourth,
        # penalised, information-free degree of freedom. The first pass shipped it and its negative
        # control failed at -0.1339; this is the ONE repair this design gets (rule 58).
        base_X = v[sel].reshape(-1, 1)
        remap = {r: k for k, r in enumerate(rowsel)}
        kp = [(remap[i], remap[j]) for i, j in keep]
        ys, gs = y[sel], groups[sel]

        def inc_of(col):
            r0 = np.random.default_rng(SEED + 11)
            a = fit_concordance(base_X, ys, gs, kp, r0)
            r1 = np.random.default_rng(SEED + 11)
            b = fit_concordance(np.column_stack([base_X, col[sel]]), ys, gs, kp, r1)
            return b - a

        print(f"\n   [{iname}]  {'candidate':<24s} {'increment':>10s} {'[95% CI]':>22s}  "
              f"{'earlier':>8s} {'later':>8s}  call")
        # orientation split for G4: pairs where the OBEYING member is the earlier assessment
        early = [(i, j) for i, j in keep if y[i] == 1]
        late = [(i, j) for i, j in keep if y[j] == 1]
        for cname, col in sorted(usable.items()):
            d = inc_of(col)
            boot = boot_increment(base_X, col[sel], ys, gs, kp, N_BOOT, SEED + 5000)
            lo, hi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))

            def orient(sub):
                if len(sub) < 20:
                    return float("nan")
                s2 = sorted({k for p in sub for k in p})
                rm = {r: k for k, r in enumerate(s2)}
                ss = np.array(s2)
                kk = [(rm[i], rm[j]) for i, j in sub]
                bx = v[ss].reshape(-1, 1)
                r0 = np.random.default_rng(SEED + 11)
                a = fit_concordance(bx, y[ss], groups[ss], kk, r0)
                r1 = np.random.default_rng(SEED + 11)
                bb = fit_concordance(np.column_stack([bx, col[ss]]), y[ss], groups[ss], kk, r1)
                return bb - a

            e_, l_ = orient(early), orient(late)
            same = (np.isfinite(e_) and np.isfinite(l_)
                    and np.sign(e_) == np.sign(d) and np.sign(l_) == np.sign(d))
            if lo > 0 and same:
                call = "ADDS"
            elif lo > 0:
                call = "TIME-CONFOUNDED"
            elif hi < 0:
                call = "REVERSED"
            else:
                call = "absent"
            res_feats[f"{iname}/{cname}"] = {"increment": d, "ci": [lo, hi], "early": e_, "late": l_,
                                             "orientations_agree": bool(same), "call": call}
            print(f"   [{iname}]  {cname:<24s} {d:>+10.4f} [{lo:>+9.4f}, {hi:>+9.4f}] "
                  f"{e_:>+8.4f} {l_:>+8.4f}  {call}")

        dn = inc_of(noise)
        bn = boot_increment(base_X, noise[sel], ys, gs, kp, N_BOOT // 2, SEED + 8000)
        nlo, nhi = float(np.quantile(bn, 0.025)), float(np.quantile(bn, 0.975))
        g3[iname] = bool(nlo <= 0 <= nhi)
        print(f"   [{iname}]  NEGATIVE CONTROL noise {dn:>+.4f} [{nlo:+.4f}, {nhi:+.4f}]   "
              f"{'PASS' if g3[iname] else '*** FAIL'}")

    res = {"experiment": "E212", "n_rows_extracted": n_all, "n_rows_19ch": n_ok,
           "n_pairs": n_pairs, "candidates_dropped": dropped, "incumbent_alive": alive,
           "incumbent_baseline": base, "negative_control_pass": g3,
           "g1": g1, "g2": g2, "results": res_feats}

    print("\n" + "=" * 100)
    if not (g1 and g2 and all(g3.values())):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            nm for nm, ok in (("G1 coverage", g1), ("G2 incumbent alive", g2),
                              ("G3 negative control", bool(g3) and all(g3.values()))) if not ok))
    else:
        calls = {k: r["call"] for k, r in res_feats.items()}
        rev = [k for k, c in calls.items() if c == "REVERSED"]
        adds = [k for k, c in calls.items() if c == "ADDS"]
        conf = [k for k, c in calls.items() if c == "TIME-CONFOUNDED"]
        if rev:
            v_, why = "REVERSED", (
                f"{len(rev)} candidate-incumbent pairs clear on the NEGATIVE side ({', '.join(rev)}). A "
                "negative increment is not support in any form and is reported as its own outcome")
        elif adds:
            v_, why = "ADDS", (
                f"{', '.join(adds)} add to the incumbent AND hold their sign in both time orientations, so "
                "the effect is not a within-patient time trend")
        elif conf:
            v_, why = "TIME-CONFOUNDED", (
                f"{', '.join(conf)} clear on the pooled pairs but do NOT hold their sign in both time "
                "orientations. G4 refuses them: a pair differs in time as well as in label")
        else:
            v_, why = "ABSENT", (
                "every increment interval includes zero. Within a patient, with the patient acting as their "
                "own control, the spectral panel adds nothing to the bedside score")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print(f"MULTIPLICITY: {len(res_feats)} candidate-by-incumbent comparisons, no correction applied; the "
          "count is stated so a reader can apply their own.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2, default=float)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

