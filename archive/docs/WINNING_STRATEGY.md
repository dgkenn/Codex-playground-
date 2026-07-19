# Winning strategy — derived from the month-long A/B (2026-06-10 → 07-11)

Source: the forward shadow-comparison ledger on the `gha-data` branch
(`gha_data/<date>/SUMMARY.txt`, 32 daily rollups, 8–12 de-duped windows/day).
Variant definitions: `strategies.py` on `claude/polymarket-btc-backtest-XZkKI`.
All numbers below are **rebate-inclusive net edge over the live baseline** (`Δvs base`,
in the ledger's per-win units), with `gross` = the same P&L **excluding** the maker rebate.

## Verdict: `av_stoikov`, ideally ensembled with `mo_size`

`av_stoikov` is the winner on a full month of forward data — not a single lucky day.

| metric | value |
|---|---|
| mean edge vs baseline | **+4.67 / win** |
| month-level t (day-as-observation, n=32) | **+7.68** |
| days with positive edge | **29 / 32 (91%)** |
| days gross-positive (edge *beyond* rebate) | **32 / 32** |
| days it was the top variant | 25 / 32 |
| trend | strengthening into July (07-10 hit +37.7 net/win, month high) |

Being gross-positive on **every** day is the key qualifier: the edge is real market-making
skill, not just rebate harvesting. Only two variants clear that bar meaningfully — and they
are the only two with a positive month-level t.

### Exact config (from `strategies.py`)
```python
Strat("av_stoikov", cap=50, skew=0.99, size_mode="flat", gate="as", tau_guard=0)
# Avellaneda–Stoikov: take on inventory ONLY when the quoted edge clears the
# variance penalty. Loose symmetric leash (skew=0.99), no hard toxicity gate.
```

## The upgrade: run `av_stoikov` + `mo_size` as an ensemble

`mo_size` is the **second real edge** (+1.88/win, t=5.76, 29/32 days, 32/32 gross). It uses a
*different* mechanism — continuous markout-weighted **sizing**, no discrete gate
(`size_mode="markout"`, `gate=None`) — so it is complementary, not redundant:

- correlation of their daily edges: **+0.38** (low → they diversify)
- on **all 3 days `av_stoikov` was negative, `mo_size` was positive** (+2.38, +1.59, +2.01)
- across all 32 days, **at least one of the two was positive every single day**

**Recommended next test (not yet in the roster):** a combined variant that applies the A-S
inventory gate *and* markout-weighted sizing:
```python
Strat("as_markout", cap=50, skew=0.99, gate="as", size_mode="markout")
```
Enroll it in the live shadow A/B; if it holds ≥ the max of its parents on gross edge, it
becomes the deployable strategy.

## The finding that forces action: the *deployed* edge has stopped working

`micro_gate` — whose own note reads *"microprice toxicity gate — THE deployed edge (+4.8/win)"* —
posts **Δ = +0.000 vs baseline on all 32 days**. On live forward data it is a **no-op**: the
lab-validated gate does not reproduce. The system is currently running a strategy that adds
nothing, while `av_stoikov`/`mo_size` sit in shadow adding measurable edge.

**Action:** promote `av_stoikov` (or the `as_markout` ensemble) to deployed; retire `micro_gate`
as the live strategy.

## Losers — prune from the live roster

Everything except the two winners is net-negative over the month. Worst offenders (mean Δ/win, days positive):

| variant | meanΔ | month t | days+ |
|---|---|---|---|
| micro_strict | −4.47 | −8.36 | 0/32 |
| micro_cal | −4.07 | −7.70 | 2/32 |
| dneutral | −3.91 | −9.33 | 1/32 |
| ufat_skew15 | −3.81 | −7.07 | 2/32 |
| ufat_band | −3.47 | −6.10 | 6/32 |
| tox_gate | −3.35 | −6.54 | 1/32 |
| micro_marg | −3.21 | −6.02 | 2/32 |
| cap25 | −2.87 | −7.86 | 2/32 |

Notable: the a-priori hypothesis in `strategies.py` that *"on Kalshi (no rebate) stricter gates
likely win — micro_strict/micro_asym first-line candidates"* is **contradicted by the forward
data** — `micro_strict` is dead last (0/32 days positive). Over-gating sheds too much fill flow;
principled inventory control (A-S) + continuous markout sizing is what actually pays.

## One-line summary
> Deploy **`av_stoikov`** (A-S inventory control, skew 0.99, gate `as`); pair it with **`mo_size`**
> for full daily coverage; retire the inert **`micro_gate`**; test the **`as_markout`** combo next.

_Caveat: 8–12 windows/day is thin per day; the conclusion rests on the 32-day sign-consistency
(29/32) and month-level t (7.68), not on any single day's paired-t._
