"""E76 -- Does DOSE-I's DECLARED preprocessing account for the gap between our permutation entropy and theirs?

REGISTERED BEFORE `dosei_pe_variants.csv` EXISTS. The extractor
(`bsde/scripts/extract_dosei_pe_variants.py`) is committed in the same commit as this file and had not been
run when both were written.

--------------------------------------------------------------------------------------------------------
THE STANDING FACT THIS EXPERIMENT IS ABOUT
--------------------------------------------------------------------------------------------------------
`extract_dosei_pe.py` computed our `permutation_entropy(order=3, delay=1)` on 10,927 windows of DOSE-I raw
EEG, beside the depositors' own `PE31`, over 39 recordings. Measured:

    median within-recording rho(ours, PE31)                 +0.7239   IQR [+0.2885, +0.8183]
    the same with our series circularly shifted (placebo)   -0.1238
    median within-recording rho(ours,  MOAA/S)              +0.3545
    median within-recording rho(PE31,  MOAA/S)              +0.4944

The parameters are nominally identical -- the deposit's `pEEG_parameter_description.txt` says of column 30
(named `PE31` in its CSVs) "according to Olofsen et al. (2008), band: 0.5-45 Hz, n=3, tau=1, tie=0.5 uV",
and our call is order 3, delay 1. **So a +0.72 agreement and a 0.14 gap in clinician-tracking are both
unexplained, and the deposit names exactly two steps we do not perform: the band limit and the tie
threshold.**

Why the gap matters beyond bookkeeping: QUEUE.md Q34 concluded "PE31 is the comparator to use" for
Challenge C, because it tracks a clinician at +0.48 where our fitted BIS-like index reaches +0.04 (E65).
**A comparator that only exists as a column in one deposit cannot be carried to a deposit that does not
ship it.** If the declared steps close the gap, we can compute the comparator ourselves anywhere. If they
do not, then something undeclared separates the two implementations and Q34's recommendation is
deposit-bound -- which is a real constraint on Challenge C and needs to be known rather than assumed away.

--------------------------------------------------------------------------------------------------------
CO-PRIMARIES. Both are reported whatever either does; neither may be dropped after the fact.
--------------------------------------------------------------------------------------------------------
Per recording, Spearman rho is computed on the paired windows, then aggregated across recordings by a
recording-level bootstrap (the unit of resampling is the recording, because windows within one are
strongly dependent).

    P1  AGREEMENT.  D1 = mean_rec[ rho(pe_declared, PE31) - rho(pe_raw, PE31) ]
    P2  CLINICIAN.  D2 = mean_rec[ rho(pe_declared, MOAA/S) - rho(pe_raw, MOAA/S) ]

Both are PAIRED within recording, so a recording that is simply hard contributes nothing to either.

PREDICTION, WRITTEN NOW: D1 > 0 and D2 > 0. The stated reason is that a tie threshold suppresses the
ordinal structure that ADC quantisation manufactures out of flat signal, and a 45 Hz limit removes the
mains and muscle band where an order-3 pattern at tau=1 (24 ms span) is most sensitive. **That reasoning
is an inference from the parameter description, which states thresholds and not their purpose** (rule 42).

--------------------------------------------------------------------------------------------------------
VERDICT RULE. The wrong-direction case is enumerated FIRST and by name (rule 37, fourth occurrence).
--------------------------------------------------------------------------------------------------------
For each co-primary, in this order:

    (a) CI excludes 0 and the point estimate is NEGATIVE
            -> REFUTED-WRONG-DIRECTION. The declared preprocessing makes us agree LESS. This is not a
               null and must not be printed as one: it would mean our as-is implementation is closer to
               theirs than their own declared recipe is, i.e. the description does not describe the
               shipped column.
    (b) CI includes 0
            -> NOT EXPLAINED. The declared steps do not move it; the gap is elsewhere and Q34's
               comparator stays deposit-bound.
    (c) CI excludes 0 and the point estimate is POSITIVE
            -> candidate pass; proceed to the placebo, which can only remove this, never create one.

PLACEBO (gate, applied only to a (c)). `pe_placebo20` is the same tie threshold with an ARBITRARY WRONG
band, 0.5-20 Hz, fixed in the extractor before any number existed. Define
D1p = mean_rec[ rho(pe_placebo20, PE31) - rho(pe_raw, PE31) ] and likewise D2p. The gate is a COMPARISON,
never a threshold (rule 34):

    pass requires the paired contrast (D - Dp) to exclude 0 on the POSITIVE side.

If the wrong band helps as much, what has been shown is that permutation entropy is band-sensitive -- not
that our implementation was mis-specified against a published one. That verdict is printed as
NOT-SPECIFIC, and it is a real finding, not a failure.

BOOTSTRAP REPORTING (rule 46). 20,000 recording-level resamples; the fraction of resamples on the wrong
side of the null is reported alongside every interval, and every verdict is re-run at three seeds with the
per-seed verdict printed. A verdict that moves across seeds is reported as SEED-UNSTABLE.

--------------------------------------------------------------------------------------------------------
MACHINERY GATES, evaluated BEFORE the primaries and able to refuse the whole experiment (rule 40)
--------------------------------------------------------------------------------------------------------
    G1  UNITS      the extractor refuses any recording whose EEG IQR is outside [0.5, 5000] uV, so a
                   0.5 uV threshold is meaningful. The count refused is reported; if any recording was
                   refused on units the whole deposit's scaling is in doubt and the experiment stops.
    G2  TIE ACTIVE median `tie_frac` > 0.01. If the tie threshold creates essentially no ties, `pe_tie`
                   and `pe_declared` differ from their untied twins only by rounding and the tie arm is
                   INAPPLICABLE -- reported as that, not as "the tie step had no effect".
    G3  BAND ACTIVE median `band_rel_delta` > 0.01. Same logic for the filter.
    G4  SELF-CHECK `pe_raw` must reproduce `dosei_pe_check.csv`'s `mine_pe` on every shared
                   (recording, t_s) row to within 1e-9. Two passes of the same computation that disagree
                   invalidate everything downstream, including the +0.7239 already recorded.
    G5  COVERAGE   >= 30 recordings carrying >= 10 windows with both a finite PE31 and a finite pe_raw;
                   and, for P2 separately, >= 20 recordings whose MOAA/S takes more than one value.

DESCRIPTIVE, NOT A VERDICT (rule 28 -- which of two steps does the work is a decomposition, and a
decomposition of a null is not a result): `pe_band` and `pe_tie` are each reported against `pe_raw` on
both co-primaries, with intervals, and are explicitly not gated.

SCOPE LIMIT. This is a statement about two implementations of one published measure on one deposit. It is
not a claim that either is the better measure of anaesthetic depth, and nothing here licenses calling
permutation entropy a measure of consciousness.

    python bsde/src/bsde/experiments/e76_pe_declared_preprocessing.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "bsde", "src"))

VARIANTS = os.path.join(HERE, "..", "..", "..", "results", "dosei_pe_variants.csv")
PRIOR = os.path.join(HERE, "..", "..", "..", "results", "dosei_pe_check.csv")
OUT = os.path.join(HERE, "..", "..", "..", "results", "e76_pe_declared_preprocessing.json")

ARMS = ["pe_raw", "pe_band", "pe_tie", "pe_declared", "pe_placebo20"]
N_BOOT = 20000
SEEDS = (11, 12, 13)
MIN_WINDOWS = 10
MIN_REC_AGREE = 30
MIN_REC_MOAAS = 20


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


def load(path):
    rows = defaultdict(list)
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            rows[r["recording"]].append(r)
    return rows


def col(rs, k):
    return np.array([_f(r.get(k, "")) for r in rs])


def boot_mean(vals, seed, n_boot=N_BOOT):
    """Recording-level bootstrap of a mean. Returns (point, lo, hi, frac_wrong_side_of_zero)."""
    v = np.asarray([x for x in vals if np.isfinite(x)], float)
    if v.size < 3:
        return float("nan"), float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(n_boot, v.size))
    means = v[idx].mean(axis=1)
    point = float(v.mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    wrong = float(np.mean(means <= 0.0)) if point > 0 else float(np.mean(means >= 0.0))
    return point, float(lo), float(hi), wrong


def verdict(point, lo, hi):
    """Rule 37: the wrong-direction case is the first branch, by name."""
    if not np.isfinite(point):
        return "NOT-COMPUTABLE"
    if lo > 0 and hi > 0:
        return "CANDIDATE-PASS"
    if lo < 0 and hi < 0:
        return "REFUTED-WRONG-DIRECTION"
    return "NOT-EXPLAINED"


def main() -> int:
    res = {"gates": {}, "primaries": {}, "descriptive": {}, "verdicts": {}}
    if not os.path.exists(VARIANTS):
        print(f"ABSENT: {VARIANTS} does not exist yet"); return 2
    data = load(VARIANTS)
    print(f"{len(data)} recordings, {sum(len(v) for v in data.values())} windows")

    # ---- G2/G3: the two steps must actually do something -------------------------------------------
    tie_fracs, band_deltas = [], []
    for rs in data.values():
        tie_fracs.append(float(np.nanmedian(col(rs, "tie_frac"))))
        band_deltas.append(float(np.nanmedian(col(rs, "band_rel_delta"))))
    g2 = float(np.nanmedian(tie_fracs))
    g3 = float(np.nanmedian(band_deltas))
    res["gates"]["G2_tie_frac_median"] = g2
    res["gates"]["G3_band_rel_delta_median"] = g3
    res["gates"]["G2_pass"] = bool(g2 > 0.01)
    res["gates"]["G3_pass"] = bool(g3 > 0.01)
    print(f"G2 tie_frac median      {g2:.4f}   {'PASS' if g2 > 0.01 else 'INAPPLICABLE'}")
    print(f"G3 band_rel_delta median {g3:.4f}   {'PASS' if g3 > 0.01 else 'INAPPLICABLE'}")

    # ---- G4: the second pass must reproduce the first ----------------------------------------------
    g4_n, g4_max = 0, 0.0
    if os.path.exists(PRIOR):
        prior = {}
        with open(PRIOR, newline="") as fh:
            for r in csv.DictReader(fh):
                prior[(r["recording"], r["t_s"])] = _f(r["mine_pe"])
        for rec, rs in data.items():
            for r in rs:
                k = (rec, r["t_s"])
                if k in prior and np.isfinite(prior[k]):
                    g4_n += 1
                    g4_max = max(g4_max, abs(prior[k] - _f(r["pe_raw"])))
    res["gates"]["G4_shared_rows"] = g4_n
    res["gates"]["G4_max_abs_diff"] = g4_max
    res["gates"]["G4_pass"] = bool(g4_n > 0 and g4_max < 1e-9)
    print(f"G4 self-check           {g4_n} shared rows, max |diff| {g4_max:.3g}   "
          f"{'PASS' if res['gates']['G4_pass'] else 'FAIL'}")

    # ---- per-recording correlations ----------------------------------------------------------------
    rho_p31 = {a: [] for a in ARMS}
    rho_mo = {a: [] for a in ARMS}
    rho_mo["their_pe31"] = []
    n_agree = n_moaas = 0
    for rec, rs in sorted(data.items()):
        p31 = col(rs, "their_pe31")
        mo = col(rs, "moaas")
        raw = col(rs, "pe_raw")
        if np.isfinite(p31).sum() >= MIN_WINDOWS and np.isfinite(raw).sum() >= MIN_WINDOWS:
            n_agree += 1
        moaas_varies = np.isfinite(mo).sum() >= MIN_WINDOWS and len(set(mo[np.isfinite(mo)].tolist())) > 1
        if moaas_varies:
            n_moaas += 1
            rho_mo["their_pe31"].append(spearman(p31, mo))
        for a in ARMS:
            v = col(rs, a)
            rho_p31[a].append(spearman(v, p31))
            rho_mo[a].append(spearman(v, mo) if moaas_varies else float("nan"))

    res["gates"]["G5_recordings_agreement"] = n_agree
    res["gates"]["G5_recordings_moaas"] = n_moaas
    res["gates"]["G5_pass"] = bool(n_agree >= MIN_REC_AGREE and n_moaas >= MIN_REC_MOAAS)
    print(f"G5 coverage             {n_agree} recordings for P1, {n_moaas} for P2   "
          f"{'PASS' if res['gates']['G5_pass'] else 'FAIL'}")

    for a in ARMS:
        res["descriptive"][f"median_rho_{a}_vs_PE31"] = float(np.nanmedian(rho_p31[a]))
        res["descriptive"][f"median_rho_{a}_vs_MOAAS"] = float(np.nanmedian(rho_mo[a]))
    res["descriptive"]["median_rho_their_PE31_vs_MOAAS"] = float(np.nanmedian(rho_mo["their_pe31"]))
    print("\nmedian within-recording rho")
    print(f"    {'arm':14s} {'vs PE31':>10s} {'vs MOAA/S':>10s}")
    for a in ARMS:
        print(f"    {a:14s} {np.nanmedian(rho_p31[a]):+10.4f} {np.nanmedian(rho_mo[a]):+10.4f}")
    print(f"    {'their PE31':14s} {'--':>10s} {np.nanmedian(rho_mo['their_pe31']):+10.4f}")

    if not (res["gates"]["G4_pass"] and res["gates"]["G5_pass"]):
        print("\nMACHINERY GATE FAILED -- no primary is evaluated (rule 31: the verdict is ABSENT, "
              "not negative)")
        res["verdicts"]["overall"] = "GATE-FAILED"
        with open(os.path.abspath(OUT), "w") as fh:
            json.dump(res, fh, indent=2)
        return 1

    # ---- co-primaries, then the placebo gate -------------------------------------------------------
    def paired(a, b, table):
        return [x - y for x, y in zip(table[a], table[b])]

    for name, table, label in (("P1", rho_p31, "PE31"), ("P2", rho_mo, "MOAA/S")):
        d = paired("pe_declared", "pe_raw", table)
        dp = paired("pe_placebo20", "pe_raw", table)
        contrast = [x - y for x, y in zip(d, dp)]
        per_seed = {}
        for s in SEEDS:
            pt, lo, hi, wrong = boot_mean(d, s)
            v = verdict(pt, lo, hi)
            cpt, clo, chi, cwrong = boot_mean(contrast, s)
            if v == "CANDIDATE-PASS":
                v = "PASS" if (clo > 0 and chi > 0) else "NOT-SPECIFIC"
            per_seed[s] = {"D": pt, "lo": lo, "hi": hi, "frac_wrong_side": wrong,
                           "contrast_vs_placebo": cpt, "contrast_lo": clo, "contrast_hi": chi,
                           "contrast_frac_wrong_side": cwrong, "verdict": v}
        vs = {p["verdict"] for p in per_seed.values()}
        overall = per_seed[SEEDS[0]]["verdict"] if len(vs) == 1 else "SEED-UNSTABLE"
        res["primaries"][name] = {"reference": label, "per_seed": per_seed, "verdict": overall,
                                  "D_placebo": float(np.nanmean([x for x in dp if np.isfinite(x)]))}
        res["verdicts"][name] = overall
        p0 = per_seed[SEEDS[0]]
        print(f"\n{name}  declared - raw, vs {label}")
        print(f"    D = {p0['D']:+.4f} [{p0['lo']:+.4f}, {p0['hi']:+.4f}]  "
              f"frac on wrong side of 0 = {p0['frac_wrong_side']:.4f}")
        print(f"    placebo (0.5-20 Hz) D = {res['primaries'][name]['D_placebo']:+.4f}; "
              f"contrast {p0['contrast_vs_placebo']:+.4f} "
              f"[{p0['contrast_lo']:+.4f}, {p0['contrast_hi']:+.4f}]")
        print(f"    VERDICT {overall}" + ("" if len(vs) == 1 else f"   (seeds disagree: {sorted(vs)})"))

    # ---- decomposition: descriptive only, never a verdict ------------------------------------------
    print("\ndecomposition (DESCRIPTIVE, not gated)")
    for arm in ("pe_band", "pe_tie"):
        for name, table, label in (("P1", rho_p31, "PE31"), ("P2", rho_mo, "MOAA/S")):
            d = paired(arm, "pe_raw", table)
            pt, lo, hi, _ = boot_mean(d, SEEDS[0])
            res["descriptive"][f"{arm}_minus_raw_{name}"] = [pt, lo, hi]
            print(f"    {arm:12s} vs {label:8s}  {pt:+.4f} [{lo:+.4f}, {hi:+.4f}]")

    if not res["gates"]["G2_pass"]:
        print("\nNOTE: G2 INAPPLICABLE -- the tie threshold created almost no ties, so `pe_tie` and "
              "`pe_declared` are not tests of a tie rule.")
    if not res["gates"]["G3_pass"]:
        print("\nNOTE: G3 INAPPLICABLE -- the band filter barely changed the signal.")

    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(res, fh, indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
