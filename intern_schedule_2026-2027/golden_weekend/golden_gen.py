#!/usr/bin/env python3
"""
Golden Weekend Schedule generator (MOCKUP) — Sep 1 - Dec 31 2026.

Implements golden_weekend/SPEC.md:
  - roster encoding (LSH by month, Lahey/BMC blocks, seniors)
  - 4 weekly modules (GOLDEN / NIGHTS / HEAVY / STEADY) with per-day duty
  - base rotation (Heavy -> Steady -> Nights -> Golden, offset by slot),
    overridden per PINS 1-6 (pins win; overridden weeks are marked)
  - day-by-day assignment for every person, every day
  - coverage check (>=2 note-writers every day)
  - per-intern tally of golden weekends + total days off
  - writes assignment.json for the HTML renderer
"""

import json
from datetime import date, timedelta

# --------------------------------------------------------------------------
# Calendar range
# --------------------------------------------------------------------------
START = date(2026, 9, 1)
END = date(2026, 12, 31)

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# --------------------------------------------------------------------------
# Weeks (Mon-Sun), per SPEC. Week 1 and Week 18 are partial (bounded by the
# overall Sep1-Dec31 date range below; no special-casing needed for that).
# --------------------------------------------------------------------------
WEEKS = [
    (1, date(2026, 9, 1), date(2026, 9, 6)),
    (2, date(2026, 9, 7), date(2026, 9, 13)),
    (3, date(2026, 9, 14), date(2026, 9, 20)),
    (4, date(2026, 9, 21), date(2026, 9, 27)),
    (5, date(2026, 9, 28), date(2026, 10, 4)),
    (6, date(2026, 10, 5), date(2026, 10, 11)),
    (7, date(2026, 10, 12), date(2026, 10, 18)),
    (8, date(2026, 10, 19), date(2026, 10, 25)),
    (9, date(2026, 10, 26), date(2026, 11, 1)),
    (10, date(2026, 11, 2), date(2026, 11, 8)),
    (11, date(2026, 11, 9), date(2026, 11, 15)),
    (12, date(2026, 11, 16), date(2026, 11, 22)),
    (13, date(2026, 11, 23), date(2026, 11, 29)),
    (14, date(2026, 11, 30), date(2026, 12, 6)),
    (15, date(2026, 12, 7), date(2026, 12, 13)),
    (16, date(2026, 12, 14), date(2026, 12, 20)),
    (17, date(2026, 12, 21), date(2026, 12, 27)),
    (18, date(2026, 12, 28), date(2026, 12, 31)),
]


def week_of(d):
    for wn, s, e in WEEKS:
        if s <= d <= e:
            return wn
    raise ValueError(f"no week contains {d}")


WEEK_RANGE = {wn: (s, e) for wn, s, e in WEEKS}

# Weeks where a slot's *person* changes mid-week because of a month/block
# boundary that falls inside the week (module stays fixed for the slot all
# week; only the physical person changes). Per SPEC only LSH is monthly, and
# Lahey/BMC blocks all happen to land on week boundaries (verified below) so
# only LSH transitions mid-week, in W5, W9, W14.
LSH_MIDWEEK_TRANSITION_WEEKS = {
    5: "Sep->Oct (Wise/Li hand off to MacNeille/Bronson starting Thu 10/1)",
    9: "Oct->Nov (MacNeille/Bronson hand off to Wise/Kennedy starting Sun 11/1)",
    14: "Nov->Dec (Wise/Kennedy hand off to MacNeille/Bronson starting Tue 12/1)",
}

# --------------------------------------------------------------------------
# Roster
# --------------------------------------------------------------------------
LSH_BY_MONTH = {
    9: ("Wise", "Li"),
    10: ("MacNeille", "Bronson"),
    11: ("Wise", "Kennedy"),
    12: ("MacNeille", "Bronson"),
}


def lsh_person(slot, d):
    lsh1, lsh2 = LSH_BY_MONTH[d.month]
    return lsh1 if slot == "LSH1" else lsh2


LAHEY_BLOCKS = [
    ("Kavelidou", date(2026, 8, 24), date(2026, 9, 20)),
    ("Ahluwalia", date(2026, 9, 21), date(2026, 10, 18)),
    ("Chiasson", date(2026, 10, 19), date(2026, 11, 15)),
    ("Vivekanandan", date(2026, 11, 16), date(2026, 12, 13)),
    ("Salam", date(2026, 12, 14), date(2027, 1, 10)),
]

BMC_BLOCKS = [
    ("Zohaib Qasun", date(2026, 8, 17), date(2026, 9, 13)),
    ("Metri", date(2026, 9, 14), date(2026, 9, 27)),
    ("Butt", date(2026, 9, 28), date(2026, 10, 11)),
    ("Mullins", date(2026, 10, 12), date(2026, 11, 8)),
    ("Saeed", date(2026, 11, 9), date(2026, 11, 22)),
    ("Shetty", date(2026, 11, 23), date(2026, 12, 6)),
    ("Villanueva", date(2026, 12, 7), date(2026, 12, 20)),
    ("Farzeela", date(2026, 12, 21), date(2027, 1, 3)),
]

SENIOR_BLOCKS = [
    ("Aksoy", date(2026, 10, 12), date(2026, 10, 25)),
    ("Ramadan", date(2026, 10, 26), date(2026, 11, 8)),
    ("Abouelazaem", date(2026, 11, 9), date(2026, 12, 6)),
    ("Sultan", date(2026, 12, 7), date(2026, 12, 20)),
    ("Panchal", date(2026, 12, 21), date(2027, 1, 17)),
]


def block_person(blocks, d):
    for name, s, e in blocks:
        if s <= d <= e:
            return name
    return None


def senior_on(d):
    """Senior rounding on a given Sunday (None before 10/12 or if not Sunday)."""
    return block_person(SENIOR_BLOCKS, d)


# Sanity: confirm Lahey/BMC blocks land on week boundaries (Mon start / Sun
# end) so no mid-week person-splits happen there, only for LSH.
def _check_blocks_align_to_weeks(blocks, label):
    for name, s, e in blocks:
        # only need to check the boundary *inside* our study window
        if START <= s <= END and s.weekday() != 0 and s != START:
            print(f"NOTE: {label} block for {name} starts mid-week ({s})")
        if START <= e <= END and e.weekday() != 6 and e < END:
            print(f"NOTE: {label} block for {name} ends mid-week ({e})")


_check_blocks_align_to_weeks(LAHEY_BLOCKS, "Lahey")
_check_blocks_align_to_weeks(BMC_BLOCKS, "BMC")

# --------------------------------------------------------------------------
# Modules & duty table
# --------------------------------------------------------------------------
CYCLE = ["HEAVY", "STEADY", "NIGHTS", "GOLDEN"]
SLOTS = ["LSH1", "LSH2", "Lahey", "BMC"]
SLOT_OFFSET = {"LSH1": 0, "LSH2": 1, "Lahey": 2, "BMC": 3}

# Per-day duty, Mon..Sun. "STEADY_SUN" is resolved at runtime (senior present
# that Sunday -> OFF; otherwise -> Day) per SPEC footnote 1.
DUTY = {
    "GOLDEN": ["Day", "Day", "Day", "Day", "Day", "OFF", "OFF"],
    "NIGHTS": ["Night", "Night", "Night", "Night", "Night", "Night", "OFF"],
    "HEAVY": ["Day", "Day", "Day", "OFF", "Day", "Day", "24H"],
    "STEADY": ["OFF", "Day", "Day", "Day", "Day", "Day", "STEADY_SUN"],
}


def base_module(slot, week_idx0):
    return CYCLE[(week_idx0 + SLOT_OFFSET[slot]) % 4]


# --------------------------------------------------------------------------
# PIN overrides (pins win over pure rotation). Each entry fully replaces the
# module set for that week's slots (all 4 modules always distinct). Derived
# by hand to satisfy PINS 1-6 while preserving rest geometry as much as
# possible; verified programmatically below.
# --------------------------------------------------------------------------
OVERRIDES = {
    # PIN 1: Anna Li (LSH2, Sep) -> GOLDEN in W1. Base W1: LSH1=HEAVY,
    # LSH2=STEADY, Lahey=NIGHTS, BMC=GOLDEN. Swap LSH2<->BMC.
    1: {"LSH2": "GOLDEN", "BMC": "STEADY"},

    # PIN 2: MacNeille (LSH1, Oct) -> GOLDEN in W7. Base W7: LSH1=NIGHTS,
    # LSH2=GOLDEN, Lahey=HEAVY, BMC=STEADY. 3-cycle LSH1<-LSH2<-BMC so
    # Bronson (LSH2) doesn't land on back-to-back NIGHTS (he's already
    # NIGHTS in W6) and Mullins (fresh BMC person starting this Monday)
    # absorbs the NIGHTS instead.
    7: {"LSH1": "GOLDEN", "LSH2": "STEADY", "BMC": "NIGHTS"},

    # PIN 3 (support): MacNeille must have exactly one Oct NIGHTS week, not
    # in his first Oct week (W5), and W7 is now GOLDEN (pin 2) so the
    # NIGHTS week has to move. Base W8: LSH1=GOLDEN, LSH2=HEAVY,
    # Lahey=STEADY, BMC=NIGHTS. Swap LSH1<->BMC.
    8: {"LSH1": "NIGHTS", "BMC": "GOLDEN"},
}

OVERRIDE_REASONS = {
    1: "PIN1: Li forced to GOLDEN (swap w/ BMC)",
    7: "PIN2: MacNeille forced to GOLDEN (3-cycle w/ LSH2, BMC)",
    8: "PIN3: MacNeille's Oct NIGHTS week moved here (was W7, now GOLDEN per PIN2)",
}


def module_table():
    table = {}
    for wn, _, _ in WEEKS:
        week_idx0 = wn - 1
        mods = {slot: base_module(slot, week_idx0) for slot in SLOTS}
        if wn in OVERRIDES:
            mods.update(OVERRIDES[wn])
        # distinctness invariant
        assert sorted(mods.values()) == sorted(CYCLE), (
            f"week {wn} modules not a permutation of CYCLE: {mods}"
        )
        table[wn] = mods
    return table


MODULE_TABLE = module_table()

# --------------------------------------------------------------------------
# Day-by-day assignment
# --------------------------------------------------------------------------
def build_schedule():
    days = []
    per_person = {}  # name -> list of (date, duty, slot, module)

    d = START
    while d <= END:
        wn = week_of(d)
        weekday = d.weekday()  # Mon=0..Sun=6
        senior_today = senior_on(d) if weekday == 6 else None

        entries = []
        for slot in SLOTS:
            module = MODULE_TABLE[wn][slot]
            if slot == "LSH1" or slot == "LSH2":
                person = lsh_person(slot, d)
            elif slot == "Lahey":
                person = block_person(LAHEY_BLOCKS, d)
            else:
                person = block_person(BMC_BLOCKS, d)

            duty = DUTY[module][weekday]
            if duty == "STEADY_SUN":
                duty = "OFF" if senior_today else "Day"

            entries.append(
                {"slot": slot, "person": person, "module": module, "duty": duty}
            )
            per_person.setdefault(person, []).append(
                {"date": d.isoformat(), "duty": duty, "slot": slot, "module": module}
            )

        note_writers = sum(1 for e in entries if e["duty"] in ("Day", "24H"))
        if weekday == 6 and senior_today:
            note_writers += 1  # senior rounds Sunday, counts per SPEC floor

        days.append(
            {
                "date": d.isoformat(),
                "weekday": WEEKDAY_NAMES[weekday],
                "week": wn,
                "entries": entries,
                "senior": senior_today,
                "note_writers": note_writers,
            }
        )
        d += timedelta(days=1)

    return days, per_person


DAYS, PER_PERSON = build_schedule()

# --------------------------------------------------------------------------
# Coverage check
# --------------------------------------------------------------------------
def coverage_violations():
    return [day for day in DAYS if day["note_writers"] < 2]


VIOLATIONS = coverage_violations()

# --------------------------------------------------------------------------
# Golden weekend + days-off tally
# --------------------------------------------------------------------------
def tally():
    results = {}
    for person, records in PER_PERSON.items():
        by_date = {r["date"]: r["duty"] for r in records}
        days_off = sum(1 for duty in by_date.values() if duty == "OFF")
        golden_weekends = 0
        for wn, s, e in WEEKS:
            sat = None
            sun = None
            cur = s
            while cur <= e:
                if cur.weekday() == 5:
                    sat = cur
                if cur.weekday() == 6:
                    sun = cur
                cur += timedelta(days=1)
            if sat and sun:
                sat_iso, sun_iso = sat.isoformat(), sun.isoformat()
                if by_date.get(sat_iso) == "OFF" and by_date.get(sun_iso) == "OFF":
                    golden_weekends += 1
        results[person] = {"golden_weekends": golden_weekends, "days_off": days_off}
    return results


TALLY = tally()

# --------------------------------------------------------------------------
# PIN verification
# --------------------------------------------------------------------------
def duty_on(person, iso_date):
    for r in PER_PERSON[person]:
        if r["date"] == iso_date:
            return r["duty"]
    return None


def module_in_week(person, wn):
    s, e = WEEK_RANGE[wn]
    for r in PER_PERSON[person]:
        rd = date.fromisoformat(r["date"])
        if s <= rd <= e:
            return r["module"]
    return None


def pin_checks():
    lines = []

    # PIN 1
    ok1 = (
        MODULE_TABLE[1]["LSH2"] == "GOLDEN"
        and duty_on("Li", "2026-09-05") == "OFF"
        and duty_on("Li", "2026-09-06") == "OFF"
        and duty_on("Li", "2026-09-04") == "Day"
    )
    lines.append(f"PIN1 (Li GOLDEN in W1, off 9/5-9/6): {'PASS' if ok1 else 'FAIL'}")

    # PIN 2
    ok2 = (
        MODULE_TABLE[7]["LSH1"] == "GOLDEN"
        and duty_on("MacNeille", "2026-10-17") == "OFF"
        and duty_on("MacNeille", "2026-10-18") == "OFF"
    )
    lines.append(f"PIN2 (MacNeille GOLDEN in W7, off 10/17-18): {'PASS' if ok2 else 'FAIL'}")

    # PIN 3: not NIGHTS in first Oct week (W5), exactly one NIGHTS week in Oct
    oct_weeks_lsh1 = [5, 6, 7, 8]
    oct_mods = [MODULE_TABLE[w]["LSH1"] for w in oct_weeks_lsh1]
    ok3 = MODULE_TABLE[5]["LSH1"] != "NIGHTS" and oct_mods.count("NIGHTS") == 1
    lines.append(
        f"PIN3 (MacNeille not Nights in first Oct wk, exactly 1 Oct Nights wk): "
        f"{'PASS' if ok3 else 'FAIL'} (Oct modules W5-W8: {oct_mods})"
    )

    # PIN 4: not NIGHTS in W17 (Christmas week)
    ok4 = MODULE_TABLE[17]["LSH1"] != "NIGHTS"
    lines.append(f"PIN4 (MacNeille not Nights in W17/Christmas): {'PASS' if ok4 else 'FAIL'}")

    # PIN 5: NYE (12/31) Day or OFF only
    nye_duty = duty_on("MacNeille", "2026-12-31")
    ok5 = nye_duty in ("Day", "OFF")
    lines.append(f"PIN5 (MacNeille NYE 12/31 Day/OFF only): {'PASS' if ok5 else 'FAIL'} (duty={nye_duty})")

    # PIN 6: Bronson not stacked with back-to-back (calendar-adjacent) hard
    # modules (HEAVY/NIGHTS), and his hard-module load over his weeks isn't
    # disproportionate vs. his LSH1 counterpart (MacNeille) over the same weeks.
    bronson_weeks = sorted(
        {w for w, s, e in WEEKS if lsh_person("LSH2", s) == "Bronson" or lsh_person("LSH2", e) == "Bronson"}
    )
    seq = [(w, MODULE_TABLE[w]["LSH2"]) for w in bronson_weeks]
    hard = {"HEAVY", "NIGHTS"}
    stacked = any(
        seq[i][1] in hard and seq[i + 1][1] in hard and seq[i + 1][0] == seq[i][0] + 1
        for i in range(len(seq) - 1)
    )
    bronson_hard = sum(1 for _, m in seq if m in hard)
    counterpart_seq = [MODULE_TABLE[w]["LSH1"] for w in bronson_weeks]
    counterpart_hard = sum(1 for m in counterpart_seq if m in hard)
    ok6 = (not stacked) and abs(bronson_hard - counterpart_hard) <= 1
    lines.append(
        f"PIN6 (Bronson module mix balanced, no calendar-adjacent hard modules, "
        f"hard-module load {bronson_hard} vs counterpart {counterpart_hard}): "
        f"{'PASS' if ok6 else 'FAIL'} (sequence={seq})"
    )

    return lines, all([ok1, ok2, ok3, ok4, ok5, ok6])


PIN_LINES, PINS_OK = pin_checks()

# --------------------------------------------------------------------------
# Output: JSON for renderer
# --------------------------------------------------------------------------
OUT_PATH = "/home/user/Codex-playground-/intern_schedule_2026-2027/golden_weekend/assignment.json"


def write_json():
    payload = {
        "range": {"start": START.isoformat(), "end": END.isoformat()},
        "weeks": [
            {
                "week": wn,
                "start": s.isoformat(),
                "end": e.isoformat(),
                "modules": MODULE_TABLE[wn],
                "overridden": wn in OVERRIDES,
                "override_reason": OVERRIDE_REASONS.get(wn),
                "lsh_midweek_transition": LSH_MIDWEEK_TRANSITION_WEEKS.get(wn),
            }
            for wn, s, e in WEEKS
        ],
        "days": DAYS,
        "tally": TALLY,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)


write_json()

# --------------------------------------------------------------------------
# Printing
# --------------------------------------------------------------------------
def print_week_table():
    print("=" * 100)
    print("PER-WEEK MODULE ASSIGNMENT (Sep 1 - Dec 31 2026)")
    print("=" * 100)
    header = f"{'Wk':>3} {'Dates':>13}  {'LSH1':<10}{'LSH2':<10}{'Lahey':<10}{'BMC':<10}  Notes"
    print(header)
    print("-" * len(header))
    for wn, s, e in WEEKS:
        mods = MODULE_TABLE[wn]
        notes = []
        if wn in OVERRIDES:
            notes.append(f"OVERRIDDEN ({OVERRIDE_REASONS[wn]})")
        if wn in LSH_MIDWEEK_TRANSITION_WEEKS:
            notes.append(f"LSH mid-week handoff: {LSH_MIDWEEK_TRANSITION_WEEKS[wn]}")
        note_str = "; ".join(notes)
        datestr = f"{s.strftime('%m/%d')}-{e.strftime('%m/%d')}"
        print(
            f"{wn:>3} {datestr:>13}  {mods['LSH1']:<10}{mods['LSH2']:<10}"
            f"{mods['Lahey']:<10}{mods['BMC']:<10}  {note_str}"
        )
    print()


def print_coverage():
    print("=" * 100)
    print("COVERAGE CHECK (>=2 note-writers every day; Day+24H, senior counts Sun)")
    print("=" * 100)
    if not VIOLATIONS:
        print("PASS: every single day (Sep 1 - Dec 31 2026) has >= 2 note-writers.")
    else:
        print(f"FAIL: {len(VIOLATIONS)} day(s) with < 2 note-writers:")
        for day in VIOLATIONS:
            print(f"  {day['date']} ({day['weekday']}, wk{day['week']}): {day['note_writers']} writer(s)")
    print()


def print_tally():
    print("=" * 100)
    print("PER-INTERN TALLY: golden weekends (Sat+Sun both OFF) & total days off")
    print("=" * 100)
    print(f"{'Person':<18}{'Golden Weekends':>18}{'Total Days Off':>18}")
    for person in sorted(TALLY):
        t = TALLY[person]
        print(f"{person:<18}{t['golden_weekends']:>18}{t['days_off']:>18}")
    print()


def print_pins():
    print("=" * 100)
    print("PIN VERIFICATION (pins override rotation)")
    print("=" * 100)
    for line in PIN_LINES:
        print(line)
    print(f"\nALL PINS SATISFIED: {PINS_OK}")
    print()


if __name__ == "__main__":
    print_week_table()
    print_coverage()
    print_tally()
    print_pins()
    print(f"Wrote day-by-day assignment -> {OUT_PATH}")
    if VIOLATIONS or not PINS_OK:
        raise SystemExit(1)
