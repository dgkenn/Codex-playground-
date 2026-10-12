"""Attach the ADMINISTERED drug axis to the VitalDB grid table. No EEG is re-read.

WHY THIS EXISTS. E22 closed at its gate because every BIS >= 80 window in this deposit is a facial-EMG
artefact (`scripts/diagnose_bis_high_windows.py`): P(BIS >= 80) is 0.0 % in EMG deciles 1-8 and 27.6 % in
decile 10. Any depth axis computed from the EEG, or from a monitor computed from the EEG, inherits that.
**The axis has to come from outside the signal**, and VitalDB records what was actually given:

    Primus/MAC            6,338 cases   age-adjusted minimum alveolar concentration
    Primus/INSP_SEVO      3,687 cases   inspired sevoflurane, %
    Primus/INSP_DES       2,046 cases   inspired desflurane, %
    Orchestra/PPF20_CE    3,511 cases   propofol effect-site concentration, ug/mL (TCI model)
    Orchestra/RFTN20_CE   4,771 cases   remifentanil effect-site concentration, ng/mL

**MAC is the reason this pivot is worth making rather than merely available.** It is the standard normalised
potency scale for volatile anaesthetics — 1.0 MAC is, by definition, the concentration at which half of
patients do not move to a skin incision — so sevoflurane and desflurane land on ONE axis without any fitting
on our part. A cross-drug depth comparison is what Challenge A asks for, and MAC supplies its x-axis from
pharmacology rather than from the EEG.

FOUR LIMITS, STATED HERE SO THEY TRAVEL WITH THE COLUMNS.

  1. **Dose is not consciousness.** MAC and effect-site concentration are what was administered, not what
     the patient experienced. Individual sensitivity varies severalfold. Any claim built on these columns is
     about tracking anaesthetic DOSE, which is a narrower and cleaner question than tracking consciousness,
     and must be worded that way.
  2. **MAC and propofol Ce are not on a common scale.** They cannot be pooled into one regression. A
     cross-drug comparison using both is a comparison of ASSOCIATION STRENGTH in two arms, never of a shared
     threshold.
  3. **Opioids reduce MAC requirement, substantially.** `Orchestra/RFTN20_CE` is carried for exactly that
     reason: a case run at 0.7 MAC with a high remifentanil infusion is not lighter than one at 1.0 MAC
     without it. Ignoring the opioid would make MAC look like a noisier depth axis than it is.
  4. **These are device readings, with the device's own gaps.** A value is the mean over the same 30 s
     window the features were computed on, and NaN where the track has no rows there. Nothing is
     interpolated across a gap, because a gap in an infusion record is informative.

WHAT IT DOES. Reads `vitaldb_grid.csv`, fetches the five numeric tracks for each case it names, and writes
`vitaldb_agents.csv` keyed by `recording_id` so it joins onto the feature table without touching it. The
feature table is not modified and no candidate is recomputed — the EEG work is already done and this only
adds columns alongside it.

Cheap: numeric tracks are a few thousand rows each, against a 9.4 MB waveform. Resumable — re-running
fetches only the cases not already present.

    python bsde/scripts/join_vitaldb_agents.py
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import numpy as np                                                            # noqa: E402

from bsde.ingestion.vitaldb import API, _fetch, cases, tracks                  # noqa: E402

AGENT_TRACKS = {
    "mac": "Primus/MAC",
    "insp_sevo": "Primus/INSP_SEVO",
    "insp_des": "Primus/INSP_DES",
    "ppf_ce": "Orchestra/PPF20_CE",
    "rftn_ce": "Orchestra/RFTN20_CE",
}
WINDOW_S = 30.0
"""The same window the features were computed over. Any other value would silently compare a feature from
one interval against a dose from another."""


def _numeric(tid: str):
    pairs = []
    for line in _fetch(f"{API}/{tid}").splitlines()[1:]:
        a, _, b = line.partition(",")
        if a and b:
            try:
                pairs.append((float(a), float(b)))
            except ValueError:
                pass
    return np.asarray(pairs, float) if pairs else np.zeros((0, 2))


def _mean_in(arr, t0: float) -> float:
    if arr is None or not arr.size:
        return float("nan")
    v = arr[(arr[:, 0] >= t0) & (arr[:, 0] < t0 + WINDOW_S), 1]
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--grid", default=os.path.join(HERE, "..", "results", "vitaldb_grid.csv"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results", "vitaldb_agents.csv"))
    a = ap.parse_args(argv)
    grid, out = os.path.abspath(a.grid), os.path.abspath(a.out)
    if not os.path.exists(grid):
        print(f"missing {grid}")
        return 2

    rows = list(csv.DictReader(open(grid, newline="")))
    want = {}
    for r in rows:
        cid = (r.get("meta_caseid") or "").strip()
        try:
            t = float(r.get("meta_t_s", ""))
        except (TypeError, ValueError):
            continue
        if cid:
            want.setdefault(cid, []).append((r["recording_id"], t))
    print(f"   {len(rows)} grid rows over {len(want)} cases", flush=True)

    fields = ["recording_id", "caseid", "t_s"] + list(AGENT_TRACKS) + ["agent_tracks_present"]
    done = set()
    if os.path.exists(out) and os.path.getsize(out) > 0:
        with open(out, newline="") as fh:
            rd = csv.DictReader(fh)
            if list(rd.fieldnames or []) != fields:
                print(f"   {out} exists with a different column set; refusing to append.")
                return 1
            done = {r["caseid"] for r in rd}
        print(f"   resuming: {len(done)} cases already present", flush=True)

    by_case = {}
    for t in tracks():
        by_case.setdefault(t["caseid"], {})[t["tname"]] = t["tid"]
    info = cases()

    todo = [c for c in sorted(want, key=lambda z: int(z)) if c not in done]
    new_file = not os.path.exists(out) or os.path.getsize(out) == 0
    with open(out, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new_file:
            w.writeheader()
        for i, cid in enumerate(todo, 1):
            tmap = by_case.get(cid, {})
            series, present = {}, []
            for key, tname in AGENT_TRACKS.items():
                tid = tmap.get(tname)
                if not tid:
                    series[key] = None
                    continue
                try:
                    series[key] = _numeric(tid)
                    present.append(key)
                except Exception as e:                                        # noqa: BLE001
                    print(f"      case {cid} {tname}: {type(e).__name__}", flush=True)
                    series[key] = None
            for rid, t in want[cid]:
                row = {"recording_id": rid, "caseid": cid, "t_s": f"{t}",
                       "agent_tracks_present": "|".join(sorted(present))}
                for key in AGENT_TRACKS:
                    row[key] = f"{_mean_in(series[key], t)}"
                w.writerow(row)
            fh.flush()
            if i % 10 == 0 or i == len(todo):
                print(f"   [{i}/{len(todo)}] case {cid}", flush=True)
            if not info.get(cid):
                print(f"      note: case {cid} is absent from the cases table", flush=True)
    print(f"   wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
