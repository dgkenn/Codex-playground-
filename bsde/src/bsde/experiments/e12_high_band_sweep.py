#!/usr/bin/env python3
"""E12 — was 20-40 Hz cherry-picked, and does moving the window off the beta peak kill the effect?

REGISTERED BEFORE ANY HIGH-BAND VARIANT WAS COMPUTED. Nothing in this project has ever fitted the aperiodic
exponent over a band starting above 3 Hz except the single 20-40 Hz choice that produced E08's 0.863.

THE GAP THIS CLOSES, STATED PLAINLY BECAUSE IT IS THE PROJECT'S WORST STANDING METHODOLOGICAL HOLE.
`exponent_high`'s band was chosen AFTER seeing that 1-20 Hz and 1-40 Hz behaved differently. E09 swept the
exponent across 72 defensible variants and found the fit's UPPER edge drove a monotone gradient
(0.070 -> 0.129 -> 0.247 -> 0.344 for fit_hi 20/30/40/45), which is what motivated splitting the band at all.
But E09 varied only `fit_lo` in {1, 2, 3}. The LOWER edge — the choice that actually defines "the high band"
and the one that was picked by hand after looking — has never been swept. Until it is, 0.863 is a number
whose denominator is unknown, and Brief 03's constraint 6 (report the size of the search space) is not
satisfied for the project's headline result.

    108 variants: fit_lo in {15, 18, 20, 22, 25, 30} Hz x fit_hi in {35, 40, 45} Hz
                  x mode in {loglog_ols, loglog_robust} x window_s in {2, 4, 8}

THE SECOND QUESTION, AND IT IS A REAL TEST RATHER THAN A SWEEP. E10 produced the hypothesis that
`exponent_high` is PROPOFOL BETA rather than a consciousness marker: propofol at moderate sedation increases
global beta/gamma power (Xi et al., PLoS One 2018;13(6):e0199120, PMID 29920532, verified from the MEDLINE
record via E-utilities), and a beta hump near the LOW EDGE of a 20-40 Hz fit window raises the band's power
and steepens the slope fitted across it at the same time. That hypothesis makes a sharp, falsifiable
prediction about band POSITION which the single 20-40 Hz fit could not test: move the window off the beta
peak and the effect should collapse.

    HONESTY ABOUT INDEPENDENCE. The propofol-beta hypothesis was generated on this deposit, so this is not
    an independent test of it — it is a new statistic (band position) applied to the same data, which is
    weaker than E11's drug-free contrast and is reported as such. It is worth running anyway because it can
    REFUTE the hypothesis cheaply, and because the sweep has to happen regardless.

REGISTERED PREDICTIONS:
    P1  NOT CHERRY-PICKED. The MEDIAN signed AUC across all 108 high-band variants exceeds 0.70. If instead
        the median sits near 0.5 and only the specific 20-40 Hz cell reaches 0.863, then the band was chosen
        by its result and the finding is an artefact of that choice. This is the prediction that decides
        whether E08 survives as anything at all.
    P2  BETA-POSITION GRADIENT, derived from the propofol-beta hypothesis and DIRECTIONAL. Median signed AUC
        DECREASES monotonically as `fit_lo` rises from 20 through 22, 25 to 30 Hz, and the 30 Hz median is at
        least 0.10 below the 20 Hz median. Propofol beta lives around 13-25 Hz; a window starting at 30 Hz has
        left it behind. If the effect is beta-driven this must happen; if the AUC is flat or rising across
        that range, the propofol-beta explanation is REFUTED for this measure and E11's outcome becomes the
        only live test of it.
    P3  PLACEBO GATE, and it gates the interpretation of P2 (rule 34: a test with no placebo has no
        denominator). `relative_band_power` computed over the SAME moving window is swept alongside. If the
        slope's fit_lo gradient is reproduced by band POWER over the identical window, the slope is a
        re-parameterisation of band power and contributes nothing of its own — and P2 would then be a fact
        about where propofol changes power, not about anything the aperiodic fit adds. The gate is MET when
        the two gradients DIFFER by more than 0.10 in their 20 Hz-to-30 Hz drop.
    P4  `analytic_dof` for the exponent family is at least 72 + 108 = 180 once this sweep exists, and every
        SEARCH_LOG entry mentioning `exponent_high` must carry that denominator rather than 72. Registered as
        a bookkeeping commitment so the number is updated whatever the result.

    FALSIFICATION OF THE E08 LEAD: P1 not met. If the 20-40 Hz cell is a lone peak in a field of noise, 0.863
    is the maximum of 108 draws and must be reported as such, not as a marker.

WHAT THIS CANNOT DO. It cannot vary the reference scheme (the deposit arrives average-referenced and the
original reference is unrecoverable), so the true analytic dof remains a LOWER bound. It cannot separate drug
from state — every Chennu contrast moves them together, which is precisely why E11 exists. And a narrow band
is a genuinely worse place to fit a power law: 20-40 Hz is 1.0 octave and 30-45 Hz is 0.58, so exponents from
the high-`fit_lo` cells are noisier by construction, which biases P2 toward being MET for reasons that have
nothing to do with beta. That bias is stated here in advance and the noise floor is reported beside the
result.
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

from bsde.features.aperiodic import welch_psd, fit_aperiodic                          # noqa: E402
from bsde.features.spectral import relative_band_power                                 # noqa: E402
from bsde.verifier.stats import directional_auc, cluster_bootstrap_ci                   # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
LONG = os.path.join(RESULTS, "e12_highband_long.csv")
FIT_LO = (15.0, 18.0, 20.0, 22.0, 25.0, 30.0)
FIT_HI = (35.0, 40.0, 45.0)
MODES = ("loglog_ols", "loglog_robust")
WINDOWS = (2.0, 4.0, 8.0)
N_CH = 8                       # same declared channel budget as the other expensive sweeps (E06)
E08_REFERENCE = 0.863          # the 20-40 Hz, 4 s, robust cell as reported by E08
DECLARED = "higher"            # exponent_high's declared direction for unconscious_vs_awake


def variants():
    return list(itertools.product(FIT_LO, FIT_HI, MODES, WINDOWS))


def extract(limit=None, log=print):
    from bsde.ingestion.chennu import ChennuRemoteZipAdapter
    refs = ChennuRemoteZipAdapter(n_epochs=4).list_recordings()
    if limit:
        refs = refs[:limit]
    done = set()
    if os.path.exists(LONG) and os.path.getsize(LONG) > 0:
        with open(LONG, newline="") as fh:
            done = {r["recording_id"] for r in csv.DictReader(fh)}
        log(f"   resuming: {len(done)} recordings already swept")
    fields = ["recording_id", "subject", "sedation_level", "variant", "fit_lo", "fit_hi",
              "mode", "window_s", "exponent", "band_power"]
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
                per_ch, acc, freqs = [], None, None
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
                # THE PLACEBO: relative power in the SAME moving window, normalised over the same 1-45 Hz
                # total every other measure in this project uses. If this reproduces the slope's gradient,
                # the slope adds nothing.
                bp = (relative_band_power(freqs, mean_psd, lo, hi, 1.0, 45.0)
                      if mean_psd is not None else float("nan"))
                rows.append({"recording_id": ref.recording_id, "subject": ref.subject,
                             "sedation_level": meta.get("sedation_level"),
                             "variant": f"{lo:g}-{hi:g}_{mode}_{wsec:g}s",
                             "fit_lo": lo, "fit_hi": hi, "mode": mode, "window_s": wsec,
                             "exponent": f"{np.mean(exps):.10g}" if exps else "",
                             "band_power": f"{bp:.10g}" if np.isfinite(bp) else ""})
            w.writerows(rows)
            fh.flush(); os.fsync(fh.fileno())
            log(f"   [{i}/{len(refs)}] {ref.recording_id[:34]:34s} {len(V)} variants")
    return LONG


def score(colname, direction):
    """Signed AUC for baseline (level 1) vs moderate (level 3), per variant, paired within subject."""
    by, meta = defaultdict(dict), {}
    for r in csv.DictReader(open(LONG, newline="")):
        if r[colname] == "":
            continue
        try:
            lvl = int(float(r["sedation_level"]))
        except (TypeError, ValueError):
            continue
        by[r["variant"]][(r["subject"], lvl)] = float(r[colname])
        meta[r["variant"]] = (float(r["fit_lo"]), float(r["fit_hi"]), r["mode"], float(r["window_s"]))
    out = {}
    for v, dd in by.items():
        subs = sorted({s for s, _ in dd})
        pair = [(s, dd[(s, 1)], dd[(s, 3)]) for s in subs if (s, 1) in dd and (s, 3) in dd]
        if len(pair) < 10:
            continue
        y = np.r_[np.zeros(len(pair)), np.ones(len(pair))]
        x = np.r_[[a for _, a, _ in pair], [b for _, _, b in pair]]
        subj = np.array([s for s, _, _ in pair] * 2)
        out[v] = {"auc": float(directional_auc(y, x, direction)), "n_pairs": len(pair),
                  "fit_lo": meta[v][0], "fit_hi": meta[v][1], "mode": meta[v][2],
                  "window_s": meta[v][3], "_y": y, "_x": x, "_subj": subj}
    return out


def median_by_lo(sc):
    g = defaultdict(list)
    for e in sc.values():
        g[e["fit_lo"]].append(e["auc"])
    return {lo: float(np.median(v)) for lo, v in sorted(g.items())}


def main() -> int:
    limit = int(os.environ.get("E12_LIMIT", "0")) or None
    V = variants()
    print("E12 — high-band sweep: was 20-40 Hz cherry-picked, and is the effect at the beta peak?")
    print(f"   {len(V)} variants: fit_lo {FIT_LO}, fit_hi {FIT_HI}, modes {MODES}, windows {WINDOWS}")
    extract(limit=limit)
    exp_s = score("exponent", DECLARED)
    if not exp_s:
        print("   no variants scored — nothing is reported"); return 1
    # The placebo is band POWER; propofol raises beta power, so its declared direction is 'higher' too. That
    # is fixed here a priori rather than chosen to make the comparison look good.
    pow_s = score("band_power", "higher")

    a = np.array([e["auc"] for e in exp_s.values()])
    med = float(np.median(a))
    q1, q3 = np.percentile(a, [25, 75])
    print("\n" + "=" * 100)
    print(f"SIGNED AUC over {a.size} high-band variants (declared direction '{DECLARED}')")
    print("=" * 100)
    print(f"   median {med:.3f}   IQR [{q1:.3f}, {q3:.3f}]   min {a.min():.3f}   max {a.max():.3f}")
    print(f"   variants above 0.5: {int((a > 0.5).sum())}/{a.size}     "
          f"E08's reported 20-40 Hz cell: {E08_REFERENCE:.3f}")
    rank = int((a >= E08_REFERENCE).sum())
    print(f"   variants scoring at least as high as E08's cell: {rank}/{a.size} "
          f"-> E08 sits at percentile {100 * (1 - rank / a.size):.0f}")

    print("\n   median signed AUC by fit_lo (the edge that was chosen by hand):")
    m_exp, m_pow = median_by_lo(exp_s), (median_by_lo(pow_s) if pow_s else {})
    print(f"      {'fit_lo':>8s} {'exponent':>10s} {'band power (placebo)':>22s}")
    for lo in sorted(m_exp):
        mp = f"{m_pow[lo]:.3f}" if lo in m_pow else "  -  "
        print(f"      {lo:8.0f} {m_exp[lo]:10.3f} {mp:>22s}")

    print("\n   median signed AUC by fit_hi:")
    g = defaultdict(list)
    for e in exp_s.values():
        g[e["fit_hi"]].append(e["auc"])
    for hi in sorted(g):
        print(f"      {hi:8.0f} {float(np.median(g[hi])):10.3f}")

    # CI on the best and on the registered 20-40 cell, so "0.863" is not compared against point estimates.
    print("\n   subject-clustered CIs on the cells that matter:")
    rng = np.random.default_rng(20260730)
    ci = {}
    named = {"best": max(exp_s.items(), key=lambda kv: kv[1]["auc"])[0],
             "worst": min(exp_s.items(), key=lambda kv: kv[1]["auc"])[0]}
    for label in ("20-40_loglog_robust_4s", "30-45_loglog_robust_4s"):
        if label in exp_s:
            named[label] = label
    for label, v in named.items():
        e = exp_s[v]
        lo_, hi_ = cluster_bootstrap_ci(
            lambda i: directional_auc(e["_y"][i], e["_x"][i], DECLARED), e["_subj"], rng, reps=2000)[:2]
        ci[v] = {"auc": e["auc"], "ci": [float(lo_), float(hi_)], "role": label}
        print(f"      {label:26s} {v:26s} {e['auc']:.3f} [{lo_:.3f}, {hi_:.3f}]")

    # ------------------------------- predictions ---------------------------------------------------
    p1 = med > 0.70
    drop_exp = (m_exp.get(20.0, np.nan) - m_exp.get(30.0, np.nan))
    los = [lo for lo in (20.0, 22.0, 25.0, 30.0) if lo in m_exp]
    monotone = all(m_exp[los[i]] >= m_exp[los[i + 1]] for i in range(len(los) - 1))
    p2 = bool(monotone and np.isfinite(drop_exp) and drop_exp >= 0.10)
    drop_pow = (m_pow.get(20.0, np.nan) - m_pow.get(30.0, np.nan)) if m_pow else float("nan")
    p3 = bool(np.isfinite(drop_exp) and np.isfinite(drop_pow) and abs(drop_exp - drop_pow) > 0.10)

    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 median across all {a.size} variants > 0.70 (not cherry-picked) : "
          f"{'MET' if p1 else 'NOT MET'} (median {med:.3f})")
    print(f"   P2 monotone decline 20->30 Hz, drop >= 0.10 (beta position)      : "
          f"{'MET' if p2 else 'NOT MET'} (monotone {monotone}, drop {drop_exp:+.3f})")
    print(f"   P3 PLACEBO GATE: band power does NOT reproduce that gradient     : "
          f"{'MET' if p3 else 'NOT MET'} (power drop {drop_pow:+.3f}, "
          f"difference {abs(drop_exp - drop_pow):.3f})")
    print(f"   P4 analytic_dof for the exponent family is now >= {72 + len(V)}          : "
          f"MET by construction (72 from E09 + {len(V)} here)")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p1:
        verdict = "CHERRY_PICKED"
        print(f"   The 20-40 Hz cell is a peak in a field that medians at {med:.3f}. E08's 0.863 is the")
        print(f"   maximum of {a.size} draws and must be reported as such. The lead is WITHDRAWN.")
    elif not p3:
        verdict = "SLOPE_IS_BAND_POWER"
        print("   The placebo reproduced the gradient: relative band power over the same moving window")
        print("   behaves like the slope fitted across it. The aperiodic fit adds nothing of its own here,")
        print("   and P2 is a fact about where propofol changes POWER. Reading it as evidence about the")
        print("   aperiodic component would be the redundancy error this project has made three times")
        print("   (rule 28). No claim is made from P2.")
    elif p2:
        verdict = "BAND_ROBUST_AND_BETA_POSITIONED"
        print("   The effect survives across the band sweep AND collapses when the window leaves the beta")
        print("   range, while band power does not explain the collapse. That is consistent with the")
        print("   propofol-beta reading — which, since the hypothesis was generated on this deposit, this")
        print("   experiment CORROBORATES rather than tests. E11's drug-free contrast remains the test.")
    else:
        verdict = "BAND_ROBUST_NOT_BETA_POSITIONED"
        print("   The effect survives across the band sweep but does NOT collapse when the window leaves")
        print("   the beta range. The propofol-beta explanation is REFUTED for this measure, and whatever")
        print("   exponent_high is tracking is not confined to the beta peak.")
    print(f"\n   verdict: {verdict}")
    print(f"\n   Denominator: analytic_dof >= {72 + len(V)} for the exponent family, and this remains a LOWER")
    print("   bound — the reference scheme cannot be varied on an average-referenced deposit.")
    print("   NOTE the registered bias: 30-45 Hz is 0.58 octaves against 20-40 Hz's 1.00, so high-fit_lo")
    print("   cells are noisier by construction and P2 is biased toward being MET for non-beta reasons.")

    dst = os.path.join(RESULTS, "e12_highband.json")
    json.dump({"experiment": "E12", "n_variants": a.size, "median_auc": med,
               "iqr": [float(q1), float(q3)], "min": float(a.min()), "max": float(a.max()),
               "e08_reference": E08_REFERENCE, "e08_percentile": float(100 * (1 - rank / a.size)),
               "median_by_fit_lo_exponent": m_exp, "median_by_fit_lo_band_power": m_pow,
               "cis": ci, "analytic_dof_lower_bound": 72 + len(V),
               "predictions": {"P1": p1, "P2": p2, "P3": p3, "P4": True},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
