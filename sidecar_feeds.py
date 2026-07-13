"""sidecar_feeds.py -- ONE process, three independent asyncio capture loops that close three data
gaps in the always-on Kalshi collector chain (collect.yml), kept in a single sidecar so runner-minutes
stay flat instead of spawning another whole workflow:

  1. COMPOSITE SPOT (Binance + Coinbase best bid/ask -> 1s-resolution composite mid + cross-venue
     spread). Purpose: a fair-value anchor independent of Kalshi's own book, for honest lead-lag work
     (xvenue.py-style studies currently only have single-venue REST polls).
  2. WS LATENCY STAMPS (Kalshi's own authenticated market-data WS, `ticker` channel, on the 4 crypto
     15-min tickers). Every ~10th message that carries a venue timestamp (`ts_ms`) is logged as
     {ts_venue, ts_local, lag_ms}. Purpose: quantify GitHub-Actions-runner-to-Kalshi latency before
     deciding whether a VPS is worth the money (CLAUDE.md: "this container is ephemeral").
  3. MACRO CALENDAR (once per run): next 7 days of high-impact US macro events (CPI/FOMC/NFP/PPI/GDP).
     Purpose: pre-known vol-regime timestamps for a future regime router.
  4. KALSHI HIRES (BTC only; DECISION_MAP node P1): every `orderbook_delta`/`trade`/`ticker` ws
     message for the active KXBTC15M market, recorded raw with a local ms timestamp. Purpose: the
     1.2s REST poll cadence is the SAMPLING FLOOR under every "no pre-fill signal" verdict (C1
     ceiling, L1.5 1.2s lead = one tick); this stream makes sub-second microstructure visible so
     those verdicts can be re-tested at true resolution, and F10 (stale-quote exceedance duration)
     can be measured below 3s. Env-gated: SIDECAR_HIRES=0 turns loops 4+5 off.
  5. SPOT HIRES (BTC only; same node): Binance btcusdt bookTicker (change-only, >=50ms apart) +
     aggTrade (all) + Coinbase BTC-USD matches (all), raw with local ms timestamps. Purpose: the
     composite spot loop samples at 1s -- too coarse to time a theo move against a Kalshi quote
     update in the sniping race; this is the native-resolution theo clock.

DESIGN: each loop is wrapped so ONE loop's failure (bad creds, network flake, unexpected schema) can
NEVER take down the other two -- this mirrors kalshi_trader.ws_feeder's "websockets missing -> warn
and return" and "disconnected -> reconnect in Ns" idioms (that file is READ ONLY reference here; the
auth/signing helpers below are a small, deliberately self-contained duplicate so this sidecar has zero
coupling to the trading module). All loops obey one shared deadline (argv[1] seconds) and a shared
asyncio.Event that a SIGTERM/SIGINT handler sets for clean early shutdown; every gzip writer is opened
once and closed exactly once in a `finally` so the gzip footer is always written (no truncated .gz).
Memory is O(1) per loop -- a handful of floats in a dict, never an unbounded buffer.

Usage:
    python sidecar_feeds.py [duration_s] [out_dir]
    python sidecar_feeds.py 2520 gha_data          # matches the ~42-min collect cycle

Env:
    GITHUB_RUN_ID              -> RUNID used in output filenames (falls back to "local")
    KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY_PATH
                                -> needed for loop 2 only (Kalshi's WS requires a signed connection
                                   even for read-only market-data channels); loop 2 logs a notice and
                                   no-ops (does not raise) when absent, so loops 1 and 3 are unaffected.

Outputs (written flat into out_dir; the caller/workflow date-partitions on commit, matching the
existing collector convention in kalshi_ladder_collect.py / pmkt_collect.py):
    spot_composite_r<RUNID>.jsonl.gz   {"ts_local","asset","binance_mid","coinbase_mid","spread_bps"}
    ws_latency_r<RUNID>.jsonl.gz       {"ts_venue","ts_local","lag_ms"}
    macro_calendar.jsonl               {"ts","name","impact",...}  (overwritten every run, NOT gzipped)
    hires_kalshi_btc_r<RUNID>.jsonl.gz {"tl":local_ms,"t":msg_type,"m":raw_payload[,"seq"]}
    hires_spot_btc_r<RUNID>.jsonl.gz   {"tl":local_ms,"src":"bnb_bt|bnb_tr|cb_tr",...essential fields}
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import json
import os
import signal
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone

import requests

try:
    import websockets
except Exception:
    websockets = None

RUNID = os.environ.get("GITHUB_RUN_ID", "local")
ASSETS = ["btc", "eth", "sol", "xrp"]

BINANCE_SYMBOLS = {"btc": "btcusdt", "eth": "ethusdt", "sol": "solusdt", "xrp": "xrpusdt"}
COINBASE_PRODUCTS = {"btc": "BTC-USD", "eth": "ETH-USD", "sol": "SOL-USD", "xrp": "XRP-USD"}

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"


def _log(tag, msg):
    print(f"[{tag}] {msg}", flush=True)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


async def _run_loop_safe(name, coro):
    """Top-level guard: an unhandled exception in one loop is logged, never propagated, so
    asyncio.gather over the three loops always completes all three (independent failure)."""
    try:
        await coro
    except asyncio.CancelledError:
        raise
    except Exception:
        _log(name, "FATAL (loop aborted, others unaffected):")
        traceback.print_exc()


# =============================================================================================
# LOOP 1 -- COMPOSITE SPOT (Binance bookTicker + Coinbase ticker -> 1s composite rows)
# =============================================================================================

async def _binance_reader(state, stop_evt):
    if not BINANCE_SYMBOLS:
        return
    streams = "/".join(f"{s}@bookTicker" for s in BINANCE_SYMBOLS.values())
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    sym2asset = {v: k for k, v in BINANCE_SYMBOLS.items()}
    backoff = 1.0
    while not stop_evt.is_set():
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=20,
                                           close_timeout=2) as ws:
                _log("spot", "binance connected")
                backoff = 1.0
                while not stop_evt.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        env = json.loads(raw)
                        d = env.get("data") or env    # combined-stream envelope {"stream","data"}
                        sym = (d.get("s") or "").lower()
                        asset = sym2asset.get(sym)
                        if asset is None:
                            continue
                        bid, ask = float(d["b"]), float(d["a"])
                        state[asset]["binance_mid"] = (bid + ask) / 2.0
                    except Exception:
                        continue
        except Exception as e:
            if stop_evt.is_set():
                break
            _log("spot", f"binance disconnected ({type(e).__name__}: {str(e)[:80]}); "
                          f"reconnect in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


async def _coinbase_reader(state, stop_evt):
    if not COINBASE_PRODUCTS:
        return
    prod2asset = {v: k for k, v in COINBASE_PRODUCTS.items()}
    backoff = 1.0
    while not stop_evt.is_set():
        try:
            async with websockets.connect("wss://ws-feed.exchange.coinbase.com", ping_interval=15,
                                           ping_timeout=20, close_timeout=2) as ws:
                sub = {"type": "subscribe", "product_ids": list(COINBASE_PRODUCTS.values()),
                       "channels": ["ticker"]}
                await ws.send(json.dumps(sub))
                _log("spot", "coinbase connected")
                backoff = 1.0
                while not stop_evt.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        msg = json.loads(raw)
                        if msg.get("type") != "ticker":
                            continue
                        asset = prod2asset.get(msg.get("product_id"))
                        if asset is None:
                            continue
                        bid, ask = msg.get("best_bid"), msg.get("best_ask")
                        if bid is None or ask is None:
                            continue
                        state[asset]["coinbase_mid"] = (float(bid) + float(ask)) / 2.0
                    except Exception:
                        continue
        except Exception as e:
            if stop_evt.is_set():
                break
            _log("spot", f"coinbase disconnected ({type(e).__name__}: {str(e)[:80]}); "
                          f"reconnect in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


async def _spot_writer(state, fh, stop_evt):
    """Samples the shared `state` dict once a second and writes one composite row per asset.
    O(1) memory: `state` only ever holds the latest mid per venue per asset."""
    n = 0
    while not stop_evt.is_set():
        ts_local = _now_iso()
        for asset in ASSETS:
            bmid = state[asset]["binance_mid"]
            cmid = state[asset]["coinbase_mid"]
            spread_bps = None
            if bmid is not None and cmid is not None:
                avg = (bmid + cmid) / 2.0
                if avg > 0:
                    spread_bps = round(abs(bmid - cmid) / avg * 1e4, 3)
            fh.write(json.dumps({"ts_local": ts_local, "asset": asset,
                                  "binance_mid": bmid, "coinbase_mid": cmid,
                                  "spread_bps": spread_bps}) + "\n")
            n += 1
        fh.flush()
        try:
            await asyncio.wait_for(stop_evt.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass
    return n


async def spot_composite_loop(out_dir, stop_evt):
    if websockets is None:
        _log("spot", "websockets not installed -> loop OFF")
        return
    path = os.path.join(out_dir, f"spot_composite_r{RUNID}.jsonl.gz")
    state = {a: {"binance_mid": None, "coinbase_mid": None} for a in ASSETS}
    fh = gzip.open(path, "at")
    try:
        n = await asyncio.gather(
            _spot_writer(state, fh, stop_evt),
            _binance_reader(state, stop_evt),
            _coinbase_reader(state, stop_evt),
        )
        _log("spot", f"done: {n[0]} rows written -> {path}")
    finally:
        fh.close()


# =============================================================================================
# LOOP 2 -- KALSHI WS LATENCY STAMPS (ticker channel, sampled every ~10th message)
# =============================================================================================
# Auth pattern READ from kalshi_trader.py (WS_URL, `cmd:"subscribe"` envelope, RSA-PSS signed
# headers over "GET"+"/trade-api/ws/v2") -- duplicated here in miniature rather than imported, so
# this sidecar has no coupling to (and cannot be broken by future edits of) the trading module.
# Kalshi's WS requires the signed connection for ALL channels, including read-only market data
# (there is no unauthenticated public WS), so loop 2 needs the same two secrets as live.yml.

def _load_kalshi_private_key():
    path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not path or not os.path.exists(path):
        return None
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        with open(path, "rb") as fh:
            return load_pem_private_key(fh.read(), password=None)
    except Exception as e:
        _log("ws_latency", f"failed to load private key: {e}")
        return None


def _kalshi_sign(private_key, method: str, path: str) -> dict:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    ts = str(int(time.time() * 1000))
    msg = (ts + method.upper() + path).encode()
    sig = private_key.sign(msg, padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH,
    ), hashes.SHA256())
    return {
        "KALSHI-ACCESS-KEY": os.environ.get("KALSHI_API_KEY_ID", ""),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "Content-Type": "application/json",
    }


def _discover_tickers(sess):
    """Nearest open KX{asset}15M market ticker per asset (public REST, no auth). Mirrors
    kalshi_trader.discover(); duplicated (not imported) for the same no-coupling reason above."""
    out = {}
    now = time.time()
    for asset in ASSETS:
        series = f"KX{asset.upper()}15M"
        try:
            d = sess.get(f"{KALSHI_BASE}/markets",
                         params={"series_ticker": series, "status": "open", "limit": 5},
                         timeout=8).json()
        except Exception:
            continue
        best = None
        for m in (d.get("markets") or []):
            try:
                ct = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp()
            except Exception:
                continue
            if ct > now + 5 and (best is None or ct < best[1]):
                best = (m["ticker"], ct)
        if best:
            out[asset] = best[0]
    return out


async def ws_latency_loop(out_dir, stop_evt):
    if websockets is None:
        _log("ws_latency", "websockets not installed -> loop OFF")
        return
    if not os.environ.get("KALSHI_API_KEY_ID"):
        _log("ws_latency", "KALSHI_API_KEY_ID not set -> loop OFF (Kalshi WS requires an "
                            "authenticated connection even for read-only market data)")
        return
    private_key = _load_kalshi_private_key()
    if private_key is None:
        _log("ws_latency", "no usable KALSHI_PRIVATE_KEY_PATH -> loop OFF")
        return

    path = os.path.join(out_dir, f"ws_latency_r{RUNID}.jsonl.gz")
    fh = gzip.open(path, "at")
    sess = requests.Session()
    loop = asyncio.get_running_loop()
    n_seen = n_logged = 0
    backoff = 1.0
    try:
        while not stop_evt.is_set():
            tickers = await loop.run_in_executor(None, _discover_tickers, sess)
            if not tickers:
                _log("ws_latency", "no open KX*15M markets found; retry in 10s")
                try:
                    await asyncio.wait_for(stop_evt.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    pass
                continue
            market_tickers = sorted(set(tickers.values()))
            try:
                auth_hdrs = _kalshi_sign(private_key, "GET", "/trade-api/ws/v2")
                try:
                    connect_ctx = websockets.connect(
                        KALSHI_WS_URL, additional_headers=auth_hdrs,
                        ping_interval=10, ping_timeout=20, max_size=None)
                except TypeError:
                    connect_ctx = websockets.connect(
                        KALSHI_WS_URL, extra_headers=auth_hdrs,
                        ping_interval=10, ping_timeout=20, max_size=None)
                async with connect_ctx as ws:
                    sub_msg = json.dumps({
                        "id": 1, "cmd": "subscribe",
                        "params": {"channels": ["ticker"], "market_tickers": market_tickers},
                    })
                    await ws.send(sub_msg)
                    _log("ws_latency", f"subscribed ticker channel: {market_tickers}")
                    backoff = 1.0
                    # re-discover periodically so a 15-min window rollover gets picked up
                    resub_at = time.time() + 120
                    while not stop_evt.is_set() and time.time() < resub_at:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        except asyncio.TimeoutError:
                            continue
                        ts_local_ms = time.time() * 1000.0
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue
                        if msg.get("type") != "ticker":
                            continue
                        payload = msg.get("msg") or {}
                        ts_venue = payload.get("ts_ms")
                        if ts_venue is None:
                            continue         # only messages carrying a venue timestamp count
                        n_seen += 1
                        if n_seen % 10 == 0:  # sample every ~10th timestamped message
                            fh.write(json.dumps({
                                "ts_venue": ts_venue,
                                "ts_local": round(ts_local_ms, 1),
                                "lag_ms": round(ts_local_ms - float(ts_venue), 1),
                            }) + "\n")
                            fh.flush()
                            n_logged += 1
            except Exception as e:
                if stop_evt.is_set():
                    break
                _log("ws_latency", f"disconnected ({type(e).__name__}: {str(e)[:80]}); "
                                    f"reconnect in {backoff:.0f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
    finally:
        fh.close()
        _log("ws_latency", f"done: {n_seen} timestamped ticker msgs seen, "
                            f"{n_logged} lag samples logged -> {path}")


# =============================================================================================
# LOOP 3 -- MACRO CALENDAR (once per run; next 7 days of CPI/FOMC/NFP/PPI/GDP)
# =============================================================================================
# PRIMARY source: Kalshi's OWN public market API (no key, already the bot's core dependency).
# Kalshi lists one binary-ladder series per macro release (KXCPI/KXCPIYOY/KXCPICOREYOY/KXFED/
# KXFEDDECISION/KXPAYROLLS/KXGDP) whose `close_time` IS the scheduled release moment (spot-checked
# 2026-07-11 against KALSHI_MACRO.md's independently-documented dates -- exact match, e.g. CPI
# 2026-07-14, GDP 2026-07-30). This is more reliable than scraping a third-party calendar because
# it is the same API every other collector in this repo already depends on.
#
# LIMITATION (documented per spec): Kalshi does NOT currently list a PPI series, and its "next
# open market" per series can be >7 days out in the FOMC/NFP/GDP off-weeks (nothing to show is
# correct behavior, not a bug). For PPI, and as a secondary supplement for other US High-impact
# events, we also try ForexFactory's no-key weekly JSON mirror (nfs.faireconomy.media). That feed
# ONLY covers the CURRENT ForexFactory calendar week (observed: Sun-Fri) -- there is no working
# "next week" endpoint (probed 2026-07-11: nfs.faireconomy.media/ff_calendar_nextweek.json -> 404),
# so near the end of a calendar week it is effectively stale for a forward-looking 7-day window.
# If BOTH sources are unreachable or empty, we fall back to a STATIC schedule: the published 2026
# FOMC meeting dates (federalreserve.gov/monetarypolicy/fomccalendars.htm) plus simple monthly-
# pattern heuristics for CPI/PPI/NFP/GDP (e.g. NFP = first Friday of the month). Those heuristic
# entries are tagged source="static_approx" and impact_note explains the +/- few days uncertainty.

KALSHI_MACRO_GROUPS = {
    "CPI":  (["KXCPI", "KXCPIYOY", "KXCPICOREYOY"], "CPI release (headline/core/YoY)"),
    "FOMC": (["KXFED", "KXFEDDECISION"], "FOMC meeting / rate decision"),
    "NFP":  (["KXPAYROLLS"], "Nonfarm Payrolls (Employment Situation)"),
    "GDP":  (["KXGDP"], "GDP (advance estimate)"),
}

# published 2026 FOMC decision days (2nd day of each 2-day meeting), 14:00 ET
FOMC_2026_DECISION_DAYS_ET = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]


def _et_to_utc_iso(d: date, hour_et: int, minute_et: int = 30) -> str:
    """Rough US-Eastern -> UTC (fixed DST heuristic: EDT/UTC-4 Mar-Nov, EST/UTC-5 Nov-Mar) --
    fine for a "which day, roughly which session" regime-router timestamp, not for trading."""
    offset = 4 if 3 <= d.month <= 10 else 5
    dt = datetime(d.year, d.month, d.day, hour_et, minute_et, tzinfo=timezone.utc) + timedelta(hours=offset)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _nearest_kalshi_macro_events(sess, now_utc, horizon_days=7):
    out = []
    for group, (series_list, name) in KALSHI_MACRO_GROUPS.items():
        best = None
        for series in series_list:
            try:
                d = sess.get(f"{KALSHI_BASE}/markets",
                             params={"series_ticker": series, "status": "open", "limit": 100},
                             timeout=10).json()
            except Exception:
                continue
            for m in (d.get("markets") or []):
                try:
                    ct = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
                except Exception:
                    continue
                if ct > now_utc and (best is None or ct < best[0]):
                    best = (ct, m.get("ticker"))
        if best and best[0] <= now_utc + timedelta(days=horizon_days):
            out.append({"ts": best[0].strftime("%Y-%m-%dT%H:%M:%SZ"), "name": name,
                        "impact": "high", "source": "kalshi_series", "series_ticker": best[1]})
    return out


def _forexfactory_us_high(now_utc, horizon_days=7):
    out = []
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        r.raise_for_status()
        events = r.json()
    except Exception as e:
        _log("macro", f"ForexFactory fetch failed ({type(e).__name__}); skipping supplement")
        return out
    end = now_utc + timedelta(days=horizon_days)
    for e in events:
        try:
            if e.get("country") != "USD" or e.get("impact") != "High":
                continue
            dt = datetime.fromisoformat(e["date"]).astimezone(timezone.utc)
            if not (now_utc <= dt <= end):
                continue
            out.append({"ts": dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "name": e.get("title", "?"),
                        "impact": "high", "source": "forexfactory"})
        except Exception:
            continue
    return out


def _static_fallback(now_utc, horizon_days=7):
    """Deterministic monthly-pattern schedule -- used only to fill gaps the two live sources
    above miss (documented limitation above), never silently instead of real data."""
    out = []
    end = now_utc + timedelta(days=horizon_days)
    for ds in FOMC_2026_DECISION_DAYS_ET:
        y, mo, dy = (int(x) for x in ds.split("-"))
        ts = _et_to_utc_iso(date(y, mo, dy), 14, 0)
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if now_utc <= dt <= end:
            out.append({"ts": ts, "name": "FOMC meeting / rate decision", "impact": "high",
                        "source": "static", "note": "published Fed calendar, decision-day 14:00 ET"})
    # monthly heuristics for whichever month(s) the window touches
    months = sorted({(now_utc.date().year, now_utc.date().month),
                      (end.date().year, end.date().month)})
    for y, mo in months:
        # NFP: first Friday of the month, 08:30 ET (BLS Employment Situation; reliable pattern)
        d0 = date(y, mo, 1)
        first_fri = d0 + timedelta(days=(4 - d0.weekday()) % 7)
        ts = _et_to_utc_iso(first_fri, 8, 30)
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if now_utc <= dt <= end:
            out.append({"ts": ts, "name": "Nonfarm Payrolls (approx.)", "impact": "high",
                        "source": "static_approx",
                        "note": "first-Friday heuristic; BLS occasionally shifts this +/-1 week"})
        # CPI / PPI: BLS does NOT publish on a fixed weekday-of-month; ~13th/~14th is a rough
        # historical median for CPI, with PPI typically the following day. Approximate only.
        for day, label in ((13, "CPI (approx.)"), (14, "PPI (approx.)")):
            try:
                d = date(y, mo, day)
            except ValueError:
                continue
            ts = _et_to_utc_iso(d, 8, 30)
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if now_utc <= dt <= end:
                out.append({"ts": ts, "name": label, "impact": "high", "source": "static_approx",
                            "note": "mid-month heuristic, NOT the real BLS schedule -- verify "
                                    "vs bls.gov/schedule before relying on this date"})
        # GDP advance estimate: quarter-end months only (Jan/Apr/Jul/Oct), ~last week
        if mo in (1, 4, 7, 10):
            d = date(y, mo, 28 if mo != 2 else 26)
            ts = _et_to_utc_iso(d, 8, 30)
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if now_utc <= dt <= end:
                out.append({"ts": ts, "name": "GDP advance estimate (approx.)", "impact": "high",
                            "source": "static_approx", "note": "last-week-of-month heuristic"})
    return out


async def macro_calendar_once(out_dir):
    """One-shot (not a poll loop): fetch, merge, de-dupe, write gha_data/macro_calendar.jsonl
    (overwritten every run -- it is a forward-looking snapshot, not an append log)."""
    loop = asyncio.get_running_loop()
    now_utc = datetime.now(timezone.utc)
    sess = requests.Session()

    kalshi_events = await loop.run_in_executor(None, _nearest_kalshi_macro_events, sess, now_utc)
    ff_events = await loop.run_in_executor(None, _forexfactory_us_high, now_utc)

    # supplement, don't duplicate: drop FF rows whose title obviously overlaps a Kalshi-derived
    # group we already have (CPI/PPI/GDP/employment/fed) so PPI (Kalshi has none) still gets through
    covered_kw = ["cpi", "gdp", "fomc", "fed", "nonfarm", "payroll", "unemployment"]
    have_group_names = {e["name"] for e in kalshi_events}
    ff_supp = []
    for e in ff_events:
        if e["name"] in have_group_names:
            continue
        nm = e["name"].lower()
        if "ppi" in nm or not any(k in nm for k in covered_kw):
            ff_supp.append(e)     # keep: either a PPI print, or not already covered by Kalshi

    events = kalshi_events + ff_supp
    if not any(e["source"] == "forexfactory" and "ppi" in e["name"].lower() for e in ff_supp):
        # neither live source produced a PPI print -> static heuristic fills the documented gap
        events += [e for e in _static_fallback(now_utc) if "PPI" in e["name"]]
    if not events:
        _log("macro", "both live sources empty/unreachable -> full static fallback")
        events = _static_fallback(now_utc)

    events.sort(key=lambda e: e["ts"])
    path = os.path.join(out_dir, "macro_calendar.jsonl")
    with open(path, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    _log("macro", f"done: {len(events)} events (next 7d) -> {path}")


# =============================================================================================
# LOOP 4 -- KALSHI HIRES (BTC): raw ws tape at native resolution (DECISION_MAP P1)
# =============================================================================================
# Same auth idiom as loop 2. Differences: subscribes orderbook_delta + trade + ticker (not just
# ticker), records EVERY message raw (no sampling -- the whole point is the sub-1.2s structure),
# and re-discovers the active market on the SAME connection (a fresh `subscribe` cmd on rollover)
# so window transitions don't cost a reconnect gap. Size guard: writing stops (loop keeps draining
# so reconnect churn stays low) past HIRES_MAX_BYTES of uncompressed output -- a stuck burst can
# then never flood the gha-data branch.

HIRES_ON = os.environ.get("SIDECAR_HIRES", "1") != "0"
HIRES_MAX_BYTES = 60_000_000          # ~60MB raw -> ~5-8MB gz per 42-min run, worst case
HIRES_ASSET = "btc"


async def kalshi_hires_loop(out_dir, stop_evt):
    if not HIRES_ON:
        _log("k_hires", "SIDECAR_HIRES=0 -> loop OFF")
        return
    if websockets is None:
        _log("k_hires", "websockets not installed -> loop OFF")
        return
    if not os.environ.get("KALSHI_API_KEY_ID"):
        _log("k_hires", "KALSHI_API_KEY_ID not set -> loop OFF (signed ws required)")
        return
    private_key = _load_kalshi_private_key()
    if private_key is None:
        _log("k_hires", "no usable KALSHI_PRIVATE_KEY_PATH -> loop OFF")
        return

    path = os.path.join(out_dir, f"hires_kalshi_{HIRES_ASSET}_r{RUNID}.jsonl.gz")
    fh = gzip.open(path, "at")
    sess = requests.Session()
    loop = asyncio.get_running_loop()
    n_written = bytes_written = 0
    sub_id = [1]
    backoff = 1.0

    def _discover_one():
        t = _discover_tickers(sess)
        return t.get(HIRES_ASSET)

    try:
        while not stop_evt.is_set():
            ticker = await loop.run_in_executor(None, _discover_one)
            if not ticker:
                _log("k_hires", "no open KXBTC15M market; retry in 10s")
                try:
                    await asyncio.wait_for(stop_evt.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                auth_hdrs = _kalshi_sign(private_key, "GET", "/trade-api/ws/v2")
                try:
                    connect_ctx = websockets.connect(
                        KALSHI_WS_URL, additional_headers=auth_hdrs,
                        ping_interval=10, ping_timeout=20, max_size=None)
                except TypeError:
                    connect_ctx = websockets.connect(
                        KALSHI_WS_URL, extra_headers=auth_hdrs,
                        ping_interval=10, ping_timeout=20, max_size=None)
                async with connect_ctx as ws:
                    subscribed = set()

                    async def _sub(mk):
                        sub_id[0] += 1
                        await ws.send(json.dumps({
                            "id": sub_id[0], "cmd": "subscribe",
                            "params": {"channels": ["orderbook_delta", "trade", "ticker"],
                                       "market_tickers": [mk]},
                        }))
                        subscribed.add(mk)
                        _log("k_hires", f"subscribed {mk}")

                    await _sub(ticker)
                    backoff = 1.0
                    next_discover = time.time() + 45
                    while not stop_evt.is_set():
                        if time.time() >= next_discover:
                            next_discover = time.time() + 45
                            nt = await loop.run_in_executor(None, _discover_one)
                            if nt and nt not in subscribed:
                                await _sub(nt)     # rollover: add next window, same connection
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        except asyncio.TimeoutError:
                            continue
                        tl_ms = time.time() * 1000.0
                        if bytes_written >= HIRES_MAX_BYTES:
                            continue               # size guard: drain, don't write
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue
                        mtype = msg.get("type")
                        if mtype not in ("orderbook_snapshot", "orderbook_delta",
                                          "trade", "ticker"):
                            continue               # skip subscribe acks/heartbeats
                        row = {"tl": round(tl_ms, 1), "t": mtype, "m": msg.get("msg")}
                        if msg.get("seq") is not None:
                            row["seq"] = msg["seq"]
                        line = json.dumps(row, separators=(",", ":")) + "\n"
                        fh.write(line)
                        n_written += 1
                        bytes_written += len(line)
                        if n_written % 500 == 0:
                            fh.flush()
            except Exception as e:
                if stop_evt.is_set():
                    break
                _log("k_hires", f"disconnected ({type(e).__name__}: {str(e)[:80]}); "
                                 f"reconnect in {backoff:.0f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
    finally:
        fh.close()
        _log("k_hires", f"done: {n_written} msgs ({bytes_written/1e6:.1f}MB raw"
                         f"{', SIZE-CAPPED' if bytes_written >= HIRES_MAX_BYTES else ''}) -> {path}")


# =============================================================================================
# LOOP 5 -- SPOT HIRES (BTC): native-resolution theo clock (DECISION_MAP P1)
# =============================================================================================

async def _bnb_hires_reader(fh, counters, stop_evt):
    url = "wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker/btcusdt@aggTrade"
    backoff = 1.0
    last_bt_ms = 0.0
    last_bt = (None, None)
    while not stop_evt.is_set():
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=20,
                                           close_timeout=2) as ws:
                _log("s_hires", "binance connected")
                backoff = 1.0
                while not stop_evt.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    except asyncio.TimeoutError:
                        continue
                    tl_ms = time.time() * 1000.0
                    if counters["bytes"] >= HIRES_MAX_BYTES:
                        continue
                    try:
                        env = json.loads(raw)
                        stream = env.get("stream", "")
                        d = env.get("data") or {}
                        if stream.endswith("bookTicker"):
                            bid, ask = d.get("b"), d.get("a")
                            # change-only + >=50ms apart: bookTicker repeats identical quotes at
                            # high frequency; the theo clock only needs actual moves
                            if (bid, ask) == last_bt or tl_ms - last_bt_ms < 50:
                                continue
                            last_bt, last_bt_ms = (bid, ask), tl_ms
                            row = {"tl": round(tl_ms, 1), "src": "bnb_bt", "b": bid, "a": ask}
                        elif stream.endswith("aggTrade"):
                            row = {"tl": round(tl_ms, 1), "src": "bnb_tr", "p": d.get("p"),
                                   "q": d.get("q"), "tv": d.get("T"), "mm": d.get("m")}
                        else:
                            continue
                        line = json.dumps(row, separators=(",", ":")) + "\n"
                        fh.write(line)
                        counters["n"] += 1
                        counters["bytes"] += len(line)
                        if counters["n"] % 1000 == 0:
                            fh.flush()
                    except Exception:
                        continue
        except Exception as e:
            if stop_evt.is_set():
                break
            _log("s_hires", f"binance disconnected ({type(e).__name__}: {str(e)[:80]}); "
                             f"reconnect in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


async def _cb_hires_reader(fh, counters, stop_evt):
    backoff = 1.0
    while not stop_evt.is_set():
        try:
            async with websockets.connect("wss://ws-feed.exchange.coinbase.com", ping_interval=15,
                                           ping_timeout=20, close_timeout=2) as ws:
                await ws.send(json.dumps({"type": "subscribe", "product_ids": ["BTC-USD"],
                                           "channels": ["matches"]}))
                _log("s_hires", "coinbase connected")
                backoff = 1.0
                while not stop_evt.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    except asyncio.TimeoutError:
                        continue
                    tl_ms = time.time() * 1000.0
                    if counters["bytes"] >= HIRES_MAX_BYTES:
                        continue
                    try:
                        msg = json.loads(raw)
                        if msg.get("type") not in ("match", "last_match"):
                            continue
                        row = {"tl": round(tl_ms, 1), "src": "cb_tr", "p": msg.get("price"),
                               "q": msg.get("size"), "tv": msg.get("time"),
                               "sd": msg.get("side")}
                        line = json.dumps(row, separators=(",", ":")) + "\n"
                        fh.write(line)
                        counters["n"] += 1
                        counters["bytes"] += len(line)
                        if counters["n"] % 1000 == 0:
                            fh.flush()
                    except Exception:
                        continue
        except Exception as e:
            if stop_evt.is_set():
                break
            _log("s_hires", f"coinbase disconnected ({type(e).__name__}: {str(e)[:80]}); "
                             f"reconnect in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


async def spot_hires_loop(out_dir, stop_evt):
    if not HIRES_ON:
        _log("s_hires", "SIDECAR_HIRES=0 -> loop OFF")
        return
    if websockets is None:
        _log("s_hires", "websockets not installed -> loop OFF")
        return
    path = os.path.join(out_dir, f"hires_spot_{HIRES_ASSET}_r{RUNID}.jsonl.gz")
    counters = {"n": 0, "bytes": 0}
    fh = gzip.open(path, "at")
    try:
        await asyncio.gather(
            _bnb_hires_reader(fh, counters, stop_evt),
            _cb_hires_reader(fh, counters, stop_evt),
        )
    finally:
        fh.close()
        _log("s_hires", f"done: {counters['n']} rows ({counters['bytes']/1e6:.1f}MB raw"
                         f"{', SIZE-CAPPED' if counters['bytes'] >= HIRES_MAX_BYTES else ''}) -> {path}")


# =============================================================================================
# entrypoint
# =============================================================================================

async def _amain(duration_s, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    stop_evt = asyncio.Event()
    running_loop = asyncio.get_running_loop()

    def _request_stop(*_a):
        if not stop_evt.is_set():
            _log("main", "shutdown signal received -> stopping loops")
            stop_evt.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            running_loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            pass   # not all platforms/threads support signal handlers; timeout still applies

    async def _deadline_watchdog():
        try:
            await asyncio.wait_for(stop_evt.wait(), timeout=duration_s)
        except asyncio.TimeoutError:
            _log("main", f"duration ({duration_s}s) elapsed -> stopping loops")
            stop_evt.set()

    _log("main", f"sidecar_feeds starting: duration={duration_s}s out_dir={out_dir} run_id={RUNID}")
    await asyncio.gather(
        _deadline_watchdog(),
        _run_loop_safe("spot", spot_composite_loop(out_dir, stop_evt)),
        _run_loop_safe("ws_latency", ws_latency_loop(out_dir, stop_evt)),
        _run_loop_safe("macro", macro_calendar_once(out_dir)),
        _run_loop_safe("k_hires", kalshi_hires_loop(out_dir, stop_evt)),
        _run_loop_safe("s_hires", spot_hires_loop(out_dir, stop_evt)),
    )
    _log("main", "all loops finished")


def main():
    duration_s = int(sys.argv[1]) if len(sys.argv) > 1 else 2520
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "gha_data"
    asyncio.run(_amain(duration_s, out_dir))


if __name__ == "__main__":
    main()
