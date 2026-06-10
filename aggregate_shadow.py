"""Aggregate all shadow_compare run files (local + GitHub-Actions gha_data/) into one
per-variant comparison, with the RIGHT statistics.

Each shadow run writes window rows: {"ws":..,"resolved_up":..,"<variant>":{"net","fills"},..}.
Because every variant sees the SAME windows, the per-window outcome variance is shared and
swamps the cumulative-total spread. So the powerful test is PAIRED: for each variant compute
the per-window (variant_net - baseline_net), and t = mean/(std/sqrt(n)). That cancels the
window effect and is far more sensitive than comparing totals. Windows are de-duped by `(asset, tenor, ws)`.

    python aggregate_shadow.py
"""
from __future__ import annotations

import json
import math

from dataio import jl_glob, jl_open


def main():
    # Canonical live corpus = the run-tagged GHA files: BOTH eras -- legacy single-asset
    # (shadow_windows_r*.jsonl) AND multi-asset (shadow_windows_<asset><tenor>m_*.jsonl[.gz]).
    # (The old glob missed every multi-asset file -> SUMMARY.txt was frozen at the pre-multi era.)
    # The bare root-level shadow_windows.jsonl is a pre-GHA local smoke test; excluded.
    files = sorted(set(jl_glob("gha_data/shadow_windows_*.jsonl")))
    if not files:                                   # local fallback when no GHA data yet
        files = sorted(jl_glob("shadow_windows*.jsonl"))
    by_ws = {}        # (asset, tenor, ws) -> {variant: net}; dedupe windows across runs.
    # KEY FIX: dedupe by (asset, tenor, ws), NOT ws alone -- the 4 assets share identical epoch
    # window-starts, so a ws-only key silently discarded 3 of 4 assets per window ("first wins").
    for fp in files:
        for line in jl_open(fp):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            ws = row.get("ws")
            if ws is None or row.get("resolved_up") is None:    # skip tombstones (unresolved)
                continue
            slot = by_ws.setdefault((row.get("asset", "btc"), row.get("tenor_min", 15), ws), {})
            for k, v in row.items():
                if isinstance(v, dict) and "net" in v:
                    slot.setdefault(k, (v["net"], v.get("gross", float("nan"))))   # (net, GROSS) ; first wins
    n = len(by_ws)
    if n == 0:
        print("no shadow windows yet."); return
    variants = sorted({k for s in by_ws.values() for k in s})
    base = "baseline"
    print(f"shadow comparison over {n} de-duped windows | files={len(files)}\n")
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


if __name__ == "__main__":
    main()
