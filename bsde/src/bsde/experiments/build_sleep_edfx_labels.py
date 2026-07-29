#!/usr/bin/env python3
"""Build the Sleep-EDF wake-vs-N3 labelled work-list, then stream it into a feature table.

WHY. This is the first REAL labelled contrast this project can run: every recording is scored, wake and
deep sleep are unambiguous states, and the two windows for one recording come from the same person on the
same night, so it is a within-subject design by construction (see `sleep_edfx.LabelledEDFWindowAdapter`'s
docstring for why `subject` is the property that must not be gotten wrong).

WHAT ONE ROW IS. For each PSG recording that has BOTH a wake block and an N3 block of at least 120 s, this
script takes a 120 s window CENTRED in the longest instance of each -- not at the edge, so a boundary
scoring uncertainty of a few epochs cannot pull the window into the neighbouring stage. A recording missing
either stage, or with both too short, is skipped and the skip is counted by reason (rule B5 in the sibling
project's error catalogue: absence must be counted, never silently dropped).

TWO NETWORK ROUND TRIPS PER RECORDING, not per row: one directory listing (cached per directory -- there are
only two, sleep-cassette and sleep-telemetry) to resolve the hypnogram filename, one small GET for the
hypnogram itself. The 120 s EEG windows are fetched later, by `stream_features`, one Range GET each -- this
script never fetches PSG signal data.

Usage:  python src/bsde/experiments/build_sleep_edfx_labels.py
Reads:  results/sleep_edfx_urls.txt
Writes: results/sleep_edfx_labelled_worklist.json
        results/sleep_edfx_labelled_worklist_summary.txt   (# per-line, human-readable skip counts)
        results/sleep_edfx_staged_features.csv             (via stream_features)
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.ingestion.sleep_edfx import (                                    # noqa: E402
    WAKE, N3, discover_hypnogram_url, fetch_directory_listing, fetch_whole,
    longest_block, parse_hypnogram_edf, LabelledEDFWindowAdapter,
)
from bsde.ingestion.runner import stream_features                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
URLS_FILE = os.path.join(RESULTS, "sleep_edfx_urls.txt")
WORKLIST_JSON = os.path.join(RESULTS, "sleep_edfx_labelled_worklist.json")
SUMMARY_TXT = os.path.join(RESULTS, "sleep_edfx_labelled_worklist_summary.txt")
FEATURES_CSV = os.path.join(RESULTS, "sleep_edfx_staged_features.csv")

MIN_BLOCK_S = 120.0
WINDOW_S = 120.0
CHANNEL_REGEX = "^EEG "


def _psg_urls() -> list:
    with open(URLS_FILE) as fh:
        return sorted(ln.strip() for ln in fh if ln.strip() and not ln.startswith("#") and "PSG" in ln)


def _centred_window(block, window_s: float) -> float:
    """The start second of a `window_s`-long window centred in `block`, clamped to stay inside it."""
    start, end = block
    center = (start + end) / 2.0
    ws = center - window_s / 2.0
    return max(start, min(ws, end - window_s))


def build_worklist(urls) -> tuple:
    """Returns (rows, skip_counts). One network round trip per directory (cached), one per hypnogram."""
    rows = []
    skips = collections.Counter()
    dir_cache: dict = {}

    for i, psg_url in enumerate(urls, 1):
        dir_url = psg_url.rsplit("/", 1)[0] + "/"
        psg_base = psg_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]  # e.g. "SC4001E0-PSG"

        try:
            if dir_url not in dir_cache:
                dir_cache[dir_url] = fetch_directory_listing(dir_url)
            hyp_url = discover_hypnogram_url(psg_url, dir_cache[dir_url])
        except Exception as e:
            skips[f"hypnogram_not_found:{type(e).__name__}"] += 1
            print(f"   [{i}/{len(urls)}] {psg_base}: hypnogram lookup FAILED: {e}")
            continue

        try:
            blob = fetch_whole(hyp_url)
            annots = parse_hypnogram_edf(blob)
        except Exception as e:
            skips[f"hypnogram_fetch_or_parse_failed:{type(e).__name__}"] += 1
            print(f"   [{i}/{len(urls)}] {psg_base}: hypnogram fetch/parse FAILED: {e}")
            continue

        wake_block = longest_block(annots, WAKE)
        n3_block = longest_block(annots, N3)

        if wake_block is None:
            skips["no_wake_block"] += 1
            continue
        if n3_block is None:
            skips["no_n3_block"] += 1
            continue
        wake_len = wake_block[1] - wake_block[0]
        n3_len = n3_block[1] - n3_block[0]
        if wake_len < MIN_BLOCK_S:
            skips["wake_block_too_short"] += 1
            continue
        if n3_len < MIN_BLOCK_S:
            skips["n3_block_too_short"] += 1
            continue

        for label, block in (("W", wake_block), ("N3", n3_block)):
            start_seconds = _centred_window(block, WINDOW_S)
            rows.append({
                "url": psg_url,
                "start_seconds": start_seconds,
                "window_s": WINDOW_S,
                "label": label,
                "subject": psg_base,
                "recording_id": f"{psg_base}@{label}",
                "meta": {"hypnogram_url": hyp_url, "block_start_s": block[0], "block_end_s": block[1]},
            })
        skips["usable"] += 1
        if i % 20 == 0 or i == len(urls):
            print(f"   [{i}/{len(urls)}] scanned, {skips['usable']} usable so far", flush=True)

    return rows, skips


def main() -> int:
    urls = _psg_urls()
    print(f"build_sleep_edfx_labels: {len(urls)} PSG urls")

    rows, skips = build_worklist(urls)

    os.makedirs(RESULTS, exist_ok=True)
    with open(WORKLIST_JSON, "w") as fh:
        json.dump(rows, fh, indent=2)

    total_recordings = len(urls)
    with open(SUMMARY_TXT, "w") as fh:
        fh.write(f"# sleep_edfx_labelled_worklist summary, built from {total_recordings} PSG recordings\n")
        fh.write(f"# usable (both W>={MIN_BLOCK_S:.0f}s and N3>={MIN_BLOCK_S:.0f}s blocks): "
                f"{skips.get('usable', 0)}\n")
        fh.write(f"# rows written to {os.path.basename(WORKLIST_JSON)}: {len(rows)} "
                f"(2 per usable recording)\n")
        for reason in sorted(skips):
            if reason == "usable":
                continue
            fh.write(f"# skipped, {reason}: {skips[reason]}\n")

    print(f"\n   usable recordings : {skips.get('usable', 0)}/{total_recordings}")
    print(f"   worklist rows     : {len(rows)}")
    for reason in sorted(skips):
        if reason == "usable":
            continue
        print(f"   skipped [{reason}]: {skips[reason]}")
    print(f"   -> {WORKLIST_JSON}")
    print(f"   -> {SUMMARY_TXT}")

    if not rows:
        print("\n   no usable rows -- nothing to stream")
        return 1

    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    seed_registry()
    cands = REGISTRY.all()

    adapter = LabelledEDFWindowAdapter(rows, dataset="sleep_edfx_staged", channel_regex=CHANNEL_REGEX)
    print(f"\n   streaming {len(rows)} labelled windows -> {FEATURES_CSV}")
    stats = stream_features(adapter, cands, FEATURES_CSV, log=print)
    print(f"   {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
