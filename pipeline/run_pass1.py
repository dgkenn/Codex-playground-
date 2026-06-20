"""run_pass1.py -- the single streaming pass (Sec 0).

Orchestrates: stream one recording -> harmonize in memory -> frozen embed +
pool -> interpretable features -> write ONE compact row -> discard raw. Shards
the work, checkpoints the compact output, and resumes after interruption.
Never holds more than one shard of raw in memory/scratch.

Only compact tables are persisted (embeddings.parquet, features.parquet,
qc.parquet). pandas/pyarrow are imported lazily by the writer.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Iterable

from common.config import config_hash
from common.logging_utils import audit_log
from guards.heldout_guard import HeldoutGuard
from pipeline.embed import (
    FrozenEmbedder,
    pool_embeddings,
    select_window_indices,
    should_keep_epoch_subset,
)
from pipeline.features import compute_features
from pipeline.harmonize import apply_harmonization, plan_harmonization
from pipeline.stream_fetch import (
    RecordingRef,
    _BDSPClient,
    iter_qualifying_recordings,
    make_client,
    open_recording,
)


# ---- resume bookkeeping --------------------------------------------------
def _checkpoint_path(cfg: dict[str, Any], done_path: str | None = None) -> str:
    if done_path:
        return done_path
    return os.path.join(cfg.get("artifacts_dir", "artifacts"), "pass1_done.txt")


def load_completed(cfg: dict[str, Any], done_path: str | None = None) -> set[str]:
    """Recording ids already written -- the resume set (Sec 0). With a per-shard
    `done_path`, each parallel worker tracks its own completions independently."""
    path = _checkpoint_path(cfg, done_path)
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as fh:
        return {ln.strip() for ln in fh if ln.strip()}


def mark_completed(cfg: dict[str, Any], recording_id: str,
                   done_path: str | None = None) -> None:
    path = _checkpoint_path(cfg, done_path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(recording_id + "\n")


def shard_match(recording_id: str, shard: int, num_shards: int) -> bool:
    """Deterministic, cross-process partition: True iff this recording belongs to
    worker `shard` of `num_shards`. Uses sha256 (NOT Python hash(), which is
    per-process salted) so disjoint workers cover every recording exactly once."""
    import hashlib
    if num_shards <= 1:
        return True
    h = int.from_bytes(hashlib.sha256(recording_id.encode("utf-8")).digest()[:8], "big")
    return (h % num_shards) == shard


def shard_iter(items: Iterable[RecordingRef], size: int):
    """Yield lists of at most `size` recordings (one shard's worth)."""
    batch: list[RecordingRef] = []
    for it in items:
        batch.append(it)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def process_recording(cfg: dict[str, Any], ref: RecordingRef,
                      embedder: FrozenEmbedder, client: _BDSPClient) -> dict[str, Any] | None:  # pragma: no cover - needs full stack
    """Stream -> harmonize -> embed -> features for one recording.

    Returns a compact row dict, or None if the recording is ineligible (e.g. not
    mappable to the common channel set, or no clean windows survive). Raw is
    released by `open_recording`'s context manager regardless of outcome.
    """
    with open_recording(cfg, ref, client) as raw:
        avail = list(getattr(raw, "ch_names", [])) or None
        plan = plan_harmonization(cfg, ref, available_channels=avail)
        if not plan.mappable:
            return None
        windows = apply_harmonization(raw, plan)
        if windows.shape[0] == 0:
            return None
        # Cap windows per recording for speed (evenly-spaced; pooling is
        # unaffected in expectation). cfg.embedding.max_windows_per_recording.
        cap = cfg.get("embedding", {}).get("max_windows_per_recording")
        if cap and windows.shape[0] > int(cap):
            idx = select_window_indices(windows.shape[0], cap)
            windows = windows[idx]
        win_emb = embedder.embed_windows(windows)
        pooled = pool_embeddings(win_emb, cfg["embedding"]["pooling"])
        feats = compute_features(windows, plan.target_sfreq_hz, cfg)
        # MORGOTH-style task outputs, when the backbone exposes them (the
        # redundancy/novelty reference, v3 Sec 13.3). No-op for CBraMod.
        task_out = None
        if hasattr(embedder, "task_outputs"):
            task_out = [float(x) for x in embedder.task_outputs(windows)]

    row = {
        **asdict(ref),
        "embedding": pooled.tolist(),
        "features": feats,
        "model_outputs": task_out,
        "n_windows": int(windows.shape[0]),
        "harmonization_hash": plan.content_hash(),
        "keep_epoch_subset": should_keep_epoch_subset(
            ref.recording_id, cfg["embedding"]["persist_epoch_subset_fraction"]
        ),
    }
    return row


def run(cfg: dict[str, Any], writer, embedder: FrozenEmbedder | None = None,
        client: _BDSPClient | None = None,
        limit: int | None = None,
        shard: tuple[int, int] | None = None,
        done_path: str | None = None) -> dict[str, Any]:  # pragma: no cover - needs full stack
    """Run Pass 1 (resumable, optionally one shard of a parallel run).

    `writer` is any object with `.write_row(dict)` and `.flush()`.

    `limit` caps the number of NEW recordings consumed this run; falls back to
    `cfg.execution.max_recordings`; None/0 means no cap. Resume-safe.

    `shard=(k, n)` makes this worker process ONLY recordings whose stable hash
    selects shard k of n (disjoint, exhaustive across workers). `done_path` gives
    this worker its own resume file so N workers writing the same out_dir don't
    clobber each other's checkpoint.
    """
    guard = HeldoutGuard(cfg)
    if cfg.get("phase") != 1:
        raise RuntimeError("run_pass1 is a Phase-1 operation; set phase: 1")

    if limit is None:
        limit = cfg.get("execution", {}).get("max_recordings")
    limit = None if not limit else int(limit)
    k, n_shards = shard if shard else (0, 1)

    client = client or make_client(cfg)
    embedder = embedder or FrozenEmbedder(cfg)
    log_path = os.path.join(cfg.get("log_dir", "artifacts/logs"), "pass1.log")
    audit_log(log_path, "pass1_start", config_hash=config_hash(cfg),
              limit=limit, shard=k, num_shards=n_shards)

    done = load_completed(cfg, done_path)
    shard_size = cfg["execution"]["shard_size_recordings"]
    n_written = 0
    n_consumed = 0  # new recordings processed this run (counts toward `limit`)

    recordings = iter_qualifying_recordings(cfg, guard, client)
    reached_limit = False
    for batch in shard_iter(recordings, shard_size):
        for ref in batch:
            if not shard_match(ref.recording_id, k, n_shards):
                continue                       # belongs to another worker
            if ref.recording_id in done:       # resume: skip already-written
                continue
            if limit is not None and n_consumed >= limit:
                reached_limit = True
                break
            n_consumed += 1
            row = process_recording(cfg, ref, embedder, client)
            if row is None:
                mark_completed(cfg, ref.recording_id, done_path)
                continue
            writer.write_row(row)
            mark_completed(cfg, ref.recording_id, done_path)
            n_written += 1
        writer.flush()  # checkpoint the compact table per batch
        if reached_limit:
            break

    audit_log(log_path, "pass1_done", n_written=n_written,
              n_consumed=n_consumed, hit_limit=reached_limit, shard=k)
    return {"n_written": n_written, "n_consumed": n_consumed,
            "hit_limit": reached_limit, "limit": limit, "shard": k,
            "num_shards": n_shards, "config_hash": config_hash(cfg)}
