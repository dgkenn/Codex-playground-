"""The append-only registration ledger: how many designs were tried, and what became of each.

WHY THIS EXISTS. `verifier/multiplicity.py` corrects for looking at 18 candidates inside one experiment.
**A loop of experiments creates multiplicity ACROSS experiments, and nothing counted it.** At the time this
file was written the repository held 32 registered experiment files and 10 outcome JSONs, and there was no
way to state that ratio without counting by hand — which means no report could state its own denominator.

The programme's constraints require reporting the size of the search space. A design that was registered,
run, and abandoned is part of that space. **A ledger that only recorded successes would be the exact
instrument the constraints exist to prevent**, so this one records registrations at the moment they are
made, before their data exists, and outcomes are attached afterwards to a row that already exists.

WHAT MAKES A ROW TRUSTWORTHY. Each row carries `registered_sha` — the git commit that first added the
experiment file. Because registrations are committed BEFORE the extraction they consume finishes, the
commit order is checkable evidence that the predictions preceded the data, and it is evidence a reader can
verify without trusting this file. `outcome` is written later and may change; `registered_sha`, `primary`
and `gates` may not.

WHAT THIS DOES NOT DO. It does not adjust any p-value. Experiment-level multiplicity here is not a set of
exchangeable tests — the designs differ in question, deposit and estimator — so a formal correction would
be false precision. **It makes the denominator visible and leaves the judgement to a reader**, which is the
honest version of what can be done with a count like this.

    python bsde/governance/registry_ledger.py report          # the denominator and the disposition table
    python bsde/governance/registry_ledger.py verify          # every ledger row has a real file and SHA
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "REGISTRATION_LEDGER.jsonl")
EXPERIMENTS = os.path.abspath(os.path.join(HERE, "..", "src", "bsde", "experiments"))

FIELDS = ("id", "challenge", "question", "deposit", "primary", "gates", "placebo",
          "registered_sha", "registered_date", "file", "outcome", "outcome_detail",
          "successor_of", "instrument_changed", "incumbent")

OUTCOMES = ("registered", "gate_failed", "absent", "blocked", "withdrawn", "negative",
            "positive", "closed")
"""Deliberately more granular than pass/fail, because the distinctions carry the meaning:

    gate_failed   a machinery gate refused; nothing about any candidate was computed
    absent        a downstream verdict could not be reached (rule 31) — NOT a negative
    blocked       registered but never run, because a prerequisite was shown to be broken
    withdrawn     a primary cleared its interval and was then withdrawn by its own placebo
    negative      fully executed, every gate passed, and the answer was no
    positive      fully executed and the primary survived every gate
    closed        abandoned by a standing pre-commitment (e.g. a one-attempt rule)
"""


def _load() -> List[dict]:
    if not os.path.exists(LEDGER):
        return []
    out = []
    with open(LEDGER) as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def _git(*args) -> str:
    """Always run from the REPO ROOT, never from this file's directory.

    The first version used `cwd=HERE`, i.e. `bsde/governance/`. Git resolves a relative pathspec against the
    working directory, so every `bsde/src/...` path matched nothing and every registering SHA came back
    empty. `verify` caught it on its first run, which is what `verify` is for.
    """
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:                                                     # noqa: BLE001
        return ""


def register(exp_id: str, challenge: str, question: str, deposit: str, primary: str,
             gates: List[str], placebo: Optional[str], file: str,
             successor_of: Optional[str] = None,
             instrument_changed: Optional[str] = None,
             incumbent: Optional[str] = None) -> dict:
    """Append a registration. Refuses to overwrite an existing id — the ledger is append-only.

    `incumbent` names the thing the result has to beat; rule 45 records that a marker reported
    without one is not a result, and an empty field is a defect rather than an omission.

    `successor_of` and `instrument_changed` exist to make the loop's one dangerous step auditable. A failed
    experiment may spawn a successor ONLY by changing the instrument, never the threshold, cohort or horizon
    that just failed; a successor row that cannot name what instrument it changed is the shape of a
    goalpost being moved, and is visible here as an empty field.
    """
    rows = _load()
    if any(r["id"] == exp_id for r in rows):
        raise ValueError(f"{exp_id} is already in the ledger; the ledger is append-only")
    sha = _git("log", "--diff-filter=A", "--format=%H", "--", file).split("\n")[-1]
    date = _git("log", "--diff-filter=A", "--format=%ad", "--date=short", "--", file).split("\n")[-1]
    row = {"id": exp_id, "challenge": challenge, "question": question, "deposit": deposit,
           "primary": primary, "gates": gates, "placebo": placebo,
           "registered_sha": sha, "registered_date": date, "file": file,
           "outcome": "registered", "outcome_detail": "",
           "successor_of": successor_of, "instrument_changed": instrument_changed,
           "incumbent": incumbent}
    with open(LEDGER, "a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def set_outcome(exp_id: str, outcome: str, detail: str = "") -> None:
    """Attach an outcome to a row that already exists. The row is rewritten in place; nothing else may be.

    Rewriting is confined to `outcome` and `outcome_detail` on purpose. If a registration's primary or gates
    could be edited after the fact the ledger would be worthless, so this function does not offer it.
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}; known: {OUTCOMES}")
    rows = _load()
    hit = [r for r in rows if r["id"] == exp_id]
    if not hit:
        raise ValueError(f"{exp_id} is not in the ledger — register it before recording an outcome")
    for r in rows:
        if r["id"] == exp_id:
            r["outcome"], r["outcome_detail"] = outcome, detail
    with open(LEDGER, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def report() -> int:
    rows = _load()
    if not rows:
        print("the ledger is empty")
        return 1
    from collections import Counter
    print(f"REGISTRATION LEDGER — {len(rows)} designs registered\n")
    print(f"   {'id':6s} {'chal':5s} {'outcome':12s} {'primary':20s} {'deposit':22s} successor-of")
    for r in sorted(rows, key=lambda z: z["id"]):
        print(f"   {r['id']:6s} {str(r.get('challenge', '')):5s} {r['outcome']:12s} "
              f"{str(r.get('primary', ''))[:20]:20s} {str(r.get('deposit', ''))[:22]:22s} "
              f"{r.get('successor_of') or ''}")
    c = Counter(r["outcome"] for r in rows)
    print("\n   disposition:")
    for k in OUTCOMES:
        if c.get(k):
            print(f"      {k:12s} {c[k]:3d}")
    reported = c.get("positive", 0) + c.get("negative", 0)
    print(f"\n   DENOMINATOR FOR ANY CLAIM FROM THIS PROGRAMME: {len(rows)} designs registered, "
          f"{reported} reached a reportable verdict")
    print("   (the rest were refused by their own gates, blocked, withdrawn, or closed by a")
    print("    pre-commitment — every one of those is part of the search space and is counted here)")
    per_ch = Counter(r.get("challenge", "?") for r in rows)
    print("\n   by challenge: " + "  ".join(f"{k}={v}" for k, v in sorted(per_ch.items())))
    return 0


def verify() -> int:
    """Every row must name a file that exists and a SHA that git knows. Cheap, and it catches drift."""
    rows = _load()
    bad = 0
    for r in rows:
        path = os.path.join(ROOT, r.get("file", ""))
        if not os.path.exists(path):
            print(f"   {r['id']}: file missing -> {r.get('file')}")
            bad += 1
        sha = r.get("registered_sha", "")
        if not sha or not _git("rev-parse", "--quiet", "--verify", f"{sha}^{{commit}}"):
            print(f"   {r['id']}: registering SHA missing or unknown to git -> {sha!r}")
            bad += 1
    print(f"   {len(rows)} rows checked, {bad} problems")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "report"
    if cmd == "report":
        return report()
    if cmd == "verify":
        return verify()
    print(__doc__.strip().splitlines()[-2])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
