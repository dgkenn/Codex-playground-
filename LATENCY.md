# Getting to sub-100ms on Polymarket — measured plan

**Why we care.** The box-arb research showed ~73% of latency-arb profit goes to **sub-100ms bots**, and
opportunities last ~2.7s. But sub-100ms matters for our *maker* edge too: it decides **queue priority**
(the front-of-queue ~1¢ component) and how fast we **pull a stale quote** before toxic flow lifts it
(adverse-selection avoidance). Same clock, both edges.

**The one-sentence answer:** sub-100ms is a **geography problem first, an engineering problem second** —
Polymarket's CLOB matching engine is in **AWS eu-west-2 (London)**, so you must run the bot in
eu-west-2 (co-lo) or Dublin/Amsterdam (<2ms away); then keep connections warm and pre-sign orders to
shave the rest. No amount of code fixes a transatlantic round trip.

## Measured baseline (this repo's `latency.py`, run from our current host)

```
CLOB (order POST; eu-west-2)   tcp 0.3ms   tls 2.8ms   TTFB 167ms   (warm-conn ~152ms)
Gamma (discovery)              tcp 0.2ms   tls 2.7ms   TTFB  74ms
Coinbase (BTC signal; US)      tcp 0.2ms   tls 2.7ms   TTFB 100ms   (warm-conn ~89ms)
```

**Read this carefully — it is the whole lesson.** TCP connect to CLOB is **0.3ms** (we sit next to a
Cloudflare edge PoP) yet a real request **TTFB is 167ms**. Ping/TCP measures the distance to the *edge*;
the order actually proxies through Cloudflare to the **London origin** and back (~152ms even on a warm
socket). **ICMP ping and `tcp` time are worthless for venue selection — only POST TTFB counts.** Run
`latency.py` on each candidate VPS and pick the one whose **CLOB TTFB** is smallest; from eu-west-2 /
Dublin that number drops from ~167ms to single-digit ms (Dublin↔London inter-region fiber is <2ms;
public reports cite ~0.8ms VPS→clob from Dublin).

## The latency budget

`end-to-end = (signal in) + (compute + sign) + (order POST TTFB) + (match/ack)`

| stage | from US (today) | from eu-west-2 co-lo | lever |
|---|---|---|---|
| signal in (BTC tick) | ~80ms if Coinbase-US | **~1–5ms** | use the in-region resolution feed, not US Coinbase |
| compute + EIP-712 sign | ~1–5ms | ~1–5ms | fast signer (coincurve), pre-built order template |
| **order POST TTFB** | **~150–167ms** | **~1–10ms** | **co-location (dominant lever)** |
| match + ack | operator-side | operator-side | nothing we control |
| **total** | **~230ms+** | **~5–20ms** | — |

Only the co-located column is in the sub-100ms cohort. From the US you cannot get there — the single
order POST already blows the budget.

## Levers, in priority order

1. **Co-locate in AWS eu-west-2 (London).** Single biggest win: CLOB POST TTFB ~150ms → low single
   digits. Polymarket offers direct co-location after a KYC/KYB form; otherwise Dublin (eu-west-1) or
   Amsterdam VPS are <2ms to London. *This alone moves us from ~230ms to ~sub-20ms.* Everything below is
   second-order until this is done.

2. **Fix the signal source — use the in-region *resolution* feed, not US Coinbase.** Our 15-min BTC
   market resolves on **Chainlink Data Streams** (Binance-sourced), surfaced by Polymarket's **RTDS**
   (`wss://ws-live-data.polymarket.com`, `btc/usd`). Reacting to **Coinbase (US)** is doubly wrong:
   (a) ~80ms transatlantic just to *learn* the price, and (b) **basis risk** — Coinbase ≠ the
   Binance/Chainlink number that actually settles the market. In eu-west-2, consume Chainlink Data
   Streams / Polymarket RTDS / Binance's AWS-proximate WS — same region as the CLOB *and* the literal
   settlement price. This both removes a transatlantic hop and tightens the signal to what we're betting
   on. **Engineering TODO:** add an `rtds_btc()` feed alongside the existing Coinbase WS and prefer it
   (the current `btc_ws_feed` Coinbase coroutine becomes the fallback, just as REST is the WS fallback).

3. **Keep connections warm (persistent HTTP/2 + WS).** A cold request pays DNS + TCP + TLS (~1.5 RTTs)
   on top of the origin RTT — our data shows ~16ms of that even at the edge, and far more cross-region.
   Hold one keep-alive HTTP/2 connection to `clob.polymarket.com` for the whole session and reuse it for
   every order/cancel; never let it idle-close. Same for the market WS and the user (fills) WS. (Our
   `requests.Session()` reuses sockets but `Connection: close` kills it — switch the order path to a
   pooled HTTP/2 client like `httpx` with keep-alive.)

4. **Pre-build and pre-sign order templates.** Orders are EIP-712 typed-data signatures. Construct the
   static fields once; at fire time fill in only price/size/salt/expiry and sign with a **C-backed
   signer (`coincurve`)** rather than pure-Python — sub-millisecond vs several ms. For known price
   levels (a tick ladder), you can even **pre-sign a small inventory of orders** and release the matching
   one instantly. Cancel-by-replace should reuse the warm socket.

5. **Keep the hot path OFF-chain.** CLOB order match/ack is off-chain (fast); Polygon settlement is
   async. So **never** put a Polygon tx (mint/split/merge, approvals) in the reaction loop — block time
   is ~2s, 20× the entire budget. For complete-set / box plays, **pre-mint inventory out-of-band** and
   only ever send CLOB orders in the hot path (this is why `live_trader.py --box-arb`'s split is a
   setup step, not a per-opportunity action — and another reason the on-chain box can't win the 2.7s race
   in-loop).

6. **Tighten the data path.** Subscribe to the CLOB market WS (`wss://ws-subscriptions-clob.polymarket.com/ws/market`)
   for book deltas instead of REST polling, and the **user WS** for fills (don't poll order status). Parse
   incrementally; avoid re-JSON-ing whole snapshots. Pin the event loop, disable Nagle (`TCP_NODELAY`) on
   the order socket.
   - **DONE (book path):** `live_trader.book_feeder` streams the token books off the market WS into an
     in-memory cache; the OMS reads it (`get_book` = WS→REST fallback) and re-decides every `--react-poll`
     (0.1s) instead of on the old 3s REST poll, so a quote-pull reacts in WS time. `TCP_NODELAY` is set via
     `netfast`. **DONE (cancel path):** `timed_cancel` is non-blocking (was `sleep(0.1)×5` = up to 0.5s of
     hot-path blocking per pull). **TODO:** the auth'd **user WS** for fills (still a 1s REST poll —
     acceptable for a hold-to-resolution maker, but the last piece for sub-ms fill handling).

7. **Measure continuously.** `latency.py` is the acceptance test: run it on the live VPS at deploy and
   periodically; alert if CLOB TTFB regresses (CF re-routing, region change). Track the **distribution**
   (p95, not mean) — tail latency is what loses queue races and gets you picked off.

## Acceptance criteria

- `latency.py` CLOB **POST TTFB p95 < 20ms** from the production host (proves eu-west-2/Dublin co-lo).
- BTC signal sourced **in-region** from the resolution feed (RTDS/Chainlink/Binance), Coinbase = fallback.
- One warm keep-alive HTTP/2 socket for all orders/cancels; `coincurve` signer; pre-built templates.
- Zero on-chain calls in the reaction loop (inventory pre-minted).
- End-to-end signal→ack p95 < 100ms (target ~20–40ms), verified by timestamped order logs.

## Honest boundary

Co-location and the actual eu-west-2 box are **ops decisions** that can't be exercised in this read-only
sandbox (CLOB TTFB here is ~130–167ms because we're transatlantic from London). What IS now wired in code:
the **in-region RTDS signal** (#2), **warm NODELAY keep-alive sockets** (#3, `netfast`), **pre-signed
orders + `coincurve` signer** (#4), **off-chain-only hot path** (#5), and the **WS book cache + fast
react loop + non-blocking cancel** (#6). `go_live.py` **gates** the co-location requirement (FAILs the
preflight unless CLOB round-trip is single-digit ms). The only remaining latency TODO is the auth'd user
WS for sub-ms fill handling (fills are a 1s REST poll today). Net: once you're on a colo box, both
**placement and reaction** are sub-10ms-capable; the dominant lever (geography) is enforced, not assumed.
