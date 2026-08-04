"""Frontal, posterior and whole-head aperiodic exponents as SEPARATE columns, on every multi-channel deposit.

WHY THIS DOES NOT ALREADY EXIST, and it is a gap worth naming. Every table in `bsde/results/` carries
`uce_v1` and `whole_head_exponent` but **neither regional exponent**, because `f_uce_v1` collapses frontal
and posterior into the score in one step. Two consequences, both discovered 2026-07-31:

  1. **`r(frontal, posterior)` cannot be recovered from any existing table**, so the question that decides
     whether UCE v1's two-region structure carries information -- does the split DECOUPLE under
     anaesthesia, where it matters? -- has never been answerable.
  2. **No `uce_v1` value in this repository is population-referenced.** `f_uce_v1` standardises only when
     `meta['uce_ref']` is supplied, and it never is. Every stored `uce_v1` is the raw weighted combination
     `0.696*frontal + 0.718*posterior`, monotone in the standardised score for fixed weights (so AUCs are
     unaffected) but **not on a "distance from an awake reference" scale and not comparable across
     cohorts.** The constants an external audit reports for that reference -- F_mean -1.4320, F_SD 0.5294,
     P_mean -1.4658, P_SD 0.5187 -- appear nowhere in this repository and have not been verified here.

This pass emits the regional exponents so both can be addressed, and emits the CHANNEL COUNTS beside them
because a "posterior exponent" averaged over one electrode is not the same measurement as one averaged over
twenty, and a reader cannot tell which they are looking at without the count.

    aperiodic_frontal      mean exponent over channels matching uce_v1.FRONTAL_CH
    aperiodic_posterior    mean over uce_v1.POSTERIOR_CH
    aperiodic_wholehead    mean over every finite channel
    n_frontal, n_posterior how many channels each average is over

Fit range, PSD method and window are `seed._exponents`' defaults (1-40 Hz, Welch 4 s, 50 % overlap,
`loglog_robust`) so these columns are directly comparable to `whole_head_exponent` in the existing tables
rather than being a second definition of the same word (rule 20).

    python bsde/scripts/extract_regional_aperiodic.py --deposit ds005620
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.registry import Candidate                              # noqa: E402
from bsde.candidates.seed import _exponents                                 # noqa: E402
from bsde.candidates.uce_v1 import regional_exponents                       # noqa: E402
from bsde.ingestion.runner import stream_features                           # noqa: E402

RESULTS = os.path.join(HERE, "..", "results")


def _regional(data, ch_names, sfreq, meta=None):
    return regional_exponents(_exponents(data, sfreq), ch_names)


def _cand(name, key):
    """One Candidate per emitted column. They share a single cached computation per recording."""
    cache = {}

    def fn(data, ch_names, sfreq, meta=None, _key=key):
        cid = id(data)
        if cid not in cache:
            cache.clear()
            cache[cid] = _regional(data, ch_names, sfreq, meta)
        return float(cache[cid][_key])

    return Candidate(
        name=name, version="1.0", fn=fn,
        interpretation=("regional aperiodic exponent, emitted so that r(frontal, posterior) and "
                        "population referencing are computable at all"),
        # The same commitment `whole_head_exponent` carries -- these ARE that measure, restricted to a
        # region. Declaring anything else would be inventing a separate hypothesis for a raw measurement.
        predictions={"unconscious_vs_awake": "higher",
                     "anaesthetic_drug_identity": "unchanged"},
        failure_conditions=["a region with no matching channel yields NaN, never a substitution from the "
                            "other region",
                            "the two regions are so collinear that their weighted combination is the "
                            "whole-head mean restated -- which is the question this column exists to make "
                            "answerable, not a defect in it"],
        # "computational" is mandatory and is genuinely satisfied: `regional_exponents` and
        # `_exponents` are both covered by tests/test_uce_v1.py and the aperiodic suite.
        requires=["computational"], complexity=1)


COLUMNS = [("aperiodic_frontal", "frontal"), ("aperiodic_posterior", "posterior"),
           ("aperiodic_wholehead", "whole_head"), ("n_frontal", "n_frontal"),
           ("n_posterior", "n_posterior")]


def build_adapter(deposit: str, window_s: float):
    if deposit == "ds005620":
        from bsde.ingestion.openneuro_brainvision import OpenNeuroBrainVisionAdapter
        return OpenNeuroBrainVisionAdapter("ds005620", dataset="ds005620", window_s=window_s), \
            ("task", "acq", "run")
    if deposit == "ds004541":
        from bsde.ingestion.ds004541 import DS004541Adapter
        return DS004541Adapter(), ()
    if deposit == "eegmmidb":
        from bsde.ingestion.eegmmidb import EEGMMIDBRestAdapter
        return EEGMMIDBRestAdapter(), ()
    if deposit == "hbn":
        from bsde.ingestion.hbn import HBNRestingAdapter
        return HBNRestingAdapter(), ()
    raise SystemExit(f"unknown deposit {deposit!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--deposit", required=True)
    ap.add_argument("--window-s", type=float, default=30.0, dest="window_s")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    adapter, meta_keys = build_adapter(a.deposit, a.window_s)
    out = a.out or os.path.join(RESULTS, f"{a.deposit}_regional_aperiodic.csv")
    cands = [_cand(name, key) for name, key in COLUMNS]
    print(f"streaming {adapter.name} -> {out}", flush=True)
    stats = stream_features(adapter, cands, os.path.abspath(out), limit=a.limit, meta_keys=meta_keys)
    print(f"   {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
