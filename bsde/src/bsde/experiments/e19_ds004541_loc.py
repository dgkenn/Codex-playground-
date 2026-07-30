#!/usr/bin/env python3
"""E19 — the first test in this project on a cohort that actually loses consciousness.

REGISTERED BEFORE ANY ds004541 FEATURE VALUE WAS READ. The stream was launched minutes before this file was
written; the only things inspected are the deposit's `events.tsv`, `participants.tsv` and raw channel
amplitudes, which are properties of the FILES rather than of any candidate.

WHY THIS MATTERS MORE THAN ITS SAMPLE SIZE. §9.16 is the largest correction in this project: the Chennu
cohort never reaches unconsciousness at any level, so E05/E07/E08/E09/E10 all measure mild-to-moderate
sedation in responsive volunteers. ds004541 marks `loc` and `roc` explicitly, against a graded stimulation
ladder (verbal/soft → verbal/strong → motor → tetanic). **It is the only reachable public EEG deposit, out of
447 OpenNeuro EEG datasets enumerated exhaustively, where consciousness is documented as actually lost.**

**n = 7 SUBJECTS WITH A `loc` MARKER. THAT IS TINY AND IT BOUNDS EVERYTHING BELOW.** No confidence interval
here will be narrow, and the predictions are written as SIGN counts across subjects rather than as intervals,
because a bootstrap interval on 7 clusters is theatre. A sign test needs 6/7 to reach one-sided p = 0.06 and
7/7 for p = 0.008; those are the only two outcomes that mean anything, and that is stated now rather than
discovered afterwards.

REGISTERED PREDICTIONS:

    P1  MACHINERY GATE, on the most robust finding in anaesthesia EEG. `relative_delta_power` must INCREASE
        from pre-LOC to post-LOC in at least 6 of 7 subjects. Purdon et al. (PNAS 2013, PMID 23487781,
        verified from the MEDLINE record) report that "loss of consciousness was marked simultaneously by an
        increase in low-frequency EEG power (<1 Hz)". If that is not recoverable here, the epoch alignment,
        the channel selection or the event parsing is wrong and NOTHING else is reported (rule 31).

    P2  PRIMARY. `exponent_high` moves in its declared direction (HIGHER when unconscious) from pre-LOC to
        post-LOC in at least 6 of 7 subjects. **This is the first time the candidate has faced actual loss of
        consciousness.** Its 0.863 on Chennu and 0.762 on ds005620 are both sedation-depth measurements
        (§9.16, §9.21); if it fails here, those numbers stand and their interpretation narrows to sedation
        depth permanently.

    P3  DISCONTINUITY, AND THE STATISTIC IS CHOSEN TO AVOID RULE 33. The drug infuses continuously before
        LOC, so a gradual pre-LOC drift is expected pharmacologically and is NOT evidence of anything. The
        question is whether the change is a STEP at the marker or a RAMP through it. Error-catalogue rule 33
        records that a ratio of two adjacent blocks cannot test locality — any steeply-changing quantity
        wins it with no discontinuity anywhere — so the statistic is the largest single-step change across
        the symmetric offset grid, and the prediction is that it coincides with the `loc` marker.
        **PLACEBO GATE (rule 34): the same statistic is computed against a pseudo-marker shifted to −180 s,
        where no clinical event occurs. If the step is just as likely to land there, P3 is meaningless and
        is reported as such.** A test with no placebo is a test with no denominator.

    P4  EMERGENCE, testing a contrast declared in `CONTRASTS` since the registry was written and never once
        exercised. Any candidate meeting P2 must REVERSE at `roc`: post-ROC lies back toward pre-LOC relative
        to post-LOC, in at least 5 of 7 subjects. A marker that tracks the drug's arrival but not its
        departure is a pharmacokinetic index, not a state marker — and §9.8 already recorded that Chennu's
        recovery level carries 276.5 µg/L of propofol still on board, so "returns to baseline" is not
        guaranteed by the design.

    FALSIFICATION OF THE LEAD: P2 not met while P1 passes. If `exponent_high` cannot mark the transition it
    was ultimately proposed for, on the only data where that transition is marked, then it is a
    sedation-depth measure and nothing more — which is exactly what §9.16 and §9.21 already suspect and what
    the anaesthesia wedge could still be built on.

SCOPE AND LIMITS, stated rather than implied.
  * **The anaesthetic agent is NOT recorded in the deposit** — not in `dataset_description.json`, the README
    or `participants.json`. Nothing here bears on Challenge A, which needs two identified drugs, and the
    agent must not be assumed to be propofol because the project's other two anaesthesia deposits are.
  * `participants.tsv` carries no age, sex, weight or height — every field is `n/a` — so **no covariate
    adjustment of any kind is possible** and none is claimed.
  * LOC is marked by unresponsiveness to graded stimulation, which is a behavioural criterion. It is the
    best available and it is not a direct observation of experience; a marker that tracks it is tracking
    responsiveness, which §9.3's H4 says an arousal index would do too.
  * 30 s windows, 62 EEG channels of an extended 10-20 montage, 1000 Hz, EOG/EKG/EMG/trigger excluded by
    name. Denominators: 18 registered candidates, analytic_dof >= 72 for the exponent family.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                        # noqa: E402
from bsde.candidates.seed import seed_registry                                        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "ds004541_loc.csv")

GATE = "relative_delta_power"
PRIMARY = "exponent_high"
GATE_MIN = 6
PRIMARY_MIN = 6
EMERGENCE_MIN = 5
PLACEBO_OFFSET = -180.0
MIN_ROWS = 80
REPORT = ("exponent_high", "exponent_gamma", "exponent_low", "whole_head_exponent", "uce_v1",
          "relative_delta_power", "relative_alpha_power", "lempel_ziv", "spectral_entropy",
          "spectral_edge_95", "wpli_alpha", "spatial_participation_ratio",
          "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
          "emg_beta_gamma_fraction", "emg_kurtosis")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    if not os.path.exists(TABLE):
        return {}
    by = defaultdict(dict)
    with open(TABLE, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("status") == "ok":
                by[r["subject"]][r.get("meta_epoch", "")] = r
    return by


def _mean_of(rows, epochs, name):
    """Mean of a candidate across a set of epochs for one subject; NaN if none are finite."""
    v = [_f(rows[e].get(name, "")) for e in epochs if e in rows]
    v = [x for x in v if np.isfinite(x)]
    return float(np.mean(v)) if v else float("nan")


def main() -> int:
    seed_registry()
    n_space = REGISTRY.search_space_size()
    print("E19 — the first test here on a cohort that actually loses consciousness")
    print(f"   search space {n_space} registered candidates; analytic dof >= 72")
    by = load()
    n_rows = sum(len(v) for v in by.values())
    if n_rows < MIN_ROWS:
        print(f"   *** only {n_rows} rows; need {MIN_ROWS}. The stream is still running — this is a")
        print("   statement about the TABLE, not about any candidate.")
        return 1

    subs = sorted(by)
    PRE = [f"loc{o:+.0f}" for o in (-60.0, -30.0)]
    POST = [f"loc{o:+.0f}" for o in (30.0, 60.0)]
    EARLY = [f"loc{o:+.0f}" for o in (-300.0, -240.0, -180.0)]
    print(f"   subjects {len(subs)}   rows {n_rows}")

    def sign_count(name, a_epochs, b_epochs, direction):
        """How many subjects move `direction` from a-block to b-block. Returns (hits, n, per-subject)."""
        hits, n, detail = 0, 0, {}
        for s in subs:
            a, b = _mean_of(by[s], a_epochs, name), _mean_of(by[s], b_epochs, name)
            if np.isfinite(a) and np.isfinite(b):
                n += 1
                up = b > a
                ok = up if direction == "higher" else (not up)
                hits += int(ok)
                detail[s] = {"pre": a, "post": b, "moved_declared": bool(ok)}
        return hits, n, detail

    # ------------------------------- P1 gate -------------------------------------------------------
    print("\n" + "=" * 100)
    print(f"P1 — MACHINERY GATE: {GATE} must INCREASE pre-LOC -> post-LOC in >= {GATE_MIN} subjects")
    print("=" * 100)
    g_hits, g_n, _ = sign_count(GATE, PRE, POST, "higher")
    p1 = g_n > 0 and g_hits >= GATE_MIN
    print(f"   delta power rose in {g_hits}/{g_n} subjects   {'GATE PASSED' if p1 else '*** GATE FAILED'}")
    if not p1:
        print("   Purdon 2013 (PMID 23487781) records that loss of consciousness is marked by increased")
        print("   low-frequency power. If that is not recoverable here, the epoch alignment, the channel")
        print("   selection or the event parsing is wrong. Nothing else is reported (rule 31).")
        json.dump({"experiment": "E19", "gate_passed": False, "gate_hits": g_hits, "n": g_n},
                  open(os.path.join(RESULTS, "e19_loc.json"), "w"), indent=2)
        return 1

    # ------------------------------- all candidates ------------------------------------------------
    print("\n" + "=" * 100)
    print("PRE-LOC vs POST-LOC, per candidate, counted as SIGNS across subjects (n is 7; no intervals)")
    print("=" * 100)
    print(f"   {'candidate':28s} {'declared':>9s} {'moved as declared':>19s}   note")
    out = {}
    for name in REPORT:
        cand = REGISTRY.get(name)
        d = cand.predicted("unconscious_vs_awake")
        if d not in ("higher", "lower"):
            d = "higher"
        hits, n, detail = sign_count(name, PRE, POST, d)
        if not n:
            continue
        out[name] = {"declared": d, "hits": hits, "n": n,
                     "per_subject": {k: {kk: vv for kk, vv in v.items()} for k, v in detail.items()}}
        flag = "  <-- primary" if name == PRIMARY else ""
        strength = ("consistent" if hits == n else ("strong" if hits >= n - 1 else ""))
        print(f"   {name:28s} {d:>9s} {hits:>10d}/{n:<8d} {strength}{flag}")

    pri = out.get(PRIMARY)
    p2 = bool(pri and pri["hits"] >= PRIMARY_MIN)

    # ------------------------------- P3 discontinuity with a placebo -------------------------------
    print("\n" + "=" * 100)
    print(f"P3 — is the change a STEP at the marker or a RAMP through it? (placebo at {PLACEBO_OFFSET:+.0f}s)")
    print("=" * 100)
    offsets = sorted({_f(by[s][e].get("meta_offset_s")) for s in subs for e in by[s]
                      if e.startswith("loc")} - {float("nan")})
    offsets = [o for o in offsets if np.isfinite(o)]
    step_at_marker = step_at_placebo = 0
    n_step = 0
    for s in subs:
        series = []
        for o in offsets:
            e = f"loc{o:+.0f}"
            if e in by[s]:
                v = _f(by[s][e].get(PRIMARY, ""))
                if np.isfinite(v):
                    series.append((o, v))
        if len(series) < 6:
            continue
        n_step += 1
        series.sort()
        os_, vs = np.array([a for a, _ in series]), np.array([b for _, b in series])
        steps = np.abs(np.diff(vs))
        # The gap that the biggest step spans; the marker sits between the last negative and first
        # positive offset, so a step "at the marker" is the one crossing 0.
        k = int(np.argmax(steps))
        crosses_marker = os_[k] < 0 < os_[k + 1]
        crosses_placebo = os_[k] < PLACEBO_OFFSET < os_[k + 1] or os_[k] == PLACEBO_OFFSET
        step_at_marker += int(crosses_marker)
        step_at_placebo += int(crosses_placebo)
    p3 = n_step > 0 and step_at_marker > step_at_placebo and step_at_marker >= max(3, n_step // 2)
    print(f"   largest single step falls AT the loc marker in {step_at_marker}/{n_step} subjects")
    print(f"   ... and at the placebo cut ({PLACEBO_OFFSET:+.0f}s) in {step_at_placebo}/{n_step}")
    if n_step and step_at_placebo >= step_at_marker:
        print("   *** THE PLACEBO IS AS GOOD AS THE MARKER. P3 carries no information: the statistic fires")
        print("   wherever it is pointed, which is what rule 34 exists to catch.")

    # ------------------------------- P4 emergence --------------------------------------------------
    print("\n" + "=" * 100)
    print("P4 — EMERGENCE: does the primary REVERSE at roc? (a contrast never before exercised)")
    print("=" * 100)
    rev, rn = 0, 0
    for s in subs:
        post = _mean_of(by[s], POST, PRIMARY)
        pre = _mean_of(by[s], PRE, PRIMARY)
        rocp = _mean_of(by[s], ["roc+60"], PRIMARY)
        if all(np.isfinite(x) for x in (pre, post, rocp)):
            rn += 1
            # "back toward pre-LOC" means the post-ROC value sits between post-LOC and pre-LOC, or beyond.
            rev += int(abs(rocp - pre) < abs(post - pre))
    p4 = rn > 0 and rev >= EMERGENCE_MIN
    print(f"   post-ROC lies back toward pre-LOC in {rev}/{rn} subjects")

    # ------------------------------- verdict --------------------------------------------------------
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 GATE delta rises at LOC in >= {GATE_MIN}                     : MET ({g_hits}/{g_n})")
    print(f"   P2 {PRIMARY} moves as declared in >= {PRIMARY_MIN}       : "
          f"{'MET' if p2 else 'NOT MET'}" + (f" ({pri['hits']}/{pri['n']})" if pri else ""))
    print(f"   P3 step at the marker, beating a placebo cut            : {'MET' if p3 else 'NOT MET'}")
    print(f"   P4 reverses at roc in >= {EMERGENCE_MIN}                          : "
          f"{'MET' if p4 else 'NOT MET'} ({rev}/{rn})")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p2:
        verdict = "PRIMARY_FAILS_AT_REAL_LOC"
        print(f"   {PRIMARY} does NOT mark loss of consciousness on the only data where it is marked")
        print(f"   ({pri['hits']}/{pri['n']} subjects). Its 0.863 on Chennu and 0.762 on ds005620 stand as")
        print("   computed, and their interpretation narrows permanently to SEDATION DEPTH (§9.16, §9.21).")
        print("   That is still a usable anaesthesia-monitoring quantity and it is not a consciousness")
        print("   marker. n = 7 is small, so this is a failure to demonstrate rather than a demonstrated")
        print("   absence — but the burden was on the candidate and it is the only test available.")
    elif not p3:
        verdict = "MARKS_LOC_BUT_NOT_AS_A_DISCONTINUITY"
        print(f"   {PRIMARY} moves as declared in {pri['hits']}/{pri['n']} subjects, but the change is not")
        print("   localised to the marker any better than to an arbitrary placebo cut. That is consistent")
        print("   with tracking the drug's continuous effect rather than the transition — which is what a")
        print("   pharmacokinetic index does, and what rule 33 warns a block ratio would have hidden.")
    else:
        verdict = "MARKS_LOC_AS_A_STEP"
        print(f"   {PRIMARY} moves as declared in {pri['hits']}/{pri['n']} subjects AND the change is a step")
        print("   at the marker rather than at a placebo cut. On n = 7 this is the strongest outcome the")
        print("   design allows, and it is still seven patients, one site, one unnamed drug.")
    print(f"\n   verdict: {verdict}")
    print("\n   NOT ESTABLISHED BY ANY OUTCOME HERE: that the marker reflects experience rather than")
    print("   responsiveness. LOC is scored behaviourally, so an arousal index (§9.3's H4) predicts the")
    print("   same result. And the agent is unrecorded, so nothing here bears on Challenge A.")

    dst = os.path.join(RESULTS, "e19_loc.json")
    json.dump({"experiment": "E19", "gate_passed": True, "search_space_size": n_space,
               "n_subjects": len(subs), "n_rows": n_rows, "gate": {"hits": g_hits, "n": g_n},
               "pre_vs_post": out, "discontinuity": {"at_marker": step_at_marker,
                                                     "at_placebo": step_at_placebo, "n": n_step},
               "emergence": {"reversed": rev, "n": rn},
               "predictions": {"P1": True, "P2": p2, "P3": p3, "P4": p4},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
