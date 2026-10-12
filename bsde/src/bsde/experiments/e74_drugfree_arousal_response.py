#!/usr/bin/env python3
"""E74 -- Challenge A. Which measures respond to an arousal change with NO DRUG in it?

REGISTERED AFTER A FEASIBILITY PROBE (rule 41) AND BEFORE ANY FEATURE-BY-ANCHOR CORRELATION. The probe read
the deposit's structure, the behavioural anchors, and the paired EEG deltas listed below. It did NOT relate
any feature to any anchor, which is the one thing this file tests.

=========================================================================================================
WHAT THE PROBE FOUND, INCLUDING THE PART THAT DAMAGES Q29's PLAN
=========================================================================================================
Q29 acquired ds004902 as Challenge A's missing DENOMINATOR: an arousal change with no pharmacology, to sit
beside the drug arms so a drug-response / state-response ratio becomes computable. The deposit is less
usable for that than Q29 assumed, and the reasons are structural:

  * **eyes-closed exists for only about half the subjects** -- the README says "eyes open, partially eyes
    closed", and the extraction bears it out: 139 eyes-open recordings against 74 eyes-closed.
  * **KSS was collected only from sub-39 onward.** Subjects with two eyes-closed sessions are sub-01
    upward. **The overlap is exactly ZERO.**
  * So the arm with the larger EEG effect (eyes-closed: `exponent_low` d_z **+0.579**, n = 36) has NO
    behavioural anchor, and the arm with the anchors (eyes-open, n = 68) has weak EEG effects
    (`dfa_exponent` +0.357, `lempel_ziv` -0.324, `exponent_low` **+0.091**).

**A calibrated ratio is therefore not available from this deposit.** What IS available is well powered and
still answers half of Challenge A's condition.

=========================================================================================================
DESIGN
=========================================================================================================
COHORT. Eyes-open only, both sessions, same subject: **n = 68**. Eye state is first-order (E44) and is held
constant by construction rather than adjusted for.

  G1 MANIPULATION GATE, evaluated first. The arousal change must have HAPPENED, measured on the deposit's
     own anchors and not on the EEG. Probe values: KSS rises **+2.000 (d_z +0.969, n = 32)** and SSS
     **+1.667 (d_z +0.782, n = 33)**. **PVT lapses do NOT move: -0.033, d_z -0.008, n = 30.** The gate
     requires a subjective anchor to clear zero; **the objective null is reported beside it either way,
     because a subjectively-sleepier cohort that is not objectively slower is a different manipulation from
     the one Q29 assumed.**

  PRIMARY  per feature, the within-subject paired d_z from normal sleep to deprivation, with a subject
           bootstrap. At n = 68 the minimum detectable |d_z| is about 0.35, so this **excludes a moderate
           effect and not a small one**, and the write-up must say which.

  S1 RATIO CONTEXT  each feature's drug-free d_z placed beside its DRUG d_z from E67 (ds005620 propofol,
           ds004541 general anaesthesia). **The RANKING is the claim, never the ratio's value**: the arms
           are different deposits and anaesthesia is a far larger state change than one night of
           deprivation, so every feature will move more in the drug arm. A feature that moves a lot for a
           drug and NOT AT ALL without one is carrying pharmacology; one that moves in both is carrying
           state. E53's cross-deposit floor bounds anything beyond the ordering.

  S2 ANCHOR  among features clearing the primary, the correlation between their change and the SUBJECTIVE
           sleepiness change (n = 32-33). Descriptive and underpowered by construction -- minimum
           detectable |rho| is about 0.50 -- and labelled as such.

  P1 PLACEBO  session labels permuted within subject, primary recomputed.

VERDICT RULE, wrong direction first.

  (a) MANIPULATION ABSENT -- G1 fails: no anchor moves, so nothing here is about arousal.
  (b) NO RESPONSE         -- no feature's paired interval excludes zero. A drug-free arousal change of this
                             size moves nothing this project measures, which would make the ratio
                             undefined for every feature (rule 53) and close this route.
  (c) NOT INFORMATIVE     -- the permutation placebo reaches the primary.
  (d) RESPONDS            -- at least one feature moves. Report which, and place them against E67's drug
                             arms as a RANKING with the depth caveat attached.

    python -m bsde.experiments.e74_drugfree_arousal_response
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
from bsde.verifier.stats import spearman                                      # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
FEATS = "/tmp/eeg_probe/sleepdep_features.csv"
PARTS = "/tmp/eeg_probe/p.tsv"
OUT = os.path.join(RESULTS, "e74_drugfree_arousal_response.json")

# Drug-arm d_z from E67, committed. propofol = ds005620 awake->sed; GA = ds004541 baseline->post-LOC.
DRUG_DZ = {"lempel_ziv": (1.551, 0.947), "relative_alpha_power": (1.184, -0.398),
           "relative_delta_power": (-0.333, -0.024), "spectral_edge_95": (-0.923, 0.208),
           "spectral_entropy": (0.113, -0.303), "whole_head_exponent": (1.110, 0.937)}
ANCHORS = {"KSS": ("KSS_NS", "KSS_SD"), "SSS": ("SSS_NS", "SSS_SD"),
           "PVT_lapses": ("PVT_item1_NS", "PVT_item1_SD")}
MIN_N = 30
REPS = 4000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _dz_ci(d, rng, reps=REPS):
    d = d[np.isfinite(d)]
    if d.size < 5 or d.std(ddof=1) < 1e-12:
        return float("nan"), float("nan"), float("nan"), int(d.size)
    pt = float(d.mean() / d.std(ddof=1))
    v = []
    for _ in range(reps):
        b = d[rng.integers(0, d.size, d.size)]
        if b.std(ddof=1) > 1e-12:
            v.append(b.mean() / b.std(ddof=1))
    v = np.sort(v)
    return pt, float(np.quantile(v, .025)), float(np.quantile(v, .975)), int(d.size)


def main() -> int:
    for p in (FEATS, PARTS):
        if not os.path.exists(p):
            print(f"MISSING {p}")
            return 2
    parts = {r["participant_id"]: r for r in csv.DictReader(open(PARTS), delimiter="\t")}
    per = defaultdict(dict)
    feat_names = None
    for r in csv.DictReader(open(FEATS, newline="")):
        if "open" in r.get("task", "").lower():
            per[r["subject"]][r["session"]] = r
            if feat_names is None:
                skip = {"cohort", "subject", "session", "file", "task", "acq", "age", "sex", "group",
                        "n_channels", "sfreq", "duration_s"}
                feat_names = [k for k in r if k not in skip and not k.startswith("n_")]
    subs = sorted(s for s, d in per.items() if "1" in d and "2" in d)
    print(f"eyes-open, both sessions: n = {len(subs)} subjects")

    # G1 manipulation gate, on the deposit's anchors only.
    rng = np.random.default_rng(SEED)
    anch = {}
    for name, (c1, c2) in ANCHORS.items():
        ss = [s for s in subs if s in parts
              and parts[s][c1] not in ("", "n/a") and parts[s][c2] not in ("", "n/a")]
        d = np.array([_f(parts[s][c2]) - _f(parts[s][c1]) for s in ss])
        pt, lo, hi, n = _dz_ci(d, np.random.default_rng(SEED))
        anch[name] = {"d_z": pt, "lo": lo, "hi": hi, "n": n,
                      "mean_delta": float(np.nanmean(d)) if d.size else float("nan")}
        print(f"   G1 {name:<11s} n={n:3d}  mean delta {anch[name]['mean_delta']:+.3f}  "
              f"d_z {pt:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    subjective = [a for a in ("KSS", "SSS") if np.isfinite(anch[a]["lo"]) and anch[a]["lo"] > 0]
    g1 = bool(subjective)
    print(f"   G1 {'PASS' if g1 else 'FAIL'} (a subjective anchor must clear zero)")

    res = {"n_subjects": len(subs), "anchors": anch, "gate_g1": g1}
    if not g1:
        verdict = ("MANIPULATION ABSENT -- no subjective anchor moved, so nothing here is about arousal.")
        print(f"\nVERDICT: {verdict}")
        res["verdict"] = verdict
        json.dump(res, open(OUT, "w"), indent=2)
        return 0

    print(f"\n{'feature':<24s} {'n':>4s} {'d_z (no drug)':>14s} {'95% CI':>20s} "
           f"{'drug: ppf / GA':>18s}")
    responders, rows = [], {}
    for f in sorted(feat_names or []):
        d = np.array([_f(per[s]["2"].get(f, "")) - _f(per[s]["1"].get(f, "")) for s in subs])
        pt, lo, hi, n = _dz_ci(d, np.random.default_rng(SEED + 1))
        if n < MIN_N or not np.isfinite(lo):
            continue
        alive = lo > 0 or hi < 0
        dg = DRUG_DZ.get(f)
        ds = f"{dg[0]:+.2f} / {dg[1]:+.2f}" if dg else "--"
        rows[f] = {"d_z": pt, "lo": lo, "hi": hi, "n": n, "responds": bool(alive),
                   "drug_dz": dg}
        print(f"{f:<24s} {n:>4d} {pt:>14.3f} [{lo:+.3f}, {hi:+.3f}]".ljust(66)
              + f"{ds:>18s}" + ("  RESPONDS" if alive else ""))
        if alive:
            responders.append(f)

    # P1 placebo: permute session labels within subject.
    rp = np.random.default_rng(SEED + 2)
    hits = []
    for _ in range(200):
        c = 0
        for f in rows:
            d = np.array([(1 if rp.random() < 0.5 else -1)
                          * (_f(per[s]["2"].get(f, "")) - _f(per[s]["1"].get(f, ""))) for s in subs])
            pt, lo, hi, n = _dz_ci(d, np.random.default_rng(SEED + 3), reps=200)
            if np.isfinite(lo) and (lo > 0 or hi < 0):
                c += 1
        hits.append(c)
    plac = float(np.mean(hits))
    print(f"\nPRIMARY  {len(responders)} of {len(rows)} features respond to a drug-free arousal change")
    print(f"P1 PLACEBO  session labels permuted within subject: {plac:.2f} responders on average "
          f"(200 draws)")

    # S2 anchor correlation, descriptive.
    s2 = {}
    best = subjective[0]
    c1, c2 = ANCHORS[best]
    ss = [s for s in subs if s in parts
          and parts[s][c1] not in ("", "n/a") and parts[s][c2] not in ("", "n/a")]
    da = np.array([_f(parts[s][c2]) - _f(parts[s][c1]) for s in ss])
    for f in responders:
        de = np.array([_f(per[s]["2"].get(f, "")) - _f(per[s]["1"].get(f, "")) for s in ss])
        ok = np.isfinite(de) & np.isfinite(da)
        s2[f] = {"rho": spearman(de[ok], da[ok]), "n": int(ok.sum()), "anchor": best}
        print(f"   S2 {f:<22s} rho with delta-{best} = {s2[f]['rho']:+.3f} (n={s2[f]['n']}, "
              f"DESCRIPTIVE, MDE ~0.50)")

    if not responders:
        verdict = ("NO RESPONSE -- a drug-free arousal change of this size moves nothing this project "
                   "measures at n = 68 (minimum detectable |d_z| ~0.35). The drug-response / state-response "
                   "ratio is undefined for every feature (rule 53) and this route to Challenge A closes on "
                   "this deposit. It excludes a MODERATE effect, not a small one.")
    elif plac >= len(responders):
        verdict = ("NOT INFORMATIVE -- permuting session labels within subject yields as many responders "
                   "as the real assignment.")
    else:
        verdict = (f"RESPONDS -- {responders} move under a drug-free arousal change. Placed against E67's "
                   f"drug arms the RANKING is the claim and not the ratio: the arms are different deposits "
                   f"and anaesthesia is a far larger state change than one night of deprivation, so a "
                   f"feature moving for a drug and NOT without one is carrying pharmacology, while one "
                   f"moving in both is carrying state.")
    print(f"\nVERDICT: {verdict}")
    print("\nNOTE: PVT lapses did not move while subjective sleepiness rose strongly. A cohort that feels "
          "sleepier without being objectively slower is a different manipulation from the one Q29 assumed, "
          "and any 'arousal' language here inherits that.")
    res.update({"features": rows, "responders": responders, "placebo_mean_responders": plac,
                "s2_anchor_correlation": s2, "verdict": verdict})
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
