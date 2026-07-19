# FAVLONG on other Kalshi tenors/markets — data inventory, test, verdict

**Node:** FAVLONG-TENOR (2026-07-15). Offline research; PROPOSE-ONLY. No orders, no live-config edits.
**Question:** the FAVLONG edge (near-expiry TAKER exploiting the book price *lagging* settlement-implied
fair value in WIDE/dislocated books) is validated on Kalshi 15m crypto (btc/eth/sol; xrp null) and was
NULL on Polymarket (tight/deep books). Does the SAME mechanism work on OTHER Kalshi tenors whose
near-expiry books are wider/less liquid — especially HOURLY crypto?

---

## 1. DATA INVENTORY

### What is STORED in `origin/gha-data`
| Product | Files | Resolution | Fields | Span |
|---|---|---|---|---|
| **15m crypto** btc/eth/sol/xrp | `ticks_/trades_/book_/fills_/shadow_windows_kalshi_{asset}15m` | **sub-second ticks** | ticks = `(t, mid, spot, micro, bid, bidq, ask, askq)` per window | 2026-06-10 .. 07-15 (~35 days) |
| **15m BTC full-depth "hires"** | `hires_kalshi_btc_r*` | sub-second L2 snapshots+deltas | full yes/no price ladder | **only 2026-07-13..15 (3 days), 1 strike offset** |
| **Kalshi perps** | (collector `kalshi_perp_collect.py` added TODAY) | — | — | **NO DATA YET** (0 rows) |

**The "hires" files are still 15m crypto** (ticker `KXBTC15M-…`), NOT a new tenor — just richer L2 for
the same 15m book. **There is NO stored non-15m Kalshi price/settlement time-series of any kind.**

### The two bot-branch scripts (learned from `origin/claude/polymarket-bot-live-ready-vw7ut5`)
- **`kalshi_hourly_box_backtest.py`** — backtests a *maker box* on **KXBTCD (hourly BTC above/below)** by
  hitting the **LIVE** public API (`api.elections.kalshi.com`) for the settled trade tape. It confirms
  hourly crypto binaries exist and are reachable, but **stores nothing** and collects no bid/ask path.
- **`kalshi_econ.py`** — a 15m-crypto maker-viability study; reads `hist_kalshi_*.parquet` per-minute
  candles from a `fetch_kalshi.py` that is **not in the data branch**. Also 15m, not a new tenor.

### What is cheaply REACHABLE live (public API, read-only, no auth — same surface those scripts use)
Kalshi lists **254 crypto series**. The direct hourly analogs of the 15m up/down markets are the hourly
**directional** ladders: **KXBTCD, KXETHD, KXSOLD, KXXRPD, KXBNBD, KXDOGED, KXNEARD, KXTOND, KXZECD, KXHYPED**
(plus hourly *range* KXBTC/KXETH/KXSOL and many daily/weekly/monthly one-touch/range binaries).

Critically, the API exposes **historical minute candlesticks with `yes_bid`/`yes_ask`/`price` OHLC**
(`/series/{s}/markets/{tk}/candlesticks`) plus **realized settlement** (`result`, `expiration_value`,
`floor_strike`) on `/markets`. So an hourly test IS reconstructable live — but only over the **rolling
settled window the API serves**: KXBTCD ≈ 54 events (~2.2 days), KXETHD/KXXRPD ≈ 136 events each (~5–6
days). BTC spot path for fair value pulled from `data-api.binance.vision` 1m klines (works for 2026-07).

---

## 2. TEST — hourly crypto directional (KXBTCD / KXETHD / KXXRPD)

I reconstructed a labeled FAVLONG test entirely from the live API + Binance spot, mirroring
`favlongshot_edge.py` mechanics exactly:
- **fair value** `NORM(z)`, `z=(spot−strike)/(spot·σ·√τ)`, σ = causal per-√s realized vol of spot up to
  decision, τ = seconds to close. Strike = ladder floor closest to decision-time spot.
- **executable price** = the ATM strike's 1-min-candle **close `yes_bid`/`yes_ask`** at decision.
- **label** = realized `result` (yes→1). **+Kalshi fee** `0.07·p(1−p)`. **Day-clustered t** by (asset,day).
- decision time tested at close−300s (last 5 min) and close−180s (last 2–3 min, the mechanism's timescale).

### Dislocation stats (the gating question: wide like 15m-crypto, or tight like Polymarket?)
| Book | near-expiry ATM spread | % near-expiry min > 1c | verdict |
|---|---|---|---|
| **15m crypto (STORED sub-second, where FAVLONG works)** | p50 **1.0c**, p90 **1.2c**, mean 0.87c | **11%** | mostly tight; edge lives in the wide **tail** |
| **Hourly KXBTCD (1-min candle close)** | p50 **1.0c**, p90 **2.0c**, mean 1.35c | **29%** | **wider tail than 15m** |
| **Hourly traded universe (BTC+ETH+XRP, at decision)** | p50 **1.0c**, p90 **3.0c**, mean 1.6–1.8c | — | wide tail present |
| Polymarket btc up/down (prior work) | penny-tight / deep | ~0% | tight → null |

**→ The FAVLONG precondition (wide/dislocated near-expiry books) IS plausibly satisfied on hourly crypto.
Hourly is NOT Polymarket-tight** — if anything it shows a fatter wide-spread tail than 15m at the candle level.

### FAVLONG scoring (realized-settlement, executable, day-clustered, +fees)
| Decision | edge | traded | mean $/ct | **day-clustered t** | asset-day clusters | winrate |
|---|---|---|---|---|---|---|
| close−300s | 0.03 | 66 | −0.021 | **−1.12** | 10 (3 pos) | 0.18 |
| close−300s | 0.05 | 62 | −0.033 | **−1.74** | 9 (2 pos) | 0.18 |
| close−180s | 0.05 | 51 | −0.005 | **−1.34** | 7 (2 pos) | 0.12 |
| close−180s | 0.08 | 47 | −0.004 | −1.45 | 7 | 0.13 |

Per-asset (edge 0.05, close−300s): btc mean +0.0003 (t=+0.07, n=40), eth −0.082 (t=−1.02), xrp −0.226 (t=−2.90, n=2).

**Multiple-testing count:** 3 assets × 3 edges × 2 decision times = 18 cells scored; **every pooled cell is
≤0**, best per-asset (BTC) is an insignificant ~0. No positive cell to select. This is a NEGATIVE/NULL sweep,
not a cherry-picked positive.

---

## 3. VERDICT (per market)

- **Hourly crypto directional (KXBTCD/ETHD/XRPD): DISCOURAGING — no demonstrable edge.** The wide-book
  precondition holds, yet the raw FAVLONG fair-value model produces a **negative** pooled day-clustered t
  (−1.1 to −1.7) with an 12–18% winrate across both timescales. The 15m edge does **not** transfer for free.
  Wide spread alone is insufficient; the 15m effect appears specific to its ultra-short terminal-convergence
  dynamics / vol regime, which a candle-level hourly reconstruction does not reproduce.
- **All other non-15m tenors (daily/weekly/monthly range & one-touch, econ/event binaries): UNTESTED —
  no stored data and (for most) too few settled instances or no spot-vs-strike structure to run FAVLONG.**
- **Kalshi perps: N/A to FAVLONG** (continuous, no expiry/settlement binary); collector just started.

**Confidence / caveats on the null (why it is DISCOURAGING, not a hard rejection):**
1. **Underpowered** — only ~5–6 days, 66–86 windows, 7–10 asset-day clusters. Charter needs ≥10 forward days.
2. **Candle-resolution book** — the executable price is a 1-min candle *close*, not the sub-second top-of-book
   FAVLONG actually trades. The edge is a **transient last-2–3-min repricing lag**; 1-min candles almost
   certainly wash out the exact dislocation. This is the single biggest confound.
3. **Spot/index basis** — fair value uses Binance USDT spot, not Kalshi's settlement index (CF Benchmarks
   BRTI/BRTI-style). Index/basis mismatch injects fair-value noise that can flip the taken side.

Net: no free hourly edge is visible, and there is no positive signal worth live sizing. A proper test
requires **forward collection of sub-second hourly books**, exactly as 15m is collected.

---

## 4. COLLECT-SPEC (to test hourly FAVLONG properly, forward)

Clone the existing 15m collector for the hourly directional series. Concretely:

- **Series:** `KXBTCD`, `KXETHD`, `KXSOLD` (drop XRP — 15m XRP was the null; keep XRPD only as a control).
- **Instrument selection per hour:** the ATM strike whose `floor_strike` is nearest live spot; also carry the
  two adjacent strikes (the ATM can migrate in the last minutes).
- **Cadence:** **sub-second / ≤1s top-of-book** for the **final 5 minutes** of each hourly window (match the
  15m tick collector's near-expiry density). Coarser (5–15s) is fine earlier in the hour.
- **Fields per tick (mirror the 15m schema so `favlongshot_edge.build_asset` works unchanged):**
  `t` (seconds into the 3600s window), `mid`, **`spot`** (Kalshi's *settlement* index, not an exchange
  proxy — pull from Kalshi's index feed or record `expiration_value` source), `micro`, `yes_bid`, `bid_qty`,
  `yes_ask`, `ask_qty`. Store one file per (series, window).
- **Settlement:** capture `result`, `expiration_value`, `floor_strike`, `close_time` per market (clean label).
- **Horizon:** **≥15 trading days** to yield ≥10 day-clusters per asset for a charter-grade day-clustered
  t≥2 gate with a train(≤day N)/test(>day N) split and a pre-registered edge threshold.
- **Then re-run** the FAVLONG battery (fair-value model v2 incl. isotonic calibration fit train-only,
  latency test, +fees, cross-asset pooled clustered t) on the sub-second hourly ticks.

Until sub-second hourly ticks exist, **hourly FAVLONG stays PARKED**: the candle-level evidence is negative,
and the mechanism cannot be fairly evaluated at 1-min resolution.

*(Reproduce: `scratchpad/hourly_favlong.py` — live-API + Binance-vision spot, offline research script.)*
