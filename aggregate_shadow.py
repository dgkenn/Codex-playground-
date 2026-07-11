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
from datetime import datetime, timezone

from dataio import jl_glob, jl_open

# The currently-deployed live variant (SWITCH.md / CLAUDE.md: the arm actually taking real fills).
# Decay watch (below) tracks THIS one specifically -- everything else is shadow-only research.
DEPLOYED = "micro_gate"


def _utc_date(ws):
    """UTC calendar date of a window-start epoch, for day-clustering (same-day windows share a
    regime: one BTC trend, one vol backdrop -- they are NOT independent draws)."""
    return datetime.fromtimestamp(ws, timezone.utc).strftime("%Y-%m-%d")


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

    # ---- regime split (av_stoikov / mo_size), 2-bucket above/below median --------------------
    # SKIPPED: inspected shadow_compare.py's window-record emit (try_settle()'s `row = {...}`) --
    # the only keys beyond "ts"/"ws"/"resolved_up"/"asset"/"tenor_min"/variant-attribution dicts are
    # "coverage" and "audit" (both metadata, not regime signal). "av_stoikov" and "mo_size" are
    # STRATEGY/variant NAMES in strategies.py, not numeric per-window fields -- there is nothing to
    # bucket by median on. Per-fill records (fills_*.jsonl) do carry richer fields, but those are a
    # different, unaggregated file this script does not read. No regime split added.


if __name__ == "__main__":
    main()
