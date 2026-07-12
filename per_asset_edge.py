#!/usr/bin/env python3
"""per_asset_edge.py -- per-asset forward-test verdict for the two winner shadow arms
(av_stoikov, mo_size) vs baseline, across the full gha-data record, for all four assets the
shadow A/B tracks (btc/eth/sol/xrp). This is the evidence base for the live-bot expansion
decision in LIVE_EXPANSION.md.

Why per-asset, not pooled: aggregate_shadow.py's per-asset table (added for the same reason)
shows a variant's edge can be concentrated in one asset -- thinner alt books mean different
fill/toxicity dynamics per asset. The live bot currently trades ONLY btc; before adding a
second asset we need each candidate's OWN numbers, not btc's edge diluting/inflating a pooled
average.

Key trap this script is built to catch: a variant can beat baseline (positive delta) while
BOTH are net-negative in absolute terms -- i.e. "less bad than baseline" is not "profitable
enough to trade with real money." We print both the paired delta AND the absolute net/win
level, and flag the split explicitly.

Data source: the `gha-data` branch (NOT this code branch -- shadow telemetry is kept off the
code branch on purpose, see watch_continuity.py). This script shallow-fetches it read-only
(--depth=1, no working-tree checkout) and reads the ~4000 shadow_windows_kalshi_<asset>15m_*
blobs directly via one `git cat-file --batch` process -- fast, and it avoids materializing the
multi-GB gha_data tree (book/fills/ladders snapshots this script doesn't need) that a full
`git archive` or checkout of the branch would pull.

    python per_asset_edge.py                 # fetches gha-data fresh, prints the verdict table
    python per_asset_edge.py --ref <sha>      # reuse an already-fetched ref (skip the fetch)
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone

REMOTE_BRANCH = "gha-data"
ASSETS = ["btc", "eth", "sol", "xrp"]
WINNERS = ["av_stoikov", "mo_size"]
BASE = "baseline"

# Verdict thresholds -- deliberately explicit/tunable, not buried in the logic below.
T_BAR = 2.0          # day-clustered |t| considered "real" (aggregate_shadow.py's own bar)
DAYS_POS_BAR = 0.60  # fraction of days the edge must be on the right side of zero
MIN_DAYS = 10        # need enough day-observations for the t-test to mean anything
MIN_FILLS_PER_WIN = 1.0   # mean fills/window below this = "can't actually get filled here"


def _run(*args, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], input=input_bytes, capture_output=True, check=True)


def fetch_ref() -> str:
    """Shallow-fetch the gha-data branch tip (no checkout); returns the commit sha."""
    subprocess.run(["git", "fetch", "--depth=1", "origin", REMOTE_BRANCH], capture_output=True, check=True)
    return _run("rev-parse", "FETCH_HEAD").stdout.decode().strip()


def list_shadow_paths(ref: str) -> list[str]:
    out = _run("ls-tree", "-r", "--name-only", ref, "--", "gha_data").stdout.decode()
    return [p for p in out.splitlines() if "/shadow_windows_kalshi_" in p]


def read_blobs(ref: str, paths: list[str]) -> dict[str, str]:
    """One `git cat-file --batch` process streams every blob's content -- far cheaper than
    thousands of individual `git show` subprocess spawns for ~4000 files."""
    spec = ("\n".join(f"{ref}:{p}" for p in paths) + "\n").encode()
    out = _run("cat-file", "--batch", input_bytes=spec).stdout
    results: dict[str, str] = {}
    i, n, pi = 0, len(out), 0
    while i < n and pi < len(paths):
        nl = out.index(b"\n", i)
        header = out[i:nl].decode(errors="replace")
        parts = header.split()
        if len(parts) < 3:               # "<oid> missing"
            i = nl + 1
            pi += 1
            continue
        size = int(parts[2])
        start = nl + 1
        results[paths[pi]] = out[start:start + size].decode("utf-8", "replace")
        i = start + size + 1             # skip the trailing newline git appends after content
        pi += 1
    return results


def _utc_date(ws: float) -> str:
    return datetime.fromtimestamp(ws, timezone.utc).strftime("%Y-%m-%d")


def load_windows(ref: str) -> dict[tuple[str, int, int], dict]:
    """(asset, tenor, ws) -> {variant: (net, fills)}; first-wins de-dupe across overlapping
    run files, matching aggregate_shadow.py's convention so the two tools agree."""
    paths = list_shadow_paths(ref)
    by_ws: dict[tuple[str, int, int], dict] = {}
    blobs = read_blobs(ref, paths)
    for path, content in blobs.items():
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            ws = row.get("ws")
            if ws is None or row.get("resolved_up") is None:      # skip unresolved tombstones
                continue
            asset = row.get("asset", "btc")
            key = (asset, row.get("tenor_min", 15), ws)
            slot = by_ws.setdefault(key, {})
            for k, v in row.items():
                if isinstance(v, dict) and "net" in v and k not in slot:
                    slot[k] = (v["net"], v.get("fills", 0))
    return by_ws


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def _day_tstat(day_means: dict[str, float]):
    n_days = len(day_means)
    if n_days == 0:
        return float("nan"), float("nan"), 0, 0
    vals = list(day_means.values())
    m = _mean(vals)
    pos = sum(1 for x in vals if x > 0)
    if n_days >= 2:
        sd = (sum((x - m) ** 2 for x in vals) / (n_days - 1)) ** 0.5
        t = m / (sd / math.sqrt(n_days)) if sd > 0 else float("nan")
    else:
        t = float("nan")
    return m, t, pos, n_days


def per_asset_stats(by_ws: dict) -> dict:
    """asset -> arm -> stats dict, plus asset -> 'n_windows' / 'n_days'."""
    windows_by_asset: dict[str, list] = {}
    for (asset, tenor, ws), slot in by_ws.items():
        windows_by_asset.setdefault(asset, []).append((ws, slot))

    out = {}
    for asset in ASSETS:
        wins = windows_by_asset.get(asset, [])
        base_present = [(ws, s) for ws, s in wins if BASE in s]
        days_all = sorted({_utc_date(ws) for ws, _ in base_present})
        asset_stats = {
            "n_windows": len(base_present),
            "n_days": len(days_all),
            "arms": {},
        }
        for v in WINNERS:
            pairs = [(ws, s[v][0] - s[BASE][0]) for ws, s in base_present if v in s]
            abs_nets = [s[v][0] for ws, s in base_present if v in s]
            fills = [s[v][1] for ws, s in base_present if v in s]
            base_fills = [s[BASE][1] for ws, s in base_present if v in s]

            day_deltas: dict[str, list] = {}
            for ws, d in pairs:
                day_deltas.setdefault(_utc_date(ws), []).append(d)
            day_means = {d: _mean(xs) for d, xs in day_deltas.items()}
            mean_d, t_d, pos_d, n_days = _day_tstat(day_means)

            asset_stats["arms"][v] = {
                "n": len(pairs),
                "mean_delta": _mean([d for _, d in pairs]),
                "day_mean_delta": mean_d,
                "day_t": t_d,
                "days_pos": pos_d,
                "n_days": n_days,
                "abs_net_per_win": _mean(abs_nets),
                "mean_fills": _mean(fills),
                "mean_fills_baseline": _mean(base_fills),
                "total_fills": sum(fills),
            }
        out[asset] = asset_stats
    return out


def verdict(asset_stats: dict) -> tuple[str, list[str]]:
    """EXPAND/HOLD + reasons, applied per-asset across BOTH winner arms."""
    reasons = []
    if asset_stats["n_windows"] == 0:
        return "HOLD", ["no shadow data for this asset"]

    clears = []
    for v in WINNERS:
        a = asset_stats["arms"][v]
        if a["n_days"] < MIN_DAYS:
            reasons.append(f"{v}: only {a['n_days']}d of paired data (<{MIN_DAYS} bar)")
            continue
        t_ok = a["day_t"] == a["day_t"] and a["day_t"] >= T_BAR
        days_ok = a["n_days"] > 0 and (a["days_pos"] / a["n_days"]) >= DAYS_POS_BAR
        abs_ok = a["abs_net_per_win"] == a["abs_net_per_win"] and a["abs_net_per_win"] > 0
        fills_ok = a["mean_fills"] == a["mean_fills"] and a["mean_fills"] >= MIN_FILLS_PER_WIN
        if t_ok and days_ok and abs_ok and fills_ok:
            clears.append(v)
        else:
            why = []
            if not t_ok:
                why.append(f"day-t={a['day_t']:+.2f}<{T_BAR:g}" if a["day_t"] == a["day_t"] else "day-t=n/a")
            if not days_ok:
                why.append(f"days+={a['days_pos']}/{a['n_days']}<{DAYS_POS_BAR:.0%}")
            if not abs_ok:
                why.append(f"ABS net/win={a['abs_net_per_win']:+.3f} (delta positive but LEVEL negative)"
                            if a["mean_delta"] > 0 else f"abs net/win={a['abs_net_per_win']:+.3f}<=0")
            if not fills_ok:
                why.append(f"mean fills/win={a['mean_fills']:.2f}<{MIN_FILLS_PER_WIN:g} (too thin to fill)")
            reasons.append(f"{v}: " + ", ".join(why))

    if clears:
        reasons = [f"{v} clears (day-t={asset_stats['arms'][v]['day_t']:+.2f}, "
                   f"days+={asset_stats['arms'][v]['days_pos']}/{asset_stats['arms'][v]['n_days']}, "
                   f"abs net/win={asset_stats['arms'][v]['abs_net_per_win']:+.3f})" for v in clears] + reasons[len(clears):]
        return "EXPAND", reasons
    return "HOLD", reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=None, help="reuse an already-fetched gha-data ref (skips the fetch)")
    args = ap.parse_args()

    ref = args.ref or fetch_ref()
    print(f"gha-data ref: {ref}")
    by_ws = load_windows(ref)
    if not by_ws:
        print("no shadow windows found -- aborting.")
        sys.exit(1)
    n_days_total = len({_utc_date(ws) for (_a, _t, ws) in by_ws.keys()})
    print(f"{len(by_ws)} de-duped windows across {n_days_total} UTC days, assets={ASSETS}\n")

    stats = per_asset_stats(by_ws)

    for v in WINNERS:
        print(f"=== arm: {v}  (vs baseline; paired per-window delta) ===")
        hdr = (f"{'asset':>6} {'n win':>6} {'n days':>7} {'mean Δ/win':>11} {'day-t':>7} "
               f"{'days+':>8} {'ABS net/win':>12} {'mean fills':>11} {'base fills':>11}")
        print(hdr)
        for asset in ASSETS:
            a = stats[asset]["arms"][v]
            dt = f"{a['day_t']:+.2f}" if a["day_t"] == a["day_t"] else "n/a"
            dp = f"{a['days_pos']}/{a['n_days']}" if a["n_days"] else "0/0"
            flag = ""
            if a["mean_delta"] == a["mean_delta"] and a["mean_delta"] > 0 and \
               a["abs_net_per_win"] == a["abs_net_per_win"] and a["abs_net_per_win"] < 0:
                flag = "  <-- Δ+ but ABS level NEGATIVE"
            print(f"{asset:>6} {a['n']:>6} {a['n_days']:>7} {a['mean_delta']:>+11.3f} {dt:>7} "
                  f"{dp:>8} {a['abs_net_per_win']:>+12.3f} {a['mean_fills']:>11.2f} "
                  f"{a['mean_fills_baseline']:>11.2f}{flag}")
        print()

    print("=== per-asset window counts (baseline-resolved) ===")
    for asset in ASSETS:
        print(f"  {asset:>4}: n_windows={stats[asset]['n_windows']:>5}  n_days={stats[asset]['n_days']:>3}")
    print()

    print("=== VERDICT: EXPAND / HOLD ===")
    verdicts = {}
    for asset in ASSETS:
        vd, reasons = verdict(stats[asset])
        verdicts[asset] = (vd, reasons)
        print(f"\n  {asset.upper():>4}: {vd}")
        for r in reasons:
            print(f"       - {r}")

    print("\nRead: day-t = day-clustered t-stat of the paired delta vs baseline (|t|>=2 = real, not "
          "noise). days+ = fraction of UTC days the arm beat baseline that day. ABS net/win = the "
          "arm's own mean net P&L per window (NOT vs baseline) -- an asset can show Δ+ while this is "
          "negative, meaning the arm is 'less bad than baseline' while still losing money outright; "
          "that is flagged and treated as a HOLD reason, not an EXPAND signal. mean fills = average "
          "fill count per 15m window for that arm (an edge nobody can get filled on isn't tradeable).")
    return verdicts


if __name__ == "__main__":
    main()
