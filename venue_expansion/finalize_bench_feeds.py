#!/usr/bin/env python3
"""
Merge the raw bench_feeds.py WS measurement output with the BRTI methodology
research, the Kalshi WS docs summary, and a bandwidth/VPS feasibility
assessment into the final venue_expansion/out/bench_feeds.json deliverable.

Idempotent: reads the three source JSON files, recomputes derived sections,
writes the combined file. Safe to re-run.
"""
import json
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "out")
WS_PATH = os.path.join(OUT_DIR, "bench_feeds.json")
BRTI_PATH = os.path.join(OUT_DIR, "brti_methodology.json")
KALSHI_PATH = os.path.join(OUT_DIR, "kalshi_ws_docs.json")


def load(p):
    with open(p) as f:
        return json.load(f)


def steady_state_bps(res):
    """Bandwidth estimate excluding the single largest message (the one-time
    initial full-book snapshot most L2/diff feeds send on connect). This is
    the number that matters for sustained multi-connection bandwidth
    planning; the snapshot cost is a one-time per-(re)connect burst, handled
    separately below."""
    if not res.get("reachable"):
        return None
    ms = res.get("message_size_bytes_clean")
    dur = res.get("duration_s_actual")
    if not ms or not dur:
        return None
    steady_total = ms["total_bytes_all_messages"] - ms["max"]
    return round(8 * steady_total / dur, 1)


def main():
    ws = load(WS_PATH)
    brti = load(BRTI_PATH)
    kalshi = load(KALSHI_PATH)

    # Idempotent: first run reads the raw bench_feeds.py output (top-level
    # "results" + "generated_at_utc" + "proxy_caveat" + "duration_s_per_probe").
    # Re-runs read the already-merged file, where the same data lives under
    # ws_cadence_measurements / generated_at_utc / proxy_caveat unchanged.
    if "results" in ws:
        results = ws["results"]
        generated_at_utc = ws["generated_at_utc"]
        proxy_caveat = ws["proxy_caveat"]
        duration_s_per_probe = ws["duration_s_per_probe"]
    else:
        results = ws["ws_cadence_measurements"]["results"]
        generated_at_utc = ws["generated_at_utc"]
        proxy_caveat = ws["proxy_caveat"]
        duration_s_per_probe = ws["ws_cadence_measurements"]["duration_s_per_probe_requested"]
        # strip derived annotations added by a previous run so recompute is clean
        for v in results.values():
            v.pop("est_steady_state_bps_excl_snapshot_burst", None)
            v.pop("one_time_snapshot_burst_bytes", None)

    # ---- per-feed steady-state bandwidth annotation ----
    for k, v in results.items():
        if v.get("reachable"):
            v["est_steady_state_bps_excl_snapshot_burst"] = steady_state_bps(v)
            ms = v.get("message_size_bytes_clean") or {}
            v["one_time_snapshot_burst_bytes"] = (
                ms.get("max") if ms.get("max", 0) > 5000 else 0
            )

    # ---- constituent coverage table ----
    active_constituents = brti["brti_constituent_exchanges_current"]["active"]
    measured_map = {
        "Coinbase": ["coinbase_trade", "coinbase_book"],
        "Kraken": ["kraken_trade", "kraken_book"],
        "Bitstamp": ["bitstamp_trade", "bitstamp_book"],
        "Gemini": ["gemini_combined_trade", "gemini_combined_book"],
    }
    coverage = []
    for c in active_constituents:
        name = c["name"]
        entry = {"constituent": name, "added": c["added"]}
        if name in measured_map:
            entry["measured_here"] = True
            entry["probe_keys"] = measured_map[name]
        elif name == "itBit":
            entry["measured_here"] = False
            entry["note"] = ("Rebranded/operated under Bakkt infrastructure; a quick "
                              "reachability probe against a guessed legacy endpoint "
                              "(api.itbit.com) failed on an EXPIRED TLS certificate "
                              "(SSLCertVerificationError, cert expired) -- itself a signal "
                              "this is not a maintained public integration path. No current "
                              "public WS market-data endpoint was located in this pass; "
                              "needs a direct Bakkt/itBit API docs lookup, not attempted here.")
        elif name == "Bullish Exchange":
            entry["measured_here"] = False
            entry["note"] = ("Guessed REST-style WS path against api.exchange.bullish.com "
                              "timed out (no response in 6s). Bullish does publish public "
                              "market-data docs; the correct WS path was not identified in "
                              "this pass -- needs a docs lookup, not attempted here.")
        elif name == "Crypto.com":
            entry["measured_here"] = False
            entry["note"] = ("wss://stream.crypto.com/exchange/v1/market IS reachable and "
                              "responded with an immediate heartbeat method call, confirming "
                              "connectivity -- but Crypto.com's public market feed requires an "
                              "explicit subscribe request/response call (unlike Coinbase/Kraken/"
                              "Bitstamp/Gemini which accept a fire-and-forget subscribe frame or "
                              "no message at all), which the quick reachability probe did not "
                              "perform. Confirmed reachable; NOT part of the mandated 30s cadence "
                              "measurement set (task specified Coinbase/Kraken/Bitstamp/Gemini).")
        elif name == "LMAX Digital":
            entry["measured_here"] = False
            entry["note"] = ("LMAX Digital is an institutional venue (FIX/binary protocols, "
                              "credentialed access); a guessed public WS URL 404'd. No free "
                              "public retail WebSocket market-data feed is known to exist for "
                              "LMAX Digital -- likely requires a paid/credentialed market-data "
                              "subscription. Treat as NOT reconstructible from a free feed.")
        else:
            entry["measured_here"] = False
            entry["note"] = "not probed in this pass"
        coverage.append(entry)

    # ---- bandwidth / VPS feasibility ----
    measured_book_bps = []
    for k in ["coinbase_book", "kraken_book", "bitstamp_book", "gemini_combined_book"]:
        v = results.get(k, {})
        b = v.get("est_steady_state_bps_excl_snapshot_burst")
        if b:
            measured_book_bps.append(b)
    median_book_bps = sorted(measured_book_bps)[len(measured_book_bps) // 2] if measured_book_bps else None

    # 4 measured constituents (Coinbase, Kraken, Bitstamp, Gemini) + 4 unmeasured
    # (itBit, Bullish, Crypto.com, LMAX) -- assume unmeasured venues cost about
    # the same as the *median measured* venue's book-channel bandwidth, since
    # no data exists for them; this is explicitly a proxy/guess, not a
    # measurement.
    n_measured = 4
    n_unmeasured_active = len(active_constituents) - n_measured  # itBit, Bullish, Crypto.com, LMAX Digital
    sum_measured_book_bps = sum(
        results[k]["est_steady_state_bps_excl_snapshot_burst"]
        for k in ["coinbase_book", "kraken_book", "bitstamp_book", "gemini_combined_book"]
        if results.get(k, {}).get("est_steady_state_bps_excl_snapshot_burst")
    )
    proxy_unmeasured_total_bps = (median_book_bps or 0) * n_unmeasured_active

    total_8_constituent_book_bps = sum_measured_book_bps + proxy_unmeasured_total_bps

    # Kalshi side: orderbook_delta for a handful of active KXBTC hourly
    # markets + cfbenchmarks_value (~1 msg/s, small JSON) is negligible next
    # to L2 book-diff feeds; no direct measurement (would require an API
    # key), so this is a rough JSON-message-count guess, clearly labeled.
    kalshi_est_bps_note = (
        "NOT measured (Kalshi WS requires an authenticated, signed connection -- "
        "no API key available in this environment). Rough guess only: "
        "orderbook_delta for a handful of concurrently-open KXBTC hourly markets "
        "plus cfbenchmarks_value at ~1 msg/s is small JSON (order of a few hundred "
        "bytes/msg at maybe 1-50 msgs/s during active trading) -- almost certainly "
        "under 50 kbps sustained, i.e. two orders of magnitude below the constituent "
        "order-book aggregate. Needs a real measurement once API credentials exist."
    )

    bandwidth_assessment = {
        "caveat": (
            "Steady-state numbers below are 'clean' in the sense that message SIZE is "
            "exact (proxy does not alter payload bytes) and duration is a monotonic "
            "wall-clock measurement (proxy adds a roughly-constant relay hop that does "
            "not distort a 30s span materially). They are NOT clean in the sense of "
            "representing a colocated VPS's raw socket bandwidth to each exchange -- "
            "TLS/WS framing overhead and TCP overhead are excluded (these are the JSON "
            "payload bytes as received by the Python websockets library, not wire bytes); "
            "add roughly 5-10% for TLS record + WS frame + TCP/IP header overhead on top "
            "of the payload-byte figures below for a wire-bandwidth estimate."
        ),
        "measured_book_channel_steady_state_bps": {
            k: results[k].get("est_steady_state_bps_excl_snapshot_burst")
            for k in ["coinbase_book", "kraken_book", "bitstamp_book", "gemini_combined_book"]
        },
        "measured_trade_channel_steady_state_bps": {
            k: results[k].get("est_steady_state_bps_excl_snapshot_burst")
            for k in ["coinbase_trade", "kraken_trade", "bitstamp_trade", "gemini_combined_trade"]
        },
        "median_measured_book_channel_bps": median_book_bps,
        "n_active_brti_constituents": len(active_constituents),
        "n_measured_here": n_measured,
        "n_unmeasured_proxy_estimated": n_unmeasured_active,
        "sum_measured_4_constituents_book_bps": round(sum_measured_book_bps, 1),
        "proxy_estimate_remaining_4_constituents_bps": round(proxy_unmeasured_total_bps, 1),
        "total_8_constituent_book_bandwidth_estimate_bps": round(total_8_constituent_book_bps, 1),
        "total_8_constituent_book_bandwidth_estimate_kbps": round(total_8_constituent_book_bps / 1000, 2),
        "kalshi_ws_bandwidth": kalshi_est_bps_note,
        "one_time_snapshot_reconnect_burst_bytes": {
            k: results[k].get("one_time_snapshot_burst_bytes")
            for k in ["coinbase_book", "gemini_combined_book"]
            if results.get(k, {}).get("one_time_snapshot_burst_bytes")
        },
        "vps_feasibility_verdict": (
            "YES, comfortably, on any bandwidth tier that would be considered for this "
            "at all. Full 8-constituent BRTI-replication order-book bandwidth estimates "
            "at roughly {:.0f} kbps steady state (measured 4 + proxy-estimated 4), plus "
            "Kalshi orderbook_delta/cfbenchmarks_value at an estimated <50 kbps -- call it "
            "under 500 kbps sustained even with generous overhead margin, i.e. well under "
            "1 Mbps. This is 2-3 "
            "orders of magnitude below a typical 1 Gbps VPS NIC and does not stress even a "
            "100 Mbps link. The real constraints for holding N constituent sockets + Kalshi "
            "WS simultaneously on one VPS are NOT bandwidth but: (1) per-connection CPU cost "
            "of JSON-parsing + order-book maintenance at the measured message RATES (Kraken "
            "book-10 hit 30 msgs/s and Gemini's combined feed hit 65 msgs/s in a 30s sample -- "
            "a full-depth Coinbase level2 feed or a busier trading period could be substantially "
            "higher), and (2) reconnect/backfill logic for each socket's large initial snapshot "
            "(coinbase_book and gemini both sent a >0.5MB one-time snapshot on connect -- see "
            "one_time_snapshot_reconnect_burst_bytes -- so a reconnect storm across 8 sockets "
            "could transiently spike to several MB, which is still trivial for any VPS NIC but "
            "worth not doing on every heartbeat miss). Single off-the-shelf VPS (e.g. a "
            "us-east-2-colocated instance near Kalshi's matching engine) is architecturally "
            "fine for this; no need to shard constituent connections across multiple hosts on "
            "bandwidth grounds."
        ).format(total_8_constituent_book_bps / 1000),
    }

    combined = {
        "component": "information_feeds",
        "generated_at_utc": generated_at_utc,
        "task": "Measure the maker's cancel-trigger information feed: BRTI methodology + "
                "constituent-exchange WS reachability/cadence + Kalshi's own WS market-data "
                "surface, and assess single-VPS feasibility for reconstructing a BRTI-relevant "
                "signal.",
        "proxy_caveat": proxy_caveat,
        "brti_methodology": brti,
        "brti_constituent_coverage": coverage,
        "kalshi_ws_docs": kalshi,
        "ws_cadence_measurements": {
            "duration_s_per_probe_requested": duration_s_per_probe,
            "results": results,
        },
        "bandwidth_and_vps_assessment": bandwidth_assessment,
        "architecture_recommendation": {
            "sockets_to_hold_open": [
                "Kalshi trade-api WS (wss://external-api-ws.kalshi.com/trade-api/ws/v2), "
                "authenticated: orderbook_delta for the specific KXBTC hourly market(s) "
                "currently open (adverse-selection / queue-position side), plus "
                "cfbenchmarks_value subscribed to index_ids=['BRTI'] as the authoritative "
                "settlement-relevant baseline (cancel-trigger side).",
                "Coinbase Exchange WS (wss://ws-feed.exchange.coinbase.com), level2_batch, "
                "BTC-USD -- measured reachable, ~486 msgs/30s incl. one large snapshot.",
                "Kraken WS (wss://ws.kraken.com), book-10, XBT/USD -- measured reachable, "
                "highest raw update rate of the 4 measured venues (~30 msgs/s).",
                "Bitstamp WS (wss://ws.bitstamp.net), diff_order_book_btcusd -- measured "
                "reachable, lowest rate of the 4 (~3 msgs/s).",
                "Gemini WS (wss://api.gemini.com/v1/marketdata/BTCUSD) -- measured reachable; "
                "NOTE this is a single combined trade+book-change socket, not two channels; "
                "highest measured raw cadence (~65 msgs/s book-relevant events).",
                "itBit, Bullish Exchange, Crypto.com, LMAX Digital -- the remaining 4 active "
                "BRTI constituents. Crypto.com confirmed reachable (needs a proper subscribe "
                "call, not attempted here). itBit's guessed endpoint has an EXPIRED TLS cert. "
                "Bullish's guessed endpoint timed out. LMAX Digital is institutional-only "
                "(no free public WS known). None of these four were cadence-measured -- see "
                "brti_constituent_coverage for per-venue notes and follow-up needed.",
            ],
            "brti_replication_approach": (
                "Two-tier design, not a single choice: (1) PRIMARY / low-effort / "
                "low-legal-risk: subscribe to Kalshi's own cfbenchmarks_value WS channel "
                "(index_ids=['BRTI']) -- it delivers the actual CF Benchmarks print at ~1Hz "
                "plus a trailing-60s average and, critically, the exact quarter-hour "
                "final-minute settlement-window average field, with presumably-cleared "
                "licensing since Kalshi is the redistributor. Use this as the authoritative "
                "cancel-trigger input and correctness baseline. (2) SECONDARY / leading "
                "indicator: reconstruct an approximate BRTI in-house from the 4-8 constituent "
                "order books using the exact published methodology (order-size-cap-then-"
                "uncross-then-cumulative-curves-then-exponential-weight-to-a-0.5%-utilized-"
                "depth, Methodology Guide v16.8 Section 4.1) to get a signal that leads the "
                "~1Hz Kalshi-redistributed print by however long the CF Benchmarks calc-engine "
                "hop takes (not measured here -- would need simultaneous capture of constituent "
                "book changes and the matching cfbenchmarks_value tick to bound this delta). "
                "The in-house reconstruction does NOT need to be bit-exact with BRTI to be "
                "useful as a cancel trigger -- a fast, roughly-correlated leading signal that "
                "gets cross-checked/corrected against the authoritative (1)-channel every ~1s "
                "is enough, and avoids betting the whole strategy on exactly replicating a "
                "documented-but-fiddly dynamic-order-size-cap/exponential-weighting formula."
            ),
            "licensing_accuracy_caveats": [
                "CF Benchmarks' Methodology Guide explicitly prohibits using 'the Information' "
                "(i.e. their published index values/methodology docs) to build derived indices, "
                "analytics, or software without a license -- this plausibly does NOT prohibit "
                "computing your own similar aggregate from PUBLIC constituent-exchange order "
                "book data (that data belongs to the exchanges, not CF Benchmarks), but it is a "
                "legal judgment call, not verified here; get counsel or a CF Benchmarks license "
                "before shipping this in production.",
                "Consuming BRTI via Kalshi's cfbenchmarks_value channel is almost certainly "
                "the licensing-safe path (Kalshi is the paying redistributor) but the terms of "
                "using that feed algorithmically (vs. just displaying it) were not checked here.",
                "Accuracy: an in-house reconstruction will NOT exactly match BRTI even with "
                "correct order-book snapshots, because (a) BRTI's dynamic order-size cap and "
                "exponential-weighting parameters (lambda = 10.3/v_T) require exact top-of-book "
                "sampling timed to CF Benchmarks' own ~200ms internal cadence, which a "
                "self-hosted poller cannot perfectly replicate without also matching their "
                "Retrieval Time semantics and contingency/outlier-exclusion rules; and (b) the "
                "methodology changed materially on 2026-06-29 (v16.8, added an order-book "
                "uncrossing step) and on 2026-05-18 (v16.6, changed Effective Time / Retrieval "
                "Lag Threshold) -- i.e. this is a living spec that has moved twice in the last "
                "~10 weeks as of this measurement, so any hand-rolled reconstruction needs a "
                "process for tracking CF Benchmarks methodology-guide version changes, not a "
                "one-time implementation.",
            ],
        },
        "summary_for_ev_study": (
            "Binance -- the info clock the parallel EV study uses -- is geo-blocked from this "
            "US-region egress at the WS layer (stream.binance.com returned HTTP 451 'restricted "
            "location'); a colocated us-east-2 VPS would likely hit the same block on the "
            "canonical endpoint, forcing use of a lower-guarantee mirror "
            "(data-stream.binance.vision, which is documented as market-data-only/no-trading and "
            "showed burstier inter-arrival behavior in this sample) or Binance.US (different, "
            "thinner order book) or a non-US proxy hop -- itself a latency cost. More fundamentally: "
            "Binance is not a BRTI constituent at all (confirmed against the current, 2026-06-08 "
            "official constituent list), so it was never going to be more than a directional proxy "
            "for the settlement-relevant price; Kalshi crypto markets settle to BRTI, computed from "
            "an 8-exchange order-book aggregate that does NOT include Binance. A production maker's "
            "cancel trigger should be built on the two-tier approach above (Kalshi's own "
            "cfbenchmarks_value channel + constituent order-book reconstruction), not a Binance trade "
            "tape, both for settlement accuracy and because Binance's own access from a US-based "
            "venue is not even guaranteed reachable at the WS layer."
        ),
    }

    with open(WS_PATH, "w") as f:
        json.dump(combined, f, indent=2, default=str)
    print("wrote merged", WS_PATH)


if __name__ == "__main__":
    main()
