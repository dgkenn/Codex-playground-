"""E131 -- Does the SMR-family predictor work in STIEGER, the cohort where `ge_norm` appeared to work?

REGISTERED BEFORE `alpha_prom` HAS BEEN PUT NEAR STIEGER'S ACCURACY. `stieger_graph62.csv` has carried
`alpha_prom` since it was written -- it is one of the two `PERIODIC` columns the extractor always
produced -- and no experiment has ever correlated it with the outcome. That is the point of this file.

=========================================================================================================
WHY, AND WHY IT IS DIAGNOSTIC RATHER THAN JUST ANOTHER TEST
=========================================================================================================
E129 replicated Blankertz's published SMR predictor on Dreyer's 87 subjects: +0.4440 [+0.2480, +0.6104]
against a published +0.53 whose single-session attenuated expectation is +0.4183. On the SAME subjects,
this project's `ge_norm` gave -0.2065. And the pre-existing `alpha_prom` -- a 7-13 Hz peak prominence
above an aperiodic fit, median over channels, computed by this project's own extractor and NOT a
transcription of anyone's published formula -- gave +0.3710 [+0.1709, +0.5512].

So in Dreyer, an SMR-family measure predicts BCI performance and `ge_norm` does not. **Stieger is the
cohort where `ge_norm` did**: E86 found +0.3069 [+0.0495, +0.5343] there, and E124 and E125 then failed to
replicate it twice. Three readings of E86 remain open and they make different predictions here:

    (i)  E86 was noise                      -> alpha_prom should work in Stieger as it does in Dreyer,
                                               and ge_norm's Stieger result was a coincidence.
    (ii) Stieger is genuinely different      -> alpha_prom should FAIL in Stieger while working in Dreyer.
    (iii) ge_norm captured SMR indirectly    -> alpha_prom should work in Stieger AND correlate with
          in Stieger only                       ge_norm there, while the two are unrelated in Dreyer.

**No further analysis of Dreyer can separate these. This can**, and it costs nothing: the column already
exists.

=========================================================================================================
DESIGN -- E86'S, WITH ONE COLUMN SUBSTITUTED AND NOTHING ELSE TOUCHED
=========================================================================================================
    P   spearman( alpha_prom , accuracy ) across the 62 subjects, PREDICTED POSITIVE, one test.

    Both are the MEAN OVER THE THREE SESSIONS, which is E86's own aggregation and is not renegotiated
    here. Using a single session, or the best session, would be a different design and a worse one.

    Case bootstrap over subjects, 4000 reps, using E108's `spearman` and `boot` -- the same estimator that
    produced +0.3069, -0.1298, -0.2065 and +0.4440, so no cross-experiment difference can be an estimator
    difference (rule 20).

SECONDARIES, reported whole either way (rule 59), NOT eligible to become the headline:
    S1  `iaf` against accuracy -- E106's escape candidate, carried so this table is complete.
    S2  rho(alpha_prom, ge_norm) IN STIEGER, and the same quantity in Dreyer for contrast. This is the
        statistic that separates reading (iii) from (i), and it is declared before either is computed.
    S3  `ge_norm` against accuracy, recomputed here from the same file, to confirm E86's +0.3069
        reproduces under this exact pipeline. **If it does not, everything downstream of E86 needs
        re-examining and that is a bigger finding than the primary.**

GATES
    G1  COVERAGE: >= 50 subjects with a finite predictor and outcome in all three sessions.
    G2  OUTCOME ALIVE: accuracy must vary and its median exceed chance. E63 and E68 already characterised
        this label's reliability; the gate is re-evaluated rather than assumed.
    G3  PREDICTOR ALIVE: `alpha_prom` must vary and be positive for most subjects, since it is a peak
        height above a fitted background and a negative median would mean the fit is wrong.

PLACEBO, gating the verdict in EITHER direction (the clause E125's first draft omitted): accuracy permuted
across subjects, 2000 draws; a real estimate inside the central 95 % is WITHDRAWN whatever its sign.
Rule 48: the primary interval is read first.

VERDICT, wrong direction FIRST (rule 37, tenth occurrence):
    (a) excludes 0 NEGATIVE -> CONTRADICTED. An SMR-family measure predicting BCI performance the WRONG
        way in one cohort while predicting it correctly in another would mean the measure is not
        measuring what Blankertz's is, and E129 would need re-reading.
    (b) includes 0 -> DOES NOT WORK HERE, and the report must say which kind (rule 31): whether Dreyer's
        +0.3710 lies inside the interval (compatible, underpowered) or outside (actively excluded).
    (c) excludes 0 POSITIVE and beats the placebo -> WORKS IN BOTH COHORTS. Combined with E124 and E125,
        this makes reading (i) the live one: E86 was noise, and this project spent Challenge B measuring
        a predictor that does not work while carrying one that does.

CALIBRATION before the run: (c) ~55 %, (b) ~35 %, (a) ~10 %.

SCOPE. 62 subjects, three sessions, a cursor-control BCI with feedback and learning across sessions --
which is NOT Dreyer's single-session OpenViBE classifier accuracy, and not Blankertz's BBCI either. The
predictor here is `alpha_prom`, a median-over-62-channels 7-13 Hz prominence, NOT the sensorimotor
Laplacian construction E129 used; E129 measured them to be similar in Dreyer (+0.3710 against +0.4440,
heavily overlapping intervals) but they are not the same measure and a difference between cohorts could
in principle be a difference between measures. Stated now (rule 47).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e131_smr_in_stieger.json")
GRAPH = os.path.join(RESULTS, "stieger_graph62.csv")
LABELS = os.path.join(RESULTS, "stieger_labels.csv")

PRIMARY = "alpha_prom"
DREYER_ALPHA_PROM = 0.3710
E86_GE_NORM = 0.3069
MIN_SUBJECTS = 50
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260803


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def subject_means(path, keys):
    by = {}
    for r in csv.DictReader(open(path, newline="")):
        s = r.get("subject")
        if not s:
            continue
        by.setdefault(s, []).append(r)
    out = {}
    for s, rows in by.items():
        d = {}
        for k in keys:
            v = [_f(r.get(k, "")) for r in rows]
            v = [q for q in v if np.isfinite(q)]
            d[k] = float(np.mean(v)) if v else float("nan")
        d["n_sessions"] = len(rows)
        out[s] = d
    return out


def main(argv=None) -> int:
    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E131", "B",
            "Does the SMR-family predictor (alpha_prom) work in STIEGER, where ge_norm appeared to?",
            "stieger",
            "spearman(alpha_prom, accuracy) over 62 subjects, three-session means, PREDICTED POSITIVE",
            ["G1 >=50 subjects", "G2 outcome alive", "G3 predictor alive and positive"],
            "accuracy permuted across subjects, 2000 draws; inside the central 95% is WITHDRAWN in "
            "EITHER direction",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E129",
            instrument_changed="the COHORT: Stieger, where ge_norm appeared to work, with the SMR-family "
                               "column that has been in stieger_graph62.csv all along and never tested")
        print("registered E131")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)
    if a.register_only:
        return 0

    sys.path.insert(0, HERE)
    from e108_ge_norm_external_replication import boot, spearman           # noqa: E402

    g = subject_means(GRAPH, [PRIMARY, "ge_norm", "iaf"])
    lab = subject_means(LABELS, ["accuracy"])
    subs = sorted(set(g) & set(lab))
    x = np.array([g[s][PRIMARY] for s in subs])
    y = np.array([lab[s]["accuracy"] for s in subs])
    gn = np.array([g[s]["ge_norm"] for s in subs])
    iaf = np.array([g[s]["iaf"] for s in subs])
    ok = np.isfinite(x) & np.isfinite(y)
    x, y, gn, iaf = x[ok], y[ok], gn[ok], iaf[ok]
    n = x.size

    res = {"n_subjects": int(n), "gates": {}}
    print(f"{len(g)} subjects with graph rows, {len(lab)} with a label; {n} usable")
    res["gates"]["G1_pass"] = bool(n >= MIN_SUBJECTS)
    # CHANCE IS DETECTED FROM THE SCALE, NOT ASSUMED. Stieger reports accuracy as a FRACTION (median
    # 0.60) while Dreyer reports a PERCENTAGE (median 56.25). A gate hardcoded to one convention refuses
    # the other and reads as a dead outcome -- which is exactly what the first run of this file did. The
    # same unit trap `mac_to_vol_pct_sevo` raises on, met again in an outcome column.
    chance = 0.5 if float(np.nanmax(y)) <= 1.5 else 50.0
    g2 = bool(np.ptp(y) > 0 and float(np.median(y)) > chance)
    res["gates"].update({"G2_median_accuracy": float(np.median(y)), "G2_chance_level": chance,
                         "G2_spread": float(np.ptp(y)), "G2_pass": g2})
    g3 = bool(np.ptp(x) > 0 and np.mean(x > 0) > 0.5)
    res["gates"].update({"G3_median": float(np.median(x)), "G3_sd": float(np.std(x)),
                         "G3_frac_positive": float(np.mean(x > 0)), "G3_pass": g3})
    print(f"G1 coverage   {n} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    print(f"G2 outcome    median {np.median(y):.4f}, spread {np.ptp(y):.4f}, chance {chance}  "
          f"{'PASS' if g2 else 'FAIL'}")
    print(f"G3 predictor  median {np.median(x):.4f}, sd {np.std(x):.4f}, "
          f"range [{x.min():.3f}, {x.max():.3f}]  {'PASS' if g3 else 'FAIL'}")
    if not (res["gates"]["G1_pass"] and g2 and g3):
        res["verdict"] = "ABSENT -- a precondition failed."
        json.dump(res, open(a.out, "w"), indent=2)
        print(f"\nVERDICT: {res['verdict']}")
        return 1

    r = spearman(x, y)
    lo, hi = boot(x, y, np.random.default_rng(SEED), reps=REPS)
    res["primary"] = {"rho": r, "lo": lo, "hi": hi, "n": int(n),
                      "dreyer_alpha_prom": DREYER_ALPHA_PROM}
    print(f"\nP  spearman({PRIMARY}, accuracy) = {r:+.4f} [{lo:+.4f}, {hi:+.4f}]  over {n} subjects")
    print(f"   the same column in Dreyer gave {DREYER_ALPHA_PROM:+.4f}")

    sec = {}
    for name, v in (("iaf", iaf), ("ge_norm", gn)):
        m = np.isfinite(v)
        rr = spearman(v[m], y[m])
        l2, h2 = boot(v[m], y[m], np.random.default_rng(SEED + 1), reps=REPS)
        sec[name] = {"rho": rr, "lo": l2, "hi": h2, "n": int(m.sum())}
        print(f"S  {name:12s} vs accuracy {rr:+.4f} [{l2:+.4f}, {h2:+.4f}]")
    m = np.isfinite(x) & np.isfinite(gn)
    sec["rho_alpha_prom_ge_norm_stieger"] = spearman(x[m], gn[m])
    print(f"S  rho(alpha_prom, ge_norm) in Stieger = {sec['rho_alpha_prom_ge_norm_stieger']:+.4f}")
    res["secondaries"] = sec

    # S3 sanity: does E86's own number reproduce under this pipeline?
    e86_ok = abs(sec["ge_norm"]["rho"] - E86_GE_NORM) < 0.05
    res["gates"]["S3_e86_reproduces"] = bool(e86_ok)
    print(f"S3 E86 reproduction: ge_norm {sec['ge_norm']['rho']:+.4f} vs published {E86_GE_NORM:+.4f}  "
          f"{'OK' if e86_ok else 'MISMATCH -- everything downstream of E86 needs re-examining'}")

    prng = np.random.default_rng(SEED + 2)
    draws = np.array([spearman(x, prng.permutation(y)) for _ in range(PLACEBO_DRAWS)])
    plo, phi = float(np.quantile(draws, .025)), float(np.quantile(draws, .975))
    inside = bool(plo <= r <= phi)
    res["placebo"] = {"p2.5": plo, "p97.5": phi, "real_inside": inside}
    print(f"PLACEBO accuracy permuted: [{plo:+.4f}, {phi:+.4f}]  real "
          f"{'INSIDE' if inside else 'OUTSIDE'}")

    if not np.isfinite(lo):
        res["verdict"] = "ABSENT -- the primary could not be estimated."
    elif inside:
        kind = ("compatible with Dreyer's +0.3710" if lo <= DREYER_ALPHA_PROM <= hi
                else "and it EXCLUDES Dreyer's +0.3710")
        res["verdict"] = (f"(b) DOES NOT WORK HERE, {kind}. {r:+.4f} [{lo:+.4f}, {hi:+.4f}] lies INSIDE "
                          f"the permutation interval [{plo:+.4f}, {phi:+.4f}], so no directional claim "
                          "survives whatever its sign.")
    elif hi < 0:
        res["verdict"] = (f"(a) CONTRADICTED -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}] excludes zero NEGATIVE, "
                          "while the same column predicts BCI performance POSITIVELY in Dreyer. An "
                          "SMR-family measure cannot point both ways, so E129 needs re-reading.")
    elif lo > 0:
        res["verdict"] = (f"(c) WORKS IN BOTH COHORTS -- {r:+.4f} [{lo:+.4f}, {hi:+.4f}] here against "
                          f"{DREYER_ALPHA_PROM:+.4f} in Dreyer, beating the permutation placebo. "
                          "Combined with E124 and E125 this makes the live reading of E86 that it was "
                          "NOISE: this project spent Challenge B measuring a predictor that does not "
                          "work while carrying, in the same files, one that does.")
    else:
        kind = ("compatible with Dreyer's +0.3710" if lo <= DREYER_ALPHA_PROM <= hi
                else "and it EXCLUDES Dreyer's +0.3710")
        res["verdict"] = f"(b) DOES NOT WORK HERE, {kind}. {r:+.4f} [{lo:+.4f}, {hi:+.4f}]."
    print(f"\nVERDICT: {res['verdict']}")
    json.dump(res, open(a.out, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
