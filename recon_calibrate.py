"""recon_calibrate.py -- sim-to-real fill-model calibration report (ALERT-ONLY, weekly).

Live trading writes two new tapes per settled window / per order:
  gha_data/live_recon_<asset>15m_r*.jsonl      per settled window (kalshi_trader.py._recon_write):
      {ws, asset, tenor, strategy, fills, requested, fill_rate, net, gross, inv_max}
      strategy = f"{a.gate}+{a.size_mode}" (kalshi_trader.py _STRATEGY_TAG, e.g. "as+markout")
  gha_data/order_lifecycle_<asset>15m_r*.jsonl per order EVENT (kalshi_trader.py._lifecycle_write):
      {ts, event: place|fill|partial|cancel|reject|expire, order_id, side, price, size, queue_ahead_est}

The shadow A/B (shadow_compare.py, READ-ONLY here) simulates the SAME windows with a queue model
(1-tick at touch, `ahead` consumption) and writes gha_data/<date>/shadow_windows_kalshi_<asset>15m_*.jsonl:
one row per settled window, per-arm attribution keyed by strategy name (baseline, av_stoikov, ...).

This script measures how far the paper queue model's predictions are from what live trading actually
saw, and prints an ALERT-ONLY report -- it NEVER edits shadow_compare.py. shadow's constants (AS_K,
MO_K, the 1-tick/`ahead` queue model, etc.) are validated against a comparable history (the 32-day
forward A/B in WINNING_STRATEGY.md); changing them is an OPERATOR decision, not something this script
should do automatically -- a constants change resets what's comparable to what came before it. Every
"RECOMMENDED shadow-constant adjustment" below is advisory text for a human to act on (or not).

Usage (workflow redirects stdout to the report file):
    python recon_calibrate.py [--data-dir gha_data] > CALIBRATION.txt
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone

from dataio import jl_glob, jl_lines
import strategies

# --- thresholds -------------------------------------------------------------------------------
MIN_JOIN_WINDOWS = 50        # below this, live<->shadow divergence stats are too noisy to trust
MIN_LIFECYCLE_PLACES = 100   # ditto for the empirical fill-probability table
MIN_DAYS_FOR_CI = 5          # per spec: day-clustered CI only reported once >=5 distinct UTC days exist

# KX*15M windows align to the fixed UTC :00/:15/:30/:45 grid -- every shadow "ws" epoch we've seen is
# an exact multiple of 900 (verified against real gha-data below). order_lifecycle rows carry only a
# raw `ts`, no window/"we" field, so time-to-close is APPROXIMATED from this grid: we = ceil(ts/900)*900.
WINDOW_S = 900

# live currently posts a flat 1 contract per order (kalshi_trader.py --post, overridden to 1 in the
# deployed live.yml session command). This is NOT itself logged per-row in live_recon (the schema has
# no size field) -- it is a documented ASSUMPTION baked into the volume-scaled ratios below. If the
# deployed --post value ever changes, update this constant (or better: get a size field added to
# live_recon) or the volume-scaled comparisons will silently drift.
LIVE_POST_CONTRACTS = 1.0

# --- live gate/size_mode string -> shadow_compare.py arm mapping ------------------------------
# kalshi_trader.py's gate_check() (its OWN live gating fn, not an import of shadow_compare.Variant)
# reimplements a subset of shadow's gates under different short names. Verified by reading both
# implementations side by side (kalshi_trader.py gate_check ~line 671 vs shadow_compare.py
# Variant._gate_one): the formulas are byte-identical for these four, so the alias is exact, not a
# guess. size_mode names line up 1:1 except kelly/depth, which only exist in kalshi_trader (no shadow
# arm runs that sizing logic -- those live strategies simply have no shadow twin to compare against).
GATE_ALIAS = {
    "ufat": "micro_ufat",   # gate_check "ufat": margin = MICRO_MARGIN*4*mid*(1-mid)  == shadow micro_ufat
    "micro": "micro",       # gate_check "micro": margin = 0                          == shadow micro
    "marg": "micro_marg",   # gate_check "marg":  margin = MICRO_MARGIN               == shadow micro_marg
    "as": "as",             # gate_check "as": A-S inventory penalty, same AS_K formula == shadow as
}
SIZE_ALIAS = {
    "flat": "flat",
    "markout": "markout",
    "kelly": None,   # no shadow analog
    "depth": None,   # no shadow analog
}


def map_strategy_tag(tag, registry):
    """live_recon "strategy" (f"{gate}+{size_mode}") -> (shadow arm name or None, note).

    Defensive/best-effort: live's tag encodes ONLY gate+size_mode, not cap/skew, so it cannot always
    uniquely identify a shadow arm (several arms share a gate+size_mode but differ in cap/skew/as_k/
    mo_k -- e.g. av_stoikov/as_cap100/as_k_half/as_k_2x are ALL gate="as", size_mode="flat"). We prefer
    the arm whose cap/skew match kalshi_trader's own CLI defaults (cap=50, skew=0.25); if none matches
    exactly (true for every "as"-gated arm, which all use skew=0.99 -- a config combination shadow has
    never actually run at skew=0.25), we fall back to the first gate+size_mode match and say so plainly
    rather than silently pick one.
    """
    if not tag or "+" not in tag:
        return None, f"tag {tag!r} not in 'gate+size_mode' form"
    live_gate, live_size = tag.split("+", 1)
    notes = []
    arm_gate = GATE_ALIAS.get(live_gate)
    if live_gate not in GATE_ALIAS:
        notes.append(f"unknown live gate {live_gate!r} (not in GATE_ALIAS)")
    arm_size = SIZE_ALIAS.get(live_size)
    if live_size not in SIZE_ALIAS:
        notes.append(f"unknown live size_mode {live_size!r} (not in SIZE_ALIAS)")
    elif arm_size is None:
        notes.append(f"no shadow analog for live size_mode {live_size!r}")
    if arm_gate is None:
        if live_gate in GATE_ALIAS:
            notes.append(f"no shadow analog for live gate {live_gate!r}")
        return None, "; ".join(notes) or "unmapped"
    if arm_size is None:
        return None, "; ".join(notes)
    cands = [s for s in registry if s.gate == arm_gate and s.size_mode == arm_size]
    if not cands:
        return None, f"no registry Strat with gate={arm_gate!r} size_mode={arm_size!r}"
    exact = [s for s in cands if s.cap == 50.0 and s.skew == 0.25]
    pool = exact if exact else cands
    chosen = pool[0]
    if len(pool) > 1:
        others = [s.name for s in pool[1:]]
        notes.append(f"AMBIGUOUS: gate+size_mode also matches {others} "
                      f"({'same cap/skew' if exact else 'no cap=50/skew=0.25 match at all'}); "
                      f"chose {chosen.name!r} (first in strategies.REGISTRY order)")
    elif not exact:
        notes.append(f"no cap=50/skew=0.25 match; used {chosen.name!r} (cap={chosen.cap} skew={chosen.skew}) "
                      f"as the closest gate+size_mode match -- shadow has never run this gate at live's "
                      f"actual cap/skew, so this comparison is approximate")
    return chosen.name, "; ".join(notes)


def utc_date(ws):
    return datetime.fromtimestamp(ws, timezone.utc).strftime("%Y-%m-%d")


def day_cluster(day_to_vals):
    """day_to_vals: dict[date] -> list[float]. One observation per day = that day's mean. Returns None
    if no days have data, else a dict with n_days/mean/sd/t/ci (t and 95% CI are a normal-approx
    day-clustered mean, same convention aggregate_shadow.py uses for its day-clustered t-stat -- NOT a
    formal Student-t interval, just consistent with how the rest of this codebase reports significance)."""
    day_means = {d: sum(v) / len(v) for d, v in day_to_vals.items() if v}
    n_days = len(day_means)
    if n_days == 0:
        return None
    vals = list(day_means.values())
    m = sum(vals) / n_days
    if n_days >= 2:
        sd = (sum((x - m) ** 2 for x in vals) / (n_days - 1)) ** 0.5
        se = sd / math.sqrt(n_days)
        t = m / se if se > 0 else float("nan")
        ci = (m - 1.96 * se, m + 1.96 * se)
    else:
        sd = se = t = float("nan")
        ci = (float("nan"), float("nan"))
    return {"n_days": n_days, "mean": m, "sd": sd, "t": t, "ci": ci}


# --- loaders ------------------------------------------------------------------------------------

def load_live_recon(data_dir):
    rows = []
    files = jl_glob(f"{data_dir}/live_recon_*15m_r*.jsonl")
    for fp in files:
        for rec in jl_lines(fp):
            rec["_src"] = fp
            rows.append(rec)
    return files, rows


def load_order_lifecycle(data_dir):
    rows = []
    files = jl_glob(f"{data_dir}/order_lifecycle_*15m_r*.jsonl")
    for fp in files:
        for rec in jl_lines(fp):
            rows.append(rec)
    return files, rows


def load_shadow_index(data_dir):
    """(asset, ws) -> full shadow window row (only rows from *_kalshi_* shadow files -- live trading is
    Kalshi-only right now, so joining against the older Polymarket-era shadow_windows_<asset>15m_*
    files, which lack the "venue" field, would silently mix venues)."""
    files = jl_glob(f"{data_dir}/shadow_windows_kalshi_*15m_*.jsonl")
    idx = {}
    n_rows = 0
    dupes = 0
    for fp in files:
        for rec in jl_lines(fp):
            n_rows += 1
            key = (rec.get("asset"), rec.get("ws"))
            if key in idx:
                dupes += 1
            idx[key] = rec
    return files, idx, n_rows, dupes


# --- report sections ------------------------------------------------------------------------------

def fmt_ci(ci):
    lo, hi = ci
    if lo != lo or hi != hi:  # NaN
        return "n/a"
    return f"[{lo:+.4f}, {hi:+.4f}]"


def section_header():
    print("=" * 96)
    print("recon_calibrate.py -- sim-to-real fill-model calibration report (ALERT-ONLY)")
    print(f"generated: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 96)
    print(
        "COMPARABILITY NOTICE: this report NEVER edits shadow_compare.py. shadow's queue model and\n"
        "constants (AS_K, MO_K, 1-tick/`ahead` fill logic, ...) are validated against a comparable\n"
        "history (the 32-day forward A/B in WINNING_STRATEGY.md / strategies.py). Any constant change\n"
        "is an OPERATOR decision -- applying one resets what future runs are comparable to. Every\n"
        "'RECOMMENDED' line below is advisory text for a human, not an instruction this script acts on."
    )
    print()


def section_inventory(live_files, live_rows, life_files, life_rows, shadow_files, shadow_rows, shadow_dupes):
    print("--- 1. DATA INVENTORY -----------------------------------------------------------------")
    assets = sorted({r.get("asset") for r in live_rows if r.get("asset")})
    print(f"live_recon:       {len(live_files)} file(s), {len(live_rows)} row(s)  assets={assets or '-'}")
    life_assets_placed = sorted({r.get("order_id") for r in life_rows if r.get("event") == "place"})
    print(f"order_lifecycle:  {len(life_files)} file(s), {len(life_rows)} event row(s) "
          f"({len(life_assets_placed)} distinct 'place' order_ids)")
    print(f"shadow_windows (kalshi): {len(shadow_files)} file(s), {shadow_rows} row(s), "
          f"{shadow_dupes} duplicate (asset,ws) keys (last-seen wins)")
    print()


def section_mapping():
    print("--- 2. LIVE STRATEGY-TAG -> SHADOW-ARM MAPPING (defensive; see map_strategy_tag) --------")
    seen = set()
    for lg in sorted(GATE_ALIAS):
        for ls in sorted(SIZE_ALIAS):
            tag = f"{lg}+{ls}"
            name, note = map_strategy_tag(tag, strategies.REGISTRY)
            if name is None and not note:
                continue
            print(f"  {tag:<16} -> {name or '(unmapped)':<14} {note}")
    print()


def build_join(live_rows, shadow_idx):
    joined = []
    n_mapped = 0
    n_asset_ws_found = 0
    unmapped_tags = defaultdict(int)
    for r in live_rows:
        arm, note = map_strategy_tag(r.get("strategy"), strategies.REGISTRY)
        if arm is None:
            unmapped_tags[r.get("strategy")] += 1
            continue
        n_mapped += 1
        key = (r.get("asset"), r.get("ws"))
        srow = shadow_idx.get(key)
        if srow is None:
            continue
        n_asset_ws_found += 1
        sarm = srow.get(arm)
        if not isinstance(sarm, dict):
            continue  # this arm wasn't (yet) enabled/logged in that particular shadow window
        joined.append({
            "asset": r.get("asset"), "ws": r.get("ws"), "day": utc_date(r["ws"]),
            "arm": arm, "map_note": note,
            "live_fills": r.get("fills", 0), "live_requested": r.get("requested", 0),
            "live_fill_rate": r.get("fill_rate"), "live_net": r.get("net", 0.0),
            "live_gross": r.get("gross", 0.0), "live_inv_max": r.get("inv_max"),
            "shadow_fills": sarm.get("fills", 0), "shadow_fill_vol": sarm.get("fill_vol", 0.0),
            "shadow_fill_rate": sarm.get("fill_rate"), "shadow_net": sarm.get("net", 0.0),
            "shadow_gross": sarm.get("gross", 0.0), "shadow_max_delta": sarm.get("max_delta"),
        })
    return joined, n_mapped, n_asset_ws_found, unmapped_tags


def section_join(live_rows, joined, n_mapped, n_asset_ws_found, unmapped_tags):
    print("--- 3. JOIN COVERAGE (live_recon <-> shadow_windows on asset+ws+mapped-arm) -------------")
    print(f"live_recon rows total:            {len(live_rows)}")
    print(f"  mapped to a known shadow arm:    {n_mapped}")
    print(f"  + matching shadow (asset,ws):    {n_asset_ws_found}")
    print(f"  + arm present in that window:    {len(joined)}   <- final joined rows")
    if unmapped_tags:
        print("  unmapped strategy tags (count):")
        for tag, n in sorted(unmapped_tags.items(), key=lambda kv: -kv[1]):
            print(f"    {tag!r}: {n}")
    print()
    if len(joined) < MIN_JOIN_WINDOWS:
        print(f"insufficient live data (n windows={len(joined)}, need >={MIN_JOIN_WINDOWS})")
        print()
    if joined:
        print(f"first real join{'s' if len(joined) > 1 else ''} (up to 5 shown):")
        for row in joined[:5]:
            print(f"  {row['day']} {row['asset']} ws={row['ws']} arm={row['arm']} | "
                  f"live: fills={row['live_fills']} requested={row['live_requested']} "
                  f"fill_rate={row['live_fill_rate']} net={row['live_net']:+.4f} | "
                  f"shadow: fills={row['shadow_fills']} fill_vol={row['shadow_fill_vol']} "
                  f"fill_rate={row['shadow_fill_rate']} net={row['shadow_net']:+.4f}"
                  + (f"   [{row['map_note']}]" if row['map_note'] else ""))
        print()
    return len(joined) >= MIN_JOIN_WINDOWS


def section_divergence(joined):
    print("--- 4. DIVERGENCE SUMMARY (live vs shadow, joined windows) ------------------------------")
    if not joined:
        print("(no joined windows -- nothing to compare)")
        print()
        return {}
    # per-window metrics. fills/net are put on a per-CONTRACT basis using shadow's actual fill_vol
    # (measured, not assumed) vs live's fills*LIVE_POST_CONTRACTS (assumed -- see constant above); this
    # is more honest than a single flat "post-size ratio" scalar because shadow's per-quote size itself
    # varies by size_mode (markout/fv scale self.post by 0..2x -- fill_vol already reflects that).
    day_fillsvol_ratio = defaultdict(list)
    day_fillscount_ratio = defaultdict(list)
    day_net_ratio = defaultdict(list)
    raw = {"live_vol": 0.0, "shadow_vol": 0.0, "live_net": 0.0, "shadow_net_scaled": 0.0,
           "live_fills": 0, "shadow_fills": 0}
    n_fillsvol = n_fillscount = n_net = 0
    for r in joined:
        live_vol = r["live_fills"] * LIVE_POST_CONTRACTS
        raw["live_vol"] += live_vol
        raw["shadow_vol"] += r["shadow_fill_vol"]
        raw["live_fills"] += r["live_fills"]
        raw["shadow_fills"] += r["shadow_fills"]
        if r["shadow_fill_vol"]:
            day_fillsvol_ratio[r["day"]].append(live_vol / r["shadow_fill_vol"])
            n_fillsvol += 1
        if r["shadow_fills"]:
            day_fillscount_ratio[r["day"]].append(r["live_fills"] / r["shadow_fills"])
            n_fillscount += 1
        if r["live_fills"] > 0 and r["shadow_fill_vol"]:
            live_net_pc = r["live_net"] / r["live_fills"]
            shadow_net_pc = r["shadow_net"] / r["shadow_fill_vol"]
            raw["live_net"] += r["live_net"]
            raw["shadow_net_scaled"] += shadow_net_pc * live_vol
            if shadow_net_pc:
                day_net_ratio[r["day"]].append(live_net_pc / shadow_net_pc)
                n_net += 1

    def report_metric(title, day_vals, n_pts, pooled_ratio=None):
        print(f"{title}  (n_windows={n_pts})")
        stats = day_cluster(day_vals)
        if stats is None:
            print("    no valid (nonzero-denominator) windows")
            return
        if stats["n_days"] >= MIN_DAYS_FOR_CI:
            print(f"    day-clustered: n_days={stats['n_days']} mean_ratio={stats['mean']:.4f} "
                  f"t={stats['t']:+.2f} 95%CI(normal-approx)={fmt_ci(stats['ci'])}")
        else:
            print(f"    n_days={stats['n_days']} < {MIN_DAYS_FOR_CI} -- point estimate only "
                  f"(no CI): mean_ratio={stats['mean']:.4f}")
        if pooled_ratio is not None:
            print(f"    pooled (sum/sum) ratio = {pooled_ratio:.4f}")

    pooled_vol = raw["live_vol"] / raw["shadow_vol"] if raw["shadow_vol"] else None
    report_metric("fills, VOLUME-scaled: (live_fills*LIVE_POST_CONTRACTS) / shadow_fill_vol",
                   day_fillsvol_ratio, n_fillsvol, pooled_vol)
    pooled_cnt = raw["live_fills"] / raw["shadow_fills"] if raw["shadow_fills"] else None
    report_metric("fills, raw EVENT-count ratio (unscaled -- ignores per-event size entirely)",
                   day_fillscount_ratio, n_fillscount, pooled_cnt)
    pooled_net = (raw["live_net"] / raw["shadow_net_scaled"]) if raw["shadow_net_scaled"] else None
    report_metric("net $/contract ratio: (live_net/live_fills) / (shadow_net/shadow_fill_vol)",
                   day_net_ratio, n_net, pooled_net)

    # fill_rate: NOT ratio'd -- the two fields measure different things. live fill_rate = fills/
    # requested (our own order-placement success rate); shadow fill_rate = fill_vol/trade_vol (our
    # share of the MARKET's total taker flow that window). Dividing one by the other would compare
    # apples to oranges, so we print them side by side only.
    lfr = [r["live_fill_rate"] for r in joined if r["live_fill_rate"] is not None]
    sfr = [r["shadow_fill_rate"] for r in joined if r["shadow_fill_rate"] is not None]
    print("fill_rate (side-by-side ONLY -- definitions differ, not a ratio):")
    print("    live fill_rate  = fills / requested (our own order-placement success rate)")
    print("    shadow fill_rate = fill_vol / trade_vol (our share of that window's total taker flow)")
    if lfr:
        print(f"    mean live fill_rate={sum(lfr)/len(lfr):.4f} (n={len(lfr)})")
    if sfr:
        print(f"    mean shadow fill_rate={sum(sfr)/len(sfr):.4f} (n={len(sfr)})")
    print()
    return {"vol_ratio": day_cluster(day_fillsvol_ratio), "net_ratio": day_cluster(day_net_ratio),
            "pooled_vol": pooled_vol, "pooled_net": pooled_net}


# --- order_lifecycle fill-probability table --------------------------------------------------------

QUEUE_BUCKETS = [("0", lambda q: q <= 0), ("1-50", lambda q: 0 < q <= 50),
                  ("51-200", lambda q: 50 < q <= 200), ("201-500", lambda q: 200 < q <= 500),
                  (">500", lambda q: q > 500)]
TAU_BUCKETS = [("<=60s", lambda t: t <= 60), ("60-300s", lambda t: 60 < t <= 300),
               ("300-600s", lambda t: 300 < t <= 600), ("600-900s", lambda t: t > 600)]


def qbucket(q):
    if q is None:
        return None
    for name, pred in QUEUE_BUCKETS:
        if pred(q):
            return name
    return None


def taubucket(ts):
    we = math.ceil(ts / WINDOW_S) * WINDOW_S  # next 900s-grid boundary
    tau = max(we - ts, 0.0)
    for name, pred in TAU_BUCKETS:
        if pred(tau):
            return name
    return TAU_BUCKETS[-1][0]


def section_fill_prob(life_rows):
    print("--- 5. EMPIRICAL FILL-PROBABILITY TABLE (order_lifecycle) -------------------------------")
    places = [r for r in life_rows if r.get("event") == "place" and r.get("order_id")]
    rejects = [r for r in life_rows if r.get("event") == "reject"]
    if len(places) < MIN_LIFECYCLE_PLACES:
        print(f"insufficient order_lifecycle data (n placed={len(places)}, need >={MIN_LIFECYCLE_PLACES})")
        if places or rejects:
            print(f"  (have {len(places)} 'place' events, {len(rejects)} 'reject' events so far)")
        print()
        return None
    events_by_oid = defaultdict(list)
    for r in life_rows:
        oid = r.get("order_id")
        ev = r.get("event")
        if oid and ev in ("fill", "partial", "cancel", "expire"):
            events_by_oid[oid].append(ev)

    table = defaultdict(lambda: {"placed": 0, "filled": 0, "partial": 0, "cancelled": 0,
                                  "expired": 0, "open": 0})
    skipped_no_queue = 0
    for p in places:
        qb = qbucket(p.get("queue_ahead_est"))
        if qb is None:
            skipped_no_queue += 1
            continue
        tb = taubucket(p["ts"])
        row = table[(qb, tb)]
        row["placed"] += 1
        evs = events_by_oid.get(p["order_id"], [])
        if "fill" in evs:
            row["filled"] += 1
        elif "partial" in evs:
            row["partial"] += 1
        elif "cancel" in evs:
            row["cancelled"] += 1
        elif "expire" in evs:
            row["expired"] += 1
        else:
            row["open"] += 1

    if skipped_no_queue:
        print(f"(excluded {skipped_no_queue} 'place' events with no queue_ahead_est)")
    reject_denom = len(places) + len(rejects)
    reject_rate = len(rejects) / reject_denom if reject_denom else None
    if reject_rate is not None:
        print(f"overall reject rate: {reject_rate:.4f} ({len(rejects)}/{reject_denom} placement attempts)")
    print()
    hdr = f"{'queue_ahead':<10} {'tau_to_close':<10} {'placed':>7} {'any_fill%':>10} " \
          f"{'full_fill%':>11} {'cancel%':>9} {'expire%':>9} {'still_open':>10}"
    print(hdr)
    print("-" * len(hdr))
    thin_cells = []
    for qb, _ in QUEUE_BUCKETS:
        for tb, _ in TAU_BUCKETS:
            row = table.get((qb, tb))
            if not row or row["placed"] == 0:
                continue
            n = row["placed"]
            any_fill = (row["filled"] + row["partial"]) / n
            full_fill = row["filled"] / n
            cancel = row["cancelled"] / n
            expire = row["expired"] / n
            print(f"{qb:<10} {tb:<10} {n:>7} {any_fill:>10.3f} {full_fill:>11.3f} "
                  f"{cancel:>9.3f} {expire:>9.3f} {row['open']:>10}")
            if n < 20:
                thin_cells.append((qb, tb, n))
    if thin_cells:
        print(f"\n(cells with n<20 are noisy: {thin_cells})")
    print()
    return table


# --- recommendations ---------------------------------------------------------------------------

def section_recommendations(div_stats, fill_table, n_joined):
    print("--- 6. RECOMMENDED shadow-constant adjustments (ALERT-ONLY -- operator decides) --------")
    recs = []
    if n_joined >= MIN_JOIN_WINDOWS and div_stats:
        vr = div_stats.get("vol_ratio")
        if vr and vr["n_days"] >= MIN_DAYS_FOR_CI:
            lo, hi = vr["ci"]
            if lo == lo and (lo > 1.15 or hi < 0.85):  # CI excludes [0.85,1.15] around 1.0
                direction = "UNDER" if lo > 1.0 else "OVER"
                recs.append(
                    f"shadow fill-VOLUME model {direction}-estimates live fills by ~{1/vr['mean']:.2f}x "
                    f"(mean live/shadow volume ratio={vr['mean']:.3f}, 95% CI={fmt_ci(vr['ci'])}, "
                    f"n_days={vr['n_days']}); consider a fill-volume scaling correction when comparing "
                    f"shadow arm P&L forecasts to live capacity.")
        nr = div_stats.get("net_ratio")
        if nr and nr["n_days"] >= MIN_DAYS_FOR_CI:
            lo, hi = nr["ci"]
            if lo == lo and (lo > 1.15 or hi < 0.85):
                direction = "UNDER" if lo > 1.0 else "OVER"
                recs.append(
                    f"shadow net-$/contract model {direction}-estimates live economics by "
                    f"~{1/nr['mean']:.2f}x (mean ratio={nr['mean']:.3f}, 95% CI={fmt_ci(nr['ci'])}, "
                    f"n_days={nr['n_days']}); the queue-favorable 1-tick fill assumption may be "
                    f"optimistic (or pessimistic) relative to real fills -- see the fill-probability "
                    f"table above for where.")
    if fill_table:
        for (qb, tb), row in fill_table.items():
            if qb in ("201-500", ">500") and row["placed"] >= 20:
                any_fill = (row["filled"] + row["partial"]) / row["placed"]
                if any_fill < 0.5:
                    recs.append(
                        f"empirical any-fill probability at queue_ahead={qb}, tau={tb} is only "
                        f"{any_fill:.2f} over {row['placed']} orders; shadow's queue model assumes a "
                        f"fill is highly likely once resting size ahead is consumed -- at this depth "
                        f"real fills lag that. Consider a fill-probability discount (or the existing "
                        f"queue_gate/Q_MAX=500 cutoff) for orders resting behind >200 in queue.")
    if not recs:
        if n_joined < MIN_JOIN_WINDOWS:
            print(f"no recommendations yet -- insufficient data (need >={MIN_JOIN_WINDOWS} joined "
                  f"windows across >={MIN_DAYS_FOR_CI} days; have {n_joined} joined windows).")
        else:
            print("no divergence cleared the alert threshold (day-clustered 95% CI excluding "
                  "[0.85x, 1.15x]) this run -- shadow and live look consistent so far.")
    else:
        for r in recs:
            print(f"  ALERT: {r}")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="gha_data",
                    help="root dir containing live_recon_*/order_lifecycle_*/shadow_windows_kalshi_* "
                         "(and their dated YYYY-MM-DD/ subdirs) -- the checked-out gha-data worktree")
    args = ap.parse_args()

    errs = strategies.validate()
    if errs:
        print("strategies.py roster FAILED validate() -- mapping table below may be unreliable:")
        for e in errs:
            print(f"  - {e}")
        print()

    live_files, live_rows = load_live_recon(args.data_dir)
    life_files, life_rows = load_order_lifecycle(args.data_dir)
    shadow_files, shadow_idx, shadow_rows, shadow_dupes = load_shadow_index(args.data_dir)

    section_header()
    section_inventory(live_files, live_rows, life_files, life_rows, shadow_files, shadow_rows, shadow_dupes)
    section_mapping()

    joined, n_mapped, n_asset_ws_found, unmapped_tags = build_join(live_rows, shadow_idx)
    sufficient = section_join(live_rows, joined, n_mapped, n_asset_ws_found, unmapped_tags)
    div_stats = section_divergence(joined)
    fill_table = section_fill_prob(life_rows)
    section_recommendations(div_stats, fill_table, len(joined))

    if not sufficient:
        print(f"SUMMARY: insufficient live data (n windows={len(joined)}, need >={MIN_JOIN_WINDOWS}). "
              f"join coverage: {len(live_rows)} live_recon rows -> {n_mapped} mapped -> "
              f"{n_asset_ws_found} asset+ws matched -> {len(joined)} joined.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
