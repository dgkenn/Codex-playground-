"""Organ-support LIBERATION SEQUENCING -> mortality (MIMIC-IV), target-trial emulation.

Candidate #1 from the pivot slate. Clinical decision (not a risk marker): among ICU patients
co-treated with invasive mechanical ventilation (IMV) and vasopressors (and, for the novel arm,
CRRT), does the ORDER in which supports are liberated predict in-hospital mortality?

Design (handles immortal-time/confounding the raw signal carries):
  * Eligibility: stays whose IMV and vasopressor intervals OVERLAP (genuinely co-treated).
  * Landmark = first liberation = min(last IMV endtime, last vasopressor endtime), among patients
    ALIVE and still on both up to that landmark. Exposure (which support liberated first) is thus
    defined prospectively at the landmark; deaths before the landmark are not classifiable (excluded,
    reported).
  * Exposure: pressor_first (vasopressor liberated before IMV) vs vent_first.
  * Adjustment (severity at/before the decision): age, comorbidity count, first-24h SOFA labs
    (creatinine/bilirubin/platelets) + lactate, pre-landmark IMV duration and vasopressor duration,
    and time from ICU intime to landmark.
  * Outcome: in-hospital mortality (primary). Secondary: 3-way order among triple-support (+CRRT).

Data: procedureevents.csv.gz (225792 IMV, 225802 CRRT) + icustays/admissions/patients/diagnoses_icd
under MIMIC_RAW; vasopressor start/end from cache/mimic_fluids_pressors.csv; SOFA labs + lactate from
cache/mimic_labs24h.csv. Heavy deps lazy. Outputs cache/liberation_sequence.json + docs doc.
"""
import os
import csv as _csv
import gzip
import json
import datetime as _dt

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE = os.path.join(_ROOT, "cache")
MIMIC_RAW = os.environ.get("MIMIC_RAW", "/tmp")
FLUID_FILTERED = os.path.join(_CACHE, "mimic_fluids_pressors.csv")
LABS_CSV = os.path.join(_CACHE, "mimic_labs24h.csv")
PROC = os.path.join(MIMIC_RAW, "procedureevents.csv.gz")
OUT_JSON = os.path.join(_CACHE, "liberation_sequence.json")

IMV = "225792"
CRRT = "225802"
PRESSORS = {221906, 221289, 229617, 221749, 229630, 229632, 221662, 222315}


def _pdt(s):
    if not s:
        return None
    try:
        return _dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _load_proc():
    """stay_id -> {imv_start, imv_end, crrt_start, crrt_end} (min start / max end)."""
    out = {}
    with gzip.open(PROC, "rt") as fh:
        for r in _csv.DictReader(fh):
            sid = r["stay_id"]
            it = r["itemid"]
            s = _pdt(r["starttime"]); e = _pdt(r["endtime"])
            if it not in (IMV, CRRT):
                continue
            d = out.setdefault(sid, {})
            pfx = "imv" if it == IMV else "crrt"
            if s is not None:
                d[pfx + "_start"] = min(d.get(pfx + "_start", s), s)
            if e is not None:
                d[pfx + "_end"] = max(d.get(pfx + "_end", e), e)
    return out


def _load_pressor_intervals():
    """stay_id -> (first_start, last_end) across vasopressor segments."""
    out = {}
    with open(FLUID_FILTERED, newline="") as fh:
        for r in _csv.DictReader(fh):
            try:
                it = int(r["itemid"])
            except (ValueError, TypeError):
                continue
            if it not in PRESSORS:
                continue
            sid = r["stay_id"]
            s = _pdt(r["starttime"]); e = _pdt(r["endtime"])
            d = out.setdefault(sid, [None, None])
            if s is not None:
                d[0] = s if d[0] is None else min(d[0], s)
            if e is not None:
                d[1] = e if d[1] is None else max(d[1], e)
    return {k: tuple(v) for k, v in out.items() if v[0] and v[1]}


def _load_links():
    stay = {}
    with gzip.open(os.path.join(MIMIC_RAW, "icustays.csv.gz"), "rt") as fh:
        for r in _csv.DictReader(fh):
            stay[r["stay_id"]] = {"hadm": r["hadm_id"], "subject": r["subject_id"],
                                  "intime": _pdt(r["intime"])}
    death = {}
    with gzip.open(os.path.join(MIMIC_RAW, "admissions.csv.gz"), "rt") as fh:
        for r in _csv.DictReader(fh):
            death[r["hadm_id"]] = (r.get("hospital_expire_flag", "0"), _pdt(r.get("deathtime")))
    age = {}
    with gzip.open(os.path.join(MIMIC_RAW, "patients.csv.gz"), "rt") as fh:
        for r in _csv.DictReader(fh):
            try:
                age[r["subject_id"]] = float(r["anchor_age"])
            except (ValueError, TypeError):
                pass
    return stay, death, age


def _load_comorbidity():
    path = os.path.join(MIMIC_RAW, "diagnoses_icd.csv.gz")
    seen = {}
    with gzip.open(path, "rt") as fh:
        for r in _csv.DictReader(fh):
            h = r.get("hadm_id"); c = r.get("icd_code")
            if h and c:
                seen.setdefault(h, set()).add(c)
    return {h: len(s) for h, s in seen.items()}


def _load_labs():
    lac, sofa = {}, {}
    if not os.path.exists(LABS_CSV):
        return lac, sofa
    with open(LABS_CSV, newline="") as fh:
        for r in _csv.DictReader(fh):
            h = r["hadm_id"]
            v = r.get("lactate")
            if v not in (None, "", "nan"):
                try:
                    lac[h] = float(v)
                except ValueError:
                    pass
            d = {}
            for k in ("creatinine", "bilirubin", "platelets"):
                vv = r.get(k)
                try:
                    d[k] = float(vv) if vv not in (None, "", "nan") else None
                except ValueError:
                    d[k] = None
            sofa[h] = d
    return lac, sofa


def _irls(X, y):
    import numpy as np
    X = np.asarray(X, float); y = np.asarray(y, float)
    b = np.zeros(X.shape[1]); W = np.ones(len(y))
    for _ in range(100):
        eta = np.clip(X @ b, -30, 30); p = 1 / (1 + np.exp(-eta))
        W = np.clip(p * (1 - p), 1e-9, None); z = eta + (y - p) / W
        try:
            bn = np.linalg.solve((X.T * W) @ X, (X.T * W) @ z)
        except np.linalg.LinAlgError:
            break
        if np.max(np.abs(bn - b)) < 1e-9:
            b = bn; break
        b = bn
    try:
        cov = np.linalg.inv((X.T * W) @ X); se = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        se = np.full(len(b), np.nan)
    return b, se


def _evalue_or(or_, p0):
    rr = or_ / (1 - p0 + p0 * or_)
    r = rr if rr >= 1 else 1.0 / rr
    return round(r + (r * (r - 1)) ** 0.5, 2)


def model():
    import numpy as np
    proc = _load_proc()
    press = _load_pressor_intervals()
    stay, death, age = _load_links()
    comorb = _load_comorbidity()
    lac, sofa = _load_labs()

    rows = []
    n_cotreated = 0
    n_excl_death_pre = 0
    triple = []
    for sid, pc in proc.items():
        if "imv_end" not in pc or sid not in press:
            continue
        imv_s = pc.get("imv_start"); imv_e = pc["imv_end"]
        pr_s, pr_e = press[sid]
        # eligibility: IMV and vasopressor intervals overlap (co-treated)
        if imv_s is None or not (imv_s <= pr_e and pr_s <= imv_e):
            continue
        link = stay.get(sid)
        if link is None:
            continue
        n_cotreated += 1
        flag, dtime = death.get(link["hadm"], ("0", None))
        landmark = min(imv_e, pr_e)
        # landmark restriction: alive and on both up to first liberation
        if dtime is not None and dtime <= landmark:
            n_excl_death_pre += 1
            continue
        a = age.get(link["subject"])
        if a is None or not np.isfinite(a):
            continue
        intime = link["intime"]
        pressor_first = 1.0 if pr_e < imv_e else 0.0
        imv_dur = (imv_e - imv_s).total_seconds() / 3600.0 if imv_s else None
        pr_dur = (pr_e - pr_s).total_seconds() / 3600.0
        t_to_lm = (landmark - intime).total_seconds() / 3600.0 if intime else None
        sl = sofa.get(link["hadm"], {})
        rows.append({
            "sid": sid, "pf": pressor_first, "age": a,
            "com": comorb.get(link["hadm"]), "lac": lac.get(link["hadm"]),
            "creat": sl.get("creatinine"), "bili": sl.get("bilirubin"), "plt": sl.get("platelets"),
            "imv_dur": imv_dur, "pr_dur": pr_dur, "t_lm": t_to_lm,
            "died": 1.0 if str(flag) == "1" else 0.0,
            "has_crrt": "crrt_end" in pc,
        })
        if "crrt_end" in pc:
            triple.append((sid, imv_e, pr_e, pc["crrt_end"],
                           1.0 if str(flag) == "1" else 0.0))

    n = len(rows)
    pf = np.array([r["pf"] for r in rows]); y = np.array([r["died"] for r in rows])
    # crude
    m_pf = float(y[pf == 1].mean()); m_vf = float(y[pf == 0].mean())

    def fit(keys):
        idx = [i for i in range(n) if all(rows[i][k] is not None for k in keys)]
        cols = [np.ones(len(idx)), np.array([rows[i]["pf"] for i in idx])]
        for k in keys:
            v = np.array([rows[i][k] for i in idx], float)
            s = v.std(); cols.append((v - v.mean()) / s if s > 0 else v - v.mean())
        X = np.column_stack(cols); yy = np.array([rows[i]["died"] for i in idx])
        b, se = _irls(X, yy)
        orr = float(np.exp(b[1]))
        ci = [float(np.exp(b[1] - 1.96 * se[1])), float(np.exp(b[1] + 1.96 * se[1]))]
        return {"or": round(orr, 3), "ci": [round(c, 3) for c in ci], "n": len(idx)}

    res_age = fit(["age"])
    res_full = fit(["age", "com", "imv_dur", "pr_dur", "t_lm"])
    res_full_lab = fit(["age", "com", "lac", "creat", "bili", "plt", "imv_dur", "pr_dur", "t_lm"])
    p0 = float(y.mean())
    ev = _evalue_or(res_full_lab["or"], p0) if res_full_lab["or"] else None

    # ---- 3-way among triple support ----
    from itertools import permutations
    order_counts = {}
    for sid, ie, pe, ce, died in triple:
        seq = tuple(x[0] for x in sorted([("V", ie), ("P", pe), ("C", ce)], key=lambda t: t[1]))
        d = order_counts.setdefault("".join(seq), [0, 0])
        d[0] += 1; d[1] += died
    triple_orders = {k: {"n": v[0], "mortality": round(v[1] / v[0], 3)}
                     for k, v in sorted(order_counts.items(), key=lambda kv: -kv[1][0])}

    return {
        "design": "target-trial emulation; landmark = first liberation among co-treated patients "
                  "alive+on-both; exposure = pressor liberated before ventilation",
        "n_cotreated_imv_vaso": n_cotreated,
        "n_excluded_death_before_first_liberation": n_excl_death_pre,
        "n_analyzed": n,
        "pressor_first_rate": round(float(pf.mean()), 3),
        "mortality_pressor_first": round(m_pf, 3),
        "mortality_vent_first": round(m_vf, 3),
        "pressor_first_OR_age": res_age,
        "pressor_first_OR_full_clinical": res_full,
        "pressor_first_OR_full_plus_labs": res_full_lab,
        "evalue_full_plus_labs": ev,
        "triple_support_n": len(triple),
        "triple_liberation_order_mortality": triple_orders,
    }


def run():
    out = model()
    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=2)
    return out


if __name__ == "__main__":
    import pprint
    pprint.pprint(run())
