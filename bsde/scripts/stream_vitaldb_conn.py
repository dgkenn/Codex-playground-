"""Stream INTER-CHANNEL connectivity onto the same VitalDB grid, using the second EEG channel.

WHY THIS EXISTS, AND WHY IT IS EMBARRASSING THAT IT DID NOT. `docs/CONSOLIDATION_2026_07_31.md`: all three
discovery challenges are blocked on the same missing measure family, and it is inter-channel phase. E36
established its Challenge A family split on wPLI; E61 could not test it and fell back on within-channel
phase because the grid adapter returns ONE channel. Akeju et al. (PMID 25233374) separate sevoflurane from
propofol at matched depth by a theta COHERENCE signature -- an inter-channel quantity.

**`BIS/EEG2_WAV` is present on 250 of 250 grid cases and carries real signal** (case 1: 1,477,268 samples,
100 % finite, sd 87.69 uV). The second channel was there from the start; the adapter simply did not ask for
it. Verified before a line of this was written.

WHAT IS COMPUTED, AND WHY IN PAIRS. For each of delta, theta, alpha and beta: magnitude-squared
**coherence** and debiased **wPLI**, on the SAME segments through the same `_cross_spectra` helper.
Coherence is volume-conduction-prone and is included only because Akeju's finding is stated in it;
wPLI is the estimator this project trusts. **Reported together they are informative in a way neither is
alone** -- coherence high with wPLI low means amplitude or a common reference rather than phase coupling,
which is exactly the trap `bis_sfs` fell into (E59, and confirmed again at rho = -0.687 against
`spectral_edge_95`).

A SUBCLASS, NOT A CHANGE TO THE SHARED ADAPTER. Editing `VitalDBGridAdapter` to return two channels would
change the definition fingerprint of every existing table and break resumption. This subclass overrides the
loader only, writes its own table, and joins on `recording_id` -- the same pattern as
`stream_vitaldb_bis.py`, with the same `--verify-join` check before any bandwidth is spent.

THE SECOND CHANNEL'S NaN MASK IS HANDLED SEPARATELY FROM THE FIRST'S AND THEN INTERSECTED. Interpolating
each channel independently and then correlating them would manufacture phase relations across a dropout
that neither channel actually recorded (rule 27). A window is refused unless BOTH channels are usable over
the SAME samples.

    for k in 0 1 2 3; do
      python bsde/scripts/stream_vitaldb_conn.py --case-shard $k --of 4 \
             --out bsde/results/vitaldb_conn.s$k.csv &
    done; wait
    python bsde/scripts/stream_vitaldb_grid.py --merge bsde/results/vitaldb_conn.csv \
           bsde/results/vitaldb_conn.s*.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Dict, List

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.candidates.registry import REGISTRY, register                    # noqa: E402
from bsde.ingestion.runner import stream_features                          # noqa: E402
from bsde.ingestion.vitaldb import SFREQ, VitalDBGridAdapter               # noqa: E402

GRID_DEFAULTS = dict(n_cases=250, grid_s=300.0, window_s=30.0, max_windows=40)
META_KEYS = ("caseid", "t_s", "bis", "sqi", "sr", "emg", "sensor_off", "nan_fraction",
             "agents_present", "age", "sex")

BANDS = {"delta": (1.0, 4.0), "theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0)}


class VitalDBTwoChannelAdapter(VitalDBGridAdapter):
    """The grid adapter with both BIS EEG channels returned, on the identical window grid."""

    EEG2_TRACK = "BIS/EEG2_WAV"

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.name = f"vitaldb-grid-2ch:{self.window_s:.0f}s"
        self._series_cache: Dict[str, np.ndarray] = {}
        self._series_case = None
        self._eeg2: Dict[str, str] = {}

    def _eeg2_tid(self, cid: str) -> str:
        """caseid -> EEG2 track id, built once from the track index.

        NOT routed through the parent's `mon` dict, which is deliberately restricted to NUMERIC monitor
        tracks: `_monitor_window` reads every entry there with `_numeric`, so putting a 9.4 MB waveform in
        it would fetch and parse the whole channel as a numeric series on every window.
        """
        if not self._eeg2:
            from bsde.ingestion.vitaldb import tracks
            for t in tracks():
                if t["tname"] == self.EEG2_TRACK:
                    self._eeg2[t["caseid"]] = t["tid"]
        return self._eeg2.get(str(cid), "")

    def _series2(self, case: str, tid: str) -> np.ndarray:
        """Two-entry cache keyed by tid, dropped when the case changes.

        The parent caches exactly ONE tid, so alternating between EEG1 and EEG2 would re-download a 9.4 MB
        track on every access. This keeps both channels of the current case and nothing else.
        """
        if self._series_case != case:
            self._series_cache, self._series_case = {}, case
        if tid not in self._series_cache:
            from bsde.ingestion.vitaldb import _fetch, parse_waveform, API
            self._series_cache[tid] = parse_waveform(_fetch(f"{API}/{tid}"))
        return self._series_cache[tid]

    def _loader(self, tid: str, start_seconds: float, mon: Dict[str, str], cid: str):
        def load():
            tid2 = self._eeg2_tid(cid)
            if not tid2:
                raise ValueError("no BIS/EEG2_WAV track for this case")
            a = self._series2(cid, tid)
            b = self._series2(cid, tid2)
            i0 = int(round(start_seconds * SFREQ))
            n = int(round(self.window_s * SFREQ))
            s1, s2 = a[i0:i0 + n], b[i0:i0 + n]
            if s1.size < n * 0.9 or s2.size < n * 0.9:
                raise ValueError(f"window at {start_seconds:.0f}s runs past one of the two records")
            m = min(s1.size, s2.size)
            s1, s2 = s1[:m], s2[:m]
            # BOTH channels must be finite on the SAME samples; interpolating each alone and then
            # correlating them would invent phase across a dropout neither channel recorded (rule 27).
            ok = np.isfinite(s1) & np.isfinite(s2)
            if ok.mean() < 0.9:
                raise ValueError(f"window at {start_seconds:.0f}s: only {100 * ok.mean():.0f}% of samples "
                                 f"are finite on BOTH channels")
            if not ok.all():
                idx = np.flatnonzero(ok)
                s1 = np.interp(np.arange(m), idx, s1[idx])
                s2 = np.interp(np.arange(m), idx, s2[idx])
            meta = {"tid": tid, "start_s": start_seconds, "nan_fraction": float(1 - ok.mean())}
            meta.update(self._monitor_window(cid, mon, start_seconds))
            return np.vstack([s1, s2]), ["BIS_EEG1", "BIS_EEG2"], SFREQ, meta
        return load


def _pair(data):
    d = np.asarray(data, float)
    if d.shape[0] < 2:
        raise ValueError("two channels required")
    return d[0], d[1]


def _mk(kind: str, band: str):
    lo, hi = BANDS[band]

    def fn(data, ch_names, sfreq, meta=None) -> float:
        from bsde.features.connectivity import coherence, wpli
        x, y = _pair(data)
        return (coherence(x, y, float(sfreq), lo, hi) if kind == "coh"
                else wpli(x, y, float(sfreq), lo, hi))
    fn.__name__ = f"f_{kind}_{band}"
    return fn


def conn_candidates() -> List:
    """Register the eight, idempotently, and return them in a fixed order."""
    for band in BANDS:
        for kind, label, interp in (
                ("coh", "coherence", "Magnitude-squared coherence between the two frontal BIS channels. "
                                     "VOLUME-CONDUCTION-PRONE BY CONSTRUCTION and included to test a "
                                     "published claim stated in this quantity (Akeju et al., PMID "
                                     "25233374), never as a preferred estimator."),
                ("wpli", "wpli", "Debiased weighted phase-lag index between the two frontal BIS channels. "
                                 "Insensitive to zero-lag common sources, which is why it and not "
                                 "coherence carries any claim from this project.")):
            name = f"{label}_{band}"
            try:
                REGISTRY.get(name)
                continue
            except KeyError:
                pass
            register(
                name=name, version="1", fn=_mk(kind, band), complexity=4,
                interpretation=f"{interp} Band {band} ({BANDS[band][0]:.0f}-{BANDS[band][1]:.0f} Hz).",
                predictions={"unconscious_vs_awake": "higher"},
                notes="THE DIRECTION IS DECLARED FOR ALPHA AND CARRIED ACROSS BANDS RATHER THAN TUNED PER "
                      "BAND, which is a deliberately weak claim: frontal alpha coherence rises under "
                      "GABAergic anaesthesia (Akeju 2014 reports peak coherence ~0.72 in both propofol and "
                      "sevoflurane), and declaring the same direction everywhere makes the non-alpha bands "
                      "opportunities to be wrong rather than free passes. `anaesthetic_drug_identity` is "
                      "LEFT UNDECLARED: E36 predicts phase measures carry little of it and Akeju reports a "
                      "theta coherence signature that does, and asserting either as a prediction would be "
                      "pre-judging the experiment these columns exist to run.",
                failure_conditions=(
                    f"{name} is unchanged between awake and anaesthetised EEG in any cohort reaching "
                    f"genuine unconsciousness.",
                    "coherence and wPLI in the same band disagree in DIRECTION across drugs, which would "
                    "mean the coherence result is volume conduction or amplitude rather than phase.",
                ),
                requires=("computational",),
                prior_art="Akeju et al., Anesthesiology 2014 (PMID 25233374); Vinck et al. 2011 (wPLI).",
            )
    return [REGISTRY.get(f"{lab}_{b}") for b in BANDS for lab in ("coherence", "wpli")]


def verify_join(refs, grid_path: str) -> int:
    if not os.path.exists(grid_path):
        print(f"   grid {grid_path} absent -- cannot verify the join")
        return 1
    with open(grid_path, newline="") as fh:
        grid_ids = {r["recording_id"] for r in csv.DictReader(fh)}
    mine = {r.recording_id for r in refs}
    both = mine & grid_ids
    print(f"   join check: {len(mine)} windows here, {len(grid_ids)} in the grid, {len(both)} shared "
          f"({100.0 * len(both) / max(1, len(mine)):.1f}% of this run)")
    return 0 if len(both) >= 0.9 * len(mine) else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--case-shard", type=int, default=0, dest="case_shard")
    ap.add_argument("--of", type=int, default=1, dest="n_case_shards")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "vitaldb_conn.csv"))
    ap.add_argument("--grid", default=os.path.join(HERE, "..", "results", "vitaldb_grid.csv"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--verify-join", action="store_true", dest="verify_join")
    a = ap.parse_args(argv)

    cands = conn_candidates()
    adapter = VitalDBTwoChannelAdapter(case_shard=a.case_shard, n_case_shards=a.n_case_shards,
                                       **GRID_DEFAULTS)
    if a.verify_join:
        return verify_join(adapter.list_recordings(), os.path.abspath(a.grid))
    print(f"streaming {adapter.name} -> {a.out}", flush=True)
    print(f"   candidates: {[c.name for c in cands]}", flush=True)
    stats = stream_features(adapter, cands, os.path.abspath(a.out), limit=a.limit, meta_keys=META_KEYS)
    print(f"   {stats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
