# KALSHI_15M_STRESS — is there a VIABLE transient-wide-spread MAKER play in the 15m BTC binary that AVOIDS the ATM queue war? (2026-06-21)

**Verdict (one line): NO. The transient-wide-spread maker play is DEAD on BOTH walls at once — it is
LATENCY-WALLED (91.8% of wide-spread episodes are a SINGLE 1.2s tick; only 5.3% survive even one full
poll, so a ~1.2s cloud bot cannot see-then-place into them — the exact same wall that buried the box)
AND, even granting the impossible best case that the bot lands the quote q0=0 inside every wide
spread, the fills are TOXIC: realized markout is −3.25c at 30s and −3.61c to SETTLEMENT
(window-clustered −3.92c / −5.73c, t=−13.6 / −6.6), and it stays negative OOS (−4.57c settlement,
t=−4.2) and in EVERY vol sub-bucket. Wide spreads are where you GET RUN OVER, not where you harvest —
the box's exact failure, sharper. Quoting into the wide spread is −EV net of adverse selection by a
wide margin. Do not build it.**

The operator's hypothesis — "the MM pulls when vol spikes, leaving a transient wide spread a maker can
fill for the spread without fighting the ATM queue" — is FALSIFIED on the data: the wide-spread
moments are (a) too fast to catch and (b) adversely selected when caught. Both, independently, kill it.

---

## Data, N, costs, screens

- **Source:** `origin/gha-data` `ticks_kalshi_btc15m_*.jsonl.gz` (tick = `[t_rel_s, mid, spot, mid2,
  bid, bid_sz, ask, ask_sz]`) × `shadow_windows_*` (`resolved_up`). **912 settled windows, 908 with
  usable tick series, 611,992 ticks, 12 days (06-10..06-21).** Read straight from git, no API.
- **Cadence:** poll/tick interval is a rock-steady **1.20s** (median = p10 = p90), identical to the MM
  heartbeat documented in `QUEUE_TIMING.md`. This is the binding latency constant.
- **Costs:** CRYPTO15M maker fee = 0; taker disposal fee = 0 at this venue → the markout IS the net
  P&L (no fee cushion to hide behind, and none needed against numbers this negative).
- **Fill model:** the BEST case for the maker. We post 1c INSIDE the wide touch (improve-tick, the
  only lever that buys q0→0 per `QUEUE_TIMING`) and assume a CAUSAL fill: our improved bid (bid+1c)
  fills iff some later tick within 30s shows `ask ≤ bid+1c` (a seller crossed down to us); symmetric
  for the improved ask. This GRANTS the queue jump the bot cannot actually win — and it still loses.
- **Anti-artifact discipline (from `KALSHI_15M_LONGSHOT.md`, where a time-in-band selection killed the
  longshot "lead"):** markout is measured strictly FORWARD from the decision tick (no look-ahead, no
  conditioning on the path that produced the fill), window-clustered t-stats (one mean/window), and an
  OOS time-split. Settlement P&L is the load-bearing column.
- Reproduce: `python kalshi_15m_stress.py`.

---

## Part 1 — Spread time-series: wide episodes are RARE and INSTANTANEOUS

| spread | value |
|---|---|
| median / mean | **1.00c / 0.86c** (mean < median: sub-penny ticks at the price tails) |
| p90 / p95 / p99 / max | 1.00c / 2.00c / 2.00c / 44.0c |
| frac spread > 2c | **6.5%** |
| frac spread > 3c | 0.27% |
| frac spread > 5c | 0.02% |

**Wide (>2c) episodes: n=1428. 91.8% are a SINGLE tick (duration 0s). Median/mean episode duration
0.00s / 0.17s.**

| episode survives ≥ | frac |
|---|---|
| 1 full poll (1.2s) — visible AND still there on the next loop | **5.3%** |
| 2 polls (2.4s) — see it, decide, place, still there | **1.3%** |

The spread snaps wide for ONE 1.2s snapshot and snaps back. A bot polling at 1.2s observes the wide
spread on poll *k*; by poll *k+1* (the soonest it could place an order) it is gone in ~95% of cases.
This is the `QUEUE_TIMING` wall restated: **the exploitable window is sub-1.2s, below our data
resolution and below our cloud react+order-ack latency.** Same wall, different play.

**Vol trigger is WEAK, not strong.** |spot move| over the prior 3.5s is essentially identical at wide
ticks (mean 0.5 bps) and narrow ticks (mean 0.6 bps); `P(wide | spot-move top 5%) = 0.002` vs base
`0.003`. The premise "vol spike → MM pulls → wide spread" is NOT what the tape shows — wide spreads are
mostly micro-structural single-snapshot blips (a level momentarily empties / a quote flickers), not
vol-driven MM withdrawals. And they are NOT a tail-grid artifact either: only 4.4% of wide ticks sit
in the price tails (<0.10 or >0.90) vs 29.5% of all ticks; ~25% are ATM (0.40–0.60). So the play fails
across the whole price range, not just at the coarse-grid corners.

## Part 2 — Wide-spread maker markout: TOXIC even in the best case

Granting the q0=0 queue jump (which the bot cannot win), at each wide tick we post inside and mark the
fill forward:

| group | fills | windows | SHORT markout (30s) | SETTLEMENT P&L (load-bearing) |
|---|---|---|---|---|
| **ALL wide-spread fills** | 2443 | 490 | **−3.25c** (clustered −3.92c, t=−13.6) | **−3.61c** (clustered −5.73c, **t=−6.6**) |

A fill in a wide-spread moment is **toxic**: the price moves AGAINST you immediately (−3.25c at 30s)
and resolves against you (−3.61c to settlement). The 1c of "spread" you improve is dwarfed by the
adverse selection — you are the liquidity the informed/fast counterparty wanted, exactly as the box's
−4.01c "touch-about-to-move" fills in `QUEUE_TIMING §1`. The wide spread is wide *because* the price
is about to jump; quoting into it buys the jump. **Captured spread ≪ adverse selection.**

## Part 3 — Gate tension (Foucault stand-down vs quoting-into-vol): NO sub-gate rescues it

The box A/B gates (`box_policy_ab.py`: t20 Foucault low-vol open, t32 VPIN>0.40 stand-down) say AVOID
high vol — but this play quotes INTO it. The irony resolves cleanly AGAINST the play: **both vol
halves lose.**

| sub-gate | fills | SHORT | SETTLEMENT |
|---|---|---|---|
| LOW-vol wide fills (Foucault-allowed) | 1319 | −3.49c | **−4.29c** (clustered −6.50c, t=−6.0) |
| HIGH-vol wide fills (gate forbids) | 1124 | −2.97c | **−2.81c** (clustered −4.13c, t=−3.3) |

The low-vol subset is, if anything, WORSE on settlement — because the low-vol-but-wide ticks are the
flickering single-level-empty blips that mean-revert and pick you off, not a harvestable premium.
There is no vol threshold that flips the sign. The gates' instinct (stand down) is correct; their
logic generalizes to "do not quote into the wide spread AT ALL," which leaves no play.

## Part 4 — Latency / capacity reality

Already decisive in Part 1: **94.7% of wide episodes do not survive a single 1.2s poll.** A GitHub-
Actions cloud bot (27ms book rtt one-way + decide + order-ack, per `QUEUE_TIMING`) cannot detect →
decide → place inside the sub-1.2s life of a wide-spread blip against the co-located mechanical ladder
MM that reprices its touch on the same 1.2s cadence. Even the 5.3% of episodes that DO persist ≥1.2s
are, per Part 2, the toxic ones (you land just in time to be run over). **There is no capacity here:
the events are too rare (6.5% of ticks, of which 92% are 1-tick), too fast, and adverse when caught.**

## OOS — survives nothing

| split | settlement P&L (clustered) | t |
|---|---|---|
| IS (06-10..06-16) | −4.96c | −5.1 |
| OOS (06-17..06-21) | **−7.31c** | **−4.2** |

The loss is STABLE and if anything LARGER OOS. This is the opposite of an overfit edge fading to zero —
it is a robust structural −EV. (Note the contrast with `KALSHI_15M_LONGSHOT.md`, where a spurious
*positive* signal was a selection artifact; here the *negative* result needs no such caveat — it is
measured forward, clustered, and OOS-stable.)

---

## VERDICT — DEAD. Two independent walls; do not build.

1. **Latency wall (primary).** Wide-spread episodes are single-1.2s-tick blips (91.8% dur=0; only
   5.3% survive one poll). A ~1.2s cloud bot is structurally too slow to post inside them — the exact
   `QUEUE_TIMING` wall that killed the ATM box, just expressed in the spread series instead of the
   queue. Co-located only.
2. **Adverse-selection wall (independent).** Even GRANTING the impossible q0=0 fill, wide-spread fills
   markout −3.25c at 30s and −3.61c to settlement (t=−6.6, window-clustered), OOS-stable at −7.3c.
   The wide spread is wide *because* price is about to move; you buy the move. The captured 1c ≪ the
   adverse selection — the box's exact failure mode.
3. **No gate rescue.** Low-vol and high-vol wide-fill subsets are both deeply negative; the Foucault/
   VPIN stand-down instinct correctly generalizes to "never quote into the wide spread."
4. **Premise falsified.** Wide spreads are NOT vol-spike-driven MM withdrawals (vol at wide ≈ vol at
   narrow ticks) and NOT a tail artifact — they are micro-structural flickers across the whole price
   range, transient and toxic.

**This is the brutal-honesty outcome the brief anticipated: the wide-spread moments ARE the toxic/
informed moments and they are too fast for cloud latency — the same wall, twice over.** The standing
project conclusions hold: 15m crypto is efficient at every horizon ≥1min (`DIRECTIONAL.md`), the box
is structurally last-in-queue (`QUEUE_TIMING.md`, `BOX_REGIME.md`), and the only real Kalshi edge is
the soft-market longshot-MAKER harvest. **No deployable config. Do not run a transient-wide-spread
maker.**

*Reproduce: `python kalshi_15m_stress.py`. N=908 windows / 611,992 ticks (gha_data 06-10..06-21).
Costs: maker/taker fee 0 at CRYPTO15M. Fill model grants q0=0 (best case). SCREENS in stdout.*
