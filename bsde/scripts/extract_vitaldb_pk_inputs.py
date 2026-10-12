"""Pull the INFUSION RECORD and demographics VitalDB publishes, so an exposure model can be built here
rather than taken on trust from the pump.

WHY. Every VitalDB result in this project used a single-agent exposure taken straight from the device:
`Orchestra/PPF20_CE` (the pump's own modelled effect-site concentration) or `Primus/INSP_SEVO`. Two
problems with that, both raised by the investigator:

  * the pump's model is whichever one the pump implements, unstated in the deposit, and cannot be varied;
  * `INSP_SEVO` is INSPIRED gas -- what is delivered to the circuit -- while `EXP_SEVO` is END-TIDAL,
    which approximates alveolar and hence effect-site concentration and is what MAC is defined on. Both
    are recorded in the same 3,687 cases and this project used the wrong one.

With the RATE tracks, an effect-site concentration can be computed independently with any published model,
and the pump's own value becomes an external check rather than the input (see `PKPD_MODEL_REVIEW.md` §6.2:
validation must never touch BIS, because BIS is derived from the EEG under test).

WHAT IS PULLED, per case, as (time, value) pairs on the case's own clock:

    Orchestra/PPF20_RATE   propofol infusion rate, mL/h of 20 mg/mL      -- drives the PK
    Orchestra/PPF20_VOL    cumulative volume, mL                          -- an independent integral check
    Orchestra/PPF20_CE     the pump's effect-site concentration           -- THE VALIDATION TARGET
    Orchestra/PPF20_CP     the pump's plasma concentration
    Orchestra/RFTN20_RATE  remifentanil rate                              -- drives the opioid PK
    Orchestra/RFTN20_CE    the pump's opioid effect-site concentration
    Primus/EXP_SEVO        END-TIDAL sevoflurane                          -- replaces INSP_SEVO
    Primus/EXP_DES         END-TIDAL desflurane
    Primus/INSP_SEVO       inspired, kept only to MEASURE the gap this project has been living with
    Primus/INSP_DES        inspired, same reason
    Primus/MAC             the monitor's own MAC

plus age, sex, height, weight, bmi, asa from the clinical table -- every covariate the Eleveld models need.

SCOPE. This script extracts. It fits nothing, computes no concentration and makes no claim.

    python bsde/scripts/extract_vitaldb_pk_inputs.py --limit 5     # smoke
    python bsde/scripts/extract_vitaldb_pk_inputs.py --shard k --of 4
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.ingestion.vitaldb import API, _fetch, cases, tracks                # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
OUT = os.path.join(RESULTS, "vitaldb_pk_inputs.jsonl")
CASE_SOURCE = os.path.join(RESULTS, "vitaldb_grid.csv")

WANT = ["Orchestra/PPF20_RATE", "Orchestra/PPF20_VOL", "Orchestra/PPF20_CE", "Orchestra/PPF20_CP",
        "Orchestra/RFTN20_RATE", "Orchestra/RFTN20_CE",
        "Primus/EXP_SEVO", "Primus/EXP_DES", "Primus/INSP_SEVO", "Primus/INSP_DES", "Primus/MAC"]
DEMOG = ["age", "sex", "height", "weight", "bmi", "asa", "anestart", "aneend", "opstart", "opend"]


def numeric_series(tid: str):
    """(time, value) pairs from a NUMERIC track. Rows carry real timestamps; never read positionally --
    the waveform reader would misalign a numeric track by hours (the mistake `_bis_window` documents)."""
    t, v = [], []
    for line in _fetch(f"{API}/{tid}").splitlines()[1:]:
        a, _, b = line.partition(",")
        if not a or not b:
            continue
        try:
            ta, vb = float(a), float(b)
        except ValueError:
            continue
        if np.isfinite(ta) and np.isfinite(vb):
            t.append(ta); v.append(vb)
    return t, v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)

    want_cases = []
    seen = set()
    for r in csv.DictReader(open(CASE_SOURCE, newline="")):
        c = r.get("meta_caseid")
        if c and c not in seen:
            seen.add(c); want_cases.append(c)
    import glob
    for f in sorted(glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv"))):
        for r in csv.DictReader(open(f, newline="")):
            c = r.get("meta_caseid")
            if c and c not in seen:
                seen.add(c); want_cases.append(c)
    want_cases = [c for i, c in enumerate(sorted(want_cases)) if i % a.of == a.shard]

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                done.add(json.loads(line)["caseid"])
            except Exception:                                               # noqa: BLE001
                continue
    todo = [c for c in want_cases if c not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"shard {a.shard}/{a.of}: {len(want_cases)} cases with EEG features, {len(done)} done, "
          f"{len(todo)} to fetch -> {out_path}", flush=True)
    if not todo:
        return 0

    tmap = {}
    for r in tracks():
        if r["tname"] in WANT:
            tmap.setdefault(r["caseid"], {})[r["tname"]] = r["tid"]
    clin = cases()

    with open(out_path, "a") as fh:
        for i, c in enumerate(todo, 1):
            rec = {"caseid": c, "tracks": {}, "demog": {}, "status": "ok", "error": ""}
            try:
                d = clin.get(c, {})
                for k in DEMOG:
                    rec["demog"][k] = d.get(k, "")
                for name, tid in (tmap.get(c) or {}).items():
                    t, v = numeric_series(tid)
                    if t:
                        rec["tracks"][name] = {"t": t, "v": v, "n": len(t)}
            except Exception as e:                                          # noqa: BLE001
                rec["status"], rec["error"] = "error", f"{type(e).__name__}: {e}"
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if i % 10 == 0 or i == len(todo):
                print(f"   [{i}/{len(todo)}] {c} {rec['status']} "
                      f"tracks={len(rec['tracks'])}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
