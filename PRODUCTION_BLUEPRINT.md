# Production build roadmap (live deploy — you run this on your infra)

> _Historical — superseded by the gating validation + 4-day multi-asset data. Kept for provenance; where this disagrees with current docs, **README.md / GATING.md / INSIGHTS_4DAY.md win**._

Canonical infra plan for taking the validated strategy live. Research here is READ-ONLY
paper; everything below is the **live build you own**. Strategy = done; this is the gap.

## Status map
| # | Component | Status | Where |
|---|---|---|---|
| 1 | **Low-latency / queue priority** — Europe VPS (Dublin/London/Frankfurt, sub-5ms to CLOB), 4-8 core, NVMe, Linux net-tuning | TODO (your infra) | decisive lever for fill rate |
| 2 | **Real-time WebSocket feed** + in-memory book + reconnect/gap-resync | DONE (paper) / port to live | `paper_trader_ws.py` |
| 3 | **Async OMS**: idempotent `client_order_id`, token-bucket rate limit, batch cancel/replace, partial-fill tracking, query-before-retry, reconcile on disconnect/restart/every-5min by client_order_id | TODO (scaffold) | extend `live_trader.py` w/ `py-clob-client-v2` |
| 4 | **Risk engine**: real-time net-delta, 25% skew cap, kill-switch (loss>5%, latency>50ms→pause, WS down>5s→flatten, rate-limit→degrade) | rails in scaffold; harden | `live_trader.py` |
| 5 | **Fee/rebate + markout monitoring** (per-side EWMA markout, vig, rebate %, fill rate) | DONE offline | `audit_report.py` |
| 6 | **Key security**: AWS Secrets Manager / Vault / HW / MPC; trading-only keys (no withdrawal); rotate 90d; env injection | TODO (your infra) | never plaintext |
| 7 | **Monitoring/state**: Prometheus+Grafana+Alertmanager; Postgres+Redis checkpoint every 5s (orders, inventory, seq); structured logs | TODO (your infra) | survive restarts, no inventory drift |
| 8 | **Capital + multi-market**: ~$5-10k/market; run BTC 5m/15m + ETH/SOL/XRP 15m on one server (shared WS/OMS) | scale after pilot | edge is per-share -> needs size+breadth |

## Decisive sequence (from the blueprint)
1. WS feed + in-memory book (done in paper) → 2. async idempotent OMS → 3. risk engine + kill-switch → 4. monitoring/alerting → 5. state persistence → 6. key security → 7. markout monitoring.
**Paper-trade 2-4 weeks, measure FILL RATE.** >50% → won the queue, scale capital. <30% → fix latency before adding money.

## Alert thresholds (live)
latency warn>20ms/crit>50ms; fill_rate warn<40%/crit<20%; P&L drawdown warn-2%/crit-5%;
vig<0.8c (overround compression); rebate<15% of taker fees; markout loss>0.5c (picked off).

## Cost ~$70-220/mo
Europe trading VPS $50-150; Secrets Manager ~$5; Prometheus/Grafana $0 (OSS); managed Postgres $15-50.

## Honest framing
Live profitability is ~90% infrastructure, 10% strategy. The edge (vig + rebate, market-neutral
via skew) is validated; whether it pays depends on **fill rate / queue position**, which only
items #1-3 + a tiny live pilot can settle. Use official `py-clob-client-v2` for execution;
consider Hummingbot / NautilusTrader (community Polymarket adapter) as the OMS shell.
