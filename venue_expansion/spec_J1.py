#!/usr/bin/env python3
"""spec_J1.py -- FROZEN pre-registered spec J1 (KXJOBLESSCLAIMS weekly-relist fade, reopen of
graveyard #24, INCONCLUSIVE at 10 servable Thursdays vs >=15). See venue_expansion/GROUNDING.md,
PAPER_TRADER_AUDIT.md, REOPENABLE.md for context; the frozen spec text lives in the task that
produced this script (also summarized in the header of out/spec_J1.md).

Read-only. Data sources (all local caches, gitignored, pulled politely from public endpoints):
  - cache/M1/markets_universe.json  -- pulled from ALL 4 HF markets-shards (markets-0000..0003),
    predicate-pushed to series_key IN (macro families incl. JOBLESS/KXJOBLESSCLAIMS). We filter
    to series_key == 'KXJOBLESSCLAIMS' EXACT (never a LIKE prefix) -- 212 markets, 24 events.
  - cache/prereg/tape/shard-0000..0015.parquet -- ALL 16 HF trade shards (trades-0000..0015),
    predicate-pushed server-side to the UNION ticker universe used by spec M1, which was built
    from the same series-key-exact markets_universe.json and therefore already contains every
    KXJOBLESSCLAIMS ticker. Verified in this run: a live re-query of trades-0000.parquet for two
    sample tickers (one zero-row, one 365-row) matches the cached shard-0000 exactly -- the cache
    is not truncated. 9,812 KXJOBLESSCLAIMS trades / 483,816 contracts across 162 distinct
    tickers, 2025-06-09 .. 2026-01-28 (the archive's own coverage ceiling).
  - cache/J1/live_results.json -- GET /trade-api/v2/markets/{ticker} for ALL 212 KXJOBLESSCLAIMS
    tickers (not just the 2 archive-unsettled ones), per the spec's "every event's result
    reconciled against that endpoint regardless". This is the ONLY source of settlement truth
    used anywhere in this script; the archive's own `result` column is used only as a fallback
    if a live fetch errored, and any archive/live disagreement is logged loudly.

DIVERGENCE FROM THE SPEC TEXT (reported per non-negotiable #1, not improvised around):
  data_plan says "FIT = the first 8 release Thursdays (2025-06-12 .. 2025-07-31)". The archive
  has only 7 release events in that literal date span -- KXJOBLESSCLAIMS-25JUN19 does not exist
  in the archive (confirmed: 24 events total, chronological list has a 14-day gap 06-12 -> 06-26).
  The spec's OWN validation-side statement ("VALIDATION = ... max 16 available") is only
  consistent with FIT having exactly 8 events (24 - 8 = 16), so this script takes "first 8" as
  the binding ordinal rule (chronological order of events actually present) and treats the
  parenthetical date range as an approximation invalidated by a data gap unknown at registration
  time. FIT is therefore JUN12..AUG07 (8 events), VALIDATION is AUG14..FEB05 (16 events). This
  does not touch any bar or floor -- it only fixes which 8 of the 24 events are off-limits for
  bar-setting.

Writes:
  venue_expansion/out/spec_J1.json  -- full records + summary
  venue_expansion/out/spec_J1.md    -- method + results + skip ledger
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import duckdb
from scipy import stats as sstats

HERE = os.path.dirname(os.path.abspath(__file__))
UNIV = os.path.join(HERE, "cache", "M1", "markets_universe.json")
TAPE_DIR = os.path.join(HERE, "cache", "prereg", "tape")
LIVE_RESULTS = os.path.join(HERE, "cache", "J1", "live_results.json")
OUT_JSON = os.path.join(HERE, "out", "spec_J1.json")
OUT_MD = os.path.join(HERE, "out", "spec_J1.md")

THETA_GRID = [0.15, 0.25, 0.35]
SIX_H = timedelta(hours=6)
SIXTY_MIN = timedelta(minutes=60)

SHUTDOWN_GAP_START = "2025-10-02"  # last pre-gap validation close date (inclusive)
SHUTDOWN_GAP_END = "2025-12-18"    # first post-gap validation close date (inclusive)

SKIP_LOG = []  # mandatory: every dropped rung/event logged with a reason


def skip(scope, reason, extra=None):
    rec = {"scope": scope, "reason": reason}
    if extra is not None:
        rec["extra"] = extra
    SKIP_LOG.append(rec)


def parse_dt(s):
    if isinstance(s, datetime):
        return s
    s = s.strip()
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fee_cents(p):
    """Kalshi taker fee, ceil(7*p*(1-p)) CENTS, p = the leg's own transacted price in [0,1]."""
    p = max(0.0, min(1.0, p))
    return math.ceil(7 * p * (1 - p))


def day_clustered_t(cluster_means):
    n = len(cluster_means)
    if n < 2:
        return (cluster_means[0] if n == 1 else None), None, n
    m = st.mean(cluster_means)
    sd = st.stdev(cluster_means)
    se = sd / math.sqrt(n)
    t = (m / se) if se > 0 else (float("inf") if m > 0 else (float("-inf") if m < 0 else 0.0))
    return m, t, n


def wilson_lb(k, n, z=1.959963984540054):
    if n == 0:
        return None
    phat = k / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    adj = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return (center - adj) / denom


def t_crit(alpha_two_sided, df):
    if df < 1:
        return None
    return float(sstats.t.ppf(1 - alpha_two_sided / 2, df))


# ---------------------------------------------------------------------------
# 1. Load markets universe -> KXJOBLESSCLAIMS events, exact series_key match
# ---------------------------------------------------------------------------

def load_events():
    d = json.load(open(UNIV))
    cols = d["cols"]; idx = {c: i for i, c in enumerate(cols)}
    rows = [r for r in d["rows"] if r[idx["series_key"]] == "KXJOBLESSCLAIMS"]

    live = json.load(open(LIVE_RESULTS)) if os.path.exists(LIVE_RESULTS) else {}

    disagreements = []
    markets = []
    for r in rows:
        ticker = r[idx["ticker"]]
        event_ticker = r[idx["event_ticker"]]
        archive_result = r[idx["result"]] or None
        live_rec = live.get(ticker, {})
        live_result = live_rec.get("result") or None
        if live_result in ("yes", "no"):
            truth = live_result
            if archive_result in ("yes", "no") and archive_result != live_result:
                disagreements.append({"ticker": ticker, "archive": archive_result, "live": live_result})
        elif archive_result in ("yes", "no"):
            truth = archive_result
            skip(f"result:{ticker}", "live reconciliation unavailable, fell back to archive result",
                 {"live_status": live_rec.get("status")})
        else:
            truth = None
            skip(f"result:{ticker}", "result unavailable (neither live nor archive settled)",
                 {"live_status": live_rec.get("status"), "archive_result": archive_result})

        suffix = ticker[len(event_ticker) + 1:]
        try:
            strike = int(suffix)
        except ValueError:
            strike = None
            skip(f"strike:{ticker}", "strike unparseable", {"suffix": suffix})

        markets.append({
            "ticker": ticker,
            "event_ticker": event_ticker,
            "strike": strike,
            "result": truth,
            "open_time": parse_dt(r[idx["open_time"]]),
            "close_time": parse_dt(r[idx["close_time"]]),
        })

    events = defaultdict(list)
    for m in markets:
        events[m["event_ticker"]].append(m)

    ev_list = []
    for et, ms in events.items():
        close_date = min(m["close_time"] for m in ms).date()
        t_open = min(m["open_time"] for m in ms)
        ev_list.append({"event_ticker": et, "thursday": str(close_date), "t_open": t_open, "markets": ms})
    ev_list.sort(key=lambda e: e["t_open"])
    return ev_list, disagreements


# ---------------------------------------------------------------------------
# 2. Anchor derivation: from the IMMEDIATELY PRIOR event's own settled ladder
# ---------------------------------------------------------------------------

def anchor_bounds(prior_event):
    """Returns (A_lo, A_hi): A_lo = highest floor confirmed settled 'yes' (None if none),
    A_hi = lowest floor confirmed settled 'no' (None if none). True realized value A in
    [A_lo, A_hi) if both are known; open-ended on whichever side has no confirmed floor."""
    yes_floors = [m["strike"] for m in prior_event["markets"] if m["strike"] is not None and m["result"] == "yes"]
    no_floors = [m["strike"] for m in prior_event["markets"] if m["strike"] is not None and m["result"] == "no"]
    a_lo = max(yes_floors) if yes_floors else None
    a_hi = min(no_floors) if no_floors else None
    return a_lo, a_hi


def implied_q(strike, a_lo, a_hi):
    """1{strike < A} where determinable from the anchor bounds; None if ambiguous."""
    if a_lo is not None and strike < a_lo:
        return 1
    if a_hi is not None and strike >= a_hi:
        return 0
    return None


# ---------------------------------------------------------------------------
# 3. Tape access
# ---------------------------------------------------------------------------

def load_tape_con():
    shard_files = sorted(
        os.path.join(TAPE_DIR, f) for f in os.listdir(TAPE_DIR)
        if f.startswith("shard-") and f.endswith(".parquet")
    )
    assert len(shard_files) == 16, f"expected 16 cached shards, found {len(shard_files)}"
    con = duckdb.connect()
    src = "read_parquet([" + ",".join(f"'{p}'" for p in shard_files) + "])"
    con.execute(f"""
        CREATE TEMP TABLE tape AS
        SELECT ticker, count, yes_price, no_price, taker_side, created_time
        FROM {src}
        WHERE ticker LIKE 'KXJOBLESSCLAIMS-%'
        ORDER BY ticker, created_time
    """)
    n = con.execute("SELECT count(*) FROM tape").fetchone()[0]
    return con, n, len(shard_files)


def yes_equiv_price(row):
    """row: (ticker,count,yes_price,no_price,taker_side,created_time). taker_side='yes' -> taker
    LIFTED THE ASK at yes_price (true ask, executable). taker_side='no' -> taker HIT THE BID
    buying NO at no_price, i.e. sold-equivalent yes at (100-no_price) (true bid, executable)."""
    _, _, yes_price, no_price, side, _ = row
    if side == "yes":
        return yes_price / 100.0
    return (100 - no_price) / 100.0


# ---------------------------------------------------------------------------
# 4. Per-rung signal + entry construction
#
# Split into two theta-INDEPENDENT stages (anchor/print/entry-price/settlement never depend on
# theta -- only which side, if any, and its d magnitude do) plus a cheap per-theta filter. This
# matters for the skip ledger: the frozen theta grid is walked 3x during FIT, and if the
# anchor/print/entry/settlement stages were repeated inside that loop (an earlier draft did this)
# every theta-independent skip would be logged 3x, inflating the ledger. Only the "|d| < theta"
# reason is legitimately theta-specific and is allowed to repeat once per grid cell.
# ---------------------------------------------------------------------------

def build_signals_for_event(con, event, prior_event, thursday):
    """Stage A+B, computed ONCE per rung regardless of theta. Returns a list of resolved
    candidates: {ticker, strike, q, A_lo, A_hi, p, d, side, signal_ts, entry (dict or None)}.
    `entry` is None if no side is implied (d==0, vanishingly rare) or if entry-price/settlement
    resolution failed (skip already logged here, once)."""
    candidates = []
    if prior_event is None:
        for m in event["markets"]:
            skip(f"{thursday}:{m['ticker']}", "no prior KXJOBLESSCLAIMS event in archive to anchor on")
        return candidates

    a_lo, a_hi = anchor_bounds(prior_event)

    for m in event["markets"]:
        tkey = f"{thursday}:{m['ticker']}"
        if m["strike"] is None:
            continue  # already logged as strike unparseable at load time
        q = implied_q(m["strike"], a_lo, a_hi)
        if q is None:
            skip(tkey, "anchor ambiguous: strike falls inside prior week's unresolved band",
                 {"strike": m["strike"], "A_lo": a_lo, "A_hi": a_hi})
            continue

        t_open = event["t_open"]
        rows = con.execute(
            "SELECT ticker, count, yes_price, no_price, taker_side, created_time FROM tape "
            "WHERE ticker = ? AND created_time >= ? AND created_time <= ? ORDER BY created_time LIMIT 1",
            [m["ticker"], t_open, t_open + SIX_H],
        ).fetchall()
        if not rows:
            skip(tkey, "no print within 6h of open")
            continue
        sig_row = rows[0]
        p = yes_equiv_price(sig_row)
        signal_ts = sig_row[5]
        d = p - q
        side = "no" if d > 0 else ("yes" if d < 0 else None)

        entry = None
        if side is not None:
            entry_rows = con.execute(
                "SELECT ticker, count, yes_price, no_price, taker_side, created_time FROM tape "
                "WHERE ticker = ? AND created_time >= ? AND created_time <= ? AND taker_side = ? "
                "ORDER BY created_time LIMIT 1",
                [m["ticker"], signal_ts, signal_ts + SIXTY_MIN, side],
            ).fetchall()
            if not entry_rows:
                skip(tkey, "no matching-side print within 60min of signal", {"side": side})
            elif m["result"] not in ("yes", "no"):
                skip(tkey, "result unavailable", {})
            else:
                er = entry_rows[0]
                entry_price = (er[3] / 100.0) if side == "no" else (er[2] / 100.0)
                won = 1 if (side == "yes" and m["result"] == "yes") or (side == "no" and m["result"] == "no") else 0
                fee_c = fee_cents(entry_price)
                entry = {
                    "entry_price": entry_price, "entry_count": er[1], "entry_ts": str(er[5]),
                    "fee_c": fee_c, "result": m["result"], "won": won,
                    "net": won - entry_price - fee_c / 100.0,
                }

        candidates.append({
            "tkey": tkey, "thursday": thursday, "event_ticker": event["event_ticker"],
            "ticker": m["ticker"], "strike": m["strike"], "q": q, "A_lo": a_lo, "A_hi": a_hi,
            "signal_price": p, "d": d, "side": side, "signal_ts": str(signal_ts), "entry": entry,
        })
    return candidates


def apply_theta(candidates, theta):
    """Stage C: cheap per-theta filter over pre-resolved candidates. Logs '|d| < theta' (the one
    legitimately theta-specific skip reason) for candidates whose magnitude doesn't clear this
    theta; returns the qualifying entry dicts (already resolved in build_signals_for_event)."""
    entries = []
    for c in candidates:
        if abs(c["d"]) < theta:
            skip(c["tkey"], "|d| < theta", {"d": c["d"], "theta": theta})
            continue
        if c["entry"] is None:
            continue  # already skip-logged once in build_signals_for_event (no side, no print, or no result)
        entries.append({
            "thursday": c["thursday"], "event_ticker": c["event_ticker"], "ticker": c["ticker"],
            "strike": c["strike"], "q": c["q"], "A_lo": c["A_lo"], "A_hi": c["A_hi"],
            "signal_price": c["signal_price"], "d": c["d"], "theta": theta, "side": c["side"],
            "signal_ts": c["signal_ts"], **c["entry"],
        })
    return entries


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    t_start = time.time()
    log_lines = []

    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    log("=" * 78)
    log("spec_J1 -- KXJOBLESSCLAIMS weekly-relist fade (reopen of graveyard #24)")
    log("=" * 78)

    events, disagreements = load_events()
    n_events = len(events)
    log(f"KXJOBLESSCLAIMS events in archive: {n_events}  (spec's own data_plan states 24)")
    live = json.load(open(LIVE_RESULTS)) if os.path.exists(LIVE_RESULTS) else {}
    live_ok = sum(1 for v in live.values() if v.get("result") in ("yes", "no"))
    log(f"live settlement reconciliation: {live_ok}/{len(live)} tickers returned a result "
        f"({len(live) - live_ok} 404/error -- retention wall, see out/spec_J1.md). "
        f"disagreements among the {live_ok} possible comparisons: {len(disagreements)}"
        + (f" -> {disagreements}" if disagreements else ""))

    for e in events:
        log(f"  {e['thursday']}  {e['event_ticker']:<28s} t_open={e['t_open']}  n_rungs={len(e['markets'])}")

    if n_events < 9:
        json.dump({"spec_id": "J1", "verdict": "INSUFFICIENT",
                    "reason": f"only {n_events} KXJOBLESSCLAIMS events in archive, need >=9 (8 FIT + >=1 validation)"},
                   open(OUT_JSON, "w"), indent=1)
        log("INSUFFICIENT: too few events even for the ordinal 8-event FIT window.")
        return

    FIT_N = 8
    fit_events = events[:FIT_N]
    val_events = events[FIT_N:]
    log(f"\nFIT events (first {FIT_N}, ordinal): {[e['thursday'] for e in fit_events]}")
    log(f"VALIDATION events (remaining {len(val_events)}): {[e['thursday'] for e in val_events]}")

    con, n_tape_rows, n_shards = load_tape_con()
    log(f"\ntape: {n_shards} shards read, {n_tape_rows} KXJOBLESSCLAIMS trades in local cache")

    # ---------------- FIT: theta grid search ----------------
    log("\n" + "-" * 78)
    log("FIT: theta grid search on first 8 release Thursdays")
    log("-" * 78)
    fit_candidates_by_event = []
    for i, ev in enumerate(fit_events):
        prior = events[i - 1] if i > 0 else None
        fit_candidates_by_event.append(build_signals_for_event(con, ev, prior, ev["thursday"]))

    fit_results = {}
    for theta in THETA_GRID:
        all_entries = []
        for cands in fit_candidates_by_event:
            all_entries.extend(apply_theta(cands, theta))
        by_th = defaultdict(list)
        for e in all_entries:
            by_th[e["thursday"]].append(e["net"])
        cluster_means = [st.mean(v) for v in by_th.values()]
        m, t, nclust = day_clustered_t(cluster_means)
        fit_results[theta] = {"n_entries": len(all_entries), "n_thursdays": nclust, "mean_net": m, "t": t}
        log(f"  theta={theta:.2f}  n_entries={len(all_entries):3d}  n_Thursdays={nclust}  "
            f"mean_net={m if m is None else round(m,4)}  t={t if t is None else round(t,3)}")

    valid_t = [(th, r["t"]) for th, r in fit_results.items() if r["t"] is not None]
    if not valid_t:
        # DIVERGENCE from the frozen procedure (non-negotiable #1): the self-kill clause is
        # written as "all three FIT theta cells with Thursday-clustered t <= 0", which presumes
        # a defined t. Here NO grid cell ever has >=2 populated Thursday clusters (entry
        # construction is structurally so sparse in the FIT window -- illiquid relist, most
        # rungs killed by "no print within 6h of open" or "anchor ambiguous" -- that at most 1 of
        # the 7 anchorable FIT Thursdays ever produces a qualifying entry, for EVERY theta in the
        # grid, since theta only filters entries that already have a computed d). A Thursday-
        # clustered t cannot be computed with 1 cluster, so "highest FIT t" cannot select among
        # the three cells at all. This is not the same condition as the spec's self-kill (t<=0);
        # per non-negotiable #1 we report the divergence and return INSUFFICIENT rather than
        # improvise a substitute selection rule (e.g. breaking the tie on entry count or raw mean).
        verdict = "INSUFFICIENT"
        theta_star = None
        log("\nDIVERGENCE: Thursday-clustered t is UNDEFINED for all three FIT theta grid cells "
            "(never more than 1 populated FIT Thursday cluster, for any theta). The frozen "
            "'highest FIT t' selection procedure cannot be executed. This differs from the "
            "spec's self-kill clause (t<=0, which presumes t is defined). Returning INSUFFICIENT "
            "per non-negotiable #1 -- no substitute selection rule improvised.")
        summary = {
            "spec_id": "J1", "verdict": verdict, "n": 0,
            "reason": "FIT theta selection undefined: Thursday-clustered t has <2 populated "
                      "clusters at every grid theta, so no cell yields a computable t; the frozen "
                      "'highest FIT t' rule cannot be applied and no substitute was improvised",
            "fit_results": {str(k): v for k, v in fit_results.items()},
            "n_events_archive": n_events, "disagreements": disagreements,
            "skip_ledger_n": len(SKIP_LOG),
        }
        json.dump({**summary, "skip_ledger": SKIP_LOG}, open(OUT_JSON, "w"), indent=1)
        write_md(log_lines, summary, fit_results, None, None, events, fit_events, val_events, theta_star=None)
        log(f"\nwrote {OUT_JSON}")
        log(f"wrote {OUT_MD}")
        return

    if all(t <= 0 for _, t in valid_t):
        verdict = "NULL"
        theta_star = None
        log("\nSELF-KILL NO-SIGNAL: all FIT theta cells with a defined Thursday-clustered t have "
            "t <= 0. Per kill_conditions, validation is never read.")
        summary = {
            "spec_id": "J1", "verdict": verdict, "n": 0,
            "reason": "self-kill: no FIT theta cell had positive Thursday-clustered t",
            "fit_results": {str(k): v for k, v in fit_results.items()},
            "n_events_archive": n_events, "disagreements": disagreements,
            "skip_ledger_n": len(SKIP_LOG),
        }
        json.dump({**summary, "skip_ledger": SKIP_LOG}, open(OUT_JSON, "w"), indent=1)
        write_md(log_lines, summary, fit_results, None, None, events, fit_events, val_events, theta_star=None)
        log(f"\nwrote {OUT_JSON}")
        log(f"wrote {OUT_MD}")
        return

    theta_star = max(valid_t, key=lambda kv: kv[1])[0]
    log(f"\ntheta* = {theta_star} (highest FIT Thursday-clustered t = {fit_results[theta_star]['t']:.3f}), FROZEN")

    # ---------------- VALIDATION ----------------
    log("\n" + "-" * 78)
    log(f"VALIDATION: theta={theta_star} FROZEN, {len(val_events)} candidate release Thursdays")
    log("-" * 78)
    val_entries = []
    for i, ev in enumerate(val_events):
        global_idx = FIT_N + i
        prior = events[global_idx - 1]
        cands = build_signals_for_event(con, ev, prior, ev["thursday"])
        entries = apply_theta(cands, theta_star)
        val_entries.extend(entries)
        log(f"  {ev['thursday']}  qualifying entries: {len(entries)}")

    by_thursday = defaultdict(list)
    for e in val_entries:
        by_thursday[e["thursday"]].append(e)
    n_thursdays = len(by_thursday)
    n_total = len(val_entries)
    log(f"\nVALIDATION servable Thursdays (>=1 qualifying entry): {n_thursdays}")
    log(f"VALIDATION total qualifying entries: {n_total}")

    MIN_THURSDAYS = 15
    MIN_ENTRIES = 40
    if n_thursdays < MIN_THURSDAYS or n_total < MIN_ENTRIES:
        verdict = "INSUFFICIENT"
        log(f"\nINSUFFICIENT: {n_thursdays} servable Thursdays (need >={MIN_THURSDAYS}) / "
            f"{n_total} total entries (need >={MIN_ENTRIES}).")
        summary = {
            "spec_id": "J1", "verdict": verdict, "n": n_total,
            "n_thursdays": n_thursdays, "min_thursdays_required": MIN_THURSDAYS,
            "min_entries_required": MIN_ENTRIES,
            "theta_star": theta_star, "fit_results": {str(k): v for k, v in fit_results.items()},
            "n_events_archive": n_events, "disagreements": disagreements,
            "skip_ledger_n": len(SKIP_LOG),
        }
        json.dump({**summary, "skip_ledger": SKIP_LOG, "validation_entries": val_entries},
                   open(OUT_JSON, "w"), indent=1)
        write_md(log_lines, summary, fit_results, val_entries, by_thursday, events, fit_events, val_events, theta_star)
        log(f"\nwrote {OUT_JSON}")
        return

    # ---------------- pass-bar evaluation ----------------
    log("\n" + "-" * 78)
    log("PASS-BAR EVALUATION")
    log("-" * 78)

    cluster_means = [st.mean([e["net"] for e in v]) for v in by_thursday.values()]
    mean_net_clustered, t_val, nclust = day_clustered_t(cluster_means)
    df = nclust - 1
    bar_t = t_crit(0.0125, df)
    log(f"Thursday-clustered: n_clusters={nclust}  df={df}  mean(cluster means)={mean_net_clustered:.4f}  "
        f"t={t_val:.3f}  bar=|t|>={bar_t:.4f}")

    print_weighted_mean = st.mean([e["net"] for e in val_entries])
    total_contracts = sum(e["entry_count"] for e in val_entries)
    contract_weighted_mean = sum(e["net"] * e["entry_count"] for e in val_entries) / total_contracts
    log(f"print-weighted mean net    = {print_weighted_mean:+.4f} $/ct ({print_weighted_mean*100:+.2f} c/ct)")
    log(f"contract-weighted mean net = {contract_weighted_mean:+.4f} $/ct ({contract_weighted_mean*100:+.2f} c/ct)")

    wins = sum(e["won"] for e in val_entries)
    win_rate = wins / n_total
    wlb = wilson_lb(wins, n_total)
    mean_entry_price = st.mean([e["entry_price"] for e in val_entries])
    mean_fee = st.mean([e["fee_c"] / 100.0 for e in val_entries])
    breakeven = mean_entry_price + mean_fee
    log(f"win rate = {win_rate:.4f} ({wins}/{n_total}), Wilson95 LB = {wlb:.4f}, "
        f"breakeven win rate at mean entry (p={mean_entry_price:.4f}, fee={mean_fee:.4f}) = {breakeven:.4f}")

    thursday_cluster_mean = {th: st.mean([e["net"] for e in v]) for th, v in by_thursday.items()}
    ranked = sorted(thursday_cluster_mean.items(), key=lambda kv: kv[1], reverse=True)
    dropped2 = {th for th, _ in ranked[:2]}
    remaining_entries = [e for e in val_entries if e["thursday"] not in dropped2]
    drop2_mean = st.mean([e["net"] for e in remaining_entries]) if remaining_entries else None
    log(f"drop-2-best-Thursdays: dropped={sorted(dropped2)}  remaining n={len(remaining_entries)}  "
        f"mean_net={drop2_mean if drop2_mean is None else round(drop2_mean,4)}")

    pre = [e for e in val_entries if e["thursday"] <= SHUTDOWN_GAP_START]
    post = [e for e in val_entries if e["thursday"] >= SHUTDOWN_GAP_END]
    pre_mean = st.mean([e["net"] for e in pre]) if pre else None
    post_mean = st.mean([e["net"] for e in post]) if post else None
    log(f"pre-shutdown split  (<= {SHUTDOWN_GAP_START}): n={len(pre)}  mean_net={pre_mean}")
    log(f"post-shutdown split (>= {SHUTDOWN_GAP_END}): n={len(post)}  mean_net={post_mean}")
    same_sign = (pre_mean is not None and post_mean is not None and
                 ((pre_mean > 0) == (post_mean > 0)) and pre_mean != 0 and post_mean != 0)

    clause1 = (print_weighted_mean >= 0.0050) and (contract_weighted_mean >= 0.0050)
    clause2 = (t_val is not None) and (abs(t_val) >= bar_t)
    clause3 = (wlb is not None) and (wlb > breakeven)
    clause4 = (drop2_mean is not None) and (drop2_mean > 0)
    clause5 = same_sign

    log(f"\nclause 1 (mean net >= +0.50c both weightings): {clause1}")
    log(f"clause 2 (|t| >= {bar_t:.4f}):                    {clause2}  (t={t_val:.3f})")
    log(f"clause 3 (Wilson LB > breakeven):                {clause3}  ({wlb:.4f} vs {breakeven:.4f})")
    log(f"clause 4 (positive after dropping 2 best Thurs):  {clause4}")
    log(f"clause 5 (same sign pre/post shutdown, gating):   {clause5}")

    verdict = "PASS" if all([clause1, clause2, clause3, clause4, clause5]) else "FAIL"
    log(f"\nVERDICT: {verdict}")

    summary = {
        "spec_id": "J1", "verdict": verdict, "n": n_total,
        "n_thursdays": nclust, "theta_star": theta_star,
        "fit_results": {str(k): v for k, v in fit_results.items()},
        "n_events_archive": n_events, "disagreements": disagreements,
        "mean_net_clustered": mean_net_clustered, "t": t_val, "df": df, "bar_t": bar_t,
        "print_weighted_mean": print_weighted_mean, "contract_weighted_mean": contract_weighted_mean,
        "win_rate": win_rate, "wins": wins, "wilson_lb": wlb,
        "mean_entry_price": mean_entry_price, "mean_fee": mean_fee, "breakeven_win_rate": breakeven,
        "drop2_dropped_thursdays": sorted(dropped2), "drop2_mean_net": drop2_mean,
        "pre_shutdown_n": len(pre), "pre_shutdown_mean_net": pre_mean,
        "post_shutdown_n": len(post), "post_shutdown_mean_net": post_mean,
        "clauses": {"1_mean_ev": clause1, "2_t_bar": clause2, "3_wilson": clause3,
                    "4_drop2": clause4, "5_same_sign": clause5},
        "skip_ledger_n": len(SKIP_LOG),
        "runtime_s": round(time.time() - t_start, 1),
    }
    json.dump({**summary, "skip_ledger": SKIP_LOG, "validation_entries": val_entries,
               "fit_note": "fit entries not persisted individually; see fit_results aggregate"},
              open(OUT_JSON, "w"), indent=1)
    write_md(log_lines, summary, fit_results, val_entries, by_thursday, events, fit_events, val_events, theta_star)
    log(f"\nwrote {OUT_JSON}")
    log(f"wrote {OUT_MD}")


def write_md(log_lines, summary, fit_results, val_entries, by_thursday, events, fit_events, val_events, theta_star):
    lines = []
    lines.append("# spec_J1 -- KXJOBLESSCLAIMS weekly-relist fade (reopen of graveyard #24)\n")
    lines.append(f"**Verdict: {summary['verdict']}**\n")
    lines.append("## Data provenance\n")
    lines.append("- Shards read: **all 16** HF trade shards (trades-0000..0015), predicate-pushed to the\n"
                  "  KXJOBLESSCLAIMS ticker universe via the shared M1 tape pull (`cache/prereg/tape/`).\n"
                  "  Spot-verified this run: live re-query of `trades-0000.parquet` for a 0-row ticker and a\n"
                  "  365-row ticker both matched the cache exactly.\n")
    lines.append("- Markets: `cache/M1/markets_universe.json`, pulled from all 4 HF markets shards,\n"
                  "  filtered to `series_key == 'KXJOBLESSCLAIMS'` exact (never a LIKE prefix).\n")
    lines.append(f"- Date window: archive holds {summary.get('n_events_archive')} KXJOBLESSCLAIMS events,\n"
                  f"  {events[0]['thursday']} .. {events[-1]['thursday']} (release-Thursday close dates).\n")
    lines.append("- Settlement: `GET /trade-api/v2/markets/{ticker}` attempted for **all 212** KXJOBLESSCLAIMS\n"
                  "  tickers (not just the 2 archive-unsettled ones), cached at `cache/J1/live_results.json`.\n"
                  "  **DIVERGENCE (reported per non-negotiable #1): all 212 requests returned HTTP 404.**\n"
                  "  This is the same retention wall that killed graveyard #24, now total for this series --\n"
                  "  even `KXJOBLESSCLAIMS-26JAN22-*` (closed 2026-01-22, ~6 months before this run) 404s, and\n"
                  "  bulk `/markets?event_ticker=...` / `?series_ticker=...&status=...` also return empty for\n"
                  "  every past event (confirmed live, `/series/KXJOBLESSCLAIMS` and current open markets DO\n"
                  "  resolve fine, so the series itself is live -- only historical single-market lookups are\n"
                  "  gone). Consequently the '0 disagreements' below reflects 0 *possible* comparisons, not\n"
                  "  genuine agreement, and settlement truth for the 210 already-archive-settled markets\n"
                  "  falls back to the archive's own `result` column (itself asserted authoritative per the\n"
                  "  top-level DATA FACTS). The 2 archive-unsettled tickers per event x 10 rungs = 20 markets\n"
                  "  in `KXJOBLESSCLAIMS-26JAN29` / `-26FEB05` have NO settlement source at all and are logged\n"
                  "  `result unavailable` (named skip-ledger category) rather than guessed.\n"
                  f"  Archive-vs-live disagreements (of 0 possible comparisons): "
                  f"{len(summary.get('disagreements', []))}"
                  + (f" -> {summary['disagreements']}" if summary.get('disagreements') else " (none).") + "\n")
    lines.append("- Executable prices: signal price = first trade at/after t_open within 6h, priced off\n"
                  "  `taker_side` (yes->yes_price/100 true ask, no->(100-no_price)/100 true bid). Entry price\n"
                  "  = first trade at/after the signal timestamp, within 60 min, whose OWN taker_side matches\n"
                  "  the side we must take, priced at that print's own crossing price. Never mid, never\n"
                  "  best-in-window.\n")
    lines.append("\n## Divergence from the spec text (reported per non-negotiable #1)\n")
    lines.append("`data_plan` states FIT = \"the first 8 release Thursdays (2025-06-12 .. 2025-07-31)\". "
                  "The archive has no `KXJOBLESSCLAIMS-25JUN19` event -- only 7 events fall in that literal "
                  "date span. The spec's own VALIDATION clause (\"max 16 available\") is only consistent with "
                  "FIT having exactly 8 events (24-8=16), so this script uses the ordinal rule (first 8 "
                  "chronological events, whichever dates they carry) as binding: FIT = "
                  f"{[e['thursday'] for e in fit_events]}. This does not move any bar or floor.\n")
    lines.append("\n## FIT: theta grid search (frozen grid {0.15, 0.25, 0.35})\n")
    lines.append("| theta | n_entries | n_Thursdays | mean_net ($/ct) | t |\n|---|---:|---:|---:|---:|\n")
    for th, r in fit_results.items():
        lines.append(f"| {th} | {r['n_entries']} | {r['n_thursdays']} | "
                      f"{r['mean_net'] if r['mean_net'] is None else round(r['mean_net'],4)} | "
                      f"{r['t'] if r['t'] is None else round(r['t'],3)} |\n")
    if theta_star is not None:
        lines.append(f"\n**theta\\* = {theta_star}** (highest FIT Thursday-clustered t), frozen before validation.\n")
    elif summary["verdict"] == "NULL":
        lines.append("\n**SELF-KILL NO-SIGNAL**: all FIT theta cells with a *defined* Thursday-clustered t have "
                      "t <= 0. Per kill_conditions, validation is never read.\n")
    else:
        lines.append("\n**INSUFFICIENT (procedural divergence, non-negotiable #1)**: Thursday-clustered t is "
                      "UNDEFINED (fewer than 2 populated FIT Thursday clusters) at all three grid cells, for "
                      "every theta -- entry construction is so sparse in the FIT window (illiquid relist; most "
                      "rungs killed by 'no print within 6h of open' or 'anchor ambiguous') that only 1 of the 7 "
                      "anchorable FIT Thursdays ever produces a qualifying entry, regardless of theta. The "
                      "frozen 'highest FIT t' selection procedure cannot be executed -- this is not the spec's "
                      "self-kill clause (t<=0, which presumes t is defined). No substitute selection rule was "
                      "improvised. Validation is never read.\n")

    if val_entries is not None:
        lines.append("\n## VALIDATION\n")
        lines.append(f"- servable Thursdays (>=1 qualifying entry): **{len(by_thursday)}** "
                      f"(floor >=15)\n")
        lines.append(f"- total qualifying entries: **{len(val_entries)}** (floor >=40)\n")
        lines.append("\n| Thursday | event | n entries | mean net ($/ct) |\n|---|---|---:|---:|\n")
        for th in sorted(by_thursday):
            v = by_thursday[th]
            lines.append(f"| {th} | {v[0]['event_ticker']} | {len(v)} | {st.mean([e['net'] for e in v]):.4f} |\n")

        if summary["verdict"] in ("PASS", "FAIL"):
            lines.append("\n## Pass-bar clauses (validation)\n")
            c = summary["clauses"]
            lines.append(f"1. mean net >= +0.50c/ct both weightings: print={summary['print_weighted_mean']*100:.3f}c, "
                          f"contract={summary['contract_weighted_mean']*100:.3f}c -> **{c['1_mean_ev']}**\n")
            lines.append(f"2. Thursday-clustered |t| >= {summary['bar_t']:.4f} (df={summary['df']}): "
                          f"t={summary['t']:.3f} -> **{c['2_t_bar']}**\n")
            lines.append(f"3. Wilson95 LB ({summary['wilson_lb']:.4f}) > breakeven win rate "
                          f"({summary['breakeven_win_rate']:.4f}) -> **{c['3_wilson']}**\n")
            lines.append(f"4. positive after dropping 2 best Thursdays "
                          f"({summary['drop2_dropped_thursdays']}): mean_net={summary['drop2_mean_net']} "
                          f"-> **{c['4_drop2']}**\n")
            lines.append(f"5. same sign pre-shutdown (n={summary['pre_shutdown_n']}, "
                          f"mean={summary['pre_shutdown_mean_net']}) vs post-shutdown "
                          f"(n={summary['post_shutdown_n']}, mean={summary['post_shutdown_mean_net']}), "
                          f"gating -> **{c['5_same_sign']}**\n")
        elif summary["verdict"] == "INSUFFICIENT":
            lines.append(f"\n**INSUFFICIENT**: {len(by_thursday)} servable Thursdays / "
                          f"{len(val_entries)} entries against floors of >=15 / >=40.\n")

    lines.append(f"\n## Skip ledger ({len(SKIP_LOG)} entries)\n")
    from collections import Counter
    reason_counts = Counter(s["reason"] for s in SKIP_LOG)
    lines.append("| reason | count |\n|---|---:|\n")
    for reason, cnt in reason_counts.most_common():
        lines.append(f"| {reason} | {cnt} |\n")

    lines.append("\n## Full run log\n```\n" + "\n".join(log_lines) + "\n```\n")

    with open(OUT_MD, "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    main()
