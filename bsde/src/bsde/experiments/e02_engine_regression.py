#!/usr/bin/env python3
"""E02 — put E01's finding through the engine, as a known-answer regression on REAL data.

WHY THIS EXPERIMENT EXISTS. E01 established by hand, on 96 real recordings, that UCE v1's frontal/posterior
structure is decorative: r(frontal, posterior) = 0.9326 and corr(UCE v1, whole-head baseline) = 0.9952. The
engine's entire justification is that it should produce findings of that kind AUTOMATICALLY rather than by
hand. So the engine is required to reach the same conclusion, from the same data, with no hand-holding — and
to reach it about the project's own flagship construct.

A verifier that cannot demote its author's prior work is decoration.

REGISTERED BEFORE RUNNING:
    P1  The engine returns a non-surviving verdict for uce_v1 on the redundancy check, citing
        `redundancy_with_simpler_measure`.
    P2  The measured |Spearman r| between uce_v1 and whole_head_exponent reproduces E01's Pearson value of
        0.9952 to within 0.02. (Spearman and Pearson need not agree exactly; a large gap would itself be
        informative and would mean one of them is being driven by a few extreme recordings.)
    P3  whole_head_exponent, the complexity-2 baseline, is NOT flagged as redundant — there is no simpler
        alternative for it to be redundant with.
    FALSIFICATION: if |r| comes out below 0.90, E01 does not replicate under the engine's own feature
    adapters, and the discrepancy between the two code paths must be resolved before either is trusted
    (sibling error-catalogue rule 20: when two scripts compute the same quantity, diff them).

AMENDMENT, 2026-07-29, recorded rather than made silently. P3 was first operationalised as
`status == PASS`. The first run exposed a defect this predicate was sitting on top of: with no simpler
alternative available, `check_redundancy` was returning PASS with the prose "below the near-redundancy
threshold" while the measured |r| was 1.0000 — a false statement in the report, since the baseline was
being compared against itself. The check now returns NOT_APPLICABLE in that situation, and P3's predicate is
widened to `status in (PASS, NOT_APPLICABLE)`.

This is a change to how a prediction is MEASURED, made because the measurement was wrong, and it does not
touch what P3 CLAIMS: the baseline must not be flagged as redundant. That claim was satisfied under both
versions of the code, so the amendment cannot have rescued a failing prediction. P1 and P2 — the predictions
that carry the actual finding — are untouched. The amendment is written here rather than applied quietly
because the difference between those two things is the entire point of the declaration format.

SCOPE. This dataset ships NO diagnostic labels (verified). Nothing here speaks to consciousness, diagnosis
or prognosis. The statistical, cross-domain and temporal layers cannot run at all, and the engine says so
rather than passing them by default.
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                          # noqa: E402
from bsde.candidates.seed import seed_registry                          # noqa: E402
from bsde.governance.search_log import append, entry_from_report        # noqa: E402
from bsde.verifier.engine import check_redundancy                       # noqa: E402
from bsde.verifier.report import (Evidence, VerifierReport, decide, render,
                                  PASS, NOT_RUN, NOT_APPLICABLE)         # noqa: E402

DATA = os.environ.get("FIGSHARE_DOC", "/tmp/uce_data/figshare_doc")
NOW = os.environ.get("BSDE_NOW", "2026-07-29T00:00:00Z")


def read_brainvision(vhdr: str):
    import mne
    raw = mne.io.read_raw_brainvision(vhdr, preload=True, verbose="ERROR")
    return raw.get_data(), raw.ch_names, float(raw.info["sfreq"])


def main() -> int:
    vhdrs = sorted(glob.glob(os.path.join(DATA, "*.vhdr")))
    if not vhdrs:
        print(f"no .vhdr under {DATA} — set FIGSHARE_DOC")
        return 1
    seed_registry()
    uce = REGISTRY.get("uce_v1")
    base = REGISTRY.get("whole_head_exponent")

    print("E02 — engine regression against E01, on real EEG")
    print(f"   dataset: Figshare 10.6084/m9.figshare.23552964 (CC BY 4.0), {len(vhdrs)} recordings")
    print(f"   candidates: {uce.name} v{uce.version} (cx {uce.complexity}) vs "
          f"{base.name} v{base.version} (cx {base.complexity})\n")

    u_vals, b_vals, used = [], [], []
    for i, v in enumerate(vhdrs, 1):
        try:
            data, chs, sf = read_brainvision(v)
            # 2 s Welch window: these are concatenated 2 s epochs, so a longer window straddles boundaries.
            uv = uce.fn(data, chs, sf, {})
            bv = base.fn(data, chs, sf, {})
        except Exception as e:
            print(f"   [{i}] {os.path.basename(v)}: FAILED {type(e).__name__}: {e}")
            continue
        u_vals.append(uv)
        b_vals.append(bv)
        used.append(os.path.basename(v)[:-5])
        if i % 20 == 0:
            print(f"   [{i}/{len(vhdrs)}]", flush=True)

    u = np.asarray(u_vals, float)
    b = np.asarray(b_vals, float)
    ok = np.isfinite(u) & np.isfinite(b)
    print(f"\n   usable recordings: {int(ok.sum())}/{len(vhdrs)}")

    reports = []
    for cand, vals, bl_name, bl_cx in [(uce, u, base.name, base.complexity),
                                       (base, b, "none simpler exists", 99)]:
        rep = VerifierReport(candidate=cand.name, candidate_version=cand.version,
                             declaration_hash=cand.declaration_hash(),
                             search_space_size=REGISTRY.search_space_size(),
                             required_layers=sorted(cand.requires),
                             datasets=["figshare_23552964"])
        rep.add(Evidence("synthetic_ground_truth", "computational", PASS,
                         "the aperiodic estimator recovers known synthetic exponents to within 0.15 across "
                         "0.5-3.0; see tests/test_aperiodic_recovery.py"))
        rep.add(check_redundancy(cand, vals[ok], b[ok], bl_name, bl_cx))
        for layer, why in [("statistical", "this dataset ships no diagnostic labels of any kind (verified), "
                                           "so no outcome contrast can be formed"),
                           ("cross_domain", "only one dataset was processed")]:
            if layer in cand.requires:
                rep.add(Evidence(f"{layer}_layer", layer, NOT_RUN, why,
                                 item="cross_dataset_performance" if layer == "statistical"
                                 else "leave_one_dataset_out"))
        reports.append(decide(rep))
        print("\n" + render(reports[-1]))

    # ---- the registered predictions -------------------------------------------------------------
    e_uce = [e for e in reports[0].evidence if e.check == "redundancy_with_simpler_measure"][0]
    r = float(e_uce.values["abs_spearman"])
    print("\n" + "=" * 100)
    print("REGISTERED PREDICTIONS")
    print("=" * 100)
    p1 = reports[0].verdict != "SURVIVE" and e_uce.status == "fail"
    p2 = abs(r - 0.9952) < 0.02
    # See the AMENDMENT note in the module docstring for why NOT_APPLICABLE counts here.
    p3 = ([e for e in reports[1].evidence if e.check == "redundancy_with_simpler_measure"][0].status
           in (PASS, NOT_APPLICABLE))
    print(f"   P1 engine demotes uce_v1 on redundancy       : {'MET' if p1 else 'NOT MET'} "
          f"(verdict {reports[0].verdict}, check {e_uce.status})")
    print(f"   P2 |Spearman r| reproduces E01's 0.9952      : {'MET' if p2 else 'NOT MET'} "
          f"(measured {r:.4f}, difference {r - 0.9952:+.4f})")
    print(f"   P3 the baseline is not flagged as redundant  : {'MET' if p3 else 'NOT MET'}")
    if r < 0.90:
        print("\n   *** FALSIFIED: E01 does not replicate through the engine's feature adapters. Diff the "
              "two code paths before trusting either (rule 20).")

    out = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "e02_engine_regression.json"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"experiment": "E02", "n_recordings_usable": int(ok.sum()),
               "abs_spearman_uce_vs_baseline": r, "e01_pearson_reference": 0.9952,
               "p1_engine_demotes_uce": bool(p1), "p2_reproduces_e01": bool(p2),
               "p3_baseline_passes": bool(p3),
               "verdicts": {rp.candidate: rp.verdict for rp in reports},
               "dataset_doi": "10.6084/m9.figshare.23552964", "labels_available": False},
              open(out, "w"), indent=2)
    print(f"\n   machine-readable result -> {out}")

    log = None
    for rp in reports:
        log = append(entry_from_report(rp, NOW, analytic_dof=1,
                                       extra={"experiment": "E02", "note": "label-free; identity check only"}))
    print(f"   search log               -> {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
