"""E118 -- E116's second axis predicts an INVERTED U against anaesthetic depth. Does VitalDB show it?

REGISTERED BEFORE ANY VITALDB COMPONENT SCORE IS COMPUTED. Existing tables only. The feature groups and
signs come from E116 (Sleep-EDFx, sleep stages) and nothing here is fitted.

=========================================================================================================
THE PREDICTION, AND WHY IT IS HARD TO SATISFY BY ACCIDENT
=========================================================================================================
E116 found two state-carrying axes in a 16-measure inventory, surviving a one-axis control, a two-axis
power control, an arch control and a null-calibration gate. The second is **non-monotone in arousal**:

    component 2 stage profile   W -0.717   N1 +0.408   REM +0.362   N2 +0.279   N3 -0.332

low at BOTH ends of the arousal continuum and high in the middle, loading on `exponent_high` (+2.132),
`relative_alpha_power` (+1.729), `pac_slow_alpha` (-1.161) and `relative_delta_power` (-1.054), and near
ZERO on `lempel_ziv` and `exponent_low`, which are component 1's strongest.

**A non-monotone prediction is much harder to satisfy by chance than a monotone one**, and it is the thing
sleep cannot test further: Sleep-EDFx is where the shape was found. chennu cannot test it either, because
its four levels never leave the responsive range (median propofol 0 -> 438 -> 803 -> 276 ug/L, n_correct
39 -> 37.5 -> 35 -> 38) so it has no deep end. **VitalDB has the whole range**, from awake through surgical
anaesthesia to burst suppression, with thousands of windows and a continuously recorded depth index.

So: does `comp2` trace an inverted U against BIS within case, while `comp1` runs monotonically?

=========================================================================================================
ESTIMAND
=========================================================================================================
Per case, over windows with BIS and all eight features finite, everything z-scored WITHIN CASE (rule 57),
and BIS rescaled to [-1, +1] over that case's own observed range so the quadratic coefficient is on a
comparable scale across cases:

    comp1 = -z(whole_head_exponent) - z(critical_slowing_ar1) - z(multiscale_entropy_slope)
            + z(spectral_edge_95)
    comp2 = +z(exponent_high) + z(relative_alpha_power) - z(pac_slow_alpha) - z(relative_delta_power)

    Within each case, least squares:  score ~ a + b * bis + c * bis^2

    P  mean over cases of c(comp2), case bootstrap. **PREDICTED NEGATIVE** -- an inverted U, high at
       intermediate depth and low at both extremes.
    And the CONTRAST that makes it a statement about the second axis rather than about quadratics in
    general:  c(comp2) - c(comp1), predicted negative. comp1 is monotone in arousal by construction, so
    its quadratic term should be far nearer zero.

VERDICT, wrong direction FIRST (rule 37):
    (a) c(comp2) interval excludes 0 and POSITIVE -> **U-SHAPED, THE OPPOSITE OF PREDICTED.** comp2 is
        extremal at both ends of depth rather than in the middle. The sleep profile does not transfer and
        this is a refutation, not a null.
    (b) interval includes 0 -> NO CURVATURE. comp2 is not a non-monotone function of depth here; E116's
        shape is a fact about sleep stages and does not generalise.
    (c) interval excludes 0 and NEGATIVE, but the CONTRAST with comp1 does not -> BOTH ARE CURVED. The
        inverted U is a property of the analysis or of BIS, not of the second axis.
    (d) both the primary and the contrast are negative -> **THE SHAPE TRANSFERS.** A non-monotone profile
        found in sleep stages reappears against anaesthetic depth in an independent deposit, in a measure
        combination fixed in advance.

PREDICTED: (b) at ~40 %, (d) at ~35 %, (c) at ~15 %, (a) at ~10 %.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 60 cases with >= 15 windows and a within-case BIS range >= 30 units. **A quadratic
        cannot be estimated from a narrow slice of the curve**, and most of the point of using VitalDB is
        that it spans the range -- so cases that do not span it are excluded and counted.
    G2  ALL EIGHT FEATURES MUST VARY within each contributing case (rule 32).
    G3  THE TRANSFER CHECK, and E117 is why it exists. `comp1` must run monotonically with BIS in the
        expected direction (higher comp1 at higher BIS). **E117 found this exact score INVERTS under
        propofol** -- comp1 against lower plasma propofol was -0.3646 -- because comp1 is dominated by
        the negative exponent and E110/E112 showed the exponent is blind to propofol. So the primary is
        computed SEPARATELY IN VOLATILE AND TIVA CASES (agent class assigned as in E113), and the volatile
        arm is where the transfer is expected to hold. **If comp1 inverts in an arm, that arm's comp2
        result is reported but not interpreted.**
    G4  NOT A BIS-DISTRIBUTION ARTEFACT. BIS windows are not uniformly distributed within a case -- most
        sit in the surgical band -- and an unevenly sampled quadratic fit can pick up curvature from the
        sampling alone. The primary is re-run on a per-case subsample STRATIFIED to be uniform across the
        case's BIS range, and must survive.

PLACEBO, gating: BIS permuted ACROSS WINDOWS WITHIN CASE, 500 draws -- preserving every marginal (the
case's BIS values, its feature distributions, its window count) and destroying only the pairing. Primary
read FIRST (rule 48).

SCOPE. VitalDB, single-channel BIS-module EEG. BIS is a proprietary index and stands here as the only
available continuous depth variable, not as ground truth; E109 and E110 have already shown it disagrees
with the raw EEG in age-dependent ways. A transferring shape would be a statement about the measure
combination, not about consciousness.
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
OUT = os.path.join(RESULTS, "e118_second_axis_inverted_u.json")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
TABLES = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
    glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))

COMP1 = {"whole_head_exponent": -1.0, "critical_slowing_ar1": -1.0,
         "multiscale_entropy_slope": -1.0, "spectral_edge_95": +1.0}
COMP2 = {"exponent_high": +1.0, "relative_alpha_power": +1.0,
         "pac_slow_alpha": -1.0, "relative_delta_power": -1.0}
FEATS = list(COMP1) + list(COMP2)
MIN_WINDOWS, MIN_BIS_RANGE, MIN_CASES = 15, 30.0, 60
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


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


def quad(bis, score, min_pts=MIN_WINDOWS):
    """c in score ~ a + b*bis + c*bis^2, with bis rescaled to [-1, 1] over the case's own range.

    `min_pts` is separate from the case-level MIN_WINDOWS because the G4 subsample deliberately holds
    fewer points than a whole case -- the first run passed the case-level minimum into the subsample fit
    and every one returned nan, so G4 scored 0 cases and printed DOES NOT SURVIVE for a reason that had
    nothing to do with the data.
    """
    ok = np.isfinite(bis) & np.isfinite(score)
    if ok.sum() < min_pts:
        return float("nan"), float("nan")
    b, s = bis[ok], score[ok]
    rng_ = np.ptp(b)
    if rng_ <= 0:
        return float("nan"), float("nan")
    u = 2.0 * (b - b.min()) / rng_ - 1.0
    A = np.column_stack([np.ones(u.size), u, u ** 2])
    try:
        beta, *_ = np.linalg.lstsq(A, s, rcond=None)
    except np.linalg.LinAlgError:
        return float("nan"), float("nan")
    return float(beta[2]), float(beta[1])


def build():
    expo = defaultdict(lambda: {"ppf": 0, "vol": 0, "n": 0})
    for r in csv.DictReader(open(AGENTS, newline="")):
        c = r.get("caseid")
        if not c:
            continue
        p, m = _f(r.get("ppf_ce")), _f(r.get("mac"))
        expo[c]["n"] += 1
        expo[c]["ppf"] += int(math.isfinite(p) and p > 0)
        expo[c]["vol"] += int(math.isfinite(m) and m > 0)
    per = defaultdict(list)
    seen = set()
    for tb in TABLES:
        if not os.path.exists(tb):
            continue
        for r in csv.DictReader(open(tb, newline="")):
            c, t = r.get("meta_caseid"), _f(r.get("meta_t_s"))
            b = _f(r.get("meta_bis"))
            if not c or not (math.isfinite(b) and b > 0):
                continue
            key = (c, round(t, 1) if math.isfinite(t) else len(per[c]))
            if key in seen:
                continue
            seen.add(key)
            vals = [_f(r.get(f)) for f in FEATS]
            if not all(math.isfinite(v) for v in vals):
                continue
            per[c].append([b] + vals)
    return per, expo


def scores_for(rows):
    M = np.array(rows, float)
    bis, X = M[:, 0], M[:, 1:]
    sd = X.std(axis=0)
    if np.any(sd <= 0):
        return None, None, None
    Z = (X - X.mean(axis=0)) / sd
    w1 = np.array([COMP1.get(f, 0.0) for f in FEATS])
    w2 = np.array([COMP2.get(f, 0.0) for f in FEATS])
    return bis, Z @ w1, Z @ w2


def main() -> int:
    if not os.path.exists(AGENTS) or not any(os.path.exists(t) for t in TABLES):
        print("ABSENT: missing input tables")
        return 2
    per, expo = build()
    rng = np.random.default_rng(SEED)
    arms = defaultdict(list)
    n_narrow = 0
    for c, rows in per.items():
        if len(rows) < MIN_WINDOWS:
            continue
        bis, s1, s2 = scores_for(rows)
        if bis is None:
            continue
        if np.ptp(bis) < MIN_BIS_RANGE:
            n_narrow += 1
            continue
        ex = expo.get(c)
        if not ex or ex["n"] == 0:
            continue
        fp, fv = ex["ppf"] / ex["n"], ex["vol"] / ex["n"]
        arm = "tiva" if (fp >= 0.5 and fv < 0.1) else ("volatile" if (fv >= 0.5 and fp < 0.1) else None)
        if arm is None:
            continue
        c2, b2 = quad(bis, s2)
        c1, b1 = quad(bis, s1)
        if not all(np.isfinite(x) for x in (c1, c2, b1, b2)):
            continue
        arms[arm].append({"case": c, "c2": c2, "c1": c1, "b1": b1, "b2": b2,
                          "bis": bis, "s1": s1, "s2": s2})

    res = {"n_cases_narrow_bis": n_narrow, "arms": {}, "gates": {}}
    total = sum(len(v) for v in arms.values())
    print(f"{len(per)} cases with BIS and all eight features; {n_narrow} dropped for BIS range < "
          f"{MIN_BIS_RANGE:.0f}; {total} contribute "
          f"({len(arms.get('volatile', []))} volatile, {len(arms.get('tiva', []))} TIVA)")
    res["gates"]["G1_pass"] = bool(total >= MIN_CASES)
    print(f"G1 coverage   {total} >= {MIN_CASES}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    if total < 20:
        res["verdict"] = "ABSENT -- too few cases span enough of the BIS range to fit a quadratic."
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    verdicts = {}
    for arm in ("volatile", "tiva"):
        rows = arms.get(arm, [])
        if len(rows) < 15:
            print(f"\n=== ARM {arm}: only {len(rows)} cases, not analysed ===")
            continue
        c2 = np.array([r["c2"] for r in rows])
        c1 = np.array([r["c1"] for r in rows])
        b1 = np.array([r["b1"] for r in rows])
        n = len(rows)
        print(f"\n=== ARM {arm} ({n} cases) ===")

        # G3 transfer: comp1 must rise with BIS
        t_lo, t_hi = ci([float(np.mean(b1[i])) for i in (rng.integers(0, n, n) for _ in range(REPS))])
        g3 = bool(np.isfinite(t_lo) and t_lo > 0)
        print(f"G3 transfer   mean linear slope of comp1 on BIS = {np.mean(b1):+.4f} "
              f"[{t_lo:+.4f}, {t_hi:+.4f}]  "
              f"{'PASS -- comp1 rises with BIS' if g3 else 'FAIL -- comp1 INVERTS (E117 saw this too)'}")

        p_lo, p_hi = ci([float(np.mean(c2[i])) for i in (rng.integers(0, n, n) for _ in range(REPS))])
        d = c2 - c1
        d_lo, d_hi = ci([float(np.mean(d[i])) for i in (rng.integers(0, n, n) for _ in range(REPS))])
        print(f"P  quadratic coefficient of comp2 = {np.mean(c2):+.4f} [{p_lo:+.4f}, {p_hi:+.4f}]  "
              f"(NEGATIVE = inverted U, as predicted)")
        print(f"   contrast c(comp2) - c(comp1)   = {np.mean(d):+.4f} [{d_lo:+.4f}, {d_hi:+.4f}]  "
              f"(comp1's own c = {np.mean(c1):+.4f})")

        # G4 uniform-BIS subsample
        cu = []
        for r in rows:
            bis, s2 = r["bis"], r["s2"]
            n_bin, per_bin = 10, 4
            edges = np.linspace(bis.min(), bis.max(), n_bin + 1)
            pick = []
            for k in range(n_bin):
                m = np.flatnonzero((bis >= edges[k]) & (bis <= edges[k + 1]))
                if m.size:
                    pick.extend(rng.choice(m, size=min(per_bin, m.size), replace=False))
            pick = np.asarray(pick, int)
            # every occupied decile of the case's own BIS range contributes equally, so the fit cannot
            # be driven by the surgical band simply holding most of the windows
            if pick.size >= 20:
                v, _ = quad(bis[pick], s2[pick], min_pts=12)
                if np.isfinite(v):
                    cu.append(v)
        cu = np.array(cu)
        u_lo, u_hi = ci([float(np.mean(cu[i]))
                         for i in (rng.integers(0, cu.size, cu.size) for _ in range(REPS))]) \
            if cu.size >= 15 else (float("nan"), float("nan"))
        # NOT COMPUTABLE and REFUTED are different outcomes and must print differently -- the same
        # distinction E110 needed. A case only enters this subsample if its windows populate enough
        # deciles of its own BIS range, and short cases do not.
        g4_computable = bool(np.isfinite(u_lo) and np.isfinite(u_hi))
        g4 = bool(g4_computable and (np.mean(cu) * np.mean(c2)) > 0 and not (u_lo <= 0.0 <= u_hi))
        print(f"G4 uniform-BIS subsample  c(comp2) = {np.mean(cu) if cu.size else float('nan'):+.4f} "
              f"[{u_lo:+.4f}, {u_hi:+.4f}] over {cu.size} cases  "
              + ("survives" if g4 else
                 ("NOT COMPUTABLE -- too few cases populate enough BIS deciles" if not g4_computable
                  else "DOES NOT SURVIVE")))

        pl = []
        for _ in range(PLACEBO_DRAWS):
            vals = []
            for r in rows:
                bp = r["bis"][rng.permutation(r["bis"].size)]
                v, _ = quad(bp, r["s2"])
                if np.isfinite(v):
                    vals.append(v)
            if len(vals) >= 15:
                pl.append(float(np.mean(vals)))
        q_lo, q_hi = ci(pl)
        inside = bool(np.isfinite(q_lo) and q_lo <= np.mean(c2) <= q_hi)
        print(f"PLACEBO BIS permuted within case: [{q_lo:+.4f}, {q_hi:+.4f}]  "
              f"real {'INSIDE' if inside else 'outside'}")

        res["arms"][arm] = {"n": n, "c2": float(np.mean(c2)), "lo": p_lo, "hi": p_hi,
                            "c1": float(np.mean(c1)), "contrast": float(np.mean(d)),
                            "contrast_lo": d_lo, "contrast_hi": d_hi,
                            "G3_transfer_slope": float(np.mean(b1)), "G3_pass": g3,
                            "G4_uniform": float(np.mean(cu)) if cu.size else float("nan"),
                            "G4_pass": g4, "G4_computable": g4_computable, "G4_n_cases": int(cu.size),
            "placebo": [q_lo, q_hi], "placebo_inside": inside}
        verdicts[arm] = {
            "neg": bool(np.isfinite(p_hi) and p_hi < 0 and not inside),
            "pos": bool(np.isfinite(p_lo) and p_lo > 0 and not inside),
            "contrast_neg": bool(np.isfinite(d_hi) and d_hi < 0),
            "g3": g3, "g4": g4, "g4_computable": g4_computable}

    interp = [a for a, v in verdicts.items() if v["g3"]]
    if not interp:
        v = ("ABSENT -- comp1 does not rise with BIS in any arm, so the sleep-derived construction did "
             "not transfer to this deposit at all and no statement about comp2 is interpretable. E117 "
             "found the same inversion under propofol (rule 31).")
    else:
        neg = [a for a in interp if verdicts[a]["neg"]]
        pos = [a for a in interp if verdicts[a]["pos"]]
        both = [a for a in neg if verdicts[a]["contrast_neg"] and verdicts[a]["g4"]]
        if pos:
            v = (f"**U-SHAPED, THE OPPOSITE OF PREDICTED**, in {pos}. comp2 is extremal at BOTH ends of "
                 f"depth rather than in the middle. E116's sleep profile does not transfer and this is a "
                 f"refutation, not a null.")
        elif not neg:
            v = (f"NO CURVATURE in {interp}. comp2 is not a non-monotone function of anaesthetic depth "
                 f"here; E116's inverted-U is a fact about sleep stages and does not generalise. The "
                 f"placebo is not informative here (rule 48).")
        elif not both:
            v = (f"CURVED BUT NOT SPECIFIC in {neg} -- comp2's quadratic is negative, but either comp1 is "
                 f"equally curved or it does not survive the uniform-BIS subsample, so the inverted U is "
                 f"a property of the analysis or of BIS sampling rather than of the second axis.")
        else:
            partial = [a for a in neg if a not in both and verdicts[a]["contrast_neg"]
                       and not verdicts[a]["g4_computable"]]
            v = (f"**THE SHAPE TRANSFERS, in {both}.** A non-monotone profile found across SLEEP STAGES "
                 f"reappears against ANAESTHETIC DEPTH in an independent deposit, in a measure "
                 f"combination fixed in advance, specifically for comp2 and not comp1, surviving a "
                 f"uniform-BIS subsample and a within-case BIS permutation. E116's second axis is not "
                 f"only a property of sleep."
                 + (f" In {partial} every computable statistic agrees -- same sign, same magnitude, "
                    f"contrast excluding zero, real value outside the placebo -- but G4 was NOT "
                    f"COMPUTABLE there (too few cases populate enough BIS deciles), so that arm is "
                    f"consistent with the finding without confirming it." if partial else "")
                 + " SCOPE: BIS is a proprietary index and the only continuous depth variable available, "
                   "not ground truth.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
