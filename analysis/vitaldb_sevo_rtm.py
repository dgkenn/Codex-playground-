#!/usr/bin/env python3
"""SEVOFLURANE replication re-run under the RTM-IMMUNE estimator.

`analysis/vitaldb_sevo_validation.py` replicated the finding in the volatile cohort using the ORIGINAL model
specification (MAP entered linearly). That specification is now known to carry a regression-to-the-mean artefact
(see `analysis/vitaldb_rtm_hardening.py`), so the replication has to be re-run under the hardened estimator or it
inherits the same flaw. Same design as the propofol hardening:

    exposure : any burst suppression in the bin vs none (raw-EEG detector)
    outcome  : MAP < 65 mmHg at t + k, ABSOLUTE time index
    strata   : exact 2 mmHg bins of CURRENT MAP -- regression to the mean held constant by design
    pooling  : Mantel-Haenszel;  CIs from a CASE-level cluster bootstrap
    controls : backward lags (-2, -4) for temporal precedence

A replication only counts if it reproduces the hardened estimate, not the inflated one.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vitaldb_rtm_hardening import mh_or, boot_ci  # noqa: E402

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")


def load():
    """caseid -> {bin_t: (bs, mbp, et_sevo)};  the `ce` column carries end-tidal sevoflurane %."""
    HD = defaultdict(dict); seen = set()
    with open(f"{DATA}/sevo_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = (float(d["bs"]),
                              float(d["mbp"]) if d["mbp"] else np.nan,
                              float(d["ce"]) if d["ce"] else np.nan)
            except Exception:
                pass
    return HD


def build(HD, lag_bins):
    case = []; phen = []; strat = []; expo = []; out = []
    ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        bv = [bd[t][1] for t in ts[:10] if bd[t][1] == bd[t][1]]
        if len(bv) < 5:
            continue
        b0 = float(np.median(bv))
        for t in ts[20:]:
            t2 = t + 30.0 * lag_bins
            if t2 not in bd:
                continue
            bs, m, _ = bd[t]; m2 = bd[t2][1]
            if m != m or m2 != m2:
                continue
            if m >= b0:
                ph = 1
            elif m < 0.9 * b0:
                ph = 0
            else:
                continue
            if c not in ci:
                ci[c] = len(ci)
            case.append(ci[c]); phen.append(ph)
            strat.append(int(np.clip(m, 30, 160) // 2))
            expo.append(1 if bs > 0 else 0); out.append(1 if m2 < 65 else 0)
    return (np.array(case, np.int32), np.array(phen, np.int8), np.array(strat, np.int16),
            np.array(expo, np.int8), np.array(out, np.int8), len(ci))


def main():
    HD = load()
    print(f"SEVOFLURANE cohort: {len(HD)} cases")
    print("Mantel-Haenszel, exact 2 mmHg strata on current MAP; CIs = case-level cluster bootstrap.")
    print(f"\n{'lag':>6s}  {'phenotype':38s} {'MH OR':>7s}  {'95% CI':>18s}  {'bins':>8s} {'cases':>6s}")
    for lag in (2, 4, -2, -4):
        case, phen, strat, expo, out, ncase = build(HD, lag)
        if not len(case):
            continue
        for ph, nm in ((1, "MAP >= own baseline (sensitivity)"), (0, "MAP <  own baseline (hypoperfusion)")):
            s = phen == ph
            if s.sum() < 500 or out[s].sum() < 25 or expo[s].sum() < 25:
                print(f"{lag:+6d}  {nm:38s} insufficient (bins={int(s.sum())}, exposed={int(expo[s].sum())})")
                continue
            uniq, remap = np.unique(case[s], return_inverse=True)
            orv = mh_or(strat[s], expo[s], out[s])
            lo, hi, nb = boot_ci(remap.astype(np.int32), strat[s], expo[s], out[s], len(uniq))
            sig = "*" if (lo == lo and (lo > 1 or hi < 1)) else "ns"
            print(f"{lag:+6d}  {nm:38s} {orv:7.2f}  [{lo:5.2f},{hi:5.2f}] {sig:>3s}  "
                  f"{int(s.sum()):8d} {len(uniq):6d}")


if __name__ == "__main__":
    sys.exit(main())
