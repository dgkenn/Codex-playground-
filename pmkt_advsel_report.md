# Polymarket short-vol longshot — ADVERSE-SELECTION tie-breaker

_Generated 2026-07-16T14:09:32.056311+00:00 | runtime 220s_

## Sample
- Resolved 7d weekly 'above on' markets enumerated: **6849**
- In longshot entry band YES mid [0.15,0.3] (causal first-half mid): **639**
- With >0 first-half YES-BUY taker volume (a resting seller could fill): **601**
- Distinct resolution weeks: **49**
- Mean causal entry mid in band: **0.2181**
- Global median half-spread (subtracted from PnL): **0.0065**
- Total first-half YES-BUY volume: **2,485,567 shares / $554,124**

## (a) TIE-BREAKER — YES-print rate: unweighted vs YES-BUY-volume-weighted

| weighting | realized YES-print rate |
|---|---:|
| UNWEIGHTED (per-market) | 0.1032 |
| YES-BUY-volume weighted (shares) | 0.0850 |
| YES-BUY-volume weighted ($) | 0.1029 |

- Share-weighted minus unweighted = **-0.0181**
- $-weighted minus unweighted = **-0.0003**
- **Adverse-selection direction: FAVORABLE (weighted print rate LOWER → Analysis A)**

### Why A and B disagree — total-market-volume vs YES-BUY taker weighting (same 601 markets)

| weighting scheme | print rate | Δ vs unweighted | corr(weight, yes_win) |
|---|---:|---:|---:|
| UNWEIGHTED (per-market) | 0.1032 | — | — |
| per-market TOTAL volume (**Analysis B's metric**) | 0.1055 | **+0.0024** | +0.006 |
| YES-BUY taker shares (**the decisive fills**) | 0.0850 | **−0.0181** | −0.034 |
| YES-BUY taker dollars | 0.1029 | −0.0003 | — |

The disagreement is entirely the weighting choice. Per-market TOTAL volume (both sides — includes NO flow and
YES-sell flow, which is heavy on markets that end up printing) tilts *mildly adverse* (+0.0024), reproducing
Analysis B. But the flow a resting SELLER of the YES longshot actually fills into is the **YES-BUY taker**
volume, and that tilts *favorable* (−0.0181, correlation with printing is negative). The seller does NOT
disproportionately fill the longshots that print — if anything slightly the opposite.

## (b) Seller PnL/contract = (entry_mid − outcome) − half_spread

| weighting | mean PnL/contract | week-clustered t | k weeks / n |
|---|---:|---:|---:|
| per-market EQUAL, week-clustered | +0.0902 | 3.73 | 49 |
| YES-BUY-VOLUME weighted (shares), week-clustered | +0.0900 | 2.88 | 49 |
| YES-BUY-VOLUME weighted ($), week-clustered | +0.0962 | 3.10 | 49 |
| FLAT pooled mean (iid SE) | +0.1057 | 8.45 | n=601 |

## (c) Tail

- Worst resolution-week PnL (equal-weight): **-0.4353** (2025-W40)
- Worst resolution-week PnL (YES-buy-vol weight): **-0.7252** (2025-W33)
- % negative weeks (equal-weight): **24.5%** of 49
- % negative weeks (YES-buy-vol weight): **20.4%** of 49

## VERDICT

**REAL & cost-surviving at realistic fills.** YES-BUY-volume weighting LOWERS the print rate (favorable adverse selection) and the seller PnL stays positive with week-clustered t≥2 net of half-spread. The data supports **ANALYSIS A** (favorable/real).
