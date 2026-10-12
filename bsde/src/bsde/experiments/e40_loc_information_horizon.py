#!/usr/bin/env python3
"""E40 — how far ahead is loss of consciousness visible AT ALL, to anything, including the monitor proxy?

THIS IS NOT A FOURTH CANDIDATE ON THIS DEPOSIT, AND THAT DISTINCTION IS THE REASON IT IS WORTH RUNNING.

QUEUE.md Q10 closed Challenge C with three reportable verdicts and one instruction: *"Nothing further on
DOSE-I with a new feature. Three instruments have now failed in the same place. A fourth feature is the
least informative thing this queue could spend a run on."* It also named the one thing that would be worth
more:

> "Ask whether the ceiling is the transition's own sharpness. E37's lead-time curve decays from 0.561 at
>  30 s to 0.497 by 180 s: whatever information exists arrives just before the loss, which is exactly where
>  the incumbent is also strongest. **A design that could separate 'no information earlier' from 'no
>  information the incumbent lacks' would be worth more than a sixth feature.**"

This file is that design. It scores **no candidate against any other**, and its primary is a property of
the LABEL rather than of any measure — structurally the same move as E38, which characterises E28's label
instead of scoring a feature against it. The two available conclusions are:

    "the information exists earlier and our measures cannot reach it"   -> Challenge C stays open, and the
                                                                          target is sensitivity, not novelty
    "nothing sees it earlier, the incumbent included"                   -> Challenge C's negative is a
                                                                          statement about the TRANSITION,
                                                                          and it is publishable as one

WHY E37's LEAD-TIME CURVE COULD NOT ANSWER THIS. Its P6 scored the label "LOC within h seconds" at h = 30,
60, 120, 180, 300. **Those horizons are nested**: the h = 300 positives contain every h = 30 positive, so a
signal confined to the last 30 s keeps contributing at every larger horizon and the curve decays for a
reason that has nothing to do with how far ahead anything is visible. **A cumulative horizon cannot measure
a lead time.** The fix is disjoint bands — windows whose time-to-loss falls in [t, t + WIDTH) against a
control class far from any loss — so each band asks its own question and none inherits the previous one's
positives. Error-catalogue rule 33 is the same shape: if the claim is about a specific distance, the
statistic must isolate that distance rather than aggregate over everything nearer.

THE CONTROL CLASS IS WHERE THIS DESIGN CAN GO WRONG, AND E33 IS WHY. Controls are conscious windows more
than `CONTROL_MIN_S` from any loss. That is exactly the construction that gave E33 a position-AUC of
**1.000** — "far from a loss" and "early in the recording" are nearly the same thing when every recording
ends in a loss. **So the position check is a per-band GATE here, not a summary statistic**: any band whose
label is explained by position within the recording is reported ABSENT for that band, and its number is not
printed. A band that fails is not evidence of absence at that lead time; it is absence of evidence.

REGISTERED BEFORE ANY BANDED STATISTIC IS COMPUTED. Failing branch written first throughout.

  G1  COHORT GATE, no candidate consulted. At least `MIN_RECORDINGS` recordings contribute, and the control
      class holds at least `MIN_CONTROL` windows. If not, nothing is reported (rule 31).

  G2  PER-BAND GATE, applied independently to every band and evaluated BEFORE that band's statistics.
      (a) at least `MIN_BAND_WINDOWS` windows and `MIN_BAND_PATIENTS` patients in the band;
      (b) position-AUC of the band-vs-control label within `MAX_POSITION_AUC_DIST` of chance — E33's check,
          promoted from a report to a gate because this design is the one that provokes it;
      (c) the incumbent VARIES in the band (rule 32) — a band where SEF95 is constant cannot support a
          comparison, and two whole ledger entries were once spent on exactly that mistake.
      A band failing any part is reported ABSENT and contributes nothing to the primary.

  P0  THE STATISTIC, declared before any of it runs. Every band reports the **out-of-fold AUC** of a
      univariate logistic with recording-level folds — **not** `|AUC - 0.5|`. A folded statistic is biased
      upward under the null (rule 46), and a horizon read off folded values would be inflated in every
      band, most severely where the data thins. The logistic absorbs the feature's sign on its training
      folds, so the out-of-fold value centres on 0.5 under the null and can fall below it; "the interval
      excludes 0.5" is therefore a valid one-sided test with no folding to correct and no direction to
      declare in advance.

  P1  THE PRIMARY, and it is a property of the label. **The information horizon: the smallest band edge
      at which the INCUMBENT's out-of-fold AUC interval includes 0.5**, i.e. the lead time beyond which the
      conventional signal no longer distinguishes an approaching loss from a control window. Reported with
      the full banded curve, not only the crossing point.

  P2  THE SAME CURVE FOR EVERY CANDIDATE E34 and E37 tested, so the question "does anything reach further
      than the incumbent?" is answered per band rather than in aggregate. **No candidate is declared a
      winner here** — a candidate whose interval excludes 0.5 in a band where the incumbent's does not is
      reported as such and becomes a registration for a successor, not a result.

  P3  THE PLACEBO, gating interpretation (rules 34 and 48). The identical banding around a FAKE landmark
      drawn uniformly in the middle 70 % of each recording. **The placebo curve must be flat at chance in
      every band.** If a fake landmark produces a horizon, the banding itself manufactures discrimination
      and P1 is void. Reported NOT INFORMATIVE if the incumbent's own nearest band already includes 0.5,
      because a placebo cannot validate a null.

  P4  REPORTED CONTEXT: band occupancy and patient counts, so a reader can see where the curve runs out of
      data rather than out of signal. **A band that thins to nothing is not a band where the signal died.**

VERDICT RULE, written before the run.

    NOT INTERPRETABLE   G1 failed, or the placebo curve is not flat.
    NO HORIZON MEASURED The incumbent's nearest band already includes 0.5. Nothing is visible at any lead
                        time here, which would contradict E34's and E37's own P3a results and should be
                        read as a fault in this design rather than a finding.
    HORIZON = t         The incumbent discriminates out to t and not beyond. **If no candidate reaches
                        further, Challenge C's negative is a statement about the transition's own
                        sharpness** — nothing sees it coming earlier, and the failure of three instruments
                        to beat the incumbent is explained by there being nothing further out to find.
                        That is a stronger and more useful negative than "our features were not good
                        enough", and it is falsifiable by any future measure that reaches past t.

SCOPE. DOSE-I, propofol procedural sedation, single-site derived pEEG at 1 Hz, `SOC` as the deposit's own
consciousness flag — which E37 established is not monitor-derived (it agrees with `MOAAS > 1` on 98.0 % of
samples at the median), so the horizon measured here is against a behaviourally anchored landmark rather
than against the monitor's own opinion. The incumbent is SEF95, not a commercial depth index: claim scope
is "ahead of SEF95", never "ahead of BIS". A horizon measured here bounds this deposit and this montage,
and nothing else.

--------------------------------------------------------------------------------------------------------
OUTCOME. **NOT INTERPRETABLE. Every band was refused by its own gate, a feasibility probe then showed no
successor can be built on this deposit, and re-reading the placebo output found a bug in this file's own
verdict code that was hiding a SECOND, independent fatal flaw.**

    G1     PASSED. 129 recordings, 79,429 conscious windows, 27,308 control windows.

    G2     **All eight bands refused.** Seven failed the position gate with position-AUC of 0.026-0.060 —
           a distance from chance of 0.44-0.47 against a 0.20 ceiling — and the eighth failed on coverage
           (10 patients). No band statistic was computed, so no candidate was ever scored.

           **The gate fired exactly where its registration said it would.** The header states: "That is
           exactly the construction that gave E33 a position-AUC of 1.000 ... So the position check is a
           per-band GATE here, not a summary statistic." It was promoted from report to gate for this
           reason and it earned the promotion.

    THE FEASIBILITY PROBE THAT PREVENTED A SUCCESSOR. Before registering any fix, the obvious one —
    position-matched controls — was probed. It does not exist in this deposit:

        control class      26,489 windows with NO LOSS AFTER them, median position **0.90**
                              819 windows >= 900 s before a loss, median position 0.43
        band windows       median position **0.26-0.35** in every band

        within-recording controls within 0.10 of a band window's position:
            [  0, 30) s   1,045 of 14,220 band windows,  38 recordings
            [ 60,120) s     485 of 11,450,               15 recordings
            [180,240) s      60 of  3,369,                1 recording
            [300,420) s       **0 of  2,131,               0 recordings**

    **The confound is structural, not a defect of this design.** In DOSE-I, "far from a loss" means "after
    the last loss", because procedural sedation cases end awake. There is no population of early-in-record
    windows that are far from any loss, because every case's early portion leads into an induction. **So
    the information-horizon question cannot be asked on this deposit by any design**, and QUEUE.md Q10
    item 2 closes the way Q9 item 2 did — checked and impossible, rather than pending.

    P3, AND THE BUG. **Rule 37, third occurrence in this project, committed by this file.** The band
    verdict was `excludes_chance = lo_ > 0.5`, a one-sided test, and the placebo run printed "at chance"
    for every band. Re-reading the numbers rather than the labels showed what that was hiding: SEF95 scored
    **0.237 [0.115, 0.418]** under a *fake* landmark — an interval lying **entirely below** chance, which
    is discriminable, not null. Corrected to a two-sided test, the placebo is discriminable in **5 of 7**
    gated bands and the curve is **not flat**:

        [  0, 30) 0.237 [0.115, 0.418]      [120,180) 0.312 [0.187, 0.507]  at chance
        [ 30, 60) 0.295 [0.169, 0.472]      [240,300) 0.314 [0.172, 0.525]  at chance
        [ 60,120) 0.254 [0.159, 0.431]      [300,420) 0.283 [0.187, 0.454]
        [180,240) 0.267 [0.131, 0.478]

    **So the design had two independent fatal flaws and the one-sided operator hid the second.** Had the
    position gate passed, this file would have reported a horizon while its own placebo was manufacturing
    discrimination — and would have printed "placebo curve flat at chance in every gated band: True"
    underneath it. The lesson is the one rule 37 already states and this file failed to apply to itself:
    **a cell that spans the null is neither direction, and a comparison operator that can only see one
    direction will convert the other into a pass.** Verdict code deserves the same scrutiny as analysis
    code, and it is now two-sided here.

    WHY THE PLACEBO IS DISCRIMINABLE, since the number is interesting even though the design is dead. A
    fake landmark drawn uniformly in the middle of each recording puts its "band" windows near the middle
    and its controls at the end, so SEF95 separates them — in the *opposite* direction to a real induction,
    which is why the AUCs sit below 0.5 rather than above. That is the same position confound as G2's,
    seen from the other side, and it confirms the diagnosis rather than adding a new one.

    WHAT SURVIVES. Nothing about Challenge C changes. Its three reportable verdicts stand, and the question
    of whether the ceiling is the transition's own sharpness remains **open and unanswerable here** — which
    is a more useful statement than an answer built on a control class that cannot support it.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance")))

from bsde.verifier.stats import auc, cluster_bootstrap_ci, cv_predict_proba   # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
PEEG_ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
OUT = os.path.join(RESULTS, "e40_loc_information_horizon.json")

INCUMBENT = "SEF95"
CANDIDATES = ("PE31", "PE32", "PE61", "MF", "WSMF30", "WSMF49", "rel_alpha", "rel_beta1",
              "rel_delta1", "rel_gamma", "sync_alpha", "CFS", "PFS", "SFS")
ALL_FEATURES = (INCUMBENT,) + CANDIDATES

BAND_EDGES = (0, 30, 60, 120, 180, 240, 300, 420, 600)
CONTROL_MIN_S = 900.0
MIN_RECORDINGS = 50
MIN_CONSCIOUS_S = 200
MIN_CONTROL = 2000
MIN_BAND_WINDOWS = 300
MIN_BAND_PATIENTS = 20
MAX_POSITION_AUC_DIST = 0.20
REPS = 400
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _load(zip_path):
    """Conscious windows with time-to-next-loss and position-in-record. E34's loader, plus position."""
    z = zipfile.ZipFile(zip_path)
    recs = []
    for nm in sorted(n for n in z.namelist() if n.endswith("_pEEG.csv")):
        rows = list(csv.DictReader(io.StringIO(z.read(nm).decode("utf-8-sig"))))
        if not rows:
            continue
        soc = np.array([_f(r.get("SOC", "")) for r in rows])
        cols = {c: np.array([_f(r.get(c, "")) for r in rows], float) for c in ALL_FEATURES}
        ok = np.isfinite(soc) & np.isfinite(cols[INCUMBENT])
        if ok.sum() < MIN_CONSCIOUS_S:
            continue
        idx = np.flatnonzero(ok)
        s = soc[idx]
        losses = np.flatnonzero((s[:-1] == 1) & (s[1:] == 0))
        conscious = np.flatnonzero(s == 1)
        if conscious.size < MIN_CONSCIOUS_S:
            continue
        ttl = np.full(conscious.size, np.inf)
        for k, c in enumerate(conscious):
            nxt = losses[losses >= c]
            if nxt.size:
                ttl[k] = float(nxt[0] - c)
        rid = os.path.basename(nm).replace("_pEEG.csv", "")
        pos = conscious.astype(float) / max(1.0, float(s.size - 1))
        recs.append({"id": rid, "n": conscious.size, "pos": pos, "ttl": ttl,
                     "n_losses": int(losses.size),
                     "cols": {c: cols[c][idx][conscious] for c in ALL_FEATURES}})
    return recs


def _stack(recs, key):
    return np.concatenate([r["cols"][key] if key in r["cols"] else r[key] for r in recs])


def _band_mask(ttl, lo, hi):
    return (ttl >= lo) & (ttl < hi)


def _banded(recs, ttl, grp, pos, cols, lo, hi, control, rng, features):
    """One band against the control class: gates first, then a directional AUC per feature."""
    band = _band_mask(ttl, lo, hi)
    sel = band | control
    n_win = int(band.sum())
    n_pat = int(np.unique(grp[band]).size)
    y = band[sel].astype(float)
    rep = {"lo": lo, "hi": hi, "n_band": n_win, "n_patients": n_pat,
           "n_control": int(control.sum())}
    if n_win < MIN_BAND_WINDOWS or n_pat < MIN_BAND_PATIENTS or np.unique(y).size < 2:
        rep["gate"] = "coverage"
        return rep
    pos_auc = float(auc(y, pos[sel]))
    rep["position_auc"] = pos_auc
    if abs(pos_auc - 0.5) > MAX_POSITION_AUC_DIST:
        rep["gate"] = "position"
        return rep
    inc = cols[INCUMBENT][sel]
    if np.unique(inc[np.isfinite(inc)]).size < 10:
        rep["gate"] = "incumbent_constant"
        return rep
    rep["gate"] = "passed"
    rep["features"] = {}
    g = grp[sel]
    for name in features:
        x = cols[name][sel]
        m = np.isfinite(x)
        if m.sum() < MIN_BAND_WINDOWS or np.unique(y[m]).size < 2:
            continue
        # OUT-OF-FOLD AUC, NOT FOLDED. |AUC - 0.5| is biased upward under the null (rule 46), so a folded
        # statistic would inflate the horizon by making every band look better than chance. The univariate
        # logistic absorbs the feature's sign on its TRAINING folds, so the out-of-fold AUC centres on 0.5
        # under the null and can fall below it — which makes "the interval excludes 0.5" a valid test with
        # no folding to correct for, and no direction to declare.
        p = cv_predict_proba(x[m], y[m], g[m], rng)
        a = float(auc(y[m], p))
        lo_, hi_, _ = cluster_bootstrap_ci(lambda i: auc(y[m][i], p[i]), g[m], rng, reps=REPS)
        # TWO-SIDED. `lo_ > 0.5` alone is rule 37 exactly — a permissive comparison that reads an
        # interval lying ENTIRELY BELOW chance as "at chance". The placebo run caught this: SEF95 scored
        # 0.237 [0.115, 0.418] under a fake landmark, which excludes 0.5 on the low side and is therefore
        # discriminable, and the one-sided test printed it as flat. A band is at chance only if its
        # interval CONTAINS 0.5.
        rep["features"][name] = {"auc": a, "ci": [float(lo_), float(hi_)],
                                 "excludes_chance": bool(np.isfinite(lo_) and np.isfinite(hi_)
                                                         and (lo_ > 0.5 or hi_ < 0.5)),
                                 "above_chance": bool(np.isfinite(lo_) and lo_ > 0.5)}
    return rep


def main(argv=None) -> int:
    print("E40 — how far ahead is loss of consciousness visible at all, to anything?")
    print("   NOT a fourth candidate. The primary is a property of the LABEL: the information horizon.")
    print("   Disjoint bands, because E37's nested horizons cannot measure a lead time (rule 33).")
    if not os.path.exists(PEEG_ZIP):
        print(f"\n   *** {os.path.basename(PEEG_ZIP)} absent.")
        return 2
    recs = _load(PEEG_ZIP)
    rng = np.random.default_rng(SEED)
    st = {"experiment": "E40", "bands": list(BAND_EDGES), "control_min_s": CONTROL_MIN_S}

    ttl = np.concatenate([r["ttl"] for r in recs])
    pos = np.concatenate([r["pos"] for r in recs])
    grp = np.concatenate([np.full(r["n"], r["id"]) for r in recs])
    cols = {c: np.concatenate([r["cols"][c] for r in recs]) for c in ALL_FEATURES}
    control = np.isfinite(ttl) & (ttl >= CONTROL_MIN_S) | ~np.isfinite(ttl)

    print("\n" + "=" * 100)
    print("G1 — COHORT GATE")
    print("=" * 100)
    print(f"   recordings contributing : {len(recs)}   (floor {MIN_RECORDINGS})")
    print(f"   conscious windows       : {ttl.size}")
    print(f"   control windows (>= {CONTROL_MIN_S:.0f} s from any loss, or no loss after) : "
          f"{int(control.sum())}   (floor {MIN_CONTROL})")
    g1 = bool(len(recs) >= MIN_RECORDINGS and control.sum() >= MIN_CONTROL)
    print(f"\n   G1 {'PASSED' if g1 else '*** FAILED'}")
    st["g1"] = {"n_recordings": len(recs), "n_windows": int(ttl.size),
                "n_control": int(control.sum()), "passed": g1}
    if not g1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("G2 / P1 / P2 — PER-BAND GATES, then the incumbent and every candidate")
    print("=" * 100)
    bands = []
    for lo, hi in zip(BAND_EDGES[:-1], BAND_EDGES[1:]):
        rep = _banded(recs, ttl, grp, pos, cols, float(lo), float(hi), control, rng, ALL_FEATURES)
        bands.append(rep)
        head = f"   [{lo:4d},{hi:4d}) s  n={rep['n_band']:6d} pat={rep['n_patients']:3d}"
        if rep["gate"] != "passed":
            print(f"{head}   *** BAND ABSENT — gate '{rep['gate']}'"
                  + (f", position-AUC {rep.get('position_auc', float('nan')):.3f}"
                     if rep["gate"] == "position" else ""))
            continue
        f = rep["features"].get(INCUMBENT)
        extra = [n for n in CANDIDATES
                 if rep["features"].get(n, {}).get("above_chance")]
        print(f"{head}   pos-AUC {rep['position_auc']:.3f}   "
              f"{INCUMBENT} {f['auc']:.3f} [{f['ci'][0]:.3f}, {f['ci'][1]:.3f}]"
              f"   {'ABOVE chance' if f['above_chance'] else ('BELOW chance' if f['excludes_chance'] else 'at chance')}")
        if extra:
            print(f"                candidates also above chance here: {extra}")
    st["bands"] = bands

    passed = [b for b in bands if b["gate"] == "passed" and INCUMBENT in b.get("features", {})]
    horizon = None
    for b in passed:
        if not b["features"][INCUMBENT]["above_chance"]:
            horizon = b["lo"]
            break
    st["horizon_s"] = horizon
    reach = {}
    for n in ALL_FEATURES:
        far = [b["lo"] for b in passed if b["features"].get(n, {}).get("above_chance")]
        reach[n] = max(far) if far else None
    st["furthest_band_above_chance"] = reach

    print("\n" + "=" * 100)
    print("P3 — PLACEBO: the identical banding around a FAKE landmark")
    print("=" * 100)
    fake_ttl = []
    for r in recs:
        n = r["n"]
        cut = int(n * float(rng.uniform(0.2, 0.9)))
        fake_ttl.append(np.abs(np.arange(n) - cut).astype(float))
    fake_ttl = np.concatenate(fake_ttl)
    fake_control = fake_ttl >= CONTROL_MIN_S
    flat = True
    p3rows = []
    for lo, hi in zip(BAND_EDGES[:-1], BAND_EDGES[1:]):
        rep = _banded(recs, fake_ttl, grp, pos, cols, float(lo), float(hi), fake_control,
                      rng, (INCUMBENT,))
        p3rows.append(rep)
        if rep["gate"] != "passed":
            print(f"   [{lo:4d},{hi:4d}) s   band absent under the placebo ('{rep['gate']}')")
            continue
        f = rep["features"].get(INCUMBENT)
        if f is None:
            continue
        bad = f["excludes_chance"]
        flat = flat and not bad
        tag = ("*** DISCRIMINABLE (interval excludes chance"
               + (", ABOVE)" if f["above_chance"] else ", BELOW)")) if bad else "at chance"
        print(f"   [{lo:4d},{hi:4d}) s   {INCUMBENT} {f['auc']:.3f} "
              f"[{f['ci'][0]:.3f}, {f['ci'][1]:.3f}]   {tag}")
    st["p3"] = {"flat": bool(flat), "bands": p3rows}
    nearest_null = bool(passed and not passed[0]["features"][INCUMBENT]["above_chance"])
    if nearest_null:
        print("\n   NOT INFORMATIVE: the incumbent's nearest band already includes chance, so there is")
        print("   no horizon for a fake landmark to fail to reproduce (rule 48).")
    else:
        print(f"\n   placebo curve flat at chance in every gated band: {flat}")

    print("\n" + "=" * 100)
    print("P4 — BAND OCCUPANCY (reported: where the curve runs out of DATA rather than signal)")
    print("=" * 100)
    for b in bands:
        print(f"   [{b['lo']:4.0f},{b['hi']:4.0f}) s   windows {b['n_band']:6d}   "
              f"patients {b['n_patients']:3d}   gate {b['gate']}")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not passed:
        verdict = "not_interpretable"
        print("   NOT INTERPRETABLE: every band was refused by its own gate.")
    elif not flat and not nearest_null:
        verdict = "not_interpretable_placebo"
        print("   NOT INTERPRETABLE: a fake landmark produces discrimination, so the banding itself")
        print("   manufactures it and no horizon can be read from this design.")
    elif nearest_null:
        verdict = "no_horizon_measured"
        print("   NO HORIZON MEASURED: the incumbent is at chance even in its nearest band, which")
        print("   contradicts E34's and E37's own P3a results and should be read as a fault in this")
        print("   design rather than as a finding.")
    else:
        verdict = "horizon_measured"
        beyond = [n for n, v in reach.items()
                  if n != INCUMBENT and v is not None
                  and (horizon is None or v >= (horizon if horizon is not None else 10 ** 9))]
        print(f"   HORIZON: the incumbent discriminates out to the band starting at "
              f"{horizon if horizon is not None else BAND_EDGES[-2]} s and not beyond.")
        if beyond:
            print(f"   Candidates reaching at least as far: {beyond}")
            print("   Reported as a registration for a successor, NOT as a result.")
        else:
            print("   NO candidate reaches further than the incumbent. Challenge C's negative is then a")
            print("   statement about the TRANSITION's own sharpness rather than about our features:")
            print("   nothing sees it coming earlier, which is why three instruments failed identically.")
    st["verdict"] = verdict
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote results/{os.path.basename(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
