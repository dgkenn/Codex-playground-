#!/usr/bin/env python3
"""E18 — LIS versus UWS: the one human contrast that holds motor output fixed and varies consciousness.

REGISTERED BEFORE ACCESS TO THE DATA HAS BEEN GRANTED. An access request for BATH-01632 was sent on
2026-07-30; no EEG from that deposit has been seen, and this file exists so that the analysis is fixed before
it can be. **A pre-registration written after the data arrives is not one, and the window closes when the
custodians reply.**

WHY THIS CONTRAST AND NOT THE COMMAND-FOLLOWING ONE. Bath's headline endpoint is motor-imagery decoding
accuracy — command-following, Challenge B. That is valuable and it is not what makes this deposit unique.
What makes it unique is the group composition:

    UWS (n = 14)   no motor output, and by clinical definition unaware
    LIS (n = 11)   no motor output, and fully conscious
    MCS (n = 17)   intermediate on the behavioural scale
    AB  (n = 2)    able-bodied benchmark, same protocol

**LIS and UWS share absent motor output and differ in consciousness.** Every contrast this project has run
confounds the two: sedation removes both together, sleep removes both together, and §9.16 established that
the Chennu cohort never loses either. This is the only human dissociation reachable, and it is precisely what
verifier layer 6 (mechanistic) was specified to need — §9.22 recorded that layer as gated on data rather than
code, and this is the data.

DECLARATION OF PRIOR KNOWLEDGE, WHICH WEAKENS THE PRIMARY AND MUST BE STATED FIRST.
The deposit's openly-available Supplementary Information — read on 2026-07-30, before this file — reports
group-level source-space functional-connectivity results whose post-hoc comparisons run **LIS > MCS** and
**LIS > UWS** across frontal, parietal, temporal and sensorimotor regions, in theta (4-7 Hz) and alpha
(8-12 Hz). **So the direction is already known to me.** A confirmation therefore carries little information.
The informative outcomes here are (a) WHICH of the registry's candidates fail to reproduce an ordering that
is known to exist in the data, and (b) whether any of them adds anything to the bedside behavioural score,
which is P4 and is the only part a clinician would care about.

WHAT WILL BE ANALYSED. Resting or pre-cue EEG, NOT the task period. The registry contains resting-state
scalars; none of them is a task-trial classifier, and the published decoding analysis is not being redone.
The record defines a pre-cue interval of -1000 to 0 ms relative to task-cue onset, and the trial structure is
a "Beep" cue followed by 10 s of imagery ending in "Relax".

    **1 s of pre-cue is too short for most of this registry** — `lempel_ziv` decimates to 100 Hz and needs
    10 s windows, `multiscale_entropy` needs thousands of samples, `critical_slowing` needs at least two
    2 s windows. This is stated now, before seeing the data, because the honest response to "the epochs are
    too short" is to report the analysis as INFEASIBLE, not to concatenate epochs across gaps. Error-
    catalogue rule 27: a mask that compresses out bad samples glues time together, and one recording in 24
    had a 1,817 s hole closed up invisibly. Concatenating pre-cue epochs would do the same thing on purpose.

REGISTERED PREDICTIONS:
    P0  FEASIBILITY GATE, declared because the data has not been seen. The deposit must supply, outside the
        task period, at least 20 s of contiguous EEG per session for at least 10 subjects in EACH of the LIS
        and UWS groups. If it does not, the registry's candidates cannot be computed as defined and the
        result is INFEASIBLE — reported as such, and NOT as a negative finding about any candidate.
    P1  MACHINERY GATE. At least one registered candidate must separate the able-bodied benchmark
        participants from the UWS group with |AUC - 0.5| >= 0.25. If a healthy adult cannot be told from a
        UWS patient by ANY candidate in this registry, on this deposit, then the montage handling, the
        referencing or the artefact rejection is wrong and nothing else is reported (rule 31). The benchmark
        n is only 2, so this gate is deliberately weak — it can catch a broken pipeline and cannot certify a
        working one.
    P2  PRIMARY. At least one candidate separates LIS from UWS with a subject-clustered CI excluding 0.5.
        Given the declaration above I expect this to be MET, and its being met is weak evidence.
    P3  ORDERING. For any candidate meeting P2, the group medians order monotonically LIS > MCS > UWS, or
        monotonically the other way — consistently, not just at the endpoints. A monotone ordering across
        three clinically-ordered groups is much harder to produce by accident than a two-group difference,
        and MCS is the group the endpoints cannot explain away.
    P4  INCREMENTAL VALUE OVER THE BEDSIDE EXAM, AND IT IS THE ONLY CLINICALLY MEANINGFUL PREDICTION HERE.
        Does the candidate still separate LIS from UWS once session-level CRS-R total is held constant?
        Framed deliberately as INCREMENTAL VALUE and not as "controlling for consciousness": CRS-R is the
        instrument that assigns the groups, so conditioning on it cannot be read as adjusting for a
        confounder. The question it answers is the one a clinician actually has — does the EEG tell me
        anything the examination did not.

    FALSIFICATION OF THE REGISTRY: P2 not met while P1 passes. If none of these candidates separates a
    conscious patient from an unaware one, on the only dataset where motor output is held fixed, then the
    registry measures arousal or output and not consciousness — and every `unconscious_vs_awake` result in
    this project is compatible with H4 (§9.3) rather than with the capacity hypothesis.

WHAT THIS CANNOT DO, and it is a real limit rather than a caveat. UWS and LIS differ in far more than
consciousness: aetiology, lesion location, time since injury, medication, sleep-wake cycling and arousal.
No design available here can separate consciousness from all of those, and a positive result must be
reported as "separates these two clinical groups", never as "detects consciousness". **A false positive here
is a clinical harm** (Brief 01 §20) — telling a family that an unaware patient is aware — and that asymmetry
is why P4 exists and why the primary is treated as weak evidence even when met.

SCOPE. n as above; group sizes are small and the LIS/UWS comparison has at most 14 against 11 subjects, so
every interval will be wide and no single-candidate claim will be strong. Denominators: the registered
candidate count and analytic_dof >= 72 for the exponent family.

STATUS: this script cannot run until access is granted. It refuses, by design, rather than reporting
anything from an absent table.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "bath_pdoc_resting.csv")

GROUPS = ("UWS", "MCS", "LIS", "AB")
MIN_WINDOW_S = 20.0
MIN_PER_GROUP = 10
BENCHMARK_MIN_EFFECT = 0.25
# Known before registering, from the deposit's public Supplementary Information. Recorded as data so that
# any later report can be checked against what was already known rather than against a memory of it.
PRIOR_KNOWLEDGE = {
    "source": "BATH-01632 public Supplementary Information, read 2026-07-30",
    "published_direction": ["LIS > MCS", "LIS > UWS"],
    "published_measure": "source-space functional connectivity, theta 4-7 Hz and alpha 8-12 Hz",
    "regions": ["frontal", "parietal", "left temporal", "right temporal", "sensorimotor", "occipital"],
    "implication": "the primary direction is known in advance, so a confirmation is weak evidence",
}


def main() -> int:
    print("E18 — LIS vs UWS: motor output held fixed, consciousness varied")
    print(f"   registered {os.path.basename(__file__)} before data access was granted")
    print(f"   prior knowledge declared: {PRIOR_KNOWLEDGE['published_direction']} "
          f"({PRIOR_KNOWLEDGE['source']})")
    if not os.path.exists(TABLE):
        print(f"\n   *** {os.path.basename(TABLE)} is not present.")
        print("   BATH-01632 is a restricted deposit and access has been requested, not granted. This")
        print("   script refuses to report rather than substituting anything for the data it needs.")
        print("\n   When the table exists, the order of evaluation is fixed by the registration:")
        print(f"     P0 feasibility  — >= {MIN_WINDOW_S:g}s contiguous non-task EEG per session for "
              f">= {MIN_PER_GROUP} subjects in EACH of LIS and UWS, else INFEASIBLE (not negative)")
        print(f"     P1 machinery    — some candidate separates AB from UWS by |AUC-0.5| >= "
              f"{BENCHMARK_MIN_EFFECT}")
        print("     P2 primary      — some candidate separates LIS from UWS, CI excluding 0.5")
        print("     P3 ordering     — monotone LIS > MCS > UWS, the part MCS cannot explain away")
        print("     P4 incremental  — does it survive holding session-level CRS-R total constant")
        return 2
    print("   table present — implement the analysis body against the real column names before running")
    return 1


if __name__ == "__main__":
    sys.exit(main())
