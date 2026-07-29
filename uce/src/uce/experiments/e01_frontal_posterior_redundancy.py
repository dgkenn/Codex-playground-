#!/usr/bin/env python3
"""E01 — Is UCE v1's frontal/posterior split informative? A LABEL-FREE test on real EEG.

WHY THIS IS THE FIRST EXPERIMENT. `docs/RESEARCH_STRATEGY.md` §0 argues, by algebra alone, that UCE v1 is
approximately a one-feature model: for two standardized variables PC1 loadings are always (1/sqrt2, 1/sqrt2)
regardless of their correlation, and "96.8 % of variance explained" is an exact restatement of
r(frontal, posterior) = 0.936. That argument makes an empirical prediction which can be tested WITHOUT ANY
DIAGNOSTIC LABEL:

    P1  r(frontal exponent, posterior exponent) is high in real resting EEG.
    P2  UCE v1 is therefore near-perfectly correlated with z(mean exponent across all channels),
        i.e. the two-region structure adds essentially nothing.

This matters because the dataset used here (Figshare 10.6084/m9.figshare.23552964) ships **no diagnostic
labels at all** — verified 2026-07-29: only .dat/.vhdr/.vmrk, markers are EEGLAB epoch boundaries, and there
is no participants file. It therefore cannot support the UWS-vs-MCS analysis it was registered for. It CAN
answer P1 and P2, because those are properties of the measure, not of the groups.

REGISTERED BEFORE RUNNING (predictions stated so they can fail):
    P1  r >= 0.80.  If r is LOW (< 0.5), strategy §0 is WRONG for this population, the two regions carry
        genuinely different information, and UCE v1's structure is justified after all.
    P2  |corr(UCE v1, z(mean exponent))| >= 0.98.
    P3  SANITY: median exponent should be physiological (roughly 0.5-3.5) and median fit R^2 high. If not,
        the pipeline is misreading the data and P1/P2 are uninterpretable (rule 31 in the sibling project).

WHAT THIS CANNOT SHOW. Nothing about consciousness, diagnosis, or prognosis. No labels exist. It is a
measurement-property experiment only, and is reported as such.
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from uce.features.aperiodic import welch_psd, fit_aperiodic          # noqa: E402
from uce.models.uce_v1 import regional_exponents, uce_v1_with_baseline  # noqa: E402

DATA = os.environ.get("FIGSHARE_DOC", "/tmp/uce_data/figshare_doc")
FIT_LO, FIT_HI = 1.0, 40.0
MODE = os.environ.get("UCE_FIT_MODE", "loglog_robust")


def read_brainvision(vhdr: str):
    import mne
    raw = mne.io.read_raw_brainvision(vhdr, preload=True, verbose="ERROR")
    return raw.get_data(), raw.ch_names, float(raw.info["sfreq"])


def main() -> int:
    vhdrs = sorted(glob.glob(os.path.join(DATA, "*.vhdr")))
    if not vhdrs:
        print(f"no .vhdr under {DATA}"); return 1
    print(f"E01 — frontal/posterior redundancy of the aperiodic exponent")
    print(f"   dataset: Figshare 10.6084/m9.figshare.23552964 (CC BY 4.0), {len(vhdrs)} subjects")
    print(f"   fit {FIT_LO}-{FIT_HI} Hz, mode={MODE}\n")

    rows = []
    for i, v in enumerate(vhdrs, 1):
        sid = os.path.basename(v)[:-5]
        try:
            data, chs, sf = read_brainvision(v)
            # Data are epoched 2 s segments concatenated; a 4 s Welch window would straddle epoch
            # boundaries. Use a 2 s window so each segment is analysed within its own epoch.
            exps = []
            for ch in data:
                try:
                    f, p = welch_psd(ch, sf, window_s=2.0, overlap=0.5)
                    exps.append(fit_aperiodic(f, p, FIT_LO, FIT_HI, MODE)["exponent"])
                except Exception:
                    exps.append(float("nan"))
            reg = regional_exponents(exps, chs)
            r2s = []
            for ch in data[:8]:
                try:
                    f, p = welch_psd(ch, sf, window_s=2.0, overlap=0.5)
                    r2s.append(fit_aperiodic(f, p, FIT_LO, FIT_HI, MODE)["r2"])
                except Exception:
                    pass
            rows.append(dict(subject=sid, n_ch=len(chs), sfreq=sf, **reg,
                             median_r2=float(np.nanmedian(r2s)) if r2s else float("nan")))
        except Exception as e:
            print(f"   [{i}] {sid}: FAILED {type(e).__name__}: {e}")
        if i % 20 == 0:
            print(f"   [{i}/{len(vhdrs)}]", flush=True)

    fr = np.array([r["frontal"] for r in rows], float)
    po = np.array([r["posterior"] for r in rows], float)
    wh = np.array([r["whole_head"] for r in rows], float)
    ok = np.isfinite(fr) & np.isfinite(po) & np.isfinite(wh)
    n = int(ok.sum())
    print(f"\n   usable subjects: {n}/{len(rows)}   channels {rows[0]['n_ch']}  sfreq {rows[0]['sfreq']:.0f} Hz")
    print(f"   frontal channels used: {rows[0]['n_frontal']}   posterior: {rows[0]['n_posterior']}")

    # ---- P3 sanity gate ---------------------------------------------------------------------------
    med_r2 = float(np.nanmedian([r["median_r2"] for r in rows]))
    med_exp = float(np.nanmedian(wh[ok]))
    print("\n" + "=" * 96)
    print("P3  SANITY GATE — is the pipeline reading real EEG sensibly?")
    print("=" * 96)
    print(f"   median whole-head exponent : {med_exp:.3f}   (physiological range roughly 0.5-3.5)")
    print(f"   median fit R^2             : {med_r2:.3f}")
    sane = (0.3 < med_exp < 4.0) and (med_r2 > 0.80) and n >= 30
    print(f"   GATE: {'PASS' if sane else 'FAIL'}")
    if not sane:
        print("\n   *** Pipeline sanity failed — P1/P2 are NOT interpretable.")
        return 1

    # ---- P1 / P2 ----------------------------------------------------------------------------------
    out = uce_v1_with_baseline(fr[ok], po[ok], wh[ok])
    r = out["r_frontal_posterior"]
    ve = out["implied_pc1_variance_explained"]
    r_uce_base = float(np.corrcoef(out["uce_v1"], out["baseline_whole_head_z"])[0, 1])

    print("\n" + "=" * 96)
    print("P1 / P2  IS THE FRONTAL/POSTERIOR SPLIT INFORMATIVE?")
    print("=" * 96)
    print(f"   r(frontal exponent, posterior exponent)          : {r:+.4f}")
    print(f"   implied PC1 variance explained = (1+r)/2         : {100*ve:.1f} %")
    print(f"      (investigator-reported derivation value       : 96.8 %)")
    print(f"   corr(UCE v1, z(mean exponent across channels))   : {r_uce_base:+.4f}")
    print(f"   frontal mean {np.nanmean(fr[ok]):.3f} +/- {np.nanstd(fr[ok]):.3f}   "
          f"posterior mean {np.nanmean(po[ok]):.3f} +/- {np.nanstd(po[ok]):.3f}")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    p1 = r >= 0.80
    p2 = abs(r_uce_base) >= 0.98
    if p1 and p2:
        print("   STRATEGY §0 CONFIRMED ON REAL EEG. The two regions are near-redundant, so the")
        print("   frontal/posterior weighting carries essentially no information and UCE v1 is, in")
        print(f"   practice, a whole-head aperiodic exponent (r with the one-feature baseline = {r_uce_base:.4f}).")
        print("   The published weights and the '96.8 % variance explained' figure must not be presented")
        print("   as evidence for a two-dimensional construct.")
    elif not p1:
        print(f"   STRATEGY §0 IS WRONG FOR THIS POPULATION: r = {r:+.4f} is below the 0.80 threshold, so")
        print("   frontal and posterior exponents carry genuinely different information here and the")
        print("   two-region structure is justified. §0 must be revised.")
    else:
        print(f"   MIXED: r = {r:+.4f} but UCE v1 vs baseline r = {r_uce_base:+.4f}. Report both.")

    print("\n   SCOPE: this dataset ships NO diagnostic labels (verified) — nothing here speaks to")
    print("   consciousness, diagnosis or prognosis. It is a property of the measure only.")

    os.makedirs(os.path.join(HERE, "..", "..", "..", "results"), exist_ok=True)
    res = {"experiment": "E01", "n_subjects_usable": n,
           "r_frontal_posterior": r, "implied_pc1_ve": ve,
           "corr_uce_v1_vs_whole_head_baseline": r_uce_base,
           "median_whole_head_exponent": med_exp, "median_fit_r2": med_r2,
           "fit_range_hz": [FIT_LO, FIT_HI], "fit_mode": MODE,
           "dataset_doi": "10.6084/m9.figshare.23552964", "labels_available": False}
    p = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "e01_redundancy.json"))
    json.dump(res, open(p, "w"), indent=2)
    print(f"\n   machine-readable result -> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
