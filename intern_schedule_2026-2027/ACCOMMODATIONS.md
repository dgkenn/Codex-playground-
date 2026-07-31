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
- **February — FIXED (scheduler correction).** Zaidi's 24-night year total was
  **not** a fairness problem, it was a **bug**. A role-swap window (`SWAP12_DAYS`,
  2/8–3/5 and 3/7–4/2) had the LSH2 and Lahey slots trading places to keep the
  month-end night float off a departing intern. That broke the march two ways:
  (1) Zaidi finished nights Fri 2/5 and by the core rule *night float returns to
  Monday long call* owns **LC on Mon 2/8** — the swap handed it to Kopp Vanuzzi
  and pushed Zaidi onto the Lahey slot, which then gave him a **second NF week
  (2/21–26)**; (2) Kopp Vanuzzi takes over **Juyal's** position in the march on
  2/8 and should simply continue it — the swap stopped him marching with Juyal
  at all. **Both windows are removed; the march is now pure for all 296 days.**
  Zaidi: February 11 → **6 nights**, year 24 → **19**, in line with everyone else.
- **January — nothing to fix.** With the march pure, January is a clean cycle
  (Zaidi 1/3–8, Ahn 1/10–15, Oghenesume 1/17–22, Juyal 1/24–29, Zaidi 1/31
  spillover). Oghenesume's wedding weekend is untouched.

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

## ❓ Open question for the scheduler

- **Kennedy holds the March month-end night float (3/28–3/31)**, with Oghenesume
  continuing the block 4/1–4/2. This is the rules' normal boundary handoff, but it
  is only acceptable if **Kennedy's April is outpatient / elective / vacation**.
  The audit is deliberately **failing** on this until it's confirmed, rather than
  silently exempting it. If April is an inpatient service, the 3/28 week moves.
- Same confirmation still outstanding for **Oghenesume (NF 4/25–30, block ends
  4/30)** → what is his May rotation? Currently carried as an exemption.
