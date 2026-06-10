# Live-readiness audit — the line-by-line pass before real money (2026-06-10)

A full audit of the live path (`live_trader.py`, `live_multi.py`, `go_live.py`, `pilot_reconcile.py`,
`fvfeed.py`, `deploy/*`) against the REAL installed SDK (`py-clob-client-v2==1.0.1`, the official
Polymarket CLOBV2 client — every call surface verified by introspection, not assumption). The paper
edge re-validated on the freshest tape the same day (see bottom). **Every finding below is FIXED in
this commit**; the live-only unknowns (A1 rebate, A2 reflexivity) still gate via the $20 pilot.

## Critical fixes (each could lose money or strand orders)

1. **Cancels were silent no-ops.** `client.cancel(...)` doesn't exist in the v2 SDK; the
   `AttributeError` was swallowed, so every pull/kill/dead-man "succeeded" while orders stayed
   resting at the venue. → `cancel_orders([oid])` + failures logged loudly + a **venue-side scoped
   `cancel_market_orders` backstop** on every non-rollover cancel-all (global `cancel_all` when the
   market is unknown).
2. **`--loss-limit` could never fire** — `realized` was initialized and compared but never updated.
   → real per-window ledger (`pos`/`cash` from OUR fills), settled into `realized` at window
   resolution (pending-retry if the oracle is late), and the kill now reads **realized + the open
   window marked to mid**, so open losses count too.
3. **Fill ingestion used the taker's side as ours** → inventory skew doubled down on adverse flow and
   the markout kill fired on *profits*; trade-level size booked the taker's whole sweep as our fill.
   → parse `maker_orders[]` (our legs only, by session order-id), our side = opposite of the trade
   `side`, size = `matched_amount`; `trader_side=TAKER` now raises an immediate alert (A3 breach).
4. **`get_trades()` unscoped** ingested the wallet's entire history — and under `live_multi`, every
   sibling's fills (any non-Up asset counted as Down!). → `TradeParams(market=cid, after=session_t0)`
   + hard filter to this window's two tokens.
5. **Partial fills orphaned the live remainder** (`resting.pop` on any fill event). → per-order
   `filled` accrual; pop only when fully matched; remainder stays managed (pulls/reshape/cancel-all).
6. **Ambiguous POST → blind re-post = possible double-place** with only one copy tracked. → never
   re-post on an exception (the 0.1s react loop re-quotes anyway) + a 5s **venue open-order
   reconciliation** sweep cancels any order the venue has that we don't recognize.
7. **No startup reconciliation** — a SIGKILL'd run (OOM under systemd) left orders resting while the
   restart booted with empty books. → live startup does a venue `cancel_all` (fail-closed: refuses to
   start if it errors). `live_multi` does ONE parent-level cancel_all and tells children to skip
   theirs (shared API key).
8. **`--max-notional` capped one order, not exposure.** → aggregate check: open BUY notional +
   cash already converted to tokens must stay ≤ the cap.
9. **`--box-arb` live = untracked orders + an on-chain mint per second.** → refused with `--live`
   (research/dry-run only); the validated edge is the ladder.
10. **Kill-switches weren't sticky** — systemd `Restart=always` resurrected a tripped loss-limit 5s
    later with a fresh $0 ledger. → kill writes `.pmkit_killed_<asset><tenor>m`; live start refuses
    while it exists (operator deletes it after diagnosing).

## High-priority fixes

- **Venue post-only flag now set** on every order (`post_only=True`, GTC) — belt-and-suspenders the
  docs promised: closes the stale-book race `would_cross` can't (reject-and-requote ≫ one 3% cross).
- **Place acks validated** — `success=False`/`errorMsg`/missing id no longer stored as a live order.
- **SELL funding gate** — the venue rejects naked conditional-token sells; sells now only rest what
  session inventory funds. Until tokens accrue, the complement-token BUY ladder *is* the offer side
  (BUY Down @ 1-p ≡ SELL Up @ p in a binary book), so the book stays two-sided.
- **`fvfeed` was hard-wired to BTC** — ETH/SOL/XRP instances gated toxicity off BTC spot. → sources
  parametrized by asset; `--spot-symbol` defaults from `--asset`.
- **Up/Down token order now mapped by outcome name** (was: positional assumption — a silent flip of
  every direction-dependent decision if the ordering ever changed). Same for `outcomePrices`.
- **True 5s markouts** — live "markout_5s" was an instantaneous mid diff; now scored 5s after the
  fill, so `pilot_reconcile`'s live-vs-paper A2 comparison is apples-to-apples.
- **`live_multi` supervises** (restart w/ backoff + Telegram alert, cap 5; clean shutdown waits for
  each child's dead-man) and weights capital via **ladder depth** (`--max-rungs`: BTC 5 / ETH,SOL 2 /
  XRP 1) instead of sub-minimum clip sizes the venue would reject.
- **`deploy/setup.sh` installed the wrong SDK** (`py-clob-client` v1). → `py-clob-client-v2`.
- **Signature type configurable** (`SIGNATURE_TYPE` in `.env`, default `POLY_PROXY` = the email-login
  deposit-wallet path; was hardcoded `POLY_1271`, which fails signature validation for standard
  Polymarket accounts).

## Robustness

- REST `book()` best-levels by explicit max/min (was positional — exactly the fallback path used
  when the WS dies). Dead-man flatten fault-isolated per order. `.env.example` warns about systemd's
  EnvironmentFile inline-comment trap. `pilot_reconcile` counts UNKNOWN trader_side fills and refuses
  to be silently blind on maker integrity. Markout list memory-bounded. Pre-signed orders cleared at
  rollover (they reference the dead window's tokens).
- **Preflight (`go_live.py`) hardened**: verifies the SDK's exact call surface (a missing method now
  fails preflight, not mid-session), validates `SIGNATURE_TYPE`, bounds paper-edge recency (48h),
  checks the discovered market isn't closed, and adds a **clock-skew check** vs the CLOB (L2 auth +
  window rollover run off local time).

## Performance re-validation on the freshest tape (same day)

- `leaderboard.py` (169 windows): **`micro_ufat` #1 Calmar in-sample (78) and top-3 OOS (148)** —
  the deployed `--gate ufat` default stands.
- `gate_lab.py` re-fit on **58,918 fills / 149 windows** → refreshed `gate_model.json`; the
  calibrated ensemble's OOS net/fill **+0.136 vs micro +0.051** (benign-finding, not over-gating) —
  `micro_cal` is current again and re-fits once the live rebate is known (Insight 10).
- `combo_lab.py` re-run: `ufat+notmid` still best raw OOS net (+10.7 vs ufat +6.05) — but stays an
  A/B (`--mid-skip`), not the default, per the Calmar/drawdown verdict in `METRICS.md`.
- `benchmark.py`: paper + structural benchmarks PASS broadly (Calmar 70, PF 4.7, MC-bootstrap 100%
  positive, OOS/IS 0.97); the two PENDING-LIVE gates (colo latency, paper-live gap) are exactly what
  the pilot measures.

## What "100% ready" honestly means here

All code-level blockers found by the audit are fixed, the full preflight/dry-run path runs clean, and
the strategy choice is re-confirmed on current data. The two things no amount of code can confirm
remain **live-only**: the maker rebate actually paying (A1) and live adverse selection vs paper (A2).
The go-live sequence is unchanged and now trustworthy end-to-end:

```
./run.sh preflight   # on the co-located box -> must print VERDICT: GO
./run.sh dryrun 120  # plumbing on the box, places nothing
./run.sh pilot 7200  # $25 cap / $5 sticky loss-limit
./run.sh reconcile   # GO only on: fill-rate, 100% maker, markout parity, REAL rebate credit
```
