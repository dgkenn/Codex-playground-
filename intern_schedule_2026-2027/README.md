# LSH Transitional-Year Intern Call Schedule — Oct 2026 → Jun 2027

Call schedule for the interns rotating through **Lemuel Shattuck Hospital (LSH)**,
continuing the **finalized September 2026** sheet through the end of the academic
year. Each day's team is **2 LSH interns + 1 BMC-South/Brighton intern + 1 Lahey
intern**, covering Long Call, Short Call, Night Float and the Saturday 24h.

## Files

| File | What it is |
|---|---|
| `schedules/TYP_<Month>_<Year>.xlsx` | One file per month (Oct 2026 – Jun 2027), same layout as the finalized September sheet. |
| `schedules/TYP_Intern_Schedule_Oct2026-Jun2027.xlsx` | All nine months in one workbook. |
| `PRINCIPLES.md` | The comprehensive scheduling rules (source of truth). |
| `RULES_COMPLIANCE.md` | Rule-by-rule audit + duty hours + the few unavoidable exceptions. |
| `generator/gen.py` | Builds the schedule (the integrated Q4 march). |
| `generator/audit.py` | Independent compliance + ACGME duty-hour audit; writes the report. |
| `generator/export.py` | Writes the Excel workbooks. |
| `generator/apply_swaps.py` + `swaps.txt` | Apply resident swaps / days-off and check every rule still holds. |

## Swaps and days off (after the schedule is finalized)

Residents' swaps go through a one-command checker so nothing breaks the rules.

1. Edit `generator/swaps.txt` — one change per line:
   - `swap 2026-11-14 KENNEDY WISE` — trade whatever each is doing that day.
   - `swap 2026-11-08:2026-11-13 KENNEDY CHIASSON` — trade a whole block (swap the
     **full** week for night float).
   - `off 2027-03-12 MATSUOKA` — give a day off; whoever is already off covers.
2. Run `python3 apply_swaps.py`.
3. It prints **PASS**, or the exact rules the swap would break (and which block to
   swap instead), and writes `Intern_Schedule_with_swaps.html` so you can see the
   result. Approve human-side (both residents + chief), keep the lines in
   `swaps.txt` as the change log, and you always have a clean, checkable record.

## The model — integrated Q4 "march"

The schedule follows the comprehensive rules exactly (see `PRINCIPLES.md`): the
four slots cycle **[LSH1, Lahey, LSH2, BMC]**, the night-float slot advances each
week, **the Friday long-call intern becomes the next week's night float**, night
float returns to Monday long call, and the **Saturday 24h is the week's middle
intern**. The generator **reproduces the finalized September exactly**, then
continues the same march — so October is staffed seamlessly from September's phase.

## Compliance

Verified by a separate auditor (`generator/audit.py`) against every rule. All hard
rules pass except a small set of **unavoidable, documented exceptions** (two
5-Saturday-month doubles; the June 21–23 wind-down where the roster has no BMC
intern; and rules-permitted transition handoffs / first-Monday starts). ACGME
duty hours all pass (busiest ≤ 80 h/wk, no shift > 24h, ≥ 1 day off/week). See
`RULES_COMPLIANCE.md` for the full breakdown, including how the deterministic march
affects individual day-off requests.

## Regenerating

```bash
cd generator
python3 gen.py       # build -> assign.pkl
python3 audit.py     # compliance + duty-hour audit; writes out/RULES_COMPLIANCE.md
python3 export.py    # writes the .xlsx files
```

Roster, rotation blocks, and the phase seed live at the top of `gen.py`.
