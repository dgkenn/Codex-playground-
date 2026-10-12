#!/usr/bin/env python3
"""Build the five-stage Sleep-EDF work-list (W, N1, N2, N3, REM) for E13.

WHY A SECOND WORK-LIST RATHER THAN AN EXTENSION OF THE FIRST. The wake-vs-N3 list is what E11 consumed, and
E11's result is on the record; appending stages to it would change what that table is while leaving its name
and its committed result unchanged. A new file with a new name keeps both readable.

ONE ROW PER (RECORDING, STAGE), with its own `start_seconds` computed from that stage's own longest
contiguous block, exactly as the two-stage builder does. A recording is kept only if ALL FIVE stages have a
block of at least `MIN_BLOCK_S`, so every retained subject contributes a complete ladder and no candidate's
five-state profile is assembled from a different set of people at each rung. That is a strict requirement and
it will reject recordings the two-stage list accepted; the rejection count is printed by reason, because a
skip rule that is not counted is a silent exclusion (rule 14: report exclusions and check whether they are
outcome-related).

WHAT WILL BE LOST, STATED BEFORE THE RUN. N1 is the scarce stage — it is transitional by definition and
rarely holds a long contiguous block — so `n1_block_too_short` is expected to dominate the skips. If it
rejects most of the corpus the ladder is not buildable at this window length and the honest response is to
report that, not to shorten the window until it fits.
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.ingestion.sleep_edfx import (STAGE_SETS, discover_hypnogram_url,          # noqa: E402
                                       fetch_directory_listing, fetch_whole,
                                       longest_block, parse_hypnogram_edf)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
URLS_FILE = os.path.join(RESULTS, "sleep_edfx_urls.txt")
WORKLIST_JSON = os.path.join(RESULTS, "sleep_edfx_five_stage_worklist.json")
SUMMARY_TXT = os.path.join(RESULTS, "sleep_edfx_five_stage_summary.txt")

MIN_BLOCK_S = 120.0
WINDOW_S = 120.0
LADDER = ("W", "N1", "N2", "N3", "REM")


def _psg_urls() -> list:
    with open(URLS_FILE) as fh:
        return sorted(ln.strip() for ln in fh
                      if ln.strip() and not ln.startswith("#") and "PSG" in ln)


def _centred_window(block, window_s: float) -> float:
    start, end = block
    ws = (start + end) / 2.0 - window_s / 2.0
    return max(start, min(ws, end - window_s))


def build_worklist(urls, log=print) -> tuple:
    rows, skips = [], collections.Counter()
    dir_cache: dict = {}
    for i, psg_url in enumerate(urls, 1):
        dir_url = psg_url.rsplit("/", 1)[0] + "/"
        psg_base = psg_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        try:
            if dir_url not in dir_cache:
                dir_cache[dir_url] = fetch_directory_listing(dir_url)
            hyp_url = discover_hypnogram_url(psg_url, dir_cache[dir_url])
            annots = parse_hypnogram_edf(fetch_whole(hyp_url))
        except Exception as e:
            skips[f"hypnogram_failed:{type(e).__name__}"] += 1
            continue

        blocks, reject = {}, None
        for label in LADDER:
            b = longest_block(annots, STAGE_SETS[label])
            if b is None:
                reject = f"no_{label}_block"
                break
            if b[1] - b[0] < MIN_BLOCK_S:
                reject = f"{label}_block_too_short"
                break
            blocks[label] = b
        if reject:
            skips[reject] += 1
            continue

        for label in LADDER:
            b = blocks[label]
            rows.append({
                "url": psg_url,
                "start_seconds": _centred_window(b, WINDOW_S),
                "window_s": WINDOW_S,
                "label": label,
                "subject": psg_base,
                "recording_id": f"{psg_base}@{label}",
                "meta": {"hypnogram_url": hyp_url, "block_start_s": b[0], "block_end_s": b[1],
                         "block_len_s": b[1] - b[0]},
            })
        skips["usable"] += 1
        if i % 20 == 0 or i == len(urls):
            log(f"   [{i}/{len(urls)}] scanned, {skips['usable']} complete ladders so far")
    return rows, skips


def main() -> int:
    urls = _psg_urls()
    print(f"five-stage work-list: {len(urls)} PSG recordings, stages {LADDER}, "
          f"min block {MIN_BLOCK_S:.0f}s, window {WINDOW_S:.0f}s")
    rows, skips = build_worklist(urls)
    json.dump(rows, open(WORKLIST_JSON, "w"), indent=1)
    n_subj = len({r["subject"] for r in rows})
    lines = [f"five-stage work-list: {len(rows)} rows over {n_subj} recordings "
             f"({len(LADDER)} stages each)", "", "skips by reason:"]
    for k, v in skips.most_common():
        lines.append(f"   {k:34s} {v}")
    lines.append("")
    lines.append(f"retention: {skips['usable']}/{len(urls)} recordings have all five stages "
                 f"with blocks >= {MIN_BLOCK_S:.0f}s")
    open(SUMMARY_TXT, "w").write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    print(f"\n   -> {WORKLIST_JSON}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
