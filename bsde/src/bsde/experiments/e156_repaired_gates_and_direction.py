#!/usr/bin/env python3
"""E156 -- E155's two survivors, with gates that can actually fail and a direction that can be wrong.

REGISTERED BEFORE THE REPAIRED GATES OR THE DIRECTION CHECK HAVE BEEN RUN. Successor to E155. Cohort,
window, weighting, candidates and null construction are E155's, unchanged. **Only the gate mechanics and
two added checks change**, and every change is named below.

=========================================================================================================
WHAT E155 ESTABLISHED AND WHY IT COULD NOT ISSUE A VERDICT
=========================================================================================================
E155 removed recording duration two ways -- a fixed 300-epoch summary window identical for every case, and
overlap weighting on propensity(arm | rank duration), which took duration's own legibility from **0.3771
to 0.0258**, a 93 % removal. **Both of E154's hits got BIGGER, not smaller:**

    alpha_peak_hz   0.3943 -> **0.4703**   null p95 0.1906   permutation p 0.0000   Holm 0.0000
    rel_theta       0.4771 -> **0.4506**   null p95 0.1780   permutation p 0.0000   Holm 0.0000

on 39 independent cases. So E154's registered explanation -- that they were the length of the operation --
is **wrong**, and E155's registered prediction with it.

It issued no verdict, correctly, because three gates were mechanically broken and all three were mine:

  * **G2 tested the adjuster against a degenerate self-null.** Duration is the weighting variable, so
    every permutation refits the propensity on it and its weighted null's 95th percentile collapses to
    0.0107. A 93 % removal failed a bar that is tight for reasons unrelated to the data. Identical in
    shape to E140's A1 defect.
  * **G4 failed on one probe of six for the same reason** (`logdur_sigma0.25`, 0.0929 against a p95 of
    0.0573) -- a probe that is nearly a deterministic function of the adjuster inherits its degeneracy.
  * **G3 passed and could not fail upward.** `P:arm_sigma2.0` went raw 0.0400 -> weighted 0.2748,
    retaining **687 %**. The weighted statistic has a different scale from the raw one, so a one-sided
    "retain >= 70 %" gate is satisfied by inflation. Fourth gate-mechanics defect in one day.

=========================================================================================================
THE FOUR CHANGES
=========================================================================================================
**1. GATE Q BECOMES FRACTIONAL.** The adjuster must lose **>= 80 % of its raw legibility** under the
weighting. Scale-free, non-degenerate, and it measures what the gate was always meant to measure.
(E155's observed removal is 93 %, so this bar is already known to be clearable -- which is disclosed, and
which is why the gate's *usefulness* now rests on G3 and G4 rather than on Q.)

**2. GATE S BECOMES FRACTIONAL** for the same reason and with the same 80 % bar.

**3. GATE P BECOMES TWO-SIDED: retention must lie in [0.70, 1.50].** An adjustment that inflates a signal
sevenfold is not preserving it, and a gate that accepts inflation cannot certify that a surviving effect
was preserved rather than manufactured. **This can now fail, and on E155's numbers it would have.**

**4. TWO ADDED CHECKS, NEITHER OF WHICH IS A GATE, BOTH OF WHICH CAN EMBARRASS THE RESULT.**

    **DIRECTION.** The signed AUC, not the folded one. The anaesthesia literature holds that sevoflurane
    produces a LOWER frontal alpha peak frequency and MORE theta than propofol at comparable depth. So
    the mixed arm should have lower `alpha_peak_hz` and higher `rel_theta`. **If the sign is reversed,
    the effect is real and it is not the pharmacology it looks like**, and that is a much more
    interesting problem than a null. E43's fourth-occurrence lesson is exactly this: a confidence
    interval answers "excludes the null", never "supports the hypothesis".

    **DEPTH SPECIFICITY.** If the arms simply differ in anaesthetic depth at 10 minutes, the canonical
    depth indices should separate them first. E155 found `rel_alpha` at 0.0732 and `spectral_edge_95` at
    0.1499, both below the null, while theta and alpha peak frequency cleared it -- a specific pattern
    rather than a global shift. Recomputed and reported here as a contrast, with the depth indices named
    in advance so the comparison is not assembled after seeing which features won.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
**IF EITHER SURVIVOR FAILS THE REPAIRED GATES, OR THE DIRECTION IS REVERSED**, nothing is claimed and the
file reports which. A reversed direction in particular must not be presented as "agent identification"
with the sign quietly dropped.

**IF BOTH SURVIVE WITH THE PREDICTED DIRECTION**, then the frontal spectrum identifies whether
sevoflurane was co-administered, at matched unresponsiveness, on 39 independent cases, against a
cluster-level null, after the one measured confounder is weighted out. **That is the drug-identification
half of Challenge A coming out POSITIVE**, which is unfavourable for any candidate built from the
amplitude family and is the first agent-identification result in this project to survive a correct null.
It would also be a measurement the field would recognise -- which is a reason to distrust its novelty,
not its validity.

**REGISTERED PREDICTION: both survive, with the literature's direction.** This is the first time in this
sequence the prediction favours a positive, and it is made only because E155 already showed the effect
surviving the confounder it was built to test; predicting a null here would be pretending not to have
seen that.

SCOPE. `mixed` is a care-pathway variable, not a randomised assignment, and this deposit records no age,
sex, surgery type or comorbidity. Anything that differs between the two care pathways and shows up in
frontal theta is an alternative explanation this cohort cannot exclude. Stated here, not appended later.

WHAT WAS ALREADY SEEN (rule 41). All of E155's output including every candidate's raw and weighted
legibility, all six S probes, all three P probes, and the weighted null percentiles.

    python bsde/src/bsde/experiments/e156_repaired_gates_and_direction.py
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import auc, auc_abs                                   # noqa: E402

sys.path.insert(0, HERE)
from e141_family_split_quality_audit_v2 import _logit, ranks, wauc             # noqa: E402
from e154_lambda_on_mgh_or import FEATURES, MIN_EPOCHS, _f                     # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "mgh_power_windows.csv")
OUT = os.path.join(RESULTS, "e156_repaired_gates.json")
E155_JSON = os.path.join(RESULTS, "e155_duration_adjusted.json")

WINDOW = 300            # epochs of unconsciousness summarised, identical for every case
PERMS = 5000
MIN_PER_ARM = 12
RETAIN_LO, RETAIN_HI = 0.70, 1.50     # two-sided: inflation is not preservation
REMOVAL = 0.80                        # an adjuster must lose >=80% of its raw legibility
DEPTH_INDICES = ("rel_alpha", "spectral_edge_95")   # named before the run, not after


def load():
    per = defaultdict(list)
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["cohort"] == "OR":
            per[r["case"]].append(r)
    cases = {}
    for c, rows in per.items():
        if rows[0]["arm"] == "pure_sevo":
            continue
        rows.sort(key=lambda r: _f(r["t"]))
        good = [r for r in rows if r["quality"] == "1"]
        con = [r for r in good if r["label"] == "1"]
        unc = [r for r in good if r["label"] == "0"]
        if len(con) < MIN_EPOCHS or len(unc) < WINDOW:
            continue
        seg = unc[:WINDOW]
        t = np.array([_f(r["t"]) for r in rows], float)
        cases[c] = {"arm": 1 if rows[0]["arm"] == "mixed" else 0,
                    "duration_s": float(np.nanmax(t) - np.nanmin(t)),
                    "n_unc": float(len(unc)),
                    **{f: float(np.nanmedian([_f(r[f]) for r in seg])) for f in FEATURES}}
    return cases


def main(argv=None) -> int:
    rng = np.random.default_rng(155)
    cases = load()
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids])
    dur = np.array([cases[c]["duration_s"] for c in ids], float)
    n_mix, n_pro = int(arm.sum()), int((1 - arm).sum())
    out = {"experiment": "E156", "window_epochs": WINDOW, "n_cases": len(ids),
           "n_mixed": n_mix, "n_propofol": n_pro, "perms": PERMS}

    g1 = n_mix >= MIN_PER_ARM and n_pro >= MIN_PER_ARM
    print(f"G1 MANIFEST  {len(ids)} cases with >= {WINDOW} good unconscious epochs: "
          f"{n_pro} pure propofol, {n_mix} mixed -> {'PASS' if g1 else 'FAIL'}")

    rd = ranks(dur)
    X = np.c_[np.ones(len(rd)), (rd - rd.mean()) / (rd.std() + 1e-12)]
    e = 1.0 / (1.0 + np.exp(-X @ _logit(X, arm.astype(float))))
    w_ovl = np.where(arm == 1, 1 - e, e)
    print(f"   propensity(arm | rank duration) range {e.min():.3f}-{e.max():.3f}")

    def raw(v, lab):
        m = np.isfinite(v)
        if len(set(lab[m].tolist())) < 2 or len(set(v[m].tolist())) < 2:
            return float("nan")
        return auc_abs(list(lab[m]), list(v[m])) - 0.5

    def wtd(v, lab, w):
        m = np.isfinite(v)
        if len(set(lab[m].tolist())) < 2 or len(set(v[m].tolist())) < 2:
            return float("nan")
        a = wauc(list(lab[m]), list(v[m]), w[m])
        return abs(a - 0.5) if math.isfinite(a) else float("nan")

    # ---- the weighted null, recomputing the propensity inside every permutation ------------------------
    cols = {f: np.array([cases[c][f] for c in ids], float) for f in FEATURES}
    cols["duration_s"] = dur
    probes = {}
    for tag, base in (("dur", dur), ("logdur", np.log(np.maximum(dur, 1.0)))):
        b = (base - base.mean()) / (base.std() + 1e-12)
        for s in (0.25, 0.5, 1.0):
            probes[f"S:{tag}_sigma{s}"] = b + s * rng.standard_normal(len(ids))
    for s in (0.5, 1.0, 2.0):
        probes[f"P:arm_sigma{s}"] = arm + s * rng.standard_normal(len(ids))
    cols.update(probes)

    null = {k: np.empty(PERMS) for k in cols}
    for i in range(PERMS):
        p = rng.permutation(arm)
        Xp = np.c_[np.ones(len(rd)), (rd - rd.mean()) / (rd.std() + 1e-12)]
        ep = 1.0 / (1.0 + np.exp(-Xp @ _logit(Xp, p.astype(float))))
        wp = np.where(p == 1, 1 - ep, ep)
        for k, v in cols.items():
            null[k][i] = wtd(v, p, wp)
    q95 = {k: float(np.nanquantile(null[k], 0.95)) for k in cols}
    obs_w = {k: wtd(v, arm, w_ovl) for k, v in cols.items()}
    obs_r = {k: raw(v, arm) for k, v in cols.items()}
    pval = {k: float(np.nanmean(null[k] >= obs_w[k])) for k in cols}
    mean_q95 = float(np.nanmean([q95[f] for f in FEATURES]))
    print(f"   weighted cluster-level null: mean 95th percentile {mean_q95:.4f} "
          f"(E154 unweighted: 0.1904, Krause 15 clusters: 0.2791)")

    # ---- G2 / G3 / G4 -----------------------------------------------------------------------------------
    # GATE Q is FRACTIONAL, not against duration's own null: duration is the weighting variable, so every
    # permutation refits the propensity on it and its weighted null collapses to a degenerate ~0.01. E155
    # failed a 93 % removal against that bar. A removal fraction is scale-free and non-degenerate.
    rem_q = 1.0 - (obs_w["duration_s"] / obs_r["duration_s"]) if obs_r["duration_s"] else float("nan")
    g2 = math.isfinite(rem_q) and rem_q >= REMOVAL
    print(f"\nG2 GATE Q  duration legibility raw {obs_r['duration_s']:+.4f} -> weighted "
          f"{obs_w['duration_s']:+.4f}  removed {rem_q:.1%} (bar {REMOVAL:.0%}) -> "
          f"{'PASS' if g2 else 'FAIL'}")

    print(f"G4 GATE S  duration-driven probes must lose >= {REMOVAL:.0%} of their raw legibility "
          f"(fractional, for the same degeneracy reason as GATE Q)")
    g4 = True
    for k in sorted(p for p in probes if p.startswith("S:")):
        rem = 1.0 - (obs_w[k] / obs_r[k]) if obs_r[k] else float("nan")
        ok = math.isfinite(rem) and rem >= REMOVAL
        g4 &= ok
        print(f"   {k:22s} raw {obs_r[k]:+.4f} -> weighted {obs_w[k]:+.4f}  removed {rem:6.1%}  "
              f"{'ok' if ok else 'FAIL'}")
    print(f"   -> {'PASS' if g4 else 'FAIL'}")

    print(f"G3 GATE P  arm-driven probes orthogonal to duration must retain within "
          f"[{RETAIN_LO:.0%}, {RETAIN_HI:.0%}] -- TWO-SIDED, because an adjustment that inflates a "
          f"signal is not preserving it")
    g3 = True
    for k in sorted(p for p in probes if p.startswith("P:")):
        ret = obs_w[k] / obs_r[k] if obs_r[k] else float("nan")
        ok = math.isfinite(ret) and RETAIN_LO <= ret <= RETAIN_HI
        g3 &= ok
        print(f"   {k:22s} raw {obs_r[k]:+.4f} -> weighted {obs_w[k]:+.4f}  retains {ret:6.1%}  "
              f"{'ok' if ok else 'FAIL'}")
    print(f"   -> {'PASS' if g3 else 'FAIL'}")
    out["G1"] = bool(g1)
    out["G2"] = {"pass": bool(g2), "raw": obs_r["duration_s"], "weighted": obs_w["duration_s"],
                 "null_p95": q95["duration_s"]}
    out["G3"] = {"pass": bool(g3), "probes": {k: {"raw": obs_r[k], "weighted": obs_w[k]}
                                              for k in probes if k.startswith("P:")}}
    out["G4"] = {"pass": bool(g4), "probes": {k: {"raw": obs_r[k], "weighted": obs_w[k],
                                                  "null_p95": q95[k]}
                                              for k in probes if k.startswith("S:")}}
    out["weighted_null_mean_q95"] = mean_q95

    gates = g1 and g2 and g3 and g4
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    hp = holm([pval[f] for f in FEATURES], FEATURES)
    print(f"{'candidate':18s} {'raw':>8s} {'weighted':>9s} {'null p95':>9s} {'p':>8s} {'p_holm':>8s} "
          f"{'E154 raw':>9s}")
    e154 = {}
    try:
        e154 = {k: v["drug_leg"] for k, v in
                json.load(open(os.path.join(RESULTS, "e154_lambda_mgh_or.json")))["per_feature"].items()}
    except Exception:                                                          # noqa: BLE001
        pass
    res = {}
    for f in sorted(FEATURES, key=lambda x: -obs_w[x]):
        res[f] = {"raw": obs_r[f], "weighted": obs_w[f], "null_p95": q95[f], "p": pval[f],
                  "p_holm": hp[f], "e154_raw": e154.get(f, float("nan")),
                  "clears": bool(hp[f] < 0.05 and obs_w[f] > q95[f])}
        print(f"{f:18s} {obs_r[f]:8.4f} {obs_w[f]:9.4f} {q95[f]:9.4f} {pval[f]:8.4f} {hp[f]:8.4f} "
              f"{e154.get(f, float('nan')):9.4f}")
    out["per_feature"] = res

    # ---- DIRECTION: signed AUC. Literature predicts sevoflurane -> LOWER alpha peak, MORE theta -------
    print(f"\nDIRECTION (signed AUC for the MIXED arm; >0.5 means mixed scores higher)")
    signed, expect = {}, {"alpha_peak_hz": "lower", "rel_theta": "higher"}
    for f in FEATURES:
        v = np.array([cases[c][f] for c in ids], float)
        m = np.isfinite(v)
        a = auc(list(arm[m]), list(v[m])) if len(set(arm[m].tolist())) > 1 else float("nan")
        signed[f] = a
        note = ""
        if f in expect:
            got = "higher" if a > 0.5 else "lower"
            note = f"   predicted {expect[f]}, observed {got} -> {'MATCHES' if got == expect[f] else 'REVERSED'}"
        print(f"   {f:18s} AUC(mixed) = {a:.4f}{note}")
    out["direction"] = {"signed_auc": signed, "predicted": expect}
    dir_ok = all((signed[f] < 0.5) == (expect[f] == "lower") for f in expect if math.isfinite(signed[f]))

    print(f"\nDEPTH SPECIFICITY (named in advance: {', '.join(DEPTH_INDICES)})")
    for f in DEPTH_INDICES:
        print(f"   {f:18s} weighted {obs_w[f]:.4f}  null p95 {q95[f]:.4f}  "
              f"{'separates' if obs_w[f] > q95[f] else 'does NOT separate'}")
    depth_quiet = all(obs_w[f] <= q95[f] for f in DEPTH_INDICES)
    out["depth_specificity"] = {"quiet": bool(depth_quiet),
                                "indices": {f: {"weighted": obs_w[f], "null_p95": q95[f]}
                                            for f in DEPTH_INDICES}}

    clears = [f for f in FEATURES if res[f]["clears"]]
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif clears and not dir_ok:
        verdict = (f"REAL BUT NOT THE PHARMACOLOGY IT LOOKS LIKE -- {', '.join(clears)} clear the "
                   f"weighted cluster-level null, but the SIGN is reversed against the literature "
                   f"prediction (sevoflurane: lower alpha peak, more theta). Signed AUCs "
                   f"{ {f: round(signed[f], 4) for f in expect} }. Something separates these arms and it "
                   f"is not the agent difference the features were expected to encode. Not claimed as "
                   f"agent identification.")
    elif clears:
        verdict = (f"POSITIVE -- {', '.join(clears)} identify whether sevoflurane was co-administered at "
                   f"matched unresponsiveness, on a fixed 10-minute window and after overlap weighting "
                   f"on duration, against a weighted cluster-level null. The registered prediction is "
                   f"WRONG. Any Challenge A candidate built from these features carries agent identity, "
                   f"and that is a finding rather than a caveat. Direction matches the literature; the "
                   f"named depth indices {'stay quiet' if depth_quiet else 'ALSO separate, so a depth difference is not excluded'}. "
                   f"`mixed` is a care-pathway variable, not a randomised assignment, and this deposit "
                   f"records no covariates -- that limit is not removable here.")
    else:
        verdict = (f"NEGATIVE, AND E154's TWO HITS WERE DURATION -- nothing clears once the summary is "
                   f"taken over a fixed 10-minute window and duration is weighted out. rel_theta went "
                   f"{e154.get('rel_theta', float('nan')):.4f} -> {obs_w['rel_theta']:.4f} and "
                   f"alpha_peak_hz {e154.get('alpha_peak_hz', float('nan')):.4f} -> "
                   f"{obs_w['alpha_peak_hz']:.4f}. On 39 independent cases the frontal amplitude family "
                   f"does not identify the agent at matched unresponsiveness, with the weighted null's "
                   f"floor at {mean_q95:.4f}.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
