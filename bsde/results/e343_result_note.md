# E343 — result note. **NOT INTERPRETABLE (G1, G2).** And the reason is the finding.

Registration: `bsde/src/bsde/experiments/e343_catalogue_recurrence.py`, committed before any statistic in
it existed. Output: `bsde/results/e343_catalogue_recurrence.json`.

**Verdict as registered: NOT INTERPRETABLE.** Both extraction gates failed. The numbers the primaries
printed — 3 rules with 5 post-statement recurrences, 3 rules recording cited-then-violated instances —
are **UNLICENSED and, as diagnosed below, demonstrably wrong in both directions.**

**E343 is not repaired and re-run.** One repair was available under rule 58 and it is not enough: the
diagnosis below shows the artifact cannot support the measurement at all, so a better parser would return
a number that is still wrong. Curating the table by hand *after* seeing the numbers is precisely the
contamination rule 58 exists to prevent.

**A process deviation to record: I ran this without `--smoke` first.** Rule 26 says smoke-test on
permuted or degenerate input before the real run, which would have exposed the extraction defects with
nothing at stake. Running it live is what made the primaries visible and therefore made the run
unrepairable. That cost is entirely self-inflicted.

---

## What the gates found

**G1(i) — the rule index is not what it appears to be.** The extractor matched **111** numbered markers
for **100** distinct rule numbers. The 11 extras are ordinary prose numbered-lists elsewhere in
`CLAUDE.md` — the E248 four-item list at lines 177–187, the container-snapshot list at 377–384, and the
ten-result-cadence list at 949–954 — all of which are formatted identically to a catalogue rule. Rule
bodies for numbers 1–4 were therefore wrong, silently.

**G1(ii) — the independent dating method covered 1 of 100 rules.** The phrase-based cross-check
(`git log -S` on a distinctive phrase, which never sees the rule number) normalised whitespace before
choosing its phrase, so the resulting 8-word strings span the file's line wrapping and match nothing.
That is a defect in my check, not in the artifact — but it means the by-number dates were never
independently verified, which is exactly what rule 23 demands and exactly what the gate is for.

**G2 — the classifier was never exercised in one of its two directions**: 3 rules flagged as
post-statement, **0** withheld as at-or-before, although the catalogue certainly contains the second kind.

## Why the artifact cannot support this measurement, which is the real result

Four defects, each verified directly against the file. They are properties of the **catalogue**, not of
the parser, and the first three are unfixable by better parsing.

1. **Two of rule 38's three recurrence markers have no date anywhere in the rule.** Rule 38 records a
   SECOND, THIRD and FOURTH occurrence and its entire body contains exactly **one** ISO date
   (`2026-08-02`). "THIRD OCCURRENCE, ninety minutes after the second" and "FOURTH OCCURRENCE the same
   day" are perfectly clear to a human and carry no timestamp a classifier can use. **A recurrence that
   cannot be dated cannot be placed before or after the rule that was supposed to prevent it**, which is
   the entire question.

2. **"Nth occurrence" conflates two opposite things and no field separates them.** Rule 36 is titled
   *"Credential precedence, third occurrence"* — the rule was **written at** its third occurrence, so
   occurrences 1–3 all predate it and it has failed zero times. Rule 37 accumulated its THIRD, FOURTH and
   FIFTH occurrences **after** being written, so it failed four times. The two are indistinguishable in
   prose. My run scored rule 36 and rule 39 as post-statement recurrences on the strength of an unrelated
   date happening to sit nearby, which is a **false positive in the direction that inflates the finding**.

3. **A recurrence can be filed under a different rule number than the rule it violates, and then no
   per-rule scan can see it.** Rule 84's title is *"…RULE 77, SECOND OCCURRENCE, AND THE DIAGNOSIS IS THE
   SAME BOTH TIMES"* — it **is** a post-statement recurrence of rule 77, written up as a new rule. Rule
   77's own body contains no marker and no date, so a scan of rule 77 finds nothing. This is a **false
   negative**, and it is the more consequential direction: the true post-statement recurrence count is
   **higher** than any prose scan can recover, and by an unknown amount.

4. **Markers split across a line break are invisible to a single-line pattern.** Rule 84's own marker was
   missed for exactly this reason, which is how defect 3 stayed hidden until the gate forced the audit.

## The conclusion, which is worth more than the count would have been

**A lessons-learned register written as prose is not machine-auditable, so nobody — including its own
author — can measure whether it works.** That is not a parsing inconvenience; it is why the premise
behind every such register goes untested. The information needed is genuinely absent from the artifact:
undated recurrences, no field distinguishing "written at the Nth occurrence" from "failed N−1 times
since", and recurrences filed under the wrong identifier.

The direction of the error is knowable even though its size is not. Defect 2 inflates; defect 3 deflates;
and defect 3 is structural rather than incidental, because a fresh recurrence is *interesting* and
therefore tends to be written up as a new rule rather than appended to an old one. **The count is most
likely an undercount, and the honest report of E343's primaries is not "5 recurrences" but "an unknown
number, at least several, that this artifact cannot pin down."**

## What the successor needs, and it is a change to the register rather than to the analysis

E344 is not a better parser. It is a structured recurrence field, and it belongs in
`bsde/src/bsde/preregistry/` where the register spec already lives — because the same defect will afflict
any register built from that spec. The minimum each recurrence needs:

```
rule_id          which rule failed  (NOT which rule the write-up was filed under)
occurred_on      ISO date
first_stated_on  the rule's own first-appearance date, carried so before/after is decidable offline
noticed_by       self | gate | reviewer  -- limitation 1 is only measurable if this exists
was_cited        whether the rule was invoked by name in the work that violated it
```

Only with `rule_id` distinct from the filing location does defect 3 become visible, and only with
`noticed_by` does the lower-bound problem become an estimable quantity rather than a caveat.

**LIMITATION 1 still stands and is now doubly binding**: a recurrence nobody noticed is invisible to any
scheme, structured or not. Structure fixes the recurrences that *were* noticed and mis-recorded; it
cannot fix the ones that were never seen.
