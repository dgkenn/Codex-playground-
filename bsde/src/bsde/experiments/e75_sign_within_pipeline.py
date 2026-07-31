#!/usr/bin/env python3
"""E75 -- Challenge A. The drug/no-drug sign comparison, done within ONE pipeline and with the depth premise tested.

REGISTERED WHILE `ds005620_full.csv` IS STILL EXTRACTING AND BEFORE ANY OF ITS VALUES HAVE BEEN READ. A
three-row pilot was inspected to confirm that 18 of 20 candidates return finite values (`lrtc_alpha` and
`pac_slow_alpha` do not). No feature has been related to any state contrast.

=========================================================================================================
WHAT E67 GOT WRONG AND WHAT CHANGES HERE
=========================================================================================================
E67 asked whether a measure moves the same way when consciousness falls with a drug and without one. It
returned ABSENT and left three defects, all now addressed:

1. **Its placebo could not fail.** Breaking the within-subject pairing changes a paired difference's
   variance, not its SIGN, so the agreement rate was mathematically insensitive to the shuffle (rule 55).
   **Fixed:** the placebo permutes the STATE LABEL within subject, which does flip signs.

2. **It mixed pipelines.** Q33 measured the cost on identical recordings: `lempel_ziv` differs **83.8 %**
   between this project's two extraction paths and `relative_alpha_power` **53.2 %**. **Fixed:** every arm
   here is bsde-path, and `ds005620` is being re-extracted with the full registry precisely so the
   well-powered drug arm stops being the six-feature bottleneck.

3. **Its depth premise was asserted, not tested.** E67 argued a sign is depth-invariant "as long as the
   effect is monotone in depth", and this project has evidence against that (E31 exists to ask whether a
   sign reversal is a depth-range effect). **Fixed:** the sleep arm carries a graded depth axis --
   W, N1, N2, N3 -- so monotonicity becomes a per-feature GATE rather than an assumption.

=========================================================================================================
DESIGN
=========================================================================================================
ARMS, all bsde-path, all within-subject:

    NO-DRUG   Sleep-EDFx W -> N3, 142 subjects
    DRUG-A    ds005620 awake -> sedated, 21 subjects (propofol)
    DRUG-B    ds004541 baseline -> post-LOC, 7 subjects (general anaesthesia)

  G1 ALIVENESS (rule 53), per feature and per arm: the paired d_z interval must exclude zero. A sign from
     an arm that did not move is a coin flip.
  G2 MONOTONICITY, per feature, on the NO-DRUG arm only, because only it has a graded depth axis. The
     medians across W, N1, N2, N3 must be monotone. **A feature that is not monotone in depth has no
     depth-invariant sign, so a cross-arm sign comparison is uninterpretable for it** and it is reported
     NOT DEPTH-MONOTONE rather than agreeing or reversing. This is the gate E67 needed and did not have.
  PRIMARY  per feature surviving G1 and G2, do the no-drug and drug arms agree in SIGN? The LIST is the
     result, not the count -- Challenge A needs to know WHICH measures survive.
  P1 PLACEBO  state labels permuted WITHIN subject in both arms, agreement recomputed. Unlike E67's pairing
     shuffle this can actually move a sign.
  P2 SECOND DRUG  the same comparison against DRUG-B. n = 7 makes it corroborative only; a feature agreeing
     with one drug arm and reversing against the other has passed nothing.

VERDICT RULE, wrong direction first.

  (a) ALL REVERSE      -- every surviving feature reverses. Everything measured here reads pharmacology.
  (b) NONE TESTABLE    -- G1 or G2 removes every feature.
  (c) NOT INFORMATIVE  -- the label-permutation placebo reproduces the agreement rate.
  (d) SPLIT            -- the informative outcome. The agreeing set is Challenge A's candidate list; the
                          reversing set must never be described as consciousness markers, since within
                          either arm alone they look fine.
  (e) ALL AGREE        -- weaker than it looks: a test nothing fails does not discriminate (rule 49).

WHAT NO OUTCOME LICENCES. Sign agreement is NECESSARY, not sufficient. And the arms remain different
deposits with different montages, so E53's floor bounds everything except the sign itself.

    python -m bsde.experiments.e75_sign_within_pipeline
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
SLEEP = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")
DRUG_A = os.path.join(RESULTS, "ds005620_full.csv")
DRUG_B = os.path.join(RESULTS, "ds004541_v2.csv")
OUT = os.path.join(RESULTS, "e75_sign_within_pipeline.json")

DEPTH = ("W", "N1", "N2", "N3")
REPS = 3000
PLACEBO_DRAWS = 300
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _dz(d, rng=None, reps=REPS):
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    if d.size < 5 or d.std(ddof=1) < 1e-12:
        return float("nan"), float("nan"), float("nan"), int(d.size)
    pt = float(d.mean() / d.std(ddof=1))
    if rng is None:
        return pt, float("nan"), float("nan"), int(d.size)
    v = []
    for _ in range(reps):
        b = d[rng.integers(0, d.size, d.size)]
        if b.std(ddof=1) > 1e-12:
            v.append(b.mean() / b.std(ddof=1))
    v = np.sort(v)
    return pt, float(np.quantile(v, .025)), float(np.quantile(v, .975)), int(d.size)


def _paired(rows, subj, is_a, is_b, feats):
    acc = defaultdict(lambda: defaultdict(lambda: ([], [])))
    for r in rows:
        s = subj(r)
        a, b = is_a(r), is_b(r)
        if not s or not (a or b):
            continue
        for f in feats:
            v = _f(r.get(f, ""))
            if np.isfinite(v):
                acc[f][s][0 if a else 1].append(v)
    return {f: np.array([np.median(y) - np.median(x)
                         for x, y in per.values() if x and y], float)
            for f, per in acc.items()}


def main() -> int:
    for p in (SLEEP, DRUG_A, DRUG_B):
        if not os.path.exists(p):
            print(f"MISSING {p} -- ds005620_full.csv is produced by scripts/stream_ds005620_full.py")
            return 2
    sleep = list(csv.DictReader(open(SLEEP, newline="")))
    da = [r for r in csv.DictReader(open(DRUG_A, newline="")) if r.get("status") == "ok"]
    db = [r for r in csv.DictReader(open(DRUG_B, newline="")) if r.get("status") == "ok"]

    def cols(rows):
        skip = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq",
                "n_samples"}
        return {c for c in rows[0] if c not in skip and not c.startswith("meta_")}
    feats = sorted(cols(sleep) & cols(da) & cols(db))
    print(f"{len(feats)} features common to all three bsde-path tables")
    print(f"   sleep {len(sleep)} rows | ds005620_full {len(da)} | ds004541 {len(db)}")

    rng = np.random.default_rng(SEED)
    NO = _paired(sleep, lambda r: r["subject"],
                 lambda r: r["recording_id"].endswith("@W"),
                 lambda r: r["recording_id"].endswith("@N3"), feats)
    A = _paired(da, lambda r: r["subject"],
                lambda r: r.get("meta_task", "") == "awake",
                lambda r: r.get("meta_task", "").startswith("sed"), feats)
    B = _paired(db, lambda r: r["subject"],
                lambda r: "@baseline" in r["recording_id"] or "@start-" in r["recording_id"],
                lambda r: "@loc" in r["recording_id"] or "@post" in r["recording_id"], feats)

    # G2 monotonicity across the graded depth axis, no-drug arm only.
    per_stage = defaultdict(lambda: defaultdict(dict))
    for r in sleep:
        if "@" in r["recording_id"]:
            st = r["recording_id"].rsplit("@", 1)[1]
            if st in DEPTH:
                for f in feats:
                    per_stage[f][r["subject"]][st] = _f(r.get(f, ""))
    mono = {}
    for f in feats:
        med = [float(np.nanmedian([per_stage[f][s].get(st, np.nan) for s in per_stage[f]]))
               for st in DEPTH]
        mono[f] = (all(x <= y for x, y in zip(med, med[1:]))
                   or all(x >= y for x, y in zip(med, med[1:])))

    print(f"\n{'feature':<26s} {'no-drug d_z':>12s} {'drug-A d_z':>11s} {'G1':>5s} {'G2 mono':>8s} "
          f"{'sign':>9s} {'drug-B':>8s}")
    agree, reverse, blocked = [], [], []
    res = {}
    for f in feats:
        n_pt, n_lo, n_hi, n_n = _dz(NO.get(f, np.array([])), np.random.default_rng(SEED))
        a_pt, a_lo, a_hi, a_n = _dz(A.get(f, np.array([])), np.random.default_rng(SEED + 1))
        b_pt, b_lo, b_hi, b_n = _dz(B.get(f, np.array([])), np.random.default_rng(SEED + 2))
        alive = all(np.isfinite(lo) and (lo > 0 or hi < 0) for lo, hi in ((n_lo, n_hi), (a_lo, a_hi)))
        ok = alive and mono[f]
        sign = "--"
        if ok:
            same = np.sign(n_pt) == np.sign(a_pt)
            sign = "AGREE" if same else "REVERSE"
            (agree if same else reverse).append(f)
        else:
            blocked.append(f)
        bs = ("--" if not (np.isfinite(b_lo) and (b_lo > 0 or b_hi < 0))
              else ("agree" if np.sign(b_pt) == np.sign(n_pt) else "reverse"))
        res[f] = {"no_drug_dz": n_pt, "drug_a_dz": a_pt, "drug_b_dz": b_pt,
                  "n_no_drug": n_n, "n_drug_a": a_n, "n_drug_b": b_n,
                  "alive": bool(alive), "monotone": bool(mono[f]), "sign": sign, "drug_b": bs}
        print(f"{f:<26s} {n_pt:>12.3f} {a_pt:>11.3f} {'ok' if alive else 'FAIL':>5s} "
              f"{str(mono[f]):>8s} {sign:>9s} {bs:>8s}")

    # P1 placebo: permute the state label within subject in BOTH arms.
    rp = np.random.default_rng(SEED + 3)
    testable = agree + reverse
    hits = []
    for _ in range(PLACEBO_DRAWS):
        c = 0
        for f in testable:
            sn = []
            for arr in (NO[f], A[f]):
                flip = np.where(rp.random(arr.size) < 0.5, -1.0, 1.0)
                sn.append(np.sign(_dz(arr * flip)[0]))
            c += int(sn[0] == sn[1])
        hits.append(c / max(1, len(testable)))
    plac = float(np.mean(hits))
    real = len(agree) / max(1, len(testable))
    # CORRECTION 2026-07-31, after the first run. The branch below originally compared |real - 0.5|
    # against |plac - 0.5|, and that gate COULD NOT FAIL: `plac` is a mean over 300 draws and sits at
    # ~0.500 by construction, while `real` with an ODD number of testable features can never equal 0.500.
    # So NOT INFORMATIVE was structurally unreachable -- rule 40 in the verdict code, which rule 37 has
    # already caught four times. The comparison is now against the placebo DISTRIBUTION, one-sided, which
    # is what "the placebo reproduces the agreement rate" has to mean. This makes the test STRICTER after
    # seeing a pass, never looser, and it changes no threshold, cohort, contrast or gate.
    plac_p = float(np.mean(np.asarray(hits) >= real))
    print(f"\nPRIMARY  {len(agree)} AGREE, {len(reverse)} REVERSE of {len(testable)} testable "
          f"(rate {real:.3f})")
    print(f"P1 PLACEBO  state labels permuted within subject: mean {plac:.3f} ({PLACEBO_DRAWS} draws); "
          f"fraction of draws reaching the real rate = {plac_p:.3f}")
    if blocked:
        print(f"BLOCKED by G1/G2: {blocked}")

    if not testable:
        verdict = "NONE TESTABLE -- G1 or G2 removed every feature."
    elif not agree:
        verdict = ("ALL REVERSE -- every surviving feature moves the opposite way with and without a drug. "
                   "Everything measured here reads pharmacology rather than state.")
    elif plac_p > 0.05:
        verdict = (f"NOT INFORMATIVE -- permuting the state label reproduces the agreement rate: "
                   f"{plac_p:.3f} of placebo draws reach {real:.3f} or better. The per-feature signs "
                   f"below are each determined by their own G1 interval and are reported as DESCRIPTIVE, "
                   f"but the SET shows no more structure than chance and must not be presented as a "
                   f"class of measures.")
    elif not reverse:
        verdict = (f"ALL AGREE -- all {len(agree)} surviving features agree in sign. WEAKER than it looks: "
                   f"a test nothing fails does not discriminate between candidates (rule 49).")
    else:
        verdict = (f"SPLIT -- AGREE {agree}; REVERSE {reverse}. The reversing set must never be described "
                   f"as consciousness markers: within either arm alone they look fine. The agreeing set is "
                   f"Challenge A's candidate list, subject to sign agreement being NECESSARY and not "
                   f"sufficient.")
    print(f"\nVERDICT: {verdict}")
    json.dump({"n_features": len(feats), "features": res, "agree": agree, "reverse": reverse,
               "blocked": blocked, "agreement_rate": real, "placebo_rate": plac, "placebo_p": plac_p,
               "placebo_hits": hits,
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
