"""aline_feasibility.py -- Resumable feasibility-sample pipeline for the A-line
waveform biomarkers (arterial-waveform morphology + ART x PPG coupling).

Goal
----
Before committing to the FULL arterial-waveform extraction (~180 GB of raw 500 Hz
SNUADC/ART + PLETH downloads across the whole ART-instrumented cohort), answer a
single YES/NO question on a small DETERMINISTIC sample (~600 cases):

    Is there an AKI signal in the A-line waveform biomarkers worth scaling up?

Two things are screened, mirroring the study's "actionable" north star:
  (1) Does each waveform biomarker predict AKI -- univariate AUROC AND an
      INCREMENTAL value over the hypotension baseline (map_auc_below_65)?
  (2) Does a key waveform biomarker look like it identifies WHO BENEFITS from a
      modifiable management lever (predictive-enrichment / treatment-interaction)?
        - art_ppv_mean (fluid-responsive / hypovolemic) -> lever: fluid vs pressor.
        - central_peripheral_decoupling / art_ppg_amp_corr (pressure != perfusion)
          -> lever: phenylephrine-predominant vs not.
      Each interaction is reported stratified by a median split of the biomarker
      plus an interaction term, on organ_renal + composite, IPTW-adjusted where
      possible.  The contractility (art_dpdt_max_mean) and vasoplegia
      (art_tau_decay_mean) markers' implied levers are NOTED but not formally
      tested (out of feasibility scope).

HONESTY / POWER
---------------
This is a ~600-case sample -> only ~18-22 renal events (cohort renal prevalence
~3.3%).  EVERY screen cell prints n / events and is flagged
"feasibility-only, underpowered".  The interaction cells are flagged
"hypothesis-generating, underpowered" even more prominently.  Nothing here is a
definitive estimate; it only decides whether the full 180 GB extraction is
justified.

STAGES
------
EXTRACT (resumable, disk-bounded):
  * pick a deterministic seeded sample of caseids that HAVE 'SNUADC/ART' in their
    /trks index (seed from cfg['seed']; N=600 or fewer if <600 have ART),
  * for each sampled case run aline_morphology.extract + cross_waveform.extract,
    MERGE the two feature dicts, append a row to cache/aline_sample.csv,
  * skip caseids already present in aline_sample.csv (-> resumable),
  * STREAM: after each case, purge that case's raw SNUADC track CSVs (ART, PLETH,
    ECG_II) so the ~50-100 MB/case waveform never accumulates on disk,
  * flush every FLUSH_EVERY cases; print progress; write
    cache/_aline_extract_done.json when complete.

SCREEN:
  * load aline_sample.csv, merge organ_renal + composite + map_auc_below_65,
  * per feature: univariate AUROC vs organ_renal and composite (on aline rows),
    AND an incremental test over the hypotension baseline (ΔAUROC + LR p) with a
    patient-clustered bootstrap CI; BH-FDR across features,
  * the two predictive-enrichment interaction looks,
  * write cache/aline_feasibility_results.json + docs/ALINE_FEASIBILITY.md,
  * write cache/_aline_done.json LAST.

Heavy deps (numpy/sklearn/pandas) are lazy-imported; this module imports with the
stdlib only so the determinism / band helpers are unit-testable without sklearn.
"""
from __future__ import annotations

import csv as _csv
import hashlib
import json
import math
import os
from typing import Any

# ---------------------------------------------------------------------------
# Constants (binding)
# ---------------------------------------------------------------------------
ART_TRACK_NAME = "SNUADC/ART"
SAMPLE_N = 600                 # target feasibility sample size
FLUSH_EVERY = 10              # flush the CSV every N cases (and report progress)

SAMPLE_CSV = "aline_sample.csv"
EXTRACT_DONE_MARKER = "_aline_extract_done.json"
RESULTS_JSON = "aline_feasibility_results.json"
DONE_MARKER = "_aline_done.json"
RESULTS_MD = "ALINE_FEASIBILITY.md"

COMPOSITE_FILE = "cohort_composite.csv"
FEATURE_MATRIX_FILE = "feature_matrix.csv"

OUTCOMES = ("organ_renal", "composite")
HYPOTENSION_BASELINE_COL = "map_auc_below_65"

# BURDEN (cumulative-dose) biomarkers screened for a MONOTONIC dose-response with
# postoperative AKI. These mirror the accepted hypotension-dose paradigm
# (minutes/AUC below MAP 65) but are derived from the arterial WAVEFORM. The
# headline is art_perfusion_failure_burden_min (occult failure at adequate
# pressure); map_auc_below_65 is reused as the POSITIVE-CONTROL comparator (a
# burden already known to be monotonically dose-responsive for AKI).
BURDEN_BIOMARKERS = (
    "art_perfusion_failure_burden_min",   # HEADLINE
    "art_perfusion_failure_burden_auc",
    "art_ppv_burden_min",
    "art_narrow_pp_burden_min",
    "art_low_dpdt_burden_min",
    "art_low_dbp_burden_min",
    "xwave_decoupling_burden_min",
)
POSITIVE_CONTROL_BURDEN = HYPOTENSION_BASELINE_COL   # map_auc_below_65
# Quartiles when enough events, else tertiles when sparse.
DOSE_RESPONSE_MAX_QUANTILES = 4
DOSE_RESPONSE_MIN_QUANTILES = 3
# Minimum cases-with-signal to even attempt a quantile dose-response.
DOSE_RESPONSE_MIN_N = 20

# Power thresholds / honesty flags.
MIN_EVENTS_FEASIBLE = 10      # below this a cell is "feasibility-only, underpowered"
FDR_ALPHA = 0.05
N_BOOTSTRAP = 500

# Track files to purge after each case (the big SNUADC 500 Hz waveforms).
_BIG_SNUADC_TRACKS = ("SNUADC/ART", "SNUADC/PLETH", "SNUADC/ECG_II")

# Waveform features whose AKI signal we screen + whose implied management lever we
# document (filled at runtime from the two feature modules' SPECS; this list is the
# documented "implied lever" map for the report).
IMPLIED_LEVERS = {
    "art_ppv_mean": "high PPV = fluid-responsive/hypovolemic -> FLUID vs pressor",
    "art_ppg_amp_corr": "pressure != perfusion (decoupling) -> phenylephrine vs norepinephrine",
    "central_peripheral_decoupling": "pressure != perfusion -> phenylephrine vs norepinephrine",
    "art_dpdt_max_mean": "low contractility -> INOTROPE vs pressor (noted, not tested)",
    "art_tau_decay_mean": "high tau / low SVR = vasoplegia -> PRESSOR vs fluid (noted, not tested)",
}


# ===========================================================================
# PURE HELPERS (stdlib only -- unit-tested without the science stack)
# ===========================================================================

def _resolve_cache_dir(cfg: dict[str, Any]) -> str:
    data = cfg.get("data")
    if isinstance(data, dict) and data.get("cache_dir"):
        return data["cache_dir"]
    if cfg.get("cache_dir"):
        return cfg["cache_dir"]
    return "vitaldb_aki/cache"


def _resolve_seed(cfg: dict[str, Any]) -> int:
    data = cfg.get("data")
    if isinstance(data, dict) and "seed" in data:
        return int(data["seed"])
    return int(cfg.get("seed", 20260626))


def select_sample(caseids_with_art: list[str], seed: int, n: int = SAMPLE_N) -> list[str]:
    """Deterministic seeded sub-sample of the ART-instrumented caseids.

    Pure / stdlib-only and FULLY DETERMINISTIC given (caseids_with_art, seed, n):
    every candidate gets a stable hash key = sha256(f"{seed}:{caseid}"); we sort by
    that key and take the first ``n``. This is independent of the input order
    (we sort the candidate list first) and of any RNG state, so two runs -- and the
    watchdog's restarts -- always pick the SAME sample, which is what makes the
    EXTRACT stage resumable against a fixed target set.

    Returns at most ``n`` caseids (fewer if <n candidates), as strings, in a
    deterministic order (by hash key).
    """
    uniq = sorted({str(c) for c in caseids_with_art})
    if n >= len(uniq):
        # Still return them hash-ordered for a stable processing order.
        keyed = [(hashlib.sha256(f"{seed}:{c}".encode()).hexdigest(), c) for c in uniq]
        keyed.sort()
        return [c for _, c in keyed]
    keyed = [(hashlib.sha256(f"{seed}:{c}".encode()).hexdigest(), c) for c in uniq]
    keyed.sort()
    return [c for _, c in keyed[:n]]


def incremental_band(auroc_base: float | None, auroc_plus: float | None
                     ) -> dict[str, Any]:
    """Classify the incremental ΔAUROC of (baseline + feature) over baseline.

    Pure / stdlib-only. Returns a dict with delta and a coarse qualitative BAND so
    the feasibility report can rank features without over-interpreting a tiny
    underpowered sample:
        delta >= 0.03  -> "promising"
        0.01 <= delta < 0.03 -> "weak"
        -0.01 <= delta < 0.01 -> "flat"
        delta < -0.01  -> "negative"
    None inputs -> band "undefined", delta None.
    """
    if auroc_base is None or auroc_plus is None:
        return {"delta": None, "band": "undefined"}
    delta = float(auroc_plus) - float(auroc_base)
    if delta >= 0.03:
        band = "promising"
    elif delta >= 0.01:
        band = "weak"
    elif delta >= -0.01:
        band = "flat"
    else:
        band = "negative"
    return {"delta": round(delta, 4), "band": band}


def rank_auroc(auroc: float | None) -> float:
    """Discrimination distance from chance: |AUROC - 0.5| (None -> -1 so it sorts
    last). Pure helper used to rank features by univariate signal strength."""
    if auroc is None:
        return -1.0
    try:
        return abs(float(auroc) - 0.5)
    except (TypeError, ValueError):
        return -1.0


def benjamini_hochberg(pvalues: list[float | None], alpha: float = FDR_ALPHA
                       ) -> list[float | None]:
    """BH step-up FDR q-values, same-order as input; None/NaN pass through as None.

    Stdlib-only re-implementation (mirrors discovery_screen.benjamini_hochberg) so
    the screen helper set is testable without importing the science stack.
    """
    indexed = []
    for i, p in enumerate(pvalues):
        if p is None:
            continue
        try:
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if pf != pf:  # NaN
            continue
        indexed.append((i, pf))
    m = len(indexed)
    q: list[float | None] = [None] * len(pvalues)
    if m == 0:
        return q
    indexed.sort(key=lambda t: t[1])
    raw = [(idx, p * m / (rank + 1)) for rank, (idx, p) in enumerate(indexed)]
    running_min = float("inf")
    for rank in range(m - 1, -1, -1):
        idx, qr = raw[rank]
        running_min = min(running_min, qr)
        q[idx] = min(running_min, 1.0)
    return q


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in ("", "nan", "na", "none"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# ===========================================================================
# DOSE-RESPONSE / MONOTONICITY cores (pure, stdlib-only -- unit-tested without
# the science stack). These implement the "does the burden monotonically track
# AKI risk" check that mirrors the accepted hypotension-dose dose-response.
# ===========================================================================

def quantile_breaks(values: list[float], n_quantiles: int) -> list[float]:
    """Interior quantile cut-points (n_quantiles-1 of them) for `values`.

    Pure / stdlib-only. Uses the (k/n_quantiles) sample percentiles via linear
    interpolation between order statistics (numpy-free). Returns the interior
    breakpoints (e.g. for quartiles: the 25th/50th/75th percentile). Duplicate
    breakpoints (heavy ties, common for burdens that are 0.0 for many cases) are
    NOT removed here; assign_quantiles handles ties so empty bins don't appear.
    """
    xs = sorted(float(v) for v in values)
    n = len(xs)
    if n == 0 or n_quantiles < 2:
        return []
    breaks: list[float] = []
    for k in range(1, n_quantiles):
        q = k / n_quantiles
        pos = q * (n - 1)
        lo = int(math.floor(pos))
        hi = int(math.ceil(pos))
        if lo == hi:
            breaks.append(xs[lo])
        else:
            frac = pos - lo
            breaks.append(xs[lo] * (1.0 - frac) + xs[hi] * frac)
    return breaks


def assign_quantiles(values: list[float], n_quantiles: int) -> list[int]:
    """Assign each value to a 0-based quantile bin index.

    Pure / stdlib-only. A value is placed in the lowest bin whose upper break it
    does NOT exceed (<= break), so ties cluster in the lower bin (the natural,
    reproducible choice when a burden has many identical 0.0 values). The result
    has the same length/order as `values`; bins range 0..(n_quantiles-1) but some
    bins may be empty under heavy ties (the dose-response table then reports the
    non-empty bins only).
    """
    breaks = quantile_breaks(values, n_quantiles)
    out: list[int] = []
    for v in values:
        fv = float(v)
        b = 0
        for thr in breaks:
            if fv <= thr:
                break
            b += 1
        out.append(b)
    return out


def dose_response_table(values: list[float], events: list[int],
                        n_quantiles: int) -> dict[str, Any]:
    """Per-quantile event RATE table + a monotonic-trend assessment.

    Pure / stdlib-only.

    Parameters
    ----------
    values : burden value per case (same length as events).
    events : 0/1 outcome per case.
    n_quantiles : requested number of quantiles (collapsed to the number of
        NON-EMPTY bins actually realised, so heavy-tie burdens don't show
        phantom empty quantiles).

    Returns dict with:
      n, events, n_quantiles_used,
      quantiles : list of {q, n, events, rate, lo, hi} (ascending burden),
      is_monotonic : True iff the realised per-quantile rates are
                     non-decreasing across ascending burden,
      spearman_rho : Spearman rho of (quantile rank vs binary event) -- a
                     stdlib rank-correlation as a coarse monotone-trend signal,
      cochran_armitage_z, cochran_armitage_p : CA linear-trend test across the
                     ordered quantiles (normal approximation, two-sided).
    """
    n = len(values)
    res: dict[str, Any] = {
        "n": n, "events": int(sum(events)),
        "n_quantiles_used": 0, "quantiles": [],
        "is_monotonic": None, "spearman_rho": None,
        "cochran_armitage_z": None, "cochran_armitage_p": None,
    }
    if n < DOSE_RESPONSE_MIN_N or n != len(events):
        return res
    if len(set(events)) < 2:
        return res

    bins = assign_quantiles(values, n_quantiles)
    # Group by realised (non-empty) bin, re-ranked to a dense 0..K-1 ascending.
    used = sorted(set(bins))
    remap = {b: i for i, b in enumerate(used)}
    K = len(used)
    res["n_quantiles_used"] = K
    if K < 2:
        return res

    counts = [0] * K
    ev = [0] * K
    for b, e in zip(bins, events):
        idx = remap[b]
        counts[idx] += 1
        ev[idx] += int(e)

    quantiles = []
    rates = []
    for i in range(K):
        rate = (ev[i] / counts[i]) if counts[i] > 0 else None
        rates.append(rate)
        # value range of this realised bin
        bin_vals = [values[j] for j in range(n) if remap[bins[j]] == i]
        quantiles.append({
            "q": i, "n": counts[i], "events": ev[i],
            "rate": round(rate, 4) if rate is not None else None,
            "lo": round(min(bin_vals), 4) if bin_vals else None,
            "hi": round(max(bin_vals), 4) if bin_vals else None,
        })
    res["quantiles"] = quantiles

    # Monotonic = rates non-decreasing across ascending burden quantiles.
    defined = [r for r in rates if r is not None]
    if len(defined) >= 2:
        res["is_monotonic"] = all(
            rates[i] is not None and rates[i + 1] is not None
            and rates[i + 1] >= rates[i] - 1e-12
            for i in range(K - 1)
        )

    # Spearman rho of (quantile rank, event) -- coarse monotone-trend signal.
    ranks = [float(remap[b]) for b in bins]
    res["spearman_rho"] = _spearman_rho(ranks, [float(e) for e in events])

    # Cochran-Armitage trend test across ordered quantiles (scores = bin index).
    z, p = cochran_armitage_trend(counts, ev)
    res["cochran_armitage_z"] = round(z, 4) if z is not None else None
    res["cochran_armitage_p"] = round(p, 6) if p is not None else None
    return res


def _spearman_rho(x: list[float], y: list[float]) -> float | None:
    """Spearman rank correlation (stdlib; average ranks for ties). None if
    degenerate (n<3 or a constant series)."""
    n = len(x)
    if n < 3 or n != len(y):
        return None

    def _rank(a: list[float]) -> list[float]:
        order = sorted(range(len(a)), key=lambda i: a[i])
        ranks = [0.0] * len(a)
        i = 0
        while i < len(a):
            j = i
            while j < len(a) and a[order[j]] == a[order[i]]:
                j += 1
            avg = (i + j - 1) / 2.0 + 1.0  # 1-based average rank
            for k in range(i, j):
                ranks[order[k]] = avg
            i = j
        return ranks

    rx = _rank(x)
    ry = _rank(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    sxy = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    sxx = sum((rx[i] - mx) ** 2 for i in range(n))
    syy = sum((ry[i] - my) ** 2 for i in range(n))
    if sxx <= 0 or syy <= 0:
        return None
    return round(sxy / math.sqrt(sxx * syy), 4)


def cochran_armitage_trend(counts: list[int], events: list[int]
                           ) -> tuple[float | None, float | None]:
    """Cochran-Armitage trend test across ordered groups (scores = 0..K-1).

    Pure / stdlib-only. Tests for a LINEAR trend in the event proportion across
    the ordered quantile groups. `counts[i]` = cases in group i, `events[i]` =
    events in group i. Uses the standard CA statistic with a normal
    approximation (two-sided p via the error function). Returns (z, p), or
    (None, None) if degenerate (one group, no events, or all-or-nothing events).

    CA statistic
    ------------
        T  = sum_i s_i * (a_i - n_i * pbar)      (s_i = group score = i)
        with pbar = total_events / total_n, and
        Var(T) = pbar*(1-pbar) * [ sum_i n_i s_i^2 - (sum_i n_i s_i)^2 / N ]
        z = T / sqrt(Var(T))
    """
    K = len(counts)
    if K < 2 or K != len(events):
        return None, None
    N = sum(counts)
    A = sum(events)
    if N <= 0 or A <= 0 or A >= N:
        return None, None
    pbar = A / N
    scores = list(range(K))
    T = sum(scores[i] * (events[i] - counts[i] * pbar) for i in range(K))
    sum_ns = sum(counts[i] * scores[i] for i in range(K))
    sum_ns2 = sum(counts[i] * scores[i] ** 2 for i in range(K))
    var = pbar * (1.0 - pbar) * (sum_ns2 - (sum_ns ** 2) / N)
    if var <= 0:
        return None, None
    z = T / math.sqrt(var)
    # Two-sided p via the normal CDF (erf).
    p = 2.0 * (1.0 - _norm_cdf(abs(z)))
    return z, max(0.0, min(1.0, p))


def _norm_cdf(z: float) -> float:
    """Standard-normal CDF via math.erf (stdlib)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ===========================================================================
# STAGE 1 -- EXTRACT (resumable, disk-bounded)
# ===========================================================================

def _existing_sample_caseids(path: str) -> set[str]:
    """Caseids already present in aline_sample.csv (resumability)."""
    out: set[str] = set()
    if not os.path.exists(path):
        return out
    try:
        with open(path, "r", newline="", encoding="utf-8") as fh:
            reader = _csv.DictReader(fh)
            for r in reader:
                cid = r.get("caseid")
                if cid is not None and str(cid).strip() != "":
                    out.add(str(cid).strip())
    except Exception:
        pass
    return out


def _art_caseids(cfg: dict[str, Any]) -> list[str]:
    """All caseids whose /trks index contains SNUADC/ART (no waveform download)."""
    from vitaldb_aki.data import tracks as _T
    # tid_for/available_tracks populate the module-level index from /trks.
    _T.tid_for(cfg, "__warm__", ART_TRACK_NAME)  # force index build (returns None)
    idx = _T._INDEX or {}
    return sorted({cid for (cid, tn) in idx if tn == ART_TRACK_NAME})


def _merge_feature_rows(aline_row: dict[str, Any],
                        cross_row: dict[str, Any]) -> dict[str, Any]:
    """Merge the aline + cross feature dicts for one case (cross keys win on the
    rare overlap, but the two namespaces are disjoint by design)."""
    merged: dict[str, Any] = {}
    merged.update(aline_row or {})
    merged.update(cross_row or {})
    return merged


def _append_rows(path: str, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Append rows to the sample CSV, writing the header iff the file is new."""
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


def run_extract(cfg: dict[str, Any]) -> dict[str, Any]:
    """EXTRACT stage: build/extend cache/aline_sample.csv for the seeded ART sample.

    Resumable + disk-bounded. Returns a small summary dict. Writes
    cache/_aline_extract_done.json once every sampled case has a row.
    """
    from vitaldb_aki.data.client import fetch_cases
    from vitaldb_aki.data import tracks as _T
    from vitaldb_aki.features import aline_morphology as _aline
    from vitaldb_aki.features import cross_waveform as _cross

    cache_dir = _resolve_cache_dir(cfg)
    os.makedirs(cache_dir, exist_ok=True)
    sample_path = os.path.join(cache_dir, SAMPLE_CSV)
    seed = _resolve_seed(cfg)

    art_ids = _art_caseids(cfg)
    sample = select_sample(art_ids, seed, SAMPLE_N)
    print(f"[aline_feasibility] {len(art_ids)} cases have {ART_TRACK_NAME}; "
          f"seeded sample N={len(sample)} (target {SAMPLE_N}, seed={seed})")

    done = _existing_sample_caseids(sample_path)
    todo = [c for c in sample if c not in done]
    print(f"[aline_feasibility] {len(done)} already extracted; {len(todo)} to go")

    if not todo:
        _write_extract_done(cache_dir, sample, len(done))
        return {"sampled": len(sample), "extracted": len(done), "new": 0}

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    # The column set = aline SPECS + cross SPECS, with caseid first.
    feat_names = [s.name for s in _aline.SPECS] + [s.name for s in _cross.SPECS]
    fieldnames = ["caseid"] + feat_names

    buffer: list[dict[str, Any]] = []
    n_new = 0
    for i, cid in enumerate(todo, 1):
        try:
            aline_out = _aline.extract(cfg, cases_by_id, [cid])
            cross_out = _cross.extract(cfg, cases_by_id, [cid])
            row = _merge_feature_rows(aline_out.get(cid, {}), cross_out.get(cid, {}))
            row["caseid"] = cid
            buffer.append(row)
            n_new += 1
        except Exception as exc:  # never let one bad case abort the long run
            print(f"[aline_feasibility]   case {cid} FAILED: "
                  f"{type(exc).__name__}: {exc}")
        finally:
            # STREAM: purge this case's big raw SNUADC waveforms so the ~50-100 MB
            # ART/PPG/ECG never accumulates. cross_waveform.extract already purges
            # internally, but aline_morphology caches ART permanently -> purge here.
            for tn in _BIG_SNUADC_TRACKS:
                try:
                    _T.purge_track(cfg, cid, tn)
                except Exception:
                    pass

        # Flush every FLUSH_EVERY cases (and report progress / watchdog signal).
        if len(buffer) >= FLUSH_EVERY:
            _append_rows(sample_path, buffer, fieldnames)
            buffer = []
            print(f"[aline_feasibility]   progress {i}/{len(todo)} "
                  f"(+{n_new} new rows; {len(done) + n_new}/{len(sample)} total)",
                  flush=True)

    if buffer:
        _append_rows(sample_path, buffer, fieldnames)
        print(f"[aline_feasibility]   final flush "
              f"({len(done) + n_new}/{len(sample)} total)", flush=True)

    total_done = _existing_sample_caseids(sample_path)
    if len(set(sample) - total_done) == 0:
        _write_extract_done(cache_dir, sample, len(total_done))

    return {"sampled": len(sample), "extracted": len(total_done), "new": n_new}


def _write_extract_done(cache_dir: str, sample: list[str], n_extracted: int) -> None:
    path = os.path.join(cache_dir, EXTRACT_DONE_MARKER)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"n_sampled": len(sample), "n_extracted": n_extracted}, fh, indent=2)
    print(f"[aline_feasibility] EXTRACT complete -> {path}", flush=True)


# ===========================================================================
# STAGE 2 -- SCREEN
# ===========================================================================

def _load_outcomes_and_baseline(cfg: dict[str, Any]):
    """Load {caseid: {organ_renal, composite}} from cohort_composite.csv and
    {caseid: map_auc_below_65} from feature_matrix.csv. Returns (outcomes, baseline,
    subjectid_map)."""
    cache_dir = _resolve_cache_dir(cfg)
    comp_path = os.path.join(cache_dir, COMPOSITE_FILE)
    fm_path = os.path.join(cache_dir, FEATURE_MATRIX_FILE)

    outcomes: dict[str, dict[str, float | None]] = {}
    subj: dict[str, str] = {}
    if os.path.exists(comp_path):
        with open(comp_path, "r", newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cid = str(r.get("caseid", "")).strip()
                if not cid:
                    continue
                outcomes[cid] = {oc: _to_float(r.get(oc)) for oc in OUTCOMES}
                if r.get("subjectid") is not None:
                    subj[cid] = str(r.get("subjectid")).strip() or cid

    baseline: dict[str, float | None] = {}
    if os.path.exists(fm_path):
        with open(fm_path, "r", newline="", encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cid = str(r.get("caseid", "")).strip()
                if not cid:
                    continue
                baseline[cid] = _to_float(r.get(HYPOTENSION_BASELINE_COL))
                if cid not in subj and r.get("subjectid") is not None:
                    subj[cid] = str(r.get("subjectid")).strip() or cid
    return outcomes, baseline, subj


def _load_sample(cfg: dict[str, Any]):
    """Load cache/aline_sample.csv as (list_of_rows, feature_names)."""
    cache_dir = _resolve_cache_dir(cfg)
    path = os.path.join(cache_dir, SAMPLE_CSV)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found -- run the EXTRACT stage first "
            "(python vitaldb_aki/analysis/aline_feasibility.py).")
    rows: list[dict[str, str]] = []
    with open(path, "r", newline="", encoding="utf-8") as fh:
        reader = _csv.DictReader(fh)
        feat_names = [c for c in (reader.fieldnames or []) if c != "caseid"]
        for r in reader:
            rows.append(dict(r))
    return rows, feat_names


def _auroc(y: list[int], x: list[float]) -> float | None:
    """Univariate AUROC of score x vs binary y (rank/Mann-Whitney). numpy lazy.

    Higher-x-is-higher-risk is NOT assumed: we return the AUROC as-is (a value
    < 0.5 means the feature is protective on this orientation). Returns None if a
    single class or < 2 usable pairs.
    """
    import numpy as np

    yy = np.asarray(y, dtype=int)
    xx = np.asarray(x, dtype=float)
    good = np.isfinite(xx)
    yy, xx = yy[good], xx[good]
    if yy.size < 2 or yy.min() == yy.max():
        return None
    pos = xx[yy == 1]
    neg = xx[yy == 0]
    if pos.size == 0 or neg.size == 0:
        return None
    # Mann-Whitney U / (n_pos * n_neg) via midrank.
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(order.size, dtype=float)
    ranks[order] = np.arange(1, order.size + 1, dtype=float)
    # Handle ties via average ranks.
    combined = np.concatenate([pos, neg])
    _, inv, counts = np.unique(combined, return_inverse=True, return_counts=True)
    # Average-rank correction.
    sorted_idx = np.argsort(combined, kind="mergesort")
    avg_ranks = np.empty(combined.size, dtype=float)
    i = 0
    sc = combined[sorted_idx]
    base = np.arange(1, combined.size + 1, dtype=float)
    while i < sc.size:
        j = i
        while j < sc.size and sc[j] == sc[i]:
            j += 1
        avg_ranks[sorted_idx[i:j]] = base[i:j].mean()
        i = j
    r_pos = avg_ranks[: pos.size].sum()
    auc = (r_pos - pos.size * (pos.size + 1) / 2.0) / (pos.size * neg.size)
    return float(auc)


def _incremental_logit(y, baseline_x, feature_x, groups, seed=0):
    """Incremental AUROC + LR p-value of (baseline + feature) over baseline alone,
    with a patient-clustered bootstrap CI on ΔAUROC.

    A logistic model outcome ~ baseline vs outcome ~ baseline + feature is fit on
    the SAME rows; ΔAUROC is the in-sample AUROC gain (feasibility -- not CV; the
    sample is too small for nested CV and this is screening only). LR p-value from
    the deviance difference (chi-square, 1 df). numpy/sklearn/scipy lazy.

    Returns a dict (auroc_base, auroc_plus, delta_auroc, lr_p, delta_ci, n, events).
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    yy = np.asarray(y, dtype=int)
    b = np.asarray(baseline_x, dtype=float)
    f = np.asarray(feature_x, dtype=float)
    g = np.asarray(groups)
    good = np.isfinite(b) & np.isfinite(f)
    yy, b, f, g = yy[good], b[good], f[good], g[good]
    n = int(yy.size)
    events = int(yy.sum()) if n else 0
    base_result = {"auroc_base": None, "auroc_plus": None, "delta_auroc": None,
                   "lr_p": None, "delta_ci": [None, None], "n": n, "events": events}
    if n < 20 or events < 3 or yy.min() == yy.max():
        return base_result

    def _fit_predict(X):
        # Standardise columns for conditioning; constant cols are dropped.
        Xs = X.copy()
        for c in range(Xs.shape[1]):
            sd = Xs[:, c].std()
            if sd > 0:
                Xs[:, c] = (Xs[:, c] - Xs[:, c].mean()) / sd
        lr = LogisticRegression(max_iter=1000, solver="lbfgs", C=1e6)
        lr.fit(Xs, yy)
        p = lr.predict_proba(Xs)[:, 1]
        # Deviance = -2 * log-likelihood.
        eps = 1e-12
        ll = float(np.sum(yy * np.log(p + eps) + (1 - yy) * np.log(1 - p + eps)))
        return p, -2.0 * ll

    Xb = b.reshape(-1, 1)
    Xp = np.column_stack([b, f])
    try:
        pb, dev_b = _fit_predict(Xb)
        pp, dev_p = _fit_predict(Xp)
    except Exception:
        return base_result

    auroc_base = _auroc(yy.tolist(), pb.tolist())
    auroc_plus = _auroc(yy.tolist(), pp.tolist())
    delta = (auroc_plus - auroc_base) if (auroc_base is not None
                                          and auroc_plus is not None) else None

    # Likelihood-ratio test (1 df: the added feature).
    from scipy import stats as _stats
    lr_stat = max(0.0, dev_b - dev_p)
    lr_p = float(1.0 - _stats.chi2.cdf(lr_stat, df=1))

    # Patient-clustered bootstrap CI on ΔAUROC.
    rng = np.random.default_rng(seed)
    uniq = np.unique(g)
    idx_by_g = {u: np.where(g == u)[0] for u in uniq}
    deltas = []
    for _ in range(N_BOOTSTRAP):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_g[u] for u in pick])
        yb = yy[idx]
        if yb.min() == yb.max():
            continue
        ab = _auroc(yb.tolist(), pb[idx].tolist())
        ap = _auroc(yb.tolist(), pp[idx].tolist())
        if ab is not None and ap is not None:
            deltas.append(ap - ab)
    if deltas:
        lo, hi = float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))
    else:
        lo, hi = None, None

    return {
        "auroc_base": round(auroc_base, 4) if auroc_base is not None else None,
        "auroc_plus": round(auroc_plus, 4) if auroc_plus is not None else None,
        "delta_auroc": round(delta, 4) if delta is not None else None,
        "lr_p": lr_p,
        "delta_ci": [round(lo, 4) if lo is not None else None,
                     round(hi, 4) if hi is not None else None],
        "n": n, "events": events,
    }


def _screen_feature(rows, feat, outcome, baseline_by_cid, outcomes_by_cid,
                    subj_by_cid, seed):
    """Screen one (feature, outcome): availability subset -> univariate AUROC +
    incremental over hypotension baseline. Returns a result dict."""
    y: list[int] = []
    xf: list[float] = []
    xb: list[float] = []
    grp: list[str] = []
    n_avail = 0
    for r in rows:
        cid = str(r.get("caseid", "")).strip()
        if str(r.get("aline_available", "")).strip() not in ("1", "1.0"):
            continue
        n_avail += 1
        oc = outcomes_by_cid.get(cid, {}).get(outcome)
        fv = _to_float(r.get(feat))
        bv = baseline_by_cid.get(cid)
        if oc is None or fv is None:
            continue
        y.append(int(round(oc)))
        xf.append(fv)
        xb.append(bv if bv is not None else 0.0)
        grp.append(subj_by_cid.get(cid, cid))

    n = len(y)
    events = sum(y)
    res: dict[str, Any] = {
        "feature": feat, "outcome": outcome,
        "n": n, "events": events,
        "n_aline_available": n_avail,
        "underpowered": bool(events < MIN_EVENTS_FEASIBLE or n < 20),
        "power_flag": "feasibility-only, underpowered",
    }
    if n < 20 or events < 3 or len(set(y)) < 2:
        res["auroc"] = None
        res["incremental"] = None
        return res

    res["auroc"] = (lambda a: round(a, 4) if a is not None else None)(
        _auroc(y, xf))
    inc = _incremental_logit(y, xb, xf, grp, seed=seed)
    res["incremental"] = inc
    res["incremental_band"] = incremental_band(
        inc.get("auroc_base"), inc.get("auroc_plus"))
    return res


# --- Dose-response / monotonicity screen -----------------------------------

def _logistic_linear_trend_p(quantile_ranks: list[int], y: list[int]) -> float | None:
    """LR p-value for a linear logistic trend of `y` on the quantile rank.

    Fits y ~ 1 vs y ~ 1 + quantile_rank and returns the chi-square(1) LR p from
    the deviance difference. numpy/sklearn/scipy lazy. None if degenerate.
    """
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from scipy import stats as _stats
    except Exception:
        return None

    yy = np.asarray(y, dtype=int)
    x = np.asarray(quantile_ranks, dtype=float)
    if yy.size < DOSE_RESPONSE_MIN_N or len(set(yy.tolist())) < 2:
        return None
    if x.std() <= 0:
        return None

    def _dev(X):
        lr = LogisticRegression(max_iter=1000, solver="lbfgs", C=1e6)
        lr.fit(X, yy)
        p = lr.predict_proba(X)[:, 1]
        eps = 1e-12
        ll = float(np.sum(yy * np.log(p + eps) + (1 - yy) * np.log(1 - p + eps)))
        return -2.0 * ll

    try:
        # Intercept-only baseline: a single constant column (LogisticRegression
        # always fits an intercept, so the "null" is a degenerate-variance col).
        x0 = np.zeros((yy.size, 1))
        xc = ((x - x.mean()) / x.std()).reshape(-1, 1)
        dev0 = _dev(x0)
        dev1 = _dev(xc)
    except Exception:
        return None
    stat = max(0.0, dev0 - dev1)
    return float(1.0 - _stats.chi2.cdf(stat, df=1))


def _dose_response_for_burden(rows, burden, outcome, outcomes_by_cid,
                              baseline_by_cid, subj_by_cid, seed,
                              require_aline=True):
    """Dose-response + monotonicity + incremental-over-hypotension for ONE burden.

    Builds the available-signal subset (cases with a non-None burden value and a
    non-None outcome; for waveform burdens also gated on aline_available), then:
      * quantiles the burden (quartiles, or tertiles when sparse) and reports the
        per-quantile event RATE table,
      * tests monotonic trend (Cochran-Armitage + Spearman rho + logistic-trend p),
      * incremental AUROC of the CONTINUOUS burden over map_auc_below_65
        (reusing _incremental_logit -- logistic base vs base+burden, DeLong-style
        in-sample ΔAUROC + patient-clustered bootstrap CI + LR p).

    The positive-control burden (map_auc_below_65) is screened with the SAME path
    (its incremental-over-itself is ~0 by construction; the dose-response table is
    the meaningful comparator). Returns a result dict. numpy/sklearn lazy (only in
    _incremental_logit / _logistic_linear_trend_p).
    """
    vals: list[float] = []
    evs: list[int] = []
    xb: list[float] = []   # hypotension baseline for the incremental test
    grp: list[str] = []
    n_avail = 0
    is_positive_control = (burden == POSITIVE_CONTROL_BURDEN)

    for r in rows:
        cid = str(r.get("caseid", "")).strip()
        if require_aline and not is_positive_control:
            if str(r.get("aline_available", "")).strip() not in ("1", "1.0"):
                continue
        oc = outcomes_by_cid.get(cid, {}).get(outcome)
        # The positive control lives in the feature matrix (baseline), not the
        # sample CSV; everything else is a sample-CSV column.
        if is_positive_control:
            bv = baseline_by_cid.get(cid)
        else:
            bv = _to_float(r.get(burden))
        base = baseline_by_cid.get(cid)
        if oc is None or bv is None:
            continue
        n_avail += 1
        vals.append(bv)
        evs.append(int(round(oc)))
        xb.append(base if base is not None else 0.0)
        grp.append(subj_by_cid.get(cid, cid))

    n = len(vals)
    events = sum(evs)
    res: dict[str, Any] = {
        "burden": burden, "outcome": outcome,
        "is_positive_control": is_positive_control,
        "n": n, "events": events, "n_signal_available": n_avail,
        "underpowered": bool(events < MIN_EVENTS_FEASIBLE or n < DOSE_RESPONSE_MIN_N),
        "power_flag": "feasibility-only, underpowered",
        "dose_response": None, "incremental": None, "logistic_trend_p": None,
    }
    if n < DOSE_RESPONSE_MIN_N or events < 3 or len(set(evs)) < 2:
        return res

    # Quartiles when enough events, else tertiles when sparse.
    nq = (DOSE_RESPONSE_MAX_QUANTILES if events >= 2 * DOSE_RESPONSE_MAX_QUANTILES
          else DOSE_RESPONSE_MIN_QUANTILES)
    dr = dose_response_table(vals, evs, nq)
    res["dose_response"] = dr

    # Logistic linear-trend p on the quantile rank.
    bins = assign_quantiles(vals, dr.get("n_quantiles_used") or nq)
    res["logistic_trend_p"] = _logistic_linear_trend_p(bins, evs)

    # Incremental AUROC of the CONTINUOUS burden over the hypotension baseline.
    # (For the positive control this is ~0 by construction -- base == feature.)
    res["incremental"] = _incremental_logit(evs, xb, vals, grp, seed=seed)
    res["incremental_band"] = incremental_band(
        res["incremental"].get("auroc_base"),
        res["incremental"].get("auroc_plus"))
    return res


def run_dose_response(cfg, rows, outcomes_by_cid, baseline_by_cid,
                      subj_by_cid, seed):
    """Dose-response / monotonicity screen across all BURDEN biomarkers + the
    map_auc_below_65 positive control, for organ_renal + composite. BH-FDR is
    applied across the burden biomarkers' Cochran-Armitage trend p-values (the
    positive control is excluded from the FDR set -- it is a reference, not a
    discovery). Returns a dict consumed by run_screen + the report writer.
    """
    burdens = [POSITIVE_CONTROL_BURDEN] + [
        b for b in BURDEN_BIOMARKERS if b != POSITIVE_CONTROL_BURDEN]
    # Only screen burdens that actually appear as a column (or the positive
    # control, which comes from the feature matrix).
    present_cols: set[str] = set()
    for r in rows:
        present_cols.update(r.keys())
    screened = [b for b in burdens
                if b == POSITIVE_CONTROL_BURDEN or b in present_cols]

    grid: list[dict[str, Any]] = []
    for b in screened:
        for oc in OUTCOMES:
            grid.append(_dose_response_for_burden(
                rows, b, oc, outcomes_by_cid, baseline_by_cid,
                subj_by_cid, seed))

    # BH-FDR across the CA trend p-values of the BURDEN cells (exclude the
    # positive control + underpowered/undefined cells).
    ca_pvals: list[float | None] = []
    for c in grid:
        if c.get("is_positive_control"):
            ca_pvals.append(None)
            continue
        dr = c.get("dose_response") or {}
        ca_pvals.append(dr.get("cochran_armitage_p"))
    qvals = benjamini_hochberg(ca_pvals, alpha=FDR_ALPHA)
    for c, q in zip(grid, qvals):
        c["ca_trend_q"] = round(q, 6) if q is not None else None

    return {
        "headline_burden": "art_perfusion_failure_burden_min",
        "positive_control": POSITIVE_CONTROL_BURDEN,
        "burdens_screened": screened,
        "grid": grid,
        "power_caveat": (
            "Dose-response is computed on the ~600-case feasibility sample "
            "(~20 renal events); EVERY quantile cell is underpowered. This is a "
            "GO/NO-GO + does-it-look-monotonic check, NOT a definitive "
            "dose-response. ~20 events split across 3-4 quantiles leaves "
            "single-digit events per bin."),
    }


# --- Predictive-enrichment / treatment-interaction look --------------------

def _build_exposure_frame(cfg, sample_cids):
    """Build a pandas frame of the sampled cases with the actionable-management
    exposures (any_vasopressor, phenylephrine_predominant, high/low_fluid, ...)
    via actionable_targets.define_exposures, reading /cases. pandas lazy."""
    import pandas as pd
    from vitaldb_aki.analysis import actionable_targets as _at

    cache_dir = _resolve_cache_dir(cfg)
    cases_path = os.path.join(cache_dir, "cases.csv")
    if not os.path.exists(cases_path):
        return None
    cases = pd.read_csv(cases_path)
    cases.columns = [c.lstrip("﻿") for c in cases.columns]
    cases["caseid"] = cases["caseid"].astype(str)
    cases = cases[cases["caseid"].isin([str(c) for c in sample_cids])].copy()
    if cases.empty:
        return None
    return _at.define_exposures(cases)


def _interaction_look(y, action, biomarker, groups, seed=0):
    """Predictive-enrichment look: does `biomarker` (median split) MODIFY the
    effect of the binary management `action` on `y`?

    Reports, per biomarker stratum (low vs high by median), the crude action->y
    risk difference + n/events, AND a single logistic interaction term
    y ~ action + bio_high + action:bio_high (interaction OR + bootstrap p).
    Feasibility-grade: crude (unweighted) within-stratum risk + a small logistic
    interaction; underpowered by construction. numpy/sklearn lazy.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    yy = np.asarray(y, dtype=int)
    a = np.asarray(action, dtype=float)
    bm = np.asarray(biomarker, dtype=float)
    g = np.asarray(groups)
    good = np.isfinite(a) & np.isfinite(bm)
    yy, a, bm, g = yy[good], a[good], bm[good], g[good]
    n = int(yy.size)
    if n < 20 or yy.sum() < 3 or len(np.unique(a)) < 2:
        return {"n": n, "events": int(yy.sum()),
                "note": "insufficient data for interaction (feasibility cell)",
                "underpowered": True}

    med = float(np.median(bm))
    bio_high = (bm > med).astype(int)

    def _stratum(mask):
        ys = yy[mask]
        as_ = a[mask]
        if ys.size == 0 or len(np.unique(as_)) < 2:
            return {"n": int(ys.size), "events": int(ys.sum()),
                    "risk_action": None, "risk_no_action": None, "rd": None}
        r1 = float(ys[as_ == 1].mean()) if (as_ == 1).any() else None
        r0 = float(ys[as_ == 0].mean()) if (as_ == 0).any() else None
        rd = (r1 - r0) if (r1 is not None and r0 is not None) else None
        return {"n": int(ys.size), "events": int(ys.sum()),
                "risk_action": round(r1, 4) if r1 is not None else None,
                "risk_no_action": round(r0, 4) if r0 is not None else None,
                "rd": round(rd, 4) if rd is not None else None}

    low = _stratum(bio_high == 0)
    high = _stratum(bio_high == 1)

    # Logistic interaction term.
    X = np.column_stack([a, bio_high, a * bio_high])
    inter_or = None
    inter_p = None
    try:
        lr = LogisticRegression(max_iter=1000, solver="lbfgs", C=1e6)
        lr.fit(X, yy)
        b_inter = float(lr.coef_[0][2])
        inter_or = round(math.exp(b_inter), 4)
        # Bootstrap p (cluster on patient).
        rng = np.random.default_rng(seed)
        uniq = np.unique(g)
        idx_by_g = {u: np.where(g == u)[0] for u in uniq}
        boot = []
        for _ in range(N_BOOTSTRAP):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            idx = np.concatenate([idx_by_g[u] for u in pick])
            yb = yy[idx]
            if yb.min() == yb.max():
                continue
            try:
                lrb = LogisticRegression(max_iter=1000, solver="lbfgs", C=1e6)
                lrb.fit(X[idx], yb)
                boot.append(float(lrb.coef_[0][2]))
            except Exception:
                continue
        if boot:
            arr = np.asarray(boot)
            if b_inter >= 0:
                inter_p = 2.0 * float((arr <= 0).mean())
            else:
                inter_p = 2.0 * float((arr >= 0).mean())
            inter_p = round(min(1.0, max(0.0, inter_p)), 4)
    except Exception:
        pass

    return {
        "n": n, "events": int(yy.sum()),
        "biomarker_median": round(med, 4),
        "low_stratum": low, "high_stratum": high,
        "interaction_or": inter_or,
        "interaction_p_bootstrap": inter_p,
        "underpowered": True,
        "power_flag": "hypothesis-generating, underpowered",
    }


def run_predictive_enrichment(cfg, rows, outcomes_by_cid, subj_by_cid, seed):
    """The two pre-specified treatment-interaction looks on the feasibility sample.

    (1) art_ppv_mean x (fluid vs pressor)         -> action = high_fluid
    (2) decoupling   x (phenylephrine-predominant)-> action = phenylephrine_predominant

    Both are reported for organ_renal + composite, with prominent underpowered
    flags. Returns a dict; gracefully degrades to {"available": False, ...} when
    /cases or sklearn is unavailable.
    """
    out: dict[str, Any] = {"available": False, "looks": {}}
    try:
        import numpy as np  # noqa: F401
    except Exception:
        out["note"] = "numpy unavailable"
        return out

    sample_cids = [str(r.get("caseid", "")).strip() for r in rows]
    try:
        exp = _build_exposure_frame(cfg, sample_cids)
    except Exception as e:
        out["note"] = f"exposure frame failed: {type(e).__name__}: {e}"
        return out
    if exp is None:
        out["note"] = "cases.csv not found / no overlap -> levers not testable"
        return out

    # Map caseid -> exposure row.
    exp_by_cid = {str(r["caseid"]): r for _, r in exp.iterrows()}

    # biomarker_col, action_col, lever label
    specs = [
        ("art_ppv_mean", "high_fluid",
         "high PPV (fluid-responsive) -> does generous FLUID help vs not?"),
        ("central_peripheral_decoupling", "phenylephrine_predominant",
         "central-peripheral decoupling -> is phenylephrine-predominant worse?"),
    ]
    # Fall back to art_ppg_amp_corr if decoupling column is absent in the sample.
    feat_present = set()
    for r in rows:
        feat_present.update(r.keys())
    if "central_peripheral_decoupling" not in feat_present and "art_ppg_amp_corr" in feat_present:
        specs[1] = ("art_ppg_amp_corr", "phenylephrine_predominant",
                    "low ART-PPG coupling (decoupled) -> is phenylephrine-predominant worse?")

    any_ok = False
    for bio_col, action_col, lever in specs:
        look_block: dict[str, Any] = {"lever": lever, "action": action_col,
                                      "biomarker": bio_col, "outcomes": {}}
        for oc in OUTCOMES:
            y, bio, act, grp = [], [], [], []
            for r in rows:
                cid = str(r.get("caseid", "")).strip()
                if str(r.get("aline_available", "")).strip() not in ("1", "1.0"):
                    continue
                ocv = outcomes_by_cid.get(cid, {}).get(oc)
                bv = _to_float(r.get(bio_col))
                erow = exp_by_cid.get(cid)
                av = _to_float(erow.get(action_col)) if erow is not None else None
                if ocv is None or bv is None or av is None:
                    continue
                y.append(int(round(ocv)))
                bio.append(bv)
                act.append(av)
                grp.append(subj_by_cid.get(cid, cid))
            look_block["outcomes"][oc] = _interaction_look(y, act, bio, grp, seed=seed)
            if look_block["outcomes"][oc].get("interaction_or") is not None:
                any_ok = True
        look_block["outcomes"] = look_block["outcomes"]
        out["looks"][bio_col] = look_block

    out["available"] = any_ok
    out["implied_levers"] = IMPLIED_LEVERS
    return out


def run_screen(cfg: dict[str, Any]) -> dict[str, Any]:
    """SCREEN stage: univariate + incremental AUROC + predictive-enrichment look.

    Writes cache/aline_feasibility_results.json + docs/ALINE_FEASIBILITY.md, then
    cache/_aline_done.json LAST. Returns the full results dict.
    """
    cache_dir = _resolve_cache_dir(cfg)
    seed = _resolve_seed(cfg)

    rows, feat_names = _load_sample(cfg)
    outcomes_by_cid, baseline_by_cid, subj_by_cid = _load_outcomes_and_baseline(cfg)

    n_total = len(rows)
    n_avail = sum(1 for r in rows
                  if str(r.get("aline_available", "")).strip() in ("1", "1.0"))
    # Event counts on the available subset.
    event_counts: dict[str, int] = {}
    for oc in OUTCOMES:
        ev = 0
        for r in rows:
            cid = str(r.get("caseid", "")).strip()
            if str(r.get("aline_available", "")).strip() not in ("1", "1.0"):
                continue
            v = outcomes_by_cid.get(cid, {}).get(oc)
            if v is not None and round(v) == 1:
                ev += 1
        event_counts[oc] = ev

    print(f"[aline_feasibility] SCREEN: {n_total} rows, {n_avail} with ART; "
          f"events {event_counts}")

    # Screen each feature x outcome (skip the availability/count flags themselves).
    skip_feats = {"aline_available", "aline_n_beats", "cross_waveform_available",
                  "brs_n_sequences"}
    screen_feats = [f for f in feat_names if f not in skip_feats]

    grid: list[dict[str, Any]] = []
    for feat in screen_feats:
        for oc in OUTCOMES:
            grid.append(_screen_feature(rows, feat, oc, baseline_by_cid,
                                        outcomes_by_cid, subj_by_cid, seed))

    # BH-FDR across the incremental LR p-values (computed cells only).
    pvals = [
        (c["incremental"].get("lr_p")
         if (c.get("incremental") and not c.get("underpowered")) else None)
        for c in grid
    ]
    qvals = benjamini_hochberg(pvals, alpha=FDR_ALPHA)
    for c, q in zip(grid, qvals):
        c["incremental_q"] = round(q, 6) if q is not None else None

    # Dose-response / monotonicity screen across the BURDEN biomarkers (+ the
    # map_auc_below_65 positive control).
    dose_response = run_dose_response(cfg, rows, outcomes_by_cid,
                                      baseline_by_cid, subj_by_cid, seed)

    # Predictive-enrichment / treatment-interaction look.
    enrichment = run_predictive_enrichment(cfg, rows, outcomes_by_cid,
                                           subj_by_cid, seed)

    # Rank features for renal by incremental ΔAUROC (then |univariate AUROC-0.5|).
    renal_cells = [c for c in grid if c["outcome"] == "organ_renal"]
    def _rank_key(c):
        inc = c.get("incremental") or {}
        d = inc.get("delta_auroc")
        return (d if d is not None else -9.0, rank_auroc(c.get("auroc")))
    renal_ranked = sorted(renal_cells, key=_rank_key, reverse=True)

    results = {
        "n_sample_rows": n_total,
        "n_aline_available": n_avail,
        "event_counts": event_counts,
        "seed": seed,
        "min_events_feasible": MIN_EVENTS_FEASIBLE,
        "fdr_alpha": FDR_ALPHA,
        "power_caveat": ("Feasibility sample (~600 cases / ~20 renal events): "
                         "every cell is UNDERPOWERED. This answers YES/NO whether a "
                         "signal is worth the full ~180 GB ART extraction, NOT a "
                         "definitive estimate."),
        "grid": grid,
        "renal_ranked": [c["feature"] for c in renal_ranked],
        "dose_response": dose_response,
        "predictive_enrichment": enrichment,
    }

    os.makedirs(cache_dir, exist_ok=True)
    results_path = os.path.join(cache_dir, RESULTS_JSON)
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_json_default)
    print(f"[aline_feasibility] results -> {results_path}")

    _write_feasibility_md(results, cfg)

    done_path = os.path.join(cache_dir, DONE_MARKER)
    with open(done_path, "w", encoding="utf-8") as fh:
        json.dump({"n_sample_rows": n_total, "n_aline_available": n_avail,
                   "event_counts": event_counts}, fh, indent=2)
    print(f"[aline_feasibility] DONE marker -> {done_path}", flush=True)
    return results


# ===========================================================================
# Report
# ===========================================================================

def _write_feasibility_md(results: dict, cfg: dict) -> str:
    """Write docs/ALINE_FEASIBILITY.md (ranked renal features + the honest caveat
    + the predictive-enrichment look + a scale-or-not recommendation)."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(pkg_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, RESULTS_MD)

    grid = results.get("grid", [])
    ec = results.get("event_counts", {})
    cell = {(c["feature"], c["outcome"]): c for c in grid}

    # Ranked renal features by incremental ΔAUROC.
    renal_order = results.get("renal_ranked", [])

    lines = [
        "# A-line Waveform Feasibility Screen",
        "",
        "**Purpose.** Decide -- on a small deterministic sample -- whether the "
        "arterial-waveform biomarkers (ART morphology + ART x PPG coupling) carry "
        "an AKI signal worth the FULL ~180 GB raw-waveform extraction. This is a "
        "GO / NO-GO feasibility screen, not an estimate.",
        "",
        "## Honest power statement (read first)",
        "",
        f"- Sample rows: **{results.get('n_sample_rows')}**; with usable ART "
        f"waveform: **{results.get('n_aline_available')}**.",
        f"- Events on the ART subset: organ_renal = **{ec.get('organ_renal')}**, "
        f"composite = **{ec.get('composite')}**.",
        f"- {results.get('power_caveat')}",
        "- EVERY cell below is flagged **feasibility-only, underpowered**. "
        "Treatment-interaction cells are **hypothesis-generating, underpowered** "
        "and must not be read as effects.",
        "",
        "## (1) Does the waveform predict AKI? Incremental over hypotension baseline",
        "",
        f"Baseline = the hypotension burden `{HYPOTENSION_BASELINE_COL}`. For each "
        "feature we report the univariate AUROC and the incremental ΔAUROC of "
        "(baseline + feature) over baseline alone (in-sample logistic; LR p; "
        "patient-clustered bootstrap CI), BH-FDR across features.",
        "",
        "### Features ranked by incremental ΔAUROC for organ_renal",
        "",
        "| Rank | Feature | Univ. AUROC | ΔAUROC vs hypotension | 95% CI | LR p | q | n | events | band |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def _f(v, spec="{:+.3f}"):
        return spec.format(v) if isinstance(v, (int, float)) else "—"

    for i, feat in enumerate(renal_order, 1):
        c = cell.get((feat, "organ_renal"), {})
        inc = c.get("incremental") or {}
        ci = inc.get("delta_ci", [None, None])
        ci_s = (f"[{_f(ci[0])}, {_f(ci[1])}]"
                if all(isinstance(x, (int, float)) for x in ci) else "—")
        band = (c.get("incremental_band") or {}).get("band", "—")
        lines.append(
            f"| {i} | {feat} | {_f(c.get('auroc'), '{:.3f}')} | "
            f"{_f(inc.get('delta_auroc'))} | {ci_s} | "
            f"{_f(inc.get('lr_p'), '{:.3f}')} | {_f(c.get('incremental_q'), '{:.3f}')} | "
            f"{inc.get('n', c.get('n'))} | {inc.get('events', c.get('events'))} | {band} |")

    # Composite quick table.
    lines += ["", "### Composite outcome (same features)", "",
              "| Feature | Univ. AUROC | ΔAUROC | LR p | q | n | events |",
              "|---|---|---|---|---|---|---|"]
    for feat in renal_order:
        c = cell.get((feat, "composite"), {})
        inc = c.get("incremental") or {}
        lines.append(
            f"| {feat} | {_f(c.get('auroc'), '{:.3f}')} | "
            f"{_f(inc.get('delta_auroc'))} | {_f(inc.get('lr_p'), '{:.3f}')} | "
            f"{_f(c.get('incremental_q'), '{:.3f}')} | "
            f"{inc.get('n', c.get('n'))} | {inc.get('events', c.get('events'))} |")

    # Burden dose-response / monotonicity.
    lines += _burden_dose_response_lines(results)

    # (2) Predictive enrichment.
    enr = results.get("predictive_enrichment", {})
    lines += ["", "## (2) Does the waveform point to a LEVER? "
              "Predictive-enrichment look", ""]
    lines += [
        "Beyond risk prediction, the study's north star is ACTIONABILITY: a "
        "waveform feature is most valuable if it identifies WHO BENEFITS from a "
        "modifiable management action. Each feature implies a lever:",
        "",
    ]
    for f_, lev in (enr.get("implied_levers") or IMPLIED_LEVERS).items():
        lines.append(f"- `{f_}`: {lev}")
    lines += [""]

    if not enr.get("available"):
        lines += [f"_Treatment-interaction look not computed: "
                  f"{enr.get('note', 'unavailable')}._", ""]
    else:
        lines += ["**These interaction cells are hypothesis-generating and "
                  "underpowered (~20 renal events split across strata). They show "
                  "DIRECTION ONLY -- whether the waveform plausibly points to a "
                  "lever, justifying the full extraction.**", ""]
        for bio, blk in (enr.get("looks") or {}).items():
            lines += [f"### {bio} x action `{blk.get('action')}`",
                      f"_Lever: {blk.get('lever')}_", "",
                      "| Outcome | Stratum | n | events | risk(action) | "
                      "risk(no action) | RD | interaction OR | interaction p |",
                      "|---|---|---|---|---|---|---|---|---|"]
            for oc, res in (blk.get("outcomes") or {}).items():
                if res.get("interaction_or") is None and "low_stratum" not in res:
                    lines.append(f"| {oc} | — | {res.get('n')} | "
                                 f"{res.get('events')} | — | — | — | — | "
                                 f"_{res.get('note','underpowered')}_ |")
                    continue
                lo = res.get("low_stratum", {})
                hi = res.get("high_stratum", {})
                for label, st in (("bio-low", lo), ("bio-high", hi)):
                    lines.append(
                        f"| {oc} | {label} | {st.get('n')} | {st.get('events')} | "
                        f"{_f(st.get('risk_action'), '{:.3f}')} | "
                        f"{_f(st.get('risk_no_action'), '{:.3f}')} | "
                        f"{_f(st.get('rd'))} | "
                        f"{_f(res.get('interaction_or'), '{:.2f}')} | "
                        f"{_f(res.get('interaction_p_bootstrap'), '{:.3f}')} |")
            lines += [""]

    # Recommendation.
    lines += ["## Recommendation: scale to the full ART cohort, or not?", ""]
    lines += _recommendation_lines(results)

    lines += ["", "---",
              "*Generated by vitaldb_aki/analysis/aline_feasibility.py "
              "(feasibility sample; underpowered by design).*", ""]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[aline_feasibility] ALINE_FEASIBILITY.md -> {md_path}")
    return md_path


def _burden_dose_response_lines(results: dict) -> list[str]:
    """Markdown for the "Burden dose-response" section: per-quartile AKI rate,
    monotonic?, trend p, incremental ΔAUROC -- led by the headline burden vs the
    map_auc_below_65 positive control, with an honest power caveat."""
    dr = results.get("dose_response") or {}
    grid = dr.get("grid") or []
    if not grid:
        return ["", "## (1b) Burden dose-response", "",
                "_Dose-response not computed (no burden columns / too few events)._",
                ""]
    cell = {(c["burden"], c["outcome"]): c for c in grid}
    headline = dr.get("headline_burden", "art_perfusion_failure_burden_min")
    pos = dr.get("positive_control", HYPOTENSION_BASELINE_COL)

    def _f(v, spec="{:.3f}"):
        return spec.format(v) if isinstance(v, (int, float)) else "—"

    lines = ["", "## (1b) Burden dose-response (monotonic dose-response with AKI risk)",
             "",
             "Each cumulative-dose burden (minutes / AUC in an abnormal waveform "
             "state, time-weighted with a 10 s gap cap) is quartiled (tertiled when "
             "sparse) across cases WITH the signal; we report the per-quantile "
             "**organ_renal** rate, whether rates are non-decreasing (monotonic), "
             "the Cochran-Armitage linear-trend p (BH-FDR across burdens), and the "
             "incremental ΔAUROC of the continuous burden OVER the hypotension "
             f"baseline `{HYPOTENSION_BASELINE_COL}`.",
             "",
             f"**Lead comparison:** the headline `{headline}` (occult perfusion "
             f"failure at adequate pressure) vs the `{pos}` POSITIVE CONTROL (the "
             "accepted hypotension-dose, known to be monotonically dose-responsive "
             "for AKI). If the positive control looks monotonic here and the "
             "headline tracks it, the waveform burden is plausibly real.",
             "",
             f"> {dr.get('power_caveat', '')}",
             "",
             "### Per-quartile organ_renal rate + monotonic trend",
             "",
             "| Burden | role | quantile rates (low->high) | monotonic? | CA z | "
             "CA p | q (FDR) | logit-trend p | ΔAUROC vs hypotension | n | events |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]

    # Order: positive control first, then headline, then the rest.
    order = [pos, headline] + [
        b for b in dr.get("burdens_screened", [])
        if b not in (pos, headline)]
    seen = set()
    for b in order:
        if b in seen:
            continue
        seen.add(b)
        c = cell.get((b, "organ_renal"))
        if c is None:
            continue
        role = ("positive control" if c.get("is_positive_control")
                else ("HEADLINE" if b == headline else "burden"))
        drr = c.get("dose_response") or {}
        qs = drr.get("quantiles") or []
        rate_str = " / ".join(
            (f"{q['rate']:.3f}" if q.get("rate") is not None else "—") for q in qs
        ) if qs else "—"
        mono = drr.get("is_monotonic")
        mono_s = "yes" if mono is True else ("no" if mono is False else "—")
        inc = c.get("incremental") or {}
        lines.append(
            f"| `{b}` | {role} | {rate_str} | {mono_s} | "
            f"{_f(drr.get('cochran_armitage_z'))} | "
            f"{_f(drr.get('cochran_armitage_p'))} | "
            f"{_f(c.get('ca_trend_q'))} | {_f(c.get('logistic_trend_p'))} | "
            f"{_f(inc.get('delta_auroc'), '{:+.3f}')} | "
            f"{c.get('n')} | {c.get('events')} |")

    # Headline spotlight.
    hc = cell.get((headline, "organ_renal"))
    if hc is not None:
        hdr = hc.get("dose_response") or {}
        lines += ["", f"### Headline spotlight: `{headline}`", ""]
        qs = hdr.get("quantiles") or []
        if qs:
            lines += ["| quantile | burden range (min) | n | events | organ_renal rate |",
                      "|---|---|---|---|---|"]
            for q in qs:
                lines.append(
                    f"| Q{q['q'] + 1} | [{_f(q.get('lo'))}, {_f(q.get('hi'))}] | "
                    f"{q.get('n')} | {q.get('events')} | "
                    f"{_f(q.get('rate'))} |")
        mono = hdr.get("is_monotonic")
        lines += ["",
                  f"- Monotonic (rates non-decreasing across quartiles): "
                  f"**{'yes' if mono is True else ('no' if mono is False else 'undetermined')}**.",
                  f"- Cochran-Armitage trend p = {_f(hdr.get('cochran_armitage_p'))}; "
                  f"Spearman rho = {_f(hdr.get('spearman_rho'))}; "
                  f"logistic-trend p = {_f(hc.get('logistic_trend_p'))}.",
                  f"- Incremental ΔAUROC over `{HYPOTENSION_BASELINE_COL}` = "
                  f"{_f((hc.get('incremental') or {}).get('delta_auroc'), '{:+.3f}')}.",
                  ""]

    lines += [
        "**Honest caveat.** With ~20 renal events split across 3-4 quantiles, "
        "each bin holds single-digit events: a non-monotonic blip or a "
        "spuriously monotonic ramp is entirely plausible by chance. A monotonic "
        "look here (especially if the `" + pos + "` positive control is ALSO "
        "monotonic on the same sample) is a GO signal for the full extraction "
        "where the dose-response can be properly powered; it is NOT a "
        "dose-response estimate.",
        ""]
    return lines


def _recommendation_lines(results: dict) -> list[str]:
    """Heuristic GO / NO-GO summary text (clearly framed as feasibility-grade)."""
    grid = results.get("grid", [])
    renal = [c for c in grid if c["outcome"] == "organ_renal"
             and c.get("incremental")]
    best_delta = None
    best_feat = None
    for c in renal:
        d = (c.get("incremental") or {}).get("delta_auroc")
        if d is not None and (best_delta is None or d > best_delta):
            best_delta, best_feat = d, c["feature"]
    enr = results.get("predictive_enrichment", {})
    any_interaction_signal = False
    for blk in (enr.get("looks") or {}).values():
        for res in (blk.get("outcomes") or {}).values():
            p = res.get("interaction_p_bootstrap")
            if p is not None and p < 0.20:  # loose, direction-only screen
                any_interaction_signal = True

    out = []
    if best_delta is None:
        out.append("- **Inconclusive:** too few events to compute a stable "
                   "incremental signal. Recommend a LARGER feasibility sample "
                   "before deciding on the full extraction.")
        return out

    out.append(f"- Best incremental renal ΔAUROC over the hypotension baseline: "
               f"**{best_delta:+.3f}** ({best_feat}).")
    pred = "**points to a lever**" if any_interaction_signal else \
           "did not show a clear directional lever signal"
    out.append(f"- The predictive-enrichment look {pred} at this (underpowered) "
               "sample size.")
    if best_delta >= 0.02 or any_interaction_signal:
        out.append("- **Tentative GO (feasibility-grade):** the waveform shows "
                   "an incremental and/or lever-pointing signal that PLAUSIBLY "
                   "justifies scaling to the full ART cohort, where adequate "
                   "events (~hundreds of renal events) can properly power both "
                   "the incremental-value and the treatment-interaction tests. "
                   "Treat this as hypothesis-generating only.")
    else:
        out.append("- **NO-GO / hold (feasibility-grade):** no incremental or "
                   "lever signal emerged above the hypotension baseline. Given "
                   "the ~180 GB cost, do NOT scale yet; revisit only with a "
                   "stronger mechanistic prior or a larger pilot.")
    out.append("- Caveat: with only ~20 renal events, both a false-negative "
               "(missed real signal) and a false-positive are very possible. "
               "This screen is a GO/NO-GO trigger, not evidence.")
    return out


def _json_default(obj):
    try:
        import numpy as np
    except ImportError:
        raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON-serializable")


# ===========================================================================
# Orchestrator
# ===========================================================================

def run_aline_feasibility(cfg: dict[str, Any]) -> dict[str, Any]:
    """Run EXTRACT then SCREEN.

    EXTRACT is resumable and disk-bounded (purges raw SNUADC waveforms per case);
    it writes cache/_aline_extract_done.json when the full seeded sample has rows.
    SCREEN runs the AUROC / incremental / predictive-enrichment analyses and writes
    cache/aline_feasibility_results.json, docs/ALINE_FEASIBILITY.md, and finally
    cache/_aline_done.json.

    Returns {"extract": <extract summary>, "screen": <screen results>}.
    """
    extract_summary = run_extract(cfg)
    screen_results = run_screen(cfg)
    return {"extract": extract_summary, "screen": screen_results}


def main() -> None:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    from common.config import load_yaml
    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    cfg = load_yaml(cfg_path)
    run_aline_feasibility(cfg)


if __name__ == "__main__":
    main()
