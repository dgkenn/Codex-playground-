#!/usr/bin/env python3
"""E59 -- computational layer. Does this repo's SyncFastSlow agree with an INDEPENDENT implementation?

REGISTERED BEFORE ANY CORRELATION BETWEEN THE TWO IMPLEMENTATIONS HAS BEEN COMPUTED. `dosei_sfs_check.csv`
exists for two pilot recordings at the time of writing (604 windows), produced only to time the extractor
and confirm the timestamp join lands. No column has been correlated with any other.

=========================================================================================================
WHY THIS EXPERIMENT EXISTS
=========================================================================================================
Rule 23: **self-written code plus self-written tests share blind spots.** `bis_subparams.sync_fast_slow` is
the first genuinely bispectral quantity in this repo -- every other feature here is spectral or
amplitude-based -- and E58 has already used it to produce a number. Its 18 unit tests are mine, built from
my own reading of the definition, and a misreading would pass all of them.

DOSE-I ships an independent implementation. `pEEG_parameter_description.txt`, verbatim:

    Column 33: SynchFastSlow according to Miller et al. (2004), log of bispectral power quotient 40-47 Hz
               over 1-47 Hz, see also Rampil et al. (1998)
    Column 35: PowerFastSlow according to Miller et al. (2004), log of power quotient 40-47 Hz over 1-47 Hz

**THE SIGN IS FIXED BY THAT SENTENCE AND NOT BY ANY DATA.** Their quotient is 40-47 over the whole range;
this repo implemented Rampil's, the whole range over 40-47. One is the reciprocal of the other, so the log
quantities must be strongly NEGATIVELY related. Predicting the sign from the documentation, before looking,
is what makes this a test rather than a description -- and it is a test the implementation can fail in two
distinct ways, enumerated in the verdict rule below.

Column 35 is the second gift and it is why this is worth more than a correctness check: it is a PURE POWER
ratio over the identical bands. If the agreement between the two SFS implementations survives partialling
out the power ratio, the bispectral machinery is doing bispectral work. If it does not, then whatever both
implementations are measuring, they are measuring it through power, and rule 28 applies -- two measurements
separated by method are not thereby measuring different things.

=========================================================================================================
DESIGN
=========================================================================================================
DATA. `results/dosei_sfs_check.csv`, built by `scripts/extract_dosei_sfs.py`: this repo's
`sync_fast_slow` over a 30 s window ENDING at each depositor timestamp, every 5th second, at the shipped
defaults (nfft=256, 0.5-47 Hz over 40-47 Hz). **The defaults are used deliberately.** Matching their band
edges first would be tuning the instrument to the reference before measuring the agreement.

ALIGNMENT was fixed in the extractor before any correlation existed: causal windows, absolute-timestamp
join, no lag search anywhere. P1 tests it directly.

UNIT OF ANALYSIS IS THE RECORDING. Consecutive seconds within a recording are massively autocorrelated, so
a pooled correlation over 10,000 windows would have an effective n of a few dozen. Every statistic below is
computed WITHIN recording and then summarised across recordings, with a recording-clustered bootstrap.

  M1 COVERAGE GATE  >= `MIN_RECORDINGS` recordings, each with >= `MIN_WINDOWS` windows where both
                    implementations are finite. Below that the summary is over too few units to read.

  V1 PRIMARY        median across recordings of Spearman(mine, theirs).
                    **PREDICTED STRONGLY NEGATIVE**, from the parameter description alone.

  V2 SPECIFICITY    median across recordings of partial Spearman(mine, theirs | their PowerFastSlow).
                    Reported whatever V1 says. This is not a gate on V1; it is a separate question about
                    what the agreement is made of.

  P1 PLACEBO        this repo's series circularly shifted by `SHIFT_S` within its own recording, then
                    correlated against theirs. Preserves every marginal and every autocorrelation and
                    destroys the alignment. **A comparison against the real effect, never a threshold**
                    (rule 34): if the shifted agreement reaches the unshifted one, the primary is measuring
                    something that does not depend on the two series describing the same moment.

VERDICT RULE -- the wrong-direction case first, because "excludes zero" and "supports the hypothesis" are
different questions (rule 37, fourth occurrence).

  (a) INVERTED       -- V1's interval lies entirely ABOVE +`AGREE`. The two agree in magnitude but this
                       repo's ratio is oriented the same way as theirs, which contradicts the parameter
                       description. Something is upside down and every use of `bis_sfs` needs re-reading,
                       including E58's.
  (b) DISAGREE       -- V1's interval includes zero, or lies between -`AGREE` and +`AGREE`. The two
                       implementations are not computing the same quantity. This repo's is not thereby
                       proven wrong -- theirs could be -- but `bis_sfs` may not be described as a
                       validated SyncFastSlow until the discrepancy is understood.
  (c) NOT INFORMATIVE-- the placebo's magnitude reaches V1's. The correlation does not depend on the two
                       series describing the same moment, so it is not evidence of agreement.
  (d) AGREE          -- V1's interval lies entirely below -`AGREE` and the placebo does not reach it.
                       `sync_fast_slow` reproduces an independent implementation of the same quantity, in
                       the orientation the documentation predicts.

WHAT AN `AGREE` WOULD AND WOULD NOT LICENCE. It would licence describing `bis_sfs` as an implementation
validated against an independent one, which is the computational verifier layer its declaration requires
and nothing more. It would NOT licence any claim about what SFS MEASURES, in either implementation, and it
is not evidence about consciousness, depth or anything clinical. Those live in the declaration's other
layers and none of them is touched here.

WHAT IS DELIBERATELY NOT TESTED HERE, AND WHY. `bis_sfs`'s registered direction on `unconscious_vs_awake`
could be tested on this deposit -- DOSE-I carries per-second SOC and MOAA/S. **It is not tested here
because that question has already been contaminated.** A probe run on 2026-07-31 to check the deposit's
feasibility read the depositors' SFS against SOC and saw the answer. A "prediction" registered afterwards
would be a prediction about a number already seen, which is precisely the move `DISCOVERY_LOOP.md` forbids.
The probe's finding is recorded in QUEUE.md as a PROBE, descriptive, and the directional claim stays
untested on DOSE-I. It can be tested cleanly on a deposit nobody has looked at.

    python -m bsde.experiments.e59_sfs_independent_check
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
from bsde.verifier.stats import _midranks, spearman                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "dosei_sfs_check.csv")
OUT = os.path.join(RESULTS, "e59_sfs_independent_check.json")

MIN_RECORDINGS = 30
MIN_WINDOWS = 100
AGREE = 0.50             # |rho| a correlation must exceed to count as agreement
SHIFT_S = 600            # placebo shift, in seconds of the original record
STRIDE_S = 5             # the extractor's stride, so the shift is SHIFT_S/STRIDE_S rows
REPS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def partial_spearman(x, y, z):
    """Spearman of x against y controlling for z, by rank-residualising both on rank(z)."""
    x, y, z = (np.asarray(a, float) for a in (x, y, z))
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if ok.sum() < 8:
        return float("nan")
    rx, ry, rz = _midranks(x[ok]), _midranks(y[ok]), _midranks(z[ok])
    A = np.column_stack([np.ones(int(ok.sum())), rz])
    ex = rx - A @ np.linalg.lstsq(A, rx, rcond=None)[0]
    ey = ry - A @ np.linalg.lstsq(A, ry, rcond=None)[0]
    return spearman(ex, ey)


def _boot_median(vals, rng, reps=REPS):
    v = np.asarray([x for x in vals if np.isfinite(x)], float)
    if v.size < 3:
        return float("nan"), float("nan")
    d = np.sort([np.median(rng.choice(v, size=v.size, replace=True)) for _ in range(reps)])
    return float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"MISSING {TABLE} -- run scripts/extract_dosei_sfs.py first")
        return 2
    by_rec = defaultdict(list)
    with open(TABLE, newline="") as fh:
        for r in csv.DictReader(fh):
            by_rec[r["recording"]].append(r)

    rng = np.random.default_rng(SEED)
    prim, spec, plac, kept = [], [], [], []
    for rec, rows in sorted(by_rec.items()):
        rows.sort(key=lambda r: _f(r["t_s"]))
        mine = np.array([_f(r["mine_sfs"]) for r in rows])
        theirs = np.array([_f(r["their_sfs"]) for r in rows])
        pfs = np.array([_f(r["their_pfs"]) for r in rows])
        ok = np.isfinite(mine) & np.isfinite(theirs)
        if int(ok.sum()) < MIN_WINDOWS:
            continue
        kept.append((rec, int(ok.sum())))
        prim.append(spearman(mine[ok], theirs[ok]))
        spec.append(partial_spearman(mine, theirs, pfs))
        shift = max(1, SHIFT_S // STRIDE_S) % len(mine)
        plac.append(spearman(np.roll(mine, shift)[ok], theirs[ok]))

    n_rec = len(kept)
    n_win = sum(k for _, k in kept)
    m1 = n_rec >= MIN_RECORDINGS
    print(f"recordings usable : {n_rec} of {len(by_rec)} ({n_win} windows)   "
          f"M1 {'PASS' if m1 else 'FAIL'} (need {MIN_RECORDINGS})")
    if not m1:
        print("M1 FAILED -- too few recordings for a cross-recording summary. Verdict ABSENT (rule 31).")
        json.dump({"gate_m1": False, "n_recordings": n_rec, "n_windows": n_win},
                  open(OUT, "w"), indent=2)
        return 1

    p_med = float(np.median(prim))
    p_lo, p_hi = _boot_median(prim, rng)
    s_med = float(np.nanmedian(spec))
    s_lo, s_hi = _boot_median(spec, rng)
    q_med = float(np.median(plac))
    q_lo, q_hi = _boot_median(plac, rng)

    print(f"V1 PRIMARY     median within-recording rho(mine, theirs) = {p_med:+.4f} "
          f"[{p_lo:+.4f}, {p_hi:+.4f}]   (predicted strongly NEGATIVE)")
    print(f"V2 SPECIFICITY partial rho(mine, theirs | their PowerFastSlow) = {s_med:+.4f} "
          f"[{s_lo:+.4f}, {s_hi:+.4f}]")
    print(f"P1 PLACEBO     mine shifted {SHIFT_S}s within recording      = {q_med:+.4f} "
          f"[{q_lo:+.4f}, {q_hi:+.4f}]")

    if not np.isfinite(p_lo):
        verdict = "ABSENT -- the bootstrap could not form an interval."
    elif p_lo > AGREE:
        verdict = (f"INVERTED -- the two implementations agree in magnitude but this repo's ratio runs the "
                   f"SAME way as theirs, contradicting a parameter description that defines theirs as the "
                   f"reciprocal. sync_fast_slow is upside down and every use of bis_sfs needs re-reading, "
                   f"E58 included.")
    elif p_hi > -AGREE:
        verdict = (f"DISAGREE -- |median rho| does not clear {AGREE:.2f} in the predicted direction. The "
                   f"two are not computing the same quantity. That does not make this repo's version "
                   f"wrong, but bis_sfs may not be called a validated SyncFastSlow until the discrepancy "
                   f"is understood.")
    elif abs(q_med) >= abs(p_med):
        verdict = ("NOT INFORMATIVE -- a circularly shifted copy of this repo's own series agrees with "
                   "theirs as well as the aligned one does, so the agreement does not depend on the two "
                   "series describing the same moment.")
    else:
        verdict = ("AGREE -- sync_fast_slow reproduces an independent implementation of SyncFastSlow, in "
                   "the orientation the parameter description predicts, and a time-shifted copy does not. "
                   "This clears the COMPUTATIONAL layer for bis_sfs and nothing else: it is not evidence "
                   "about what SFS measures, in either implementation.")
    print(f"\nVERDICT: {verdict}")
    if np.isfinite(s_med) and abs(s_med) < AGREE <= abs(p_med):
        print("NOTE: the agreement does NOT survive partialling out the depositors' pure power ratio over "
              "the identical bands. Both implementations may be tracking power rather than phase coupling "
              "(rule 28). This does not change the verdict above, which is about agreement, not about "
              "what is being agreed on.")

    json.dump({"gate_m1": True, "n_recordings": n_rec, "n_windows": n_win,
               "primary_median_rho": {"median": p_med, "lo": p_lo, "hi": p_hi},
               "specificity_partial_rho": {"median": s_med, "lo": s_lo, "hi": s_hi},
               "placebo_shifted_rho": {"median": q_med, "lo": q_lo, "hi": q_hi},
               "per_recording_primary": dict(zip([r for r, _ in kept], [float(v) for v in prim])),
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
