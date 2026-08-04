"""multivariate_complexity.py -- SYSTEM-WIDE physiologic complexity (§7C/§7F novel).

The bp_variability module measures complexity ONE signal at a time (univariate
SampEn of MAP, of HR). This module asks a different, deeper question:

  **How complex is the WHOLE physiologic system, taken together?**

A healthy organism is a *complex, loosely-coupled* dynamical system: MAP, HR,
EtCO2, SpO2 (and depth-of-anesthesia, BIS) each carry their own regulatory
"texture", and they do NOT all march in lock-step. As a system approaches
failure, that joint richness collapses -- every channel starts moving together,
rigidly, in a low-dimensional way. This loss of *joint* complexity is a
universal pre-failure signature that no single-signal entropy can see: each
channel can look individually plausible while the ENSEMBLE has gone rigid.

We operationalise that with two complementary axes computed over the aligned
multi-signal ensemble:

  1. JOINT COMPLEXITY -- multivariate Sample Entropy (Ahmed & Mandic 2011):
     composite delay vectors that span ALL channels at once. LOWER == the whole
     system is more regular / lower-dimensional / rigid == sicker physiology.
     (mvcplx_joint_sampen)

  2. NETWORK INTEGRATION -- the pairwise |Pearson r| structure across the
     ensemble: mean (overall co-movement / rigidity), SD (heterogeneity of
     coupling across the network), and max (the single dominant coupling).
     (mvcplx_mean_pairwise_corr / mvcplx_corr_dispersion / mvcplx_max_pairwise_corr)

ENSEMBLE & ALIGNMENT
--------------------
Four CORE signals (MAP, HR, EtCO2, SpO2) plus an OPTIONAL fifth (BIS). Each is
fetched via first_available over a candidate list and range-gated. The signals
are then aligned onto a common dt=5 s grid: at each grid point we keep a value
for a signal only if it has a *fresh* sample within `max_stale` seconds (last-
value-hold with a staleness cap). A grid point is JOINTLY VALID only when ALL
present signals are fresh there; the multivariate statistics use only those
jointly-valid points. This is the key cost of "system-wide": joint availability
shrinks N (it needs >=3 signals simultaneously), but the core four are widely
recorded so most cases still qualify. We require >=3 of the four core signals
present with >=50 jointly-valid grid points before emitting any statistic.

LEAKAGE (§11)
-------------
All features are timing="intraop". The window is [t_start, opend] and no sample
at t > opend is ever used (_intraop_window + _clip_to_window copied verbatim from
pfds). audit_specs() enforces no-postop at import.

MISSINGNESS
-----------
If <3 core signals are jointly usable (or <50 joint grid points), mvcplx_available
== 0 (an int flag, NOT None) and EVERY other feature is None. mvcplx_n_signals is
context only.

NUMERICS
--------
Alignment, z-scoring, and Pearson are pure Python (stdlib). Multivariate SampEn
is O(n^2) in the joint grid length; its template match is NUMPY-vectorized
(lazily imported inside the function, so the stdlib-only paths are unaffected)
and is bit-equivalent to the prior pure-Python counting. The joint series is
uniform-capped to MAX_MVSAMPEN_LEN points by stride BEFORE the template match,
bounding both time and the O(n^2) match-matrix memory. Degenerate (constant /
fully-rigid) and too-short ensembles are guarded before the match so they return
fast (0.0 or None) without hanging the extraction.

TRACK PRIORITIES (binding)
  MAP:   Solar8000/ART_MBP -> Solar8000/NIBP_MBP -> EV1000/ART_MBP   gate 20-200
  HR:    Solar8000/HR -> Solar8000/PLETH_HR                          gate 20-220
  EtCO2: Solar8000/ETCO2 -> Primus/ETCO2                             gate 5-70
  SpO2:  Solar8000/PLETH_SPO2                                        gate 50-100
  BIS:   BIS/BIS (optional 5th)                                      gate 0-100

Protocol reference: §7C (complexity companion to bp_variability), §7F (ensemble
coupling).
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Physiologic range gates (binding; artifact rejection; match sibling modules)
# ---------------------------------------------------------------------------
MAP_MIN: float = 20.0
MAP_MAX: float = 200.0
HR_MIN: float = 20.0
HR_MAX: float = 220.0
ETCO2_MIN: float = 5.0
ETCO2_MAX: float = 70.0
SPO2_MIN: float = 50.0
SPO2_MAX: float = 100.0
BIS_MIN: float = 0.0
BIS_MAX: float = 100.0

# ---------------------------------------------------------------------------
# Alignment + statistic parameters (pre-registered)
# ---------------------------------------------------------------------------
ALIGN_DT_S: float = 5.0            # common grid spacing
ALIGN_MAX_STALE_S: float = 10.0    # a signal is "fresh" within this of a sample
MIN_CORE_SIGNALS: int = 3          # >=3 of the 4 core signals required
MIN_JOINT_POINTS: int = 50         # >=50 jointly-valid grid points required

# Multivariate Sample Entropy parameters (Ahmed & Mandic 2011).
MVSAMPEN_M: int = 2                # embedding dimension per channel
MVSAMPEN_R_FRAC: float = 0.2       # tolerance r in z-scored units
# Cap on joint grid length before the multivariate template match. The match is
# now numpy-vectorized but is O(n^2) in MEMORY (an n x n match matrix), so the
# cap bounds peak memory as well as time. Lowered 2000 -> 1500: the joint grid
# already spans every channel, so 1500 points retain the full ensemble shape.
MAX_MVSAMPEN_LEN: int = 1500

# ---------------------------------------------------------------------------
# Track candidate lists (binding; first_available picks the first present).
# ---------------------------------------------------------------------------
MAP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "EV1000/ART_MBP",
]
HR_TRACK_CANDIDATES: list[str] = [
    "Solar8000/HR",
    "Solar8000/PLETH_HR",
]
ETCO2_TRACK_CANDIDATES: list[str] = [
    "Solar8000/ETCO2",
    "Primus/ETCO2",
]
SPO2_TRACK_CANDIDATES: list[str] = [
    "Solar8000/PLETH_SPO2",
]
BIS_TRACK_CANDIDATES: list[str] = [
    "BIS/BIS",
]

# (signal-name, candidate-list, (vmin, vmax), is_core)
_ENSEMBLE: list[tuple[str, list[str], tuple[float, float], bool]] = [
    ("MAP", MAP_TRACK_CANDIDATES, (MAP_MIN, MAP_MAX), True),
    ("HR", HR_TRACK_CANDIDATES, (HR_MIN, HR_MAX), True),
    ("EtCO2", ETCO2_TRACK_CANDIDATES, (ETCO2_MIN, ETCO2_MAX), True),
    ("SpO2", SPO2_TRACK_CANDIDATES, (SPO2_MIN, SPO2_MAX), True),
    ("BIS", BIS_TRACK_CANDIDATES, (BIS_MIN, BIS_MAX), False),  # optional 5th
]
CORE_SIGNALS: tuple[str, ...] = tuple(name for name, _, _, core in _ENSEMBLE if core)

# ---------------------------------------------------------------------------
# Feature specs (§9 nested design; all "intraop" -- leakage firewall §11).
# First spec MUST be mvcplx_available.
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "mvcplx_available", "comprehensive", "intraop",
        f"1 if >={MIN_CORE_SIGNALS} of the core ensemble signals "
        f"(MAP/HR/EtCO2/SpO2) are jointly usable with >={MIN_JOINT_POINTS} "
        "aligned grid points, else 0",
    ),
    FeatureSpec(
        "mvcplx_n_signals", "comprehensive", "intraop",
        "Number of jointly-available ensemble signals (core+optional BIS) used "
        "for the multivariate statistics (context; integer). None if unavailable",
    ),
    FeatureSpec(
        "mvcplx_joint_sampen", "comprehensive", "intraop",
        "MULTIVARIATE Sample Entropy across the available signals "
        "(Ahmed-Mandic; composite delay vectors across channels, m=2, "
        "r=0.2 in z-scored units, Chebyshev distance; joint grid uniform-capped "
        f"to <={MAX_MVSAMPEN_LEN} pts). LOWER = system-wide rigidity / loss "
        "of joint complexity. None if undefined",
    ),
    FeatureSpec(
        "mvcplx_mean_pairwise_corr", "comprehensive", "intraop",
        "Mean of |Pearson r| over all signal pairs on the joint grid; overall "
        "network integration -- high = rigid co-movement of the ensemble. None "
        "if unavailable",
    ),
    FeatureSpec(
        "mvcplx_corr_dispersion", "comprehensive", "intraop",
        "Population SD of the pairwise |Pearson r| values; heterogeneity of "
        "coupling across the network (uniform vs patchy coupling). None if "
        "unavailable",
    ),
    FeatureSpec(
        "mvcplx_max_pairwise_corr", "comprehensive", "intraop",
        "Single strongest |pairwise Pearson r| across the ensemble; the "
        "dominant coupling. None if unavailable",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Window helpers (copied verbatim from pfds._intraop_window -- binding contract)
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None."""
    def _f(key: str) -> float | None:
        v = case.get(key)
        if v is None or str(v).strip() in ("", "nan", "NA", "None"):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    opend = _f("opend")
    if opend is None:
        return None, None
    anestart = _f("anestart")
    if anestart is not None:
        return anestart, opend
    opstart = _f("opstart")
    if opstart is not None:
        return opstart, opend
    return None, opend


def _clip_to_window(
    samples: list[tuple[float, float]],
    t_start: float | None,
    t_end: float | None,
) -> list[tuple[float, float]]:
    """Return only samples in [t_start, t_end].  t_end is the leakage cutoff."""
    out = []
    for t, v in samples:
        if t_start is not None and t < t_start:
            continue
        if t_end is not None and t > t_end:
            continue
        out.append((t, v))
    return out


def _filter_physiologic(
    samples: list[tuple[float, float]],
    vmin: float,
    vmax: float,
) -> list[tuple[float, float]]:
    """Drop samples outside [vmin, vmax] (artifact rejection)."""
    return [(t, v) for t, v in samples if vmin <= v <= vmax]


# ===========================================================================
# Pure multi-signal alignment (no I/O; unit-testable on synthetic series).
# ===========================================================================

def _align_grid(
    signals_dict: dict[str, list[tuple[float, float]]],
    t_start: float,
    t_end: float,
    dt: float = ALIGN_DT_S,
    max_stale: float = ALIGN_MAX_STALE_S,
) -> tuple[list[str], list[list[float]]]:
    """Align multiple (t, v) signals onto a common dt grid; keep jointly-valid points.

    For each grid time g in [t_start, t_end] stepping by `dt`, every signal is
    sampled by LAST-VALUE-HOLD: the most recent sample at or before g, accepted
    only if it is "fresh" (g - sample_t <= max_stale). A grid point is retained
    ONLY when EVERY signal in `signals_dict` has a fresh value there ("jointly
    valid"). This guarantees the returned channels are perfectly aligned and gap-
    free across the whole ensemble.

    Parameters
    ----------
    signals_dict : {name: [(t, v), ...]}
        Each list is the in-window, range-gated samples for one signal. Empty
        lists / signals are treated as never-fresh (they would void every grid
        point), so the caller must only pass signals it wants to require.
    t_start, t_end : float
        Grid bounds (seconds). t_end is the leakage cutoff; no grid point exceeds
        it.
    dt : float
        Grid spacing (seconds).
    max_stale : float
        Maximum age (seconds) of a held sample for it to count as fresh.

    Returns
    -------
    (names, channels) :
        `names` is the signal order (sorted, deterministic). `channels` is a list
        of parallel value arrays, channels[k][i] being signal names[k] at the
        i-th jointly-valid grid point. All channels have equal length. Returns
        ([], []) if no signals, an invalid window, or no jointly-valid points.
    """
    names = sorted(signals_dict.keys())
    if not names or t_end <= t_start or dt <= 0:
        return [], []

    # Pre-sort each signal once and keep an advancing cursor (the grid marches
    # forward in time, so a single forward pointer per signal suffices).
    sorted_sigs: dict[str, list[tuple[float, float]]] = {
        nm: sorted(signals_dict[nm], key=lambda x: x[0]) for nm in names
    }
    cursors: dict[str, int] = {nm: 0 for nm in names}

    channels: list[list[float]] = [[] for _ in names]

    # Iterate the grid by integer steps to avoid float drift accumulation.
    n_steps = int(math.floor((t_end - t_start) / dt)) + 1
    for step in range(n_steps):
        g = t_start + step * dt
        if g > t_end:
            break

        held: list[float | None] = []
        all_fresh = True
        for nm in names:
            seq = sorted_sigs[nm]
            cur = cursors[nm]
            # Advance cursor to the last sample with t <= g.
            while cur + 1 < len(seq) and seq[cur + 1][0] <= g:
                cur += 1
            cursors[nm] = cur
            if not seq:
                held.append(None)
                all_fresh = False
                continue
            st, sv = seq[cur]
            if st > g or (g - st) > max_stale:
                # No sample at-or-before g, or the held sample is stale.
                held.append(None)
                all_fresh = False
            else:
                held.append(sv)

        if all_fresh:
            for k in range(len(names)):
                channels[k].append(held[k])  # type: ignore[arg-type]

    if not channels or not channels[0]:
        return names, [[] for _ in names]
    return names, channels


# ===========================================================================
# Pure statistic helpers (no I/O; unit-testable on synthetic series).
# ===========================================================================

def _mean(series: list[float]) -> float | None:
    """Arithmetic mean; None if empty."""
    if not series:
        return None
    return sum(series) / len(series)


def _sd(series: list[float]) -> float | None:
    """Population standard deviation.  None if < 2 samples."""
    n = len(series)
    if n < 2:
        return None
    m = sum(series) / n
    var = sum((x - m) ** 2 for x in series) / n
    return math.sqrt(var)


def _zscore(series: list[float]) -> list[float] | None:
    """Z-score a series to zero mean / unit SD.

    Returns None if < 2 samples or the series is CONSTANT (SD == 0): a constant
    channel carries no information and cannot be normalised, so it is excluded
    upstream rather than divided by zero.
    """
    n = len(series)
    if n < 2:
        return None
    m = sum(series) / n
    var = sum((x - m) ** 2 for x in series) / n
    sd = math.sqrt(var)
    if sd <= 0.0:
        return None
    return [(x - m) / sd for x in series]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation of two equal-length series.

    Returns None if < 2 paired points, length mismatch, or either series is
    constant (zero variance -> correlation undefined).
    """
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    return sxy / math.sqrt(sxx * syy)


def _pairwise_corr_stats(
    channels: list[list[float]],
) -> tuple[float | None, float | None, float | None]:
    """Mean / SD / max of |Pearson r| over all distinct channel pairs.

    `channels` is a list of equal-length value arrays (one per signal). The
    statistics are taken over the |r| of every unordered pair (i<j). Pairs whose
    correlation is undefined (constant channel) are skipped.

    Returns (mean_abs_r, sd_abs_r, max_abs_r). All three are None if there are
    fewer than 2 channels or no pair yields a defined correlation. SD is the
    POPULATION SD of the |r| values (0.0 when only one pair exists).
    """
    k = len(channels)
    if k < 2:
        return None, None, None
    abs_rs: list[float] = []
    for i in range(k):
        for j in range(i + 1, k):
            r = _pearson(channels[i], channels[j])
            if r is not None:
                abs_rs.append(abs(r))
    if not abs_rs:
        return None, None, None
    mean_r = sum(abs_rs) / len(abs_rs)
    if len(abs_rs) >= 2:
        var = sum((x - mean_r) ** 2 for x in abs_rs) / len(abs_rs)
        sd_r = math.sqrt(var)
    else:
        sd_r = 0.0
    max_r = max(abs_rs)
    return mean_r, sd_r, max_r


def _uniform_cap_channels(
    channels: list[list[float]],
    maxlen: int = MAX_MVSAMPEN_LEN,
) -> list[list[float]]:
    """Uniformly decimate ALL channels in lockstep to <= maxlen points by stride.

    Multivariate SampEn is O(n^2) in the joint length; long records are
    intractable in pure Python. We stride every channel by the SAME factor so
    the channels stay aligned (the joint structure is preserved). Returns the
    channels unchanged when already short enough.
    """
    if not channels or not channels[0]:
        return channels
    n = len(channels[0])
    if maxlen <= 0 or n <= maxlen:
        return [list(c) for c in channels]
    stride = (n + maxlen - 1) // maxlen   # ceil(n / maxlen)
    return [c[::stride] for c in channels]


def _multivariate_sampen(
    channels: list[list[float]],
    m: int = MVSAMPEN_M,
    r: float = MVSAMPEN_R_FRAC,
) -> float | None:
    """Multivariate Sample Entropy (Ahmed & Mandic 2011), NUMPY-vectorized.

    The channels must already be Z-SCORED (zero mean / unit SD) so that the
    single tolerance `r` is meaningful across every channel and the Chebyshev
    distance is comparable. With p channels each embedded at dimension m, the
    composite delay vector at index i spans all channels:

        X_m(i) = [ ch0[i], ch0[i+1], ..., ch0[i+m-1],
                   ch1[i], ..., ch1[i+m-1],
                   ...,
                   ch(p-1)[i], ..., ch(p-1)[i+m-1] ]    (length p*m)

    MVSampEn = -ln( A / B ) where, over all template pairs (i != j) within
    Chebyshev (max-norm) distance r:
        B = fraction matching at composite dimension p*m
        A = fraction matching at composite dimension p*(m+1)
    Following the multivariate construction, the (m+1) embedding extends EVERY
    channel by one sample (the composite dimension grows from p*m to p*(m+1)).

    Lower MVSampEn == the ensemble is more regular / lower-dimensional == rigid.

    Parameters
    ----------
    channels : list[list[float]]
        p equal-length z-scored value arrays. (Constant channels must be removed
        by the caller -- z-scoring a constant is undefined.)
    m : int
        Per-channel embedding dimension (default 2).
    r : float
        Tolerance in z-scored units (default 0.2). Chebyshev radius.

    Returns
    -------
    float | None
        MVSampEn value, or None when undefined:
          * fewer than 1 channel, or unequal channel lengths
          * series too short ( n < m + 2 )
          * no length-(m) template pairs match (B == 0), or
          * matches at m but none extend to m+1 (A == 0; unbounded -> None).

    Edge cases / documented behaviour:
      * A set of IDENTICAL (or perfectly coupled) channels collapses to one
        effective dimension: nearly every extended template still matches, so
        A/B ~ 1 and MVSampEn ~ 0 (minimum -- maximal rigidity). This is the
        intended "rigid ensemble => low joint entropy" behaviour.
      * Independent noisy channels rarely match at the longer template, so
        A << B and MVSampEn is large.

    Implementation / guards
    -----------------------
    The triple Python loop (template pairs x channels x lags) is replaced by
    numpy: per channel we stack the (last x mm) sliding-window templates, take the
    pairwise |t_i - t_j| via broadcasting, and the composite Chebyshev distance is
    the max ACROSS channels and lags. Pairs (i<j) within r are counted on the
    strict upper triangle. Integer pair counts are identical to the old loop, so
    MVSampEn matches to floating-point round-off (~1e-12). numpy is lazily
    imported (stdlib core unaffected).

    Guards (run BEFORE any O(n^2) work):
      * SHORT / unequal: <1 channel, unequal channel lengths, or n < m + 2 -> None.
      * NON-FINITE: any non-finite sample in any channel -> None (the caller
        z-scores upstream, so this is defensive).
      * DEGENERATE / CONSTANT: a channel set whose joint range is ~0 (every
        composite template within r) would make the naive counter walk all
        ~n^2/2 pairs while every one matches (A == B). We short-circuit that
        all-match case to 0.0 -- maximal rigidity / minimal joint entropy --
        without materialising a second match matrix.
    """
    import numpy as np

    p = len(channels)
    if p < 1:
        return None
    n = len(channels[0])
    for c in channels:
        if len(c) != n:
            return None
    if n < m + 2:
        return None

    mat = np.asarray(channels, dtype=float)  # shape (p, n)
    if mat.ndim != 2 or not np.isfinite(mat).all():
        return None

    def _match_fraction(mm: int) -> tuple[int, int]:
        """(matched_pairs, total_pairs) for composite length-mm templates (i<j).

        The composite Chebyshev match is built as a single (last x last) boolean
        matrix accumulated one (channel, lag) plane at a time: a pair (i, j)
        matches iff |x_c[i+k] - x_c[j+k]| <= r for EVERY channel c and lag
        k in [0, mm). For each (c, k) we form that one (last x last) tolerance
        mask and AND it into the running `within`. Peak memory is O(last^2)
        (a handful of boolean/float matrices), NOT O(p * last^2 * mm), and we
        never pay per-row Python overhead. Bit-identical pair counts to the
        original triple loop.
        """
        last = n - mm + 1   # number of templates of per-channel length mm
        if last < 2:
            return 0, 0
        within = np.ones((last, last), dtype=bool)
        for c in range(p):
            xc = mat[c]
            for k in range(mm):
                col = xc[k:k + last]                       # (last,)
                d = np.abs(col[:, None] - col[None, :])    # (last, last)
                within &= (d <= r)
                if not within.any():
                    return 0, last * (last - 1) // 2
        matched = int(np.triu(within, k=1).sum())
        total = last * (last - 1) // 2
        return matched, total

    b_cnt, b_tot = _match_fraction(m)
    if b_tot == 0 or b_cnt == 0:
        # No matches at the base dimension -> statistic undefined.
        return None
    # DEGENERATE all-match fast path: every base-length pair already matches
    # (constant / fully-rigid ensemble). Then every extended pair matches too, so
    # A == B and MVSampEn == 0 exactly -- skip the second (a) match matrix.
    if b_cnt == b_tot:
        return 0.0

    a_cnt, a_tot = _match_fraction(m + 1)
    if a_tot == 0:
        return None
    if a_cnt == 0:
        # Matches at m but none extend to m+1: MVSampEn -> +inf; report None.
        return None
    b = b_cnt / b_tot
    a = a_cnt / a_tot
    return -math.log(a / b)


def _round(v: float | None, ndigits: int = 6) -> float | None:
    """Round a value, passing None through unchanged."""
    return None if v is None else round(v, ndigits)


# ===========================================================================
# Case-level computation (pure given aligned channels).
# ===========================================================================

def compute_multivariate_complexity(
    signals_dict: dict[str, list[tuple[float, float]]],
    t_start: float,
    t_end: float,
) -> dict[str, Any]:
    """Compute all multivariate-complexity features for one case.

    `signals_dict` holds the in-window, range-gated samples for each PRESENT
    ensemble signal (a signal absent for this case is simply not a key). The
    function aligns them, applies the availability gate (>=MIN_CORE_SIGNALS core
    signals AND >=MIN_JOINT_POINTS joint grid points), and emits the SPECS row.

    Returns a dict with every SPECS key; mvcplx_available is 0 with all others
    None when the gate fails.
    """
    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["mvcplx_available"] = 0

    if not signals_dict:
        return dict(none_row)

    names, channels = _align_grid(signals_dict, t_start, t_end)
    if not names or not channels or not channels[0]:
        return dict(none_row)

    n_joint = len(channels[0])
    n_core_present = sum(1 for nm in names if nm in CORE_SIGNALS)

    if n_core_present < MIN_CORE_SIGNALS or n_joint < MIN_JOINT_POINTS:
        return dict(none_row)

    row: dict[str, Any] = dict(none_row)
    row["mvcplx_available"] = 1
    row["mvcplx_n_signals"] = len(names)

    # ---- Network integration: pairwise |corr| structure on the joint grid ----
    mean_r, sd_r, max_r = _pairwise_corr_stats(channels)
    row["mvcplx_mean_pairwise_corr"] = _round(mean_r)
    row["mvcplx_corr_dispersion"] = _round(sd_r)
    row["mvcplx_max_pairwise_corr"] = _round(max_r)

    # ---- Joint complexity: multivariate SampEn on z-scored, capped channels ---
    capped = _uniform_cap_channels(channels, MAX_MVSAMPEN_LEN)
    z_channels: list[list[float]] = []
    for c in capped:
        z = _zscore(c)
        if z is not None:   # drop constant channels (undefined z-score)
            z_channels.append(z)
    if z_channels:
        row["mvcplx_joint_sampen"] = _round(_multivariate_sampen(z_channels))

    return row


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract)
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for multivariate-complexity features.

    Downloads each ensemble signal per case (cached) via first_available, clips
    to the intraop window [t_start, opend], and range-gates it. When fewer than
    MIN_CORE_SIGNALS core signals are jointly usable (or <MIN_JOINT_POINTS aligned
    grid points), mvcplx_available == 0 and every other feature is None.
    """
    from vitaldb_aki.data.tracks import first_available  # noqa: F401
    from vitaldb_aki.data.client import to_float  # noqa: F401

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["mvcplx_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)
        # No usable window cutoff => cannot align deterministically.
        if t_end is None:
            out[cid_str] = dict(none_row)
            continue
        # _align_grid needs a finite lower bound; fall back to 0.0 if anestart /
        # opstart were absent (t_start is None means "from recording start").
        grid_start = 0.0 if t_start is None else t_start

        signals_dict: dict[str, list[tuple[float, float]]] = {}
        for sig_name, candidates, (vmin, vmax), _is_core in _ENSEMBLE:
            _tname, raw = first_available(cfg, cid_str, candidates)
            if not raw:
                continue
            samples = _clip_to_window(raw, grid_start, t_end)
            samples = _filter_physiologic(samples, vmin, vmax)
            if samples:
                signals_dict[sig_name] = samples

        out[cid_str] = compute_multivariate_complexity(signals_dict, grid_start, t_end)

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.multivariate_complexity
# ===========================================================================
if __name__ == "__main__":
    import csv
    import os
    import sys

    sys.path.insert(
        0,
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    from common.config import load_yaml
    from vitaldb_aki.data.client import fetch_cases

    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
    )
    cfg = load_yaml(cfg_path)

    cohort_path = os.path.join(cfg["data"]["cache_dir"], "cohort.csv")
    cohort_ids: list[str] = []
    with open(cohort_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            cohort_ids.append(str(r["caseid"]))
            if len(cohort_ids) >= 12:
                break

    print(f"Multivariate-complexity validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case multivariate-complexity summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
