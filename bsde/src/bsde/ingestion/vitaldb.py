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
