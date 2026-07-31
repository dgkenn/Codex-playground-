#!/usr/bin/env python3
"""E69 -- BSDE core. Does any measure place REM sleep with WAKE, or with DEEP SLEEP?

REGISTERED BEFORE ANY REM VALUE HAS BEEN READ. E67 used the same table but touched only its `@W` and `@N3`
rows; the `@REM`, `@N1` and `@N2` rows have not been opened.

=========================================================================================================
WHY REM, AND WHY IT IS THE DISSOCIATION THIS PROGRAMME HAS BEEN LOOKING FOR
=========================================================================================================
`BRIEF_01` asks for separation of arousal, cognitive-processing capacity, command-following and behavioural
output. `candidates/seed.py` carries a standing warning that the project's main contrast merges anaesthetic
LOC with sleep N3-vs-wake -- *"exactly the two states that H4, 'the marker is an arousal index', predicts
should behave alike"* -- and names the informative domains as *"the ones that dissociate arousal from
experience: ds005620, ketamine, and locked-in syndrome."*

**REM is a fourth, it is free, and it has been in `results/` the whole time.** Its dissociation is the
cleanest of the four:

    state   experience        behavioural responsiveness
    W       present           present
    REM     present (dreams)  ABSENT (atonia)
    N3      largely absent    absent

So a measure of EXPERIENCE or cognitive capacity should read REM like wake. A measure of BEHAVIOURAL
OUTPUT or responsiveness should read REM like N3.

=========================================================================================================
THE NULL EXPECTATION IS NOT 50/50, AND SAYING SO IS WHAT MAKES THIS HONEST
=========================================================================================================
**REM EEG is low-amplitude and desynchronised -- physically wake-like.** Any spectral or complexity measure
will therefore tend to place REM near wake for reasons that have nothing to do with experience. So
"REM groups with W" is the CHEAP outcome and must not be reported as evidence that a measure tracks
consciousness.

**The informative result is the opposite one.** A measure that places REM with N3, despite REM's wake-like
spectrum, is tracking something other than cortical desynchronisation -- and behavioural output is the
candidate. Finding none would say that everything this project measures is a desynchronisation index,
which is H4 confirmed and is worth knowing plainly.

**NOTHING HERE IS A CONSCIOUSNESS DETECTOR AND NO OUTPUT MAY BE DESCRIBED AS ONE.** Sleep staging is scored
from the EEG itself, so stage and signal are not independent; this asks how a measure ORDERS three
scorer-defined states, not whether anyone was conscious.

=========================================================================================================
DESIGN
=========================================================================================================
DATA. `sleep_edfx_five_stage.csv`: 142 subjects, five stages each, within-subject by construction.

  G1 SEPARATION GATE (rule 53), per feature and evaluated first. The W-vs-N3 paired contrast must exclude
  zero. **If a measure does not distinguish wake from deep sleep, "which one REM resembles" is meaningless**
  and the feature is reported UNTESTABLE, never as grouping either way.

  PRIMARY   the fraction of subjects for whom REM lies nearer W than N3 on that feature, tested against
            0.5 with a subject bootstrap. **Rank-based and division-free**, so no subject with a small
            W-N3 gap can blow it up -- the failure mode a ratio statistic would have.
  S1        the median standardised position of REM on the W->N3 axis, (REM-W)/(N3-W), over subjects whose
            denominator exceeds `MIN_GAP` of the population spread. DESCRIPTIVE, reported with the excluded
            fraction, and not the primary precisely because of that exclusion.
  S2        the full W / N1 / N2 / N3 ordering. A measure that is not monotone across the depth staircase
            is not reading depth, and that is worth seeing next to any REM claim.
  P1 PLACEBO  stage labels permuted WITHIN subject, primary recomputed. This destroys the state assignment
            while preserving every subject's own value distribution -- and unlike a pairing shuffle it can
            actually move a fraction-nearer statistic (rule 55, learned from E67 one experiment ago).

VERDICT RULE, wrong direction first.

  (a) ALL BEHAVIOURAL -- every surviving feature places REM with N3. Given REM's wake-like spectrum this
                         would be surprising and would need replication before it meant anything.
  (b) NONE TESTABLE   -- G1 removes every feature.
  (c) NOT INFORMATIVE -- the within-subject label permutation reproduces the primary.
  (d) ALL AROUSAL     -- every surviving feature places REM with W. **The expected outcome**, and it means
                         the feature set is a desynchronisation family: H4 confirmed, no separation of
                         experience from behaviour anywhere in it.
  (e) SPLIT           -- the informative outcome. Any feature departing from the family is the one worth
                         pursuing, and its identity matters more than the count.

    python -m bsde.experiments.e69_rem_dissociation
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

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")
OUT = os.path.join(RESULTS, "e69_rem_dissociation.json")

FEATURES = ["exponent_low", "exponent_high", "whole_head_exponent", "lempel_ziv", "spectral_entropy",
            "relative_alpha_power", "relative_delta_power", "spectral_edge_95", "pac_slow_alpha",
            "critical_slowing_ar1", "multiscale_entropy_slope", "emg_index"]
STAGES = ("W", "N1", "N2", "N3", "REM")
MIN_GAP = 0.10
REPS = 4000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    per = defaultdict(dict)
    for r in csv.DictReader(open(TABLE, newline="")):
        rid = r["recording_id"]
        if "@" not in rid:
            continue
        stage = rid.rsplit("@", 1)[1]
        if stage not in STAGES:
            continue
        per[r["subject"]][stage] = {f: _f(r.get(f, "")) for f in FEATURES}
    return per


def _boot_mean(v, rng, reps=REPS):
    v = np.asarray(v, float)
    if v.size < 5:
        return float("nan"), float("nan")
    d = np.sort([v[rng.integers(0, v.size, v.size)].mean() for _ in range(reps)])
    return float(np.quantile(d, .025)), float(np.quantile(d, .975))


def main() -> int:
    per = load()
    rng = np.random.default_rng(SEED)
    subs = [s for s, d in per.items() if all(st in d for st in STAGES)]
    print(f"{len(subs)} subjects with all five stages\n")
    res, agree_w, agree_n3, untestable = {}, [], [], []

    print(f"{'feature':<26s} {'W-N3 d_z':>9s} {'G1':>5s} {'frac REM~W':>11s} {'95% CI':>18s} "
          f"{'REM pos':>8s} {'monotone':>9s}")
    for f in FEATURES:
        W = np.array([per[s]["W"][f] for s in subs])
        N3 = np.array([per[s]["N3"][f] for s in subs])
        RE = np.array([per[s]["REM"][f] for s in subs])
        ok = np.isfinite(W) & np.isfinite(N3) & np.isfinite(RE)
        d = (N3 - W)[ok]
        if d.size < 20 or d.std(ddof=1) < 1e-12:
            untestable.append(f)
            res[f] = {"testable": False}
            print(f"{f:<26s} {'--':>9s} {'FAIL':>5s}")
            continue
        dz = float(d.mean() / d.std(ddof=1))
        bl, bh = _boot_mean(d, np.random.default_rng(SEED))
        alive = (bl > 0) or (bh < 0)
        near_w = (np.abs(RE - W) < np.abs(RE - N3))[ok].astype(float)
        frac = float(near_w.mean())
        flo, fhi = _boot_mean(near_w, np.random.default_rng(SEED + 1))
        gap = np.abs(N3 - W)[ok]
        thr = MIN_GAP * float(np.quantile(np.concatenate([W[ok], N3[ok]]), .75)
                              - np.quantile(np.concatenate([W[ok], N3[ok]]), .25))
        use = gap > thr
        pos = ((RE - W) / (N3 - W))[ok][use]
        medpos = float(np.median(pos)) if pos.size else float("nan")
        stage_med = [float(np.nanmedian([per[s][st][f] for s in subs])) for st in ("W", "N1", "N2", "N3")]
        mono = all(x <= y for x, y in zip(stage_med, stage_med[1:])) or \
               all(x >= y for x, y in zip(stage_med, stage_med[1:]))
        if not alive:
            untestable.append(f)
        elif frac > 0.5:
            agree_w.append(f)
        else:
            agree_n3.append(f)
        res[f] = {"testable": bool(alive), "w_n3_dz": dz, "frac_rem_near_w": frac,
                  "lo": flo, "hi": fhi, "median_position": medpos,
                  "n_used_for_position": int(use.sum()), "stage_medians": stage_med,
                  "monotone_W_to_N3": bool(mono)}
        print(f"{f:<26s} {dz:>9.3f} {'ok' if alive else 'FAIL':>5s} {frac:>11.3f} "
              f"[{flo:.3f}, {fhi:.3f}]".rjust(0) + f"{'':>2s}{medpos:>8.3f} {str(mono):>9s}")

    # P1 placebo: permute stage labels WITHIN subject.
    rp = np.random.default_rng(SEED + 2)
    testable = agree_w + agree_n3
    plac = []
    for _ in range(200):
        fr = []
        for f in testable:
            v = []
            for s in subs:
                vals = [per[s][st][f] for st in STAGES]
                if not all(np.isfinite(x) for x in vals):
                    continue
                sh = rp.permutation(vals)
                v.append(float(abs(sh[4] - sh[0]) < abs(sh[4] - sh[3])))
            if v:
                fr.append(np.mean(v))
        plac.append(np.mean(fr) if fr else np.nan)
    plac_mean = float(np.nanmean(plac))
    real = float(np.mean([res[f]["frac_rem_near_w"] for f in testable])) if testable else float("nan")
    print(f"\nPRIMARY  mean fraction REM-nearer-W over {len(testable)} testable features = {real:.3f}")
    print(f"P1 PLACEBO  stage labels permuted within subject = {plac_mean:.3f} (200 draws)")
    if untestable:
        print(f"G1 removed: {untestable}")

    if not testable:
        verdict = "NONE TESTABLE -- G1 removed every feature; no measure separates W from N3 here."
    elif not agree_w:
        verdict = ("ALL BEHAVIOURAL -- every surviving feature places REM with N3 despite REM's wake-like "
                   "spectrum. Surprising enough to need replication before it means anything.")
    elif abs(real - 0.5) <= abs(plac_mean - 0.5):
        verdict = ("NOT INFORMATIVE -- permuting stage labels within subject reproduces the primary, so "
                   "the grouping does not depend on which state a value came from.")
    elif not agree_n3:
        verdict = (f"ALL AROUSAL -- all {len(agree_w)} surviving features place REM with WAKE. This is the "
                   f"EXPECTED outcome given REM's desynchronised spectrum and it is not evidence that any "
                   f"of them tracks experience: it says the feature set is a desynchronisation family, "
                   f"which is H4 confirmed. Nothing here separates experience from behavioural output.")
    else:
        verdict = (f"SPLIT -- {agree_n3} place REM with DEEP SLEEP while {agree_w} place it with wake. The "
                   f"departing features are the ones worth pursuing: they are not simply reading cortical "
                   f"desynchronisation, and behavioural output is the candidate for what they do read.")
    print(f"\nVERDICT: {verdict}")
    print("\nNOTE: sleep stage is scored FROM the EEG, so stage and signal are not independent. This "
          "measures how a feature ORDERS three scorer-defined states, and is not a consciousness detector.")

    json.dump({"n_subjects": len(subs), "features": res, "rem_with_wake": agree_w,
               "rem_with_n3": agree_n3, "untestable": untestable,
               "primary_mean_frac": real, "placebo_mean_frac": plac_mean,
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
