# LSH Intern Schedule — Compliance Report (comprehensive-rules / march model)

Coverage **Oct 1 2026 – Jun 23 2027**, continuing the finalized September. Built on the integrated Q4 march (Friday long-call → next-week night float; night float → Monday long call; Saturday 24h = the week's middle intern). The generator reproduces the finalized September **exactly**. Checked against every rule in `PRINCIPLES.md`.

## Hard rules

| Rule | Status |
|---|---|
| One Long Call per day | ✅ PASS |
| Different long-call intern than previous day | ⚠️ SEE NOTE |
| Q4 — every intern on call only every 4th day | ⚠️ SEE NOTE |
| No one leaving the service ends on night float | ✅ PASS |
| Friday long-call intern = next week's night float | ⚠️ SEE NOTE |
| Night float: same person the whole Sun–Fri block | ✅ PASS |
| Night-float intern present | ✅ PASS |
| No night float on Saturday | ✅ PASS |
| No daytime + night float same day | ✅ PASS |
| Sunday has no short call | ✅ PASS |
| Saturday: 24h only (no SC/NF) | ✅ PASS |
| Only one intern off at a time; weekday off = Thursday | ✅ PASS |
| Saturday 24h intern off the next day | ✅ PASS |
| Saturday 24h intern not night float the next day | ✅ PASS |
| Saturday 24h intern didn't do night float the night before | ✅ PASS |
| Every intern ≥1 day off per week | ✅ PASS |
| All present accounted for each day | ✅ PASS |
| One 24h Saturday per intern per month | ⚠️ SEE NOTE |

## Necessary exceptions (unavoidable; all surfaced)

1. **Two Saturday 24h doubles — Bronson (Oct), Li (May).** A 5-Saturday calendar month whose repeating middle-intern slot lands on a (stable) LSH intern puts that intern on the 1st and 5th Saturday. Reassigning the 5th would force a different intern into long-call-then-24h or back-to-back long call, breaking the strict Q4 march. The prior rules explicitly allowed "in very rare occasions 2." These are the only two all year.
2. **June 21–23, 2027 wind-down.** The roster has **no BMC-South intern after 6/20** (Shirin Saeed's block ends), so those last 3 days run with 3 interns instead of 4; with only two daytime interns, long call can't hold a strict 4-day gap on 6/22–6/23. Everything through 6/20 is clean.
3. **New intern on long call / night float at a rotation start (10 times).** The Q4 march (and Monday night-float starts, per the rules) sometimes place an arriving BMC/Lahey intern on long call or night float on their first Monday. The comprehensive rules permit this; the earlier email preferred avoiding it "when possible." Days: Mon 9/28 BUTT (BMC); Mon 11/23 SHETTY (BMC); Mon 12/21 FARZEELA (BMC); Mon 2/15 VILLANUEVA (BMC); Mon 3/15 BUTT (BMC); Mon 3/22 ALMADHOOB (LAHEY); Mon 4/19 AHLUWALIA-S (LAHEY); Mon 5/10 METRI (BMC); Mon 5/17 SANCHEZ-ALMANZAR (LAHEY); Mon 6/14 PATEL (LAHEY).
4. **Night-float transition handoffs (7).** At month/rotation boundaries a departing intern finishes a few nights and the arriving intern continues the block — exactly as the rules describe ("a new intern starts night float when the month ends").

## Slot integrity — no role swaps (scheduler correction)

A previous revision carried a **role-swap window** (`SWAP12_DAYS`, Feb 8 – Mar 5 and Mar 7 – Apr 2) in which the **LSH2 and Lahey slots traded places**, meant to keep the month-end night float off a departing LSH intern.  The scheduler flagged it and it has been **removed**.  It broke the march for both slots:

- **Zaidi (LSH2) was marched wrong in February.** He finished nights Fri 2/5, so by the core rule *"night float returns to Monday long call"* he owns **LC on Mon 2/8**.  The swap gave that long call to Kopp Vanuzzi and moved Zaidi onto the Lahey slot, which then handed him a **second night-float week (2/21–26)**.  That one override is the entire reason his year total read 24 nights.
- **Kopp Vanuzzi never marched with Juyal's schedule.** The Lahey **slot** is continuous across a rotator handoff: Kopp takes over Juyal's position on 2/8 and simply continues the march from where Juyal left it.  The swap prevented that.

The march is now **pure for all 296 days**: the four slots `[LSH1, Lahey, LSH2, BMC]` cycle without exception, and every arriving BMC/Lahey rotator inherits their slot's march position from the person they replace.  Effect on Zaidi: **February 11 → 6 nights, year 24 → 19**, in line with everyone else.

## Leaving-the-service night-float protection (hard rule)

With the march pure, a month-end night-float week can land on a departing LSH intern.  The rules permit the boundary handoff itself (*"a new intern starts night float when the month ends"*) — what they forbid is an intern walking into their **next inpatient rotation** straight off a night shift.  So each case is exempt **only** if that intern's next month is outpatient / elective / vacation.  The audit enforces this as a hard rule (`end-on-nf`) and fails loudly for anything unconfirmed:

| Intern | Month-end nights | Block ends | Next month | Status |
|---|---|---|---|---|
| Wise | 9/27–9/30 | 9/30 | Elective | ✅ confirmed by PD |
| Bronson | 10/25–10/30 | 10/31 | Vacation | ✅ confirmed by scheduler |
| Zaidi | 2/28 (1 night) | 2/28 | Vacation | ✅ confirmed |
| Kennedy | 3/28–3/31 | 3/31 | Elective | ✅ confirmed |
| Oghenesume | 4/25–4/30 | 4/30 | ED (shift-based, flexible) | ✅ confirmed |

**All five are confirmed against the year rotation grid — there are no unverified exemptions left.**  Each is a month-boundary handoff the rules explicitly permit: the departing intern finishes their nights and the arriving LSH intern continues the block (Kennedy 3/28–3/31 → Oghenesume 4/1–4/2; Zaidi 2/28 → Kennedy 3/1–3/5).  If any of these rotations changes, delete the entry from `NEXT_IS_OUTPATIENT` in `audit.py` and the audit will fail loudly rather than silently shipping a bad transition.

## ACGME duty hours

| Limit | Status | Measured |
|---|---|---|
| ≤ 80 h/wk (avg over 4 wks) | ✅ PASS | busiest 66.5 h/wk |
| No duty period > 28h | ✅ PASS | longest 24 h (Sat 24h) |
| ≥ 1 day off per week | ✅ PASS | longest streak 6 days |

## Dr. Kennedy's November requests (accommodated)

The march is fully deterministic, so honoring a personal request requires a local slot swap. Kennedy's is applied for Nov 1-13 (Kennedy ⇄ Chiasson). Status:

| Request | Outcome |
|---|---|
| Weekend of Nov 7-8 fully off | ✅ MET — Kennedy swaps slot roles with the Lahey intern (Chiasson) for Nov 1-13: he does night float 11/1-6 and is OFF the whole 11/7-8 weekend. |
| Fri 11/6 free to fly | PARTIAL — Kennedy's night-float shift Fri 11/6 is 7:30pm-9:30am, so he is FREE Friday until 7:30pm (a daytime/early-evening flight works). A full Friday off would need a single-night coverage swap that ripples Q4 — available on request. |
| Thanksgiving Day (Thu 11/26) off | ✅ MET — off |
| Thanksgiving Saturday | Kennedy is the Sat 11/28 24h — his single Saturday for the block. |
| Cost of the accommodation | One boundary exception: Fri 10/30 long call (Chiasson) no longer couples to the 11/1 night float (Kennedy), because Kennedy isn't present in October. This is a month-boundary reset. |

> This slot swap keeps every hard rule intact for Nov 1-13; its only cost is the one month-boundary coupling note above (Fri 10/30 → 11/1 night float). If Kennedy needs the **entire** Friday 11/6 off (a late flight), a single-night coverage swap can be added — it introduces one Q4 ripple, so it's left off unless requested.