"""Which channels in this window are plausibly scalp EEG at all?

WHY THIS EXISTS. E20's registered gate failed, and the cause was not biology: in one 30 s awake window of
`ds004541`, 23 of 62 channels sat in a physiological amplitude band and 39 did not, running from 1,600 up to
153,000 microvolts. `_mean_psd` averages power across every channel it is handed, and nothing anywhere in
this pipeline had ever asked whether a channel was a channel. Over all 62 that window reports relative alpha
of 0.021; over the 23 plausible ones, 0.092. An awake human with 2 % alpha has not been recorded.

WHAT WAS TRIED FIRST AND DID NOT WORK, recorded because it is the obvious idea. The first diagnosis was that
one enormous channel dominated the power sum, and the fix would be a robust aggregator — a per-frequency
median across channels. It moved relative delta by 0.007, because on that deposit **the median channel is
bad too**. Robust aggregation defends against a minority of outliers. It cannot defend against a majority.
Only rejecting channels can, which is what this module does.

WHY THE TEST IS ABSOLUTE AND NOT RELATIVE. A scale-free test — "reject channels more than 10x the montage
median" — needs no units and would be tidier. It also fails on exactly the case that motivated this, because
the median is inside the bad population. The plausible band has to be anchored to physiology, and that means
it has to be anchored to volts.

    THE COST OF THAT, AND IT IS NOT NEGOTIABLE: **this test is only meaningful when the data really are in
    microvolts.** `Adapter.units` declares that per deposit, and one of them, HBN, declares
    `"uncalibrated"`. `channel_quality` therefore takes the units and REFUSES to judge amplitude when they
    are not microvolts, returning every channel as kept with `units_unknown` recorded. A filter that
    silently rejected every channel of an uncalibrated deposit, or silently kept every channel of a broken
    one, would both be worse than saying so.

THE BAND IS A DECLARED JUDGEMENT, NOT A FITTED PARAMETER. 5 to 150 microvolts brackets scalp EEG with room
at the top for high-amplitude slow waves under anaesthesia and at the bottom for a quiet electrode. It was
chosen from physiology before any deposit was scored against it, and it is not tuned per deposit — a
per-deposit threshold would be a free parameter fitted to make results come out, which is the thing the
programme's constraints exist to prevent.

WHAT THIS MODULE DELIBERATELY DOES NOT DO. It does not interpolate, re-reference, or repair. It reports a
mask and the reasons behind it. Whether a caller drops the bad channels, refuses the window, or records the
count alongside the result is the caller's decision and should be visible in the caller's code.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

MIN_SD_UV = 5.0
MAX_SD_UV = 150.0
MAX_NONFINITE_FRACTION = 0.10
MIN_KEPT_FRACTION = 0.50
"""Below this fraction of surviving channels, a window is worth flagging rather than silently averaging over
whatever is left. Reported by `channel_quality`; acting on it is the caller's decision."""

MICROVOLT_UNITS = frozenset({"microvolts", "uv", "µv", "microvolt"})


def channel_quality(data: np.ndarray, ch_names: Optional[Sequence[str]] = None,
                    units: str = "microvolts") -> Dict[str, object]:
    """A keep-mask over channels, with the reason each rejected channel was rejected.

    Three tests, in order, and a channel fails on the first that applies:

      `nonfinite`  more than 10 % of its samples are NaN or infinite — a dropout, not a signal.
      `flat`       zero variance across the window — a disconnected or shorted electrode. This one is
                   unit-free and is applied even when the units are unknown, because a constant is not a
                   measurement in any unit.
      `amplitude`  standard deviation outside 5-150 microvolts. Applied ONLY when `units` says microvolts.

    Returns `keep` (bool array), `reasons` (per-channel string, empty when kept), `n_kept`, `frac_kept`,
    `sd_uv`, and `units_judged` — False when the amplitude test was skipped, so a caller can tell "every
    channel passed" from "amplitude was never tested".
    """
    x = np.asarray(data, float)
    if x.ndim == 1:
        x = x[None, :]
    n_ch = x.shape[0]
    keep = np.ones(n_ch, bool)
    reasons: List[str] = [""] * n_ch

    finite = np.isfinite(x)
    frac_nonfinite = 1.0 - finite.mean(axis=1) if x.shape[1] else np.ones(n_ch)

    sd = np.full(n_ch, np.nan)
    for i in range(n_ch):
        v = x[i][finite[i]]
        if v.size:
            sd[i] = float(np.std(v))

    judged = str(units).strip().lower() in MICROVOLT_UNITS
    for i in range(n_ch):
        if frac_nonfinite[i] > MAX_NONFINITE_FRACTION:
            keep[i], reasons[i] = False, "nonfinite"
            continue
        if not np.isfinite(sd[i]) or sd[i] == 0.0:
            keep[i], reasons[i] = False, "flat"
            continue
        if judged and not (MIN_SD_UV <= sd[i] <= MAX_SD_UV):
            keep[i], reasons[i] = False, "amplitude"

    return {"keep": keep, "reasons": reasons, "sd_uv": sd,
            "n_channels": int(n_ch), "n_kept": int(keep.sum()),
            "frac_kept": float(keep.mean()) if n_ch else float("nan"),
            "units_judged": bool(judged),
            "below_min_kept_fraction": bool(n_ch and keep.mean() < MIN_KEPT_FRACTION),
            "ch_names": list(ch_names) if ch_names is not None else None}


def summarise(q: Dict[str, object]) -> str:
    """One line, for a log. Names the failure modes present rather than only the count."""
    from collections import Counter
    bad = Counter(r for r in q["reasons"] if r)                       # type: ignore[union-attr]
    tail = ("  " + " ".join(f"{k}={v}" for k, v in sorted(bad.items()))) if bad else ""
    unjudged = "" if q["units_judged"] else "  (amplitude NOT tested: units are not microvolts)"
    return (f"{q['n_kept']}/{q['n_channels']} channels kept "
            f"({q['frac_kept']:.0%}){tail}{unjudged}")
