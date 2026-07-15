# Independent Reproduction — Polymarket btc-updown-5m "favorite + underdog-wallet gate"

**Verdict: NOT-CONFIRMED.** Built from scratch (own fetch + own analysis, no prior-agent code/files). The
claimed effect does **not** reproduce: the ">=2 distinct underdog wallets" gate is economically inert
because it is satisfied by ~100% of liquid btc-updown-5m markets, and a favorite bought in the ~0.84 band
is roughly **calibrated** (wins ~86–88%, not 97%). I get **no t~+5** — at most a weak t~1.4 on a wide band
at the realistic fill, collapsing to ~0.3 in the tight 0.84 band. Fresh/forward data (2026-07-15) behaves
identically to the archive.

## Pipeline (independent, from scratch)
- **Markets:** `gamma-api/events?slug=btc-updown-5m-<epoch>` → conditionId, clobTokenIds, outcomes, and
  **true UMA resolution** via `outcomePrices` (kept only clean 1/0 resolved markets).
- **Fills:** `data-api/trades?market=<conditionId>` paged DESC (needed `User-Agent: curl/8.0` header or the
  proxy 403s urllib). Each 5-min window has ~1,500–2,800 fills.
- **Sample:** 1,239 resolved btc-updown-5m markets over 5 UTC days — **repro/in-archive** 2026-07-08, -09,
  -11, -12 (1,017 markets) and **fresh/forward, out-of-archive** 2026-07-15 (222 markets; archive reportedly
  ended ~07-14).
- **Window/T:** window = [epoch, epoch+300]; **T = epoch+150 (mid-window, guessed)**.
- **Favorite:** side with reconstructed price >0.5 at T (Up-price series from all prints, Down→1−p).
- **Gate:** distinct proxyWallets with a **BUY on the underdog token, ts ≤ T** ("aggressive" = taker BUY);
  also tested $50/$100/$250 notional floors.
- **Entry price two ways:** (a) NAIVE mid@T (last print ≤ T — what a sloppy backtest uses); (b) **FILLABLE
  ask** = VWAP of favorite taker-BUY fills in (T, T+30s] (what you'd actually pay).
- **Resolution/PnL:** favorite won iff its `outcomePrices`==1; net PnL = (1−a if win else −a) − 0.01 spread;
  **t clustered by calendar day**.

## Task 1 — From-scratch repro: does the gate split 68% → 97% at ~0.84?
**No.** The gate does not discriminate at all. Distinct underdog buyers before T: **median 217 per market**;
`frac(≥2 wallets)=1.000`. Even at $50 notional it's 0.99; at $100, 0.86–0.94.

Calibration, pooled 5 days (this is the whole story):

| fav price band | n | win rate | avg price | win−price |
|---|---|---|---|---|
| 0.80–0.82 | 44 | 0.886 | 0.805 | +0.081 |
| 0.82–0.84 | 49 | 0.898 | 0.825 | +0.073 |
| **0.84–0.86** | **44** | **0.864** | **0.845** | **+0.019** |
| 0.86–0.88 | 57 | 0.930 | 0.864 | +0.065 |
| 0.88–0.92 | 130 | 0.946 | 0.896 | +0.050 |

The ~0.84 favorite wins **~86–88%, not 97%.** Because the gate is satisfied by 100% of the band,
**gated win = ungated win = ALL win** (e.g. repro band [0.80,0.88): all three = 0.854). There is no "ungated
68%" population to compare against — markets with <2 underdog buyers essentially do not exist.

## Net-of-spread, day-clustered t (pooled 5 days) — did I reproduce t~+5?
**No.**

| band | entry | mean net/trade | **day-clustered t** |
|---|---|---|---|
| 0.80–0.88 (n=194) | naive mid@T | +0.050 | **2.32** |
| 0.80–0.88 | **fillable ask** | +0.036 | **1.44** |
| 0.82–0.86 (n=93) | naive mid@T | +0.037 | 1.05 |
| 0.82–0.86 | fillable ask | +0.027 | 0.82 |
| 0.83–0.85 (n=46, tight ~0.84) | naive mid@T | +0.024 | 0.34 |
| 0.83–0.85 | fillable ask | +0.017 | 0.30 |

The best number anywhere is t≈2.3 on a **wide** band using the **optimistic** mid; it falls to ~1.4 at the
realistic fill and ~0.3 in the tight 0.84 band. Nothing resembles **+5.4**.

## Task 2 — Decisive fresh/forward test (2026-07-15, out of original universe)
Same behavior: gate `frac(≥2)=1.000` (median 249 underdog buyers). The [0.84,0.88) band shows 100% (n=15) and
[0.80,0.88) 93.8% (n=32) — consistent with the mild calibration edge plus small-n luck, **not** a gate
effect (there is no ungated bucket). A single fresh day cannot yield a day-clustered t, but the gate's total
saturation on genuinely out-of-archive data is the cleanest confirmation that the "should-be-arbitraged,
selective signal" simply isn't selective.

## Task 3 — Leak hunt
- **(a) Is 0.84 a real fillable ask?** Roughly yes, but the backtest mid is optimistic. Live CLOB book on an
  active market: favorite bid/ask **spread ≈ 1c** with real depth (~$100–270/level). Empirically
  `fill_ask − mid@T` = **mean +0.010, median +0.017, p90 +0.095**. So the naive mid used by a backtest is
  ~1–2c better than you can actually buy (and occasionally ~10c better when price is moving). Substituting the
  real fill cuts the mild edge roughly in half and drops the wide-band t from 2.32 → 1.44. This ~1–2c
  optimism (entering at a stale/mid price rather than the lifted ask, especially the p90 fast-move cases) is
  the most plausible source of a phantom t~+5 in the original.
- **(b) Is the gate strictly ts ≤ T?** Mine is. And it matters: **1,237/1,239 markets have underdog buyers
  arriving AFTER T** (median 125 post-T buyers). A construction using ts ≤ window_end would ingest huge post-T
  flow. (Here it wouldn't change the result — the gate is saturated either way — but it is a real look-ahead
  trap in the general construction.)
- **Stricter gates go the wrong way / are non-robust:** $250-notional underdog gate on the 2-day repro gave
  gated win 0.737 vs ungated 0.889 (opposite of the claim); pooled it's mildly positive but confounded and
  nowhere near 97/68. No gate threshold reproduces the split.

## Task 4 — Capacity
~288 windows/asset/day; ~30–40 land in the 0.80–0.88 favorite band/day. Top-of-book depth at the ~0.84 ask is
only ~$100–300 before it moves 1c, so fillable size per signal is a few hundred dollars. Even taking the mild
residual edge at face value, it is a **micro-capacity** phenomenon; net of the realistic ~1–2c fill premium
and 1c spread it is break-even-to-negative in the tight 0.84 band.

## What is actually true
There is a **small, genuine favorite-longshot-style mispricing** (mid/high-priced favorites underpriced by
~2–8c; wide-band naive t~2.3, realistic-fill t~1.4 over 5 days). It is **not** significant at +5, **not**
caused by the underdog-wallet gate (which is inert), and **marginal-to-negative** after realistic fills at the
~0.84 entry.

## Specs I had to guess (and robustness)
- T = epoch+150 (mid-window). The gate is saturated at any T inside the window (hundreds of underdog buyers
  span the whole window), so the null is not a T artifact.
- "Aggressive" = taker BUY on underdog token; tested notional floors $50/$100/$250 — none make the gate
  selective enough to matter.
- Fillable ask window (T, T+30s]; spread cost 1c. Widening either only worsens the edge.

## Verdict
**NOT-CONFIRMED.** I did not reproduce t~+5 (best realistic t≈1.4 on a wide band, ≈0.3 at 0.84). The
underdog-wallet gate is economically inert (satisfied by ~100% of liquid markets on both archive and fresh
2026-07-15 data), so the claimed 68%→97% split cannot exist as described — the ~0.84 favorite is simply
~86–88% calibrated. The 0.84 book is tight and roughly fillable, but the backtest mid is ~1–2c optimistic,
which is the likely origin of the phantom edge; capacity is a few hundred dollars/signal.
