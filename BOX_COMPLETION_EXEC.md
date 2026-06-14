# BOX_COMPLETION_EXEC — the second-leg completion / execution layer of the BTC 15m maker-box

**Verdict (one line): The dominant live completion-toxicity cost is the STRANDED odd leg riding naked
to settlement (−50…−61c each), not the legging-gap chase — and its root cause is QUEUE POSITION
(we fill ~last vs the 1.2s mechanical ladder-MM), which is the backtest's optimistic q0=0 fill model
made real. The single biggest deployable win is making strand-completion RELIABLE: lower
`--dispose-cross-s`, widen the give cap, and harden the `--max-net` projection clamp that lets a
3rd same-side leg over-fill into an unpaired residual. The live-vs-backtest gap is MOSTLY irreducible
latency — the box ceiling is set by queue position — so the realistic target is bounding the strand,
not preventing it. Expected: cut the strand drag from ~−6c/box (toxic-strand share) toward the
bounded-disposal floor of ~−10c/strand instead of ~−50c, i.e. roughly +1.5…+3c/box across all boxes
once strands are capped, but ZERO of it is a free completion — every fix is loss-mitigation.**

This is the COMPLETION/EXECUTION follow-up that BOX_ADVERSE_OPEN.md (commit 8be459b) pointed to: it
proved toxicity is invisible at open (OOS AUC 0.56) and that the LIVE 31% vs BACKTEST 5.7% toxic gap
lives in execution. This study pins WHERE in execution, and STRESS-tests every completion lever
against the known-optimistic fill model.

---

## Data window, N, costs, method

- **Live (the execution-gap truth):** every commit of `origin/live-state`, days **2026-06-13/14**,
  `kalshi_fees_btc15m.jsonl` (raw fills, dedup by `trade_id` → **771 fills**) + `kalshi_winrec_…jsonl`
  (per-window: `legging_gap_s`, `n_taker/n_maker`, `n_dispose_cross`, costs; dedup by `ws` → **61
  winrecs**). Settle via Kalshi API `markets/<ticker>.result`. **96 settled markets**, ~48/day.
  P&L per box = `(payout − cost)/n_boxes`, settle-adjusted.
- **Tape (SCREEN, for N):** `hist_kalshi_btc15m.parquet` × `trades_kalshi_btc15m.parquet`,
  **311 windows w/ book+tape, span 2026-05-25 .. 2026-06-13**, reconstructed via
  `box_policy_ab.window_fills` with the deployed pair-gate (`depth≥33k, k≤10, |sig|<10`). Boxes built
  always-pair (`--max-net 1`). **469 pair-gated boxes** at q0=0.
- **Costs:** resting maker legs fee-free (post-only). A crossing/disposal pays the Kalshi taker fee
  `ceil(M·P·(1−P)·100)/100`, M=0.07.
- **TOXIC ≡ box P&L < 0.** Script: `box_completion_exec.py` (self-contained; walks live-state, reads
  the two parquets).
- **Backtests SCREEN.** Live N is small (~tens/day); leaned on tape for N, live for the execution gap.

---

## 1. CHARACTERIZE the second-leg completion

### The toxicity is STRANDS, not completed-but-toxic boxes — the live decomposition flips the tape's

| live population | N | toxic | mean c/box | dollar P&L |
|---|---|---|---|---|
| ALL settled markets | 96 | **31%** | −5.5c | **−$5.18** (~−$2.6/day) |
| BALANCED (ny==nn) | 75 | 14 toxic | −0.0c | **+$0.81** (net positive!) |
| **STRANDED (ny≠nn)** | **21** | **16 toxic** | **−25.1c** | **−$5.99** |

**The entire net loss is the stranded boxes.** Balanced (completed) boxes are net-POSITIVE live.
This DIFFERS from BOX_ADVERSE_OPEN's q0=0 tape (which found ~90% of toxicity in *completed* boxes) —
because the q0=0 reconstruction almost never strands (1.3%), so on the tape the only toxicity left is
completed-but-toxic. **Live, the strand rate is 21.9%** (matches q0≈8000 tape; see §2), and the
stranded odd leg is the dominant cost. Strand share of toxic *count* = 53%; of toxic *dollars* ≈ 100%.

### The legging gap does NOT drive live toxicity — the strand is the killer, and it has a tiny gap

| | N | gap median | gap mean | gap p90 |
|---|---|---|---|---|
| CLEAN boxes | 66 | 3.7s | 21.2s | 57.6s |
| TOXIC boxes | 28 | **2.5s** | 5.6s | 7.2s |

Toxic boxes have a **shorter** legging gap than clean ones (the hypothesized "long gap → toxic" is
absent live; OLS slope only +0.05c/box per second, corr +0.16, dominated by a −5.5c intercept).
Spot move during the gap is ~0bps for both clean and toxic (median 0.0, p90 ~2bps). **The gap-and-
spot-move-during-gap mechanism is NOT the live driver.** The strands fill FAST and then sit unpaired.

### What the toxic strands actually are: over-fill residuals that ride naked to settlement

Inspecting the worst strands' fill sequences (all `taker=0`, settled worthless ≈ −50…−61c):

```
130445-45  YES@.36(14s) + NO@.62(16s)=box, then 2nd NO@.63(17s) → net −1 NO stranded  → −61c
131815-15  NO@.50(19s)  + YES@.50(20s)=box, then 2nd YES@.50(22s)→ net +1 YES stranded → −50c
131745-45  NO@.56 + YES@.43 = box, then 2nd NO@.60 (3s later)    → net −1 NO stranded  → −59c
```

**14 of 16 toxic strands are OVER-FILLS** (a clean box forms, then a 3rd same-side maker leg fills
1–3s later with no partner); 2 never paired at all. This is exactly the `--max-net 1` race the trader
code flags at line 1601 ("two NO rungs both resting at net=0 each passed the old filled-only clamp,
then both filled ~1s apart → net −2"). The resting-order *projection* clamp (kalshi_trader.py
1599–1610) is meant to stop this but these windows are 06-13/14, i.e. it is still leaking. The odd
residual then rides naked to settlement because the dispose-cross did not complete it (taker=0 on the
catastrophic ones; one window even fired `n_dispose_cross=47×` and still lost −51c — give-cap thrash).

### c/box lost to a strand
A stranded odd leg averages **−25c/box** live (and −50…−61c on 1–2-contract boxes, where the odd
leg is the whole box). Small boxes (max(ny,nn)≤2) account for **−$3.8 of the −$6.5 toxic-strand
dollars** — the tiny boxes have no completed partner to dilute the naked leg.

---

## 2. EXPLAIN the live-31% vs backtest-5.7% gap — it is QUEUE POSITION (cause (b)), not (a) or (c)

The q0=0 reconstruction fills the completing leg at the **same-minute resting touch** and almost
never strands. Two independent tape experiments reproduce the live numbers by injecting realism:

**(i) Re-price the completing leg at the MOVED touch g minutes after the open leg fills** (the
post-open price-path cost the q0=0 model omits):

| assumed legging gap | N | toxic | mean c/box | strand |
|---|---|---|---|---|
| g=0 (the optimistic backtest) | 469 | **8.1%** | +0.52c | 22% |
| g=1 min | 469 | 49.3% | −0.01c | 31% |
| g=2 min | 469 | 56.1% | −2.95c | 35% |

**(ii) Queue-depth sensitivity (q0 = contracts ahead of us at the touch):**

| q0 | boxes | strand | toxic | mean c/box |
|---|---|---|---|---|
| 0 (front-of-queue) | 469 | 1.3% | 14.9% | −0.69c |
| 2000 | 415 | 8.9% | 53.0% | −6.39c |
| **8000** | 297 | **21.9%** | 73.7% | −12.43c |
| 15000 | 159 | 41.5% | 83.0% | −19.28c |

**The LIVE strand rate is 21.9% — it lands exactly on the q0≈8000 row.** We are deep in the queue, not
front. The mechanism (FINGERPRINT.md): the dominant ladder-MM reprices on a ~1.2s mechanical heartbeat
and ladders the whole book at fixed size; when a taker crosses, it fills the resting size AHEAD of us
first, so our completing leg is passed over and strands.

**Root-cause ranking, with evidence:**
- **(b) live latency / queue position — DOMINANT.** The strand rate is a clean monotone function of q0
  and live sits at q0≈8000. The backtest's q0=0 is the entire 5.7%→31% gap.
- **(a) optimistic fill model — the SAME thing, expressed as a model flaw.** q0=0 *is* the optimism;
  the live_gate.py header already records "the tape/shadow A/B mis-modeled strands 4×: predicted 13%,
  live was 48%." Confirmed: do NOT trust any lever that only looks good at q0=0.
- **(c) over-aggressive chasing — NOT the driver.** Live toxic boxes have near-zero taker fills
  (mean 0.37 takers/box) and ~0bps spot move during the gap; the chase ramp is barely firing on the
  losers. The losses are NAKED-HOLD strands, not over-chased completions.

---

## 3. COMPLETION-LEVER TESTS (offline tape; STRESSED against the optimistic model)

**LEVER A — simultaneous / paired quoting (shrink the gap to ~0).** This is the g=0 / q0=0 row: 8%
toxic, +0.5c/box. It is the upper bound and **it is exactly what the optimistic model already
assumes** — live queue position caps it. Quoting both legs from t0 does not move us up the queue, so
the realized benefit is small. **Do NOT bank the g=0 number.** Verdict: marginal; helps only insofar
as it gets the second leg quoted *earlier* (queue priority), which is Lever C.

**LEVER B — smarter chase (complete toward the moved touch only when the move is small; else
strand-and-dispose).** Tested at g=2min over a sweep of the max-spot-move-to-still-chase threshold:

| policy | N | mean c/box | toxic% |
|---|---|---|---|
| ALWAYS CHASE (deployed) | 469 | −2.95c | 56.1 |
| chase if move≤20bps | 469 | −2.83c | 55.9 |
| chase if move≤12bps | 469 | −2.86c | 55.7 |
| NEVER chase (strand+dispose) | 469 | −2.60c | 52.2 |

**The chase-vs-hold threshold barely matters** (all within ~0.4c), and "never chase, always
strand-and-dispose" is marginally BEST on the tape. This says: when completion would lock a loss, a
bounded disposal beats chasing into the move — but the effect is small because the tape rarely strands.
A spot-momentum gate on chase-vs-hold is a real-but-thin lever; the bigger prize is making the
disposal itself reliable (Lever C). Stress note: at q0=0 the tape under-strands, so this lever's
upside is *understated* — live, where strands are 22%, bounding the disposal matters far more.

**LEVER C — reliable strand DISPOSAL + max-net hardening (the live-evidenced fix).** The live
catastrophe is the odd leg riding naked to settlement (−50c) when a bounded cross (≈−10c) was
available, and the over-fill that created the odd leg. On the tape, disposing at a give cap vs holding
naked moves the 6 tape strands little (too few to matter offline) — but live this is the −$6 of −$5
total P&L. The deployable change is operational, not a tape-tunable: (1) cross the residual reliably
within a short age, (2) widen the give cap so a −50c naked hold is never preferred to a −10…−20c cross,
(3) stop the residual forming via a hard projection clamp on resting same-side orders.

---

## 4. RECOMMENDED TRADER CHANGES (flags / params / code) + expected impact + live A/B

All recommendations rest on the trader's OWN observables (net residual, leg age, give budget, depth,
spot move) — deployable now. A future read-only external lead signal plugs in at the chase-vs-hold
decision (Lever B), noted below.

### C1 — Complete the residual FASTER and with a wider give cap (primary, biggest live $)
The −50c strands are odd legs that never crossed. The dispose-cross only fires at `age ≥
--dispose-cross-s` (default **90s**) and is give-capped at `--chase-max-give` (2c) mid-window /
`--close-max-give` (4c) near close, with a hard `--dispose-max-give` HOLD fallback.

- **`--dispose-cross-s 90 → 25`.** Cross a still-unpaired residual at 25s instead of 90s. A 1-contract
  odd leg has no completing partner coming (the box already formed); waiting 90s only lets the touch
  run further. Live strands fill the box in <3s then sit — the 90s wait is pure exposure.
- **`--dispose-max-give 0.10 → 0.25` and `--chase-max-give 0.02 → 0.06`.** The HOLD-CAPPED fallback
  (line 1729) currently rides a leg naked rather than cross beyond a 10c lock loss — but a naked hold
  is a −50c expected loss, so a bounded −25c cross is strictly better than holding for the typical
  longshot residual. Raise the cap so disposal is preferred to the catastrophic naked hold.
- **Expected:** converts the −25c-avg strand toward a bounded ~−10…−15c disposal. With ~22% strand
  rate × (≈−25c → ≈−12c) ≈ **+2.8c/box** across all boxes (loss mitigation, not new edge). Stress:
  this number is from LIVE strand economics, not the optimistic tape — robust to the q0 problem.

### C2 — Harden the `--max-net` projection clamp (stop the over-fill that creates the residual)
14/16 toxic strands are over-fills: a 3rd same-side maker leg fills 1–3s after the box completes. The
projection clamp (lines 1599–1611) counts resting + pending-cancel same-side orders, but residuals
still form on 06-13/14.

- **Code:** after a box completes (net returns to 0), **immediately cancel ALL resting same-side
  orders before re-arming the opener**, and treat any same-side order whose cancel is unconfirmed as
  live (already partially done via `pending_cancel`, but the race shows a gap). Add a short
  post-completion quote freeze (e.g. 1.5s, one MM heartbeat) on the side that just over-filled.
- **Expected:** removes the over-fill class (14 of 16 toxic strands). At ~16 toxic strands / 96 mkt,
  eliminating the over-fill residual is worth roughly the strand dollar loss it prevents — order
  **+3…+5c/box** if combined with C1 catching the few genuine strands. The single highest-leverage
  code change; it attacks the residual at the source rather than disposing it.

### C3 — Chase-vs-hold gate on the trader's own spot move (thin, deploy after C1/C2)
At the chase ramp (lines 1626–1631) and the dispose-cross (line 1696), condition the COMPLETE-by-cross
on the spot move since the open leg filled (already in `ctx.spot`/`sig`): **chase toward the moved
touch only when `|spot move over the gap| ≤ ~15bps`; otherwise strand-and-dispose flat** (a bounded
loss beats completing into a confirmed run). Tape says this is worth ~0.3c and "never chase into a big
move" is marginally best. **This is where a future READ-ONLY external lead signal plugs in** (a leading
venue's prob / spot momentum): replace the trader's own lagged spot move with the lead signal to decide
chase-vs-hold — but the own-spot-move version is deployable now and captures most of the thin edge.

### Live A/B plan
- **Arm:** C1 (`--dispose-cross-s 25 --dispose-max-give 0.25 --chase-max-give 0.06`) + C2 (post-
  completion same-side cancel/freeze) on; control = current params. Alternate by window (even/odd ws)
  to balance regime.
- **Primary metric:** strand rate (target <10%, gate (a) in live_gate.py) and per-stranded-window
  realized c (target −10…−15c, not −25…−50c). **Secondary:** total c (must not fall — net-of-volume).
- **N:** live_gate.py needs ~50–100 windows/arm (~2–4 days) for confidence; the strand rate moves fast
  (per-window), so a directional read on strand rate comes in ~1 day.
- **Kill criterion:** if total c/day drops (the cross fees on completed boxes outweigh the strand
  savings) or strand rate doesn't fall, revert. Watch the −51c/47×-cross thrash window — cap re-cross
  attempts per window.

---

## Honest bottom line

The live-vs-backtest toxicity gap is **mostly irreducible latency / queue position** — we are at
q0≈8000 behind the 1.2s mechanical ladder-MM, and that sets the box ceiling. We cannot become front-
of-queue by quoting; the simultaneous-quoting upper bound (g=0, +0.5c) is exactly the optimism we can't
realize. **What IS fixable is the consequence:** stop the over-fill residual (C2) and, when a leg does
strand, dispose it at a bounded loss instead of riding it naked to −50c (C1). That is loss-mitigation,
not new edge — but it is the −$6/−$5 of the live P&L, the dominant remaining $/day lever. Do NOT bank
any lever that only looks good at q0=0; every recommendation here is grounded in the LIVE strand
economics, which the optimistic tape understates by ~4×.

*Backtests SCREEN (q0=0 / q0-sensitivity, 311 windows, 469 boxes). Live = 96 settled markets, 771
fills, 61 winrecs, days 2026-06-13/14. Costs: maker fee-free, taker M=0.07.*
