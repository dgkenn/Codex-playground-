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

import re
from dataclasses import dataclass, field
from typing import Any

from common.hashing import hash_object
from pipeline.stream_fetch import RecordingRef

# Canonical 10-20 names in their standard capitalisation form.
_CANONICAL_10_20 = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
    "Fz", "Cz", "Pz",
]

# Upper-case lookup: canonical upper -> canonical standard form.
_UPPER_TO_CANONICAL: dict[str, str] = {c.upper(): c for c in _CANONICAL_10_20}

# Modern (ACNS 2017+) 10-20 electrode names mapped to old equivalents
# accepted by clinical EDF recorders.  Both directions are accepted as input;
# the canonical form in this study is the *old* name.
_MODERN_TO_OLD: dict[str, str] = {
    "T7": "T3",
    "T8": "T4",
    "P7": "T5",
    "P8": "T6",
}

# Suffixes that clinical amplifiers append after the electrode name.
# Stripped in order; each is tried as a case-insensitive suffix match.
_REF_SUFFIXES = ["-REF", "-LE", "-AVG", "-A1", "-A2", "REF"]

# Leading prefix added by some clinical systems (e.g. "EEG Fp1-REF").
_EEG_PREFIX_RE = re.compile(r"^EEG\s+", re.IGNORECASE)


def normalize_channel_names(names: list[str]) -> dict[str, str]:
    """Return {canonical_name: original_name} for channels that map to 10-20.

    Normalization steps (applied in order):
    1. Strip surrounding whitespace.
    2. Strip a leading "EEG " prefix (case-insensitive).
    3. Strip a recognised reference suffix (-REF, -LE, -AVG, -A1, -A2, REF).
    4. Strip any remaining surrounding whitespace.
    5. Apply modern->old 10-20 equivalence (T7->T3, T8->T4, P7->T5, P8->T6).
    6. Resolve to the canonical capitalisation form.

    If multiple inputs map to the same canonical name the first occurrence wins.
    Names that do not resolve to a canonical 10-20 electrode are silently
    ignored (ECG, EOG, A1/A2 reference electrodes, etc.).
    """
    result: dict[str, str] = {}
    for original in names:
        # Step 1: strip outer whitespace.
        name = original.strip()
        # Step 2: strip "EEG " prefix.
        name = _EEG_PREFIX_RE.sub("", name)
        # Step 3: strip reference suffix (case-insensitive, longest match first).
        name_upper = name.upper()
        for suffix in _REF_SUFFIXES:
            if name_upper.endswith(suffix.upper()):
                name = name[: len(name) - len(suffix)]
                break
        # Step 4: strip again after suffix removal.
        name = name.strip()
        # Step 5: modern->old equivalence on upper-cased token.
        upper = name.upper()
        old_upper = _MODERN_TO_OLD.get(upper, upper)
        # Step 6: resolve to canonical capitalisation.
        canonical = _UPPER_TO_CANONICAL.get(old_upper)
        if canonical is None:
            continue  # not a 10-20 electrode we care about
        if canonical not in result:  # first occurrence wins
            result[canonical] = original
    return result


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
    # Mapping from *original* channel name in the raw file -> canonical 10-20
    # name, for the channels we intend to keep.  Empty when no renaming is
    # needed (original names already match the canonical set).
    rename_map: tuple[tuple[str, str], ...] = field(default_factory=tuple)

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
    # rename_map items: (original_name, canonical_name) -- stored as a sorted
    # tuple of pairs so the dataclass remains frozen and hashable.
    rename_pairs: list[tuple[str, str]] = []

    if available_channels is not None:
        # Build normalized map: canonical_name -> original_name.
        norm_map = normalize_channel_names(available_channels)
        # Determine which target channels are covered.
        dropped = [c for c in target if c not in norm_map]
        # Build the rename map only for channels that need renaming (i.e. the
        # original name differs from the canonical name).
        for canonical, original in norm_map.items():
            if canonical in target and original != canonical:
                rename_pairs.append((original, canonical))
        rename_pairs.sort()  # deterministic order

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
        rename_map=tuple(rename_pairs),
    )


def apply_harmonization(raw, plan: HarmonizationPlan):  # pragma: no cover - needs mne + signal
    """Apply the plan to a lazy raw reader, returning windowed array in memory.

    Returns a float32 array of shape (n_windows, n_channels, n_samples). Nothing
    is written to disk. Requires mne; imported lazily.
    """
    import numpy as np  # noqa: F401  (used by mne ops below)
    try:
        import mne  # noqa: F401
    except ImportError as exc:
        raise ImportError("apply_harmonization requires mne") from exc

    if not plan.mappable:
        raise ValueError(
            f"recording not mappable to common channel set; "
            f"missing {plan.dropped_channels}"
        )

    # Rename non-canonical channel names to their canonical equivalents before
    # picking.  plan.rename_map contains (original_name, canonical_name) pairs.
    if plan.rename_map:
        raw.rename_channels({orig: canon for orig, canon in plan.rename_map})

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
