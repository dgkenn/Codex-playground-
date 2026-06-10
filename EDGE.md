# EDGE.md — deep dive: the three things that make up the edge

> **Current state (updated after 4 days of multi-asset data — see `INSIGHTS_4DAY.md`).** Two claims below
> were REVISED by the data: (1) the toxicity gate that wins is now **`ufat_band`** (`ufat` p-adaptive margin
> + skip the toxic 0.30–0.55 zone), not plain `micro_gate`; (2) **front-of-queue is NOT lower adverse
> selection** — the data shows the *opposite* (front fills are the toxic ones; benign fills come from deep
> sweeps). Corrections are inline below. The 3-lever decomposition itself still holds.

The whole edge decomposes as, per window:
    net = Σ_fills [ rebate(p)·sz  +  markout_to_resolution·sz ]
- `rebate(p)·sz` ≈ 0.20·0.07·p(1-p)·sz (~+0.0025/sh at p=0.5) — the ONLY positive term in expectation.
- `markout·sz` (gross) ≈ 0 in aggregate (58 windows): spread-capture is eaten by adverse selection.
So **net ≈ the rebate**, and everything is about (a) collecting more rebate (= getting filled = QUEUE),
(b) not giving it back to adverse selection (= TOXICITY-AVOIDANCE), and (c) not losing it to a directional
inventory bet at resolution (= DELTA-NEUTRAL, SMALL). Those are the three levers below.

================================================================================
## 1. FRONT-OF-QUEUE PRIORITY — the binding constraint and the biggest prize
WHAT: under price-time (FIFO) priority, earlier resting orders fill first. In a 1-tick-spread market
you cannot price-improve to jump the queue, so queue *position* is the only contestable execution edge.

EVIDENCE (ours): relative tick = **1.96%** (1c on ~$0.50) — order(s) of magnitude above equities, the
canonical "large-tick / queue-dominated" regime. Fill rate is only **~6%** and **68% of decisions are
skew/queue-blocked** — i.e. we capture a sliver of flow; the binding constraint is getting filled, not
finding signal. ~204 repricing events/window (queue resets) where position decides who fills.

MAGNITUDE: queue value ≈ the spread ≈ **1c/share ≈ 4-8× the rebate** (Moallemi-Yuan: positional value
~ spread for large tick). So *of the three levers, this is the largest* — and it's pure execution.

CAPTURE: standing ladder (aged rungs = accrued priority; never reflexively cancel) + lead-aware
protection (queue-jump: protect the side the BTC-lead/depletion says the touch is heading toward).
**CORRECTION (INSIGHTS_4DAY #6, 56k fills):** front-of-queue is NOT lower adverse selection — it's the
opposite. Front fills mark out **−0.0018** while DEEP-queue fills (caught in big benign sweeps) mark out
**+0.0095**. Informed flow picks off the front; uninformed liquidity-demand sweeps fill the deep rungs.
So queue priority raises fill *rate* but worsens the *mix* — it is a fill-VOLUME lever, not a
toxicity lever. Don't over-pay latency for front position; rest a fuller ladder to catch the sweeps.

HONEST LIMIT: this is the one lever **paper cannot measure** — the sim fills us at ~front (q_ahead≈0),
so the entire paper A/B is the *front-of-queue upper bound*; the live haircut vs paper IS the queue
battle. Realizing it is live-execution (latency, FIFO race vs colocated bots) — the live pilot's job.
LIT: Moallemi-Yuan (2016); Queue-Reactive Model (Huang-Lehalle-Rosenbaum 2015); Fokker-Planck (2013).

================================================================================
## 2. TOXICITY-AVOIDANCE — the measured, robust, paper-provable edge
WHAT: decline the fills that are adversely selected (the counterparty is right about the next move),
keeping the rebate-positive ones. The maker's occupational hazard (Glosten-Milgrom).

EVIDENCE (ours): adverse selection is real and significant — baseline 30s-markout **t=-3.06 over 37
windows**. The **microprice edge** is the one robust separator (sign-consistent 21/8 windows); the
composite toxicity score separates winners/losers in **75% of windows**, incl. resolution P&L. Gating
on it (micro_gate) beats baseline by **+5.0/win, t=+5.99 (58w)** — the single largest *measured* uplift.

MAGNITUDE: micro_gate turns gross from ≈0/negative to clearly positive; the A/B uplift is ~+5/win, i.e.
toxicity-avoidance roughly *doubles-to-triples* the rebate-only baseline (+0.39/win).

CAPTURE: microprice gate. **UPDATE (4-day prospective + `gate_lab`/`combo_lab`):** plain `micro_gate` is
beaten — the deployable winner is **`ufat`** (p-adaptive margin: strict at p≈0.5, loose at the benign
tails) and the best combo is **`ufat_band`** (`ufat` + skip the toxic 0.30–0.55 P(up) zone), ~2× OOS
net/win vs `ufat`. The long-run gate is **`micro_cal`** (keep iff predicted_markout + rebate > 0, so the
threshold tracks the real rebate). The microprice IS the Avellaneda-Stoikov reservation anchor, so the
gate also controls inventory indirectly (the levers aren't super-additive). Flow/VPIN/queue/spread gates
were tested and do NOT help (see `GATING.md`).

HONEST LIMIT: short-horizon markout OVERSTATES the cost — it's largely transient (mo5 -0.0016 -> mo30
-0.0041 -> mo_res +0.0006), so don't over-cancel (churn locks transient losses). Per-fill SNR is tiny
(R²~0.01-0.04); the signal works only in aggregate. The offensive version (predict BTC, take) FAILS
the fee (lag_taker -27.9/win) — toxicity-avoidance is DEFENSIVE only.
LIT: Glosten-Milgrom (1985); Stoikov micro-price (2018); Cont-Kukanov-Stoikov OFI (2014).

================================================================================
## 3. DELTA-NEUTRAL, SMALL INVENTORY — protect the rebate from the resolution bet
WHAT: hold little net inventory and keep it balanced (sell UP+DOWN ~equally), because the *real*
resolution cost is a directional inventory bet, and in a large-tick market you cannot exit cheaply
(exit = cross/taker-fee or wait in queue).

EVIDENCE (ours): the capacity dial is monotone — cap25 **t=+3.64**, skew15 **t=+3.87** beat baseline;
**cap100 LOSES (t=-2.48)**; more capacity = more adverse exposure & impact. We already sell UP/DOWN
~evenly (3439/3369) = naturally delta-neutral box-selling. The price-level "favorite-longshot" P&L
that looked like alpha was REGIME-CONFOUNDED (flips by outcome, 23/35 windows) — i.e. directional
inventory is *risk, not edge*, which is exactly why you neutralize it.

MAGNITUDE: tighter inventory adds ~+1.7-1.9/win over baseline; cap100 costs ~-1.7/win. So the dial is
worth ~±2/win — and it's the cheapest lever (just a parameter).

CAPTURE: tight cap/skew (cap25, skew15, dneutral skew=0.08), the principled Avellaneda-Stoikov
continuous penalty (av_stoikov), delta-neutral two-sided selling. Quote small per clip.

HONEST LIMIT: too tight forgoes rebate volume (it's a threshold, not "minimize inventory"); the optimum
is where marginal adverse-exposure = marginal rebate. Still being pinned down in the A/B.
LIT: Ho-Stoll (1981); Avellaneda-Stoikov (2008); Gueant-Lehalle-Fernandez-Tapia (2013).

================================================================================
## HOW THE THREE INTERACT (the unified picture)
- They are **complementary and partly substitutable**: front-of-queue lowers toxicity (fill early not
  on the sweep); the microprice gate (toxicity) also caps inventory (declines the fills that build
  adverse positions); small inventory makes you willing to hold front-queue without exit fear.
- **Ranking by size:** queue priority (~1c, biggest, execution/live) > toxicity-avoidance (~+5/win,
  measured, software) > inventory dial (~±2/win, a parameter).
- **Ranking by certainty:** toxicity-avoidance (paper-proven) > inventory (paper-proven) > queue
  (live-only, but the literature is unambiguous it's the dominant large-tick lever).
- **The edge is multiplicative:** rebate × (fills you win = queue) × (1 - toxicity) × (survive to
  resolution = delta-neutral/small). Drop any one and net -> ~0. Paper shows the last three; the first
  (queue) is the live multiplier and the whole reason the paper edge may not survive intact.

BOTTOM LINE: there is NO directional/predictive alpha (BTC-taker and FLB both tested & rejected). The
edge is entirely microstructural execution: **win the queue, dodge the toxic fills, stay flat and small,
harvest the rebate twice.** Paper proves levers 2-3 and bounds lever 1; live must prove lever 1.
