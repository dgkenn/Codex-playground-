> **INTERIM, 216 of 503 hours (43.5%).** The container was restarted mid-study and the tape fetch
> was killed at 216 hours; the 216 are the exact head of the saved seed-20261027 shuffle (3 stragglers
> from a concurrent writer were moved to `cache/maker_fill/tape_stray/` so this is an airtight uniform
> subsample, not a near-prefix). The fetch has been restarted and the full-coverage run will replace
> this file.
>
> **Completing it cannot change the verdict, and here is the arithmetic.** The cluster unit is the
> calendar day and **59 of the window's 60 days are already covered** — the remaining hours fall
> *inside those same days*, so they add almost nothing to the day-clustered standard error. The best
> cell (T=15, k=1, N=25) has EV +0.516c per quoted contract with SE 0.983c, t=0.52 against a
> Bonferroni bar of 3.22. Clearing that bar needs SE to fall 6.1x, i.e. **~2,220 days ≈ 6.1 years**
> of this product. The verdict is INSUFFICIENT and more data of this kind cannot move it.

# Maker fill: does a fee-free resting ask on KXBTCD longshots survive adverse selection?  (MAKER_FILL_SPEC.md, executed)

**VERDICT: INSUFFICIENT**  (frozen PASS/KILL rule applied verbatim, N=25 decisive; numbers beside each bar in section 6)

Sample: 216 of 1408 hourly events, 59 UTC days, 7,716 quotes (placement sha256 `952024f7610125ca`), 7,716 with an official yes/no result.

## 1. Anchor (f): volume provenance -- resolution FIRST

**Resolution.** *Candle archive alone: NOT-MEASURABLE* for the pessimistic fill models (and for T=5 and the final five minutes of every cell). *Hugging Face `TrevorJS/kalshi-trades`: does not cover this window* (its card states trades run June 2021 - January 2026, last modified 2026-01-30; the universe is closes 2026-08-22..2026-10-20). *The public Kalshi API `GET /markets/trades` does carry the missing data* -- every print with `yes_price`, `count_fp`, `taker_side` and a microsecond `created_time` -- for exactly this window, so price-conditional volume is MEASURED from prints rather than attributed. The study below runs on that tape, fetched into `cache/maker_fill/tape/` for the 3,371 strikes the frozen placement rule quotes; no hour was added.

Why the candles cannot do it: a candle row carries total `volume_fp` plus only the trade-price low/high/open/close/mean of the minute. (1) If `high < a` the minute had no volume at >= a, and if `low >= a` all of it did -- both are identified. If `low < a <= high` -- the normal case for a quote one to three cents above the bid in a minute that traded on both sides -- volume at >= a can be anything from ~0 to the full minute, so the cumulative-volume-exceeds-N rule is undetermined. The volume-weighted mean narrows it but does not close it (F-ii). (2) Independently of that, the cache holds no candle after close-300s, so 'held to close' cannot be observed for any cell and T=5 has no post-quote data at all (F-iii).


**F-i. The tape reproduces the candle archive** (integrity of the replacement data). First 120 hours in work order, every candle minute with volume > 0, tape prints re-bucketed into (end-60s, end]:

* minutes compared: 22,529; exact per-minute volume match (|diff| < 0.015 contracts): 22,529 (100.00%); total candle volume 59,043,820.3 vs total tape volume 59,043,820.3 (ratio 1.0000).
* `price.mean_dollars` check on exactly-matching minutes (n=22,529): volume-weighted tape mean within 0.5c of the candle mean in 22,529 (100.0%); simple (unweighted) mean within 0.5c in 17,735 (78.7%). The mean-tightened bracket below therefore rests on a validated, not assumed, definition.

**F-ii. What the candles alone can and cannot say (N=25 pessimistic, in-window only, T=5 excluded because no post-T candle exists).** `rigorous` = bracket from trade-price low/high only; `mean-tight` = also uses the volume-weighted mean. A quote is *ambiguous* when the lower-bound and upper-bound fill status disagree. `tape in bracket` checks the bracket logic against the tape clipped to the same window (must be 100%).

| T | k | quotes | LB fills | UB fills | tape fills (in window) | ambiguous (rigorous) | ambiguous (mean-tight) | tape inside rigorous | tape inside mean-tight | candle-optimistic == tape-optimistic |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 5 | 1 | 256 | no candle after T exists in the cache | | | | | | | |
| 5 | 2 | 252 | no candle after T exists in the cache | | | | | | | |
| 5 | 3 | 250 | no candle after T exists in the cache | | | | | | | |
| 15 | 1 | 546 | 192 | 452 | 434 | 47.6% | 13.0% | 100.0% | 100.0% | 100.0% |
| 15 | 2 | 534 | 126 | 301 | 292 | 32.8% | 11.0% | 100.0% | 100.0% | 100.0% |
| 15 | 3 | 524 | 104 | 230 | 225 | 24.0% | 10.3% | 100.0% | 100.0% | 100.0% |
| 30 | 1 | 859 | 491 | 741 | 726 | 29.1% | 4.7% | 100.0% | 100.0% | 100.0% |
| 30 | 2 | 849 | 315 | 539 | 528 | 26.4% | 6.6% | 100.0% | 100.0% | 100.0% |
| 30 | 3 | 838 | 242 | 434 | 429 | 22.9% | 7.5% | 100.0% | 100.0% | 100.0% |
| 45 | 1 | 958 | 709 | 871 | 858 | 16.9% | 3.3% | 100.0% | 100.0% | 100.0% |
| 45 | 2 | 932 | 496 | 653 | 645 | 16.8% | 2.6% | 100.0% | 100.0% | 100.0% |
| 45 | 3 | 918 | 386 | 536 | 526 | 16.3% | 4.6% | 100.0% | 100.0% | 100.0% |

**F-iii. What the candle cache cannot see: the last 5 minutes before close** (the original fetch stopped at close-300s; min over all strikes of close - last candle end = 300s). Share of FILLED quotes (tape, optimistic) whose first fill is inside the final 5 minutes, and share of N=25 fills completing there:

| T | k | optimistic fills | first fill in final 5 min | N=25 fills | N=25 fill completes in final 5 min |
|--:|--:|--:|--:|--:|--:|
| 5 | 1 | 230 | 230 (100.0%) | 222 | 222 (100.0%) |
| 5 | 2 | 153 | 153 (100.0%) | 151 | 151 (100.0%) |
| 5 | 3 | 116 | 116 (100.0%) | 110 | 110 (100.0%) |
| 15 | 1 | 457 | 2 (0.4%) | 436 | 2 (0.5%) |
| 15 | 2 | 305 | 4 (1.3%) | 296 | 4 (1.4%) |
| 15 | 3 | 234 | 4 (1.7%) | 229 | 4 (1.7%) |
| 30 | 1 | 751 | 0 (0.0%) | 726 | 0 (0.0%) |
| 30 | 2 | 542 | 1 (0.2%) | 529 | 1 (0.2%) |
| 30 | 3 | 437 | 1 (0.2%) | 430 | 1 (0.2%) |
| 45 | 1 | 873 | 0 (0.0%) | 858 | 0 (0.0%) |
| 45 | 2 | 655 | 1 (0.2%) | 646 | 1 (0.2%) |
| 45 | 3 | 538 | 1 (0.2%) | 527 | 1 (0.2%) |

## 2. Anchor (a): adverse selection -- P(YES | filled) vs P(YES | quoted), per cell, BEFORE any EV

Same cell = same (k, T) quote rule; `quoted` is every quote placed in the cell (unfilled included), `filled` the subset the model fills. Wilson 95% intervals treat strikes as independent, which they are not (one BTC move hits every strike of an hour); the `day-bootstrap` column resamples whole UTC days (2000 draws, seed 20261028) for the difference P(YES|filled) - P(YES|quoted) in percentage points and is the honest width. `std. quoted` = P(YES|quoted) re-weighted to the price-level mix of the filled quotes (removes the composition effect that a mixed-price cell can create). `break-even` = mean ask of the filled quotes /100: the YES rate at which a fee-free short is exactly flat. KILL column: ratio >= 2 AND Wilson(filled).lo > Wilson(quoted).hi.


### optimistic (front of queue)

| T | k | quoted n | P(YES|quoted) [Wilson] | filled n | P(YES|filled) [Wilson] | ratio | std. quoted | break-even | day-bootstrap 95% of diff (pp) | KILL cond. |
|--:|--:|--:|---|--:|---|--:|--:|--:|---|:--:|
| 5 | 1 | 256 | 5.08% [2.99%, 8.49%] | 230 | 5.65% [3.33%, 9.43%] | 1.11 | 5.38% | 6.24% | [+0.26, +0.96] | no |
| 5 | 2 | 252 | 5.16% [3.04%, 8.62%] | 153 | 8.50% [5.03%, 13.99%] | 1.65 | 6.46% | 7.78% | [+1.75, +5.36] | no |
| 5 | 3 | 250 | 5.20% [3.06%, 8.69%] | 116 | 11.21% [6.67%, 18.23%] | 2.16 | 7.86% | 9.53% | [+3.29, +9.36] | no |
| 15 | 1 | 546 | 4.95% [3.42%, 7.10%] | 457 | 5.91% [4.09%, 8.46%] | 1.19 | 5.21% | 6.67% | [+0.53, +1.42] | no |
| 15 | 2 | 534 | 4.49% [3.04%, 6.60%] | 305 | 7.87% [5.34%, 11.44%] | 1.75 | 5.86% | 8.35% | [+1.98, +4.82] | no |
| 15 | 3 | 524 | 4.58% [3.10%, 6.72%] | 234 | 10.26% [6.99%, 14.81%] | 2.24 | 6.72% | 9.53% | [+3.44, +7.91] | YES |
| 30 | 1 | 859 | 5.59% [4.24%, 7.33%] | 751 | 6.39% [4.85%, 8.37%] | 1.14 | 5.95% | 6.65% | [+0.45, +1.24] | no |
| 30 | 2 | 849 | 5.42% [4.09%, 7.15%] | 542 | 8.49% [6.42%, 11.14%] | 1.57 | 6.63% | 8.35% | [+1.69, +4.48] | no |
| 30 | 3 | 838 | 5.49% [4.14%, 7.24%] | 437 | 10.53% [7.98%, 13.76%] | 1.92 | 7.42% | 9.77% | [+2.75, +7.51] | no |
| 45 | 1 | 958 | 7.41% [5.92%, 9.25%] | 873 | 8.13% [6.50%, 10.13%] | 1.10 | 7.61% | 6.86% | [+0.38, +1.17] | no |
| 45 | 2 | 932 | 7.08% [5.60%, 8.91%] | 655 | 10.08% [8.00%, 12.62%] | 1.42 | 7.85% | 8.00% | [+1.64, +4.41] | no |
| 45 | 3 | 918 | 6.86% [5.40%, 8.68%] | 538 | 11.71% [9.26%, 14.70%] | 1.71 | 8.15% | 9.36% | [+2.74, +6.97] | no |

### pessimistic N=25  (DECISIVE for the verdict)

| T | k | quoted n | P(YES|quoted) [Wilson] | filled n | P(YES|filled) [Wilson] | ratio | std. quoted | break-even | day-bootstrap 95% of diff (pp) | KILL cond. |
|--:|--:|--:|---|--:|---|--:|--:|--:|---|:--:|
| 5 | 1 | 256 | 5.08% [2.99%, 8.49%] | 222 | 5.86% [3.45%, 9.76%] | 1.15 | 5.35% | 6.20% | [+0.35, +1.32] | no |
| 5 | 2 | 252 | 5.16% [3.04%, 8.62%] | 151 | 8.61% [5.10%, 14.17%] | 1.67 | 6.45% | 7.72% | [+1.84, +5.53] | no |
| 5 | 3 | 250 | 5.20% [3.06%, 8.69%] | 110 | 11.82% [7.04%, 19.18%] | 2.27 | 8.12% | 9.64% | [+3.63, +10.40] | no |
| 15 | 1 | 546 | 4.95% [3.42%, 7.10%] | 436 | 6.19% [4.29%, 8.86%] | 1.25 | 5.41% | 6.84% | [+0.70, +1.83] | no |
| 15 | 2 | 534 | 4.49% [3.04%, 6.60%] | 296 | 8.11% [5.51%, 11.78%] | 1.80 | 5.98% | 8.41% | [+2.13, +5.16] | no |
| 15 | 3 | 524 | 4.58% [3.10%, 6.72%] | 229 | 10.48% [7.14%, 15.12%] | 2.29 | 6.86% | 9.62% | [+3.58, +8.19] | YES |
| 30 | 1 | 859 | 5.59% [4.24%, 7.33%] | 726 | 6.61% [5.02%, 8.66%] | 1.18 | 6.04% | 6.75% | [+0.56, +1.55] | no |
| 30 | 2 | 849 | 5.42% [4.09%, 7.15%] | 529 | 8.70% [6.58%, 11.40%] | 1.60 | 6.67% | 8.42% | [+1.81, +4.80] | no |
| 30 | 3 | 838 | 5.49% [4.14%, 7.24%] | 430 | 10.70% [8.12%, 13.97%] | 1.95 | 7.50% | 9.84% | [+2.82, +7.80] | no |
| 45 | 1 | 958 | 7.41% [5.92%, 9.25%] | 858 | 8.28% [6.61%, 10.31%] | 1.12 | 7.57% | 6.83% | [+0.46, +1.36] | no |
| 45 | 2 | 932 | 7.08% [5.60%, 8.91%] | 646 | 10.22% [8.11%, 12.79%] | 1.44 | 7.88% | 8.02% | [+1.71, +4.62] | no |
| 45 | 3 | 918 | 6.86% [5.40%, 8.68%] | 527 | 11.95% [9.46%, 15.00%] | 1.74 | 8.15% | 9.36% | [+2.88, +7.33] | no |

### pessimistic N=100

| T | k | quoted n | P(YES|quoted) [Wilson] | filled n | P(YES|filled) [Wilson] | ratio | std. quoted | break-even | day-bootstrap 95% of diff (pp) | KILL cond. |
|--:|--:|--:|---|--:|---|--:|--:|--:|---|:--:|
| 5 | 1 | 256 | 5.08% [2.99%, 8.49%] | 213 | 6.10% [3.60%, 10.16%] | 1.20 | 5.27% | 6.15% | [+0.48, +1.74] | no |
| 5 | 2 | 252 | 5.16% [3.04%, 8.62%] | 149 | 8.72% [5.17%, 14.35%] | 1.69 | 6.52% | 7.79% | [+1.91, +5.69] | no |
| 5 | 3 | 250 | 5.20% [3.06%, 8.69%] | 107 | 12.15% [7.24%, 19.68%] | 2.34 | 8.31% | 9.64% | [+3.81, +10.83] | no |
| 15 | 1 | 546 | 4.95% [3.42%, 7.10%] | 420 | 6.43% [4.46%, 9.19%] | 1.30 | 5.51% | 6.87% | [+0.84, +2.19] | no |
| 15 | 2 | 534 | 4.49% [3.04%, 6.60%] | 287 | 8.36% [5.68%, 12.14%] | 1.86 | 5.93% | 8.35% | [+2.29, +5.47] | no |
| 15 | 3 | 524 | 4.58% [3.10%, 6.72%] | 223 | 10.76% [7.34%, 15.51%] | 2.35 | 6.93% | 9.69% | [+3.75, +8.62] | YES |
| 30 | 1 | 859 | 5.59% [4.24%, 7.33%] | 685 | 7.01% [5.33%, 9.17%] | 1.25 | 6.17% | 6.87% | [+0.78, +2.18] | no |
| 30 | 2 | 849 | 5.42% [4.09%, 7.15%] | 500 | 9.20% [6.97%, 12.05%] | 1.70 | 6.84% | 8.56% | [+2.02, +5.65] | no |
| 30 | 3 | 838 | 5.49% [4.14%, 7.24%] | 408 | 11.27% [8.56%, 14.71%] | 2.05 | 7.66% | 9.96% | [+3.14, +8.55] | YES |
| 45 | 1 | 958 | 7.41% [5.92%, 9.25%] | 831 | 8.54% [6.83%, 10.64%] | 1.15 | 7.64% | 6.90% | [+0.61, +1.74] | no |
| 45 | 2 | 932 | 7.08% [5.60%, 8.91%] | 624 | 10.58% [8.40%, 13.24%] | 1.49 | 7.97% | 8.13% | [+1.95, +5.08] | no |
| 45 | 3 | 918 | 6.86% [5.40%, 8.68%] | 511 | 12.33% [9.76%, 15.46%] | 1.80 | 8.23% | 9.41% | [+3.11, +7.77] | no |

### Same price level (pooled over k; ask level a), optimistic and N=25

| T | ask a | model | quoted n | P(YES|quoted) [Wilson] | filled n | P(YES|filled) [Wilson] | ratio | break-even |
|--:|---|---|--:|---|--:|---|--:|--:|
| 5 | 2c | opt | 91 | 1.10% [0.19%, 5.96%] | 78 | 1.28% [0.23%, 6.91%] | 1.17 | 2.00% |
| 5 | 2c | n25 | 91 | 1.10% [0.19%, 5.96%] | 76 | 1.32% [0.23%, 7.08%] | 1.20 | 2.00% |
| 5 | 3c | opt | 118 | 0.85% [0.15%, 4.64%] | 65 | 1.54% [0.27%, 8.21%] | 1.82 | 3.00% |
| 5 | 3c | n25 | 118 | 0.85% [0.15%, 4.64%] | 65 | 1.54% [0.27%, 8.21%] | 1.82 | 3.00% |
| 5 | 4-5c | opt | 218 | 1.83% [0.72%, 4.62%] | 109 | 3.67% [1.44%, 9.06%] | 2.00 | 4.41% |
| 5 | 4-5c | n25 | 218 | 1.83% [0.72%, 4.62%] | 104 | 3.85% [1.51%, 9.47%] | 2.10 | 4.42% |
| 5 | 6-10c | opt | 170 | 8.24% [4.97%, 13.35%] | 109 | 12.84% [7.81%, 20.41%] | 1.56 | 7.59% |
| 5 | 6-10c | n25 | 170 | 8.24% [4.97%, 13.35%] | 104 | 13.46% [8.19%, 21.34%] | 1.63 | 7.54% |
| 5 | 11-20c | opt | 161 | 11.80% [7.69%, 17.70%] | 138 | 13.77% [8.99%, 20.50%] | 1.17 | 15.01% |
| 5 | 11-20c | n25 | 161 | 11.80% [7.69%, 17.70%] | 134 | 14.18% [9.27%, 21.09%] | 1.20 | 15.01% |
| 15 | 2c | opt | 150 | 0.00% [0.00%, 2.50%] | 104 | 0.00% [0.00%, 3.56%] | n/a | 2.00% |
| 15 | 2c | n25 | 150 | 0.00% [0.00%, 2.50%] | 95 | 0.00% [0.00%, 3.89%] | n/a | 2.00% |
| 15 | 3c | opt | 221 | 0.45% [0.08%, 2.52%] | 111 | 0.90% [0.16%, 4.93%] | 1.99 | 3.00% |
| 15 | 3c | n25 | 221 | 0.45% [0.08%, 2.52%] | 103 | 0.97% [0.17%, 5.30%] | 2.15 | 3.00% |
| 15 | 4-5c | opt | 466 | 1.29% [0.59%, 2.78%] | 221 | 2.71% [1.25%, 5.80%] | 2.11 | 4.44% |
| 15 | 4-5c | n25 | 466 | 1.29% [0.59%, 2.78%] | 208 | 2.88% [1.33%, 6.15%] | 2.24 | 4.44% |
| 15 | 6-10c | opt | 431 | 4.18% [2.66%, 6.50%] | 294 | 6.12% [3.91%, 9.47%] | 1.47 | 7.64% |
| 15 | 6-10c | n25 | 431 | 4.18% [2.66%, 6.50%] | 291 | 6.19% [3.95%, 9.56%] | 1.48 | 7.63% |
| 15 | 11-20c | opt | 336 | 14.88% [11.47%, 19.08%] | 266 | 18.80% [14.56%, 23.92%] | 1.26 | 15.26% |
| 15 | 11-20c | n25 | 336 | 14.88% [11.47%, 19.08%] | 264 | 18.94% [14.67%, 24.10%] | 1.27 | 15.27% |
| 30 | 2c | opt | 250 | 1.20% [0.41%, 3.47%] | 190 | 1.58% [0.54%, 4.54%] | 1.32 | 2.00% |
| 30 | 2c | n25 | 250 | 1.20% [0.41%, 3.47%] | 182 | 1.65% [0.56%, 4.73%] | 1.37 | 2.00% |
| 30 | 3c | opt | 373 | 1.88% [0.91%, 3.82%] | 200 | 3.50% [1.71%, 7.05%] | 1.87 | 3.00% |
| 30 | 3c | n25 | 373 | 1.88% [0.91%, 3.82%] | 194 | 3.61% [1.76%, 7.26%] | 1.92 | 3.00% |
| 30 | 4-5c | opt | 717 | 3.07% [2.03%, 4.60%] | 362 | 6.08% [4.05%, 9.03%] | 1.98 | 4.45% |
| 30 | 4-5c | n25 | 717 | 3.07% [2.03%, 4.60%] | 341 | 6.45% [4.30%, 9.57%] | 2.10 | 4.45% |
| 30 | 6-10c | opt | 614 | 4.72% [3.31%, 6.70%] | 464 | 6.25% [4.39%, 8.83%] | 1.32 | 7.51% |
| 30 | 6-10c | n25 | 614 | 4.72% [3.31%, 6.70%] | 455 | 6.37% [4.47%, 9.00%] | 1.35 | 7.53% |
| 30 | 11-20c | opt | 592 | 13.34% [10.84%, 16.32%] | 514 | 15.37% [12.51%, 18.74%] | 1.15 | 15.01% |
| 30 | 11-20c | n25 | 592 | 13.34% [10.84%, 16.32%] | 513 | 15.40% [12.53%, 18.78%] | 1.15 | 15.02% |
| 45 | 2c | opt | 265 | 1.89% [0.81%, 4.34%] | 225 | 2.22% [0.95%, 5.10%] | 1.18 | 2.00% |
| 45 | 2c | n25 | 265 | 1.89% [0.81%, 4.34%] | 222 | 2.25% [0.97%, 5.16%] | 1.19 | 2.00% |
| 45 | 3c | opt | 380 | 2.63% [1.44%, 4.78%] | 241 | 4.15% [2.27%, 7.47%] | 1.58 | 3.00% |
| 45 | 3c | n25 | 380 | 2.63% [1.44%, 4.78%] | 237 | 4.22% [2.31%, 7.59%] | 1.60 | 3.00% |
| 45 | 4-5c | opt | 761 | 4.34% [3.10%, 6.03%] | 461 | 7.16% [5.14%, 9.88%] | 1.65 | 4.43% |
| 45 | 4-5c | n25 | 761 | 4.34% [3.10%, 6.03%] | 452 | 7.30% [5.25%, 10.08%] | 1.68 | 4.42% |
| 45 | 6-10c | opt | 730 | 7.53% [5.83%, 9.68%] | 548 | 10.04% [7.79%, 12.84%] | 1.33 | 7.78% |
| 45 | 6-10c | n25 | 730 | 7.53% [5.83%, 9.68%] | 541 | 10.17% [7.89%, 13.00%] | 1.35 | 7.78% |
| 45 | 11-20c | opt | 672 | 14.43% [11.98%, 17.29%] | 591 | 16.41% [13.65%, 19.61%] | 1.14 | 14.87% |
| 45 | 11-20c | n25 | 672 | 14.43% [11.98%, 17.29%] | 579 | 16.75% [13.93%, 20.01%] | 1.16 | 14.88% |

### Sensitivity: only prints with taker_side = yes count toward the fill (prints that actually lifted offers); N=25 and optimistic

| T | k | model | filled n | P(YES|filled) [Wilson] | P(YES|quoted) | ratio |
|--:|--:|---|--:|---|--:|--:|
| 5 | 1 | opt | 229 | 5.68% [3.35%, 9.47%] | 5.08% | 1.12 |
| 5 | 1 | n25 | 220 | 5.91% [3.49%, 9.85%] | 5.08% | 1.16 |
| 5 | 2 | opt | 151 | 8.61% [5.10%, 14.17%] | 5.16% | 1.67 |
| 5 | 2 | n25 | 150 | 8.67% [5.13%, 14.26%] | 5.16% | 1.68 |
| 5 | 3 | opt | 115 | 11.30% [6.73%, 18.38%] | 5.20% | 2.17 |
| 5 | 3 | n25 | 110 | 11.82% [7.04%, 19.18%] | 5.20% | 2.27 |
| 15 | 1 | opt | 457 | 5.91% [4.09%, 8.46%] | 4.95% | 1.19 |
| 15 | 1 | n25 | 436 | 6.19% [4.29%, 8.86%] | 4.95% | 1.25 |
| 15 | 2 | opt | 304 | 7.89% [5.36%, 11.48%] | 4.49% | 1.76 |
| 15 | 2 | n25 | 295 | 8.14% [5.53%, 11.82%] | 4.49% | 1.81 |
| 15 | 3 | opt | 233 | 10.30% [7.02%, 14.87%] | 4.58% | 2.25 |
| 15 | 3 | n25 | 228 | 10.53% [7.18%, 15.18%] | 4.58% | 2.30 |
| 30 | 1 | opt | 750 | 6.40% [4.86%, 8.38%] | 5.59% | 1.15 |
| 30 | 1 | n25 | 724 | 6.63% [5.04%, 8.68%] | 5.59% | 1.19 |
| 30 | 2 | opt | 542 | 8.49% [6.42%, 11.14%] | 5.42% | 1.57 |
| 30 | 2 | n25 | 527 | 8.73% [6.61%, 11.45%] | 5.42% | 1.61 |
| 30 | 3 | opt | 434 | 10.60% [8.04%, 13.85%] | 5.49% | 1.93 |
| 30 | 3 | n25 | 423 | 10.87% [8.25%, 14.20%] | 5.49% | 1.98 |
| 45 | 1 | opt | 871 | 8.15% [6.51%, 10.16%] | 7.41% | 1.10 |
| 45 | 1 | n25 | 856 | 8.29% [6.63%, 10.33%] | 7.41% | 1.12 |
| 45 | 2 | opt | 655 | 10.08% [8.00%, 12.62%] | 7.08% | 1.42 |
| 45 | 2 | n25 | 646 | 10.22% [8.11%, 12.79%] | 7.08% | 1.44 |
| 45 | 3 | opt | 537 | 11.73% [9.28%, 14.73%] | 6.86% | 1.71 |
| 45 | 3 | n25 | 526 | 11.98% [9.47%, 15.03%] | 6.86% | 1.75 |

### Diagnostic (single pre-declared split, not a filter): entry-candle age <= 120 s vs > 120 s, k = 1, 2

| T | k | candle age | model | quoted n | P(YES|quoted) | filled n | P(YES|filled) [Wilson] |
|--:|--:|---|---|--:|--:|--:|---|
| 5 | 1 | fresh<=120s | opt | 256 | 5.08% | 230 | 5.65% [3.33%, 9.43%] |
| 5 | 1 | fresh<=120s | n25 | 256 | 5.08% | 222 | 5.86% [3.45%, 9.76%] |
| 5 | 1 | stale>120s | opt | 0 | n/a | 0 | n/a n/a |
| 5 | 1 | stale>120s | n25 | 0 | n/a | 0 | n/a n/a |
| 5 | 2 | fresh<=120s | opt | 252 | 5.16% | 153 | 8.50% [5.03%, 13.99%] |
| 5 | 2 | fresh<=120s | n25 | 252 | 5.16% | 151 | 8.61% [5.10%, 14.17%] |
| 5 | 2 | stale>120s | opt | 0 | n/a | 0 | n/a n/a |
| 5 | 2 | stale>120s | n25 | 0 | n/a | 0 | n/a n/a |
| 15 | 1 | fresh<=120s | opt | 546 | 4.95% | 457 | 5.91% [4.09%, 8.46%] |
| 15 | 1 | fresh<=120s | n25 | 546 | 4.95% | 436 | 6.19% [4.29%, 8.86%] |
| 15 | 1 | stale>120s | opt | 0 | n/a | 0 | n/a n/a |
| 15 | 1 | stale>120s | n25 | 0 | n/a | 0 | n/a n/a |
| 15 | 2 | fresh<=120s | opt | 534 | 4.49% | 305 | 7.87% [5.34%, 11.44%] |
| 15 | 2 | fresh<=120s | n25 | 534 | 4.49% | 296 | 8.11% [5.51%, 11.78%] |
| 15 | 2 | stale>120s | opt | 0 | n/a | 0 | n/a n/a |
| 15 | 2 | stale>120s | n25 | 0 | n/a | 0 | n/a n/a |
| 30 | 1 | fresh<=120s | opt | 859 | 5.59% | 751 | 6.39% [4.85%, 8.37%] |
| 30 | 1 | fresh<=120s | n25 | 859 | 5.59% | 726 | 6.61% [5.02%, 8.66%] |
| 30 | 1 | stale>120s | opt | 0 | n/a | 0 | n/a n/a |
| 30 | 1 | stale>120s | n25 | 0 | n/a | 0 | n/a n/a |
| 30 | 2 | fresh<=120s | opt | 849 | 5.42% | 542 | 8.49% [6.42%, 11.14%] |
| 30 | 2 | fresh<=120s | n25 | 849 | 5.42% | 529 | 8.70% [6.58%, 11.40%] |
| 30 | 2 | stale>120s | opt | 0 | n/a | 0 | n/a n/a |
| 30 | 2 | stale>120s | n25 | 0 | n/a | 0 | n/a n/a |
| 45 | 1 | fresh<=120s | opt | 958 | 7.41% | 873 | 8.13% [6.50%, 10.13%] |
| 45 | 1 | fresh<=120s | n25 | 958 | 7.41% | 858 | 8.28% [6.61%, 10.31%] |
| 45 | 1 | stale>120s | opt | 0 | n/a | 0 | n/a n/a |
| 45 | 1 | stale>120s | n25 | 0 | n/a | 0 | n/a n/a |
| 45 | 2 | fresh<=120s | opt | 932 | 7.08% | 655 | 10.08% [8.00%, 12.62%] |
| 45 | 2 | fresh<=120s | n25 | 932 | 7.08% | 646 | 10.22% [8.11%, 12.79%] |
| 45 | 2 | stale>120s | opt | 0 | n/a | 0 | n/a n/a |
| 45 | 2 | stale>120s | n25 | 0 | n/a | 0 | n/a n/a |

## 3. Anchor (b): quote counts, fill counts, fill rates -- unfilled quotes are in every denominator

| T | k | quotes | days | opt fills | opt rate | N=25 fills | N=25 rate | N=25 filled days | N=100 fills | N=100 rate | N=100 filled days |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 5 | 1 | 256 | 59 | 230 | 89.8% | 222 | 86.7% | 58 | 213 | 83.2% | 58 |
| 5 | 2 | 252 | 59 | 153 | 60.7% | 151 | 59.9% | 53 | 149 | 59.1% | 53 |
| 5 | 3 | 250 | 59 | 116 | 46.4% | 110 | 44.0% | 44 | 107 | 42.8% | 42 |
| 15 | 1 | 546 | 59 | 457 | 83.7% | 436 | 79.9% | 59 | 420 | 76.9% | 59 |
| 15 | 2 | 534 | 59 | 305 | 57.1% | 296 | 55.4% | 58 | 287 | 53.7% | 58 |
| 15 | 3 | 524 | 59 | 234 | 44.7% | 229 | 43.7% | 57 | 223 | 42.6% | 57 |
| 30 | 1 | 859 | 59 | 751 | 87.4% | 726 | 84.5% | 59 | 685 | 79.7% | 59 |
| 30 | 2 | 849 | 59 | 542 | 63.8% | 529 | 62.3% | 59 | 500 | 58.9% | 59 |
| 30 | 3 | 838 | 59 | 437 | 52.1% | 430 | 51.3% | 58 | 408 | 48.7% | 58 |
| 45 | 1 | 958 | 59 | 873 | 91.1% | 858 | 89.6% | 59 | 831 | 86.7% | 59 |
| 45 | 2 | 932 | 59 | 655 | 70.3% | 646 | 69.3% | 59 | 624 | 67.0% | 57 |
| 45 | 3 | 918 | 59 | 538 | 58.6% | 527 | 57.4% | 56 | 511 | 55.7% | 56 |

## 4. EV (fee-free, cents), per QUOTED contract beside per FILLED contract

Per-quoted EV = sum of P&L over filled quotes / all quotes (unfilled = 0). Signed t is day-clustered (CR1, equal weight, df = days - 1) on the per-quoted series. Bonferroni: 24 comparisons, two-sided alpha = 0.00208, bar = Student-t quantile at p = 0.99896. Per-filled EV = mean(a) - 100 x P(YES|filled) exactly.


### optimistic (front of queue)

| T | k | quotes | filled | EV per quoted | SE | t (signed) | bar | EV per filled | t (per filled) | mean ask filled | gates 1/2/3/4/5 | all five |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|:--:|
| 5 | 1 | 256 | 230 | 0.527 | 1.200 | 0.44 | 3.22 | 0.59 | 0.44 | 6.24 | n/Y/n/n/Y | no |
| 5 | 2 | 252 | 153 | -0.433 | 1.238 | -0.35 | 3.22 | -0.71 | -0.35 | 7.78 | n/n/n/n/Y | no |
| 5 | 3 | 250 | 116 | -0.780 | 1.199 | -0.65 | 3.22 | -1.68 | -0.65 | 9.53 | n/n/n/n/Y | no |
| 15 | 1 | 546 | 457 | 0.637 | 0.983 | 0.65 | 3.22 | 0.76 | 0.65 | 6.67 | n/Y/n/n/Y | no |
| 15 | 2 | 534 | 305 | 0.277 | 0.994 | 0.28 | 3.22 | 0.49 | 0.28 | 8.35 | n/n/n/n/Y | no |
| 15 | 3 | 524 | 234 | -0.324 | 0.962 | -0.34 | 3.22 | -0.73 | -0.34 | 9.53 | n/n/n/n/Y | no |
| 30 | 1 | 859 | 751 | 0.226 | 1.402 | 0.16 | 3.22 | 0.26 | 0.16 | 6.65 | n/n/n/Y/Y | no |
| 30 | 2 | 849 | 542 | -0.085 | 1.400 | -0.06 | 3.22 | -0.13 | -0.06 | 8.35 | n/n/n/Y/Y | no |
| 30 | 3 | 838 | 437 | -0.396 | 1.408 | -0.28 | 3.22 | -0.76 | -0.28 | 9.77 | n/n/n/n/Y | no |
| 45 | 1 | 958 | 873 | -1.164 | 1.793 | -0.65 | 3.22 | -1.28 | -0.65 | 6.86 | n/n/n/Y/Y | no |
| 45 | 2 | 932 | 655 | -1.457 | 1.785 | -0.82 | 3.22 | -2.07 | -0.82 | 8.00 | n/n/n/Y/Y | no |
| 45 | 3 | 918 | 538 | -1.375 | 1.735 | -0.79 | 3.22 | -2.35 | -0.81 | 9.36 | n/n/n/Y/Y | no |

### pessimistic N=25

| T | k | quotes | filled | EV per quoted | SE | t (signed) | bar | EV per filled | t (per filled) | mean ask filled | gates 1/2/3/4/5 | all five |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|:--:|
| 5 | 1 | 256 | 222 | 0.297 | 1.205 | 0.25 | 3.22 | 0.34 | 0.25 | 6.20 | n/n/n/n/Y | no |
| 5 | 2 | 252 | 151 | -0.532 | 1.232 | -0.43 | 3.22 | -0.89 | -0.43 | 7.72 | n/n/n/n/Y | no |
| 5 | 3 | 250 | 110 | -0.960 | 1.200 | -0.80 | 3.22 | -2.18 | -0.79 | 9.64 | n/n/n/n/Y | no |
| 15 | 1 | 546 | 436 | 0.516 | 0.981 | 0.53 | 3.22 | 0.65 | 0.53 | 6.84 | n/Y/n/n/Y | no |
| 15 | 2 | 534 | 296 | 0.167 | 0.987 | 0.17 | 3.22 | 0.30 | 0.17 | 8.41 | n/n/n/n/Y | no |
| 15 | 3 | 524 | 229 | -0.378 | 0.957 | -0.39 | 3.22 | -0.86 | -0.40 | 9.62 | n/n/n/n/Y | no |
| 30 | 1 | 859 | 726 | 0.120 | 1.406 | 0.09 | 3.22 | 0.14 | 0.09 | 6.75 | n/n/n/Y/Y | no |
| 30 | 2 | 849 | 529 | -0.170 | 1.401 | -0.12 | 3.22 | -0.27 | -0.12 | 8.42 | n/n/n/Y/Y | no |
| 30 | 3 | 838 | 430 | -0.438 | 1.415 | -0.31 | 3.22 | -0.85 | -0.31 | 9.84 | n/n/n/n/Y | no |
| 45 | 1 | 958 | 858 | -1.291 | 1.789 | -0.72 | 3.22 | -1.44 | -0.72 | 6.83 | n/n/n/Y/Y | no |
| 45 | 2 | 932 | 646 | -1.519 | 1.785 | -0.85 | 3.22 | -2.19 | -0.86 | 8.02 | n/n/n/Y/Y | no |
| 45 | 3 | 918 | 527 | -1.487 | 1.728 | -0.86 | 3.22 | -2.59 | -0.88 | 9.36 | n/n/n/Y/Y | no |

### pessimistic N=100

| T | k | quotes | filled | EV per quoted | SE | t (signed) | bar | EV per filled | t (per filled) | mean ask filled | gates 1/2/3/4/5 | all five |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|:--:|
| 5 | 1 | 256 | 213 | 0.035 | 1.223 | 0.03 | 3.22 | 0.04 | 0.03 | 6.15 | n/n/n/n/Y | no |
| 5 | 2 | 252 | 149 | -0.556 | 1.230 | -0.45 | 3.22 | -0.94 | -0.45 | 7.79 | n/n/n/n/Y | no |
| 5 | 3 | 250 | 107 | -1.072 | 1.198 | -0.89 | 3.22 | -2.50 | -0.89 | 9.64 | n/n/n/n/Y | no |
| 15 | 1 | 546 | 420 | 0.341 | 0.993 | 0.34 | 3.22 | 0.44 | 0.34 | 6.87 | n/n/n/n/Y | no |
| 15 | 2 | 534 | 287 | -0.006 | 0.983 | -0.01 | 3.22 | -0.01 | -0.01 | 8.35 | n/n/n/n/Y | no |
| 15 | 3 | 524 | 223 | -0.456 | 0.962 | -0.47 | 3.22 | -1.07 | -0.47 | 9.69 | n/n/n/n/Y | no |
| 30 | 1 | 859 | 685 | -0.109 | 1.410 | -0.08 | 3.22 | -0.14 | -0.08 | 6.87 | n/n/n/Y/Y | no |
| 30 | 2 | 849 | 500 | -0.375 | 1.419 | -0.26 | 3.22 | -0.64 | -0.26 | 8.56 | n/n/n/Y/Y | no |
| 30 | 3 | 838 | 408 | -0.641 | 1.406 | -0.46 | 3.22 | -1.32 | -0.46 | 9.96 | n/n/n/n/Y | no |
| 45 | 1 | 958 | 831 | -1.424 | 1.784 | -0.80 | 3.22 | -1.64 | -0.80 | 6.90 | n/n/n/Y/Y | no |
| 45 | 2 | 932 | 624 | -1.637 | 1.778 | -0.92 | 3.22 | -2.45 | -0.93 | 8.13 | n/n/n/Y/Y | no |
| 45 | 3 | 918 | 511 | -1.623 | 1.715 | -0.95 | 3.22 | -2.92 | -0.97 | 9.41 | n/n/n/Y/Y | no |

## 5. Anchors (c), (d), (e)

**(c) No look-ahead in placement.** AST scan passed: placement functions ['quote_for', 'place_hour'] reference none of the forbidden names (RESULT_KEY, TAPE, fill, fill_models, fills, load_tape, res, result, results, tape, trades); `tail_pricing.entry_quote`/`candle_rows` reference no result. Placement is a separate pass (`quotes`) that writes `quotes.json` before the tape or any result is read; `analyze` recomputes placement from the candle cache and asserts the sha256 equals the saved one, and asserts every quote's entry-candle age is >= 0 (candle end <= cutoff). The quote price is the entry candle's `yes_bid.close` + k; nothing after the cutoff enters it. Ten hand-worked placements (T=15, k=1, first ten in work order), raw candle JSON re-parsed independently of `normalize()`; the fill columns are the tape result AFTER placement:

| ticker | cutoff ts | entry candle end (<= cutoff) | raw yes_bid close | b | a = b+1 | first candle after cutoff | opt fill | N=25 | N=100 |
|---|--:|--:|--:|--:|--:|--:|:--:|:--:|:--:|
| KXBTCD-26SEP1101-T77199.99 | 1789101900 | 1789101900 | 0.0900 | 9 | 10 | 1789101960 | Y | Y | Y |
| KXBTCD-26SEP1101-T77299.99 | 1789101900 | 1789101900 | 0.0100 | 1 | 2 | 1789101960 | Y | Y | Y |
| KXBTCD-26SEP2719-T84399.99 | 1790549100 | 1790549100 | 0.0900 | 9 | 10 | 1790549160 | Y | Y | n |
| KXBTCD-26SEP2719-T84499.99 | 1790549100 | 1790549100 | 0.0400 | 4 | 5 | 1790549160 | Y | Y | Y |
| KXBTCD-26SEP1023-T76999.99 | 1789094700 | 1789094700 | 0.0600 | 6 | 7 | 1789094760 | Y | Y | Y |
| KXBTCD-26SEP1023-T77099.99 | 1789094700 | 1789094700 | 0.0200 | 2 | 3 | 1789094760 | Y | Y | Y |
| KXBTCD-26OCT2009-T81699.99 | 1792500300 | 1792500300 | 0.1900 | 19 | 20 | 1792500360 | Y | Y | Y |
| KXBTCD-26OCT2009-T81799.99 | 1792500300 | 1792500300 | 0.0600 | 6 | 7 | 1792500360 | Y | Y | Y |
| KXBTCD-26OCT2009-T81899.99 | 1792500300 | 1792500300 | 0.0200 | 2 | 3 | 1792500360 | Y | Y | Y |
| KXBTCD-26OCT2009-T81999.99 | 1792500300 | 1792500300 | 0.0100 | 1 | 2 | 1792500360 | Y | Y | n |

**(d) Queue assumption.** Book depth is NOT in any archive available here (candles or trade tape): the number of contracts resting ahead of a quote at its price is unobserved. `N` is therefore an explicit assumption (25 = the deployed `DEPTH_CAP`, 100 = a deeper queue), and the optimistic bound assumes front of queue (N=0), which this program has already shown is optimistic. How the answer moves with N:

| fill model | cells with n_filled>=500 & >=40 filled days | cells passing all five gates | verdict if struck on this model |
|---|--:|--:|---|
| optimistic | 5 | 0 | INSUFFICIENT |
| N=25 (decisive) | 5 | 0 | INSUFFICIENT |
| N=100 | 5 | 0 | INSUFFICIENT |

**(e) Tail risk** (SAMPLED hours only: a full-universe day holds about 6.5x as many positions, so absolute losses are understated by roughly that factor). Worst single UTC day aggregate P&L over the cell's filled quotes; maximum simultaneous short exposure = largest single-hour sum of (100 - a) over filled quotes (all positions of one hour are open together; hours do not overlap), cents, 100c = $1.

| T | k | model | filled | worst day (UTC) | worst-day P&L (c) | max hour short exposure (c) |
|--:|--:|---|--:|---|--:|--:|
| 5 | 1 | opt | 230 | 2026-08-25 | -103 | 470 |
| 5 | 1 | n25 | 222 | 2026-08-25 | -105 | 375 |
| 5 | 2 | opt | 153 | 2026-08-25 | -115 | 371 |
| 5 | 2 | n25 | 151 | 2026-08-25 | -115 | 371 |
| 5 | 3 | opt | 116 | 2026-08-25 | -114 | 273 |
| 5 | 3 | n25 | 110 | 2026-08-25 | -122 | 273 |
| 15 | 1 | opt | 457 | 2026-10-20 | -222 | 560 |
| 15 | 1 | n25 | 436 | 2026-10-20 | -222 | 560 |
| 15 | 2 | opt | 305 | 2026-10-20 | -250 | 468 |
| 15 | 2 | n25 | 296 | 2026-10-20 | -250 | 468 |
| 15 | 3 | opt | 234 | 2026-10-20 | -242 | 463 |
| 15 | 3 | n25 | 229 | 2026-10-20 | -242 | 463 |
| 30 | 1 | opt | 751 | 2026-08-24 | -769 | 1298 |
| 30 | 1 | n25 | 726 | 2026-08-24 | -769 | 1015 |
| 30 | 2 | opt | 542 | 2026-08-24 | -755 | 1195 |
| 30 | 2 | n25 | 529 | 2026-08-24 | -755 | 1004 |
| 30 | 3 | opt | 437 | 2026-08-24 | -778 | 997 |
| 30 | 3 | n25 | 430 | 2026-08-24 | -782 | 822 |
| 45 | 1 | opt | 873 | 2026-08-25 | -1047 | 1299 |
| 45 | 1 | n25 | 858 | 2026-08-25 | -1047 | 1299 |
| 45 | 2 | opt | 655 | 2026-08-25 | -1011 | 1109 |
| 45 | 2 | n25 | 646 | 2026-08-25 | -1011 | 1109 |
| 45 | 3 | opt | 538 | 2026-08-25 | -906 | 942 |
| 45 | 3 | n25 | 527 | 2026-08-25 | -906 | 942 |

## 6. Verdict: frozen rule, numbers beside each bar (N=25 decisive)

* Cells meeting the n floor (n_filled >= 500 AND >= 40 filled days) under N=25: **5 of 12** (30|1|n25, 30|2|n25, 45|1|n25, 45|2|n25, 45|3|n25).
* PASS cells (all five gates): **0** (none).
* Best cell by EV per quoted under N=25: **15|1|n25** -- quotes 546, filled 436 over 59 days:
  * Gate 1 (Wilson UB of P(YES|filled) < mean ask/100): UB 8.86% vs 6.84% -> NOT met.
  * Gate 2 (EV per quoted >= +0.5c): 0.516c -> met.
  * Gate 3 (signed day-clustered t >= bar): t = 0.53 vs bar 3.22 -> NOT met.
  * Gate 4 (n_filled >= 500 over >= 40 days): 436 over 59 -> NOT met.
  * Gate 5 (fill rate >= 5%): 79.9% -> met.

KILL clause (every floor-meeting cell must show P(YES|filled) >= 2 x P(YES|quoted) with non-overlapping Wilson 95%):

| cell | filled n | P(YES|quoted) [Wilson] | P(YES|filled) [Wilson] | ratio (bar 2.0) | non-overlap | fires |
|---|--:|---|---|--:|:--:|:--:|
| 30|1|n25 | 726 | 5.59% [4.24%, 7.33%] | 6.61% [5.02%, 8.66%] | 1.18 | no | no |
| 30|2|n25 | 529 | 5.42% [4.09%, 7.15%] | 8.70% [6.58%, 11.40%] | 1.60 | no | no |
| 45|1|n25 | 858 | 7.41% [5.92%, 9.25%] | 8.28% [6.61%, 10.31%] | 1.12 | no | no |
| 45|2|n25 | 646 | 7.08% [5.60%, 8.91%] | 10.22% [8.11%, 12.79%] | 1.44 | no | no |
| 45|3|n25 | 527 | 6.86% [5.40%, 8.68%] | 11.95% [9.46%, 15.00%] | 1.74 | yes | no |

## 7. Exclusions (count and reason)

| T | untradeable (no candle / yes_bid = 0), strike-T obs | no candle | quote skipped: a = bid+k > 20c (k=1 / k=2 / k=3) |
|--:|--:|--:|---|
| 5 | 44,026 | 0 | 47,872 / 47,881 / 47,889 |
| 15 | 43,108 | 0 | 48,110 / 48,132 / 48,155 |
| 30 | 42,180 | 0 | 48,350 / 48,379 / 48,409 |
| 45 | 41,748 | 0 | 48,477 / 48,522 / 48,560 |

* Untradeable strike-T observations are never quoted (a = yes_bid + k is undefined at bid 0) and are not in any denominator below; they are 41,748-44,026 of 92,560 per T, as in the tail-pricing study.
* Non -T / non-greater strikes: 0.  Quotes without an official yes/no `result`: 0.
* Quotes with a > 20c are outside the frozen placed universe (cap); the spec line 'above 20c is reported but cannot PASS' is read as a statement about that excluded region, not as an instruction to simulate it. Counts above.
* Calendar day = UTC date of close. Universe: the 503 completed hours of the tail-pricing cache (prefix of the saved seed-20261027 shuffle; never re-sorted); no hour added.
* Interpretation choices fixed before any fill or outcome was computed are listed in the docstring of `maker_fill.py`.
