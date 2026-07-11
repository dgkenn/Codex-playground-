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
            asset = row.get("asset", "btc")
            slot = by_ws.setdefault((asset, row.get("tenor_min", 15), ws), {})
            slot.setdefault("_asset", asset)          # per-asset breakdown table (below)
            if row.get("regime") is not None and "_regime" not in slot:
                slot["_regime"] = row["regime"]        # regime split table (below); missing on legacy rows
            for k, v in row.items():
                if isinstance(v, dict) and "net" in v:
                    slot.setdefault(k, (v["net"], v.get("gross", float("nan"))))   # (net, GROSS) ; first wins
    n = len(by_ws)
    if n == 0:
        print("no shadow windows yet."); return
    # "_asset"/"_regime" are per-window metadata keys stashed in the same dict as the variant
    # (net, gross) tuples above -- exclude them from the discovered variant-name set.
    variants = sorted({k for s in by_ws.values() for k in s if not k.startswith("_")})
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


if __name__ == "__main__":
    main()
