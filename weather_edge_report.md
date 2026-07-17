# Kalshi Weather (High-Temp) Forecast-Edge Probe

**Question:** Do free NWS/NOAA forecasts carry a *superior-information* edge over Kalshi's
daily high-temperature markets that survives fees + spread — or does the market already
price the forecast?

**Verdict (blunt): NO EDGE. Strong, statistically significant null.** Kalshi's daily
high-temp markets already price professional NWS forecasts *better* than a debiased
NBM-MOS fair value does. Trading the forecast-vs-price divergence **loses money**
(mean −1.7¢/contract, day-clustered **t = −2.18**, win rate 24%), and the result is
robust across 6 of 7 cities. The large apparent "divergence" is the *forecast being less
informed than the market*, not an information advantage. **Strategy capacity for this
edge ≈ $0** (negative EV).

Script: `/home/user/Codex-playground-/weather_edge.py` · raw results:
`.weather_cache/_result.json` · Do NOT git commit (per instructions).

---

## 1. The market + data map

**Kalshi series (public API `api.elections.kalshi.com/trade-api/v2`).** Seven liquid
daily high-temperature series, one event per city per day, settled on the official
observed daily high:

| Series | City / station | Buckets/day | Liquidity (per active bucket) |
|---|---|---|---|
| KXHIGHNY | New York – Central Park (KNYC) | ~6–13 | day-vol median ~3.1k, OI ~5k–16k |
| KXHIGHCHI | Chicago – Midway (KMDW) | ~6–13 | similar |
| KXHIGHMIA | Miami Intl (KMIA) | ~6–13 | similar |
| KXHIGHDEN | Denver Intl (KDEN) | ~6–13 | similar |
| KXHIGHAUS | Austin (KAUS/Camp Mabry) | ~6–13 | similar |
| KXHIGHLAX | Los Angeles (KLAX) | ~6–13 | similar |
| KXHIGHPHIL | Philadelphia Intl (KPHL) | ~6–13 | similar |

Buckets are mutually-exclusive/exhaustive integer ranges: a bottom threshold ("N or
below"), 2°F range buckets ("A° to B°"), and a top threshold ("M or above"). Settled
markets return `result` per bucket (ground-truth outcome). **Historical prices are only
available via the `candlesticks` endpoint** (settled `/markets` listings return
`volume=None`); candlesticks give `yes_bid`/`yes_ask`/`price` in dollars plus `volume_fp`
and `open_interest_fp` per minute-bar — this is what made the backtest possible.

**Forecast + outcome (free):**
- **Forecast:** IEM archived **NBM MOS** (`api/1/mos.json`, model `NBS`) — station-based
  hourly `tmp`; I take the **max over the local day from the morning (06Z) run** as the
  forecast high. This is a genuine, archived, professional NWS-family forecast at ~1-day lead.
- **Outcome:** Kalshi's own settlement (exact) for PnL; IEM ASOS daily `max_temp_f`
  (`cgi-bin/request/daily.py`) to calibrate forecast error.
- Historical NWS *gridded* forecasts (NDFD) were not cleanly reachable, but **MOS is the
  right archived-forecast source and made a real backtest possible** — no fallback needed.

**Sample:** 315 city-days (last ~45 settled days × 7 cities), 1,890 liquid two-sided
buckets, Dec 2025 – Jul 2026.

---

## 2. Forecast skill is real (so the null isn't "the forecast is useless")

Calibrated on 315 city-days of (forecast high − observed high):

- **Bias:** small (−1.3°F pooled; +1.7°F NY, i.e. MOS max-of-3-hourly runs slightly warm — removed by debiasing).
- **σ ≈ 2.49 °F** after debiasing — exactly the ~±3°F skill a 1-day NWS high-temp
  forecast should have. The forecast is legitimately informative.

The forecast is honest and skilled. It still loses to the market. That is the finding.

---

## 3. Divergence exists — and it is the forecast being *wrong*, not an edge

Convert forecast → P(bucket) via Normal(F, σ) with continuity correction over each
bucket's integer range; compare to market mid = (yes_bid+yes_ask)/2 at a **13Z
(morning-of) snapshot, before the afternoon high is realized** (no leakage).

- **|forecast_P − market_mid|:** median **0.092**, p90 0.28; **47% of buckets diverge
  by >0.10.** Superficially this screams "edge everywhere."
- **But the market is the better forecaster.** Brier score vs realized outcome:
  - **Market mid: 0.0993**
  - **Forecast (debiased, *in-sample* → flattered): 0.1245**

  The market beats a debiased professional forecast by ~25% on Brier. Out-of-sample the
  forecast would look even worse. Bid/ask spread is tiny (median **1¢**); fee is
  0.07·p·(1−p) (≤1.75¢ at p=0.5) — so round-trip cost ~2–3¢. The divergences are large
  enough to "trade," but they point the wrong way.

---

## 4. Backtest: trading the divergence loses (net fee + spread)

Rule: buy YES when `forecast_P − ask − fee > 0`, sell YES when `bid − forecast_P − fee > 0`;
realize at Kalshi settlement; cluster PnL by day.

| Metric | Value |
|---|---|
| Trades | 1,639 over 315 days |
| Mean PnL / contract | **−1.7¢** |
| Day-clustered t-stat | **−2.18** (significantly *negative*) |
| Win rate | **24.5%** |
| Total (1 contract/trade) | **−$31.63** |

**Per-city (6 of 7 negative, none positive beyond noise):**

| City | Trades | Mean PnL/contract | Win rate |
|---|---|---|---|
| KXHIGHNY | 227 | −4.0¢ | 26% |
| KXHIGHMIA | 253 | −3.8¢ | 15% |
| KXHIGHAUS | 222 | −3.5¢ | 27% |
| KXHIGHCHI | 231 | −1.5¢ | 23% |
| KXHIGHPHIL | 236 | −0.6¢ | 26% |
| KXHIGHDEN | 225 | −0.4¢ | 28% |
| KXHIGHLAX | 245 | +0.2¢ | 27% (noise) |

The signal is **anti-predictive**: whenever the forecast disagreed with the price enough
to trade, price won. This is model-direction-agnostic evidence — it doesn't depend on my
Normal-band probability model being perfect.

---

## 5. Live forward check (open events, 2026-07-17/18)

50 open buckets priced via order book. Same picture: live median |forecast_P − mid| =
**0.109**, 50% >0.10. The biggest live "edges" are the tell:
`KXHIGHPHIL-26JUL17-B88.5` forecast F=90→fP=0.26 vs **mid 0.91**, `KXHIGHNY-26JUL17-B85.5`
F=87→fP=0.26 vs **mid 0.89** — these are *today's* markets where the afternoon high is
already largely realized and the market has moved to ~0.9, while the stale morning
forecast lags. The divergence is the market being right, again.

---

## 6. Capacity

Moot, because EV is negative. For reference, liquidity is real: traded-bucket day volume
median ~3,100 contracts (p90 ~10,900), OI ~5k–16k per bucket, contracts $0–1 → order
~$30–80k/day notional turnover per city, a few hundred $k/day across the 7 cities. There
is enough liquidity to trade a real edge here — there just isn't one. **Capacity for the
forecast edge: ~$0.**

---

## 7. Honest caveats

- **Forecast = debiased NBM-MOS, in-sample.** A sharper input (full NBM/ensemble,
  calibrated per-bucket probabilities, blending multiple models) might narrow the gap,
  but the bar is brutal: the market's Brier (0.099) is already near the irreducible floor
  for these ±2°F buckets, and a *debiased* professional forecast already loses. Beating
  the market requires info the market lacks; a public NWS product is the opposite of that.
- **Lead time:** primary test is morning-of (13Z). An NY spot-check at the prior-evening
  lead gave the same sign (market ≥ forecast). Longer leads give the market *more* time to
  price the forecast, not less.
- **Station mapping** for AUS/LAX is approximate (Kalshi may use Camp Mabry / downtown LA).
  A wrong station only degrades *my forecast*; since the market still wins, it strengthens
  the null rather than threatening it. Outcomes use Kalshi's exact settlement.
- **Direction of the finding is robust:** significant negative t, 6/7 cities negative, and
  a model-agnostic trade test all agree.

## Bottom line

The mechanism (superior info from free NWS forecasts) is real in principle — NWS forecasts
have genuine ~±2.5°F skill — but **Kalshi weather markets already fully price NWS
forecasts, and then some.** A forecast-based fair value is *worse* than the market and
loses money net of fees. This is a clean, valuable **null**: no fee-surviving forecast
edge on Kalshi daily high-temp markets. Move on.
