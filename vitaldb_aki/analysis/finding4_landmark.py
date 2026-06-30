"""Finding 4 landmark test -- the red-team "make-or-break" analysis.

Reviewer critique (REDTEAM_PUB_FINDING4.md, CRITICAL-1): the headline NEE total
load is integrated over the WHOLE stay, so dying patients accumulate vasopressor-
minutes up to the moment of death -- exposure and outcome are coterminous, and the
OR 3.18/SD may be a near-identity ("dying patients get more pressor"). The mandatory
missing analysis is a LANDMARK design: measure NEE over the FIRST 24h only, restrict
to patients ALIVE at the 24h landmark, and predict SUBSEQUENT in-hospital mortality.

This module does exactly that, reusing the validated NEE conversion (PRESSORS,
VASO_NEE_PER_UNIT_MIN, gates) from resuscitation_balance_crossval so the only thing
that changes vs the headline is the time window + alive-at-landmark restriction.

Also addresses CRITICAL-3 (thin adjustment): reports age-only AND age+lactate ORs,
and a dopamine-NEE-weight sensitivity (0.01 vs 0.05) for the MODERATE concern.

Outputs cache/finding4_landmark.json and docs/FINDING4_LANDMARK.md. stdlib + numpy/
scipy only; heavy deps lazy. MIMIC_RAW must point at the dir with icustays/admissions/
patients .csv.gz (default env or scratchpad).
"""
import os
import csv as _csv
import gzip
import json
import datetime as _dt

from resuscitation_balance_crossval import (
    PRESSORS, DOBUTAMINE, VASO_NEE_PER_UNIT_MIN, CRYSTALLOID, COLLOID,
    FLUID_FILTERED, LABS_CSV, MIMIC_RAW, _parse_dt, _CACHE,
)

LANDMARK_H = 24.0  # landmark at 24h after ICU intime
OUT_JSON = os.path.join(_CACHE, "finding4_landmark.json")


def _load_links_with_death():
    """stay_id -> {hadm, subject, intime}; hadm -> (expire_flag, deathtime);
    subject -> age. deathtime is parsed datetime or None."""
    icu = os.path.join(MIMIC_RAW, "icustays.csv.gz")
    adm = os.path.join(MIMIC_RAW, "admissions.csv.gz")
    pat = os.path.join(MIMIC_RAW, "patients.csv.gz")
    if not all(os.path.exists(p) for p in (icu, adm, pat)):
        raise FileNotFoundError(f"icustays/admissions/patients missing under {MIMIC_RAW}")
    stay_link = {}
    with gzip.open(icu, "rt") as fh:
        for row in _csv.DictReader(fh):
            stay_link[row["stay_id"]] = {
                "hadm": row["hadm_id"], "subject": row["subject_id"],
                "intime": _parse_dt(row["intime"]),
            }
    hadm_death = {}
    with gzip.open(adm, "rt") as fh:
        for row in _csv.DictReader(fh):
            hadm_death[row["hadm_id"]] = (
                row.get("hospital_expire_flag", "0"),
                _parse_dt(row.get("deathtime")),
            )
    subj_age = {}
    with gzip.open(pat, "rt") as fh:
        for row in _csv.DictReader(fh):
            try:
                subj_age[row["subject_id"]] = float(row.get("anchor_age") or "nan")
            except ValueError:
                subj_age[row["subject_id"]] = None
    return stay_link, hadm_death, subj_age


def _nee_first_window(stay_link, dopamine_weight=0.01):
    """Per-stay NEE load + peak accumulated ONLY over [intime, intime+24h].

    Identical conversion/gates to the headline _stay_aggregate, but each segment is
    kept only if its starttime falls in the first-24h window. dopamine_weight lets us
    run the 0.01 (headline) vs 0.05 (literature) sensitivity."""
    import numpy as np
    stay = {}
    with open(FLUID_FILTERED, newline="") as fh:
        for row in _csv.DictReader(fh):
            sid = row["stay_id"]
            if not sid:
                continue
            link = stay_link.get(sid)
            if link is None or link["intime"] is None:
                continue
            try:
                iid = int(row["itemid"])
            except (ValueError, TypeError):
                continue
            name, wgt = PRESSORS.get(iid, (None, None))
            if name is None:
                continue  # landmark test is NEE-only; fluids irrelevant here
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
            # ---- first-24h window gate (the landmark restriction) ----
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
                nee_rate = VASO_NEE_PER_UNIT_MIN * upm
            else:
                if uom != "mcg/kg/min":
                    continue
                if rate > 5:
                    continue
                nee_rate = wgt * rate
            t1 = _parse_dt(row.get("endtime"))
            dur = None
            if t1 is not None:
                # clip segment end to the landmark so load is strictly first-24h
                end = min(t1, link["intime"] + _dt.timedelta(hours=LANDMARK_H))
                dur = (end - t0).total_seconds() / 60.0
                if dur <= 0 or dur > 24 * 60:
                    dur = None
            d = stay.setdefault(sid, {"rates": [], "loads": []})
            d["rates"].append(nee_rate)
            d["loads"].append(nee_rate * dur if dur is not None else None)
    out = {}
    for sid, d in stay.items():
        loads = [x for x in d["loads"] if x is not None]
        out[sid] = {
            "nee_peak": float(np.max(d["rates"])) if d["rates"] else 0.0,
            "nee_load": float(np.sum(loads)) if loads else (
                float(np.sum(d["rates"])) if d["rates"] else 0.0),
            "has_pressor": len(d["rates"]) > 0,
        }
    return out


def _load_lactate():
    lac = {}
    if not os.path.exists(LABS_CSV):
        return lac
    with open(LABS_CSV, newline="") as fh:
        for row in _csv.DictReader(fh):
            v = row.get("lactate")
            if v not in (None, "", "nan"):
                try:
                    lac[row["hadm_id"]] = float(v)
                except ValueError:
                    pass
    return lac


def _adj_or_per_sd(x, y, covars):
    """Age(+covars)-adjusted logistic OR per SD of x, with 95% CI by bootstrap.
    x is log1p(NEE); covars is a list of equal-length arrays (or empty)."""
    import numpy as np
    from scipy import stats  # noqa: F401 (kept for parity / availability check)
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    sd = x.std()
    if sd == 0:
        return None
    cols = [(x - x.mean()) / sd]
    for c in covars:
        c = np.asarray(c, float)
        cs = c.std()
        cols.append((c - c.mean()) / cs if cs > 0 else c - c.mean())
    X = np.column_stack([np.ones(len(x))] + cols)

    def _fit(Xm, ym):
        b = np.zeros(Xm.shape[1])
        for _ in range(100):
            eta = Xm @ b
            p = 1.0 / (1.0 + np.exp(-np.clip(eta, -30, 30)))
            W = p * (1 - p)
            W = np.clip(W, 1e-6, None)
            z = eta + (ym - p) / W
            try:
                b_new = np.linalg.solve((Xm.T * W) @ Xm, (Xm.T * W) @ z)
            except np.linalg.LinAlgError:
                break
            if np.max(np.abs(b_new - b)) < 1e-8:
                b = b_new
                break
            b = b_new
        return b

    b = _fit(X, y)
    or_sd = float(np.exp(b[1]))
    # bootstrap CI (subject-agnostic stay-level; matches headline method)
    rng = np.random.RandomState(12345)
    bs = []
    n = len(y)
    for _ in range(400):
        idx = rng.randint(0, n, n)
        try:
            bb = _fit(X[idx], y[idx])
            bs.append(np.exp(bb[1]))
        except Exception:
            continue
    ci = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))] if bs else None
    return {"or_per_sd": round(or_sd, 3), "ci": [round(c, 3) for c in ci] if ci else None,
            "n": n}


def _quartile_gradient(nee, y):
    import numpy as np
    nee = np.asarray(nee, float)
    y = np.asarray(y, float)
    order = np.argsort(nee)
    q = np.array_split(order, 4)
    rates = [float(y[ix].mean()) for ix in q]
    ns = [int(len(ix)) for ix in q]
    return {"q_mortality": [round(r, 4) for r in rates], "q_n": ns,
            "q1": round(rates[0], 4), "q4": round(rates[-1], 4),
            "monotone_nondecr": bool(all(rates[i] <= rates[i + 1] + 1e-9
                                         for i in range(3)))}


def model(dopamine_weight=0.01):
    import numpy as np
    stay_link, hadm_death, subj_age = _load_links_with_death()
    lac = _load_lactate()
    summ = _nee_first_window(stay_link, dopamine_weight=dopamine_weight)

    nee_load, nee_peak, age, lact, y = [], [], [], [], []
    n_pressor = 0
    excl_dead_pre = 0
    excl_no_age = 0
    for sid, s in summ.items():
        if not s["has_pressor"]:
            continue
        n_pressor += 1
        link = stay_link.get(sid)
        if link is None:
            continue
        flag, dtime = hadm_death.get(link["hadm"], ("0", None))
        intime = link["intime"]
        landmark = intime + _dt.timedelta(hours=LANDMARK_H)
        # ---- LANDMARK restriction: must be alive at 24h ----
        if dtime is not None and dtime <= landmark:
            excl_dead_pre += 1
            continue
        a = subj_age.get(link["subject"])
        if a is None or not np.isfinite(a):
            excl_no_age += 1
            continue
        died = 1.0 if str(flag) == "1" else 0.0  # in-hospital death (after landmark)
        nee_load.append(s["nee_load"])
        nee_peak.append(s["nee_peak"])
        age.append(a)
        lact.append(lac.get(link["hadm"]))
        y.append(died)

    n = len(y)
    logload = [float(np.log1p(v)) for v in nee_load]
    res_age = _adj_or_per_sd(logload, y, [age])
    grad = _quartile_gradient(nee_load, y)

    # lactate-adjusted subset
    mask = [i for i in range(n) if lact[i] is not None]
    lac_res = None
    if len(mask) > 50:
        ll = [logload[i] for i in mask]
        yy = [y[i] for i in mask]
        aa = [age[i] for i in mask]
        lv = [lact[i] for i in mask]
        lac_res = _adj_or_per_sd(ll, yy, [aa, lv])
        lac_res["subset_n"] = len(mask)

    overall_mort = float(np.mean(y)) if n else None
    return {
        "design": "LANDMARK: NEE accumulated over first-24h ICU window; cohort restricted "
                  "to patients ALIVE at the 24h landmark; outcome = subsequent in-hospital death",
        "dopamine_weight": dopamine_weight,
        "n_pressor_stays_first24h": n_pressor,
        "n_excluded_dead_before_landmark": excl_dead_pre,
        "n_excluded_no_age": excl_no_age,
        "n_analyzed": n,
        "overall_post_landmark_mortality": round(overall_mort, 4) if overall_mort is not None else None,
        "age_adj_or_per_sd_logNEEload": res_age,
        "age_lactate_adj_or_per_sd": lac_res,
        "quartile_gradient": grad,
    }


def run():
    primary = model(dopamine_weight=0.01)
    dopa_sens = model(dopamine_weight=0.05)
    out = {
        "primary_dopa0.01": primary,
        "sensitivity_dopa0.05": {
            "n_analyzed": dopa_sens["n_analyzed"],
            "age_adj_or_per_sd_logNEEload": dopa_sens["age_adj_or_per_sd_logNEEload"],
            "quartile_gradient": dopa_sens["quartile_gradient"],
        },
    }
    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=2)
    return out


if __name__ == "__main__":
    import pprint
    pprint.pprint(run())
