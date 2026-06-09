# Queue priority — getting filled FIRST (on the right side)

Polymarket's CLOB is **price-time priority**: a better price beats everyone; at the same price, earliest
order wins. So "filled first" = (a) post a better price when you can, (b) arrive first when you can't, and
(c) never give up the place you've earned. **Critical caveat:** you don't want *all* fills first — winning
queue races indiscriminately means winning the *toxic* ones (informed flow hits the stale side first), which
inverts the rebate edge. Every lever below is therefore gated to act **on the benign side only**.

Below: each of the 5 levers, the concrete things we built for it, and the flag. Defaults are conservative
(behavior-changing levers are opt-in); recommended pilot settings at the bottom.

---

## P1 — Price improvement (jump the whole queue when the spread allows)
A better price has priority over the entire queue at the touch. We only quoted at/behind the touch before.
1. **`--improve`** — when spread ≥ 2 ticks, post **one tick inside** the touch (`bb+tick` / `ba-tick`),
   instantly front-of-book by price priority. (`baseline_levels`.)
2. **Toxicity-gated** — the improved level is fed through the same `model_filter`, so we only improve on the
   side the microprice says is **benign** (improving the toxic side would just win adverse races).
3. **Still post-only** — the `would_cross` guard guarantees the improved order never crosses (no taker fee).
4. **No-op on 1-tick books** — nothing to step into, so it's free to leave on for liquid BTC and only acts
   on the 5m / ETH / SOL / XRP / quiet-moment books where the spread actually widens.

## P2 — Never surrender your place (preserve earned priority)
Every cancel/replace sends you to the **back** of the new queue. The fast 0.1s react loop made this riskier
(more chances to churn on flicker), so we hardened priority preservation.
1. **`--min-rest-s` (default 2s)** — never cancel a resting order for a NON-toxic reason (reshape/reprice)
   until it's rested this long; stops the react loop from churning away priority on transient book flicker.
2. **Toxic pulls stay exempt** — the adverse-selection defense (`model_pull`) is never debounced; only
   cosmetic reshape churn is.
3. **Front-of-book is sacred** (`--age-protect`) — an aged order is only pulled by a *severe* toxic move,
   never by reshaping. Aged + in-band rungs always HOLD.
4. **Lead-aware protect** (`--queue-jump`) — HOLD the side the book is moving toward (you'll be front when
   the touch arrives), shed the side it's leaving.

## P3 — Win the new-level race (be first when the touch moves)
When the book steps to a fresh price the level is empty — first to post wins. Pure latency.
1. **`--presign-depth N`** — pre-sign a deeper band (touch ± N ticks + the inside-touch improve level), so a
   touch move fires at the new level with **zero signing on the path**.
2. **WS book cache** (`book_feeder`) — detect the move in WS time, not on a REST poll (see LATENCY.md).
3. **Non-blocking cancel** (`timed_cancel`) — re-posting after a move isn't stuck behind a 0.5s confirm poll.
4. **`--presign` + `coincurve`** — the order is a pure POST with sub-ms signing; colo is gated by preflight.

## P4 — Go where the queue is SHORT (front-of-short beats back-of-deep)
1. **`--max-queue-ahead Q`** — skip posting at a level whose queue-ahead exceeds Q; don't bury yourself
   behind a huge stack — quote deeper where you're near the front.
2. **Layered rungs** (`--layers`, `--max-rungs`) — rest at several levels; get filled when the book steps to
   the deeper one where you're already front.
3. **Breadth** (`live_multi.py`) — less-contested ETH/SOL/XRP + 5m markets have shorter queues per level.
4. **q_ahead logged** at every placement (`order_log.jsonl`) so `pilot_reconcile.py` can show where fills
   actually came from and tune the cap.

## P5 — Operational (your side / monitoring)
1. **p95/p99 latency**, not mean — a single slow POST = back of the line. `clob_selfcheck` and `go_live.py`
   now report median + **p95 + p99** and gate on the tail (p99 < 40ms for a co-located GO).
2. **Continuous latency monitor** — `--lat-recheck-s` (default 300s) re-checks during the run and
   `notify.alert`s on a >2× regression (a Cloudflare re-route silently demotes you).
3. **Same-AZ / placement group** in eu-west-2 — one notch tighter than London-metro. Pick the candidate VPS
   with the smallest CLOB **p99** via `latency.py`. (Ops decision; can't be scripted.)
4. **30-day volume tier** — a higher tier raises API rate limits (more re-quotes/sec) and the rebate share;
   compounds once you scale. Track it toward the next breakpoint.

---

## Recommended pilot flags
Tighter-spread markets benefit most from `--improve`; keep `min-rest-s` to protect priority under the fast loop:
```bash
I_UNDERSTAND_REAL_MONEY=yes python live_trader.py --live --presign --presign-depth 2 \
  --improve --min-rest-s 2 --max-queue-ahead 300 \
  --max-notional 25 --loss-limit 5 --asset eth --tenor-min 5      # 5m/ETH = wider spreads to improve into
```
Then `python pilot_reconcile.py` — watch **fill rate** (P-levers should lift it) AND **markout** (it must NOT
get worse; if it does, the improvement is winning toxic races — back off `--improve` or tighten the gate).
Validate every lever in DRY-RUN first (all are exercised without `--live`).

## The honest tension
P1 and P3/P4 raise *fill rate*; the edge needs *benign* fill rate. The gates (toxicity overlay, min-rest,
lead-aware protect) exist to keep the extra fills on the right side. `pilot_reconcile.py`'s markout check is
the referee: more fills + same-or-better markout = real win; more fills + worse markout = back off.
