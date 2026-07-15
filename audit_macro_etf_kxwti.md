# Paper Sleeve Edge Audit: macro-paper, etf-paper, kxwti-paper

## Audit Date: 2026-07-15
**Methodology**: Real settlement P&L only (not self-reported metrics or pre-entry edge estimates).

---

## 1. MACRO-PAPER (CPI/Fed decisions on Kalshi)

**Verdict**: INSUFFICIENT-DATA

**Analysis**:
- 10 pending positions created 2026-07-12; 8 have matured (close_time < 2026-07-15).
- Pre-registered bar (per workflow docstring): >=6 settled events AND aggregate t>=2.
- **Critical gap**: macro_settled.jsonl does NOT exist on origin/gha-data. The pending.json file contains only entry_price and edge_at_entry; no settlement prices or realized P&L recorded.
- Without settlement data (actual Kalshi close prices vs. entry), cannot compute realized P&L or t-statistic.
- **Status**: 8 positions mathematically settled, but settlement results never recorded. Cannot render verdict on edge.

---

## 2. ETF-PAPER (Portfolio + allweather trend overlay)

**Verdict**: ILLUSION

**Analysis**:
- Track record file: gha_data/paper/portfolio_paper_track.jsonl contains only 2 data points (2026-06-29 and 2026-07-13).
- Period return: +1.08% (+$10.39 on $1,000).
- Target validation metric: rolling Sharpe >=0.7 over 3–6 months.
- **Critical gap**: 2 weeks << 3-6 months. Insufficient data to establish rolling Sharpe; one positive week shows no edge. 
- Early-stage position paper marked as edge when it is merely warm-start drift.
- **Status**: No forward proof yet; early positive performance at week 2 is noise, not edge.

---

## 3. KXWTI-PAPER (WTI oil daily strike maker ladder on Kalshi)

**Verdict**: NULL

**Analysis**:
- Pending data: 630 total positions (79 filled, 551 resting) created from 2026-07-12 snapshots.
- Pre-registered bar: >=14 forward days, day-clustered t>=3, positive on >=80% of days.
- Filled positions show: 100% of entries had edge_at_quote > 0 (average +10.95% pre-entry edge).
- **Critical gap**: No settlement data. Pending file has only entry-side metrics (quote_price, edge_at_quote, fair_p_at_quote); no settlement prices, no realized P&L (kxwti_settled.csv does not exist).
- Pre-entry edge of +10.95% is a venue-scan signal, not realized performance. Market could have gapped or filled moved against positions after entry.
- **Status**: 79 filled positions show theoretical positive edge, but actual settlement results never recorded. Cannot confirm REAL EDGE vs. markout illusion.

---

## Summary

| Sleeve | Verdict | Reason |
|--------|---------|--------|
| **macro-paper** | INSUFFICIENT-DATA | 8 matured positions but macro_settled.jsonl absent; no realized P&L recorded |
| **etf-paper** | ILLUSION | 2 weeks of +1.08% return; far below 3-6mo validation window. Early noise, not edge. |
| **kxwti-paper** | NULL | 79 filled positions, 100% positive pre-entry edge, but kxwti_settled.csv missing; no realized P&L to verify |

**Conclusion**: None of the three sleeves have convincing evidence of real edges. Macro and KXWTI suffer from missing settlement data (workflows not committing settled.jsonl/.csv files). ETF-paper shows early positive performance but only 2 weeks in—insufficient to clear rolling Sharpe >=0.7 validation bar. Be unsparing: null verdicts and INSUFFICIENT-DATA are expected early-stage outcomes. Do NOT deploy any of these live until real, post-settlement P&L data confirms the edge.
