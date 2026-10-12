"""pressor_requirement_phen.py -- INTERNAL REPLICATION of the stable-epoch
vasopressor dose-REQUIREMENT finding in an INDEPENDENT drug: PHENYLEPHRINE (PHEN).

This MIRRORS analysis/pressor_requirement.py (the norepinephrine extractor/model)
exactly, but conditions on PHEN-only stable constant-infusion epochs. Phenylephrine
is a pure alpha-1 agonist (no beta), so it raises MAP purely by SVR -- a clean,
mechanistically-independent second agent. If the norepi finding (split-half
reliability 0.82, ~5.6x between-patient spread, early-half predicts late-half)
REPLICATES here, the dose-requirement phenotype is not norepi-specific; it is a
patient-level vasoconstrictor-requirement trait.

Estimand (per patient) = the phenylephrine dose (per kg) required to sustain MAP in
the clinical target band [55, 80] mmHg, over that patient's PHEN-ONLY stable epochs.

Same machinery as the norepi build:
  - stable-epoch detection: maximal constant-RATE runs >= MIN_EPOCH (180 s), drop
    the first SETTLE (60 s) post-change.
  - MAP target band [55, 80]; dose_per_kg = rate / weight.
  - PHEN-only: no OTHER vasoconstrictor (NEPI/DOPA/VASO) running in the epoch.
  - reliability = within-patient split-half Spearman (odd vs even epoch medians).
  - spread = between-patient p90/p10 fold-range of the requirement.
  - early->late = time-split Spearman: median over the EARLIER half of a case's
    epochs vs median over the LATER half (the early-ID robustness check).

Tracks are SMALL numeric (Orchestra/PHEN_RATE + Solar8000/ART_MBP + Solar8000/HR +
weight from cases.csv) -- NO big SNUADC waveform -> fast. Tracks purged per case.

stdlib only at import; numpy/pandas/scipy lazy. SHARDED + RESUMABLE (mirrors
combined_biosignal / lever_discrimination): per-shard CSV
cache/pressor_requirement_phen_epochs_s{shard}.csv, _all_done() dedup across shards,
model() globs all shards.

Run: python3 -m vitaldb_aki.analysis.pressor_requirement_phen \
        [--limit N] [--nshards N --shard i] [--model-only]
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

# vasoCONSTRICTORS that raise MAP via SVR (exclude pure inotropes EPI/DOBU here).
VASOCON = ("NEPI", "PHEN", "DOPA", "VASO")
PRIMARY_DRUG = "PHEN"           # phenylephrine -- the independent replication agent
MAP_TRACK = "Solar8000/ART_MBP"
HR_TRACK = "Solar8000/HR"
CVP_TRACK = "Solar8000/CVP"
BIS_TRACK = "BIS/BIS"
MAC_TRACK = "Primus/MAC"
SVR_TRACKS = ("EV1000/SVR", "EV1000/SVRI")

MIN_EPOCH = 180.0               # a stable epoch must last >= 3 min
SETTLE = 60.0                   # drop the first 60 s after a rate change (settling)
RATE_TOL = 1e-6                 # rate "constant" tolerance
MAP_MIN, MAP_MAX = 20.0, 200.0
TARGET_LO, TARGET_HI = 55.0, 80.0   # clinical MAP target band for the requirement
MIN_EPOCHS_PER_CASE = 2
EPOCHS_CSV = os.path.join(_CACHE, "pressor_requirement_phen_epochs.csv")
_FIELDS = ["caseid", "drug", "t_start", "t_end", "dur", "rate", "dose_per_kg",
           "map_mean", "map_sd", "n_map", "hr_mean", "cvp_mean", "bis_mean",
           "mac_mean", "phen_only", "svr_mean", "weight", "age", "sex", "asa", "optype"]


def _cohort(trks_path):
    """Cases with a PHEN_RATE pump AND ART_MBP. Also returns which vasoconstrictors
    each case has (to enforce PHEN-only) and which have SVR."""
    by_drug = {d: set() for d in VASOCON}
    map_cases, svr_cases = set(), set()
    with open(trks_path, newline="", encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            cid, tn = row["caseid"], row["tname"]
            if tn == MAP_TRACK:
                map_cases.add(cid)
            elif tn in SVR_TRACKS:
                svr_cases.add(cid)
            elif tn.startswith("Orchestra/") and tn.endswith("_RATE"):
                d = tn[len("Orchestra/"):-len("_RATE")]
                if d in by_drug:
                    by_drug[d].add(cid)
    drug_of = {}
    for d, cs in by_drug.items():
        for c in cs:
            drug_of.setdefault(c, []).append(d)
    # cohort = cases that have PHEN + ART_MBP
    phen_cases = by_drug.get(PRIMARY_DRUG, set())
    return sorted(phen_cases & map_cases, key=lambda c: int(c)), drug_of, svr_cases


def _case_meta(cases_path):
    meta = {}
    with open(cases_path, newline="", encoding="utf-8") as fh:
        r = _csv.DictReader(fh)
        idc = [c for c in r.fieldnames if c.lstrip("﻿").lower() == "caseid"][0]
        for row in r:
            meta[row[idc]] = {"weight": row.get("weight", ""), "age": row.get("age", ""),
                              "sex": row.get("sex", ""), "asa": row.get("asa", ""),
                              "optype": row.get("optype", "")}
    return meta


def _segments(rate_series):
    """Maximal piecewise-constant POSITIVE-rate runs. Returns [(t0,t1,rate)]."""
    segs = []
    if not rate_series:
        return segs
    seg_start, seg_rate = rate_series[0]
    last_t = rate_series[0][0]
    for t, v in rate_series[1:]:
        if abs(v - seg_rate) > RATE_TOL:
            if seg_rate > 0 and (last_t - seg_start) >= MIN_EPOCH:
                segs.append((seg_start, last_t, seg_rate))
            seg_start, seg_rate = t, v
        last_t = t
    if seg_rate > 0 and (last_t - seg_start) >= MIN_EPOCH:
        segs.append((seg_start, last_t, seg_rate))
    return segs


def _win(series, lo, hi, vmin=None, vmax=None):
    import numpy as np
    vals = [v for (t, v) in series if lo <= t < hi and (vmin is None or vmin <= v <= vmax)]
    if not vals:
        return None, None, 0
    return float(np.mean(vals)), float(np.std(vals)), len(vals)


def _rate_at(series, t0, t1):
    """Mean rate of a (possibly different) pump over [t0,t1]; 0 if absent."""
    import numpy as np
    vals = [v for (t, v) in series if t0 <= t < t1]
    return float(np.mean(vals)) if vals else 0.0


def _process_case(cfg, cid, drugs_present, meta, svr_case):
    from vitaldb_aki.data.tracks import download_track, purge_track
    map_s = download_track(cfg, cid, MAP_TRACK)
    if len(map_s) < 10:
        purge_track(cfg, cid, MAP_TRACK); return []
    hr_s = download_track(cfg, cid, HR_TRACK)
    cvp_s = download_track(cfg, cid, CVP_TRACK)
    bis_s = download_track(cfg, cid, BIS_TRACK)
    mac_s = download_track(cfg, cid, MAC_TRACK)
    svr_s, svr_src = [], ""
    if svr_case:
        for st in SVR_TRACKS:
            s = download_track(cfg, cid, st)
            if len(s) >= 4:
                svr_s, svr_src = s, st; break
    rate_cache = {d: download_track(cfg, cid, f"Orchestra/{d}_RATE") for d in drugs_present}
    m = meta.get(cid, {})
    try:
        wkg = float(m.get("weight") or "nan")
    except ValueError:
        wkg = float("nan")
    rows = []
    # PHEN replication: only stable epochs of the PRIMARY_DRUG (phenylephrine)
    for drug in [d for d in drugs_present if d == PRIMARY_DRUG]:
        for (t0, t1, rate) in _segments(rate_cache[drug]):
            a, b = t0 + SETTLE, t1
            if b - a < MIN_EPOCH - SETTLE:
                continue
            mmean, msd, nmap = _win(map_s, a, b, MAP_MIN, MAP_MAX)
            if mmean is None or nmap < 6:
                continue
            # phen-only: no OTHER vasoconstrictor running in this epoch
            others = [d for d in drugs_present if d != drug]
            phen_only = int(all(_rate_at(rate_cache[d], t0, t1) <= RATE_TOL for d in others))
            hr_m, _, _ = _win(hr_s, a, b, 20, 220)
            cvp_m, _, _ = _win(cvp_s, a, b, -5, 40)
            bis_m, _, _ = _win(bis_s, a, b, 0, 100)
            mac_m, _, _ = _win(mac_s, a, b, 0, 5)
            svr_m, _, _ = _win(svr_s, a, b, 100, 6000) if svr_s else (None, None, 0)
            rows.append({
                "caseid": cid, "drug": drug, "t_start": round(t0, 1), "t_end": round(t1, 1),
                "dur": round(t1 - t0, 1), "rate": round(rate, 5),
                "dose_per_kg": round(rate / wkg, 6) if wkg == wkg and wkg > 0 else None,
                "map_mean": round(mmean, 2), "map_sd": round(msd, 2) if msd is not None else None,
                "n_map": nmap, "hr_mean": round(hr_m, 1) if hr_m is not None else None,
                "cvp_mean": round(cvp_m, 2) if cvp_m is not None else None,
                "bis_mean": round(bis_m, 1) if bis_m is not None else None,
                "mac_mean": round(mac_m, 3) if mac_m is not None else None,
                "phen_only": phen_only, "svr_mean": round(svr_m, 1) if svr_m is not None else None,
                "weight": m.get("weight", ""), "age": m.get("age", ""), "sex": m.get("sex", ""),
                "asa": m.get("asa", ""), "optype": m.get("optype", "")})
    for tn in [MAP_TRACK, HR_TRACK, CVP_TRACK, BIS_TRACK, MAC_TRACK] + ([svr_src] if svr_src else []):
        purge_track(cfg, cid, tn)
    for d in drugs_present:
        purge_track(cfg, cid, f"Orchestra/{d}_RATE")
    return rows


# ----------------------------------------------------- sharded resumable I/O
def _shard_files():
    import glob
    base = EPOCHS_CSV.replace(".csv", "")
    return sorted(glob.glob(base + "_s*.csv")) + ([EPOCHS_CSV] if os.path.exists(EPOCHS_CSV) else [])


def _existing(path):
    done = set()
    if os.path.exists(path):
        for row in _csv.DictReader(open(path, newline="")):
            done.add(row["caseid"])
    return done


def _all_done():
    done = set()
    for f in _shard_files():
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
    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cohort, drug_of, svr_cases = _cohort(os.path.join(_CACHE, "trks.csv"))
    meta = _case_meta(os.path.join(_CACHE, "cases.csv"))
    if nshards > 1:
        cohort = [c for i, c in enumerate(cohort) if i % nshards == shard]
    out_csv = EPOCHS_CSV if nshards == 1 else EPOCHS_CSV.replace(".csv", f"_s{shard}.csv")
    done = _existing(out_csv) | (_all_done() if nshards > 1 else set())
    todo = [c for c in cohort if c not in done]
    if limit:
        todo = todo[:limit]
    print(f"[phen] shard {shard}/{nshards}: {len(cohort)} PHEN+ART_MBP cases; "
          f"{len(done)} done; processing {len(todo)}", flush=True)
    for i, cid in enumerate(todo, 1):
        try:
            rows = _process_case(cfg, cid, drug_of.get(cid, []), meta, cid in svr_cases)
            _append(out_csv, rows)
            print(f"[phen]  [{i}/{len(todo)}] case {cid}: {len(rows)} stable epochs", flush=True)
        except Exception as exc:
            print(f"[phen]  [{i}/{len(todo)}] case {cid} FAILED: {type(exc).__name__}: {exc}", flush=True)
    return len(cohort)


# --------------------------------------------------------------------- modeling
def _icc_splithalf(per_case_epochs):
    """Within-patient reliability of the requirement: for cases with >=4 target-band
    phen-only epochs, correlate the median dose over ODD vs EVEN epochs."""
    import numpy as np
    from scipy import stats
    odd, even = [], []
    for cid, doses in per_case_epochs.items():
        if len(doses) >= 4:
            o = doses[0::2]; e = doses[1::2]
            odd.append(float(np.median(o))); even.append(float(np.median(e)))
    if len(odd) < 5:
        return {"n_cases_ge4_epochs": len(odd)}
    r = float(stats.spearmanr(odd, even)[0])
    return {"n_cases_ge4_epochs": len(odd), "splithalf_spearman": round(r, 3)}


def _early_late(per_case_epochs_time):
    """Early->late stability: for cases with >=4 target-band phen-only epochs ORDERED
    BY TIME, correlate the median dose over the EARLIER half vs the LATER half across
    patients. This is the early-identifiability robustness check (a single early window
    should index the later requirement)."""
    import numpy as np
    from scipy import stats
    early, late = [], []
    for cid, doses in per_case_epochs_time.items():
        if len(doses) >= 4:
            h = len(doses) // 2
            early.append(float(np.median(doses[:h]))); late.append(float(np.median(doses[h:])))
    if len(early) < 5:
        return {"n_cases_ge4_epochs": len(early)}
    r = float(stats.spearmanr(early, late)[0])
    return {"n_cases_ge4_epochs": len(early), "early_late_spearman": round(r, 3)}


def model():
    import numpy as np, pandas as pd
    from scipy import stats
    files = _shard_files()
    if not files:
        return {"available": False}
    df = pd.concat([pd.read_csv(p, low_memory=False) for p in files], ignore_index=True)
    df = df.drop_duplicates(["caseid", "t_start", "t_end"], keep="last")
    for c in df.columns:
        if c not in ("caseid", "drug", "sex", "optype"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["caseid"] = df["caseid"].astype(str)
    res = {"seed": SEED, "primary_drug": PRIMARY_DRUG,
           "n_epochs_total": int(len(df)),
           "n_cases_any_epoch": int(df["caseid"].nunique()),
           "target_band": [TARGET_LO, TARGET_HI]}
    # primary: phen-only, target-band, valid per-kg dose
    q = df[(df["drug"] == PRIMARY_DRUG) & (df["phen_only"] == 1) &
           (df["map_mean"].between(TARGET_LO, TARGET_HI)) & df["dose_per_kg"].notna()].copy()
    res["n_qualifying_epochs"] = int(len(q))
    # per-case requirement phenotype = median dose_per_kg in target band
    per_case_doses = {cid: list(g["dose_per_kg"].values) for cid, g in q.groupby("caseid")}
    # time-ordered doses for the early->late split
    per_case_doses_time = {cid: list(g.sort_values("t_start")["dose_per_kg"].values)
                           for cid, g in q.groupby("caseid")}
    pheno = {cid: float(np.median(v)) for cid, v in per_case_doses.items()
             if len(v) >= MIN_EPOCHS_PER_CASE}
    res["n_cases_with_phenotype"] = len(pheno)
    if len(pheno) >= 8:
        vals = np.array(list(pheno.values()))
        vals_pos = vals[vals > 0]
        res["requirement_phenotype_rate_per_kg_units"] = {
            "median": round(float(np.median(vals)), 5),
            "iqr": [round(float(np.percentile(vals, 25)), 5), round(float(np.percentile(vals, 75)), 5)],
            "p10_p90": [round(float(np.percentile(vals, 10)), 5), round(float(np.percentile(vals, 90)), 5)],
            "fold_range_p90_p10": round(float(np.percentile(vals_pos, 90) / np.percentile(vals_pos, 10)), 1)
            if vals_pos.size and np.percentile(vals_pos, 10) > 0 else None}
        res["reliability"] = _icc_splithalf(per_case_doses)
        res["early_to_late"] = _early_late(per_case_doses_time)
        # construct validity: requirement vs cumulative exposure, achieved MAP, SVR
        cum, achieved_map, svr_case = {}, {}, {}
        for cid, g in df[(df["drug"] == PRIMARY_DRUG)].groupby("caseid"):
            gd = g[g["dose_per_kg"].notna()]
            cum[cid] = float((gd["dose_per_kg"] * gd["dur"]).sum())
            achieved_map[cid] = float(g["map_mean"].mean())
            sv = g["svr_mean"].dropna()
            if len(sv):
                svr_case[cid] = float(sv.mean())
        cids = [c for c in pheno if c in cum]
        cv = {}
        if len(cids) >= 8:
            ph = np.array([pheno[c] for c in cids])
            cv["vs_cumulative_exposure_spearman"] = round(float(stats.spearmanr(
                ph, [cum[c] for c in cids])[0]), 3)
            cv["vs_achieved_MAP_spearman"] = round(float(stats.spearmanr(
                ph, [achieved_map[c] for c in cids])[0]), 3)
        svr_ids = [c for c in pheno if c in svr_case]
        if len(svr_ids) >= 6:
            cv["vs_EV1000_SVR_spearman"] = round(float(stats.spearmanr(
                [pheno[c] for c in svr_ids], [svr_case[c] for c in svr_ids])[0]), 3)
            cv["n_svr_overlap"] = len(svr_ids)
        cv["note"] = ("expect: vs cumulative exposure POSITIVE (vasoplegic need more), "
                      "vs achieved MAP <=0, vs EV1000 SVR NEGATIVE (low tone = high requirement)")
        res["construct_validity"] = cv
        # REPLICATION logic (mirrors norepi GO thresholds)
        fold = res["requirement_phenotype_rate_per_kg_units"].get("fold_range_p90_p10") or 0
        relib = res["reliability"].get("splithalf_spearman")
        elate = res["early_to_late"].get("early_late_spearman")
        spread_ok = fold >= 3
        reliable_ok = (relib or 0) >= 0.4
        abundant_ok = len(pheno) >= 25
        earlylate_ok = (elate or 0) >= 0.4
        res["replicates"] = bool(spread_ok and (reliable_ok or earlylate_ok))
        res["verdict"] = (
            (f"REPLICATES -- in PHENYLEPHRINE (independent alpha-1 agent), a stable-epoch "
             f"dose-REQUIREMENT phenotype exists in {len(pheno)} patients, varies ~{fold}-fold "
             f"between patients (p10-p90), split-half reliability {relib}, and early-half->late-half "
             f"Spearman {elate}. The norepinephrine finding is NOT norepi-specific: the requirement "
             f"is a reproducible patient-level vasoconstrictor trait."
             + ("" if abundant_ok else
                f" (N={len(pheno)} below the 25-case abundance bar from the norepi build -- "
                f"replication on spread+reliability holds, but N is modest; collect more.)"))
            if res["replicates"] else
            (f"DOES NOT YET REPLICATE -- {len(pheno)} PHEN phenotype cases; spread fold-range "
             f"{fold}, split-half reliability {relib}, early->late {elate}. "
             f"Need more cases / stronger reliability before declaring the requirement reproduces "
             f"in phenylephrine."))
    else:
        res["verdict"] = (f"INSUFFICIENT -- only {len(pheno)} PHEN cases with >= {MIN_EPOCHS_PER_CASE} "
                          f"target-band phen-only epochs so far (extraction may be incomplete).")
    return res


def _doc(res):
    L = ["# Internal replication: stable-epoch dose-REQUIREMENT in PHENYLEPHRINE (PHEN)\n",
         "Tests whether the norepinephrine stable-epoch dose-REQUIREMENT finding "
         "(docs/PRESSOR_REQUIREMENT.md: split-half reliability 0.82, ~5.6x between-patient spread, "
         "early-half predicts late-half +0.54) REPLICATES in an INDEPENDENT drug -- phenylephrine, "
         "a pure alpha-1 agonist that raises MAP purely via SVR. Same machinery: PHEN-only stable "
         f"constant-infusion epochs (>= {int(MIN_EPOCH)} s, {int(SETTLE)} s settle), MAP target band "
         f"[{TARGET_LO}, {TARGET_HI}], dose_per_kg = rate/weight, same split-half reliability + p90/p10 "
         "spread + time-split early->late computations.\n"]
    if not res.get("available", True):
        L.append("_no epochs extracted yet._")
        open(os.path.join(_DOCS, "PRESSOR_REQUIREMENT_PHEN.md"), "w").write("\n".join(L) + "\n"); return
    L += [f"- Stable PHEN epochs extracted: **{res['n_epochs_total']}** over "
          f"**{res['n_cases_any_epoch']}** cases.",
          f"- Qualifying PHEN-only target-band epochs: **{res.get('n_qualifying_epochs')}**; "
          f"cases with a requirement phenotype (>= {MIN_EPOCHS_PER_CASE} epochs): "
          f"**{res.get('n_cases_with_phenotype')}**.\n"]
    ph = res.get("requirement_phenotype_rate_per_kg_units")
    if ph:
        L += ["## Requirement phenotype (PHEN rate / kg to hold target MAP)",
              f"- median {ph['median']}, IQR {ph['iqr']}, p10-p90 {ph['p10_p90']}, "
              f"**between-patient fold-range (p90/p10) = {ph['fold_range_p90_p10']}**.",
              f"- **Reliability (within-patient split-half):** {res.get('reliability')}.",
              f"- **Early-half -> late-half (time split):** {res.get('early_to_late')}.",
              f"- **Construct validity:** {res.get('construct_validity')}.\n",
              "## Replication verdict vs norepinephrine",
              "| metric | norepinephrine | phenylephrine (this) |",
              "| --- | --- | --- |",
              f"| N phenotype cases | 52 | {res.get('n_cases_with_phenotype')} |",
              f"| split-half reliability | 0.82 | {res.get('reliability',{}).get('splithalf_spearman')} |",
              f"| spread p90/p10 | 5.6 | {ph['fold_range_p90_p10']} |",
              f"| early->late Spearman | +0.54 | {res.get('early_to_late',{}).get('early_late_spearman')} |\n",
              res.get("verdict", ""), ""]
    else:
        L += ["## Verdict", res.get("verdict", ""), ""]
    L += ["## Caveats",
          "- **Dose units:** Orchestra RATE is device units (mL/h); absolute ug/kg/min needs the "
          "per-case drug concentration VitalDB does not expose. Between-patient comparison assumes a "
          "comparable standard institutional phenylephrine mix; the split-half reliability is "
          "concentration-invariant within a case.",
          "- **Independent agent, same patient pool:** PHEN is mechanistically independent of NEPI "
          "(pure alpha-1 vs mixed alpha/beta), so a positive replication is evidence the requirement "
          "is a drug-agnostic vasoconstrictor trait, not a norepi-specific artifact. Patients may "
          "overlap with the norepi cohort; this is an internal (same-centre) replication, not external.",
          "- **Single-centre (SNUH/VitalDB);** external replication on another database still required.",
          "- N may be modest: phenylephrine is more often given as boluses than as long constant "
          "infusions, so qualifying stable epochs are scarcer than for norepinephrine."]
    open(os.path.join(_DOCS, "PRESSOR_REQUIREMENT_PHEN.md"), "w").write("\n".join(L) + "\n")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=int(os.environ.get("PHEN_LIMIT", "130")))
    ap.add_argument("--model-only", action="store_true")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    a = ap.parse_args()
    if not a.model_only:
        extract(a.limit, shard=a.shard, nshards=a.nshards)
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "pressor_requirement_phen.json"), "w"),
              indent=2, default=float)
    _doc(res)
    print("\n[phen] VERDICT: " + res.get("verdict", "no data"), flush=True)
    print("[phen] -> docs/PRESSOR_REQUIREMENT_PHEN.md", flush=True)


if __name__ == "__main__":
    main()
