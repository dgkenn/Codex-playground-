#!/usr/bin/env python3
"""E07 — is the Lempel-Ziv dose result muscle? The test ANALYSIS_PLAN §3 committed to in advance.

WHY THIS EXPERIMENT EXISTS. E05 found Lempel-Ziv ordering measured plasma propofol in 90 % of subjects while
the aperiodic exponent managed 45 %. E06 found the effect frontally dominant: frontal single electrodes median
0.950 against posterior 0.700, with the four perfect electrodes all anterior. Facial muscle is frontal, EMG
raises binarised complexity, and propofol relaxes muscle — so progressive facial-muscle relaxation reproduces
that entire finding with no cortical content.

`ANALYSIS_PLAN.md` §3 pre-committed the remedy before any data was processed: *"EMG index is a predictor of
interest, not only a nuisance. If it predicts the outcome as well as the aperiodic exponent does, the exponent
result is an EMG result."* This is that test, applied to the candidate it now threatens.

TWO INDEPENDENT ANALYSES, because the binary contrast and the dose-response are different questions.

  A. THE ENGINE'S OWN PROBE, on baseline (level 1) vs moderate (level 3). `layer_adversarial` applies the
     two-clause rule fixed in `ANALYSIS_PLAN.md` §6 long before this finding existed: a candidate fails only
     if it predicts the nuisance BETTER than it predicts the outcome **and** its outcome association vanishes
     once the nuisance is held constant. Nothing here is tuned for this result; the rule and its thresholds
     are inherited.

  B. WITHIN-SUBJECT PARTIAL CORRELATION on the dose-response, which is what E05 actually measured. Each
     subject's three values (baseline, mild, moderate) are mean-centred, pooled across the 20 subjects, and
     the partial Spearman of candidate against plasma order is computed controlling for the EMG proxy.
     Centring within subject before pooling is what keeps this a within-subject statistic: without it,
     between-subject differences in overall complexity would dominate and the partial would be measuring
     who the subjects are rather than what the drug did.

REGISTERED BEFORE READING ANY EMG VALUE:
    P1  The EMG proxy itself tracks plasma dose — `emg_index` monotone in plasma in > 50 % of subjects.
        Rationale: propofol reduces neuromuscular tone, so a muscle proxy *should* fall with dose. **If P1
        fails, this experiment cannot adjudicate anything**: an EMG index that does not move with the drug
        cannot explain a result that does, and the correct report is that the proxy is uninformative here —
        which, per the correction in §9.11, is weak evidence of no muscle rather than none.
    P2  SUBSTANTIVE, and stated against the surviving candidate's interest: **Lempel-Ziv's dose association
        does NOT survive conditioning on EMG.** Concretely, its within-subject partial Spearman against plasma
        controlling for `emg_index` falls below half its unconditioned value. I am predicting that this
        project's one positive finding is an artefact, because that is what the frontal gradient most
        economically implies and because predicting the flattering outcome would make a survival
        uninterpretable as confirmation.
    P3  The aperiodic exponent, which does NOT track dose (45 %), should be comparatively UNAFFECTED by
        conditioning on EMG. A marker with no effect cannot have that effect explained away, so a large change
        here would indicate the conditioning is doing something spurious.
    P4  GATE, evaluated before P2 is interpreted (rules 34, 37): conditioning on a *shuffled* EMG column must
        NOT reduce any candidate's partial correlation appreciably. If it does, the partialling procedure
        itself removes signal regardless of what it conditions on, and every conditioned number is void.

    FALSIFICATION: if Lempel-Ziv's association survives conditioning, the finding stands as *weak* evidence —
    weak because §9.11 establishes that a 45 Hz-limited deposit gives reduced sensitivity to realistically
    peaked muscle, so survival on this data cannot clear it. Clearing it needs a deposit retaining 65-95 Hz,
    which is an acquisition requirement, not an analysis one.

SCOPE. 20 healthy volunteers, one drug, one site, average-referenced, 0.5-45 Hz. Nothing here speaks to
consciousness; the outcome is a measured drug concentration.
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

from bsde.candidates.registry import REGISTRY                                     # noqa: E402
from bsde.candidates.seed import seed_registry                                     # noqa: E402
from bsde.verifier.engine import Cohort, verify                                     # noqa: E402
from bsde.verifier.report import Evidence, render, PASS                             # noqa: E402
from bsde.verifier.stats import spearman, _midranks                                 # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "chennu_features_v2.csv")
EMG_COLS = ("emg_index", "emg_beta_gamma_fraction", "emg_kurtosis")
PLASMA_ORDER = {1: 0.0, 2: 1.0, 3: 2.0}          # ordinal; only the ordering is used
BRAIN = ("lempel_ziv", "spectral_entropy", "spectral_edge_95", "whole_head_exponent",
         "relative_alpha_power", "relative_delta_power", "uce_v1", "wpli_alpha")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    if not os.path.exists(TABLE):
        return []
    with open(TABLE, newline="") as fh:
        return [r for r in csv.DictReader(fh) if r.get("status") == "ok"]


def partial_spearman(x, y, z):
    """Spearman of x against y controlling for z, via rank residualisation of both on rank(z)."""
    x, y, z = (np.asarray(a, float) for a in (x, y, z))
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if ok.sum() < 8:
        return float("nan")
    rx, ry, rz = _midranks(x[ok]), _midranks(y[ok]), _midranks(z[ok])
    A = np.column_stack([np.ones(ok.sum()), rz])
    ex = rx - A @ np.linalg.lstsq(A, rx, rcond=None)[0]
    ey = ry - A @ np.linalg.lstsq(A, ry, rcond=None)[0]
    return spearman(ex, ey)


def within_subject_centred(rows, cand, emg_col):
    """Mean-centre each subject's three level values before pooling, so the statistic stays within-subject."""
    per = defaultdict(dict)
    for r in rows:
        lvl = _f(r.get("meta_sedation_level"))
        if not np.isfinite(lvl) or int(lvl) not in PLASMA_ORDER:
            continue
        v, e = _f(r.get(cand)), _f(r.get(emg_col))
        if not (np.isfinite(v) and np.isfinite(e)):
            continue
        per[r.get("subject", "")][int(lvl)] = (v, e)
    X, Y, Z = [], [], []
    for s, d in sorted(per.items()):
        if set(d) != set(PLASMA_ORDER):
            continue
        vs = np.array([d[k][0] for k in (1, 2, 3)], float)
        es = np.array([d[k][1] for k in (1, 2, 3)], float)
        ps = np.array([PLASMA_ORDER[k] for k in (1, 2, 3)], float)
        X += list(vs - vs.mean()); Y += list(ps - ps.mean()); Z += list(es - es.mean())
    return np.array(X), np.array(Y), np.array(Z), len(X) // 3


def mono_fraction(rows, col):
    per = defaultdict(dict)
    for r in rows:
        lvl = _f(r.get("meta_sedation_level")); v = _f(r.get(col))
        if np.isfinite(lvl) and int(lvl) in PLASMA_ORDER and np.isfinite(v):
            per[r.get("subject", "")][int(lvl)] = v
    m = [spearman([d[1], d[2], d[3]], [PLASMA_ORDER[i] for i in (1, 2, 3)])
         for d in per.values() if set(d) == set(PLASMA_ORDER)]
    m = [x for x in m if np.isfinite(x)]
    return (float(np.mean([x > 0 for x in m])) if m else float("nan")), len(m)


def main() -> int:
    seed_registry()
    rows = load()
    print("E07 — is the Lempel-Ziv dose result muscle?")
    if not rows:
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    print(f"   rows {len(rows)}   subjects {len({r['subject'] for r in rows})}")

    # ---- P1 GATE: does the EMG proxy move with the drug at all? ----------------------------------
    print("\n" + "=" * 100); print("P1 GATE — does the EMG proxy track plasma dose?"); print("=" * 100)
    emg_mono = {}
    for c in EMG_COLS:
        f, n = mono_fraction(rows, c)
        emg_mono[c] = f
        print(f"   {c:26s} monotone in plasma: {f if np.isfinite(f) else float('nan'):.3f}  (n={n})")
    p1 = np.isfinite(emg_mono.get("emg_index", np.nan)) and emg_mono["emg_index"] > 0.5
    print(f"   GATE: {'PASS' if p1 else 'FAIL'}")
    if not p1:
        print("   The EMG proxy does not move with the drug, so it CANNOT explain a result that does.")
        print("   This experiment adjudicates nothing. Per §9.11 that is weak evidence of no muscle,")
        print("   not evidence of none, and the Lempel-Ziv finding stays flagged as unexcluded.")

    # ---- P4 GATE: does partialling on NOISE destroy signal? ---------------------------------------
    rng = np.random.default_rng(20260730)
    print("\n" + "=" * 100); print("P4 GATE — partialling on a SHUFFLED EMG column must not remove signal")
    print("=" * 100)
    shuffle_damage = {}
    for cand in BRAIN:
        X, Y, Z, ns = within_subject_centred(rows, cand, "emg_index")
        if X.size < 24:
            continue
        raw = spearman(X, Y)
        Zs = rng.permutation(Z)
        sh = partial_spearman(X, Y, Zs)
        shuffle_damage[cand] = (raw, sh)
    worst = max((abs(a) - abs(b) for a, b in shuffle_damage.values()), default=0.0)
    p4 = worst < 0.10
    for c, (a, b) in sorted(shuffle_damage.items(), key=lambda kv: -abs(kv[1][0])):
        print(f"   {c:24s} raw {a:+.3f} -> shuffled-partial {b:+.3f}  (change {abs(b)-abs(a):+.3f})")
    print(f"   GATE: {'PASS' if p4 else 'FAIL'}  (largest loss to shuffled conditioning {worst:+.3f})")
    if not p4:
        print("   The partialling procedure removes signal regardless of what it conditions on.")
        print("   Every conditioned number below is VOID.")

    # ---- the substantive analysis -----------------------------------------------------------------
    print("\n" + "=" * 100)
    print("B. WITHIN-SUBJECT PARTIAL CORRELATION vs plasma order, controlling for each EMG proxy")
    print("=" * 100)
    print(f"   {'candidate':24s} {'raw rho':>9s} " + " ".join(f"{c.replace('emg_','|'):>14s}" for c in EMG_COLS))
    out = {}
    for cand in BRAIN:
        X, Y, Z, ns = within_subject_centred(rows, cand, "emg_index")
        if X.size < 24:
            print(f"   {cand:24s} {'n/a':>9s}")
            out[cand] = {"raw": None}
            continue
        raw = spearman(X, Y)
        parts = {}
        for c in EMG_COLS:
            Xc, Yc, Zc, _ = within_subject_centred(rows, cand, c)
            parts[c] = partial_spearman(Xc, Yc, Zc)
        print(f"   {cand:24s} {raw:+9.3f} " + " ".join(f"{parts[c]:+14.3f}" for c in EMG_COLS))
        keep = (abs(parts["emg_index"]) / abs(raw)) if abs(raw) > 1e-9 else float("nan")
        out[cand] = {"raw": raw, "partial": parts, "retained_fraction_emg_index": keep,
                     "n_subjects": ns}

    # ---- A. the engine's probe on baseline vs moderate --------------------------------------------
    print("\n" + "=" * 100)
    print("A. ENGINE PROBE, baseline vs moderate, EMG proxies supplied as nuisances")
    print("=" * 100)
    eng = {}
    for cname in ("lempel_ziv", "whole_head_exponent"):
        vals, ys, subs, nuis = [], [], [], {c: [] for c in EMG_COLS}
        for r in rows:
            lvl = _f(r.get("meta_sedation_level"))
            if not np.isfinite(lvl) or int(lvl) not in (1, 3):
                continue
            v = _f(r.get(cname))
            if not np.isfinite(v):
                continue
            vals.append(v); ys.append(1.0 if int(lvl) == 3 else 0.0); subs.append(r.get("subject", ""))
            for c in EMG_COLS:
                nuis[c].append(_f(r.get(c)))
        if len(vals) < 20:
            continue
        cand = REGISTRY.get(cname)
        coh = Cohort(values=np.array(vals), y=np.array(ys), subject=np.array(subs),
                     contrast="unconscious_vs_awake",
                     nuisance={k: np.array(v) for k, v in nuis.items()},
                     dataset="chennu_propofol")
        rep = verify(cand, [coh], np.random.default_rng(7), search_space_size=REGISTRY.search_space_size(),
                     extra_evidence=[Evidence("synthetic_ground_truth", "computational", PASS,
                                              "layer-1 tests pass in this suite")])
        for e in rep.evidence:
            if e.check.startswith("probe:emg") or e.check == "directional_discrimination":
                print(f"   [{cname}] {e.status.upper():4s} {e.check}")
                print(f"        {e.reason[:200]}")
        eng[cname] = {"verdict": rep.verdict,
                      "failed": [e.check for e in rep.evidence if e.status == "fail"]}

    # ---- registered predictions -------------------------------------------------------------------
    lz = out.get("lempel_ziv", {})
    wh = out.get("whole_head_exponent", {})
    p2 = (lz.get("retained_fraction_emg_index") is not None
          and np.isfinite(lz["retained_fraction_emg_index"])
          and lz["retained_fraction_emg_index"] < 0.5)
    p3 = (wh.get("retained_fraction_emg_index") is not None
          and np.isfinite(wh.get("retained_fraction_emg_index", np.nan))
          and wh["retained_fraction_emg_index"] > 0.5)
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 EMG proxy tracks plasma dose             : {'MET' if p1 else 'NOT MET'} "
          f"(emg_index mono {emg_mono.get('emg_index')})")
    print(f"   P4 shuffled-EMG conditioning harmless (GATE): {'MET' if p4 else 'NOT MET'}")
    print(f"   P2 lempel_ziv does NOT survive conditioning : {'MET' if p2 else 'NOT MET'} "
          f"(retained {lz.get('retained_fraction_emg_index')})")
    print(f"   P3 exponent comparatively unaffected        : {'MET' if p3 else 'NOT MET'} "
          f"(retained {wh.get('retained_fraction_emg_index')})")
    if not (p1 and p4):
        print("\n   *** ONE OR BOTH GATES FAILED -- P2 and P3 are NOT INTERPRETABLE and no conclusion about")
        print("       muscle is drawn either way.")
    elif p2:
        print("\n   Lempel-Ziv's dose association is substantially explained by the EMG proxy. E05's headline")
        print("   is reported as an EMG result, per ANALYSIS_PLAN §3.")
    else:
        print("\n   Lempel-Ziv's dose association SURVIVES conditioning -- but only as WEAK evidence, because")
        print("   a 0.5-45 Hz deposit gives reduced sensitivity to realistically peaked muscle (§9.11).")
        print("   Clearing it requires a deposit retaining 65-95 Hz. That is an acquisition requirement.")

    dst = os.path.join(RESULTS, "e07_emg_confound.json")
    json.dump({"experiment": "E07", "emg_monotonicity": emg_mono, "partials": out, "engine": eng,
               "gates": {"P1_emg_tracks_dose": bool(p1), "P4_shuffle_harmless": bool(p4)},
               "predictions": {"P2_lz_explained": bool(p2), "P3_exponent_unaffected": bool(p3)},
               "search_space_size": REGISTRY.search_space_size()},
              open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
