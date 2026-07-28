# LSH Intern Schedule — Time-Off Requests: Status Report

Whole-year schedule (Sep 1 2026 – Jun 23 2027), original Q4-march rules.
Base schedule is clean (5 pre-documented exceptions: June 21–23 wind-down;
two 5-Saturday months — Bronson Oct, Li May). Accommodations below are layered
on top via `generator/swaps.txt`; their cost is listed honestly.

## ✅ Granted (in the schedule)

| Intern | Request | Status | Cost |
|---|---|---|---|
| **Oghenesume** | Jan 30–31 off (FIRM wedding) | ✅ both days off | 1 unavoidable Q4 gap on Li (Feb 1→3); Feb runs only 3 daytime interns at the Q4 minimum |
| **MacNeille** | Weekend 10/17–18 off | ✅ off | 2 Q4 gaps, both on **non-LSH** interns (Ahluwalia wind-down, Chiasson first days) |
| **MacNeille** | Don't start October on 2 nights | ✅ starts on a **day shift** 10/1 | 1 residual night remains on 10/2 (see conflicts) |
| **MacNeille** | ≤ 1 night-float week in October | ✅ one week (10/25–30) | + the single 10/2 night |
| **Anna Li** | 9/4 short call | ✅ already short call | none |
| **Anna Li** | 9/6 off | ✅ already off | none |
| **Bronson** | No outsized Friday long call | ✅ already lowest Friday-LC share of anyone | none |
| **Wise** | (rule) not end September on nights | ✅ ends on day shifts | none (structural boundary fix) |
| **Matsuoka** | none | — | — |

## ✅ Second-round accommodations (now applied)

| Intern | Request | Status | Cost |
|---|---|---|---|
| **MacNeille** | No night float Christmas week (12/20–25) + SC on NYE | ✅ **Bronson takes the Christmas NF week** (approved); MacNeille has no Christmas nights and short call 12/31 | 2 Q4 gaps (Bronson 12/29→31, MacNeille 12/26→28) |
| **Kennedy** | Night float the first week of Nov (Sun 11/1 → Fri 11/6 night) | ✅ **NF 11/1–6**, off 11/7–8 weekend, back on days 11/9–13. Chiasson takes his 11/8–13 nights in return (unavoidable — she holds the 11/1–6 nights). Thanksgiving 11/26 off | documented KEN_SWAP month-boundary coupling only |
| **Kennedy** | Thanksgiving Day off | ✅ off 11/26 (already); he holds the 11/28 Saturday 24h | none |
| **Oghenesume** | April 9–12 off | ✅ **4/10–11 weekend fully off** (freed the 4/11 Sunday long call) | 2 Q4 gaps on **Rivera** (BMC, non-LSH) |

**Note on Kennedy's Friday 11/6 and Oghenesume's 4/9 / 4/12:** these are weekdays,
and the rules only allow a *full* day off on Thursdays. So the best possible is a
**short call** (light day, done ~3:30pm) — which is what they now have. Fully
freeing them, or putting Oghenesume on night float to free those days, would
cascade badly (it pushed another intern to *end* April on nights), so I left it
at the clean weekend-off.

## 🔧 Night-float balance fixes (from the scheduler's review)

Root cause found: in a month spanning **5 night-float week-starts**, the 4-slot
cycle wraps and doubles one LSH slot, so that intern gets a **start-spillover +
end-of-month** night pattern (~7–8 nights) while their partner gets one clean
week. The generator had no balancing logic and no cross-month memory.

- **October — fixed.** Swapped the LSH pair to `[Bronson, MacNeille]` so Bronson
  (whose Nov is vacation) absorbs the start+end double and MacNeille gets one
  clean mid-month week (10/11–16) — matching the scheduler's manual exactly and
  honoring MacNeille's "one week, not starting on nights" request. His 10/17–18
  weekend off is now automatic (post-nights), so the earlier swap for it was
  removed.
- **New audit check.** `audit.py` now prints a **night-float fairness** report:
  every start+end double per month, plus the year-total nights per intern with a
  spread flag. This surfaces the imbalance automatically going forward.
- **January — can't safely rebalance.** Structurally forced: January has 3 LSH
  night-float weeks (odd, can't split evenly), and Oghenesume's firm wedding
  forces the 1/31 week onto Zaidi (he continues into Feb; Oghenesume must be off).
  Swapping the pair would put Oghenesume on nights during his wedding. Left as-is
  (the imbalance is only 1 night within January).
- **Zaidi's year total (24 nights) — needs a scheduler decision.** He's well
  above everyone else, driven mostly by **February (11 nights)** — the month-end
  protection has him cover two boundary weeks so departing interns don't finish
  on nights. Reducing it means relaxing that protection or offloading a February
  week, both judgment calls for the scheduler (February is a "perfect storm" where
  everyone present in late Feb except one Lahey rotator is leaving).

## ❌ Conflicts (can't accommodate within the rules)

- **Anna Li — 9/5 (her wedding Saturday).** 9/4 short call + 9/6 off are granted,
  but her **9/5 Saturday 24h can't be reassigned without breaking a rule** —
  September's first week is over-constrained: Wise is on a night-float block,
  Qasun holds the next Saturday and long calls on both sides of 9/5, and Kavelidou
  is night-float-adjacent. **Recommend: a senior or float covers her 9/5 24h**
  operationally (standard for a firm wedding).

- **Anna Li — May graduation.** Pending — the university hasn't confirmed which of
  two tentative weekends. Both are achievable by shifting her NF week (5/9–14)
  earlier or later; will apply once she confirms.

- **MacNeille — residual 10/2 night.** His October start was cut from 2 nights to
  1; fully eliminating the last night (10/2) would break Q4/coverage at the
  Sep→Oct boundary.

- **MacNeille & Anna Li — August / September pre-Oct items** that fall in the
  finalized August sheet are out of scope for this generator.
