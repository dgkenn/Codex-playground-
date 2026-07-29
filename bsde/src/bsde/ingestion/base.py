"""The adapter protocol: how a dataset is presented to the engine without ever landing on disk.

THE INVARIANT THIS FILE EXISTS TO ENFORCE. Raw EEG is never written to local storage. An adapter yields
`RecordingRef` handles; calling `.load()` returns arrays in memory, they are reduced to a feature row, and
they go out of scope. Nothing between the remote store and the feature row is persisted.

Three reasons this is the design rather than download-then-process:

  1. **Scale.** I-CARE alone is 1.5 TB. The sandbox's writable disk is a fixed per-session allowance, and
     `df` misreports it. Downloading is not merely slower, it does not fit.
  2. **Governance.** Credentialed patient data that is never written cannot be accidentally committed,
     cached into an image, or left in a container snapshot. The strongest guarantee about a file is that it
     was never created.
  3. **Ephemerality.** This container's `/tmp` and git worktree roll back on restart. Hours of extraction
     have been lost that way. A resumable stream that keeps only the FEATURE table is cheap to restart; a
     download is not.

WHAT AN ADAPTER MUST GUARANTEE, and what the runner's tests check:

  * `list_recordings()` returns a **deterministic, stable order** — sharding depends on it.
  * `recording_id` is **stable across runs and across machines**. It is the resume key. Deriving it from an
     enumeration index would silently corrupt a resumed run whenever the listing changes.
  * `load()` returns `(data[n_channels, n_samples] in MICROVOLTS, ch_names, sfreq, meta)`.

UNITS ARE PART OF THE CONTRACT, not a detail. MNE reads EDF in volts; every model here expects microvolts.
A factor of 1e6 in the amplitude does not change the aperiodic exponent — it shifts the offset — but it
does change band power, Lempel-Ziv thresholds and anything with an absolute scale. `to_microvolts` exists so
the conversion happens in exactly one place and is declared per adapter rather than assumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

import numpy as np

LoadResult = Tuple[np.ndarray, List[str], float, Dict[str, Any]]


@dataclass
class RecordingRef:
    """A handle to one recording. Holds no signal data — `load()` fetches on demand."""

    recording_id: str
    dataset: str
    load: Callable[[], LoadResult]
    subject: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.recording_id:
            raise ValueError("recording_id may not be empty — it is the resume key")
        if not self.subject:
            # Defaulting subject to recording_id is safe ONLY when there is genuinely one recording per
            # subject. An adapter with repeated recordings MUST set it, or subject-level splitting silently
            # becomes recording-level splitting and every confidence interval is too narrow.
            self.subject = self.recording_id


class Adapter:
    """Base class. Subclasses implement `list_recordings`."""

    name: str = "unnamed"
    units: str = "microvolts"

    def list_recordings(self) -> Sequence[RecordingRef]:
        raise NotImplementedError

    def __iter__(self) -> Iterable[RecordingRef]:
        return iter(self.list_recordings())


def to_microvolts(data: np.ndarray, source_units: str) -> np.ndarray:
    """Convert to microvolts from a DECLARED source unit. Raises on anything it does not recognise.

    Guessing from the magnitude of the data was considered and rejected: it works until it meets a flat
    channel, a recording in a genuinely unusual scale, or an already-converted array, and then it fails
    silently in a way no test would catch.
    """
    factors = {"microvolts": 1.0, "uv": 1.0, "µv": 1.0,
               "volts": 1e6, "v": 1e6,
               "millivolts": 1e3, "mv": 1e3,
               "nanovolts": 1e-3, "nv": 1e-3}
    key = str(source_units).strip().lower()
    if key not in factors:
        raise ValueError(f"unknown source units {source_units!r}; declare one of {sorted(set(factors))}")
    f = factors[key]
    return np.asarray(data, float) if f == 1.0 else np.asarray(data, float) * f


def shard_of(recording_id: str, n_shards: int) -> int:
    """Which shard a recording belongs to. Stable across processes and machines.

    NOT Python's `hash()`. String hashing is salted per process (PYTHONHASHSEED), so `hash()` would put the
    same recording in different shards on different runs — the shards would silently overlap and leave gaps,
    and only the randomised path would be affected, which is the hardest kind of bug to notice.
    """
    import hashlib
    if n_shards < 1:
        raise ValueError("n_shards must be >= 1")
    h = hashlib.sha256(recording_id.encode()).digest()
    return int.from_bytes(h[:8], "big") % n_shards
