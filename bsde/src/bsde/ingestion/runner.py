"""The streaming feature runner: fetch, reduce to a row, discard, append, repeat — and survive being killed.

RESUMPTION IS THE WHOLE POINT. Every extraction in the sibling project was lost at least once to container
reclamation, and the ones that survived did so because they were resumable. The rule inherited from there:
a script reads what is already in its output file and fetches only the remainder.

The guarantee implemented here is stronger than "skip what is done":

  * **Rows are flushed and fsynced after every recording.** A row that made it to disk is on disk. Buffering
    a hundred rows and losing them to a SIGKILL is how "resumable" becomes "resumable in principle".
  * **A failed recording is recorded as a failure row, not skipped silently.** Otherwise a resumed run
    retries the same broken file forever, and — worse — the final table's row count silently disagrees with
    the dataset's recording count with nothing to explain the gap. `status` distinguishes `ok` from `error`,
    and errors carry their exception type.
  * **The header is written once and CHECKED on resume.** Appending rows with a different column set to an
    existing file produces a table that parses fine and means nothing. If the candidate set has changed,
    the run refuses to continue rather than corrupting the file.

DETERMINISM. Given the same recording and the same candidates, the row is byte-identical between runs. No
timestamps, no random seeds, no clock reads inside the loop. That is what makes `--resume` verifiable: run
twice, diff the files, expect no difference.

SHARDING is by stable hash of `recording_id`, so N processes can run concurrently against disjoint slices
with no coordination and no shared state. Shards are disjoint and complete by construction.
"""
from __future__ import annotations

import csv
import os
import sys
from typing import Any, Dict, List, Sequence

# Run directly as a script path (`python src/bsde/ingestion/runner.py ...`) without an install or a
# hand-set PYTHONPATH. Only applies when there is no package context, so a normal import is untouched.
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np

from bsde.ingestion.base import Adapter, RecordingRef, shard_of


def _row_for(ref: RecordingRef, candidates: Sequence, fields: Sequence[str]) -> Dict[str, Any]:
    """Compute one feature row. The raw arrays go out of scope when this function returns."""
    row = {"recording_id": ref.recording_id, "dataset": ref.dataset, "subject": ref.subject,
           "status": "ok", "error": "", "n_channels": "", "sfreq": "", "n_samples": ""}
    try:
        data, ch_names, sfreq, meta = ref.load()
        data = np.asarray(data, float)
        row["n_channels"] = data.shape[0]
        row["n_samples"] = data.shape[1]
        row["sfreq"] = f"{float(sfreq):.6g}"
        merged = dict(ref.meta)
        merged.update(meta or {})
        for c in candidates:
            try:
                v = c.fn(data, ch_names, sfreq, merged)
                row[c.name] = "" if v is None or not np.isfinite(v) else f"{float(v):.10g}"
            except Exception as e:                      # one bad candidate must not lose the whole row
                row[c.name] = ""
                row["error"] = (row["error"] + f"|{c.name}:{type(e).__name__}").lstrip("|")
    except Exception as e:
        row["status"] = "error"
        row["error"] = f"{type(e).__name__}: {e}"[:300]
        for c in candidates:
            row[c.name] = ""
    return {k: row.get(k, "") for k in fields}


def stream_features(adapter: Adapter, candidates: Sequence, out_csv: str,
                    shard: int = 0, n_shards: int = 1, limit: int | None = None,
                    log=print) -> Dict[str, int]:
    """Extract features for every recording in this shard, appending to `out_csv`. Resumable.

    Returns counts. Raises if `out_csv` exists with a different column set — see the module docstring.
    """
    fields = (["recording_id", "dataset", "subject", "status", "error",
               "n_channels", "sfreq", "n_samples"] + [c.name for c in candidates])

    done: set = set()
    if os.path.exists(out_csv) and os.path.getsize(out_csv) > 0:
        with open(out_csv, newline="") as fh:
            rd = csv.DictReader(fh)
            existing = list(rd.fieldnames or [])
            if existing != fields:
                raise ValueError(
                    f"{out_csv} already exists with a different column set. Refusing to append, because "
                    f"the result would parse cleanly and mean nothing.\n  on disk: {existing}\n  wanted : "
                    f"{fields}\nUse a new output path, or delete the old one deliberately.")
            done = {r["recording_id"] for r in rd}
        log(f"   resuming: {len(done)} rows already present in {out_csv}")

    refs = [r for r in adapter.list_recordings() if shard_of(r.recording_id, n_shards) == shard]
    todo = [r for r in refs if r.recording_id not in done]
    if limit is not None:
        todo = todo[:limit]
    log(f"   shard {shard}/{n_shards}: {len(refs)} recordings, {len(todo)} remaining")

    os.makedirs(os.path.dirname(os.path.abspath(out_csv)) or ".", exist_ok=True)
    new_file = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    n_ok = n_err = 0
    with open(out_csv, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new_file:
            w.writeheader()
            fh.flush()
            os.fsync(fh.fileno())
        for i, ref in enumerate(todo, 1):
            row = _row_for(ref, candidates, fields)
            w.writerow(row)
            fh.flush()
            os.fsync(fh.fileno())          # a row on disk is a row that survives SIGKILL
            n_ok += row["status"] == "ok"
            n_err += row["status"] == "error"
            if i % 10 == 0 or i == len(todo):
                log(f"   [{i}/{len(todo)}] ok={n_ok} err={n_err}")
    return {"n_in_shard": len(refs), "n_processed": len(todo), "n_ok": n_ok, "n_error": n_err,
            "n_already_done": len(done)}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: python -m bsde.ingestion.runner --adapter brainvision --path DIR --out FILE [--shard k --of n]"""
    import argparse

    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY

    ap = argparse.ArgumentParser(description="Stream a dataset into a feature table. Raw EEG never lands.")
    ap.add_argument("--adapter", required=True,
                    choices=["brainvision", "openneuro", "http_edf", "wfdb", "openneuro_brainvision"])
    ap.add_argument("--path", required=True,
                    help="brainvision: local dir | openneuro*: accession | http_edf: file with one URL per "
                         "line | wfdb: base URL (record names come from --records)")
    ap.add_argument("--records", default="", help="wfdb only: file with one record name per line")
    ap.add_argument("--suffix", default="_eeg.edf", help="openneuro only: key suffix to select")
    ap.add_argument("--window-s", type=float, default=300.0, dest="window_s")
    ap.add_argument("--channel-regex", default="", dest="channel_regex",
                    help="http_edf only: select channels by label regex, e.g. '^EEG ' for polysomnography")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dataset", default="")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1, dest="n_shards")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--candidates", default="", help="comma-separated names; default = all seeded")
    a = ap.parse_args(argv)

    seed_registry()
    cands = (REGISTRY.all() if not a.candidates
             else [REGISTRY.get(n.strip()) for n in a.candidates.split(",") if n.strip()])

    ds = a.dataset or os.path.basename(a.path.rstrip("/"))
    if a.adapter == "brainvision":
        from bsde.ingestion.local_brainvision import BrainVisionAdapter
        adapter = BrainVisionAdapter(a.path, dataset=ds)
    elif a.adapter == "openneuro":
        from bsde.ingestion.openneuro_s3 import OpenNeuroS3Adapter
        adapter = OpenNeuroS3Adapter(a.path, dataset=ds, suffix=a.suffix, window_s=a.window_s)
    elif a.adapter == "openneuro_brainvision":
        from bsde.ingestion.openneuro_brainvision import OpenNeuroBrainVisionAdapter
        adapter = OpenNeuroBrainVisionAdapter(a.path, dataset=ds, window_s=a.window_s)
    elif a.adapter == "http_edf":
        from bsde.ingestion.http_edf import HttpEDFAdapter
        urls = [ln.strip() for ln in open(a.path) if ln.strip() and not ln.startswith("#")]
        adapter = HttpEDFAdapter(urls, dataset=ds, window_s=a.window_s,
                                 channel_regex=a.channel_regex or None)
    elif a.adapter == "wfdb":
        from bsde.ingestion.physionet_wfdb import PhysioNetWFDBAdapter
        if not a.records:
            raise SystemExit("--records is required for --adapter wfdb")
        recs = [ln.strip() for ln in open(a.records) if ln.strip() and not ln.startswith("#")]
        adapter = PhysioNetWFDBAdapter(a.path, recs, dataset=ds, window_s=a.window_s)
    else:
        raise SystemExit(f"unhandled adapter {a.adapter}")

    print(f"streaming {adapter.name} -> {a.out}")
    print(f"   candidates: {[c.name for c in cands]}")
    stats = stream_features(adapter, cands, a.out, shard=a.shard, n_shards=a.n_shards, limit=a.limit)
    print(f"   {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
