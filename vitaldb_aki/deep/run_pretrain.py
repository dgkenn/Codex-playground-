"""run_pretrain.py -- CPU feasibility driver for the deep-learning arm (§9F, §10).

What this proves
----------------
That the whole deep path -- stream one case's 4 intraoperative waveforms ->
clip to [.., opend] -> resample to a common low rate -> window -> masked-signal
SSL on the compact 1D-CNN encoder -> frozen per-case embeddings -> dump to disk --
RUNS END TO END ON CPU, on a small downsampled subset, with the SSL loss DECREASING.

What this is NOT
----------------
This is a FEASIBILITY proof, not the real pretraining. This box is CPU-only
(torch 2.5.1+cpu, no GPU). For the actual study we would: use the full cohort, a
higher common rate / longer context, more epochs, and early stopping on a held-out
patient split -- all of which need a GPU. The architecture and streaming here are the
exact ones a GPU run would scale up; only the scale (cases, rate, steps) changes.
See README.md for the boundary and how the frozen embedding feeds the H3 head-to-head.

Usage
-----
    python -m vitaldb_aki.deep.run_pretrain --cases 20
    python -m vitaldb_aki.deep.run_pretrain --cases 30 --steps 60 --rate 25 --out emb.npz

Disk-sparing: cases are streamed one at a time (``iter_case_windows``); windows are
accumulated only up to ``--max-windows`` for the tiny SSL training pool, and per-case
embeddings are pooled and the raw windows released before the next case.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.config import load_yaml
from vitaldb_aki.deep import waveforms as W
from vitaldb_aki.deep.encoder import WaveformEncoder, mean_pool_embeddings
from vitaldb_aki.deep.ssl import MaskedReconstructionSSL

_DEFAULT_CFG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")


def _load_cohort_caseids(cfg: dict[str, Any], cap: int) -> list[str]:
    """Read the first `cap` caseids from the cached labelable cohort."""
    path = os.path.join(cfg["data"]["cache_dir"], "cohort.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found -- run `python vitaldb_aki/cli.py cohort` first."
        )
    ids: list[str] = []
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            cid = str(row.get("caseid", "")).strip()
            if cid:
                ids.append(cid)
            if len(ids) >= cap:
                break
    return ids


def _cases_by_id(cfg: dict[str, Any], caseids: list[str]) -> list[dict]:
    """Fetch the /cases rows (carry the anestart/opstart/opend timing for §11)."""
    from vitaldb_aki.data.client import fetch_cases

    want = set(caseids)
    by_id = {str(c.get("caseid", "")).strip(): c for c in fetch_cases(cfg)}
    out = []
    for cid in caseids:
        c = by_id.get(cid)
        if c is not None:
            out.append(c)
    return out


def run(cfg: dict[str, Any], n_cases: int = 20, n_steps: int = 40,
        rate_hz: float = W.COMMON_RATE_HZ, batch_size: int = 64,
        max_windows: int = 4000, out_path: str | None = None,
        seed: int = 0) -> dict[str, Any]:
    """Stream a small subset, run SSL, dump frozen per-case embeddings. CPU-only."""
    import numpy as np
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    caseids = _load_cohort_caseids(cfg, n_cases)
    cases = _cases_by_id(cfg, caseids)
    print(f"[feasibility] {len(cases)} cases requested; streaming waveforms "
          f"@ {rate_hz} Hz, {W.WINDOW_SECONDS}s windows ({W.WINDOW_LEN} samples)...")

    # ---- stream cases: collect a tiny SSL training pool + per-case windows ----
    case_windows: dict[str, Any] = {}
    pool: list[Any] = []           # windows for the SSL pool (capped at max_windows)
    n_pool = 0
    for cid, windows in W.iter_case_windows(cfg, cases, rate_hz, W.WINDOW_LEN):
        case_windows[cid] = windows
        if n_pool < max_windows:
            take = min(windows.shape[0], max_windows - n_pool)
            pool.append(windows[:take])
            n_pool += take
        print(f"  case {cid}: {windows.shape[0]} windows "
              f"(pool={n_pool}/{max_windows})")

    if not pool:
        raise RuntimeError(
            "no windows produced -- check waveform coverage / cohort cache / network."
        )

    X = np.concatenate(pool, axis=0).astype("float32")   # (N, C, L)
    # Per-channel standardization over the pool (stabilizes the recon loss scale).
    mu = X.mean(axis=(0, 2), keepdims=True)
    sd = X.std(axis=(0, 2), keepdims=True) + 1e-6
    Xn = (X - mu) / sd
    print(f"[feasibility] SSL pool: {Xn.shape} (windows, channels, samples)")

    # ---- build encoder + SSL, run a few steps, watch the loss ----
    encoder = WaveformEncoder(n_channels=W.N_CHANNELS)
    n_params = encoder.count_parameters()
    print(f"[feasibility] encoder params: {n_params} "
          f"(emb_dim={encoder.emb_dim}); CPU-only torch={torch.__version__}")
    ssl = MaskedReconstructionSSL(encoder, win_len=W.WINDOW_LEN,
                                  n_channels=W.N_CHANNELS, seed=seed)

    n = Xn.shape[0]
    losses: list[float] = []
    for step in range(n_steps):
        idx = rng.integers(0, n, size=min(batch_size, n))
        loss = ssl.train_step(Xn[idx])
        losses.append(loss)
        if step % max(1, n_steps // 10) == 0 or step == n_steps - 1:
            print(f"  step {step:3d}  loss={loss:.5f}")

    first, last = losses[0], losses[-1]
    print(f"[feasibility] loss {first:.5f} -> {last:.5f} over {n_steps} steps "
          f"({'DOWN' if last < first else 'NOT down'})")

    # ---- freeze encoder; dump per-case mean-pooled embeddings ----
    encoder.eval()
    case_ids_out: list[str] = []
    embs: list[Any] = []
    for cid, windows in case_windows.items():
        wn = ((windows.astype("float32") - mu) / sd)
        we = encoder.embed_windows(wn)               # (n_windows, emb_dim)
        embs.append(mean_pool_embeddings(we))
        case_ids_out.append(cid)
        # release this case's raw windows
    emb_matrix = np.stack(embs, axis=0) if embs else np.zeros((0, encoder.emb_dim))

    out_path = out_path or os.path.join(
        cfg["data"]["cache_dir"], "deep", "case_embeddings.npz"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    np.savez(out_path,
             caseids=np.asarray(case_ids_out),
             embeddings=emb_matrix.astype("float32"))
    print(f"[feasibility] wrote per-case embeddings {emb_matrix.shape} -> {out_path}")

    return {
        "n_cases_with_windows": len(case_ids_out),
        "n_pool_windows": int(Xn.shape[0]),
        "encoder_params": int(n_params),
        "loss_first": float(first),
        "loss_last": float(last),
        "loss_decreased": bool(last < first),
        "embedding_shape": list(emb_matrix.shape),
        "out_path": out_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=_DEFAULT_CFG)
    ap.add_argument("--cases", type=int, default=20, help="max cases to stream")
    ap.add_argument("--steps", type=int, default=40, help="SSL training steps")
    ap.add_argument("--rate", type=float, default=W.COMMON_RATE_HZ,
                    help="common resample rate (Hz)")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--max-windows", type=int, default=4000,
                    help="cap windows in the SSL training pool (memory)")
    ap.add_argument("--out", default=None, help="output .npz for per-case embeddings")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    import json
    summary = run(cfg, n_cases=args.cases, n_steps=args.steps, rate_hz=args.rate,
                  batch_size=args.batch_size, max_windows=args.max_windows,
                  out_path=args.out, seed=args.seed)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
