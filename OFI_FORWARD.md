# EXO-OFI — exogenous order-flow → Kalshi 15m binary, PRE-REGISTERED forward experiment

**Registered 2026-07-15, before any signed-flow data exists (ungameable).** Operator-chosen domain:
"exogenous signal → Kalshi." This is the ONLY genuinely-untested part of that domain — the archive
already carries sampled spot + microprice, and the backtest proved observable **spot momentum is
already priced** by the Kalshi book (node EXO-MOM: the tradeable near-expiry momentum overlay is
NEGATIVE in-sample across every pre-registered config; residual momentum lead ~1c gross is sub-fee).
The untested question is whether **true signed order flow + book imbalance** from a major spot venue
(Coinbase) leads the 15m binary's terminal settlement by more than transaction costs. Prior is WEAK
(realized flow drives spot, and spot is priced) but non-zero (microstructure OFI can lead at
seconds-to-minutes). Forward-only: no historical signed-flow archive exists.

## Data (collector: `ofi_collect.py`, workflow `.github/workflows/ofi-collect.yml`)
Coinbase public REST, ~2s poll, self-chaining always-on (mirrors collect.yml). Per asset per poll:
`ts, mid, spread, buy_vol, sell_vol, ntrades, ofi(=buy_vol−sell_vol), cvd, book_imb(top-10), last_price`.
Written to `gha_data/<day>/ofi_coinbase_<asset>_r<run>.jsonl.gz`. Aggressor sign per Coinbase
convention (trade `side` = maker side → taker is the opposite).

## Frozen decision rule (implemented in `ofi_forward.py` — DO NOT retune)
Universe: btc/eth/sol. Decision instant per Kalshi 15m window = ws+720s (last ~3 min), matching the
tick archive that supplies the window list and the outcome.
- **Primary signal** `S = OFI_2m / scale` where `OFI_2m = Σ ofi` over Coinbase snapshots in
  `[ws+600, ws+720]`, and `scale` = trailing-30-window median of `Σ|ofi|` in the same sub-interval
  for that asset (scale-free, computed causally from prior windows only).
- **Threshold** `Z = 1.0` (FIXED, pre-registered, no grid). Trade only if `|S| ≥ Z`.
- **Direction:** `S>0` (net buying pressure) → BUY YES at the Kalshi ask; `S<0` → SELL YES at bid.
- **P&L:** `outcome − ask − fee` (buy) or `bid − outcome − fee` (sell), fee `= 0.07·p·(1−p)`.
- **Outcome label:** market's own terminal settlement (final tick mid > 0.5). No strike proxy, no
  outcome-dependent window dropping (both are known look-ahead traps in this repo).
- Secondary/report-only diagnostics (NOT the gate): book_imb at decision, OFI_1m, CVD slope. These
  are logged for understanding but the gate is the primary signal above.

## Gate (charter, do not relax)
- **PASS:** pooled per-(asset,day) day-clustered t ≥ 2 over ≥ 10 FORWARD days (days strictly after
  the first full collection day) **AND** BTC-alone mean > 0 (deepest book — no single-asset corner).
- **KILL:** pooled t < 0 after ≥ 10 forward days.
- Until then: CLOCK-NOT-STARTED / ACCRUING.
- PROPOSE-ONLY: no live sizing, flag, or switch touched without explicit operator authorization,
  and only after PASS.

## Honest prior / what would make this real vs. another artifact
EXO-MOM already showed the observable exogenous signal (spot) is priced. For EXO-OFI to be REAL and
not a repeat artifact it must clear the gate with a SINGLE pre-registered signal+threshold (above) —
no per-asset feature/threshold search (that search is exactly what made EXO-MOM's +2.41 evaporate).
BTC (deepest, most-informative flow) carrying the sign is the key non-corner check. If it clears,
the next step before any capital is a latency/impact audit (can we actually act at ws+720 before the
book reprices, at size, net of the ~2-4c spread we must cross).
