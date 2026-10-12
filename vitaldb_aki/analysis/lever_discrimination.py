"""lever_discrimination.py -- power up the FLUID-vs-PRESSOR lever test (actionability
Test 2) at large N, and add the concordance->outcome payoff.

The bedside decision in a hypotensive patient is FLUID (preload-responsive: high PPV) vs
PRESSOR (vasoplegic: low diastolic tone). If the two A-line axes are INDEPENDENT they
carry orthogonal decision information MAP alone lacks. The actionability prototype (n=13)
was underpowered. This extracts the two axes (ART-only morphology -- NO ECG, so ~half the
download) for the OUTCOME-bearing ART cohort and tests:

  1. ORTHOGONALITY  -- corr(PPV axis, tone axis) at large N (independent levers?).
  2. QUADRANTS      -- fluid-indicated / pressor-indicated / mixed counts.
  3. CONCORDANCE -> OUTCOME (the payoff) -- did patients whose ACTUAL management matched
     the A-line-indicated lever have less organ injury? Actual lean from body-size-
     normalised crystalloid/colloid (mL/kg) vs pressor (phe/eph) totals; outcome from
     cohort_composite. Honest confounding caveat (clinicians may already read PPV/tone off
     the same A-line -> concordance high, null expected; a POSITIVE concordance benefit is
     the strong, recoverable-gap signal).

stdlib only at import; heavy deps lazy. Sharded + resumable (mirrors combined_biosignal).
Run: python3 -m vitaldb_aki.analysis.lever_discrimination [--limit N] [--nshards N --shard i] [--model-only]
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
ART_TRACK = "SNUADC/ART"
OUT_CSV = os.path.join(_CACHE, "lever_axes.csv")
_FIELDS = ["caseid", "art_ppv_mean", "art_ppv_burden_min", "art_dbp_mean", "art_map_mean",
           "art_sbp_mean", "art_pulse_pressure_mean", "diastolic_over_map", "map_dia_form_factor"]


def _cohort(trks_path, comp_path):
    import collections
    ct = collections.defaultdict(set)
    for r in _csv.DictReader(open(trks_path, newline="", encoding="utf-8")):
        ct[r["caseid"]].add(r["tname"])
    art = {c for c, ts in ct.items() if ART_TRACK in ts}
    comp_ids = set()
    if os.path.exists(comp_path):
        for r in _csv.DictReader(open(comp_path, newline="")):
            comp_ids.add(str(r["caseid"]))
    return sorted(art & comp_ids, key=lambda c: int(c))


def _existing(path):
    done = set()
    if os.path.exists(path):
        for row in _csv.DictReader(open(path, newline="")):
            done.add(row["caseid"])
    return done


def _feature_files():
    import glob
    return sorted(glob.glob(OUT_CSV.replace(".csv", "*.csv")))


def _all_done():
    done = set()
    for f in _feature_files():
        done |= _existing(f)
    return done


def _append(path, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def extract(limit, shard=0, nshards=1):
    from common.config import load_yaml
    from vitaldb_aki.data import tracks as _T
    from vitaldb_aki.data.client import fetch_cases
    from vitaldb_aki.features import aline_morphology as _aline
    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cohort = _cohort(os.path.join(_CACHE, "trks.csv"), os.path.join(_CACHE, "cohort_composite.csv"))
    if nshards > 1:
        cohort = [c for i, c in enumerate(cohort) if i % nshards == shard]
    out_csv = OUT_CSV if nshards == 1 else OUT_CSV.replace(".csv", f"_s{shard}.csv")
    done = _existing(out_csv) | (_all_done() if nshards > 1 else set())
    todo = [c for c in cohort if c not in done]
    if limit:
        todo = todo[:limit]
    print(f"[lever] shard {shard}/{nshards}: {len(cohort)} ART+outcome cases; {len(done)} done; "
          f"processing {len(todo)}", flush=True)
    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    def _one(cid):
        try:
            a = _aline.extract(cfg, cases_by_id, [cid]).get(cid, {})
            dbp = a.get("art_dbp_mean"); amap = a.get("art_map_mean"); pp = a.get("art_pulse_pressure_mean")
            row = {"caseid": cid}
            for k in ("art_ppv_mean", "art_ppv_burden_min", "art_dbp_mean", "art_map_mean",
                      "art_sbp_mean", "art_pulse_pressure_mean"):
                row[k] = a.get(k)
            try:
                row["diastolic_over_map"] = (float(dbp) / float(amap)) if (dbp and amap and float(amap) > 0) else None
                row["map_dia_form_factor"] = ((float(amap) - float(dbp)) / float(pp)) if (amap and dbp and pp and float(pp) > 0) else None
            except (TypeError, ValueError):
                row["diastolic_over_map"] = row["map_dia_form_factor"] = None
            return row
        except Exception as exc:
            print(f"[lever]   case {cid} FAILED: {type(exc).__name__}: {exc}", flush=True)
            return None
        finally:
            for tn in (ART_TRACK, "Solar8000/ART_MBP"):
                try:
                    _T.purge_track(cfg, cid, tn)
                except Exception:
                    pass

    import concurrent.futures
    workers = max(1, int(os.environ.get("LEVER_WORKERS", "1")))
    n_new = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for s in range(0, len(todo), workers):
            chunk = todo[s:s + workers]
            rows = [r for r in ex.map(_one, chunk) if r is not None]
            n_new += len(rows)
            if rows:
                _append(out_csv, rows)
            print(f"[lever]   progress {min(s + workers, len(todo))}/{len(todo)} (+{n_new})", flush=True)
    return len(cohort)


# --------------------------------------------------------------------- modeling
def _spear_ci(x, y, nboot=2000):
    import numpy as np
    from scipy import stats
    m = np.isfinite(x) & np.isfinite(y); x, y = x[m], y[m]
    if len(x) < 10:
        return {"r": None, "n": int(len(x))}
    r = float(stats.spearmanr(x, y)[0])
    rng = np.random.default_rng(SEED); bs = []
    for _ in range(nboot):
        idx = rng.integers(0, len(x), len(x))
        bs.append(stats.spearmanr(x[idx], y[idx])[0])
    return {"r": round(r, 3), "ci": [round(float(np.nanpercentile(bs, 2.5)), 3),
            round(float(np.nanpercentile(bs, 97.5)), 3)], "n": int(len(x))}


def _load_mgmt_outcome():
    import numpy as np, pandas as pd
    cs = pd.read_csv(os.path.join(_CACHE, "cases.csv"), low_memory=False)
    idc = [c for c in cs.columns if c.lstrip("﻿").lower() == "caseid"][0]
    cs = cs.rename(columns={idc: "caseid"}); cs["caseid"] = cs["caseid"].astype(str)
    for c in ("intraop_crystalloid", "intraop_colloid", "intraop_phe", "intraop_eph", "weight"):
        if c in cs.columns:
            cs[c] = pd.to_numeric(cs[c], errors="coerce")
    wkg = cs["weight"].where(cs["weight"] > 0, np.nan)
    cs["fluid_ml_per_kg"] = (cs["intraop_crystalloid"].fillna(0) + cs["intraop_colloid"].fillna(0)) / wkg
    cs["pressor_bolus"] = cs["intraop_phe"].fillna(0) + cs["intraop_eph"].fillna(0)
    comp = pd.read_csv(os.path.join(_CACHE, "cohort_composite.csv")); comp["caseid"] = comp["caseid"].astype(str)
    keep = ["caseid", "fluid_ml_per_kg", "pressor_bolus", "weight"] + \
           [c for c in ("age", "asa", "optype") if c in cs.columns]
    return cs[keep].merge(comp[["caseid", "composite", "organ_renal", "organ_hypoperfusion"]], on="caseid", how="inner")


def model():
    import numpy as np, pandas as pd
    files = _feature_files()
    if not files:
        return {"available": False}
    f = pd.concat([pd.read_csv(p, low_memory=False) for p in files], ignore_index=True)
    f["caseid"] = f["caseid"].astype(str)
    f = f.drop_duplicates("caseid", keep="last")
    for c in _FIELDS[1:]:
        f[c] = pd.to_numeric(f[c], errors="coerce")
    res = {"seed": SEED, "n_axes_cases": int(len(f))}
    ppv = f["art_ppv_burden_min"].where(f["art_ppv_burden_min"].notna(), f["art_ppv_mean"])
    # NOTE: map_dia_form_factor is DEGENERATE (= 1/3 constant when art_map_mean is the formula
    # DBP+PP/3); use diastolic_over_map (DBP/MAP), the real varying tone carrier. Low = vasoplegic.
    tone = f["diastolic_over_map"]
    d = pd.DataFrame({"caseid": f["caseid"], "ppv": ppv, "tone": tone}).dropna()
    res["n_both_axes"] = int(len(d))
    if len(d) >= 20:
        res["orthogonality_ppv_vs_tone"] = _spear_ci(d["ppv"].to_numpy(float), d["tone"].to_numpy(float))
        pmed, tmed = d["ppv"].median(), d["tone"].median()
        hi_ppv = d["ppv"] > pmed; lo_tone = d["tone"] < tmed
        res["lever_quadrants"] = {
            "fluid_indicated": int((hi_ppv & ~lo_tone).sum()),
            "pressor_indicated": int((~hi_ppv & lo_tone).sum()),
            "mixed_ambiguous": int((hi_ppv & lo_tone).sum() + (~hi_ppv & ~lo_tone).sum())}
        res["frac_decision_relevant"] = round(
            (res["lever_quadrants"]["fluid_indicated"] + res["lever_quadrants"]["pressor_indicated"]) / len(d), 2)
        # CONCORDANCE -> OUTCOME
        try:
            mo = _load_mgmt_outcome()
            dd = d.merge(mo, on="caseid", how="inner")
            res["n_concordance"] = int(len(dd))
            if len(dd) >= 40:
                # A-line lever: FLUID if high PPV & not low tone; PRESSOR if low tone & not high PPV
                dd = dd.assign(_hp=dd["ppv"] > pmed, _lt=dd["tone"] < tmed)
                reco = np.where(dd["_hp"] & ~dd["_lt"], "fluid",
                                np.where(~dd["_hp"] & dd["_lt"], "pressor", "mixed"))
                # actual lean: fluid if high mL/kg & low bolus pressor; pressor if the reverse
                fhi = dd["fluid_ml_per_kg"] > dd["fluid_ml_per_kg"].median()
                phi = dd["pressor_bolus"] > dd["pressor_bolus"].median()
                actual = np.where(fhi & ~phi, "fluid", np.where(phi & ~fhi, "pressor", "mixed"))
                clear = (reco != "mixed") & (actual != "mixed")
                concordant = clear & (reco == actual)
                for oc in ("composite", "organ_renal", "organ_hypoperfusion"):
                    y = pd.to_numeric(dd[oc], errors="coerce").to_numpy(float)
                    cc = concordant & np.isfinite(y); dc = clear & ~concordant & np.isfinite(y)
                    if cc.sum() >= 8 and dc.sum() >= 8:
                        res[f"concordant_vs_discordant_{oc}_RD"] = round(
                            float(np.mean(y[cc]) - np.mean(y[dc])), 3)
                        res[f"_n_{oc}"] = [int(cc.sum()), int(dc.sum())]
                res["concordance_note"] = ("negative RD (concordant LOWER injury) = recoverable benefit "
                    "from following the A-line lever. Confounded: clinicians may already act on PPV/tone "
                    "-> null expected; a clear negative RD is the strong signal.")
        except Exception as exc:
            res["concordance_error"] = str(exc)
    o = res.get("orthogonality_ppv_vs_tone", {})
    # honest: CI excluding 0 => the axes are CORRELATED (not independent), regardless of |r| size
    ci = o.get("ci") or [0, 0]
    independent = bool(o.get("r") is not None and ci[0] <= 0 <= ci[1])
    res["verdict"] = (
        f"Lever axes {'INDEPENDENT' if independent else 'CORRELATED (NOT independent -- CI excludes 0)'} "
        f"(PPV vs real-tone[diastolic/MAP] r={o.get('r')} {o.get('ci')}, n={o.get('n')}); "
        f"{res.get('frac_decision_relevant')} of patients have a clear single A-line lever. "
        + (f"Concordance->outcome: composite RD {res.get('concordant_vs_discordant_composite_RD')} "
           f"(n={res.get('_n_composite')})." if 'concordant_vs_discordant_composite_RD' in res else
           "Concordance->outcome pending N."))
    return res


def _doc(res):
    L = ["# Fluid-vs-pressor lever discrimination (powered) + concordance->outcome\n",
         "Does the A-line tell you WHICH lever (fluid vs pressor)? Tests the two axes -- PPV "
         "(preload-responsive->fluid) and diastolic tone (vasoplegic->pressor) -- at large N, and "
         "whether matching the A-line-indicated lever associates with less organ injury.\n"]
    if not res.get("available", True):
        L.append("_no axes extracted yet._")
        open(os.path.join(_DOCS, "LEVER_DISCRIMINATION.md"), "w").write("\n".join(L) + "\n"); return
    L += [f"- Cases with morphology axes: **{res['n_axes_cases']}** (both PPV+tone: {res.get('n_both_axes')}).",
          f"- **Orthogonality (PPV vs tone):** {res.get('orthogonality_ppv_vs_tone')} "
          "(|r|<0.3 = independent decision axes).",
          f"- **Lever quadrants:** {res.get('lever_quadrants')}; decision-relevant fraction "
          f"{res.get('frac_decision_relevant')}.",
          f"- **Concordance -> outcome** (n={res.get('n_concordance')}): composite RD "
          f"{res.get('concordant_vs_discordant_composite_RD')} {res.get('_n_composite','')}, renal RD "
          f"{res.get('concordant_vs_discordant_organ_renal_RD')}, hypoperfusion RD "
          f"{res.get('concordant_vs_discordant_organ_hypoperfusion_RD')}.",
          f"  _{res.get('concordance_note','')}_\n",
          "## Verdict", res.get("verdict", ""), "",
          "## Caveats",
          "- Actual fluid/pressor lean uses end-of-case TOTALS (no timing) -> coarse; the concordance "
          "test is exploratory. Confounding by indication runs BOTH ways (clinicians may already read "
          "the A-line) -> a null concordance benefit is consistent with 'already optimal'; only a clear "
          "negative RD is decisive. Single-centre. Needs a trial for a causal lever-guidance claim."]
    open(os.path.join(_DOCS, "LEVER_DISCRIMINATION.md"), "w").write("\n".join(L) + "\n")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=int(os.environ.get("LEVER_LIMIT", "400")))
    ap.add_argument("--model-only", action="store_true")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    a = ap.parse_args()
    if not a.model_only:
        extract(a.limit, shard=a.shard, nshards=a.nshards)
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "lever_discrimination.json"), "w"), indent=2, default=float)
    _doc(res)
    print("[lever] VERDICT:", res.get("verdict", "no data"), flush=True)
    print("[lever] -> docs/LEVER_DISCRIMINATION.md", flush=True)


if __name__ == "__main__":
    main()
