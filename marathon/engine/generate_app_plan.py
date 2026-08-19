#!/usr/bin/env python3
"""Regenerate ``app_plan.generated.json``, which the phone build inlines.

This existed only as a file. The JSON was produced once, by hand, and then read by
``tools/build-coach.mjs`` for every subsequent build — so a change to the plan, the ramp protocol or
the pace derivation reached the engine and its tests and stopped there, while the phone kept
shipping whatever was generated the first time. A generated artefact with no generator is a copy
that drifts, and this one drifts silently.

    python engine/generate_app_plan.py            # rewrite the JSON
    python engine/generate_app_plan.py --check    # exit 1 if it is out of date

The profile is the estimated one: age and resting heart rate are not measured yet, and the plan has
to exist before they are. Both are labelled as estimates all the way through to the app, which shows
them as placeholders until the athlete replaces them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from marathon_engine.app_plan import build_app_plan          # noqa: E402
from marathon_engine.cli import _estimated_profile           # noqa: E402

#: The placeholder profile the shipped plan is built from. Change these and regenerate; the app
#: shows both as unconfirmed until the athlete enters their own, because every zone boundary and
#: every ramp stage depends on them.
DEFAULT_AGE = 30.0
DEFAULT_HR_REST = 55.0

OUT = Path(__file__).resolve().parent / "app_plan.generated.json"


def build(age: float = DEFAULT_AGE, hr_rest: float = DEFAULT_HR_REST) -> str:
    plan = build_app_plan(_estimated_profile(age=age, hr_rest=hr_rest))
    # Sorted and compact: the file is inlined into a 170 kB page, and a stable key order means a
    # regeneration that changed nothing produces a byte-identical file rather than a phantom diff.
    return json.dumps(plan, sort_keys=True, separators=(",", ":"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the committed file is out of date")
    ap.add_argument("--age", type=float, default=DEFAULT_AGE)
    ap.add_argument("--hr-rest", type=float, default=DEFAULT_HR_REST)
    args = ap.parse_args()

    fresh = build(args.age, args.hr_rest)
    if args.check:
        current = OUT.read_text().strip() if OUT.exists() else ""
        if current != fresh:
            print(f"{OUT.name} is out of date -- run: python engine/generate_app_plan.py",
                  file=sys.stderr)
            return 1
        print(f"{OUT.name} is up to date ({len(fresh) / 1024:.0f} kB)")
        return 0

    OUT.write_text(fresh)
    plan = json.loads(fresh)
    weeks = sum(len(p["weeks"]) for p in plan["phases"])
    print(f"wrote {OUT} ({len(fresh) / 1024:.0f} kB): "
          f"{len(plan['phases'])} phases, {weeks} weeks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
