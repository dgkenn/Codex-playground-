#!/usr/bin/env python3
"""kalshi_wing_maker.py -- the MAKER economics of the wing-overpricing edge (node MULTISTRIKE-WING-VRP).

The wing overpricing is real (kalshi_wing_vrp.py). The TAKER version dies to the spread (you'd sell at the
low bid). But a MAKER selling a wing does NOT pay the spread -- it fills at the price the BUYER pays when they
lift a resting YES offer. So the honest maker-sell economics is, over every WING taker-BUY trade actually
printed: PnL = (price_the_buyer_paid) - result - fee. That price IS the ask a resting maker would have been
lifted at (conservative: assumes the maker is at front-of-queue at exactly the transacted price -- no better).
Adverse selection is fully captured: if buyers are informed, `result` is 1 more often on the trades they buy,
which lowers the mean. Day-clustered by close date, OOS train/test. Fee = ceil(0.07 p(1-p)) to the cent, min 1c.

This makes the maker question BACKTESTABLE from historical trades (no forward wait). PROPOSE-ONLY.
"""
import urllib.request, json, math, time, sys
from collections import defaultdict
import statistics as st

B = "https://api.elections.kalshi.com/trade-api/v2"
WING = float(sys.argv[1]) if len(sys.argv) > 1 else 0.15   # yes-price <= WING = wing
MAXEVENTS = int(sys.argv[2]) if len(sys.argv) > 2 else 400
FEE = lambda p: max(0.01, math.ceil(0.07 * p * (1 - p) * 100) / 100)


def get(url, tries=4):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read())
        except Exception:
            time.sleep(1 + i)
    return {}


def paged(path, key, cap=100000):
    out, cur = [], None
    while len(out) < cap:
        u = path + (f"&cursor={cur}" if cur else "")
        d = get(u)
        rows = d.get(key, [])
        out += rows
        cur = d.get("cursor")
        if not cur or not rows:
            break
    return out


def main():
    evs = paged(f"{B}/events?series_ticker=KXBTCD&status=settled&limit=200", "events", MAXEVENTS)
    print(f"settled events: {len(evs)} (using up to {MAXEVENTS})", flush=True)
    # per (asset,day) -> list of maker-sell PnLs
    day_sell = defaultdict(list)
    day_gross = defaultdict(list)
    nwin_trades = 0
    ev_used = 0
    for ei, ev in enumerate(evs[:MAXEVENTS]):
        et = ev.get("event_ticker")
        mkts = get(f"{B}/markets?event_ticker={et}&limit=400").get("markets", [])
        if not mkts:
            continue
        # close date for clustering
        ct = (mkts[0].get("close_time") or "")[:10]
        for m in mkts:
            res = m.get("result")
            if res not in ("yes", "no"):
                continue
            try:
                if float(m.get("volume_fp", 0) or 0) <= 0:   # untraded -> no wing buys, skip the API call
                    continue
            except (TypeError, ValueError):
                continue
            tkr = m.get("ticker")
            ot, cl = m.get("open_time"), m.get("close_time")
            outcome = 1 if res == "yes" else 0
            trades = paged(f"{B}/markets/trades?ticker={tkr}&limit=1000", "trades", 4000)
            if not trades:
                continue
            # uncertain window: [open, open+0.8*(close-open)] via created_time ordering; use first 80% of trades by time
            trades = [t for t in trades if t.get("created_time")]
            trades.sort(key=lambda t: t["created_time"])
            if len(trades) < 2:
                continue
            cut = trades[int(0.8 * len(trades))]["created_time"]  # exclude last 20% (convergence)
            for t in trades:
                if t["created_time"] >= cut:
                    break
                if t.get("taker_side") != "yes":       # only BUYERS lifting a YES offer -> maker SELLS
                    continue
                yp = t.get("yes_price_dollars")
                try:
                    p = float(yp)
                except (TypeError, ValueError):
                    continue
                if not (0 < p <= WING):                # WING only
                    continue
                cnt = float(t.get("count_fp", 1) or 1)
                pnl = (p - outcome) - FEE(p)            # maker sells YES at p, pays fee, owes outcome
                day_sell[ct].append((pnl, cnt))
                day_gross[ct].append((p - outcome, cnt))
                nwin_trades += 1
        ev_used += 1
        if ev_used % 40 == 0:
            print(f"  {ev_used} events, {nwin_trades} wing-buy trades so far", flush=True)
    # day-clustered stats (count-weighted per-day mean)
    def daymean(dd):
        return {d: sum(p * c for p, c in v) / sum(c for p, c in v) for d, v in dd.items() if v}
    ds = daymean(day_sell)
    dg = daymean(day_gross)
    days = sorted(ds)
    ntr = int(0.7 * len(days))
    tr, te = set(days[:ntr]), set(days[ntr:])

    def dct(dm, subset):
        xs = [dm[d] for d in dm if d in subset]
        if len(xs) < 2:
            return float("nan"), len(xs), float("nan")
        sd = st.stdev(xs)
        t = st.mean(xs) / (sd / math.sqrt(len(xs))) if sd > 0 else float("nan")
        return t, len(xs), st.mean(xs)

    print(f"\nWING<= {WING}  maker-SELL over {nwin_trades} taker-buy wing trades, {len(days)} dates "
          f"({days[0]}..{days[-1]}), train={len(tr)} test={len(te)}")
    for lbl, dm in (("GROSS (no fee)", dg), ("NET fee", ds)):
        tt, nt, mt = dct(dm, tr)
        te_t, ne, me = dct(dm, te)
        allt, na, ma = dct(dm, set(days))
        print(f"  {lbl:14s}: TRAIN mean={mt:+.4f} t={tt:+.2f} (n={nt}) | "
              f"TEST mean={me:+.4f} t={te_t:+.2f} (n={ne}) | ALL mean={ma:+.4f} t={allt:+.2f}")


if __name__ == "__main__":
    main()
