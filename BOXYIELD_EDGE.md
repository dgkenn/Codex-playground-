# BOX-YIELD EDGE -- Phase 1 (GAIN side of the 15m crypto box bot)

**Focus:** the second term of `TOTAL PnL = (#boxes) x (avg locked edge/box) - strand losses`
plus capital allocation. *When* are boxes fattest (widest lock margin) and *how* should we size
capital onto fat boxes? And: does trading more assets (ETH, and by extension SOL/XRP) add
profitable breadth?

Harness: `box_yield_edge.py` (reuses `load_parquet_windows`, `run_p0`, `full_metrics`,
`_live_open_ok` from `ladder_baseline_study.py` / `box_policy_ab.py`).
Data: BTC 916 windows-with-fills, ETH 2384. IS = first 60% / OOS = last 40%.
Live policy = the deployed **t36 guarded-opener** (`--guard-yes-spread 0.02`, parsed live from
`live.yml`). **All numbers are BACKTEST on the maker-fill reconstruction; forward-validation
required before any sizing change ships.**

### Definition: lock margin per box
A box = one YES(bid) leg + one NO(ask) leg paired inside the window. Its locked PnL is
`(res - b0) + (a0 - res) = a0 - b0` -- the spread captured between the two entries, **independent
of settlement**. So a completed box is near-risk-free and its "edge" = the captured spread (the
`margin` column below, in cents). A *strand* is an unpaired leg held to settlement -- that is the
res-dependent directional risk and the only real downside.

---

## TASK 1 -- BASELINE LOCK-MARGIN (live policy)

| Split   | windows | boxes | avg margin/box | total locked | strands | total strand | NET/win |
|---------|--------:|------:|---------------:|-------------:|--------:|-------------:|--------:|
| BTC IS  | 549 | 3059 | **+0.556c** (t=+3.04) | +1702c | 189 | -191c | **+2.753c** |
| BTC OOS | 367 | 2241 | **+0.551c** (t=+2.49) | +1236c | 140 | -258c | **+2.664c** |
| BTC ALL | 916 | 5300 | **+0.554c** (t=+3.93) | +2938c | 329 | -449c | **+2.717c** |

- **Avg lock-margin/box = +0.55c, median +1.0c, highly stable IS->OOS (+0.556 -> +0.551c).**
- Fill rate ~5.8-6.1 boxes/window; ~36% of windows leave one stranded leg.
- Strand drag is small in aggregate (~-0.45c/win on BTC ALL) but is the entire tail risk.
- Reference: BTC OOS P0 (no gate) nets +2.771c/win at only 12.3% strand-rate -- the t36 gate
  trades *more* (it doesn't suppress much) and nets about the same. The gate is close to neutral
  on net; the edge lives in the margin term, not the gate.

---

## TASK 2 -- EDGE BY REGIME (BTC, live policy)

`NET edge` = avg margin minus expected strand cost spread across all opened positions in that
regime (i.e. cents per opened box net of the strand it might become).

### By k-slot (opening minute 2-12) -- ALL
| k_open | nBox | avg margin | strand% | NET edge | t(margin) |
|-------:|-----:|-----------:|--------:|---------:|----------:|
| 2  | 871 | +0.398c | 0.0%  | +0.398c | +1.61 |
| 3  | 657 | +0.328c | 0.0%  | +0.328c | +0.99 |
| 4  | 508 | +0.361c | 0.2%  | +0.355c | +0.83 |
| 5  | 558 | +0.635c | 0.9%  | +0.581c | +1.60 |
| **6**  | 539 | **+1.278c** | 0.9%  | **+1.219c** | **+3.27** |
| **7**  | 522 | **+1.236c** | 2.2%  | **+1.184c** | **+3.18** |
| 8  | 496 | +0.361c | 4.8%  | +0.283c | +0.75 |
| 9  | 419 | +0.928c | 8.3%  | +0.953c | +1.40 |
| 10 | 368 | -0.147c | 11.8% | -0.610c | -0.19 |
| 11 | 268 | -0.465c | 16.2% | -0.557c | -0.47 |
| 12 | 94  | +1.219c | 60.2% | -0.110c | +5.52 |

**Fattest boxes open at k=6-7 (mid-window): +1.2-1.3c margin at t>3, strand<3%.** This is the
sweet spot -- enough price discovery to have a real spread, not so late that the pairing leg
can't land. k=10-11 are net-negative (margin collapses *and* strands spike). k=12 shows a
deceptive +1.2c margin but 60% strand-rate -> NET ~0; do not chase late opens.

### By UTC session -- ALL
| session | nBox | avg margin | strand% | NET edge | t |
|---------|-----:|-----------:|--------:|---------:|---:|
| **Asia (00-07)** | 1549 | **+0.919c** | 6.1% | **+0.863c** | +3.66 |
| EU (07-13)   | 1274 | +0.046c | 5.8% | -0.162c | +0.16 |
| US (13-21)   | 1807 | +0.443c | 5.6% | +0.455c | +1.77 |
| **LateUS (21-24)** | 670 | **+0.977c** | 6.0% | +0.581c | +2.47 |

**Asia and late-US sessions carry the edge (+0.86c, +0.58c NET, both t>2.4). The EU session is
noise (+0.05c margin, t=0.16) and slightly net-negative.** Strand-rate is flat ~6% across
sessions, so this is a pure margin (spread-width) effect, not a strand effect.

### By vol-regime (window mean |sig|, bps) -- ALL then OOS
| vol | nBox | avg margin | strand% | NET edge | t | OOS NET |
|-----|-----:|-----------:|--------:|---------:|---:|--------:|
| lo  (<3)    | 1201 | +0.760c | 6.8% | +0.390c | +2.81 | +0.265c |
| **mid (3-8)** | 2809 | +0.665c | 5.6% | **+0.688c** | +3.43 | **+0.701c** |
| hi  (>=8)   | 1290 | +0.122c | 5.5% | -0.043c | +0.40 | -0.170c |

**Answer to "is high-|sig| a wider-spread-but-more-strands net win or loss?": it is a net LOSS,
and not because of strands.** High-vol windows do *not* strand more (5.5% vs 6.8% in calm). The
margin itself collapses to +0.12c (t=0.40, indistinguishable from zero) and NET goes negative.
The "wide spread in volatility" intuition is wrong here -- in fast markets the legs fill at
adverse/stale prices and the *captured* spread shrinks. **Mid-vol (3-8 bps) is the fattest and
most stable regime (NET +0.69c, t=+3.4, IS==OOS).** This is the single most robust edge tell.

---

## TASK 3 -- EDGE-PROPORTIONAL SIZING (fractional-Kelly on locked margin)

Completed box ~ risk-free, so the "edge" is the locked margin net of strand probability. We
estimate a `(session x vol-bucket)` net-edge map **on IS only** (no outcome leakage) and size each
opened box by `1 + f*(edge_regime - mean_edge)/|mean_edge|`, clipped [0,3], mean-size ~ 1
(capital-neutral allocation, not added leverage). Evaluated OOS vs flat size.

| Policy | net/win | Sharpe | Sortino | MaxDD | WR% | d vs flat (paired t) |
|--------|--------:|-------:|--------:|------:|----:|---------------------:|
| flat (live)   | +2.664c | +0.080 | +0.073 | 771c | 58.3% | -- |
| edge f=0.25   | +3.212c | **+0.089** | +0.083 | **740c** | 58.3% | +0.55c (t=+0.73) |
| edge f=0.50   | +3.777c | +0.088 | +0.075 | 784c | 46.9% | +1.11c (t=+0.87) |
| edge f=0.75   | +4.240c | +0.085 | +0.070 | 808c | 44.4% | +1.58c (t=+0.96) |
| edge f=1.00   | +4.540c | +0.082 | +0.059 | 848c | 37.9% | +1.88c (t=+0.97) |
| edge f=1.50   | +5.484c | +0.083 | +0.059 | 940c | 35.7% | +2.82c (t=+1.18) |
| edge f=2.00   | +6.360c | +0.085 | +0.061 |1034c | 35.7% | +3.70c (t=+1.32) |

**Recommendation: edge-proportional sizing helps, but modestly and on net more than on
risk-adjusted return.** Total net/win rises monotonically with `f` (you are correctly tilting
capital onto the fat mid-vol / Asia boxes), but:
- The Sharpe peak is the **mild f=0.25** (+0.089 vs +0.080) which *also* cuts MaxDD (740 vs 771c).
- Aggressive tilts (f>=1) keep raising raw net but Sortino *falls* and MaxDD climbs ~10-35% --
  concentration adds tail risk faster than mean past the gentle tilt.
- **None of the paired-difference t-stats clear 2** (best is f=2 at t=+1.32). So edge-sizing is a
  positive-EV nudge but is **not yet statistically distinguishable from flat** on this sample.
  Honest call: ship the gentle **f=0.25** tilt (Sharpe-and-drawdown dominant, low risk of harm),
  treat the larger net gains at high f as unconfirmed.

---

## TASK 4 -- CROSS-ASSET BREADTH (BTC vs ETH; SOL/XRP by extension)

| Book | boxes/win | avg margin | **median margin** | strand% | net/win | Sharpe |
|------|----------:|-----------:|------------------:|--------:|--------:|-------:|
| BTC OOS | 6.11 | **+0.551c** | +1.0c | 38% | **+2.664c** | **+0.080** |
| ETH OOS | 5.75 | **-1.459c** | **+2.0c** | 37% | **-10.523c** | **-0.387** |

**ETH does NOT add profitable breadth -- it adds toxic throughput.** The trap: ETH's *median*
box margin (+2.0c) is *wider* than BTC's (+1.0c), but the *mean* is -1.5c because **29.6% of ETH
boxes lock in a negative margin**, with a brutal left tail (5th pctile = -21c). The pairing leg
fills at crossed/stale prices in ETH's thinner, faster book -- classic adverse selection on the
completing leg. A spread-floor buffer at open does **not** rescue it (buf 0.00->0.03 leaves
avg margin -1.0 to -1.2c and net negative throughout), confirming the toxicity is on the
*pairing* side, not a thin-open artifact.

Portfolio (251 common OOS windows):
| Construction | net/win | Sharpe |
|--------------|--------:|-------:|
| BTC alone | +4.325c | **+0.132** |
| ETH alone | -11.739c | -0.433 |
| 50/50 BTC+ETH | -3.707c | -0.157 |
| SUM (both full) | -7.414c | -0.157 |

BTC-ETH window-PnL correlation **+0.23** (low -- so the diversification *geometry* is there), but
**diversification cannot help when one sleeve has negative expected return**: 50/50 vs BTC-alone
is **-8.03c/win (t=-6.79)** -- a decisively significant *destruction* of value. Adding ETH at the
current fill model is strongly net-negative.

**Verdict on breadth:** do **not** trade ETH 15m boxes with the BTC policy. SOL/XRP almost
certainly share ETH's thinner-book toxicity and should be assumed guilty until a per-asset study
shows a positive *mean* (not median) box margin. Breadth is only profitable if a future
per-asset selection model can suppress the negative-margin tail; until then BTC is the book.

---

## RECOMMENDED SELECTION + SIZING RULES (trader-flag sketch)

Backtest-screened, **forward-validation pending**:

1. **Asset:** BTC only for now. Gate ETH/SOL/XRP behind a per-asset positive-*mean*-margin check
   (median is misleading). `--assets btc`.
2. **Slot selection:** prefer k=5-9 opens; **avoid opening new legs at k>=10** (margin collapses,
   strands spike). `--open-kmin 5 --open-kmax 9` (k=2-4 are fine but thin-edge; keep for fills).
3. **Vol regime:** concentrate in **mid-vol (window mean|sig| 3-8 bps)**; down-weight hi-vol
   (>=8 bps) where margin ~ 0. `--vol-band 3:8` as a sizing multiplier, not a hard gate.
4. **Session:** tilt capital to **Asia (00-07 UTC) and late-US (21-24)**; neutralize EU (07-13).
   `--session-weights asia=1.3,eu=0.7,us=1.0,lateus=1.2`.
5. **Sizing:** gentle **fractional-Kelly f=0.25** on the IS-estimated `(session x vol)` net-edge
   map, mean-size 1.0, clip [0,3]. `--edge-size-frac 0.25`. (Higher f raises net but not Sharpe
   and adds drawdown; do not exceed f~0.5 without forward confirmation.)

---

## MARGINAL GAINS vs LIVE (with t-stats)

| Change | OOS effect | t-stat | confidence |
|--------|-----------|-------:|-----------|
| edge-size f=0.25 vs flat | +0.55c/win, Sharpe +0.089 vs +0.080, MaxDD -31c | +0.73 | weak +, ship (low harm) |
| edge-size f=2.0 vs flat | +3.70c/win net | +1.32 | unconfirmed |
| add ETH 50/50 | -8.03c/win | **-6.79** | **strongly negative -- do not ship** |
| slot/session/vol tilts | margin tells t=+3.2 to +3.7 (k6-7, Asia, mid-vol) | -- | robust IS==OOS |

## IS/OOS STABILITY

- Avg lock-margin: +0.556c (IS) -> +0.551c (OOS). Essentially identical -- the *level* of edge
  is stable.
- Vol-regime ranking (mid > lo > hi) holds IS and OOS; mid-vol NET +0.688c (ALL) vs +0.701c
  (OOS) -- the strongest and most reproducible tell.
- Sizing sweep done OOS with an IS-only edge map (no leakage); gentle tilt is the robust pick.

## NOVEL IDEAS / NOTES

- **Avellaneda-Stoikov reservation-price skew:** the regime tables say the captured spread is
  widest mid-window (k6-7) and in mid-vol. An A-S reservation price `r = mid - q*gamma*sigma^2*tau`
  would naturally quote wider (capture more margin) exactly when inventory `q` and time-left `tau`
  are favorable, and tighten late -- a principled continuous version of the k-slot rule. Worth a
  Phase-2 prototype: skew the YES/NO quote offsets by current net inventory and remaining tau,
  targeting the +1.2c k6-7 band. Expected to lift avg margin without the discrete-gate cliff.
- **Kelly portfolio across assets:** mathematically attractive (BTC-ETH corr only +0.23) but
  **moot until each asset has positive mean box margin**. The cross-asset Kelly is the right
  framework once a per-asset toxicity filter makes ETH/SOL/XRP mean-positive; today it allocates
  into a losing sleeve.
- **Honest noise calls:** the *sizing* edge (f-sweep) is directionally right but every paired
  t-stat < 2 -- positive EV, not proven. k=2-4 margins and the lo-vol bucket are also low-t. The
  *strong* claims (mid-vol best, ETH toxic, k6-7 fattest) all clear t>3 / |t|>6.

**Bottom line:** the GAIN-side edge is real and stable (~+0.55c/box), concentrated in mid-vol /
Asia / k6-7. Tilt capital there with a gentle f=0.25 Kelly. Do **not** add ETH (or untested
SOL/XRP) -- their wider *median* spread is a negative-mean adverse-selection trap. Breadth needs a
per-asset toxicity filter first.
