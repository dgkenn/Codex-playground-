# Live Post-Mortem — KXBTC15M maker session ended by loss-limit kill

**Status: LIVE TRADING PAUSED.** The sticky sentinel `.kalshi_killed_btc15m`
(`loss_limit realized=-1.79 mark=-1.22`, total −$3.01) stays in place until the
operator explicitly deletes it. The account ended **flat at $11.40** — net **+$1.40**
on the $10 deposit across the full live campaign, even counting the losing session.
The kill worked exactly as designed: it bounded a bad hour at −$3 instead of letting
it run.

This document is the full analysis of every live fill, what actually caused the
loss, the hypotheses that did NOT survive testing, and the two fixes implemented
in `kalshi_trader.py`.

---

## 1. What the live tape shows (103 fills, `kalshi_fees_btc15m.jsonl`)

| stat | value |
|---|---|
| fills | 103 (56 yes / 47 no) — **0 takers**, 100% maker, **fee = $0.00 on every fill** |
| mean per-fill markout-to-settle | **+1.93¢** |
| median per-fill | **−0.30¢** |
| per-fill win rate | 48% |
| worst single window | **−$2.00** |
| mean entry price | 0.453 |

The shape is the story: a *positive mean* riding on a *negative median*. Most fills
are small coin-flips; the edge lives in a subset, and the losses concentrate — one
window alone produced 2/3 of the loss that tripped the kill. The per-fill economics
are fine; the **per-window accumulation** is what failed.

## 2. Hypothesis tested and REJECTED: "low-price entries are toxic"

Losing fills entered at mean p = 0.35 vs winners at 0.566, which suggests a price
floor (e.g. "don't quote below p=0.40"). Tested properly on the deep historical
tape (20,318 queue-replayed real fills, bucketed by entry price): **every price
bucket's mean markout differs from the pooled mean with |t| < 0.6**. The price-level
pattern in the live sample is a 103-fill artifact of *which side the trend ran over*,
not a causal feature. No price-floor gate was added — it would cut volume without
cutting risk.

## 3. The actual cause: serial same-side accumulation into a trend

In the losing window the bot stacked **8 same-side contracts** — fill, cooldown,
re-quote, fill again — against a spot move that kept going. The deep tape confirms
this is the general failure mode, not a one-off. Mean markout by how many same-side
fills the window had ALREADY produced when the fill happened:

| prior same-side fills in window | 0 | 1 | 2 | 3 | 4 | 5+ |
|---|---|---|---|---|---|---|
| mean markout (¢/fill) | +0.08 | +0.12 | +0.23 | +0.30 | +0.27 | **−0.02** |

Fills 1–4 per side per window are fine — they actually *improve* (early fills in an
active window are benign flow). The **5th-and-beyond bucket is where the edge dies**:
by then the repeated one-directional fills *are* the toxicity signal, and the
fill-cooldown alone (20s) does not outlast a 15-minute trend.

## 4. The fix, backtested as a policy: cap same-side fills per window

Replaying the cap over the same 20k-fill tape:

| cap (same-side fills/window) | none | **4** | 3 | 2 | 1 |
|---|---|---|---|---|---|
| net/win (¢) | +1.75 | **+1.42** | +0.83 | +0.39 | +0.15 |
| t-stat | +2.1 | **+4.7** | +3.3 | +2.0 | +1.1 |

Cap = 4 keeps **81% of the net** while **more than doubling the t-stat (2.1 → 4.7)**
— it removes almost pure variance. Tighter caps throw away the good fills 2–4
bring; no cap leaves the tail that killed the live session.

## 5. Changes implemented in `kalshi_trader.py` (this commit)

1. **`--max-fills-side` (default 4)** — hard cap on fills per side per window.
   Counter incremented in `book_fill` (both WS and REST fill paths), checked in the
   placement loop before any quote goes out, reset at window rollover.
2. **Hard ±3 net-contract inventory clamp** — the directional clamp was previously
   `max(1, --max-notional)`, which silently loosens whenever the dollar budget is
   raised. It is now a hard constant ±3 net contracts: the absolute worst-case
   directional loss per window is $3 regardless of configuration. (The losing
   window reached net 8.)

Both verified: compiles, dry-run clean, counter resets across rollover.

## 6. What was already ruled out earlier (kept for the record)

- **Stop-loss exits**: tested on the same 20,318 fills — hold-to-settle earns
  +0.10¢/fill while every stop variant loses −0.18..−0.99¢ (binary 15-min markets
  mean-revert; stops sell the bottom). Ruin control is *size*, not exits.
- **Fees**: all 103 live fills report `fee_cost = 0` — CRYPTO15M maker fee-exemption
  is confirmed ground truth, the `--fee-mult` machinery stays for other series.

## 7. Re-arm checklist (when the operator decides to resume)

1. Delete `.kalshi_killed_btc15m` (deliberate manual act — that's the design).
2. `python kalshi_preflight.py` → must print GO.
3. Run with the new defaults; `--max-fills-side 4` and the ±3 clamp are on
   automatically. Same $2–3 loss limit until the cap'd config has a clean session.
