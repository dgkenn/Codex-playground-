"""harmonize.py -- on-the-fly, in-memory harmonization (Sec 7.2).

Maps each raw recording to the foundation model's expected input: the common
10-20 channel set, a single reference, the model's sampling rate, dual 50/60 Hz
notch, bandpass, windowing, and automated artifact rejection. The output feeds
the model directly and is **never written to disk** (Sec 0).

mne is imported lazily. `plan_harmonization` is pure and unit-testable: it
resolves the deterministic recipe (channel picks, resample ratio, notch list)
from the config + recording metadata without touching signal, so the harmonized
recipe can be hashed and frozen (one of the four frozen objects, Sec 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from common.hashing import hash_object
from pipeline.stream_fetch import RecordingRef


@dataclass(frozen=True)
class HarmonizationPlan:
    target_channels: tuple[str, ...]
    reference: str
    target_sfreq_hz: float
    notch_hz: tuple[float, ...]
    bandpass_hz: tuple[float, float]
    window_seconds: float
    window_stride_seconds: float
    artifact_method: str
    artifact_reject_z: float
    source_sfreq_hz: float | None = None
    dropped_channels: tuple[str, ...] = field(default_factory=tuple)

    @property
    def mappable(self) -> bool:
        """A recording is eligible only if every target channel is present
        (Sec 5: montages not mappable to the common set are excluded)."""
        return len(self.dropped_channels) == 0

    def content_hash(self) -> str:
        return hash_object(self.__dict__)


def plan_harmonization(cfg: dict[str, Any], ref: RecordingRef,
                       available_channels: list[str] | None = None) -> HarmonizationPlan:
    """Resolve the deterministic harmonization recipe for one recording.

    Pure function of (config, recording metadata, channel list); does not read
    signal. `available_channels` lets eligibility be decided before any data is
    streamed.
    """
    m = cfg["model"]
    h = cfg["harmonization"]
    target = list(m["channels_10_20"])

    dropped: list[str] = []
    if available_channels is not None:
        avail = {c.upper() for c in available_channels}
        dropped = [c for c in target if c.upper() not in avail]

    return HarmonizationPlan(
        target_channels=tuple(target),
        reference=h.get("reference", "average"),
        target_sfreq_hz=float(m["expected_sfreq_hz"]),
        notch_hz=tuple(float(x) for x in h.get("notch_hz", [50, 60])),
        bandpass_hz=tuple(h.get("bandpass_hz", [0.5, 45])),
        window_seconds=float(m["window_seconds"]),
        window_stride_seconds=float(m["window_stride_seconds"]),
        artifact_method=h.get("artifact_rejection", "amplitude_zscore"),
        artifact_reject_z=float(h.get("artifact_reject_z", 6.0)),
        source_sfreq_hz=ref.sampling_rate,
        dropped_channels=tuple(dropped),
    )


def apply_harmonization(raw, plan: HarmonizationPlan):  # pragma: no cover - needs mne + signal
    """Apply the plan to a lazy raw reader, returning windowed array in memory.

    Returns a float32 array of shape (n_windows, n_channels, n_samples). Nothing
    is written to disk. Requires mne; imported lazily.
    """
    import numpy as np  # noqa: F401  (used by mne ops below)
    try:
        import mne
    except ImportError as exc:
        raise ImportError("apply_harmonization requires mne") from exc

    if not plan.mappable:
        raise ValueError(
            f"recording not mappable to common channel set; "
            f"missing {plan.dropped_channels}"
        )

    raw.pick(list(plan.target_channels))
    raw.set_eeg_reference(plan.reference, verbose=False)
    raw.notch_filter(freqs=list(plan.notch_hz), verbose=False)
    raw.filter(plan.bandpass_hz[0], plan.bandpass_hz[1], verbose=False)
    if abs(raw.info["sfreq"] - plan.target_sfreq_hz) > 1e-6:
        raw.resample(plan.target_sfreq_hz, verbose=False)

    data = raw.get_data()  # (n_channels, n_samples), in memory only
    win = int(round(plan.window_seconds * plan.target_sfreq_hz))
    stride = int(round(plan.window_stride_seconds * plan.target_sfreq_hz))
    windows = _window_and_reject(data, win, stride, plan.artifact_reject_z)
    return windows


def _window_and_reject(data, win: int, stride: int, reject_z: float):  # pragma: no cover - needs numpy
    import numpy as np

    n_ch, n = data.shape
    starts = range(0, max(0, n - win + 1), stride)
    kept = []
    for s in starts:
        seg = data[:, s:s + win]
        z = (seg - seg.mean(axis=1, keepdims=True)) / (seg.std(axis=1, keepdims=True) + 1e-9)
        if np.abs(z).max() <= reject_z:  # automated artifact rejection
            kept.append(seg.astype("float32"))
    if not kept:
        return np.empty((0, n_ch, win), dtype="float32")
    return np.stack(kept, axis=0)
