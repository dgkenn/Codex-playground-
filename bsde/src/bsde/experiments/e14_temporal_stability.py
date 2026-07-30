#!/usr/bin/env python3
"""E14 — does group-level discrimination survive contact with a single window?

REGISTERED BEFORE ANY MULTI-WINDOW FEATURE VALUE EXISTS. The work-list is derived offline from
`sleep_edfx_five_stage_worklist.json`, which contains stage labels and block boundaries and no EEG at all;
nothing has been read from a second or third window of any block.

THE QUESTION, AND WHY NOTHING IN THIS PROJECT HAS ASKED IT.

Every result this project has produced — E02 through E13 — collapses a recording to ONE number and then asks
whether that number separates groups. Chennu's 0.863, Sleep-EDF's 0.99s, every AUC in every table: one window
per subject per state, compared across subjects. That answers a question about populations.

**A clinician has one patient and one window.** The question they face is whether THIS window is N3 or REM,
this patient sedated or awake. A measure can separate two populations perfectly and be useless for that, if
its window-to-window scatter inside a state is as large as the distance between states. Nothing in layers 2-4
of the verifier can detect it, because they never see two windows from the same state.

Verifier layer 5 exists to measure it and has never been run on real data, because every feature table this
project holds has exactly one window per (subject, state). This experiment builds the table it needs.

    temporal SNR  =  (between-state separation within a subject) / (within-state scatter)

Below 1.0, single-window classification is impossible whatever the group AUC says.

DESIGN. 60 recordings, deterministically the first 60 by sorted identifier among those whose W, N2, N3 and
REM blocks all run to at least 360 s — stated so the selection is checkable and cannot have been chosen by
result. N1 is DROPPED: it is transitional by definition, its median block is exactly 360 s, and requiring it
would have cut the corpus from 108 recordings to 51. Three non-overlapping 120 s windows are taken from the
central 360 s of each block, so all three sit far from the stage boundaries and any scatter between them is
within-state variation rather than contamination from a neighbouring stage.

    60 recordings x 4 states x 3 windows = 720 rows

REGISTERED PREDICTIONS:
    P1  MACHINERY GATE. `relative_delta_power` must have temporal SNR above 2.0 across these states. Delta
        power is the defining feature of N3 and is grossly different in W; if even that measure cannot clear
        its own within-state scatter, the windowing or the stage blocks are wrong and nothing else is
        reported (rule 31: absent, not negative).
    P2  PRIMARY, AND IT IS A PREDICTION OF FAILURE. At least one candidate with a strong group-level
        association on this very data (|AUC-0.5| >= 0.40 on W vs N3 in E11's table) has temporal SNR below
        1.0. If met, group discrimination demonstrably overstates single-window usability in this candidate
        set, and every AUC this project has reported carries that caveat. If NOT met — if every
        well-discriminating candidate is also temporally stable — that is a genuinely good result for the
        candidate set and I will have predicted the pessimistic outcome and been wrong.
    P3  SNR RANKING DIFFERS FROM AUC RANKING. Spearman correlation between candidates' |AUC-0.5| and their
        temporal SNR is below +0.70. Registered because if SNR simply reproduces AUC it is a redundant axis
        and layer 5 adds a number rather than a check — the fourth instance of the redundancy this project
        has over-predicted three times (rule 28). A LOW correlation is what justifies the layer existing.
    P4  ICC IS HIGH — median across candidates above 0.5 — so that row-level resampling would have
        materially overstated precision. Registered as a bookkeeping check with teeth: if it holds, then any
        analysis anywhere in this project that resampled rows instead of subjects has intervals that are too
        narrow, and `effective_sample_size` quantifies by how much.

    FALSIFICATION OF THE LAYER ITSELF: P3 not met. If temporal SNR is just AUC wearing a different name, the
    layer should be withdrawn rather than kept for completeness.

WHAT THIS STILL DOES NOT TEST. Temporal PRECEDENCE — whether a measure moves before the state label does — is
the other half of layer 5 and is not attempted. It needs densely-sampled transitions with a verified time
axis, and rule 27 records what happens when the time axis is not checked first. Three windows from the middle
of a stable block are the wrong instrument for it, deliberately: they are chosen to sit AWAY from transitions.
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
from bsde.verifier.stats import auc, spearman                                          # noqa: E402
from bsde.verifier.temporal import (intraclass_correlation, single_window_penalty,     # noqa: E402
                                    temporal_snr)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
FIVE_STAGE_WL = os.path.join(RESULTS, "sleep_edfx_five_stage_worklist.json")
WORKLIST_JSON = os.path.join(RESULTS, "sleep_edfx_multiwindow_worklist.json")
TABLE = os.path.join(RESULTS, "sleep_edfx_multiwindow.csv")

STATES = ("W", "N2", "N3", "REM")
N_WINDOWS = 3
WINDOW_S = 120.0
MIN_BLOCK_S = N_WINDOWS * WINDOW_S          # 360 s -- exactly what three non-overlapping windows need
N_RECORDINGS = 60
GATE = "relative_delta_power"
GATE_MIN_SNR = 2.0
STRONG_AUC = 0.40                            # |AUC - 0.5| threshold for "strong group-level association"
SNR_UNUSABLE = 1.0
RANK_CORR_MAX = 0.70
CANDIDATES = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
              "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
              "uce_v1", "wpli_alpha", "spatial_participation_ratio", "multiscale_entropy_slope",
              "pac_slow_alpha", "critical_slowing_ar1", "emg_beta_gamma_fraction", "emg_kurtosis")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def build_worklist() -> list:
    """Derived entirely from the five-stage work-list — no network, no EEG read."""
    wl = json.load(open(FIVE_STAGE_WL))
    blocks = defaultdict(dict)
    for r in wl:
        blocks[r["subject"]][r["label"]] = (r["url"], r["meta"]["block_start_s"],
                                            r["meta"]["block_end_s"], r["meta"]["hypnogram_url"])
    ok = sorted(s for s, d in blocks.items()
                if all(st in d and (d[st][2] - d[st][1]) >= MIN_BLOCK_S for st in STATES))
    chosen = ok[:N_RECORDINGS]
    rows = []
    for subj in chosen:
        for st in STATES:
            url, b0, b1, hyp = blocks[subj][st]
            # Three consecutive windows centred in the block, so all sit away from the stage boundaries.
            span = N_WINDOWS * WINDOW_S
            start0 = max(b0, min((b0 + b1) / 2.0 - span / 2.0, b1 - span))
            for k in range(N_WINDOWS):
                rows.append({
                    "url": url,
                    "start_seconds": start0 + k * WINDOW_S,
                    "window_s": WINDOW_S,
                    "label": f"{st}#{k}",
                    "subject": subj,
                    "recording_id": f"{subj}@{st}#{k}",
                    "meta": {"hypnogram_url": hyp, "stage": st, "window_index": k,
                             "block_start_s": b0, "block_end_s": b1},
                })
    print(f"   qualifying recordings (all of {STATES} with blocks >= {MIN_BLOCK_S:.0f}s): {len(ok)}")
    print(f"   selected the first {len(chosen)} by sorted identifier -> {len(rows)} rows")
    return rows


def load_e11_auc() -> dict:
    """|AUC - 0.5| per candidate from E11's wake-vs-N3 table, for P2 and P3. Read from the committed JSON
    rather than recomputed, so this experiment compares against the number that was actually reported."""
    p = os.path.join(RESULTS, "e11_propofol_beta.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p))
    return {k: abs(float(v)) for k, v in
            d.get("saturation", {}).get("abs_auc_minus_half", {}).items()}


def main() -> int:
    seed_registry()
    if "--build" in sys.argv:
        rows = build_worklist()
        json.dump(rows, open(WORKLIST_JSON, "w"), indent=1)
        print(f"   -> {WORKLIST_JSON}")
        return 0

    print("E14 — does group-level discrimination survive contact with a single window?")
    print(f"   search space {REGISTRY.search_space_size()} registered candidates; analytic dof >= 72")
    if not os.path.exists(TABLE):
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    with open(TABLE, newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status") == "ok"]
    stage = np.array([r["recording_id"].rsplit("@", 1)[-1].split("#")[0] for r in rows])
    subj = np.array([r["subject"] for r in rows])
    n_cells = len({(s, st) for s, st in zip(subj, stage)})
    print(f"   rows {len(rows)}   recordings {len(set(subj))}   (subject, state) cells {n_cells}")

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)   # noqa: E731
    rng = np.random.default_rng(20260730)

    # W vs N3 outcome for the single-window penalty, matching E11's contrast.
    keep = np.isin(stage, ("W", "N3"))
    y_all = np.where(stage == "N3", 1.0, 0.0)

    # ------------------------------- P1 gate ------------------------------------------------------
    print("\n" + "=" * 100)
    print(f"P1 — MACHINERY GATE: {GATE} temporal SNR must exceed {GATE_MIN_SNR}")
    print("=" * 100)
    g = temporal_snr(col(GATE), subj, stage)
    p1 = np.isfinite(g["snr"]) and g["snr"] > GATE_MIN_SNR
    print(f"   {GATE:26s} SNR {g['snr']:.2f}  (between {g['between']:.4g} / within {g['within']:.4g}, "
          f"{g['n_subjects']} subjects)   {'GATE PASSED' if p1 else '*** GATE FAILED'}")
    if not p1:
        print("   Delta power is the defining feature of N3 and is grossly different in W. If it cannot")
        print("   clear its own within-state scatter, the windowing or the stage blocks are wrong.")
        json.dump({"experiment": "E14", "gate_passed": False, "gate": g},
                  open(os.path.join(RESULTS, "e14_temporal.json"), "w"), indent=2, default=str)
        return 1

    # ------------------------------- the table ----------------------------------------------------
    e11 = load_e11_auc()
    print("\n" + "=" * 100)
    print("TEMPORAL STABILITY BY CANDIDATE")
    print("=" * 100)
    print(f"   {'candidate':28s} {'SNR':>7s} {'within':>10s} {'between':>10s} {'ICC':>6s} "
          f"{'n_eff/n':>8s} {'|AUC-.5|':>9s} {'penalty':>8s}")
    res = {}
    for name in CANDIDATES:
        v = col(name)
        if not np.isfinite(v).any():
            continue
        s = temporal_snr(v, subj, stage)
        # The cell, not the subject: see intraclass_correlation's docstring for what grouping by subject
        # alone did to this number on the first run.
        i = intraclass_correlation(v, subj, stage)
        pen = single_window_penalty(v[keep], subj[keep], y_all[keep], rng, state=stage[keep])
        a = e11.get(name, float("nan"))
        res[name] = {"snr": s, "icc": i, "penalty": pen, "e11_abs_auc": float(a)}
        ratio = (i["n_eff"] / i["n_rows"]) if np.isfinite(i.get("n_eff", np.nan)) else float("nan")
        print(f"   {name:28s} {s['snr']:7.2f} {s['within']:10.4g} {s['between']:10.4g} "
              f"{i.get('icc', float('nan')):6.3f} {ratio:8.2f} {a:9.3f} {pen['penalty']:8.3f}")

    # ------------------------------- predictions ---------------------------------------------------
    strong = {n: e for n, e in res.items()
              if np.isfinite(e["e11_abs_auc"]) and e["e11_abs_auc"] >= STRONG_AUC}
    unusable = {n: e["snr"]["snr"] for n, e in strong.items()
                if np.isfinite(e["snr"]["snr"]) and e["snr"]["snr"] < SNR_UNUSABLE}
    p2 = len(unusable) > 0

    pairs = [(e["e11_abs_auc"], e["snr"]["snr"]) for e in res.values()
             if np.isfinite(e["e11_abs_auc"]) and np.isfinite(e["snr"]["snr"])]
    rho = spearman([a for a, _ in pairs], [s for _, s in pairs]) if len(pairs) >= 5 else float("nan")
    p3 = np.isfinite(rho) and rho < RANK_CORR_MAX

    iccs = [e["icc"]["icc"] for e in res.values() if np.isfinite(e["icc"].get("icc", np.nan))]
    med_icc = float(np.median(iccs)) if iccs else float("nan")
    p4 = np.isfinite(med_icc) and med_icc > 0.5

    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 GATE {GATE} SNR > {GATE_MIN_SNR}                   : MET ({g['snr']:.2f})")
    print(f"   P2 a strongly-discriminating candidate has SNR < {SNR_UNUSABLE}    : "
          f"{'MET' if p2 else 'NOT MET'} ({ {k: round(v, 2) for k, v in unusable.items()} or 'none'})")
    # BOUNDARY FLAG. Spearman over a dozen candidates is quantised, and rho landed on the threshold to
    # within one unit in the last place. A verdict decided by floating-point representation is not a
    # verdict, and printing "MET" without saying so would be the third time today a knife-edge threshold
    # was reported as a finding.
    on_boundary = np.isfinite(rho) and abs(rho - RANK_CORR_MAX) < 1e-9
    print(f"   P3 SNR ranking differs from AUC ranking (rho < {RANK_CORR_MAX})  : "
          f"{'MET' if p3 else 'NOT MET'} (rho {rho:+.17g} over {len(pairs)} candidates)")
    if on_boundary:
        print(f"      *** ON THE BOUNDARY: rho differs from {RANK_CORR_MAX} by "
              f"{abs(rho - RANK_CORR_MAX):.1e}. This 'MET' is a coin flip on floating-point")
        print("      representation, not evidence. TREAT P3 AS UNDETERMINED: the layer's own")
        print("      justification -- that temporal SNR is not AUC wearing a different name -- is")
        print("      NOT established by this run, and the layer is retained provisionally.")
    print(f"   P4 median ICC > 0.5, so row-level resampling misleads    : "
          f"{'MET' if p4 else 'NOT MET'} (median ICC {med_icc:.3f})")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p3:
        verdict = "LAYER_REDUNDANT_WITH_AUC"
        print(f"   Temporal SNR tracks |AUC-0.5| at rho {rho:+.3f}. It is AUC wearing a different name, and")
        print("   layer 5 adds a number rather than a check. On the registered falsification the layer")
        print("   should be WITHDRAWN rather than kept for completeness — the fourth instance of the")
        print("   redundancy this project has over-predicted three times (rule 28).")
    elif p2:
        verdict = "GROUP_AUC_OVERSTATES_SINGLE_WINDOW_USE"
        print(f"   {len(unusable)} of {len(strong)} strongly-discriminating candidates cannot classify a")
        print(f"   single window: {sorted(unusable)}. Their within-state scatter equals or exceeds the")
        print("   between-state gap. Every AUC this project has reported is a population statement, and")
        print("   for these candidates it does not transfer to the setting the measure would be used in.")
    else:
        verdict = "DISCRIMINATION_TRANSFERS"
        print("   Every strongly-discriminating candidate is also temporally stable. I predicted the")
        print("   pessimistic outcome and was wrong, which is the good outcome for the candidate set:")
        print("   group-level AUC on this data does transfer to a single window.")
    print(f"\n   verdict: {verdict}")
    print("\n   NOT TESTED HERE: temporal PRECEDENCE. These windows sit deliberately AWAY from transitions.")

    dst = os.path.join(RESULTS, "e14_temporal.json")
    json.dump({"experiment": "E14", "gate_passed": True, "gate": g, "n_rows": len(rows),
               "n_recordings": len(set(subj)), "by_candidate": res, "auc_vs_snr_spearman": rho,
               "median_icc": med_icc, "unusable_but_discriminating": unusable,
               "p3_on_boundary": bool(on_boundary), "icc_grouping": "(subject, state) cell",
               "predictions": {"P1": True, "P2": bool(p2), "P3": bool(p3), "P4": bool(p4)},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
