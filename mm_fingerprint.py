"""mm_fingerprint.py -- Competitor (maker) fingerprinting from public Kalshi book/trade tape.

Offline analysis over the collected book/trades streams on the `gha-data` branch
(gha_data/<date>/book_kalshi_<asset>15m_r*.jsonl.gz). Kalshi's public feeds carry NO order IDs and
NO participant identity -- only anonymous aggregate size at each price level (book) and anonymous
individual fills (trades). So "detecting a maker" here is HEURISTIC CLUSTERING, not ground truth:

    A resident market-maker that ladders many price levels at a near-IDENTICAL size (the pattern
    FINGERPRINT.md already found for the BTC ladder-MM, e.g. "YES=265, NO=250 across dozens of
    levels") leaves a size-repetition signature no independent population of retail orders would
    coincidentally produce at that level count. We detect that signature per book snapshot, track
    its coverage/top-of-book share over time, and treat a size that appears at >=LEVEL_MIN distinct
    price levels in >=MIN_COVERAGE of a day's snapshots as "one active maker."

This is deliberately NOT a claim of true identity resolution -- see the LIMITS section in
MM_FINGERPRINT.md. It is a monitoring signal: has the size/cadence signature of the dominant
quoter(s) changed week over week? A brand-new signature taking a large top-of-book share is the
leading indicator that a new competitor has arrived (edge decay risk) before it shows up in our own
fill-rate/markout numbers.

    python mm_fingerprint.py --data-dir gha_data --days 14 --assets btc,eth,sol,xrp \
        --out mm_fingerprint_summary.json

Outputs a per-day-per-asset summary (maker cluster count, top-of-book share, two-sided-presence
ratio, cadence, hourly activity) plus a week-over-week NEW-MAKER flag (>20% TOB share, absent from
the prior week's known-signature set).
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Tunables (documented in MM_FINGERPRINT.md methodology section)
# ---------------------------------------------------------------------------
SIZE_MIN = 50        # ignore level sizes below this (retail/partial-fill noise, not ladder-signature)
LEVEL_MIN = 8         # a size must repeat at >=this many distinct price levels to count as a "ladder"
MIN_COVERAGE = 0.05    # a (side,size) signature must be present in >=this fraction of a day's snapshots
                       # to count as an "active maker" that day
CO_OCCUR_MIN = 0.6    # yes-signature + no-signature merge into one maker if they co-occur >=this often
TOB_REL_TOL = 0.15    # a touch-level size within +/-15% of a signature's size counts as "at the touch"
NEW_MAKER_TOB_BAR = 0.20   # week-over-week NEW-MAKER flag threshold (TOB share)
SIZE_MATCH_TOL = 0.12  # relative size tolerance when matching a signature across days/weeks


def iter_book_records(fp):
    """Yield type=='book' records from a book_kalshi_*.jsonl.gz file. Corrupt/truncated files
    (mid-write on the collector side) are skipped past the last good line, never raise."""
    try:
        with gzip.open(fp, "rt") as fh:
            for line in fh:
                if '"type": "book"' not in line[:25]:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except (EOFError, OSError, gzip.BadGzipFile):
        return


def touch(levels):
    """Best (highest-price) level of a side's ladder -- mirrors kalshi_trader's own yb[-1]/nb[-1]
    convention (Kalshi lists levels ascending by price)."""
    if not levels:
        return None, None
    p, s = levels[-1]
    return p, s


def qualifying_signatures(levels):
    """(size -> level_count) for sizes repeated at >=LEVEL_MIN levels, size>=SIZE_MIN.
    Returns list of (size, level_count, price_set) for qualifying sizes only."""
    if not levels:
        return []
    by_size = defaultdict(list)
    for p, s in levels:
        rs = round(s)
        if rs >= SIZE_MIN:
            by_size[rs].append(round(p, 4))
    return [(sz, len(ps), frozenset(ps)) for sz, ps in by_size.items() if len(ps) >= LEVEL_MIN]


def analyze_day_asset(files):
    """Process every book_kalshi_<asset>15m_*.jsonl.gz file for one (date, asset). Returns a
    summary dict or None if no usable book snapshots were found."""
    n = 0
    side_sig_hits = Counter()          # (side, size) -> #records where it qualifies
    side_sig_tob = Counter()            # (side, size) -> #records where it's AT the touch
    both_sides_n = 0                    # records with a qualifying signature on BOTH sides
    either_side_n = 0                   # records with a qualifying signature on >=1 side
    hour_counts = Counter()             # hour -> #records
    hour_present = Counter()            # hour -> #records where >=1 signature qualifies
    cooccur = Counter()                  # (yes_size, no_size) -> #records both qualify
    # cadence tracking: per (side,size), the set of price-levels holding it, to detect reshapes
    last_levelset = {}                   # (side,size) -> (t, frozenset)
    change_gaps = defaultdict(list)      # (side,size) -> [dt between successive level-set changes]
    prev_t = None

    for fp in files:
        for r in iter_book_records(fp):
            t = r.get("t")
            yb = r.get("yes") or []
            nb = r.get("no") or []
            if t is None or (not yb and not nb):
                continue
            n += 1
            hr = datetime.fromtimestamp(t, tz=timezone.utc).hour
            hour_counts[hr] += 1

            sig_y = qualifying_signatures(yb)
            sig_n = qualifying_signatures(nb)
            ty_p, ty_s = touch(yb)
            tn_p, tn_s = touch(nb)

            any_side = bool(sig_y or sig_n)
            if any_side:
                either_side_n += 1
                hour_present[hr] += 1
            if sig_y and sig_n:
                both_sides_n += 1

            for sz, lvln, pset in sig_y:
                side_sig_hits[("yes", sz)] += 1
                if ty_s is not None and abs(ty_s - sz) <= TOB_REL_TOL * max(sz, 1):
                    side_sig_tob[("yes", sz)] += 1
                key = ("yes", sz)
                if key in last_levelset:
                    pt, pset0 = last_levelset[key]
                    if pset0 != pset and (t - pt) < 10.0:
                        change_gaps[key].append(t - pt)
                last_levelset[key] = (t, pset)

            for sz, lvln, pset in sig_n:
                side_sig_hits[("no", sz)] += 1
                if tn_s is not None and abs(tn_s - sz) <= TOB_REL_TOL * max(sz, 1):
                    side_sig_tob[("no", sz)] += 1
                key = ("no", sz)
                if key in last_levelset:
                    pt, pset0 = last_levelset[key]
                    if pset0 != pset and (t - pt) < 10.0:
                        change_gaps[key].append(t - pt)
                last_levelset[key] = (t, pset)

            for sz1, _, _ in sig_y:
                for sz2, _, _ in sig_n:
                    cooccur[(sz1, sz2)] += 1
            prev_t = t

    if n == 0:
        return None

    kept = {k: c for k, c in side_sig_hits.items() if c / n >= MIN_COVERAGE}

    # --- cluster yes/no signatures into "makers" via co-occurrence ---
    yes_kept = sorted([sz for (side, sz) in kept if side == "yes"])
    no_kept = sorted([sz for (side, sz) in kept if side == "no"])
    used_no = set()
    clusters = []
    for ys in yes_kept:
        best_ns, best_rate = None, 0.0
        for ns in no_kept:
            if ns in used_no:
                continue
            co = cooccur.get((ys, ns), 0)
            denom = min(kept[("yes", ys)], kept[("no", ns)])
            rate = co / denom if denom else 0.0
            if rate > best_rate:
                best_rate, best_ns = rate, ns
        if best_ns is not None and best_rate >= CO_OCCUR_MIN:
            used_no.add(best_ns)
            cov = max(kept[("yes", ys)], kept[("no", best_ns)]) / n
            tob = (side_sig_tob[("yes", ys)] + side_sig_tob[("no", best_ns)]) / (
                kept[("yes", ys)] + kept[("no", best_ns)])
            clusters.append({"yes_size": ys, "no_size": best_ns, "coverage": round(cov, 4),
                             "tob_share": round(tob, 4), "two_sided": True})
        else:
            cov = kept[("yes", ys)] / n
            tob = side_sig_tob[("yes", ys)] / kept[("yes", ys)]
            clusters.append({"yes_size": ys, "no_size": None, "coverage": round(cov, 4),
                             "tob_share": round(tob, 4), "two_sided": False})
    for ns in no_kept:
        if ns in used_no:
            continue
        cov = kept[("no", ns)] / n
        tob = side_sig_tob[("no", ns)] / kept[("no", ns)]
        clusters.append({"yes_size": None, "no_size": ns, "coverage": round(cov, 4),
                         "tob_share": round(tob, 4), "two_sided": False})

    clusters.sort(key=lambda c: -c["coverage"])

    # cadence of the DOMINANT cluster (largest coverage side)
    cadence_s = None
    if clusters:
        top = clusters[0]
        key = ("yes", top["yes_size"]) if top["yes_size"] is not None else ("no", top["no_size"])
        gaps = change_gaps.get(key, [])
        if len(gaps) >= 3:
            cadence_s = round(statistics.median(gaps), 2)

    hourly_activity = {h: round(hour_present.get(h, 0) / hour_counts[h], 3) for h in sorted(hour_counts)}
    two_sided_ratio = round(both_sides_n / either_side_n, 4) if either_side_n else 0.0

    # NOTE on distinct_makers_est: `clusters` uses the permissive MIN_COVERAGE=0.05 bar to keep
    # low-frequency candidate signatures visible in the detail list (transparency), but round
    # human-chosen sizes (100, 150, 200, ...) can coincidentally clear LEVEL_MIN from MANY
    # independent retail participants, not one bot -- see MM_FINGERPRINT.md LIMITS. The reported
    # "distinct active makers" count therefore uses a stricter 10% coverage bar (CONFIDENT_COVERAGE)
    # so headline counts aren't inflated by round-lot coincidence; the fuller cluster list (with
    # each one's own coverage) is still returned for anyone who wants the permissive view.
    CONFIDENT_COVERAGE = 0.10
    n_confident = sum(1 for c in clusters if c["coverage"] >= CONFIDENT_COVERAGE)
    n_dominant = sum(1 for c in clusters if c["coverage"] >= 0.20)

    return {
        "n_snapshots": n,
        "distinct_makers_est": n_confident,
        "distinct_signatures_permissive": len(clusters),
        "dominant_makers_est": n_dominant,
        "two_sided_presence_ratio": two_sided_ratio,
        "dominant_cluster": clusters[0] if clusters else None,
        "dominant_cadence_s": cadence_s,
        "clusters": clusters,
        "hourly_activity": hourly_activity,
    }


def size_matches_any(size, known_sizes, tol=SIZE_MATCH_TOL):
    return any(abs(size - k) <= tol * max(size, k) for k in known_sizes)


def week_over_week(daily, assets):
    """daily: {asset: {date: summary}}. Splits the sorted date list into an older week (weekA) and
    the most recent week (weekB); flags a NEW-MAKER when a weekB cluster with tob_share > 20% has
    no size match (yes or no leg) anywhere in weekA's known-signature set."""
    out = {}
    for asset in assets:
        days = sorted(daily.get(asset, {}))
        if len(days) < 2:
            out[asset] = {"flags": [], "note": "insufficient days for week-over-week"}
            continue
        mid = max(1, len(days) - 7)
        weekA, weekB = days[:mid], days[mid:]
        known = set()
        for d in weekA:
            s = daily[asset][d]
            if not s:
                continue
            for c in s["clusters"]:
                if c["coverage"] >= 0.03:
                    if c["yes_size"] is not None:
                        known.add(c["yes_size"])
                    if c["no_size"] is not None:
                        known.add(c["no_size"])
        flags = []
        for d in weekB:
            s = daily[asset][d]
            if not s:
                continue
            for c in s["clusters"]:
                if c["tob_share"] <= NEW_MAKER_TOB_BAR:
                    continue
                sizes = [x for x in (c["yes_size"], c["no_size"]) if x is not None]
                if not any(size_matches_any(sz, known) for sz in sizes):
                    flags.append({"date": d, "cluster": c})
        out[asset] = {"weekA_days": weekA, "weekB_days": weekB,
                      "weekA_known_sizes": sorted(known), "flags": flags}
    return out


def main():
    ap = argparse.ArgumentParser(description="Heuristic maker-fingerprinting over the public book tape")
    ap.add_argument("--data-dir", default="gha_data")
    ap.add_argument("--assets", default="btc,eth,sol,xrp")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--out", default="mm_fingerprint_summary.json")
    a = ap.parse_args()

    assets = [x.strip() for x in a.assets.split(",") if x.strip()]
    all_dates = sorted(d for d in os.listdir(a.data_dir)
                       if os.path.isdir(os.path.join(a.data_dir, d)) and d[:2] == "20")
    dates = all_dates[-a.days:] if a.days else all_dates
    print(f"[mm_fingerprint] dates: {dates[0]}..{dates[-1]} ({len(dates)} days) assets={assets}")

    daily = {asset: {} for asset in assets}
    for asset in assets:
        for d in dates:
            files = sorted(glob.glob(os.path.join(a.data_dir, d, f"book_kalshi_{asset}15m_*.jsonl.gz")))
            if not files:
                daily[asset][d] = None
                continue
            summary = analyze_day_asset(files)
            daily[asset][d] = summary
            if summary:
                dom = summary["dominant_cluster"]
                dom_desc = (f"yes={dom['yes_size']} no={dom['no_size']} tob={dom['tob_share']:.0%}"
                           if dom else "none")
                print(f"  {asset} {d}: n={summary['n_snapshots']:5d} makers~{summary['distinct_makers_est']} "
                      f"2sided={summary['two_sided_presence_ratio']:.2f} cadence={summary['dominant_cadence_s']} "
                      f"dom=[{dom_desc}]")
            else:
                print(f"  {asset} {d}: NO DATA")

    wow = week_over_week(daily, assets)

    print("\n=== WEEK-OVER-WEEK NEW-MAKER FLAGS ===")
    for asset in assets:
        w = wow[asset]
        if w.get("flags"):
            for f in w["flags"]:
                c = f["cluster"]
                print(f"  [NEW-MAKER] {asset} {f['date']}: yes={c['yes_size']} no={c['no_size']} "
                      f"tob_share={c['tob_share']:.0%} coverage={c['coverage']:.0%}")
        else:
            print(f"  {asset}: no new-maker flags "
                  f"(weekA known sizes: {w.get('weekA_known_sizes')})")

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "dates": dates, "assets": assets,
          "params": {"SIZE_MIN": SIZE_MIN, "LEVEL_MIN": LEVEL_MIN, "MIN_COVERAGE": MIN_COVERAGE,
                     "CO_OCCUR_MIN": CO_OCCUR_MIN, "TOB_REL_TOL": TOB_REL_TOL,
                     "NEW_MAKER_TOB_BAR": NEW_MAKER_TOB_BAR},
          "daily": daily, "week_over_week": wow}
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"\n[mm_fingerprint] wrote {a.out}")


if __name__ == "__main__":
    main()
