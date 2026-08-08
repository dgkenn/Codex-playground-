#!/usr/bin/env python3
"""E343 -- does writing a failure mode down prevent it? Exact-denominator audit of an error catalogue.

PRE-REGISTRATION. Committed before any statistic in it exists.

THE QUESTION AND WHY IT IS ANSWERABLE HERE. Every "lessons learned" register, post-mortem file, methods
checklist and reporting guideline rests on one premise: that writing a failure mode down reduces the rate
at which it recurs. **The premise is almost never measured**, because measuring it needs an exact
denominator -- the complete set of documented failure modes, each dated, with the subsequent work
inspectable -- and such artifacts are rarely public with their history intact.

This repository has one. `CLAUDE.md` carries a numbered error catalogue whose opening line is *"Every rule
below was paid for with a wrong result in this project"*, it has 100 rules, and the file's git history
(81 commits, 2026-06-19 to 2026-08-08) dates every rule's first appearance to the commit.

**THE SETTING IS MAXIMALLY FAVOURABLE TO THE PREMISE, AND THAT IS THE POINT.** One analyst; a catalogue
they wrote themselves from their own errors, so nothing is unfamiliar or externally imposed; a standing
instruction at the head of the section to read it before designing any analysis; and rules routinely
cited by number inside the experiment files that follow. If documentation prevents recurrence anywhere, it
should prevent it here. Whatever recurrence this setting shows is therefore a **floor** on what a
multi-analyst, externally-imposed checklist would show, not a typical value.

PRIOR ART. A targeted PubMed search via E-utilities (rule 25 -- never WebFetch) for a study measuring
recurrence of documented methodological failure modes against an exact denominator returned nothing
relevant: the "lessons learned + recurrence" hits are clinical (secondary stroke prevention, PMID
34575320; papillomatosis registry, PMID 36855411) and the "same statistical error repeated despite
guidelines" query returned a single unrelated pharmacy survey. **PubMed indexes metaresearch poorly, so
this is a search result and not a proof of novelty**, and it is worded that way in any write-up.

------------------------------------------------------------------------------------------------------
PRIMARIES.

P1  POST-STATEMENT RECURRENCE. For each rule, whether its own body records the same failure mode
    occurring AFTER that rule was already in the file, and how many times. A recurrence marker is a
    dated "SECOND/THIRD/FOURTH/FIFTH/SIXTH OCCURRENCE" passage inside the rule's own text; it counts as
    POST-STATEMENT only if its date is strictly after the rule's first-appearance commit date.
    **Reported as a COUNT, never as an unqualified rate -- see LIMITATION 1.**

P2  EXPOSURE. Days between a rule's first appearance and each of its recorded recurrences, and every
    rule's total exposure in days, so that a rule written yesterday is not scored as a rule that held.

P3  CITED-THEN-VIOLATED. The count of rules whose body records the rule being invoked BY NAME in the very
    work that then violated it. **This is the strongest available form of the finding**, because it
    removes the only innocent explanation a recurrence otherwise has -- that the analyst had not read the
    rule. The catalogue contains sentences of exactly this shape, e.g. rule 54's *"Rule 54 was cited by
    name inside the file that then failed it"*, and P3 counts them.

PREDICTION: post-statement recurrence is non-zero and CONCENTRATED -- a minority of rules recur, and the
ones that do recur repeatedly rather than once.

WRONG IF zero rules recur post-statement. **That is named as the outcome that would refute the premise of
this whole line**: the catalogue would have held perfectly across its exposure, and the interesting
question would become what makes it work rather than what makes it fail.

GATES.
  G1  EXTRACTION FIDELITY (rule 23 -- validate against an INDEPENDENT implementation). Two things must
      hold. (i) The rule index built by a line-start regex over the current file must be exactly the
      contiguous set 1..N with no duplicates and no gaps. (ii) Each rule's first-appearance date, found
      by walking every commit and asking which ones contain that RULE NUMBER, must agree with a second
      and mechanically different method: `git log -S` on a distinctive PHRASE taken from the rule's own
      body, which never looks at the number at all. **Any disagreement fails the gate**, because a
      renumbering would silently corrupt every date and the number-based method alone cannot see it.
  G2  THE CLASSIFIER MUST BE CAPABLE BOTH WAYS (rule 40). The post-statement classifier must be shown, on
      the real data, both to FLAG at least one marker dated after its rule's first appearance and to NOT
      FLAG at least one marker dated at or before it. Both cases are printed with their dates. If either
      is absent the classifier was never exercised in one of its directions and the file reports NOT
      INTERPRETABLE -- a distinction that matters here because the catalogue genuinely contains both
      kinds: some rules were WRITTEN AT their third occurrence (rule 36's "Credential precedence, third
      occurrence") and others ACCUMULATED occurrences afterwards.
  G3  EXPOSURE FLOOR. Rules with under 7 days of exposure are reported separately and excluded from any
      denominator, because they have not had the opportunity to recur.

------------------------------------------------------------------------------------------------------
LIMITATIONS, STATED BEFORE THE RESULT BECAUSE THEY BOUND WHAT IT CAN MEAN.

  1. **A recurrence is counted only if the analyst wrote it down.** There is no independent adjudicator,
     no second reader, and no mechanism that would surface a recurrence nobody noticed. The count is
     therefore a LOWER BOUND and the true recurrence rate is unknown and higher. Dividing it by 100 would
     be false precision dressed as a rate, which is why P1's primary is a COUNT.
  2. **n = 1 analyst, one project.** This is a case study with an exact denominator -- rare, and worth
     reporting for that reason -- not an estimate of a population parameter.
  3. **Catalogue size and calendar time are perfectly collinear**, because the catalogue only ever grows.
     "Does a larger catalogue help or hurt" is not identifiable from this artifact and is not asked.
  4. The unit is a RULE, not an experiment. A rule that recurred once in work that produced fifty
     experiments and a rule that recurred once in work that produced five are counted identically.

    python -m bsde.experiments.e343_catalogue_recurrence
"""
from __future__ import annotations

import argparse, datetime, json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))  # the catalogue and its git history live at the repo root
RESULTS = os.path.join(ROOT, "results")
CAT = "CLAUDE.md"
EXPOSURE_FLOOR_DAYS = 7

RULE_RE = re.compile(r"^(\d{1,3})\. \*\*", re.M)
OCC_RE = re.compile(r"\*\*(SECOND|THIRD|FOURTH|FIFTH|SIXTH)[^*]{0,120}?OCCURRENCE", re.I)
OCC_LOOSE = re.compile(r"(SECOND|THIRD|FOURTH|FIFTH|SIXTH)[ ,]{0,3}OCCURRENCE", re.I)
DATE_RE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)")
CITED_RE = re.compile(
    r"(cit(?:ed|es|ing) rule \d+|inside a file whose docstring cites|"
    r"by name inside the file that then failed|was cited by name)", re.I)


def sh(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True).stdout


def parse_rules(text):
    hits = [(m.start(), int(m.group(1))) for m in RULE_RE.finditer(text)]
    out = {}
    for i, (pos, num) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        out[num] = text[pos:end]
    return out, [n for _, n in hits]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(RESULTS, "e343_catalogue_recurrence.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)

    cur = open(os.path.join(REPO, CAT)).read()
    rules, order = parse_rules(cur)
    today = datetime.date.today()
    print(f"[catalogue] {len(rules)} rules parsed from {CAT}")

    # ------------------------------------------------------------------ G1(i) index integrity
    nums = sorted(rules)
    contiguous = nums == list(range(1, len(nums) + 1))
    nodup = len(order) == len(set(order))
    print(f"[G1i] numbers {min(nums)}..{max(nums)}, contiguous = {contiguous}, "
          f"no duplicates = {nodup}")

    # ------------------------------------------------------- first appearance, method A (by number)
    commits = [l.split() for l in sh("git", "log", "--reverse", "--format=%H %aI",
                                     "--", CAT).strip().splitlines()]
    print(f"[history] {len(commits)} commits touching {CAT}, "
          f"{commits[0][1][:10]} to {commits[-1][1][:10]}")
    birthA = {}
    for h, iso in commits:
        blob = sh("git", "show", f"{h}:{CAT}")
        if not blob:
            continue
        _, present = parse_rules(blob)
        for n in set(present):
            birthA.setdefault(n, iso[:10])

    # ---------------------------------------- first appearance, method B (by phrase, never the number)
    # A distinctive phrase from the rule's own body, long enough to be unique and containing no digits
    # that could be the rule number. `git log -S` reports commits that CHANGED the count of that string,
    # so its last (oldest) entry is the commit that introduced it.
    def phrase_of(body):
        txt = re.sub(r"\s+", " ", body)
        txt = txt.split("**", 2)[-1] if txt.count("**") >= 2 else txt
        words = [w for w in txt.split() if w.isalpha() and len(w) > 3]
        for i in range(len(words) - 7):
            cand = " ".join(words[i:i + 8])
            if cur.count(cand) == 1:
                return cand
        return None

    birthB, phrase_used = {}, {}
    for n, body in rules.items():
        ph = phrase_of(body)
        if not ph:
            continue
        phrase_used[n] = ph
        out = sh("git", "log", "-S", ph, "--format=%aI", "--", CAT).strip().splitlines()
        if out:
            birthB[n] = out[-1][:10]

    agree = [n for n in rules if n in birthB and birthA.get(n) == birthB[n]]
    disagree = {n: (birthA.get(n), birthB.get(n)) for n in rules
                if n in birthB and birthA.get(n) != birthB[n]}
    covered = len(birthB)
    G1 = bool(contiguous and nodup and covered >= 0.8 * len(rules) and not disagree)
    print(f"[G1ii] independent phrase-based dating covered {covered}/{len(rules)} rules; "
          f"agree {len(agree)}, DISAGREE {len(disagree)}")
    for n, (x, y) in list(disagree.items())[:10]:
        print(f"        rule {n}: by-number {x}  by-phrase {y}   phrase={phrase_used.get(n)!r}")
    print(f"[G1] -> {'PASS' if G1 else 'FAIL'}")

    # ------------------------------------------------------------------------- P1/P2 recurrence
    rec, atwrite, undated = {}, {}, {}
    for n, body in rules.items():
        born = birthA.get(n)
        if not born:
            continue
        bd = datetime.date.fromisoformat(born)
        post, at, und = [], [], []
        for m in OCC_LOOSE.finditer(body):
            seg = body[m.start():m.start() + 400]
            dm = DATE_RE.search(seg)
            word = m.group(1).upper()
            if not dm:
                und.append(word)
                continue
            d = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            (post if d > bd else at).append((word, d.isoformat()))
        if post:
            rec[n] = post
        if at:
            atwrite[n] = at
        if und:
            undated[n] = und

    print("\n" + "=" * 96)
    print("P1 -- POST-STATEMENT RECURRENCE: the failure mode occurred again after the rule existed")
    tot = 0
    for n in sorted(rec):
        born = birthA[n]
        gaps = [(w, d, (datetime.date.fromisoformat(d)
                        - datetime.date.fromisoformat(born)).days) for w, d in rec[n]]
        tot += len(gaps)
        print(f"  rule {n:>3}  written {born}  exposure {(today - datetime.date.fromisoformat(born)).days:>3}d")
        for w, d, g in gaps:
            print(f"           {w:<7} recurred {d}  {g:>3} days after the rule was written")
    print(f"\n  rules with >= 1 post-statement recurrence: {len(rec)}")
    print(f"  total recorded post-statement recurrences : {tot}")
    if rec:
        mx = max(len(v) for v in rec.values())
        print(f"  worst single rule: {max(rec, key=lambda k: len(rec[k]))} with {mx} recurrences")

    print("\n  markers dated AT OR BEFORE the rule's own writing (the rule was written AT the Nth")
    print("  occurrence, so these are NOT failures of the rule) --")
    for n in sorted(atwrite):
        print(f"    rule {n:>3} written {birthA[n]}: " +
              ", ".join(f"{w} @ {d}" for w, d in atwrite[n]))
    if undated:
        print("\n  markers with no date in range, excluded from both counts: " +
              ", ".join(f"rule {n} ({','.join(v)})" for n, v in sorted(undated.items())))

    # ------------------------------------------------------------------------------- G2
    G2 = bool(rec and atwrite)
    print(f"\n[G2] classifier exercised BOTH ways -- flagged {len(rec)} post-statement and withheld "
          f"on {len(atwrite)} at-or-before -> {'PASS' if G2 else 'FAIL'}")

    # ------------------------------------------------------------------------------- G3, exposure
    exposure = {n: (today - datetime.date.fromisoformat(birthA[n])).days
                for n in rules if n in birthA}
    young = sorted(n for n, d in exposure.items() if d < EXPOSURE_FLOOR_DAYS)
    eligible = sorted(n for n, d in exposure.items() if d >= EXPOSURE_FLOOR_DAYS)
    print(f"\n[G3] exposure: {len(eligible)} rules with >= {EXPOSURE_FLOOR_DAYS}d, "
          f"{len(young)} younger and excluded from any denominator: {young}")
    if exposure:
        ev = sorted(exposure.values())
        print(f"     exposure days: min {ev[0]}, median {ev[len(ev)//2]}, max {ev[-1]}")

    # ------------------------------------------------------------------------------- P3
    print("\n" + "=" * 96)
    print("P3 -- CITED-THEN-VIOLATED: the rule was invoked by name in the work that then broke it")
    cited = {}
    for n, body in rules.items():
        m = CITED_RE.search(body)
        if m:
            seg = re.sub(r"\s+", " ", body[max(0, m.start() - 160):m.start() + 200])
            cited[n] = seg.strip()
    for n in sorted(cited):
        print(f"  rule {n:>3}: ...{cited[n][:230]}...")
    print(f"\n  rules recording a cited-then-violated instance: {len(cited)}")

    # ------------------------------------------------------------------------------- verdict
    print("\n" + "=" * 96)
    if not (G1 and G2):
        verdict = "NOT INTERPRETABLE"
        why = ("gate failed: " + ", ".join(g for g, ok in (("G1", G1), ("G2", G2)) if not ok)
               + " -- rule 31: the downstream verdict is absent, not negative.")
    elif tot == 0:
        verdict = "THE CATALOGUE HELD"
        why = ("no rule records its failure mode recurring after it was written. The premise that "
               "documenting a failure mode prevents it is not contradicted by this artifact, and the "
               "question becomes what makes it work.")
    else:
        verdict = "DOCUMENTATION DID NOT PREVENT RECURRENCE"
        why = (f"{len(rec)} of {len(eligible)} rules with at least {EXPOSURE_FLOOR_DAYS} days of "
               f"exposure record the failure mode recurring AFTER the rule was written, "
               f"{tot} recorded recurrences in total, in the most favourable setting available -- one "
               f"analyst, a self-written catalogue, a standing instruction to read it, and rules cited "
               f"by number in the work. {len(cited)} rules record being invoked BY NAME inside the very "
               f"work that then violated them. Lower bound (LIMITATION 1): only recurrences the analyst "
               f"noticed and wrote down are counted.")
    print(f"VERDICT: {verdict}\n  {why}")
    print("\nLIMITATION 1, repeated next to the number so it cannot be quoted without it: this is a "
          "LOWER BOUND. A recurrence nobody noticed is invisible to this measurement.")

    out = {"verdict": verdict, "why": why,
           "n_rules": len(rules), "n_commits": len(commits),
           "history_span": [commits[0][1][:10], commits[-1][1][:10]],
           "gates": {"G1": G1, "G2": G2, "contiguous": contiguous, "no_duplicates": nodup,
                     "phrase_dated": covered, "date_agree": len(agree),
                     "date_disagree": disagree},
           "P1": {"rules_with_recurrence": {str(k): v for k, v in rec.items()},
                  "n_rules_recurred": len(rec), "n_recurrences": tot},
           "P1_at_writing": {str(k): v for k, v in atwrite.items()},
           "P1_undated": {str(k): v for k, v in undated.items()},
           "P2": {"exposure_days": {str(k): v for k, v in exposure.items()},
                  "eligible": eligible, "excluded_young": young},
           "P3": {"n_cited_then_violated": len(cited),
                  "rules": {str(k): v for k, v in cited.items()}},
           "birth_by_number": {str(k): v for k, v in birthA.items()},
           "birth_by_phrase": {str(k): v for k, v in birthB.items()}}
    if a.smoke:
        print("\n[SMOKE] no artifact written")
        return 0
    json.dump(out, open(a.out, "w"), indent=1, default=str)
    print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
