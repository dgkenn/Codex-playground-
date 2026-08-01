"""E109 -- WHERE is BIS wrong? Does its agreement with the raw EEG degrade with patient age?

REGISTERED BEFORE ANY AGREEMENT STATISTIC IS COMPUTED. Existing tables only (`vitaldb_grid*.csv`); a
coverage probe was run first (rule 41) and found 246 of 247 cases carry >= 10 windows with BIS, exponent
and age all finite and both measures varying within case, median 48 windows per case, age 0.6-89 with
quartiles 49 / 59 / 69.

=========================================================================================================
WHY THE QUESTION HAD TO CHANGE
=========================================================================================================
Challenge C has now asked "does our measure add to the incumbent?" four times and been told no four times,
on held-out data each time: E78 (comparators tie on held-out recordings), E84 (all 27 candidates NO
INCREMENT over the deposit's own PE31/SEF95, incumbent alive at out-of-bag rho +0.3310), E99 (the exponent
HURTS BIS for suppression detection, -0.0306, and the harm disappears once the monitor's own EMG is in the
baseline), E90/E102 (availability, not validity).

**Four failures with the same shape are a result about the question, not four accidents.** BIS is a
mature, heavily tuned product with EMG suppression and a burst-suppression subparameter; a single-channel
aperiodic slope is not going to beat it at its own endpoint, and this project should stop asking.

The question with clinical value and no incumbent to beat is the complementary one: **where does BIS stop
tracking the EEG at all?** Rule 15 says discrimination without calibration is half a result and the missing
half is the half clinicians use. Age is the first place to look, because BIS's age behaviour is a known
clinical soft spot and because VitalDB records it.

=========================================================================================================
THE ESTIMAND, AND WHY IT NEEDS NO GROUND TRUTH
=========================================================================================================
There is no ground-truth "depth" in this deposit -- BIS is the only depth label and it is the thing under
examination, so any design that scores BIS against a truth is circular. **This design does not need one.**
It measures AGREEMENT between two independent readings of the same patient at the same moment: the
vendor's index, and an aperiodic exponent computed here from the raw waveform. Disagreement does not say
which is right. It says the two come apart, and WHERE.

Per case, over windows with BIS, exponent and age finite:

    agree_c = spearman( meta_bis , whole_head_exponent )   within case, across windows

Both vary within a case because depth changes through an anaesthetic. `agree_c` is expected NEGATIVE: a
steeper (larger) exponent means more low-frequency dominance means deeper anaesthesia means lower BIS.

    P  spearman( agree_c , age_c ) across cases, case bootstrap, 4000 reps.

VERDICT, wrong direction FIRST (rule 37). Note the sign carefully: `agree_c` is negative when the two
agree, so **agreement getting WORSE with age means `agree_c` rising toward zero, i.e. a POSITIVE P.**

    (a) P's interval excludes 0 and NEGATIVE -> AGREEMENT IMPROVES WITH AGE. BIS tracks the raw EEG BETTER
        in older patients. Not what the clinical literature would suggest, and it would need explaining
        before use; named first because it is the outcome that contradicts the motivation.
    (b) interval includes 0 -> NO AGE MODULATION. BIS and the exponent come apart no more in the old than
        in the young on this deposit. A clean negative, and it closes the age angle.
    (c) interval excludes 0 and POSITIVE -> AGREEMENT DEGRADES WITH AGE. The two readings diverge more in
        older patients. **This is a statement about DISCORDANCE and not about which reading is correct**,
        and that distinction must survive into any downstream use.

PREDICTED: (c) at ~45 %, (b) at ~45 %, (a) at ~10 %.

=========================================================================================================
GATES -- G3 is the one most likely to fire and it is the whole methodological risk
=========================================================================================================
    G1  COVERAGE. >= 60 cases with >= 10 windows, BIS and exponent each varying within case (rule 32: a
        rank correlation on a constant is undefined, not zero).
    G2  AGREEMENT EXISTS AT ALL. The median `agree_c` must be clearly negative -- if BIS and the exponent
        do not agree anywhere, there is no agreement for age to modulate and the primary is meaningless.
        Compared against a per-case Gaussian control, not a fixed threshold (rule 63).
    G3  RANGE RESTRICTION, and this gate is the reason the experiment could be wrong. **A correlation is
        attenuated by a narrow range in either variable.** If older patients are simply held over a
        narrower band of depth -- which is clinically plausible, since frail patients are kept lighter and
        more tightly controlled -- their `agree_c` is attenuated for a reason that has nothing to do with
        the monitor. So: the within-case SD of BIS and of the exponent are correlated with age and
        REPORTED, and the primary is re-run as a PARTIAL correlation given both. **If the partial loses
        the interval, the unrestricted estimate is withdrawn**, because it is then a range effect.
        **The same attenuation arrives by a second route that has nothing to do with range: SAMPLE SIZE.**
        A within-case correlation estimated from fewer windows is noisier and therefore attenuated toward
        zero, so if older patients have shorter records their `agree_c` drifts up for a purely statistical
        reason. `log(n_windows)` is therefore a third adjuster in the same partial, and the count is
        correlated with age and reported. Both routes attenuate in the SAME direction as the predicted
        effect, which is what makes them dangerous rather than merely untidy.
    G4  ARTEFACT AND QUALITY. Median `emg_index` and `meta_sqi` per case correlated with age and reported.
        These are NOT adjusted for: SQI is the monitor's own confidence and EMG is partly what BIS
        suppresses, so conditioning on either is conditioning on the mechanism under study (rule 13).
        Reported so a reader can see whether a discordance coincides with the monitor declaring itself
        unreliable -- which E60's corollary says to check before modelling any region a reference behaves
        strangely in.
    G5  NOT A CHILDREN EFFECT. The deposit spans 0.6 to 89 years and a handful of paediatric cases could
        drive everything, in a population where BIS is separately known to be invalid. The primary is
        re-run on ADULTS ONLY (>= 18). Both are reported; a result present only with children included is
        described as a paediatric finding, which is a different and smaller claim.

PLACEBO, gating the verdict: age shuffled across cases, 2000 draws, primary recomputed. A real estimate
inside the placebo's central 95 % is WITHDRAWN. The primary's interval is read FIRST -- a placebo cannot
validate or invalidate a null (rule 48).

SCOPE. VitalDB, single-channel BIS-module EEG, 247 surgical cases. "Agreement" is a within-case rank
correlation between two simultaneous readings and is not an accuracy. Nothing here establishes that either
reading is correct, and nothing here concerns consciousness.
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e109_bis_agreement_by_age.json")
TABLES = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
    glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))

MIN_WINDOWS, MIN_CASES = 10, 60
ADULT_AGE = 18.0
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _rank(x):
    return np.argsort(np.argsort(np.asarray(x, float))).astype(float)


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.ptp(x[ok]) <= 0 or np.ptp(y[ok]) <= 0:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def partial_spearman(x, y, Z):
    """Rank-partial correlation of x and y given the columns of Z."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    Z = np.asarray(Z, float)
    ok = np.isfinite(x) & np.isfinite(y) & np.all(np.isfinite(Z), axis=1)
    if ok.sum() < Z.shape[1] + 6:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    RZ = np.column_stack([np.ones(ok.sum())] + [_rank(Z[ok, j]) for j in range(Z.shape[1])])
    bx, *_ = np.linalg.lstsq(RZ, rx, rcond=None)
    by, *_ = np.linalg.lstsq(RZ, ry, rcond=None)
    ex, ey = rx - RZ @ bx, ry - RZ @ by
    d = float(np.sqrt((ex ** 2).sum() * (ey ** 2).sum()))
    return float((ex * ey).sum() / d) if d > 1e-12 else float("nan")


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def main() -> int:
    if not any(os.path.exists(t) for t in TABLES):
        print("ABSENT: no vitaldb_grid table")
        return 2
    per = defaultdict(list)
    seen = set()
    for t in TABLES:
        if not os.path.exists(t):
            continue
        for r in csv.DictReader(open(t, newline="")):
            c = r.get("meta_caseid")
            b, e, a = _f(r.get("meta_bis")), _f(r.get("whole_head_exponent")), _f(r.get("meta_age"))
            ts = _f(r.get("meta_t_s"))
            if not c or not (math.isfinite(b) and b > 0 and math.isfinite(e) and math.isfinite(a)):
                continue
            key = (c, round(ts, 3) if math.isfinite(ts) else len(per[c]))
            if key in seen:
                continue
            seen.add(key)
            per[c].append((b, e, a, _f(r.get("meta_sqi")), _f(r.get("emg_index"))))

    cases, agree, age, sd_b, sd_e, sqi, emg, nwin = [], [], [], [], [], [], [], []
    for c, v in per.items():
        b = np.array([x[0] for x in v], float)
        e = np.array([x[1] for x in v], float)
        if b.size < MIN_WINDOWS or np.ptp(b) <= 0 or np.ptp(e) <= 0:
            continue
        rho = spearman(b, e)
        if not np.isfinite(rho):
            continue
        cases.append(c); agree.append(rho); age.append(v[0][2])
        sd_b.append(float(b.std())); sd_e.append(float(e.std()))
        sqi.append(float(np.nanmedian([x[3] for x in v])))
        emg.append(float(np.nanmedian([x[4] for x in v])))
        nwin.append(int(b.size))
    agree = np.array(agree); age = np.array(age)
    sd_b = np.array(sd_b); sd_e = np.array(sd_e)
    sqi = np.array(sqi); emg = np.array(emg)

    res = {"n_cases_seen": len(per), "n_cases": len(cases), "gates": {}}
    print(f"{len(per)} cases in the table; {len(cases)} contribute "
          f"(>= {MIN_WINDOWS} windows, both measures varying); median {int(np.median(nwin))} windows/case")
    res["gates"]["G1_pass"] = bool(len(cases) >= MIN_CASES)
    print(f"G1 coverage   {len(cases)} >= {MIN_CASES}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    rng = np.random.default_rng(SEED)
    med = float(np.median(agree))
    gnull = float(np.quantile([np.median(rng.normal(size=agree.size)) for _ in range(2000)], 0.025))
    g2 = bool(med < gnull)
    res["gates"].update({"G2_median_agreement": med, "G2_gaussian_2.5pct": gnull, "G2_pass": g2})
    print(f"G2 agreement  median within-case rho(BIS, exponent) = {med:+.4f}  "
          f"(Gaussian 2.5th pct {gnull:+.4f})  {'PASS' if g2 else 'FAIL'}")
    if not (res["gates"]["G1_pass"] and g2):
        res["verdict"] = ("GATE-FAILED -- no coverage, or BIS and the exponent do not agree anywhere, so "
                          "there is no agreement for age to modulate.")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    point = spearman(agree, age)
    lo, hi = ci([spearman(agree[i], age[i]) for i in (rng.integers(0, agree.size, agree.size)
                                                      for _ in range(REPS))])
    res["primary"] = {"rho": point, "lo": lo, "hi": hi, "n_cases": len(cases)}
    print(f"\nP  spearman(within-case agreement, age) = {point:+.4f} [{lo:+.4f}, {hi:+.4f}]  "
          f"over {len(cases)} cases")
    print("   (agreement is NEGATIVE when the two track each other, so POSITIVE here = worse with age)")

    # ---- G3 RANGE RESTRICTION ---------------------------------------------------------------------
    Z = np.column_stack([sd_b, sd_e, np.log(np.asarray(nwin, float))])
    pr = partial_spearman(agree, age, Z)
    pr_lo, pr_hi = ci([partial_spearman(agree[i], age[i], Z[i])
                       for i in (rng.integers(0, agree.size, agree.size) for _ in range(REPS))])
    g3 = bool(np.isfinite(pr_lo) and not (pr_lo <= 0.0 <= pr_hi) and (pr * point) > 0)
    nw = np.asarray(nwin, float)
    res["gates"]["G3"] = {"rho_sdBIS_age": spearman(sd_b, age), "rho_sdExp_age": spearman(sd_e, age),
                          "rho_nwindows_age": spearman(nw, age),
                          "partial": pr, "lo": pr_lo, "hi": pr_hi, "pass": g3}
    print(f"G3 attenuation  rho(sd BIS, age) {spearman(sd_b, age):+.4f}   "
          f"rho(sd exponent, age) {spearman(sd_e, age):+.4f}   "
          f"rho(n_windows, age) {spearman(nw, age):+.4f}")
    print(f"                PARTIAL given both spreads AND log n_windows: {pr:+.4f} "
          f"[{pr_lo:+.4f}, {pr_hi:+.4f}]  {'survives' if g3 else 'DOES NOT SURVIVE'}")

    # ---- G4 ARTEFACT AND QUALITY, reported never adjusted (rule 13) -------------------------------
    res["gates"]["G4"] = {"rho_sqi_age": spearman(sqi, age), "rho_emg_age": spearman(emg, age),
                          "median_sqi": float(np.nanmedian(sqi))}
    print(f"G4 quality    rho(median SQI, age) {spearman(sqi, age):+.4f}   "
          f"rho(median emg_index, age) {spearman(emg, age):+.4f}   "
          f"median SQI {np.nanmedian(sqi):.1f}  (reported, NOT adjusted -- rule 13)")

    # ---- G5 ADULTS ONLY ---------------------------------------------------------------------------
    ad = age >= ADULT_AGE
    a_point = spearman(agree[ad], age[ad])
    a_lo, a_hi = ci([spearman(agree[ad][i], age[ad][i])
                     for i in (rng.integers(0, int(ad.sum()), int(ad.sum())) for _ in range(REPS))])
    g5 = bool(np.isfinite(a_lo) and (a_point * point) > 0 and not (a_lo <= 0.0 <= a_hi))
    res["gates"]["G5"] = {"n_adults": int(ad.sum()), "n_children": int((~ad).sum()),
                          "rho": a_point, "lo": a_lo, "hi": a_hi, "pass": g5}
    print(f"G5 adults     {int(ad.sum())} adults, {int((~ad).sum())} under {ADULT_AGE:.0f}; "
          f"adults-only {a_point:+.4f} [{a_lo:+.4f}, {a_hi:+.4f}]  "
          f"{'holds' if g5 else 'does NOT hold without children'}")

    pl = [spearman(agree, age[rng.permutation(age.size)]) for _ in range(PLACEBO_DRAWS)]
    p_lo, p_hi = ci(pl)
    inside = bool(np.isfinite(p_lo) and p_lo <= point <= p_hi)
    res["placebo"] = {"lo": p_lo, "hi": p_hi, "inside": inside}
    print(f"\nPLACEBO age shuffled: [{p_lo:+.4f}, {p_hi:+.4f}]  "
          f"real {'INSIDE' if inside else 'outside'}")

    excl = not (lo <= 0.0 <= hi)
    if not excl:
        v = ("NO AGE MODULATION -- BIS and the aperiodic exponent come apart no more in older patients "
             "than in younger ones on this deposit. The age angle is closed. The placebo is NOT "
             "informative here: there was no effect for it to fail to reproduce (rule 48).")
    elif inside:
        v = "WITHDRAWN BY PLACEBO -- shuffling age reproduces the estimate."
    elif not g3:
        v = ("WITHDRAWN BY G3 -- the estimate does not survive adjustment for how wide a range of BIS and "
             "of exponent each case actually spans and for how many windows it contributes, so it is an "
             "attenuation effect and not a statement about the monitor.")
    elif point < 0:
        v = ("AGREEMENT IMPROVES WITH AGE -- BIS tracks the raw EEG BETTER in older patients, which "
             "contradicts the motivation for this experiment and needs explaining before any use.")
    else:
        v = ("AGREEMENT DEGRADES WITH AGE -- the vendor's index and an exponent computed from the raw "
             "waveform diverge more in older patients, surviving adjustment for range restriction"
             + ("" if g5 else " but NOT surviving exclusion of paediatric cases, so it is a paediatric "
                              "finding and must be described as one")
             + ". THIS IS A STATEMENT ABOUT DISCORDANCE AND NOT ABOUT WHICH READING IS CORRECT: this "
               "deposit contains no ground-truth depth, and nothing here shows the exponent is right "
               "where BIS is not.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
