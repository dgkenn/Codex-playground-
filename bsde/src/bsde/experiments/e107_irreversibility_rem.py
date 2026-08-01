"""E107 -- Does a PROVABLY non-spectral measure place REM differently from the arousal axis?

REGISTERED WHILE THE EXTRACTION IS STILL RUNNING and before any stage contrast has been computed. The
feature module was validated against analytic ground truths first, on synthetic processes only.

=========================================================================================================
THE CLAIM THIS ATTACKS
=========================================================================================================
This project's summary finding is that **everything it has measured is a single arousal axis**, and REM is
where that claim is testable, because REM is the state in which arousal and experience come apart. Three
independent routes have placed REM with SLEEP: E69's fraction-nearer-wake, E93/E95's axis position at
**0.629** of the way from wake to N3, and E100's per-channel low-frequency version at 0.440. **In two of
the three the placement was measured to be substantially muscle** -- E100's entire effect vanished after
residualising on submental EMG (d_z -0.257 -> -0.000), and submental EMG itself sits at REM position
+1.094, beyond the N3 end.

Every one of those measures is a summary of AMPLITUDE or of the POWER SPECTRUM.

=========================================================================================================
WHY THIS INSTRUMENT IS DIFFERENT, AND THE ARGUMENT IS A THEOREM
=========================================================================================================
By Wiener-Khinchin the PSD is the Fourier transform of the autocovariance, and the autocovariance is
**symmetric in lag**. Time reversal therefore leaves the autocovariance -- and hence the PSD, the aperiodic
exponent, every band power, spectral entropy, the alpha peak -- **exactly unchanged**. A statistic that
measures time asymmetry can only be reading structure that no spectral summary can see. This is not
rule 60's usual "check the correlation and hope"; it is an identity.

Two further properties matter for the specific failure modes that killed the earlier attempts:

  * `permutation_irreversibility` uses only the ORDERING of samples, so it is invariant to any monotone
    amplitude transform. **It cannot be muscle AMPLITUDE**, which is what E70 and E100 turned out to be
    measuring (and rule 57 -- an amplitude in arbitrary units is not a magnitude -- cannot bite it).
  * A PHASE-RANDOMISED SURROGATE has the identical power spectrum and is Gaussian-linear, hence
    time-reversible. Every measure is extracted twice, real and surrogate, and **the primary quantity is
    real MINUS surrogate**, which by construction contains no spectral information at all. Same discipline
    as E104's sham arm: the control is cut from the same window.

Validated before extraction on analytic ground truths: reversible processes returned ~0.0001, a sawtooth
0.116, skewed-innovation AR(1) 0.085; surrogates of the irreversible cases collapsed to ~0.0006 while
preserving the aperiodic exponent to 0.5 % (+2.013 vs +2.023).

=========================================================================================================
PRIMARY -- the same statistic E93/E95/E100 used, so the numbers are comparable
=========================================================================================================
Per subject, on that subject's OWN wake-to-N3 axis:

    position(m) = ( m_REM - m_W ) / ( m_N3 - m_W )       0 = REM sits with wake, 1 = REM sits with N3

    P1  paired d_z of  position(irreversibility) - position(whole_head_exponent).
        PREDICTED NEGATIVE: REM closer to wake on an axis that is not the spectrum.

    The irreversibility measure is `frontal_irr3 - frontal_irr3_surr`, declared here. `irr4` and the
    posterior site are SECONDARY and reported always, never substituted for the primary (rule 59).

VERDICT, wrong direction FIRST (rule 37):

    (a) interval excludes 0 and POSITIVE -> WORSE THAN THE EXPONENT. Irreversibility places REM even
        further from wake. The single-axis reading survives its sharpest test and is strengthened.
    (b) interval includes 0 -> NO DIFFERENCE. A provably non-spectral measure orders REM exactly as the
        spectral one does. **This is the strongest possible form of the single-axis result**, because the
        usual escape -- "the measures were all the same family" -- is mathematically unavailable here.
    (c) interval excludes 0 and NEGATIVE -> REM MOVES TOWARD WAKE, and then G5 decides whether it is a
        finding or muscle again.

PREDICTED: (b) at ~50 %, (c) at ~35 %, (a) at ~15 %.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 50 subjects with all five stages in both the irreversibility and the spectra tables.
    G2  NON-DEGENERATE DENOMINATOR, and it is written properly this time. E100 found its frontal position
        statistic unstable (IQR [-1.355, +0.293]) because a ratio blows up when the W-to-N3 span is small,
        and its gate "only excluded exact zeros". Here a subject contributes a measure only if
        **|m_N3 - m_W| >= 0.25 x the between-subject SD of that measure**, a threshold fixed before the
        run and applied identically to every measure including the incumbent, so it cannot favour one.
        Subjects dropped are counted and reported.
    G3  THE AXIS MUST EXIST. Irreversibility must actually change from W to N3, in a consistent direction
        across subjects, against a Gaussian control on the same subjects (rule 63). **If it does not, there
        is no axis to place REM on and the verdict is ABSENT, not a null** (rule 31).
    G4  THE SURROGATE MUST WORK. Median surrogate irreversibility must be far below the median real value.
        If the surrogate is not near zero the measure is not measuring irreversibility and nothing below
        it means anything.
    G5  MUSCLE, and this is the gate that killed E100. Submental EMG's own axis position is reported, and
        P1 is recomputed after residualising every measure on EMG within subject. **A P1 that survives only
        before adjustment is muscle and the verdict says so.** The permutation form cannot be muscle
        amplitude by construction, but it can still be muscle WAVEFORM SHAPE, and that is an empirical
        question this gate answers rather than an argument.

PLACEBO: stage labels permuted within subject, 500 draws, position statistics recomputed. Primary read
FIRST (rule 48).

EXCLUSIONS: SC4001E0, the smoke-test burn from earlier sleep work (rule 26), carried over unchanged.

SCOPE. Sleep-EDFx, two bipolar derivations, no dream reports. A REM placement nearer wake would be a fact
about this measure on this deposit and NOT evidence of experience: distinguishing dreaming from
non-dreaming REM requires serial awakenings and reports (Siclari et al., PMID 28394322), which no deposit
this project can reach has. Nothing here detects or measures consciousness.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e107_irreversibility_rem.json")
IRR = os.path.join(RESULTS, "sleep_edfx_irreversibility.csv")
SPEC = os.path.join(RESULTS, "sleep_edfx_channel_spectra.csv")
FIVE = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")
EMG = os.path.join(RESULTS, "sleep_edfx_emg.csv")

STAGES = ("W", "N1", "N2", "N3", "REM")
BURNED = {"SC4001E0"}
PRIMARY = "frontal_irr3_net"
INCUMBENT = "whole_head_exponent"
SECONDARY = ["frontal_irr4_net", "posterior_irr3_net", "posterior_irr4_net", "frontal_incr_net"]
DENOM_MIN_SD = 0.25
MIN_SUBJECTS = 50
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def dz(d):
    d = np.asarray([x for x in d if np.isfinite(x)], float)
    if d.size < 3 or d.std(ddof=1) <= 0:
        return float("nan")
    return float(d.mean() / d.std(ddof=1))


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def load():
    per = defaultdict(dict)
    if not os.path.exists(IRR):
        return None
    for r in csv.DictReader(open(IRR, newline="")):
        s, st = r.get("subject", ""), r.get("label", "")
        if s in BURNED or st not in STAGES:
            continue
        d = per[s].setdefault(st, {})
        for site in ("frontal", "posterior"):
            for m in ("irr3", "irr4", "incr"):
                real, surr = _f(r.get(f"{site}_{m}", "")), _f(r.get(f"{site}_{m}_surr", ""))
                d[f"{site}_{m}_net"] = real - surr
                d[f"{site}_{m}_raw"] = real
                d[f"{site}_{m}_surr"] = surr
    if os.path.exists(FIVE):
        for r in csv.DictReader(open(FIVE, newline="")):
            rid = r.get("recording_id", "")
            if "@" not in rid:
                continue
            s, st = r.get("subject", ""), rid.rsplit("@", 1)[1]
            if s in per and st in per[s]:
                per[s][st][INCUMBENT] = _f(r.get(INCUMBENT, ""))
    if os.path.exists(EMG):
        for r in csv.DictReader(open(EMG, newline="")):
            s, st = r.get("subject", ""), r.get("label", "")
            if s in per and st in per[s]:
                per[s][st]["emg"] = _f(r.get("emg_mean", ""))
    return per


def positions(per, measure, resid_on=None):
    """position(REM) on each subject's own W-to-N3 axis, with G2's denominator rule applied."""
    vals = {}
    for s, st in per.items():
        v = {k: st.get(k, {}).get(measure, float("nan")) for k in ("W", "N3", "REM")}
        if resid_on is not None:
            e = {k: st.get(k, {}).get("emg", float("nan")) for k in ("W", "N3", "REM")}
            if not all(np.isfinite(list(v.values()) + list(e.values()))):
                continue
            xs = np.array([e["W"], e["N3"], e["REM"]], float)
            ys = np.array([v["W"], v["N3"], v["REM"]], float)
            if np.ptp(xs) > 0:
                b, a = np.polyfit(xs, ys, 1)
                ys = ys - (a + b * xs)
            v = {"W": ys[0], "N3": ys[1], "REM": ys[2]}
        if all(np.isfinite(list(v.values()))):
            vals[s] = v
    if not vals:
        return {}, 0
    spread = float(np.std([x["N3"] - x["W"] for x in vals.values()]))
    out, dropped = {}, 0
    for s, v in vals.items():
        den = v["N3"] - v["W"]
        if spread <= 0 or abs(den) < DENOM_MIN_SD * spread:
            dropped += 1
            continue
        out[s] = (v["REM"] - v["W"]) / den
    return out, dropped


def main() -> int:
    per = load()
    if per is None:
        print(f"ABSENT: {IRR} -- extraction has not landed")
        return 2
    per = {s: st for s, st in per.items()
           if all(k in st for k in STAGES) and INCUMBENT in st.get("W", {})}
    res = {"n_subjects_all_stages": len(per), "gates": {}}
    print(f"{len(per)} subjects with all five stages in both tables")
    res["gates"]["G1_pass"] = bool(len(per) >= MIN_SUBJECTS)
    print(f"G1 coverage   {len(per)} >= {MIN_SUBJECTS}  "
          f"{'PASS' if res['gates']['G1_pass'] else 'FAIL'}")
    if not res["gates"]["G1_pass"]:
        res["verdict"] = "GATE-FAILED -- extraction incomplete or coverage too low"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)

    # G4 surrogate validity
    real_med = float(np.nanmedian([st[k]["frontal_irr3_raw"] for st in per.values() for k in STAGES]))
    surr_med = float(np.nanmedian([st[k]["frontal_irr3_surr"] for st in per.values() for k in STAGES]))
    g4 = bool(np.isfinite(real_med) and np.isfinite(surr_med) and surr_med < 0.5 * real_med)
    res["gates"].update({"G4_real_median": real_med, "G4_surrogate_median": surr_med, "G4_pass": g4})
    print(f"G4 surrogate  median real irr3 {real_med:.5f}  vs surrogate {surr_med:.5f}  "
          f"{'PASS' if g4 else 'FAIL'}")

    # G3 the axis must exist
    span = np.array([st["N3"]["frontal_irr3_net"] - st["W"]["frontal_irr3_net"]
                     for st in per.values()], float)
    span = span[np.isfinite(span)]
    ax_dz = dz(span)
    noise95 = float(np.quantile(np.abs([dz(rng.normal(size=span.size)) for _ in range(2000)]), .95))
    g3 = bool(np.isfinite(ax_dz) and abs(ax_dz) > noise95)
    res["gates"].update({"G3_W_to_N3_dz": ax_dz, "G3_noise95": noise95, "G3_pass": g3})
    print(f"G3 axis       irr3 W->N3 change d_z {ax_dz:+.4f} vs Gaussian 95th {noise95:.4f}  "
          f"{'PASS' if g3 else 'FAIL'}")
    if not (g3 and g4):
        res["verdict"] = ("ABSENT -- irreversibility does not change from wake to N3 (no axis to place REM "
                          "on), and/or the surrogate is not behaving, so nothing was tested (rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    pos_p, drop_p = positions(per, PRIMARY)
    pos_i, drop_i = positions(per, INCUMBENT)
    res["gates"]["G2_dropped"] = {"primary": drop_p, "incumbent": drop_i}
    shared = sorted(set(pos_p) & set(pos_i))
    print(f"G2 denominator dropped {drop_p} (primary) and {drop_i} (incumbent) subjects; "
          f"{len(shared)} contribute to P1")
    print(f"\nMEDIAN POSITIONS   {PRIMARY} {np.median([pos_p[s] for s in shared]):+.4f}   "
          f"{INCUMBENT} {np.median([pos_i[s] for s in shared]):+.4f}   "
          f"(0 = REM with wake, 1 = REM with N3)")

    d = np.array([pos_p[s] - pos_i[s] for s in shared], float)
    point = dz(d)
    lo, hi = ci([dz(d[rng.integers(0, d.size, d.size)]) for _ in range(REPS)])
    res["primary"] = {"d_z": point, "lo": lo, "hi": hi, "n": int(d.size),
                      "median_pos_primary": float(np.median([pos_p[s] for s in shared])),
                      "median_pos_incumbent": float(np.median([pos_i[s] for s in shared]))}
    print(f"P1 position({PRIMARY}) - position({INCUMBENT})  d_z {point:+.4f} [{lo:+.4f}, {hi:+.4f}]  "
          f"over {d.size} subjects")

    # secondaries, always reported (rule 59)
    print("\nSECONDARY (reported, never substituted for the primary)")
    res["secondary"] = {}
    for m in SECONDARY:
        pm, dm = positions(per, m)
        sh = sorted(set(pm) & set(pos_i))
        if len(sh) < 10:
            print(f"   {m:<26s} too few subjects ({len(sh)})")
            continue
        dd = np.array([pm[s] - pos_i[s] for s in sh], float)
        l2, h2 = ci([dz(dd[rng.integers(0, dd.size, dd.size)]) for _ in range(REPS)])
        res["secondary"][m] = {"d_z": dz(dd), "lo": l2, "hi": h2, "n": len(sh),
                               "median_pos": float(np.median([pm[s] for s in sh]))}
        print(f"   {m:<26s} median pos {np.median([pm[s] for s in sh]):+.4f}   "
              f"d_z {dz(dd):+.4f} [{l2:+.4f}, {h2:+.4f}]  n={len(sh)}")

    # G5 MUSCLE
    emg_pos, _ = positions(per, "emg")
    pos_pr, _ = positions(per, PRIMARY, resid_on="emg")
    pos_ir, _ = positions(per, INCUMBENT, resid_on="emg")
    sh = sorted(set(pos_pr) & set(pos_ir))
    g5_dz = g5_lo = g5_hi = float("nan")
    if len(sh) >= 10:
        dd = np.array([pos_pr[s] - pos_ir[s] for s in sh], float)
        g5_dz = dz(dd)
        g5_lo, g5_hi = ci([dz(dd[rng.integers(0, dd.size, dd.size)]) for _ in range(REPS)])
    res["gates"]["G5"] = {"emg_median_position": float(np.median(list(emg_pos.values())))
                          if emg_pos else float("nan"),
                          "d_z_after_emg": g5_dz, "lo": g5_lo, "hi": g5_hi, "n": len(sh)}
    print(f"\nG5 muscle     submental EMG's own REM position "
          f"{np.median(list(emg_pos.values())) if emg_pos else float('nan'):+.4f}")
    print(f"              P1 after residualising on EMG: d_z {g5_dz:+.4f} [{g5_lo:+.4f}, {g5_hi:+.4f}] "
          f"over {len(sh)} subjects")

    pl = []
    for _ in range(PLACEBO_DRAWS):
        shuffled = {}
        for s, st in per.items():
            ks = list(STAGES)
            perm = rng.permutation(len(ks))
            shuffled[s] = {ks[i]: st[ks[perm[i]]] for i in range(len(ks))}
        pp, _ = positions(shuffled, PRIMARY)
        pi, _ = positions(shuffled, INCUMBENT)
        sh2 = sorted(set(pp) & set(pi))
        if len(sh2) >= 10:
            v = dz(np.array([pp[s] - pi[s] for s in sh2], float))
            if np.isfinite(v):
                pl.append(v)
    p_lo, p_hi = ci(pl)
    inside = bool(np.isfinite(p_lo) and p_lo <= point <= p_hi)
    res["placebo"] = {"lo": p_lo, "hi": p_hi, "inside": inside, "n_draws": len(pl)}
    print(f"PLACEBO stage labels permuted within subject: [{p_lo:+.4f}, {p_hi:+.4f}]  "
          f"real {'INSIDE' if inside else 'outside'}")

    excl = not (lo <= 0.0 <= hi)
    surv = bool(np.isfinite(g5_lo) and not (g5_lo <= 0.0 <= g5_hi) and (g5_dz * point) > 0)
    if not excl:
        v = ("NO DIFFERENCE -- a PROVABLY non-spectral measure orders REM exactly as the aperiodic "
             "exponent does. This is the strongest form of the single-axis result available to this "
             "project, because the usual escape ('they were all the same family') is mathematically "
             "unavailable: time reversal leaves every spectral summary unchanged. The placebo is not "
             "informative here (rule 48).")
    elif inside:
        v = "WITHDRAWN BY PLACEBO -- permuting stage labels reproduces the difference."
    elif point > 0:
        v = ("WORSE THAN THE EXPONENT -- irreversibility places REM even further from wake than the "
             "spectral measure does. The single-axis reading survives its sharpest test and is "
             "strengthened.")
    elif not surv:
        v = ("MUSCLE -- REM moves toward wake on the irreversibility axis, but the effect does not survive "
             "residualisation on submental EMG. Same fate as E100, by a different route: the permutation "
             "form cannot be muscle AMPLITUDE, so what it is reading is muscle WAVEFORM SHAPE.")
    else:
        v = ("REM MOVES TOWARD WAKE, AND IT IS NOT MUSCLE -- a measure that is provably orthogonal to the "
             "power spectrum, invariant to monotone amplitude transforms, and net of a phase-randomised "
             "surrogate, places REM nearer wake than the aperiodic exponent does, and survives EMG "
             "adjustment. FIRST evidence in this project of a second axis. Scope travels with it: no dream "
             "reports exist in this deposit, so this is NOT evidence of experience (Siclari's design is "
             "what would be needed) and nothing here detects consciousness.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
