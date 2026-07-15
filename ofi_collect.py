#!/usr/bin/env python3
"""ofi_collect.py -- EXOGENOUS order-flow collector (node EXO-OFI, 2026-07-15).

WHY: the operator chose "exogenous signal -> Kalshi 15m binaries" as the next research domain.
The gha-data tick archive already carries sampled `spot` and `micro`, and the backtest showed that
observable SPOT MOMENTUM is already priced by the Kalshi book (node EXO-MOM: tradeable overlay
negative in-sample). The one exogenous signal the archive does NOT contain -- and therefore the
only genuinely-untested part of this hypothesis -- is TRUE SIGNED ORDER FLOW and BOOK IMBALANCE
from a major spot venue (CVD/OFI, depth imbalance, aggressor ratio, trade intensity). Microstructure
theory says signed flow can lead price at a seconds-to-minutes horizon; if that lead survives into
the 15m binary's terminal settlement it would be a directional taker signal the Kalshi book misses.
This can ONLY be forward-tested (no historical signed-flow archive exists), so this collector starts
the forward clock. The hypothesis is PRE-REGISTERED in OFI_FORWARD.md before any data exists.

WHAT: polls Coinbase Exchange public REST (no auth) for BTC-USD / ETH-USD / SOL-USD, and every
~POLL_SEC seconds writes one snapshot row per asset with signed-flow + book-imbalance features
computed since the previous poll. Output mirrors the tick archive's shape so it can be JOINED to
each Kalshi 15m window (by wall-clock timestamp) and to the window outcome (from settle_recorder).

Row schema (gzipped JSONL, one object per asset per poll):
  ts        : unix seconds (float) of this snapshot
  asset     : btc/eth/sol
  mid       : (best_bid+best_ask)/2  from the L2 book
  spread    : best_ask - best_bid
  buy_vol   : base-asset volume of BUY-aggressor trades since last poll
  sell_vol  : base-asset volume of SELL-aggressor trades since last poll
  ntrades   : trade count since last poll
  ofi       : buy_vol - sell_vol  (signed order-flow imbalance over the interval)
  cvd       : running cumulative (buy_vol - sell_vol) within this collector run
  book_imb  : (bid_depth10 - ask_depth10)/(bid_depth10 + ask_depth10), top-10 levels
  last_price: last trade price seen

READ-ONLY (public REST, no keys, no orders). PROPOSE-ONLY: this only COLLECTS. No live trading
decision is made here or on this data without the operator's explicit word and a passed forward gate.
Self-chaining + graceful SIGTERM drain mirror collect.yml so the forward series has no gaps.
"""
import json, gzip, os, sys, time, signal, urllib.request, urllib.error
from datetime import datetime, timezone

ASSETS = {"btc": "BTC-USD", "eth": "ETH-USD", "sol": "SOL-USD"}
POLL_SEC = float(os.environ.get("OFI_POLL_SEC", "2.0"))
RUN_SEC = float(os.environ.get("OFI_RUN_SEC", "1080"))     # ~18 min, > one 15m window; self-chain continues
OUT_DIR = os.environ.get("OFI_OUT_DIR", "gha_data")
BOOK_LEVELS = 10
_STOP = {"v": False}


def _sig(*_):
    _STOP["v"] = True


signal.signal(signal.SIGTERM, _sig)
signal.signal(signal.SIGINT, _sig)


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ofi-collect"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def poll_trades(product, after_id):
    """Return (rows_newer_than_after_id, newest_id). Coinbase returns newest-first."""
    try:
        d = _get(f"https://api.exchange.coinbase.com/products/{product}/trades?limit=100")
    except Exception:
        return [], after_id
    rows, newest = [], after_id
    for tr in d:
        tid = tr.get("trade_id")
        if tid is None:
            continue
        if newest is None or tid > newest:
            newest = tid
        if after_id is not None and tid <= after_id:
            continue
        rows.append(tr)
    return rows, newest


def poll_book(product):
    """Return (mid, spread, book_imbalance, last_price_none). Level-2, top BOOK_LEVELS."""
    try:
        d = _get(f"https://api.exchange.coinbase.com/products/{product}/book?level=2")
    except Exception:
        return None
    bids, asks = d.get("bids", []), d.get("asks", [])
    if not bids or not asks:
        return None
    bb, ba = float(bids[0][0]), float(asks[0][0])
    bd = sum(float(b[1]) for b in bids[:BOOK_LEVELS])
    ad = sum(float(a[1]) for a in asks[:BOOK_LEVELS])
    imb = (bd - ad) / (bd + ad) if (bd + ad) > 0 else 0.0
    return (bb + ba) / 2.0, ba - bb, imb


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    run_id = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
    last_id = {a: None for a in ASSETS}
    cvd = {a: 0.0 for a in ASSETS}
    writers = {}

    def writer_for(asset, day):
        key = (asset, day)
        if key not in writers:
            d = os.path.join(OUT_DIR, day)
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, f"ofi_coinbase_{asset}_r{run_id}.jsonl.gz")
            writers[key] = gzip.open(path, "at")
        return writers[key]

    # prime trade ids so the first interval's OFI isn't a huge backlog
    for a, prod in ASSETS.items():
        _, last_id[a] = poll_trades(prod, None)

    t_end = time.time() + RUN_SEC
    npolls = 0
    while time.time() < t_end and not _STOP["v"]:
        cycle_start = time.time()
        for a, prod in ASSETS.items():
            trades, newest = poll_trades(prod, last_id[a])
            last_id[a] = newest
            buy_vol = sell_vol = 0.0
            last_price = None
            for tr in trades:
                sz = float(tr.get("size", 0) or 0)
                # Coinbase 'side' = the MAKER side; taker aggressor is the opposite.
                # side=='buy' => resting bid was hit => SELL-aggressor; side=='sell' => BUY-aggressor.
                if tr.get("side") == "sell":
                    buy_vol += sz
                elif tr.get("side") == "buy":
                    sell_vol += sz
                last_price = float(tr.get("price")) if tr.get("price") else last_price
            ofi = buy_vol - sell_vol
            cvd[a] += ofi
            bk = poll_book(prod)
            if bk is None:
                continue
            mid, spread, imb = bk
            now = time.time()
            row = dict(ts=round(now, 3), asset=a, mid=mid, spread=spread,
                       buy_vol=round(buy_vol, 6), sell_vol=round(sell_vol, 6),
                       ntrades=len(trades), ofi=round(ofi, 6), cvd=round(cvd[a], 6),
                       book_imb=round(imb, 5), last_price=last_price)
            day = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d")
            w = writer_for(a, day)
            w.write(json.dumps(row) + "\n")
        npolls += 1
        # pace to POLL_SEC
        slp = POLL_SEC - (time.time() - cycle_start)
        while slp > 0 and not _STOP["v"]:
            step = min(0.25, slp)
            time.sleep(step)
            slp -= step
    for w in writers.values():
        try:
            w.close()
        except Exception:
            pass
    print(f"ofi_collect: {npolls} polls, {len(writers)} files, stop={_STOP['v']}", file=sys.stderr)


if __name__ == "__main__":
    main()
