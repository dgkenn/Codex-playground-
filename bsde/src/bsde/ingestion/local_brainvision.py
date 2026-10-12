"""BrainVision adapter for a local directory. The simplest adapter, and the reference for the others.

`recording_id` is the .vhdr basename, which is stable across runs and machines — never an enumeration
index, which would silently reshuffle shards and corrupt a resumed run whenever the directory listing
changes.

MNE returns BrainVision data in VOLTS. The conversion to microvolts is declared here rather than assumed,
and it happens in exactly one place (`to_microvolts`).
"""
from __future__ import annotations

import glob
import os
from typing import List

from bsde.ingestion.base import Adapter, RecordingRef, to_microvolts


class BrainVisionAdapter(Adapter):
    units = "volts"

    def __init__(self, root: str, dataset: str = "brainvision", subject_from_name=None) -> None:
        self.root = root
        self.dataset = dataset
        self.name = f"brainvision:{dataset}"
        # A dataset with several sessions per person MUST pass this, or subject-level splitting silently
        # degrades to recording-level splitting and every interval is too narrow.
        self._subject_from_name = subject_from_name

    def list_recordings(self) -> List[RecordingRef]:
        out = []
        for vhdr in sorted(glob.glob(os.path.join(self.root, "*.vhdr"))):   # sorted == deterministic order
            rid = os.path.basename(vhdr)[:-5]
            out.append(RecordingRef(
                recording_id=rid, dataset=self.dataset,
                subject=(self._subject_from_name(rid) if self._subject_from_name else rid),
                load=self._make_loader(vhdr),
                meta={"path": vhdr, "format": "brainvision"}))
        return out

    def _make_loader(self, vhdr: str):
        def load():
            import mne
            raw = mne.io.read_raw_brainvision(vhdr, preload=True, verbose="ERROR")
            data = to_microvolts(raw.get_data(), self.units)
            return data, list(raw.ch_names), float(raw.info["sfreq"]), {"source_units": self.units}
        return load
