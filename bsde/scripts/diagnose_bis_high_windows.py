"""What actually is a BIS >= 80 window inside a general anaesthetic? Measured, not assumed.

WHY THIS EXISTS. E22's machinery gate failed: among patients supplying both arms, the responsive windows
occurred later in the case in only 37.0 %, against a registered floor of 70 %. The first guess was that
light windows sit at the START of the recording, before the anaesthetic deepens. That guess was wrong in
its cause and the real answer is worse.

WHAT THE DATA SAYS. Of 168 windows at BIS >= 80 with the sensor attached, **164 sit INSIDE the anaesthetic
record**, between `anestart` and `aneend`. Four sit after `aneend`. None sits before `anestart`. So they are
not awake windows at either end of the case; they are high-BIS readings during maintenance.

The monitor's own channels say why. Inside the anaesthetic, split into EMG deciles:

    EMG decile   1   2   3   4   5   6   7   8      9        10
    P(BIS>=80)  0%  0%  0%  0%  0%  0%  0%  0%    0.5%     27.6%

**Every high-BIS window is in the top EMG decile.** Restricting the responsive arm to EMG <= 35 leaves 5
rows across 4 patients; adding SQI >= 90 leaves 2 rows in 1 patient. Median EMG is 49 in the responsive arm
against 27 in the unresponsive one, and median SQI is 70 against 93.

That is the classic BIS failure mode, demonstrated here on the device's own muscle channel rather than
argued from a spectral proxy: **frontalis EMG in the 70-110 Hz band inflates the index.** A BIS of 80 in a
paralysed-then-recovering patient under maintenance anaesthesia is a muscle reading, not a conscious one.

WHAT THIS COSTS. E22's responsive arm was, in substance, defined by facial muscle activity. Its gate failed
and the failure was correct — for a better reason than the gate itself tested. The same defect reaches E23,
whose arms are E22's by construction, and E24, whose emergence landmark is the first BIS >= 80 window and is
therefore the first big EMG burst.

**The deeper consequence, which contradicts a claim in `ingestion/vitaldb.py`'s own header.** That file
asserts "the transition available here is EMERGENCE, not induction", reasoning from `aneend` sitting
comfortably inside every track. The reasoning omits the monitor: the EEG runs past `aneend`, and the BIS
strip does not. With four post-`aneend` high-BIS windows in 250 cases, **emergence is not labelled in this
deposit either.** VitalDB captures maintenance, and only maintenance.

    python bsde/scripts/diagnose_bis_high_windows.py [--table bsde/results/vitaldb_grid.csv]
"""
from __future__ import annotations

import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.abspath(os.path.join(HERE, "..", "results", "vitaldb_grid.csv"))

BIS_HIGH = 80.0
CLEAN_EMG_MAX = 35.0
CLEAN_SQI_MIN = 90.0


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    table = os.path.abspath(argv[argv.index("--table") + 1]) if "--table" in argv else DEFAULT
    if not os.path.exists(table):
        print(f"missing {table}")
        return 2
    rows = [r for r in csv.DictReader(open(table, newline="")) if r.get("status") == "ok"]
    g = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)          # noqa: E731
    bis, sqi, emg = g("meta_bis"), g("meta_sqi"), g("meta_emg")
    ras, rae = g("meta_rel_anestart_s"), g("meta_rel_aneend_s")
    off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    subj = np.array([r.get("subject", "") for r in rows])

    live = ~off & np.isfinite(bis) & np.isfinite(emg) & np.isfinite(sqi)
    intra = live & (ras >= 0) & (rae < 0)
    high = live & (bis >= BIS_HIGH)

    print(f"WHAT IS A BIS >= {BIS_HIGH:.0f} WINDOW? — {os.path.basename(table)}, "
          f"{len(rows)} decoded windows, {len(set(subj))} patients\n")
    print(f"   windows at BIS >= {BIS_HIGH:.0f} with the sensor attached: {int(high.sum())}")
    print(f"      before anestart                 : {int((high & (ras < 0)).sum())}")
    print(f"      inside the anaesthetic record   : {int((high & (ras >= 0) & (rae < 0)).sum())}")
    print(f"      after aneend                    : {int((high & (rae >= 0)).sum())}")
    print("   (a high-BIS window that is neither before induction nor after emergence is, by elimination,")
    print("    a high reading during maintenance — which needs an explanation other than consciousness)\n")

    q = np.quantile(emg[intra], np.linspace(0, 1, 11))
    print("   inside the anaesthetic, by EMG decile:")
    print(f"      {'EMG range':>18s} {'n':>6s} {'P(BIS>=80)':>11s} {'median BIS':>11s} {'median SQI':>11s}")
    for i in range(10):
        m = intra & (emg >= q[i]) & ((emg <= q[i + 1]) if i == 9 else (emg < q[i + 1]))
        if not m.any():
            continue
        print(f"      {f'{q[i]:.1f}-{q[i + 1]:.1f}':>18s} {int(m.sum()):6d} "
              f"{np.mean(bis[m] >= BIS_HIGH):11.1%} {np.median(bis[m]):11.1f} {np.median(sqi[m]):11.1f}")

    try:
        from scipy.stats import spearmanr
        rho = spearmanr(bis[intra], emg[intra]).statistic
        print(f"\n   Spearman BIS vs EMG inside the anaesthetic: {rho:+.3f} over {int(intra.sum())} windows")
    except Exception:                                                        # noqa: BLE001
        pass

    print(f"\n   how many high-BIS windows survive a muscle filter?")
    for label, cond in (("all", high),
                        (f"SQI >= {CLEAN_SQI_MIN:.0f}", high & (sqi >= CLEAN_SQI_MIN)),
                        (f"EMG <= {CLEAN_EMG_MAX:.0f}", high & (emg <= CLEAN_EMG_MAX)),
                        ("both", high & (sqi >= CLEAN_SQI_MIN) & (emg <= CLEAN_EMG_MAX))):
        print(f"      {label:16s} rows {int(cond.sum()):5d}   patients {len(set(subj[cond])):4d}")
    print("\n   A responsive arm that survives a muscle filter in single figures is not a responsive arm.")
    print("   This is the documented BIS failure mode — frontalis EMG at 70-110 Hz inflates the index —")
    print("   shown here on the device's own muscle channel rather than argued from a spectral proxy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
