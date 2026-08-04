"""Stream VitalDB onto a DENSE, transition-focused sampling plan, carrying BIS at its NATIVE rate.

MECHANICAL EXTRACTION for Challenge C timing (see `bsde/docs/PROBE_2026_08_02_CHALLENGE_C_TIMING.md` and
`build_vitaldb_transitions_plan.py`, which builds the plan this script streams). No registration, no ledger
row, no correlation with BIS or any state label happens here or should be added here -- that is a registered
experiment's job.

WHAT IS REUSED VERBATIM FROM `stream_vitaldb_grid.py` / `stream_vitaldb_fine.py` / `bsde.ingestion.vitaldb`:
API access (`_fetch`, `tracks()`, `cases()`), the case list (from the cached grid table via the plan
builder), channel selection (`BIS/EEG1_WAV` only, exactly as `VitalDBTargetedAdapter` already does), and all
preprocessing (NaN interpolation, the SQI-gated sensor-off handling, the candidate panel). NONE of that is
touched. The only things that change are (1) WHICH windows are taken -- the dense plan, not a grid or a
handful of offsets -- and (2) what rides along with each window: the raw, per-second BIS/SQI/SR/EMG samples,
not just their window mean.

WHY THE MONITOR NEEDS ITS OWN SUBCLASS. `VitalDBTargetedAdapter._monitor_window` (unmodified, inherited)
already returns the WINDOW MEAN of each monitor track, gated on SQI as documented in `vitaldb.py`. That mean
is kept here (columns `meta_bis`, `meta_sqi`, `meta_sr`, `meta_emg`) for continuity with `vitaldb_grid.csv`.
But the task this table exists for is TIMING, and BIS was measured (2026-08-02, one live case) to update
at 1 Hz -- so a 10 s window mean already throws away up to ~10 native samples worth of exactly the
information a timing question needs. `_TransitionAdapter` below adds the raw (offset-from-window-start,
value) pairs for each monitor track as a packed string column, computed from `self._numeric(...)`, which is
the SAME per-case-cached numeric fetch the inherited mean already uses -- so this costs no extra network
call, only a slice-and-format over an array already in memory.

RETRY WITH EXPONENTIAL BACKOFF. `vitaldb._fetch` has no retry of its own, and a transient failure inside
`ref.load()` is caught by the runner and written as a PERMANENT `status=error` row -- a resumed run does not
retry error rows, it treats them as done (`stream_features` builds its resume set from EVERY existing
`recording_id`, regardless of status). So a network blip would poison a window forever unless retried BEFORE
it reaches the runner. This module monkeypatches `bsde.ingestion.vitaldb._fetch` (module-level function
lookup, so this is visible to `_series`/`_numeric`/`tracks`/`cases`, all of which call the module-level name
at call time, not a bound copy) with a wrapper that retries up to 6 times with exponential backoff + jitter.
The wrapped function is installed once, at import, and is otherwise byte-identical to the original.

RESUMPTION. Delegated entirely to `bsde.ingestion.runner.stream_features`, which already (a) opens the
output in APPEND mode, never "w", (b) fsyncs after every row, (c) builds its resume set by reading the
existing file, and (d) refuses to append a different column set or a drifted candidate definition. Nothing
in this script re-implements any of that.

    for k in 0 1 2 3; do
      python bsde/scripts/stream_vitaldb_transitions.py --case-shard $k --of 4 \
             --out bsde/results/vitaldb_transitions.s$k.csv &
    done; wait
    python bsde/scripts/stream_vitaldb_grid.py --merge bsde/results/vitaldb_transitions.csv \
           bsde/results/vitaldb_transitions.s?.csv
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from typing import Dict, List, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import numpy as np  # noqa: E402

from bsde.candidates.registry import REGISTRY                         # noqa: E402
from bsde.candidates.seed import seed_registry                        # noqa: E402
from bsde.ingestion.runner import stream_features                     # noqa: E402
import bsde.ingestion.vitaldb as vdb                                  # noqa: E402
from bsde.ingestion.vitaldb import VitalDBTargetedAdapter             # noqa: E402
from bsde.ingestion.base import RecordingRef                          # noqa: E402

from stream_vitaldb_grid import META_KEYS as GRID_META_KEYS           # noqa: E402


# ---------------------------------------------------------------------------------------------------------
# Retry with exponential backoff, installed over the module-level fetch every VitalDB call goes through.
# ---------------------------------------------------------------------------------------------------------
_ORIG_FETCH = vdb._fetch


def _fetch_with_retry(url: str, timeout: float = 300.0, max_retries: int = 6, base_delay: float = 2.0):
    last_exc = None
    for attempt in range(max_retries):
        try:
            return _ORIG_FETCH(url, timeout=timeout)
        except Exception as e:  # noqa: BLE001 -- deliberately broad: network errors take many shapes
            last_exc = e
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
            print(f"   [retry] {type(e).__name__}: {e} -- attempt {attempt + 1}/{max_retries}, "
                  f"sleeping {delay:.1f}s ({url})", flush=True)
            time.sleep(delay)
    raise last_exc  # pragma: no cover -- unreachable, last iteration always re-raises


vdb._fetch = _fetch_with_retry


TRACE_META_KEYS = ("bis_trace", "bis_n", "sqi_trace", "sqi_n", "sr_trace", "sr_n", "emg_trace", "emg_n")
META_KEYS = tuple(GRID_META_KEYS) + TRACE_META_KEYS


class _TransitionAdapter(VitalDBTargetedAdapter):
    """`VitalDBTargetedAdapter`, unchanged, plus raw native-rate monitor traces per window.

    Every piece of case discovery, channel selection, NaN handling and the window-mean monitor gating is
    the PARENT class's code, untouched -- this only adds columns to the metadata dict the parent already
    builds, by re-slicing the SAME cached numeric arrays the parent's own `_monitor_window` reads.
    """

    def _loader(self, tid: str, start_seconds: float, mon: Dict[str, str], cid: str):
        base_load = super()._loader(tid, start_seconds, mon, cid)

        def load():
            data, ch_names, sfreq, meta = base_load()
            meta = dict(meta)
            meta.update(self._raw_traces(cid, mon, start_seconds))
            return data, ch_names, sfreq, meta

        return load

    def _raw_traces(self, cid: str, mon: Dict[str, str], t0: float) -> Dict[str, object]:
        """Native-rate (offset_from_window_start, value) pairs for every monitor track, packed as a string.

        `self._numeric` is the PARENT's own per-case-cached numeric fetch (same cache `_monitor_window`
        reads) -- calling it again here is a dict lookup, not a second network fetch. Format:
        `"o1:v1|o2:v2|..."`, offsets in seconds relative to the window start, 3 decimals; values at 4
        significant figures. Sensor-off (SQI==0) windows are NOT scrubbed here, unlike the parent's gated
        mean -- the raw trace is the ground truth an analysis would need to notice the sensor went off
        mid-window, which a single NaN'd mean cannot show.
        """
        out: Dict[str, object] = {}
        for name, tid in mon.items():
            short = name.split("/")[-1].lower()
            arr = self._numeric(cid, name, tid)
            if arr.size:
                m = (arr[:, 0] >= t0) & (arr[:, 0] < t0 + self.window_s)
                sub = arr[m]
            else:
                sub = np.zeros((0, 2))
            out[f"{short}_trace"] = "|".join(f"{(t - t0):.3f}:{v:.4g}" for t, v in sub)
            out[f"{short}_n"] = int(sub.shape[0])
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", default=os.path.join(HERE, "..", "results", "vitaldb_transitions_plan.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "vitaldb_transitions.csv"))
    ap.add_argument("--window-s", type=float, default=10.0, dest="window_s")
    ap.add_argument("--case-shard", type=int, default=0, dest="case_shard")
    ap.add_argument("--of", type=int, default=1, dest="n_case_shards")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--n-plan-cases", type=int, default=None, dest="n_plan_cases",
                    help="deterministic subset: keep only the first N plan cases, sorted by caseid (int)")
    a = ap.parse_args(argv)

    plan = json.load(open(os.path.abspath(a.plan)))
    if a.n_plan_cases is not None:
        keep = sorted(plan.keys(), key=lambda x: int(x))[: a.n_plan_cases]
        plan = {k: plan[k] for k in keep}
        print(f"deterministic subset: first {a.n_plan_cases} plan cases by caseid -> {sorted(keep, key=int)}",
              flush=True)

    seed_registry()
    cands = REGISTRY.all()
    adapter = _TransitionAdapter(plan, window_s=a.window_s, dataset="vitaldb_transitions",
                                 case_shard=a.case_shard, n_case_shards=a.n_case_shards)
    print(f"streaming {adapter.name} over {len(plan)} planned cases "
          f"({sum(len(v) for v in plan.values())} windows) -> {a.out}", flush=True)
    print(f"   candidates: {[c.name for c in cands]}", flush=True)
    stats = stream_features(adapter, cands, os.path.abspath(a.out), limit=a.limit, meta_keys=META_KEYS)
    print(f"   {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
