"""Healthy Brain Network (HBN) resting-state adapter — EEGLAB `.set` over plain HTTPS, anonymously.

WHAT THIS DEPOSIT IS, AND WHAT IT IS NOT. HBN is the Child Mind Institute's paediatric/adolescent cohort
(`s3://fcp-indi/data/Projects/HBN/BIDS_EEG/cmi_bids_R*`), ~3,000 subjects aged roughly 5-21, community
recruited and enriched for psychopathology. It contains **no anaesthetic, no disorders-of-consciousness
patients, no sleep staging and no command-following**, so it serves none of the three discovery challenges.
It is ingested for exactly one reason: it is the largest healthy population with a documented `age` column
that this project can reach, and **nothing here has ever been tested against a developmental gradient.**

THREE PROPERTIES OF THE RAW FILES THAT WOULD SILENTLY CORRUPT A RESULT, ALL MEASURED BEFORE THIS WAS WRITTEN.

1. **THE UNITS ARE NOT MICROVOLTS.** After removing a per-channel DC offset the AC amplitude is ~724 in file
   units, where plausible EEG is 5-50 uV. The true scale factor is not recorded in the file and this module
   DOES NOT INVENT ONE. The consequence is a scope limit that must travel with every number computed here:
   **only SCALE-INVARIANT features are valid on this deposit.** Exponents (a slope; scale moves the
   intercept), band-power RATIOS, spectral entropy, spectral edge, Lempel-Ziv (median-threshold
   binarisation), wPLI (phase), multiscale entropy (r = 0.15 x SD), Tort PAC, participation ratio (an
   eigenvalue ratio) and kurtosis are all scale-invariant. `critical_slowing`'s `envelope_variance` is NOT
   and must not be compared across deposits from here.

2. **THE DC OFFSETS ARE ENORMOUS** — measured between -148,179 and +60,114 across channels in one recording.
   `welch_psd` removes each segment's mean so the spectral path is safe, but the time-domain features are
   not, so the per-channel mean is removed here, once, for everything.

3. **THE REFERENCE CHANNEL IS ALL ZEROS.** These are EGI 129-channel recordings referenced to Cz, and Cz is
   present in the file as a flat trace (measured SD exactly 0.0). A flat channel is not data; it is dropped,
   and the drop is counted into `meta` rather than being silent.

MONTAGE. Channels are EGI names (`E1`...`E128`, `Cz`) with **no 10-20 labels**, so `uce_v1` -- which selects
frontal and posterior regions by 10-20 name -- correctly returns NaN here. That is the declared behaviour
(§9.10), not a failure to handle the montage.

CONDITIONS. The resting-state run alternates instructed eyes-open and eyes-closed blocks, marked in the
recording's own event structure (`instructed_toOpenEyes` / `instructed_toCloseEyes`). Both are emitted as
separate rows so the deposit supplies a WITHIN-SUBJECT, drug-free state contrast alongside the between-subject
age gradient.

COST. One `.set` is 30-105 MB and measured at ~37 MB/s. A one-entry blob cache means the two conditions for a
subject cost one download rather than two, which halves the transfer -- correct only because
`list_recordings` returns the two rows for a subject consecutively, and that ordering is asserted rather than
assumed.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from typing import Dict, List, Optional

import numpy as np

from bsde.ingestion.base import Adapter, RecordingRef

BUCKET = "https://fcp-indi.s3.amazonaws.com"
ROOT = "data/Projects/HBN/BIDS_EEG"
TASK = "RestingState"
OPEN_EVENT, CLOSE_EVENT = "instructed_toOpenEyes", "instructed_toCloseEyes"
CONDITIONS = ("closed", "open")
_UA = {"User-Agent": "bsde/1.0 (research; anonymous S3 read)"}


def _get(url: str, timeout: float = 300.0) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=timeout).read()


def participants(release: str) -> List[Dict[str, str]]:
    """Rows of `participants.tsv`, which is where `age` comes from. Fetched, never assumed."""
    text = _get(f"{BUCKET}/{ROOT}/cmi_bids_{release}/participants.tsv", timeout=120).decode("utf-8")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def blocks_from_events(events: np.ndarray, sfreq: float) -> Dict[str, List[tuple]]:
    """Eyes-open and eyes-closed intervals from the EEGLAB event struct.

    A block runs from its instruction to the NEXT instruction of either kind; the final block is closed at
    the recording end by the caller, which is why this returns open-ended last intervals as (start, None).
    """
    marks = []
    for e in np.atleast_1d(events):
        t = str(getattr(e, "type", ""))
        if t in (OPEN_EVENT, CLOSE_EVENT):
            lat = float(np.squeeze(getattr(e, "latency", np.nan)))
            if np.isfinite(lat):
                marks.append((lat / sfreq, "open" if t == OPEN_EVENT else "closed"))
    marks.sort()
    out: Dict[str, List[tuple]] = {"open": [], "closed": []}
    for i, (t0, kind) in enumerate(marks):
        t1 = marks[i + 1][0] if i + 1 < len(marks) else None
        out[kind].append((t0, t1))
    return out


class HBNRestingAdapter(Adapter):
    """One row per (subject, eyes-open/eyes-closed). `subject` is the BIDS `sub-NDAR...` id."""

    units = "uncalibrated"
    """DELIBERATELY NOT "microvolts". The scale factor is unknown and is not invented; see the module
    docstring. Any consumer that needs absolute amplitude must refuse this deposit rather than guess."""

    def __init__(self, release: str = "R1", window_s: float = 20.0, limit: Optional[int] = None,
                 conditions: tuple = CONDITIONS, dataset: str = "hbn_resting") -> None:
        self.release = release
        self.window_s = window_s
        self.limit = limit
        self.conditions = conditions
        self.dataset = dataset
        self.name = f"hbn:{release}"
        self._cache_key: Optional[str] = None
        self._cache_val = None

    # --- listing -------------------------------------------------------------------------------
    def list_recordings(self) -> List[RecordingRef]:
        rows = [r for r in participants(self.release)
                if (r.get("RestingState") or "").strip() == "available"]
        rows.sort(key=lambda r: r["participant_id"])
        if self.limit:
            rows = rows[:self.limit]
        refs = []
        for r in rows:
            sub = r["participant_id"]
            for cond in self.conditions:
                refs.append(RecordingRef(
                    recording_id=f"{sub}@{cond}", dataset=self.dataset, subject=sub,
                    load=self._make_loader(sub, cond),
                    meta={"age": r.get("age", ""), "sex": r.get("sex", ""),
                          "condition": cond, "release": r.get("release_number", self.release),
                          "commercial_use": r.get("commercial_use", ""),
                          "p_factor": r.get("p_factor", ""), "ehq_total": r.get("ehq_total", "")}))
        # The one-entry blob cache is only correct if a subject's rows are CONSECUTIVE. Assert it rather
        # than rely on the loop above staying this way.
        subs = [x.subject for x in refs]
        assert all(subs[i] == subs[i + 1] for i in range(0, len(subs) - 1, len(self.conditions))) \
            or len(self.conditions) == 1, "subject rows must be consecutive for the blob cache to be valid"
        return refs

    # --- loading -------------------------------------------------------------------------------
    def _blob(self, sub: str) -> bytes:
        if self._cache_key == sub:
            return self._cache_val
        url = f"{BUCKET}/{ROOT}/cmi_bids_{self.release}/{sub}/eeg/{sub}_task-{TASK}_eeg.set"
        blob = _get(url)
        self._cache_key, self._cache_val = sub, blob
        return blob

    def _make_loader(self, sub: str, cond: str):
        def load():
            from scipy.io import loadmat
            m = loadmat(io.BytesIO(self._blob(sub)), squeeze_me=True, struct_as_record=False)
            sfreq = float(np.squeeze(m["srate"]))
            data = np.asarray(m["data"], float)
            names = [str(c.labels) for c in np.atleast_1d(m["chanlocs"])]
            total = data.shape[1] / sfreq

            blocks = blocks_from_events(m["event"], sfreq)
            cand = [(t0, (t1 if t1 is not None else total)) for t0, t1 in blocks.get(cond, [])]
            cand = [(a, b) for a, b in cand if b - a >= self.window_s]
            if not cand:
                raise ValueError(f"no {cond}-eyes block of at least {self.window_s:g}s")
            t0, t1 = max(cand, key=lambda ab: ab[1] - ab[0])          # the longest such block
            mid = (t0 + t1) / 2.0
            s0 = int(round(max(t0, mid - self.window_s / 2.0) * sfreq))
            seg = data[:, s0:s0 + int(round(self.window_s * sfreq))]

            # Per-channel DC removal, and flat channels dropped rather than left to poison a feature.
            seg = seg - seg.mean(axis=1, keepdims=True)
            keep = seg.std(axis=1) > 0
            n_flat = int((~keep).sum())
            seg, names = seg[keep], [n for n, k in zip(names, keep) if k]

            return seg, names, sfreq, {"condition": cond, "block_start_s": t0, "block_end_s": t1,
                                       "n_flat_channels_dropped": n_flat, "units": self.units}
        return load
