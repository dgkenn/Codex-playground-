"""PhysioNet EEG Motor Movement/Imagery Database — 109 subjects, open, and it makes Challenge B testable.

WHY A BCI DATASET IS THE RIGHT ALTERNATIVE FOR A DISORDERS-OF-CONSCIOUSNESS CHALLENGE. Brief 03's Challenge
B asks for **spontaneous EEG features associated with command-following**. In a DoC patient, command
following is a behavioural or covert response to an instruction, and the deposits that label it are
access-controlled: Bath is requested and not granted, and the one open DoC deposit this project holds
(figshare 23552964, 98 recordings) ships **no label file of any kind** — 298 files, every one BrainVision,
no group assignment and no CRS-R. It cannot answer the question or any weaker version of it.

The BCI literature has been asking a structurally identical question for fifteen years under a different
name. **Motor imagery is command-following that produces no movement** — the subject is instructed, complies
covertly, and the only evidence is the EEG. And 15-30 % of healthy people cannot do it well enough to
operate a BCI, a phenomenon named "BCI illiteracy". So "which spontaneous EEG features predict who will
show a detectable response to instruction" is a question with a real answer, a real spread, and published
prior art:

    Blankertz B, Sannelli C, Halder S, Hammer EM, Kubler A, Muller KR, Curio G, Dickhaus T.
    "Neurophysiological predictor of SMR-based BCI performance." NeuroImage 2010 Jul 15; PMID 20303409.
    Hammer EM et al. "Psychological predictors of SMR-BCI performance." Biol Psychol 2012; PMID 21964375.

Both verified through NCBI E-utilities, not WebFetch (rule 25, and rule 39 for records generally).

**Blankertz is a BASELINE, not a citation.** It reports that a measure computed from RESTING EEG predicts
subsequent BCI performance. Any candidate here has to be compared against that, exactly as Challenge C's
candidates were compared against BIS — a marker presented alone, without the incumbent beside it, is not a
result.

WHAT THIS SUBSTITUTION COSTS, AND IT IS NOT SMALL. **Healthy BCI performance is not DoC command-following.**
A healthy subject who cannot drive a BCI is not unconscious; they are inattentive, untrained, or have a low
sensorimotor rhythm. The failure modes differ, the populations differ, and a feature that predicts one may
be silent for the other. What transfers is the FORM of the claim — spontaneous signal predicting a
covert instructed response — and the machinery for testing it, including the within-subject null layer
§9.22 recorded as missing for Challenge B. **No result from this deposit may be worded as a DoC result.**

THE DEPOSIT, verified against the server rather than the paper:
    109 subjects, 14 runs each, 1,526 records, 64 channels, 160 Hz, EDF+ with a 65th annotation channel.
    R01  baseline, eyes open    } spontaneous: no task, no instruction
    R02  baseline, eyes closed  }
    R03 R07 R11  executed movement, left vs right fist
    R04 R08 R12  IMAGINED movement, left vs right fist        <- command-following without movement
    R05 R09 R13  executed, both fists vs both feet
    R06 R10 R14  imagined, both fists vs both feet

ANNOTATIONS. Each `.edf.event` is a WFDB binary annotation file whose label sequence is readable as embedded
strings (`T0 duration: 4.2`, `T1 duration: 4.1`, ...). Onsets are reconstructed by cumulative duration, and
**that reconstruction is verified rather than trusted**: `events()` refuses to return a sequence whose total
duration differs from the EDF header's own record count by more than `DURATION_TOLERANCE_S`. On S001R04 the
reconstruction totals 124.5 s against a 125.0 s record — the final rest period is truncated — which is
inside tolerance and is the expected shape.
"""
from __future__ import annotations

import re
import urllib.request
from typing import Dict, List, Optional, Sequence, Tuple

from bsde.ingestion.base import Adapter, RecordingRef
from bsde.ingestion.http_edf import read_edf_window_http

BASE = "https://physionet.org/files/eegmmidb/1.0.0"
SFREQ = 160.0
N_SUBJECTS = 109
EEG_ONLY = r"^(?!EDF Annotations)"

REST_RUNS = ("R01", "R02")
IMAGERY_LR_RUNS = ("R04", "R08", "R12")
EXECUTED_LR_RUNS = ("R03", "R07", "R11")

DURATION_TOLERANCE_S = 2.0
"""How far the reconstructed annotation timeline may sit from the EDF header's own duration before the
sequence is refused. A cumulative reconstruction drifts if any duration string is missed, and a silently
drifted timeline would epoch every trial at the wrong moment while still producing a full table."""

EXCLUDED_SUBJECTS = frozenset({"S088", "S089", "S092", "S100"})
"""Documented by PhysioNet as having a damaged or non-standard record. Named rather than discovered, so the
exclusion is a property of the deposit and not of anything measured here (rule 14)."""


def _get(url: str, timeout: float = 60.0) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "bsde/1.0"}), timeout=timeout).read()


def subjects() -> List[str]:
    return [f"S{i:03d}" for i in range(1, N_SUBJECTS + 1) if f"S{i:03d}" not in EXCLUDED_SUBJECTS]


def record_duration_s(sub: str, run: str) -> float:
    """From the EDF header alone: 8 bytes of record count times 8 bytes of record duration."""
    h = _get(f"{BASE}/{sub}/{sub}{run}.edf", timeout=60)[:256].decode("latin-1")
    return int(h[236:244]) * float(h[244:252])


def events(sub: str, run: str, verify: bool = True) -> List[Tuple[float, str, float]]:
    """`[(onset_s, label, duration_s), ...]` for one run, reconstructed and then checked.

    Raises if the reconstructed timeline disagrees with the EDF header by more than
    DURATION_TOLERANCE_S. That check is the point: the onsets are a cumulative sum, so a single missed
    duration shifts every subsequent trial and produces a table that looks complete and is wrong.
    """
    txt = _get(f"{BASE}/{sub}/{sub}{run}.edf.event", timeout=60).decode("latin-1")
    pairs = re.findall(r"(T[012]) duration: ([0-9.]+)", txt)
    if not pairs:
        raise ValueError(f"{sub}{run}: no annotations parsed")
    out, t = [], 0.0
    for label, dur in pairs:
        d = float(dur)
        out.append((t, label, d))
        t += d
    if verify:
        rec = record_duration_s(sub, run)
        if abs(t - rec) > DURATION_TOLERANCE_S:
            raise ValueError(f"{sub}{run}: reconstructed timeline {t:.1f}s vs record {rec:.1f}s "
                             f"(tolerance {DURATION_TOLERANCE_S}s) — refusing to epoch on a drifted axis")
    return out


def read_window(sub: str, run: str, start_s: float, window_s: float):
    return read_edf_window_http(f"{BASE}/{sub}/{sub}{run}.edf", window_s=window_s,
                                start_seconds=start_s, channel_regex=EEG_ONLY)


class EEGMMIDBRestAdapter(Adapter):
    """One row per (subject, baseline run). SPONTANEOUS EEG only — no task run is ever read here.

    That separation is deliberate and load-bearing: the feature table this produces must contain nothing
    from the runs that define the label, or the association it is used to test is circular. The label is
    built by a separate script from the imagery runs, and the two are joined on `subject`.
    """

    units = "microvolts"

    def __init__(self, window_s: float = 55.0, runs: Sequence[str] = REST_RUNS,
                 dataset: str = "eegmmidb_rest", subs: Optional[Sequence[str]] = None) -> None:
        self.window_s = window_s
        self.runs = tuple(runs)
        self.dataset = dataset
        self.subs = list(subs) if subs is not None else subjects()
        self.name = "physionet:eegmmidb:rest"

    def list_recordings(self) -> List[RecordingRef]:
        refs: List[RecordingRef] = []
        for sub in self.subs:
            for run in self.runs:
                refs.append(RecordingRef(
                    recording_id=f"{sub}@{run}", dataset=self.dataset, subject=sub,
                    load=self._loader(sub, run),
                    meta={"run": run, "condition": "eyes_open" if run == "R01" else "eyes_closed",
                          "sfreq": SFREQ}))
        return refs

    def _loader(self, sub: str, run: str):
        def load():
            # Start at 2 s: the first seconds of these baseline runs carry the settling transient that
            # every montage shows when recording begins, and it is broadband.
            return read_window(sub, run, 2.0, self.window_s)
        return load
