"""kalshi_perp_collect.py -- READ-ONLY discovery-driven collector for Kalshi CRYPTO PERPETUALS.

WHY: we run/validate FAVLONG on Kalshi's 15-min binaries and want a return driver that's ORTHOGONAL
to it -- perp carry/basis. We currently collect ONLY the 15m binaries (ticks_kalshi_{btc,eth,sol,
xrp}15m via kalshi_collect.py); NO perp data exists yet. Step 1 (this file) is a collector that just
starts ACCRUING perp data so we can collect-then-forward-validate the three paper edges designed in
perp_strategy_design.md. No orders. No live-config edits. Market data only.

WHAT KALSHI'S PERP PRODUCT ACTUALLY IS (confirmed live in PERP_HEDGE.md, this repo):
  * Perps live on a DIFFERENT host from the binaries: https://external-api.kalshi.com/trade-api/v2
    (demo: external-api.demo.kalshi.co). The public elections host (api.elections.kalshi.com) that
    serves the 15m binaries does NOT list perps.
  * Surface (all read-only here): /margin/markets, /margin/markets/{ticker}/orderbook,
    /margin/funding_rates/estimate, /margin/funding_history. (Order/position/balance endpoints exist
    too -- we NEVER touch them.)
  * BTCPERP: cash-settled USD, never expires, tracks CF Benchmarks BRTI (updates ~1Hz), 8-hour
    funding, contract_size 0.01 BTC (~$1k notional), 0% fees currently. bid/ask/leverage_estimate/
    liquidation-price fields observed live. ETH/SOL/XRP perps may or may not exist yet -> we do NOT
    hardcode a product list, we DISCOVER.
  * Auth: SAME RSA-PSS SHA-256 signing as the binary bot (kalshi_trader.py). Reading /margin/markets
    returned 200 with our existing key EVEN THOUGH the account's margin trading is not enabled --
    i.e. read-only market data works with just an authenticated key. If no key is present the
    collector writes a note file and exits 0 (a keyless CI run must never crash the workflow).

DISCOVERY-DRIVEN + SELF-DESCRIBING (we do NOT assume the exact product/schema):
  * List /margin/markets (authed). Log EVERY candidate ticker/series seen. Filter for crypto perps
    by ticker/type pattern (PERP / PERPETUAL / continuous, and an asset substring BTC|ETH|SOL|XRP).
  * FALLBACK: also scan the public elections /series + /markets for any perpetual-looking ticker,
    in case the product ever surfaces there too. Everything found is logged.
  * Dump the FULL raw market object once per discovered market into registry_kalshi_perp_<tag>.json
    (plus the funding-endpoint raw responses) so the FIRST CI run teaches us the real schema.
  * Per poll we extract a curated core (bid/ask/mid/last/volume/open_interest) AND, because we don't
    know the exact funding/mark/index/settlement field names, we ALSO sweep every key whose name
    contains fund|mark|index|settle|liquid|notional|leverage and carry it through verbatim. So we
    capture funding/mark/index no matter what Kalshi calls them.

OUTPUT (mirrors the other collectors; the workflow date-partitions gha_data/. into gha_data/<day>/
at commit time, giving the final gha_data/<YYYY-MM-DD>/ticks_kalshi_perp_<asset>_<tag>.jsonl.gz):
  ticks_kalshi_perp_<asset>_<tag>.jsonl.gz     ~POLL_S perp top-of-book + funding/mark/index/OI
  ticks_kalshi_perp_binmid_<asset>_<tag>.jsonl.gz  SAME-CLOCK 15m-binary mid (public, no auth) so
                                                the perp<->binary basis is computable on one clock
  registry_kalshi_perp_<tag>.json              full raw schema of every discovered perp + funding
  NOTE_kalshi_perp_<tag>.json                  written iff nothing discovered / no key (exit 0)

    python kalshi_perp_collect.py [duration_s] [out_dir] [tag]     # default 3600 gha_data perp<ts>

Auth env (same as kalshi_trader.py / live.yml): KALSHI_API_KEY_ID + KALSHI_PRIVATE_KEY_PATH (a PEM
file; live.yml writes the KALSHI_PRIVATE_KEY secret to a 0600 temp file and exports the path).
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

import requests

# Perps are on external-api, NOT the public elections host that serves the 15m binaries.
PERP_BASE = "https://external-api.kalshi.com/trade-api/v2"
PERP_PATH_PREFIX = "/trade-api/v2"          # what _sign signs (host-relative, no query string)
PUBLIC_BASE = "https://api.elections.kalshi.com/trade-api/v2"   # binaries + discovery fallback

BIN_ASSETS = ("btc", "eth", "sol", "xrp")   # 15m-binary series for the aligned co-collection
POLL_S = 2.5                                 # perp funding/marks move slowly; book faster; be gentle
FUND_POLL_S = 30.0                           # funding rate barely moves (8h funding) -> sample ~30s

# key-name substrings we carry through verbatim so we don't miss the funding/mark/index/settlement
# fields whatever Kalshi actually names them (schema is unknown until the first live run).
EXTRA_KEY_HINTS = ("fund", "mark", "index", "settle", "liquid", "notional", "leverage",
                   "brti", "contract_size", "expected", "expiration")

STOP = [False]     # set by SIGTERM -> graceful drain + exit
_HB = [0.0]        # heartbeat throttle


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def f(x):
    """Robust float: Kalshi returns some numerics as strings / "_fp" strings (e.g. "165897.35")."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Auth -- RSA-PSS SHA-256, copied VERBATIM from kalshi_trader.py so this collector stays standalone
# and import-light (like kalshi_ladder_collect.py). If the key is absent we run keyless (perp reads
# will fail -> handled by the "nothing discovered" note path).
# ---------------------------------------------------------------------------

def _load_private_key():
    path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not path:
        return None
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        with open(path, "rb") as fh:
            return load_pem_private_key(fh.read(), password=None)
    except Exception as e:
        print(f"[auth] failed to load private key from {path}: {e}", flush=True)
        return None


def _sign(private_key, method, path):
    """Kalshi RSA-PSS headers: base64(RSA-PSS(SHA256, salt=digest_len) of ts_ms+METHOD+path).
    path = /trade-api/v2/... WITHOUT query string. Returns {} if no key (unauthenticated call)."""
    key_id = os.environ.get("KALSHI_API_KEY_ID", "")
    if private_key is None or not key_id:
        return {}
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    ts = str(int(time.time() * 1000))
    msg = (ts + method.upper() + path).encode()
    sig = private_key.sign(msg, padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH,
    ), hashes.SHA256())
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "Content-Type": "application/json",
    }


def authed_get(sess, pkey, path, params=None, timeout=8):
    """GET PERP_BASE+path with a fresh RSA-PSS signature over PERP_PATH_PREFIX+path.
    Returns (json_dict, rtt_ms) or (None, rtt_ms) on error. Never raises."""
    t0 = time.time()
    try:
        hdrs = _sign(pkey, "GET", PERP_PATH_PREFIX + path)
        r = sess.get(PERP_BASE + path, params=params, headers=hdrs, timeout=timeout)
        rtt = (time.time() - t0) * 1e3
        if r.status_code != 200:
            return {"_status": r.status_code, "_body": r.text[:300]}, rtt
        return r.json(), rtt
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {str(e)[:120]}"}, (time.time() - t0) * 1e3


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _asset_of(ticker, series=""):
    """Normalized asset tag for a perp -> its own output file. Prefers a known crypto substring; else
    derives the token between the KX prefix and the PERP suffix (KXLTCPERP->ltc, KXHBARPERP->hbar) so
    every discovered perp gets a distinct file instead of collapsing into one 'unknown'."""
    s = f"{ticker} {series}".upper()
    for a in ("BTC", "ETH", "SOL", "XRP", "DOGE", "LINK", "LTC", "BCH", "DOT",
              "HBAR", "NEAR", "SUI", "XLM", "ZEC", "HYPE", "KSHIB", "ADA", "AVAX"):
        if a in s:
            return a.lower()
    t = (ticker or "").upper()
    if t.startswith("KX") and t.endswith("PERP"):
        core = t[2:-4]
        if core:
            return core.lower()
    return "unknown"


def _looks_perp(ticker, series="", obj=None):
    """True if this looks like a crypto PERPETUAL (not a dated binary). The live product tickers are
    KX{ASSET}PERP (KXBTCPERP/KXETHPERP/KXSOLPERP/KXXRPPERP/...); ending in PERP is the strong signal
    and cleanly excludes lookalikes like KXIPOPERPLEXITY. Kept broad on the fallbacks so a future
    naming (e.g. a dated perp series or a funding_rate-bearing object) is still auto-discovered."""
    t = (ticker or "").upper()
    if t.endswith("PERP") or t.endswith("PERPETUAL"):
        return True
    s = f"{ticker} {series}".upper()
    if "PERPETUAL" in s or "-PERP-" in s:
        return True
    if isinstance(obj, dict):
        # schema-agnostic: any field advertising a perpetual/funding product
        blob = json.dumps(obj).upper()
        if any(tok in blob for tok in ("FUNDING_RATE", "SETTLEMENT_MARK_PRICE", "REFERENCE_PRICE")):
            return True
    return False


def list_margin_markets(sess, pkey):
    """GET /margin/markets -> (list_of_market_dicts, rtt_ms). Paginated defensively (the live product
    returns all 16 crypto perps in ONE page with no cursor, but we page in case that grows). This ONE
    call is the complete perp snapshot: bid/ask/price/reference_price/settlement_mark_price/OI/volume
    for every perp (confirmed live 2026-07-15) -- no per-market call needed for the core row."""
    out, cursor = [], None
    rtt0 = 0.0
    for _ in range(10):
        params = {"limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d, rtt = authed_get(sess, pkey, "/margin/markets", params=params)
        rtt0 = rtt
        if not isinstance(d, dict) or d.get("_status") or d.get("_error"):
            break
        ms = d.get("markets") or d.get("margin_markets") or d.get("data") or []
        out.extend([m for m in ms if isinstance(m, dict)])
        cursor = d.get("cursor")
        if not cursor or not ms:
            break
        time.sleep(0.15)
    return out, rtt0


def discover(sess, pkey):
    """Discover crypto perp markets from /margin/markets. Returns (perps, discovery_log).
    perps: [{ticker, series, asset, raw}]. Nothing hardcoded -- the 16 live perps
    (KX{BTC,ETH,SOL,XRP,LINK,LTC,DOGE,BCH,DOT,HBAR,NEAR,SUI,XLM,ZEC,HYPE,KSHIB}PERP as of
    2026-07-15) are all DISCOVERED, so a new listing is picked up automatically next run. We do NOT
    scan the public elections host: perps are definitively only on external-api /margin/markets;
    scanning the binaries there just bloats the registry with thousands of irrelevant tickers."""
    ms, rtt = list_margin_markets(sess, pkey)
    log = {"utc": now_iso(),
           "authed": bool(_sign(pkey, "GET", PERP_PATH_PREFIX + "/margin/markets")),
           "endpoint": "/margin/markets", "rtt_ms": round(rtt, 1),
           "n_markets_listed": len(ms),
           "all_tickers": sorted(m.get("ticker", "") for m in ms),
           "perps": []}
    perps, seen = [], set()
    for m in ms:
        tk = m.get("ticker") or m.get("market_ticker") or m.get("id")
        series = m.get("series_ticker") or m.get("series") or ""
        if not tk or tk in seen or not _looks_perp(tk, series, m):
            continue
        seen.add(tk)
        perps.append({"ticker": tk, "series": series, "asset": _asset_of(tk, series), "raw": m})
    log["perps"] = [{"ticker": p["ticker"], "asset": p["asset"]} for p in perps]
    return perps, log


# ---------------------------------------------------------------------------
# Per-market polling
# ---------------------------------------------------------------------------

def extract_extras(obj):
    """Sweep every key whose name hints at funding/mark/index/settlement/etc and return {k: float|raw}.
    Schema-agnostic: captures the perp-specific fields no matter what Kalshi names them."""
    out = {}
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        kl = k.lower()
        if any(h in kl for h in EXTRA_KEY_HINTS):
            fv = f(v)
            out[k] = fv if fv is not None else v
    return out


def _pxts(obj, key):
    """Pull a {price, ts_ms} sub-object (reference_price/settlement_mark_price/liquidation_mark_price)
    -> (price_float, ts_ms). Returns (None, None) if absent."""
    v = obj.get(key) if isinstance(obj, dict) else None
    if isinstance(v, dict):
        return f(v.get("price")), v.get("ts_ms")
    return f(v), None


def parse_perp_row(p, obj, nowt):
    """Build a self-describing perp row from ONE /margin/markets snapshot object. Field names are the
    live schema (2026-07-15): bid/ask strings, price=last, reference_price=index(BRTI), settlement_
    mark_price=mark, liquidation_mark_price, open_interest(+notional), volume/volume_24h(+notional),
    contract_size, tick_size, leverage_estimate(s), status. extract_extras() also sweeps any
    funding/mark/index-named key so a schema change can't silently drop the perp-specific fields."""
    row = {"t": round(nowt, 3), "ts": now_iso(), "ticker": p["ticker"], "series": p["series"],
           "asset": p["asset"], "venue": "kalshi", "product": "perp"}
    if not isinstance(obj, dict):
        row["err"] = "no_snapshot"
        return row
    bid = f(obj.get("bid") or obj.get("yes_bid") or obj.get("yes_bid_dollars"))
    ask = f(obj.get("ask") or obj.get("yes_ask") or obj.get("yes_ask_dollars"))
    row["bid"], row["ask"] = bid, ask
    row["mid"] = round((bid + ask) / 2, 6) if (bid is not None and ask is not None) else None
    row["last"] = f(obj.get("price") or obj.get("last_price") or obj.get("last_price_dollars"))
    row["volume"] = f(obj.get("volume") or obj.get("volume_fp"))
    row["volume_24h"] = f(obj.get("volume_24h") or obj.get("volume_24h_fp"))
    row["open_interest"] = f(obj.get("open_interest") or obj.get("open_interest_fp"))
    row["oi_notional_usd"] = f(obj.get("open_interest_notional_value_dollars"))
    row["vol_notional_usd"] = f(obj.get("volume_notional_value_dollars"))
    row["index"], row["index_ts_ms"] = _pxts(obj, "reference_price")          # BRTI index
    row["mark"], row["mark_ts_ms"] = _pxts(obj, "settlement_mark_price")      # settlement mark
    row["liq_mark"], _ = _pxts(obj, "liquidation_mark_price")
    row["contract_size"] = f(obj.get("contract_size"))
    row["tick_size"] = f(obj.get("tick_size"))
    row["leverage_estimate"] = f(obj.get("leverage_estimate"))
    row["status"] = obj.get("status")
    row["extras"] = extract_extras(obj)   # anything fund*/mark*/index*/settle*/liquid*/notional*
    return row


def fetch_orderbook(sess, pkey, tk, depth=10):
    """Full-depth top-of-book for one perp: (bid, ask, bids[:depth], asks[:depth], rtt_ms).
    Live shape: {"orderbook": {"bids": [[price,qty],...], "asks": [[price,qty],...]}} (public)."""
    ob, rtt = authed_get(sess, pkey, f"/margin/markets/{tk}/orderbook")
    o = ob.get("orderbook") if isinstance(ob, dict) else None
    if not isinstance(o, dict):
        o = ob if isinstance(ob, dict) else {}
    bids = o.get("bids") or o.get("buy") or o.get("yes") or o.get("yes_dollars")
    asks = o.get("asks") or o.get("sell") or o.get("no") or o.get("no_dollars")
    def _lv(levels, side):
        # Kalshi returns levels WORST-price-first (best at the end). Normalize to NEAR-TOUCH-first,
        # best `depth` levels, so the stored depth is the tradeable side regardless of API ordering.
        rows = [[f(lv[0]), f(lv[1])] for lv in (levels or [])
                if isinstance(lv, (list, tuple)) and len(lv) >= 2 and f(lv[0]) is not None]
        rows.sort(key=lambda r: r[0], reverse=(side == "bid"))   # bids high->low, asks low->high
        return rows[:depth]
    return (_best(bids, "bid"), _best(asks, "ask"), _lv(bids, "bid"), _lv(asks, "ask"), round(rtt, 1))


def fetch_funding(sess, pkey, tk):
    """Funding estimate for one perp. Live shape (public):
    {funding_rate, mark_price, next_funding_time, computed_time, market_ticker}. Returns dict/None."""
    est, _ = authed_get(sess, pkey, "/margin/funding_rates/estimate", params={"ticker": tk})
    if isinstance(est, dict) and not est.get("_status") and not est.get("_error"):
        return {"funding_rate": f(est.get("funding_rate")),
                "mark_price": f(est.get("mark_price")),
                "next_funding_time": est.get("next_funding_time"),
                "computed_time": est.get("computed_time")}
    return None


def _best(levels, side):
    """Best price off a level list. Handles [[price,qty],...] (ascending, best-at-end for Kalshi
    yes/no books) and [{price/qty}] dict rows. Returns float price or None. Robust to unknown shape."""
    if not levels or not isinstance(levels, list):
        return None
    prices = []
    for lv in levels:
        if isinstance(lv, (list, tuple)) and lv:
            p = f(lv[0])
        elif isinstance(lv, dict):
            p = f(lv.get("price") or lv.get("px") or lv.get("p") or lv.get("dollars"))
        else:
            p = f(lv)
        if p is not None:
            prices.append(p)
    if not prices:
        return None
    return max(prices) if side == "bid" else min(prices)


# ---------------------------------------------------------------------------
# Aligned 15m-binary mid co-collection (public, NO auth) -- same clock as the perp polls so the
# perp<->binary basis is computable on ONE clock. (collect.yml already collects the richer
# ticks_kalshi_<asset>15m stream, but on a DIFFERENT cron minute -> not time-aligned to these polls.)
# ---------------------------------------------------------------------------

def poll_binmid(sess, asset):
    """Nearest open 15m binary's YES top-of-book mid for `asset` (public no-auth). Returns row/None."""
    series = f"KX{asset.upper()}15M"
    try:
        d = sess.get(f"{PUBLIC_BASE}/markets",
                     params={"series_ticker": series, "status": "open", "limit": 5}, timeout=6).json()
    except Exception:
        return None
    now = time.time()
    best = None
    for m in d.get("markets") or []:
        try:
            ct = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        if ct > now + 5 and (best is None or ct < best["_ct"]):
            yb = f(m.get("yes_bid_dollars")); ya = f(m.get("yes_ask_dollars"))
            best = {"_ct": ct, "ticker": m.get("ticker"),
                    "yes_bid": yb, "yes_ask": ya,
                    "mid": round((yb + ya) / 2, 6) if (yb is not None and ya is not None) else None,
                    "last": f(m.get("last_price_dollars"))}
    if best is None:
        return None
    ct = best.pop("_ct", None)
    best.update({"t": round(now, 3), "ts": now_iso(), "asset": asset, "series": series,
                 "venue": "kalshi", "product": "binary15m",
                 "ws": int(ct) - 900 if ct else None})   # window-start, for joining vs perp clock
    return best


def heartbeat(tag, out_dir, n_perps, polls):
    now = time.time()
    if now - _HB[0] < 90:
        return
    _HB[0] = now
    try:
        json.dump({"utc": now_iso(), "tag": tag, "status": "running",
                   "n_perps": n_perps, "polls": polls},
                  open(os.path.join(out_dir, f"HEARTBEAT_kalshi_perp_{tag}.json"), "w"), indent=2)
        url = os.environ.get("HEARTBEAT_URL")
        if url:
            try:
                requests.get(url, timeout=8)
            except Exception:
                pass
    except Exception:
        pass


def write_note(out_dir, tag, reason, log=None):
    """Graceful 'nothing to collect' marker so a keyless / no-perp CI run still leaves a breadcrumb
    and exits 0 (never fails the workflow)."""
    try:
        os.makedirs(out_dir, exist_ok=True)
        note = {"utc": now_iso(), "tag": tag, "status": "no_perp_data", "reason": reason}
        if log is not None:
            note["discovery"] = log
        json.dump(note, open(os.path.join(out_dir, f"NOTE_kalshi_perp_{tag}.json"), "w"), indent=2)
    except Exception:
        pass


def main():
    signal.signal(signal.SIGTERM, lambda *_: STOP.__setitem__(0, True))

    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    tag = sys.argv[3] if len(sys.argv) > 3 else f"perp{int(time.time())}"
    os.makedirs(out_dir, exist_ok=True)

    sess = requests.Session()
    # Auth is OPTIONAL: the perp READ endpoints (/margin/markets[/orderbook],
    # /margin/funding_rates/estimate) are public -- confirmed returning 200 with NO key 2026-07-15.
    # A key (KALSHI_API_KEY_ID + KALSHI_PRIVATE_KEY_PATH) is signed onto every request when present,
    # so this collector keeps working unchanged if Kalshi later gates these behind auth.
    pkey = _load_private_key()
    authed = pkey is not None and bool(os.environ.get("KALSHI_API_KEY_ID"))

    print(f"{now_iso()} [perp] discovering crypto perpetuals on {PERP_BASE} (authed={authed}) ...",
          flush=True)
    perps, log = discover(sess, pkey)
    # ALWAYS write the registry: full raw schema of every discovered perp + endpoint diagnostics, so
    # the FIRST CI run teaches us the real product schema.
    registry = {"utc": now_iso(), "tag": tag, "authed": authed,
                "n_perps": len(perps), "discovery": log,
                "markets": {p["ticker"]: {"series": p["series"], "asset": p["asset"], "raw": p["raw"]}
                            for p in perps}}
    json.dump(registry, open(os.path.join(out_dir, f"registry_kalshi_perp_{tag}.json"), "w"),
              indent=2, default=str)
    print(f"{now_iso()} [perp] discovered {len(perps)} perp market(s): "
          f"{[p['ticker'] for p in perps]} (of {log.get('n_markets_listed')} margin markets listed)",
          flush=True)

    if not perps:
        write_note(out_dir, tag, "no_perp_markets_discovered", log)
        print(f"{now_iso()} [perp] no perp markets discovered -> note written, exit 0", flush=True)
        return

    # one perp file per asset (ALL discovered perps recorded, not just the paired ones -- the extra
    # crypto perps are free carry/basis history); binary-mid file only for the paired 15m assets.
    perp_fh, bin_fh = {}, {}
    def _perp_file(asset):
        if asset not in perp_fh:
            perp_fh[asset] = gzip.open(
                os.path.join(out_dir, f"ticks_kalshi_perp_{asset}_{tag}.jsonl.gz"), "at")
        return perp_fh[asset]
    def _bin_file(asset):
        if asset not in bin_fh:
            bin_fh[asset] = gzip.open(
                os.path.join(out_dir, f"ticks_kalshi_perp_binmid_{asset}_{tag}.jsonl.gz"), "at")
        return bin_fh[asset]

    # FOCUS assets = discovered perps that ALSO have a 15m binary (btc/eth/sol/xrp): for these we add
    # full-depth orderbook + funding estimate + the aligned binary mid, since they're the pairs the
    # basis/carry edges will actually trade. Other perps get the (free) snapshot row only.
    focus = [p for p in perps if p["asset"] in BIN_ASSETS]
    bin_assets = sorted({p["asset"] for p in focus})

    print(f"{now_iso()} [perp] collecting {dur}s; focus(paired w/ 15m)={[p['ticker'] for p in focus]}; "
          f"aligned binaries={bin_assets}", flush=True)
    end = time.time() + dur
    polls = 0
    last_fund = 0.0
    while time.time() < end and not STOP[0]:
        t0 = time.time()
        heartbeat(tag, out_dir, len(perps), polls)
        funding_due = (t0 - last_fund) >= FUND_POLL_S
        if funding_due:
            last_fund = t0

        # ONE snapshot call gives every perp's core row (bid/ask/price/index/mark/OI/volume).
        snap_list, snap_rtt = list_margin_markets(sess, pkey)
        snap = {m.get("ticker"): m for m in snap_list if isinstance(m, dict)}
        for p in perps:
            if STOP[0]:
                break
            try:
                row = parse_perp_row(p, snap.get(p["ticker"]), t0)
                row["snap_rtt_ms"] = round(snap_rtt, 1)
                if p in focus:
                    # full-depth book (microstructure) every cycle for the paired perps
                    bb, ba, bids, asks, ob_rtt = fetch_orderbook(sess, pkey, p["ticker"])
                    if bb is not None:
                        row["bid"] = bb
                    if ba is not None:
                        row["ask"] = ba
                    if bb is not None and ba is not None:
                        row["mid"] = round((bb + ba) / 2, 6)
                    row["book"] = {"bids": bids, "asks": asks, "rtt_ms": ob_rtt}
                    if funding_due:
                        fu = fetch_funding(sess, pkey, p["ticker"])
                        if fu is not None:
                            row["funding"] = fu
            except Exception as e:
                row = {"t": round(time.time(), 3), "ts": now_iso(), "ticker": p["ticker"],
                       "asset": p["asset"], "err": f"{type(e).__name__}: {str(e)[:120]}"}
            _perp_file(p["asset"]).write(json.dumps(row, default=str) + "\n")

        # aligned 15m-binary mid (public, no auth) -- one call per paired asset, SAME clock as above
        for a in bin_assets:
            if STOP[0]:
                break
            try:
                br = poll_binmid(sess, a)
            except Exception:
                br = None
            if br is not None:
                _bin_file(a).write(json.dumps(br, default=str) + "\n")
        for fh in list(perp_fh.values()) + list(bin_fh.values()):
            try:
                fh.flush()
            except Exception:
                pass
        polls += 1
        time.sleep(max(0.0, POLL_S - (time.time() - t0)))

    for fh in list(perp_fh.values()) + list(bin_fh.values()):
        try:
            fh.close()
        except Exception:
            pass
    try:
        json.dump({"utc": now_iso(), "tag": tag, "status": "stopped",
                   "n_perps": len(perps), "polls": polls},
                  open(os.path.join(out_dir, f"HEARTBEAT_kalshi_perp_{tag}.json"), "w"), indent=2)
    except Exception:
        pass
    print(f"{now_iso()} [perp] done: {polls} poll cycles, {len(perps)} perp market(s)"
          f"{' (SIGTERM drain)' if STOP[0] else ''}", flush=True)


if __name__ == "__main__":
    main()
