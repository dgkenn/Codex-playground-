"""promotion_check.py -- the PRE-REGISTERED promotion bar (strategies.py, as_markout entry),
implemented exactly as declared BEFORE any data was collected:

    >=14 forward UTC days of paired data vs baseline
    day-clustered t >= 3      (t over the daily MEAN of variant-minus-baseline net, one obs/day --
                                windows within a day share a regime, so window-level t is
                                anti-conservative; see aggregate_shadow.py's day-clustered section)
    gross-positive >= 80% of those days   (day-mean GROSS, i.e. the variant's own P&L excluding the
                                rebate, > 0 -- the edge must exist outside rebate harvesting)
    mean edge >= max(av_stoikov, mo_size) on the SAME days   (a candidate only earns a promotion
                                slot if it beats BOTH current winners over the identical calendar
                                days they all three have data for -- an unfair regime-luck comparison
                                otherwise)

Runs over every ENABLED non-baseline variant strategies.py declares AND that actually appears in the
collected data (variants strategies.py has just added but the collector hasn't run with yet simply
report n_days=0 -- "wait", not an error). ALERT-ONLY: this script never edits strategies.py or any
roster file; promotion is a human/operator decision. It only prints + (optionally) pings Telegram.

    python promotion_check.py

Output: one line per candidate --
    PROMOTE-READY <name> n_days=.. t=.. mean_edge/day=.. gross_pos=.. vs_ref_bar=.. (same_days=..)
    wait <name> n_days=.. t=.. mean_edge/day=.. gross_pos=.. -- <unmet bar(s)>

SECTION 2 -- "per-market challengers" (TASK 2): the global promotion bar above asks "should this
arm replace av_stoikov/mo_size EVERYWHERE". This section asks the narrower question per_market_
champion.py explores on demand -- "does this arm beat av_stoikov head-to-head on ONE asset" -- and
runs it automatically every day so a tailoring opportunity doesn't sit unnoticed until someone
remembers to run the deep-dive script. It reuses per_market_champion.py's own head-to-head day-
clustered stats function and its pre-registered dethronement bar (day-clustered t>=3, days-positive
fraction>=70%, n_days>=10) so the daily line and the on-demand script can never disagree on what
"beats the champion on this asset" means. Data comes from THIS script's own load_windows() (the
same gha_data/ this daily job already has on disk) -- no second git fetch of gha-data.

    per-market <asset> <arm> n_days=.. t=.. days+=.. (..%) mean_delta/win=.. vs av_stoikov
    TAILOR-READY <asset> <arm> n_days=.. t=.. days+=.. (..%) mean_delta/win=.. vs av_stoikov
    insufficient days <asset> <arm> n_days=.. (<5) -- ...

Exit code is always 0 (this is a reporting job, never a CI gate) -- unexpected errors are caught and
printed rather than raised, per notify.py's "never raises into the pipeline" convention.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from dataio import jl_glob, jl_lines

BASELINE = "baseline"
REFERENCE_WINNERS = ("av_stoikov", "mo_size")   # the bar every ensemble/ablation arm must clear
MIN_DAYS = 14
T_BAR = 3.0
GROSS_POS_FRAC = 0.80


def _utc_date(ws: float) -> str:
    """UTC calendar date of a window-start epoch (same day-clustering key as aggregate_shadow.py)."""
    return datetime.fromtimestamp(ws, timezone.utc).strftime("%Y-%m-%d")


def enabled_variants() -> set[str] | None:
    """Names of the currently-enabled roster (strategies.py), or None if it can't be imported (then
    every variant found in the data is treated as a candidate -- degrade gracefully, never crash)."""
    try:
        import strategies
        return {s.name for s in strategies.enabled()}
    except Exception:
        return None


def load_windows() -> dict:
    """(asset, tenor, ws) -> {variant: (net, gross)} ; de-duped exactly like aggregate_shadow.py so
    the two tools never disagree on the underlying corpus. Reads gha_data/ recursively (date-
    partitioned subdirs), plain or gzipped, via dataio.jl_glob/jl_lines."""
    by_ws: dict = {}
    for fp in jl_glob("gha_data/shadow_windows_*.jsonl"):
        for row in jl_lines(fp):
            ws = row.get("ws")
            if ws is None or row.get("resolved_up") is None:      # tombstone / unresolved -> skip
                continue
            slot = by_ws.setdefault((row.get("asset", "btc"), row.get("tenor_min", 15), ws), {})
            for k, v in row.items():
                if isinstance(v, dict) and "net" in v:
                    slot.setdefault(k, (v["net"], v.get("gross", v["net"])))
    return by_ws


def day_stats(by_ws: dict, variant: str, base: str = BASELINE) -> dict | None:
    """Day-clustered stats for `variant` vs `base`, or None if they never co-occur.

    Returns {n_days, t, mean_edge, gross_pos_frac, day_means} where day_means maps
    UTC-date -> that day's MEAN (variant.net - base.net) across the day's shared windows."""
    day_deltas: dict[str, list[float]] = {}
    day_gross: dict[str, list[float]] = {}
    for (_asset, _tenor, ws), s in by_ws.items():
        if variant not in s or base not in s:
            continue
        d = _utc_date(ws)
        day_deltas.setdefault(d, []).append(s[variant][0] - s[base][0])
        day_gross.setdefault(d, []).append(s[variant][1])       # variant's OWN gross that window
    if not day_deltas:
        return None
    day_means = {d: sum(v) / len(v) for d, v in day_deltas.items()}
    day_gross_means = {d: sum(v) / len(v) for d, v in day_gross.items()}
    n_days = len(day_means)
    vals = list(day_means.values())
    mean_edge = sum(vals) / n_days
    if n_days >= 2:
        sd = (sum((x - mean_edge) ** 2 for x in vals) / (n_days - 1)) ** 0.5
        t = mean_edge / (sd / math.sqrt(n_days)) if sd > 0 else float("nan")
    else:
        t = float("nan")
    gross_pos_frac = sum(1 for m in day_gross_means.values() if m > 0) / n_days
    return {"n_days": n_days, "t": t, "mean_edge": mean_edge,
            "gross_pos_frac": gross_pos_frac, "day_means": day_means}


def same_days_bar(st: dict, ref_stats: dict[str, dict | None]) -> tuple[float, float, int]:
    """Restrict to days shared by `st` AND every available reference winner; return
    (candidate's mean edge over those days, max(reference mean edges) over those SAME days,
    n shared days). NaN-safe: if no reference has data yet, returns (nan, nan, 0)."""
    shared = set(st["day_means"])
    avail_refs = {r: rst for r, rst in ref_stats.items() if rst is not None}
    for rst in avail_refs.values():
        shared &= set(rst["day_means"])
    if not shared or not avail_refs:
        return float("nan"), float("nan"), 0
    v_mean = sum(st["day_means"][d] for d in shared) / len(shared)
    ref_means = [sum(rst["day_means"][d] for d in shared) / len(shared) for rst in avail_refs.values()]
    return v_mean, max(ref_means), len(shared)


# --- SECTION 2: per-market challengers (TASK 2) ------------------------------------------------
# Local display floor for THIS section only -- a row prints once >=5 days of head-to-head data
# exist, purely so an emerging tailoring signal is visible early. The dethronement FLAG
# (TAILOR-READY) still requires the full, stricter per_market_champion.py bar (n_days>=
# MIN_DAYS_EVAL=10, imported below) -- unchanged, so a 5-9 day row can only ever print as
# "per-market" (informational), never "TAILOR-READY".
PER_MARKET_MIN_DAYS_DISPLAY = 5


def per_market_challengers(by_ws: dict) -> list[str]:
    """Second section: for each asset x each enabled non-champion arm, day-clustered head-to-head
    vs av_stoikov ON THAT ASSET (reusing per_market_champion.py's own stats function + bar
    constants). Prints one line per (asset, arm) with >=PER_MARKET_MIN_DAYS_DISPLAY days of
    head-to-head data (else an "insufficient days" line, matching this file's "wait" convention).
    Returns the TAILOR-READY lines (for the Telegram push, same convention as PROMOTE-READY)."""
    try:
        from per_market_champion import (
            GLOBAL_CHAMPION, TAILOR_T_BAR, TAILOR_DAYS_POS_BAR, MIN_DAYS_EVAL,
            ASSETS, build_asset_data, head_to_head_stats,
        )
    except Exception as e:                 # never fail the pipeline on this section's account
        print(f"per-market challengers: unavailable (per_market_champion import failed: {e})")
        return []

    asset_data = build_asset_data(by_ws)
    enabled = enabled_variants()
    tailor_lines: list[str] = []
    for asset in ASSETS:
        wins = asset_data.get(asset, [])
        if not wins:
            print(f"per-market {asset}: no shadow-window data for this asset yet")
            continue
        if enabled is not None:
            names = sorted(enabled - {BASELINE, GLOBAL_CHAMPION})
        else:               # can't import strategies -- degrade to every arm seen in this asset's data
            names = sorted({k for _ws, s in wins for k in s} - {BASELINE, GLOBAL_CHAMPION})
        for arm in names:
            h2h = head_to_head_stats(wins, arm, GLOBAL_CHAMPION)
            n_days = h2h["n_days"]
            if n_days < PER_MARKET_MIN_DAYS_DISPLAY:
                print(f"insufficient days {asset} {arm} n_days={n_days} "
                      f"(<{PER_MARKET_MIN_DAYS_DISPLAY}) -- no head-to-head data with {GLOBAL_CHAMPION} yet")
                continue
            t, days_pos, pos_frac = h2h["day_t"], h2h["days_pos"], h2h["days_pos_frac"]
            t_str = f"{t:+.2f}" if t == t else "n/a"
            pos_str = f"{days_pos}/{n_days}" if n_days else "0/0"
            pf_str = f"{pos_frac:.0%}" if pos_frac == pos_frac else "n/a"
            clears = (n_days >= MIN_DAYS_EVAL and t == t and t >= TAILOR_T_BAR
                      and pos_frac == pos_frac and pos_frac >= TAILOR_DAYS_POS_BAR)
            prefix = "TAILOR-READY" if clears else "per-market"
            line = (f"{prefix} {asset} {arm} n_days={n_days} t={t_str} days+={pos_str} ({pf_str}) "
                    f"mean_delta/win={h2h['mean_delta']:+.3f} vs {GLOBAL_CHAMPION}")
            print(line)
            if clears:
                tailor_lines.append(line)
    return tailor_lines


def run() -> tuple[list[str], list[str]]:
    """Do the check, print every line, and return (PROMOTE-READY lines, TAILOR-READY lines) for
    the Telegram push."""
    by_ws = load_windows()
    if not by_ws:
        print("promotion_check: no shadow-window data found under gha_data/ -- nothing to check.")
        return [], []

    enabled = enabled_variants()
    all_variants = sorted({k for s in by_ws.values() for k in s} - {BASELINE})
    candidates = [v for v in all_variants if enabled is None or v in enabled]
    # also surface enabled-but-not-yet-collected variants (freshly added to strategies.py) as "wait"
    if enabled is not None:
        for v in sorted(enabled - {BASELINE} - set(all_variants)):
            print(f"wait {v} n_days=0 t=n/a mean_edge/day=n/a gross_pos=n/a -- no data collected yet")

    ref_stats = {r: day_stats(by_ws, r) for r in REFERENCE_WINNERS}

    promote_lines: list[str] = []
    for v in candidates:
        st = day_stats(by_ws, v)
        if st is None:
            print(f"wait {v} n_days=0 t=n/a mean_edge/day=n/a gross_pos=n/a -- no paired data with baseline yet")
            continue
        n_days, t, mean_edge, gross_pos_frac = st["n_days"], st["t"], st["mean_edge"], st["gross_pos_frac"]
        v_shared_mean, ref_bar, n_shared = same_days_bar(st, ref_stats)

        ok_days = n_days >= MIN_DAYS
        ok_t = (t == t) and t >= T_BAR
        ok_gross = gross_pos_frac >= GROSS_POS_FRAC
        ok_edge = (v_shared_mean == v_shared_mean and ref_bar == ref_bar and v_shared_mean >= ref_bar)

        t_str = f"{t:+.2f}" if t == t else "n/a"
        if ok_days and ok_t and ok_gross and ok_edge:
            line = (f"PROMOTE-READY {v} n_days={n_days} t={t_str} mean_edge/day={mean_edge:+.3f} "
                    f"gross_pos={gross_pos_frac:.0%} vs_ref_bar={ref_bar:+.3f} (same_days={n_shared})")
            print(line)
            promote_lines.append(line)
        else:
            reasons = []
            if not ok_days:
                reasons.append(f"days {n_days}/{MIN_DAYS}")
            if not ok_t:
                reasons.append(f"t {t_str}<{T_BAR}")
            if not ok_gross:
                reasons.append(f"gross_pos {gross_pos_frac:.0%}<{GROSS_POS_FRAC:.0%}")
            if not ok_edge:
                edge_str = f"{v_shared_mean:+.3f} < ref {ref_bar:+.3f}" if v_shared_mean == v_shared_mean else "no reference overlap yet"
                reasons.append(f"edge {edge_str}")
            print(f"wait {v} n_days={n_days} t={t_str} mean_edge/day={mean_edge:+.3f} "
                  f"gross_pos={gross_pos_frac:.0%} -- {', '.join(reasons)}")

    print("\n--- per-market challengers (head-to-head vs av_stoikov, per asset; see module docstring) ---")
    tailor_lines = per_market_challengers(by_ws)
    return promote_lines, tailor_lines


def main() -> None:
    try:
        promote_lines, tailor_lines = run()
    except Exception as e:                 # reporting job: never fail the pipeline on a bug here
        print(f"promotion_check: ERROR (non-fatal): {e}")
        return
    if promote_lines:
        try:
            from notify import alert_sync
            alert_sync("PROMOTION BAR CLEARED (pre-registered, strategies.py):\n" + "\n".join(promote_lines))
        except Exception as e:
            print(f"promotion_check: Telegram push failed (non-fatal): {e}")
    if tailor_lines:
        try:
            from notify import alert_sync
            alert_sync("PER-MARKET TAILORING OPPORTUNITY (per_market_champion.py dethronement bar):\n"
                        + "\n".join(tailor_lines))
        except Exception as e:
            print(f"promotion_check: Telegram push failed (non-fatal): {e}")


if __name__ == "__main__":
    main()
