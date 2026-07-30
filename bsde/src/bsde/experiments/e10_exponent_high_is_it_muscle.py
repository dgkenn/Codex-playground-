#!/usr/bin/env python3
"""E10 — the 20-40 Hz exponent's best alternative explanation is that it is a muscle measure.

WHY THIS EXPERIMENT EXISTS, STATED BEFORE ANY NUMBER IS READ.

E08 found `exponent_high` (the aperiodic slope fitted over 20-40 Hz) at signed AUC 0.863 [0.790, 0.948] for
baseline versus moderate sedation on Chennu — by a wide margin the best-performing candidate this project has
produced, and the only one that has survived its own declared direction. §9.13 attributed the 1-40 Hz
exponent's failure to band-averaging: 1-20 Hz and 20-40 Hz carry OPPOSITE dose responses, so a fit spanning
both cancels.

Then I noticed that `EMG_BAND` is (20.0, 45.0).

`exponent_high` and the project's own muscle proxy read the SAME FREQUENCIES. That is not a loose analogy;
the slope of the 20-40 Hz tail and the fraction of power in 20-45 Hz are close to being two parameterisations
of one quantity. And the confound has the right SIGN for free: propofol reduces muscle tone, less muscle means
less 20-45 Hz power, less high-frequency power means a STEEPER 20-40 Hz slope, and steeper is exactly the
direction `exponent_high` declares for unconsciousness. A pure EMG artefact would reproduce the finding
without any cortical claim at all.

Error-catalogue rule 28 is the reason this is worth a whole experiment: this project has already
over-predicted three redundant measures by assuming that two things measured differently must be measuring
different things. Here they are not even measured differently — they are measured over the same band.

THE ASYMMETRY, REGISTERED IN ADVANCE, BECAUSE IT DECIDES WHAT A NULL MEANS.
This experiment can REFUTE `exponent_high` strongly and can CLEAR it only weakly. The Chennu deposit arrives
filtered 0.5-45 Hz, and `test_but_a_45hz_lowpass_DOES_degrade_realistically_peaked_emg` measured that a 45 Hz
low-pass substantially reduces (without eliminating) detectability of EMG peaked at 70 Hz, where surface
muscle actually lives. So the EMG proxy available here is a DEGRADED instrument. If it fires, the confound is
real. If it does not fire, that is weak evidence of no muscle rather than evidence of no muscle (§9.11), and
the conclusion must say so in those words.

THE RULE FOR CALLING IT A CONFOUND — both clauses, per the standing two-clause rule:
    (a) the nuisance must track the outcome at least as well as the candidate does, AND
    (b) the candidate's association must vanish when the nuisance is held constant.
Clause (a) alone is correlation between two markers of the same state; clause (b) alone can fire on a valid
marker whenever the nuisance is partly the state itself, which `residual_auc`'s own docstring warns about.

REGISTERED PREDICTIONS, written before reading any correlation or residual:
    P1  `exponent_high` and `emg_beta_gamma_fraction` are STRONGLY related, |rho| >= 0.5, and NEGATIVELY so
        (a steeper high-band slope means less relative high-band power). This is close to arithmetic given
        that they share a band; I am registering it so that if it FAILS I have to explain why two measures of
        the same frequencies came apart, rather than quietly moving on.
    P2  `exponent_high`'s signed AUC is ATTENUATED by EMG residualisation by more than 0.05, but SURVIVES —
        its residual CI still excludes 0.5. I am predicting partial confounding rather than total, because
        the 20-40 Hz slope also responds to genuine cortical beta/gamma changes under propofol. This is the
        prediction most likely to be wrong and it is stated with a number so that it can be.
    P3  CONTROL, AND IT GATES P2. `relative_delta_power` (1-4 Hz, three octaves below the EMG band) must NOT
        be materially attenuated by the same residualisation — change in signed AUC below 0.05. If
        residualising EMG also destroys a 1-4 Hz marker, then the procedure is removing sedation itself
        rather than muscle, and P2's attenuation carries no information about muscle whatsoever. Without
        this control the whole experiment is uninterpretable, which is why it is a gate and not a footnote.
    P4  MACHINERY GATE, EVALUATED FIRST AND ABLE TO VOID EVERYTHING BELOW IT. Both `exponent_high` and the
        EMG proxies must actually VARY across the analysis cohort, and the cohort must contain both classes.
        Rule 32 exists because this project once compared two predictors across two whole ledger entries
        before noticing one of them was constant in the stratum being compared.

    FALSIFICATION OF THE LEAD: if `exponent_high`'s residual CI spans 0.5 while `relative_delta_power`'s does
    not, the best result this project has is a muscle artefact and must be withdrawn as a lead. That outcome
    is reportable and this script will print it in those terms.

SCOPE AND DENOMINATOR. 20 healthy volunteers, one drug, one site, average-referenced, 0.5-45 Hz, levels 1 vs
3. The search space is the registered candidate count printed below, and the analytic degrees of freedom are
NOT 1: E09 measured a lower bound of 72 for the exponent family alone. Both denominators are printed beside
every number.

WHAT THIS DOES NOT CLOSE. `exponent_high`'s own fit band (20-40 Hz) was chosen AFTER seeing that 1-20 and
1-40 behaved differently, and E09's sweep varied only fit_lo in {1,2,3} — it never swept a high-band fit. That
gap is real and is not addressed here; it needs its own extraction pass and its own pre-registration.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                        # noqa: E402
from bsde.candidates.seed import seed_registry                                        # noqa: E402
from bsde.verifier.stats import (directional_auc, cluster_bootstrap_ci, spearman,     # noqa: E402
                                 _midranks)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "chennu_features_v3.csv")

TARGET = "exponent_high"
NUISANCES = ("emg_beta_gamma_fraction", "emg_index", "emg_kurtosis")
CONTROL = "relative_delta_power"
ALSO_REPORT = ("whole_head_exponent", "exponent_low", "lempel_ziv", "spectral_entropy")
ATTENUATION_THRESHOLD = 0.05
EMG_DIRECTION = "lower"
"""Declared a priori from physiology, not read off the data: propofol reduces muscle tone, so every muscle
proxy should be LOWER under sedation. Fixed here as a constant so that it is one decision made once, visible
in the diff, rather than a per-proxy choice made while looking at results."""


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def col(rows, name):
    return np.array([_f(r.get(name, "")) for r in rows], float)


def residualise(x: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Midrank residual of `x` on `v`, linear plus quadratic — the same construction `residual_auc` uses.

    Reimplemented here rather than called through `residual_auc` for one reason: the CI must be computed with
    the residualisation REFITTED inside each bootstrap resample. Residualising once on the full sample and
    then bootstrapping the fixed residuals treats the nuisance fit as known and understates the interval,
    which is the same mistake error-catalogue rule 9 records for out-of-bag AUC increments.
    """
    rx, rv = _midranks(x), _midranks(v)
    rv = (rv - rv.mean()) / (rv.std() if rv.std() > 1e-12 else 1.0)
    A = np.column_stack([np.ones(rx.size), rv, rv ** 2])
    try:
        beta, *_ = np.linalg.lstsq(A, rx, rcond=None)
    except np.linalg.LinAlgError:
        return np.full_like(rx, np.nan)
    return rx - A @ beta


def scored(y, x, v, direction):
    """Signed AUC of `x` against `y` after holding `v` constant. `v=None` means no residualisation."""
    ok = np.isfinite(x) & np.isfinite(y) & (np.isfinite(v) if v is not None else True)
    if ok.sum() < 10 or len(np.unique(y[ok])) < 2:
        return float("nan")
    xx = residualise(x[ok], v[ok]) if v is not None else x[ok]
    if not np.isfinite(xx).all():
        return float("nan")
    # After residualising on midranks the sign convention is preserved: the residual still increases with x
    # at fixed v, so the candidate's declared direction applies unchanged.
    return directional_auc(y[ok], xx, direction)


def main() -> int:
    seed_registry()
    n_space = REGISTRY.search_space_size()
    print("E10 — is the 20-40 Hz exponent a muscle measure?")
    print(f"   search space {n_space} registered candidates; analytic dof >= 72 (E09 lower bound), NOT 1")
    if not os.path.exists(TABLE):
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    with open(TABLE, newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status") == "ok"]

    lvl = np.array([_f(r.get("meta_sedation_level")) for r in rows])
    keep = np.isin(lvl, (1.0, 3.0))
    rows = [r for r, k in zip(rows, keep) if k]
    y = (lvl[keep] == 3.0).astype(float)
    subj = np.array([r.get("subject", "") for r in rows])
    print(f"   rows {len(rows)}   subjects {len(set(subj))}   "
          f"baseline {int((y == 0).sum())} / moderate {int((y == 1).sum())}")

    # ============================ P4 — MACHINERY GATE, BEFORE ANYTHING ELSE ==========================
    print("\n" + "=" * 100); print("P4 — MACHINERY GATE (rule 32: does everything actually VARY here?)")
    print("=" * 100)
    gate_ok, gate_msgs = True, []
    if len(np.unique(y)) < 2:
        gate_ok = False; gate_msgs.append("outcome is constant")
    for nm in (TARGET, CONTROL) + NUISANCES:
        v = col(rows, nm)
        n_fin = int(np.isfinite(v).sum())
        n_uni = len(np.unique(v[np.isfinite(v)]))
        ok = n_fin >= 20 and n_uni > 5
        gate_ok &= ok
        print(f"   {nm:28s} finite {n_fin:4d}/{len(rows)}  distinct {n_uni:4d}  {'ok' if ok else '*** FAILS'}")
        if not ok:
            gate_msgs.append(f"{nm}: finite={n_fin} distinct={n_uni}")
    if not gate_ok:
        print(f"\n   *** MACHINERY GATE FAILED: {gate_msgs}")
        print("   No verdict is issued. A failed precondition makes the downstream answer ABSENT, not")
        print("   negative (error-catalogue rule 31).")
        json.dump({"experiment": "E10", "gate_passed": False, "gate_failures": gate_msgs},
                  open(os.path.join(RESULTS, "e10_exponent_high_emg.json"), "w"), indent=2)
        return 1
    print("\n   gate PASSED — every quantity varies in the cohort being compared")

    rng = np.random.default_rng(20260730)

    # ============================ P1 — do they measure the same thing? ===============================
    print("\n" + "=" * 100); print("P1 — REDUNDANCY: does the 20-40 Hz slope track the 20-45 Hz muscle proxy?")
    print("=" * 100)
    tgt = col(rows, TARGET)
    rho = {}
    for nm in NUISANCES:
        r = spearman(tgt, col(rows, nm))
        rho[nm] = float(r)
        print(f"   rho({TARGET}, {nm:26s}) = {r:+.3f}")
    p1 = np.isfinite(rho[NUISANCES[0]]) and abs(rho[NUISANCES[0]]) >= 0.5 and rho[NUISANCES[0]] < 0

    # ============================ clause (a) — does EMG track sedation at all? =======================
    print("\n" + "=" * 100)
    print("CLAUSE (a) — does the nuisance track the outcome at least as well as the candidate?")
    print("=" * 100)
    d_t = REGISTRY.get(TARGET).predicted("unconscious_vs_awake")
    a_t = scored(y, tgt, None, d_t)
    lo_t, hi_t = cluster_bootstrap_ci(
        lambda i: scored(y[i], tgt[i], None, d_t), subj, rng, reps=2000)[:2]
    print(f"   {TARGET:28s} declared {d_t:6s}  AUC {a_t:.3f} [{lo_t:.3f}, {hi_t:.3f}]")
    emg_auc = {}
    for nm in NUISANCES:
        v = col(rows, nm)
        # EMG_DIRECTION is fixed a priori and is NOT read off the data. The first draft of this script took
        # max() over both directions, which chooses the sign from the sample and then asks whether the result
        # exceeds 0.5 — a question it has already forced to be yes, since the two AUCs sum to 1 and the max
        # is >= 0.5 by construction. The bootstrap lower bound inherits that bias and clause (a) would have
        # fired on noise. Propofol reduces muscle tone, so every muscle proxy is declared LOWER under
        # sedation, from physiology, before the number is read.
        a = scored(y, v, None, EMG_DIRECTION)
        lo, hi = cluster_bootstrap_ci(
            lambda i: scored(y[i], v[i], None, EMG_DIRECTION), subj, rng, reps=2000)[:2]
        emg_auc[nm] = {"auc": float(a), "ci": [float(lo), float(hi)], "declared": EMG_DIRECTION}
        if hi < 0.5:
            note = "   <- moves OPPOSITE to declared (muscle RISES with sedation?)"
        elif lo > 0.5:
            note = "   <- tracks sedation in the declared direction"
        else:
            note = "   <- spans 0.5"
        print(f"   {nm:28s} declared {EMG_DIRECTION:6s}  AUC {a:.3f} [{lo:.3f}, {hi:.3f}]{note}")
    clause_a = any(e["ci"][0] > 0.5 and e["auc"] >= a_t for e in emg_auc.values())
    print(f"\n   clause (a) — a nuisance tracks the outcome AT LEAST AS WELL as the candidate: "
          f"{'YES' if clause_a else 'NO'}")

    # ============================ P2/P3 — clause (b), residualisation ================================
    print("\n" + "=" * 100)
    print("CLAUSE (b) — does the association survive holding the muscle proxy constant?")
    print("=" * 100)
    print(f"   {'candidate':28s} {'nuisance':26s} {'raw':>7s} {'residual AUC':>22s}  {'delta':>7s}")
    resid = {}
    for cname in (TARGET, CONTROL) + ALSO_REPORT:
        cand = REGISTRY.get(cname)
        d = cand.predicted("unconscious_vs_awake")
        x = col(rows, cname)
        if d not in ("higher", "lower") or not np.isfinite(x).any():
            continue
        raw = scored(y, x, None, d)
        resid[cname] = {"declared": d, "raw_auc": float(raw), "by_nuisance": {}}
        for nm in NUISANCES:
            v = col(rows, nm)
            a = scored(y, x, v, d)
            lo, hi = cluster_bootstrap_ci(
                lambda i: scored(y[i], x[i], v[i], d), subj, rng, reps=2000)[:2]
            survives = lo > 0.5
            resid[cname]["by_nuisance"][nm] = {"auc": float(a), "ci": [float(lo), float(hi)],
                                               "delta": float(a - raw), "survives": bool(survives)}
            mark = "" if survives else "   *** no longer excludes 0.5"
            print(f"   {cname:28s} {nm:26s} {raw:7.3f} {a:8.3f} [{lo:.3f}, {hi:.3f}] "
                  f"{a - raw:+7.3f}{mark}")

    tgt_worst = min(resid[TARGET]["by_nuisance"].values(), key=lambda e: e["auc"])
    ctl_worst = min(resid[CONTROL]["by_nuisance"].values(), key=lambda e: e["auc"])
    p2 = (abs(tgt_worst["delta"]) > ATTENUATION_THRESHOLD) and tgt_worst["survives"]
    p3 = abs(ctl_worst["delta"]) <= ATTENUATION_THRESHOLD

    # ============================ verdict ============================================================
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 exponent_high strongly & negatively tracks the EMG proxy : "
          f"{'MET' if p1 else 'NOT MET'} (rho {rho[NUISANCES[0]]:+.3f}, needed <= -0.5)")
    print(f"   P2 attenuated by > {ATTENUATION_THRESHOLD} yet still excludes 0.5      : "
          f"{'MET' if p2 else 'NOT MET'} (worst delta {tgt_worst['delta']:+.3f}, "
          f"residual CI [{tgt_worst['ci'][0]:.3f}, {tgt_worst['ci'][1]:.3f}])")
    print(f"   P3 CONTROL relative_delta_power NOT attenuated (gate)       : "
          f"{'MET' if p3 else 'NOT MET'} (worst delta {ctl_worst['delta']:+.3f})")
    print(f"   P4 machinery gate                                           : MET")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p3:
        verdict = "UNINTERPRETABLE"
        print("   The CONTROL was attenuated too. Residualising the EMG proxy removes sedation itself, not")
        print("   muscle, so nothing here distinguishes a muscle artefact from a real marker. No claim is")
        print("   made about exponent_high in either direction (rule 31: absent, not negative).")
    elif clause_a and not tgt_worst["survives"]:
        verdict = "REFUTED_AS_MUSCLE"
        print("   BOTH CLAUSES FIRED. The muscle proxy tracks sedation at least as well as exponent_high,")
        print("   and exponent_high's association does not survive holding it constant, while the 1-4 Hz")
        print("   control is untouched. THE BEST RESULT THIS PROJECT HAS IS A MUSCLE ARTEFACT and is")
        print("   withdrawn as a lead.")
    elif not tgt_worst["survives"]:
        verdict = "ATTENUATED_BUT_CLAUSE_A_FAILED"
        print("   exponent_high does not survive residualisation, but the nuisance does NOT track sedation")
        print("   better than it does, so the two-clause rule is not satisfied. Residualising on a measure")
        print("   that shares a frequency band can remove the signal without the confound being real —")
        print("   this is the case residual_auc's own docstring warns about. Flagged, not concluded.")
    else:
        verdict = "SURVIVES_WEAKLY"
        print("   exponent_high survives residualisation on every muscle proxy available, and the 1-4 Hz")
        print("   control behaves as it should. THIS CLEARS IT ONLY WEAKLY. The deposit is filtered")
        print("   0.5-45 Hz and the EMG proxy measured here is a degraded instrument (§9.11); a negative")
        print("   from a degraded instrument is weak evidence of no muscle, not evidence of no muscle.")
        print("   Clearing this properly needs a deposit with unfiltered high frequencies.")
    print(f"\n   verdict: {verdict}")
    print(f"\n   Denominators for every number above: {n_space} registered candidates, analytic dof >= 72.")
    print("   NOT CLOSED BY THIS EXPERIMENT: the 20-40 Hz band was itself chosen after seeing 1-20 and")
    print("   1-40 behave differently, and no sweep of the HIGH band has been run.")

    dst = os.path.join(RESULTS, "e10_exponent_high_emg.json")
    json.dump({"experiment": "E10", "gate_passed": True, "search_space_size": n_space,
               "analytic_dof_lower_bound": 72, "n_rows": len(rows), "n_subjects": len(set(subj)),
               "spearman_with_nuisance": rho, "nuisance_outcome_auc": emg_auc,
               "clause_a": bool(clause_a), "residualised": resid,
               "predictions": {"P1": bool(p1), "P2": bool(p2), "P3": bool(p3), "P4": True},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
