# ENGINEERING_STACK — verified latency stack for a Kalshi maker bot (2026-07-30)

Every number below went through: Sonnet measurement build → Sonnet independent re-run → Fable review
gate. Numbers are labeled **MEASURED** (reproduced ≤2× across runs), **DELTA-VALID** (absolute value
proxy-polluted but the difference is real), **CITED** (verified against a live source this week), or
**ASSUMED** (no measurement exists — listed as open validation items).
Artifacts: `bench_signing.py/.json`, `bench_transport.py/.json`, `bench_feeds.py/.json`,
`out/orderpath_research.json`, `out/bench_verify.json`.

**Bottom line: "HFT hedge-fund tier" is achievable — and turns out to be barely necessary.** The
MM1 viability curve is nearly flat from R=1s to R=300s, so the economics demand seconds, not
microseconds. The stack below delivers a **~1.4–2.7ms** compute+wire reaction floor (excluding
unmeasured engine-side ack), roughly **400× inside** the 1-second cell that already clears the
economic bar. Speed is not the moat; being *persistent, warm, and settlement-native* is.

---

## 1. Placement (CITED + verified IP mapping)

- Kalshi's matching engine: **AWS us-east-2 (Ohio)** — `trading-api.kalshi.com` → EC2
  3.137.133.121 / 3.138.233.55, mapped via the official `ip-ranges.amazonaws.com`.
- Deploy: one EC2/Lightsail box **in us-east-2**. Cited cross-AZ RTT: **1.0–2.0ms** (cloudping).
  Same-region placement replaces colocation entirely at this venue.
- Retail hostname `api.elections.kalshi.com` is CloudFront-fronted (anycast edge). The measured
  origin-vs-edge median delta was **noise (−0.9ms)** — the earlier "2.7× lower variance" claim was
  withdrawn by the verifier as not decision-grade. Choose hostname on auth/compat grounds; re-measure
  proxy-free from the VPS before caring.
- DNS: origin IPs showed zero churn (60s TTL). Pre-resolve and pin origin IPs; **never** pin the
  CloudFront hostname (its edge IP set demonstrably rotates).

## 2. Process architecture (MEASURED — the single biggest lever)

| pattern | per-request cost |
|---|---|
| subprocess-per-call (the old cron-leg pattern) | **255–354ms** |
| warm process, key in memory | **0.37–0.68ms** |

A ~500–650× tax. **The GHA cron architecture was itself the latency bottleneck all along.** One
long-lived asyncio process, RSA key held in memory, is the whole fix.

- Language: warm **Python is already within ~1.1× of the OpenSSL native floor** (its `cryptography`
  package wraps libcrypto). A Rust rewrite buys ~0.03ms — not worth it. Counter-intuitive and
  measured: the pure-Rust RustCrypto `rsa` crate is **3.4× slower** than Python's OpenSSL binding.
- Key: RSA-2048, not 3072 (3.6× cheaper signing; single-run number, directionally safe).
- JSON serialization: microseconds either way; not a decision point.

## 3. Transport (DELTA-VALID)

- **One persistent kept-alive HTTP/2 connection.** Reconnect penalty: **~500–655ms** — one cold
  reconnect at the wrong moment consumes most of a 1-second budget by itself. Keep-alive is a hard
  requirement, not an optimization. Maintain a warm standby connection for failover.
- H2 steady-state jitter measured ~3× tighter than H1.1 in this environment (proxy-inclusive;
  re-confirm from the VPS).
- All absolute REST latencies from this container are proxy-polluted (65–127ms steady-state) and are
  planning upper bounds only.

## 4. Information feeds (CITED + reachability-verified)

The settlement-relevant index for Kalshi crypto is **CF Benchmarks BRTI — and Binance is not even a
constituent** (verified against the official constituent list v13.5). The measured MM1 edge used
Binance only as a proxy clock; production should be settlement-native:

- **Tier 1 (authoritative trigger):** Kalshi's own authenticated `cfbenchmarks_value` WS channel,
  `index_ids=['BRTI']` — BRTI disseminates at ~1s standard / 200ms max cadence (CITED, methodology
  guide v16.8). **This leg has zero measurements** (WS auth = 401 without an API key) — first thing
  to validate live.
- **Tier 2 (leading indicator):** in-house approximate BRTI from constituent books. Verified
  reachable free WS: Coinbase, Kraken, Bitstamp, Gemini (+ Crypto.com endpoint confirmed up).
  Open: itBit (bad TLS on guessed endpoint), Bullish, LMAX (institutional, likely a permanent gap).
  Bandwidth is trivial (<1Mbps all-in); CPU for book maintenance is the real cost.
- BRTI methodology is a **living spec** — it changed twice in the 10 weeks before measurement.
  Reconstruction needs a version-tracking chore, not a one-time build.

## 5. Order path (CITED — 27/30 claims source-verified by the recheck)

- Rate limits are **token-based**; the tier ladder was verified exactly. Basic: 100 write tok/s.
  **Premier** (≥0.125% of prior-month exchange volume, sustained) is the milestone: 10× write
  ceiling + FIX access by default.
- **FIX shares the same token buckets as REST** — it buys protocol overhead, not throughput. Do not
  budget a FIX-derived rate increase.
- Reprice primitive: **amend** (cheapest single call). Kill switch: **batch-cancel at 2 tokens/order**
  (5× cheaper than create) + MassCancelRequest (1/sec throttle; whether it also consumes write
  tokens is UNVERIFIED — open item).
- Queue-position endpoint costs read tokens ~20·M/s for M markets — affordable ≤50 markets at Basic.
- MM/Liquidity programs: MM agreement requires ~98% quote uptime, confers **no API-tier benefit**
  (verified absence); LIP rewards $10–$1,000/day pools, excludes MM-agreement holders.
  `kalshi.com/regulatory/liquidity-provider-program` 429'd in both passes — unread by anyone; do not
  rely on claims sourced only there.

## 6. The reaction budget, honestly stratified

Target: spot-move → cancel-confirmed. Economic requirement (MM1): **≤1s keeps 98.6% of BTC volume
at +0.80c/ct** (front-of-queue optimistic bound; MM2 verification in flight).

| leg | value | status |
|---|---|---|
| BRTI dissemination cadence | 200ms max / ~1s std | CITED |
| Signal parse + decision + sign + serialize | 0.4–0.7ms | MEASURED |
| Wire, same-region | 1.0–2.0ms | CITED |
| **Engine processing + cancel ack** | **unknown, assumed <900ms** | **ASSUMED — the one leg the verdict cannot survive without; measure first from the VPS** |
| Compute+wire floor (excl. engine ack) | **~1.4–2.7ms** | MEASURED+CITED band |

Verifier's verdict: **QUALIFIED YES** on sub-second reaction from a same-region VPS. The two
failure modes that could eat the budget are both self-inflicted and both measured: a cold
subprocess (255–354ms) or a cold reconnect (500–655ms). The stack exists precisely to make those
impossible.

## 7. Queue-position plan (from the verified mechanics)

Price-time priority + observable `queue_position_fp` + hourly book resets:
1. **Listing-time quoting**: every KXBTC/KXETH hourly opens with an empty book at a known instant —
   scheduled presence = structural front-of-queue, 24×/day per asset (MM2's listing-window cut
   measures the EV of exactly this population).
2. **Queue-aware exposure**: poll queue position; cancel when buried (back-of-queue fills are
   disproportionately toxic).
3. **Decrease, never cancel-replace** to downsize (priority preservation implied by the dedicated
   endpoint; needs a two-order live test).
4. Order splitting for granular priority; churn discipline elsewhere.

## 8. Open validation items (first week on the VPS, before any order)

1. Proxy-free RTT + engine ack time (the ASSUMED leg) — REST round-trip on a test order at 1 contract.
2. Authenticated WS: does `cfbenchmarks_value` deliver BRTI at documented cadence?
3. Decrease-preserves-priority two-order test.
4. MassCancelRequest token accounting.
5. Origin vs CloudFront hostname, measured clean.

Cost of the whole stack: one small us-east-2 VPS (~$5–20/mo) + an IBKR-free ordinary Kalshi account.
No colocation, no FIX, no Rust, no paid feeds required at canary scale.
