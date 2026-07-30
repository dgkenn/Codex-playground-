#!/usr/bin/env python3
"""
COMPONENT: INFORMATION FEEDS -- the maker's cancel trigger.

Measures WebSocket cadence for the free public feeds of CF Benchmarks BRTI
constituent exchanges (trade channel + order-book/diff channel where
available), plus a Binance comparison, from this container.

CRITICAL CAVEAT: all outbound HTTPS/WSS from this container goes through an
agent proxy (see $HTTPS_PROXY). Absolute one-way latencies are NOT measured
here (no server-side timestamp cross-check was attempted for most feeds, and
even where exchanges embed timestamps, the "when did *I* see the connect"
number is proxy-inclusive). What IS measured cleanly:
  - message cadence / inter-arrival intervals within a single held-open
    connection (the proxy is a mostly-fixed relay hop; it shifts absolute
    arrival time but roughly preserves inter-arrival spacing for a TCP/TLS
    stream that's already established)
  - message sizes (payload bytes as received) -- exact, proxy does not alter
    payload content
  - reachability (binary signal, not sensitive to proxy latency)
This script labels every number accordingly in the JSON output.

Run: python3 bench_feeds.py [--duration 30]
Output: out/bench_feeds.json (written incrementally, one exchange at a time,
so a container restart mid-run does not lose completed measurements).
"""

import asyncio
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

import websockets

OUT_PATH = os.path.join(os.path.dirname(__file__), "out", "bench_feeds.json")
DEFAULT_DURATION = 30.0
PROXY_CAVEAT = (
    "This container's outbound HTTPS/WSS is routed through an agent proxy. "
    "Absolute latency/arrival-time numbers are proxy-inclusive upper bounds "
    "and NOT representative of a colocated VPS. Cadence (inter-arrival "
    "intervals) and message sizes are clean/proxy-invariant measurements: "
    "the proxy is a persistent relay on an already-open TCP stream, so it "
    "shifts arrival time but does not materially distort spacing between "
    "consecutive messages, and it does not alter payload bytes."
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def measure_ws(name, url, subscribe_msg, duration, max_size=20 * 1024 * 1024,
                      connect_timeout=10, filter_fn=None):
    """Connect, optionally send a subscribe message, then collect messages for
    `duration` seconds. Returns a result dict. filter_fn(msg_dict)->bool can
    restrict which messages count toward cadence stats (e.g. Gemini mixes
    'trade' and 'change' events in one socket)."""
    result = {
        "name": name,
        "url": url,
        "reachable": False,
        "error": None,
        "measured_at_utc": now_iso(),
        "duration_s_requested": duration,
    }
    arrivals = []  # monotonic timestamps of qualifying messages
    sizes = []     # byte length of every raw message received (all messages,
                    # for bandwidth purposes) regardless of filter
    filtered_sizes = []
    n_total_msgs = 0
    t_start = None
    try:
        async with asyncio.timeout(connect_timeout):
            ws = await websockets.connect(url, max_size=max_size)
        result["reachable"] = True
        try:
            async with ws:
                if subscribe_msg is not None:
                    await ws.send(json.dumps(subscribe_msg))
                t_start = time.monotonic()
                t_end = t_start + duration
                while True:
                    remaining = t_end - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        async with asyncio.timeout(remaining + 1):
                            raw = await ws.recv()
                    except (asyncio.TimeoutError, TimeoutError):
                        break
                    t_recv = time.monotonic()
                    n_total_msgs += 1
                    nbytes = len(raw) if isinstance(raw, (bytes, bytearray)) else len(raw.encode("utf-8"))
                    sizes.append(nbytes)
                    keep = True
                    if filter_fn is not None:
                        try:
                            parsed = json.loads(raw)
                        except Exception:
                            parsed = None
                        keep = filter_fn(parsed)
                    if keep:
                        arrivals.append(t_recv)
                        filtered_sizes.append(nbytes)
        finally:
            pass
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        return result

    result["duration_s_actual"] = round(time.monotonic() - t_start, 3) if t_start is not None else None
    result["n_messages_total_raw"] = n_total_msgs
    result["n_messages_counted"] = len(arrivals)

    if len(arrivals) >= 2:
        inter = [round((b - a) * 1000, 4) for a, b in zip(arrivals[:-1], arrivals[1:])]
        inter_sorted = sorted(inter)

        def pct(p):
            if not inter_sorted:
                return None
            k = min(len(inter_sorted) - 1, max(0, int(round(p * (len(inter_sorted) - 1)))))
            return inter_sorted[k]

        span = arrivals[-1] - arrivals[0]
        result["cadence_clean_proxy_invariant"] = {
            "msgs_per_sec": round(len(arrivals) / span, 3) if span > 0 else None,
            "inter_arrival_ms_p50": pct(0.50),
            "inter_arrival_ms_p90": pct(0.90),
            "inter_arrival_ms_p99": pct(0.99),
            "inter_arrival_ms_min": inter_sorted[0] if inter_sorted else None,
            "inter_arrival_ms_max": inter_sorted[-1] if inter_sorted else None,
            "inter_arrival_ms_mean": round(statistics.mean(inter), 4) if inter else None,
        }
    else:
        result["cadence_clean_proxy_invariant"] = None

    if sizes:
        result["message_size_bytes_clean"] = {
            "n_all_messages": len(sizes),
            "mean": round(statistics.mean(sizes), 1),
            "median": statistics.median(sizes),
            "min": min(sizes),
            "max": max(sizes),
            "total_bytes_all_messages": sum(sizes),
        }
        result["est_bandwidth_bps_clean"] = round(
            8 * sum(sizes) / (time.monotonic() - t_start), 1
        ) if t_start is not None else None
    if filtered_sizes and filter_fn is not None:
        result["message_size_bytes_filtered_channel"] = {
            "n_filtered_messages": len(filtered_sizes),
            "mean": round(statistics.mean(filtered_sizes), 1),
            "total_bytes_filtered": sum(filtered_sizes),
        }
    return result


def incremental_write(state):
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, OUT_PATH)


# ----------------------------------------------------------------------------
# Filter functions for feeds that mix message types on one socket
# ----------------------------------------------------------------------------

def gemini_trade_filter(msg):
    if not msg or "events" not in msg:
        return False
    return any(e.get("type") == "trade" for e in msg.get("events", []))


def gemini_change_filter(msg):
    if not msg or "events" not in msg:
        return False
    return any(e.get("type") == "change" for e in msg.get("events", []))


async def main():
    duration = DEFAULT_DURATION
    if "--duration" in sys.argv:
        duration = float(sys.argv[sys.argv.index("--duration") + 1])

    state = {
        "component": "information_feeds",
        "generated_at_utc": now_iso(),
        "proxy_caveat": PROXY_CAVEAT,
        "duration_s_per_probe": duration,
        "results": {},
    }
    incremental_write(state)

    probes = [
        # (key, human name, url, subscribe_msg, filter_fn, max_size)
        ("coinbase_trade", "Coinbase Exchange - matches (trade) channel, BTC-USD",
         "wss://ws-feed.exchange.coinbase.com",
         {"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["matches"]},
         None, 1 << 20),
        ("coinbase_book", "Coinbase Exchange - level2_batch (L2 diff) channel, BTC-USD",
         "wss://ws-feed.exchange.coinbase.com",
         {"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["level2_batch"]},
         None, 20 << 20),
        ("kraken_trade", "Kraken - trade channel, XBT/USD",
         "wss://ws.kraken.com",
         {"event": "subscribe", "pair": ["XBT/USD"], "subscription": {"name": "trade"}},
         None, 1 << 20),
        ("kraken_book", "Kraken - book-10 (L2 diff, depth 10) channel, XBT/USD",
         "wss://ws.kraken.com",
         {"event": "subscribe", "pair": ["XBT/USD"], "subscription": {"name": "book", "depth": 10}},
         None, 1 << 20),
        ("bitstamp_trade", "Bitstamp - live_trades_btcusd channel",
         "wss://ws.bitstamp.net",
         {"event": "bts:subscribe", "data": {"channel": "live_trades_btcusd"}},
         None, 1 << 20),
        ("bitstamp_book", "Bitstamp - diff_order_book_btcusd channel",
         "wss://ws.bitstamp.net",
         {"event": "bts:subscribe", "data": {"channel": "diff_order_book_btcusd"}},
         None, 4 << 20),
        ("gemini_combined_trade", "Gemini - v1 marketdata/BTCUSD, trade events only (shared socket also carries book changes)",
         "wss://api.gemini.com/v1/marketdata/BTCUSD",
         None, gemini_trade_filter, 4 << 20),
        ("gemini_combined_book", "Gemini - v1 marketdata/BTCUSD, book change events only (same socket as trade)",
         "wss://api.gemini.com/v1/marketdata/BTCUSD",
         None, gemini_change_filter, 4 << 20),
        ("binance_trade_marketdata_vision", "Binance - btcusdt@trade via data-stream.binance.vision "
         "(main stream.binance.com WAS UNREACHABLE: HTTP 451 geo-restriction from this egress; see note)",
         "wss://data-stream.binance.vision/ws/btcusdt@trade",
         None, None, 1 << 20),
    ]

    # First: record the direct connectivity failure for the canonical Binance
    # endpoint, since it is itself a finding.
    canonical_binance = await measure_ws(
        "binance_trade_canonical_stream_binance_com",
        "wss://stream.binance.com:9443/ws/btcusdt@trade",
        None, min(duration, 8.0),
    )
    state["results"]["binance_trade_canonical_stream_binance_com"] = canonical_binance
    incremental_write(state)

    for key, name, url, sub, filt, max_size in probes:
        print(f"[{now_iso()}] probing {key} ...", file=sys.stderr)
        res = await measure_ws(name, url, sub, duration, max_size=max_size, filter_fn=filt)
        state["results"][key] = res
        incremental_write(state)
        print(f"[{now_iso()}] done {key}: reachable={res.get('reachable')} "
              f"n_counted={res.get('n_messages_counted')} error={res.get('error')}",
              file=sys.stderr)
        await asyncio.sleep(1.0)  # be polite between probes

    incremental_write(state)
    print("wrote", OUT_PATH, file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
