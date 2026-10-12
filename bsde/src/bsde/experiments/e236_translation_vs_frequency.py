#!/usr/bin/env python3
"""E236 -- translation sensitivity or frequency range? A head-to-head on the same 4-versus-11 split.

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E235 by an instrument change: a SECOND measured instrument property is added, so the two
competing explanations of the same split can be separated instead of one being assumed.

WHERE THIS COMES FROM. E235 correlated each panel measure's synthetic TRANSLATION SENSITIVITY against
its empirical SEVOFLURANE ADVANTAGE (|mean signed rho| in the sevoflurane arm minus the propofol arm) and
got rho = +0.6107, permutation p_hi = 0.0100, with every gate passing. A post-hoc check withdrew it: four
measures -- `emg_index`, `emg_kurtosis`, `exponent_gamma`, `exponent_high` -- have essentially zero
translation sensitivity AND negative sevoflurane advantage, and dropping them collapses the correlation
among the remaining eleven to **+0.0273, p_hi = 0.4705**. The association is a 4-versus-11 threshold
contrast, not a dose-response, and it is now catalogue rule 89.

**THE PROBLEM THAT LEAVES IS A CONFOUNDED GROUPING, AND IT IS EXACTLY RULE 50.** Those four measures are
all HIGH-FREQUENCY or EMG measures. "Sevoflurane's effect is concentrated at low frequencies" produces
the identical 4-versus-11 split with no translation in it whatsoever. E235 named one mechanism for a
split that two mechanisms predict equally well, which is naming a cause without the control that
separates causes.

WHAT THIS FILE ADDS. A second instrument property, measured the same way and on the same synthetic
signals, so the two can be put in competition:

  TRANSLATION SENSITIVITY (E235's, unchanged): mean |change| when a peak at the sevoflurane arm's own
  median frequency is moved down by half that arm's median within-case excursion, over the candidate's
  across-seed standard deviation. Geometry derived at run time, not chosen (rules 4 and 63).

  RESPONSE CENTROID, new: a narrowband bump is injected at each frequency from 2 to 44 Hz in turn and the
  candidate's absolute response measured; the centroid is the response-weighted mean frequency. It says
  WHERE IN THE SPECTRUM a candidate looks, and it is a property of the code alone -- no real recording is
  touched by either axis, so neither can peek at a label.

PRIMARIES, all across the 15 measures, all against permutation nulls (10,000 draws) and never a
parametric p, because 15 dependent measures make a parametric p wrong in the direction that flatters
whichever hypothesis is being tested.

  P1  partial Spearman(advantage, translation sensitivity | centroid).
  P2  partial Spearman(advantage, centroid | translation sensitivity).
      Whichever survives conditioning on the other is the explanation the data prefer. Both surviving
      means both contribute; neither surviving means the split is real and neither instrument property
      explains it, which is a third and perfectly good answer.
  P3  RULE 89 APPLIED AT REGISTRATION RATHER THAN POST HOC. P1 and P2 are recomputed on the subset with
      NON-ZERO translation sensitivity. E235's headline died on exactly this check, so it is registered
      here as a primary rather than discovered afterwards. A predictor that survives P1/P2 but dies in P3
      is reported as a threshold contrast, never as a dose-response.

GATES, each able to go either way (rules 40 and 81).

  G1  THE TWO INSTRUMENT PROPERTIES MUST NOT BE COLLINEAR -- rule 60 run as a gate. If translation
      sensitivity and centroid correlate above 0.9 across the measures, no partial correlation can
      separate them and the head-to-head is impossible; the file must say so rather than reporting
      unstable partials. The observed |rho| between them is printed either way.
  G2  CAPABILITY, THREE SYNTHETIC CANDIDATES WHOSE ANSWERS ARE KNOWN BY CONSTRUCTION, and they are chosen
      to dissociate the two axes rather than merely to work. (i) power in a fixed 8-13 Hz box: HIGH
      translation sensitivity, MID centroid. (ii) power in a fixed 30-45 Hz box: near-ZERO translation
      sensitivity, because a peak moving from ~9.7 to ~7.5 Hz never enters it, and HIGH centroid. (iii)
      total broadband power: near-ZERO translation sensitivity and a BROAD centroid. Probe (ii) is the
      one that matters: it is high-frequency AND translation-insensitive, which is precisely the
      confounded combination the real four measures have, and if the two axes cannot tell (i) from (ii)
      they cannot do this experiment.
  G3  BOTH AXES MUST VARY across the measures.
  G4  COVERAGE: at least 12 measures on all three axes.

PLACEBO. Each instrument property is permuted across measures independently, preserving both marginals
and destroying only the pairing with empirical behaviour. This is the destruction that matches the
estimand (rule 55), and it is compared against its DISTRIBUTION (rule 37).

VERDICT RULE, wrong-direction cases enumerated FIRST (rule 37).

  (a) P2 survives with the WRONG SIGN -- centroid POSITIVELY related to sevoflurane advantage, i.e.
      high-frequency measures showing MORE advantage -> WRONG DIRECTION for the frequency explanation,
      reported as such rather than folded into a null.
  (b) Neither P1 nor P2 survives its permutation null -> NEITHER INSTRUMENT PROPERTY EXPLAINS THE SPLIT.
      The 4-versus-11 contrast stands as an unexplained fact about the panel, and Challenge A's
      panel-wide magnitude claim is neither supported nor refuted by instrument properties.
  (c) P1 survives and P2 does not -> TRANSLATION, and E235's withdrawn verdict is reinstated with the
      confound now controlled.
  (d) P2 survives and P1 does not -> FREQUENCY RANGE. Sevoflurane's advantage tracks where a measure
      looks in the spectrum, not how it responds to the spectrum moving, and the translation story is
      dead.
  (e) Both survive -> BOTH CONTRIBUTE, reported with both partials and no claim about which dominates.

  In every branch, P3 is reported beside the verdict, and any branch resting on a predictor that dies in
  P3 is restated as a threshold contrast. Gating, applied AFTER the primaries because a gate can only
  invalidate a pass and never rescue a null (rule 37): G1 failing -> NOT INTERPRETABLE, the properties
  are the same property. G2 failing -> NOT INTERPRETABLE.

SCOPE. Both instrument axes are measured on a single-channel pink-plus-peak model at 128 Hz; a candidate
whose behaviour depends on real EEG structure absent from that model is mis-scored on both axes equally.
The unit of analysis is the measure, so n = 15 and this is low-powered by construction. The measures are
not independent (rule 60) and no effective-n correction is attempted or claimed. BIS is not used.

INCUMBENT (rule 45): translation sensitivity, E235's explanation, which frequency range must beat or fail
to beat on the same measures, the same signals and the same code path.

    python bsde/src/bsde/experiments/e236_translation_vs_frequency.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

SFREQ = 128.0
DURATION_S = 30.0
N_SEEDS = 10
SWEEP = tuple(range(2, 45, 2))
MIN_WINDOWS = 10
MIN_CASES = 20
MIN_MEASURES = 12
N_PERM = 10000
COLLINEAR_MAX = 0.9
SEED = 20260802

GRID = "bsde/results/vitaldb_grid.s*.csv"
IAF = "bsde/results/vitaldb_iaf.s*.csv"
PK = "bsde/results/vitaldb_pk_inputs.s%d.jsonl"
OUT = "bsde/results/e236_translation_vs_frequency.json"
SKIP = ("meta_", "recording_id", "dataset", "subject", "status", "error",
        "n_channels", "sfreq", "n_samples")


def _num(r, f):
    try:
        return float(r[f])
    except (TypeError, ValueError, KeyError):
        return float("nan")


def _hold(track, t_eval):
    import numpy as np
    t = np.asarray(track["t"], float)
    v = np.asarray(track["v"], float)
    ok = np.isfinite(t) & np.isfinite(v)
    t, v = t[ok], v[ok]
    if t.size == 0:
        return np.full(len(t_eval), np.nan)
    o = np.argsort(t)
    t, v = t[o], v[o]
    i = np.searchsorted(t, np.asarray(t_eval, float), side="right") - 1
    return np.where(i >= 0, v[np.clip(i, 0, len(v) - 1)], np.nan)


def _live(tr, key):
    import numpy as np
    if key not in tr:
        return False
    v = np.asarray(tr[key]["v"], float)
    return bool(np.isfinite(v).any() and np.nanmax(v) > 0)


def _rho(x, e):
    import numpy as np
    from bsde.verifier.stats import spearman
    m = np.isfinite(x) & np.isfinite(e)
    if m.sum() < MIN_WINDOWS or np.std(x[m]) <= 0 or np.std(e[m]) <= 0:
        return float("nan")
    return float(spearman(x[m], e[m]))


def _signal(f0, seed, amp=1.2):
    import numpy as np
    rng = np.random.default_rng(seed)
    n = int(SFREQ * DURATION_S)
    t = np.arange(n) / SFREQ
    return np.vstack([np.cumsum(rng.normal(0, 1, n)) * 0.4
                      + amp * np.sin(2 * np.pi * f0 * t + rng.uniform(0, 6))
                      for _ in range(2)])


def _background(seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    n = int(SFREQ * DURATION_S)
    return np.vstack([np.cumsum(rng.normal(0, 1, n)) * 0.4 for _ in range(2)])


def _eval(fn, sig):
    try:
        v = float(fn(sig, ["a", "b"], SFREQ, {}))
    except Exception:
        return float("nan")
    return v


def translation_sensitivity(fn, f0, shift):
    import numpy as np
    base = np.asarray([_eval(fn, _signal(f0, 100 + s)) for s in range(N_SEEDS)], float)
    moved = np.asarray([_eval(fn, _signal(f0 - shift, 100 + s)) for s in range(N_SEEDS)], float)
    ok = np.isfinite(base) & np.isfinite(moved)
    if ok.sum() < N_SEEDS // 2:
        return float("nan")
    sd = float(np.std(base[ok], ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return float("nan")
    return float(np.mean(np.abs(moved[ok] - base[ok])) / sd)


def response_centroid(fn):
    """Response-weighted mean frequency: WHERE in the spectrum this candidate looks.

    A narrowband bump is injected at each swept frequency and the candidate's absolute deviation from its
    own background value is the response at that frequency. Normalising by the background's across-seed
    sd puts every candidate on the same scale before weighting, so a loud candidate does not get a
    different centroid from a quiet one with the same shape.
    """
    import numpy as np
    bg = np.asarray([_eval(fn, _background(200 + s)) for s in range(N_SEEDS)], float)
    ok = np.isfinite(bg)
    if ok.sum() < N_SEEDS // 2:
        return float("nan"), float("nan")
    mu, sd = float(np.mean(bg[ok])), float(np.std(bg[ok], ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return float("nan"), float("nan")
    resp = []
    for f in SWEEP:
        v = np.asarray([_eval(fn, _signal(float(f), 300 + s)) for s in range(N_SEEDS)], float)
        v = v[np.isfinite(v)]
        resp.append(abs(float(np.mean(v)) - mu) / sd if len(v) else 0.0)
    resp = np.asarray(resp, float)
    tot = resp.sum()
    if not np.isfinite(tot) or tot <= 0:
        return float("nan"), 0.0
    return float((np.asarray(SWEEP, float) * resp).sum() / tot), float(tot)


def partial_spearman(x, y, z):
    """Spearman partial: correlate the residuals of the ranks."""
    import numpy as np
    from bsde.verifier.stats import _midranks
    X, Y, Z = _midranks(np.asarray(x, float)), _midranks(np.asarray(y, float)), _midranks(np.asarray(z, float))
    for a in (X, Y, Z):
        if np.std(a) <= 0:
            return float("nan")
    rxy = np.corrcoef(X, Y)[0, 1]
    rxz = np.corrcoef(X, Z)[0, 1]
    ryz = np.corrcoef(Y, Z)[0, 1]
    d = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    return float((rxy - rxz * ryz) / d) if d > 0 else float("nan")


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import read_rows, spearman
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    rng = np.random.default_rng(SEED)
    seed_registry()

    # ---- empirical axis ------------------------------------------------------------------------------
    rows = []
    for p in sorted(glob.glob(GRID)):
        r, _ = read_rows(p)
        rows += r
    cols = [k for k in rows[0] if not k.startswith(SKIP) and k != "uce_v1"]
    by = {}
    for r in rows:
        by.setdefault(r["meta_caseid"], []).append(r)
    for c in by:
        by[c].sort(key=lambda r: _num(r, "meta_t_s"))
    tracks = {}
    for s in range(4):
        for line in open(PK % s):
            rr = json.loads(line)
            tracks[rr["caseid"]] = rr

    arms = {"propofol": [], "sevoflurane": []}
    rho = {"propofol": {}, "sevoflurane": {}}
    for c, panel in by.items():
        tr = tracks[c]["tracks"]
        hp, hs, hd = (_live(tr, "Orchestra/PPF20_CE"), _live(tr, "Primus/EXP_SEVO"),
                      _live(tr, "Primus/EXP_DES"))
        if hp and (hs or hd):
            continue
        arm = "propofol" if hp else ("sevoflurane" if hs else None)
        if arm is None:
            continue
        te = [_num(r, "meta_t_s") for r in panel]
        if len(te) < MIN_WINDOWS:
            continue
        e = _hold(tr["Orchestra/PPF20_CE" if arm == "propofol" else "Primus/EXP_SEVO"], te)
        if np.isfinite(e).sum() < MIN_WINDOWS or np.nanstd(e) <= 0:
            continue
        arms[arm].append(c)
        rho[arm][c] = {f: _rho(np.asarray([_num(r, f) for r in panel], float), e) for f in cols}
    print(f"arms: {{'propofol': {len(arms['propofol'])}, 'sevoflurane': {len(arms['sevoflurane'])}}}")

    adv = {}
    for f in cols:
        a = np.asarray([rho["propofol"][c][f] for c in arms["propofol"]], float)
        b = np.asarray([rho["sevoflurane"][c][f] for c in arms["sevoflurane"]], float)
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if len(a) >= MIN_CASES and len(b) >= MIN_CASES:
            adv[f] = abs(float(b.mean())) - abs(float(a.mean()))

    # ---- derived geometry (E235's, unchanged) -----------------------------------------------------------
    per = {}
    for p in sorted(glob.glob(IAF)):
        r, _ = read_rows(p)
        for row in r:
            per.setdefault(row["meta_caseid"], []).append(_num(row, "alpha_peak_hz_wide"))
    meds, exc = [], []
    for c in arms["sevoflurane"]:
        v = np.asarray(per.get(c, []), float)
        v = v[np.isfinite(v)]
        if len(v) >= MIN_WINDOWS:
            meds.append(float(np.median(v)))
            exc.append(float(np.percentile(v, 90) - np.percentile(v, 10)))
    assert meds
    F0, SHIFT = float(np.median(meds)), float(np.median(exc)) / 2.0
    print(f"derived geometry: centre {F0:.3f} Hz, shift {SHIFT:.3f} Hz -> {F0 - SHIFT:.3f} Hz")

    # ---- instrument axes ---------------------------------------------------------------------------------
    sens, cent, mass = {}, {}, {}
    for f in list(adv):
        cand = REGISTRY.get(f)
        if cand is None:
            continue
        s = translation_sensitivity(cand.fn, F0, SHIFT)
        c, m = response_centroid(cand.fn)
        if np.isfinite(s) and np.isfinite(c):
            sens[f], cent[f], mass[f] = s, c, m

    # ---- G2 capability: three probes that DISSOCIATE the two axes -------------------------------------
    def _box(lo, hi):
        def fn(data, ch, sf, meta):
            import numpy as np
            from numpy.fft import rfft, rfftfreq
            x = np.asarray(data, float).mean(axis=0)
            P = np.abs(rfft(x)) ** 2
            fr = rfftfreq(len(x), 1.0 / sf)
            band = (fr >= lo) & (fr <= hi)
            tot = (fr > 0.5) & (fr <= 45.0)
            return float(P[band].sum() / P[tot].sum())
        return fn

    def total_power(data, ch, sf, meta):
        import numpy as np
        return float(np.var(np.asarray(data, float).mean(axis=0)))

    probes = {"fixed_8_13": _box(8.0, 13.0), "fixed_30_45": _box(30.0, 45.0), "total_power": total_power}
    cap = {}
    for k, fn in probes.items():
        c, _m = response_centroid(fn)
        cap[k] = {"sens": translation_sensitivity(fn, F0, SHIFT), "centroid": c}
    g2 = (cap["fixed_8_13"]["sens"] > 1.0 and cap["fixed_30_45"]["sens"] < 0.5
          and cap["fixed_30_45"]["centroid"] > cap["fixed_8_13"]["centroid"] + 5.0
          and cap["total_power"]["sens"] < 0.5)
    print("G2 capability (the two axes must DISSOCIATE, not merely work):")
    for k, v in cap.items():
        print(f"     {k:14s} translation {v['sens']:8.4f}   centroid {v['centroid']:7.3f} Hz")
    print(f"     -> G2 {'PASS' if g2 else 'FAIL'}")

    shared = sorted(set(sens) & set(cent) & set(adv))
    g4 = len(shared) >= MIN_MEASURES
    sv = np.asarray([sens[f] for f in shared], float)
    cv = np.asarray([cent[f] for f in shared], float)
    av = np.asarray([adv[f] for f in shared], float)
    collin = abs(float(spearman(sv, cv)))
    g1 = collin <= COLLINEAR_MAX
    g3 = float(np.std(sv, ddof=1)) > 0 and float(np.std(cv, ddof=1)) > 0
    print(f"G1 collinearity of the two instrument axes: |rho| = {collin:.4f} "
          f"(max {COLLINEAR_MAX}) -> {'PASS' if g1 else 'FAIL'}")
    print(f"G3 both axes vary -> {'PASS' if g3 else 'FAIL'};  G4 {len(shared)} measures -> "
          f"{'PASS' if g4 else 'FAIL'}")

    print()
    print(f"{'measure':30s}{'transl':>10}{'centroid':>10}{'advantage':>11}")
    for f in sorted(shared, key=lambda k: -sens[k]):
        print(f"{f:30s}{sens[f]:10.4f}{cent[f]:10.3f}{adv[f]:+11.4f}")

    def perm_p(stat_fn, obs, which):
        n = len(shared)
        null = []
        for _ in range(N_PERM):
            i = rng.permutation(n)
            null.append(stat_fn(i, which))
        null = np.asarray([v for v in null if np.isfinite(v)], float)
        return float(np.mean(null >= obs)), float(np.mean(null <= obs)), null

    def stat(i, which):
        if which == "sens":
            return partial_spearman(av, sv[i], cv)
        return partial_spearman(av, cv[i], sv)

    p1 = partial_spearman(av, sv, cv)
    p2 = partial_spearman(av, cv, sv)
    p1_hi, p1_lo, _ = perm_p(stat, p1, "sens")
    p2_hi, p2_lo, _ = perm_p(stat, p2, "cent")
    print()
    print(f"P1 partial(advantage, translation | centroid) = {p1:+.4f}   "
          f"perm p_hi {p1_hi:.4f}  p_lo {p1_lo:.4f}")
    print(f"P2 partial(advantage, centroid   | translation) = {p2:+.4f}   "
          f"perm p_hi {p2_hi:.4f}  p_lo {p2_lo:.4f}")

    # ---- P3: rule 89 at registration, not post hoc ------------------------------------------------------
    keep = [f for f in shared if sens[f] > 0.01]
    p3 = {"n": len(keep), "dropped": [f for f in shared if sens[f] <= 0.01]}
    if len(keep) >= 8:
        sk = np.asarray([sens[f] for f in keep], float)
        ck = np.asarray([cent[f] for f in keep], float)
        ak = np.asarray([adv[f] for f in keep], float)
        p3["p1"] = partial_spearman(ak, sk, ck)
        p3["p2"] = partial_spearman(ak, ck, sk)
        nk = len(keep)
        n1 = np.asarray([partial_spearman(ak, sk[rng.permutation(nk)], ck) for _ in range(N_PERM)], float)
        n2 = np.asarray([partial_spearman(ak, ck[rng.permutation(nk)], sk) for _ in range(N_PERM)], float)
        p3["p1_hi"] = float(np.nanmean(n1 >= p3["p1"]))
        p3["p1_lo"] = float(np.nanmean(n1 <= p3["p1"]))
        p3["p2_hi"] = float(np.nanmean(n2 >= p3["p2"]))
        p3["p2_lo"] = float(np.nanmean(n2 <= p3["p2"]))
        print(f"P3 on the {len(keep)} measures with NON-ZERO translation sensitivity "
              f"(rule 89, registered not post hoc):")
        print(f"     P1 {p3['p1']:+.4f} (p_hi {p3['p1_hi']:.4f}, p_lo {p3['p1_lo']:.4f})   "
              f"P2 {p3['p2']:+.4f} (p_hi {p3['p2_hi']:.4f}, p_lo {p3['p2_lo']:.4f})")
        print(f"     dropped: {p3['dropped']}")
    else:
        print(f"P3 not evaluable: only {len(keep)} measures have non-zero translation sensitivity")

    s1 = min(p1_hi, p1_lo) < 0.025
    s2 = min(p2_hi, p2_lo) < 0.025
    if s2 and p2 > 0:
        verdict = ("WRONG DIRECTION for the frequency explanation -- high-frequency measures show MORE "
                   "sevoflurane advantage, the opposite of what 'sevoflurane acts at low frequencies' "
                   "predicts; reported as such rather than folded into a null")
    elif not s1 and not s2:
        verdict = ("NEITHER INSTRUMENT PROPERTY EXPLAINS THE SPLIT -- the 4-versus-11 contrast stands as "
                   "an unexplained fact about the panel, and Challenge A's panel-wide magnitude claim is "
                   "neither supported nor refuted by instrument properties")
    elif s1 and not s2:
        verdict = ("TRANSLATION -- it survives conditioning on where each measure looks in the spectrum, "
                   "so E235's withdrawn verdict is reinstated with the confound controlled")
    elif s2 and not s1:
        verdict = ("FREQUENCY RANGE -- sevoflurane's advantage tracks WHERE a measure looks, not how it "
                   "responds to the spectrum moving; the translation story is dead")
    else:
        verdict = "BOTH CONTRIBUTE -- both partials survive; no claim is made about which dominates"
    if "p1" in p3 and (s1 or s2):
        dead = []
        if s1 and min(p3.get("p1_hi", 1), p3.get("p1_lo", 1)) >= 0.025:
            dead.append("translation")
        if s2 and min(p3.get("p2_hi", 1), p3.get("p2_lo", 1)) >= 0.025:
            dead.append("centroid")
        if dead:
            verdict += (f" | THRESHOLD CONTRAST, not dose-response: {', '.join(dead)} does not survive "
                        "P3 on the non-zero-sensitivity subset (rule 89)")
    if not g2:
        verdict = "NOT INTERPRETABLE -- G2 failed; the two axes do not dissociate a fixed low box from a fixed high box"
    elif not g1:
        verdict = (f"NOT INTERPRETABLE -- G1 failed; the two instrument properties are collinear at "
                   f"|rho| = {collin:.4f} and are the same property (rule 60)")
    elif not g3 or not g4:
        verdict = "NOT INTERPRETABLE -- G3 or G4 failed"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"measures": shared, "sensitivity": sens, "centroid": cent, "advantage": adv,
                   "geometry": {"f0": F0, "shift": SHIFT},
                   "p1": {"est": p1, "p_hi": p1_hi, "p_lo": p1_lo},
                   "p2": {"est": p2, "p_hi": p2_hi, "p_lo": p2_lo},
                   "p3": p3, "collinearity": collin, "capability": cap,
                   "arms": {a: len(arms[a]) for a in arms},
                   "gates": {"G1": bool(g1), "G2": bool(g2), "G3": bool(g3), "G4": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
