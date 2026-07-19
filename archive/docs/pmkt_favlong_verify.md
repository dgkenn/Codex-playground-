# PMKT-COPYTRADE favorite-longshot candidate — adversarial verification

Node: PMKT-FAVLONG-VERIFY (2026-07-15). Read-only, offline, propose-only. No orders, no live action.
Target: the candidate in `edge_polymarket_copytrade.md` — "BUY the underpriced FAVORITE when >=2 tracked
wallets late-buy the UNDERDOG" on btc-updown-5m, reportedly OOS day-clustered t=+5.5, win 97% at
entry ~0.85, net of the 1c spread. Mandate: KILL it (find the leak) or prove it has none, the way
FAVLONG died when its clean-label toggle collapsed 5.74 -> 1.8 -> 0.9.

Scripts audited: `scratchpad/ct_lib.py`, `ct_control.py`, `ct_final.py`, `ct_repull.py`.
Data: `causal_trades.pkl` (smart/dumb wallet raw trades), `pmkt_cache/*.pkl` (per-market Up/Down
bid/ask/size time series), `wallet_market.jsonl`. My audits: `scratchpad/audit_favlong.py`,
`audit2.py` … `audit9.py`. Reproduced the report's baseline exactly (n=100, wr=0.970, entry=0.846,
t_day=+5.53) before stressing it.

## TL;DR verdict — REAL under every deployable toggle (NOT a FAVLONG-type artifact), but thin/implausible
Unlike FAVLONG, **no deployable toggle collapses this.** Strict causal + executable reconstruction leaves
the OOS day-clustered t at **≈ +5.4** (trade-implied-fair entry +5.85; +1c extra slippage +5.37), vs the
reported +5.5. The signal is strictly causal, the ~0.84 entry is a real fillable tight-book ask confirmed
by contemporaneous taker prints, and settlement is the true Gamma label. I could not find a look-ahead.
**However** the effect is economically implausible as a scalable edge and its live capture rests on one
untested assumption (below). Classification by the task's own definition ("survives causal signal + true
executable ask + real depth + true settlement, OOS t >> 2 net of realistic cost") = **REAL**, with a
capacity/economic reservation, not ARTIFACT.

## Toggle-by-toggle (before -> after)

1. **ENTRY-PRICE CAUSALITY / EXECUTABILITY — SURVIVES.** Entry uses `buy_price(..., cross=True)` = the
   favorite ASK at the last quote <= T (not a mid/trade-print/stale-bid). Staleness of that quote is
   p50=1s (mean 6s). Re-priced at the first ask *strictly after* T: entry 0.850 -> 0.858, t_day +5.53 ->
   **+5.84** (does not die — opposite of FAVLONG). Cross-checked the book ask against **actual taker
   prints** on the favorite in [T-15,T+15]: book favmid 0.835 vs trade-implied fair 0.837 (median gap
   +0.005); book spread is a tight 1c (p25=p50=p75=0.010). Real accounts are lifting the favorite at
   ~0.84 near T and winning. Re-scoring at trade-implied fair: mean +0.132, **t +5.85**; +1c extra
   slippage: **t +5.37**. The "0.85" is a genuine executable price, not fiction.

2. **LABEL / FAVORITE / SIGNAL LEAK — SURVIVES (this is where FAVLONG died; here it does not).**
   Favorite = book mid > 0.5 at T (causal). Signal = wallet net-long underdog built only from trades
   with `ts <= T` (`ct_final.feats`). I verified the raw timestamps: trade `ts` is in-window Unix
   seconds on the same epoch as `wstart` (rel_ts within [~27, ~380]s), and the counted underdog buys sit
   at rel_ts ~115-170s, i.e. genuinely before T=180 (`audit7`). Moving the signal measurement EARLIER
   (ts <= T-15 … T-60) while holding entry/settlement at T=180 makes the edge **stronger** (t up to
   +8.5), i.e. the predictive content is not riding last-second/after-T flow. No epoch/units leak, no
   post-T contamination, no final-settled-position leak.

3. **SETTLEMENT — SURVIVES.** `win_idx` = Gamma `outcomePrices` (UMA resolution), mapped through
   `clobTokenIds`. Consistent with terminal book prices on inspection. Causal, correct payout label.

4. **DEPTH / CAPACITY — real price, thin size.** Archived favorite ask size (Up leg) is large
   (p50 ≈ 25.6k, p10 ≈ 10.7k shares) and the book is tight (1c). Actual taker fills at ~0.84 confirm
   small-size executability. But frequency is only ~6-7 signals/test-day, and the favorite mid is
   **actively climbing through the entry** (favmid +0.075 over T->T+60 in gate markets), so the passive
   "fill at the observed ask" assumption is the one thing offline data cannot fully validate for size.

5. **RECONCILE WITH 'BOOK IS EFFICIENT' — resolved: the book is calibrated *on average*; the gate is a
   real conditional residual, not skill and not momentum.** Unconditional test-favorite calibration is
   clean (ask 0.55->win 0.51, 0.65->0.64, 0.75->0.80, 0.84->0.86, 0.95->0.97). Within a fixed ask band
   the gate splits same-priced favorites hard: at ask 0.80-0.88, gate Dd>=2 wins 100% (21/21) vs
   non-gate 68% (13/19); the two halves sum back to calibration. Mechanism tests:
   - **Identity-independent AND reproduced by RANDOM wallet sets** (random 705-wallet gates: win
     0.956-0.967, t +4.9 … +5.8, ≈ the real dumb gate +5.4). So it is NOT wallet skill — it is a proxy
     for "the cheap underdog attracted enough buyers by T" (participation).
   - **NOT price momentum.** A pure "favorite already rose pre-T" gate is NULL (win 0.79, t +0.67), and
     controlling the dumb gate for pre-T favorite move leaves both halves at ~0.97. Cheap-side
     participation carries information *beyond* the favorite's own price path.
   Reading: a behavioral microstructure residual — heavy bottom-fishing on a collapsing longshot marks a
   decisive move that continues — that the prior nodes never tested (they tested directional flow, the
   FAVLONG near-expiry mechanism, and skill-copy, all null). It is genuinely orthogonal to those.

6. **MULTIPLE TESTING / HELD-OUT — robust.** Present in TRAIN (t_day +6.22, n=167) as well as TEST
   (t_day +5.38, n=96). Wins spread across all 15 test days (13/15 strongly positive) and across 42
   independent contiguous-window runs (run-clustered t = 4.96, barely below the day-clustered 5.38), so
   it is not a handful of BTC trend-days or a lucky config corner. The ~180-config search did not
   manufacture it.

## Where the residual doubt lives (why this still deserves caution despite surviving)
The magnitude is economically implausible: a **costless, public, identity-independent** signal that
splits same-priced favorites into 68%-winners and 100%-winners should be arbitraged instantly by the MMs
quoting those 25k-share asks. That it survives to T in a tight 1c book is the paradox. I could not
resolve it into a leak after nine targeted audits, which points to one of two things: (a) a genuine but
**thin, non-scalable** inefficiency whose historical fills are small tracked-wallet takers transiting a
fast move — real for tiny size, gone at scale; or (b) a **sample-level selection** I cannot test, because
all 632 markets share one construction and I have no truly held-out universe (extending the gate needs
tracked-wallet trades that exist only for these 632 markets). The deployable failure point, if any, is
**execution**: filling ~0.84 in real time while the favorite is climbing through it, at ~6 thin signals/
day, with impact/adverse-selection a 1c book cannot absorb — not a statistical look-ahead.

## Verdict
**REAL — does NOT collapse under any deployable toggle** (causal pre-T signal, true executable
tight-book ask confirmed by live taker prints, true Gamma settlement, robust across train/test/days/runs/
identity, not explained by momentum). **Strict deployable OOS day-clustered t ≈ +5.4** (unchanged from
the reported +5.5; +5.85 at trade-implied fair, +5.37 with +1c extra slippage). This is categorically
different from FAVLONG, whose clean-label toggle collapsed it 5.74->0.9 — here every analogous toggle
holds. **BUT** it is not the skill-copy thesis (that is a clean NULL, confirmed) and it is not a scalable
edge: it is a thin-capacity, participation-driven favorite-underpricing residual whose economic
implausibility and passive-fill assumption warrant **small-size live validation of fill quality before
any deployment**, and de-duplication against the repo's existing FAVLONG theme. Recommendation: treat as
**REAL-but-unproven-deployable**; do not size it on the backtested +12c/contract until live ask-depth and
fill-at-the-climbing-ask are measured.
