#!/usr/bin/env python3
"""E233 -- is the alpha reversal a property of the OSCILLATION or of the 8-13 Hz BOX we measure it in?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E232 by an instrument change: `relative_alpha_power` replaced by a measure anchored to each
recording's OWN alpha peak. Cohort, arms, gates, statistic and verdict machinery are E229/E232's.

THE STANDING RESULT. Across a 15-measure panel on VitalDB, 10 of the 11 measures clearing a donor null
for directional consistency in both arms AGREE in direction (exact binomial p = 0.0059), and exactly one
reverses: `relative_alpha_power`, +0.1189 against propofol effect-site concentration and -0.2482 against
sevoflurane end-tidal (E229, 114 vs 87 cases). It survived restriction to remifentanil-exposed cases
(E232: +0.1136 / -0.2642, same 10 of 11, same p), so opioid PRESENCE is excluded.

THE THREAT THIS FILE EXISTS TO TEST, AND IT IS THE MOST DANGEROUS ONE LEFT.
`relative_alpha_power` is power in a FIXED 8-13 Hz window divided by total power. It is not a measurement
of an oscillation; it is a measurement of how much of the spectrum happens to fall inside a box. **If the
two agents move the alpha peak in opposite directions relative to that box, a fixed-band measure reverses
with no reversal whatsoever in the underlying rhythm.** Propofol is known to produce frontal alpha and
volatiles to slow the spectrum; a peak drifting across 8 Hz in one arm and sitting inside the band in the
other is sufficient to manufacture the entire finding. Nothing in E229 or E232 can distinguish that from
biology, because both used the fixed band.

THE INSTRUMENT THAT CAN. `bsde.candidates.seed` registers `alpha_peak_hz_wide` (spectral peak located
over a 5-15 Hz search, returning NaN rather than a band edge when there is no peak) and
`relative_alpha_power_iaf` (relative power in a +/-2 Hz window centred on THAT peak). Their capability is
established independently in `tests/test_iaf_capability.py`, on synthetic signals whose true peak is known
by construction, and the three properties that matter were measured there rather than assumed: the fixed
measure collapses by more than fivefold when an unchanged oscillation moves from 10 Hz to 7 Hz; the
anchored measure varies by less than 1.5-fold across peaks from 6 to 14 Hz; and the two do not behave
alike, so anchoring is not cosmetic. That test is re-run here as gate G3 rather than cited, because a
capability claim living in another file is a capability claim not made (rule 22).

ARMS OF THE TEST, all on the same cases and windows.

  A1  DOES THE PEAK ITSELF MOVE IN OPPOSITE DIRECTIONS? Consistency and direction of
      `alpha_peak_hz_wide` against each arm's exposure. This is the MECHANISM the band-placement
      explanation requires. If the peak does not move oppositely, band placement cannot produce the
      reversal and A2 becomes a confirmation rather than a test.
  A2  DOES THE ANCHORED MEASURE REVERSE? `relative_alpha_power_iaf`, same machinery. THE PRIMARY.
  A3  DOES THE FIXED MEASURE REVERSE ON THIS TABLE? `relative_alpha_power` re-derived on the 6,679
      windows the IAF extraction covers, which is a different window set from E229's. A3 is not a
      result; it is the check that A2 is being compared against a like-for-like incumbent rather than
      against a number from another table (rule 59: import the whole row, never a hand-copied subset).

PRIMARY. P1 = the direction contrast for `relative_alpha_power_iaf`, mean signed rho in the propofol arm
minus mean signed rho in the sevoflurane arm, with a cluster bootstrap over cases, read beside the same
contrast for the fixed measure (A3) on identical cases.

  P2 = the count of features clearing the donor null on consistency in both arms whose directions AGREE,
  with the ANCHORED alpha substituted for the fixed one. E229 and E232 both put this at 10 of 11. If
  band placement is the explanation it becomes 11 of 11.

GATES.

  G1  ALIVENESS (rule 53). The sevoflurane arm must clear its donor null on consistency for a majority of
      features, as in E229/E232.
  G2  PEAK DETECTABILITY MUST NOT DIFFER BY ARM, and this is the gate that can most easily sink the file.
      `alpha_peak_hz_wide` is NaN where no peak exists: 6,200 of 6,679 windows are finite overall. If the
      missing windows are concentrated in one arm, the anchored measure is computed on a stratum selected
      on exactly the thing under test (rule 32: a measurement's availability defines a stratum, and that
      stratum is selected on what makes the measurement possible). The per-arm detectability rates and
      their difference are computed, printed, and gated at a difference the machinery can resolve rather
      than at a round number (rule 63): the threshold is the 95th percentile of the arm-label-permuted
      difference, measured here.
  G3  CAPABILITY, run not cited. `tests/test_iaf_capability.py` is executed as a subprocess and must pass
      in full. It contains both the input that should fail (the fixed measure, which must collapse) and
      the input that should pass (the anchored measure, which must stay flat), which is rules 40 and 81.
  G4  COVERAGE. At least 20 cases per arm with a finite anchored measure on at least 10 windows.

PLACEBO. Two, because E230 and E231 both died on a placebo that could not touch their estimand
(rule 88). (i) The DONOR-EXPOSURE null, per feature and per arm, as in E229 -- this is what "clears the
null" means throughout. (ii) An ARM-LABEL PERMUTATION for the direction contrast: arm membership is
shuffled across cases and P1 recomputed, 300 times. That is the only destruction which removes the drug
contrast while preserving cohort, windows, covariates and code path, and E232 declared it and did not
implement it. It is implemented here.

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37, and the catalogue records four prior
occurrences of getting this wrong).

  (a) The anchored contrast excludes zero and is LARGER than the fixed contrast -> BAND PLACEMENT WAS
      MASKING THE EFFECT. The reversal is real and the fixed band understated it. Reported with both
      numbers; this is a strengthening, not a pass by default.
  (b) The anchored contrast excludes zero and is comparable to the fixed contrast -> BIOLOGY. Band
      placement is excluded as the explanation and the reversal is a property of the oscillation.
  (c) The anchored contrast INCLUDES zero, or alpha no longer clears its donor null in one arm, while
      the fixed contrast on the same cases still excludes zero -> BAND PLACEMENT. The reversal is an
      artefact of measuring a moving oscillation through a fixed 8-13 Hz box, and every alpha claim in
      this project -- E229, E232, and the whole Challenge A thread back to NOTE_ALPHA_INSTABILITY.md --
      must be restated as a statement about band placement rather than about the drug.
  (d) The anchored contrast reverses in the OPPOSITE direction to the fixed one -> reported as such,
      with the sign, as a failure to replicate rather than as any kind of pass.

  Gating, applied AFTER the primary is evaluated because a gate can only invalidate a pass, never rescue
  a null (rule 37): G2 or G3 failing -> NOT INTERPRETABLE. The arm-label placebo reproducing P1 -> NOT
  INTERPRETABLE.

SCOPE. VitalDB is single-channel frontal, so this is a frontal alpha statement and nothing else. The
anchored band is +/-2 Hz around a peak located over 5-15 Hz; a rhythm outside that search is invisible to
both measures equally. BIS is not used. The anchors are the recorded exposures.

INCUMBENT (rule 45): `relative_alpha_power`, the fixed-band measure, computed on the identical cases and
windows in arm A3 -- not imported from E229.

    python bsde/src/bsde/experiments/e233_band_placement_or_biology.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

MIN_WINDOWS = 10
MIN_CASES = 20
N_DONOR = 300
N_BOOT = 2000
N_PERM = 300
SEED = 20260802

GRID = "bsde/results/vitaldb_grid.s*.csv"
IAF = "bsde/results/vitaldb_iaf.s*.csv"
PK = "bsde/results/vitaldb_pk_inputs.s%d.jsonl"
OUT = "bsde/results/e233_band_placement_or_biology.json"
CAP_TEST = "tests/test_iaf_capability.py"

FIXED = "relative_alpha_power"
ANCHOR = "relative_alpha_power_iaf"
PEAK = "alpha_peak_hz_wide"
CONTROLS = ("critical_slowing_ar1", "emg_beta_gamma_fraction", "emg_index", "exponent_low",
            "lempel_ziv", "multiscale_entropy_slope", "relative_delta_power", "spectral_edge_95",
            "spectral_entropy", "whole_head_exponent")


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
    """Rule 87: a channel counts only if it is EVER NONZERO."""
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


def consistency(vals):
    """Resultant length |mean signed| / mean|.|, bounded in [0,1]. E227 died proving a median cannot
    do this job for a bimodal sign distribution; this is E227's replacement, unchanged."""
    import numpy as np
    v = np.asarray([x for x in vals if np.isfinite(x)], float)
    if len(v) < MIN_CASES:
        return float("nan"), float("nan"), len(v), float("nan")
    S = float(np.mean(np.abs(v)))
    C = float(abs(np.mean(v)) / S) if S > 0 else float("nan")
    return C, S, len(v), float(np.mean(v))


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import read_rows
    rng = np.random.default_rng(SEED)

    # ---- G3 capability: RUN the test file, do not cite it (rule 22) --------------------------------
    cap = subprocess.run([sys.executable, "-m", "pytest", CAP_TEST, "-q"],
                         capture_output=True, text=True)
    g3 = cap.returncode == 0
    print(f"G3 capability: {CAP_TEST} -> {'PASS' if g3 else 'FAIL'}  "
          f"({cap.stdout.strip().splitlines()[-1] if cap.stdout.strip() else cap.returncode})")

    # ---- join grid and iaf on (caseid, t_s) --------------------------------------------------------
    grid = {}
    for p in sorted(glob.glob(GRID)):
        r, _ = read_rows(p)
        for row in r:
            grid[(row["meta_caseid"], row["meta_t_s"])] = row
    joined = []
    for p in sorted(glob.glob(IAF)):
        r, _ = read_rows(p)
        for row in r:
            g = grid.get((row["meta_caseid"], row["meta_t_s"]))
            if g is None:
                continue
            m = dict(g)
            for k in (ANCHOR, PEAK):
                m[k] = row.get(k, "")
            joined.append(m)
    by = {}
    for row in joined:
        by.setdefault(row["meta_caseid"], []).append(row)
    for c in by:
        by[c].sort(key=lambda r: _num(r, "meta_t_s"))
    print(f"joined: {len(joined)} windows over {len(by)} cases")
    assert len(joined) > 0

    tracks = {}
    for s in range(4):
        for line in open(PK % s):
            r = json.loads(line)
            tracks[r["caseid"]] = r

    FEATS = [ANCHOR, FIXED, PEAK] + list(CONTROLS)
    arms = {"propofol": [], "sevoflurane": []}
    rho = {"propofol": {}, "sevoflurane": {}}
    detect = {"propofol": [], "sevoflurane": []}
    excl = {"few_windows": 0, "exposure_flat": 0}
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
            excl["few_windows"] += 1
            continue
        e = _hold(tr["Orchestra/PPF20_CE" if arm == "propofol" else "Primus/EXP_SEVO"], te)
        if np.isfinite(e).sum() < MIN_WINDOWS or np.nanstd(e) <= 0:
            excl["exposure_flat"] += 1
            continue
        pk = np.asarray([_num(r, PEAK) for r in panel], float)
        detect[arm].append(float(np.mean(np.isfinite(pk))))
        d = {}
        for f in FEATS:
            x = np.asarray([_num(r, f) for r in panel], float)
            d[f] = _rho(x, e)
        arms[arm].append(c)
        rho[arm][c] = d
    print(f"arms: {{'propofol': {len(arms['propofol'])}, 'sevoflurane': {len(arms['sevoflurane'])}}}  "
          f"exclusions (rule 14): {excl}")
    g4 = all(len(arms[a]) >= MIN_CASES for a in arms)
    print(f"G4 coverage: {'PASS' if g4 else 'FAIL'}")

    # ---- G2 peak detectability must not differ by arm ------------------------------------------------
    dp, ds = float(np.mean(detect["propofol"])), float(np.mean(detect["sevoflurane"]))
    obs = abs(dp - ds)
    alld = np.asarray(detect["propofol"] + detect["sevoflurane"], float)
    n_p = len(detect["propofol"])
    perm = []
    for _ in range(N_PERM):
        i = rng.permutation(len(alld))
        perm.append(abs(alld[i[:n_p]].mean() - alld[i[n_p:]].mean()))
    thr = float(np.percentile(perm, 95))
    g2 = obs <= thr
    print(f"G2 peak detectability: propofol {dp:.4f}, sevoflurane {ds:.4f}, difference {obs:.4f} against "
          f"an arm-permuted 95th percentile of {thr:.4f} -> {'PASS' if g2 else 'FAIL'}")

    # ---- donor nulls, per feature per arm -------------------------------------------------------------
    nullC = {a: {} for a in arms}
    for a in arms:
        cs = arms[a]
        key = "Orchestra/PPF20_CE" if a == "propofol" else "Primus/EXP_SEVO"
        draws = {f: [] for f in FEATS}
        for _ in range(N_DONOR):
            per = {f: [] for f in FEATS}
            for c in cs:
                d = cs[int(rng.integers(0, len(cs)))]
                if d == c:
                    continue
                dte = [_num(r, "meta_t_s") for r in by[d]]
                de = _hold(tracks[d]["tracks"][key], dte)
                n = min(len(by[c]), len(de))
                if n < MIN_WINDOWS:
                    continue
                for f in FEATS:
                    x = np.asarray([_num(r, f) for r in by[c][:n]], float)
                    v = _rho(x, de[:n])
                    if np.isfinite(v):
                        per[f].append(v)
            for f in FEATS:
                C, _S, _n, _m = consistency(per[f])
                if np.isfinite(C):
                    draws[f].append(C)
        nullC[a] = {f: float(np.percentile(draws[f], 95)) if draws[f] else float("nan") for f in FEATS}

    res = {}
    for a in arms:
        res[a] = {}
        for f in FEATS:
            C, S, n, ms = consistency([rho[a][c][f] for c in arms[a]])
            res[a][f] = {"C": C, "S": S, "n": n, "mean_signed": ms, "C_null95": nullC[a][f],
                         "C_pass": bool(np.isfinite(C) and C > nullC[a][f])}
    print()
    print(f"{'feature':28s}{'PPF signed':>12}{'C':>8}{'null':>8}{'':2}"
          f"{'SEV signed':>12}{'C':>8}{'null':>8}")
    for f in FEATS:
        p, s = res["propofol"][f], res["sevoflurane"][f]
        print(f"{f:28s}{p['mean_signed']:+12.4f}{p['C']:8.4f}{p['C_null95']:8.4f}"
              f"{'*' if p['C_pass'] else ' ':>2}"
              f"{s['mean_signed']:+12.4f}{s['C']:8.4f}{s['C_null95']:8.4f}"
              f"{'*' if s['C_pass'] else ' ':>2}")

    # ---- primaries -------------------------------------------------------------------------------------
    def contrast(f, pc, sc):
        a = np.asarray([rho["propofol"][c][f] for c in pc], float)
        b = np.asarray([rho["sevoflurane"][c][f] for c in sc], float)
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        return float(a.mean() - b.mean()) if len(a) and len(b) else float("nan")

    p1 = contrast(ANCHOR, arms["propofol"], arms["sevoflurane"])
    a3 = contrast(FIXED, arms["propofol"], arms["sevoflurane"])
    a1 = contrast(PEAK, arms["propofol"], arms["sevoflurane"])
    boot = []
    for _ in range(N_BOOT):
        pc = [arms["propofol"][i] for i in rng.integers(0, len(arms["propofol"]), len(arms["propofol"]))]
        sc = [arms["sevoflurane"][i] for i in rng.integers(0, len(arms["sevoflurane"]),
                                                          len(arms["sevoflurane"]))]
        boot.append((contrast(ANCHOR, pc, sc), contrast(FIXED, pc, sc), contrast(PEAK, pc, sc)))
    boot = np.asarray(boot)
    lo, hi = float(np.nanpercentile(boot[:, 0], 2.5)), float(np.nanpercentile(boot[:, 0], 97.5))
    flo, fhi = float(np.nanpercentile(boot[:, 1], 2.5)), float(np.nanpercentile(boot[:, 1], 97.5))
    klo, khi = float(np.nanpercentile(boot[:, 2], 2.5)), float(np.nanpercentile(boot[:, 2], 97.5))

    # arm-label permutation placebo -- the one E232 declared and did not implement (rule 88)
    allcases = [(c, "propofol") for c in arms["propofol"]] + [(c, "sevoflurane") for c in arms["sevoflurane"]]
    plac = []
    for _ in range(N_PERM):
        i = rng.permutation(len(allcases))
        fake_p = [allcases[j][0] for j in i[:len(arms["propofol"])]]
        fake_s = [allcases[j][0] for j in i[len(arms["propofol"]):]]
        a = [rho[dict(allcases)[c]][c][ANCHOR] for c in fake_p]
        b = [rho[dict(allcases)[c]][c][ANCHOR] for c in fake_s]
        a = np.asarray([v for v in a if np.isfinite(v)], float)
        b = np.asarray([v for v in b if np.isfinite(v)], float)
        if len(a) and len(b):
            plac.append(float(a.mean() - b.mean()))
    plac = np.asarray(plac)
    p_plac = float(np.mean(np.abs(plac) >= abs(p1)))

    both = [f for f in [ANCHOR] + list(CONTROLS)
            if res["propofol"][f]["C_pass"] and res["sevoflurane"][f]["C_pass"]]
    agree = sum(1 for f in both
                if np.sign(res["propofol"][f]["mean_signed"]) == np.sign(res["sevoflurane"][f]["mean_signed"]))
    print()
    print(f"A1 peak location  contrast : {a1:+.4f} [{klo:+.4f}, {khi:+.4f}]   (Hz, propofol minus sevoflurane)")
    print(f"A3 FIXED band     contrast : {a3:+.4f} [{flo:+.4f}, {fhi:+.4f}]   (incumbent, same cases)")
    print(f"P1 ANCHORED band  contrast : {p1:+.4f} [{lo:+.4f}, {hi:+.4f}]")
    print(f"P2 direction agreement with the ANCHORED alpha: {agree}/{len(both)}  (E229 and E232: 10/11)")
    print(f"arm-label placebo on P1: mean {plac.mean():+.4f}, |p| = {p_plac:.4f} "
          f"-> {'BEATEN' if p_plac < 0.05 else 'NOT BEATEN'}")

    anchored_reverses = (lo > 0 or hi < 0) and res["propofol"][ANCHOR]["C_pass"] \
        and res["sevoflurane"][ANCHOR]["C_pass"]
    fixed_reverses = (flo > 0 or fhi < 0)
    if anchored_reverses and np.sign(p1) != np.sign(a3):
        verdict = (f"OPPOSITE TO THE INCUMBENT -- the anchored contrast is {p1:+.4f} against the fixed "
                   f"{a3:+.4f}; reported as a failure to replicate with the sign, not as a pass")
    elif anchored_reverses and abs(p1) > abs(a3):
        verdict = (f"BAND PLACEMENT WAS MASKING THE EFFECT -- anchoring the band to each recording's own "
                   f"peak makes the reversal LARGER ({p1:+.4f} against the fixed {a3:+.4f}); the reversal "
                   "is real and the fixed band understated it")
    elif anchored_reverses:
        verdict = (f"BIOLOGY -- the reversal survives anchoring the band to each recording's own alpha "
                   f"peak ({p1:+.4f} against the fixed {a3:+.4f}), so it is a property of the oscillation "
                   "and not of the 8-13 Hz box")
    elif fixed_reverses:
        verdict = ("BAND PLACEMENT -- the fixed band reverses on these cases and the peak-anchored "
                   "measure does not. Every alpha claim in this project, E229 and E232 included, must be "
                   "restated as a statement about where the peak sits relative to a fixed window rather "
                   "than about the drug")
    else:
        verdict = ("NEITHER MEASURE REVERSES ON THIS TABLE -- the joined window set does not reproduce "
                   "the incumbent, so nothing here is a test of it")
    if not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; the anchored measure's capability is not established"
    elif not g2:
        verdict = ("NOT INTERPRETABLE -- G2 failed; peak detectability differs by arm, so the anchored "
                   "measure is computed on a stratum selected on the thing under test (rule 32)")
    elif not g4:
        verdict = "NOT INTERPRETABLE -- G4 coverage failed"
    elif anchored_reverses and p_plac >= 0.05:
        # THE PLACEBO GATES A PASS AND NEVER A NULL, which is what this file registered: "a gate can only
        # invalidate a pass, never rescue a null". The first draft applied it unconditionally, so a P1
        # whose interval INCLUDES zero -- the outcome branch (c) is built on -- was refused by a control
        # that cannot speak to nulls at all (rule 48: a placebo cannot validate a null, and equally cannot
        # invalidate one). Repaired once, with the reason, per rule 58; the code now matches the
        # registered gating principle rather than contradicting it.
        verdict = "NOT INTERPRETABLE -- the arm-label permutation reproduces the contrast"
    elif not anchored_reverses:
        verdict += (f" | the arm-label placebo on the null primary is NOT INFORMATIVE by rule 48 "
                    f"(|p| = {p_plac:.4f} against P1 = {p1:+.4f}, whose interval includes zero); it is "
                    "reported and does not gate")
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"per_feature": res, "arms": {a: len(arms[a]) for a in arms}, "exclusions": excl,
                   "a1_peak": {"est": a1, "lo": klo, "hi": khi},
                   "a3_fixed": {"est": a3, "lo": flo, "hi": fhi},
                   "p1_anchored": {"est": p1, "lo": lo, "hi": hi},
                   "p2_agreement": {"agree": agree, "n": len(both), "features": both},
                   "detectability": {"propofol": dp, "sevoflurane": ds, "diff": obs, "perm_p95": thr},
                   "placebo_arm_label": {"mean": float(plac.mean()), "p": p_plac,
                                         "beaten": bool(p_plac < 0.05)},
                   "gates": {"G2": bool(g2), "G3": bool(g3), "G4": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
