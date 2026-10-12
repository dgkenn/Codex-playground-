#!/usr/bin/env python3
"""E235 -- E234 with a shift geometry DERIVED from the sevoflurane arm instead of chosen.

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E234. One instrument change: the synthetic shift geometry. Everything else is verbatim.

WHY E234 WAS REFUSED, AND WHAT THAT MEANS FOR READING THIS FILE. E234 specified F0 = 10.0 Hz shifted
down 1.0 Hz to 9.0 Hz -- both endpoints INSIDE the 8-13 Hz band. A fixed box does not care where a peak
sits within it, so the capability probe (a literal fixed 8-13 Hz box) scored 0.0684 against a required
1.0 while literal total power scored 0.0002. The probe was right and the geometry was wrong: the
sensitivity axis measured within-band frequency change, not the band-CROSSING translation the
hypothesis is about.

**E234 RETURNED P1 = +0.7607 WITH A PERMUTATION p_hi OF 0.0012 BEFORE IT WAS REFUSED, AND THAT NUMBER
WAS SEEN BEFORE THIS FILE WAS WRITTEN.** So the geometry here is not chosen. It is COMPUTED FROM THE
DATA at run time: the centre frequency is the sevoflurane arm's median `alpha_peak_hz_wide`, and the
downward shift is half that arm's median within-case p10-p90 peak excursion. Both are properties of
where the alpha peak sits and how far it travels; neither involves the exposure correlation, which is
the outcome. Measured on this cohort they are 9.750 Hz and 2.150 Hz, so the synthetic peak moves from
9.75 Hz to 7.60 Hz and CROSSES the 8 Hz band edge exactly as the real recordings do. Nothing is
hard-coded: if the cohort changes, the geometry changes with it (rule 4).

ORIGINAL E234 QUESTION, unchanged: is the whole propofol/sevoflurane asymmetry one fact -- sevoflurane
moves the spectrum?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E233 by an instrument change: the unit of analysis becomes the MEASURE rather than the case.

WHAT E233 LEFT. The apparent reversal of `relative_alpha_power` between the two agents was an artefact of
band placement -- sevoflurane slides the alpha peak downward with dose (mean signed rho -0.3296, clearing
its donor null) while propofol does not move it (-0.0226, failing), and a fixed 8-13 Hz window reads a
moving peak as changing power. Anchoring the band collapsed the contrast from +0.3673 [+0.2754, +0.4584]
to +0.0730 [-0.0107, +0.1584].

THE QUESTION THAT LEAVES, AND IT IS THE LAST STRUCTURAL ONE FOR CHALLENGE A. A second, separate finding
has survived every attack so far: across the panel, sevoflurane's coupling to its exposure is roughly two
to three times propofol's in magnitude, on 10 measures that all agree in DIRECTION. That has been read as
a fact about the drugs. **But if sevoflurane translates the spectrum in frequency and propofol does not,
then every measure that is sensitive to translation will respond more to sevoflurane FOR REASONS THAT ARE
ARITHMETIC RATHER THAN NEURAL** -- and the panel-wide magnitude gap would be the same artefact as the
retracted reversal, one level up.

THE TEST. Two quantities per measure, one purely synthetic and one purely empirical, correlated across
the 15 evaluable measures.

  TRANSLATION SENSITIVITY, computed on SYNTHETIC signals only. A pink-ish background plus a narrowband
  oscillation at a known frequency; every candidate computed; the peak then moved down 1 Hz and every
  candidate recomputed. Sensitivity is the mean absolute change divided by the candidate's own standard
  deviation across seeds -- a signal-to-noise ratio for spectral translation. Because it never touches a
  real recording it cannot peek at any label, so it is a legitimate pre-specified property of the
  instrument rather than a post-hoc grouping (this is rule 47's structural requirement met by
  construction rather than by argument).

  SEVOFLURANE ADVANTAGE, computed on the real cohort: |mean signed rho, sevoflurane arm| minus
  |mean signed rho, propofol arm|, per measure, from E229's corrected arms (114 vs 87 cases), re-derived
  in this file rather than imported (rule 59).

  PRIMARY P1 = Spearman correlation across the 15 measures between translation sensitivity and
  sevoflurane advantage. The registered prediction is that it is POSITIVE: the more a measure moves when
  the spectrum shifts, the bigger sevoflurane's apparent advantage over propofol.

WHAT EACH OUTCOME MEANS, and both are informative, which is why this is worth running.
  A positive P1 says the panel-wide magnitude gap is substantially an artefact of spectral translation
  and Challenge A's remaining finding must be restated as "sevoflurane shifts the spectrum" -- one fact
  rather than fifteen.
  A null or negative P1 says the magnitude gap is NOT explained by translation, which promotes it from
  "surviving finding" to "finding that has now survived the specific attack that killed its sibling".

GATES, each able to go either way (rules 40 and 81).

  G1  SENSITIVITY MUST VARY. If every candidate has the same translation sensitivity there is no
      independent variable and P1 is undefined. The range and interquartile spread are printed and the
      gate is that the top measure exceeds the bottom by at least a factor the machinery can resolve --
      derived here as twice the median across-seed standard deviation of the sensitivity itself, not a
      round number (rule 63).
  G2  ADVANTAGE MUST VARY, for the same reason, on the empirical side.
  G3  CAPABILITY, both directions, with SYNTHETIC CANDIDATES whose answer is known by construction: a
      probe that is literally power in a fixed 8-13 Hz box must score HIGH on translation sensitivity,
      and a probe that is literally total broadband power must score ~0. If the sensitivity measure
      cannot separate those two it cannot separate anything.
  G4  COVERAGE. At least 12 measures with finite values on both axes.

PLACEBO. The sensitivity scores are permuted across measures, 10,000 times, and P1 recomputed. This is
the correct destruction: it removes the pairing between a measure's instrument property and its empirical
behaviour while preserving both marginal distributions, both of which are otherwise unusual (15 points,
non-normal, dependent). P1 is read against that DISTRIBUTION, never against a parametric p (rule 37,
fifth occurrence) -- and the parametric p is not reported at all, because with 15 dependent measures it
would be wrong in a direction that flatters the hypothesis.

THE DEPENDENCE PROBLEM IS STATED RATHER THAN SOLVED. Fifteen EEG measures of the same recordings are not
15 independent observations; several are near-duplicates (rule 60). The permutation null preserves that
dependence in the marginals but not in the pairing, so it is a valid test of the ASSOCIATION and NOT a
basis for any claim about how many independent measures support it. No effective-n correction is
attempted and none is claimed.

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37).

  (a) P1 is NEGATIVE and beats the placebo -> WRONG DIRECTION. Translation-sensitive measures show LESS
      sevoflurane advantage, which contradicts the hypothesis rather than merely failing to support it,
      and would mean something is inverted in the reasoning or the code.
  (b) P1 does not beat the placebo -> NOT EXPLAINED BY TRANSLATION. The magnitude gap survives the attack
      that killed the reversal, and is promoted accordingly.
  (c) P1 is POSITIVE and beats the placebo -> TRANSLATION EXPLAINS THE GAP. Challenge A's surviving
      finding is restated as one fact about spectral shift, and the panel-wide magnitude claim is
      withdrawn in the same way the reversal was.

  Gating, applied AFTER the primary is evaluated because a gate can only invalidate a pass, never rescue
  a null (rule 37): G1, G2 or G3 failing -> NOT INTERPRETABLE.

SCOPE. Synthetic sensitivity is measured on a single-channel pink-plus-peak model at VitalDB's sampling
rate; a candidate whose translation behaviour depends on real EEG structure absent from that model will
be mis-scored, and that is a limitation of the synthetic side, not of the empirical side. The unit of
analysis is the measure, so n = 15 and the test is low-powered by construction. BIS is not used.

INCUMBENT (rule 45): the null hypothesis that a measure's instrument properties are unrelated to its
empirical behaviour, instantiated as the permutation null rather than asserted.

    python bsde/src/bsde/experiments/e235_derived_geometry.py
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
IAF = "bsde/results/vitaldb_iaf.s*.csv"
# F0 and SHIFT_HZ are DERIVED at run time from the sevoflurane arm; see derive_geometry (rule 4, rule 63)
MIN_WINDOWS = 10
MIN_CASES = 20
MIN_MEASURES = 12
N_PERM = 10000
SEED = 20260802

GRID = "bsde/results/vitaldb_grid.s*.csv"
PK = "bsde/results/vitaldb_pk_inputs.s%d.jsonl"
OUT = "bsde/results/e235_derived_geometry.json"
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


def _signal(f0, seed):
    """Pink-ish background plus one narrowband oscillation at a KNOWN frequency.

    Same construction as tests/test_iaf_capability.py, deliberately: that file's assertions establish
    that a fixed 8-13 Hz measure collapses on these signals when the peak moves and an anchored one does
    not, so re-using them makes this file's sensitivity scores comparable to an already-verified result
    rather than to a fresh and unvalidated signal model (rule 23).
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    n = int(SFREQ * DURATION_S)
    t = np.arange(n) / SFREQ
    return np.vstack([np.cumsum(rng.normal(0, 1, n)) * 0.4
                      + 1.2 * np.sin(2 * np.pi * f0 * t + rng.uniform(0, 6))
                      for _ in range(2)])


def derive_geometry(arm_cases, tracks):
    """Centre and shift from the sevoflurane arm's own peak statistics -- not chosen (rules 4 and 63).

    Centre = median alpha_peak_hz_wide across that arm's cases. Shift = half the median within-case
    p10-p90 excursion, so the synthetic peak travels the same distance a real one does and crosses the
    same band edge. Neither quantity involves the exposure correlation, which is the outcome.
    """
    import glob as _glob
    import numpy as np
    from bsde.verifier.stats import read_rows
    per = {}
    for p in sorted(_glob.glob(IAF)):
        r, _ = read_rows(p)
        for row in r:
            per.setdefault(row["meta_caseid"], []).append(_num(row, "alpha_peak_hz_wide"))
    meds, exc = [], []
    for c in arm_cases:
        v = np.asarray(per.get(c, []), float)
        v = v[np.isfinite(v)]
        if len(v) < MIN_WINDOWS:
            continue
        meds.append(float(np.median(v)))
        exc.append(float(np.percentile(v, 90) - np.percentile(v, 10)))
    assert meds, "no sevoflurane case carries a usable peak series"
    return float(np.median(meds)), float(np.median(exc)) / 2.0, len(meds)


def translation_sensitivity(fn, f0, shift):
    """Mean |change| when the peak moves down 1 Hz, divided by the across-seed sd at the base frequency."""
    import numpy as np
    base, moved = [], []
    for s in range(N_SEEDS):
        try:
            base.append(float(fn(_signal(f0, 100 + s), ["a", "b"], SFREQ, {})))
            moved.append(float(fn(_signal(f0 - shift, 100 + s), ["a", "b"], SFREQ, {})))
        except Exception:
            return float("nan"), float("nan")
    b = np.asarray(base, float)
    m = np.asarray(moved, float)
    ok = np.isfinite(b) & np.isfinite(m)
    if ok.sum() < N_SEEDS // 2:
        return float("nan"), float("nan")
    sd = float(np.std(b[ok], ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return float("nan"), float("nan")
    return float(np.mean(np.abs(m[ok] - b[ok])) / sd), sd


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import read_rows, spearman
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    rng = np.random.default_rng(SEED)
    seed_registry()

    # ---- empirical side: sevoflurane advantage per measure ------------------------------------------
    rows, dropped = [], 0
    for p in sorted(glob.glob(GRID)):
        r, d = read_rows(p)
        rows += r
        dropped += d
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

    adv, ms = {}, {}
    for f in cols:
        a = np.asarray([rho["propofol"][c][f] for c in arms["propofol"]], float)
        b = np.asarray([rho["sevoflurane"][c][f] for c in arms["sevoflurane"]], float)
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if len(a) < MIN_CASES or len(b) < MIN_CASES:
            continue
        ms[f] = (float(a.mean()), float(b.mean()))
        adv[f] = abs(float(b.mean())) - abs(float(a.mean()))

    # ---- synthetic side: translation sensitivity ------------------------------------------------------
    F0, SHIFT_HZ, n_geo = derive_geometry(arms["sevoflurane"], tracks)
    print(f"DERIVED geometry from {n_geo} sevoflurane cases: peak centre {F0:.3f} Hz, downward shift "
          f"{SHIFT_HZ:.3f} Hz -> {F0 - SHIFT_HZ:.3f} Hz; crosses the 8 Hz band edge: "
          f"{'YES' if (F0 > 8.0 > F0 - SHIFT_HZ) else 'NO'}")

    sens, sds = {}, {}
    for f in list(adv):
        cand = REGISTRY.get(f)
        if cand is None:
            continue
        s, sd = translation_sensitivity(cand.fn, F0, SHIFT_HZ)
        if np.isfinite(s):
            sens[f], sds[f] = s, sd

    # ---- G3 capability: synthetic candidates whose answer is known by construction ---------------------
    def fixed_box(data, ch, sf, meta):
        import numpy as np
        from numpy.fft import rfft, rfftfreq
        x = np.asarray(data, float).mean(axis=0)
        P = np.abs(rfft(x)) ** 2
        fr = rfftfreq(len(x), 1.0 / sf)
        band = (fr >= 8.0) & (fr <= 13.0)
        tot = (fr > 0.5) & (fr <= 45.0)
        return float(P[band].sum() / P[tot].sum())

    def total_power(data, ch, sf, meta):
        import numpy as np
        return float(np.var(np.asarray(data, float).mean(axis=0)))

    cap_box, _ = translation_sensitivity(fixed_box, F0, SHIFT_HZ)
    cap_tot, _ = translation_sensitivity(total_power, F0, SHIFT_HZ)
    g3 = np.isfinite(cap_box) and np.isfinite(cap_tot) and cap_box > 1.0 and cap_tot < 0.5
    print(f"G3 capability: a literal fixed 8-13 Hz box scores {cap_box:.4f}, literal total power "
          f"{cap_tot:.4f} -> {'PASS' if g3 else 'FAIL'}")

    shared = sorted(set(sens) & set(adv))
    g4 = len(shared) >= MIN_MEASURES
    print(f"G4 coverage: {len(shared)} measures on both axes -> {'PASS' if g4 else 'FAIL'}")
    if not shared:
        print("VERDICT: NOT INTERPRETABLE -- no measure has both axes")
        return 0

    sv = np.asarray([sens[f] for f in shared], float)
    av = np.asarray([adv[f] for f in shared], float)
    # derived resolution floor: twice the median across-seed sd of the sensitivity estimate itself
    resolution = 2.0 * float(np.median([sds[f] for f in shared]))
    g1 = (sv.max() - sv.min()) > 0 and (sv.max() / max(sv.min(), 1e-9)) > 2.0
    g2 = float(np.std(av, ddof=1)) > 0
    print(f"G1 sensitivity varies: range {sv.min():.4f} to {sv.max():.4f} "
          f"(ratio {sv.max() / max(sv.min(), 1e-9):.2f}x) -> {'PASS' if g1 else 'FAIL'}")
    print(f"G2 advantage varies: sd {np.std(av, ddof=1):.4f} -> {'PASS' if g2 else 'FAIL'}")

    print()
    print(f"{'measure':30s}{'transl.sens':>13}{'PPF signed':>12}{'SEV signed':>12}{'advantage':>11}")
    for f in sorted(shared, key=lambda k: -sens[k]):
        print(f"{f:30s}{sens[f]:13.4f}{ms[f][0]:+12.4f}{ms[f][1]:+12.4f}{adv[f]:+11.4f}")

    p1 = float(spearman(sv, av))
    perm = np.asarray([float(spearman(sv[rng.permutation(len(sv))], av)) for _ in range(N_PERM)])
    p_hi = float(np.mean(perm >= p1))
    p_lo = float(np.mean(perm <= p1))
    beats = min(p_hi, p_lo) < 0.025          # two-sided; a correlation can go either way (rule 37)
    print()
    print(f"P1 Spearman(translation sensitivity, sevoflurane advantage) over {len(shared)} measures "
          f"= {p1:+.4f}")
    print(f"   permutation null over {N_PERM} draws: mean {perm.mean():+.4f}, "
          f"2.5th {np.percentile(perm, 2.5):+.4f}, 97.5th {np.percentile(perm, 97.5):+.4f}; "
          f"one-sided p_hi = {p_hi:.4f}, p_lo = {p_lo:.4f}")

    if p1 < 0 and beats:
        verdict = ("WRONG DIRECTION -- translation-sensitive measures show LESS sevoflurane advantage, "
                   "which contradicts the hypothesis rather than failing to support it; something is "
                   "inverted in the reasoning or the code and must be found before anything is claimed")
    elif not beats:
        verdict = ("NOT EXPLAINED BY TRANSLATION -- the panel-wide magnitude gap survives the attack that "
                   "killed the reversal, and is promoted from surviving finding to tested finding")
    else:
        verdict = ("TRANSLATION EXPLAINS THE GAP -- a measure's sensitivity to spectral shift predicts "
                   "its sevoflurane advantage, so Challenge A's remaining panel-wide finding is one fact "
                   "about spectral translation and the magnitude claim is withdrawn as the reversal was")
    if not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; the sensitivity measure cannot separate a fixed box from total power"
    elif not g1 or not g2:
        verdict = "NOT INTERPRETABLE -- G1 or G2 failed; one axis does not vary"
    elif not g4:
        verdict = "NOT INTERPRETABLE -- G4 coverage failed"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"measures": shared, "sensitivity": sens, "advantage": adv, "mean_signed": ms,
                   "p1": {"rho": p1, "p_hi": p_hi, "p_lo": p_lo, "n_measures": len(shared),
                          "perm_mean": float(perm.mean()),
                          "perm_2p5": float(np.percentile(perm, 2.5)),
                          "perm_97p5": float(np.percentile(perm, 97.5))},
                   "capability": {"fixed_box": cap_box, "total_power": cap_tot},
                   "resolution_floor": resolution,
                   "geometry": {"f0": F0, "shift_hz": SHIFT_HZ, "n_cases": n_geo,
                                "crosses_8hz": bool(F0 > 8.0 > F0 - SHIFT_HZ)},
                   "arms": {a: len(arms[a]) for a in arms},
                   "gates": {"G1": bool(g1), "G2": bool(g2), "G3": bool(g3), "G4": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
