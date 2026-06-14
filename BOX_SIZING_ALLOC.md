# BOX_SIZING_ALLOC — growth-optimal sizing & capital allocation across the Kalshi box book

**Verdict (one line): The growth-optimal size is the SMALLEST tradeable unit — 1 contract/box — and
even that does not compound, because on the LIVE distribution the per-box mean is NEGATIVE
(−2.1c/box post-fix, −7.3c/box pre-fix). The clean paired edge (+0.69c/box) divided by the bounded
disposal cost (−15c) sets a BREAK-EVEN strand rate of ~4–5%; live runs at 18–31%. The book is +EV
ONLY if the completion fixes drive the live strand rate below ~4–5% — a regime the live tape has
never shown. Therefore the honest "$/day at $X bankroll" answer is: do NOT size up at any bankroll
until a live re-test confirms strand <~5%. IF (and only if) it does, the book saturates at
~$500 working capital and makes a realistic ~$2–8/day gross, full stop — a fill-rate-capped,
single-account, low-hundreds-of-dollars-of-capacity strategy, not a scalable one.**

This is the deliberately brutal read the brief demanded: size for the LIVE distribution (31% toxic),
not the optimistic q0=0 backtest (5.7%). Every number below is reproducible via `box_sizing_alloc.py`.

---

## Inputs — LIVE-validated vs SCREENED (tagged)

| input | value | source | status |
|---|---|---|---|
| 15M clean/paired edge | **+0.69c/box** | AUDIT_EDGE.md (62 live boxes), matches backtest | **LIVE** |
| 15M toxic share (per box, all settled) | **31%** | BOX_COMPLETION_EXEC.md (96 settled mkts) | **LIVE** |
| 15M strand rate (per window) | **21.9%** (=q0≈8000) | BOX_COMPLETION_EXEC.md | **LIVE** |
| 15M toxic loss pre-fix | **−25c/box** avg (−50…−61c tiny boxes) | live winrec strands | **LIVE** |
| 15M toxic loss post-fix (bounded) | **−15c** typ / **−25c** worst (give-cap 0.25) | BOX_DISPOSAL_EV + C1/C2 | **EXPECTED** |
| 15M fill ceiling | **~6–10 contracts/window** | live fees (6 c/win obs) + REST $21 min | **LIVE** |
| 15M windows/day | **96** | series mechanics | **LIVE** |
| HOURLY (KXBTCD) clean edge | **+1.0c** deploy (+1.5c median screen) | KALSHI_TENOR_EXPANSION.md (20 hrs) | **SCREEN** |
| HOURLY toxic share | **12% ASSUMED** (screen <10%, haircut up for queue) | no live data | **ASSUMED** |
| HOURLY toxic loss | **−20c ASSUMED** (longer tenor, bounded class) | — | **ASSUMED** |
| HOURLY fill ceiling | **~200 contracts/window** (886k flow, queue-haircut) | screen | **SCREEN** |
| HOURLY windows/day | **24** | series mechanics | **SCREEN** |
| Daily loss-limit (shared, 1 account) | **$12** | SIZING.md Stage-A | config |

> KXBTCD_DEPLOY.md (the sibling agent's queue-haircut pin) had **not landed** on the branch at write
> time. Hourly economics here use the +1.5c/24-window screen with an explicit haircut (p_tox=12%,
> tox=−20c). If KXBTCD_DEPLOY lands with tighter numbers, re-run with those.

---

## 1–2. Per-box P&L mixture — mean & variance

Per-box P&L modeled as a two-point mixture: clean box `+c` w.p. `(1−p_tox)`, toxic strand `−L` w.p.
`p_tox`. Mean `μ = (1−p)c − pL`; variance `σ² = (1−p)c² + pL² − μ²`.

| scenario | p_tox | clean | tox | **mean (c/box)** | std (c/box) |
|---|---|---|---|---|---|
| 15M LIVE pre-fix (brutal bar) | 31% | +0.69 | −25 | **−7.27** | 11.9 |
| 15M post-fix (expected) | 18% | +0.69 | −15 | **−2.13** | 6.0 |
| HOURLY KXBTCD (screen+haircut) | 12% | +1.00 | −20 | **−1.52** | 6.8 |

**The fat negative tail dominates both mean and variance.** The clean edge is a sub-cent sliver; one
toxic strand erases ~20–35 clean boxes. The variance is ~entirely the toxic-tail term — exactly the
"binary box is NOT simple Kelly, it's a near-arb with a toxic tail" structure the brief flagged.

---

## 3. Kelly / fractional sizing — growth-optimal contracts/box

The growth objective is `E[log(1 + n·X/B)]` maximized over integer `n`, capped by (a) the fill-rate
ceiling, (b) the loss-limit size cap `N_max = ⌊L/(1.645·σ_day)⌋`, (c) bankroll/log-growth.

| bankroll | growth-opt n\* | fill cap | loss-limit cap | **binding constraint** |
|---|---|---|---|---|
| $10 | **1** | 10 | 12 | **log-growth (μ<0 → minimize stake)** |
| $100 | **1** | 10 | 12 | **log-growth (μ<0 → minimize stake)** |
| $1,000 | **1** | 10 | 12 | **log-growth (μ<0 → minimize stake)** |

**Because the live mean is negative, the log-growth-optimal stake is the floor (1, i.e. "as small as
possible / don't play").** Kelly on a negative-mean bet is f\*=0. The fill ceiling (10) and the
loss-limit (12) are NON-binding at the live distribution — they would only bind if the edge were
positive. **At a hypothetical positive edge (target regime, §6), the fill-rate ceiling of ~10
contracts/window is the binding constraint at every bankroll ≥ ~$20** — you cannot deploy more than
~10 contracts/window into the 15M taker-print book regardless of bankroll. So: bankroll binds below
~$20, fill-rate binds above it; the loss-limit never binds (SIZING.md confirmed 0% breach at Stage-A).

---

## 4. Allocation across the two markets + realistic $/day + saturation

Settlements are disjoint (15M at :00/:15/:30/:45, hourly at :00 only on a separate series/book), so
the two are **additive return streams, not competing for flow**. The shared constraints are the
single account and the $12 loss-limit (which does not bind). Optimal split = run each market at its
own fill ceiling once bankroll covers its per-window working capital.

**At the live (negative) distribution, $/day at every bankroll is NEGATIVE** (15M ≈ −$20/day at
ceiling; hourly ≈ −$73/day at ceiling) — i.e. the honest realized expectation is a LOSS, which is why
the bot is OFF. The numbers below are therefore presented as the **conditional (IF the fixes work)**
saturation economics, alongside the live-realistic verdict.

**Working capital to saturate** (contracts in flight × ~$1/box × settlement-lag buffer):
- 15M saturates at **~$100** working capital (matches the doc "saturates ~$100"). More bankroll adds
  $0/day on 15M — the taker-print fill ceiling (~10 c/win) is hit.
- Hourly needs **~$400** working capital to run its ~200 c/window ceiling.
- **The two-market book SATURATES at ~$500.** Beyond that, more bankroll adds nothing (fill-rate /
  queue-position capped — you cannot push $1M into a $500-capacity book).

**Conditional $/day by bankroll** (using the BEST-realistic post-fix case, §6: p_tox=10%/tox=−12c
→ 15M still −0.6c/box; and the TARGET case p_tox=4% → 15M +0.18c/box, +$1.75/day at ceiling):

| bankroll | 15M size | 15M $/day (target case) | +hourly | combined $/day | binding |
|---|---|---|---|---|---|
| $10 | ~5 c/win | ~+$0.9 | — (no capital) | **~+$0.9** | bankroll |
| $100 | 10 c/win (ceiling) | ~+$1.8 | — (hourly needs ~$400) | **~+$1.8** | 15M fill ceiling |
| $1,000 | 10 c/win (ceiling) | ~+$1.8 | +200 c/win | **~+$8–10** (15M +$1.8, hourly +$6–8) | hourly fill ceiling |

- Adding the hourly does NOT raise $/day proportionally at small bankroll — it only kicks in once
  bankroll clears ~$400 of dedicated working capital. Below that, the $/day is purely the 15M ceiling.
- **Steady-state (saturation ≈ $500–1,000): ~$2–10/day gross IF strand <~5%.** This is the honest
  "how much can this make" ceiling. It is a low-hundreds-of-dollars-of-capacity, single-account,
  ~$2–10/day strategy — NOT scalable.

---

## 5. Risk of ruin

MC over 60 compounding days at the growth-opt size (ruin = bankroll < 10% of start):

| bankroll | size | P(ruin, 60d) — LIVE dist | median end | p5 end | maxDD p95 |
|---|---|---|---|---|---|
| $10 | 5 c/box | **100%** (μ<0 bleeds out) | $0 | $0 | >100% |
| $100 | 10 c/box | **100%** (μ<0 bleeds out) | $0 | $0 | >100% |
| $1,000 | 10 c/box | 0% (slow bleed survives 60d on size) | $289 | $281 | 72% |

**On the live negative-mean distribution, small bankrolls are RUINED with certainty** — not from a
single tail event (the loss is bounded −25c by the give-cap) but from the negative drift. The
bounded tail makes the loss a slow bleed, not a blow-up; the loss-limit caps daily damage at $12 but
cannot turn a negative edge positive. **At a hypothetical positive edge with 1-contract sizing,
P(ruin) is <2%** (SIZING.md/Schlesinger) because the tail is bounded and the stake is tiny — the
recommended size (1 contract / fill-ceiling-limited) keeps ruin negligible the moment the edge is
genuinely positive. The danger is never over-sizing the tail; it is trading a negative edge at all.

---

## 6. Break-even — the load-bearing number

Mean = 0 at `p_tox* = c/(c+L)`:

| scenario | clean | tox | **break-even p_tox** | live p_tox | status |
|---|---|---|---|---|---|
| 15M pre-fix | +0.69 | −25 | **2.7%** | 31% | NEGATIVE |
| 15M post-fix | +0.69 | −15 | **4.4%** | 18% (exp) | NEGATIVE |
| HOURLY | +1.00 | −20 | **4.8%** | 12% (assumed) | NEGATIVE |

This reproduces AUDIT_EDGE.md exactly ("break-even needs strand_rate < ~4.3%"). **The box book is
+EV only below ~4–5% strand/toxic rate.** The completion fixes (give-cap 0.25, post-complete-freeze
1.5s, C1+C2) are loss-MITIGATION — they bound the toxic loss and remove the over-fill class (14/16
toxic strands), targeting strand <10% and disposal −12c. Even the BEST-realistic post-fix case
(p_tox=10%, tox=−12c) is still −0.58c/box (−$5.6/day at ceiling); only the TARGET case (p_tox=4%,
tox=−12c) flips positive (+0.18c/box, +$1.75/day). **The entire viability of the book rests on the
unproven hypothesis that the fixes cut the live strand rate by ~4–6× (18–31% → <5%).**

---

## Recommendation

1. **Size:** 1 contract/box (the floor). Do NOT scale. The growth-optimal stake on the live
   distribution is zero; 1 contract is the minimum live re-test unit.
2. **Gate before any scale-up:** run the C1+C2 fixes live and require `live_gate.py` to show strand
   rate **<5%** and per-stranded-window realized **>−12c** over ~50–100 windows (~2–4 days), AND net
   c/day ≥ 0. This is the GO bar. The current pre-fix 31% is ~6× over the bar.
3. **IF the gate passes:** size up to the 15M fill ceiling (~10 c/window) — that, not bankroll, is
   the binding constraint above ~$20. Add the hourly only once working capital clears ~$400.
4. **Realistic ceiling (conditional on the gate):** book saturates at **~$500 working capital**,
   steady-state **~$2–10/day gross**. More bankroll adds nothing past saturation (fill-rate capped).
5. **Risk of ruin** at 1-contract sizing with the bounded −25c tail: **negligible (<2%) once the edge
   is positive**; **100% if traded at the current negative edge**. The bounded give-cap means ruin
   (if it comes) is a slow drift, not a blow-up — but a negative edge is a negative edge.

*Reproduce: `python box_sizing_alloc.py`. Live = 96 settled mkts / 771 fills / 61 winrecs (origin/
live-state, 2026-06-13/14). Hourly = screen (20 hrs) + stated haircut. Backtests SCREEN; the LIVE
strand rate is the binding truth.*
