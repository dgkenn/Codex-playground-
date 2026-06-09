# Paper → Live: the gap map (and what we do about each)

Our edge is a thin per-fill rebate net of adverse selection, so **any single gap below can flip it
negative.** This is the living checklist that gates `DEPLOY.md`. Each item: the paper assumption, the live
reality, why it matters to *our* edge, the world-class fix, and status.

Legend: ✅ done · 🔄 measured/in-progress · ⏳ pilot confirms · 📋 planned

---

## A. EDGE-KILLERS (binary — get one wrong and there's no edge)

### A1. The rebate is the entire edge — paper only *assumes* it. ⏳
- **Paper:** `REBATE=0.07`, credits ~20% of generated taker fee per matched share. Gross markout ≈ 0/slightly
  negative; net is positive *only* via this credit.
- **Live unknown:** Does the maker rebate pay on 15m crypto? At what %? Tiered by 30-day volume (a $20 account
  = lowest tier)? When/where does it credit?
- **Fix:** Treat the rebate as a measured input. `pilot_reconcile.py` reports the *predicted* credit per fill;
  the operator confirms the *actual* credit hit the burner wallet. Model the **worst-case tier** — if positive
  there, the rest is upside. Pull the live fee per market rather than hardcoding (see B3).
- **Status:** the pilot's #1 job. Until an actual credit is observed, the edge is unconfirmed.

### A2. Reflexivity / observer effect — live, the book reacts to us. 🔄✅(partial)
- **Paper:** we're invisible; the tape is fixed; the microprice signal is clean.
- **Live:** our resting size is *in* the book, so it biases the **microprice — the exact signal `micro_gate`
  uses.** And informed flow picks off resting quotes harder than the passive tape implies.
- **Fix:** (a) ✅ compute the microprice **excluding our own resting size at the touch** (`live_trader.py`,
  `own_b`/`own_a` subtraction). (b) keep clips tiny (small footprint). (c) ⏳ calibrate the gate threshold on
  *live* realized markout — start conservative, loosen only as live confirms. (d) 📋 randomize quote
  price/size/timing so we're not a fade-able target.
- **Status:** own-order-excluded microprice shipped; live markout vs paper is check [3] in `pilot_reconcile.py`.

### A3. Accidental taker fees flip the sign instantly. ✅
- **Paper:** we're always maker (fee 0, rebate +).
- **Live:** a marketable limit / crossed quote during a fast move pays the **taker fee (~3% peak at p=0.5)** —
  one cross erases dozens of clean windows.
- **Fix:** ✅ `would_cross()` guard in `live_trader.place()` refuses any order that would be marketable
  (BUY ≥ best ask, SELL ≤ best bid) — a post-only guarantee independent of any SDK flag. On the box, ALSO set
  the venue post-only order option if the SDK exposes one (belt-and-suspenders). `pilot_reconcile.py` check [2]
  alarms on any TAKER fill.
- **Status:** guard shipped + routed through ladder and box-arb placements.

### A4. Fill rate / queue position — paper *models* it; live *is* it. 🔄⏳
- **Paper:** models queue position (size-ahead, consumption).
- **Live:** true FIFO position is set by latency and is unobservable; too far back → you only fill when the
  level is about to be wrong (you get the toxic fills, miss the benign — pure adverse selection).
- **Fix:** ✅ latency (sub-50ms achieved; sub-10ms path: eu-west-2 placement group + busy-poll + pinned core),
  ✅ `--presign` (signing off the hot path), 🔄 reconstruct queue from `price_change` deltas, ⏳ measure live
  fill rate (`pilot_reconcile.py` check [1]; >50% = winnable, <30% = fix latency).

---

## B. EDGE-ERODERS (shave the thin margin)

- **B1. Reaction-path latency.** ✅ the maker loop now reads a **WS book cache** (`book_feeder`/`get_book`)
  and re-decides every `--react-poll` (0.1s) instead of the old 3s REST poll; `timed_cancel` is non-blocking
  (was up to 0.5s hot-path blocking per pull); predictive pulls (`micro_react`/`spot_react`) pull *before*
  the reprice. TODO: auth'd user WS for sub-ms *fills* (1s REST poll today).
- **B2. Tick/lot quantization.** ✅ clip floor above the venue minimum (~$1–2, not literal pennies — see the
  "can we test with pennies" analysis); model PnL on the real tick grid.
- **B3. Dynamic/per-market fees.** 📋 read live fee per market from the CLOB API (`getClobMarketInfo`); the fee
  sizes the rebate, so this feeds A1. (`fees.py` has the per-category table; wire the live read.)
- **B4. Competition for the rebate pool.** 🔄 rebate is a *share* of the pool — breadth into less-contested
  markets/tenors (multi-asset collector live); win on latency where contested.
- **B5. Shared capital across markets.** 📋 paper gives each variant its own infinite book; live, one bankroll
  funds BTC/ETH/SOL/XRP at once and inventory ties up capital. Build a portfolio capital allocator with
  cross-market inventory netting (not N independent books).
- **B6. Microprice staleness.** ✅ compute on the freshest snapshot; predictive gates compensate for lag.

---

## C. TAIL RISKS (rare, but one event erases many windows of pennies)

### C1. Disconnect/crash with open orders + inventory = naked risk. ✅
- **Paper:** zero risk on a crash. **Live:** a WS gap = quoting blind / holding unhedged inventory through a move.
- **Fix:** ✅ `live_trader.py` dead-man switch: (a) `atexit` + SIGTERM/SIGINT handlers cancel-all on *any* exit
  (systemd stop, kill, crash) — not just clean ones; (b) **staleness watchdog** (`--deadman-s`, default 15s):
  if the book feed goes dark while we hold orders, cancel-all until it recovers; (c) **error-storm** trip after
  5 consecutive loop errors. 📋 on the box, enable exchange-side cancel-on-disconnect if the venue offers it.
- **Status:** shipped.

- **C2. Forced-flatten cost.** 🔄 paper assumes hold-to-resolution; a risk breach forces a *taker* flatten
  (spread + fee). Fix: size so we're never *forced* to flatten; tiny delta-neutral inventory; model the
  emergency-flatten cost as a tail. (`--loss-limit` + markout kill exist; keep inventory tiny.)
- **C3. Settlement/redemption reality.** 🔄 paper: sets→$1, instant, free. Live: on-chain redeem
  (relayer/gas/timing), capital locked until resolution, oracle delay/dispute. Fix: verify redeem end-to-end
  once (`collateral.MintMerge`); model capital lockup in sizing; monitor the oracle.
- **C4. Exchange mechanics / API errors.** 🔄 rejects, rate limits, nonce/approvals, order-state ambiguity.
  Fix: handle every error code, backoff, an order-state reconciliation loop (query, don't assume). Dead-man
  (C1) covers the worst case.
- **C5. Liquidity/regime gaps.** 📋 don't quote a book below a depth/spread threshold; volatility regime filter.

---

## D. MEASUREMENT & PROCESS

- **D1. PnL truth.** ✅ `pilot_reconcile.py` reconciles live fills/rebate/markout vs paper as a t-stat → go/no-go
  is a number, not an eyeballed balance. (Live net confidence is **scale-invariant** — more *windows* confirm,
  not bigger clips.)
- **D2. Overfitting to a regime.** ✅ IS/OOS split in `leaderboard.py`; freeze params, re-tune only on fresh OOS
  clearing t>2.58.
- **D3. Clock sync.** 📋 NTP-synced box; use exchange timestamps for `tau`.

---

## The honest hierarchy

**A1 (is the rebate real?) and A2 (reflexive adverse selection) decide this** — the only two things shadow
fundamentally cannot measure, and either can independently kill the edge. A3 + C1–C2 are "don't blow up"
hygiene (now engineered). Everything in B is a few percent each. **The $20 pilot exists to resolve A1 and get
the first read on A2/A4** — run it, then `python pilot_reconcile.py` for the verdict.

## Pilot gate (run order)
1. `python strategies.py` (roster valid) · paper edge holds (`leaderboard.py`, IS+OOS).
2. DRY-RUN on the live box: `python live_trader.py --presign --duration 120` (places nothing; check
   `clob_selfcheck` colo verdict + post-only guard logs + dead-man arms).
3. Tiny live: `I_UNDERSTAND_REAL_MONEY=yes python live_trader.py --live --presign --max-notional 25 --loss-limit 5`.
4. `python pilot_reconcile.py` → GO only if: fill rate >50%, 100% maker, live markout not worse than paper,
   and **actual rebate credit confirmed**.
