# CLV Sleeve Audit: Weather & Sports

## Executive Summary

Audit of two paper trading sleeves that track CLV (closing-line value) as a proxy for edge. **Critical finding: Weather sleeve shows classic CLV-illusion pattern—positive CLV (+49.43) masks deeply negative realized settlement P&L (-11.84), violating the first principle that CLV must predict realized outcomes. Sports sleeve has no data collected.**

---

## 1. Kalshi Weather CLV (`gha_data/weather/weather_clv_log.csv`)

**Status:** ACTIVE, SETTLEMENT OUTCOMES RECORDED

### Data Coverage
- **Total bets logged:** 1,440 (583 signaled)
- **Date range:** 2026-06-15 to 2026-07-13 (28 calendar days)
- **Cities:** NYC, CHI, MIA, AUS, LAX, PHX, DAL, BOS
- **Settlement type:** Next-day high temperature brackets with actual_high recorded

### Realized P&L Analysis
- **Total realized P&L:** -11.84 (negative)
- **Mean P&L per bet:** -0.0203 (negative)
- **Median P&L per bet:** -0.0533 (negative)
- **Win rate:** 58/583 = 9.96% (severe underperformance)
- **Day-clustered t-test:** t = -1.68, p = 0.104 (not significant; no edge detected)

### CLV Proxy Analysis
- **Total CLV:** +49.43 (reported as positive edge)
- **Mean CLV per bet:** +0.0848
- **CLV vs realized P&L divergence:** P&L - CLV = -61.26 (massive misalignment)

### Verdict: **CLV-ONLY-ILLUSION**
The weather sleeve exhibits the exact pathology flagged in the task: positive CLV (+49.43) coexists with negative realized settlement P&L (-11.84). The 61-point divergence indicates the NBM fair-value model and Kalshi prices moved favorably on paper (CLV) but bets lost systematically in settlement. Root cause: either NBM forecast calibration is poor, or the strategy's entry signal over-fits CLV without edge in realized outcomes. Win rate of 10% is consistent with random chance on binary brackets.

---

## 2. Sports CLV (`gha_data/sports_clv/sports_clv.csv`)

**Status:** INSUFFICIENT DATA

### Data Collection
- **Workflow:** `.github/workflows/sports-clv.yml` (configured, runs 3x daily)
- **Data source:** Pinnacle h2h (sharp line) via the-odds-api + Kalshi YES mid snapshots
- **Target:** Track Kalshi-vs-sharp timing lag via cross-correlation at 0-15 min lags
- **Expected path:** `gha_data/sports_clv/sports_clv.csv` on gha-data branch

### Actual Status
- **File exists:** No
- **Rows collected:** 0
- **Reason:** ODDS_API_KEY secret not configured; workflow runs but collects nothing silently (design: no spurious commits without data)

### Verdict: **INSUFFICIENT-DATA**
Workflow is properly wired and idempotent (safe to run without credentials), but has never produced data. No settlement outcomes recorded. Cannot compute realized P&L or validate CLV. Requires the operator to add the `ODDS_API_KEY` repository secret (the-odds-api free tier, 500 req/month budget is within 360 req/month usage).

---

## Recommendations

1. **Weather sleeve:** Retire or redesign. The +49 CLV proves the model sees opportunity on paper, but the -12 realized loss proves it doesn't translate. Audit NBM calibration and consider whether spread/fee (1.6-1.8% typical) is too high for the signal's magnitude.

2. **Sports sleeve:** Enable by setting ODDS_API_KEY, then let it run 3-4 weeks to accumulate ≥100 snapshots before judging. Focus on realized settlement P&L of h2h bets (if Kalshi records them), not just timing-lag metrics.

3. **Program-wide:** Enforce CLV audit discipline: any sleeve with positive CLV and negative realized P&L must be flagged and explained before re-risking capital.
