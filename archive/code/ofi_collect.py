#!/usr/bin/env python3
"""ofi_collect.py -- WIDENED exogenous order-flow collector (node EXO-OFI / EXO-OFI-WIDE, 2026-07-15).

WHY: operator chose to widen the live EXO-OFI forward experiment to test the RICHEST version of the
order-flow hypothesis (still pre-registered, still forward-gated). The archive has sampled
spot+microprice (already priced -> EXO-MOM/EXO-XASSET); the untested exogenous signals are TRUE
signed order flow and leverage-stress microstructure, captured here across MULTIPLE venues:
  - MULTI-VENUE SIGNED FLOW: Coinbase + crypto.com + Kraken spot (informed flow often hits one venue
    first -> cross-venue OFI divergence is itself a signal).
  - LEVERAGE STRESS / LIQUIDATION-CASCADE PROXY: crypto.com BTCUSD-PERP mark + OPEN INTEREST, and
    perp-vs-spot basis. A liquidation cascade shows as a one-sided flow burst + spread widening +
    rapid OI drop / basis spike (no direct liquidation feed is reachable stdlib/no-auth; this is the
    standard proxy). Kalshi perp funding is structurally 0 (PERP-ALLASSETS), so OI/basis carry the
    leverage signal, not funding.

Aggressor-sign conventions (handled per venue):
  - Coinbase /trades `side` = MAKER side -> taker is the opposite (side 'sell' => BUY-aggressor).
  - crypto.com get-trades `s` = TAKER side -> 's'=='buy' => BUY-aggressor.
  - Kraken Trades side (idx 3) 'b'/'s' = aggressor -> 'b' => BUY-aggressor.

Row schema (gzipped JSONL, one object per asset per poll):
  ts, asset,
  cb_mid, cb_spread, cb_book_imb, cb_ofi,       # Coinbase (PRIMARY gate uses cb_ofi)
  cdc_mid, cdc_ofi,                             # crypto.com spot
  kr_mid, kr_ofi,                               # Kraken spot
  multi_ofi,                                     # cb_ofi+cdc_ofi+kr_ofi (venues present)
  perp_mark, perp_oi, perp_basis                 # crypto.com perp mark, open interest, mark-cb_mid

READ-ONLY public REST, no auth, no orders. PROPOSE-ONLY. Self-chaining + SIGTERM drain mirror
collect.yml so the forward series has no gaps. Every venue poll is independently try/except-guarded
so one venue outage never drops the row (the primary cb_ofi is preserved whenever Coinbase is up).
"""
import json, gzip, os, sys, time, signal, urllib.request
from datetime import datetime, timezone

CB = {"btc": "BTC-USD", "eth": "ETH-USD", "sol": "SOL-USD"}
CDC = {"btc": "BTC_USD", "eth": "ETH_USD", "sol": "SOL_USD"}
KR = {"btc": "XBTUSD", "eth": "ETHUSD", "sol": "SOLUSD"}
PERP = {"btc": "BTCUSD-PERP", "eth": "ETHUSD-PERP", "sol": "SOLUSD-PERP"}
POLL_SEC = float(os.environ.get("OFI_POLL_SEC", "3.0"))
RUN_SEC = float(os.environ.get("OFI_RUN_SEC", "1080"))
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


def cb_trades(product, after_id):
    """Coinbase: (buy_vol, sell_vol, newest_id). side=maker -> taker is opposite."""
    try:
        d = _get(f"https://api.exchange.coinbase.com/products/{product}/trades?limit=100")
    except Exception:
        return 0.0, 0.0, after_id
    buy = sell = 0.0
    newest = after_id
    for tr in d:
        tid = tr.get("trade_id")
        if tid is None:
            continue
        if newest is None or tid > newest:
            newest = tid
        if after_id is not None and tid <= after_id:
            continue
        sz = float(tr.get("size", 0) or 0)
        if tr.get("side") == "sell":       # maker sold -> taker bought
            buy += sz
        elif tr.get("side") == "buy":
            sell += sz
    return buy, sell, newest


def cb_book(product):
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


def cdc_trades(inst, seen_ts):
    """crypto.com: (buy_vol, sell_vol, mid_est, newest_ts). s=taker side."""
    try:
        d = _get(f"https://api.crypto.com/exchange/v1/public/get-trades?instrument_name={inst}")
        rows = d.get("result", {}).get("data", [])
    except Exception:
        return 0.0, 0.0, None, seen_ts
    buy = sell = 0.0
    newest = seen_ts
    last_p = None
    for tr in rows:
        ts = int(tr.get("t", 0))
        if newest is None or ts > newest:
            newest = ts
        if seen_ts is not None and ts <= seen_ts:
            continue
        q = float(tr.get("q", 0) or 0)
        if tr.get("s") == "buy":
            buy += q
        elif tr.get("s") == "sell":
            sell += q
        last_p = float(tr.get("p")) if tr.get("p") else last_p
    return buy, sell, last_p, newest


def kr_trades(pair, since):
    """Kraken: (buy_vol, sell_vol, last_price, newest_since). side idx3 'b'/'s' = aggressor."""
    try:
        url = f"https://api.kraken.com/0/public/Trades?pair={pair}&count=100"
        d = _get(url)
        res = d.get("result", {})
        key = [k for k in res if k != "last"]
        rows = res[key[0]] if key else []
    except Exception:
        return 0.0, 0.0, None, since
    buy = sell = 0.0
    last_p = None
    newest = since
    for tr in rows:
        # [price, volume, time, side, ordertype, misc, id]
        t = float(tr[2])
        if newest is None or t > newest:
            newest = t
        if since is not None and t <= since:
            continue
        vol = float(tr[1])
        if tr[3] == "b":
            buy += vol
        elif tr[3] == "s":
            sell += vol
        last_p = float(tr[0])
    return buy, sell, last_p, newest


def cdc_perp(inst):
    """crypto.com perp: (mark, open_interest). a=last/mark, oi=open interest."""
    try:
        d = _get(f"https://api.crypto.com/exchange/v1/public/get-tickers?instrument_name={inst}")
        r = d.get("result", {}).get("data", [])
        if not r:
            return None
        t = r[0]
        mark = float(t.get("a")) if t.get("a") else None
        oi = float(t.get("oi")) if t.get("oi") else None
        return mark, oi
    except Exception:
        return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    run_id = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
    cb_id = {a: None for a in CB}
    cdc_ts = {a: None for a in CDC}
    kr_since = {a: None for a in KR}
    writers = {}

    def writer_for(asset, day):
        key = (asset, day)
        if key not in writers:
            d = os.path.join(OUT_DIR, day)
            os.makedirs(d, exist_ok=True)
            writers[key] = gzip.open(os.path.join(d, f"ofi_coinbase_{asset}_r{run_id}.jsonl.gz"), "at")
        return writers[key]

    # prime trade cursors so the first interval isn't a backlog
    for a in CB:
        _, _, cb_id[a] = cb_trades(CB[a], None)
        _, _, _, cdc_ts[a] = cdc_trades(CDC[a], None)
        _, _, _, kr_since[a] = kr_trades(KR[a], None)

    t_end = time.time() + RUN_SEC
    npolls = 0
    while time.time() < t_end and not _STOP["v"]:
        cyc = time.time()
        for a in CB:
            row = {"asset": a}
            # Coinbase (primary)
            b, s, cb_id[a] = cb_trades(CB[a], cb_id[a])
            cb_ofi = b - s
            bk = cb_book(CB[a])
            cb_mid = None
            if bk:
                cb_mid, cb_spread, cb_imb = bk
                row.update(cb_mid=cb_mid, cb_spread=round(cb_spread, 4),
                           cb_book_imb=round(cb_imb, 5))
            row["cb_ofi"] = round(cb_ofi, 6)
            # crypto.com spot
            cb2, cs2, cdc_mid, cdc_ts[a] = cdc_trades(CDC[a], cdc_ts[a])
            cdc_ofi = cb2 - cs2
            row.update(cdc_mid=cdc_mid, cdc_ofi=round(cdc_ofi, 6))
            # Kraken spot
            kb, ks, kr_mid, kr_since[a] = kr_trades(KR[a], kr_since[a])
            kr_ofi = kb - ks
            row.update(kr_mid=kr_mid, kr_ofi=round(kr_ofi, 6))
            # multi-venue OFI (venues that reported)
            row["multi_ofi"] = round(cb_ofi + cdc_ofi + kr_ofi, 6)
            # perp leverage stress
            pp = cdc_perp(PERP[a])
            if pp:
                mark, oi = pp
                row.update(perp_mark=mark, perp_oi=oi,
                           perp_basis=(round(mark - cb_mid, 3) if (mark and cb_mid) else None))
            now = time.time()
            row["ts"] = round(now, 3)
            day = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d")
            writer_for(a, day).write(json.dumps(row) + "\n")
        npolls += 1
        slp = POLL_SEC - (time.time() - cyc)
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
