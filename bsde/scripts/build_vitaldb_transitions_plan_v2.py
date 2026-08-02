"""Build the v2 (EXPANDED) sampling plan for VitalDB, direct from the live API rather than the 250-case
cache -- MECHANICAL COHORT EXPANSION, not a registered experiment. This script decides WHICH TIMES to
sample; it never looks at a candidate, a BIS value, an outcome, or any relationship between them.

WHY. `build_vitaldb_transitions_plan.py` (v1, UNTOUCHED by this file) reads `anestart`/`aneend` only from
the cached `vitaldb_grid*.csv` tables, which were themselves built by `VitalDBGridAdapter` with
`require_monitor=True` and `ane_type == "General"` and BOTH `anestart` and `aneend` finite -- and, being a
cache, capped at `n_cases=250` (sorted by caseid, so the LOWEST 250 case ids only). That is the binding
power limit on the transitions analysis: of 250 cases only ~35-60 contribute a usable measurement. This
script re-derives the eligible case set from the live `/cases` and `/trks` endpoints with no case-count cap,
so every case VitalDB carries an EEG track and a usable `aneend` for is included.

FILTER CHAIN, exactly as instructed and reported by `main()`, no additional exclusions:
    all cases (rows in /cases)
        -> has the EEG track the adapter actually uses (BIS/EEG1_WAV, matched from
           `bsde/src/bsde/ingestion/vitaldb.py`'s `EEG_TRACK` constant, not invented here)
        -> has a usable `aneend` (parses to a finite float)
`anestart` usability is measured and reported SEPARATELY on that final set, never used to exclude a case --
`VitalDBTargetedAdapter.list_recordings` (the adapter this plan is actually streamed through, verified by
reading `stream_vitaldb_transitions.py`) does not require a monitor track or `ane_type == "General"` either;
it only requires the case to appear in `by_case` with the EEG track present. So this plan does not apply
those two filters -- doing so would exclude cases the extractor can in fact process. `ane_type` distribution
on the eligible set is measured and printed for transparency but does not filter anything.

WINDOW GEOMETRY, IDENTICAL TO v1: 10 s window, 10 s stride, transition-600s to transition+600s (121 points),
both transitions attempted per case, negative-time windows dropped (`t >= 0`, case-relative) -- the induction
window mostly does not survive this on the ~92% of cases where `anestart` is itself negative, exactly as v1's
module docstring records; that is a property of the deposit, reported not concealed.

THE v1 250 CASES ARE KEPT VERBATIM. `vitaldb_transitions_plan.json` (v1's output, read-only here) is unioned
into this plan's per-case time lists rather than re-derived, so a case already streamed into
`vitaldb_transitions.s*.csv` keeps exactly the times that file's rows key on -- the resumable, de-duplicating
extractor (rule 56) then only fetches what v1 never had, never re-derives what it already has even if a fresh
API pull produced a marginally different anestart/aneend for the same case (it should not, the source table
is static, but this makes the guarantee independent of that).

OUTPUTS (new paths, nothing existing is touched):
    bsde/results/vitaldb_transitions2_plan.json   {caseid: sorted [times...]}
    bsde/results/vitaldb_transitions2_meta.json   {caseid: {anestart_s, aneend_s, ane_type, has_bis_bis,
                                                             has_bis_sqi}}  + a top-level "_summary" block
                                                   recording every filter-chain count this run measured.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
sys.path.insert(0, SRC)

from bsde.ingestion.vitaldb import EEG_TRACK  # noqa: E402 -- matched from the adapter, not invented here

API = "https://api.vitaldb.net"
PRE_S = 600.0
POST_S = 600.0
STEP_S = 10.0

V1_PLAN = os.path.join(RESULTS, "vitaldb_transitions_plan.json")


def _fetch(url: str, timeout: float = 300.0) -> str:
    """Byte-identical to `bsde.ingestion.vitaldb._fetch` -- duplicated rather than imported so this script
    has no runtime dependency on the module beyond the EEG_TRACK constant, and so a future edit to the
    adapter's fetch behaviour cannot silently change what THIS script does without also being reviewed here.
    """
    blob = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "bsde/1.0"}), timeout=timeout).read()
    if blob[:2] == b"\x1f\x8b":
        blob = gzip.decompress(blob)
    return blob.decode("utf-8-sig", "replace")


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _window(center: float) -> list:
    n = int(round((PRE_S + POST_S) / STEP_S)) + 1  # 121
    return [round(center - PRE_S + i * STEP_S, 3) for i in range(n)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(RESULTS, "vitaldb_transitions2_plan.json"))
    ap.add_argument("--meta-out", default=os.path.join(RESULTS, "vitaldb_transitions2_meta.json"))
    ap.add_argument("--v1-plan", default=V1_PLAN)
    a = ap.parse_args(argv)

    print(f"fetching {API}/cases ...", flush=True)
    cases_text = _fetch(f"{API}/cases")
    cases_rows = list(csv.DictReader(io.StringIO(cases_text)))
    cases_cols = list(cases_rows[0].keys()) if cases_rows else []
    print(f"  /cases: {len(cases_rows)} rows, {len(cases_cols)} columns", flush=True)
    print(f"  columns: {cases_cols}", flush=True)

    print(f"fetching {API}/trks ...", flush=True)
    trks_text = _fetch(f"{API}/trks")
    trks_rows = list(csv.DictReader(io.StringIO(trks_text)))
    trks_cols = list(trks_rows[0].keys()) if trks_rows else []
    print(f"  /trks: {len(trks_rows)} rows, {len(trks_cols)} columns", flush=True)
    print(f"  columns: {trks_cols}", flush=True)

    by_case: dict = {}
    for r in trks_rows:
        by_case.setdefault(r["caseid"], {})[r["tname"]] = r["tid"]
    info = {r["caseid"]: r for r in cases_rows}

    n_all_cases = len(info)
    n_all_case_ids_in_trks = len(by_case)

    # step: has the EEG track the adapter actually uses
    has_eeg = sorted((cid for cid, tmap in by_case.items() if EEG_TRACK in tmap), key=lambda x: int(x))
    print(f"EEG_TRACK matched from bsde.ingestion.vitaldb.EEG_TRACK = {EEG_TRACK!r}", flush=True)
    print(f"all cases (rows in /cases): {n_all_cases}", flush=True)
    print(f"case ids appearing in /trks at all: {n_all_case_ids_in_trks}", flush=True)
    print(f"has {EEG_TRACK}: {len(has_eeg)}", flush=True)

    # step: has a usable aneend
    has_aneend = [cid for cid in has_eeg if cid in info and math.isfinite(_f(info[cid].get("aneend")))]
    print(f"has {EEG_TRACK} AND usable aneend: {len(has_aneend)}", flush=True)

    # measured, NOT filtered on: anestart usability within the final eligible set
    n_has_anestart = sum(1 for cid in has_aneend if math.isfinite(_f(info[cid].get("anestart"))))
    print(f"  of those, usable anestart: {n_has_anestart} ({100.0 * n_has_anestart / max(1, len(has_aneend)):.1f}%)",
          flush=True)

    # measured, NOT filtered on: ane_type distribution, and monitor-track presence, on the eligible set
    ane_type_counts: dict = {}
    n_has_bis_bis = n_has_bis_sqi = 0
    for cid in has_aneend:
        at = (info[cid].get("ane_type") or "").strip() or "(blank)"
        ane_type_counts[at] = ane_type_counts.get(at, 0) + 1
        tmap = by_case.get(cid, {})
        if "BIS/BIS" in tmap:
            n_has_bis_bis += 1
        if "BIS/SQI" in tmap:
            n_has_bis_sqi += 1
    print(f"  ane_type distribution on eligible set: {ane_type_counts}", flush=True)
    print(f"  of those, also has BIS/BIS: {n_has_bis_bis}; also has BIS/SQI: {n_has_bis_sqi}", flush=True)

    # ---- build the plan: emergence window always (aneend usable, by construction of has_aneend); ----
    # ---- induction window only where anestart is usable, exactly like v1 ----------------------------
    plan: dict = {}
    meta: dict = {}
    n_induction_planned = n_induction_kept = 0
    n_emergence_planned = n_emergence_kept = 0
    cases_with_induction_window = 0
    for cid in sorted(has_aneend, key=lambda x: int(x)):
        c = info[cid]
        ast, aet = _f(c.get("anestart")), _f(c.get("aneend"))
        tmap = by_case.get(cid, {})
        times = set()
        if math.isfinite(ast):
            ind = _window(ast)
            n_induction_planned += len(ind)
            kept = [t for t in ind if t >= 0.0]
            n_induction_kept += len(kept)
            if kept:
                cases_with_induction_window += 1
            times.update(kept)
        emg = _window(aet)
        n_emergence_planned += len(emg)
        kept = [t for t in emg if t >= 0.0]
        n_emergence_kept += len(kept)
        times.update(kept)
        if times:
            plan[cid] = sorted(times)
            meta[cid] = {
                "anestart_s": ast, "aneend_s": aet,
                "ane_type": c.get("ane_type", ""),
                "has_bis_bis": "BIS/BIS" in tmap,
                "has_bis_sqi": "BIS/SQI" in tmap,
            }

    n_new_cases = len(plan)
    n_new_windows = sum(len(v) for v in plan.values())
    print(f"newly-derived plan (before v1 union): {n_new_cases} cases, {n_new_windows} windows "
          f"({n_new_windows / max(1, n_new_cases):.1f} per case)", flush=True)
    print(f"  induction: planned {n_induction_planned}, survive t>=0 {n_induction_kept} "
          f"({cases_with_induction_window}/{n_new_cases} cases keep >=1 induction window)", flush=True)
    print(f"  emergence: planned {n_emergence_planned}, survive t>=0 {n_emergence_kept}", flush=True)

    # ---- union in v1's plan verbatim, so v1's exact windows for its 250 cases are preserved even if a ----
    # ---- fresh /cases pull produced a marginally different anestart/aneend for the same case id --------
    v1_path = os.path.abspath(a.v1_plan)
    n_v1_cases = n_v1_windows_added = n_v1_cases_new_to_plan = 0
    if os.path.exists(v1_path):
        v1_plan = json.load(open(v1_path))
        n_v1_cases = len(v1_plan)
        for cid, times in v1_plan.items():
            before = set(plan.get(cid, []))
            if cid not in plan:
                n_v1_cases_new_to_plan += 1
            after = before | set(times)
            n_v1_windows_added += len(after - before)
            plan[cid] = sorted(after)
            if cid not in meta:
                # v1 case that the fresh API pull did not classify as eligible (should not happen since v1's
                # own criteria are strictly stricter than this script's, but recorded defensively -- rule 5).
                meta[cid] = {"anestart_s": _f(None), "aneend_s": _f(None), "ane_type": "",
                             "has_bis_bis": None, "has_bis_sqi": None, "source": "v1_only"}
        print(f"unioned v1 plan ({v1_path}): {n_v1_cases} v1 cases, "
              f"{n_v1_cases_new_to_plan} of them were NOT already in this run's eligible set, "
              f"{n_v1_windows_added} windows added by the union", flush=True)
    else:
        print(f"WARNING: v1 plan not found at {v1_path} -- proceeding WITHOUT the union step "
              f"(the task requires keeping v1's 250 cases in the plan; this run could not verify that "
              f"they are present beyond whatever this script independently derived).", flush=True)

    tot_cases = len(plan)
    tot_windows = sum(len(v) for v in plan.values())

    meta["_summary"] = {
        "n_all_cases": n_all_cases,
        "n_case_ids_in_trks": n_all_case_ids_in_trks,
        "n_has_eeg_track": len(has_eeg),
        "n_has_eeg_and_usable_aneend": len(has_aneend),
        "n_has_usable_anestart_within_eligible": n_has_anestart,
        "ane_type_distribution_eligible": ane_type_counts,
        "n_has_bis_bis_within_eligible": n_has_bis_bis,
        "n_has_bis_sqi_within_eligible": n_has_bis_sqi,
        "n_v1_cases": n_v1_cases,
        "n_v1_cases_not_independently_eligible": n_v1_cases_new_to_plan,
        "final_plan_n_cases": tot_cases,
        "final_plan_n_windows": tot_windows,
        "window_geometry": {"pre_s": PRE_S, "post_s": POST_S, "step_s": STEP_S},
        "eeg_track": EEG_TRACK,
    }

    json.dump(plan, open(os.path.abspath(a.out), "w"))
    json.dump(meta, open(os.path.abspath(a.meta_out), "w"), indent=2, sort_keys=True)

    print(f"FINAL v2 plan: {tot_cases} cases, {tot_windows} total windows "
          f"({tot_windows / max(1, tot_cases):.1f} per case, step {STEP_S:.0f}s) -> {a.out}", flush=True)
    print(f"meta -> {a.meta_out}", flush=True)
    assert tot_cases > 0, "empty plan (rule 5)"
    assert tot_cases >= n_v1_cases, "v2 plan has FEWER cases than v1 -- the union step is broken"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
