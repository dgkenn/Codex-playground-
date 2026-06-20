"""writer.py -- the compact-table sink for Pass 1 (Sec 0, 19).

Pass 1 emits ONE compact row per recording; this writer fans that row into three
aligned tables -- embeddings, features, qc -- keyed by recording_id. To stay both
disk- and RAM-sparing it writes one fragment per shard into a directory dataset
(part-000000.parquet, ...) and clears its buffer on every `flush`, so neither raw
signal nor the full corpus is ever held in memory.

Parquet (via pyarrow) is the production backend; when pyarrow is absent the
writer transparently falls back to newline-delimited JSON so the streaming
contract is testable with the standard library alone.
"""
from __future__ import annotations

import json
import os
from typing import Any


def _have_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


class CompactTableWriter:
    """Buffered, shard-fragmented writer for the three compact tables."""

    def __init__(self, cfg: dict[str, Any], out_dir: str | None = None,
                 backend: str | None = None):
        self.cfg = cfg
        self.out_dir = out_dir or cfg.get("artifacts_dir", "artifacts")
        self.backend = backend or ("parquet" if _have_pyarrow() else "jsonl")
        self._buf_emb: list[dict] = []
        self._buf_mo: list[dict] = []
        self._buf_feat: list[dict] = []
        self._buf_qc: list[dict] = []
        self._frag = self._next_fragment_index()
        for sub in ("embeddings", "features", "qc"):
            os.makedirs(os.path.join(self.out_dir, sub), exist_ok=True)

    # -- public API ---------------------------------------------------------
    def write_row(self, row: dict[str, Any]) -> None:
        """Split one Pass-1 row into its aligned table records."""
        rid = row["recording_id"]
        self._buf_emb.append({"recording_id": rid, "embedding": list(row["embedding"])})
        feat = {"recording_id": rid}
        feat.update(row["features"])  # already a flat name->float mapping
        self._buf_feat.append(feat)
        # Optional MORGOTH-style task outputs (the redundancy/novelty reference,
        # v3 Sec 13.3). Present only when the backbone emits task heads; absent
        # for CBraMod. Persisted to its own aligned table.
        if "model_outputs" in row and row["model_outputs"] is not None:
            self._buf_mo.append({"recording_id": rid,
                                 "model_outputs": list(row["model_outputs"])})
        meta = {k: v for k, v in row.items()
                if k not in ("embedding", "features", "model_outputs")}
        self._buf_qc.append(meta)

    def flush(self) -> None:
        """Persist the buffered shard as one fragment per table, then clear."""
        if not self._buf_emb:
            return
        tag = f"part-{self._frag:06d}"
        writer = self._write_parquet if self.backend == "parquet" else self._write_jsonl
        writer("embeddings", tag, self._buf_emb)
        writer("features", tag, self._buf_feat)
        writer("qc", tag, self._buf_qc)
        if self._buf_mo:                       # only when task outputs exist
            os.makedirs(os.path.join(self.out_dir, "model_outputs"), exist_ok=True)
            writer("model_outputs", tag, self._buf_mo)
        self._buf_emb.clear()
        self._buf_feat.clear()
        self._buf_qc.clear()
        self._buf_mo.clear()
        self._frag += 1

    def close(self) -> None:
        self.flush()

    def __enter__(self) -> "CompactTableWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- backends -----------------------------------------------------------
    def _write_parquet(self, sub: str, tag: str, rows: list[dict]) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(rows)
        path = os.path.join(self.out_dir, sub, f"{tag}.parquet")
        codec = self.cfg.get("execution", {}).get("array_codec", "zstd")
        level = self.cfg.get("execution", {}).get("compression_level", 5)
        pq.write_table(table, path, compression=codec, compression_level=level)

    def _write_jsonl(self, sub: str, tag: str, rows: list[dict]) -> None:
        path = os.path.join(self.out_dir, sub, f"{tag}.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")

    def _next_fragment_index(self) -> int:
        """Resume-safe: continue numbering after any existing fragments."""
        emb_dir = os.path.join(self.out_dir, "embeddings")
        if not os.path.isdir(emb_dir):
            return 0
        existing = [f for f in os.listdir(emb_dir) if f.startswith("part-")]
        return len(existing)


# ---- reader (for the analysis stages) -------------------------------------
def load_compact_tables(cfg: dict[str, Any], out_dir: str | None = None) -> dict[str, Any]:
    """Read the embeddings + features + qc fragments back into memory.

    Returns {recording_id: [...], embedding: [[...]], features: [{...}],
    qc: [{...}]} with the three tables row-aligned by recording_id. Used by the
    Phase-1 analysis orchestrator, which then runs entirely on these compacts.
    """
    out_dir = out_dir or cfg.get("artifacts_dir", "artifacts")
    backend = "parquet" if _have_pyarrow() else "jsonl"
    emb = _read_table(os.path.join(out_dir, "embeddings"), backend)
    feat = _read_table(os.path.join(out_dir, "features"), backend)
    qc = _read_table(os.path.join(out_dir, "qc"), backend)

    by_id = {r["recording_id"]: r for r in emb}
    order = list(by_id)
    tables = {
        "recording_id": order,
        "embedding": [by_id[i]["embedding"] for i in order],
        "features": _align(feat, order),
        "qc": _align(qc, order),
    }
    # Optional MORGOTH task-output table (row-aligned), present only when the
    # backbone emits task heads -> drives the redundancy/novelty control.
    mo = _read_table(os.path.join(out_dir, "model_outputs"), backend)
    if mo:
        by_mo = {r["recording_id"]: r["model_outputs"] for r in mo}
        tables["model_outputs"] = [by_mo[i] for i in order]
    return tables


def _align(rows: list[dict], order: list[str]) -> list[dict]:
    idx = {r["recording_id"]: r for r in rows}
    return [idx[i] for i in order]


def _read_table(path: str, backend: str) -> list[dict]:
    rows: list[dict] = []
    if not os.path.isdir(path):
        return rows
    if backend == "parquet":
        import pyarrow.parquet as pq
        for f in sorted(os.listdir(path)):
            if f.endswith(".parquet"):
                rows.extend(pq.read_table(os.path.join(path, f)).to_pylist())
    else:
        for f in sorted(os.listdir(path)):
            if f.endswith(".jsonl"):
                with open(os.path.join(path, f), encoding="utf-8") as fh:
                    rows.extend(json.loads(ln) for ln in fh if ln.strip())
    return rows
