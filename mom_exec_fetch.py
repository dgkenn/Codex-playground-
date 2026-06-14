"""Fetch LIVE perp order-book depth + funding + OI for the locked top-15 USDT-perp
universe, to build a realistic execution-cost-vs-size model for cross-sectional momentum.

Primary venue: OKX public REST (no auth) -- books (400 levels), funding-rate-history,
open-interest, instrument ctVal. Backup venues: Kraken Futures, dYdX v4 (best-effort;
geo/availability may vary). Binance/Bybit are geo-blocked per task and not used.

Order-book size on OKX perps is in CONTRACTS; USD notional per level = price * size * ctVal.
We take several snapshots a few seconds apart and average the walked-book curve to reduce
single-snapshot noise (cloud bot = seconds latency, not HFT, so a snapshot ~ what we'd hit).

Outputs (NON-repo, /tmp/exec_data):
  book_depth.json   -- per-coin averaged walk-the-book cost curve (bps vs USD notional, each side)
  funding.json      -- per-coin recent funding (ann %), for holding-cost while in position
  meta.json         -- ctVal, mid, spread, top-of-book, snapshot count, timestamp
"""
import urllib.request, json, time, os
import numpy as np

OUT = "/tmp/exec_data"
os.makedirs(OUT, exist_ok=True)

# Locked universe: top-15 liquid OKX USDT perps (by recent 30d median quote volume in mom_data).
UNIVERSE = ["BTC","ETH","SOL","DOGE","XRP","NEAR","SUI","TON","BNB","ADA","FIL","BCH","LINK","XLM","LTC"]

# USD notional grid to walk the book to (per side, per single coin leg).
SIZE_GRID = [1e3,5e3,1e4,2.5e4,5e4,1e5,2.5e5,5e5,1e6,2.5e6,5e6,1e7]
N_SNAPSHOTS = 5
SNAP_GAP_S = 4.0


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def okx_instruments():
    d = _get("https://www.okx.com/api/v5/public/instruments?instType=SWAP")
    m = {}
    for it in d["data"]:
        if it["instId"].endswith("-USDT-SWAP"):
            m[it["instId"]] = float(it["ctVal"])
    return m


def okx_book(inst):
    d = _get(f"https://www.okx.com/api/v5/market/books?instId={inst}&sz=400")
    bk = d["data"][0]
    bids = [(float(p), float(s)) for p, s, *_ in bk["bids"]]
    asks = [(float(p), float(s)) for p, s, *_ in bk["asks"]]
    return bids, asks


def walk_book(levels, ctval, mid, side, usd_target):
    """Walk one side of the book to fill usd_target notional. Return slippage in bps
    vs mid (one-way). side='buy' walks asks (price up), 'sell' walks bids (price down)."""
    filled_usd = 0.0
    cost_usd = 0.0  # sum(price*qty_coin) actually paid
    coin_filled = 0.0
    for price, size_ct in levels:
        coin = size_ct * ctval
        lvl_usd = coin * price
        take_usd = min(lvl_usd, usd_target - filled_usd)
        if take_usd <= 0:
            break
        take_coin = take_usd / price
        cost_usd += take_coin * price
        coin_filled += take_coin
        filled_usd += take_usd
        if filled_usd >= usd_target * 0.999:
            break
    if coin_filled == 0:
        return None, 0.0
    vwap = cost_usd / coin_filled
    if side == "buy":
        slip = (vwap / mid - 1.0)
    else:
        slip = (mid / vwap - 1.0)
    fill_frac = filled_usd / usd_target
    return slip * 1e4, fill_frac  # bps, fraction of target filled


def main():
    ctvals = okx_instruments()
    depth = {}
    meta = {}
    for s in UNIVERSE:
        inst = f"{s}-USDT-SWAP"
        ctval = ctvals.get(inst)
        if ctval is None:
            print(f"SKIP {s}: no ctVal"); continue
        # accumulate slippage curves across snapshots
        buy_curves, sell_curves, fill_buy, fill_sell = [], [], [], []
        mids, spreads, top_usd = [], [], []
        for k in range(N_SNAPSHOTS):
            try:
                bids, asks = okx_book(inst)
            except Exception as e:
                print(f"  {s} snap {k} err {e}"); continue
            mid = (bids[0][0] + asks[0][0]) / 2.0
            spread_bps = (asks[0][0] - bids[0][0]) / mid * 1e4
            mids.append(mid); spreads.append(spread_bps)
            # depth available at top 1 level each side (USD)
            top_usd.append(min(bids[0][1], asks[0][1]) * ctval * mid)
            bc = [walk_book(asks, ctval, mid, "buy", u) for u in SIZE_GRID]
            sc = [walk_book(bids, ctval, mid, "sell", u) for u in SIZE_GRID]
            buy_curves.append([x[0] for x in bc]); fill_buy.append([x[1] for x in bc])
            sell_curves.append([x[0] for x in sc]); fill_sell.append([x[1] for x in sc])
            time.sleep(SNAP_GAP_S)
        if not mids:
            continue

        def avg_curve(curves):
            arr = np.array([[np.nan if v is None else v for v in c] for c in curves], float)
            return np.nanmean(arr, axis=0).tolist()

        depth[s] = {
            "size_grid_usd": SIZE_GRID,
            "buy_slip_bps": avg_curve(buy_curves),
            "sell_slip_bps": avg_curve(sell_curves),
            "fill_frac_buy": np.nanmean(np.array(fill_buy, float), axis=0).tolist(),
            "fill_frac_sell": np.nanmean(np.array(fill_sell, float), axis=0).tolist(),
        }
        meta[s] = {
            "ctVal": ctval, "mid": float(np.mean(mids)),
            "spread_bps": float(np.mean(spreads)),
            "top_level_usd": float(np.mean(top_usd)),
            "n_snap": len(mids),
        }
        rt2 = depth[s]["buy_slip_bps"][6]  # ~$250k one-way
        print(f"OK {s}: mid {meta[s]['mid']:.4f} spread {meta[s]['spread_bps']:.2f}bps "
              f"buy-slip@250k {rt2:.2f}bps fill {depth[s]['fill_frac_buy'][6]:.2f}")

    json.dump(depth, open(f"{OUT}/book_depth.json", "w"), indent=1)
    json.dump(meta, open(f"{OUT}/meta.json", "w"), indent=1)
    print(f"\nSaved book_depth.json, meta.json for {len(depth)} coins")

    # ---- Funding (recent ~3mo, all OKX serves) ----
    funding = {}
    for s in UNIVERSE:
        inst = f"{s}-USDT-SWAP"
        try:
            d = _get(f"https://www.okx.com/api/v5/public/funding-rate-history?instId={inst}&limit=100")
            rates = [float(r["fundingRate"]) for r in d.get("data", [])]
        except Exception as e:
            print(f"  funding {s} err {e}"); rates = []
        if rates:
            per8h = float(np.mean(rates))
            funding[s] = {"per8h": per8h, "ann_pct": per8h * 3 * 365 * 100, "n": len(rates)}
    json.dump(funding, open(f"{OUT}/funding.json", "w"), indent=1)
    print(f"Saved funding.json: {len(funding)} coins")
    print("Funding ann%:", {k: round(v["ann_pct"], 1) for k, v in funding.items()})


if __name__ == "__main__":
    main()
