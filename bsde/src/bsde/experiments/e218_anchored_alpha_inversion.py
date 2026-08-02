#!/usr/bin/env python3
"""E218 — does a PEAK-ANCHORED alpha band remove the propofol/sevoflurane inversion?

REGISTERED WHILE THE EXTRACTION IT CONSUMES IS STILL RUNNING. No value of either new measure has been read
on real data. What HAS been computed, and is reported below as the premise rather than as a result, is the
pair of measures' behaviour on SYNTHETIC signals with a known peak frequency — `tests/test_iaf_capability.py`,
committed before this file.

=========================================================================================================
THE THING E213 COULD NOT TEST, AND THE THING THE LITERATURE SAYS NOBODY HAS
=========================================================================================================
E213 asked whether the inversion of `relative_alpha_power` between propofol and sevoflurane is an artefact
of measuring a moving alpha peak through a fixed 8-13 Hz window. It returned **ABSENT** — removing the
cases whose peak sits on the band floor changed the arm gap by -0.0310, the 18.8th percentile of a
matched-size null. Its scope section says exactly what that could not settle:

    *this file can show the fixed band distorts the contrast. It CANNOT show what a peak-ANCHORED measure
    would find, because no per-window spectra were stored, only scalar summaries.*

**Removing cases and replacing the measure are different interventions**, and the second is much stronger:
a case whose peak sits at 8.4 Hz is not "pinned" and is still mismeasured by a box that starts at 8.0.

A literature search on 2026-08-02, verified against E-utilities rather than summarised, found the transfer
unmade: **`"individual alpha frequency"[tiab]` returns 234 papers and ZERO of them mention anesthesia or
anaesthesia.** Individual alpha frequency is standard in cognitive EEG and has apparently never been carried
into anaesthesia depth monitoring.

=========================================================================================================
THE PREMISE, MEASURED ON SYNTHETIC SIGNALS BEFORE ANY REAL DATA WAS TOUCHED
=========================================================================================================
On pink noise plus one oscillation of fixed amplitude whose frequency is swept, six committed tests
establish:

  * `alpha_peak_hz` is not merely censored outside 8-13 Hz, it is **wrong**: it returns ~8.5 Hz for a true
    peak at 6.0, at 7.5 and at 14.0 alike.
  * `relative_alpha_power` falls from 0.43 to 0.028 — **fifteenfold** — when the peak moves 1 Hz below the
    band edge, while the oscillation generating it is unchanged.
  * `alpha_peak_hz_wide` recovers the true peak across 6-14 Hz, and `relative_alpha_power_iaf` is flat
    across the same range (spread under 1.5x).

So the anchored measure demonstrably does what it claims **on signals where the truth is known**. Whether
that matters for the inversion is what this file asks.

    **P1  Does the deep-versus-light direction of `relative_alpha_power_iaf` still invert between propofol
          and sevoflurane, as `relative_alpha_power`'s does, on the SAME cases and the SAME windows?**

    **P2  How much does an uncensored peak estimator change the measured propofol-minus-sevoflurane peak
          shift at depth?** This is reported whatever P1 gives, because our own measurement of that shift
          disagrees with Akeju 2014 (PMID 25233374, n = 60, *"maximum power and coherence at approximately
          10 Hz"* for BOTH agents) and the censoring is a candidate explanation for the disagreement.

=========================================================================================================
STATISTIC
=========================================================================================================
E213's arm gap, unchanged, on both measures over the same cases:

    G = frac(deep - light > 0 | sevoflurane) - frac(deep - light > 0 | propofol)

with a **case-level bootstrap** on the DIFFERENCE `|G_fixed| - |G_iaf|`. Both measures are computed on the
same windows in one extraction pass, so no part of the comparison is confounded by which extraction a value
came from — the failure rule 20 records, where two scripts computing the same quantity were never diffed.

Because `|G|` is a folded statistic and is biased upward under the null (rule 46), it is only ever
differenced against itself on the SAME rows, which is exactly what this comparison does.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 12 clean single-agent cases per arm, and `relative_alpha_power_iaf` finite on at least
    `MIN_FINITE_FRAC` of windows. **The candidate's own registered failure condition is that it returns NaN
    on more than a third of windows** — if the peak vanishes at depth, an anchored band has nothing to
    anchor to exactly where it is needed, and that is a refutation of the measure rather than a data
    problem.
G2  **THE INVERSION MUST BE ALIVE FOR THE FIXED MEASURE** (rule 53). `|G_fixed|` must exceed its own
    arm-label permutation p95. If there is no inversion on this cohort, removing one is meaningless.
G3  **RULE 60 ESCAPE CHECK, AND IT IS THE CANDIDATE'S OWN FAILURE CONDITION.** `relative_alpha_power_iaf`
    must NOT correlate above 0.9 with `relative_alpha_power` across cases. If it does, anchoring changed
    nothing and this is the incumbent renamed — the error rule 60 was written for, where a measure chosen
    to escape a family had to be shown to differ from it and was not.
G5  **THE ANCHORED MEASURE MUST ITSELF CARRY DEPTH, WITHIN EACH ARM** (rule 83). ADDED AFTER THE FIRST
    RUN, WHICH DID NOT HAVE IT AND WAS WRONG WITHOUT IT. A measure that carries no depth signal at all
    cannot invert, so "the inversion is gone" and "the measure does nothing" print identically -- the
    discrimination-versus-equivalence error. The first run returned ANCHORING REMOVES IT and the anchored
    measure's deep-above-light rate was -0.0455 in propofol and -0.0423 in sevoflurane against sign-flip
    floors of 0.2727 and 0.2394, i.e. dead in both arms. The gate is added because it makes the test
    STRICTER after a pass, which is the safe direction; a gate loosened after a failure would not be.
G4  the peak estimators must actually differ: `alpha_peak_hz_wide` must report values OUTSIDE [8, 13] on a
    non-trivial fraction of windows. If every peak really does lie inside the fixed band on real data, the
    censoring is immaterial here whatever the synthetic tests show.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G4 fails.
  (2) ANCHORING MAKES IT WORSE   `|G_iaf|` is LARGER than `|G_fixed|` with the difference interval
                          excluding zero. The fixed band was masking a stronger inversion, which refutes
                          band placement in the opposite direction from (3) and is reported as its own
                          outcome.
  (3) NO CHANGE           the difference interval includes zero. Band placement is refuted CONSTRUCTIVELY —
                          the second and much stronger refutation after E213's — and the inversion is a
                          property of the alpha oscillation rather than of the box it is measured in.
  (4) PARTIAL             `|G_iaf|` is smaller with the difference excluding zero, but `|G_iaf|` still
                          exceeds its own permutation floor. Band placement explains part of the inversion
                          and not all of it.
  (5) ANCHORING REMOVES IT  `|G_iaf|` falls below its own permutation floor while `|G_fixed|` exceeds it.

**REGISTERED PREDICTION: (3) or (4), and I lean (3) at about 60:40.** E213 already refused the
case-removal version of this story on this cohort, and E216 found that selecting features for frequency
invariance does not buy transport. Two independent attempts have failed to make the inversion a
measurement artefact. **(5) would be the most valuable result this challenge has produced** — a fixed
measure that inverts between agents and an anchored one that does not is a constructive fix, in a niche the
literature says is empty. **(2) would be the most interesting**, because it would mean the fixed band has
been UNDERSTATING an agent difference that everyone reports using fixed bands.

**SCOPE.** VitalDB's EEG is a SINGLE frontal channel (`BIS/EEG1_WAV`) at 128 Hz, so "peak" here is a
one-channel peak and nothing about topography is tested. The cohort, the deep/light tercile definition and
the arm labels are E186's unchanged, so this shares that cohort's limitations and none of them are new.

    python bsde/src/bsde/experiments/e218_anchored_alpha_inversion.py
"""

from __future__ import annotations

import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.verifier.stats import spearman                                       # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e218_anchored_alpha_inversion.json")
SHARDS = os.path.join(RESULTS, "vitaldb_iaf.s*.csv")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")

SEED = 20260802
MIN_PER_ARM = 12
MIN_WINDOWS = 9
MIN_FINITE_FRAC = 0.667          # the candidate's own declared failure condition
N_BOOT = 4000
N_PERM = 4000
REDUNDANCY_CEILING = 0.9         # the candidate's own declared failure condition
FIXED = "relative_alpha_power"
ANCHORED = "relative_alpha_power_iaf"
PEAK_FIXED = "alpha_peak_hz"
PEAK_WIDE = "alpha_peak_hz_wide"


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def load_cases():
    """E186/E169's cohort construction, unchanged, reading the new extraction."""
    dose = {r["recording_id"]: r for r in csv.DictReader(open(AGENTS, newline=""))}
    rows = defaultdict(list)
    n_all = 0
    for p in sorted(glob.glob(SHARDS)):
        for r in csv.DictReader(open(p, newline="")):
            n_all += 1
            if r.get("status") != "ok":
                continue
            ag = (r.get("meta_agents_present") or "").strip()
            if ag not in ("propofol", "sevoflurane"):
                continue
            d = dose.get(r["recording_id"])
            if d is None:
                continue
            r["_exposure"] = _f(d["mac"]) if ag == "sevoflurane" else _f(d["ppf_ce"])
            rows[r["meta_caseid"]].append(r)

    cases, windows = {}, []
    for c, rs in rows.items():
        rs.sort(key=lambda r: _f(r["meta_t_s"]))
        keep = [r for r in rs if math.isfinite(r["_exposure"])]
        if len(keep) < MIN_WINDOWS:
            continue
        windows.extend(keep)
        order = sorted(keep, key=lambda r: r["_exposure"])
        k = max(3, len(order) // 3)
        light, deep = order[:k], order[-k:]
        d = {"arm": 1 if rs[0]["meta_agents_present"] == "sevoflurane" else 0}
        ok = True
        for f in (FIXED, ANCHORED, PEAK_FIXED, PEAK_WIDE):
            for tag, grp in (("deep", deep), ("light", light)):
                v = [_f(r.get(f, "")) for r in grp]
                v = [x for x in v if math.isfinite(x)]
                d[f"{tag}_{f}"] = float(np.median(v)) if v else float("nan")
                ok = ok and bool(v)
        if ok:
            cases[c] = d
    return cases, windows, n_all


def gap(d, arm):
    a = (arm > 0.5) & np.isfinite(d)
    b = (arm < 0.5) & np.isfinite(d)
    if a.sum() == 0 or b.sum() == 0:
        return float("nan")
    return float(np.mean(d[a] > 0) - np.mean(d[b] > 0))


def main() -> int:
    print("E218 — does a PEAK-ANCHORED alpha band remove the propofol/sevoflurane inversion?")
    cases, windows, n_all = load_cases()
    ids = sorted(cases)
    arm = np.array([cases[c]["arm"] for c in ids], float)
    n = len(ids)
    nA, nB = int((arm < 0.5).sum()), int((arm > 0.5).sum())
    print(f"   {n_all} extracted windows, {len(windows)} in clean single-agent cases, "
          f"{n} cases: {nA} propofol, {nB} sevoflurane")

    fin = {f: float(np.mean([np.isfinite(_f(r.get(f, ""))) for r in windows]))
           for f in (FIXED, ANCHORED, PEAK_FIXED, PEAK_WIDE)}
    for f, v in fin.items():
        print(f"   finite fraction over windows: {f:<28s} {v:.4f}")
    g1 = bool(min(nA, nB) >= MIN_PER_ARM and fin[ANCHORED] >= MIN_FINITE_FRAC)
    print(f"G1 >= {MIN_PER_ARM} cases per arm and the anchored measure finite on >= "
          f"{MIN_FINITE_FRAC:.3f} of windows   {'PASS' if g1 else '*** FAIL'}")

    D = {f: np.array([cases[c][f"deep_{f}"] - cases[c][f"light_{f}"] for c in ids], float)
         for f in (FIXED, ANCHORED)}
    rng = np.random.default_rng(SEED)
    Gf, Ga = gap(D[FIXED], arm), gap(D[ANCHORED], arm)
    perm = np.array([abs(gap(D[FIXED], rng.permutation(arm))) for _ in range(N_PERM)])
    p95 = float(np.quantile(perm, 0.95))
    g2 = bool(abs(Gf) > p95)
    perm_a = np.array([abs(gap(D[ANCHORED], rng.permutation(arm))) for _ in range(N_PERM)])
    p95a = float(np.quantile(perm_a, 0.95))
    print(f"G2 INVERSION ALIVE for the FIXED measure  G {Gf:+.4f}  |G| {abs(Gf):.4f} vs "
          f"arm-permutation p95 {p95:.4f}   {'PASS' if g2 else '*** FAIL'}")
    print(f"   for reference, the ANCHORED measure    G {Ga:+.4f}  |G| {abs(Ga):.4f} vs its own "
          f"p95 {p95a:.4f}")

    for lab, a in (("propofol", 0.0), ("sevoflurane", 1.0)):
        m = (arm == a) & np.isfinite(D[FIXED])
        v = D[FIXED][m]
        obs = float(np.mean(v > 0) - 0.5) * 2.0
        nul = np.array([float(np.mean((v * np.random.default_rng(SEED + 600 + k)
                                       .choice([-1.0, 1.0], size=v.size)) > 0) - 0.5) * 2.0
                        for k in range(1000)])
        print(f"   FIXED measure within {lab:<12s} deep-above-light {obs:+.4f} vs sign-flip p95 "
              f"{float(np.quantile(np.abs(nul), 0.95)):.4f} ({v.size} cases)")

    dv = np.array([cases[c][f"deep_{FIXED}"] for c in ids])
    av = np.array([cases[c][f"deep_{ANCHORED}"] for c in ids])
    m = np.isfinite(dv) & np.isfinite(av)
    rho = spearman(list(dv[m]), list(av[m]))
    g3 = bool(abs(rho) < REDUNDANCY_CEILING)
    print(f"G3 RULE-60 ESCAPE CHECK  rho(deep {FIXED}, deep {ANCHORED}) = {rho:+.4f} vs ceiling "
          f"{REDUNDANCY_CEILING}   {'PASS' if g3 else '*** FAIL'}")

    wide = np.array([_f(r.get(PEAK_WIDE, "")) for r in windows])
    wide = wide[np.isfinite(wide)]
    out_frac = float(np.mean((wide < 8.0) | (wide > 13.0))) if wide.size else float("nan")
    g4 = bool(np.isfinite(out_frac) and out_frac > 0.05)
    print(f"G4 THE ESTIMATORS DIFFER  {out_frac:.4f} of uncensored peaks lie OUTSIDE [8, 13] "
          f"({wide.size} windows)   {'PASS' if g4 else '*** FAIL'}")

    # G5, added after the first run (see the docstring). Rule 83: a measure must be shown to carry the
    # thing before its failure to carry a CONFOUND means anything.
    alive_arm, g5 = {}, True
    for lab, a in (("propofol", 0.0), ("sevoflurane", 1.0)):
        m = (arm == a) & np.isfinite(D[ANCHORED])
        v = D[ANCHORED][m]
        obs = float(np.mean(v > 0) - 0.5) * 2.0
        nul = np.array([float(np.mean((v * np.random.default_rng(SEED + 900 + k)
                                       .choice([-1.0, 1.0], size=v.size)) > 0) - 0.5) * 2.0
                        for k in range(N_PERM)])
        fl = float(np.quantile(np.abs(nul), 0.95))
        ok = bool(abs(obs) > fl)
        alive_arm[lab] = {"deep_above_light": obs, "floor": fl, "n": int(v.size), "pass": ok}
        g5 = g5 and ok
        print(f"G5 ANCHORED MEASURE ALIVE  {lab:<12s} deep-above-light {obs:+.4f} vs sign-flip p95 "
              f"{fl:.4f} ({v.size} cases)   {'PASS' if ok else '*** FAIL'}")

    diff = abs(Gf) - abs(Ga)
    boot = []
    for b in range(N_BOOT):
        g = np.random.default_rng(SEED + 3000 + b)
        pick = g.choice(n, size=n, replace=True)
        bf, ba = gap(D[FIXED][pick], arm[pick]), gap(D[ANCHORED][pick], arm[pick])
        if np.isfinite(bf) and np.isfinite(ba):
            boot.append(abs(bf) - abs(ba))
    boot = np.array(boot)
    lo, hi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
    print(f"\nP1  |G_fixed| - |G_anchored| = {diff:+.4f} [{lo:+.4f}, {hi:+.4f}]  "
          f"(case bootstrap, {boot.size} draws)")

    # P2, reported whatever P1 gives
    def peak_at_depth(col):
        out = {}
        for lab, a in (("propofol", 0), ("sevoflurane", 1)):
            v = np.array([cases[c][f"deep_{col}"] for c in ids if cases[c]["arm"] == a], float)
            v = v[np.isfinite(v)]
            out[lab] = float(np.median(v)) if v.size else float("nan")
        out["shift"] = out["propofol"] - out["sevoflurane"]
        return out
    p2 = {PEAK_FIXED: peak_at_depth(PEAK_FIXED), PEAK_WIDE: peak_at_depth(PEAK_WIDE)}
    print("\nP2  propofol-minus-sevoflurane alpha peak at DEPTH, censored vs uncensored estimator")
    for col, d in p2.items():
        print(f"   {col:<20s} propofol {d['propofol']:6.2f} Hz   sevoflurane {d['sevoflurane']:6.2f} Hz"
              f"   shift {d['shift']:+.2f} Hz")

    res = {"experiment": "E218", "n_cases": n, "n_propofol": nA, "n_sevo": nB,
           "n_windows": len(windows), "finite_fraction": fin,
           "G_fixed": Gf, "G_anchored": Ga, "perm_p95_fixed": p95, "perm_p95_anchored": p95a,
           "redundancy_rho": rho, "outside_band_fraction": out_frac,
           "diff": diff, "ci": [lo, hi], "peak_shift": p2,
           "g1": g1, "g2": g2, "g3": g3, "g4": g4, "g5": g5, "anchored_alive": alive_arm}

    print("\n" + "=" * 100)
    if not (g1 and g2 and g3 and g4 and g5):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            nm for nm, ok in (("G1 coverage", g1), ("G2 inversion alive", g2),
                              ("G3 rule-60 escape", g3), ("G4 estimators differ", g4),
                              ("G5 anchored measure alive", g5)) if not ok))
    elif hi < 0:
        v_, why = "ANCHORING MAKES IT WORSE", (
            f"the anchored measure inverts MORE strongly than the fixed one ({abs(Ga):.4f} vs "
            f"{abs(Gf):.4f}, difference {diff:+.4f} [{lo:+.4f}, {hi:+.4f}]). The fixed band was MASKING an "
            "agent difference, which refutes band placement in the opposite direction")
    elif lo <= 0 <= hi:
        v_, why = "NO CHANGE", (
            f"anchoring the band to each recording's own peak changes the inversion by {diff:+.4f} "
            f"[{lo:+.4f}, {hi:+.4f}], an interval including zero. Band placement is refuted "
            "CONSTRUCTIVELY -- the second and stronger refutation after E213 -- and the inversion is a "
            "property of the alpha oscillation, not of the box it is measured in")
    elif abs(Ga) > p95a:
        v_, why = "PARTIAL", (
            f"anchoring shrinks the inversion from {abs(Gf):.4f} to {abs(Ga):.4f} (difference "
            f"{diff:+.4f} [{lo:+.4f}, {hi:+.4f}]) but the anchored measure still inverts beyond its own "
            f"permutation floor of {p95a:.4f}. Band placement explains part of it and not all")
    else:
        v_, why = "ANCHORING REMOVES IT", (
            f"the fixed measure inverts at {abs(Gf):.4f} against a floor of {p95:.4f}; the anchored one "
            f"sits at {abs(Ga):.4f} against its own floor of {p95a:.4f} and does NOT clear it, with the "
            f"difference {diff:+.4f} [{lo:+.4f}, {hi:+.4f}] excluding zero. A band anchored to each "
            "recording's own peak carries depth without carrying agent identity")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print("SCOPE: VitalDB EEG is a SINGLE frontal channel at 128 Hz, so 'peak' is a one-channel peak and\n"
          "  nothing about topography is tested. Cohort, tercile definition and arm labels are E186's,\n"
          "  so this inherits that cohort's limitations and adds none.")

    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2, default=float)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
