"""pmkt_5m_collect.py -- FORWARD trade+wallet collector for Polymarket BTC 5-min up/down markets.

WHY THIS EXISTS (read POLYMARKET_CLASSIFY.md): Polymarket exposes per-trade wallet identity, but it
serves NO bulk resolved history for short-tenor crypto markets -- the data-api/trades feed is only a
~30-min rolling window and resolved 5m/15m windows drop out of the Gamma index within ~10 min of close.
So the one-off "informed-wallet signature" study (operator choice B) cannot be a retrospective; it needs
a short FORWARD capture. This collector polls the trades feed, dedupes by transactionHash, keeps the
btc-updown-5m trades (wallet, size, price, side, outcome side, window), and records each window's
RESOLUTION (winner from outcomePrices) shortly after it closes -- while it is still indexed. ~3h of this
yields ~36 windows x hundreds of trades = enough wallets to score directional accuracy and compare the
informed subset's behavioral fingerprint to our Kalshi toxic-flow detectors (pmkt_signature_study.py).

Read-only, public, no auth, no money. Does NOT touch the live Kalshi bot or its collectors.

    python pmkt_5m_collect.py [duration_s] [out_dir]
"""
from __future__ import annotations
import gzip, json, os, sys, time
from datetime import datetime, timezone
import requests

DATA_API = "https://data-api.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com"
PREFIX = "btc-updown-5m"
POLL = 4.0                      # feed poll cadence (s); feed holds ~30 min so this never misses
RESOLVE_LAG = 90               # s after a window's end before we read its resolution


def _slug_end(slug: str) -> int:
    try:
        return int(slug.rsplit("-", 1)[-1]) + 300   # window start + 300s
    except Exception:
        return 0


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3 * 3600
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    os.makedirs(out_dir, exist_ok=True)
    trades_fp = os.path.join(out_dir, "pmkt_5m_trades.jsonl.gz")
    res_fp = os.path.join(out_dir, "pmkt_5m_resolution.jsonl")
    tfh = gzip.open(trades_fp, "at")

    seen_tx: set[str] = set()
    windows: dict[str, dict] = {}      # conditionId -> {slug, end, resolved}
    resolved: set[str] = set()
    if os.path.exists(res_fp):
        for ln in open(res_fp):
            try:
                resolved.add(json.loads(ln)["conditionId"])
            except Exception:
                pass

    end_at = time.time() + dur
    n_tr = 0
    print(f"pmkt_5m_collect: {dur}s -> {trades_fp} (+ {res_fp})", flush=True)
    while time.time() < end_at:
        t0 = time.time()
        # 1) pull rolling feed (paginate a little to not miss bursts)
        for off in (0, 500, 1000):
            try:
                batch = requests.get(f"{DATA_API}/trades",
                                     params={"limit": 500, "offset": off}, timeout=10).json()
            except Exception:
                break
            if not batch:
                break
            hit = False
            for tr in batch:
                if not tr.get("slug", "").startswith(PREFIX):
                    continue
                hit = True
                tx = tr.get("transactionHash", "") + str(tr.get("asset", "")) + str(tr.get("timestamp"))
                if tx in seen_tx:
                    continue
                seen_tx.add(tx)
                cid = tr["conditionId"]
                windows.setdefault(cid, {"slug": tr["slug"], "end": _slug_end(tr["slug"])})
                tfh.write(json.dumps({
                    "ts": tr.get("timestamp"), "cid": cid, "slug": tr["slug"],
                    "wallet": tr.get("proxyWallet"), "side": tr.get("side"),
                    "size": tr.get("size"), "price": tr.get("price"),
                    "outcome": tr.get("outcome"), "oidx": tr.get("outcomeIndex"),
                }) + "\n")
                n_tr += 1
            if not hit and off > 0:
                break
        tfh.flush()
        # 2) resolve windows whose end passed > RESOLVE_LAG ago and not yet resolved
        now = time.time()
        for cid, w in list(windows.items()):
            if cid in resolved or w["end"] == 0 or now < w["end"] + RESOLVE_LAG:
                continue
            try:
                r = requests.get(f"{GAMMA}/markets", params={"condition_ids": cid}, timeout=8).json()
            except Exception:
                continue
            if not r:                      # dropped from index before we caught it
                resolved.add(cid)
                continue
            m = r[0]
            op = m.get("outcomePrices")
            op = json.loads(op) if isinstance(op, str) else op
            if not op:
                continue
            try:
                prices = [float(x) for x in op]
            except Exception:
                continue
            if max(prices) < 0.9:          # not settled yet, check again next loop
                continue
            winner = int(prices.index(max(prices)))
            with open(res_fp, "a") as rf:
                rf.write(json.dumps({"conditionId": cid, "slug": w["slug"],
                                     "winner_idx": winner, "outcomePrices": prices,
                                     "captured": round(now, 1)}) + "\n")
            resolved.add(cid)
            print(f"{datetime.now(timezone.utc):%H:%M}Z resolved {w['slug'][-15:]} winner_idx={winner}", flush=True)
        if int(now) % 300 < POLL:
            print(f"{datetime.now(timezone.utc):%H:%M}Z trades={n_tr} windows={len(windows)} resolved={len(resolved)}", flush=True)
        time.sleep(max(0.0, POLL - (time.time() - t0)))
    tfh.close()
    print(f"done: {n_tr} trades, {len(windows)} windows, {len(resolved)} resolved", flush=True)


if __name__ == "__main__":
    main()
