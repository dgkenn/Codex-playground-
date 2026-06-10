"""latency.py -- decompose REAL execution latency to the venues that gate sub-100ms trading.

Why this exists: the box-arb / latency-arb literature shows ~73% of the edge goes to sub-100ms bots,
and Polymarket's CLOB matching engine lives in AWS eu-west-2 (London). For OUR maker edge the same
clock decides queue priority (front-of-queue ~1c) and how fast we can pull a stale quote before toxic
flow lifts it. ICMP ping is a LIE here: Polymarket is behind Cloudflare, so ping hits a 1ms edge node
while a real order POST round-trips to London (~80ms from the US). This measures what actually matters:
the per-stage TTFB (DNS -> TCP -> TLS -> first byte) of a real HTTPS request, repeated, plus the WS
data path. Run it on every candidate VPS; the region that wins the order POST wins the edge.

    python latency.py [samples]            # default 20
"""
import socket, ssl, sys, time, statistics as st

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20

# (label, host, path)  -- the latency-critical hops. CLOB order POST is the one that gates execution;
# gamma = market discovery; coinbase = our BTC signal source (note the transatlantic tension, see below).
TARGETS = [
    ("CLOB  (order POST; eu-west-2/London)", "clob.polymarket.com", "/time"),
    ("Gamma (market discovery)",             "gamma-api.polymarket.com", "/markets?limit=1"),
    ("Data-API",                              "data-api.polymarket.com", "/"),
    ("Coinbase (BTC signal; US)",            "api.coinbase.com", "/v2/time"),
]
WS_TARGETS = [
    ("CLOB market WS", "ws-subscriptions-clob.polymarket.com", 443, "/ws/market"),
    ("Coinbase WS",    "ws-feed.exchange.coinbase.com",        443, "/"),
]


def stage_timings(host, path, ctx):
    """One real HTTPS GET, timed per stage. Returns dict of ms, or None on failure."""
    t = {}
    t0 = time.perf_counter()
    try:
        ai = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)[0]
    except Exception as e:
        return {"err": f"dns {e}"}
    t["dns"] = (time.perf_counter() - t0) * 1e3
    addr = ai[4]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    t1 = time.perf_counter()
    try:
        s.connect(addr)
    except Exception as e:
        s.close(); return {"err": f"tcp {e}", "dns": t["dns"]}
    t["tcp"] = (time.perf_counter() - t1) * 1e3
    t2 = time.perf_counter()
    try:
        ss = ctx.wrap_socket(s, server_hostname=host)
    except Exception as e:
        s.close(); return {"err": f"tls {e}", "dns": t["dns"], "tcp": t["tcp"]}
    t["tls"] = (time.perf_counter() - t2) * 1e3
    req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n"
           f"User-Agent: lat/1\r\nAccept: */*\r\n\r\n")
    t3 = time.perf_counter()
    try:
        ss.sendall(req.encode())
        first = ss.recv(1)                       # TTFB = first byte of the response
        t["ttfb"] = (time.perf_counter() - t3) * 1e3
        while ss.recv(65536):                    # drain to full response
            pass
        t["full"] = (time.perf_counter() - t3) * 1e3
    except Exception as e:
        t["err"] = f"http {e}"
    finally:
        try: ss.close()
        except Exception: pass
    t["total"] = (time.perf_counter() - t0) * 1e3
    return t


def p(label, key, samples):
    xs = [s[key] for s in samples if key in s and "err" not in s or (key in s)]
    xs = [s[key] for s in samples if key in s]
    if not xs:
        return f"{key:>5}: --"
    xs.sort()
    med = st.median(xs); mn = xs[0]; p95 = xs[min(len(xs) - 1, int(0.95 * len(xs)))]
    return f"{key:>5}: min {mn:6.1f}  med {med:6.1f}  p95 {p95:6.1f} ms"


def http_bench(ctx):
    print(f"== HTTPS per-stage TTFB ({N} samples each; ICMP ping is irrelevant -- this is the real path) ==")
    for label, host, path in TARGETS:
        samples = []
        for _ in range(N):
            r = stage_timings(host, path, ctx)
            samples.append(r)
            time.sleep(0.05)
        errs = [s.get("err") for s in samples if "err" in s]
        ok = [s for s in samples if "ttfb" in s]
        print(f"\n{label}  [{host}]")
        if not ok:
            print(f"  UNREACHABLE: {errs[:1]}"); continue
        for k in ("dns", "tcp", "tls", "ttfb", "full"):
            print(f"  {p(label, k, ok)}")
        warm = [s["full"] - s["dns"] - s["tcp"] - s["tls"] for s in ok]  # warm-conn proxy (reuse DNS+TCP+TLS)
        warm.sort()
        print(f"  warm-conn proxy (full - dns - tcp - tls) med: {st.median(warm):6.1f} ms  "
              f"<- what a kept-alive socket would see")
        if errs:
            print(f"  ({len(errs)}/{N} errors: {errs[0]})")


def ws_bench():
    try:
        import asyncio, websockets
    except Exception as e:
        print(f"\n(ws bench skipped: {e})"); return
    print(f"\n== WS connect + time-to-first-message ==")

    async def one(host, port, path):
        url = f"wss://{host}:{port}{path}"
        t0 = time.perf_counter()
        try:
            async with websockets.connect(url, open_timeout=10, ping_interval=None, max_size=None) as ws:
                conn = (time.perf_counter() - t0) * 1e3
                if "clob" in host:
                    await ws.send('{"assets_ids":[],"type":"market"}')
                t1 = time.perf_counter()
                try:
                    await asyncio.wait_for(ws.recv(), timeout=8)
                    msg = (time.perf_counter() - t1) * 1e3
                except Exception:
                    msg = float("nan")
                return conn, msg
        except Exception as e:
            return None, str(e)[:50]

    async def run():
        for label, host, port, path in WS_TARGETS:
            conn, msg = await one(host, port, path)
            if conn is None:
                print(f"  {label:16} UNREACHABLE: {msg}")
            else:
                mtxt = f"{msg:.1f} ms" if msg == msg else "no msg"
                print(f"  {label:16} connect {conn:6.1f} ms   first-msg {mtxt}")
    asyncio.run(run())


def main():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE   # timing only, not a security boundary
    http_bench(ctx)
    ws_bench()
    print("\nBUDGET: sub-100ms end-to-end = (signal in) + (compute+sign) + (order POST TTFB) + (match).")
    print("The order-POST TTFB to CLOB is the gate. If it's >~80ms you are cross-Atlantic from London")
    print("(eu-west-2) -- no amount of code fixes that; co-locate in eu-west-2/Dublin. A warm kept-alive")
    print("socket removes DNS+TCP+TLS (~1.5 RTTs) per order, so reuse connections and pre-sign orders.")


if __name__ == "__main__":
    main()
