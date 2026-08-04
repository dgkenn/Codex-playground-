"""E111 -- Does irreversibility BELOW the muscle band still place REM with sleep?

REGISTERED WHILE THE BAND-RESOLVED EXTRACTION IS RUNNING and before any banded stage contrast exists.

=========================================================================================================
THE BLOCKER THIS ATTACKS, IN NUMBERS
=========================================================================================================
E107 was the sharpest test this project has run and it went against a second axis. A measure PROVABLY
orthogonal to the whole power spectrum placed REM at position **+0.9974** on the wake-to-N3 axis -- deeper
than the aperiodic exponent's +0.4788 -- with P1 = +1.4539 [+1.0166, +2.2259], all four secondaries
agreeing and two putting REM past N3.

**But G5 showed 81 % of it is shared with submental EMG**: after within-subject residualisation P1 fell
from +1.4539 to +0.2739 [+0.0759, +0.4445], and submental EMG's own REM position is +0.9886 -- almost
exactly where irreversibility puts it. Since the permutation form CANNOT be muscle amplitude (it uses only
sample orderings), what it reads must be muscle WAVEFORM SHAPE.

**Muscle has a spectral address.** Surface EMG is overwhelmingly a high-frequency, broadband phenomenon;
cortical rhythms are not. So a band restriction is a direct, physical way to remove muscle from the
measurement rather than adjusting for it after the fact -- and adjusting after the fact is what every
previous attempt did, including E107's own G5. This is rule 54's discipline (a named confound with no
corresponding line of code is an unnamed confound wearing a disclaimer) applied by moving the confound out
of the instrument instead of into a covariate.

=========================================================================================================
DESIGN -- E107's ANALYSIS, UNCHANGED, ON BAND-RESTRICTED SIGNALS
=========================================================================================================
Two new extractions of the same 710 windows, same code path, differing only in a zero-phase band-pass
applied before measurement (zero-phase matters and is not a detail: a causal filter imposes its own
group-delay asymmetry, which is exactly the quantity being measured, so `filtfilt` is required rather than
preferred). The surrogate is built from the ALREADY-FILTERED signal, so real-minus-surrogate remains free
of spectral content inside the band.

    LOW  0.5-12 Hz   -- below surface EMG. THE PRIMARY.
    HIGH 20-45 Hz    -- the muscle band. A POSITIVE CONTROL for the band split, not a candidate.

    P1  paired d_z of position(frontal_irr3_net | 0.5-12 Hz) - position(whole_head_exponent),
        identical statistic and identical gates to E107.

VERDICT, wrong direction FIRST (rule 37):

    (a) P1 excludes 0 and POSITIVE -> STILL DEEPER THAN THE EXPONENT, WITHOUT MUSCLE. The single-axis
        reading survives the strongest remaining objection to E107 and becomes very hard to escape: a
        provably non-spectral measure, restricted below the muscle band, still orders REM with sleep.
    (b) P1 includes 0 -> THE MUSCLE BAND WAS CARRYING E107. Irreversibility below 12 Hz orders REM exactly
        as the exponent does; E107's dramatic +1.4539 was a muscle effect and must be re-described.
    (c) P1 excludes 0 and NEGATIVE -> REM MOVES TOWARD WAKE ONCE MUSCLE IS FILTERED OUT. The first
        evidence of a second axis in this project, obtained by removing the confound rather than
        adjusting for it. G5 still has to hold.

PREDICTED: (a) at ~45 %, (b) at ~40 %, (c) at ~15 %. E107's own G5 is the reason (c) is not lower --
something survived EMG adjustment there, at +0.2739 -- and the reason it is not higher is that the same
adjustment removed four-fifths.

=========================================================================================================
GATES -- E107's five, unchanged, plus the one this design needs
=========================================================================================================
G1-G5 are E107's and are applied by running E107's own code (rule 20: the analysis is not reimplemented,
it is the same object in memory with a different input table).

    G6  THE BAND SPLIT MUST DO WHAT IT CLAIMS. The 20-45 Hz measure must be MORE EMG-dependent than the
        0.5-12 Hz measure, quantified as the drop in P1 under EMG residualisation in each band. **If the
        low band is just as muscle-dependent as the muscle band, the filter has not separated anything**
        and the primary is not interpretable as muscle-free -- report ABSENT rather than a verdict
        (rule 31). This is the gate that distinguishes a real physical control from a hopeful one, and it
        is the reason the 20-45 Hz arm is extracted at all.

SCOPE. Unchanged from E107: Sleep-EDFx, two bipolar derivations, no dream reports, SC4001E0 excluded. A
REM placement nearer wake would be a fact about this measure on this deposit and NOT evidence of
experience; nothing here detects or measures consciousness.
"""
from __future__ import annotations

import json
import os

import numpy as np

from bsde.experiments import e107_irreversibility_rem as e107

RESULTS = e107.RESULTS
LOW_BAND, HIGH_BAND = "0.5-12", "20-45"


def _run(band):
    """E107's analysis, unchanged, on one band's table. Returns its result dict or None."""
    tbl = os.path.join(RESULTS, f"sleep_edfx_irreversibility.band{band}.csv")
    if not os.path.exists(tbl):
        print(f"ABSENT: {tbl}")
        return None
    e107.IRR = tbl
    e107.OUT = os.path.join(RESULTS, f"e111_irreversibility_band{band}.json")
    print(f"\n{'=' * 95}\nBAND {band} Hz  ->  {os.path.basename(e107.OUT)}\n{'=' * 95}")
    e107.main()
    try:
        return json.load(open(e107.OUT))
    except Exception:                                                       # noqa: BLE001
        return None


def main() -> int:
    out = {"bands": {}}
    for band in (LOW_BAND, HIGH_BAND):
        r = _run(band)
        if r is None:
            print("\nVERDICT: ABSENT -- band-resolved extraction has not landed")
            return 2
        out["bands"][band] = r

    lo, hi = out["bands"][LOW_BAND], out["bands"][HIGH_BAND]

    def drop(res):
        """Fraction of P1 removed by EMG residualisation. 1.0 = entirely muscle, 0.0 = none."""
        p = res.get("primary", {}).get("d_z", float("nan"))
        g = res.get("gates", {}).get("G5", {}).get("d_z_after_emg", float("nan"))
        if not (np.isfinite(p) and np.isfinite(g)) or abs(p) < 1e-9:
            return float("nan")
        return float(1.0 - g / p)

    d_lo, d_hi = drop(lo), drop(hi)
    g6 = bool(np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo)
    out["G6"] = {"emg_dependence_low": d_lo, "emg_dependence_high": d_hi, "pass": g6}
    print(f"\n{'=' * 95}\nG6 BAND SEPARATION -- fraction of P1 removed by EMG residualisation")
    print(f"   {LOW_BAND:>7s} Hz  {d_lo:6.1%}      {HIGH_BAND:>7s} Hz  {d_hi:6.1%}      "
          f"{'PASS -- the filter separated muscle' if g6 else 'FAIL -- the filter separated nothing'}")

    p1 = lo.get("primary", {})
    point, plo, phi = p1.get("d_z"), p1.get("lo"), p1.get("hi")
    med = p1.get("median_pos_primary")
    inside = lo.get("placebo", {}).get("inside", True)
    gates_ok = all(lo.get("gates", {}).get(k, False)
                   for k in ("G1_pass", "G3_pass", "G4_pass"))
    print(f"\nPRIMARY (band {LOW_BAND} Hz)  d_z {point:+.4f} [{plo:+.4f}, {phi:+.4f}]   "
          f"median REM position {med:+.4f}")

    if not gates_ok:
        v = f"ABSENT -- E107's own gates failed on the {LOW_BAND} Hz table; nothing was tested (rule 31)."
    elif not g6:
        v = (f"ABSENT -- G6 FAILED. The {LOW_BAND} Hz measure is as EMG-dependent ({d_lo:.1%}) as the "
             f"{HIGH_BAND} Hz muscle band ({d_hi:.1%}), so the band restriction did not separate muscle "
             f"and the primary cannot be read as muscle-free (rule 31).")
    elif inside:
        v = "WITHDRAWN BY PLACEBO -- permuting stage labels reproduces the difference."
    elif plo <= 0.0 <= phi:
        v = (f"THE MUSCLE BAND WAS CARRYING E107 -- below 12 Hz, irreversibility orders REM the same way "
             f"the aperiodic exponent does (d_z {point:+.4f} [{plo:+.4f}, {phi:+.4f}]). E107's +1.4539 "
             f"was substantially a muscle effect and must be re-described as one.")
    elif point > 0:
        v = (f"STILL DEEPER THAN THE EXPONENT, WITHOUT MUSCLE -- a provably non-spectral measure, "
             f"restricted below the muscle band, still places REM at {med:+.4f} and still further from "
             f"wake than the exponent (d_z {point:+.4f} [{plo:+.4f}, {phi:+.4f}]). The single-axis "
             f"reading survives the strongest remaining objection to E107 and is now very hard to escape.")
    else:
        v = (f"REM MOVES TOWARD WAKE ONCE MUSCLE IS FILTERED OUT -- d_z {point:+.4f} "
             f"[{plo:+.4f}, {phi:+.4f}], median REM position {med:+.4f}. First evidence of a second axis "
             f"in this project, obtained by REMOVING the confound rather than adjusting for it. Scope is "
             f"unchanged: no dream reports exist in this deposit and nothing here detects consciousness.")
    out["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(out, open(os.path.join(RESULTS, "e111_irreversibility_below_muscle.json"), "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
