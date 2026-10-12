"""Which licences does a result depend on? Answered by query, not by memory.

THE DECISION THIS SERVES. The programme's position is: make the scientific breakthrough on whatever data is
reachable, including non-commercial deposits, and build any commercial artefact later on a clean corpus.
**That is sound, and it rests on a distinction worth stating precisely: a DISCOVERY is not copyrightable.**
Learning that a feature tracks emergence carries no licence with it; only the data, and artefacts derived
from the data, do. So the later clean rebuild re-derives a known fact on clean inputs, which is a
straightforward thing to do — *provided you can still say which results came from which deposit.*

That proviso is the whole reason this module exists. It is cheap now and expensive to reconstruct later,
which is exactly the shape of thing that gets skipped.

WHAT IT DOES. Every feature table this project writes carries a `dataset` column, and every deposit has a row
in `data_registry/LICENSE_TABLE.csv`. This joins them, so "which licences does this result stand on, and
would it survive a commercial rebuild?" is a function call rather than an archaeology project.

THREE THINGS A LATER CLEAN REBUILD DOES NOT UNDO, which is why the answer is not simply "defer everything":

  1. **ShareAlike propagating into a derived artefact.** If a model's weights are Adapted Material under
     CC BY-NC-SA, retraining later helps only if the new artefact is genuinely independent — not initialised
     from the old weights, not architecture-selected or hyperparameter-tuned on the restricted data. The
     knowledge transfers freely; the artefact may not.
  2. **Public disclosure.** This repository is public, so every commit is a disclosure with a date on it.
     That clock is a patent matter, entirely separate from licensing, and no licence choice affects it.
  3. **Data use agreements are contracts, not licences.** Bath and the MGH GABA dataset require signed
     undertakings limiting use to an approved scope. A breach is not cured by later retraining, and it can
     foreclose future access from that group and its collaborators. Where this project has declared a
     non-commercial scope in writing — as in the Bath access request — that declaration has to stay true.

`UNVERIFIED` is preserved and never silently read as permission. A deposit whose terms have not been read
end-to-end reports as unknown, because "the bucket was public" is not a licence.
"""
from __future__ import annotations

import csv
import os
from typing import Dict, Iterable, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_CSV = os.path.abspath(os.path.join(HERE, "..", "..", "data_registry", "LICENSE_TABLE.csv"))

DATASET_TO_REGISTRY = {
    "chennu": "chennu_propofol",
    "chennu_propofol": "chennu_propofol",
    "ds005620": "openneuro_ds005620",
    "ds004541": "openneuro_ds004541",
    "ds007554": "openneuro_ds007554",
    "sleep_edfx": "physionet_sleep_edfx",
    "sleep_edfx_staged": "physionet_sleep_edfx",
    "sleep_edfx_five_stage": "physionet_sleep_edfx",
    "sleep_edfx_multiwindow": "physionet_sleep_edfx",
    "hbn_resting": "hbn",
    "vitaldb": "vitaldb",
    "icare": "icare",
    "figshare_doc_rest": "figshare_doc_rest",
    "figshare_23552964": "figshare_doc_rest",   # the table carries the article id, not the slug
    "bath_pdoc": "bath_pdoc_mi",
}
"""The `dataset` column value a table carries -> the registry key. Explicit rather than fuzzy-matched: a
near-miss here would silently report the wrong licence, which is worse than reporting none."""


def load_registry(path: str = REGISTRY_CSV) -> Dict[str, dict]:
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as fh:
        return {r["dataset_id"]: r for r in csv.DictReader(fh)}


def licence_for(dataset: str, registry: Optional[Dict[str, dict]] = None) -> dict:
    """The registry row for a table's `dataset` value, or an explicit unknown.

    An unmapped dataset returns `commercial_use='UNVERIFIED'` rather than raising or defaulting to
    permissive: a new deposit that nobody added to the registry must not read as clean.
    """
    reg = registry if registry is not None else load_registry()
    key = DATASET_TO_REGISTRY.get(dataset)
    if key is None or key not in reg:
        return {"dataset_id": f"UNMAPPED:{dataset}", "license_name": "UNVERIFIED — not in the registry",
                "commercial_use": "UNVERIFIED", "share_alike": "UNVERIFIED", "dua_required": "UNVERIFIED"}
    return reg[key]


def datasets_in_table(csv_path: str) -> List[str]:
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="") as fh:
        return sorted({(r.get("dataset") or "").strip()
                       for r in csv.DictReader(fh) if (r.get("dataset") or "").strip()})


def audit(csv_paths: Iterable[str]) -> dict:
    """Licence exposure of a set of feature tables.

    `commercially_clean` is True only when EVERY contributing deposit says `commercial_use == 'YES'`.
    UNVERIFIED counts against it, deliberately: the question being asked is "can this be rebuilt for a
    commercial artefact without further work", and an unread licence means the answer is not yet yes.
    """
    reg = load_registry()
    per_table, blockers, unverified = {}, set(), set()
    for p in csv_paths:
        ds = datasets_in_table(p)
        rows = []
        for d in ds:
            lic = licence_for(d, reg)
            rows.append({"dataset": d, "registry_id": lic.get("dataset_id"),
                         "license": lic.get("license_name"), "commercial": lic.get("commercial_use"),
                         "share_alike": lic.get("share_alike"), "dua": lic.get("dua_required")})
            if lic.get("commercial_use") == "NO":
                blockers.add(lic.get("dataset_id"))
            elif lic.get("commercial_use") != "YES":
                unverified.add(lic.get("dataset_id"))
        per_table[os.path.basename(p)] = rows
    return {"per_table": per_table,
            "commercial_blockers": sorted(blockers),
            "unverified": sorted(unverified),
            "commercially_clean": not blockers and not unverified}


def main(argv: Optional[List[str]] = None) -> int:
    import glob
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    paths = argv or sorted(glob.glob(os.path.join(HERE, "..", "..", "results", "*.csv")))
    rep = audit(paths)
    print("PROVENANCE AUDIT — which licences do these results stand on?\n")
    for tbl, rows in sorted(rep["per_table"].items()):
        if not rows:
            continue
        print(f"  {tbl}")
        for r in rows:
            print(f"      {r['dataset']:24s} -> {str(r['registry_id']):22s} "
                  f"commercial={r['commercial']:11s} SA={r['share_alike']:16s} dua={r['dua']}")
    print(f"\n  commercial blockers (commercial_use = NO): {rep['commercial_blockers'] or 'none'}")
    print(f"  unverified (terms not read end-to-end)   : {rep['unverified'] or 'none'}")
    print(f"\n  commercially clean as it stands: {rep['commercially_clean']}")
    if not rep["commercially_clean"]:
        print("  -> the SCIENCE is unaffected; this says only that a commercial artefact would need to be")
        print("     rebuilt from the clean subset, and it names exactly which deposits to exclude.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
