"""physio_network.py -- the physiologic COUPLING NETWORK across the vital ensemble.

Mechanistic thesis
------------------
Single-channel coupling (cross_waveform.py) captures one edge at a time. The
novelty here is to treat the WHOLE vital ensemble (MAP, HR, EtCO2, SpO2, Temp)
as a TIME-EVOLVING GRAPH and read its topology.

Organ-system integration is a network: the autonomic, respiratory, and
cardiovascular controllers keep their outputs mutually coupled. Multi-organ
decompensation -- the road to AKI and other postoperative organ failure -- does
not show up as any single edge breaking. It shows up as the whole NETWORK
DISINTEGRATING:

  * edges weakening (pairwise |corr| falling toward 0),
  * the network fragmenting (more weak-edge / disconnected slots over time),
  * directed information flow collapsing (transfer entropy dropping; the
    driver-follower hierarchy flattening).

These are systems-level signatures that no single pairwise coupling captures.

NETWORK CONSTRUCTION
--------------------
1. Align every available signal onto a common dt=5 s grid over the intraop
   window [t_start, opend] using last-value-hold with a staleness cap
   (max_stale=10 s). Only JOINTLY-valid grid points are kept (every retained
   signal must have a fresh sample at that time).
2. Require >=3 signals present and >=60 joint grid points; else the network is
   not computable (physnet_available=0).
3. Carve the joint series into consecutive, non-overlapping WINDOWS (120 s).
   In each window, edge weight(i, j) = |Pearson corr| between signals i, j.
   An edge is "on" when its weight >= EDGE_ON (0.5).

FEATURES (topology = comprehensive; transfer entropy = pk / heavier)
--------------------------------------------------------------------
  physnet_available             -- 1 if >=3 signals jointly usable, else 0
  physnet_n_signals             -- ensemble size actually used (context)
  physnet_mean_connectivity     -- mean |corr| over all pairs, averaged across
                                   all windows (overall integration)
  physnet_connectivity_decline  -- mean connectivity in the FIRST third of
                                   windows minus the LAST third (disintegration
                                   over the case; positive = weakening). None if
                                   < 3 windows.
  physnet_decouple_event_rate   -- count of edge "break" events (edge >= EDGE_ON
                                   in one window dropping < EDGE_ON in the next)
                                   per HOUR of intraop time
  physnet_weak_edge_frac        -- fraction of all (window x edge) slots with
                                   weight < EDGE_ON (sparsity / fragmentation)
  physnet_mean_transfer_entropy -- mean pairwise directed transfer entropy
                                   across the ensemble (total directed
                                   information flow). pk-tier.
  physnet_te_asymmetry          -- mean over unordered pairs of
                                   |TE(i->j) - TE(j->i)| (net directionality /
                                   driver-follower imbalance). pk-tier.

LEAKAGE (Sec 11)
----------------
All features are timing="intraop". The intraop window ends at opend; no sample
at t > opend is ever used (the alignment grid never extends past opend).
audit_specs() enforces the no-postop rule at import.

MISSINGNESS
-----------
If fewer than 3 signals are jointly usable (or too few joint points), ALL
features are None EXCEPT physnet_available, which is 0. Each signal is
range-gated before alignment (artifact rejection identical in spirit to
pfds.py / hemodynamics.py).

NUMERICS: Pearson, alignment, and the network topology are pure stdlib. Transfer
entropy's joint-histogram counting is numpy-vectorized (np.bincount over flattened
bin indices; numpy lazily imported inside the function so the stdlib paths are
unaffected) and is bit-identical to the prior dict counting; it is additionally
capped to TE_MAX_POINTS by uniform stride and guards short/degenerate series.

Protocol reference: Sec 7C (hemodynamic axis), Sec 7F (multi-signal coupling).
"""
from __future__ import annotations

import math
from typing import Any

from vitaldb_aki.features.base import FeatureSpec, audit_specs

# The matrix builder parallelizes track-heavy modules per case.
USES_TRACKS = True

# ---------------------------------------------------------------------------
# Signal ensemble + physiologic gates (binding; mirror pfds.py / hemodynamics).
# Each entry: candidate track names (first_available order) + [vmin, vmax].
# NUMERIC tracks only -- no packed 500 Hz waveforms here.
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
TEMP_TRACK_CANDIDATES: list[str] = [
    "Solar8000/BT",
]

MAP_MIN: float = 20.0
MAP_MAX: float = 200.0
HR_MIN: float = 20.0
HR_MAX: float = 220.0
ETCO2_MIN: float = 5.0
ETCO2_MAX: float = 70.0
SPO2_MIN: float = 50.0
SPO2_MAX: float = 100.0
TEMP_MIN: float = 30.0
TEMP_MAX: float = 42.0

# Ordered ensemble: (signal_name, candidates, vmin, vmax). Temp is optional
# (often absent) but treated identically when present.
SIGNAL_ENSEMBLE: list[tuple[str, list[str], float, float]] = [
    ("MAP", MAP_TRACK_CANDIDATES, MAP_MIN, MAP_MAX),
    ("HR", HR_TRACK_CANDIDATES, HR_MIN, HR_MAX),
    ("EtCO2", ETCO2_TRACK_CANDIDATES, ETCO2_MIN, ETCO2_MAX),
    ("SpO2", SPO2_TRACK_CANDIDATES, SPO2_MIN, SPO2_MAX),
    ("Temp", TEMP_TRACK_CANDIDATES, TEMP_MIN, TEMP_MAX),
]

# ---------------------------------------------------------------------------
# Network / alignment constants (binding; pre-registered).
# ---------------------------------------------------------------------------
GRID_DT_S: float = 5.0          # alignment grid spacing
MAX_STALE_S: float = 10.0       # last-value-hold staleness cap
MIN_SIGNALS: int = 3            # require >=3 jointly usable signals
MIN_JOINT_POINTS: int = 60      # require >=60 jointly-valid grid points
WINDOW_S: float = 120.0         # consecutive non-overlapping network windows
EDGE_ON: float = 0.5            # |corr| threshold for an "on" edge
TE_NBINS: int = 3               # terciles for binned transfer entropy
TE_MAX_POINTS: int = 2000       # cap joint length for TE (cost control)
TE_MIN_POINTS: int = 100        # minimum joint points to attempt TE

# ---------------------------------------------------------------------------
# Feature specs (Sec 9 nested design; all "intraop" -- leakage firewall Sec 11).
# First spec is the availability flag, per the binding contract.
# ---------------------------------------------------------------------------
SPECS: list[FeatureSpec] = [
    FeatureSpec(
        "physnet_available", "comprehensive", "intraop",
        "1 if >=3 vital signals were jointly usable (aligned, >=60 joint grid "
        "points) for the physiologic coupling network, else 0",
    ),
    FeatureSpec(
        "physnet_n_signals", "comprehensive", "intraop",
        "ensemble size: number of vital signals jointly usable in the network "
        "(integer, context)",
    ),
    FeatureSpec(
        "physnet_mean_connectivity", "comprehensive", "intraop",
        "mean edge weight |Pearson corr| over all signal pairs, averaged across "
        "all 120 s windows -- overall network integration",
    ),
    FeatureSpec(
        "physnet_connectivity_decline", "comprehensive", "intraop",
        "mean connectivity in the FIRST third of windows minus the LAST third "
        "(network disintegration over the case; positive = weakening). None if "
        "< 3 windows",
    ),
    FeatureSpec(
        "physnet_decouple_event_rate", "comprehensive", "intraop",
        "count of edge break events (an edge >= EDGE_ON in one window dropping "
        "< EDGE_ON in the next) per HOUR of intraop time -- decoupling dynamics",
    ),
    FeatureSpec(
        "physnet_weak_edge_frac", "comprehensive", "intraop",
        "fraction of all (window x edge) slots with weight < EDGE_ON -- network "
        "sparsity / fragmentation",
    ),
    FeatureSpec(
        "physnet_mean_transfer_entropy", "pk", "intraop",
        "mean pairwise directed binned transfer entropy across the ensemble "
        "(total directed information flow); k=3 tercile bins, lag 1 grid step. "
        "Heavier (pk-tier)",
    ),
    FeatureSpec(
        "physnet_te_asymmetry", "pk", "intraop",
        "mean over unordered pairs of |TE(i->j) - TE(j->i)| (net directionality "
        "/ driver-follower imbalance). Heavier (pk-tier)",
    ),
]

audit_specs(SPECS)   # hard error at import if any feature has postop timing


# ===========================================================================
# Window / gating helpers (copied from pfds.py for the binding contract).
# ===========================================================================

def _intraop_window(case: dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (t_start, t_end) in seconds.  Priority: anestart > opstart > None.

    Copied verbatim from pfds._intraop_window per the binding contract:
    t_end is opend (the leakage cutoff); no sample at t > opend is ever used.
    """
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


def _filter_physiologic(
    samples: list[tuple[float, float]],
    vmin: float,
    vmax: float,
) -> list[tuple[float, float]]:
    """Drop samples outside [vmin, vmax] (artifact rejection)."""
    return [(t, v) for t, v in samples if vmin <= v <= vmax]


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


# ===========================================================================
# Pure computational helpers (no I/O; unit-testable on synthetic series).
# ===========================================================================

def _uniform_cap(series: list[float], maxlen: int) -> list[float]:
    """Uniformly decimate `series` to at most `maxlen` points by integer stride.

    Bounds the per-pass cost of transfer entropy on pathologically long aligned
    grids (uniform striding preserves temporal structure far better than
    truncation and is deterministic). Returned unchanged when already short
    enough or when maxlen <= 0.
    """
    n = len(series)
    if maxlen <= 0 or n <= maxlen:
        return list(series)
    stride = (n + maxlen - 1) // maxlen   # ceil(n / maxlen)
    return series[::stride]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient of two equal-length series.

    Returns None if fewer than 2 points or either series is constant (zero
    variance -- correlation undefined). Clamped to [-1, 1] for numerical safety.
    """
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    sx = sum(xs[:n])
    sy = sum(ys[:n])
    mx = sx / n
    my = sy / n
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    for i in range(n):
        dx = xs[i] - mx
        dy = ys[i] - my
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
    if sxx <= 0.0 or syy <= 0.0:
        return None
    r = sxy / math.sqrt(sxx * syy)
    if r > 1.0:
        r = 1.0
    elif r < -1.0:
        r = -1.0
    return r


def _align_grid(
    signals_dict: dict[str, list[tuple[float, float]]],
    t_start: float,
    t_end: float,
    dt: float = GRID_DT_S,
    max_stale: float = MAX_STALE_S,
) -> tuple[list[float], dict[str, list[float]]]:
    """Align multiple irregular signals onto a common dt grid; keep JOINT points.

    For each grid time g (t_start, t_start+dt, ... up to <= t_end), each signal
    contributes its most recent sample at or before g via last-value-hold, but
    only if that sample is no older than `max_stale` seconds (otherwise the
    signal is considered missing at g). A grid point is kept only when EVERY
    signal in `signals_dict` has a fresh value there (jointly valid).

    Pure: no I/O, no numpy. Each input series may be unsorted; it is sorted by
    time internally.

    Returns
    -------
    (grid_times, aligned) where:
      grid_times : list[float]  -- the retained jointly-valid grid times
      aligned    : dict[name -> list[float]]  -- per-signal values at those
                   times, all the same length as grid_times.

    If signals_dict is empty, or t_end <= t_start, or no grid point is jointly
    valid, returns ([], {name: [] for name in signals_dict}).
    """
    names = list(signals_dict.keys())
    empty: dict[str, list[float]] = {nm: [] for nm in names}
    if not names or t_end <= t_start or dt <= 0:
        return [], empty

    # Sort each signal once for the marching last-value-hold.
    sorted_sigs: dict[str, list[tuple[float, float]]] = {
        nm: sorted(signals_dict[nm], key=lambda p: p[0]) for nm in names
    }
    # Per-signal cursor into its sorted samples.
    cursor: dict[str, int] = {nm: 0 for nm in names}
    last: dict[str, tuple[float, float] | None] = {nm: None for nm in names}

    grid_times: list[float] = []
    aligned: dict[str, list[float]] = {nm: [] for nm in names}

    # March the grid forward; advance each cursor monotonically.
    n_steps = int(math.floor((t_end - t_start) / dt)) + 1
    for k in range(n_steps):
        g = t_start + k * dt
        if g > t_end:
            break
        joint_ok = True
        held: dict[str, float] = {}
        for nm in names:
            sig = sorted_sigs[nm]
            cur = cursor[nm]
            # Advance to the latest sample with time <= g.
            while cur < len(sig) and sig[cur][0] <= g:
                last[nm] = sig[cur]
                cur += 1
            cursor[nm] = cur
            held_sample = last[nm]
            if held_sample is None or (g - held_sample[0]) > max_stale:
                joint_ok = False
                break
            held[nm] = held_sample[1]
        if joint_ok:
            grid_times.append(g)
            for nm in names:
                aligned[nm].append(held[nm])

    return grid_times, aligned


def _network_per_window(
    channels: dict[str, list[float]],
    win_pts: int,
    edge_on: float = EDGE_ON,
) -> list[dict[tuple[str, str], float]]:
    """Build a per-window edge network from aligned channels.

    `channels` maps signal name -> aligned value list (all equal length, on a
    common grid). The grid is carved into consecutive, NON-overlapping windows
    of `win_pts` points each (a trailing partial window is dropped). In each
    window, edge weight(i, j) = |Pearson corr| between signals i and j over the
    pairs (sorted by name for a canonical key).

    Returns a list (one dict per window) of {(name_i, name_j): weight}. Pairs
    whose correlation is undefined in a window (constant signal) are omitted
    from that window's dict.

    `edge_on` is accepted for interface symmetry (thresholding happens in the
    decouple counter / fragmentation features); it does not affect the weights.
    """
    names = sorted(channels.keys())
    if len(names) < 2 or win_pts < 2:
        return []
    lengths = {len(channels[nm]) for nm in names}
    if len(lengths) != 1:
        # Defensive: channels must be co-aligned. Trim to the shortest.
        n = min(lengths)
    else:
        n = lengths.pop()
    if n < win_pts:
        return []

    pairs = [
        (names[i], names[j])
        for i in range(len(names))
        for j in range(i + 1, len(names))
    ]

    nets: list[dict[tuple[str, str], float]] = []
    n_windows = n // win_pts
    for w in range(n_windows):
        lo = w * win_pts
        hi = lo + win_pts
        net: dict[tuple[str, str], float] = {}
        for a, b in pairs:
            r = _pearson(channels[a][lo:hi], channels[b][lo:hi])
            if r is not None:
                net[(a, b)] = abs(r)
        nets.append(net)
    return nets


def _mean_connectivity(window_nets: list[dict[tuple[str, str], float]]) -> float | None:
    """Mean edge weight over all pairs, averaged across all windows.

    For each window the mean is taken over its defined edges; the per-window
    means are then averaged. Windows with no defined edges are skipped. Returns
    None if there are no windows with any defined edge.
    """
    per_window: list[float] = []
    for net in window_nets:
        if net:
            per_window.append(sum(net.values()) / len(net))
    if not per_window:
        return None
    return sum(per_window) / len(per_window)


def _connectivity_decline(
    window_nets: list[dict[tuple[str, str], float]],
) -> float | None:
    """First-third mean connectivity minus last-third mean connectivity.

    Splits the window sequence into thirds by count; positive = the network
    weakened over the case (disintegration). Returns None if < 3 windows or
    either third has no defined edges.
    """
    n = len(window_nets)
    if n < 3:
        return None
    third = n // 3
    first = window_nets[:third]
    last = window_nets[n - third:]

    def _mean(nets: list[dict[tuple[str, str], float]]) -> float | None:
        vals: list[float] = []
        for net in nets:
            if net:
                vals.append(sum(net.values()) / len(net))
        if not vals:
            return None
        return sum(vals) / len(vals)

    m_first = _mean(first)
    m_last = _mean(last)
    if m_first is None or m_last is None:
        return None
    return m_first - m_last


def _decouple_events(
    window_nets: list[dict[tuple[str, str], float]],
    edge_on: float = EDGE_ON,
) -> int:
    """Count edge "break" events across consecutive windows.

    A break is an edge with weight >= edge_on in window w dropping < edge_on in
    window w+1 (the edge must be defined in both windows to count). Returns the
    total number of such break events over the whole sequence.
    """
    if len(window_nets) < 2:
        return 0
    events = 0
    for w in range(len(window_nets) - 1):
        cur = window_nets[w]
        nxt = window_nets[w + 1]
        for edge, weight in cur.items():
            if weight >= edge_on and edge in nxt and nxt[edge] < edge_on:
                events += 1
    return events


def _weak_edge_frac(
    window_nets: list[dict[tuple[str, str], float]],
    edge_on: float = EDGE_ON,
) -> float | None:
    """Fraction of all (window x edge) slots with weight < edge_on.

    Counts over all defined edges in all windows. Returns None if there are no
    defined edge slots at all.
    """
    total = 0
    weak = 0
    for net in window_nets:
        for weight in net.values():
            total += 1
            if weight < edge_on:
                weak += 1
    if total == 0:
        return None
    return weak / total


def _tercile_bins(values: list[float], nbins: int = TE_NBINS) -> list[int]:
    """Assign each value to one of `nbins` equal-COUNT bins (terciles for 3).

    Bin edges are chosen on the sorted values so each bin holds roughly the same
    number of points (rank-based binning -- robust to scale and outliers).
    Returns a list of bin indices in [0, nbins-1], same length as `values`.
    Ties at an edge fall into the lower bin via rank position.
    """
    n = len(values)
    if n == 0:
        return []
    if nbins < 1:
        nbins = 1
    # Rank each value (average-free: use sorted order; ties broken by index so
    # the partition is by rank position, giving near-equal counts).
    order = sorted(range(n), key=lambda i: values[i])
    bins = [0] * n
    for rank, idx in enumerate(order):
        b = (rank * nbins) // n
        if b >= nbins:
            b = nbins - 1
        bins[idx] = b
    return bins


def _transfer_entropy(
    x: list[float],
    y: list[float],
    nbins: int = TE_NBINS,
) -> float | None:
    """Binned transfer entropy TE(X -> Y) with lag 1 grid step. NUMPY-vectorized.

    TE(X->Y) = sum p(y_{t+1}, y_t, x_t) * log2[ p(y_{t+1}|y_t, x_t) /
                                                p(y_{t+1}|y_t) ]

    Each signal is discretized into `nbins` equal-count bins (terciles for
    nbins=3). Probabilities are estimated by counting the joint triples
    (y_{t+1}, y_t, x_t) over t = 0 .. n-2. Logarithm base 2 (bits).

    Cost / poison-pill guards
    -------------------------
    The estimator is per-pair O(n) (one pass over transitions), so it was never
    the bottleneck the SampEn modules were -- but it is called over many
    pairs x windows. The Python dict-counting loop is replaced by a vectorized
    joint histogram (a single np.bincount over flattened bin indices), and:
      * the joint series is capped to TE_MAX_POINTS by uniform stride (bounds the
        single pass even on pathologically long aligned grids);
      * SHORT series (< 3 points / < 2 transitions) -> None;
      * a DEGENERATE constant series bins to a single tercile, so every
        conditional ratio is 1 and TE == 0.0 -- returned without spurious work.

    Returns None if fewer than 2 usable transitions. TE is >= 0 by construction
    (it is a conditional mutual information estimate); tiny negative values from
    floating point are clamped to 0.
    """
    import numpy as np

    n = min(len(x), len(y))
    if n < 3:
        return None
    xs = _uniform_cap(list(x[:n]), TE_MAX_POINTS)
    ys = _uniform_cap(list(y[:n]), TE_MAX_POINTS)
    n = min(len(xs), len(ys))
    if n < 3:
        return None

    if nbins < 1:
        nbins = 1
    bx = np.asarray(_tercile_bins(xs, nbins), dtype=np.intp)
    by = np.asarray(_tercile_bins(ys, nbins), dtype=np.intp)

    # Transitions t -> t+1 (t = 0 .. n-2). Vectorize the joint counts via a
    # single flat histogram of the (y1, y0, x0) triples; the marginals are
    # reductions of that 3-D table. Bit-identical to the old dict counting.
    y1 = by[1:]        # y_{t+1}
    y0 = by[:-1]       # y_t
    x0 = bx[:-1]       # x_t
    total = y1.shape[0]
    if total < 2:
        return None

    nb = nbins
    flat = (y1 * nb + y0) * nb + x0          # index into (nb, nb, nb)
    c_yyx = np.bincount(flat, minlength=nb * nb * nb).reshape(nb, nb, nb)
    c_yx = c_yyx.sum(axis=0)                 # (y0, x0)  -- marginal over y1
    c_yy = c_yyx.sum(axis=2)                 # (y1, y0)  -- marginal over x0
    c_y = c_yyx.sum(axis=(0, 2))             # (y0,)     -- marginal over y1, x0

    idx = np.argwhere(c_yyx > 0)             # occupied (y1, y0, x0) cells
    te = 0.0
    for yy1, yy0, xx0 in idx:
        n_yyx = c_yyx[yy1, yy0, xx0]
        p_yyx = n_yyx / total
        p_y1_given_yx = n_yyx / c_yx[yy0, xx0]
        p_y1_given_y = c_yy[yy1, yy0] / c_y[yy0]
        if p_y1_given_yx > 0.0 and p_y1_given_y > 0.0:
            te += p_yyx * math.log2(p_y1_given_yx / p_y1_given_y)
    if te < 0.0:
        te = 0.0
    return float(te)


def _mean_te(
    channels: dict[str, list[float]],
    nbins: int = TE_NBINS,
    max_points: int = TE_MAX_POINTS,
) -> tuple[float | None, float | None]:
    """Mean directed transfer entropy and TE asymmetry across the ensemble.

    For every ORDERED pair (i, j) computes TE(i -> j); the first return value is
    the mean over all ordered pairs (total directed information flow). The
    second is the mean over UNORDERED pairs of |TE(i->j) - TE(j->i)| (net
    directionality / driver-follower imbalance).

    Each channel is capped to the first `max_points` aligned points before
    binning (cost control). Returns (None, None) if < 2 channels or no pair
    yields a defined TE in both directions.
    """
    names = sorted(channels.keys())
    if len(names) < 2:
        return None, None
    capped = {nm: channels[nm][:max_points] for nm in names}

    ordered_te: list[float] = []
    asym: list[float] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            te_ab = _transfer_entropy(capped[a], capped[b], nbins)
            te_ba = _transfer_entropy(capped[b], capped[a], nbins)
            if te_ab is not None:
                ordered_te.append(te_ab)
            if te_ba is not None:
                ordered_te.append(te_ba)
            if te_ab is not None and te_ba is not None:
                asym.append(abs(te_ab - te_ba))

    mean_te = sum(ordered_te) / len(ordered_te) if ordered_te else None
    mean_asym = sum(asym) / len(asym) if asym else None
    return mean_te, mean_asym


# ===========================================================================
# Case-level aggregation (pure; takes already-gated aligned channels).
# ===========================================================================

def compute_network_features(
    aligned: dict[str, list[float]],
    t_start: float,
    t_end: float,
    grid_dt: float = GRID_DT_S,
    window_s: float = WINDOW_S,
    edge_on: float = EDGE_ON,
) -> dict[str, Any]:
    """Compute all physnet features from co-aligned channels.

    `aligned` maps signal name -> aligned value list (all equal length, on a
    grid of spacing `grid_dt` over [t_start, t_end]). Requires >= MIN_SIGNALS
    channels and >= MIN_JOINT_POINTS joint points or returns the none-row with
    physnet_available=0.

    Returns a dict with every SPECS key.
    """
    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["physnet_available"] = 0

    names = sorted(aligned.keys())
    if len(names) < MIN_SIGNALS:
        return dict(none_row)
    n_points = min((len(aligned[nm]) for nm in names), default=0)
    if n_points < MIN_JOINT_POINTS:
        return dict(none_row)

    row: dict[str, Any] = dict(none_row)
    row["physnet_available"] = 1
    row["physnet_n_signals"] = len(names)

    # --- Topology (comprehensive) -----------------------------------------
    win_pts = max(2, int(round(window_s / grid_dt))) if grid_dt > 0 else 2
    window_nets = _network_per_window(aligned, win_pts, edge_on)

    mc = _mean_connectivity(window_nets)
    if mc is not None:
        row["physnet_mean_connectivity"] = round(mc, 6)

    decl = _connectivity_decline(window_nets)
    if decl is not None:
        row["physnet_connectivity_decline"] = round(decl, 6)

    n_events = _decouple_events(window_nets, edge_on)
    intraop_hours = (t_end - t_start) / 3600.0 if t_end > t_start else None
    if intraop_hours is not None and intraop_hours > 0:
        row["physnet_decouple_event_rate"] = round(n_events / intraop_hours, 6)

    wef = _weak_edge_frac(window_nets, edge_on)
    if wef is not None:
        row["physnet_weak_edge_frac"] = round(wef, 6)

    # --- Directed information flow (pk; heavier) --------------------------
    if n_points >= TE_MIN_POINTS:
        mean_te, te_asym = _mean_te(aligned)
        if mean_te is not None:
            row["physnet_mean_transfer_entropy"] = round(mean_te, 6)
        if te_asym is not None:
            row["physnet_te_asymmetry"] = round(te_asym, 6)

    return row


# ===========================================================================
# extract() -- the module entry point (FeatureSpec contract).
# ===========================================================================

def extract(
    cfg: dict[str, Any],
    cases_by_id: dict[str, dict],
    caseids: list[str],
) -> dict[str, dict[str, Any]]:
    """Emit {caseid: {feature_name: value|None}} for the physiologic network.

    Downloads each ensemble signal per case (cached numeric tracks), gates it to
    its physiologic range and the intraop window [t_start, opend], aligns all
    present signals onto a common dt=5 s grid keeping jointly-valid points, then
    computes the time-evolving coupling network.

    Missingness: if < MIN_SIGNALS signals are jointly usable (or < MIN_JOINT_POINTS
    joint grid points), all features are None EXCEPT physnet_available (0).
    """
    from vitaldb_aki.data.tracks import download_track, first_available
    from vitaldb_aki.data.client import to_float  # noqa: F401 (contract import)

    none_row: dict[str, Any] = {s.name: None for s in SPECS}
    none_row["physnet_available"] = 0

    out: dict[str, dict[str, Any]] = {}

    for cid in caseids:
        cid_str = str(cid)
        case = cases_by_id.get(cid_str)
        if case is None:
            out[cid_str] = dict(none_row)
            continue

        t_start, t_end = _intraop_window(case)
        if t_start is None or t_end is None or t_end <= t_start:
            out[cid_str] = dict(none_row)
            continue

        # ---- Gather + gate each ensemble signal -------------------------
        signals: dict[str, list[tuple[float, float]]] = {}
        for sig_name, candidates, vmin, vmax in SIGNAL_ENSEMBLE:
            _tname, raw = first_available(cfg, cid_str, candidates)
            if not raw:
                continue
            clipped = _clip_to_window(raw, t_start, t_end)
            gated = _filter_physiologic(clipped, vmin, vmax)
            if len(gated) >= 2:
                signals[sig_name] = gated

        if len(signals) < MIN_SIGNALS:
            out[cid_str] = dict(none_row)
            continue

        # ---- Align onto the common grid (joint points only) -------------
        _grid_times, aligned = _align_grid(
            signals, t_start, t_end, dt=GRID_DT_S, max_stale=MAX_STALE_S
        )
        # Drop any signal that ended up entirely missing (shouldn't happen, but
        # _align_grid keeps every key) and re-check the joint count.
        out[cid_str] = compute_network_features(aligned, t_start, t_end)

    return out


# ===========================================================================
# Real-data validation (run once; network code under __main__).
# Run: python -m vitaldb_aki.features.physio_network
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

    print(f"physio_network validation on {len(cohort_ids)} cases: {cohort_ids}")

    all_cases = fetch_cases(cfg)
    cases_by_id = {str(c["caseid"]): c for c in all_cases}

    result = extract(cfg, cases_by_id, cohort_ids)

    keys = [s.name for s in SPECS]
    print("\nPer-case physio_network summary:")
    for cid in cohort_ids:
        r = result.get(cid, {})
        vals = "  ".join(f"{k}={r.get(k)!r}" for k in keys)
        print(f"  case {cid:>5s}: {vals}")
