#!/usr/bin/env python3
"""E22 — Discovery Challenge A, second attempt: arms defined by the depth index, not by a charted time.

REGISTERED BEFORE ANY CANDIDATE VALUE FROM `vitaldb_grid.csv` HAS BEEN READ. What has been inspected of the
new table is BIS, SQI, SR, EMG and the window's standard deviation on three cases, while checking that the
sensor-off sentinel is handled — the monitor columns and the machinery, never a candidate. The candidate
columns are untouched, and this file is committed before they are.

WHY THERE IS A SECOND ATTEMPT. E21 registered its arms as fixed offsets either side of `aneend` and its
machinery gate failed at 1 of 22 cases (4.5 %), which closed it. The diagnosis, recorded in full in that
file and in `ingestion/vitaldb.py`, is two defects in the extraction:

    `BIS/BIS` writes a literal 0.0 while the strip is detached, and 0 is inside the index's valid range,
    so the detached windows read as isoelectric — the deepest possible state. `aneend` is charted when the
    anaesthetic record is closed, several minutes AFTER the patient is already responding, so the offsets
    E21 called "responsive" mostly sat after the monitor came off.

**E21's predictions are not edited and its failure is not revised.** Both defects say one thing — a window's
arm must be defined by the depth index rather than by its sign relative to a charted time — and that is a
different design, so it gets a different registration. What follows is that design.

CHALLENGE A, in Brief 03's words: *the simplest representation predicting loss and recovery of
responsiveness across multiple anaesthetic drugs, while minimising the information it carries about which
drug was used.* Its acceptance condition is not an AUC. It is that **a drug-identity probe must NOT
out-predict the responsiveness model.** A marker that silently encodes the agent is a pharmacology detector
wearing a consciousness label.

THE ARMS, FIXED HERE, FROM PUBLISHED CLINICAL THRESHOLDS AND NOT FROM THIS DATA.

    unresponsive   BIS <= 60      the conventional upper bound of adequate general anaesthesia; the depth
                                  range targeted by the B-Aware and B-Unaware trial protocols is 40-60
    responsive     BIS >= 80      the conventional light/awake range
    indeterminate  60 < BIS < 80  EXCLUDED, and counted

The thresholds are the guideline numbers precisely so that nothing about the split is chosen from the
distribution in front of me. The marginal BIS distribution in the first VitalDB table was seen while
diagnosing E21 — quantiles 7.6 / 36.3 / 46.1 / 56.5 / 74.1 / 79.9 / 90.4 — so a data-derived cut would not
have been credible even if it had been proposed.

WHAT IS CIRCULAR HERE, STATED AS THE HEADLINE LIMITATION RATHER THAN A FOOTNOTE. BIS is computed from the
same two frontal electrodes the candidates are computed from. So P2 asks "does this candidate agree with the
BIS algorithm", not "does this candidate track consciousness", and a high AUC there is the weakest result in
this file. **It is P4 and P5 that carry the weight**, and neither is damaged by the circularity: P4 compares
drug information against state information using the same labels for both, and P5 asks whether the apparent
state effect survives a control that holds state constant. Any reader taking one number from this experiment
should take P4's.

REGISTERED PREDICTIONS, in the order they are evaluated. Each gate is evaluated before anything downstream
of it exists, and a failed gate means the downstream verdict is ABSENT, not negative (rule 31).

    P1  MACHINERY GATE, and it uses no EEG and no candidate.
        (a) COVERAGE — at least 15 patients supply both arms, in at least two of the three drug groups.
            Challenge A is a cross-drug claim and cannot be made from one drug.
        (b) DIRECTION — among patients supplying both arms, the responsive windows occur LATER in the case
            than the unresponsive ones in >= 70 %. This reads `t_s` from the clinical record, nothing else.
            It is deliberately loose: `aneend` was shown to lag emergence, and some patients are legitimately
            light early, just after the sensor goes on and before the anaesthetic deepens. A floor of 70 %
            tests that the arms are not INVERTED, which is what E21 turned out to be, without asserting a
            precision the charted times do not have.

    P2  RESPONSIVENESS, PER DRUG ARM. `exponent_high` separates the arms WITHIN subject — the mean over
        patients of each patient's own AUC — with a subject-clustered CI excluding 0.5, in each drug group
        having >= 15 evaluable patients. Scored within subject because E14 measured an intraclass
        correlation above 0.9 across windows of the same person; a pooled AUC would mostly be answering
        whether two people differ.

    P3  DRUG INVARIANCE. The candidate's |AUC - 0.5| differs by no more than 0.15 between its best and its
        worst reported arm. A representation that works under propofol and fails under desflurane is not
        what Challenge A asks for.

    P4  THE DRUG-IDENTITY PROBE — THE ACCEPTANCE CONDITION. **Held at constant state: the unresponsive
        windows only, so a state difference cannot leak into the probe.** Can the candidate tell one agent
        from another? Its |AUC - 0.5| must be BELOW the responsiveness |AUC - 0.5|, **for EVERY drug pair
        with adequate coverage**. If the drug is more legible than the state, the representation encodes
        pharmacology and **Challenge A is failed however good P2 looks.** This probe is between-subject by
        construction — one patient has one agent — so it is scored pooled with a subject-clustered CI, and
        that asymmetry with P2 is a real limitation of the comparison rather than a choice: the two AUCs are
        not computed by the same estimator.

        AMENDMENT, MADE BEFORE ANY CANDIDATE VALUE WAS READ AND RECORDED HERE RATHER THAN APPLIED SILENTLY.
        As first registered, P4 named one pair: sevoflurane versus desflurane. A **permuted** smoke run
        (`--permute-within-subject`, rule 26) over the part-streamed table then measured the coverage: of
        106 cases, 63 were single-agent, and of those only **4 were desflurane**. Projected to the full
        stream that is roughly 10 patients, against a registered floor of 15 — so the acceptance condition
        would have come back UNTESTED for want of one drug, which is a null result about the paperwork
        rather than about the marker.
            The amendment removes the choice instead of re-making it: **every pair with adequate coverage is
        probed, and P4 requires all of them to pass.** That is strictly harder than naming one pair, it
        cannot be steered, and it needs no judgement at the time of reading. What licenses it is the timing
        and the source: the counts come from the clinical table and are computable with no candidate value
        in hand, and none had been read — the permuted run reports nothing else. Had a single AUC been seen
        first, this change would not be available and the pair would have stood.

    P5  PLACEBO, AND IT GATES THE VERDICT (rule 34). Same candidate, same estimator, arms replaced by
        early-deep versus late-deep — both drawn from BIS <= 60 windows only, split at each patient's own
        median `t_s`, so the state is held constant and only time-in-case varies. Its |AUC - 0.5| must be
        below HALF the responsiveness |AUC - 0.5|. **If it is not, P2 is reporting drift within maintenance
        rather than a state difference, and P2 is withdrawn.** R410 is the reason this is a gate and not a
        remark: a primary that passed every pairwise comparison was meaningless because the same statistic
        fired at an arbitrary cut where nothing happens.

    P6  THE MUSCLE CONTROL, reported and not gating. VitalDB carries `BIS/EMG`, a real muscle channel rather
        than the spectral proxies that §9.15 found two of disagreeing in sign. Reported: the arms' EMG
        separation, and P2 recomputed after dropping every window in the top EMG quartile. A candidate whose
        state effect vanishes there is reading arousal-related muscle activity. This is reported for all
        candidates because `exponent_high` sits at 20-40 Hz, where scalp EMG lives.

    FALSIFICATION: P4 not met, or P5 not met. The first is a failure of the challenge — the outcome the
    challenge was designed to detect — and the second is a failure of the experiment.

SCOPE AND LIMITS, none of which a larger n repairs.
  * **One site, one monitor, one country, one two-channel frontal montage.** `uce_v1` needs frontal AND
    posterior 10-20 names and is unavailable; 128 Hz sampling puts `exponent_gamma` (50-90 Hz) above Nyquist
    and it is NaN by design.
  * **Induction is absent from this deposit entirely.** `anestart` is negative in 91.8 % of cases because
    the strip goes on after the patient is asleep. So "loss and recovery" is, here, recovery only, plus
    whatever light windows occur early. ds004541 remains the only deposit with an explicit `loc` marker.
  * **A case enters the responsive arm only if its monitoring caught a light window.** That is not
    independent of the case: it goes with when the strip was applied and how long it stayed on. The
    surviving fraction is reported per drug group, and an arm-to-arm difference in it is a confound for P3
    rather than a nuisance (rule 14).
  * **Multi-agent cases are excluded from P2-P4 and counted.** Propofol induction followed by a volatile is
    routine, so `agents_present` frequently names two; a case naming more than one has no single drug label
    and cannot contribute to a per-drug arm. This is a large exclusion and it is not random — it removes
    precisely the mixed practice — so the per-drug results describe single-agent cases only.
  * Surgical populations differ by agent; desflurane and sevoflurane are not randomly assigned. Age, sex,
    BMI, ASA and emergency status are carried in the table and are **not** adjusted for here. P3 and P4 are
    comparisons of a marker's behaviour, not causal claims about drugs.
  * Cases are taken in ascending case id, never selected by result.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                          # noqa: E402
from bsde.candidates.seed import seed_registry                                          # noqa: E402
from bsde.verifier.stats import (auc_abs, cluster_bootstrap_ci, directional_auc,        # noqa: E402
                                 n_evaluable_subjects, within_subject_auc)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e22_challenge_a_bis_arms.json")

BIS_UNRESPONSIVE_MAX = 60.0
BIS_RESPONSIVE_MIN = 80.0
ARMS = ("propofol", "sevoflurane", "desflurane")
PROBE_PAIRS = (("propofol", "sevoflurane"), ("propofol", "desflurane"),
               ("sevoflurane", "desflurane"))
"""Every pair, not one chosen pair — see the P4 amendment in the module docstring. A pair without adequate
coverage is reported as ABSENT and does not silently pass."""
MIN_PROBE_PATIENTS = 15
PRIMARY = "exponent_high"
MIN_PATIENTS_PER_ARM = 15
MIN_ARMS_WITH_COVERAGE = 2
GATE_DIRECTION_MIN = 0.70
INVARIANCE_TOL = 0.15
PLACEBO_MAX_RATIO = 0.50
GATE_MIN_ROWS = 1500
"""A row-count floor on the TABLE, named after E15's smoke test that reported "GATE PASSED (100.0%)" from a
single row. 1,500 is roughly 60 cases at this grid spacing — below that the coverage counts below cannot
reach their own minimums anyway, so the failure would be reported as thin coverage without saying why."""

REPORT = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
          "emg_beta_gamma_fraction", "emg_kurtosis", "emg_index")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _ci(fn, subject, rng, reps=2000):
    lo, hi, n_ok = cluster_bootstrap_ci(fn, subject, rng, reps=reps)
    return float(lo), float(hi), int(n_ok)


def _registered_order() -> None:
    print("   Registered order of evaluation, fixed here and not re-openable:")
    print(f"     P1 GATE  coverage >= {MIN_PATIENTS_PER_ARM} patients with both arms in "
          f">= {MIN_ARMS_WITH_COVERAGE} drug groups, and responsive-later in "
          f">= {GATE_DIRECTION_MIN:.0%} of them")
    print(f"     P2       {PRIMARY} separates the arms WITHIN subject, CI excluding 0.5, in each arm")
    print(f"     P3       |AUC-0.5| differs by <= {INVARIANCE_TOL} between best and worst arm")
    print("     P4       drug probe on EVERY covered pair (UNRESPONSIVE windows only) must NOT out-predict "
          "responsiveness -- the acceptance condition")
    print(f"     P5 GATE  placebo (early-deep vs late-deep, state held constant) |AUC-0.5| must be below "
          f"{PLACEBO_MAX_RATIO:.0%} of P2's")
    print("     P6       EMG control, reported, not gating")


def main(argv=None) -> int:
    # SMOKE-TESTING IS DONE ON PERMUTED LABELS, NEVER REAL ONES (rule 26). `--permute-within-subject`
    # shuffles the BIS column inside each patient before the arms are derived, so every code path below runs
    # on real feature distributions while revealing nothing about the association. That keeps the
    # registration clean while the table is still streaming. Two things should happen under permutation and
    # both are checks on the harness rather than on the data: P1's direction gate should FAIL, because a
    # shuffled BIS has no reason to put light windows late in the case, and any AUC that is reported should
    # sit at chance.
    args = list(sys.argv[1:] if argv is None else argv)
    permute = "--permute-within-subject" in args
    table = TABLE
    if "--table" in args:                 # only ever used to point a PERMUTED smoke run at a partial merge
        table = os.path.abspath(args[args.index("--table") + 1])
    seed_registry()
    if permute:
        print("=" * 100)
        print("PERMUTED RUN — BIS is shuffled within each patient. NOTHING BELOW IS A RESULT.")
        print("It exercises the code paths and measures the harness, not the data (rule 26).")
        print("=" * 100)
    print("E22 — Challenge A with arms defined by BIS, on the whole-case VitalDB grid")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    if not os.path.exists(table):
        print(f"\n   *** {os.path.basename(table)} absent — the VitalDB grid stream has not produced it.")
        _registered_order()
        return 2

    all_rows = list(csv.DictReader(open(table, newline="")))
    rows = [r for r in all_rows if r.get("status") == "ok"]
    # DECODE FAILURES ARE AN EXCLUSION AND ARE NOT INDEPENDENT OF THE ARM (rule 14). Two thirds of them are
    # "runs past the record" and the rest are "entirely NaN (device disconnected)", and both cluster at the
    # END of the case -- which is where the responsive arm lives. So the responsive arm is systematically
    # the thinner one, for a reason that has nothing to do with any candidate. Counted here, and their
    # position relative to `aneend` is reported, rather than being filtered out in silence.
    failed = [r for r in all_rows if r.get("status") != "ok"]
    if failed:
        rel = np.array([_f(r.get("meta_rel_aneend_s", "")) for r in failed], float)
        rel_ok = np.array([_f(r.get("meta_rel_aneend_s", "")) for r in rows], float)
        rel, rel_ok = rel[np.isfinite(rel)], rel_ok[np.isfinite(rel_ok)]
        print(f"\n   decode failures: {len(failed)} of {len(all_rows)} windows "
              f"({len(failed) / max(1, len(all_rows)):.1%})")
        if rel.size and rel_ok.size:
            print(f"      median time relative to aneend — failed {np.median(rel):+8.0f} s   "
                  f"decoded {np.median(rel_ok):+8.0f} s")
            print("      (failures sit later in the case, so the responsive arm is the thinner one; "
                  "this is an outcome-related exclusion and is reported as one)")
    if len(rows) < GATE_MIN_ROWS and not permute:
        print(f"\n   *** {os.path.basename(table)} holds {len(rows)} usable rows, below the registered "
              f"floor of {GATE_MIN_ROWS}. The stream is still running; nothing is reported.")
        _registered_order()
        return 2

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)          # noqa: E731
    subj = np.array([r.get("subject", "") for r in rows])
    t_s = col("meta_t_s")
    bis = col("meta_bis")
    emg = col("meta_emg")
    sensor_off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    if permute:
        # Shuffled WITHIN subject, so each patient keeps their own BIS distribution and only its pairing
        # with time and with the EEG is destroyed. Shuffling across patients would additionally destroy the
        # between-patient composition and would make the permuted run easier than the real one.
        prng = np.random.default_rng(11071963)
        for s in np.unique(subj):
            k = np.flatnonzero(subj == s)
            bis[k] = prng.permutation(bis[k])
    agents = np.array([r.get("meta_agents_present", "") for r in rows])
    single = np.isin(agents, ARMS)                # exactly one agent named; "a|b" and "" both fail this
    arm = np.where(single, agents, "")

    unresp = np.isfinite(bis) & (bis <= BIS_UNRESPONSIVE_MAX) & ~sensor_off
    resp = np.isfinite(bis) & (bis >= BIS_RESPONSIVE_MIN) & ~sensor_off
    indet = np.isfinite(bis) & ~unresp & ~resp & ~sensor_off
    keep = unresp | resp
    y = resp.astype(float)                        # 1 = responsive, 0 = unresponsive

    print(f"\n   table {os.path.basename(table)}: {len(rows)} usable rows, "
          f"{len(set(subj))} patients, {len({r.get('meta_caseid', '') for r in rows})} cases")
    print(f"   sensor off (SQI = 0, all monitor values void) : {int(sensor_off.sum()):5d} rows  EXCLUDED")
    print(f"   BIS missing for another reason                : "
          f"{int((~np.isfinite(bis) & ~sensor_off).sum()):5d} rows  EXCLUDED")
    print(f"   indeterminate {BIS_UNRESPONSIVE_MAX:.0f} < BIS < {BIS_RESPONSIVE_MIN:.0f}"
          f"                  : {int(indet.sum()):5d} rows  EXCLUDED")
    print(f"   unresponsive  BIS <= {BIS_UNRESPONSIVE_MAX:.0f}                     : "
          f"{int(unresp.sum()):5d} rows  ({len(set(subj[unresp]))} patients)")
    print(f"   responsive    BIS >= {BIS_RESPONSIVE_MIN:.0f}                     : "
          f"{int(resp.sum()):5d} rows  ({len(set(subj[resp]))} patients)")
    print(f"   single-agent cases                            : "
          f"{len({r.get('meta_caseid', '') for r, s in zip(rows, single) if s})} of "
          f"{len({r.get('meta_caseid', '') for r in rows})}")

    # ------------------------------------------------------------------ P1
    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE (uses the clinical record only: no EEG, no candidate)")
    print("=" * 100)
    both = sorted({s for s in set(subj[unresp]) if s in set(subj[resp])})
    per_group = {a: len({s for s in both if a in set(arm[subj == s])}) for a in ARMS}
    groups_ok = [a for a, n in per_group.items() if n >= MIN_PATIENTS_PER_ARM]
    print(f"   patients supplying BOTH arms: {len(both)}")
    for a in ARMS:
        surviving = per_group[a]
        total = len({s for s in set(subj[single & (arm == a)])})
        frac = surviving / total if total else float("nan")
        print(f"      {a:12s} {surviving:4d} of {total:4d} single-agent patients ({frac:6.1%} survive "
              f"the both-arms requirement)")
    print("   (a difference between groups in that surviving fraction is a confound for P3, rule 14)")

    later = n_dir = 0
    for s in both:
        m = subj == s
        tu, tr = t_s[m & unresp], t_s[m & resp]
        tu, tr = tu[np.isfinite(tu)], tr[np.isfinite(tr)]
        if tu.size and tr.size:
            n_dir += 1
            later += int(np.median(tr) > np.median(tu))
    frac_later = later / n_dir if n_dir else float("nan")
    cov_ok = len(groups_ok) >= MIN_ARMS_WITH_COVERAGE
    dir_ok = np.isfinite(frac_later) and frac_later >= GATE_DIRECTION_MIN
    print(f"   (a) coverage : {len(groups_ok)} drug groups with >= {MIN_PATIENTS_PER_ARM} both-arm "
          f"patients {sorted(groups_ok)}   {'PASSED' if cov_ok else '*** FAILED'}")
    print(f"   (b) direction: responsive windows later in the case in {later}/{n_dir} "
          f"({frac_later:.1%})   {'PASSED' if dir_ok else '*** FAILED'}")

    state = {"experiment": "E22", "table": os.path.basename(table), "n_rows": len(rows),
             "n_patients": len(set(subj)), "arms": {"unresponsive_max_bis": BIS_UNRESPONSIVE_MAX,
                                                    "responsive_min_bis": BIS_RESPONSIVE_MIN},
             "exclusions": {"sensor_off": int(sensor_off.sum()), "indeterminate": int(indet.sum()),
                            "bis_missing": int((~np.isfinite(bis) & ~sensor_off).sum())},
             "p1": {"both_arms_patients": len(both), "per_group": per_group,
                    "groups_with_coverage": groups_ok, "direction_fraction": frac_later,
                    "n_direction": n_dir, "passed": bool(cov_ok and dir_ok)}}
    if not (cov_ok and dir_ok):
        print("\n   P1 FAILED. Nothing downstream is reported: the verdict is ABSENT, not negative "
              "(rule 31).")
        json.dump(state, open(OUT, "w"), indent=2)
        return 1

    # ------------------------------------------------------------------ P2
    print("\n" + "=" * 100)
    print("P2 — RESPONSIVENESS, PER DRUG ARM (within-subject AUC, subject-clustered CI)")
    print("=" * 100)
    rng = np.random.default_rng(20260730)
    direction = REGISTRY.get(PRIMARY).predicted("unconscious_vs_awake") or "higher"
    print(f"   {PRIMARY}: declared to run {direction!r} in the unconscious state; scored so that > 0.5 "
          "means it moved as declared")
    x = col(PRIMARY)

    def arm_mask(a):
        return keep & (arm == a) & np.isfinite(x)

    per_arm = {}
    print(f"\n   {'arm':13s} {'pats':>5s} {'rows':>6s} {'within-subject AUC':>20s} {'95% CI':>20s} "
          f"{'|AUC-.5|':>9s}")
    for a in ARMS:
        m = arm_mask(a)
        n_eval = n_evaluable_subjects(1 - y[m], x[m], subj[m])
        if n_eval < MIN_PATIENTS_PER_ARM:
            print(f"   {a:13s} {n_eval:5d} {int(m.sum()):6d}   fewer than {MIN_PATIENTS_PER_ARM} "
                  "evaluable patients; not reported")
            continue
        ym, xm, sm = 1 - y[m], x[m], subj[m]      # y=0 (unresponsive) is the declared-unconscious side
        au = within_subject_auc(ym, xm, sm, direction)
        lo, hi, _ = _ci(lambda i: within_subject_auc(ym[i], xm[i], sm[i], direction), sm, rng)
        per_arm[a] = {"auc": au, "ci": [lo, hi], "abs": abs(au - 0.5), "n_patients": n_eval,
                      "n_rows": int(m.sum())}
        print(f"   {a:13s} {n_eval:5d} {int(m.sum()):6d} {au:20.3f} "
              f"{f'[{lo:.3f}, {hi:.3f}]':>20s} {abs(au - 0.5):9.3f}")
    excl = [a for a, d in per_arm.items() if not (d["ci"][0] > 0.5 or d["ci"][1] < 0.5)]
    p2 = bool(per_arm) and not excl
    print(f"\n   P2 {'PASSED' if p2 else '*** FAILED'}"
          + ("" if p2 else f" — CI includes 0.5 in {excl or ['no arm was reportable']}"))
    state["p2"] = {"direction": direction, "per_arm": per_arm, "passed": p2}

    # ------------------------------------------------------------------ P3
    print("\n" + "=" * 100)
    print(f"P3 — DRUG INVARIANCE: |AUC-0.5| spread across arms <= {INVARIANCE_TOL}")
    print("=" * 100)
    if len(per_arm) < 2:
        print("   fewer than two reportable arms — P3 is ABSENT, not failed (rule 31).")
        state["p3"] = {"passed": None, "reason": "fewer than two reportable arms"}
    else:
        spread = max(d["abs"] for d in per_arm.values()) - min(d["abs"] for d in per_arm.values())
        p3 = spread <= INVARIANCE_TOL
        print(f"   best {max(per_arm, key=lambda a: per_arm[a]['abs'])} = "
              f"{max(d['abs'] for d in per_arm.values()):.3f}   "
              f"worst {min(per_arm, key=lambda a: per_arm[a]['abs'])} = "
              f"{min(d['abs'] for d in per_arm.values()):.3f}   spread {spread:.3f}   "
              f"{'PASSED' if p3 else '*** FAILED'}")
        state["p3"] = {"spread": float(spread), "passed": bool(p3)}

    # ------------------------------------------------------------------ P4
    print("\n" + "=" * 100)
    print("P4 — DRUG-IDENTITY PROBE, EVERY PAIR WITH COVERAGE, STATE HELD CONSTANT")
    print("=" * 100)
    print("   Unresponsive windows only, so no state difference can leak into the probe. Between-subject")
    print("   by construction — one patient, one agent — so this AUC is pooled with a subject-clustered CI,")
    print("   while P2's is within-subject. The two are NOT computed by the same estimator, and that")
    print("   asymmetry is a real limit on the comparison rather than a choice.")
    print("   Every pair is probed and ALL must pass; see the P4 amendment in this file's header for why")
    print("   that replaced a single named pair, and for the timing that licenses the change.")
    probes, verdicts = {}, []
    print(f"\n   {'pair':28s} {'pats':>9s} {'rows':>6s} {'drug |AUC-.5|':>14s} {'state |AUC-.5|':>15s} "
          f"{'verdict':>9s}")
    for pa, pb in PROBE_PAIRS:
        m = unresp & np.isin(arm, (pa, pb)) & np.isfinite(x)
        yy = (arm[m] == pb).astype(float)
        ss = subj[m]
        n_a, n_b = len(set(ss[yy == 0])), len(set(ss[yy == 1]))
        label = f"{pa} vs {pb}"
        if min(n_a, n_b) < MIN_PROBE_PATIENTS:
            probes[label] = {"passed": None, "reason": "underpowered", "n": {pa: n_a, pb: n_b}}
            print(f"   {label:28s} {f'{n_a}/{n_b}':>9s} {int(m.sum()):6d} "
                  f"{'—':>14s} {'—':>15s} {'ABSENT':>9s}")
            continue
        xp = x[m]
        probe = auc_abs(yy, xp)                   # direction-free: which drug is "higher" is meaningless
        plo, phi, _ = _ci(lambda i: auc_abs(yy[i], xp[i]), ss, rng)
        probe_abs = abs(probe - 0.5)
        # The LARGER of the two arms' state effects, which is the harder bar for the probe to clear.
        state_abs = max((per_arm[a]["abs"] for a in (pa, pb) if a in per_arm), default=float("nan"))
        ok = bool(np.isfinite(state_abs) and probe_abs < state_abs)
        probes[label] = {"probe_auc": float(probe), "probe_ci": [plo, phi],
                         "probe_abs": float(probe_abs), "state_abs": float(state_abs),
                         "n": {pa: n_a, pb: n_b}, "passed": ok}
        verdicts.append(ok)
        print(f"   {label:28s} {f'{n_a}/{n_b}':>9s} {int(m.sum()):6d} {probe_abs:14.3f} "
              f"{state_abs:15.3f} {'PASSED' if ok else '*** FAILED':>9s}")
    if not verdicts:
        print(f"\n   No pair reached {MIN_PROBE_PATIENTS} patients on both sides. Challenge A's acceptance")
        print("   condition is UNTESTED — absent, not passed (rule 31).")
        p4 = None
    else:
        p4 = all(verdicts)
        print(f"\n   P4 {'PASSED on every covered pair — the state is more legible than the drug' if p4 else '*** FAILED on at least one pair — the drug is more legible than the state; Challenge A is FAILED'}")
    state["p4"] = {"pairs": probes, "passed": p4}

    # ------------------------------------------------------------------ P5
    print("\n" + "=" * 100)
    print(f"P5 — PLACEBO, GATING: early-deep vs late-deep, state held constant "
          f"(|AUC-0.5| must be < {PLACEBO_MAX_RATIO:.0%} of P2's)")
    print("=" * 100)
    print("   Both sides are BIS <= 60 windows, split at each patient's OWN median t_s. If the candidate")
    print("   separates these, P2 is reporting drift through the case rather than a state difference.")
    placebo = {}
    for a in ARMS:
        if a not in per_arm:
            continue
        m = unresp & (arm == a) & np.isfinite(x)
        lab = np.full(m.sum(), np.nan)
        sm, tm, xm = subj[m], t_s[m], x[m]
        for s in np.unique(sm):
            k = sm == s
            tt = tm[k]
            if np.isfinite(tt).sum() < 2:
                continue
            med = np.nanmedian(tt)
            if not np.isfinite(med) or np.nanmin(tt) == np.nanmax(tt):
                continue
            lab[k] = (tt > med).astype(float)     # 1 = late-deep, plays the "responsive" role
        ok = np.isfinite(lab) & np.isfinite(xm)
        n_eval = n_evaluable_subjects(lab[ok], xm[ok], sm[ok])
        if n_eval < MIN_PATIENTS_PER_ARM:
            print(f"   {a:13s} only {n_eval} evaluable patients; placebo ABSENT for this arm")
            continue
        # Scored with the SAME declared direction as P2, so "fires like the real contrast" is what > 0.5
        # means here too. A placebo that fires in the opposite direction is not evidence of anything and
        # is why the criterion is on |AUC-0.5| rather than on the signed value.
        pa = within_subject_auc(1 - lab[ok], xm[ok], sm[ok], direction)
        plo, phi, _ = _ci(lambda i: within_subject_auc(1 - lab[ok][i], xm[ok][i], sm[ok][i], direction),
                          sm[ok], rng)
        ratio = abs(pa - 0.5) / per_arm[a]["abs"] if per_arm[a]["abs"] > 0 else float("inf")
        placebo[a] = {"auc": pa, "ci": [plo, phi], "abs": abs(pa - 0.5), "ratio_to_p2": float(ratio),
                      "n_patients": n_eval}
        print(f"   {a:13s} placebo AUC {pa:.3f} [{plo:.3f}, {phi:.3f}]   |AUC-0.5| {abs(pa - 0.5):.3f}   "
              f"= {ratio:5.1%} of P2's {per_arm[a]['abs']:.3f}")
    if not placebo:
        print("   no arm had an evaluable placebo — P5 is ABSENT, and so the P2 verdict is UNGATED and "
              "must not be read as established (rule 31).")
        p5 = None
    else:
        worst = max(placebo.values(), key=lambda d: d["ratio_to_p2"])
        p5 = bool(worst["ratio_to_p2"] < PLACEBO_MAX_RATIO)
        print(f"\n   P5 {'PASSED' if p5 else '*** FAILED — P2 is WITHDRAWN: the same statistic fires where no state change occurs'}"
              f"   (worst arm {worst['ratio_to_p2']:.1%})")
    state["p5"] = {"per_arm": placebo, "passed": p5}

    # ------------------------------------------------------------------ P6
    print("\n" + "=" * 100)
    print("P6 — MUSCLE CONTROL (BIS/EMG, a real muscle channel, not a spectral proxy). Reported, not gating")
    print("=" * 100)
    m_emg = keep & np.isfinite(emg)
    if m_emg.sum() and len(np.unique(y[m_emg])) == 2:
        emg_auc = auc_abs(y[m_emg], emg[m_emg])
        print(f"   EMG itself separates the arms with |AUC| {emg_auc:.3f} over {int(m_emg.sum())} rows — "
              "muscle tone does return with responsiveness, as expected.")
    hi_emg = np.nanquantile(emg[keep & np.isfinite(emg)], 0.75) if np.isfinite(emg[keep]).any() else np.nan
    print(f"   dropping windows with EMG above the {0.75:.0%} quantile ({hi_emg:.1f}):")
    print(f"\n   {'candidate':26s} {'arm':13s} {'AUC all':>9s} {'AUC low-EMG':>13s} {'shift':>8s}")
    emg_ctrl = {}
    for cname in REPORT:
        xc = col(cname)
        if not np.isfinite(xc).any():
            continue
        d = REGISTRY.get(cname).predicted("unconscious_vs_awake") or "higher"
        for a in ARMS:
            m = keep & (arm == a) & np.isfinite(xc)
            if n_evaluable_subjects(1 - y[m], xc[m], subj[m]) < MIN_PATIENTS_PER_ARM:
                continue
            a_all = within_subject_auc(1 - y[m], xc[m], subj[m], d)
            ml = m & np.isfinite(emg) & (emg <= hi_emg)
            if n_evaluable_subjects(1 - y[ml], xc[ml], subj[ml]) < MIN_PATIENTS_PER_ARM:
                print(f"   {cname:26s} {a:13s} {a_all:9.3f} {'too few':>13s}")
                continue
            a_low = within_subject_auc(1 - y[ml], xc[ml], subj[ml], d)
            emg_ctrl.setdefault(cname, {})[a] = {"auc_all": a_all, "auc_low_emg": a_low}
            print(f"   {cname:26s} {a:13s} {a_all:9.3f} {a_low:13.3f} {a_low - a_all:+8.3f}")
    state["p6"] = emg_ctrl

    # ------------------------------------------------------------------ verdict
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p5 is False:
        print("   P2 is WITHDRAWN by its own placebo, so Challenge A is not addressed by this run.")
        verdict = "withdrawn_by_placebo"
    elif p5 is None:
        print("   The placebo could not be evaluated, so the P2 verdict is UNGATED and is reported as")
        print("   provisional rather than established (rule 31).")
        verdict = "ungated"
    elif p4 is None:
        print("   The drug probe was underpowered, so Challenge A's acceptance condition is UNTESTED.")
        print("   P2 and P3 stand on their own terms and do not, between them, address the challenge.")
        verdict = "acceptance_condition_untested"
    elif p4 and p2:
        print("   Challenge A is MET on this deposit: the representation separates the arms in every")
        print("   reported drug group, survives its placebo, and carries less drug information than state")
        print("   information. This is one site, one monitor and a proxy for responsiveness — it is a")
        print("   first pass at the challenge, not a settled answer to it.")
        verdict = "met"
    elif not p4:
        print("   Challenge A is FAILED: the drug is more legible in this representation than the state is.")
        verdict = "failed_drug_probe"
    else:
        print("   Challenge A is not met: the responsiveness contrast did not clear its own interval.")
        verdict = "failed_p2"
    state["verdict"] = verdict
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
