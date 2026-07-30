"""VitalDB — raw intraoperative EEG with the anaesthetic agent identified per case. Open, CC-BY 4.0.

WHY THIS DEPOSIT CHANGES WHAT THE PROJECT CAN ATTEMPT. Two of the three discovery challenges have been
blocked on data since they were written (§5, §9.22):

    Challenge A  needs >= 2 IDENTIFIED and DIFFERENT anaesthetic drugs, with a drug-identity probe that must
                 NOT out-predict the responsiveness model. Chennu and ds005620 are both propofol; ds004541
                 does not record its agent at all. There was no second drug.
    Challenge C  needs a trajectory feature that predicts a transition AHEAD of a conventional monitor, and
                 there was no deposit carrying both EEG and a monitor to be ahead of.

VitalDB carries both, verified against the API rather than the paper:

    BIS/EEG1_WAV, BIS/EEG2_WAV   5,871 cases   raw EEG, 128 Hz, microvolts
    BIS/BIS                      5,867 cases   the conventional monitor, for Challenge C
    BIS/SR                       5,569 cases   suppression ratio -- burst suppression, scored by the device
    BIS/EMG                      5,577 cases   a real muscle channel, not a spectral proxy
    Orchestra/PPF20_CE           3,511 cases   propofol effect-site concentration (TCI)
    Primus/INSP_SEVO             3,687 cases   sevoflurane
    Primus/INSP_DES              2,046 cases   desflurane

**Three identified agents, thousands of cases, one site, one monitor.** The agents overlap within cases
(propofol induction followed by a volatile is routine), so "the agent" is a property of a TIME WINDOW rather
than of a case, and `agent_tracks_present` returns what a case carries rather than asserting a single label.

WHAT THE 128 Hz SAMPLING COSTS, stated because it silently disables one candidate. Nyquist is 64 Hz, so
`exponent_gamma` (50-90 Hz) is NaN here BY DESIGN -- the same graceful degradation it shows on Sleep-EDF.
`exponent_high` (20-40 Hz) is inside the band and unaffected. The BIS sensor is a frontal strip of two
channels, so `uce_v1`, which needs frontal AND posterior 10-20 names, is also unavailable.

THE MUSCLE PROBE THIS DEPOSIT MAKES POSSIBLE, and it is better than anything the project has had.
`intraop_rocu` and `intraop_vecu` record neuromuscular-blocker dose per case. A paralysed patient cannot
generate EMG. So a candidate whose value depends on NMB dose, with anaesthetic depth held constant, is
reading muscle -- a direct test, against an administered drug, rather than against a spectral proxy of the
kind §9.15 found two of disagreeing in sign.

HOW MUCH POST-EMERGENCE RECORDING THERE IS, measured on six cases rather than assumed: the EEG track ends a
median of **+544 s** after `aneend`, and in one of six it ended **860 s BEFORE** it. Post-emergence EEG
exists, but it is short and not guaranteed — the monitor comes off soon after the anaesthetic does. Offsets
past +300 s overran roughly half the records in a first run, so the positive grid stops there. This is the
mirror of the induction problem below: **the sensor goes on after induction and comes off around emergence,
so this deposit captures the middle of an anaesthetic well and both of its edges poorly.**

WHICH TRANSITION THIS DEPOSIT ACTUALLY CONTAINS, measured rather than assumed. `anestart` is NEGATIVE in
**91.8 %** of cases -- the BIS sensor is applied after the patient is already induced, so **induction and
loss of consciousness are simply not in the recording** and no amount of windowing will recover them.
`aneend` sits at a median of 9,770 s (2.7 h) into the record, comfortably inside every track. **The
transition available here is EMERGENCE, not induction**, which is why `anchor` defaults to `aneend`. That
suits Challenge C, whose wording is about predicting delayed emergence ahead of a conventional monitor, and
it means ds004541 -- with its explicit `loc` marker -- remains the only deposit that can speak to induction.

COST. One EEG track is ~9.4 MB and spans about three hours. Tracks are fetched whole and cached one at a
time, because the API serves a track as a single CSV; there is no range request for a segment.

TWO DEFECTS FOUND BY E21's GATE, RECORDED HERE BECAUSE BOTH ARE PROPERTIES OF THIS DEPOSIT AND WILL BITE
ANY FUTURE READER OF IT. E21's machinery gate asked only "does BIS rise from the unresponsive block to the
responsive one", expected >= 80 % of cases, and got **1 of 22 (4.5 %)**. It was right to fail and the cause
was not the hypothesis:

  1. **`BIS/BIS` emits a literal `0.0` while the sensor is off, and 0 is inside the index's valid range.**
     171 of 348 successfully-decoded windows carried `meta_bis == 0.0`, and the fraction rises monotonically
     toward the end of the case (11 % at `aneend-1200`, 92 % at `aneend+300`) because the strip comes off
     with the anaesthetic. Read as a measurement it says "isoelectric", i.e. the deepest possible state, so
     the emerging arm scored as *more* suppressed than maintenance and the gate inverted. Demonstrated on
     case 30, whose BIS reads 85.6 at `aneend-300` and then exactly 0.0 for every sample from `aneend-260`
     to the end of the record: a patient mid-emergence cannot be isoelectric. `_monitor_window` now returns
     BIS and SR as NaN whenever `BIS/SQI` reads 0, which is a POSITIVE test for the detached sensor rather
     than a blanket ban on the value 0 -- a genuine BIS of 0 recorded at high signal quality, which deep
     burst suppression does produce, is kept. This is error-catalogue rule 6 in a new dress: the column was
     populated, and that is not the same as valid.
  2. **`aneend` is not the moment of emergence; it lags it.** Measured on the four cases inspected, BIS is
     already >= 68 at `aneend-120` in three of them and 85.6 at `aneend-300` in the fourth, while the deep
     maintenance values sit at 24-46. `aneend` is a chart time entered when the anaesthetic record is
     closed, after the patient is already responding. So offsets of +180/+300 s are not "shortly after
     emergence" -- they are after the monitor has been unplugged, which is precisely why they are also the
     offsets with the most decode errors. **Windows must be labelled by BIS, not by their sign relative to
     `aneend`.**

`VitalDBGridAdapter` below is the consequence: it samples the whole case on a fixed grid and carries the
monitor values with each window so that arms can be defined on the index rather than on a chart time. The
grid costs almost nothing extra, because the expensive operation is fetching a case's waveform track and
that is per case, not per window.
"""
from __future__ import annotations

import csv
import gzip
import io
import urllib.request
from typing import Dict, List, Optional, Sequence

import numpy as np

from bsde.ingestion.base import Adapter, RecordingRef

API = "https://api.vitaldb.net"
EEG_TRACK = "BIS/EEG1_WAV"
SFREQ = 128.0
"""Verified from the data, not the documentation: consecutive samples are 0.0078125 s apart."""

AGENT_TRACKS = {
    "propofol": "Orchestra/PPF20_CE",
    "sevoflurane": "Primus/INSP_SEVO",
    "desflurane": "Primus/INSP_DES",
}
MONITOR_TRACKS = ("BIS/BIS", "BIS/SR", "BIS/SEF", "BIS/EMG", "BIS/SQI")


def _fetch(url: str, timeout: float = 300.0) -> str:
    blob = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "bsde/1.0"}), timeout=timeout).read()
    if blob[:2] == b"\x1f\x8b":                     # the API gzips regardless of Accept-Encoding
        blob = gzip.decompress(blob)
    # utf-8-SIG: the cases endpoint begins with a BOM, which silently renames the first column to
    # "\ufeffcaseid" and makes every lookup of "caseid" a KeyError.
    return blob.decode("utf-8-sig", "replace")


def tracks() -> List[dict]:
    return list(csv.DictReader(io.StringIO(_fetch(f"{API}/trks"))))


def cases() -> Dict[str, dict]:
    return {r["caseid"]: r for r in csv.DictReader(io.StringIO(_fetch(f"{API}/cases")))}


def subject_of(case: dict) -> str:
    """The PATIENT, which is not the case.

    237 of VitalDB's 6,388 cases share a `subjectid` with another case -- one patient has eight. Clustering
    on `caseid` would treat repeat surgeries on the same person as independent and narrow every confidence
    interval accordingly. Falls back to the case id only when `subjectid` is absent, so the failure is a
    conservative one.
    """
    sid = (case.get("subjectid") or "").strip()
    return f"subj{sid}" if sid else f"case{case.get('caseid', '?')}"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def parse_waveform(text: str) -> np.ndarray:
    """A VitalDB waveform CSV, into a dense array.

    The `Time` column is populated only on the first sample of each device packet -- rows 2..n of a packet
    carry an empty time field. So the file is a REGULARLY SAMPLED series with sparse timestamps, and it must
    be read positionally rather than by timestamp. Reading it as (time, value) pairs and dropping the
    unstamped rows would silently discard most of the signal.
    """
    out = []
    for line in text.splitlines()[1:]:
        i = line.find(",")
        if i < 0:
            continue
        v = line[i + 1:]
        out.append(float(v) if v else np.nan)
    return np.asarray(out, float)


class VitalDBAdapter(Adapter):
    """One row per (case, epoch). Epochs are fixed offsets from anaesthesia start, which is the transition.

    `subject` is the PATIENT (`subjectid`), never the case: 237 of 6,388 cases share a patient with another
    case and one patient has eight, so clustering on the case id would treat repeat surgeries as independent
    observations and narrow every interval. Verified against the cases table, not assumed from the docs.
    """

    units = "microvolts"

    def __init__(self, agent: Optional[str] = None, n_cases: int = 40, window_s: float = 30.0,
                 offsets: Sequence[float] = (-1200.0, -600.0, -300.0, -120.0, 60.0, 180.0, 300.0),
                 dataset: str = "vitaldb", require_monitor: bool = True,
                 anchor: str = "aneend") -> None:
        if agent is not None and agent not in AGENT_TRACKS:
            raise ValueError(f"unknown agent {agent!r}; known: {sorted(AGENT_TRACKS)}")
        self.agent = agent
        self.n_cases = n_cases
        self.window_s = window_s
        self.offsets = tuple(offsets)
        self.dataset = dataset
        self.require_monitor = require_monitor
        if anchor not in ("aneend", "anestart"):
            raise ValueError("anchor must be 'aneend' or 'anestart'")
        self.anchor = anchor
        self.name = f"vitaldb:{agent or 'any'}:{anchor}"
        self._cache_tid: Optional[str] = None
        self._cache_val: Optional[np.ndarray] = None
        self._bis_tid: Optional[str] = None
        self._bis_val: Optional[np.ndarray] = None

    def list_recordings(self) -> List[RecordingRef]:
        trk = tracks()
        by_case: Dict[str, Dict[str, str]] = {}
        for r in trk:
            by_case.setdefault(r["caseid"], {})[r["tname"]] = r["tid"]
        info = cases()

        eligible = []
        for cid, tmap in by_case.items():
            if EEG_TRACK not in tmap:
                continue
            if self.require_monitor and "BIS/BIS" not in tmap:
                continue
            if self.agent and AGENT_TRACKS[self.agent] not in tmap:
                continue
            c = info.get(cid)
            if not c or c.get("ane_type") != "General":
                continue
            if not np.isfinite(_f(c.get(self.anchor))):
                continue
            eligible.append(cid)
        eligible.sort(key=lambda x: int(x))          # deterministic, never a random or "best" subset
        chosen = eligible[: self.n_cases]

        refs: List[RecordingRef] = []
        for cid in chosen:
            c, tmap = info[cid], by_case[cid]
            t_ane = _f(c.get(self.anchor))
            present = [a for a, t in AGENT_TRACKS.items() if t in tmap]
            for off in self.offsets:
                t0 = t_ane + off - (self.window_s if off < 0 else 0.0)
                if t0 < 0:
                    continue
                refs.append(RecordingRef(
                    recording_id=f"case{cid}@ane{off:+.0f}", dataset=self.dataset,
                    subject=subject_of(c),
                    load=self._loader(tmap[EEG_TRACK], t0, tmap.get("BIS/BIS")),
                    meta={"caseid": cid, "offset_s": off,
                          "phase": f"pre_{self.anchor}" if off < 0 else f"post_{self.anchor}",
                          "anchor": self.anchor,
                          "agents_present": "|".join(sorted(present)),
                          "requested_agent": self.agent or "",
                          "anestart_s": t_ane, "aneend_s": _f(c.get("aneend")),
                          "opstart_s": _f(c.get("opstart")), "opend_s": _f(c.get("opend")),
                          "age": c.get("age", ""), "sex": c.get("sex", ""), "bmi": c.get("bmi", ""),
                          "asa": c.get("asa", ""), "emop": c.get("emop", ""),
                          "intraop_ppf": c.get("intraop_ppf", ""), "intraop_mdz": c.get("intraop_mdz", ""),
                          "intraop_rocu": c.get("intraop_rocu", ""),
                          "intraop_vecu": c.get("intraop_vecu", ""),
                          "subjectid": c.get("subjectid", ""),
                          "has_bis": str("BIS/BIS" in tmap), "has_sr": str("BIS/SR" in tmap)}))
        return refs

    def _series(self, tid: str) -> np.ndarray:
        if self._cache_tid == tid:
            return self._cache_val
        arr = parse_waveform(_fetch(f"{API}/{tid}"))
        self._cache_tid, self._cache_val = tid, arr
        return arr

    def _bis_window(self, bis_tid: Optional[str], t0: float) -> float:
        """Mean BIS over the same window. A NUMERIC track: its rows carry real timestamps, unlike the
        waveform tracks whose Time column is sparse, so it is read as (time, value) pairs and NOT
        positionally. Using the waveform reader here would misalign it by hours."""
        if not bis_tid:
            return float("nan")
        if self._bis_tid != bis_tid:
            pairs = []
            for line in _fetch(f"{API}/{bis_tid}").splitlines()[1:]:
                a, _, b = line.partition(",")
                if a and b:
                    try:
                        pairs.append((float(a), float(b)))
                    except ValueError:
                        pass
            self._bis_tid = bis_tid
            self._bis_val = np.asarray(pairs, float) if pairs else np.zeros((0, 2))
        arr = self._bis_val
        if arr is None or not arr.size:
            return float("nan")
        m = (arr[:, 0] >= t0) & (arr[:, 0] < t0 + self.window_s)
        v = arr[m, 1]
        v = v[np.isfinite(v)]
        return float(v.mean()) if v.size else float("nan")

    def _loader(self, tid: str, start_seconds: float, bis_tid: Optional[str] = None):
        def load():
            arr = self._series(tid)
            i0 = int(round(start_seconds * SFREQ))
            n = int(round(self.window_s * SFREQ))
            seg = arr[i0:i0 + n]
            if seg.size < n * 0.9:
                raise ValueError(f"window at {start_seconds:.0f}s runs past the record "
                                 f"({seg.size} of {n} samples)")
            if not np.isfinite(seg).any():
                raise ValueError(f"window at {start_seconds:.0f}s is entirely NaN (device disconnected)")
            # Interpolate short NaN runs rather than dropping them: dropping would GLUE TIME TOGETHER, which
            # is error-catalogue rule 27 -- a 1,817 s hole was once closed up invisibly that way.
            ok = np.isfinite(seg)
            if not ok.all():
                if ok.mean() < 0.5:
                    raise ValueError(f"window at {start_seconds:.0f}s is {100 * (1 - ok.mean()):.0f}% NaN")
                seg = np.interp(np.arange(seg.size), np.flatnonzero(ok), seg[ok])
            return seg[None, :], ["BIS_EEG1"], SFREQ, {
                "tid": tid, "start_s": start_seconds, "nan_fraction": float(1 - ok.mean()),
                "bis": self._bis_window(bis_tid, start_seconds)}
        return load


MONITOR_SENTINEL_ZERO = ("BIS/BIS", "BIS/SR")
"""Tracks on which a literal 0.0 may be the monitor's off-state rather than a measurement. Both are indices
whose valid range INCLUDES zero, which is why the sentinel is undetectable from the value alone."""

SQI_TRACK = "BIS/SQI"
"""The arbiter. Measured on cases 30 and 35: `BIS/SQI` reads exactly 0.0 over precisely the spans where
`BIS/BIS` reads exactly 0.0, and `BIS/SR` and `BIS/EMG` stop emitting rows there entirely. So SQI > 0 is a
positive test for "the sensor was attached", and gating on it preserves a genuine BIS of 0 recorded with good
signal quality -- which does occur in deep burst suppression and must not be discarded by a blanket rule."""


class VitalDBGridAdapter(Adapter):
    """One row per (case, grid point), the whole case sampled, every monitor value carried alongside.

    WHY A GRID AND NOT OFFSETS. `VitalDBAdapter` labels a window by its sign relative to `aneend`, and the
    module docstring records why that is wrong: `aneend` is a charted time entered after the patient is
    already responding, and the windows on its positive side are mostly after the sensor came off. A grid
    plus the monitor value lets the ARM be defined by the index -- which is the quantity that actually
    encodes hypnotic depth -- while `aneend` is demoted to a covariate.

    WHY IT IS NEARLY FREE. The expensive operation is fetching a case's EEG track (~9.4 MB, served whole,
    no range requests). That is once per case. Going from 7 windows per case to 40 multiplies the DSP, which
    is milliseconds, and not the transfer, which is minutes. The first version left ~97 % of each fetched
    track unused.

    WHAT IS NOT FIXED BY THIS. Induction is still absent (`anestart` is negative in 91.8 % of cases), the
    montage is still two frontal channels, and Nyquist is still 64 Hz. Those are properties of the deposit.
    """

    units = "microvolts"

    def __init__(self, n_cases: int = 60, window_s: float = 30.0, grid_s: float = 300.0,
                 max_windows: int = 40, tail_s: float = 300.0, dataset: str = "vitaldb_grid",
                 require_monitor: bool = True,
                 monitor_tracks: Sequence[str] = ("BIS/BIS", "BIS/SQI", "BIS/SR", "BIS/EMG"),
                 skip_cases: Sequence[str] = (),
                 case_shard: int = 0, n_case_shards: int = 1) -> None:
        self.n_cases = n_cases
        self.window_s = window_s
        self.grid_s = grid_s
        self.max_windows = max_windows
        self.tail_s = tail_s
        self.dataset = dataset
        self.require_monitor = require_monitor
        self.monitor_tracks = tuple(monitor_tracks)
        self.skip_cases = set(str(c) for c in skip_cases)
        # SHARDING IS BY CASE, NEVER BY WINDOW, and the distinction is the whole point. `shard_of` in the
        # runner hashes the recording id, which would scatter one case's forty windows across every shard
        # and make each shard re-download that case's 9.4 MB waveform track. Splitting the CASE LIST instead
        # keeps the per-case fetch cache intact, so four shards cost four times the bandwidth of one shard,
        # not four times the bandwidth of the whole job.
        if n_case_shards < 1 or not (0 <= case_shard < n_case_shards):
            raise ValueError(f"bad shard {case_shard}/{n_case_shards}")
        self.case_shard = case_shard
        self.n_case_shards = n_case_shards
        self.name = (f"vitaldb-grid:{grid_s:.0f}s"
                     + (f":case-shard{case_shard}of{n_case_shards}" if n_case_shards > 1 else ""))
        self._cache_tid: Optional[str] = None
        self._cache_val: Optional[np.ndarray] = None
        self._num: Dict[str, np.ndarray] = {}
        self._num_case: Optional[str] = None

    def list_recordings(self) -> List[RecordingRef]:
        by_case: Dict[str, Dict[str, str]] = {}
        for r in tracks():
            by_case.setdefault(r["caseid"], {})[r["tname"]] = r["tid"]
        info = cases()

        eligible = []
        for cid, tmap in by_case.items():
            if cid in self.skip_cases or EEG_TRACK not in tmap:
                continue
            if self.require_monitor and not all(t in tmap for t in ("BIS/BIS", SQI_TRACK)):
                continue
            c = info.get(cid)
            if not c or c.get("ane_type") != "General":
                continue
            if not (np.isfinite(_f(c.get("anestart"))) and np.isfinite(_f(c.get("aneend")))):
                continue
            eligible.append(cid)
        eligible.sort(key=lambda x: int(x))          # deterministic; never a random or "best" subset
        # `n_cases` is applied BEFORE sharding, so the union of all shards is exactly the same case set a
        # single unsharded run would produce. Applying it after would give each shard its own `n_cases`
        # cases and quietly multiply the cohort by the shard count.
        chosen = [c for i, c in enumerate(eligible[: self.n_cases])
                  if i % self.n_case_shards == self.case_shard]

        refs: List[RecordingRef] = []
        for cid in chosen:
            c, tmap = info[cid], by_case[cid]
            t0_case = max(0.0, _f(c.get("anestart")))
            t1_case = _f(c.get("aneend")) + self.tail_s
            present = [a for a, t in AGENT_TRACKS.items() if t in tmap]
            mon = {n: tmap[n] for n in self.monitor_tracks if n in tmap}

            n_pts = int(max(0.0, (t1_case - t0_case)) // self.grid_s) + 1
            step = 1 if n_pts <= self.max_windows else int(np.ceil(n_pts / self.max_windows))
            for i in range(0, n_pts, step):
                t = t0_case + i * self.grid_s
                refs.append(RecordingRef(
                    recording_id=f"case{cid}@t{t:.0f}", dataset=self.dataset, subject=subject_of(c),
                    load=self._loader(tmap[EEG_TRACK], t, mon, cid),
                    meta={"caseid": cid, "t_s": t,
                          "rel_anestart_s": t - _f(c.get("anestart")),
                          "rel_aneend_s": t - _f(c.get("aneend")),
                          "anestart_s": _f(c.get("anestart")), "aneend_s": _f(c.get("aneend")),
                          "opstart_s": _f(c.get("opstart")), "opend_s": _f(c.get("opend")),
                          "agents_present": "|".join(sorted(present)),
                          "age": c.get("age", ""), "sex": c.get("sex", ""), "asa": c.get("asa", ""),
                          "bmi": c.get("bmi", ""), "emop": c.get("emop", ""),
                          "intraop_ppf": c.get("intraop_ppf", ""),
                          "intraop_mdz": c.get("intraop_mdz", ""),
                          "intraop_rocu": c.get("intraop_rocu", ""),
                          "intraop_vecu": c.get("intraop_vecu", ""),
                          "subjectid": c.get("subjectid", "")}))
        return refs

    def _series(self, tid: str) -> np.ndarray:
        if self._cache_tid == tid:
            return self._cache_val
        arr = parse_waveform(_fetch(f"{API}/{tid}"))
        self._cache_tid, self._cache_val = tid, arr
        return arr

    def _numeric(self, cid: str, name: str, tid: str) -> np.ndarray:
        """A numeric monitor track as (time, value) pairs, cached for the duration of ONE case.

        Read by timestamp, unlike the waveform tracks whose `Time` column is sparse and must be read
        positionally. The cache is dropped when the case changes so memory stays bounded by one case's
        monitor tracks rather than by the whole run.
        """
        if self._num_case != cid:
            self._num, self._num_case = {}, cid
        if name in self._num:
            return self._num[name]
        pairs = []
        for line in _fetch(f"{API}/{tid}").splitlines()[1:]:
            a, _, b = line.partition(",")
            if a and b:
                try:
                    pairs.append((float(a), float(b)))
                except ValueError:
                    pass
        arr = np.asarray(pairs, float) if pairs else np.zeros((0, 2))
        self._num[name] = arr
        return arr

    def _monitor_window(self, cid: str, mon: Dict[str, str], t0: float) -> Dict[str, float]:
        """Mean of each monitor track over the analysis window, with the off-state removed.

        `BIS/SQI == 0` is the positive test for a detached sensor (see SQI_TRACK). When it fires, EVERY
        monitor value is returned as NaN -- not merely the ones in MONITOR_SENTINEL_ZERO. Those two are
        listed because their sentinel is undetectable from the value alone (0 is inside their valid range and
        reads as "maximally suppressed", which is the exact opposite of the truth and is why E21's gate
        inverted). But a detached strip invalidates the rest as well: `BIS/EMG` read 57.6 at a grid point
        whose SQI was 0 and whose EEG had a standard deviation of 536 microvolts, which is dangling leads,
        not muscle. The narrower rule would have left that in as a real muscle measurement.

        `sensor_off` is returned rather than the row being dropped, so that downstream exclusions are counted
        instead of silently applied (rule 14).
        """
        out: Dict[str, float] = {}
        for name, tid in mon.items():
            arr = self._numeric(cid, name, tid)
            if not arr.size:
                out[name] = float("nan")
                continue
            v = arr[(arr[:, 0] >= t0) & (arr[:, 0] < t0 + self.window_s), 1]
            v = v[np.isfinite(v)]
            out[name] = float(v.mean()) if v.size else float("nan")
        sqi = out.get(SQI_TRACK, float("nan"))
        sensor_off = bool(np.isfinite(sqi) and sqi <= 0.0)
        if sensor_off:
            out = {name: float("nan") for name in out}
        elif not np.isfinite(sqi):
            # No SQI track at all (possible only with require_monitor=False), so the off-state cannot be
            # tested for. Fall back to distrusting an exact 0.0 on the two tracks where it is ambiguous.
            # This loses the rare genuine isoelectric window; without SQI there is no way to keep it.
            for name in MONITOR_SENTINEL_ZERO:
                if name in out and out[name] == 0.0:
                    out[name] = float("nan")
        short = {name.split("/")[-1].lower(): val for name, val in out.items()}
        short["sensor_off"] = sensor_off
        return short

    def _loader(self, tid: str, start_seconds: float, mon: Dict[str, str], cid: str):
        def load():
            arr = self._series(tid)
            i0 = int(round(start_seconds * SFREQ))
            n = int(round(self.window_s * SFREQ))
            seg = arr[i0:i0 + n]
            if seg.size < n * 0.9:
                raise ValueError(f"window at {start_seconds:.0f}s runs past the record "
                                 f"({seg.size} of {n} samples)")
            if not np.isfinite(seg).any():
                raise ValueError(f"window at {start_seconds:.0f}s is entirely NaN (device disconnected)")
            ok = np.isfinite(seg)
            if not ok.all():
                # Interpolate short NaN runs; dropping them would GLUE TIME TOGETHER (rule 27).
                if ok.mean() < 0.5:
                    raise ValueError(f"window at {start_seconds:.0f}s is {100 * (1 - ok.mean()):.0f}% NaN")
                seg = np.interp(np.arange(seg.size), np.flatnonzero(ok), seg[ok])
            meta = {"tid": tid, "start_s": start_seconds, "nan_fraction": float(1 - ok.mean())}
            meta.update(self._monitor_window(cid, mon, start_seconds))
            return seg[None, :], ["BIS_EEG1"], SFREQ, meta
        return load
