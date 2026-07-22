# Golden Weekend Schedule — Build Spec (mockup, Sep 1 – Dec 31 2026)

An **experimental** alternative to the Q4 march. Goal: every intern gets one true
**golden weekend** (Sat+Sun off) plus one extra weekend day off per 4-week cycle,
with **never fewer than 2 note-writers on any day** (18-patient cap → ≤9 notes each).
This is a MOCKUP to visualize the format — not the production schedule.

## Roster (4 intern slots each week: LSH1, LSH2, Lahey, BMC)

LSH by month:  Sep = Wise, Li · Oct = MacNeille, Bronson · Nov = Wise, Kennedy · Dec = MacNeille, Bronson
(LSH1 = first name, LSH2 = second name.)

Lahey blocks: Kavelidou 8/24–9/20 · Ahluwalia 9/21–10/18 · Chiasson 10/19–11/15 · Vivekanandan 11/16–12/13 · Salam 12/14–1/10
BMC blocks:  Zohaib Qasun 8/17–9/13 · Metri 9/14–9/27 · Butt 9/28–10/11 · Mullins 10/12–11/8 · Saeed 11/9–11/22 · Shetty 11/23–12/6 · Villanueva 12/7–12/20 · Farzeela 12/21–1/3

Seniors (round Sundays when on service; NONE before 10/12):
  Aksoy 10/12–10/25 · Ramadan 10/26–11/8 · Abouelazaem 11/9–12/6 · Sultan 12/7–12/20 · Panchal 12/21–1/17

## Weeks (Mon–Sun). Sep 1 2026 is a Tuesday, so week 1 is a Tue-start partial.
W1 9/1–9/6 · W2 9/7–9/13 · W3 9/14–9/20 · W4 9/21–9/27 · W5 9/28–10/4 · W6 10/5–10/11 ·
W7 10/12–10/18 · W8 10/19–10/25 · W9 10/26–11/1 · W10 11/2–11/8 · W11 11/9–11/15 · W12 11/16–11/22 ·
W13 11/23–11/29 · W14 11/30–12/6 · W15 12/7–12/13 · W16 12/14–12/20 · W17 12/21–12/27 · W18 12/28–12/31 (partial)

## The four weekly modules (per-day duty)

| Module | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| **GOLDEN** | Day | Day | Day | Day | Day | **OFF** | **OFF** |
| **NIGHTS** | Night | Night | Night | Night | Night | Night | OFF |
| **HEAVY**  | Day | Day | Day | **OFF** | Day | Day | **24H** |
| **STEADY** | **OFF** | Day | Day | Day | Day | Day | OFF¹ |

¹ Steady's Sunday is **OFF when a senior is on service** (senior rounds that Sunday);
  when NO senior is on service, Steady works Sunday as a Day.

"Day" = daytime rounding (≤9 notes). "Night" = night float. "24H" = Sun 7a→Mon 7a.
Nights module = Mon–Sat (6 nights, the ACGME cap); Heavy's Sun 24H covers Sunday night.
After a Heavy week (Sun 24H), that intern's next module is Steady (Mon OFF = post-call rest).

## Rotation

Each week the 4 slots hold 4 DISTINCT modules. Base cycle order **Heavy → Steady → Nights → Golden**
(this order gives good rest geometry: Heavy's Sun-24H → Steady's Mon-off; Steady's weekend →
rested into Nights; Nights → Golden's long recovery). Rotate by slot so all four are covered each week:
`module(slot, week) = CYCLE[(week_index + slot_offset) % 4]`, offsets 0/1/2/3 per slot — but see PINS,
which take priority and may locally override the pure rotation (mark overridden weeks in a footnote).

## Coverage invariant (MUST verify)

Every day, count interns doing Day or 24H = **note-writers**. Must be **≥ 2 every single day**
(Sunday floor = Heavy's 24H + [senior, or Steady if no senior]). Print any day that violates this.

## PINS — Shattuck intern requests (HARD; override rotation to satisfy)

1. **Anna Li (LSH2, Sep) → GOLDEN in W1 (9/1–9/6)** — firm wedding; she is OFF Sat 9/5 + Sun 9/6.
   (She is a Day intern Fri 9/4 in Golden — fine, done by evening to travel.)
2. **MacNeille (LSH1, Oct) → GOLDEN in W7 (10/12–10/18)** — off weekend 10/17–18.
3. **MacNeille (LSH1, Oct) must NOT be NIGHTS in his first Oct week** (no "starting on nights"), and has exactly ONE Nights week in Oct.
4. **MacNeille (LSH1, Dec) must NOT be NIGHTS during Christmas week W17 (12/21–27)**; his Dec Nights week must be elsewhere.
5. **MacNeille light on NYE (Thu 12/31, W18): Day or OFF — never Nights/24H.**
6. **Bronson (LSH2 Oct, LSH2 Dec): keep his module mix balanced** (don't stack all the hard modules on him).

## Deliverables (write into this `golden_weekend/` directory)

1. `golden_gen.py` — implements the above; prints per-week module assignment table, the coverage
   check (≥2/day), and a per-intern tally of golden weekends + days off. Must run clean under python3.
2. `golden_weekend_schedule.html` — a self-contained, scrollable month view (Sep, Oct, Nov, Dec 2026),
   one row per day (Day/Date), columns for each on-duty person's module/role, color-coded by module
   (Golden = gold, Nights = navy, Heavy = red-ish, Steady = green, OFF = grey), a legend, and the
   senior shown on their Sundays. Match the clean aesthetic of the existing `Intern_Schedule_FullYear.html`.
   Theme-agnostic, no external assets.
