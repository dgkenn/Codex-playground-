"""Streaming Pass-1 pipeline: fetch -> harmonize -> embed -> features.

Disk-sparing core (Sec 0): raw waveforms are transient. Each recording is
streamed once, harmonized in memory, embedded by the frozen model, reduced to a
compact feature vector, written as a single row, then discarded.

Heavy dependencies (mne, torch, the foundation-model checkpoint) are imported
lazily inside the functions that need them so the rest of the package -- and the
integrity tests -- import cleanly without the ML stack installed.
"""
