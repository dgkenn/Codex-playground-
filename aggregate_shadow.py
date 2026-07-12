"""Aggregate all shadow_compare run files (local + GitHub-Actions gha_data/) into one
per-variant comparison, with the RIGHT statistics.

Each shadow run writes window rows: {"ws":..,"resolved_up":..,"<variant>":{"net","fills"},..}.
Because every variant sees the SAME windows, the per-window outcome variance is shared and
swamps the cumulative-total spread. So the powerful test is PAIRED: for each variant compute
the per-window (variant_net - baseline_net), and t = mean/(std/sqrt(n)). That cancels the
window effect and is far more sensitive than comparing totals. Windows are de-duped by `(asset, tenor, ws)`.

RUNTIME-DATA-AVAILABILITY FIX (see _remote_recent_shadow_blobs docstring below): paper-collect.yml
runs `python aggregate_shadow.py > gha_data/SUMMARY.txt` in its "per-run summary" step, which
executes BEFORE the data-committing step and against a `gha_data/` that was just `rm -rf`'d and
repopulated with ONLY that one run's ~40 minutes of fresh files (flat, no date subdirs -- the
date-partitioned multi-run history lives exclusively on the `gha-data` branch and only lands
under `gha_data/<date>/` in the LATER commit step). So the local glob alone -- even though it
correctly recurses into date subdirs and de-dupes by (asset,tenor,ws) -- only ever SAW one run's
~8-12 windows at runtime, not the day's ~340. This was mistaken for a glob bug; it is actually a
data-availability-at-runtime bug. The fix pulls the trailing TRAILING_DAYS of already-committed
history straight out of `gha-data` branch git objects (no working-tree/index writes) and merges
it in before de-duping, so the "daily rollup" actually rolls up the day.

    python aggregate_shadow.py
    python aggregate_shadow.py --no-fetch          # local-only (dev/offline; skip the gha-data pull)
    python aggregate_shadow.py --dir PATH [--dir PATH2 ...]   # scan extra local roots (testing)
    python aggregate_shadow.py --selftest          # synthetic two-runid/two-asset/one-day fixture
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

from dataio import jl_glob, jl_open

# The currently-deployed live variant (SWITCH.md / CLAUDE.md: the arm actually taking real fills).
# Decay watch (below) tracks THIS one specifically -- everything else is shadow-only research.
DEPLOYED = "micro_gate"

GHA_REMOTE_BRANCH = "gha-data"
# Bounds the remote pull so cost doesn't grow as the gha-data branch accumulates months of
# history (collect.yml date-partitions the branch for exactly this reason -- see its header
# comment on why no directory is allowed to accumulate unboundedly). 30 UTC days comfortably
# covers the 14-day decay-watch window below with margin for the day-clustered leaderboard to
# have enough days to be meaningful.
TRAILING_DAYS = 30
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _utc_date(ws):
    """UTC calendar date of a window-start epoch, for day-clustering (same-day windows share a
    regime: one BTC trend, one vol backdrop -- they are NOT independent draws)."""
    return datetime.fromtimestamp(ws, timezone.utc).strftime("%Y-%m-%d")


# ----------------------------------------------------------------------------------------------
# Corpus assembly: local files + (best-effort) trailing history from the gha-data branch.
# ----------------------------------------------------------------------------------------------

def _ingest_lines(lines, by_ws: dict) -> int:
    """Parse shadow-window JSONL lines into `by_ws` ((asset,tenor,ws) -> {variant:(net,gross)}),
    de-duping with first-wins semantics (same convention as promotion_check.py / per_asset_edge.py
    / dashboard.py, so every consumer of this corpus agrees on it). Returns rows ingested."""
    n = 0
    for line in lines:
        line = line.strip() if isinstance(line, str) else line.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        ws = row.get("ws")
        if ws is None or row.get("resolved_up") is None:    # skip tombstones (unresolved)
            continue
        asset = row.get("asset", "btc")
        slot = by_ws.setdefault((asset, row.get("tenor_min", 15), ws), {})
        slot.setdefault("_asset", asset)          # per-asset breakdown table (below)
        if row.get("regime") is not None and "_regime" not in slot:
            slot["_regime"] = row["regime"]        # regime split table (below); missing on legacy rows
        for k, v in row.items():
            if isinstance(v, dict) and "net" in v:
                slot.setdefault(k, (v["net"], v.get("gross", float("nan"))))   # (net, GROSS) ; first wins
        n += 1
    return n


def _local_has_day_dirs(root: str) -> bool:
    """True if `root` already contains date-named subdirs (i.e. a full/partial gha-data checkout
    is already on disk -- e.g. a dev box, or strategy-alert.yml-style `git checkout origin/gha-data
    -- gha_data`). In that case the remote pull below would be redundant network+CPU work."""
    return os.path.isdir(root) and any(_DATE_RE.match(n) for n in os.listdir(root))


def _run_git(*args, input_bytes: bytes | None = None):
    return subprocess.run(["git", *args], input=input_bytes, capture_output=True, timeout=90)


def _parse_batch(out: bytes, paths: list[str]) -> list[tuple[str, bytes]]:
    """Split a `git cat-file --batch` stream into (path, raw_bytes) pairs. Each entry is framed
    as `<oid> blob <size>\\n<content>\\n` (or `<oid> missing\\n` if the path didn't resolve)."""
    results = []
    i, n, pi = 0, len(out), 0
    while i < n and pi < len(paths):
        nl = out.index(b"\n", i)
        header = out[i:nl].decode(errors="replace")
        parts = header.split()
        if len(parts) < 3:                # "<oid> missing"
            i = nl + 1
            pi += 1
            continue
        size = int(parts[2])
        start = nl + 1
        results.append((paths[pi], out[start:start + size]))
        i = start + size + 1              # skip git's trailing newline after the blob content
        pi += 1
    return results


def _remote_recent_shadow_blobs(branch: str = GHA_REMOTE_BRANCH, days: int = TRAILING_DAYS):
    """Best-effort: pull the trailing `days` UTC date-dirs' shadow_windows_* files straight out of
    git objects on the committed `gha-data` branch -- WITHOUT touching the working tree or index
    (one `git fetch` + one `git cat-file --batch`; same blob-streaming technique per_asset_edge.py
    uses for the same branch). Returns a list of (path, text) pairs; [] on ANY failure (offline,
    no remote, sandboxed test env, etc -- this must never crash the aggregation; local-only data
    is the graceful fallback, exactly like the pre-existing "no GHA data yet" local fallback)."""
    try:
        if _run_git("fetch", "--depth=1", "origin", branch).returncode != 0:
            return []
        ref = "FETCH_HEAD"
        days_out = _run_git("ls-tree", "-d", "--name-only", f"{ref}:gha_data")
        if days_out.returncode != 0:
            return []
        all_days = sorted(n for n in days_out.stdout.decode(errors="replace").splitlines()
                           if _DATE_RE.match(n))
        recent = all_days[-days:]
        if not recent:
            return []
        paths_out = _run_git("ls-tree", "-r", "--name-only", ref, "--",
                              *[f"gha_data/{d}" for d in recent])
        if paths_out.returncode != 0:
            return []
        paths = [p for p in paths_out.stdout.decode(errors="replace").splitlines()
                 if os.path.basename(p).startswith("shadow_windows_")
                 and (p.endswith(".jsonl") or p.endswith(".jsonl.gz"))]
        if not paths:
            return []
        spec = ("\n".join(f"{ref}:{p}" for p in paths) + "\n").encode()
        batch = _run_git("cat-file", "--batch", input_bytes=spec)
        if batch.returncode != 0:
            return []
        out = []
        for path, raw in _parse_batch(batch.stdout, paths):
            try:
                text = gzip.decompress(raw).decode("utf-8", "replace") if path.endswith(".gz") \
                    else raw.decode("utf-8", "replace")
            except Exception:
                continue
            out.append((path, text))
        return out
    except Exception:
        return []


def build_corpus(roots: list[str] = ("gha_data",), no_fetch: bool = False,
                  days: int = TRAILING_DAYS) -> tuple[dict, int]:
    """Assemble the de-duped (asset,tenor,ws)->{variant:(net,gross)} corpus from local `roots`
    (each scanned recursively into date subdirs via jl_glob; defaults to just "gha_data") and --
    unless a full local checkout is already present under one of `roots` or `no_fetch` -- the
    trailing `days` of already-committed history pulled read-only from the gha-data branch.
    Returns (by_ws, n_sources) where n_sources counts every individual file/blob that contributed
    at least one row. `roots` is caller-controlled (not implicitly "gha_data" + extras) so tests
    can point it at an isolated fixture directory without also picking up a real local gha_data/."""
    roots = list(roots)
    files = sorted(set().union(*(set(jl_glob(os.path.join(r, "shadow_windows_*.jsonl")))
                                  for r in roots)) if roots else set())
    by_ws: dict = {}
    n_sources = 0
    for fp in files:
        rows = _ingest_lines(jl_open(fp), by_ws)
        if rows:
            n_sources += 1

    have_local_history = any(_local_has_day_dirs(r) for r in roots)
    if not no_fetch and not have_local_history:
        for _path, text in _remote_recent_shadow_blobs(days=days):
            rows = _ingest_lines(text.splitlines(), by_ws)
            if rows:
                n_sources += 1

    if not files and not by_ws:                        # local fallback when no GHA data yet at all
        for fp in sorted(jl_glob("shadow_windows*.jsonl")):
            rows = _ingest_lines(jl_open(fp), by_ws)
            if rows:
                n_sources += 1

    return by_ws, n_sources


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", action="append", default=[], dest="extra_dirs",
                     help="extra local root(s) to scan for shadow_windows_*.jsonl (repeatable)")
    ap.add_argument("--no-fetch", action="store_true",
                     help="skip the read-only gha-data branch pull (local files only)")
    ap.add_argument("--days", type=int, default=TRAILING_DAYS,
                     help=f"trailing UTC days to pull from the gha-data branch (default {TRAILING_DAYS})")
    ap.add_argument("--selftest", action="store_true",
                     help="run the built-in synthetic regression fixture and exit (no I/O to gha_data/)")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(_selftest())

    by_ws, n_sources = build_corpus(roots=["gha_data"] + args.extra_dirs,
                                     no_fetch=args.no_fetch, days=args.days)
    _report(by_ws, n_sources)


def _report(by_ws: dict, n_sources: int) -> None:
    n = len(by_ws)
    if n == 0:
        print("no shadow windows yet."); return
    # "_asset"/"_regime" are per-window metadata keys stashed in the same dict as the variant
    # (net, gross) tuples above -- exclude them from the discovered variant-name set.
    variants = sorted({k for s in by_ws.values() for k in s if not k.startswith("_")})
    base = "baseline"
    print(f"shadow comparison over {n} de-duped windows | files={n_sources}\n")
    rows = []
    for v in variants:
        nets = [s[v][0] for s in by_ws.values() if v in s]
        grs = [s[v][1] for s in by_ws.values() if v in s and s[v][1] == s[v][1]]
        tot = sum(nets); m = tot / len(nets)
        gm = sum(grs) / len(grs) if grs else float("nan")            # GROSS/win = edge OUTSIDE the rebate
        if len(grs) >= 2:                                            # gross t vs 0 (window-clustered)
            gsd = (sum((x - gm) ** 2 for x in grs) / (len(grs) - 1)) ** 0.5
            gt = gm / (gsd / math.sqrt(len(grs))) if gsd > 0 else float("nan")
        else:
            gt = float("nan")
        # paired NET vs baseline over shared windows
        pairs = [s[v][0] - s[base][0] for s in by_ws.values() if v in s and base in s]
        if len(pairs) >= 2 and v != base:
            dm = sum(pairs) / len(pairs)
            sd = (sum((x - dm) ** 2 for x in pairs) / (len(pairs) - 1)) ** 0.5
            t = dm / (sd / math.sqrt(len(pairs))) if sd > 0 else float("nan")
        else:
            dm = t = float("nan")
        rows.append((tot, v, len(nets), m, dm, t, gm, gt))
    rows.sort(reverse=True)
    print(f"{'variant':>12} {'net/win':>8} {'Δvs base':>9} {'paired t':>9} {'GROSS/win':>9} {'gross t':>8}")
    for tot, v, nv, m, dm, t, gm, gt in rows:
        ts = "" if v == base else (f"{dm:+.3f}" if dm == dm else "n/a")
        tt = "" if v == base else (f"{t:+.2f}" if t == t else "n/a")
        flag = " <edge>" if (gm == gm and gm > 0) else ""
        print(f"{v:>12} {m:>+8.3f} {ts:>9} {tt:>9} {gm:>+9.3f} {gt:>+8.2f}{flag}")
    print(f"\nRead: paired t = net edge OVER baseline (rebate-inclusive). GROSS/win = trade P&L EXCLUDING "
          f"the rebate = the edge OUTSIDE rebates; gross t vs 0, |t|>2 notable. n={n}.")
    print("Only positive-GROSS variants have an edge beyond rebate harvesting (the micro-gate family).")

    # ---- day-clustered stats -----------------------------------------------------------------
    # Windows sharing a UTC date share a regime (one BTC trend, one vol backdrop), so their
    # per-window paired deltas are correlated -- treating each window as an independent draw
    # (the table above) is anti-conservative. Cluster to one observation per (variant, day):
    # the day's MEAN delta vs baseline, then run the t-test ACROSS days.
    day_variant_deltas = {}          # date -> variant -> [paired deltas within that day]
    all_days = set()
    for (asset, tenor, ws), s in by_ws.items():
        d = _utc_date(ws)
        all_days.add(d)
        if base not in s:
            continue
        for v in variants:
            if v == base or v not in s:
                continue
            day_variant_deltas.setdefault(d, {}).setdefault(v, []).append(s[v][0] - s[base][0])

    variant_day_means = {}           # variant -> {date: mean delta for that day}
    for d, vd in day_variant_deltas.items():
        for v, deltas in vd.items():
            variant_day_means.setdefault(v, {})[d] = sum(deltas) / len(deltas)

    def _day_stats(day_means: dict):
        """mean/sd/t ACROSS days (n = n_days, not n_windows) + days-positive fraction."""
        n_days = len(day_means)
        if n_days == 0:
            return None
        vals = list(day_means.values())
        mean_d = sum(vals) / n_days
        pos = sum(1 for x in vals if x > 0)
        if n_days >= 2:
            sd_d = (sum((x - mean_d) ** 2 for x in vals) / (n_days - 1)) ** 0.5
            t_d = mean_d / (sd_d / math.sqrt(n_days)) if sd_d > 0 else float("nan")
        else:
            t_d = float("nan")
        return mean_d, t_d, pos, n_days

    print("\nday-clustered (windows within a day share regime)")
    print(f"{'variant':>12} {'n_days':>6} {'mean Δ/day':>10} {'clust t':>9} {'days+':>7}")
    day_rows = []
    for v in variants:
        if v == base:
            continue
        stats = _day_stats(variant_day_means.get(v, {}))
        if stats is None:
            continue
        day_rows.append((stats[0], v, *stats))
    day_rows.sort(reverse=True)
    for mean_d, v, _mean_d2, t_d, pos, n_days in day_rows:
        t_str = f"{t_d:+.2f}" if t_d == t_d else "n/a"
        print(f"{v:>12} {n_days:>6} {mean_d:>+10.3f} {t_str:>9} {f'{pos}/{n_days}':>7}")

    # ---- decay watch: is the DEPLOYED edge still alive? --------------------------------------
    # Two failure modes over the trailing 14 UTC days actually present in the data:
    #   (a) INERT: the gate isn't firing differently from baseline any more (mean |Δ| ~ 0) --
    #       something upstream (feed, market structure) neutered the trigger condition.
    #   (b) DECAYED: the edge flipped sign and is now day-clustered-significantly NEGATIVE.
    last14 = set(sorted(all_days)[-14:])
    dep_deltas_14 = [s[DEPLOYED][0] - s[base][0] for (asset, tenor, ws), s in by_ws.items()
                      if DEPLOYED in s and base in s and _utc_date(ws) in last14]
    dep_day_means_14 = {d: m for d, m in variant_day_means.get(DEPLOYED, {}).items() if d in last14}
    dstats = _day_stats(dep_day_means_14)

    if not dep_deltas_14 or dstats is None:
        print(f"\ndeploy-watch: {DEPLOYED} -- insufficient data in the trailing 14 UTC days to assess "
              f"(n_windows={len(dep_deltas_14)}).")
    else:
        mean_abs = sum(abs(x) for x in dep_deltas_14) / len(dep_deltas_14)
        mean_d, t_d, pos, n_days = dstats
        if mean_abs < 0.01:
            print(f"\nDECAY-ALERT: {DEPLOYED} looks INERT over the last {n_days} UTC days -- "
                  f"mean|Δ vs baseline|={mean_abs:.4f} < 0.01 across {len(dep_deltas_14)} windows "
                  f"(gate is barely diverging from baseline; it may not be firing).")
        elif t_d == t_d and t_d < -2:
            print(f"\nDECAY-ALERT: {DEPLOYED} looks DECAYED over the last {n_days} UTC days -- "
                  f"day-clustered t={t_d:+.2f} < -2 (mean Δ/day={mean_d:+.4f}, days+={pos}/{n_days}); "
                  f"the edge has likely reversed.")
        else:
            print(f"\ndeploy-watch: {DEPLOYED} OK -- mean|Δ|={mean_abs:.4f} (n={len(dep_deltas_14)} "
                  f"windows), day-clustered t={t_d:+.2f} (days+={pos}/{n_days}) over last {n_days} UTC days.")

    # ---- per-asset breakdown (enabled arms only) ----------------------------------------------
    # Same paired-delta-vs-baseline logic as the top table, sliced by asset -- a variant's edge may
    # be concentrated in one asset (thinner alt books = more/less toxic flow) and that's invisible
    # in the pooled cross-asset numbers above.
    try:
        import strategies
        enabled_names = [s.name for s in strategies.enabled() if s.name != base]
    except Exception:
        enabled_names = [v for v in variants if v != base]   # fallback: everything discovered
    assets = sorted({s["_asset"] for s in by_ws.values() if "_asset" in s})
    if assets and enabled_names:
        print("\nper-asset (enabled arms only): mean paired-Δ vs baseline, n windows")
        header = f"{'variant':>12}" + "".join(f" {a:>14}" for a in assets)
        print(header)
        for v in enabled_names:
            cells = []
            for a in assets:
                pairs = [s[v][0] - s[base][0] for s in by_ws.values()
                         if s.get("_asset") == a and v in s and base in s]
                if pairs:
                    m = sum(pairs) / len(pairs)
                    cells.append(f"{m:+.3f}/n={len(pairs)}")
                else:
                    cells.append("n/a")
            print(f"{v:>12}" + "".join(f" {c:>14}" for c in cells))

    # ---- regime split (av_stoikov / mo_size), 2-bucket above/below median ---------------------
    # Precursor to a regime-router strategy: does the edge concentrate in calm or volatile windows?
    # Median-split on realized mid-price vol (regime.mid_vol, REGIME FIELDS task); rows without a
    # "regime" key (pre-existing data captured before this field existed) are simply excluded --
    # this is additive, not a replacement for the tables above.
    reg_rows = [(s["_regime"].get("mid_vol"), s) for s in by_ws.values()
                if "_regime" in s and s["_regime"].get("mid_vol") is not None]
    if len(reg_rows) >= 4:
        vols = sorted(v for v, _s in reg_rows)
        mid_i = len(vols) // 2
        median_vol = vols[mid_i] if len(vols) % 2 else (vols[mid_i - 1] + vols[mid_i]) / 2.0
        lo = [s for v, s in reg_rows if v <= median_vol]
        hi = [s for v, s in reg_rows if v > median_vol]
        print(f"\nregime split (median mid_vol={median_vol:.6g}, n_lo={len(lo)} n_hi={len(hi)})")
        print(f"{'variant':>12} {'lo-vol Δ':>10} {'n':>5} {'hi-vol Δ':>10} {'n':>5}")
        for v in ("av_stoikov", "mo_size"):
            if v not in variants:
                continue
            lo_pairs = [s[v][0] - s[base][0] for s in lo if v in s and base in s]
            hi_pairs = [s[v][0] - s[base][0] for s in hi if v in s and base in s]
            lo_m = f"{sum(lo_pairs) / len(lo_pairs):+.3f}" if lo_pairs else "n/a"
            hi_m = f"{sum(hi_pairs) / len(hi_pairs):+.3f}" if hi_pairs else "n/a"
            print(f"{v:>12} {lo_m:>10} {len(lo_pairs):>5} {hi_m:>10} {len(hi_pairs):>5}")
    else:
        print(f"\nregime split: insufficient rows with a 'regime' field yet (n={len(reg_rows)}, need >=4).")


# ----------------------------------------------------------------------------------------------
# Self-test: synthetic two-runid/two-asset/one-day fixture, no network, no real gha_data/ I/O.
# Asserts the assembled window count equals the de-duped union across runids/assets, i.e. that
# overlapping runs of the SAME (asset, ws) collapse to one window while distinct (asset, ws)
# pairs across assets/runids all survive -- the exact behavior the under-counting bug broke.
# ----------------------------------------------------------------------------------------------

def _selftest() -> int:
    import shutil

    tmp = tempfile.mkdtemp(prefix="aggregate_shadow_selftest_")
    try:
        day_dir = os.path.join(tmp, "gha_data", "2026-07-01")
        os.makedirs(day_dir, exist_ok=True)

        base_ws = 1782000000     # an arbitrary 15m-aligned epoch
        WS = [base_ws + i * 900 for i in range(6)]     # 6 distinct window-starts

        def row(asset, ws, resolved=True):
            r = {"ws": ws, "asset": asset, "tenor_min": 15,
                 "resolved_up": 1 if resolved else None,
                 "baseline": {"net": 1.0, "gross": 1.0},
                 "micro_gate": {"net": 1.5, "gross": 1.5}}
            return json.dumps(r)

        # runid r1 (btc): windows 0,1,2 ; runid r2 (btc): windows 1,2,3 (1,2 OVERLAP with r1 --
        # must collapse, not double-count) ; runid r1 (eth): windows 0,1 ; runid r3 (eth): windows
        # 4,5 (disjoint, both must survive). One tombstone row (unresolved) must be excluded.
        files = {
            "shadow_windows_kalshi_btc15m_r1.jsonl": [row("btc", WS[0]), row("btc", WS[1]), row("btc", WS[2])],
            "shadow_windows_kalshi_btc15m_r2.jsonl": [row("btc", WS[1]), row("btc", WS[2]), row("btc", WS[3]),
                                                       row("btc", WS[4], resolved=False)],   # tombstone
            "shadow_windows_kalshi_eth15m_r1.jsonl": [row("eth", WS[0]), row("eth", WS[1])],
            "shadow_windows_kalshi_eth15m_r3.jsonl": [row("eth", WS[4]), row("eth", WS[5])],
        }
        for name, lines in files.items():
            with open(os.path.join(day_dir, name), "w") as fh:
                fh.write("\n".join(lines) + "\n")

        # union: btc has WS[0..4] = 5 distinct (asset,ws) pairs (WS[4] tombstone-only -> excluded
        # -> 4 resolved); eth has WS[0],WS[1],WS[4],WS[5] = 4 distinct pairs.
        expected = 4 + 4

        by_ws, n_sources = build_corpus(roots=[os.path.join(tmp, "gha_data")], no_fetch=True)

        ok = True
        detail = []
        if len(by_ws) != expected:
            ok = False
            detail.append(f"window count: got {len(by_ws)}, want {expected}")
        if n_sources != len(files):
            ok = False
            detail.append(f"n_sources: got {n_sources}, want {len(files)}")
        # spot-check: an overlapping (asset,ws) pair present in BOTH r1 and r2 must appear exactly
        # once (dict key identity already guarantees this, but assert the key is present).
        if ("btc", 15, WS[1]) not in by_ws:
            ok = False
            detail.append("overlapping (btc, WS[1]) window missing from the de-duped corpus")
        if ("btc", 15, WS[4]) in by_ws:
            ok = False
            detail.append("tombstone-only window (btc, WS[4]) should have been excluded")

        if ok:
            print(f"SELFTEST PASS: {len(by_ws)} de-duped windows from {n_sources} files "
                  f"(2 assets, overlapping + disjoint runids, one tombstone excluded) -- matches "
                  f"the expected de-duped union.")
            return 0
        else:
            print("SELFTEST FAIL: " + "; ".join(detail))
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
