# FAVLONG true-strike recovery test

**Node:** FAVLONG-TRUESTRIKE (2026-07-15). Decisive recovery test of the one candidate edge.
**Question:** FAVLONG's fair-value model used a *proxy* strike = the window's OPEN SPOT
(`tk[0][2]`), not the real Kalshi preset strike. Removing the illegal clean-label drop already
collapsed the "validated" edge (OOS pooled t 5.74 -> deployable 1.80). Hypothesis under test:
the residual weakness is the *wrong strike*; using the TRUE `floor_strike` + TRUE `result` from
the Kalshi API will RECOVER a deployable edge (OOS day-clustered t >= 2, no look-ahead).

**Offline / read-only.** No orders, no live changes. Public Kalshi API (finalized markets only).

---

## 1. Feasibility + coverage (Task 1)

- Ticker format confirmed against real tickers: `KX{BTC,ETH,SOL}15M-<YYMMMDD><HHMM>-<MM>` where
  the date+time are the **CLOSE time in US/Eastern** and the `-MM` suffix repeats the close minute
  (00/15/30/45). Example verified: `KXBTC15M-26JUL151130-30` -> `floor_strike` 65353.64,
  `result` yes, `close_time` 2026-07-15T15:30:00Z (= 11:30 ET). One market (the ATM contract)
  per event throughout — no strike-ladder ambiguity for these 15m crypto series.
- The FAVLONG cache stores only relative tick seconds, so windows were **rebuilt from
  `origin/gha-data` preserving `ws`** (window-start epoch) with `build_asset`'s exact filters.
  Rebuild matches the frozen cache window-for-window (proxy-deployable reproduced to t=1.79 vs the
  stated 1.80 — see §3), plus one newer day (2026-07-15) that post-dates the frozen cache.
- Strikes fetched in bulk via `GET /markets?series_ticker=...&min_close_ts&max_close_ts` (paginated,
  paced, cached to disk), keyed by `close_time` epoch = `ws + 900`.

**Historical availability is NOT a limitation** — June windows return fully finalized:

| asset | windows | matched close | with floor_strike | with result | TEST-set strike cov. |
|-------|--------:|--------------:|------------------:|------------:|---------------------:|
| btc   | 2889 | 2889 (100%) | 2886 (99.9%) | 2889 (100%) | 1169/1169 (100%) |
| eth   | 2905 | 2905 (100%) | 2902 (99.9%) | 2905 (100%) | 1154/1154 (100%) |
| sol   | 2943 | 2943 (100%) | 2940 (99.9%) | 2943 (100%) | 1220/1220 (100%) |

Coverage back to 2026-06-10 is essentially complete, so the curve-fit-strike fallback (Task 4)
is **not needed** — every train and test window has its true strike and true settlement.

---

## 2. Method (Task 2)

Taker mechanics, fee model, decision_t=720, edge=0.03, day-clustered per-(asset,day) t are held
IDENTICAL to `favlongshot_edge` / `favlong_model_v2`. Only three things are swapped:
`strike = floor_strike` (not `tk[0][2]`), `outcome = 1[result=="yes"]` (fallback `mid_close>0.5`
if a result is missing), and the illegal `if out_proxy != outcome: continue` clean-label drop is
**removed** — every gate-passing window is traded. Calibration = the stdlib-bucket isotonic the
forward harness deploys, fit on TRAIN only (`sklearn` is broken in this env; it is not the
deployed path anyway). Model config = `baseline/logndrift` (the v2-selected calibrated variant).
Train <= 2026-06-30, Test > 2026-06-30.

---

## 3. Side-by-side OOS results (Task 3)

Cache-day-matched (test <= 2026-07-14) so the proxy baseline lines up 1:1 with the prior finding:

| configuration | strike | clean-label | pooled OOS t | mean $/ct | btc | eth | sol |
|---|---|---|---:|---:|---:|---:|---:|
| proxy-INFLATED (look-ahead) | proxy | **ON** | **5.76** | +0.0509 | 4.47 | 3.23 | 2.32 |
| proxy-DEPLOYABLE (prior finding) | proxy | off | **1.79** | +0.0151 | 1.97 | 1.40 | -0.28 |
| **TRUE-strike DEPLOYABLE (calibrated)** | **true** | **off** | **0.91** | +0.0100 | **-0.27** | **1.16** | **0.66** |
| TRUE-strike raw-tuned (arith/sm0.8) | true | off | -0.68 | -0.0058 | -0.79 | 0.62 | -0.95 |

(Full set incl. 2026-07-15: proxy-inflated 5.76, proxy-deployable 2.05, true-strike calibrated
**0.78**; same story.) Reproduction of the prior proxy numbers is exact — proxy-deployable
btc 1.97 / eth 1.40 / sol -0.28 vs the stated 1.97 / 1.41 / -0.27 — confirming the harness and
window alignment are correct.

**Model search (v2 discipline) on the true strike:** all 24 vol×money×cal variants have
**negative or zero pooled t on TRAIN** — the in-sample edge itself disappears once the strike is
correct. The train-best variant gives OOS t=0.82; the most generous post-hoc best-of-24 TEST t is
only **1.31**. No configuration, calibrated or raw, clears the t>=2 gate.

### Fixed-windows analysis (the ~7% proxy-error windows)

The premise was that badly-wrong-proxy windows lose money and the true strike would rescue them.
It does the opposite. Proxy error is usually tiny (median ~0.02% of strike; p99 ~0.15-0.22%).
Splitting TEST windows at the top-7% proxy error (> ~0.089% of strike):

| window group | proxy-strike model $/ct | true-strike model $/ct |
|---|---:|---:|
| low-error 93% | +0.0171 | +0.0108 |
| **high-error top 7%** | +0.0044 | **-0.0178** |

The true strike makes the high-error windows *worse* (a net loser), and it shrinks the good
windows too. Consistently, the true-strike fair value is **better calibrated** to the true outcome
(Brier drops, e.g. sol 0.100 -> 0.089) — and that is exactly why it has no edge: a correctly
specified model no longer diverges from the market price enough to trade. The market prices the
true strike efficiently; the "signal" was the model's own strike misspecification.

---

## 4. Verdict

**NOT-RECOVERED.** Using the TRUE Kalshi strike + TRUE settlement, with no look-ahead and net of
fees, FAVLONG's deployable OOS day-clustered t is **0.91** (cache-matched days) / **0.78** (full),
per-asset btc **-0.27**, eth **1.16**, sol **0.66** — far below the t>=2 charter gate, and *below*
even the flawed proxy-deployable 1.80. The train edge vanishes under every model variant, and the
proposed fix degrades rather than rescues the previously-catastrophic proxy-error windows.

The apparent edge was a **double artifact**: (1) the clean-label outcome-peek inflated t to 5.74,
and (2) the residual "deployable 1.80" was itself produced by the proxy-vs-true **strike
misspecification** (open spot != preset strike). Correcting the strike — the thing that was
supposed to recover the edge — eliminates it, because it makes the fair-value model agree with an
already-efficient market. **FAVLONG has no deployable edge.** Recommend retiring it as a live
candidate; do not size it.

*Artifacts (scratchpad, uncommitted): `strikes_{btc,eth,sol}.json` (true strike/result maps),
`win_ws_{btc,eth,sol}.pkl` (ws-preserving rebuild), `recov_clean/recovery.py`, `diag.py`,
`search.py`.*
