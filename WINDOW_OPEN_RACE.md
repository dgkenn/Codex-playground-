# Window-open race — VERDICT: NO-GO at REST latency

**Study:** `window_open_race_study.py` (study 4 of the scaling batch). Asks whether t=0 (the moment a
15-min window opens) is contestable at REST latency, using the durable gha-data book stream
(`overnight_data/book_kalshi_btc15m_*.jsonl.gz`, full-depth + spot + `rtt_ms`, ~1.2s cadence).

## What the snapshots show
- **Coverage:** 136 windows present; only **21** have a snapshot within 15s of open (the collector
  rarely catches a window from near t=0 — only 1 window starts <1.5s in). Low-N; read accordingly.
- **The book is born tight, before we arrive:** in **21/21 (100%)** covered windows the very first
  snapshot is already a two-sided tradeable book. Book-birth time-from-open: p10 7.2s, p50 14.4s,
  p90 14.8s. No dead / one-sided interval is observable at our polling resolution.
- **Arrival lag dominates everything:** our first REST snapshot lands at **~14.4s (p50)** from open.
  REST `rtt_ms` is tiny (p50 30ms, p90 67ms) — irrelevant next to the 14s arrival lag. Structural
  floor ≈ 14.5s.
- **No early edge survives:** early spread (3–10s) p50 1c / p90 3c vs settled (30–60s) p50 1c /
  p90 2c — the 1c is just the normal market spread. Wide (>2c) spread surviving to our latency
  floor occurs in only **3/21 (14%)** windows, and even those are measured at our 14s arrival, not
  true t=0 where a real opener would compete.

## Verdict
**NO-GO. Do not build an open-quote / window-open-race strategy at REST latency.** Three compounding
reasons: the book is already tight at first poll (100%), our ~14s arrival lag obliterates any t=0
edge, and the rare wide-open spread (14%) neither survives nor is even measured at true t=0. The
collector's REST cadence cannot see the contest, let alone win it.

**If ever revisited:** it would require sub-second **WebSocket** infrastructure and a fresh
data capture from true t=0 (this dataset has only 1 window <1.5s) — a different project, not an
increment on the current REST stack. Park it; the maker-box edge does not live at the open.
