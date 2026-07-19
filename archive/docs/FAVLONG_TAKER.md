# favlong_taker.py — PAPER-mode near-expiry contrarian taker (FAVLONG)

Paper-only execution module for node **FAVLONG**, the first validated positive edge of the
research program. It wraps the decision math from `favlongshot_edge.py` (the source of truth) in a
clean book-feed interface, a paper fill/settlement simulator, and telemetry consistent with the
live Kalshi bot.

## What the edge is

On Kalshi 15-minute crypto binaries (btc/eth/sol "up/above-strike"), the book is over-confident in
the last ~2–3 minutes of the 900s window (favorite-longshot bias / terminal overconfidence). At
`decision_t=720s` we compute a fair-value probability of settling above strike from spot-vs-strike,
scaled by **causal** realized vol and shrinking time-to-expiry. If the executable price underprices
that fair value by more than `edge=0.05`, we **take** that side:

- `fair − ask > edge` → **buy** the up-contract at the ask
- `bid − fair > edge` → **sell** the up-contract at the bid

Per-contract P&L settles against the market's own terminal price (`mid_close > 0.5`), with the
Kalshi per-contract fee `0.07·p·(1−p)` applied.

## Safety guardrails (read first)

- **PROPOSE-ONLY / PAPER-MODE.** The module cannot place real orders. There is no live order path.
- `--mode paper` is the default and the only functional mode. It simulates fills at the recorded
  executable price and books realized P&L on paper.
- **`--mode live` HARD-REFUSES** (raises `SystemExit` before doing anything). Live sizing requires
  **both**:
  1. the **FORWARD GATE** to have passed — pooled, day-clustered `t ≥ 2` over **≥ 10 forward days**
     (favorite-longshot is a known effect that can decay, so in-sample edge is not sufficient); and
  2. **explicit operator authorization**.
- The module does **not** touch `live.yml`, `LIVE_SWITCH`, or any live sizing/quoting/switch flag.
- Orders are capped by displayed depth **and** the `max_contracts` parameter (default 50).

## Usage

```bash
export FAVLONG_CACHE=/tmp/favlong_cache          # cached historical windows

python3 favlong_taker.py                          # BTC self-test, first 6 cached days
python3 favlong_taker.py --asset btc --days 999   # all cached days
python3 favlong_taker.py --asset eth --days 999   # eth / sol also supported
python3 favlong_taker.py --lag 5                  # fill 5 ticks later (latency stress test)
python3 favlong_taker.py --no-clean-label         # keep proxy-vs-market disagreements
python3 favlong_taker.py --mode live              # HARD-REFUSES (guardrail demo)
```

### Programmatic (wiring a live book feed later)

```python
from favlong_taker import PaperTaker

taker = PaperTaker(asset="btc", max_contracts=50)          # mode defaults to paper
# snapshots: iterable of (t_in_win, mid, spot, bid, ask, bidq, askq) for one window
rec = taker.trade_window(snapshots, strike=open_spot, ws=window_start_epoch)
#   rec is None if no edge; otherwise a settlement record (side/price/size/fee/outcome/pnl)
taker.close()
```

Each traded window appends one JSONL line to `favlong_paper_<asset>15m.jsonl` — a flat record with
a `ctx` block (spot, strike, bid/ask/mid, sig, tau, fair, ev, depth), matching the live bot's
fee-ledger telemetry style.

## Self-test result (reproduces favlongshot_edge.py)

Scored the cached BTC windows the same way `favlongshot_edge.py` does (clean-label filter on,
per-contract, +Kalshi fee):

| source                 | trades | winrate | mean $/ct | d-clust t |
|------------------------|-------:|--------:|----------:|----------:|
| `favlongshot_edge.py`  |  1413  |  0.210  | +0.0260   |   3.25    |
| `favlong_taker.py`     |  1401  |  0.210  | +0.0256   |   3.21    |

The ~12-trade difference is the paper module's `depth ≥ 1` sizing gate (a paper fill needs real
displayed depth; the reference sizes nothing). Per-contract edge is essentially identical and
clears the ~2–4c/ct BTC sanity bar. eth/sol are also positive (+1.6c, +1.8c/ct), consistent with
the cross-asset replication that is the evidence FAVLONG is a real favorite-longshot bias.

## Honest caveats (from favlongshot_edge.py)

- Small edge: ~2c/ct net pooled, ~4c/ct BTC alone. Real but modest; ~62% of asset-days positive →
  real variance, needs sizing/risk management, not all-in.
- Only BTC clears `t ≥ 2` OOS; confidence comes from pooling the shared mechanism across assets.
- Concentrated in the last 2–3 min (`t ≥ 600s`); at `t ≤ 450s` the edge is ~0.
- Taker strategy (crosses the spread) — new execution vs the live maker box bot. **Forward-gate
  before any live sizing.**
