# LIVE_EXPANSION.md — which assets should the live bot trade, and how

**Question:** the live Kalshi MM bot (`kalshi_trader.py` via `.github/workflows/live.yml`, always-on
on `main`) trades ONLY `btc` 15m markets today. The shadow A/B (`gha-data` branch) has 33 UTC days
of per-asset forward data for btc/eth/sol/xrp. Should the live bot expand, to which assets, and how
— without breaking the risk rails (`$5` max notional, `$6` sticky loss-limit, per-asset kill
sentinel, singleton concurrency)?

**Evidence base:** `per_asset_edge.py` (new, this branch) — per-asset forward stats for the two
32-day shadow-A/B winner arms (`av_stoikov` = `--gate as`, `mo_size` = `--size-mode markout`) vs
baseline, plus `MM_FINGERPRINT.md`'s maker-competition census (last 14 days, same branch).

## 1. The numbers (real run, `python per_asset_edge.py`, gha-data ref `afea1fe4`)

10,975 de-duped windows across **33 UTC days** (2026-06-10 → 2026-07-12; the task brief said "32
days," the branch has picked up one more day since), ~2,740-2,746 windows/asset (BTC/ETH/SOL
slightly ahead of XRP — a handful of XRP windows didn't resolve).

```
=== arm: av_stoikov  (vs baseline; paired per-window delta, CENTS/window) ===
 asset  n win  n days  mean Δ/win   day-t    days+  ABS net/win  mean fills  base fills
   btc   2746      33      +8.979  +16.09    33/33      +33.440      588.82      478.61
   eth   2746      33      +1.983   +6.39    31/33       +5.049       73.69       54.24
   sol   2745      33      +0.658   +3.67    27/33       +1.679       25.56       19.06
   xrp   2738      33      +1.198   +5.33    27/33       +2.868       26.78       19.72

=== arm: mo_size  (vs baseline; paired per-window delta, CENTS/window) ===
 asset  n win  n days  mean Δ/win   day-t    days+  ABS net/win  mean fills  base fills
   btc   2746      33      +4.770  +16.96    33/33      +29.231      455.54      478.61
   eth   2746      33      +0.588   +6.19    30/33       +3.654       53.04       54.24
   sol   2745      33      +0.260   +2.92    21/33       +1.281       18.48       19.06
   xrp   2738      33      +0.287   +2.21    23/33       +1.956       19.05       19.72

=== per-asset window counts (baseline-resolved) ===
   btc: n_windows= 2746  n_days= 33
   eth: n_windows= 2746  n_days= 33
   sol: n_windows= 2745  n_days= 33
   xrp: n_windows= 2738  n_days= 33

=== VERDICT: EXPAND / HOLD (script's mechanical bar: day-t>=2, days+>=60%, ABS net/win>0, mean fills/win>=1) ===
   BTC: EXPAND — av_stoikov (t=+16.09, 33/33, abs=+33.440)  mo_size (t=+16.96, 33/33, abs=+29.231)
   ETH: EXPAND — av_stoikov (t=+6.39,  31/33, abs=+5.049)   mo_size (t=+6.19,  30/33, abs=+3.654)
   SOL: EXPAND — av_stoikov (t=+3.67,  27/33, abs=+1.679)   mo_size (t=+2.92,  21/33, abs=+1.281)
   XRP: EXPAND — av_stoikov (t=+5.33,  27/33, abs=+2.868)   mo_size (t=+2.21,  23/33, abs=+1.956)
```

All four assets mechanically clear the script's bar (day-clustered t >= 2, majority days-positive,
positive absolute P&L level — not just "less bad than baseline" — and fills that actually happen).
**But the bar clearing on all four is not itself the recommendation** — read the caveats below
before trusting the ranking at face value; the numbers themselves argue for a *staged*, not
uniform, expansion.

### Reading the strength gradient (this is the part the bar alone hides)

| asset | signal quality | notes |
|---|---|---|
| **btc** | strongest by ~5-8x on every axis | already live; the reference case |
| **eth** | clean, second-strongest | t=6.2-6.4, days+ 30-31/33 (91-94%) — nearly as consistent as btc |
| **xrp** | real but thinner | av_stoikov solid (t=5.3, 82%), but mo_size is the weakest-clearing arm anywhere (t=2.2, 70%) |
| **sol** | real but thinnest / least persistent | mo_size days+ = 21/33 = **64%**, barely above a coin flip on the "which days" axis despite t=2.92 |

`mo_size`'s days-positive fraction is the widest spread in the table (btc 100% → eth ~91% → xrp 70%
→ sol 64%). That is the signal a single pass/fail bar erases: sol and xrp's edge is real on
average but comes from fewer, larger days rather than a steady daily tailwind — more fragile to a
regime shift than btc/eth's edge.

### Units / scaling caveat (read before sizing anything)

`net` in the shadow data is **cents per window at the shadow strategy's `cap=50` contracts**
(`strategies.py` `Strat.cap` default) — matches the magnitude of the "+4.67c/win" style
comments already in `kalshi_trader.py`. The **live** bot posts `--post 1 --max-rungs 1`
(≈1-2 contracts/side per box, nowhere near cap=50). Scaling the shadow ABS net/win down by a rough
`1/10`–`1/5` factor (cap 50 → ~5-10 live-equivalent contracts) gives an order-of-magnitude estimate
of live per-window edge:

| asset | shadow ABS net/win (cap=50) | ~live-scaled estimate |
|---|---|---|
| btc | +33.4c | ~3.3–6.7c/window |
| eth | +5.0c  | ~0.5–1.0c/window |
| sol | +1.7c  | ~0.17–0.34c/window |
| xrp | +2.9c  | ~0.29–0.57c/window |

This is a **linear approximation, not a validated live number** — thin books (sol/xrp) don't
necessarily scale linearly with size (queue-depth effects), and there is zero live-fill history for
eth/sol/xrp to check it against. Treat the live-scaled column as "plausibly worth doing," not as a
P&L forecast.

## 2. MM_FINGERPRINT.md's competition read — the other half of the decision

`MM_FINGERPRINT.md` (last 14 days, same `gha-data` corpus) found:

- **btc**: one mechanical resident MM (unchanged for weeks), touch is ~92% small-lot — the
  condition our edge depends on is intact.
- **eth**: one stable ~90-lot ladder, mostly one-sided (two-sided ratio 0.08), TOB 8-12%.
  Real but thinner competition than btc — consistent with eth's numbers above (real edge,
  somewhat smaller).
- **sol**: the marginal 50-lot signature **disappeared entirely on 07-10/07-11** — effectively no
  resident ladder maker right now.
- **xrp**: **zero** qualifying maker signatures on all 14 days — nobody ladders this book.

**The trap:** "no competition" is not unambiguously good news. It cuts two ways:
1. *Bullish read*: less competition at the touch = more room for our quotes to be the best price,
   supporting the sol/xrp edge numbers above.
2. *Bearish read*: on btc/eth, a resident MM plausibly absorbs some of the toxic/informed flow
   before it reaches us. On sol/xrp, **there is no one else — any informed flow that shows up lands
   on us with nobody sharing the adverse-selection risk.** `MM_FINGERPRINT.md` says this explicitly
   for xrp: *"Thin competition, but also no MM absorbing toxicity."*

The shadow numbers for sol/xrp are measured over the full 33-day window; the "maker vanished"
finding is from the *trailing 14 days only*. That means part of sol's measured edge comes from a
regime (early June) that had more competition than sol has today — the forward-looking risk on
sol/xrp is **less validated by the trailing data** than the headline t-stat suggests, in either
direction (competition returning would compress the edge; its current absence could make recent
weeks better OR could mean recent weeks are the first exposure to real informed-flow risk with no
shadow precedent, since the shadow sim doesn't model a live order's queue interaction with an
actual informed counterparty the way real fills would).

## 3. Recommendation: staged expansion, not "flip all four"

1. **Wave 1 — add ETH now.** Cleanest secondary signal (t=6.2-6.4, 91-94% days-positive), real but
   not-yet-thin competition per the fingerprint, smallest behavioral gap from btc's already-live
   av_stoikov/mo_size dynamics. Lowest-risk first expansion.
2. **Wave 2 — SOL and XRP, staged, after Wave 1 has run long enough to sanity-check the shadow→live
   scaling assumption (§1) on a second asset (eth).** Both clear the mechanical bar, but: (a)
   `mo_size` days-positive is materially weaker (sol 64%, xrp 70%, vs btc/eth 91-100%), and (b)
   neither asset has a resident MM right now to share adverse-selection risk with us (§2). Bring
   them in one at a time, watch live fill-rate / markout / kill-sentinel trips for the first ~1-2
   weeks each before adding the next, rather than launching both simultaneously.
3. Do **not** launch all four simultaneously on day one — see the bankroll math below for why, and
   because a correlated failure mode (e.g. a shared BTC-led market shock hitting all four assets'
   inventory in the same direction at once) is untested; the shadow data treats each asset's paired
   delta independently but real fills on a single account are not necessarily independent risk.

`live.yml.proposed` (this branch) is deliberately written so the operator can apply it with the
matrix trimmed to `[btc, eth]` first and extend it later — see the comment at the top of the matrix
key in that file.

## 4. The live.yml changes this requires (implemented in `live.yml.proposed`)

`live.yml.proposed` is a new file on this branch — **it is not applied**; the operator reviews it
and, if they agree, copies it over `.github/workflows/live.yml` on `main` (still gated by
`LIVE_SWITCH` + secrets as always — adopting the file does not itself start any new trading).

### a. Concurrency: per-workflow singleton → per-asset groups
The current workflow's `concurrency: group: live-trade-singleton` is **workflow-scoped**: expanding
to a matrix under that one group would *serialize* all four assets onto a single runner slot one at
a time, defeating parallel multi-asset trading. Fixed by moving concurrency to the `trade` job and
templating the group name on the matrix value:

```yaml
jobs:
  trade:
    strategy:
      fail-fast: false
      matrix:
        asset: [btc, eth, sol, xrp]      # trim per the staged rollout above
    concurrency:
      group: live-trade-${{ matrix.asset }}
      cancel-in-progress: false
```

This preserves the property that actually matters — **never two live bots on the same asset** —
while letting different assets run truly in parallel.

### b. LIVE_SWITCH is global; the loss-limit kill is per-asset. Is one global trip flipping all
four assets off desired? **No — recommend NOT.**

Today, a single-asset (btc-only) design makes this moot: the per-asset kill sentinel
(`.kalshi_killed_btc15m`) and the global `LIVE_SWITCH` are effectively the same scope. Expanding to
four assets under the *unmodified* logic would mean: **one asset's loss-limit trip writes
`LIVE_SWITCH=off`, which the "gate on the switch" step reads globally — silently stopping the other
three, profitable, untouched assets.** That is very likely not what the operator wants; a bad ETH
day should not halt a fine BTC day.

`live.yml.proposed` fixes this with a new **per-asset switch file**, `LIVE_SWITCH_<ASSET>` (e.g.
`LIVE_SWITCH_ETH`), checked alongside the existing global one:

- gate = `global LIVE_SWITCH == on` **AND** `LIVE_SWITCH_<ASSET> missing-or-on` **AND** no local kill
  sentinel this run.
- a loss-limit kill now flips only `LIVE_SWITCH_<ASSET>` off (committed, sticky, same
  retry/rebase-on-push-conflict pattern as the old global flip) — the other assets' switch files
  are untouched.
- the **global** `LIVE_SWITCH` remains the master "stop everything now" switch, operator-controlled,
  and is still the fast (<1 min) in-process flatten path via `REMOTE_SWITCH_URL` — unchanged on
  purpose, see the "known limitation" note in the proposed file (there is currently no per-asset
  fast-stop; that needs a `kalshi_trader.py` code change, out of scope for this new-files-only pass).
- missing `LIVE_SWITCH_<ASSET>` == "on" (backward compatible: applying this file with no per-asset
  files present behaves exactly like today for whichever assets are enabled).

### c. Self-chain: matrix fan-out trap

The existing self-chain step re-dispatches `live.yml` via `workflow_dispatch` at the end of each
run. Naively leaving that step inside a 4-way matrix means **each of the 4 legs independently
re-dispatches the same (4-asset) workflow** — 4 legs → 4 dispatches → 16 legs next cycle → 64 the
cycle after. `live.yml.proposed` fixes this by splitting the dispatch into a separate, non-matrixed
`chain` job (`needs: trade`, `if: always()`) that runs once after all four legs finish and fires
exactly one dispatch, gated only on the global switch. Wall-clock cadence is unchanged (~47
min/cycle, same as today) since the four legs run in parallel, not sequentially.

### d. Total notional at a $50 bankroll — does 4 assets fit?

Per-asset caps are unchanged: **$5 max notional, $6 sticky loss-limit** (from the live `kalshi_trader.py`
invocation flags — `SWITCH.md`'s "$3" mention is stale documentation, the actual flag is
`--loss-limit 6`).

```
n_assets   simultaneous notional ($5 × n)   worst-case simultaneous loss ($6 × n)   % of $50 bankroll (notional / loss)
   1              $5                                  $6                              10% / 12%
   2 (btc+eth)     $10                                 $12                              20% / 24%
   3               $15                                 $18                              30% / 36%
   4 (all)         $20                                 $24                              40% / 48%
```

At $50 bankroll, **all four assets simultaneously live is a real tail-risk number** — a
(low-probability, since each asset trips its OWN loss-limit independently, but not impossible if a
shared shock moves inventory the same direction across assets) worst case where all four hit their
loss-limit the same day is **48% of bankroll**, not a small number. Two assets (btc+eth, Wave 1) is
a much more comfortable 24% worst-case. This is the concrete argument for staging Wave 2
(sol/xrp) rather than enabling the full matrix on day one — it isn't only a signal-quality
argument (§1-§3), it's a bankroll-sizing one.

### e. Runner-minutes cost: from "always-on ×1" to "always-on ×4"

Each leg runs up to 2820s (47 min) and is kept continuously alive by the self-chain + 25-min cron
backstop — i.e. each enabled asset is independently **always-on** (~100% duty cycle), not just
"runs sometimes." Concretely:

- 1 asset (today): ~1 continuous runner ≈ 43,200 runner-minutes/month (30d × 1440 min/day).
- 4 assets (full matrix): ~4 continuous runners in parallel ≈ **~172,800 runner-minutes/month**,
  i.e. a straight **4×** of today's usage, not a fraction of it (the matrix legs run in parallel,
  they don't share the time budget).
- Cost: the repo is public (`SWITCH.md`), and GitHub Actions on standard hosted runners is
  free/unmetered for public repositories — so this is a **$0** line item *as of today's GitHub
  policy*, not a token-bucket concern. Two things worth the operator's own verification rather than
  taking on faith here: (1) that public-repo unmetered minutes policy hasn't changed, and (2) that a
  near-100%-duty-cycle Actions workflow at 4× scale doesn't trip GitHub's fair-use/abuse review for
  unusual sustained usage on a free tier (soft risk, not a hard blocker, but worth a periodic check
  of the Actions tab).
- Concurrent-job count: matrix(4) + chain(1) = 5 jobs/cycle, well under the standard 20-concurrent-job
  cap on free/pro accounts — not a binding constraint even at the full 4-asset matrix.

## 5. Summary

| asset | shadow verdict | competition (14d) | recommendation |
|---|---|---|---|
| btc | EXPAND (already live) | 1 resident MM, touch ~92% small-lot | keep as-is |
| eth | EXPAND, clean | 1 resident MM, one-sided | **add now (Wave 1)** |
| sol | EXPAND, weaker persistence (mo_size 64% days+) | no resident MM (vanished 07-10/11) | **stage (Wave 2)**, reduced conviction, watch live fill data before adding xrp too |
| xrp | EXPAND, mo_size weak (t=2.21, 70% days+) | no resident MM, ever (14d census) | **stage (Wave 2)**, same caution as sol, no MM to share adverse-selection risk |

`live.yml.proposed` implements the mechanics for all four (concurrency, per-asset switch, chain
split, unchanged per-asset caps) so the operator can apply it with whatever matrix subset they're
comfortable with today — the file's matrix line is the one edit needed to start with `[btc, eth]`
and grow it later.
