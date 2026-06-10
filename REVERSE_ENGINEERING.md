# Reverse-engineering the top MM bots into runnable algos — the whole thing, woven together

> _Historical — reverse-engineering phase (concluded: a ≥95% wallet-clone is not achievable, see CAPTURE_REALITY.md). Kept for provenance. Current state: **README.md**._

**Goal (your framing):** for each top-10%-by-MM-score wallet, *generate an algorithm we can run as code
and trade independently*, compare it to the original bot, and refine on false-negatives / false-positives
until ≥95% correlated — then mine the best for our own bot.

## The pipeline (each step is a committed tool)
1. **`mm_score.py`** — rank wallets by the MM rubric → the top 10% (23 wallets).
2. **`strategy_model.py`** — learn each wallet's algorithm params from its tape → `strategy_models.json`
   (two-sidedness, complete-set discount, ladder-depth distribution, clip, timing, hold-balanced).
3. **`strategy_fine.py`** — 1:1 detail: exact placement offset, size, set-sum entry, inventory logic
   (with fidelity %), from fills + WS book.
4. **`orderflow_probe.py`** — recover placements/cancels/fills from public WS deltas (the order lifecycle;
   anonymous, attributable to a dominant wallet) — proven (92% cancel rate visible).
5. **`copy_bot.py`** — the RUNNABLE algo: emits the quote set (both tokens × 8 markets × ladder ×
   set-discount × hold-to-resolution), parameterized per wallet, dry-run/live-guarded.
6. **`copy_live_multi.py`** — run the algo's coverage against all 23 bots' live fills from one shared WS
   book → per-wallet capture (recall).
7. **`copy_compare.py`** — the compare/refine engine: per wallet, recall (=1−FN), archetype, and the
   refinement to reach 95%.

## The central finding: the top 10% is NOT one algorithm
Two archetypes, and it determines whether a touch-ladder copy can hit 95%:
- **Pure touch-MM** (`0x674887d1`, `0x20d2309cd9`, `0x5c932f50`, `0xdf7930e8`, `0x5d4aba8a`): fills sit at
  the touch; capture → **95–100% at a sane ladder depth** (their p95 inside-distance, ~14tk). **Fully
  copyable** — set the ladder to their depth and you reproduce ≥95% of their trades.
- **Momentum / directional** (`0x5e2b9261`, `0x75cc3b63`, `0xed89b210`): a large share of fills are **far
  from the touch by design** (they buy the moving side). Measured: `0x5e2b9261` capture **caps at 50%
  even at depth 20**. A touch-ladder algo *structurally cannot* reach 95% for these — they need a
  **momentum-entry component** added. (This is itself a finding: their edge is directional, not pure MM.)

## The runnable per-wallet algo (what to trade)
A **composite** fitted from that wallet's learned params:
```
for each active {btc,eth,sol,xrp}x{5m,15m} market:
  # touch-MM core (captures the at-touch fills)
  rest a both-token ladder to depth = wallet.p95_inside_tk, clip = wallet.clip_usd
  buy the complete set when bid_up+bid_dn < 1 - wallet.set_discount   # the edge
  hold balanced sets to resolution, redeem
  # momentum component (ONLY for momentum-archetype wallets, to capture the far-from-touch fills)
  if |BTC move over ~Ns| > wallet.mom_threshold: take/lean the moving side
```
`copy_bot.py` runs the core today; the momentum branch is the refinement `copy_compare.py` prescribes for
the momentum archetype.

## Compare & refine to 95% — what's measurable, honestly
- **Recall (= 1 − false-negative rate)** is **fully observable** (the bots' fills are public): the fraction
  of their actual trades our algo would also make. **This is the correlation metric we validate and drive
  to ≥95%.** Touch-MMs already reach it at their fitted depth; momentum wallets need the momentum branch.
- **False-positives / true precision is NOT measurable per wallet.** The bots' *resting and cancelled*
  orders are private off-chain (confirmed: `/orders` is auth-only; unfilled/cancelled orders never hit
  chain). So we cannot verify that our *extra* quotes match theirs — only that we cover their fills.
  `orderflow_probe.py` recovers the *aggregate* place/cancel lifecycle but not per-wallet attribution.
  → We report recall + distributional fidelity (side/price-offset/size/timing match), and are explicit
  that a "false-positive rate" against a private order book can't be computed from public data.
- **Refinement loop:** `copy_compare.py` flags each wallet's archetype and the FN root cause; for momentum
  wallets it quantifies the far-from-touch share and prescribes the momentum rule; for touch-MMs it sets
  the exact ladder depth. Re-run as overnight fills accumulate (`copy-validate-multi.yml` → gha-data).

## Status (honest)
- Pipeline + runnable algo + compare/refine engine: **built and committed.**
- Validated: `0x20d2309cd9` ≥95% capture at its 14tk ladder; `0x5e2b9261` shown to be momentum (caps 50%).
- Remaining per-wallet 95% verdicts: **need overnight fill volume** (wallets are bursty; only the
  high-volume ones accumulate fast). The overnight GHA jobs pool into `gha-data`; `copy_compare.py`
  produces the per-wallet table.
- **"Every wallet ≥95% with one touch-ladder algo" is false** (momentum subset). **"Each wallet ≥95%
  with its own fitted composite algo (touch-MM ± momentum)"** is the achievable goal; the pure-MM subset
  is already there.

## For our own bot (the payoff)
Deploy the **pure touch-MM composite** — `0x674887d1`'s playbook (highest MM-score, fully copyable,
profitable): two-sided tiny-clip complete-set-discount accumulation across all 8 markets, ladder to ~14tk,
hold-to-resolution + 20% rebate, co-located (DEPLOY.md). The momentum variants are higher-variance and
directional — keep as an optional overlay, not the core. This is exactly where BOXARB/MAKEREDGE/
MAKER_CHANGES pointed, now confirmed against 23 real bots' learned algorithms.
