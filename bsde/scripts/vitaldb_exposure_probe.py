#!/usr/bin/env python3
"""Fetch NON-EEG drug exposure at the two window states, for every landmarked single-agent case.

WHY. E295 tried to rule out circularity in the depth gradient by stratifying on a muscle channel instead
of BIS, and failed: `emg_index` is itself depth-related, so it reproduced 56 % of the gradient. Every
depth axis used so far is derived from the same EEG as the candidates. This script supplies one that is
not: the anaesthesia machine's own record of how much drug the patient is receiving.

    volatiles  Primus/MAC          -- minimum alveolar concentration, already EQUIPOTENT across
                                       sevoflurane and desflurane by construction
    propofol   Orchestra/PPF20_CE  -- Schnider effect-site concentration from the TCI pump

NO CROSS-DRUG POTENCY CONSTANT IS ASSUMED OR NEEDED. The analysis converts each case's exposure to a
percentile WITHIN ITS OWN ARM, giving a unitless "how deep is this case for this drug" axis on which
volatile and intravenous cases are comparable without equating MAC to ug/mL. That avoids the
non-equipotence problem (Kuizenga 2019) rather than trying to solve it.

Emits one row per case: exposure at the maintenance (control) window centre and at the pre-landmark
window, plus coverage diagnostics. Resumable; writes to a CSV that is appended and fsynced per row.
"""
from __future__ import annotations

import argparse, csv, gzip, io, json, math, os, sys, time, urllib.request

API = "https://api.vitaldb.net"
VOL = ("Primus/MAC",)
IV = ("Orchestra/PPF20_CE",)


def get(url, timeout=120, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bsde/1.0"})
            b = urllib.request.urlopen(req, timeout=timeout).read()
            return gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 ** k)


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def series(tid):
    """Return (times, values) for a numeric track, dropping non-finite values."""
    txt = get(f"{API}/{tid}").decode("utf-8-sig", "replace")
    ts, vs = [], []
    for row in csv.reader(io.StringIO(txt)):
        if len(row) < 2:
            continue
        t, v = f(row[0]), f(row[1])
        if math.isfinite(t) and math.isfinite(v):
            ts.append(t); vs.append(v)
    return ts, vs


def near(ts, vs, t0, halfwidth=150.0):
    """Median of the track within +-halfwidth of t0. NaN if nothing in range."""
    sel = [v for t, v in zip(ts, vs) if abs(t - t0) <= halfwidth]
    if not sel:
        return float("nan")
    sel.sort()
    return sel[len(sel) // 2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--landmarks", default="bsde/results/vitaldb_vent_landmarks.s*.csv")
    ap.add_argument("--ctrl-plan", default="bsde/results/vitaldb_ctrlwin_plan.json")
    ap.add_argument("--out", default="bsde/results/vitaldb_exposure.csv")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args()

    import glob
    lm = {}
    for p in sorted(glob.glob(a.landmarks)):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ("sevo", "des", "ppf"):
                lm[r["caseid"]] = r
    plan = json.load(open(a.ctrl_plan)) if os.path.exists(a.ctrl_plan) else {}
    ctr = {k: (v[0] + v[-1]) / 2.0 for k, v in plan.items()}

    trks = {}
    for row in csv.DictReader(io.StringIO(get(f"{API}/trks").decode("utf-8-sig", "replace"))):
        trks.setdefault(row["caseid"], {})[row["tname"]] = row["tid"]

    done = set()
    if os.path.exists(a.out):
        for r in csv.DictReader(open(a.out)):
            done.add(r["caseid"])
    cases = [c for i, c in enumerate(sorted(lm, key=int))
             if i % a.of == a.shard and c not in done]
    print(f"[exposure] {len(cases)} cases to do (shard {a.shard}/{a.of}); {len(done)} already present")

    hdr = ["caseid", "arm", "track", "exp_ctrl", "exp_pre", "t_ctrl", "t_pre", "n_samples", "note"]
    new = not os.path.exists(a.out)
    fh = open(a.out, "a", newline="")
    w = csv.writer(fh)
    if new:
        w.writerow(hdr); fh.flush(); os.fsync(fh.fileno())

    for n, cid in enumerate(cases, 1):
        r = lm[cid]
        arm = r["arm"]
        want = IV if arm == "ppf" else VOL
        tid = None; tname = ""
        for t in want:
            if t in trks.get(cid, {}):
                tid, tname = trks[cid][t], t
                break
        trec = f(r.get("t_rec_s"))
        tc = ctr.get(cid, float("nan"))
        if tid is None:
            w.writerow([cid, arm, "", "", "", tc, trec, 0, "no track"])
        else:
            try:
                ts, vs = series(tid)
                w.writerow([cid, arm, tname,
                            near(ts, vs, tc) if math.isfinite(tc) else "",
                            near(ts, vs, trec - 150.0) if math.isfinite(trec) else "",
                            tc, trec, len(ts), ""])
            except Exception as e:
                w.writerow([cid, arm, tname, "", "", tc, trec, 0, f"error: {type(e).__name__}"])
        fh.flush(); os.fsync(fh.fileno())
        if n % 100 == 0:
            print(f"   [{n}/{len(cases)}]", flush=True)
    fh.close()
    print("[exposure] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
