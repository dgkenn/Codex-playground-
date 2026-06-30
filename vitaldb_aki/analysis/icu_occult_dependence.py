"""ICU occult vasopressor dependence at normal pressure — the novel top-tier test.

The control-theory claim, made testable where the mechanism actually holds (the ICU, where
pressors are titrated to a MAP target so MAP is held near-constant): among patients whose MAP is
AT TARGET, does the vasopressor REQUIREMENT still stratify mortality? If so, the reassuring
pressure conceals risk that lives in the dose — a monitoring error VIS does not capture (VIS does
not condition on MAP being regulated) and that the dead cross-encounter "trait" never claimed.

This module needs per-stay MAP from MIMIC chartevents (itemids 220052 ABPm / 225312 ART BP mean /
220181 NBPm), stream-filtered to the pressor cohort's first-24h window (scratchpad/mimic_map_raw.csv:
stay_id,charttime,itemid,valuenum). It reuses the validated first-24h NEE from finding4_landmark.

Outputs cache/icu_occult_dependence.json + docs/ICU_OCCULT_DEPENDENCE.md. Heavy deps lazy.

Tests run:
  (A) CONTROL-THEORY PREMISE IN THE ICU (closes Round-1 causal Issue 1): within-stay MAP CV vs
      NEE-rate CV over the first 24h — is MAP CV << dose CV in the ICU, as in VitalDB?
  (B) OCCULT DEPENDENCE: restrict to AT-TARGET-MAP stays (median first-24h MAP in [65,85] AND
      low time-below-65); does the first-24h requirement stratify post-24h mortality (landmark)?
      Head-to-head: requirement-within-band vs MAP-within-band for mortality (AUC + OR).
  (C) INFORMATION CONTENT: incremental AUC of requirement over MAP (and vice versa) for mortality,
      overall and within the at-target stratum.
"""
import os
import csv as _csv
import json
import datetime as _dt

from finding4_landmark import (
    _load_links_with_death, _nee_first_window, _load_lactate, _adj_or_per_sd,
    _quartile_gradient, LANDMARK_H,
)
from resuscitation_balance_crossval import _parse_dt, _CACHE

MAP_RAW = os.path.join(os.environ.get("MAP_RAW_DIR", "/tmp"), "mimic_map_raw.csv")
OUT_JSON = os.path.join(_CACHE, "icu_occult_dependence.json")
INVASIVE = {"220052", "225312"}   # arterial-line means (regulated-to-target)
NONINVASIVE = {"220181"}


def _map_first24(stay_link, map_path):
    """Per-stay first-24h MAP summary from the stream-filtered chartevents MAP file.
    Prefers invasive arterial means; falls back to NBP. Returns
    {stay_id: {map_median, map_cv, n_map, frac_below_65, invasive}}."""
    import numpy as np
    vals = {}  # sid -> list of (charttime, valuenum, is_invasive)
    if not os.path.exists(map_path):
        raise FileNotFoundError(f"MAP file not found: {map_path}")
    with open(map_path, newline="") as fh:
        for row in _csv.reader(fh):
            if len(row) < 4:
                continue
            sid, ct, iid, v = row[0], row[1], row[2], row[3]
            link = stay_link.get(sid)
            if link is None or link["intime"] is None:
                continue
            t = _parse_dt(ct)
            if t is None:
                continue
            hrs = (t - link["intime"]).total_seconds() / 3600.0
            if hrs < 0 or hrs > LANDMARK_H:
                continue
            try:
                fv = float(v)
            except ValueError:
                continue
            if fv < 10 or fv > 200:  # physiologic gate for a mean pressure
                continue
            vals.setdefault(sid, []).append((iid in INVASIVE, fv))
    out = {}
    for sid, lst in vals.items():
        inv = [v for isinv, v in lst if isinv]
        use = inv if len(inv) >= 3 else [v for _, v in lst]
        if len(use) < 3:
            continue
        arr = np.asarray(use, float)
        m = float(arr.mean())
        out[sid] = {
            "map_median": float(np.median(arr)),
            "map_mean": m,
            "map_cv": float(arr.std() / m) if m > 0 else None,
            "n_map": int(arr.size),
            "frac_below_65": float((arr < 65).mean()),
            "invasive": len(inv) >= 3,
        }
    return out


def _nee_rate_cv(stay_link, dopamine_weight=0.01):
    """Per-stay CV of the NEE infusion RATE over first-24h segments (for the control-theory
    premise: compare to MAP CV). Reuses the segment-level conversion via a light re-stream."""
    # _nee_first_window returns peak/load; for CV we need the rate series, so recompute inline
    import numpy as np
    from finding4_landmark import PRESSORS, VASO_NEE_PER_UNIT_MIN, FLUID_FILTERED
    rates = {}
    with open(FLUID_FILTERED, newline="") as fh:
        for row in _csv.DictReader(fh):
            sid = row["stay_id"]
            link = stay_link.get(sid)
            if link is None or link["intime"] is None:
                continue
            try:
                iid = int(row["itemid"])
            except (ValueError, TypeError):
                continue
            name, wgt = PRESSORS.get(iid, (None, None))
            if name is None:
                continue
            if name == "dopamine":
                wgt = dopamine_weight
            try:
                rate = float(row["rate"])
            except (ValueError, TypeError):
                continue
            if rate <= 0:
                continue
            t0 = _parse_dt(row["starttime"])
            if t0 is None:
                continue
            hrs = (t0 - link["intime"]).total_seconds() / 3600.0
            if hrs < 0 or hrs > LANDMARK_H:
                continue
            uom = (row.get("rateuom") or "").strip().lower()
            if name == "vasopressin":
                if uom == "units/hour":
                    upm = rate / 60.0
                elif uom == "units/min":
                    upm = rate
                else:
                    continue
                if upm <= 0 or upm > 1.0:
                    continue
                nee = VASO_NEE_PER_UNIT_MIN * upm
            else:
                if uom != "mcg/kg/min" or rate > 5:
                    continue
                nee = wgt * rate
            rates.setdefault(sid, []).append(nee)
    out = {}
    for sid, r in rates.items():
        if len(r) < 3:
            continue
        a = np.asarray(r, float)
        m = a.mean()
        out[sid] = float(a.std() / m) if m > 0 else None
    return out


def _oof_auc(x, y):
    """5-fold out-of-fold AUC of a 1-col logistic (x can be 1 or 2 col)."""
    import numpy as np
    x = np.asarray(x, float)
    if x.ndim == 1:
        x = x[:, None]
    y = np.asarray(y, float)
    n = len(y)
    rng = np.random.RandomState(7)
    idx = rng.permutation(n)
    folds = np.array_split(idx, 5)
    pred = np.zeros(n)

    def fit(Xtr, ytr):
        Xtr = np.column_stack([np.ones(len(Xtr)), Xtr])
        b = np.zeros(Xtr.shape[1])
        for _ in range(60):
            eta = np.clip(Xtr @ b, -30, 30)
            p = 1 / (1 + np.exp(-eta))
            W = np.clip(p * (1 - p), 1e-6, None)
            z = eta + (ytr - p) / W
            try:
                b = np.linalg.solve((Xtr.T * W) @ Xtr, (Xtr.T * W) @ z)
            except np.linalg.LinAlgError:
                break
        return b

    for f in range(5):
        te = folds[f]
        tr = np.concatenate([folds[g] for g in range(5) if g != f])
        # standardize on train
        mu = x[tr].mean(0); sd = x[tr].std(0); sd[sd == 0] = 1
        b = fit((x[tr] - mu) / sd, y[tr])
        Xte = np.column_stack([np.ones(len(te)), (x[te] - mu) / sd])
        pred[te] = 1 / (1 + np.exp(-np.clip(Xte @ b, -30, 30)))
    # AUC
    pos = pred[y == 1]; neg = pred[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty_like(order, float); ranks[order] = np.arange(1, len(order) + 1)
    auc = (ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
    return float(auc)


def model(dopamine_weight=0.01, band=(65.0, 85.0), max_frac_below=0.10):
    import numpy as np
    stay_link, hadm_death, subj_age = _load_links_with_death()
    lac = _load_lactate()
    nee = _nee_first_window(stay_link, dopamine_weight=dopamine_weight)
    mapsum = _map_first24(stay_link, MAP_RAW)
    necv = _nee_rate_cv(stay_link, dopamine_weight=dopamine_weight)

    # ---- (A) control-theory premise in the ICU: MAP CV vs NEE-rate CV ----
    paired = [(mapsum[s]["map_cv"], necv[s]) for s in mapsum
              if s in necv and mapsum[s]["map_cv"] is not None and necv[s] is not None]
    premise = None
    if paired:
        mcv = np.array([p[0] for p in paired]); dcv = np.array([p[1] for p in paired])
        premise = {"n": len(paired), "map_cv_median": round(float(np.median(mcv)), 4),
                   "nee_rate_cv_median": round(float(np.median(dcv)), 4),
                   "ratio_dose_over_map": round(float(np.median(dcv) / np.median(mcv)), 2)}

    # ---- assemble landmark cohort with MAP ----
    rows = []
    for sid, s in nee.items():
        if not s["has_pressor"] or sid not in mapsum:
            continue
        link = stay_link.get(sid)
        if link is None:
            continue
        flag, dtime = hadm_death.get(link["hadm"], ("0", None))
        landmark = link["intime"] + _dt.timedelta(hours=LANDMARK_H)
        if dtime is not None and dtime <= landmark:
            continue  # landmark: alive at 24h
        a = subj_age.get(link["subject"])
        if a is None or not np.isfinite(a):
            continue
        ms = mapsum[sid]
        rows.append({"nee": s["nee_load"], "lognee": float(np.log1p(s["nee_load"])),
                     "map_med": ms["map_median"], "frac_lo": ms["frac_below_65"],
                     "age": a, "lac": lac.get(link["hadm"]),
                     "died": 1.0 if str(flag) == "1" else 0.0})
    n = len(rows)

    def col(k):
        return [r[k] for r in rows]

    # ---- (C) information content overall ----
    y = col("died")
    auc_map = _oof_auc(col("map_med"), y)
    auc_req = _oof_auc(col("lognee"), y)
    auc_both = _oof_auc(list(zip(col("map_med"), col("lognee"))), y)

    # ---- (B) occult dependence: AT-TARGET-MAP stratum ----
    at = [r for r in rows if band[0] <= r["map_med"] <= band[1] and r["frac_lo"] <= max_frac_below]
    occult = None
    if len(at) > 200:
        yat = [r["died"] for r in at]
        req_at = [r["lognee"] for r in at]
        map_at = [r["map_med"] for r in at]
        grad = _quartile_gradient([r["nee"] for r in at], yat)
        or_req = _adj_or_per_sd(req_at, yat, [[r["age"] for r in at]])
        # lactate-adjusted within band
        lmask = [i for i in range(len(at)) if at[i]["lac"] is not None]
        or_req_lac = None
        if len(lmask) > 100:
            or_req_lac = _adj_or_per_sd([req_at[i] for i in lmask], [yat[i] for i in lmask],
                                        [[at[i]["age"] for i in lmask], [at[i]["lac"] for i in lmask]])
            or_req_lac["subset_n"] = len(lmask)
        occult = {
            "band": band, "max_frac_below_65": max_frac_below, "n_at_target": len(at),
            "mortality_at_target": round(float(np.mean(yat)), 4),
            "requirement_quartile_gradient": grad,
            "requirement_OR_per_sd_age_adj": or_req,
            "requirement_OR_per_sd_age_lactate_adj": or_req_lac,
            "auc_requirement_within_band": _oof_auc(req_at, yat),
            "auc_MAP_within_band": _oof_auc(map_at, yat),
        }

    return {
        "n_landmark_with_MAP": n,
        "control_theory_premise_ICU": premise,
        "information_content": {
            "auc_MAP_alone": auc_map, "auc_requirement_alone": auc_req,
            "auc_MAP_plus_requirement": auc_both,
            "delta_auc_req_over_map": round(auc_both - auc_map, 4) if (auc_both and auc_map) else None,
        },
        "occult_dependence_at_target": occult,
    }


def run():
    out = model()
    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=2)
    return out


if __name__ == "__main__":
    import pprint
    pprint.pprint(run())
