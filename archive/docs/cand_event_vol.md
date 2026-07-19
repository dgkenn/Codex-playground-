# Candidate: Event-Vol Premium around scheduled macro catalysts (Kalshi econ)

**Status: INSUFFICIENT-DATA (point estimate: NO premium — implied move ≈ realized move gross, negative net of costs).**
Orthogonal to FAVLONG (crypto microstructure). Read-only public Kalshi API. No orders, no keys. Paper only.
Date: 2026-07-15. Branch: `claude/coding-bot-ab-test-results-ffmhxw` (staged, uncommitted; lead reviews/commits/verifies).

---

## Hypothesis

Just before a scheduled macro release (CPI, Core CPI, jobs/NFP, unemployment), Kalshi's econ strike
ladder implies a distribution over the outcome with some **implied move** (implied dispersion). Does
that implied move systematically **exceed** the realized move (=> selling event-vol / the ladder's
implied "straddle" is +EV), the classic vol-risk-premium — or fall short?

## Method

**API / client.** Same public REST base as `settle_recorder.py`:
`https://api.elections.kalshi.com/trade-api/v2`, stdlib `urllib`, no auth, read-only. All calls cached
to disk + paced (~0.35s) + retried; deep-ITM/OTM strikes and older events skipped to cap lookups (gentle
on the shared API). Scripts in scratchpad (`kapi.py`, `pipeline.py`, `collect.py`, `score.py`).

**Ladders used.** The econ series are cumulative "greater-or-equal" digital ladders — market `-Tk` pays
$1 iff outcome ≥ `k`, so the pre-release mid-price of `-Tk` **is** the implied P(X ≥ k), i.e. a full
implied CDF. Quantitative test run on the four numeric ladders: `KXCPIYOY` (headline CPI YoY, 0.1%%
grid), `KXCPICOREYOY` (Core CPI YoY), `KXU3` (unemployment, 0.1%% grid), `KXPAYROLLS` (NFP, coarse job-
count grid). **`KXFEDDECISION` is categorical (hold/cut/hike), not a numeric ladder — no well-defined
"implied move," so it is excluded from the straddle test** (noted, not scored).

**Pre-release snapshot.** Historical 1-minute candlesticks
`GET /series/{s}/markets/{ticker}/candlesticks` return per-minute `yes_bid` / `yes_ask` (so spread is
observable historically). For each strike I take the last candle in `[close−420s, close−30s]` with a
two-sided quote. Markets close 1 min before the release (e.g. CPI close 12:29Z, print 12:30Z), so every
snapshot is genuinely pre-release. I skip the release-second candle (blown-out spread).

**Straddle-equivalent P&L (tradeable, dollar-denominated).**
1. Implied median `k0` = strike where the P(≥k) curve crosses 0.5 (linear interp).
2. Straddle basket = the near-money legs (pre-release mid ∈ [0.03, 0.97]) — 1 contract each. Above `k0`
   the leg pays $1 iff outcome ≥ k (a YES); below `k0` it pays $1 iff outcome < k (a NO). This basket
   replicates "number of strikes the outcome lands from the implied median" — the discrete analog of a
   straddle: it is worth more the larger the move.
3. **Implied move** = Σ leg prices (premium the seller collects). **Realized move** = Σ leg payoffs
   (what the seller pays out).
4. **Straddle-SELL P&L (gross, mid)** = implied − realized. **Net** = gross − Σ half-spread (crossing to
   the bid per leg) − Σ Kalshi quadratic fee `ceil(0.07·p(1−p)·100)/100` per leg.
5. Realized outcome `X_real` = midpoint of the winning bin (where `result` flips yes→no). Events where
   the outcome landed outside the quoted near-money band are flagged **censored** and dropped.

Positive mean net P&L => implied move > realized => harvestable premium (sell vol). Negative => implied
move < realized => no premium (the ladder under-prices the move).

## Data availability — the binding constraint (honest sparsity)

Kalshi's public API returns the settled **event** rows far back (44 CPI, 43 Core CPI, 40 Payrolls, 60
U3, 26 Fed monthlies), **but the underlying market objects (and thus the strike ladder + candlesticks)
are retrievable only for the ~3 most-recent monthly events per series** — anything closing more than
~3 months ago returns **zero markets** via both `/events?with_nested_markets` and `/markets?event_ticker=`.
So the *analyzable* universe is tiny and cannot be deepened from history; it can only grow forward.

After also dropping events with too-thin pre-release quotes (Core CPI is illiquid: JUN/MAY had <4 two-
sided legs) and one censored payrolls event, **n = 7 usable events**:

## Per-event results

| event | legs | implied move | realized move | gross P&L | net P&L |
|---|---:|---:|---:|---:|---:|
| KXCPIYOY-26JUN | 3 | 0.46 | 1.0 | −0.545 | **−0.660** |
| KXCPIYOY-26MAY | 6 | 0.95 | 0.0 | +0.950 | **+0.550** |
| KXCPIYOY-26APR | 6 | 0.81 | 1.0 | −0.185 | **−0.390** |
| KXCPICOREYOY-26APR | 2 | 0.48 | 1.0 | −0.515 | **−0.590** |
| KXU3-26JUN | 4 | 0.58 | 1.0 | −0.420 | **−0.590** |
| KXU3-26MAY | 4 | 0.73 | 0.0 | +0.735 | **+0.550** |
| KXPAYROLLS-26JUN | 12 | 2.68 | 6.0 | −3.320 | **−3.940** |

Short-vol signature: seller wins small when the print lands at the implied median (26MAY CPI/U3), loses
when it moves a strike or more, and gets run over on the tail (26JUN NFP came in far below the implied
median — realized move 6 strikes vs 2.68 implied).

## Aggregate (event-clustered; each monthly release independent)

**All n = 7**
- implied move mean 0.957 vs realized move mean 1.429 (ratio **0.67**) — but driven by the one NFP outlier.
- GROSS straddle-sell P&L: mean **−0.47/event**, t = **−0.89** (NS)
- NET (after spread + fees): mean **−0.72/event**, t = **−1.27** (NS)
- NET per leg: mean −0.118, t = −1.72 (NS)

**Ex-payrolls outlier n = 6**
- implied move mean 0.670 vs realized move mean 0.667 (ratio **1.005**) — **essentially identical**.
- GROSS P&L: mean **+0.003/event**, t = **+0.01** (dead zero)
- NET P&L: mean **−0.188/event**, t = **−0.80** (NS)

Interpretation: **gross implied move ≈ realized move → the vol-risk-premium is ~zero, not positive.**
There is no free event-vol to sell. Net of Kalshi spread + fees the straddle is modestly *negative* EV
in *either* direction (you pay the frictions to put it on). The only large deviation is a single NFP
miss where realized ≫ implied — i.e. if anything the ladder *under*-priced that move, the opposite of a
harvestable short-vol premium, and it torpedoes the short-vol P&L.

## Verdict: INSUFFICIENT-DATA (and no positive premium in-sample)

- **n = 7** analyzable events is far too small for inference — all P&L t-stats |t| < 1.3, and one NFP
  print dominates the mean. Cannot reject zero; cannot claim an edge.
- **Point estimate is against the hypothesis, not for it:** gross implied move ≈ realized move (VRP ≈ 0),
  net-of-cost EV slightly negative. No systematic event-vol premium to sell was found. **REAL: no. NULL
  on the point estimate, formally INSUFFICIENT-DATA on power.**
- **Structural ceiling:** history cannot be mined deeper (public API drops markets/candlesticks after
  ~3 months), so this can only be resolved by **forward-collecting** ~1 CPI + 1 Core CPI + 1 NFP + 1 U3
  per month. Even at a clean +signal, ~12–24 months (~50–100 events) would be needed for a 2σ result,
  and the gross ≈ 0 / cost-negative starting point makes that a low-priority forward collection vs
  FAVLONG. Recommend: **park as a cheap forward-logging sleeve (snapshot the pre-release ladder monthly),
  do not allocate capital.** Re-evaluate once n ≳ 30.

## Caveats

- Straddle "move" is in strike-count (grid) units, not dollars of underlying; cross-series magnitudes
  aren't directly comparable (payrolls grid is coarser), which is why the raw mean is outlier-sensitive —
  hence the per-leg and ex-outlier cuts.
- `X_real` = winning-bin midpoint (±0.05%% CPI/U3 discretization).
- Costs modeled as half-spread-to-bid + quadratic taker fee per leg; real slippage on the thin far legs
  could be worse, making net EV if anything *more* negative — does not change the verdict.
- Fed decisions excluded (categorical); a separate "surprise vs implied hold-probability" test could be
  built but is also n≈3 accessible.
