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
| **Kennedy** | *(equity check on the above)* | ✅ **verified cost-free** — see below | none in workload |
| **Oghenesume** | April 9–12 off | ✅ **4/10–11 weekend fully off** (freed the 4/11 Sunday long call) | 2 Q4 gaps on **Rivera** (BMC, non-LSH) |

**Note on Kennedy's Friday 11/6 and Oghenesume's 4/9 / 4/12:** these are weekdays,
and the rules only allow a *full* day off on Thursdays. So the best possible is a
**short call** (light day, done ~3:30pm) — which is what they now have. Fully
freeing them, or putting Oghenesume on night float to free those days, would
cascade badly (it pushed another intern to *end* April on nights), so I left it
at the clean weekend-off.

## ⚖️ Equity check on the November (Kennedy ⇄ Chiasson) accommodation

Re-ran November **with and without** the swap and compared every intern.

**1. Nobody's workload changes — at all.** November totals are identical in both
versions for all seven interns present: nights, long calls, Saturday 24h, short
calls, days off, and total hours. The swap moves *which week* Kennedy and
Chiasson hold night float; it does not move any work between them.

| Nov 2026 | NF | LC | 24h | SC | OFF | hrs |
|---|---|---|---|---|---|---|
| Wise | 6 | 7 | 1 | 9 | 7 | 262 |
| Kennedy | 6 | 6 | 1 | 10 | 7 | 259 |
| Chiasson | 6 | 3 | 0 | 3 | 3 | 142 |
| Saeed | 6 | 2 | 0 | 3 | 3 | 132 |
| Vivekanandan | 2 | 3 | 1 | 6 | 3 | 136 |

*(unchanged by the accommodation — every figure is the same either way)*

**2. Chiasson does not lose a free weekend.** Hers *moves*, 11/7–8 → 10/31–11/1.
She has exactly one fully-free weekend in her Lahey block (10/19–11/15) in both
versions, plus her single Saturday 24h on 10/24 either way. An earlier
November-only count appeared to show 1 → 0; that was a calendar artifact —
the Saturday of her free weekend simply lands in October.

**3. Nobody outside the pair is touched.** Wise, Saeed, Mullins, Vivekanandan and
Shetty have byte-identical schedules in both versions.

**4. Kennedy is not getting a lighter year.** Normalised per day on LSH (some
interns do 3 LSH months, some 2), he carries the **most** nights of anyone:

| intern | LSH days | nights | nights/30d | Sat 24h |
|---|---|---|---|---|
| **Kennedy** | 61 | 15 | **7.4** | 2 |
| Oghenesume | 84 | 20 | 7.1 | 2 |
| Wise | 60 | 14 | 7.0 | 2 |
| Bronson | 93 | 20 | 6.5 | 3 |
| Zaidi | 89 | 19 | 6.4 | 3 |
| Li | 89 | 18 | 6.1 | 4 |
| MacNeille | 62 | 12 | 5.8 | 3 |
| Matsuoka | 54 | 10 | 5.6 | 2 |

**The one real cost** is the audit's single `fri-lc-nf` flag: Chiasson is Friday
long call 10/30 but Kennedy takes the 11/1 Sunday nights, so the *Friday-LC →
next-week's-nights* chain breaks once at the month boundary. In the pure march
Chiasson would have gone 10/30 long call straight into nights 11/1–6; instead she
gets the free weekend and starts nights 11/8. That is the only structural
consequence, and it lands as a benefit rather than a burden.

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

## ✅ Month-end night-float transitions — all confirmed

Every case where an LSH intern's nights run to their block end is now verified
against the year rotation grid. No unconfirmed exemptions remain.

| Intern | Nights | Block ends | Next rotation | |
|---|---|---|---|---|
| Wise | 9/27–9/30 | 9/30 | Elective | ✅ |
| Bronson | 10/25–10/30 | 10/31 | Vacation | ✅ |
| Zaidi | 2/28 (1 night) | 2/28 | Vacation | ✅ |
| Kennedy | 3/28–3/31 | 3/31 | Elective | ✅ |
| Oghenesume | 4/25–4/30 | 4/30 | ED — shift-based, flexible | ✅ |

Each is the boundary handoff the rules describe: the departing intern finishes
their nights and the arriving LSH intern continues the block (Kennedy 3/28–31 →
Oghenesume 4/1–2; Zaidi 2/28 → Kennedy 3/1–5). If any rotation changes, remove
the entry from `NEXT_IS_OUTPATIENT` in `audit.py` and the audit fails loudly.
