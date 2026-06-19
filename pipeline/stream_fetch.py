"""stream_fetch.py -- per-recording streaming / batch-and-delete (Sec 0, 4).

The cardinal rule: never hold more than one shard of raw signal on disk. Two
access modes are supported, selected by `data.access_mode`:

  * "stream"           -- yield a handle that reads the recording lazily; the
                          caller consumes it and nothing lands on disk.
  * "batch_and_delete" -- download one shard to scratch, yield its members,
                          then delete the shard before fetching the next.

The actual BDSP transport is an adapter boundary (`_BDSPClient`). It is left as
a thin, well-documented seam: wiring it to the Brain Data Science Platform's
credentialed API is the only site-specific I/O in the whole pipeline.
"""
from __future__ import annotations

import contextlib
import os
import shutil
from dataclasses import dataclass
from typing import Any, Iterable, Iterator

from guards.heldout_guard import HeldoutGuard


@dataclass(frozen=True)
class RecordingRef:
    """Identity + acquisition metadata for one EEG recording.

    Phase-1 safe: carries EEG-acquisition metadata only -- no outcome, no ICD,
    no medications, no report text (Sec 0, 13).
    """
    recording_id: str
    patient_id: str
    hospital: str
    device: str | None = None
    sampling_rate: float | None = None
    montage: str | None = None
    n_channels: int | None = None
    duration_s: float | None = None
    care_setting: str | None = None
    age: float | None = None
    sex: str | None = None
    uri: str | None = None


class _BDSPClient:
    """Adapter boundary to the Brain Data Science Platform.

    Replace the method bodies with credentialed BDSP calls. They are isolated
    here so the rest of the pipeline never imports transport details.
    """

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg

    def list_recordings(self, hospital: str) -> Iterable[RecordingRef]:  # pragma: no cover - I/O seam
        raise NotImplementedError(
            "Wire _BDSPClient.list_recordings to the credentialed BDSP catalog. "
            "It must return RecordingRef objects with acquisition metadata only."
        )

    def open_stream(self, ref: RecordingRef):  # pragma: no cover - I/O seam
        raise NotImplementedError(
            "Wire _BDSPClient.open_stream to return a lazy raw reader "
            "(e.g. an mne.io.Raw with preload=False)."
        )

    def download_shard(self, refs: list[RecordingRef], dest: str) -> str:  # pragma: no cover - I/O seam
        raise NotImplementedError(
            "Wire _BDSPClient.download_shard for batch_and_delete mode."
        )


def iter_qualifying_recordings(
    cfg: dict[str, Any], guard: HeldoutGuard, client: _BDSPClient | None = None
) -> Iterator[RecordingRef]:
    """Yield eligible recordings from the *discovery* sites only (Phase 1).

    Every site label is routed through the firewall guard, so a held-out
    recording can never enter the Phase-1 stream even if the catalog returns it.
    Applies the one-recording-per-patient and age eligibility rules (Sec 5).
    """
    client = client or _BDSPClient(cfg)
    min_age = cfg.get("cohort", {}).get("primary_min_age_years", 18)
    seen_patients: set[str] = set()

    sites = list(cfg.get("sites", {}).get("discovery") or [])
    for hospital in sites:
        guard.check_site_access(hospital, context="stream_fetch")
        for ref in client.list_recordings(hospital):
            guard.check_site_access(ref.hospital, context="stream_fetch:ref")
            if ref.age is not None and ref.age < min_age:
                continue
            if ref.patient_id in seen_patients:  # earliest-qualifying upstream
                continue
            seen_patients.add(ref.patient_id)
            yield ref


@contextlib.contextmanager
def open_recording(cfg: dict[str, Any], ref: RecordingRef, client: _BDSPClient):
    """Context manager that yields a lazy raw reader and guarantees cleanup.

    In batch_and_delete mode the shard is removed on exit; in stream mode the
    reader is simply closed. Either way nothing raw survives the `with` block --
    the disk-sparing contract (Sec 0).
    """
    mode = cfg.get("data", {}).get("access_mode", "stream")
    scratch = cfg.get("data", {}).get("scratch_dir", "/tmp/heedb_scratch")
    raw = None
    shard_dir = None
    try:
        if mode == "batch_and_delete":
            os.makedirs(scratch, exist_ok=True)
            shard_dir = client.download_shard([ref], scratch)
        raw = client.open_stream(ref)
        yield raw
    finally:
        if raw is not None and hasattr(raw, "close"):
            with contextlib.suppress(Exception):
                raw.close()
        if shard_dir and os.path.isdir(shard_dir):
            shutil.rmtree(shard_dir, ignore_errors=True)  # delete before next
