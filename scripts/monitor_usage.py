#!/usr/bin/env python3
"""
scripts/monitor_usage.py — live resource + progress dashboard for an overnight
Pass-1 EEG shard run.

Usage:
    python3 scripts/monitor_usage.py --out artifacts [--interval 30]
        [--workers 16] [--scratch /tmp/heedb_scratch] [--target 0]

Stops when:
  • $OUT/STOP_MONITOR is present, OR
  • workers_alive == 0 for 3 consecutive samples AND at least one worker was
    ever seen alive.

Progress definitions
  rows      = total records embedded (lines in embeddings/*.jsonl  OR
               pyarrow row-counts for embeddings/*.parquet)
  completed = total lines across pass1_done_w*.txt
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gpu_stats():
    """Return (util_pct_str, mem_used_str) or ('n/a','n/a')."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "n/a", "n/a"
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return "n/a", "n/a"
        # Summarise across GPUs: average util, total mem used
        utils, mem_used_vals, mem_total_vals = [], [], []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    utils.append(float(parts[0]))
                    mem_used_vals.append(float(parts[1]))
                    mem_total_vals.append(float(parts[2]))
                except ValueError:
                    pass
        if not utils:
            return "n/a", "n/a"
        avg_util = sum(utils) / len(utils)
        total_used = sum(mem_used_vals)
        total_mem = sum(mem_total_vals)
        if len(lines) == 1:
            util_str = f"{avg_util:.0f}%"
            mem_str = f"{total_used:.0f}/{total_mem:.0f} MiB"
        else:
            util_str = f"{avg_util:.0f}% (avg {len(lines)} GPUs)"
            mem_str = f"{total_used:.0f}/{total_mem:.0f} MiB"
        return util_str, mem_str
    except FileNotFoundError:
        return "n/a (no nvidia-smi)", "n/a"
    except Exception as exc:  # noqa: BLE001
        return f"n/a ({exc})", "n/a"


def _count_workers(psutil):
    """Count live processes whose cmdline contains 'run_shard.py'."""
    count = 0
    try:
        for proc in psutil.process_iter(["cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                if any("run_shard.py" in part for part in cmdline):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:  # noqa: BLE001
        pass
    return count


def _count_rows_jsonl(path: Path) -> int:
    """Count non-empty lines in a .jsonl file."""
    try:
        with path.open("rb") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return 0


def _count_rows_parquet(path: Path) -> int:
    """Return parquet row count using pyarrow metadata (no data read)."""
    try:
        import pyarrow.parquet as pq  # lazy import
        meta = pq.read_metadata(str(path))
        return meta.num_rows
    except Exception:  # noqa: BLE001
        return 0


def _embedding_rows(out_dir: Path) -> int:
    """Sum records across all embeddings/ files (jsonl + parquet)."""
    embed_dir = out_dir / "embeddings"
    if not embed_dir.is_dir():
        return 0
    total = 0
    for p in embed_dir.iterdir():
        if p.suffix == ".jsonl":
            total += _count_rows_jsonl(p)
        elif p.suffix == ".parquet":
            total += _count_rows_parquet(p)
    return total


def _completed_ids(out_dir: Path) -> int:
    """Sum line counts across all pass1_done_w*.txt files."""
    total = 0
    for p in out_dir.glob("pass1_done_w*.txt"):
        try:
            with p.open("rb") as fh:
                total += sum(1 for line in fh if line.strip())
        except OSError:
            pass
    return total


def _disk_gb(path_str: str):
    """Return (free_gb, total_gb) for the filesystem containing path_str, or (None,None)."""
    try:
        import psutil as _psutil
        du = _psutil.disk_usage(path_str)
        return du.free / 1e9, du.total / 1e9
    except Exception:  # noqa: BLE001
        return None, None


def _format_dashboard(
    *,
    ts: str,
    cpu_pct: float,
    load1: float,
    load5: float,
    ram_pct: float,
    ram_used_gb: float,
    ram_total_gb: float,
    disk_out_free: float | None,
    disk_out_total: float | None,
    disk_scratch_free: float | None,
    disk_scratch_total: float | None,
    net_recv_mbps: float,
    gpu_util: str,
    gpu_mem: str,
    workers_alive: int,
    num_workers: int,
    rows: int,
    completed: int,
    rows_per_min: float,
    eta_min: float | None,
) -> str:
    def _disk_str(free, total):
        if free is None:
            return "n/a"
        used = total - free
        return f"{used:.1f}/{total:.1f} GB ({100*used/max(total,1):.0f}% used, {free:.1f} GB free)"

    eta_str = "n/a" if eta_min is None else (
        f"{eta_min/60:.1f} h" if eta_min > 120 else f"{eta_min:.0f} min"
    )
    lines = [
        f"=== {ts} UTC ===",
        f"  CPU     : {cpu_pct:.1f}%  load(1/5): {load1:.2f}/{load5:.2f}",
        f"  RAM     : {ram_used_gb:.1f}/{ram_total_gb:.1f} GB  ({ram_pct:.1f}%)",
        f"  Disk/out: {_disk_str(disk_out_free, disk_out_total)}",
        f"  Disk/tmp: {_disk_str(disk_scratch_free, disk_scratch_total)}",
        f"  Net IN  : {net_recv_mbps:.2f} MB/s (S3 proxy)",
        f"  GPU     : util={gpu_util}  mem={gpu_mem}",
        f"  Workers : {workers_alive}/{num_workers} alive",
        f"  Progress: rows={rows}  completed={completed}  "
        f"rate={rows_per_min:.1f} rows/min  ETA={eta_str}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Live resource + progress monitor for overnight EEG Pass-1 run."
    )
    parser.add_argument("--out", default="artifacts",
                        help="Output directory (default: artifacts)")
    parser.add_argument("--interval", type=float, default=30,
                        help="Sampling interval in seconds (default: 30)")
    parser.add_argument("--workers", type=int, default=16,
                        help="Expected number of shard workers (default: 16)")
    parser.add_argument("--scratch", default="/tmp/heedb_scratch",
                        help="Scratch directory to monitor for disk (default: /tmp/heedb_scratch)")
    parser.add_argument("--target", type=int, default=0,
                        help="Total expected rows for ETA; 0 = unknown (default: 0)")
    args = parser.parse_args()

    # Lazy import psutil — exit clearly if absent
    try:
        import psutil
    except ImportError:
        print(
            "ERROR: psutil is not installed.\n"
            "Install it with:  pip install psutil",
            file=sys.stderr,
        )
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stop_sentinel = out_dir / "STOP_MONITOR"
    log_path = out_dir / "monitor.log"

    csv_header = [
        "ts", "cpu_pct", "load1", "ram_pct", "ram_used_gb",
        "disk_out_free_gb", "disk_scratch_free_gb", "net_recv_mbps",
        "gpu_util", "gpu_mem_used", "workers_alive",
        "rows", "completed", "rows_per_min", "eta_min",
    ]
    write_header = not log_path.exists() or log_path.stat().st_size == 0

    # State for rate / ETA calculation
    t0 = time.monotonic()
    rows_at_start: int | None = None

    # State for auto-stop when workers drain
    ever_had_workers = False
    zero_worker_streak = 0

    # State for net throughput delta
    prev_net_recv = None
    prev_net_time = None

    try:
        log_fh = log_path.open("a", newline="")
    except OSError as exc:
        print(f"WARNING: cannot open {log_path}: {exc}", file=sys.stderr)
        log_fh = None

    csv_writer = None
    if log_fh is not None:
        csv_writer = csv.writer(log_fh)
        if write_header:
            csv_writer.writerow(csv_header)
            log_fh.flush()

    print(f"[monitor] starting — out={out_dir}  interval={args.interval}s  "
          f"workers={args.workers}  target={args.target or 'unknown'}")
    print(f"[monitor] touch {stop_sentinel} to stop.\n", flush=True)

    try:
        while True:
            # ----------------------------------------------------------------
            # Check stop sentinel
            # ----------------------------------------------------------------
            if stop_sentinel.exists():
                print("[monitor] STOP_MONITOR detected — exiting.", flush=True)
                break

            # ----------------------------------------------------------------
            # Sample (wrapped so a transient error never kills the monitor)
            # ----------------------------------------------------------------
            try:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                # CPU
                cpu_pct = psutil.cpu_percent(interval=None)
                load1, load5, _ = os.getloadavg()

                # RAM
                vm = psutil.virtual_memory()
                ram_pct = vm.percent
                ram_used_gb = vm.used / 1e9
                ram_total_gb = vm.total / 1e9

                # Disk
                # Ensure scratch parent exists for disk_usage fallback
                scratch_probe = args.scratch if os.path.exists(args.scratch) else "/"
                disk_out_free, disk_out_total = _disk_gb(str(out_dir))
                disk_scratch_free, disk_scratch_total = _disk_gb(scratch_probe)

                # Net throughput
                net_counters = psutil.net_io_counters()
                now_time = time.monotonic()
                if prev_net_recv is not None and prev_net_time is not None:
                    delta_bytes = max(0, net_counters.bytes_recv - prev_net_recv)
                    delta_t = max(0.001, now_time - prev_net_time)
                    net_recv_mbps = delta_bytes / delta_t / 1e6
                else:
                    net_recv_mbps = 0.0
                prev_net_recv = net_counters.bytes_recv
                prev_net_time = now_time

                # GPU
                gpu_util, gpu_mem = _gpu_stats()

                # Workers
                workers_alive = _count_workers(psutil)
                if workers_alive > 0:
                    ever_had_workers = True

                # Progress
                rows = _embedding_rows(out_dir)
                completed = _completed_ids(out_dir)

                if rows_at_start is None:
                    rows_at_start = rows

                elapsed_min = (time.monotonic() - t0) / 60.0
                rows_delta = rows - rows_at_start
                rows_per_min = rows_delta / max(elapsed_min, 1e-6)

                eta_min: float | None = None
                if args.target > 0 and rows_per_min > 0:
                    remaining = args.target - rows
                    if remaining > 0:
                        eta_min = remaining / rows_per_min

                # ----------------------------------------------------------------
                # Print dashboard
                # ----------------------------------------------------------------
                dashboard = _format_dashboard(
                    ts=ts,
                    cpu_pct=cpu_pct,
                    load1=load1,
                    load5=load5,
                    ram_pct=ram_pct,
                    ram_used_gb=ram_used_gb,
                    ram_total_gb=ram_total_gb,
                    disk_out_free=disk_out_free,
                    disk_out_total=disk_out_total,
                    disk_scratch_free=disk_scratch_free,
                    disk_scratch_total=disk_scratch_total,
                    net_recv_mbps=net_recv_mbps,
                    gpu_util=gpu_util,
                    gpu_mem=gpu_mem,
                    workers_alive=workers_alive,
                    num_workers=args.workers,
                    rows=rows,
                    completed=completed,
                    rows_per_min=rows_per_min,
                    eta_min=eta_min,
                )
                print(dashboard, flush=True)

                # ----------------------------------------------------------------
                # Append to CSV log
                # ----------------------------------------------------------------
                if csv_writer is not None:
                    try:
                        gpu_util_csv = gpu_util.replace("%", "").split()[0] if gpu_util != "n/a" else ""
                        gpu_mem_csv = gpu_mem.split("/")[0] if gpu_mem != "n/a" else ""
                        csv_writer.writerow([
                            ts,
                            f"{cpu_pct:.1f}",
                            f"{load1:.2f}",
                            f"{ram_pct:.1f}",
                            f"{ram_used_gb:.2f}",
                            f"{disk_out_free:.1f}" if disk_out_free is not None else "",
                            f"{disk_scratch_free:.1f}" if disk_scratch_free is not None else "",
                            f"{net_recv_mbps:.3f}",
                            gpu_util_csv,
                            gpu_mem_csv,
                            workers_alive,
                            rows,
                            completed,
                            f"{rows_per_min:.2f}",
                            f"{eta_min:.1f}" if eta_min is not None else "",
                        ])
                        log_fh.flush()
                    except Exception as csv_exc:  # noqa: BLE001
                        print(f"[monitor] WARNING: CSV write failed: {csv_exc}", file=sys.stderr)

                # ----------------------------------------------------------------
                # Auto-stop logic: 3 consecutive zero-worker samples after boot
                # ----------------------------------------------------------------
                if ever_had_workers and workers_alive == 0:
                    zero_worker_streak += 1
                    if zero_worker_streak >= 3:
                        print(
                            "[monitor] All workers finished (0 alive for 3 samples) — exiting.",
                            flush=True,
                        )
                        break
                else:
                    zero_worker_streak = 0

            except Exception as sample_exc:  # noqa: BLE001
                print(f"[monitor] WARNING: sample error (continuing): {sample_exc}",
                      file=sys.stderr, flush=True)

            # Wait for next sample (check sentinel every second so we stop promptly)
            deadline = time.monotonic() + args.interval
            while time.monotonic() < deadline:
                if stop_sentinel.exists():
                    break
                time.sleep(min(1.0, deadline - time.monotonic()))

    finally:
        if log_fh is not None:
            log_fh.close()
        print("[monitor] done.", flush=True)


if __name__ == "__main__":
    main()
