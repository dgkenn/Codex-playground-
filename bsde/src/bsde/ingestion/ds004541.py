"""OpenNeuro ds004541 — human general anaesthesia with marked loss and recovery of consciousness.

WHY THIS DEPOSIT MATTERS MORE THAN ITS SIZE SUGGESTS. §9.16 is the largest correction in this project: the
Chennu cohort never reaches unconsciousness, so every result built on it measures mild-to-moderate sedation
in responsive volunteers. **ds004541 carries explicit `loc` and `roc` events** — loss and recovery of
consciousness, marked per subject against a graded stimulation ladder (`verbal/soft`, `verbal/strong`,
`motor`, `tetanic/1`, `tetanic/2`). It is the only reachable public EEG deposit found, in an exhaustive
enumeration of all 447 OpenNeuro EEG datasets, where consciousness is documented as actually lost.

n = 8 patients. That is small and it is the whole cohort; no claim from it will be strong.

WHAT IT ALSO SUPPLIES THAT NOTHING ELSE HERE DOES.
  * A **within-subject transition with a time axis**, which is what verifier layer 5's unbuilt half —
    temporal PRECEDENCE — requires. Windows are emitted at fixed offsets relative to `loc` so that "did the
    measure move before the clinician marked it" is answerable rather than assertable.
  * A proper **extended 10-20 montage** (Fp1 ... Cb2), so `uce_v1`, which selects frontal and posterior
    regions by 10-20 name and returns NaN on HBN's EGI caps, is computable here.
  * Dedicated **EMG and EKG channels**. Every muscle-confound argument in this project so far has rested on
    spectral proxies computed from EEG channels (§9.15 found two of them disagreeing in sign); this deposit
    has an actual muscle recording. It is NOT used as a feature here, but it is available and is far better
    evidence than a proxy.
  * **CC0** — the cleanest licence of any deposit this project touches.

THE DRUG IS NOT RECORDED, AND THAT LIMIT IS LOAD-BEARING. Neither `dataset_description.json`, the README
(boilerplate, "in preparation") nor `participants.json` names an anaesthetic agent. **This deposit therefore
CANNOT serve discovery Challenge A**, which requires two identified and different drugs, and it must not be
assumed to be propofol because the other two anaesthesia deposits here are. Recorded as unknown until the
authors or a publication say otherwise.

CHANNEL SELECTION. `EDF Annotations` is sampled at 30 Hz against the signals' 1000 Hz, and
`decode_edf_window` refuses to build one array from mixed rates — the guard added after that function was
found silently truncating every channel to the shortest. EOG, EKG, EMG, `Trigger` and the mastoids are
excluded from the analysis array by the same regex, deliberately and by name.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from typing import Dict, List, Optional

from bsde.ingestion.base import Adapter, RecordingRef
from bsde.ingestion.http_edf import read_edf_window_http

BUCKET = "https://s3.amazonaws.com/openneuro.org"
ACCESSION = "ds004541"
TASK = "anesthesia"

EEG_ONLY = r"^(?!VEOG|HEOG|EKG|EMG|Trigger|EDF |M1|M2)"
"""Negative lookahead rather than a positive list: the montage is a full extended 10-20 and enumerating 62
wanted names would break silently the first time a subject's cap differed, whereas the six unwanted ones are
stable and few."""

DEFAULT_OFFSETS = (-300.0, -240.0, -180.0, -120.0, -60.0, -30.0,
                   30.0, 60.0, 120.0, 180.0, 240.0, 300.0)
"""Seconds relative to `loc`. Symmetric on purpose: an asymmetric grid would make any before/after
difference partly a difference in how much time each side samples."""


def _get(url: str, timeout: float = 60.0) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "bsde/1.0"}), timeout=timeout).read()


def participants() -> List[str]:
    text = _get(f"{BUCKET}/{ACCESSION}/participants.tsv", timeout=60).decode("utf-8-sig", "replace")
    return [r["participant_id"] for r in csv.DictReader(io.StringIO(text), delimiter="\t")
            if r.get("participant_id", "").startswith("sub-")]


def events(sub: str, ses: str = "ses-01") -> Dict[str, float]:
    """`trial_type` -> onset seconds. Later duplicates win, which matters for none of the markers used."""
    url = f"{BUCKET}/{ACCESSION}/{sub}/{ses}/eeg/{sub}_{ses}_task-{TASK}_events.tsv"
    text = _get(url, timeout=60).decode("utf-8-sig", "replace")
    out: Dict[str, float] = {}
    for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
        try:
            out[(r.get("trial_type") or "").strip()] = float(r["onset"])
        except (TypeError, ValueError, KeyError):
            continue
    return out


class DS004541Adapter(Adapter):
    """One row per (subject, epoch). Epochs are `baseline` plus fixed offsets around `loc` and `roc`.

    `recording_id` is `sub-XX@<epoch>`; `subject` is `sub-XX`, so every downstream interval is clustered on
    the patient rather than on the window — 8 patients contributing ~14 windows each would otherwise look
    like 112 independent observations, which E14 measured as an ICC of 0.9+ on comparable data.
    """

    units = "microvolts"

    def __init__(self, window_s: float = 30.0, offsets: tuple = DEFAULT_OFFSETS,
                 dataset: str = "ds004541", include_roc: bool = True) -> None:
        self.window_s = window_s
        self.offsets = offsets
        self.dataset = dataset
        self.include_roc = include_roc
        self.name = f"openneuro:{ACCESSION}"

    def list_recordings(self) -> List[RecordingRef]:
        refs: List[RecordingRef] = []
        for sub in participants():
            try:
                ev = events(sub)
            except Exception:
                continue
            loc, roc = ev.get("loc"), ev.get("roc")
            t_start, t_end = ev.get("start"), ev.get("end")
            url = f"{BUCKET}/{ACCESSION}/{sub}/ses-01/eeg/{sub}_ses-01_task-{TASK}_eeg.edf"

            plan: List[tuple] = []
            if ev.get("baseline") is not None:
                plan.append(("baseline", ev["baseline"], 0.0, "baseline"))
            if loc is not None:
                for off in self.offsets:
                    t0 = loc + off - (self.window_s if off < 0 else 0.0)
                    if t0 < 0:
                        continue
                    plan.append((f"loc{off:+.0f}", t0, off, "pre_loc" if off < 0 else "post_loc"))
            if roc is not None and self.include_roc:
                for off in (-60.0, 60.0):
                    t0 = roc + off - (self.window_s if off < 0 else 0.0)
                    if t0 < 0:
                        continue
                    plan.append((f"roc{off:+.0f}", t0, off, "pre_roc" if off < 0 else "post_roc"))

            for label, t0, off, phase in plan:
                refs.append(RecordingRef(
                    recording_id=f"{sub}@{label}", dataset=self.dataset, subject=sub,
                    load=self._loader(url, t0),
                    meta={"epoch": label, "phase": phase, "offset_s": off,
                          "loc_s": loc, "roc_s": roc, "start_s": t_start, "end_s": t_end,
                          "window_start_s": t0, "url": url}))
        return refs

    def _loader(self, url: str, start_seconds: float):
        def load():
            return read_edf_window_http(url, window_s=self.window_s,
                                        start_seconds=start_seconds, channel_regex=EEG_ONLY)
        return load
