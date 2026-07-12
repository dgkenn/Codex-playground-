#!/usr/bin/env python3
"""kalshi_longshot_paper.py -- FORWARD paper-track of the longshot-maker harvest
(KALSHI_MAKER_VERDICT.md): sell overpriced longshots as a maker on soft, zero-maker-fee
Kalshi categories. Look-ahead-free out-of-sample validation of the +0.97c/contract edge
AND a real read on passive fill rate.

The edge: on soft markets a cheap YES longshot (mid < ~0.20) is overpriced; resting a
maker offer to SELL YES at the touch (yes_ask) collects the premium and wins ~ (1 - p_true)
of the time, where p_true < priced. P&L per contract at settle = entry - settle_yes.
Soft categories charge ZERO maker fee (fee_type=quadratic), so the premium is kept.

State persists across runs as JSON on the gha-data branch (the GHA workflow handles git):
  <state_dir>/longshot_pending.json  -- open paper positions awaiting settlement
  <state_dir>/longshot_settled.csv   -- realized results (append-only) + running aggregate
Each run: (1) SETTLE matured pendings -> append realized P&L; (2) SNAPSHOT new open longshots.

Public API, no auth, READ-ONLY, no money. PAPER ONLY.
    python kalshi_longshot_paper.py <state_dir>
"""
import sys, os, json, time, csv, urllib.request, urllib.parse, datetime as dt

BASE = "https://api.elections.kalshi.com/trade-api/v2"
# soft, mostly zero-maker-fee categories (KALSHI_MAKER_RANK.md). Flagship maker-fee SERIES
# are excluded per-market via the fee_type guard below.
CATS = ["Entertainment", "Science and Technology", "Climate and Weather", "Politics"]
# OPTIMIZED band/timing (KALSHI_LONGSHOT_OPTIMAL.md) so the forward paper-track validates the SAME
# strategy the bot deploys, not the old wide blend. Band [0.05,0.15); quote only the first half of life.
LONG_LO, LONG_HI = 0.05, 0.15     # optimal band -- net +5.45c vs the old [0.02,0.20] blend
MAXSPREAD = 0.10
MIN_VOL = 200.0                   # require some real volume to be plausibly fillable
MAX_LIFE_FRAC = 0.50              # quote only the first half of a market's life (late third is -EV)
MAX_DAYS_TO_CLOSE = 60             # LONGSHOT_RUNBOOK.md: forward-track should validate the SAME
                                   # deployable band as the live bot -- don't open positions that
                                   # won't mature for months/years (was unbounded; found markets
                                   # with close_time years out accumulating in longshot_pending.json)
STALE_PENDING_DAYS = 45            # drop (as expired_unscored) if still unresolved this long after snapshot


def _life_frac(m):
    try:
        o = dt.datetime.fromisoformat((m.get("open_time") or "").replace("Z", "+00:00"))
        c = dt.datetime.fromisoformat((m.get("close_time") or "").replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        span = (c - o).total_seconds()
        return (now - o).total_seconds() / span if span > 0 else None
    except Exception:
        return None


def _days_to_close(m):
    try:
        c = dt.datetime.fromisoformat((m.get("close_time") or "").replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        return (c - now).total_seconds() / 86400.0
    except Exception:
        return None
NEW_PER_RUN = 60                  # cap new snapshots/run


def get(path, params=""):
    u = f"{BASE}{path}" + ("?" + params if params else "")
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research"}), timeout=25))
        except Exception:
            if a == 3:
                return {}
            time.sleep(1.2*(a+1))


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def series_for(cat, cap=80):
    out, cur = [], ""
    while len(out) < cap:
        d = get("/series", f"category={urllib.parse.quote(cat)}&limit=100" + (f"&cursor={cur}" if cur else ""))
        out += [s["ticker"] for s in d.get("series", []) if s.get("ticker")]
        cur = d.get("cursor") or ""
        if not cur:
            break
    return out[:cap]


def open_markets(st, cap=200):
    out, cur = [], ""
    while len(out) < cap:
        d = get("/markets", f"series_ticker={st}&status=open&limit=100" + (f"&cursor={cur}" if cur else ""))
        ms = d.get("markets", [])
        out += ms
        cur = d.get("cursor") or ""
        if not cur or not ms:
            break
    return out[:cap]


def is_maker_free(m):
    ft = (m.get("fee_type") or "").lower()
    return "maker_fee" not in ft        # quadratic (soft default) = zero maker fee; exclude *_with_maker_fees


def accepts_market(m):
    """True iff an OPEN market m passes every entry filter for a new snapshot (the same
    deployable band the live bot quotes -- see LONGSHOT_RUNBOOK.md). Pulled out of the
    SNAPSHOT loop so it's independently testable (see --selftest / kalshi_longshot_paper_test.py)."""
    if m.get("mve_collection_ticker") or (m.get("market_type") and m.get("market_type") != "binary"):
        return False
    if not is_maker_free(m):
        return False
    yb = fnum(m.get("yes_bid_dollars")); ya = fnum(m.get("yes_ask_dollars"))
    if yb is None or ya is None or not (0 < yb < ya < 1):
        return False
    mid = (yb + ya) / 2
    if not (LONG_LO <= mid <= LONG_HI):
        return False
    if (ya - yb) > MAXSPREAD:
        return False
    if (fnum(m.get("volume_fp")) or 0) < MIN_VOL:
        return False
    lf = _life_frac(m)                  # OPT+EXEC: quote only the first half of life
    if lf is not None and lf > MAX_LIFE_FRAC:
        return False
    dtc = _days_to_close(m)             # RUNBOOK: forward-track the deployable band --
    if dtc is None or not (0 < dtc <= MAX_DAYS_TO_CLOSE):   # don't open far-dated positions
        return False
    return True


def classify_settlement(p, m, now, stale_days=STALE_PENDING_DAYS):
    """Decide the fate of one pending position p given its current market state m (the dict
    returned by GET /markets/{ticker}, or {} if the ticker 404'd/vanished).
    Returns ("settle", row) | ("pending", None) | ("expired", row)."""
    status = (m.get("status") or "").lower()
    result = (m.get("result") or "").lower()
    if status == "finalized" and result in ("yes", "no"):
        settle_yes = 1.0 if result == "yes" else 0.0
        pnl = p["entry_sell_yes"] - settle_yes          # short YES at entry; zero maker fee
        vol_after = (fnum(m.get("volume_fp")) or 0.0) - p.get("vol_at_entry", 0.0)
        return "settle", {
            "settle_ts": now.isoformat(timespec="seconds"), "snap_ts": p["ts"], "ticker": p["ticker"],
            "category": p["category"], "entry_sell_yes": round(p["entry_sell_yes"], 4),
            "result": result, "pnl_per_contract": round(pnl, 4),
            "vol_after_entry": round(vol_after, 1), "status": "settled",
        }
    age = (now - dt.datetime.fromisoformat(p["ts"])).days
    if age <= stale_days:
        return "pending", None
    return "expired", {
        "settle_ts": now.isoformat(timespec="seconds"), "snap_ts": p["ts"], "ticker": p["ticker"],
        "category": p["category"], "entry_sell_yes": round(p["entry_sell_yes"], 4),
        "result": result or "unresolved", "pnl_per_contract": "",
        "vol_after_entry": "", "status": "expired_unscored",
    }


def main():
    state_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(state_dir, exist_ok=True)
    pend_path = os.path.join(state_dir, "longshot_pending.json")
    settled_path = os.path.join(state_dir, "longshot_settled.csv")
    now = dt.datetime.now(dt.timezone.utc)
    nowiso = now.isoformat(timespec="seconds")

    pending = []
    if os.path.exists(pend_path):
        try:
            pending = json.load(open(pend_path))
        except Exception:
            pending = []

    # ---------- 1. SETTLE matured pendings ----------
    # Kalshi's ACTUAL per-market `status` field value for a resolved market is "finalized"
    # (confirmed against the live API 2026-07-12; "settled" is only a *query filter* value
    # accepted by GET /markets?status=settled, it never appears in a returned market object --
    # that mismatch was the root cause of zero settlements for 24 days straight: every pending
    # ticker gets fetched via GET /markets/{ticker}, whose `status` field is "closed" -> then
    # "finalized" once the settlement source posts, never literally "settled"). See also
    # weather_settle.py which already checks `status == "finalized"` for the same API.
    # still open / awaiting settlement source / vanished (404 -> m == {}) is kept unless it's
    # gone stale (>STALE_PENDING_DAYS since snapshot). Previously stale rows were silently
    # dropped with no record; now they get an explicit expired_unscored row so the CSV reflects
    # every pending position's fate (per LONGSHOT_RUNBOOK.md go-live gate, which reads
    # realized-edge stats off this file -- silent drops understated n).
    settled_rows, still_pending = [], []
    for p in pending:
        m = get(f"/markets/{p['ticker']}").get("market") or {}
        action, row = classify_settlement(p, m, now)
        if action == "pending":
            still_pending.append(p)
        else:
            settled_rows.append(row)

    # append settled rows (both real settlements and expired_unscored)
    file_exists = os.path.exists(settled_path)
    if settled_rows:
        fieldnames = ["settle_ts", "snap_ts", "ticker", "category", "entry_sell_yes",
                      "result", "pnl_per_contract", "vol_after_entry", "status"]
        with open(settled_path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                w.writeheader()
            for r in settled_rows:
                w.writerow(r)

    # ---------- 2. SNAPSHOT new open longshots ----------
    have = {p["ticker"] for p in still_pending}
    added = 0
    for cat in CATS:
        if added >= NEW_PER_RUN:
            break
        for st in series_for(cat):
            if added >= NEW_PER_RUN:
                break
            for m in open_markets(st):
                if added >= NEW_PER_RUN:
                    break
                tk = m.get("ticker")
                if not tk or tk in have:
                    continue
                if not accepts_market(m):
                    continue
                yb = fnum(m.get("yes_bid_dollars")); ya = fnum(m.get("yes_ask_dollars"))
                mid = (yb + ya) / 2
                still_pending.append({
                    "ts": nowiso, "ticker": tk, "series": st, "category": cat,
                    "yes_bid": round(yb, 4), "yes_ask": round(ya, 4), "mid": round(mid, 4),
                    "entry_sell_yes": round(ya, 4),     # maker: rest a YES offer AT the touch
                    "close_time": m.get("close_time"), "vol_at_entry": fnum(m.get("volume_fp")) or 0.0,
                    "title": (m.get("title") or "")[:80],
                })
                have.add(tk); added += 1

    json.dump(still_pending, open(pend_path, "w"), indent=0)

    # ---------- 3. report running aggregate ----------
    # (expired_unscored rows carry no pnl -- exclude from the realized-edge stats, but count
    #  them separately so a growing expired pile is visible rather than silently invisible)
    n = tot = wins = expired = 0
    if os.path.exists(settled_path):
        for r in csv.DictReader(open(settled_path)):
            if r.get("status") == "expired_unscored":
                expired += 1
                continue
            n += 1; tot += float(r["pnl_per_contract"]); wins += (r["result"] == "no")
    print(f"[{nowiso}] settled+{len(settled_rows)} (new) | snapshotted {added} new longshots | "
          f"pending now {len(still_pending)} | expired_unscored (lifetime) {expired}")
    if n:
        print(f"  CUMULATIVE paper harvest: n={n}  mean P&L={tot/n*100:+.2f}c/contract  "
              f"NO-win rate={wins/n:.3f}  total={tot*100:+.1f}c (per 1-contract clip)")
    else:
        print("  no settled paper positions yet (first runs only snapshot; edge accrues as they resolve)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        import kalshi_longshot_paper_test
        sys.exit(kalshi_longshot_paper_test.run())
    main()
