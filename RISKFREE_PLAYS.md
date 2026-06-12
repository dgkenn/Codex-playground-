# Risk-free play taxonomy — exhaustive enumeration + test verdicts

The operator asked repeatedly whether there are OTHER risk-free plays beyond the maker-box. This is
the comprehensive map. Bottom line: **the patient maker-box is the only viable risk-free play in this
venue; the book is efficient to ~1 tick and no taker arbitrage survives fees.**

## The full structure list and its verdict

| # | Structure | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | **Maker box** (rest YES+NO same market, both fill → $1) | ✅ DEPLOYED | our core; risk = unpaired leg |
| 2 | Cross-asset hedge (BTC vs ETH/SOL binary) | ❌ dead | settlement variance (~0.08) swamps cross-cov (~0.03); 1-contract hedge raises variance 78-115% |
| 3 | Multi-asset certainty-gated boxes (eth/sol/xrp) | ❌ dead | OOS −31¢/day; 0 boxes complete at realistic queue |
| 4 | Late-window favorite (buy near-decided side) | ❌ dead taker | 96-100% win but ask prices it + cent-rounding fee; maybe maker-only, fill prob unknown |
| 5 | Perp / funding basis hedge | ❌ dead | min perp size ~$1000 notional ≫ our size; margin off |
| 6 | Calendar / overlapping-tenor arb | ❌ dead | Kalshi has no simultaneously-live crypto tenors with shared settlement |
| 7 | Maker-rebate harvest | ❌ dead | fee = $0, no rebate to capture |
| 8 | **Intra-market crossed box (taker)**: yes_ask+no_ask<$1 | ❌ none exist | scan below |
| 9 | **Complete-set Dutch book**: Σ yes_ask < $1 on a true partition | ❌ none exist | scan below |
| 10 | **Cross-strike vertical lock** | ❌ none real | scan below (all hits were phantom 1-lot quotes) |

## The live arb scan (2026-06-12, ~270 Kalshi markets, public REST, fees applied)
Scanned every active market for structures 8-10. **The trustworthy result is the distribution, not
the raw "hits":**
- **Median yes_ask + no_ask across 624 liquid markets = $1.0100** (min $1.0010, max $1.97). **NO single
  market has yes_ask+no_ask < $1** — zero intra-market taker arbs. The tightest book sits 0.1¢ ABOVE
  $1, i.e. the ~1¢ we already harvest as a MAKER is exactly the efficient-market spread; a taker
  cannot capture it.

### ⚠️ The big "net¢" numbers in the raw scan are FALSE POSITIVES — do NOT chase them
The scanner flagged "Dutch-sell" sums like KXNASDAQ100U Σbid=$39 over 60 legs (net "3749¢") and
"Dutch-buy" sums like KXBTCMAX150 Σask=$0.10 over 4 legs (net "86¢"). These are NOT arbs: those
strike ladders are **monotonic/nested** ("index above X at 16:00", "max ≥ X"), not mutually-exclusive
exhaustive partitions. Multiple legs resolve YES simultaneously, so selling/buying the whole ladder is
naked directional risk, not a locked $1 — the scanner's partition assumption was wrong. Likewise every
VERTICAL_LOCK / DUTCH hit had size=1, vol_24h=0 (stale single-contract phantom quotes that vanish on a
real order). A genuine 90¢-free edge does not persist through a scan in a bot-traded market.

## Conclusion
The market is efficient to within the minimum tick. No risk-free TAKER play exists; the only risk-free
edge is the MAKER spread, which is precisely the box we already run. The productive levers remain what
they were: (1) second-leg execution (the completion chase, now live), (2) the toxicity exit/gate under
A/B test, (3) eventual size-up per SCALE_GATE.md — NOT a new arb structure. A continuous Dutch-book
taker scanner is not worth building: the genuine partitions are priced ≥$1 and the apparent dislocations
are nested-ladder artifacts. Re-scan only opportunistically; do not staff a taker bot against this book.
