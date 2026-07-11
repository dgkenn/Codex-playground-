"""verdict_ledger.py -- append-only registry of every strategy arm ever tested (the multiple-testing
denominator: how many arms did we actually try per family, before quoting a single winner's t-stat).

Each row in verdicts.jsonl is one verdict event:
    {"name": str, "added": "YYYY-MM-DD"|null, "source_evidence": str, "forward_verdict": str|null,
     "status": "baseline"|"winner"|"pruned"|"watch"|"testing"}

APPEND-ONLY: a name can have MULTIPLE rows over time (its verdict evolves -- e.g. "testing" ->
"winner"/"pruned" once forward data clears the bar); `--check` prints the full history in order, the
LAST row is the current verdict. Nothing here ever deletes or rewrites an existing line.

Seeding (--seed): strategies.py's REGISTRY is the source of truth for the 34 known arms. Each note is
parsed programmatically:
    - a "32d: ..." fragment              -> forward_verdict = that fragment, added = the 32-day
                                             forward window's start (2026-06-10; the note's own dated
                                             window) since the arm was live for the whole review.
    - a "PRUNED ..." fragment (no 32d:)  -> forward_verdict = that fragment; these predate the 32-day
                                             window (added date not recoverable -- shallow git history
                                             here has exactly one commit; left null rather than guessed).
    - neither (fresh ensemble/ablation candidates with no verdict yet, or baseline)
                                          -> forward_verdict = null, status inferred from enabled+note.
`--seed` is idempotent: it only appends a row for a REGISTRY name that has NO existing row yet, so
re-running it (e.g. every CI run) never duplicates the seed.

CLI:
    python verdict_ledger.py --seed            # idempotent: add rows for any un-seeded REGISTRY arms
    python verdict_ledger.py --check as_markout # print that arm's full verdict history
    python verdict_ledger.py --stats            # family-wise tested/won/lost/watch/testing counts
"""
from __future__ import annotations

import argparse
import json
import os

LEDGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verdicts.jsonl")
WINDOW_START = "2026-06-10"   # the 32-day forward review's start date (strategies.py REGISTRY comment)


def load_ledger(path: str = LEDGER_PATH) -> list[dict]:
    """All rows, in file (== append) order. Tolerant of a missing file or corrupt lines."""
    rows: list[dict] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
    return rows


def latest_by_name(rows: list[dict]) -> dict[str, dict]:
    """Current verdict per name = the LAST row for that name (append order)."""
    out: dict[str, dict] = {}
    for r in rows:
        n = r.get("name")
        if n:
            out[n] = r
    return out


def _family(strat) -> str:
    """Group arms by the dimension the note text actually argues about (gate family is the natural
    multiple-testing bucket -- e.g. 'REFUTES the stricter-gates-win hypothesis' only makes sense
    counted within the gate family)."""
    if strat.name == "baseline":
        return "baseline"
    if strat.gate:
        return f"gate:{strat.gate}"
    if strat.size_mode != "flat":
        return f"size:{strat.size_mode}"
    return "skew/cap (no gate)"


def _parse_note(note: str) -> str | None:
    """Programmatic extraction of the forward_verdict fragment from a REGISTRY note."""
    if "32d:" in note:
        return "32d: " + note.split("32d:", 1)[1].strip()
    if "PRUNED" in note:
        return note[note.index("PRUNED"):].strip()
    return None


def _infer_status(strat, forward_verdict: str | None) -> str:
    note = strat.note.lower()
    if strat.name == "baseline":
        return "baseline"
    if not strat.enabled:
        return "pruned"
    if "kept enabled" in note and "watch" in note:
        return "watch"
    # Only trust "winner" wording INSIDE an actual 32d forward-verdict fragment -- ablation/candidate
    # notes (as_markout, as_cap100, ...) mention "winner" in passing (referring to av_stoikov/mo_size)
    # while having no verdict of their own yet; a bare substring check on the whole note misclassifies
    # them. Requiring it inside a "32d:"-prefixed forward_verdict avoids that false positive.
    if forward_verdict and forward_verdict.startswith("32d:") and "winner" in forward_verdict.lower():
        return "winner"
    return "testing"        # enabled, no forward verdict yet (fresh ensemble/ablation candidate)


def _infer_added(strat, forward_verdict: str | None) -> str | None:
    if strat.name == "baseline":
        return WINDOW_START
    if forward_verdict and forward_verdict.startswith("32d:"):
        return WINDOW_START          # live for the whole 32-day review
    if forward_verdict and forward_verdict.startswith("PRUNED"):
        return None                  # predates the 32-day window; not recoverable from shallow history
    return None                      # fresh candidate; exact add date not tracked pre-ledger


def seed_rows_from_registry() -> list[dict]:
    """Build the full seed row list from strategies.py's REGISTRY (does not touch the ledger file)."""
    import strategies
    rows = []
    for s in strategies.REGISTRY:
        fv = _parse_note(s.note)
        rows.append({
            "name": s.name,
            "added": _infer_added(s, fv),
            "source_evidence": s.note,
            "forward_verdict": fv,
            "status": _infer_status(s, fv),
        })
    return rows


def seed(path: str = LEDGER_PATH) -> int:
    """Idempotently append a row for every REGISTRY arm not already present. Returns rows added."""
    existing = {r.get("name") for r in load_ledger(path)}
    to_add = [r for r in seed_rows_from_registry() if r["name"] not in existing]
    if to_add:
        with open(path, "a") as fh:
            for r in to_add:
                fh.write(json.dumps(r) + "\n")
    return len(to_add)


def check(name: str, path: str = LEDGER_PATH) -> list[dict]:
    return [r for r in load_ledger(path) if r.get("name") == name]


def compute_stats(path: str = LEDGER_PATH) -> dict[str, dict[str, int]]:
    """Family -> {tested, winner, pruned, watch, testing, baseline} counts, from the CURRENT verdict
    (latest row) per name -- the multiple-testing denominator per family."""
    rows = load_ledger(path)
    current = latest_by_name(rows)
    try:
        import strategies
        strat_by_name = {s.name: s for s in strategies.REGISTRY}
    except Exception:
        strat_by_name = {}

    fams: dict[str, dict[str, int]] = {}
    for name, rec in current.items():
        strat = strat_by_name.get(name)
        fam = _family(strat) if strat is not None else "unknown"
        bucket = fams.setdefault(fam, {"tested": 0, "winner": 0, "pruned": 0, "watch": 0,
                                        "testing": 0, "baseline": 0})
        bucket["tested"] += 1
        status = rec.get("status", "testing")
        if status in bucket:
            bucket[status] += 1
    return fams


def _print_stats(fams: dict[str, dict[str, int]]) -> None:
    print(f"{'family':>22} {'tested':>7} {'winner':>7} {'pruned':>7} {'watch':>6} {'testing':>8}")
    for fam in sorted(fams, key=lambda f: -fams[f]["tested"]):
        b = fams[fam]
        print(f"{fam:>22} {b['tested']:>7} {b['winner']:>7} {b['pruned']:>7} {b['watch']:>6} {b['testing']:>8}")
    total_tested = sum(b["tested"] for b in fams.values())
    total_won = sum(b["winner"] for b in fams.values())
    print(f"\n{total_won}/{total_tested} arms tested are current winners (excl. baseline) -- "
          f"the honest multiple-testing denominator.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", action="store_true", help="idempotently seed from strategies.py REGISTRY")
    ap.add_argument("--check", metavar="NAME", help="print an arm's full verdict history")
    ap.add_argument("--stats", action="store_true", help="family-wise tested/won/lost/watch/testing counts")
    args = ap.parse_args()

    if args.seed:
        n = seed()
        print(f"verdict_ledger: seeded {n} new row(s) into {LEDGER_PATH}")
        return
    if args.check:
        hist = check(args.check)
        if not hist:
            print(f"{args.check}: no ledger entries")
            return
        print(f"=== {args.check} ({len(hist)} verdict event(s)) ===")
        for r in hist:
            print(f"  added={r.get('added')} status={r.get('status')} "
                  f"forward_verdict={r.get('forward_verdict')!r}")
            print(f"    source: {r.get('source_evidence')}")
        return
    if args.stats:
        _print_stats(compute_stats())
        return
    ap.print_help()


if __name__ == "__main__":
    main()
