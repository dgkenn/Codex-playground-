#!/usr/bin/env python3
"""E09 — preprocessing sensitivity, and the analytic degrees of freedom this project has been hiding.

TWO THINGS AT ONCE, AND THE SECOND IS THE UNCOMFORTABLE ONE.

1. **Is the aperiodic exponent's failure real or a fitting artefact?** E05 found it orders measured plasma
   propofol in only 45 % of subjects — below chance — while complexity measures reached 80-90 %. §9.9 recorded
   an untested alternative explanation: the Chennu deposit is filtered **0.5-45 Hz**, this project fits
   **1-40 Hz**, and 40 Hz sits inside that filter's roll-off, where a slope estimate can be distorted in a
   dose-independent way. That has been flagged as the highest-priority unbuilt check twice and never run.

2. **`analytic_dof = 1` has been a false claim in every SEARCH_LOG entry this project has written.** Brief 03's
   anti-p-hacking constraint 6 requires reporting the size of the search space, and `effective_search_space`
   is defined as candidates x analytic degrees of freedom. Every entry so far declares `analytic_dof: 1` —
   asserting that no analytic choice was explored. But 1-40 Hz, `loglog_robust`, and a 4-second Welch window
   were **choices**, made once, never varied, and never counted. Declaring 1 is not a lie about what was run;
   it is a lie about what *could have been* run and would have been reported had it looked better. This
   experiment measures the real number by varying them deliberately.

`preprocessing_sensitivity` is one of the ten required report items (Brief 03 item 5) and **nothing in this
project computes it**. This is that check.

THE SWEEP. The exponent is recomputed under every combination of:
    fit_lo    in {1, 2, 3} Hz
    fit_hi    in {20, 30, 40, 45} Hz
    mode      in {loglog_ols, loglog_robust}
    window_s  in {2, 4, 8} seconds
= 72 analysis variants, all of which are defensible and any of which could have been the project's default.

SCORING. For each variant, the **signed** directional AUC for baseline (level 1) vs moderate (level 3),
scored against the exponent's declared direction (`higher` when unconscious), plus the fraction of subjects in
whom it rises monotonically with plasma. Signed, per the standing rule from §9.12 — an unsigned statistic is
what let a wrong-direction candidate be reported as best-in-class for three experiments.

REGISTERED BEFORE RUNNING:
    P1  The SIGN of the exponent's dose association is NOT stable across the 72 variants: at least 10 % of
        variants land on each side of 0.5. If so, no single exponent number should ever have been quoted
        without its sensitivity band, including the 0.947 reported for ds005620 and the 45 % reported here.
    P2  Variants whose upper edge reaches 45 Hz differ systematically from those stopping at 30 Hz — the
        filter-roll-off explanation from §9.9, stated as a directional comparison rather than a vague
        "sensitivity".
    P3  The spread across variants is LARGE relative to the effect: the interquartile range of the signed AUC
        exceeds 0.10. A measure whose apparent performance moves by more than that under choices nobody
        pre-registered is not yet a measurement.
    P4  CONTROL, and it gates the interpretation of P1-P3. `relative_delta_power` — computed from a band
        integral rather than a slope fit — must be SUBSTANTIALLY LESS variant-sensitive than the exponent.
        If everything is equally unstable, the instability is in the cohort or the outcome, not in the
        exponent's estimator, and P1-P3 say nothing specific about the aperiodic fit.

    FALSIFICATION: if the exponent's signed AUC is stable across all 72 variants, the §9.9 preprocessing
    explanation is dead, the 45 % failure is a real property of the marker on this data, and that is a
    cleaner and more interesting negative than the one I expect.

WHAT THIS CANNOT DO. It cannot vary the reference scheme: the deposit arrives average-referenced and the
original recording reference is not recoverable, so re-referencing is outside what any analysis here can
reach. Reference choice is known to change the exponent, so the true analytic dof is LARGER than 72 — this
is a lower bound, and it is reported as one.
"""
from __future__ import annotations

import csv
import itertools
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.features.aperiodic import welch_psd, fit_aperiodic                        # noqa: E402
from bsde.features.spectral import relative_band_power                               # noqa: E402
from bsde.verifier.stats import directional_auc, spearman                            # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
LONG = os.path.join(RESULTS, "e09_preproc_long.csv")
FIT_LO = (1.0, 2.0, 3.0)
FIT_HI = (20.0, 30.0, 40.0, 45.0)
MODES = ("loglog_ols", "loglog_robust")
WINDOWS = (2.0, 4.0, 8.0)
PLASMA_ORDER = {1: 0.0, 2: 1.0, 3: 2.0}
N_CH = 8          # same declared channel budget as the other expensive sweeps, justified by E06


def variants():
    return list(itertools.product(FIT_LO, FIT_HI, MODES, WINDOWS))


def extract(limit=None, log=print):
    from bsde.ingestion.chennu import ChennuRemoteZipAdapter
    adapter = ChennuRemoteZipAdapter(n_epochs=4)
    refs = adapter.list_recordings()
    if limit:
        refs = refs[:limit]
    done = set()
    if os.path.exists(LONG):
        with open(LONG, newline="") as fh:
            done = {r["recording_id"] for r in csv.DictReader(fh)}
        log(f"   resuming: {len(done)} recordings already swept")
    fields = ["recording_id", "subject", "sedation_level", "variant", "fit_lo", "fit_hi",
              "mode", "window_s", "exponent", "rel_delta"]
    new = not os.path.exists(LONG) or os.path.getsize(LONG) == 0
    V = variants()
    with open(LONG, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        for i, ref in enumerate(refs, 1):
            if ref.recording_id in done:
                continue
            try:
                data, ch, sf, meta = ref.load()
            except Exception as e:
                log(f"   [{i}] {ref.recording_id}: FAILED {type(e).__name__}: {e}")
                continue
            d = np.asarray(data, float)[:N_CH]
            psd_cache = {}
            for wsec in WINDOWS:
                acc, freqs = None, None
                per_ch = []
                for c in d:
                    try:
                        f, p = welch_psd(c, sf, window_s=wsec, overlap=0.5)
                        per_ch.append((f, p))
                        acc = p if acc is None else acc + p
                        freqs = f
                    except Exception:
                        pass
                psd_cache[wsec] = (per_ch, freqs, (acc / len(per_ch)) if per_ch else None)
            rows = []
            for (lo, hi, mode, wsec) in V:
                per_ch, freqs, mean_psd = psd_cache[wsec]
                exps = []
                for f, p in per_ch:
                    try:
                        exps.append(fit_aperiodic(f, p, lo, hi, mode)["exponent"])
                    except Exception:
                        pass
                exps = [e for e in exps if np.isfinite(e)]
                rd = (relative_band_power(freqs, mean_psd, 1.0, 4.0, lo, hi)
                      if mean_psd is not None else float("nan"))
                rows.append({"recording_id": ref.recording_id, "subject": ref.subject,
                             "sedation_level": meta.get("sedation_level"),
                             "variant": f"{lo:g}-{hi:g}_{mode}_{wsec:g}s",
                             "fit_lo": lo, "fit_hi": hi, "mode": mode, "window_s": wsec,
                             "exponent": f"{np.mean(exps):.10g}" if exps else "",
                             "rel_delta": f"{rd:.10g}" if np.isfinite(rd) else ""})
            w.writerows(rows)
            fh.flush(); os.fsync(fh.fileno())
            log(f"   [{i}/{len(refs)}] {ref.recording_id[:34]:34s} {len(V)} variants")
    return LONG


def score(colname):
    """Signed AUC (baseline vs moderate) and plasma monotonicity, per variant."""
    by = defaultdict(dict)
    for r in csv.DictReader(open(LONG, newline="")):
        if r[colname] == "":
            continue
        try:
            lvl = int(float(r["sedation_level"]))
        except (TypeError, ValueError):
            continue
        by[r["variant"]][(r["subject"], lvl)] = float(r[colname])
    out = {}
    for v, d in by.items():
        subs = sorted({s for s, _ in d})
        pair = [(d[(s, 1)], d[(s, 3)]) for s in subs if (s, 1) in d and (s, 3) in d]
        if len(pair) < 10:
            continue
        y = np.r_[np.zeros(len(pair)), np.ones(len(pair))]
        x = np.r_[[a for a, _ in pair], [b for _, b in pair]]
        auc = directional_auc(y, x, "higher")
        mono = [spearman([d[(s, i)] for i in (1, 2, 3)], [PLASMA_ORDER[i] for i in (1, 2, 3)])
                for s in subs if all((s, i) in d for i in (1, 2, 3))]
        mono = [m for m in mono if np.isfinite(m)]
        out[v] = {"auc": auc, "mono": float(np.mean([m > 0 for m in mono])) if mono else float("nan"),
                  "n_pairs": len(pair)}
    return out


def main() -> int:
    limit = int(os.environ.get("E09_LIMIT", "0")) or None
    print("E09 — preprocessing sensitivity of the aperiodic exponent")
    print(f"   {len(variants())} analysis variants: fit_lo {FIT_LO}, fit_hi {FIT_HI}, "
          f"modes {MODES}, windows {WINDOWS}")
    extract(limit=limit)
    exp_s, del_s = score("exponent"), score("rel_delta")
    if not exp_s:
        print("   no variants scored"); return 1

    a = np.array([v["auc"] for v in exp_s.values() if np.isfinite(v["auc"])])
    m = np.array([v["mono"] for v in exp_s.values() if np.isfinite(v["mono"])])
    ad = np.array([v["auc"] for v in del_s.values() if np.isfinite(v["auc"])])
    q1, q3 = np.percentile(a, [25, 75])
    dq1, dq3 = (np.percentile(ad, [25, 75]) if ad.size else (np.nan, np.nan))
    print("\n" + "=" * 100)
    print(f"EXPONENT signed AUC (baseline vs moderate, declared direction 'higher') over {a.size} variants")
    print("=" * 100)
    print(f"   median {np.median(a):.3f}   IQR [{q1:.3f}, {q3:.3f}]   full range [{a.min():.3f}, {a.max():.3f}]")
    print(f"   variants ABOVE 0.5 (supports declaration): {int((a > 0.5).sum())}/{a.size}")
    print(f"   variants BELOW 0.5 (opposite):             {int((a < 0.5).sum())}/{a.size}")
    print(f"   plasma monotonicity: median {np.median(m):.3f}  range [{m.min():.3f}, {m.max():.3f}]")

    print("\n   by upper fit edge (the §9.9 filter-roll-off question):")
    for hi in FIT_HI:
        sel = [v["auc"] for k, v in exp_s.items() if f"-{hi:g}_" in k and np.isfinite(v["auc"])]
        if sel:
            print(f"      fit_hi {hi:>4g} Hz : median AUC {np.median(sel):.3f}  (n={len(sel)})")

    print(f"\n   CONTROL relative_delta_power over {ad.size} variants: "
          f"median {np.median(ad):.3f} IQR [{dq1:.3f}, {dq3:.3f}]" if ad.size else "\n   control unavailable")

    frac_above, frac_below = (a > 0.5).mean(), (a < 0.5).mean()
    p1 = frac_above >= 0.10 and frac_below >= 0.10
    hi30 = [v["auc"] for k, v in exp_s.items() if "-30_" in k and np.isfinite(v["auc"])]
    hi45 = [v["auc"] for k, v in exp_s.items() if "-45_" in k and np.isfinite(v["auc"])]
    p2 = bool(hi30 and hi45 and abs(np.median(hi30) - np.median(hi45)) > 0.05)
    p3 = (q3 - q1) > 0.10
    p4 = bool(ad.size and (dq3 - dq1) < (q3 - q1))
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 sign NOT stable (>=10% each side)        : {'MET' if p1 else 'NOT MET'} "
          f"({100*frac_above:.0f}% above, {100*frac_below:.0f}% below)")
    print(f"   P2 45 Hz edge differs from 30 Hz by >0.05   : {'MET' if p2 else 'NOT MET'}")
    print(f"   P3 IQR of signed AUC exceeds 0.10           : {'MET' if p3 else 'NOT MET'} ({q3-q1:.3f})")
    print(f"   P4 CONTROL delta power less variant-sensitive: {'MET' if p4 else 'NOT MET'} "
          f"(delta IQR {dq3-dq1:.3f} vs exponent {q3-q1:.3f})")
    if not p4:
        print("\n   *** CONTROL FAILED. If a band integral is as unstable as a slope fit, the instability is")
        print("       in the cohort or the outcome rather than in the aperiodic estimator, and P1-P3 say")
        print("       nothing specific about the fit. Interpretation is WITHHELD.")

    print(f"\n   ANALYTIC DEGREES OF FREEDOM: at least {len(variants())} for the exponent alone, against the")
    print("   analytic_dof = 1 declared in every SEARCH_LOG entry this project has written. A LOWER BOUND:")
    print("   reference scheme cannot be varied here because the deposit arrives average-referenced and the")
    print("   original reference is unrecoverable.")

    dst = os.path.join(RESULTS, "e09_preprocessing_sensitivity.json")
    json.dump({"experiment": "E09", "n_variants": len(variants()),
               "exponent": {"median_auc": float(np.median(a)), "iqr": [float(q1), float(q3)],
                            "min": float(a.min()), "max": float(a.max()),
                            "frac_above_half": float(frac_above), "frac_below_half": float(frac_below),
                            "median_mono": float(np.median(m))},
               "control_rel_delta": ({"median_auc": float(np.median(ad)),
                                      "iqr": [float(dq1), float(dq3)]} if ad.size else None),
               "by_variant": exp_s,
               "predictions": {"P1": bool(p1), "P2": bool(p2), "P3": bool(p3), "P4": bool(p4)}},
              open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
