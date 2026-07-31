"""E78 -- `bis_rbr` against the E76-corrected permutation entropy, on identical windows, on held-out DOSE-I.

REGISTERED BEFORE `dosei_holdout_comparators.csv` EXISTS. The extractor is committed in the same commit and
had not been run when this was written. **No value of either measure on any held-out recording has been
seen.**

--------------------------------------------------------------------------------------------------------
THE DEBT THIS DISCHARGES
--------------------------------------------------------------------------------------------------------
QUEUE.md **Q35** was an exploratory 29-feature scan on data E65 had already used. It found `bis_rbr` at
median within-recording rho **+0.5258** against MOAA/S, beating the deposit's shipped `PE31` (+0.4813) and
`SEF95` (+0.2507), and amended Q34's "PE31 is the comparator to use" to "`bis_rbr` matches or beats it
under every adjustment tried". Q35 wrote its own debt in the same paragraph:

    "A registered test on a deposit or a partition not used here, with `bis_rbr` and PE31 pre-declared,
     and the 29-feature multiplicity handled rather than noted."

**E76 then changed the arithmetic.** Our permutation entropy had been mis-specified: applying the deposit's
declared 0.5-45 Hz band and 0.5 uV tie threshold raises clinician tracking by +0.1609 [+0.0764, +0.2613],
to a median of **+0.5304**. Against Q35's +0.5258 that is a tie -- and the two numbers come from different
window definitions in different passes, so a reader should not accept even the tie. **The question is
therefore genuinely open, and it is Challenge C's comparator choice.**

--------------------------------------------------------------------------------------------------------
HOW THE MULTIPLICITY IS HANDLED -- by design, not by correction
--------------------------------------------------------------------------------------------------------
Q35 scanned 29 features. **No correction to that scan is applied or attempted**, because a corrected scan
is still a scan. Instead this is a confirmatory test of ONE pre-declared contrast between TWO pre-declared
measures, on recordings none of the 29 was computed on. Every DOSE-I number this project holds -- E33, E34,
E59, E65, Q35, Q36, E76 -- comes from the same 43 recordings; the deposit ships 171 pEEG tables; the
extractor refuses any recording in that union of 43 and asserts the refusal.

--------------------------------------------------------------------------------------------------------
PRIMARY
--------------------------------------------------------------------------------------------------------
Per recording, Spearman rho against MOAA/S for each measure on the SAME windows; then

    D = mean_rec[ rho(bis_rbr, MOAA/S) - rho(pe_declared, MOAA/S) ]

aggregated by a recording-level bootstrap (20,000 resamples, three seeds, the fraction of resamples on the
wrong side of zero reported beside every interval -- rule 46).

**SIGNED, not folded.** Both measures are predicted to rise as sedation lightens, so both rhos are predicted
POSITIVE. A measure that tracks the clinician backwards has not won anything, and a folded |rho| would hand
it a score; rule 46's second half says a folded statistic is biased upward under the null and must never be
reported as a single measure's effect size.

PREDICTION WRITTEN NOW: **D includes zero.** Q35's margin over the shipped PE31 was +0.0445, and E76's
correction moved our PE by more than three times that, in the direction that erases it. Stating the
prediction that contradicts this project's own earlier amendment is the point of registering it.

--------------------------------------------------------------------------------------------------------
VERDICT RULE -- the wrong-direction case is the first branch, by name (rule 37, now at five occurrences)
--------------------------------------------------------------------------------------------------------
    (a) CI excludes 0 and D is NEGATIVE
            -> PE-BETTER. Q35's amendment is REFUTED on held-out data: `bis_rbr` does not match or beat
               permutation entropy, it loses to it. This is not "no difference" and must not print as one.
    (b) CI includes 0
            -> TIE. Neither is adopted over the other. Q35's amendment survives only in the weak form
               ("matches"), never in the strong form ("beats"), and Challenge C may use either provided it
               says which and reports the other beside it.
    (c) CI excludes 0 and D is POSITIVE
            -> RBR-BETTER. Only here is Q35's amendment supported by a confirmatory test.

--------------------------------------------------------------------------------------------------------
GATES, before the primary, each able to refuse it (rule 40)
--------------------------------------------------------------------------------------------------------
    G1  HELD OUT     zero overlap with the 43 recordings already used. Any overlap and the verdict is
                     ABSENT, because a held-out test on used data is not a held-out test.
    G2  COVERAGE     >= 20 recordings carrying >= 10 windows with finite `bis_rbr`, `pe_declared` and
                     MOAA/S, and MOAA/S taking more than one value in the recording.
    G3  BOTH VARY    within each included recording BOTH measures must vary (rule 32: a comparison between
                     two predictors requires both to vary in the stratum they are compared in). Recordings
                     failing this are excluded and the count is reported, not silently dropped.
    G4  PREPROCESS   median `tie_frac` > 0.01 and median `band_rel_delta` > 0.01, so `pe_declared` is
                     actually the declared recipe rather than a relabelling of the raw one. The extractor
                     separately refuses any recording whose EEG IQR is outside [0.5, 5000] uV.

INCUMBENTS, named in advance (rule 45) and reported beside the primary as DESCRIPTIVE: the deposit's own
`PE31` and `SEF95`, each with its median rho and its paired difference against both candidates. They gate
nothing and set no threshold; they exist so the winner is read against two published bars rather than only
against the loser.

PLACEBO, applied only after the primary and only able to remove a result (rule 34). Each measure's series
is circularly shifted within its recording by half its length and the rhos recomputed. Both are expected to
collapse toward zero. **If a measure's shifted rho does NOT collapse, that measure's correlation with
MOAA/S is a shared slow trend rather than a tracking relationship, and the primary is NOT INTERPRETABLE for
it** -- reported as that, not as a win for the other.

SCOPE. This ranks two computable comparators against one behavioural sedation scale on one deposit. It is
not a claim that either measures consciousness, and it does not transfer to anaesthesia with neuromuscular
blockade, where E77's scope limit applies to `bis_rbr` in particular.

    python -m bsde.experiments.e78_holdout_comparator_headtohead
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

TABLE = os.path.join(RESULTS, "dosei_holdout_comparators.csv")
OUT = os.path.join(RESULTS, "e78_holdout_comparator_headtohead.json")
USED_TABLES = ("dosei_features.csv", "dosei_pe_check.csv", "dosei_pe_variants.csv")

CANDIDATES = ("bis_rbr", "pe_declared")
INCUMBENTS = ("their_pe31", "their_sef95")
MIN_WINDOWS = 10
MIN_RECORDINGS = 20
N_BOOT = 20000
SEEDS = (21, 22, 23)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < MIN_WINDOWS:
        return float("nan")
    x, y = a[ok], b[ok]
    if len(set(x.tolist())) < 2 or len(set(y.tolist())) < 2:
        return float("nan")
    from scipy.stats import spearmanr
    return float(spearmanr(x, y).statistic)


def used_recordings() -> set:
    out = set()
    for name in USED_TABLES:
        p = os.path.join(RESULTS, name)
        if not os.path.exists(p):
            continue
        with open(p, newline="") as fh:
            rd = csv.DictReader(fh)
            key = "recording" if "recording" in (rd.fieldnames or []) else "recording_id"
            for r in rd:
                v = r.get(key, "")
                if v:
                    out.add(v.split("@")[0])
    return out


def boot_mean(vals, seed, n_boot=N_BOOT):
    v = np.asarray([x for x in vals if np.isfinite(x)], float)
    if v.size < 3:
        return float("nan"), float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, v.size, size=(n_boot, v.size))].mean(axis=1)
    point = float(v.mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    wrong = float(np.mean(means <= 0.0)) if point > 0 else float(np.mean(means >= 0.0))
    return point, float(lo), float(hi), wrong


def verdict(point, lo, hi):
    if not np.isfinite(point):
        return "NOT-COMPUTABLE"
    if lo < 0 and hi < 0:
        return "PE-BETTER"
    if lo > 0 and hi > 0:
        return "RBR-BETTER"
    return "TIE"


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE} does not exist yet"); return 2
    res = {"gates": {}, "primary": {}, "descriptive": {}, "placebo": {}}
    rows = defaultdict(list)
    with open(TABLE, newline="") as fh:
        for r in csv.DictReader(fh):
            rows[r["recording"]].append(r)
    print(f"{len(rows)} recordings, {sum(len(v) for v in rows.values())} windows")

    overlap = sorted(set(rows) & used_recordings())
    res["gates"]["G1_overlap"] = overlap
    res["gates"]["G1_pass"] = not overlap
    print(f"G1 held out       {len(overlap)} overlapping recordings   "
          f"{'PASS' if not overlap else 'FAIL ' + str(overlap[:5])}")

    tie = float(np.nanmedian([np.nanmedian([_f(r['tie_frac']) for r in v]) for v in rows.values()]))
    band = float(np.nanmedian([np.nanmedian([_f(r['band_rel_delta']) for r in v]) for v in rows.values()]))
    res["gates"].update({"G4_tie_frac": tie, "G4_band_rel_delta": band,
                         "G4_pass": bool(tie > 0.01 and band > 0.01)})
    print(f"G4 preprocessing  tie_frac {tie:.4f}, band_rel_delta {band:.4f}   "
          f"{'PASS' if res['gates']['G4_pass'] else 'FAIL'}")

    rho = {k: [] for k in CANDIDATES + INCUMBENTS}
    rho_shift = {k: [] for k in CANDIDATES}
    kept, dropped_novary = [], []
    for rec, rs in sorted(rows.items()):
        mo = np.array([_f(r["moaas"]) for r in rs])
        if np.isfinite(mo).sum() < MIN_WINDOWS or len(set(mo[np.isfinite(mo)].tolist())) < 2:
            continue
        cols = {k: np.array([_f(r[k]) for r in rs]) for k in CANDIDATES + INCUMBENTS}
        if any(np.isfinite(cols[k]).sum() < MIN_WINDOWS
               or len(set(cols[k][np.isfinite(cols[k])].tolist())) < 2 for k in CANDIDATES):
            dropped_novary.append(rec)
            continue
        kept.append(rec)
        for k in CANDIDATES + INCUMBENTS:
            rho[k].append(spearman(cols[k], mo))
        for k in CANDIDATES:
            rho_shift[k].append(spearman(np.roll(cols[k], len(cols[k]) // 2), mo))

    res["gates"].update({"G2_recordings": len(kept), "G3_dropped_no_variation": len(dropped_novary),
                         "G2_pass": bool(len(kept) >= MIN_RECORDINGS)})
    print(f"G2 coverage       {len(kept)} recordings usable   "
          f"{'PASS' if len(kept) >= MIN_RECORDINGS else 'FAIL'}")
    print(f"G3 both vary      {len(dropped_novary)} recordings dropped for a constant measure")

    print("\nmedian within-recording rho vs MOAA/S")
    for k in CANDIDATES + INCUMBENTS:
        res["descriptive"][f"median_rho_{k}"] = float(np.nanmedian(rho[k]))
        print(f"    {k:14s} {np.nanmedian(rho[k]):+.4f}")

    if not (res["gates"]["G1_pass"] and res["gates"]["G2_pass"] and res["gates"]["G4_pass"]):
        print("\nGATE FAILED -- the primary is not evaluated. The verdict is ABSENT, not a tie (rule 31).")
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    d = [a - b for a, b in zip(rho["bis_rbr"], rho["pe_declared"])]
    per_seed = {}
    for s in SEEDS:
        pt, lo, hi, wrong = boot_mean(d, s)
        per_seed[s] = {"D": pt, "lo": lo, "hi": hi, "frac_wrong_side": wrong,
                       "verdict": verdict(pt, lo, hi)}
    vs = {p["verdict"] for p in per_seed.values()}
    overall = per_seed[SEEDS[0]]["verdict"] if len(vs) == 1 else "SEED-UNSTABLE"
    p0 = per_seed[SEEDS[0]]
    res["primary"] = {"per_seed": per_seed, "verdict": overall}
    print(f"\nPRIMARY  D = rho(bis_rbr) - rho(pe_declared) = {p0['D']:+.4f} "
          f"[{p0['lo']:+.4f}, {p0['hi']:+.4f}]  frac wrong side {p0['frac_wrong_side']:.4f}")
    print(f"    VERDICT {overall}" + ("" if len(vs) == 1 else f"  (seeds disagree: {sorted(vs)})"))

    print("\nagainst the named incumbents (DESCRIPTIVE, gating nothing)")
    for c in CANDIDATES:
        for inc in INCUMBENTS:
            dd = [a - b for a, b in zip(rho[c], rho[inc])]
            pt, lo, hi, _ = boot_mean(dd, SEEDS[0])
            res["descriptive"][f"{c}_minus_{inc}"] = [pt, lo, hi]
            print(f"    {c:14s} - {inc:12s} {pt:+.4f} [{lo:+.4f}, {hi:+.4f}]")

    print("\nPLACEBO  circular shift within recording (can only remove a result)")
    for c in CANDIDATES:
        m_real = float(np.nanmedian(rho[c]))
        m_shift = float(np.nanmedian(rho_shift[c]))
        collapsed = abs(m_shift) < abs(m_real) / 2.0
        res["placebo"][c] = {"real": m_real, "shifted": m_shift, "collapsed": bool(collapsed)}
        print(f"    {c:14s} real {m_real:+.4f}  shifted {m_shift:+.4f}   "
              f"{'collapses' if collapsed else 'DOES NOT COLLAPSE -- rho is a shared slow trend'}")
    if not all(v["collapsed"] for v in res["placebo"].values()):
        res["verdict"] = "NOT-INTERPRETABLE"
        print("\nAt least one measure's correlation survives a circular shift, so the primary is "
              "NOT INTERPRETABLE for it and is withdrawn rather than reported as a win for the other.")
    else:
        res["verdict"] = overall

    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
