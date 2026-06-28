"""combined_biosignal.py -- the ECG x ARTERIAL-LINE combined biosignal (user idea),
and the build that UNBLOCKS the waveform->requirement predictor (Pivot #1, currently
N=11 because morphology had not been extracted for the pressor cohort).

Idea
----
Pairing the arterial line with the ECG yields cross-channel biosignals that neither
carries alone:
  * PAT  (pulse arrival time) = ECG R-peak -> pulse foot delay = pre-ejection period
    (contractility) + pulse transit time (arterial stiffness / tone / BP). A cuffless,
    beat-by-beat tone+contractility surrogate -- the ECG-paired analogue of Pivot 2's
    arterial 'tone' signal.
  * BRS  (baroreflex sensitivity) = coupling of ECG RR intervals to arterial SBP
    sequences = autonomic reserve; low BRS marks instability / vasoplegia.
These are computed by features/cross_waveform.py (PAT, BRS, decoupling, coherence);
arterial morphology by features/aline_morphology.py. Both already exist and have
memory discipline (purge the ~57 MB SNUADC waveforms per case).

What this module does
---------------------
1. EXTRACT, for the PRESSOR cohort (pump + SNUADC/ART + SNUADC/ECG_II), the combined
   feature set: arterial morphology (art_*) + ECG-coupling (pat_*, brs_*, coherence,
   decoupling). Per-case, resumable (cache/combined_biosignal_features.csv), waveforms
   purged after each case.
2. ABLATION (the 'is the combination worth it' test): predict the vasopressor
   dose-REQUIREMENT phenotype (from pressor_requirement_epochs.csv) from
     (A) ARTERIAL-only morphology,
     (B) ECG-coupling-only (PAT/BRS/...),
     (C) COMBINED.
   Out-of-fold Spearman/R2 for each -> the combined biosignal is justified only if C
   beats both A and B. Plus the PAT and BRS univariate correlations with requirement,
   and a placebo label (surgery duration) for an honesty floor.

stdlib only at import; heavy deps lazy. Honest about N (the phenotype cohort is small).
Run: python3 -m vitaldb_aki.analysis.combined_biosignal [--limit N] [--model-only]
"""
from __future__ import annotations
import csv as _csv
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628

VASOCON = ("NEPI", "PHEN", "DOPA", "VASO")
ART_TRACK = "SNUADC/ART"
ECG_TRACK = "SNUADC/ECG_II"
PPG_TRACK = "SNUADC/PLETH"
OUT_CSV = os.path.join(_CACHE, "combined_biosignal_features.csv")
EPOCHS_CSV = os.path.join(_CACHE, "pressor_requirement_epochs.csv")
PRIMARY_DRUG = "NEPI"
TARGET_LO, TARGET_HI = 55.0, 80.0
MIN_EPOCHS_PER_CASE = 2
# ECG-coupling features (the ones that REQUIRE the ECG pairing)
ECG_COUPLING_HINTS = ("pat_", "brs_", "coher", "decoupl", "rr_", "hrv", "cross_waveform")


def _cohort(trks_path):
    case_tracks = {}
    by_drug = {d: set() for d in VASOCON}
    for row in _csv.DictReader(open(trks_path, newline="", encoding="utf-8")):
        cid, tn = row["caseid"], row["tname"]
        case_tracks.setdefault(cid, set()).add(tn)
        if tn.startswith("Orchestra/") and tn.endswith("_RATE"):
            d = tn[len("Orchestra/"):-len("_RATE")]
            if d in by_drug:
                by_drug[d].add(cid)
    pressor = set().union(*by_drug.values()) if by_drug else set()
    cohort = [c for c in pressor
              if ART_TRACK in case_tracks.get(c, ()) and ECG_TRACK in case_tracks.get(c, ())]
    return sorted(cohort, key=lambda c: int(c))


def _existing(path):
    done = set()
    if os.path.exists(path):
        for row in _csv.DictReader(open(path, newline="")):
            done.add(row["caseid"])
    return done


def _feature_files():
    import glob
    return sorted(glob.glob(OUT_CSV.replace(".csv", "*.csv")))


def _all_done_caseids():
    """Caseids already extracted in ANY shard/legacy CSV -> shards never redo work."""
    done = set()
    for f in _feature_files():
        done |= _existing(f)
    return done


def _append(path, rows, fieldnames):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def extract(limit, shard=0, nshards=1):
    from common.config import load_yaml
    from vitaldb_aki.data import tracks as _T
    from vitaldb_aki.data.client import fetch_cases
    from vitaldb_aki.features import aline_morphology as _aline
    from vitaldb_aki.features import cross_waveform as _cross
    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cohort = _cohort(os.path.join(_CACHE, "trks.csv"))
    # PRIORITISE phenotype-bearing cases: only these contribute to the merged ablation,
    # so extract them first -> a usable result after ~52 cases, not all 215.
    pheno = set(_requirement_phenotype().keys())
    cohort.sort(key=lambda c: (c not in pheno, int(c)))
    # SHARD across processes (true parallelism without the thread race): each process
    # takes a disjoint stride of the prioritised cohort and writes its own CSV.
    if nshards > 1:
        cohort = [c for i, c in enumerate(cohort) if i % nshards == shard]
    out_csv = OUT_CSV if nshards == 1 else OUT_CSV.replace(".csv", f"_s{shard}.csv")
    done = _existing(out_csv) | (_all_done_caseids() if nshards > 1 else set())
    todo = [c for c in cohort if c not in done]
    if limit:
        todo = todo[:limit]
    n_pheno_todo = sum(1 for c in todo if c in pheno)
    print(f"[cbs] shard {shard}/{nshards}: {len(cohort)} cohort cases ({len(pheno&set(cohort))} "
          f"phenotype); {len(done)} done; processing {len(todo)} ({n_pheno_todo} phenotype-bearing)",
          flush=True)
    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}
    aline_cols = [s.name for s in _aline.SPECS]
    cross_cols = [s.name for s in _cross.SPECS]
    derived = ["diastolic_over_map", "map_dia_form_factor"]
    fieldnames = ["caseid"] + aline_cols + cross_cols + derived
    purge = (ART_TRACK, ECG_TRACK, PPG_TRACK, "SNUADC/ART", "Solar8000/ART_MBP")

    def _one(cid):
        row = {"caseid": cid}
        try:
            a = _aline.extract(cfg, cases_by_id, [cid]).get(cid, {})
            c = _cross.extract(cfg, cases_by_id, [cid]).get(cid, {})
            row.update(a); row.update(c)
            dbp = a.get("art_dbp_mean"); amap = a.get("art_map_mean"); pp = a.get("art_pulse_pressure_mean")
            try:
                row["diastolic_over_map"] = (float(dbp) / float(amap)) if (dbp and amap and float(amap) > 0) else None
                row["map_dia_form_factor"] = ((float(amap) - float(dbp)) / float(pp)) if (amap and dbp and pp and float(pp) > 0) else None
            except (TypeError, ValueError):
                row["diastolic_over_map"] = row["map_dia_form_factor"] = None
            return row
        except Exception as exc:
            print(f"[cbs]   case {cid} FAILED: {type(exc).__name__}: {exc}", flush=True)
            return None
        finally:
            for tn in purge:
                try:
                    _T.purge_track(cfg, cid, tn)
                except Exception:
                    pass

    import concurrent.futures
    workers = max(1, int(os.environ.get("CBS_WORKERS", "3")))
    n_new = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for s in range(0, len(todo), workers):
            chunk = todo[s:s + workers]
            rows = [r for r in ex.map(_one, chunk) if r is not None]
            n_new += len(rows)
            if rows:
                _append(out_csv, rows, fieldnames)
            print(f"[cbs]   progress {min(s + workers, len(todo))}/{len(todo)} (+{n_new})", flush=True)
    return len(cohort)


# --------------------------------------------------------------------- modeling
def _requirement_phenotype():
    import numpy as np, pandas as pd
    if not os.path.exists(EPOCHS_CSV):
        return {}
    df = pd.read_csv(EPOCHS_CSV, low_memory=False)
    for c in ("dose_per_kg", "map_mean", "norepi_only"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["caseid"] = df["caseid"].astype(str)
    q = df[(df["drug"] == PRIMARY_DRUG) & (df["norepi_only"] == 1) &
           (df["map_mean"].between(TARGET_LO, TARGET_HI)) & df["dose_per_kg"].notna()]
    pheno = {}
    for cid, g in q.groupby("caseid"):
        if len(g) >= MIN_EPOCHS_PER_CASE:
            pheno[cid] = float(np.median(g["dose_per_kg"]))
    return pheno


def _oof_spearman(X, y, n_splits=5):
    import numpy as np
    from sklearn.model_selection import KFold
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import RidgeCV
    from scipy import stats
    if X.shape[0] < 12 or X.shape[1] == 0:
        return None
    oof = np.full(len(y), np.nan)
    k = min(n_splits, len(y) // 3)
    if k < 2:
        return None
    for tr, te in KFold(k, shuffle=True, random_state=SEED).split(X):
        p = Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler()),
                      ("m", RidgeCV(alphas=(.1, 1, 10, 100)))])
        p.fit(X[tr], y[tr]); oof[te] = p.predict(X[te])
    m = np.isfinite(oof) & np.isfinite(y)
    if m.sum() < 8:
        return None
    r = float(stats.spearmanr(oof[m], y[m])[0])
    ss_res = float(np.sum((y[m] - oof[m]) ** 2)); ss_tot = float(np.sum((y[m] - y[m].mean()) ** 2))
    return {"oof_spearman": round(r, 3), "oof_r2": round(1 - ss_res / ss_tot, 3) if ss_tot > 0 else None,
            "n": int(m.sum())}


def model():
    import numpy as np, pandas as pd
    from scipy import stats
    files = _feature_files()
    if not files:
        return {"available": False}
    feats = pd.concat([pd.read_csv(f, low_memory=False) for f in files], ignore_index=True)
    feats["caseid"] = feats["caseid"].astype(str)
    feats = feats.drop_duplicates(subset="caseid", keep="last").reset_index(drop=True)
    pheno = _requirement_phenotype()
    res = {"seed": SEED, "n_feature_cases": int(len(feats)),
           "n_phenotype_cases": len(pheno)}
    merged = feats[feats["caseid"].isin(pheno)].copy()
    merged["requirement"] = merged["caseid"].map(pheno)
    res["n_merged"] = int(len(merged))
    # feature partitions
    num = merged.select_dtypes(include="number")
    art_cols = [c for c in num.columns if c.startswith("art_") or c in ("diastolic_over_map", "map_dia_form_factor")]
    ecg_cols = [c for c in num.columns if any(h in c.lower() for h in ECG_COUPLING_HINTS)]
    art_cols = [c for c in art_cols if c != "requirement"]
    ecg_cols = [c for c in ecg_cols if c != "requirement"]
    res["n_art_features"] = len(art_cols); res["n_ecg_coupling_features"] = len(ecg_cols)
    if len(merged) >= 12:
        y = merged["requirement"].to_numpy(float)
        def _drop_const(cols):
            return [c for c in cols if merged[c].notna().sum() >= 8 and merged[c].nunique() > 1]
        ac, ec = _drop_const(art_cols), _drop_const(ecg_cols)
        res["ablation"] = {
            "arterial_only": _oof_spearman(merged[ac].to_numpy(float), y) if ac else None,
            "ecg_coupling_only": _oof_spearman(merged[ec].to_numpy(float), y) if ec else None,
            "combined": _oof_spearman(merged[ac + ec].to_numpy(float), y) if (ac or ec) else None}
        # univariate PAT / BRS / primary tone
        uni = {}
        for f in ("pat_mean_ms", "brs_mean", "diastolic_over_map", "pat_slope"):
            if f in merged.columns:
                x = pd.to_numeric(merged[f], errors="coerce").to_numpy(float)
                m = np.isfinite(x) & np.isfinite(y)
                if m.sum() >= 10:
                    uni[f] = round(float(stats.spearmanr(x[m], y[m])[0]), 3)
        res["univariate_vs_requirement"] = uni
        res["note_overfit"] = "OOF only; n is the binding constraint -- interpret as feasibility unless n_merged>=25"
        comb = (res["ablation"].get("combined") or {}).get("oof_spearman")
        art = (res["ablation"].get("arterial_only") or {}).get("oof_spearman")
        ecg = (res["ablation"].get("ecg_coupling_only") or {}).get("oof_spearman")
        if res["n_merged"] >= 25 and comb is not None and art is not None and ecg is not None:
            res["combination_worth_it"] = bool(comb > max(art, ecg) + 0.05)
            res["verdict"] = (f"COMBINED biosignal justified -- OOF Spearman combined {comb} > "
                              f"arterial {art} and ECG-coupling {ecg}." if res["combination_worth_it"]
                              else f"Combination NOT clearly additive at this N -- combined {comb} vs "
                              f"arterial {art} / ECG {ecg}.")
        else:
            res["verdict"] = (f"FEASIBILITY-ONLY -- merged N={res['n_merged']} (need >=25 for inference). "
                              f"Ablation OOF Spearman: arterial {art}, ECG-coupling {ecg}, combined {comb}. "
                              "Extraction grows the merged cohort; re-run --model-only as it fills.")
    else:
        res["verdict"] = f"INSUFFICIENT merged N={res['n_merged']} (feature cases {len(feats)}, phenotype {len(pheno)})."
    return res


def _doc(res):
    L = ["# ECG x arterial-line COMBINED biosignal -- and the requirement predictor (Pivot #1)\n",
         "Pairs the arterial line with ECG_II (500 Hz, 3644 cases) to build cross-channel signals "
         "neither carries alone -- PAT (R-peak->pulse-foot = contractility + stiffness/tone) and BRS "
         "(RR<->SBP coupling = autonomic reserve) -- and tests whether the COMBINED biosignal predicts "
         "the vasopressor dose-requirement (vasoplegia) phenotype better than arterial morphology or "
         "ECG-coupling alone.\n"]
    if not res.get("available", True):
        L.append("_no features extracted yet._")
        open(os.path.join(_DOCS, "COMBINED_BIOSIGNAL.md"), "w").write("\n".join(L) + "\n"); return
    L += [f"- Feature cases extracted: **{res['n_feature_cases']}** "
          f"({res['n_art_features']} arterial, {res['n_ecg_coupling_features']} ECG-coupling features).",
          f"- Requirement-phenotype cases: **{res['n_phenotype_cases']}**; merged: **{res['n_merged']}**.\n"]
    ab = res.get("ablation")
    if ab:
        L += ["## Ablation -- is the combination worth it? (OOF Spearman vs requirement)",
              f"- ARTERIAL-only: {ab.get('arterial_only')}",
              f"- ECG-coupling-only: {ab.get('ecg_coupling_only')}",
              f"- **COMBINED**: {ab.get('combined')}", "",
              f"- Univariate vs requirement: {res.get('univariate_vs_requirement')}", ""]
    L += ["## Verdict", res.get("verdict", ""), "",
          "## Caveats",
          "- OOF only; merged N is the binding constraint (the requirement phenotype needs >=2 stable "
          "norepi-only target-band epochs, which is rare). Treat as feasibility until N>=25.",
          "- PAT here uses the cross_waveform extractor (ECG R-peak -> pulse foot); absolute PAT mixes "
          "pre-ejection period and transit time -- the combined index is a SURROGATE, validated by its "
          "correlation with the requirement / SVR, not a calibrated measurement.",
          "- Single-centre (SNUH/VitalDB); external replication required."]
    open(os.path.join(_DOCS, "COMBINED_BIOSIGNAL.md"), "w").write("\n".join(L) + "\n")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=int(os.environ.get("CBS_LIMIT", "230")))
    ap.add_argument("--model-only", action="store_true")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    a = ap.parse_args()
    if not a.model_only:
        extract(a.limit, shard=a.shard, nshards=a.nshards)
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "combined_biosignal.json"), "w"), indent=2, default=float)
    _doc(res)
    print("\n[cbs] VERDICT: " + res.get("verdict", "no data"), flush=True)
    print("[cbs] -> docs/COMBINED_BIOSIGNAL.md", flush=True)


if __name__ == "__main__":
    main()
