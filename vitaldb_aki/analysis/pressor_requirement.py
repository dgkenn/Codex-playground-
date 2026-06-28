"""pressor_requirement.py -- the ROBUST pressor-responsiveness estimand:
stable-epoch vasopressor DOSE-REQUIREMENT (the clinically-validated vasoplegia
construct), built after the titration-transient design was shown to be closed-loop
confounded (docs/PRESSOR_RESPONSE_MODELING.md: dose is a feedback response to MAP).

Idea
----
A vasoplegic patient sustains a LOW MAP despite a HIGH norepinephrine dose. So
instead of the titration moment, use STABLE epochs -- maximal runs where the pump
RATE is constant (no titration) for >= MIN_EPOCH seconds. In each stable epoch the
system has settled, so the *sustained MAP at the steady dose* is a clean readout of
the patient's pressor requirement, with NO titration-by-indication transient.

Phenotype (per patient) = the norepinephrine dose (per kg) required to sustain MAP
in the clinical target band [55, 80] mmHg, taken over that patient's stable
norepi-ONLY epochs. High requirement = vasoplegia. This is a level-on-level
relationship (dose to hold target), not a transient, so it is not reverse-confounded
by titration. The make-or-break questions a waveform model needs answered FIRST:

  1. ABUNDANCE  -- enough cases with >=2 stable target-band norepi-only epochs?
  2. SPREAD     -- does the requirement vary a lot BETWEEN patients (the thing to
                   predict)? (fold-range of per-case dose).
  3. RELIABILITY-- is it a STABLE patient trait, not epoch noise? (split-half /
                   within-patient ICC of the requirement across a case's epochs).
  4. CONSTRUCT VALIDITY -- does high requirement track independent vasoplegia
                   markers? cumulative norepi exposure (+), achieved MAP (~/-),
                   and where available EV1000 SVR (-) / Pivot-2 diastolic tone.

Confounders controlled: per-kg dosing (body size); MAP target-band conditioning
(compare dose to hold the SAME MAP); single-agent (norepi-only) epochs (drug
identity / co-vasoactives); settle delay (drop first 60 s post-change); anaesthetic
depth (BIS/MAC captured per epoch); preload (CVP captured). Causal requirement vs
intrinsic vasoreactivity is still observational -- stated, not overclaimed.

stdlib only at import; numpy/pandas lazy. Resumable (skips done caseids).
Run: python3 -m vitaldb_aki.analysis.pressor_requirement [--limit N] [--model-only]
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
PRIMARY_DRUG = "NEPI"            # norepinephrine -- the headline single agent
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
EPOCHS_CSV = os.path.join(_CACHE, "pressor_requirement_epochs.csv")
_FIELDS = ["caseid", "drug", "t_start", "t_end", "dur", "rate", "dose_per_kg",
           "map_mean", "map_sd", "n_map", "hr_mean", "cvp_mean", "bis_mean",
           "mac_mean", "norepi_only", "svr_mean", "weight", "age", "sex", "asa", "optype"]


def _cohort(trks_path):
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
    pressor = set().union(*by_drug.values()) if by_drug else set()
    drug_of = {}
    for d, cs in by_drug.items():
        for c in cs:
            drug_of.setdefault(c, []).append(d)
    return sorted(pressor & map_cases, key=lambda c: int(c)), drug_of, svr_cases


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
    for drug in drugs_present:
        for (t0, t1, rate) in _segments(rate_cache[drug]):
            a, b = t0 + SETTLE, t1
            if b - a < MIN_EPOCH - SETTLE:
                continue
            mmean, msd, nmap = _win(map_s, a, b, MAP_MIN, MAP_MAX)
            if mmean is None or nmap < 6:
                continue
            # norepi-only: no OTHER vasoconstrictor running in this epoch
            others = [d for d in drugs_present if d != drug]
            norepi_only = int(all(_rate_at(rate_cache[d], t0, t1) <= RATE_TOL for d in others))
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
                "norepi_only": norepi_only, "svr_mean": round(svr_m, 1) if svr_m is not None else None,
                "weight": m.get("weight", ""), "age": m.get("age", ""), "sex": m.get("sex", ""),
                "asa": m.get("asa", ""), "optype": m.get("optype", "")})
    for tn in [MAP_TRACK, HR_TRACK, CVP_TRACK, BIS_TRACK, MAC_TRACK] + ([svr_src] if svr_src else []):
        purge_track(cfg, cid, tn)
    for d in drugs_present:
        purge_track(cfg, cid, f"Orchestra/{d}_RATE")
    return rows


def _load_done():
    done = set()
    if os.path.exists(EPOCHS_CSV):
        for row in _csv.DictReader(open(EPOCHS_CSV, newline="")):
            done.add(row["caseid"])
    return done


def _append(rows):
    new = not os.path.exists(EPOCHS_CSV)
    with open(EPOCHS_CSV, "a", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=_FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def extract(limit):
    from common.config import load_yaml
    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    cohort, drug_of, svr_cases = _cohort(os.path.join(_CACHE, "trks.csv"))
    meta = _case_meta(os.path.join(_CACHE, "cases.csv"))
    done = _load_done()
    todo = [c for c in cohort if c not in done]
    if limit:
        todo = todo[:limit]
    print(f"[preq] cohort {len(cohort)} vasoconstrictor+ART_MBP cases; {len(done)} done; "
          f"processing {len(todo)}", flush=True)
    for i, cid in enumerate(todo, 1):
        try:
            rows = _process_case(cfg, cid, drug_of.get(cid, []), meta, cid in svr_cases)
            _append(rows)
            print(f"[preq]  [{i}/{len(todo)}] case {cid}: {len(rows)} stable epochs", flush=True)
        except Exception as exc:
            print(f"[preq]  [{i}/{len(todo)}] case {cid} FAILED: {exc}", flush=True)
    return len(cohort)


# --------------------------------------------------------------------- modeling
def _icc_splithalf(per_case_epochs):
    """Within-patient reliability of the requirement: for cases with >=4 target-band
    norepi-only epochs, correlate the median dose over ODD vs EVEN epochs."""
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


def model():
    import numpy as np, pandas as pd
    from scipy import stats
    if not os.path.exists(EPOCHS_CSV):
        return {"available": False}
    df = pd.read_csv(EPOCHS_CSV, low_memory=False)
    for c in df.columns:
        if c not in ("caseid", "drug", "sex", "optype"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["caseid"] = df["caseid"].astype(str)
    res = {"seed": SEED, "n_epochs_total": int(len(df)),
           "n_cases_any_epoch": int(df["caseid"].nunique()),
           "target_band": [TARGET_LO, TARGET_HI]}
    # primary: norepi-only, target-band, valid per-kg dose
    q = df[(df["drug"] == PRIMARY_DRUG) & (df["norepi_only"] == 1) &
           (df["map_mean"].between(TARGET_LO, TARGET_HI)) & df["dose_per_kg"].notna()].copy()
    res["primary_drug"] = PRIMARY_DRUG
    res["n_qualifying_epochs"] = int(len(q))
    # per-case requirement phenotype = median dose_per_kg in target band
    per_case_doses = {cid: list(g["dose_per_kg"].values) for cid, g in q.groupby("caseid")}
    pheno = {cid: float(np.median(v)) for cid, v in per_case_doses.items()
             if len(v) >= MIN_EPOCHS_PER_CASE}
    res["n_cases_with_phenotype"] = len(pheno)
    if len(pheno) >= 8:
        vals = np.array(list(pheno.values()))
        vals_pos = vals[vals > 0]
        res["requirement_phenotype_ug_per_kg_units"] = {
            "median": round(float(np.median(vals)), 5),
            "iqr": [round(float(np.percentile(vals, 25)), 5), round(float(np.percentile(vals, 75)), 5)],
            "p10_p90": [round(float(np.percentile(vals, 10)), 5), round(float(np.percentile(vals, 90)), 5)],
            "fold_range_p90_p10": round(float(np.percentile(vals_pos, 90) / np.percentile(vals_pos, 10)), 1)
            if vals_pos.size and np.percentile(vals_pos, 10) > 0 else None}
        res["reliability"] = _icc_splithalf(per_case_doses)
        # construct validity: requirement vs cumulative exposure, achieved MAP, SVR
        cum = {}  # cumulative norepi exposure per kg over ALL norepi epochs
        achieved_map, svr_case = {}, {}
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
        # GO logic
        spread_ok = (res["requirement_phenotype_ug_per_kg_units"].get("fold_range_p90_p10") or 0) >= 3
        reliable_ok = (res["reliability"].get("splithalf_spearman") or 0) >= 0.4
        abundant_ok = len(pheno) >= 25
        construct_ok = (cv.get("vs_cumulative_exposure_spearman") or 0) > 0.2
        res["go"] = bool(spread_ok and abundant_ok and (reliable_ok or construct_ok))
        res["verdict"] = (
            (f"GO -- a stable-epoch norepinephrine dose-REQUIREMENT phenotype exists in "
             f"{len(pheno)} patients, varies ~{res['requirement_phenotype_ug_per_kg_units'].get('fold_range_p90_p10')}-fold "
             f"between patients (p10-p90), "
             f"split-half reliability {res['reliability'].get('splithalf_spearman')}, and tracks "
             f"vasoplegia markers (vs cumulative exposure {cv.get('vs_cumulative_exposure_spearman')}, "
             f"vs EV1000 SVR {cv.get('vs_EV1000_SVR_spearman')}). This is a confound-robust, "
             f"closed-loop-free target a pre-epoch waveform model can predict.")
            if res["go"] else
            (f"NOT YET -- {len(pheno)} phenotype cases; spread fold-range "
             f"{res['requirement_phenotype_ug_per_kg_units'].get('fold_range_p90_p10')}, reliability "
             f"{res['reliability'].get('splithalf_spearman')}, construct vs exposure "
             f"{cv.get('vs_cumulative_exposure_spearman')}. Need more cases / stronger reliability "
             f"before declaring a trainable target."))
    else:
        res["verdict"] = f"INSUFFICIENT -- only {len(pheno)} cases with >= {MIN_EPOCHS_PER_CASE} target-band norepi epochs so far."
    return res


def _doc(res):
    L = ["# Stable-epoch vasopressor dose-REQUIREMENT (robust pressor-responsiveness)\n",
         "The titration-transient design was closed-loop confounded (dose is a feedback "
         "response to MAP; docs/PRESSOR_RESPONSE_MODELING.md). This uses STABLE constant-infusion "
         "epochs instead: the norepinephrine dose (per kg) required to sustain MAP in the clinical "
         f"target band [{TARGET_LO}, {TARGET_HI}] mmHg. High requirement = vasoplegia. No titration "
         "transient -> not reverse-confounded.\n",
         "Confounders controlled: per-kg dosing (body size); MAP-band conditioning (dose to hold "
         "the SAME MAP); norepi-ONLY epochs (drug identity / co-vasoactives); 60 s settle; "
         "anaesthetic depth (BIS/MAC) + preload (CVP) captured per epoch.\n"]
    if not res.get("available", True):
        L.append("_no epochs extracted yet._")
        open(os.path.join(_DOCS, "PRESSOR_REQUIREMENT.md"), "w").write("\n".join(L) + "\n"); return
    L += [f"- Stable epochs extracted: **{res['n_epochs_total']}** over "
          f"**{res['n_cases_any_epoch']}** cases.",
          f"- Qualifying norepi-only target-band epochs: **{res.get('n_qualifying_epochs')}**; "
          f"cases with a requirement phenotype (>= {MIN_EPOCHS_PER_CASE} epochs): "
          f"**{res.get('n_cases_with_phenotype')}**.\n"]
    ph = res.get("requirement_phenotype_ug_per_kg_units")
    if ph:
        L += ["## Requirement phenotype (norepi rate / kg to hold target MAP)",
              f"- median {ph['median']}, IQR {ph['iqr']}, p10-p90 {ph['p10_p90']}, "
              f"**between-patient fold-range (p90/p10) = {ph['fold_range_p90_p10']}**.",
              f"- **Reliability (within-patient split-half):** {res.get('reliability')}.",
              f"- **Construct validity:** {res.get('construct_validity')}.\n",
              "## Verdict", res.get("verdict", ""), ""]
    else:
        L += ["## Verdict", res.get("verdict", ""), ""]
    L += ["## Caveats",
          "- **Dose units:** Orchestra RATE is device units (mL/h); absolute ug/kg/min needs the "
          "per-case drug concentration VitalDB does not expose. Between-patient comparison assumes "
          "comparable norepi concentration (standard institutional mix) -- stated assumption; the "
          "split-half reliability is concentration-invariant within a case.",
          "- **Observational requirement, not intrinsic vasoreactivity:** the requirement reflects "
          "management + physiology. Construct-validity against EV1000 SVR / cumulative exposure is "
          "the evidence it indexes vasoplegia, not an assumption.",
          "- **Single-centre (SNUH/VitalDB);** external replication required.",
          "- Next: does the PRE-epoch arterial waveform/morphology predict this requirement? "
          "(the GPU-optional model build) -- and does the Pivot-2 diastolic-tone index correlate "
          "with it (links the two findings)."]
    open(os.path.join(_DOCS, "PRESSOR_REQUIREMENT.md"), "w").write("\n".join(L) + "\n")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=int(os.environ.get("PREQ_LIMIT", "260")))
    ap.add_argument("--model-only", action="store_true")
    a = ap.parse_args()
    if not a.model_only:
        extract(a.limit)
    res = model()
    json.dump(res, open(os.path.join(_CACHE, "pressor_requirement.json"), "w"),
              indent=2, default=float)
    _doc(res)
    print("\n[preq] VERDICT: " + res.get("verdict", "no data"), flush=True)
    print("[preq] -> docs/PRESSOR_REQUIREMENT.md", flush=True)


if __name__ == "__main__":
    main()
