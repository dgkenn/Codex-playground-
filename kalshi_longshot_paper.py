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


def _life_frac(m):
    try:
        o = dt.datetime.fromisoformat((m.get("open_time") or "").replace("Z", "+00:00"))
        c = dt.datetime.fromisoformat((m.get("close_time") or "").replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        span = (c - o).total_seconds()
        return (now - o).total_seconds() / span if span > 0 else None
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
    settled_rows, still_pending = [], []
    for p in pending:
        m = get(f"/markets/{p['ticker']}").get("market") or {}
        status = (m.get("status") or "").lower()
        result = (m.get("result") or "").lower()
        if status == "settled" and result in ("yes", "no"):
            settle_yes = 1.0 if result == "yes" else 0.0
            pnl = p["entry_sell_yes"] - settle_yes          # short YES at entry; zero maker fee
            vol_after = (fnum(m.get("volume_fp")) or 0.0) - p.get("vol_at_entry", 0.0)
            settled_rows.append({
                "settle_ts": nowiso, "snap_ts": p["ts"], "ticker": p["ticker"],
                "category": p["category"], "entry_sell_yes": round(p["entry_sell_yes"], 4),
                "result": result, "pnl_per_contract": round(pnl, 4),
                "vol_after_entry": round(vol_after, 1),
            })
        elif status in ("", "active", "open", "initialized") or result not in ("yes", "no"):
            # still open (or unresolved) -- keep, unless it's gone stale (>45d past snapshot)
            age = (now - dt.datetime.fromisoformat(p["ts"])).days
            if age <= 45:
                still_pending.append(p)
        # markets that 404 / vanish are dropped

    # append settled rows
    new_settle = bool(settled_rows)
    file_exists = os.path.exists(settled_path)
    if settled_rows:
        with open(settled_path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(settled_rows[0].keys()))
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
                if m.get("mve_collection_ticker") or (m.get("market_type") and m.get("market_type") != "binary"):
                    continue
                if not is_maker_free(m):
                    continue
                yb = fnum(m.get("yes_bid_dollars")); ya = fnum(m.get("yes_ask_dollars"))
                if yb is None or ya is None or not (0 < yb < ya < 1):
                    continue
                mid = (yb + ya) / 2
                if not (LONG_LO <= mid <= LONG_HI):
                    continue
                if (ya - yb) > MAXSPREAD:
                    continue
                if (fnum(m.get("volume_fp")) or 0) < MIN_VOL:
                    continue
                lf = _life_frac(m)                  # OPT+EXEC: quote only the first half of life
                if lf is not None and lf > MAX_LIFE_FRAC:
                    continue
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
    n = tot = wins = 0
    if os.path.exists(settled_path):
        for r in csv.DictReader(open(settled_path)):
            n += 1; tot += float(r["pnl_per_contract"]); wins += (r["result"] == "no")
    print(f"[{nowiso}] settled+{len(settled_rows)} (new) | snapshotted {added} new longshots | "
          f"pending now {len(still_pending)}")
    if n:
        print(f"  CUMULATIVE paper harvest: n={n}  mean P&L={tot/n*100:+.2f}c/contract  "
              f"NO-win rate={wins/n:.3f}  total={tot*100:+.1f}c (per 1-contract clip)")
    else:
        print("  no settled paper positions yet (first runs only snapshot; edge accrues as they resolve)")


if __name__ == "__main__":
    main()
