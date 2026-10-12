#!/usr/bin/env python3
"""Feature extraction over OpenNeuro ds005385 (Dortmund Vital Study) — the open adult age/sex cohort.

PRE-REGISTRATION. Written and committed BEFORE any feature value exists. This script produces the feature
table; the two experiments that consume it (E44, E45) are registered here so the analysis cannot be chosen
after seeing the numbers.

WHY THIS DATASET, AND WHY NOW. `bsde/docs/EXISTING_NORMATIVE_MODELS.md` established that no existing
normative EEG database models an aperiodic measure, so the reference has to be built rather than imported.
Two numbers gate that build and neither has been measured on our own estimator:

  (1) how much eye state moves the exponent -- PMID 42395346 reports Cohen's d = -0.761, which would make it
      the largest uncontrolled term in a HEEDB-derived reference after vigilance, and HEEDB does not record
      eye state;
  (2) how stable the exponent is across years -- the same paper reports ICC = 0.668 at five years, which
      caps any trait correlation at sqrt(0.668) ~ 0.82 and therefore bounds Challenge B.

ds005385 answers both directly and needs no credentials. Verified through the OpenNeuro GraphQL API
(snapshot 1.0.3): 608 subjects, age 20-70, 376 F / 232 M, two sessions about five years apart. Verified
through the public S3 mirror: each subject-session has FOUR 184 s continuous resting blocks --
`task-EyesOpen` and `task-EyesClosed`, each recorded `acq-pre` and `acq-post` a two-hour neurocognitive
battery. 64 EEG channels, 1000 Hz, FCz reference, DC-250 Hz, 50 Hz line (BrainAmp DC / actiCAP 64).

  IMPORTANT: `task-EyesOpen` and `task-EyesClosed` are SEPARATE FILES, one condition each, confirmed by
  reading `events.tsv` (a single `boundary` marker at onset 1 and nothing else). The EO/EC contrast is
  therefore between files, not within one. Getting this backwards would invert the sign of E44's primary,
  which is exactly the class of error the error catalogue's rule 37 keeps re-teaching, so it was checked
  against the raw sidecar rather than inferred from the task label.

---------------------------------------------------------------------------------------------------------
E44 -- HOW FAR DOES EYE STATE MOVE THE MEASURES WE INTEND TO PUT ON A NORMATIVE SCALE?
---------------------------------------------------------------------------------------------------------
PRIMARY. Within-subject paired difference, eyes-closed minus eyes-open, at `acq-pre` in `ses-1`, for each
of `exponent_low` (1-20 Hz) and `lempel_ziv` -- the two measures E43's band decomposition selected as more
EMG-robust than BIS. Reported as Cohen's d_z with a subject-level bootstrap CI.

PREDICTION, stated before the run. Both intervals exclude zero. Direction is NOT predicted for
`exponent_low`: PMID 42395346 reports the exponent RISES with eyes open (d = -0.761 on their sign
convention) which is the opposite of the naive "eyes closed = drowsier = steeper" intuition, and the
project has been burned four times by verdict rules that did not enumerate the wrong-direction case. The
registered question is MAGNITUDE, and the decision rule is about magnitude only.

DECISION RULE, written before the run and deliberately two-sided.
  * |d_z| >= 0.5 for either measure  -> eye state is a FIRST-ORDER term. It must be resolved in-signal and
    frozen into the reference alongside the wake detector, and `NORMAL_REFERENCE_COVARIATES.md` is correct
    to have promoted it out of "known unknowns".
  * |d_z| < 0.2 for both             -> the promotion was an over-reaction driven by one citation on one
    cohort, and it should be reverted in writing, not quietly dropped.
  * anything between                 -> report the number, change nothing, and say it is between.
The middle branch exists so that the rule cannot be satisfied by whatever comes out.

A COST OF THE E43 SWITCH, FOUND IN THE SMOKE RUN AND REGISTERED BEFORE ANY ANALYSIS RUN. On the first
subject, `exponent_low` read 0.265 eyes-closed against 1.773 eyes-open, while `rel_alpha` went 0.276 ->
0.054 -- the Berger effect, which also confirms the task labels are the right way round. A 1.5-unit swing
in an aperiodic slope is not credible as aperiodic: **the alpha peak occupies a much larger share of a
1-20 Hz fit window than of a 1-45 Hz one, so the sub-band E43 selected for EMG-robustness is MORE
oscillation-contaminated than the broadband fit it replaced.** That is a genuine cost of the E43 switch and
it was not visible in E43's own design, which never varied eye state.

Both an OLS and a peak-suppressed (`mode="loglog_robust"`, the project's existing iterative
positive-residual trim) fit are therefore emitted for the 1-20 Hz and 1-45 Hz bands. E44's primary is
reported on BOTH, and the pair is what makes it interpretable: if the OLS contrast is large and the robust
contrast is small, the effect was alpha and not the aperiodic slope. **Neither column replaces the other,
and the OLS columns stay the ones comparable to E43.**

INCUMBENT (rule 45). The comparator is the broadband `whole_head_exponent`, which is the measure this
project would have used before E43. If eye state moves the broadband exponent MORE than `exponent_low`,
that is a second, independent reason to prefer the sub-band fit, and it is a reason that has nothing to do
with EMG. If it moves it LESS, that is a cost of the E43 switch and must be reported as one.

PLACEBO (rules 34, 48). The `acq-pre` vs `acq-post` contrast within the SAME eye state. Both conditions are
resting EEG from the same subject, session and montage, separated by a two-hour cognitive battery -- so a
real EO/EC effect should exceed it. The placebo is a COMPARISON against the primary, never an absolute
threshold, and if the primary's interval includes zero the placebo branch must print NOT INFORMATIVE
rather than PASSED.

---------------------------------------------------------------------------------------------------------
E45 -- WHAT IS THE FIVE-YEAR STABILITY OF EACH MEASURE ON OUR OWN ESTIMATOR?
---------------------------------------------------------------------------------------------------------
PRIMARY. ICC(2,1) between `ses-1` and `ses-2`, matched on task and acq, for `exponent_low`, `lempel_ziv`,
`whole_head_exponent` and `lrtc_alpha` (E42's refined Challenge B marker, which has never had a reliability
estimate of any kind).

WHY IT MATTERS AND WHAT IT CANNOT SHOW. E38 measured a LABEL's reliability and found it capped Challenge B
at rho ~ 0.54. Nobody has measured the PREDICTOR's. sqrt(ICC) is the ceiling on any trait correlation the
measure can support. A five-year interval is a LOWER BOUND on measurement reliability, not an estimate of
it -- real biological change over five years is confounded with measurement error and cannot be separated
here. So a high ICC is informative and a low one is ambiguous, and the write-up must say so rather than
report sqrt(ICC) as "the reliability".

PREDICTION. `exponent_low` ICC in [0.5, 0.8]; `lrtc_alpha` LOWER than `exponent_low`, because DFA over a
184 s window has fewer effectively independent scales than a spectral fit does.

---------------------------------------------------------------------------------------------------------
WHAT THIS SCRIPT DOES
---------------------------------------------------------------------------------------------------------
Streams one EDF at a time from the public S3 mirror, computes per-channel features, reduces across channels
by MEDIAN (the delocalization argument in `UCE_AND_THE_THREE_CHALLENGES.md`; a median also survives a few
bad electrodes without a rejection step that would need its own registration), appends one row, and DELETES
the file. Peak disk is one EDF (~25 MB) regardless of how many subjects run -- the container's writable
allowance is a few tens of GB and the full deposit is 79.5 GB, so process-and-discard is not an
optimisation, it is the only way this runs at all.

RESUMABLE, like every extraction script in this repo: it reads the keys already present in the output CSV
and fetches only the remainder. Kill it and restart it freely.

ORDERED BY WHAT UNBLOCKS WHAT. `ses-1/acq-pre` for both eye states runs first across all subjects, so E44
becomes answerable before anything else finishes; then `ses-2/acq-pre` for E45; then the `acq-post` blocks
for E44's placebo. A partial run is therefore a usable run.

PREPROCESSING, fixed here and not tuned later:
  * mne reads EDF in VOLTS; everything downstream expects MICROVOLTS, so x1e6 (repo convention).
  * resample 1000 -> 250 Hz. The anti-alias lowpass sits near 125 Hz, far above the 45 Hz top of any fit,
    so it cannot steepen a slope -- the failure mode `NORMAL_REFERENCE_COVARIATES.md` §4 names as the most
    likely source of a spurious result.
  * NO notch. Line is 50 Hz here and no fit goes above 45 Hz, so a notch would add skirts inside the fit
    range for no benefit. This differs from a 60 Hz deployment and is recorded because it must be matched
    if this cohort is ever compared to a 60 Hz one.
  * NO high-pass, NO re-reference, NO ICA, NO epoch rejection. Every one of those is a choice that would
    have to be frozen into the reference; the EMG proxies are emitted as COLUMNS so that gating can be
    registered separately rather than baked in silently.

DATA HANDLING. ds005385 is a public, anonymised, openly-licensed OpenNeuro deposit -- unlike HEEDB it is not
credentialed. It is still written under /tmp/eeg_probe/ and not committed, because the repo's standing rule
is that no derived subject-level table goes into git regardless of provenance.

    python analysis/ds005385_extract.py --out /tmp/eeg_probe/ds005385_features.csv
    python analysis/ds005385_extract.py --limit 4 --out /tmp/eeg_probe/ds005385_smoke.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "bsde", "src"))
from eeg_features_common import features_from_file, MONTAGE, TARGET_SFREQ   # noqa: E402

S3 = "https://s3.amazonaws.com/openneuro.org/ds005385"
PARTICIPANTS = S3 + "/participants.tsv"


# (session, acquisition) in the order that unblocks the most analysis soonest. See ORDERED BY WHAT UNBLOCKS
# WHAT above. Each entry is expanded over both eye states.
PASSES = (("1", "pre"), ("2", "pre"), ("1", "post"), ("2", "post"))
TASKS = ("EyesClosed", "EyesOpen")



def _participants():
    txt = urllib.request.urlopen(PARTICIPANTS).read().decode("utf-8")
    return list(csv.DictReader(txt.splitlines(), delimiter="\t"))


def _url(sub, ses, task, acq):
    return (f"{S3}/{sub}/ses-{ses}/eeg/"
            f"{sub}_ses-{ses}_task-{task}_acq-{acq}_eeg.edf")


def _features(path):
    """Delegates to the SINGLE shared feature path. See `analysis/eeg_features_common.py`.

    This used to be a local copy. It was moved out when the multi-cohort reference work began, because a
    normative curve fitted in one deposit and compared against the same curve in another is uninterpretable
    if the two were computed by even slightly different code -- the difference could be the population, the
    hardware or the pipeline and nothing in the output would say which. Rule 20, applied before the fact:
    there is now only one implementation, so there is nothing to diff.

    The shared path is a strict SUPERSET of what this script emitted before: it adds absolute band powers,
    the aperiodic offset and r2, the aperiodic-corrected (residual) band powers, and the alpha peak
    frequency. Every column E44 and E45 were registered on is unchanged and computed identically.
    """
    return features_from_file(path)


def _check_schema(path, fields):
    """Abort if an existing output file's header does not match the columns we are about to write.

    **This is a data-integrity guard, not a nicety.** A resumed run after a schema change appended 65-column
    rows underneath a 53-column header, and every value in those rows was shifted: `sfreq` read 10 (the
    channel count), `duration_s` read 1.13, `lempel_ziv` read 2.415 -- a value the statistic cannot produce,
    which is the only reason it was noticed. Nothing else in the pipeline would have rejected them.

    The autonomous loop restarts these extractors, so this path is exercised routinely and must fail loudly
    rather than corrupt the table. Rule 5: a silent mismatch is not evidence of a match.
    """
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        return
    with open(path) as fh:
        existing = next(csv.reader(fh), None)
    if existing and list(existing) != list(fields):
        only_new = [c for c in fields if c not in (existing or [])]
        only_old = [c for c in (existing or []) if c not in fields]
        raise SystemExit(
            f"\nSCHEMA MISMATCH in {path}\n"
            f"   existing header : {len(existing)} columns\n"
            f"   this run writes : {len(fields)} columns\n"
            f"   new columns     : {only_new}\n"
            f"   dropped columns : {only_old}\n"
            "Appending would shift every value in the new rows. Delete the file to re-extract, or move it "
            "aside and merge deliberately. Refusing to continue.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="/tmp/eeg_probe/ds005385_features.csv")
    ap.add_argument("--limit", type=int, default=0, help="stop after N successful recordings (smoke test)")
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    parts = _participants()
    print(f"{len(parts)} participants", flush=True)

    done = set()
    if os.path.exists(a.out):
        with open(a.out) as fh:
            for r in csv.DictReader(fh):
                done.add((r["subject"], r["session"], r["task"], r["acq"]))
        print(f"resuming: {len(done)} recordings already present", flush=True)

    jobs = []
    for ses, acq in PASSES:
        flag = "session" + ses
        for p in parts:
            if (p.get(flag) or "").strip() != "yes":
                continue
            for task in TASKS:
                key = (p["participant_id"], ses, task, acq)
                if key not in done:
                    jobs.append((key, p))
    print(f"{len(jobs)} recordings to fetch", flush=True)

    fields = None
    n_ok = n_fail = 0
    t0 = time.time()
    for (sub, ses, task, acq), p in jobs:
        url = _url(sub, ses, task, acq)
        tmp = tempfile.NamedTemporaryFile(suffix=".edf", delete=False)
        tmp.close()
        try:
            # NB: this handle must NOT be called `fh` -- that is the open output-CSV handle, and shadowing
            # it here closes it on the first `with` exit, so the third row dies on "flush of closed file".
            with urllib.request.urlopen(url, timeout=180) as r, open(tmp.name, "wb") as dl:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    dl.write(chunk)
            feats = _features(tmp.name)
        except Exception as exc:                                          # noqa: BLE001
            n_fail += 1
            print(f"   FAIL {sub} ses-{ses} {task} {acq}: {type(exc).__name__}: {exc}", flush=True)
            continue
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        row = {"subject": sub, "session": ses, "task": task, "acq": acq,
               "age": p.get("age", ""), "sex": p.get("sex", ""),
               "handedness": p.get("handedness", "")}
        row.update(feats)
        if fields is None:
            fields = list(row.keys())
            _check_schema(a.out, fields)
            write_header = not os.path.exists(a.out) or os.path.getsize(a.out) == 0
            fh = open(a.out, "a", newline="")
            w = csv.DictWriter(fh, fieldnames=fields)
            if write_header:
                w.writeheader()
        w.writerow(row)
        fh.flush()
        n_ok += 1
        if n_ok % 20 == 0:
            el = time.time() - t0
            print(f"   {n_ok} ok / {n_fail} fail / {len(jobs)} total   "
                  f"{el / n_ok:.1f} s per recording   "
                  f"eta {(len(jobs) - n_ok) * el / n_ok / 3600:.1f} h", flush=True)
        if a.limit and n_ok >= a.limit:
            break

    print(f"\n{n_ok} written, {n_fail} failed -> {a.out}")
    print("NOT committed: derived subject-level tables live under /tmp/eeg_probe only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
