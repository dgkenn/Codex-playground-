"""Aggregate all shadow_compare run files (local + GitHub-Actions gha_data/) into one
per-variant comparison, with the RIGHT statistics.

Each shadow run writes window rows: {"ws":..,"resolved_up":..,"<variant>":{"net","fills"},..}.
Because every variant sees the SAME windows, the per-window outcome variance is shared and
swamps the cumulative-total spread. So the powerful test is PAIRED: for each variant compute
the per-window (variant_net - baseline_net), and t = mean/(std/sqrt(n)). That cancels the
window effect and is far more sensitive than comparing totals. Windows are de-duped by `ws`.

    python aggregate_shadow.py
"""
from __future__ import annotations

import glob
import json
import math


def main():
    # Canonical live corpus = the run-tagged GHA files only. The bare root-level
    # shadow_windows.jsonl is a pre-GHA local smoke test (different session/regime);
    # pooling it with the live run would contaminate inference, so it is excluded.
    files = sorted(glob.glob("gha_data/shadow_windows_r*.jsonl"))
    if not files:                                   # local fallback when no GHA data yet
        files = sorted(glob.glob("shadow_windows*.jsonl"))
    by_ws = {}                          # ws -> {variant: net}; dedupe windows across runs
    for fp in files:
        for line in open(fp):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            ws = row.get("ws")
            if ws is None:
                continue
            slot = by_ws.setdefault(ws, {})
            for k, v in row.items():
                if isinstance(v, dict) and "net" in v:
                    slot.setdefault(k, v["net"])           # first occurrence wins (dedupe)
    n = len(by_ws)
    if n == 0:
        print("no shadow windows yet."); return
    variants = sorted({k for s in by_ws.values() for k in s})
    base = "baseline"
    print(f"shadow comparison over {n} de-duped windows | files={len(files)}\n")
    rows = []
    for v in variants:
        nets = [s[v] for s in by_ws.values() if v in s]
        tot = sum(nets); m = tot / len(nets)
        # paired vs baseline over shared windows
        pairs = [s[v] - s[base] for s in by_ws.values() if v in s and base in s]
        if len(pairs) >= 2 and v != base:
            dm = sum(pairs) / len(pairs)
            sd = (sum((x - dm) ** 2 for x in pairs) / (len(pairs) - 1)) ** 0.5
            t = dm / (sd / math.sqrt(len(pairs))) if sd > 0 else float("nan")
        else:
            dm = t = float("nan")
        rows.append((tot, v, len(nets), m, dm, t))
    rows.sort(reverse=True)
    print(f"{'variant':>12} {'net_total':>10} {'n':>4} {'net/win':>8} {'Δvs base/win':>13} {'paired t':>9}")
    for tot, v, nv, m, dm, t in rows:
        ts = "" if v == base else f"{dm:+.3f}" if dm == dm else "n/a"
        tt = "" if v == base else (f"{t:+.2f}" if t == t else "n/a")
        print(f"{v:>12} {tot:>+10.2f} {nv:>4} {m:>+8.3f} {ts:>13} {tt:>9}")
    print(f"\nRead: paired t is the variant's per-window edge OVER baseline (shared windows). "
          f"|t|>2 ~ notable, |t|>2.6 ~ solid; n={n} so anything below that is still noise.")
    print("Totals alone mislead -- they ride the shared window outcomes; the paired column is the signal.")


if __name__ == "__main__":
    main()
