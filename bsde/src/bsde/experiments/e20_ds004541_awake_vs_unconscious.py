#!/usr/bin/env python3
"""E20 — awake versus unconscious, with the awake reference taken before the drug rather than before the mark.

THIS IS E19 RE-SPECIFIED AFTER ITS GATE FAILED, AND IS LABELLED AS ONE. E19's gate required
`relative_delta_power` to rise from pre-LOC to post-LOC in at least 6 of 7 subjects; it rose in **4 of 7**.
The diagnosis is not a broken pipeline and not a weak feature:

    relative_delta_power, median across 7 subjects, offsets relative to the `loc` mark
        -300s 0.859   -240s 0.819   -180s 0.856   -120s 0.897   -60s 0.828   -30s 0.906
        +30s  0.878   +60s  0.882   +120s 0.790   +180s 0.861   +240s 0.915   +300s 0.838
    the three subjects with a pre-drug `baseline` epoch: 0.683

**The delta transition is complete before the earliest window in E19's grid.** Delta is ~0.86 five minutes
before the clinical mark against ~0.68 before the drug, and it is flat across the whole ±300 s span. E19
compared two points on a plateau and its gate correctly refused to certify that as a transition.

A SECOND, INDEPENDENT DEFECT IN E19'S DESIGN, which is why the anchor changes rather than just the window.
The interval from `start` (drug onset) to `loc` ranges from **133 s to 511 s** across these seven patients.
A window at a fixed offset before `loc` therefore sits in a different pharmacological phase for every
subject — for sub-03, `loc − 300 s` falls **before the infusion began**. Offsets relative to `loc` cannot
define a common awake reference, whatever window length is chosen.

    THE FIX IS DETERMINED BY THE DATA'S STRUCTURE, NOT BY WHAT MAKES A PREDICTION PASS. All seven subjects
    carry a `start` event and all have several minutes of recording before it; only three carry `baseline`.
    So the awake reference is `start − 180/−120/−60 s`, which is pre-drug in every subject by construction.

**ONE ATTEMPT. If this gate fails too, ds004541 does not support an awake-versus-unconscious contrast and
nothing about any candidate is reported from it — not "until a third framing is tried".** Two gates already
failed on HBN for the same reason (§E16, §E17) and the rule there applies here: a sequence of framings tried
until one passes is a search over framings.

REGISTERED PREDICTIONS:
    P1  GATE. `relative_delta_power` rises from the pre-drug awake reference to post-LOC in >= 6 of 7
        subjects. Purdon et al. (PNAS 2013, PMID 23487781, verified from the MEDLINE record) report loss of
        consciousness marked by increased low-frequency power; against a genuinely pre-drug reference this is
        close to guaranteed if the machinery works, which is exactly what a gate should be.
    P2  PRIMARY, AND CARRIED OVER FROM E19 UNCHANGED. `exponent_high` moves in its declared direction
        (HIGHER when unconscious) from the pre-drug reference to post-LOC in >= 6 of 7 subjects. It has never
        faced actual loss of consciousness; its 0.863 on Chennu and 0.762 on ds005620 are both sedation-depth
        measurements (§9.16, §9.21).
    P3  PRECEDENCE — **AND ITS DIRECTION IS ALREADY KNOWN TO ME, WHICH IS DECLARED HERE RATHER THAN HIDDEN.**
        E19's diagnostic showed delta at `loc − 300 s` sitting near its post-LOC value and far from the three
        available pre-drug baselines. So P3 is not a blind prediction. What is genuinely new is the
        measurement on all seven subjects against a pre-drug reference that did not exist when that
        diagnostic was run: **delta at `loc − 300 s` lies closer to post-LOC than to the pre-drug reference in
        >= 5 of 7 subjects.** If met, the EEG transition precedes the behavioural mark by more than five
        minutes — which is temporal precedence, verifier layer 5's unbuilt half, arriving through a gate
        failure rather than through a designed test.
    P4  EMERGENCE, exercising `emergence_within_subject` for the first time. `exponent_high` at `roc + 60 s`
        lies back toward the pre-drug reference relative to post-LOC, in >= 5 of 7 subjects.

    FALSIFICATION OF THE LEAD: P2 not met while P1 passes. Then `exponent_high` does not mark loss of
    consciousness on the only reachable data where it is marked, and its interpretation narrows permanently
    to sedation depth.

SCOPE, unchanged from E19 and still binding. n = 7, one site, **and the anaesthetic agent is not recorded
anywhere in the deposit**, so nothing here bears on Challenge A. `participants.tsv` is entirely `n/a`, so no
covariate adjustment is possible. LOC is scored behaviourally, so an arousal index (§9.3's H4) predicts the
same result a consciousness marker would. Sign counts, not intervals: on 7 clusters a bootstrap interval is
theatre, and 6/7 is one-sided p = 0.06 with 7/7 at p = 0.008.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                        # noqa: E402
from bsde.candidates.seed import seed_registry                                        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "ds004541_v2.csv")

AWAKE = ("start-180", "start-120", "start-60")
POST_LOC = ("loc+30", "loc+60")
EARLY_PRE_LOC = ("loc-300",)
ROC = ("roc+60",)
GATE, PRIMARY = "relative_delta_power", "exponent_high"
GATE_MIN = PRIMARY_MIN = 6
PRECEDENCE_MIN = EMERGENCE_MIN = 5
MIN_ROWS = 100
REPORT = ("exponent_high", "exponent_gamma", "exponent_low", "whole_head_exponent", "uce_v1",
          "relative_delta_power", "relative_alpha_power", "lempel_ziv", "spectral_entropy",
          "spectral_edge_95", "wpli_alpha", "spatial_participation_ratio",
          "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
          "emg_beta_gamma_fraction", "emg_kurtosis")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main() -> int:
    seed_registry()
    print("E20 — awake (pre-drug) vs unconscious; E19's gate RE-SPECIFIED, one attempt")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    if not os.path.exists(TABLE):
        print(f"   *** {os.path.basename(TABLE)} absent. Nothing reported.")
        return 2
    by = defaultdict(dict)
    with open(TABLE, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("status") == "ok":
                by[r["subject"]][r.get("meta_epoch", "")] = r
    n_rows = sum(len(v) for v in by.values())
    if n_rows < MIN_ROWS:
        print(f"   *** {n_rows} rows, need {MIN_ROWS}; the stream is still running. A statement about the")
        print("   TABLE, not about any candidate.")
        return 1
    subs = sorted(by)
    print(f"   subjects {len(subs)}   rows {n_rows}")

    def block(s, epochs, name):
        v = [_f(by[s][e].get(name, "")) for e in epochs if e in by[s]]
        v = [x for x in v if np.isfinite(x)]
        return float(np.mean(v)) if v else float("nan")

    def signs(name, a, b, direction):
        hits = n = 0
        per = {}
        for s in subs:
            x, y = block(s, a, name), block(s, b, name)
            if np.isfinite(x) and np.isfinite(y):
                n += 1
                ok = (y > x) if direction == "higher" else (y < x)
                hits += int(ok)
                per[s] = {"awake": x, "unconscious": y, "as_declared": bool(ok)}
        return hits, n, per

    # ---- P1 gate ----
    print("\n" + "=" * 100)
    print(f"P1 — GATE: {GATE} rises from PRE-DRUG awake to post-LOC in >= {GATE_MIN} of 7")
    print("=" * 100)
    gh, gn, _ = signs(GATE, AWAKE, POST_LOC, "higher")
    p1 = gn > 0 and gh >= GATE_MIN
    print(f"   delta rose in {gh}/{gn}   {'GATE PASSED' if p1 else '*** GATE FAILED'}")
    if not p1:
        print("\n   *** AND THAT IS THE END OF IT, as registered: one attempt. Against a genuinely pre-drug")
        print("   reference, delta failing to rise means this deposit does not support an awake-vs-")
        print("   unconscious contrast in a form this pipeline can read. Nothing about any candidate is")
        print("   reported from ds004541, and a third framing is not tried.")
        json.dump({"experiment": "E20", "gate_passed": False, "gate": {"hits": gh, "n": gn},
                   "no_further_framings": True},
                  open(os.path.join(RESULTS, "e20_awake_vs_unconscious.json"), "w"), indent=2)
        return 1

    # ---- all candidates ----
    print("\n" + "=" * 100)
    print("PRE-DRUG AWAKE vs POST-LOC, sign counts across subjects (n = 7; no intervals, see SCOPE)")
    print("=" * 100)
    print(f"   {'candidate':28s} {'declared':>9s} {'as declared':>13s}")
    out = {}
    for name in REPORT:
        d = REGISTRY.get(name).predicted("unconscious_vs_awake")
        if d not in ("higher", "lower"):
            d = "higher"
        h, n, per = signs(name, AWAKE, POST_LOC, d)
        if not n:
            continue
        out[name] = {"declared": d, "hits": h, "n": n, "per_subject": per}
        tag = "  <-- primary" if name == PRIMARY else ""
        print(f"   {name:28s} {d:>9s} {h:>7d}/{n:<5d}"
              f"{' consistent' if h == n else ''}{tag}")
    pri = out.get(PRIMARY)
    p2 = bool(pri and pri["hits"] >= PRIMARY_MIN)

    # ---- P3 precedence ----
    print("\n" + "=" * 100)
    print("P3 — PRECEDENCE: is the EEG already transitioned 300 s BEFORE the behavioural mark?")
    print("=" * 100)
    ph = pn = 0
    for s in subs:
        aw, un = block(s, AWAKE, GATE), block(s, POST_LOC, GATE)
        early = block(s, EARLY_PRE_LOC, GATE)
        if all(np.isfinite(x) for x in (aw, un, early)):
            pn += 1
            ph += int(abs(early - un) < abs(early - aw))
    p3 = pn > 0 and ph >= PRECEDENCE_MIN
    print(f"   delta at loc-300s sits closer to POST-LOC than to pre-drug awake in {ph}/{pn} subjects")
    if p3:
        print("   -> the EEG transition PRECEDES the behavioural mark by more than five minutes. That is")
        print("      temporal precedence, layer 5's unbuilt half, and its direction was already known from")
        print("      E19's diagnostic -- declared in this file's header rather than presented as new.")

    # ---- P4 emergence ----
    print("\n" + "=" * 100)
    print("P4 — EMERGENCE: does the primary reverse at roc? (emergence_within_subject, first exercise)")
    print("=" * 100)
    eh = en = 0
    for s in subs:
        aw, un, rc = block(s, AWAKE, PRIMARY), block(s, POST_LOC, PRIMARY), block(s, ROC, PRIMARY)
        if all(np.isfinite(x) for x in (aw, un, rc)):
            en += 1
            eh += int(abs(rc - aw) < abs(un - aw))
    p4 = en > 0 and eh >= EMERGENCE_MIN
    print(f"   post-ROC lies back toward pre-drug awake in {eh}/{en} subjects")

    # ---- verdict ----
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 GATE delta rises, pre-drug -> post-LOC   : MET ({gh}/{gn})")
    print(f"   P2 {PRIMARY} moves as declared        : {'MET' if p2 else 'NOT MET'}"
          + (f" ({pri['hits']}/{pri['n']})" if pri else ""))
    print(f"   P3 EEG precedes the mark by > 300 s        : {'MET' if p3 else 'NOT MET'} ({ph}/{pn})")
    print(f"   P4 reverses at roc                        : {'MET' if p4 else 'NOT MET'} ({eh}/{en})")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p2:
        verdict = "PRIMARY_FAILS_AT_REAL_LOC"
        print(f"   {PRIMARY} does NOT mark loss of consciousness against a pre-drug reference")
        print(f"   ({pri['hits']}/{pri['n']}). Its Chennu 0.863 and ds005620 0.762 stand as computed and")
        print("   their interpretation narrows permanently to SEDATION DEPTH. Still a usable anaesthesia")
        print("   quantity; not a consciousness marker. n = 7, so this is a failure to demonstrate rather")
        print("   than a demonstrated absence — but it was the only test available and the burden was its.")
    else:
        verdict = "MARKS_LOC"
        print(f"   {PRIMARY} moves as declared in {pri['hits']}/{pri['n']} subjects against a pre-drug")
        print("   reference. This is the first evidence in the project that it responds to actual loss of")
        print("   consciousness rather than to sedation depth. Seven patients, one site, one unnamed drug,")
        print("   and a behaviourally-scored endpoint that an arousal index would also satisfy (§9.3 H4).")
    print(f"\n   verdict: {verdict}")

    dst = os.path.join(RESULTS, "e20_awake_vs_unconscious.json")
    json.dump({"experiment": "E20", "respecified_from": "E19", "gate_passed": True,
               "gate": {"hits": gh, "n": gn}, "awake_epochs": list(AWAKE),
               "n_subjects": len(subs), "n_rows": n_rows, "awake_vs_post_loc": out,
               "precedence": {"hits": ph, "n": pn, "direction_known_in_advance": True},
               "emergence": {"hits": eh, "n": en},
               "predictions": {"P1": True, "P2": p2, "P3": p3, "P4": p4},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
