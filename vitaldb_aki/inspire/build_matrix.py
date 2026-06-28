"""build_matrix.py -- turn raw PhysioNet INSPIRE 1.4.2 tables into the
``cache/inspire_matrix.csv`` analysis matrix that
``analysis/external_validation.py`` (and the internal estimators it reuses)
consume.

One row per ``op_id``.  Column names are the INTERNAL feature names the
estimators expect (see ``INSPIRE_VARIABLE_MAP`` in analysis/external_validation.py
and DEFAULT_PS_COVARIATES in analysis/hypotension_treatment.py).

INSPIRE 1.4.2 schema actually shipped (from cache/inspire_raw/schema.csv +
parameters.csv -- the PhysioNet docs differ slightly from the scaffold's earlier
best-effort guesses, so this builder targets the REAL columns):

  operations(op_id, subject_id, case_id, opdate, age, sex(M/F), weight, height,
             race, asa, emop(0/1), department, antype, icd10_pcs,
             *_time columns are integer SECONDS from a per-subject reference)
  labs(subject_id, chart_time[s], item_name, value)   long; cr item_name='creatinine'
  vitals(op_id, subject_id, chart_time[s], item_name, value)  long; intraop
         MAP = 'art_mbp' (invasive) | 'nibp_mbp' (non-invasive);
         pressors = 'phe'(ug bolus) 'eph'(mg) 'epi'(ug) 'nepi'(ug/kg/min rate)
         'pepi'(ug/h rate) 'vaso' 'dopai'/'dobui'; 'ebl'(mL)
  ward_vitals(subject_id, chart_time, item_name, value)  -- crrt/ecmo/iabp/vent flags
  medications(subject_id, chart_time, route, drug_name, atc_code)  ward/prescription
  diagnosis(subject_id, chart_time, icd10_cm)

KEY schema facts (verified against the real gz files):
  * Times are SECONDS from a per-SUBJECT reference (not per-op, not from opstart).
    Creatinine/MAP windows are therefore anchored on operations.opstart_time /
    opend_time / anstart_time / anend_time (same reference frame).
  * labs/medications/diagnosis are keyed by SUBJECT_ID (a subject may have several
    ops); we attribute a subject's labs to each of that subject's ops using that
    op's own anchors.  Baseline cr = last cr before that op's anstart_time.
  * Intraop pressors live in the VITALS table (phe/eph/nepi/...), NOT medications
    (medications is ward/po prescriptions).  norepinephrine is therefore recorded
    on INSPIRE (unlike VitalDB where it is pump-track-only).

Leakage firewall: PREDICTORS use preop labs + intraop vitals/meds only.  OUTCOMES
(KDIGO renal, composite organ axes, death) are y and may use postop data BY
DEFINITION.  Nothing postop becomes a feature.

Memory: vitals.csv.gz is LARGE and long-format -> read CHUNKED (pandas chunksize)
keyed by op_id; never load whole.  If vitals is absent or fails ``gzip -t``, build
everything else and leave the MAP columns empty (NaN) -- MAP-dependent targets are
then PENDING (handled gracefully by the harness required-cols check).

Heavy deps (pandas/numpy) are lazy-imported inside functions, per repo convention.

Entry point
-----------
    build_inspire_matrix(raw_dir, out_path, cfg=None) -> dict   # summary
    python3 -m vitaldb_aki.inspire.build_matrix [--raw DIR] [--out PATH]
"""
from __future__ import annotations

import gzip
import math
import os
from typing import Any

# --------------------------------------------------------------------------
# Locations & constants
# --------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.dirname(_HERE)
DEFAULT_RAW_DIR = os.path.join(_PKG_ROOT, "cache", "inspire_raw")
DEFAULT_OUT = os.path.join(_PKG_ROOT, "cache", "inspire_matrix.csv")

RANDOM_SEED = 20260626

# MAP item_names in vitals (prefer invasive arterial, fall back to non-invasive).
MAP_ITEMS_PREF = ["art_mbp", "nibp_mbp"]
# Physiologic artifact gate for MAP (mmHg).
MAP_LO, MAP_HI = 20.0, 200.0
# MAP thresholds for burden AUC.
MAP_THRESHOLDS = (65.0, 70.0, 75.0)

# Pressor item_names in vitals (bolus doses + infusion rates).
PRESSOR_VITALS = {
    "phe": "phenylephrine",      # ug bolus
    "pepi": "phenylephrine",     # ug/h infusion rate (phenylephrine)
    "eph": "ephedrine",          # mg bolus
    "epi": "epinephrine",        # ug bolus
    "epii": "epinephrine",       # ug/kg/min rate
    "nepi": "norepinephrine",    # ug/kg/min rate
    "vaso": "vasopressin",
    "dopai": "dopamine",
    "dobui": "dobutamine",
    "ntgi": "nitroglycerin",     # vasodilator -- not a pressor; tracked for completeness
}
# Pressors that count toward "any_vasopressor" and choice.
PRESSOR_ANY = {"phe", "pepi", "eph", "epi", "epii", "nepi", "vaso", "dopai"}

# medications ATC pressor codes (secondary source / ward).
ATC_PRESSORS = {
    "C01CA03": "norepinephrine",
    "C01CA06": "phenylephrine",
    "C01CA26": "ephedrine",
    "C01CA24": "epinephrine",
    "C01CA04": "dopamine",
    "C01CA07": "dobutamine",
    "H01BA01": "vasopressin",
}

# Preop hypertension / diabetes ICD-10-CM prefixes (diagnosis.icd10_cm).
HTN_ICD_PREFIXES = ("I10", "I11", "I12", "I13", "I15")
DM_ICD_PREFIXES = ("E10", "E11", "E12", "E13", "E14")

# Baseline preop window: accept cr within 365 d before the op anchor.
# Times are in MINUTES, so the window is in minutes too.
BASELINE_PREOP_WINDOW_MIN = 365 * 24 * 60.0

VITALS_CHUNKSIZE = 2_000_000

# INSPIRE 1.4.2 relative-time UNIT: integer MINUTES from a per-subject reference.
# (Verified empirically: median opend-opstart = 80, p95 = 325, max = 2140 -> minutes,
# not seconds; the official PhysioNet docs state times are minutes from the first
# event of each patient.)  Convert to SECONDS for label_case / KDIGO windows.
TIME_UNIT_SECONDS = 60.0


# --------------------------------------------------------------------------
# gzip integrity / availability
# --------------------------------------------------------------------------
def gz_ok(path: str) -> bool:
    """Return True iff *path* exists and passes a gzip integrity read (== gzip -t).

    Used to skip a table that is mid-download (the live INSPIRE pull writes these
    files concurrently; we must never crash on a truncated gz)."""
    if not os.path.isfile(path):
        return False
    try:
        with gzip.open(path, "rb") as fh:
            while fh.read(1 << 20):
                pass
        return True
    except Exception:
        return False


def _raw(raw_dir: str, name: str) -> str:
    return os.path.join(raw_dir, name)


# --------------------------------------------------------------------------
# numeric helpers
# --------------------------------------------------------------------------
def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


# ===========================================================================
# 1. OPERATIONS  -> per-op covariates + anchors
# ===========================================================================
def load_operations(raw_dir: str):
    """Load operations.csv.gz -> DataFrame indexed by op_id with derived covariates.

    Returns a pandas DataFrame; raises FileNotFoundError if operations is absent or
    fails gzip integrity (operations is mandatory -- nothing can be built without it).
    """
    import numpy as np
    import pandas as pd

    path = _raw(raw_dir, "operations.csv.gz")
    if not gz_ok(path):
        raise FileNotFoundError(
            f"operations.csv.gz absent or failed gzip integrity at {path!r}. "
            "It is the mandatory anchor table (per-op covariates + opstart/opend/"
            "anstart/anend windows). Wait for the INSPIRE download to finish."
        )
    ops = pd.read_csv(path, compression="gzip")

    # Normalise expected columns (real INSPIRE 1.4.2 names).
    def col(*names):
        for n in names:
            if n in ops.columns:
                return ops[n]
        return pd.Series([np.nan] * len(ops))

    out = pd.DataFrame()
    out["op_id"] = col("op_id").astype("Int64").astype(str)
    out["subject_id"] = col("subject_id").astype("Int64").astype(str)
    out["case_id"] = col("case_id")
    # internal-name aliases the estimators key on:
    out["caseid"] = out["op_id"]
    out["subjectid"] = out["subject_id"]

    out["age"] = pd.to_numeric(col("age"), errors="coerce")
    sex = col("sex").astype(str).str.strip().str.upper()
    out["sex_male"] = (sex == "M").astype(int)
    out["weight_kg"] = pd.to_numeric(col("weight"), errors="coerce")
    out["height_cm"] = pd.to_numeric(col("height"), errors="coerce")
    out["asa_class"] = pd.to_numeric(col("asa"), errors="coerce")
    out["emergency"] = pd.to_numeric(col("emop"), errors="coerce").fillna(0).astype(int)
    dept = col("department").astype(str).str.strip()
    out["department"] = dept
    out["optype"] = dept
    out["antype"] = col("antype").astype(str)

    # BMI + BSA (Mosteller).
    w, h = out["weight_kg"], out["height_cm"]
    out["bmi"] = w / (h / 100.0) ** 2
    out["bsa"] = np.sqrt((w * h) / 3600.0)

    # Time anchors (seconds from per-subject reference).
    for t in ("opstart_time", "opend_time", "anstart_time", "anend_time",
              "orin_time", "orout_time", "icuin_time", "icuout_time",
              "inhosp_death_time", "allcause_death_time"):
        out[t] = pd.to_numeric(col(t), errors="coerce")

    # Durations (minutes). Times are already in MINUTES (see TIME_UNIT_SECONDS).
    out["anesthesia_duration"] = (out["anend_time"] - out["anstart_time"])
    out["surgery_duration"] = (out["opend_time"] - out["opstart_time"])
    out.loc[out["surgery_duration"] <= 0, "surgery_duration"] = np.nan
    out.loc[out["anesthesia_duration"] <= 0, "anesthesia_duration"] = np.nan

    # optype_code (factorised int) for confounding / one-hot in estimators.
    out["optype_code"] = pd.factorize(out["department"])[0].astype(float)

    out = out[out["op_id"].notna() & (out["op_id"] != "<NA>")].reset_index(drop=True)
    return out


# ===========================================================================
# 2. LABS  -> per-subject analyte series (streamed; subject_id keyed)
# ===========================================================================
def load_lab_series(raw_dir: str, items: set[str]):
    """Stream labs.csv.gz -> {item_name: {subject_id: [(time_s, value), ...]}}.

    Only the requested *items* are retained.  Returns sorted-by-time lists.
    labs is keyed by subject_id; per-op attribution happens later via op anchors.
    """
    import pandas as pd

    path = _raw(raw_dir, "labs.csv.gz")
    if not gz_ok(path):
        raise FileNotFoundError(f"labs.csv.gz absent/failed gzip at {path!r}")

    series: dict[str, dict[str, list]] = {it: {} for it in items}
    for chunk in pd.read_csv(path, compression="gzip", chunksize=VITALS_CHUNKSIZE,
                             dtype={"subject_id": str, "item_name": str}):
        chunk = chunk[chunk["item_name"].isin(items)]
        if chunk.empty:
            continue
        t = pd.to_numeric(chunk["chart_time"], errors="coerce")
        v = pd.to_numeric(chunk["value"], errors="coerce")
        ok = t.notna() & v.notna()
        for sid, tt, vv, it in zip(chunk["subject_id"][ok], t[ok], v[ok], chunk["item_name"][ok]):
            series[it].setdefault(str(sid), []).append((float(tt), float(vv)))
    for it in series:
        for sid in series[it]:
            series[it][sid].sort(key=lambda x: x[0])
    return series


# ===========================================================================
# 3. DIAGNOSIS / MEDICATIONS  -> per-subject comorbidity & ward-pressor flags
# ===========================================================================
def load_comorbidities(raw_dir: str) -> dict[str, dict[str, int]]:
    """Return {subject_id: {'preop_htn':0/1, 'preop_dm':0/1}} from diagnosis ICD-10.

    INSPIRE diagnosis lacks a clean preop/postop split for chronic comorbidity
    coding, but HTN/DM are CHRONIC conditions; any recorded I10*/E11* etc. flags the
    subject (documented as a chronic-comorbidity flag, not a temporal event)."""
    import pandas as pd

    path = _raw(raw_dir, "diagnosis.csv.gz")
    out: dict[str, dict[str, int]] = {}
    if not gz_ok(path):
        return out
    for chunk in pd.read_csv(path, compression="gzip", chunksize=VITALS_CHUNKSIZE,
                             dtype={"subject_id": str, "icd10_cm": str}):
        code = chunk["icd10_cm"].astype(str).str.strip().str.upper()
        htn = code.str.startswith(HTN_ICD_PREFIXES)
        dm = code.str.startswith(DM_ICD_PREFIXES)
        for sid, h, d in zip(chunk["subject_id"], htn, dm):
            rec = out.setdefault(str(sid), {"preop_htn": 0, "preop_dm": 0})
            if h:
                rec["preop_htn"] = 1
            if d:
                rec["preop_dm"] = 1
    return out


def load_med_pressors(raw_dir: str) -> dict[str, set]:
    """Return {subject_id: {pressor_name,...}} from medications ATC codes (secondary
    pressor source; intraop pressors come from vitals)."""
    import pandas as pd

    path = _raw(raw_dir, "medications.csv.gz")
    out: dict[str, set] = {}
    if not gz_ok(path):
        return out
    for chunk in pd.read_csv(path, compression="gzip", chunksize=VITALS_CHUNKSIZE,
                             dtype=str):
        atc_cols = [c for c in chunk.columns if c.startswith("atc_code")]
        # Vectorised: melt atc columns, filter to pressor codes, then group.
        keep = chunk[["subject_id"] + atc_cols].copy()
        long = keep.melt(id_vars="subject_id", value_vars=atc_cols,
                         value_name="atc").dropna(subset=["atc"])
        long["atc"] = long["atc"].astype(str).str.strip().str.upper()
        long = long[long["atc"].isin(ATC_PRESSORS)]
        for sid, atc in zip(long["subject_id"], long["atc"]):
            out.setdefault(str(sid), set()).add(ATC_PRESSORS[atc])
    return out


# ===========================================================================
# 4. VITALS  -> per-op MAP burden + pressor exposure (STREAMED CHUNKED)
# ===========================================================================
def stream_vitals_features(raw_dir: str, op_anchors: dict[str, tuple]):
    """Stream vitals.csv.gz CHUNKED -> per-op MAP burden + pressor totals.

    op_anchors: {op_id: (anstart_s, anend_s)} -- the intraop window (anesthesia
    start..end). MAP samples within [anstart, anend] are used.

    Returns (map_feats, pressor_feats, available):
      map_feats[op_id]   = {map_mean, map_lowest, map_auc_below_65/70/75,
                            map_min_below_65, time_weighted_mean, n_map, recovery_velocity}
      pressor_feats[op_id] = {'phe_ug':..,'eph_mg':..,'nepi_rate':..,'any':0/1,...}
      available = True if vitals readable, else False (all MAP -> empty/PENDING).

    MAP integration is time-weighted (trapezoid over the sample timeline).  Because
    INSPIRE vitals are long-format and arrive per-(op_id,item) we accumulate a
    per-op timeline incrementally; chunks are ordered within a file by op so a
    streaming accumulator with a flush-on-op-change keeps memory bounded.  To stay
    robust to arbitrary row ordering we accumulate compact per-op arrays (MAP only;
    pressors are scalar sums) -- bounded because each op's intraop MAP is ~minutes.
    """
    import numpy as np
    import pandas as pd

    path = _raw(raw_dir, "vitals.csv.gz")
    if not gz_ok(path):
        return {}, {}, False

    want_items = set(MAP_ITEMS_PREF) | set(PRESSOR_VITALS.keys())
    op_set = set(op_anchors.keys())

    # Per-op MAP samples: {op_id: {'art':[(t,v)], 'nibp':[(t,v)]}}
    map_samp: dict[str, dict[str, list]] = {}
    # Per-op pressor scalar accumulators.
    pres: dict[str, dict[str, float]] = {}

    def _anchor(opid):
        a = op_anchors.get(opid)
        if a is None:
            return None, None
        return a

    for chunk in pd.read_csv(path, compression="gzip", chunksize=VITALS_CHUNKSIZE,
                             dtype={"op_id": str, "item_name": str}):
        chunk = chunk[chunk["item_name"].isin(want_items)]
        if chunk.empty:
            continue
        opid = chunk["op_id"].astype(str)
        t = pd.to_numeric(chunk["chart_time"], errors="coerce")
        v = pd.to_numeric(chunk["value"], errors="coerce")
        it = chunk["item_name"]
        ok = t.notna() & v.notna() & opid.isin(op_set)
        for o, tt, vv, item in zip(opid[ok], t[ok], v[ok], it[ok]):
            an0, an1 = _anchor(o)
            if an0 is None:
                continue
            if item in ("art_mbp", "nibp_mbp"):
                if not (an0 <= tt <= an1):
                    continue
                if not (MAP_LO <= vv <= MAP_HI):
                    continue
                d = map_samp.setdefault(o, {"art": [], "nibp": []})
                d["art" if item == "art_mbp" else "nibp"].append((tt, vv))
            elif item in PRESSOR_VITALS:
                # pressor doses: count intraop administrations (within window)
                if an0 is not None and an1 is not None and not (an0 <= tt <= an1):
                    continue
                p = pres.setdefault(o, {})
                p[item] = p.get(item, 0.0) + (vv if vv > 0 else 0.0)

    # ---- reduce MAP samples to features ----
    map_feats: dict[str, dict] = {}
    for o, d in map_samp.items():
        samp = d["art"] if len(d["art"]) >= 3 else d["nibp"]
        if len(samp) < 2:
            samp = d["art"] + d["nibp"]
        samp = sorted(samp, key=lambda x: x[0])
        if len(samp) < 2:
            continue
        ts = np.array([s[0] for s in samp], dtype=float)
        vs = np.array([s[1] for s in samp], dtype=float)
        # ts is in MINUTES (INSPIRE time unit) -> dt is already minutes.
        # Cap gaps at 5 min to avoid crediting long monitor dropouts.
        dt = np.diff(ts)
        dt = np.clip(dt, 0.0, 5.0)
        seg_v = (vs[:-1] + vs[1:]) / 2.0   # midpoint MAP per interval
        total_min = float(dt.sum())
        feats = {
            "map_mean": float(vs.mean()),
            "map_lowest": float(vs.min()),
            "map_time_weighted_mean": (float((seg_v * dt).sum() / total_min)
                                       if total_min > 0 else float(vs.mean())),
            "n_map": int(len(vs)),
        }
        for thr in MAP_THRESHOLDS:
            below = np.clip(thr - seg_v, 0.0, None)   # mmHg under threshold per seg
            feats[f"map_auc_below_{int(thr)}"] = float((below * dt).sum())
        feats["map_min_below_65"] = float((dt * (seg_v < 65.0)).sum())
        # ---- recovery_velocity proxy (degraded-resolution): late-vs-early mean
        # MAP delta scaled by nadir depth, matching reperfusion_dynamics estimand.
        nadir_depth = max(65.0 - feats["map_lowest"], 0.0)
        half = len(vs) // 2
        if half >= 1 and (len(vs) - half) >= 1:
            early = float(vs[:half].mean())
            late = float(vs[half:].mean())
            feats["map_early_vs_late_mean_delta"] = late - early
        else:
            feats["map_early_vs_late_mean_delta"] = 0.0
        feats["recovery_velocity"] = (
            feats["map_early_vs_late_mean_delta"] / (nadir_depth + 1.0)
        )
        map_feats[o] = feats

    # ---- reduce pressor accumulators ----
    pressor_feats: dict[str, dict] = {}
    for o, p in pres.items():
        any_p = int(any(p.get(k, 0.0) > 0 for k in PRESSOR_ANY))
        phe = p.get("phe", 0.0) + p.get("pepi", 0.0)
        nepi = p.get("nepi", 0.0)
        eph = p.get("eph", 0.0)
        epi = p.get("epi", 0.0) + p.get("epii", 0.0)
        pressor_feats[o] = {
            "any_vasopressor": any_p,
            "intraop_phe": phe,
            "intraop_norepi": nepi,
            "intraop_eph": eph,
            "intraop_epi": epi,
            "_phe_present": int(phe > 0),
            "_norepi_present": int(nepi > 0),
        }
    return map_feats, pressor_feats, True


# ===========================================================================
# 5. OUTCOMES  -- KDIGO renal + composite organ axes + mortality
# ===========================================================================
def _pick_baseline_cr(series, anchor_min):
    """Most recent creatinine strictly before *anchor_min* within the preop window.

    All times are in MINUTES (per-subject reference)."""
    preop = [(t, v) for t, v in series if t < anchor_min and v > 0]
    if not preop:
        return None
    best = max(preop, key=lambda x: x[0])
    if best[0] < anchor_min - BASELINE_PREOP_WINDOW_MIN:
        return None
    return best[1]


def _ckd_epi_2021(cr, age, female):
    """CKD-EPI 2021 (race-free) eGFR (mL/min/1.73m2)."""
    if cr is None or age is None or cr <= 0:
        return None
    k = 0.7 if female else 0.9
    a = -0.241 if female else -0.302
    cr_k = cr / k
    egfr = 142.0 * (min(cr_k, 1.0) ** a) * (max(cr_k, 1.0) ** -1.200) \
        * (0.9938 ** age)
    if female:
        egfr *= 1.012
    return egfr


def compute_outcomes(ops, lab_series, cfg):
    """Per-op outcomes: organ_renal (KDIGO), organ_* component flags, composite,
    death; plus baseline_cr / egfr_ckd_epi / ckd.

    Uses inspire/labeling.py label_case for the renal axis (SAME thresholds as
    cohort/labeling.py). Composite organ axes mirror config.yaml organ_outcomes:
    hepatocellular (AST/ALT>=3xULN), cholestatic (tbil>=2xULN), coagulation_inr
    (ptinr>=1.5 from normal baseline), hypoperfusion (lacate>=4), mortality.
    """
    import numpy as np
    import pandas as pd
    from vitaldb_aki.cohort.labeling import label_case

    kcfg = (cfg or {}).get("kdigo") or {
        "abs_rise_mgdl": 0.3, "abs_window_h": 48,
        "rel_ratio": 1.5, "rel_window_h": 168,
    }
    oo = (cfg or {}).get("organ_outcomes", {}) or {}
    uln = oo.get("ULN", {"ast": 40.0, "alt": 40.0, "tbil": 1.2})
    win_h = float(oo.get("postop_window_h", 168))
    win_min = win_h * 60.0          # postop window in MINUTES (INSPIRE time unit)

    cr_map = lab_series.get("creatinine", {})
    ast_map = lab_series.get("ast", {})
    alt_map = lab_series.get("alt", {})
    tbil_map = lab_series.get("total_bilirubin", {})
    inr_map = lab_series.get("ptinr", {})
    lac_map = lab_series.get("lacate", {})

    rows = []
    for _, op in ops.iterrows():
        sid = op["subject_id"]
        opid = op["op_id"]
        anstart = op.get("anstart_time")
        opend = op.get("opend_time")
        anend = op.get("anend_time")
        anchor = anstart if pd.notna(anstart) else op.get("opstart_time")
        postop_anchor = opend if pd.notna(opend) else anend
        rec = {"op_id": opid}

        # ---- baseline creatinine + eGFR + CKD ----
        crser = cr_map.get(sid, [])
        baseline = _pick_baseline_cr(crser, anchor) if pd.notna(anchor) else None
        rec["baseline_cr"] = baseline
        female = (op.get("sex_male", 1) == 0)
        egfr = _ckd_epi_2021(baseline, op.get("age"), female)
        rec["egfr_ckd_epi"] = egfr
        rec["ckd"] = int(egfr is not None and egfr < 60.0) if egfr is not None else np.nan

        # ---- KDIGO renal (postop cr relative to postop_anchor) ----
        # label_case works in SECONDS -> convert dt (minutes) * 60.
        if baseline is not None and pd.notna(postop_anchor):
            postop = [((t - float(postop_anchor)) * TIME_UNIT_SECONDS, v)
                      for t, v in crser if t > float(postop_anchor)]
            lr = label_case(str(opid), baseline, "preop_lab", postop, kcfg)
            rec["organ_renal"] = lr.aki
            rec["aki_stage"] = lr.stage
        else:
            rec["organ_renal"] = None
            rec["aki_stage"] = None

        # ---- helper: postop peak/nadir of an analyte within win ----
        def _postop_vals(series):
            if pd.isna(postop_anchor):
                return []
            return [v for t, v in series.get(sid, [])
                    if float(postop_anchor) < t <= float(postop_anchor) + win_min]

        # hepatocellular: AST or ALT >= 3x ULN
        ast_v = _postop_vals(ast_map)
        alt_v = _postop_vals(alt_map)
        hep = None
        if ast_v or alt_v:
            hep = int((max(ast_v, default=0) >= 3 * uln.get("ast", 40.0)) or
                      (max(alt_v, default=0) >= 3 * uln.get("alt", 40.0)))
        rec["organ_hepatocellular"] = hep

        # cholestatic: tbil >= 2x ULN
        tb_v = _postop_vals(tbil_map)
        rec["organ_cholestatic"] = (int(max(tb_v) >= 2 * uln.get("tbil", 1.2))
                                    if tb_v else None)

        # coagulation_inr: postop ptinr>=1.5 from documented normal preop (<1.3)
        inr_pre = [v for t, v in inr_map.get(sid, [])
                   if pd.notna(anchor) and t < float(anchor)]
        inr_post = _postop_vals(inr_map)
        if inr_pre and min(inr_pre[-1:], default=99) < 1.3 and inr_post:
            rec["organ_coagulation"] = int(max(inr_post) >= 1.5)
        else:
            rec["organ_coagulation"] = None

        # hypoperfusion: lactate >= 4
        lac_v = _postop_vals(lac_map)
        rec["organ_hypoperfusion"] = (int(max(lac_v) >= 4.0) if lac_v else None)

        # mortality (in-hospital death recorded)
        death = op.get("inhosp_death_time")
        rec["death_inhosp"] = int(pd.notna(death))

        rows.append(rec)

    out = pd.DataFrame(rows)

    # ---- composite = any positive organ axis OR death (None-aware) ----
    axes = ["organ_renal", "organ_hepatocellular", "organ_cholestatic",
            "organ_coagulation", "organ_hypoperfusion"]
    def _composite(row):
        vals = [row.get(a) for a in axes]
        if row.get("death_inhosp") == 1:
            return 1
        if any(v == 1 for v in vals):
            return 1
        # labelable iff at least one axis is observed (renal observed is the
        # backbone, matching the internal composite's labelable set)
        if row.get("organ_renal") is None and all(v is None for v in vals):
            return None
        return 0
    out["composite"] = out.apply(_composite, axis=1)
    return out


# ===========================================================================
# ORCHESTRATOR
# ===========================================================================
def build_inspire_matrix(raw_dir: str = DEFAULT_RAW_DIR,
                         out_path: str = DEFAULT_OUT,
                         cfg: dict | None = None) -> dict:
    """Build cache/inspire_matrix.csv from the raw INSPIRE tables.

    Returns a summary dict (cohort N, base rates, what's pending). Never writes to
    cache/inspire_raw/* (read-only). MAP columns are left NaN (PENDING) if vitals is
    absent / failed gzip integrity.
    """
    import numpy as np
    import pandas as pd

    cfg = cfg or _load_cfg()
    summary: dict[str, Any] = {"raw_dir": raw_dir, "out_path": out_path}

    # --- 1. operations (mandatory) ---
    ops = load_operations(raw_dir)
    summary["n_operations"] = int(len(ops))

    # --- 2. labs -> analyte series ---
    lab_items = {"creatinine", "ast", "alt", "total_bilirubin", "ptinr", "lacate"}
    lab_series = load_lab_series(raw_dir, lab_items)
    summary["n_subjects_with_cr"] = len(lab_series.get("creatinine", {}))

    # --- 3. outcomes ---
    outc = compute_outcomes(ops, lab_series, cfg)

    # --- 4. comorbidities + ward pressors ---
    comorb = load_comorbidities(raw_dir)
    med_pres = load_med_pressors(raw_dir)

    # --- 5. vitals (MAP + intraop pressors) -- streamed; optional ---
    op_anchors = {}
    for _, op in ops.iterrows():
        an0 = op.get("anstart_time")
        an1 = op.get("anend_time")
        if pd.isna(an0):
            an0 = op.get("opstart_time")
        if pd.isna(an1):
            an1 = op.get("opend_time")
        if pd.notna(an0) and pd.notna(an1) and an1 > an0:
            op_anchors[op["op_id"]] = (float(an0), float(an1))
    map_feats, pressor_feats, vitals_ok = stream_vitals_features(raw_dir, op_anchors)
    summary["vitals_available"] = vitals_ok
    summary["n_ops_with_map"] = len(map_feats)

    # --- 6. assemble matrix ---
    m = ops.copy()
    m = m.merge(outc, on="op_id", how="left")

    # comorbidities by subject
    m["preop_htn"] = m["subject_id"].map(
        lambda s: comorb.get(s, {}).get("preop_htn", 0)).astype(int)
    m["preop_dm"] = m["subject_id"].map(
        lambda s: comorb.get(s, {}).get("preop_dm", 0)).astype(int)

    # MAP features
    map_cols = ["map_mean", "map_lowest", "map_time_weighted_mean", "n_map",
                "map_auc_below_65", "map_auc_below_70", "map_auc_below_75",
                "map_min_below_65", "map_early_vs_late_mean_delta",
                "recovery_velocity"]
    for c in map_cols:
        m[c] = m["op_id"].map(lambda o: map_feats.get(o, {}).get(c, np.nan))

    # pressor features (vitals primary; medications ATC as secondary presence)
    pres_cols = ["any_vasopressor", "intraop_phe", "intraop_norepi", "intraop_eph",
                 "intraop_epi", "_phe_present", "_norepi_present"]
    for c in pres_cols:
        m[c] = m["op_id"].map(lambda o: pressor_feats.get(o, {}).get(c, np.nan))
    # phe_vs_norepi among pressor-exposed: 1=phe-only/dominant, 0=norepi present
    def _phe_vs_norepi(row):
        phe = row.get("_phe_present")
        nor = row.get("_norepi_present")
        if pd.isna(phe) and pd.isna(nor):
            return np.nan
        phe = 0 if pd.isna(phe) else int(phe)
        nor = 0 if pd.isna(nor) else int(nor)
        if phe == 0 and nor == 0:
            return np.nan
        if nor == 1:
            return 0          # norepinephrine present -> norepi arm
        return 1              # phenylephrine without norepi -> phe arm
    if vitals_ok:
        m["phe_vs_norepi"] = m.apply(_phe_vs_norepi, axis=1)
    else:
        # vitals absent: fall back to medications-ATC presence for choice if any
        def _med_choice(s):
            drugs = med_pres.get(s, set())
            if "norepinephrine" in drugs:
                return 0
            if "phenylephrine" in drugs:
                return 1
            return np.nan
        m["phe_vs_norepi"] = m["subject_id"].map(_med_choice)
        m["any_vasopressor"] = m["subject_id"].map(
            lambda s: int(bool(med_pres.get(s, set()) & set(ATC_PRESSORS.values()))))

    # ebl: from vitals if present (cumulative); else NaN
    m["ebl"] = np.nan  # INSPIRE ebl is a vitals item; only if vitals streamed -> optional add

    # --- 7. select + write ---
    keep = [
        "op_id", "subject_id", "case_id", "caseid", "subjectid",
        "age", "sex_male", "weight_kg", "height_cm", "bmi", "bsa",
        "asa_class", "emergency", "department", "optype", "optype_code", "antype",
        "anesthesia_duration", "surgery_duration",
        "baseline_cr", "egfr_ckd_epi", "ckd",
        "preop_htn", "preop_dm",
        "organ_renal", "aki_stage", "organ_hepatocellular", "organ_cholestatic",
        "organ_coagulation", "organ_hypoperfusion", "death_inhosp", "composite",
        "map_mean", "map_lowest", "map_time_weighted_mean", "n_map",
        "map_auc_below_65", "map_auc_below_70", "map_auc_below_75",
        "map_min_below_65", "map_early_vs_late_mean_delta", "recovery_velocity",
        "any_vasopressor", "intraop_phe", "intraop_norepi", "intraop_eph",
        "intraop_epi", "phe_vs_norepi", "ebl",
    ]
    keep = [c for c in keep if c in m.columns]
    matrix = m[keep].copy()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    matrix.to_csv(out_path, index=False)

    # --- 8. summary stats ---
    def _rate(col):
        if col not in matrix.columns:
            return None
        s = pd.to_numeric(matrix[col], errors="coerce")
        n = int(s.notna().sum())
        return {"n_labelable": n, "n_pos": int((s == 1).sum()),
                "rate": round(float((s == 1).sum()) / n, 4) if n else None}

    summary["n_matrix_rows"] = int(len(matrix))
    summary["aki_renal"] = _rate("organ_renal")
    summary["composite"] = _rate("composite")
    summary["ckd_prevalence"] = _rate("ckd")
    summary["n_with_baseline_cr"] = int(pd.to_numeric(
        matrix["baseline_cr"], errors="coerce").notna().sum())
    summary["any_vasopressor_rate"] = _rate("any_vasopressor")
    summary["preop_htn_rate"] = _rate("preop_htn")
    summary["preop_dm_rate"] = _rate("preop_dm")
    summary["map_pending"] = not vitals_ok
    summary["pressor_choice_n"] = int(pd.to_numeric(
        matrix.get("phe_vs_norepi"), errors="coerce").notna().sum()) \
        if "phe_vs_norepi" in matrix.columns else 0
    return summary


def _load_cfg() -> dict:
    """Load config.yaml (kdigo/organ_outcomes/seed). Falls back to defaults."""
    path = os.path.join(_PKG_ROOT, "config.yaml")
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


# ===========================================================================
# CLI
# ===========================================================================
if __name__ == "__main__":
    import argparse
    import json
    import sys

    _root = os.path.dirname(_PKG_ROOT)
    if _root not in sys.path:
        sys.path.insert(0, _root)

    ap = argparse.ArgumentParser(description="Build cache/inspire_matrix.csv from raw INSPIRE tables.")
    ap.add_argument("--raw", default=DEFAULT_RAW_DIR)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    try:
        summ = build_inspire_matrix(args.raw, args.out)
    except FileNotFoundError as exc:
        print(f"[build_matrix] BLOCKED: {exc}")
        sys.exit(2)
    print("[build_matrix] wrote", args.out)
    print(json.dumps(summ, indent=2, default=str))
