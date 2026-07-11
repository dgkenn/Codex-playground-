# MM_FINGERPRINT.md — maker-fingerprint competition monitor (2026-07-11)

**Question:** who else is market-making the KX{BTC,ETH,SOL,XRP}15M books, and — the leading
indicator of edge decay — has a NEW maker arrived recently? Run on the last 14 days of real
collected data (`gha-data` branch, 2026-06-28 → 2026-07-11, ~60k book snapshots/day/asset).

Tool: `mm_fingerprint.py` (offline; reads `gha_data/<date>/book_kalshi_<asset>15m_r*.jsonl.gz`).
Full per-day output: `mm_fingerprint_summary.json` (run `python mm_fingerprint.py --data-dir
gha_data --days 14` after fetching the gha-data branch).

## Methodology (heuristic clustering — read LIMITS before believing any number)

Kalshi's public book/trade feeds carry **no order IDs and no participant identity** — only
anonymous aggregate size per price level. So a "maker" here is a **size-repetition signature**:
a resident ladder-MM quotes many price levels at a near-identical size (the pattern FINGERPRINT.md
verified in June: e.g. BTC laddered at 265/250 across dozens of levels), which a population of
independent retail orders would not coincidentally produce at that level count. Per snapshot we:

1. Count sizes >= 50 contracts repeated at >= 8 distinct price levels on a side (a "ladder
   signature").
2. Keep signatures present in >= 5% of a day's snapshots; report as a "maker" at >= 10% coverage
   (the stricter bar avoids round-lot coincidence inflating the count).
3. Merge a YES-side and a NO-side signature into one two-sided maker when they co-occur in >= 60%
   of snapshots.
4. **TOB share** = fraction of a signature's snapshots where the top-of-book size is within 15% of
   the signature size (i.e. the touch IS that maker).
5. **Cadence** = median gap between changes of the price-level set holding the signature.
6. **Week-over-week NEW-MAKER flag**: a recent-week cluster with TOB share > 20% whose size
   (±12%) never appeared in the prior week's signature set.

## Findings — last 14 days

| asset | est. distinct ladder makers (median/day) | two-sided presence | dominant signature (latest day) | dominant TOB share | reshape cadence | NEW-MAKER flags |
|-------|----------------------------------------|--------------------|-------------------------------|--------------------|-----------------|-----------------|
| btc   | ~6 signatures (likely 1–2 real firms, see below) | 0.69–0.78 | 300/550 + 350/350 ladders, ~45% of snapshots | **5–8%** | 1.2s | **none** |
| eth   | 2 | 0.08 | single 90-lot ladder, ~43% of snapshots | 8–12% | 1.2s | none |
| sol   | 0–2 (marginal 50-lot) | 0.00 | none on 07-10/07-11 | ~1–2% | — | none |
| xrp   | **0** | 0.00 | none, all 14 days | — | — | none |

### BTC — the current-competition read (the one that matters for our live maker)

- **No new competition arrived.** Zero NEW-MAKER flags across the 14 days. The largest
  top-of-book share held by ANY single signature in the most recent week was **9.8%**
  (a 550/550 cluster on 07-05) — less than half the 20% alarm bar. Week-over-week signature
  sets fully overlap (weekA sizes {100…700} all reappear in weekB within tolerance).
- **The book is still one dominant mechanical resident MM + retail.** The top 3 daily clusters
  (300/550, 550/300, 350/350 on 07-11) co-occur, share the same 1.2s reshape heartbeat, and use
  sizes from one 25/50-multiple family that rotates day-to-day (425→650→300/550…). That is far
  more consistent with **one firm re-parameterizing its ladder** than with several independent
  firms — the same actor FINGERPRINT.md profiled in June (then quoting 300/315; the 1.2s
  mechanical heartbeat is unchanged). Headline "6 makers/day" is an upper bound on signature
  count, not a firm count.
- **The top of book is NOT signature-dominated: dominant-cluster TOB share is only ~5–8%.**
  ~92% of the time the touch is small odd-lot size — retail and small makers (our class). The
  ladder-MM provides depth BEHIND the touch; queue competition AT the touch remains thin. This is
  the direct micro-condition our maker edge depends on, and it is intact.
- **Change vs the June census: the hour-22 MM absence is gone.** Signature presence is now ~100%
  in every UTC hour (June: median ladder depth 0 in hour 22). The thin-competition hour no longer
  exists — remove it from any schedule reasoning.
- Two-sided presence ratio 0.69–0.78 (dipped to 0.55 on 07-07, recovered) — the resident MM
  quotes both sides most of the time; no persistent one-sided (directional) reconfiguration.

### ETH / SOL / XRP

- **ETH:** one stable ~90-lot ladder signature, mostly ONE-SIDED (two-sided ratio ~0.08), TOB
  8–12%. Note the June census sized ETH's MM at 20/21 — the size family has shifted to 90 since;
  with no order IDs we cannot distinguish "same firm resized" from "replacement firm," but during
  this 14-day window it is one stable signature, under the flag bar.
- **SOL:** the marginal 50-lot signature disappeared entirely on 07-10/07-11 — effectively **no
  resident ladder maker** right now.
- **XRP:** zero qualifying signatures on all 14 days. Nobody ladders this book at detectable
  scale. (Thin competition, but also no MM absorbing toxicity — consistent with why we trade BTC.)

## LIMITS — what this analysis cannot see (honest list)

1. **No order IDs.** Everything above is heuristic clustering on public aggregate size. Two
   signatures ≠ two firms (BTC's clusters almost certainly ONE firm); one signature could in
   principle be two firms coincidentally using the same size.
2. **Size-randomizing or single-level makers are invisible.** The detector keys on size
   repetition across >= 8 levels. A sophisticated competitor that randomizes size or quotes only
   the touch (the dangerous kind for queue competition) leaves no ladder signature. TOB share of
   *unmatched* sizes (~92% on BTC) bounds where such an actor could hide; a sustained JUMP in
   dominant-cluster displacement or our own live fill-rate/markout decay (live_recon +
   order_lifecycle logs) is the complementary detector.
3. **Cadence is snapshot-limited.** The collector samples ~1.2–1.4s, so "1.2s cadence" means
   "reshapes at least as fast as we sample" — consistent with, but not independent proof of, the
   1.2s WS-measured heartbeat from June.
4. **TOB share is exact-size-matched (±15%).** A maker quoting a different size at the touch than
   in its ladder is undercounted at the touch.
5. **Two weeks of data, one venue, 15m crypto series only.** The week-over-week split is 7d vs 7d
   inside the same fortnight; a maker that arrived >2 weeks ago already counts as "known".

## Verdict

**Competition on KXBTC15M is unchanged: one mechanical resident ladder-MM (same 1.2s heartbeat as
June) plus retail; no new maker signature took meaningful top-of-book share in the last two weeks
(max 9.8% vs the 20% alarm bar); the touch remains ~92% small-lot.** The edge-decay early-warning
is quiet. Re-run `mm_fingerprint.py` weekly (it is cheap) and treat a NEW-MAKER flag — or a
sustained drop in our own fill-rate at unchanged quote quality (order_lifecycle log) — as the
signal to re-evaluate before scaling.
