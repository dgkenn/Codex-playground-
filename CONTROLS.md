# CONTROLS.md — the layered control stack against double-trading / inventory breaches

Born from the 2026-06-12 |net|=−2 incident: an orphaned supervisor loop + a fresh one ran TWO
traders on one account; each obeyed max-net=1 individually and breached it jointly. A secondary
cancel-fail race compounded it. These controls make recurrence require multiple simultaneous
failures, each independently alarmed.

## The layers (defense in depth — each works if every layer above it fails)

| Layer | Control | Scope | Action on violation |
|---|---|---|---|
| **L0** | `live_loop.sh` flock (`/tmp/.live_loop.lock`) | one supervisor per host | second loop exits at startup |
| **L1** | trader-process flock (`.kalshi_trader_<asset>15m.lock`) | one trader per host | second trader refuses to start (SystemExit) |
| **L2** | **foreign-order detector**: every ~30s the trader scans open orders on its ticker; any order_id ∉ its own `placed_oids` = another trader is live | **cross-host** (GHA vs local vs anything) | Telegram 🚨 + flatten + exit (fail-closed; operator re-arms exactly one) |
| **L3** | inventory clamp counts resting + **pending_cancel** (cancel-sent-but-unconfirmed orders stay counted until venue-confirmed gone or fill books) | within-trader race | placement blocked |
| **L4** | order TTL (150s venue-side expiration on every order) | orphaned orders after SIGKILL | orders self-cancel at the venue |
| **L5** | inventory-breach tripwire: any booked fill pushing \|net\| past max-net | catches anything the above missed | immediate ⚠️ Telegram |
| **L6** | sticky loss-limit + dead-man cancel-all + startup reconciliation | money backstops | halt / clean slate |

## Operational invariants (the human-side controls)
1. **Start the local trader ONLY via `./live_loop.sh`** (repo-versioned; carries L0). Never bare
   `python kalshi_trader.py --live` in a second shell — L1 will refuse anyway, but don't lean on it.
2. **Kill processes by PID, never `pkill -f` with a pattern** — the pattern matches your own shell's
   command line and kills the wrong thing (this is how the orphan survived on 2026-06-12).
3. **After ANY restart/cycle: run `./bot_status.sh`** — it asserts loops≤1, traders≤1, prints
   switch/sentinel state and recent settles. The single-instance invariant is checked, not assumed.
4. **Turning on the GHA cloud trader while a local loop runs is a double-trade** — L2 will halt one
   of them within ~30s (fail-closed), but the sanctioned procedure is: stop local (`./live_switch.sh
   off`, wait for session end) → enable GHA → confirm via Telegram 🟢 → never both.
5. A false-positive L2 halt is possible (a lost place-ack makes our own order look foreign — rare).
   The failure direction is SAFE (halt + alert); reconciliation at next start cleans up.

## What each past incident maps to
- Two loops / two traders (2026-06-12): now stopped by L0, L1; detected cross-host by L2; capped by L3/L5.
- Cancel-fail invisible order: L3 (pending_cancel registry).
- Container SIGKILL orphan orders (−$1.13 window): L4 (TTL) + L6 (reconciliation).
- Any novel cause pushing net past the cap: L5 alarms within one housekeeping cycle.
