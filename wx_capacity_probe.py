#!/usr/bin/env python3
"""wx_capacity_probe.py -- is DEPTH_CAP=25 right? Measure ACTUAL fillable depth on live Kalshi weather books.

The capacity ceiling (~$750/mo free) is set almost entirely by DEPTH_CAP=25 -- the assumed max contracts a
single fire's book can absorb without moving the price. That was a Tier-1 estimate ("books 5-100ct"); it is
THE lever on the monthly ceiling, so it's worth measuring against real order books. This samples today's live
KXHIGH/KXLOWT ladders and, for each active rung, reads the public order book to report how many contracts sit
at the ask within our MAX_PAY_CENTS (98c) -- i.e. how many we could actually buy right now without walking the
book. Aggregated, that says whether 25 is conservative, about right, or optimistic.

Modes:
    (default)    one text sweep: aggregate fillable-depth stats printed to stdout (the original probe)
    --retro      retrospective depth proxy from the backtest (volume/oi at exec)
    --snapshot   STRUCTURED sweep: append one JSONL line per near-lock rung per sweep (FULL ladder levels,
                 both sides, PLUS the running-extreme temperature) to wx_book_snapshots.jsonl -- the dataset
                 DEPTH_CAP calibration AND the maker study both need. Schema: see snapshot() docstring + the
                 committed wx_book_snapshot_schema.md (the maker-study sibling consumes this file; change it
                 only with a schema-version bump there).
    --snapshot-loop [--minutes M] [--every E]
                 Run repeated --snapshot sweeps inside ONE process for up to M minutes (default 25), spaced
                 ~E minutes apart (default 5, +/- small jitter). This is the fix for GitHub Actions cron
                 coalescing: observed kwx-depthprobe runs land ~60 min apart despite a 30-min cron entry (a
                 known Actions scheduling behavior where a repo's second within-hour trigger gets dropped
                 under platform load), so a single job now takes several closely-spaced snapshots itself
                 (same "loop inside one leg" pattern kwx-live uses for continuity) instead of depending on
                 cron to hit the cadence. Exits early if the time budget would be exceeded mid-loop.
    --report     read the accrued snapshots and print the DEPTH_CAP evidence (depth distribution at <=98c on
                 near-lock rungs, share of empty books, per-station medians).
    --prune-days N
                 Rewrite wx_book_snapshots.jsonl keeping only rows whose ts_utc is within the last N days
                 (default 21 -- the maker study's docstring only needs "1-2 weeks"; DEPTH_CAP calibration is
                 similar). Bounds the committed-file growth from the denser --snapshot-loop cadence. No-op
                 (prints and exits 0) if nothing is old enough to drop.

PROPOSE-ONLY: reads public market data only. No auth, no orders.
"""
import json, os, random, ssl, statistics as st, sys, time, datetime as dt, urllib.request
import kwx_runner as R

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"
SNAP_PATH = os.path.join(HERE, "wx_book_snapshots.jsonl")   # force-added by the kwx-depthprobe workflow

# A rung is a NEAR-LOCK CANDIDATE when its ladder-quote yes ask sits in [NEARLOCK_MIN_ASK_C, MAX_PAY_CENTS]:
# the market already leans yes (implied p >= ~0.5, i.e. the temp is approaching/at the strike -- exactly the
# books a mechanical-lock fire will hit) but the rung is still buyable under the bot's 98c pay cap. Below 50c
# the rung is far from locking (book depth there isn't what a fire consumes); above 98c it's dead-on-arrival.
NEARLOCK_MIN_ASK_C = 50
BOOK_SLEEP_S = 0.2      # polite pause between public order-book requests (one sweep hits ~40 events + books)
DEFAULT_PRUNE_DAYS = 21   # maker study only needs "1-2 weeks"; keep a safety margin, drop the rest


def _get(url, to=20):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=to, context=_CTX))


def _levels_c(ob, key):
    """Normalize one book side to [[price_c, count], ...]. Kalshi has served two encodings: legacy
    'orderbook' {key: [[price_c, size], ...]} in int cents, and current 'orderbook_fp'
    {key_dollars: [["0.9700", "25.00"], ...]} in dollar strings. The matched KEY decides the unit
    (a per-value guess would misread a legit 1c legacy level as $1)."""
    raw, dollars = ob.get(key), False
    if raw is None:
        raw, dollars = ob.get(key + "_dollars"), True
    out = []
    for lvl in (raw or []):
        p, sz = float(lvl[0]), float(lvl[1])
        out.append([int(round(p * 100 if dollars else p)), int(round(sz))])
    return out


def book_levels(ticker):
    """Fetch the public order book -> (yes_bid_levels, yes_ask_levels), both [[price_c, count], ...] sorted
    best-first (bids: highest price first; asks: lowest first), or None on fetch failure.
    Kalshi books store resting BIDS on both sides: the 'yes' side is resting YES bids; the 'no' side is
    resting NO bids, and a NO bid at price q IS a YES ask at (100 - q) -- YES buyers lift those NO orders.
    Handles both the legacy 'orderbook' (int cents) and current 'orderbook_fp' (dollar strings) payloads."""
    try:
        d = _get(f"{KBASE}/markets/{ticker}/orderbook")
        ob = d.get("orderbook") or d.get("orderbook_fp") or {}
    except Exception:
        return None
    yes_bids = _levels_c(ob, "yes")
    no_bids = _levels_c(ob, "no")
    yes_asks = [[100 - p, n] for p, n in no_bids]
    yes_bids.sort(key=lambda l: -l[0])
    yes_asks.sort(key=lambda l: l[0])
    return yes_bids, yes_asks


def orderbook_ask_depth(ticker, max_pay_c=98):
    """Contracts available to BUY YES at <= max_pay_c cents (sum of yes-ask levels within the cap).
    Thin wrapper over book_levels() so the text probe and the structured snapshot share one parser
    (the legacy direct 'orderbook' read silently returned None once Kalshi moved to 'orderbook_fp')."""
    lv = book_levels(ticker)
    if lv is None:
        return None
    return sum(n for p, n in lv[1] if p <= max_pay_c)


def retro():
    """Retrospective depth-proxy read from the backtest (available any hour, unlike the live probe which needs
    active US markets). volume_at_exec / oi_at_exec sit at each lock moment. CAVEAT: traded volume + open
    interest are NOT resting-ask depth -- they bound liquidity but don't pin the fillable number; the live
    probe is the definitive measure. Still, they answer the shape: are the fires our FREE feed catches on
    thin/quiet rungs (DEPTH_CAP~right) or deep ones (headroom)?"""
    import json, statistics as st
    raw = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_trackA_results_raw.json")))
    caught_vol, caught_oi = [], []
    for r in raw:
        c = r["cells"].get("1_3")
        if not c or not c.get("fired") or not c.get("exec_price") or c["exec_price"] >= 0.99:
            continue
        g = c.get("decay_gap_by_min", {}).get("10")   # catchable on the free/MADIS feed (~10 min)?
        if g is None or (1 - g) >= 0.99:
            continue
        caught_vol.append(c.get("volume_at_exec") or 0)
        caught_oi.append(c.get("oi_at_exec") or 0)
    if not caught_vol:
        print("no caught fires"); return
    pc = lambda a, q: sorted(a)[min(len(a) - 1, int(q * len(a)))]
    n = len(caught_vol)
    print(f"RETROSPECTIVE depth proxy | {n} fires catchable at ~10min (free feed)")
    print(f"  volume_at_exec (traded):  median {st.median(caught_vol):.0f}  p75 {pc(caught_vol,.75):.0f}  p90 {pc(caught_vol,.90):.0f}")
    print(f"  oi_at_exec (open interest): median {st.median(caught_oi):.0f}  p90 {pc(caught_oi,.90):.0f}")
    print(f"  share of caught fires with volume_at_exec < DEPTH_CAP({R.DEPTH_CAP}): "
          f"{100*sum(1 for v in caught_vol if v < R.DEPTH_CAP)/n:.0f}%")
    print("  read: the free feed catches thin/quiet rungs (low traded volume) -> DEPTH_CAP~25 is likely near-right\n"
          "  for them, NOT obviously conservative. The depth headroom lives in the DEEP/fast fires that need\n"
          "  Synoptic; so Synoptic likely compounds -- more fires AND deeper fills. Live probe confirms the number.")


# ---------------- structured snapshots (--snapshot / --report) ----------------
def _mkt_int(m, *keys):
    """First parseable int among the market payload keys (Kalshi serves e.g. 'volume' or 'volume_fp')."""
    for k in keys:
        v = m.get(k)
        if v is None:
            continue
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            continue
    return None


def _running_extreme_f(station, lst_date, offset, kind):
    """Best-effort running-extreme temperature (degF) for this station/day, via the SAME read-only feed
    abstraction kwx_runner uses to gate live fires (R.feed_for_station(...).running_extreme(...)) -- no
    trading decision here, just the observed value the maker study needs to know how close a rung is to
    locking. Returns None (never raises) on any feed error/outage; the caller logs that absence rather than
    dropping the row, matching wx_maker_study's documented tolerance for missing running_extreme_f."""
    try:
        r = R.feed_for_station(station).running_extreme(station, lst_date, offset, kind)
        return r["extreme_f"] if r else None
    except Exception:
        return None


def snapshot():
    """One structured sweep of the books behind today's NEAR-LOCK candidate rungs -> append JSONL rows.

    Appends ONE line per near-lock rung per sweep to wx_book_snapshots.jsonl. SCHEMA (v2 -- consumed by the
    maker-study sibling; keep in sync with wx_book_snapshot_schema.md, bump schema_v on any change):
      schema_v         : 2 (v2 adds running_extreme_f; v1 rows lack it and readers must tolerate that)
      ts_utc           : ISO-8601 UTC capture time (same for every row of one sweep)
      series           : Kalshi series (e.g. KXHIGHDEN / KXLOWTDEN)
      event_ticker     : the city-day event (e.g. KXHIGHDEN-26JUL19)
      ticker           : the rung's market ticker
      station / kind / lst_date : METAR station, 'max'|'min', the market's local-standard-time date
      floor_strike / cap_strike : rung strikes in degF (null = open-ended side)
      status           : market status from the event payload ('active', ...)
      volume / open_interest    : traded contracts / open interest (null if the API omits both encodings)
      quote_yes_ask_c / quote_yes_bid_c : ladder-quote top of book in cents (what gated the near-lock filter)
      yes_bid_levels   : FULL ladder of resting YES bids, [[price_c, count], ...] best-first (price desc)
      yes_ask_levels   : FULL ladder of YES asks (= NO bids at 100-q), [[price_c, count], ...] best-first (asc)
      best_yes_bid / best_yes_ask : top-of-book cents from the levels (null when that side is empty)
      depth_at_or_below_98c       : sum of yes-ask counts at price <= MAX_PAY_CENTS -- the fillable-depth
                                    number DEPTH_CAP must be calibrated against
      running_extreme_f           : observed running max/min (degF) for this station/day at capture time,
                                    from the same read-only feed kwx_runner gates live fires with (null if
                                    the feed errored/had no data this sweep) -- the field the maker study
                                    needs to decide "approaching lock" and place a hypothetical bid; one
                                    feed call per (station, lst_date, kind), reused across every rung of
                                    that event/kind so it costs one extra request per event, not per rung.
    An EMPTY book still logs a row (empty level lists, depth 0): the share of empty near-lock books is itself
    DEPTH_CAP evidence. Rows are NOT deduped across sweeps -- the time series through the fire window is the
    point. Book fetch failures are skipped (transient), not logged as empties."""
    now = dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0)
    mkts = R.active_market_days()
    print(f"snapshot sweep {now.isoformat()} | {len(mkts)} city-market-days | "
          f"near-lock = quote yes_ask in [{NEARLOCK_MIN_ASK_C},{R.MAX_PAY_CENTS}]c")
    n_rows = n_events = n_bookfail = n_ext_ok = 0
    examples = []
    with open(SNAP_PATH, "a") as fout:
        for series, ev, station, offset, lst_date, kind in mkts:
            try:
                d = _get(f"{KBASE}/events/{ev}")
            except Exception:
                continue        # event not open (off-season city / pre-open) -- normal, skip quietly
            n_events += 1
            ext_f = None          # fetched once per event (same station/day/kind for every rung in it)
            ext_fetched = False
            for m in d.get("markets", []):
                if m.get("status") not in ("active", "open", None):
                    continue
                ask_d, bid_d = R._dollars(m, "yes_ask"), R._dollars(m, "yes_bid")
                quote_ask_c = int(round(ask_d * 100)) if ask_d else None
                quote_bid_c = int(round(bid_d * 100)) if bid_d else None
                # near-lock gate: see NEARLOCK_MIN_ASK_C comment. No quote at all -> not a candidate.
                if not quote_ask_c or not (NEARLOCK_MIN_ASK_C <= quote_ask_c <= R.MAX_PAY_CENTS):
                    continue
                if not ext_fetched:   # lazy + cached: only pay the feed call for events with a candidate rung
                    ext_f = _running_extreme_f(station, lst_date, offset, kind)
                    ext_fetched = True
                    if ext_f is not None:
                        n_ext_ok += 1
                lv = book_levels(m["ticker"])
                time.sleep(BOOK_SLEEP_S)         # be polite: one public book request per near-lock rung
                if lv is None:
                    n_bookfail += 1
                    continue
                yes_bids, yes_asks = lv
                row = {
                    "schema_v": 2, "ts_utc": now.isoformat(),
                    "series": series, "event_ticker": ev, "ticker": m["ticker"],
                    "station": station, "kind": kind, "lst_date": lst_date,
                    "floor_strike": m.get("floor_strike"), "cap_strike": m.get("cap_strike"),
                    "status": m.get("status"),
                    "volume": _mkt_int(m, "volume", "volume_fp"),
                    "open_interest": _mkt_int(m, "open_interest", "open_interest_fp"),
                    "quote_yes_ask_c": quote_ask_c, "quote_yes_bid_c": quote_bid_c,
                    "yes_bid_levels": yes_bids, "yes_ask_levels": yes_asks,
                    "best_yes_bid": yes_bids[0][0] if yes_bids else None,
                    "best_yes_ask": yes_asks[0][0] if yes_asks else None,
                    "depth_at_or_below_98c": sum(n for p, n in yes_asks if p <= R.MAX_PAY_CENTS),
                    "running_extreme_f": ext_f,
                }
                fout.write(json.dumps(row) + "\n")
                n_rows += 1
                if len(examples) < 8:
                    examples.append(row)
    print(f"logged {n_rows} near-lock rung rows over {n_events} open events "
          f"({n_bookfail} book fetch failures skipped, running_extreme_f present for {n_ext_ok} events) "
          f"-> {SNAP_PATH}")
    for r in examples:
        print(f"  {r['ticker']:<24} ask={r['quote_yes_ask_c']}c bid={r['quote_yes_bid_c']}c "
              f"depth<=98c={r['depth_at_or_below_98c']:>4}ct  ext={r['running_extreme_f']}  "
              f"levels ask/bid={len(r['yes_ask_levels'])}/{len(r['yes_bid_levels'])}  "
              f"vol={r['volume']} oi={r['open_interest']}")


def snapshot_loop(minutes=25.0, every_min=5.0):
    """Repeat --snapshot inside ONE process for up to `minutes`, spaced ~`every_min` apart (+/- 20% jitter
    to avoid a thundering-herd pattern against the public API). Purpose: GitHub Actions cron coalescing --
    observed kwx-depthprobe runs land ~60 min apart despite a 30-min cron entry (the platform silently drops
    a repo's second within-hour trigger under load; this is a documented Actions behavior, not a bug in this
    script) -- so density has to come from INSIDE one job rather than from cron precision, the same "loop
    inside one leg" shape kwx-live already uses for continuity. Stops early (does not start a sweep that
    would run past the budget) so it stays well inside the job's timeout-minutes with room for the git
    commit/push step."""
    deadline = time.monotonic() + minutes * 60
    n = 0
    while True:
        t0 = time.monotonic()
        print(f"--- snapshot-loop sweep {n + 1} ({(deadline - t0) / 60:.1f} min left in budget) ---")
        try:
            snapshot()
        except Exception as e:
            print(f"  [snapshot-loop] sweep failed, continuing: {type(e).__name__}: {e}")
        n += 1
        elapsed = time.monotonic() - t0
        gap = max(5.0, every_min * 60 * random.uniform(0.8, 1.2))
        nxt = time.monotonic() + max(0.0, gap - elapsed)
        if nxt >= deadline:
            break
        time.sleep(max(0.0, nxt - time.monotonic()))
    print(f"snapshot-loop done: {n} sweep(s) in {minutes:.0f}-min budget")


def prune_days(days=DEFAULT_PRUNE_DAYS):
    """Rewrite SNAP_PATH keeping only rows within the last `days` (by ts_utc), so the denser --snapshot-loop
    cadence doesn't let the committed jsonl grow unbounded. The maker study only needs 1-2 weeks; DEPTH_CAP
    calibration is similarly a rolling-window question, so old rows are dead weight, not lost history that
    matters. Malformed lines are dropped (same tolerance as every other reader in this file). No-op (prints,
    exits without writing) if nothing would be dropped, so a routine cron call doesn't create a no-op commit."""
    if not os.path.exists(SNAP_PATH):
        print("prune: no snapshot file yet, nothing to do")
        return
    cutoff = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=days)
    kept, dropped, bad = [], 0, 0
    for line in open(SNAP_PATH):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            ts = dt.datetime.fromisoformat(str(r["ts_utc"]).replace("Z", "+00:00"))
        except Exception:
            bad += 1
            continue     # drop unparseable/torn lines rather than propagate them forever
        if ts >= cutoff:
            kept.append(line)
        else:
            dropped += 1
    if dropped == 0 and bad == 0:
        print(f"prune: {len(kept)} rows, all within {days}d -- nothing to drop")
        return
    with open(SNAP_PATH, "w") as f:
        for line in kept:
            f.write(line + "\n")
    print(f"prune: kept {len(kept)} rows (< {days}d old), dropped {dropped} stale + {bad} malformed")


def report_snapshots():
    """DEPTH_CAP evidence from the accrued structured snapshots: the distribution of fillable depth at
    <=98c on near-lock rungs at fire-window times -- the number DEPTH_CAP=25 was only ever a proxy for."""
    rows = []
    if os.path.exists(SNAP_PATH):
        for line in open(SNAP_PATH):
            try:
                rows.append(json.loads(line))
            except Exception:
                pass    # tolerate a torn line from a killed run; every good line still counts
    print(f"=== WX BOOK-SNAPSHOT REPORT (DEPTH_CAP evidence) | DEPTH_CAP(assumed)={R.DEPTH_CAP} ===")
    if not rows:
        print("no snapshots accrued yet -- run --snapshot during US-afternoon fire windows first.")
        return
    depths = sorted(r["depth_at_or_below_98c"] for r in rows)
    n = len(depths)
    pc = lambda q: depths[min(n - 1, int(q * n))]
    sweeps = len({r["ts_utc"] for r in rows})
    rung_days = len({(r["ticker"], r["lst_date"]) for r in rows})
    print(f"  rows: {n}  (sweeps: {sweeps}, unique rung-days: {rung_days}, "
          f"days: {len({r['lst_date'] for r in rows})})")
    print(f"  fillable YES depth at ask<={R.MAX_PAY_CENTS}c: median {st.median(depths):.0f}  "
          f"mean {st.mean(depths):.0f}  p25 {pc(.25)}  p75 {pc(.75)}  p90 {pc(.90)}  max {max(depths)}")
    empty = sum(1 for x in depths if x == 0)
    below = sum(1 for x in depths if x < R.DEPTH_CAP)
    above2 = sum(1 for x in depths if x >= 2 * R.DEPTH_CAP)
    print(f"  empty books (depth 0): {empty}/{n} ({100*empty/n:.0f}%)   "
          f"depth < DEPTH_CAP({R.DEPTH_CAP}): {below}/{n} ({100*below/n:.0f}%)   "
          f"depth >= 2x cap: {above2}/{n} ({100*above2/n:.0f}%)")
    per = {}
    for r in rows:
        per.setdefault(r["station"], []).append(r["depth_at_or_below_98c"])
    print("  per-station median depth (near-lock rows):")
    for stn, ds in sorted(per.items(), key=lambda kv: -st.median(kv[1])):
        print(f"    {stn:>6}: median {st.median(ds):>5.0f}ct  n={len(ds)}")
    print("  read: DEPTH_CAP should sit near the median fillable depth on these rungs. If depth<cap on most\n"
          "  rows, 25 rarely binds (ceiling is depth-real); if most rows sit >=2x cap, 25 is conservative and\n"
          "  the monthly ceiling rises roughly in proportion to raising it.")


def _arg_val(flag, default, cast=float):
    """Tiny positional-free option reader (`--flag VALUE`) -- avoids pulling in argparse for two knobs
    shared by a script that's otherwise plain sys.argv flag-checks."""
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            try:
                return cast(sys.argv[i + 1])
            except ValueError:
                pass
    return default


def main():
    if "--retro" in sys.argv:
        retro(); return
    if "--snapshot-loop" in sys.argv:
        snapshot_loop(minutes=_arg_val("--minutes", 25.0), every_min=_arg_val("--every", 5.0)); return
    if "--snapshot" in sys.argv:
        snapshot(); return
    if "--prune-days" in sys.argv:
        prune_days(days=int(_arg_val("--prune-days", DEFAULT_PRUNE_DAYS, cast=float))); return
    if "--report" in sys.argv:
        report_snapshots(); return
    mkts = R.active_market_days()
    print(f"sampling live Kalshi weather books | {len(mkts)} city-market-days today | DEPTH_CAP(assumed)={R.DEPTH_CAP}\n")
    depths = []
    n_rungs = 0
    per_city = {}
    for series, ev, station, offset, lst_date, kind in mkts:
        rungs = R.event_rungs(ev)
        if not rungs:
            continue
        city_depths = []
        for rr in rungs:
            ask = rr.get("yes_ask_c")
            if not ask or ask > R.MAX_PAY_CENTS:
                continue
            d = orderbook_ask_depth(rr["ticker"])
            time.sleep(BOOK_SLEEP_S)   # be polite to the public API (same pacing as --snapshot)
            if d is None:
                continue
            n_rungs += 1
            depths.append(d)
            city_depths.append(d)
        if city_depths:
            per_city[station] = (len(city_depths), st.median(city_depths))
    if not depths:
        print("no active tradeable rungs found right now (markets may be pre-open or fully repriced).")
        return
    depths.sort()
    p = lambda q: depths[min(len(depths) - 1, int(q * len(depths)))]
    print(f"tradeable rungs sampled: {n_rungs}")
    print(f"fillable YES depth at ask<=98c (contracts): median {st.median(depths):.0f}  "
          f"mean {st.mean(depths):.0f}  p25 {p(0.25):.0f}  p75 {p(0.75):.0f}  p90 {p(0.90):.0f}  max {max(depths)}")
    below = sum(1 for d in depths if d < R.DEPTH_CAP) / len(depths)
    print(f"share of rungs with depth < DEPTH_CAP(25): {100*below:.0f}%  "
          f"(if high, 25 rarely binds -> ceiling is depth-real; if low, 25 is conservative -> ceiling could rise)")
    print("\nper-station median fillable depth (rungs):")
    for stn, (n, med) in sorted(per_city.items(), key=lambda kv: -kv[1][1]):
        print(f"  {stn:>6}: median {med:>4.0f}ct over {n} rungs")
    print("\nread: DEPTH_CAP should sit near the median fillable depth of the rungs we actually fire on. If the "
          "measured median >> 25, raise DEPTH_CAP (ceiling rises); if << 25, the ceiling is even lower than modeled.")


if __name__ == "__main__":
    main()
