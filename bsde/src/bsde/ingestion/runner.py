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
import hashlib
import inspect
import json
import os
import sys
from typing import Any, Dict, List, Sequence

# Run directly as a script path (`python src/bsde/ingestion/runner.py ...`) without an install or a
# hand-set PYTHONPATH. Only applies when there is no package context, so a normal import is untouched.
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np

from bsde.ingestion.base import Adapter, RecordingRef, shard_of



def definition_fingerprint(candidates: Sequence) -> Dict[str, str]:
    """Per-candidate fingerprint of the CODE that produces its values, not just its declared claim.

    WHY THIS IS SEPARATE FROM `declaration_hash`. A candidate's declaration hash deliberately EXCLUDES the
    callable, so that refactoring an implementation does not invalidate a pre-registered claim. That is right
    for the registry and wrong here: resuming a stream after a feature's implementation changed silently
    mixes two definitions in one column, and nothing about the file's shape reveals it.

    Not hypothetical. `f_lziv` was changed to resample to a common rate -- a correctness fix, because LZ76
    normalised by n/log2(n) is not comparable across sampling rates -- while an I-CARE stream was mid-flight.
    The already-written rows carried the old definition, the column set was byte-identical, and the existing
    guard would have appended new-definition rows beside them without complaint. The table would have parsed
    cleanly and mixed two measures under one heading.

    The fingerprint hashes the SOURCE FILE of each candidate's function. That is coarse -- any edit to
    `seed.py` invalidates every resume against it -- and coarse in the safe direction, because module-level
    constants such as `LZIV_TARGET_HZ` are part of a feature's definition and a function-only hash misses
    them.
    """
    out = {}
    for c in candidates:
        try:
            src = inspect.getsourcefile(c.fn)
            blob = open(src, "rb").read() if src else b""
        except Exception:
            blob = b""
        h = hashlib.sha256(blob).hexdigest()[:16] if blob else "unknown"
        out[c.name] = f"{c.declaration_hash()}:{h}"
    return out


def _manifest_path(out_csv: str) -> str:
    return out_csv + ".manifest.json"


def _row_for(ref: RecordingRef, candidates: Sequence, fields: Sequence[str],
             meta_keys: Sequence[str] = ()) -> Dict[str, Any]:
    """Compute one feature row. The raw arrays go out of scope when this function returns."""
    row = {"recording_id": ref.recording_id, "dataset": ref.dataset, "subject": ref.subject,
           "status": "ok", "error": "", "n_channels": "", "sfreq": "", "n_samples": ""}
    # Persist declared metadata keys. Without this the STATE LABEL is lost: an adapter can parse
    # `task-sed` out of a BIDS path into ref.meta, but if the row does not carry it the feature table has
    # no outcome column and the whole extraction has to be redone or reverse-engineered from the id.
    for k in meta_keys:
        row[f"meta_{k}"] = "" if ref.meta.get(k) is None else str(ref.meta.get(k))
    try:
        data, ch_names, sfreq, meta = ref.load()
        data = np.asarray(data, float)
        row["n_channels"] = data.shape[0]
        row["n_samples"] = data.shape[1]
        row["sfreq"] = f"{float(sfreq):.6g}"
        merged = dict(ref.meta)
        merged.update(meta or {})
        for k in meta_keys:
            if row.get(f"meta_{k}", "") == "" and merged.get(k) is not None:
                row[f"meta_{k}"] = str(merged.get(k))
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
                    log=print, meta_keys: Sequence[str] = (),
                    allow_definition_drift: bool = False) -> Dict[str, int]:
    """Extract features for every recording in this shard, appending to `out_csv`. Resumable.

    Returns counts. Raises if `out_csv` exists with a different column set — see the module docstring.
    """
    fields = (["recording_id", "dataset", "subject", "status", "error",
               "n_channels", "sfreq", "n_samples"]
              + [f"meta_{k}" for k in meta_keys] + [c.name for c in candidates])
    fp = definition_fingerprint(candidates)

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
        mp = _manifest_path(out_csv)
        if os.path.exists(mp):
            prev = json.load(open(mp)).get("definitions", {})
            drift = {k: (prev.get(k), fp[k]) for k in fp if k in prev and prev[k] != fp[k]}
            if drift and not allow_definition_drift:
                raise ValueError(
                    "the CODE defining these candidates changed since the existing rows were written, so "
                    "resuming would mix two definitions of the same column in one table:\n"
                    + "\n".join(f"    {k}: {a} -> {b}" for k, (a, b) in sorted(drift.items()))
                    + f"\nDelete {out_csv} and re-run, or pass allow_definition_drift=True if you have "
                      "verified the change cannot affect the already-written values.")
            if drift:
                log(f"   WARNING: definition drift accepted for {sorted(drift)} -- this table now mixes "
                    "definitions and any cross-row comparison of those columns is invalid.")

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
            with open(_manifest_path(out_csv), "w") as mf:
                json.dump({"definitions": fp, "fields": list(fields)}, mf, indent=2, sort_keys=True)
        for i, ref in enumerate(todo, 1):
            row = _row_for(ref, candidates, fields, meta_keys=meta_keys)
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
    ap.add_argument("--allow-definition-drift", action="store_true",
                    dest="allow_definition_drift",
                    help="resume even though a feature's implementation changed; the table will then mix definitions")
    ap.add_argument("--meta-keys", default="", dest="meta_keys",
                    help="comma-separated ref.meta keys to persist as meta_<key> columns, e.g. 'task,acq,run'")
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
    mk = [k.strip() for k in a.meta_keys.split(',') if k.strip()]
    stats = stream_features(adapter, cands, a.out, shard=a.shard, n_shards=a.n_shards, limit=a.limit,
                            meta_keys=mk, allow_definition_drift=a.allow_definition_drift)
    print(f"   {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
