"""Turn the standalone sweep experiments into report `Evidence`, so mandatory report rows stop lying.

THE GAP THIS CLOSES. `report.py` declares ten mandatory `REPORT_ITEMS`, two of which — `preprocessing_
sensitivity` and `reduced_channel` — were populated by **nothing**. Every report printed `NOT_RUN` against
them. Meanwhile E09 had computed 72 preprocessing variants, E12 had registered 108 more, and E06 had swept
every channel. **The work existed and never reached the report**, which is the same failure as a check that
was never run, because a reader of the report cannot tell the two apart.

Brief 03's constraint 5 lists `preprocessing_sensitivity` among the required report items. A required item
that no code can satisfy is a constraint the project cannot meet by construction, and that is worth more than
the wiring itself: **a mandatory row nothing populates is a promise the report format makes and the code
cannot keep.**

WHY THIS IS A SEPARATE MODULE AND NOT A LAYER. These sweeps are expensive, per-project, and run offline over
raw recordings — they are not something `verify()` can compute from a `Cohort` of scalars. So they are read
from the committed result JSON and converted to Evidence, and the conversion is deliberately strict:

  * a sweep whose JSON is absent yields NOT_RUN, never a pass;
  * a sweep that did not cover the candidate being verified yields NOT_RUN naming the candidate, so
    "the sweep ran" is never mistaken for "the sweep ran on THIS candidate";
  * the evidence carries the sweep's own numbers, so a reader can disagree with the interpretation.

**A PASS HERE IS NOT AVAILABLE, BY DESIGN.** Preprocessing sensitivity is reported as NOT_APPLICABLE with the
spread attached, or FAIL when the spread crosses the null — because there is no defensible threshold at which
a sensitivity sweep "passes", and inventing one would convert a descriptive number into a green light. The
one thing a sweep CAN establish is failure: a candidate whose sign flips across defensible analysis choices
has been refuted by its own analyst degrees of freedom.
"""
from __future__ import annotations

import json
import os
from typing import Sequence

from bsde.verifier.report import Evidence, FAIL, NOT_APPLICABLE, NOT_RUN

SIGN_FLIP_FRACTION = 0.10
"""If at least this fraction of analysis variants land on EACH side of 0.5, the candidate's DIRECTION is a
choice the analyst made rather than a property of the data. E09 registered exactly this threshold before
running, and it is reused here rather than re-invented."""


def _load(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return None


def preprocessing_evidence(candidate_name: str, results_dir: str) -> Evidence:
    """`preprocessing_sensitivity` from E09's sweep of the aperiodic exponent.

    E09 swept fit range, estimator and Welch window — 72 defensible variants — for the exponent family only.
    Any other candidate correctly gets NOT_RUN naming itself, because a sweep of a different measure says
    nothing about this one.
    """
    covered = {"whole_head_exponent", "exponent_low", "exponent_high", "uce_v1"}
    d = _load(os.path.join(results_dir, "e09_preprocessing_sensitivity.json"))
    if d is None:
        return Evidence("preprocessing_sensitivity", "adversarial", NOT_RUN,
                        "no preprocessing sweep has been run and committed. Brief 03 lists this among the "
                        "required report items, so this row is a promise the format makes that the project "
                        "cannot yet keep.", item="preprocessing_sensitivity")
    if candidate_name not in covered:
        return Evidence("preprocessing_sensitivity", "adversarial", NOT_RUN,
                        f"E09 swept the aperiodic exponent family ({sorted(covered)}); {candidate_name} was "
                        "not among them. A sweep of a different measure is not evidence about this one.",
                        values={"swept": sorted(covered), "n_variants": d.get("n_variants")},
                        item="preprocessing_sensitivity")
    ex = d.get("exponent", {})
    above = float(ex.get("frac_above_half", float("nan")))
    below = float(ex.get("frac_below_half", float("nan")))
    flips = (above >= SIGN_FLIP_FRACTION and below >= SIGN_FLIP_FRACTION)
    q1, q3 = (ex.get("iqr") or [float("nan"), float("nan")])[:2]
    return Evidence(
        "preprocessing_sensitivity", "adversarial", FAIL if flips else NOT_APPLICABLE,
        (f"across {d.get('n_variants')} defensible analysis variants (fit range, estimator, Welch window) "
         f"the signed AUC has median {ex.get('median_auc')}, IQR [{q1}, {q3}], range "
         f"{ex.get('min')}-{ex.get('max')}. " +
         (f"{above:.0%} of variants land above 0.5 and {below:.0%} below: the candidate's DIRECTION is an "
          "analysis choice, not a property of the data."
          if flips else
          f"{max(above, below):.0%} of variants agree on direction, so the SIGN is stable across the sweep "
          "even where the magnitude is not. Reported rather than passed: there is no defensible threshold "
          "at which a sensitivity sweep constitutes a pass.")),
        values={"n_variants": d.get("n_variants"), **ex}, item="preprocessing_sensitivity",
        fatal=flips)


def reduced_channel_evidence(candidate_name: str, results_dir: str) -> Evidence:
    """`reduced_channel` from E06's per-channel sweep — how much is lost going from a full montage to one."""
    d = _load(os.path.join(results_dir, "e06_channel_sweep.json"))
    if d is None:
        return Evidence("reduced_channel", "adversarial", NOT_RUN,
                        "no channel sweep has been run and committed.", item="reduced_channel")
    summary = (d.get("summary") or {}).get(candidate_name)
    if summary is None:
        return Evidence("reduced_channel", "adversarial", NOT_RUN,
                        f"E06's channel sweep covered {sorted((d.get('summary') or {}))}; "
                        f"{candidate_name} was not among them.",
                        values={"swept": sorted((d.get("summary") or {}))}, item="reduced_channel")
    return Evidence(
        "reduced_channel", "adversarial", NOT_APPLICABLE,
        (f"full montage {summary.get('mono_all')}, 10-20 subset {summary.get('mono_ten_twenty')}, "
         f"median single channel {summary.get('mono_single_median')} "
         f"(worst {summary.get('mono_single_min')}, best {summary.get('mono_single_max')}). "
         "Reported, not thresholded: how much degradation is acceptable is a product decision, and the "
         "WORST single channel matters more than the median if the deployed device cannot choose."),
        values=summary, item="reduced_channel")


def sweep_evidence(candidate_name: str, results_dir: str) -> Sequence[Evidence]:
    """Both sweep-derived report items, ready to pass to `verify(extra_evidence=...)`."""
    return (preprocessing_evidence(candidate_name, results_dir),
            reduced_channel_evidence(candidate_name, results_dir))
