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

#: The athlete's profile, as far as it is actually known.
#:
#: Age is given. Resting heart rate is the value the athlete entered in the app, which is a stated
#: number rather than one measured lying down on waking -- so it is his and not a placeholder, but it
#: is not laboratory-grade either. It is the anchor of the whole zone model: 55 (Polar's untouched
#: factory default, which is what this said before) against 67 moves every zone edge by four to five
#: beats, which is the difference between "easy" and "steady" at the top of Z2.
#:
#: The one piece of evidence available says the higher number is the likelier: thirty minutes sitting
#: still after the 22 August run, heart rate fell to 73 and stopped. Post-exercise sitting is above
#: true rest, so 67 is plausible and 55 is not.
DEFAULT_AGE = 30.0
DEFAULT_HR_REST = 67.0

#: The longest continuous run observed, in minutes, from the baseline session of 2026-08-05:
#: 24:12 total, 1.81 mi, four run blocks of 2.9 / 4.7 / 3.6 / 1.5 minutes at 9:55-10:30 per mile,
#: with heart rate reaching 155 within three minutes and peaking at 180.
#:
#: Recorded here rather than inferred, because it changes the plan: the run-walk ladder starts one
#: rung below demonstrated capacity instead of at the bottom. What it deliberately does NOT change
#: is the prescribed intensity — the same session showed heart rate reaching Z5 inside four minutes
#: of running, which is the definition of an athlete who can run and cannot yet run easy.
DEMONSTRATED_RUN_MIN = 4.7

#: The fastest he was OBSERVED running with heart rate still inside the easy ceiling, km/h.
#:
#: From the 22 August recording, the first with heart rate and speed on one clock. Pairing each
#: heart rate with the speed 25 seconds earlier -- heart rate lags, and without the lag every number
#: is attributed to the wrong speed -- gives:
#:
#:     5.5 km/h   121 bpm     45% HRR
#:     6.5 km/h   135 bpm     56% HRR
#:     7.5 km/h   136 bpm     57% HRR
#:     8.0 km/h   138 bpm     59% HRR
#:
#: and from the 5 August baseline, running blocks at 9.7 km/h took him to 155 within three minutes
#: and 180 at peak. So the ceiling sits between 8 and 9.7, and 8.0 is the fastest speed with evidence
#: under it rather than around it.
#:
#: Deliberately the low end of the plausible range. The cost of prescribing too slow is a slightly
#: easy session; the cost of prescribing too fast is every run block in Z4, which is the mistake he
#: is already making unaided. The ramp test replaces this with a real fit across six speeds.
OBSERVED_EASY_RUN_KMH = 8.0

OUT = Path(__file__).resolve().parent / "app_plan.generated.json"


def build(age: float = DEFAULT_AGE, hr_rest: float = DEFAULT_HR_REST,
          demonstrated_run_min: float = DEMONSTRATED_RUN_MIN,
          observed_easy_run_kmh: float = OBSERVED_EASY_RUN_KMH) -> str:
    profile = _estimated_profile(age=age, hr_rest=hr_rest)
    profile.demonstrated_run_min = demonstrated_run_min
    profile.observed_easy_run_kmh = observed_easy_run_kmh
    plan = build_app_plan(profile)
    # Sorted and compact: the file is inlined into a 170 kB page, and a stable key order means a
    # regeneration that changed nothing produces a byte-identical file rather than a phantom diff.
    return json.dumps(plan, sort_keys=True, separators=(",", ":"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the committed file is out of date")
    ap.add_argument("--age", type=float, default=DEFAULT_AGE)
    ap.add_argument("--hr-rest", type=float, default=DEFAULT_HR_REST)
    ap.add_argument("--demonstrated-run-min", type=float, default=DEMONSTRATED_RUN_MIN,
                    help="longest continuous run actually observed, in minutes")
    ap.add_argument("--observed-easy-run-kmh", type=float, default=OBSERVED_EASY_RUN_KMH,
                    help="fastest observed running speed with heart rate inside the easy ceiling")
    args = ap.parse_args()

    fresh = build(args.age, args.hr_rest, args.demonstrated_run_min, args.observed_easy_run_kmh)
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
