#!/usr/bin/env bash
# One-shot apply of the three live-path fixes to the live bot branch.
# Built + Fable-safety-reviewed + orchestrator-verified on claude/calci-trading-bot-strategy-mgyxti.
# Full rationale: venue_expansion/FORWARD_DATA_2026-08-02.md ; details: livefix/APPLY.md
set -euo pipefail

RESEARCH_BRANCH=claude/calci-trading-bot-strategy-mgyxti
LIVE_BRANCH=claude/coding-bot-ab-test-results-ffmhxw

echo ">> fetching"
git fetch origin "$RESEARCH_BRANCH" "$LIVE_BRANCH"
git checkout "$LIVE_BRANCH"
git pull --ff-only origin "$LIVE_BRANCH"

echo ">> pulling reviewed copies"
git checkout "origin/$RESEARCH_BRANCH" -- livefix/

for f in kalshi_exec.py kwx_forward.py kwx_paper_gate.py wx_forecast_model.py wx_forecast_forward.py; do
  cp "livefix/$f" "./$f"; echo "   applied $f"
done
cp livefix/livefix_selftest.py ./livefix_selftest.py

echo ">> selftest (expect: Ran 28 tests ... OK)"
python3 livefix_selftest.py

rm -rf livefix
git add -A
git commit -m "Fix dead v2 order endpoint, phantom-win scoring, bracket-floor convention

- kalshi_exec: migrate to POST /portfolio/events/orders on external-api.kalshi.com;
  single-book translation (buy NO at P == sell YES at 1-P); fill VWAP translated back
- kwx_forward/kwx_paper_gate: _is_scoreable requires numeric filled>0 AND a fill status,
  so rejected orders can no longer be scored as wins (cap_c fallback removed)
- wx_forecast_model/_forward: bracket convention derived from 616 settled rows vs official
  results (full bracket lo<=X<=hi; cap-only X<hi); 21.9% -> 7.0% disagreement"

cat <<'MSG'

=========================== DONE — NOW DO THE PRE-FLIGHT ===========================
The order path has NEVER touched a live Kalshi endpoint. Before trusting it, with
KWX_SWITCH=off and 1 contract only:

 1. Fire ONE 1-contract NO buy on a cheap ticker.
 2. GET /trade-api/v2/portfolio/positions  ->  confirm the position is NO / SHORT-YES,
    NOT long YES.  <-- the single assumption the whole migration rests on
 3. Capture the verbatim 201 body; confirm keys are literally fill_count and
    average_fill_price (strings). If renamed, _parse_fill returns filled=None, which
    kwx_runner.py:679 treats as a fire with no fill and no error.
 4. Confirm exec-log fill_vwap_c equals the price paid PER NO CONTRACT (not the YES price).
 5. Auth: orders now go to external-api.kalshi.com while reads stay on
    api.elections.kalshi.com. A key mismatch shows up as a 401 on that first order.
Then: git push origin HEAD
====================================================================================
MSG
