# archive/ — retired strategies

These are dead strategies and their old research. **None of it is imported or run
by the live K-WX weather bot** (see the top-level `README.md`). Kept for reference
only. Layout: `code/` (Python), `docs/` (markdown reports/plans), `data/`
(stale result/log/position files).

## Strategies (one line each)

- **box / boxwide** — the original Kalshi "box" arbitrage strategy; K-WX inherited its live-harness pattern and credentials env vars.
- **favlong / favlongshot** (`favlong_*.py`, `favlongshot_edge.py`) — favorite-longshot bias taker on Kalshi crypto/other ladders; tuning, isotonic map, v2 model, XRP segment work.
- **pmkt / polymarket** (`pmkt_*.py`) — Polymarket edges: categories, verticals, horizon/drift, copy-trade/wallet tracking, advsel, econ/biz/short-vol paper sleeves.
- **perp** (`perp_forward.py`) — crypto perpetual-futures forward strategy and placement study.
- **wing** (`kalshi_wing_*.py`, `wing_paper.py`, `analyze_wing.py`) — Kalshi wing/VRP maker (verify, VRP, cross-asset variants).
- **longshot** (`longshot_*.py`, `xcat_longshot.py`) — longshot timing / conditional / cross-category tail-bias studies.
- **btc / deribit derivatives** (`btc_*.py`, `deribit_density.py`) — BTC order-flow and derivatives backtests, Deribit option-density signal.
- **short-vol / VRP** (`*shortvol*.py`, `vrp_regime.py`, `xasset_shortvol.py`, `wang_transform.py`) — variance-risk-premium / short-vol sleeves across Kalshi, Polymarket, and cross-asset.
- **ETF / macro / WTI** (`kxwti-*`, macro/etf audits) — macro and ETF-driven Kalshi bracket paper strategies (KXWTI etc.).
- **kalshi trader experiments** (`kalshi_earnings.py`, `kalshi_spx.py`, `kalshi_theta_decay.py`, `kalshi_new_listing.py`, `kalshi_maker_rebate.py`, `kalshi_structural_arb.py`, `kalshi_onetouch.py`, `kalshi_fast_sensor.py`, `kalshi_calibration.py`) — assorted Kalshi edges (earnings, SPX, theta decay, new-listing, maker rebate, structural arb, one-touch, calibration) — tested NULL or capacity-capped.
- **order-flow / OFI** (`ofi_*.py`, `trade_flow_*.py`, `fill_model.py`, `funding_basis_signal.py`, `momentum_edge.py`, `crossasset_edge.py`, `cross_venue_leadlag.py`, `xvenue_converge.py`) — order-flow imbalance, fill modeling, funding-basis, momentum, and cross-venue convergence research.
- **riskless / structural** (`riskless_*.py`, `bucket_arb.py`, `orthostack_*.py`, `strand_model.py`, `edge_capture.py`, `aggressive_frontier.py`, `daily_return_frontier.py`, `daily_shortvol.py`) — riskless-arb scans, bucket arb, ortho-stack RV, strand model, and daily-return frontier work.
- **early weather (pre-K-WX)** (`weather_edge.py`, `phase2_trackA_price.py`, `phase3_feed_correlation.py`) — earlier weather explorations superseded by the current K-WX runner; Track-A price backtest and feed-correlation study kept for provenance.
- **misc infra** (`portfolio.py`, `sizing.py`, `strategies.py`, `realized_pnl.py`, `settle_recorder.py`, `live_anchor.py`, `health_check.py`, `qcx_sports.py`, `pmkt_sportsbook.py`) — shared helpers and one-off tools from the retired multi-strategy program.

The corresponding `*_report.md` / `*_summary.json` / `*_positions.jsonl` files in
`docs/` and `data/` are the outputs of the studies above.
