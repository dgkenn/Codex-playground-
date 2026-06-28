"""recovery_velocity_screen.py -- does the TRUE post-nadir MAP recovery velocity
(from analysis/recovery_velocity_extract.py, raw numeric MAP series) carry
organ-injury risk BEYOND static hypotension burden?

This is the properly-powered re-test of the thesis that the summary-statistic
proxy (analysis/reperfusion_dynamics.py) could only weakly probe. It reuses that
module's validated harness verbatim -- DeLong incremental AUROC (models/metrics),
IPTW-adjusted per-SD logistic + E-values, BH-FDR -- and simply swaps the
proxy features for the real recovery-velocity features measured from the raw
signal: rv_depthwt_slope (mmHg/min debt-repayment rate), rv_min_slope (worst/
slowest episode), rv_max_time_to_recover, rv_frac_unrecovered, rv_median_tau, etc.

Cohort: cases with a recovered hypotensive episode (rv_depthwt_slope present).
The static-burden baseline and the recovery features are therefore compared on
the SAME hypotensive cases -- a fair "at matched burden" contrast, free of the
no-episode artifact that produced the proxy's anti-hypothesis quartile trend.

Hypothesis: SLOWER recovery (low slope / high time-to-recover / unrecovered
episodes) -> MORE organ injury, at matched static burden.

Run: python3 -m vitaldb_aki.analysis.recovery_velocity_screen   (from repo root)
Outputs: cache/recovery_velocity_results.json, docs/RECOVERY_VELOCITY.md.
stdlib only at module import; heavy deps lazy (inherited from reperfusion_dynamics).
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
_RV_CSV = os.path.join(_CACHE, "recovery_velocity.csv")

RANDOM_SEED = 20260626
PRIMARY_OUTCOMES = ("composite", "organ_renal")
NEGATIVE_CONTROL = "organ_hepatocellular"

# The real recovery-velocity features (from the raw MAP series). Lower slope /
# longer time-to-recover / more unrecovered = slower debt repayment = hypothesised
# WORSE. rv_median_tau: larger = slower exponential recovery = worse.
RECOVERY_FEATURES = [
    "rv_depthwt_slope", "rv_min_slope", "rv_median_slope",
    "rv_max_time_to_recover", "rv_frac_unrecovered",
    "rv_total_unrecovered_min", "rv_median_tau", "rv_n_episodes",
]
# Primary single feature for the dose-response (the overall debt-repayment rate).
PRIMARY_FEATURE = "rv_depthwt_slope"


def _load_with_recovery():
    """reperfusion_dynamics.load_merged() (matrix + outcomes) LEFT-joined to the
    recovery-velocity CSV, restricted to cases with a measured recovery slope."""
    import pandas as pd
    from vitaldb_aki.analysis.reperfusion_dynamics import load_merged

    df = load_merged()
    if not os.path.exists(_RV_CSV):
        raise FileNotFoundError(
            f"{_RV_CSV} not found -- run analysis.recovery_velocity_extract first "
            "(it streams the raw numeric MAP series; gated behind the hypotensive "
            "cohort). The screen cannot run until extraction has produced it.")
    rv = pd.read_csv(_RV_CSV)
    rv["caseid"] = rv["caseid"].astype(str)
    df["caseid"] = df["caseid"].astype(str)
    keep = ["caseid"] + [c for c in RECOVERY_FEATURES if c in rv.columns]
    df = df.merge(rv[keep], on="caseid", how="left")
    # restrict to the cohort with a measured recovery slope (defined episode)
    df = df[df[PRIMARY_FEATURE].notna()].reset_index(drop=True)
    return df


def _quartile_doseresponse(df, feature, outcome):
    """AKI rate by quartile of `feature` + Cochran-Armitage-style trend.
    Records the trend DIRECTION so a significant p in the anti-hypothesis
    direction is not misread as support (the proxy module's lesson)."""
    import numpy as np
    import pandas as pd
    s = pd.to_numeric(df[feature], errors="coerce")
    y = pd.to_numeric(df[outcome], errors="coerce")
    m = s.notna() & y.notna()
    s, y = s[m], y[m]
    try:
        q = pd.qcut(s, 4, labels=False, duplicates="drop")
    except ValueError:
        return None
    rates, ns = [], []
    for k in sorted(pd.unique(q.dropna())):
        yk = y[q == k]
        rates.append(round(float(yk.mean()), 4))
        ns.append(int(yk.size))
    # trend test (reuse repo if available, else simple slope of rate vs quartile)
    try:
        from vitaldb_aki.analysis.map_target_analysis import cochran_armitage_trend as _ca
        p = float(_ca([int(q.eq(k).sum()) for k in sorted(pd.unique(q.dropna()))],
                      [int(((q == k) & (y == 1)).sum()) for k in sorted(pd.unique(q.dropna()))]))
    except Exception:
        # fallback: Pearson corr p of (quartile index, outcome)
        from scipy import stats
        p = float(stats.pearsonr(q.dropna().astype(float), y[q.notna()])[1])
    # For rv_depthwt_slope (higher = FASTER recovery), hypothesis = injury rate
    # DECREASES across quartiles (high slope -> low injury). Direction check:
    direction = "pro-hypothesis" if rates[-1] < rates[0] else "ANTI-hypothesis"
    return {"feature": feature, "outcome": outcome, "quartile_rates": rates,
            "quartile_n": ns, "trend_p": p, "trend_direction_for_faster_recovery": direction,
            "note": "higher rv_depthwt_slope = FASTER recovery; pro-hypothesis = injury "
                    "falls as recovery speeds up"}


def main():
    import numpy as np
    from vitaldb_aki.analysis.reperfusion_dynamics import (
        incremental_auroc, adjusted_logistic_iptw, STATIC_BASELINE,
    )
    from vitaldb_aki.analysis.actionable_targets import benjamini_hochberg

    df = _load_with_recovery()
    avail = [c for c in RECOVERY_FEATURES if c in df.columns and df[c].notna().sum() >= 50]
    results = {
        "seed": RANDOM_SEED,
        "n_cohort": int(len(df)),
        "recovery_features_used": avail,
        "static_baseline": list(STATIC_BASELINE),
        "incremental_auroc": {},
        "adjusted_iptw": {},
        "dose_response": {},
    }
    print(f"[recovery_screen] cohort N={len(df)} (cases with a measured recovery slope); "
          f"features={avail}", flush=True)

    # 1) Incremental AUROC of the recovery feature SET over static burden.
    for outcome in (*PRIMARY_OUTCOMES, NEGATIVE_CONTROL):
        if outcome not in df.columns:
            continue
        try:
            results["incremental_auroc"][outcome] = incremental_auroc(
                df, avail, outcome, seed=RANDOM_SEED)
        except Exception as exc:  # noqa: BLE001
            results["incremental_auroc"][outcome] = {"error": str(exc)}

    # 2) IPTW-adjusted per-SD association for each recovery feature; BH-FDR over all.
    pvals, keys = [], []
    for outcome in (*PRIMARY_OUTCOMES, NEGATIVE_CONTROL):
        if outcome not in df.columns:
            continue
        results["adjusted_iptw"][outcome] = {}
        for feat in avail:
            try:
                r = adjusted_logistic_iptw(df, feat, outcome, seed=RANDOM_SEED)
            except Exception as exc:  # noqa: BLE001
                r = {"error": str(exc)}
            results["adjusted_iptw"][outcome][feat] = r
            if isinstance(r, dict) and r.get("p_value") is not None and outcome in PRIMARY_OUTCOMES:
                pvals.append(float(r["p_value"]))
                keys.append((outcome, feat))
    if pvals:
        flags = benjamini_hochberg(pvals)
        results["fdr"] = {"tests": [{"outcome": o, "feature": f, "p": p, "survives": bool(s)}
                                    for (o, f), p, s in zip(keys, pvals, flags)],
                          "n_survive": int(sum(flags))}

    # 3) Dose-response of the primary debt-repayment rate.
    for outcome in PRIMARY_OUTCOMES:
        if outcome in df.columns:
            dr = _quartile_doseresponse(df, PRIMARY_FEATURE, outcome)
            if dr:
                results["dose_response"][outcome] = dr

    os.makedirs(_CACHE, exist_ok=True)
    with open(os.path.join(_CACHE, "recovery_velocity_results.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=float)
    _write_doc(results)
    open(os.path.join(_CACHE, "_recovery_velocity_screen_done.json"), "w").write("{}")
    print("[recovery_screen] DONE -> cache/recovery_velocity_results.json + "
          "docs/RECOVERY_VELOCITY.md", flush=True)
    # terse stdout summary
    for o, r in results["incremental_auroc"].items():
        if "delta_auroc" in r:
            print(f"  {o}: ΔAUROC={r['delta_auroc']:+.4f} (DeLong p={r.get('delong_p')})",
                  flush=True)


def _write_doc(results):
    lines = []
    A = lines.append
    A("# Recovery Velocity vs Static Hypotension Burden (raw MAP series)\n")
    A("## Interpretation & limitations (READ FIRST)\n")
    A("- **Observational, single-centre** (VitalDB / SNUH). Confounding by "
      "indication remains; this is **hypothesis-generating**, external validation "
      "on INSPIRE pending (INSPIRE has numeric MAP, so this IS externally testable).")
    A("- Recovery velocity is measured from the **raw numeric MAP time-series** "
      "(`Solar8000/ART_MBP`, ~0.5-2 Hz) -- the per-episode rate at which MAP climbs "
      "back out of each hypotensive nadir -- NOT a per-case summary proxy. This is "
      "the properly-powered re-test of the reperfusion thesis (cf. "
      "docs/REPERFUSION_DYNAMICS.md, which used summary stats and was under-powered).")
    A("- **Cohort = cases with a recovered MAP<65 episode** (recovery velocity is "
      "undefined without one). Static burden and recovery velocity are compared on "
      "the SAME hypotensive cases -- a fair 'at matched burden' contrast.")
    A("- `rv_depthwt_slope` (mmHg/min) = total mmHg recovered / total minutes "
      "recovering = the overall debt-repayment RATE. **Higher = faster recovery.** "
      "Hypothesis: faster recovery -> LESS injury.")
    A("- **Negative control:** `organ_hepatocellular` -- recovery dynamics should "
      "not plausibly cause it; a signal there flags residual confounding.")
    A(f"- **Cohort N = {results.get('n_cohort')}**; features: "
      f"{', '.join(results.get('recovery_features_used', []))}.\n")

    A("## Incremental AUROC over static burden (DeLong)\n")
    A(f"Static-burden baseline: `{', '.join(results.get('static_baseline', []))}`.\n")
    for o, r in results.get("incremental_auroc", {}).items():
        if "delta_auroc" in r:
            A(f"- **{o}:** base AUROC {r.get('base_auroc')} -> +recovery "
              f"{r.get('full_auroc')}; **ΔAUROC = {r['delta_auroc']:+.4f}** "
              f"(95% CI {r.get('delta_ci')}), DeLong p = {r.get('delong_p')}.")
        elif "error" in r:
            A(f"- {o}: (not computed: {r['error']})")
    A("")
    A("## IPTW-adjusted per-SD association + FDR\n")
    fdr = results.get("fdr", {})
    A(f"BH-FDR across primary-outcome tests: **{fdr.get('n_survive', 0)} survive** "
      "at q<0.05.\n")
    for o in PRIMARY_OUTCOMES:
        block = results.get("adjusted_iptw", {}).get(o, {})
        if not block:
            continue
        A(f"### {o}")
        for feat, r in block.items():
            if isinstance(r, dict) and "or_per_sd" in r:
                A(f"- `{feat}`: OR/SD = {r.get('or_per_sd')} "
                  f"(95% CI {r.get('ci')}), p = {r.get('p_value')}, "
                  f"E-value = {r.get('e_value')}.")
        A("")
    A("## Dose-response (primary: rv_depthwt_slope quartiles)\n")
    for o, dr in results.get("dose_response", {}).items():
        A(f"- **{o}:** injury rate by recovery-rate quartile (slowest→fastest) = "
          f"{dr['quartile_rates']} (n {dr['quartile_n']}); trend p = {dr['trend_p']:.3g}; "
          f"direction = **{dr['trend_direction_for_faster_recovery']}**.")
    A("\n## Methods (brief)\n")
    A("- Recovery features from raw `Solar8000/ART_MBP` (fallback NIBP/EV1000), "
      "intraop window, physiologic filter 20-200 mmHg, 10 s gap cap. Per MAP<65 "
      "episode: depth = 65 - nadir; time-to-recover to 65; slope = depth/time; "
      "exponential tau of the recovery limb. Aggregated per case.")
    A("- Incremental AUROC: paired out-of-fold logistic, StratifiedGroupKFold; "
      "DeLong test + bootstrap CI (`models/metrics.py`). IPTW per-SD logistic reuses "
      "`hypotension_treatment` propensity weights; E-values per VanderWeele & Ding; "
      "BH-FDR across primary tests. Seed 20260626.")
    A("\n---\n*Generated by vitaldb_aki/analysis/recovery_velocity_screen.py*")
    os.makedirs(_DOCS, exist_ok=True)
    with open(os.path.join(_DOCS, "RECOVERY_VELOCITY.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
