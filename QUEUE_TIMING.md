# QUEUE_TIMING — can heartbeat-timed requoting cut the BTC-box strand below ~5%?

**Verdict (one line): NO. The box is structurally last-in-queue from this cloud infra and
heartbeat-timed requoting (`--qtime-mp-margin`) cannot clear the ~5% strand bar. To make the box
+EV the live strand must fall from ~22% (q0≈8000) to <4.4%, which requires a ~90% queue-position
cut to q0<~815. The one lever that actually buys q0→0 is improve-tick, and it costs ~1c/box — more
than the entire +0.69c edge — so it converts the edge negative on the BALANCED majority while only
marginal on the unidentifiable strand subset. `qtime` fires on the wrong subset (diverging-touch
fills, which are already the toxic ones) and, even at its optimistic q0→0 upper bound, blends to
~7–9% strand at sensible margins — still ABOVE the bar. Our react+order-ack latency cannot win the
sub-1.2s race against a co-located mechanical MM whose heartbeat EQUALS our poll cadence (both
1.2s). The box stays dead at our bankroll; this is the decisive finding.**

The brief's make-or-break question — "can we get strand <5% by improving queue position?" — resolves
to NO on every lever tested, net-of-edge-cost and haircut for tape-optimism.

---

## Data window, N, costs

- **LIVE queue position:** every commit of `origin/live-state`, days **2026-06-13/14**.
  `kalshi_fees_btc15m.jsonl` raw fills dedup by `trade_id` → **771 fills** (452 with `resting_s`);
  `kalshi_winrec_btc15m.jsonl` dedup by `ws` → **61 winrecs**; `kalshi_markout.jsonl` → **2968
  per-fill markout records**. Each fill `ctx` carries `resting_s`, touch depth `bq/aq`, `mid`,
  `micro`, `spot`, `sig`.
- **MM heartbeat + strand sim (TAPE, SCREEN):** `origin/gha-data` `book_kalshi_btc15m_*.jsonl.gz`
  (full-depth ~1.2s book snapshots + spot, days 2026-06-11..14, **103 files / ~197k snapshots**)
  × `trades_kalshi_btc15m_*.jsonl.gz` (**~2.8M taker prints**). Strand sim runs on **310 windows**
  with both book-dwell and tape flow (**103 windows** have local book-dwell episodes).
- **Costs / economics:** maker legs fee-free (post-only); a crossing/disposal pays Kalshi taker fee
  `ceil(M·P·(1−P)·100)/100`, M=0.07. Clean paired edge **+0.69c/box** (AUDIT_EDGE, 62 live boxes);
  bounded disposal **~−15c/strand** (BOX_SIZING post-fix). Break-even strand
  = 0.69/(15+0.69) = **4.4%**.
- Script: `queue_timing.py` (self-contained; walks live-state commits, reads book+trade tape).
- **Backtests SCREEN.** Tape queue sim is OPTIMISTIC (real latency/queue is worse) — haircut applied
  in the verdict.

---

## 1. LIVE queue-position estimate — we are NOT front-of-queue (confirms q0≈8000)

`resting_s` = how long our order sat before it filled. Front-of-queue at a touch being hit fills
near-instantly; deep-in-queue waits a heartbeat or more.

| metric | value |
|---|---|
| resting_s before fill | **median 1.37s**, mean 1.87s, p75 2.31s, p90 3.74s |
| frac resting <0.3s (front/instant) | **7.7%** |
| frac resting >2.0s (sat in queue) | **34.7%** |
| same-side touch depth we join behind (`bq`/`aq`) | median 519, mean 903, p90 2132 |

**We rest ~1 full MM heartbeat (1.37s ≈ 1.2s) before filling and only 7.7% of fills are
front-instant.** We sit behind the resting ladder, not ahead of it — the live realization of the
backtest's optimistic q0=0. Markout confirms the toxicity of last-place fills:

| markout split by `\|micro−mid\|` at fill | n | markout |
|---|---|---|
| < 0.003 | 691 | −0.17c |
| 0.003–0.006 | 980 | −0.58c |
| **≥ 0.006 (touch about to move)** | **79** | **−4.01c** |

The fills that happen when the touch is diverging — the exact regime `qtime` targets — are the
**most toxic** (−4.01c). We get filled last, at a stale price, right as the touch runs. This is the
queue-position signature: when it matters, we are at the back. (Markout by resting time is non-
monotone — +0.59c <0.5s, −0.48c 0.5–2s, +0.53c >2s — because the >2s survivors are the calm windows
where the touch never moved; the divergence cut above is the cleaner read.)

Committed-window strand rate in this slice is 4/61 (6.6% all) / 4/34 (**11.8%** of traded windows) —
above the 4.4% bar. The sibling's settle-based **21.9%** (q0≈8000, 96 settled markets) is the
authoritative live anchor; the small committed-winrec slice agrees directionally (well above
break-even).

## 2. MM heartbeat — mechanical 1.2s, and it EQUALS our own poll cadence

| measure (tape) | value |
|---|---|
| book snapshot / our poll cadence | **1.20s** (median, p10=p90=1.20 — rock-steady) |
| touch-change interval (MM requote at best level) | **1.20s** median |
| modal ladder sizes (MM fingerprint) | YES/NO **300 / 265 / 315** repeated (BTC ladder MM) |
| reprice lag after ≥8bp spot move (n=129 moves) | median 0.0s, mean 1.53s, p75 1.20s |
| frac touch still stale 3s after move | 9.3% |

The ladder MM is mechanical and re-prices its **touch** within ~1 snapshot of a spot move. The
decisive structural fact: **our snapshot+loop cadence (1.20s) is identical to the MM heartbeat
(1.2s).** The exploitable "gap between a spot move and the MM's next heartbeat" is *sub-1.2s* — and
that window is **below our data resolution AND below our cloud react+order-ack latency** (book
`rtt_ms` median ~27ms one-way, plus decide + order ack on GitHub Actions). There is no reliable
window in which a seconds-latency cloud bot lands AHEAD of a co-located mechanical MM that reprices
on the same cadence. (FINGERPRINT's "74% stale @3s" is per-LEVEL across the deep ladder; the TOUCH —
what governs queue resets for our completing leg — tracks spot within one heartbeat, so the touch is
not the slow-stale part we could exploit.)

## 3. qtime heartbeat-timed requote simulation — does NOT reach <5%

Strand is a monotone function of queue position q0. My independent temporal **dwell model**
(strand iff no single touch-dwell episode brings >q0 taker flow at our price before the touch moves;
touch DWELL median 2.40s) reproduces the sibling's LIVE-validated q0→strand curve:

| q0 | strand (my dwell model, this tape) | strand (sibling LIVE anchor) |
|---|---|---|
| 0 | 0.0% | 1.3% |
| 300–1000 | 6.8% | — |
| 2000 | 10.7% | 8.9% |
| 8000 | 66.0% | **21.9% (LIVE)** |
| 15000 | 97.1% | 41.5% |

Both curves are monotone and steep (mine steeper at high q0; the sibling's settle-calibrated curve is
the trusted one for inversion). **The 4.4% break-even strand is reached at q0 ≈ 815** — i.e. live
q0≈8000 must drop **~90%** to clear the bar.

**Can `qtime` deliver that?** `qtime` only fires when microprice diverges from mid (touch about to
move). Sweep of the margin against where it fires and the OPTIMISTIC upper bound (assume it lands us
q0→0 on EVERY firing fill, q0=8000 otherwise; blend via the sibling curve):

| `--qtime-mp-margin` | fires on % of fills | strand UPPER BOUND | <4.4%? |
|---|---|---|---|
| 0.002 | 71.9% | **7.1%** | no |
| 0.003 | 59.5% | **9.6%** | no |
| 0.005 | 11.9% | 19.4% | no |
| 0.008 | 4.0% | 21.1% | no |

**Even the unrealizable upper bound (perfect front-of-queue on every firing fill) never reaches
4.4%.** Two reasons: (a) the divergence trigger fires on the *toxic* fills (§1: −4.01c markout at
≥0.006 div) — landing front there just means filling faster INTO a move; (b) the strand-driving
touches are the stable-then-suddenly-gone ones the divergence signal does not pre-empt. The sweep is
a **plateau (7–9% at low margins), not a spike** — no threshold clears the bar. Haircutting this
tape-optimistic upper bound for real cloud latency pushes realized strand back toward the live 22%.

The prior `queue_q2_analysis.py` separately showed `qtime` at 0.003 *gives up positive markout*
(repricing at small divergence forfeits real value; break-even margin ~0.005). But that is a thin
markout question — even at the favorable margin the **strand never clears 4.4%.** `qtime` is at best a
small markout lever, not a strand fix.

## 4. Other queue levers — none move us up the queue from cloud latency

- **improve-tick (quote 1 tick better to jump the whole queue, q0→0).** BTC 15m mid-band tick =
  0.01 = **1c**. The edge is +0.69c/box. Improving 1 tick on a single (completing) leg costs **1c** —
  already larger than the edge (turns it to −0.31c). It buys strand ≈1.3% (q0→0), saving
  (0.219−0.013)×15c ≈ **+3.1c** vs the 1c tick → net ≈ **+2.1c on the strand-prone subset**, BUT it
  is a pure **−1c** drag on the BALANCED majority (~78% already-paired), which the +0.69c edge cannot
  absorb. improve-tick "works" only if applied selectively to the ~22% of boxes that WILL strand —
  unidentifiable ex-ante (BOX_ADVERSE_OPEN: toxicity invisible at open, OOS AUC 0.56). Blended across
  all boxes it erodes the edge negative. **Net: improve-tick trades a strand problem for an
  edge-erosion problem; it does not make the book +EV.**
- **Faster react-loop / earlier WS placement.** Binding constraint is order-ack latency, not loop
  frequency. The MM heartbeat (1.2s) equals our poll; to land front we must detect→decide→ACK inside
  1.2s against a co-located mechanical actor. From GitHub Actions (~27ms book rtt one-way + order
  ack) this is not reliably winnable. Faster cadence than 1.2s does not help.
- **Post both legs in one batch (simultaneous quoting).** The sibling's g=0 / Lever A: shrinks the
  legging gap but does NOT move us up either queue — it is exactly the q0=0 optimism we cannot
  realize. Marginal.

## 5. Verdict — structurally last-in-queue; box dead at our bankroll

**Strand cannot reach <5% via queue-timing.** Every path fails the net-of-cost, haircut bar:

1. **qtime** never clears 4.4% even at its q0→0 upper bound (plateau 7–9%), and it fires on the
   already-toxic diverging-touch subset. Realistic (haircut) effect ≈ live 22%.
2. **improve-tick** is the only lever that truly buys q0→0, but at 1c/box it exceeds the 0.69c edge —
   negative on the balanced majority, only marginal on the unidentifiable strand subset.
3. **cadence / WS-early / batch** do not move queue position from seconds-latency cloud infra; the MM
   heartbeat equals our poll and it is co-located.

Root cause is infrastructure: **a GitHub-Actions cloud bot with ~1.2s poll and seconds order-ack is
structurally behind a mechanical ladder-MM that reprices its touch on the same 1.2s cadence.** We
fill last (median resting 1.37s ≈ one heartbeat; only 7.7% front-instant; most-toxic fills exactly
when the touch diverges). This is the live realization of the backtest's q0=0 optimism and it caps
the box at q0≈8000 → ~22% strand → negative EV.

**Recommended config: do NOT enable `--qtime-mp-margin` as a strand fix.** If run at all for the thin
markout lever, use **0.005** (not 0.003 — 0.003 forfeits positive markout per `queue_q2_analysis`),
but expect ~zero strand benefit. **Do NOT enable improve-tick** (erodes the edge). The deployable
wins are loss-MITIGATION, not queue improvement — the sibling's C1/C2 (`--dispose-cross-s 25`,
`--dispose-max-give 0.25`, `--chase-max-give 0.06`, + post-completion same-side cancel/freeze), which
bound the strand COST without touching queue position. **Net: the box is structurally last-in-queue
from this infra and cannot clear the 5% bar; treat it as dead at our bankroll unless the execution
venue / latency changes.**

*Live = 771 fills / 61 winrecs / 2968 markouts, days 2026-06-13/14 (all live-state commits).
Tape SCREEN = 103 book files (~197k snaps) × ~2.8M trades, 310 windows (103 with book-dwell),
days 2026-06-11..14. Costs: maker fee-free, taker M=0.07; edge +0.69c, disposal −15c, break-even
strand 4.4%. SCREENS in `queue_timing.py` stdout.*
