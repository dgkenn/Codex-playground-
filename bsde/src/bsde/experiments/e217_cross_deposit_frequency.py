#!/usr/bin/env python3
"""E217 — E214's estimand change: does frequency sensitivity predict CROSS-DEPOSIT disagreement?

REGISTERED BEFORE ANY CROSS-DEPOSIT EFFECT HAS BEEN COMPUTED.

=========================================================================================================
WHY THIS EXPERIMENT EXISTS, IN THE WORDS OF ITS PARENT'S LEDGER ROW
=========================================================================================================
E214 asked whether a measure's sensitivity to WHERE IN FREQUENCY the spectrum sits predicts how badly its
depth relationship disagrees between propofol and sevoflurane. It passed and it was weak — rho +0.5706 at
p = 0.046 over ten points, not robust to dropping any single feature, and with a placebo that was neither
computed on the same rows as the primary nor independent of it (the two axes correlate -0.6500). Its own
ledger row names the successor:

    *the successor must change the ESTIMAND, not the threshold: cross-DEPOSIT transport, which E214's own
    scope names as untested, would widen the panel and give a placebo that can be matched.*

That is this file, and nothing about the threshold, the sensitivity measure or the direction rule moves.

**What widens.** Four deposits carry an ordered depth or consciousness contrast AND share a feature panel:
`chennu_features_v3`, `ds004541_v2`, `ds005620_full`, `sleep_edfx_five_stage`. Their feature intersection is
**17 measures**, against E214's 10 — and cross-deposit disagreement spans device, montage, reference,
sampling rate, population and drug at once, where E214 varied only the drug.

    **P1  Across the 17 shared features, is frequency-shift sensitivity POSITIVELY correlated with
          DISAGREEMENT BETWEEN DEPOSITS in the direction and size of the deep-versus-light effect?**

=========================================================================================================
THE CONTRASTS, DECLARED BEFORE ANY VALUE IS READ
=========================================================================================================
Each deposit contributes ONE binary deep-versus-light contrast. Where a deposit's ordering is not
established by the deposit itself, the ambiguous level is NOT used rather than assumed into an order:

    ds005620      light = `task-awake`            deep = `task-sed` and `task-sed2` POOLED
                  (pooled deliberately: nothing in the deposit establishes that sed2 is deeper than sed,
                   so they are not ordered against each other, only against awake)
    ds004541      light = baseline + awake_pre_drug     deep = post_loc + pre_roc
                  (`post_roc` is EXCLUDED -- the subject is conscious again, so the phase label is not
                   monotone in depth and treating it as the deep end would be an error of the kind
                   catalogue rule 61 exists to prevent)
    sleep_edfx    light = W                       deep = N3
                  (REM is EXCLUDED: it is not ordered against N1-N3 on this ladder)
    chennu        light = sedation level 1        deep = sedation level 4

**CHENNU IS PARTIALLY EXPOSED AND IT IS DECLARED.** E208 computed out-of-fold INCREMENTS over an incumbent
for four candidates on chennu and printed them, which is why no successor may present chennu as a fresh test
of that estimand. The quantity this file computes — the within-deposit sign and size of a feature's
deep-minus-light effect — was never computed or printed there. That is a different quantity, and the honest
position is not that chennu is clean but that **the primary is reported BOTH WITH AND WITHOUT it**, and if
the two disagree the version without chennu is the one that counts.

=========================================================================================================
STATISTIC
=========================================================================================================
Within each deposit, all rows of both arms are ranked TOGETHER and only then split (E165's capability gate
caught a factor-77 error from ranking two blocks separately, and rule 73 records it). The standardised
effect is

    e(f, d) = median(rank | deep) - median(rank | light),  in units of that deposit's pooled rank spread

and cross-deposit disagreement is

    **D(f) = the standard deviation of e(f, d) across deposits.**

A measure whose depth response is the same everywhere has D near zero. A measure that says opposite things
in two deposits has a large one. **D involves no model, no fitting and no held-out set** — which is the
point, because E214's weakness was that it had only ten summary numbers and this has 17 built from every
subject in four deposits.

**THE PLACEBO IS MATCHED THIS TIME.** E214's amplitude-gain placebo ran on 9 features while its primary ran
on 10, and on the matched 9 the primary did not clear. Here both axes are restricted to the features where
BOTH are finite, before either correlation is computed, and the restricted set is printed.

=========================================================================================================
GATES
=========================================================================================================
G1  every deposit contributes >= `MIN_SUBJECTS` subjects and both arms are non-empty.
G2  **THE DEPTH EFFECT MUST EXIST** (rule 53). In each deposit, at least `MIN_ALIVE_FEATURES` features must
    show a deep-versus-light effect beyond a within-deposit label permutation floor. A deposit where no
    feature responds to depth contributes only noise to D, and pooling it would manufacture disagreement.
G3  >= `MIN_FEATURES` features finite in every deposit, with exclusions NAMED (rules 14, 74). Rows whose
    fields equal their own column names -- shard-concatenation header artefacts, present in three tables in
    this repository -- are dropped by the shared loader and the count reported.
G4  **MATCHED PLACEBO**: the primary and the amplitude-gain placebo are computed on the IDENTICAL feature
    set, and the placebo must predict D strictly less well.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2, G3 or G4's matching requirement fails.
  (2) INVERTED           the correlation's null percentile is at or below 5 — frequency-sensitive measures
                         agree BETTER across deposits. E214 is refuted on a wider panel and a harder
                         estimand, and that is reported as its own outcome.
  (3) ABSENT             the percentile is inside the null's central range. E214's finding does not
                         generalise beyond the two-agent contrast it was measured on.
  (4) NOT FREQUENCY-SPECIFIC  the primary clears but the matched amplitude placebo does as well or better.
  (5) FREQUENCY PREDICTS DISAGREEMENT   the primary is above the 95th percentile AND strictly beats the
                         matched placebo, both with and without chennu.

**REGISTERED PREDICTION: (3) ABSENT, and I am close to even between (3) and (5).** The reasoning for (3):
E214 was weak, and cross-deposit disagreement is driven by device, montage and population as much as by
frequency, so the signal has more competition here. The reasoning for (5): the mechanism is arithmetic
rather than biological — a fixed frequency window mismeasures a spectrum that has slid, and spectra slide
between populations and montages as readily as between drugs — so if the effect is real at all it should be
LARGER here, not smaller. **Those two readings make opposite predictions about the effect size relative to
E214's, and that comparison is the most informative thing this file can produce**, so it is reported
whatever the verdict.

**SCOPE.** Four deposits give four points per feature, so D is a standard deviation over four numbers and is
noisy by construction. This bounds what any verdict can mean and is stated in advance rather than discovered.

    python bsde/src/bsde/experiments/e217_cross_deposit_frequency.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import spearman, read_rows                            # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e217_cross_deposit_frequency.json")
E214_JSON = os.path.join(RESULTS, "e214_frequency_sensitivity_transport.json")

SEED = 20260802
MIN_SUBJECTS = 8
MIN_FEATURES = 12
MIN_ALIVE_FEATURES = 3
N_PERM = 40000
PERM_ALIVE = 2000

META = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples",
        "label", "channels", "sfreq_eeg", "window_index", "start_seconds"}


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def deposits():
    """Each deposit's (light rows, deep rows), by contrasts declared in the docstring before any read."""
    out, dropped = {}, {}

    rows, d = read_rows(os.path.join(RESULTS, "ds005620_full.csv"))
    dropped["ds005620"] = d
    rows = [r for r in rows if r.get("status") == "ok"]
    out["ds005620"] = ([r for r in rows if r.get("meta_task") == "awake"],
                       [r for r in rows if r.get("meta_task") in ("sed", "sed2")])

    rows, d = read_rows(os.path.join(RESULTS, "ds004541_v2.csv"))
    dropped["ds004541"] = d
    rows = [r for r in rows if r.get("status") == "ok"]
    out["ds004541"] = ([r for r in rows if r.get("meta_phase") in ("baseline", "awake_pre_drug")],
                       [r for r in rows if r.get("meta_phase") in ("post_loc", "pre_roc")])

    rows, d = read_rows(os.path.join(RESULTS, "sleep_edfx_five_stage.csv"))
    dropped["sleep_edfx"] = d
    rows = [r for r in rows if r.get("status", "ok") == "ok" and "@" in r.get("recording_id", "")]
    stage = {r["recording_id"]: r["recording_id"].rsplit("@", 1)[1] for r in rows}
    out["sleep_edfx"] = ([r for r in rows if stage[r["recording_id"]] == "W"],
                         [r for r in rows if stage[r["recording_id"]] == "N3"])

    rows, d = read_rows(os.path.join(RESULTS, "chennu_features_v3.csv"))
    dropped["chennu"] = d
    rows = [r for r in rows if r.get("status", "ok") == "ok"]
    out["chennu"] = ([r for r in rows if _f(r.get("meta_sedation_level")) == 1.0],
                     [r for r in rows if _f(r.get("meta_sedation_level")) == 4.0])
    return out, dropped


def effect(light, deep, f, rng=None, permute=False):
    """Standardised deep-minus-light effect, ranking BOTH arms together and only then splitting (rule 73)."""
    vl = np.array([_f(r.get(f, "")) for r in light])
    vd = np.array([_f(r.get(f, "")) for r in deep])
    allv = np.concatenate([vl, vd])
    m = np.isfinite(allv)
    if m.sum() < 6 or np.unique(allv[m]).size < 3:
        return float("nan")
    order = np.argsort(np.argsort(np.where(m, allv, np.nanmax(allv[m]) + 1.0)))
    rk = order.astype(float)
    rk[~m] = np.nan
    lab = np.concatenate([np.zeros(vl.size), np.ones(vd.size)])
    if permute:
        lab = rng.permutation(lab)
    a, b = rk[(lab == 1) & m], rk[(lab == 0) & m]
    if a.size < 3 or b.size < 3:
        return float("nan")
    spread = np.nanstd(rk[m])
    return float((np.median(a) - np.median(b)) / (spread + 1e-12))


def main() -> int:
    print("E217 — does frequency sensitivity predict CROSS-DEPOSIT disagreement about depth?")
    e214 = json.load(open(E214_JSON))
    S, A = e214["S"], e214["A"]

    dep, dropped_hdr = deposits()
    feats = None
    for name, (lo, hi) in dep.items():
        cols = {c for c in (lo + hi)[0] if c not in META and not c.startswith("meta_")}
        feats = cols if feats is None else (feats & cols)
    feats = sorted(f for f in feats if f in S)
    print(f"   feature intersection carrying a synthetic sensitivity: {len(feats)}")
    for name, (lo, hi) in dep.items():
        subs = len({r.get("subject", "") for r in lo + hi})
        print(f"   {name:<12s} light {len(lo):4d}  deep {len(hi):4d}  subjects {subs:4d}"
              + (f"   [{dropped_hdr[name]} header-artefact rows dropped]" if dropped_hdr[name] else ""))

    g1 = all(len(lo) > 0 and len(hi) > 0
             and len({r.get("subject", "") for r in lo + hi}) >= MIN_SUBJECTS
             for lo, hi in dep.values())
    print(f"G1 every deposit has both arms and >= {MIN_SUBJECTS} subjects   {'PASS' if g1 else '*** FAIL'}")

    print("\nG2 THE DEPTH EFFECT MUST EXIST IN EACH DEPOSIT (rule 53)")
    E, alive_counts = {}, {}
    rng = np.random.default_rng(SEED)
    for name, (lo, hi) in dep.items():
        n_alive = 0
        for f in feats:
            e = effect(lo, hi, f)
            E.setdefault(f, {})[name] = e
            if not np.isfinite(e):
                continue
            nul = np.array([abs(effect(lo, hi, f, rng, permute=True)) for _ in range(200)])
            if abs(e) > np.quantile(nul[np.isfinite(nul)], 0.95):
                n_alive += 1
        alive_counts[name] = n_alive
        print(f"   {name:<12s} {n_alive} of {len(feats)} features beyond their within-deposit "
              f"permutation p95")
    # G2 IS PER-ARM, NOT GLOBAL (catalogue rule 71). The first version tested every deposit and refused
    # the whole file when one failed -- including the arm that does not use that deposit. Rule 71 was
    # written for the mirror of this: a verdict branch firing on a gate passed by some OTHER arm. Both
    # directions are the same error, which is that a gate belongs to the arm whose claim it licenses.
    g2_arm = {}
    print(f"   (floor {MIN_ALIVE_FEATURES} per deposit; the gate is evaluated PER ARM -- rule 71)")

    def disagreement(names):
        out = {}
        for f in feats:
            v = np.array([E[f].get(n, np.nan) for n in names], float)
            out[f] = float(np.std(v)) if np.isfinite(v).all() else float("nan")
        return out

    res = {"experiment": "E217", "features": feats, "effects": E,
           "deposits": {k: {"n_light": len(v[0]), "n_deep": len(v[1]),
                            "n_subjects": len({r.get("subject", "") for r in v[0] + v[1]})}
                        for k, v in dep.items()},
           "header_rows_dropped": dropped_hdr, "alive_counts": alive_counts, "arms": {}}

    for tag, names in (("all_four", sorted(dep)), ("without_chennu", sorted(set(dep) - {"chennu"}))):
        g2_arm[tag] = all(alive_counts[n] >= MIN_ALIVE_FEATURES for n in names)
        D = disagreement(names)
        # G4: the primary and the placebo are computed on the IDENTICAL feature set, chosen before either
        # correlation exists. E214's placebo ran on 9 features against a primary on 10 and that mismatch
        # was the reason its pass did not survive matching.
        use = [f for f in feats if np.isfinite(D[f]) and np.isfinite(S[f]) and np.isfinite(A.get(f, np.nan))]
        y = [D[f] for f in use]
        xs = [S[f] for f in use]
        az = [A[f] for f in use]
        rho = spearman(xs, y)
        rho_a = spearman(az, y)
        nul = np.array([spearman(list(rng.permutation(xs)), y) for _ in range(N_PERM)])
        nul_a = np.array([spearman(list(rng.permutation(az)), y) for _ in range(N_PERM)])
        pct = float(np.mean(nul <= rho) * 100.0)
        pct_a = float(np.mean(nul_a <= rho_a) * 100.0)
        res["arms"][tag] = {"deposits": names, "n_features": len(use), "features_used": use,
                            "disagreement": {f: D[f] for f in use},
                            "rho_primary": rho, "pct_primary": pct,
                            "rho_placebo": rho_a, "pct_placebo": pct_a,
                            "one_sided_p": float(np.mean(nul >= rho)),
                            "beats_placebo": bool(pct > pct_a)}
        print(f"\n[{tag}]  {len(use)} features on BOTH axes (matched)")
        print(f"   {'feature':<28s} {'S':>7s} {'A':>7s} {'D(disagree)':>12s}")
        for f in sorted(use, key=lambda k: -D[k]):
            print(f"   {f:<28s} {S[f]:>7.4f} {A[f]:>7.4f} {D[f]:>12.4f}")
        print(f"   PRIMARY rho(S, D) = {rho:+.4f}  percentile {pct:.1f}%  one-sided p "
              f"{float(np.mean(nul >= rho)):.4f}")
        print(f"   PLACEBO rho(A, D) = {rho_a:+.4f}  percentile {pct_a:.1f}%")

    a4 = res["arms"]["all_four"]
    aw = res["arms"]["without_chennu"]
    g3 = bool(len(a4["features_used"]) >= MIN_FEATURES)
    g4 = bool(a4["beats_placebo"] and aw["beats_placebo"])
    g2 = bool(g2_arm.get("all_four") and g2_arm.get("without_chennu"))
    res["g2_per_arm"] = g2_arm
    for tag, ok in g2_arm.items():
        print(f"G2 [{tag}] {'PASS' if ok else '*** FAIL'}"
              + ("" if ok else "  -- deposits failing: "
                 + ", ".join(n for n in res['arms'][tag]['deposits']
                             if alive_counts[n] < MIN_ALIVE_FEATURES)))
    res["g1"], res["g2"], res["g3"], res["g4"] = g1, g2, g3, g4
    print(f"\nG3 >= {MIN_FEATURES} matched features   {'PASS' if g3 else '*** FAIL'}")
    print(f"G4 matched placebo beaten in BOTH arms   {'PASS' if g4 else '*** FAIL'}")

    print("\n" + "=" * 100)
    if not (g1 and g2 and g3):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 cohort", g1), ("G2 depth effect exists", g2),
                            ("G3 matched features", g3)) if not ok))
    elif a4["pct_primary"] <= 5.0:
        v_, why = "INVERTED", (
            f"frequency-sensitive measures agree BETTER across deposits, not worse "
            f"(rho {a4['rho_primary']:+.4f}, {a4['pct_primary']:.1f}th percentile). E214 is refuted on a "
            "wider panel and a harder estimand")
    elif a4["pct_primary"] < 95.0 or aw["pct_primary"] < 95.0:
        v_, why = "ABSENT", (
            f"rho {a4['rho_primary']:+.4f} at the {a4['pct_primary']:.1f}th percentile with all four "
            f"deposits and {aw['rho_primary']:+.4f} at the {aw['pct_primary']:.1f}th without chennu. "
            "E214's finding does not generalise from the two-agent contrast to disagreement between "
            "deposits")
    elif not g4:
        v_, why = "NOT FREQUENCY-SPECIFIC", (
            f"the primary clears in both arms but the MATCHED amplitude-gain placebo does as well or "
            f"better ({a4['rho_placebo']:+.4f} at {a4['pct_placebo']:.1f}%). Whatever predicts "
            "cross-deposit disagreement here, it is not frequency specifically")
    else:
        v_, why = "FREQUENCY PREDICTS DISAGREEMENT", (
            f"rho {a4['rho_primary']:+.4f} ({a4['pct_primary']:.1f}th percentile) with all four deposits "
            f"and {aw['rho_primary']:+.4f} ({aw['pct_primary']:.1f}th) without chennu, beating a MATCHED "
            "amplitude placebo in both. A measure's dependence on where the spectrum sits predicts its "
            "disagreement across device, montage, population and drug at once")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print(f"\nCOMPARISON TO E214, reported whatever the verdict because the two readings of this "
          f"experiment make opposite predictions about it:\n"
          f"   E214 (two agents, one deposit, 10 features): rho +0.5706\n"
          f"   E217 (four deposits, {len(a4['features_used'])} features):     rho "
          f"{a4['rho_primary']:+.4f}")
    print("=" * 100)
    print("SCOPE: four deposits give four points per feature, so D is a standard deviation over four\n"
          "  numbers and is noisy by construction. chennu is PARTIALLY EXPOSED -- E208 printed\n"
          "  increments over an incumbent for four candidates there -- so the arm without it is the\n"
          "  one that counts if the two disagree.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2, default=float)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
