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

## 3b. The rollover burst (operator observation, answered)

The bot visibly "buys a ton right when the previous market resolves, then sits on
the position." Both halves are by design, and neither is caused by the loss limit:

- **The burst**: the zero-RTT rollover prefetches the next market and quotes at
  second 0, deliberately — being first to rest at the touch of a fresh, thin, wide
  book is the queue-priority edge. **85 of 103 live fills (83%) arrived in the first
  minute** of their window.
- **The sit**: positions are held to settlement because exits were tested on 20,318
  fills and every stop variant lost (§6). Max hold is 15 minutes by construction.

Is the burst costing PnL/Sharpe? **No — it IS the PnL.** Live fills by entry time:

| minutes into window | 0–1 | 1–2 | 2–4 | 4–8 |
|---|---|---|---|---|
| fills | 85 | 6 | 3 | 9 |
| mean settle PnL (¢/fill) | **+3.24** | −3.33 | −3.83 | −4.97 |
| total (¢) | **+275** | −20 | −12 | −45 |

Minute-0 fills produced more than the session's entire net; the mid-window fills
lost. The caveat cuts the other way: minute-0 is also where the −$2 blowup window
lived (10 fills inside 70 seconds — exactly what `--max-fills-side 4` now stops),
and the candle-based deep-tape backtests could never validate minutes 0–2, so the
open-burst edge rests on the live sample alone (n=85, t≈0.7 — positive, not yet
significant). Verdict: keep quoting the open, keep the caps, let live n accumulate.

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

## 8. Box decomposition (added 2026-06-11): the profit is the PAIRS

Splitting every window's PnL into its **boxed** component (min(yes,no) contracts —
paired YES+NO bought for < $1 total pays $1 at settlement *regardless of outcome*,
i.e. risk-free once filled) and the **unpaired directional residual**:

|  | live (11 windows) | tape (1,158 windows, 20,318 fills) |
|---|---|---|
| windows completing ≥1 box | 10/11 | 1,154/1,158 |
| locked (risk-free) PnL | **+468¢** | **+18.04¢/win (t=+34.5)** |
| directional residual | −269¢ | **−16.29¢/win (t=−16.9)** |
| net | +199¢ | +1.75¢/win |

The strategy is a **box harvester taxed ~90% by unpaired inventory**. Policy test —
walk the tape in fill order, take a fill only if |net| stays ≤ L:

| L (max net) | none | 4 | 3 | 2 | **1 (strict pairing)** |
|---|---|---|---|---|---|
| net/win (¢) | +1.75 | +1.75 | +1.79 | +1.81 | **+1.96** |
| t | +2.1 | +2.1 | +2.2 | +2.3 | **+4.3** |
| OOS Calmar | 0.5 | 0.5 | 0.5 | 0.4 | **0.9** |

L=1 keeps the box income, skips most of the bleed, and is strictly LESS risky
(max directional exposure $1/window). Deployed as `--max-net` (default 1): after a
YES fill only the NO side quotes until paired, and vice versa. Per-window `[BOX]`
telemetry (paired count, locked $, unpaired residual) now prints at every rollover.

## 7. Re-arm checklist (when the operator decides to resume)

1. Delete `.kalshi_killed_btc15m` (deliberate manual act — that's the design).
2. `python kalshi_preflight.py` → must print GO.
3. Run with the new defaults; `--max-fills-side 4` and the ±3 clamp are on
   automatically. Same $2–3 loss limit until the cap'd config has a clean session.

---

## Live performance audit — 2026-06-12 (~2 days live, 42 audited windows)

**Verdict: box engine works, but the sample is too thin to claim alpha, and 100% of the
real losses are one failure mode — a stranded YES leg.** Numbers below are the AUDIT-FILE
realized cash (`window_audit_btc15m.jsonl`), which I trust over the scorecard's internal
attribution.

### Actual vs expected (verified, audit file n=42 windows)
| metric | expected | actual | verdict |
|---|---|---|---|
| net realized | >0 | **+$1.34** (42 win) / +$2.69 (scorecard, 70 win) | positive but NOT significant: per-window +0.03$ (t≈1.0, p≈0.35) |
| pairing rate | ~96% OOS | **97%** (Wilson [94.5,98.4]) | IN LINE |
| per-fill markout | ~0 (maker) | −0.28c | flat, not significant |
| fees | $0 | **$0** (714 fills) | CONFIRMED |
| effective spread captured | +0.5–1c | −0.22c | drag from strands (boxes themselves are +) |
| sample size | "many" | 42 windows, ~2 days, power ~15% | **THIN — need ≥180 windows (~4–5 more days) for 80% power** |

### Every loss, root-caused
- **8 of 42 windows carried an unpaired leg; 5 of those were net-negative (total ≈ −$2.0).**
- **6 of the 8 strands were the YES side** → the entire loss center is **stranded YES legs**:
  our YES bid fills as price falls toward it, the NO bid never pairs (NO is rising, nobody
  sells it cheap to us), BTC closes below strike, YES settles $0. Classic unpaired-leg adverse
  selection on the side a down-move pushes into us. Matches the structural YES-toxicity finding
  (H7/t02/t08: unpaired YES toxic, unpaired NO mildly favorable).
- **1 inventory breach** (06-12 14:15, net=−2, duplicate NO fills before the pairing gate);
  outcome +5.7c by luck. A control-race failure, not a strategy failure.
- The scorecard's **−$7.96 "directional residual" is NOT realized cash** — audit shows strand
  windows netted −$0.9. Treat −7.96 as internal MTM/attribution; reconcile per-leg before trusting.

### Three high-leverage fixes (ranked)
1. **Graduate a directional/toxicity OPEN-guard onto the LIVE opener** (bot is ungated P0 today).
   Every loss is a leg filled into an adverse spot trend; pull/widen the bid on the side a live
   down-move (YES) or up-move (NO) is pushing into us. t07 (spot-gate) + t02 (YES-caution) +
   t35 (thin-window combo) are the validated candidates — deploy the first that clears n≥300 fwd.
   Attacks 100% of the realized loss bucket.
2. **Asymmetric reservation-price skew (Avellaneda-Stoikov on the box).** Quote YES and NO NON-
   symmetrically by regime+inventory: demand more edge on the structurally-toxic side so a strand
   there is CHEAP (cheap strands lose less, t11), and HOLD favorable unpaired NO legs to settle
   (t08) instead of chasing. Cuts cost-per-strand even when one happens.
3. **Strand circuit-breaker + close the pairing race.** (a) Pause opening NEW boxes after K strands
   in M minutes (the losses clustered in one afternoon regime — stop feeding it). (b) Fix the
   duplicate-fill race behind the net=−2 breach (atomic pair-check + L3 pending_cancel). Caps the tail.

**Meta-lever:** keep the bot running clean to reach n≥180 before any alpha claim; keep gates in
A/B (not live money) until n≥300. Today we cannot statistically separate the +$1–2 from noise.
