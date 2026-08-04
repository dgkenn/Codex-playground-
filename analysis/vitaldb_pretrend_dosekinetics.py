#!/usr/bin/env python3
"""THE TWO REMAINING CONFOUNDS for the within-case precedence result, tested head-on.

The within-case model shows that a suppressed bin is followed by a pressure fall while NOT being preceded by one
(propofol). Two alternative explanations survive everything tested so far, and both would produce exactly that
asymmetry without any causal role for the suppression itself:

  CONFOUND 1 -- DOSE KINETICS, not dose level.
      The model holds the effect-site concentration Ce(t) fixed, but not its RATE OF CHANGE. A propofol bolus or a
      TCI step raises Ce; the EEG suppresses within seconds while the vasodilatory pressure effect arrives over the
      following minute. Suppression would then merely be the fastest-appearing marker of a rising dose, and the
      pressure fall would be caused by the same dose rise, not by the suppression. Conditioning on the LEVEL of Ce
      cannot remove this; conditioning on dCe over the same window can.

  CONFOUND 2 -- PRE-EXISTING PRESSURE TREND.
      If pressure is already sliding when the suppression appears, the forward window inherits the ongoing slide
      while the backward window does not capture it symmetrically. Conditioning on the preceding trajectory removes
      this: the estimate then answers "given that the pressure was doing THIS coming into bin t, does suppression
      change what it does next?"

      COLLINEARITY TRAP -- the pre-trend must NOT be MAP(t) - MAP(t-k). That quantity is exactly the negative of
      the backward outcome MAP(t-k) - MAP(t), so including it makes the backward regression perfectly collinear:
      the backward coefficient is forced to zero and "forward minus backward" silently degenerates into "forward",
      printing a clean-looking and entirely meaningless asymmetry. The pre-trend is therefore measured over the
      window BEFORE the backward window, MAP(t-k) - MAP(t-2k), which is collinear with neither outcome.

Models, all with CASE FIXED EFFECTS and CASE-level cluster bootstrap, run on the identical bin set (bins that have
both a forward and a backward neighbour, so nothing differs between the two directions except direction):

    M0  dMAP ~ BS + MAP(t) + Ce(t)                                    (the published within-case model)
    M1  M0 + dCe = Ce(t) - Ce(t-k)                                    (kills confound 1)
    M2  M0 + pre-trend = MAP(t) - MAP(t-k)                            (kills confound 2)
    M3  M0 + dCe + pre-trend                                          (both)
    M4  M3 restricted to bins where |dCe| is essentially zero          (the sharpest version of confound 1:
                                                                       a stable-infusion subgroup)

Negative control (frontal EMG) is run through M3 as well: if the design itself manufactures a forward-backward
asymmetry, EMG will show one too.

Verdict rule fixed in advance: the precedence claim survives only if the forward-minus-backward difference stays
clearly negative in M3 AND in the stable-dose subgroup M4, while the EMG control stays null.

PRE-TREND WINDOW -- CORRECTED after adversarial review, and this changed a reported number.
The pre-trend was previously MAP(t-k) - MAP(t-2k). That is not exactly collinear with the backward outcome
MAP(t-k) - MAP(t), but it SHARES THE ENDPOINT MAP(t-k) with it. Measured on the real within-case demeaned data the
partial correlation was 0.528 against the backward outcome and 0.023 against the forward one. The consequence was
one-sided: adding it shrank the BACKWARD coefficient from -0.412 to -0.202 while leaving the FORWARD coefficient
untouched at -1.278, inflating the forward-minus-backward statistic from -0.870 to -1.076, i.e. by about 24 %,
entirely through the backward side. The pre-trend is now measured over [t-3k, t-2k], which shares NO endpoint with
either outcome (raw correlation with the backward outcome falls from 0.389 to 0.035). Roughly half of the apparent
benefit of pre-trend adjustment was this artefact; the corrected asymmetry is near -0.97 rather than -1.08. The
forward coefficient is unaffected by any of this.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)

# --- physiologic range filter for arterial pressure -------------------------------------------------
# The propofol pipeline never range-filtered MAP. bridge_bins.csv contains 4.27 % of values <= 0
# (minimum -78 mmHg -- negative arterial pressure is impossible) and 0.62 % above 200 mmHg: transducer
# zeroing, line flushes and disconnections. Left unfiltered they produced dMAP values up to +/-390 mmHg
# and inflated every forward-minus-backward statistic about three-fold (-0.33 -> -0.97 mmHg). Filtering
# implausible VALUES is the principled fix; winsorising the outcome would only mask them.
# The filtered estimate is stable across windows [30,150], [25,160], [20,180] and [40,140]
# (asymmetry -0.340, -0.330, -0.323, -0.333), so the exact threshold is not doing the work.
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))


def _map_ok(raw):
    """Parse a MAP field, returning NaN unless it lies in the physiologic window."""
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")



def load(cohort):
    HD = defaultdict(dict); seen = set()
    fn = "bridge_bins.csv" if cohort == "prop" else "sevo_bins.csv"
    with open(f"{DATA}/{fn}") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                HD[cid][t] = [float(d["bs"]),
                              _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan,
                              np.nan]
            except Exception:
                pass
    if cohort == "prop":
        seen = set()
        with open(f"{DATA}/bis_bins.csv") as fh:
            for d in csv.DictReader(fh):
                try:
                    cid = d["caseid"]; t = float(d["bin_t"])
                    if (cid, t) in seen or cid not in HD or t not in HD[cid]:
                        continue
                    seen.add((cid, t))
                    HD[cid][t][3] = float(d["emg"]) if d["emg"] else np.nan
                except Exception:
                    pass
    return HD


def build(HD, k, exposure, emg_cut):
    case = []; e = []; m0 = []; dz = []; dce = []; pre = []; df = []; db = []
    ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k; tb3 = t - 90.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd or tb3 not in bd:
                continue
            bs, m, dose, emg = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; mb3 = bd[tb3][1]; doseb = bd[tb][2]
            if m != m or mf != mf or mb != mb or mb2 != mb2 or mb3 != mb3 or dose != dose or doseb != doseb:
                continue
            if exposure == "bs":
                x = bs
            elif exposure == "bsbin":
                x = 1.0 if bs > 0 else 0.0
            else:
                if emg != emg or emg_cut is None:
                    continue
                x = 1.0 if emg > emg_cut else 0.0
            if c not in ci:
                ci[c] = len(ci)
            case.append(ci[c]); e.append(x); m0.append(m); dz.append(dose)
            dce.append(dose - doseb)
            pre.append(mb2 - mb3)         # [t-3k, t-2k]: shares NO endpoint with db (see docstring)
            df.append(mf - m); db.append(mb - m)
    return dict(case=np.array(case, np.int32), e=np.array(e), m0=np.array(m0), dz=np.array(dz),
                dce=np.array(dce), pre=np.array(pre), df=np.array(df), db=np.array(db), ncase=len(ci))


def demean(cols, case, ncase, w):
    sw = np.bincount(case, weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    return [v - (np.bincount(case, weights=w * v, minlength=ncase) / sw)[case] for v in cols]


def coef(D, sel, extra, dy, w):
    """Exposure coefficient in dy ~ e + MAP(t) + dose(t) [+ extra] with case fixed effects."""
    cols = [D["e"][sel], D["m0"][sel], D["dz"][sel]] + [D[x][sel] for x in extra] + [dy]
    dm = demean(cols, D["case"][sel], D["ncase"], w)
    X = np.column_stack(dm[:-1]); y = dm[-1]
    A = (X.T * w) @ X
    try:
        return np.linalg.solve(A + 1e-8 * np.eye(X.shape[1]), (X.T * w) @ y)[0]
    except np.linalg.LinAlgError:
        return None


def report(D, sel, extra, name):
    n = int(sel.sum())
    if n < 5000:
        print(f"   {name:52s} insufficient ({n} bins)")
        return
    cs = D["case"][sel]
    order = np.argsort(cs, kind="stable")
    for key in ("case", "e", "m0", "dz", "dce", "pre", "df", "db"):
        pass
    sub = {k: D[k][sel][order] for k in ("case", "e", "m0", "dz", "dce", "pre", "df", "db")}
    sub["ncase"] = D["ncase"]
    allsel = np.ones(n, bool)
    starts = np.searchsorted(sub["case"], np.arange(D["ncase"]), side="left")
    ends = np.searchsorted(sub["case"], np.arange(D["ncase"]), side="right")
    span = ends - starts
    w1 = np.ones(n)
    pf = coef(sub, allsel, extra, sub["df"], w1)
    pb = coef(sub, allsel, extra, sub["db"], w1)
    if pf is None or pb is None:
        print(f"   {name:52s} fit failed")
        return
    diffs = []
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        w = np.repeat(cnt, span)
        a = coef(sub, allsel, extra, sub["df"], w); b = coef(sub, allsel, extra, sub["db"], w)
        if a is not None and b is not None:
            diffs.append(a - b)
    if len(diffs) < 50:
        print(f"   {name:52s} bootstrap failed")
        return
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    tag = "PRECEDENCE" if hi < 0 else ("REVERSED" if lo > 0 else "symmetric -- NO precedence")
    print(f"   {name:52s} fwd={pf:+7.3f} bwd={pb:+7.3f}  fwd-bwd={pf-pb:+7.3f} "
          f"[{lo:+.3f},{hi:+.3f}]  {tag}   n={n}, cases={len(np.unique(sub['case']))}")


def main():
    cohort = os.environ.get("COHORT", "prop")
    k = int(os.environ.get("K", "2"))
    HD = load(cohort)
    vals = [bd[t][3] for c, bd in HD.items() for t in bd if bd[t][3] == bd[t][3]]
    emg_cut = float(np.median(vals)) if len(vals) > 1000 else None
    print(f"cohort={cohort}  k=+/-{k} bins (+/-{30*k}s)  case fixed effects, {NBOOT} case-level bootstrap reps")
    print("outcome = signed change in MAP (mmHg); reported statistic = forward minus backward")

    for expo, lab in (("bs", "burst-suppressed FRACTION (per full suppression)"),
                      ("bsbin", "ANY burst suppression vs none"),
                      ("emg", "frontal EMG above median -- NEGATIVE CONTROL")):
        D = build(HD, k, expo, emg_cut)
        if D is None or len(D["case"]) < 5000:
            print(f"\n=== {lab} === insufficient")
            continue
        print(f"\n=== {lab} ===")
        allb = np.ones(len(D["case"]), bool)
        report(D, allb, [], "M0  MAP(t) + dose(t)                    [published]")
        report(D, allb, ["dce"], "M1  + dCe over the same window          [kinetics]")
        report(D, allb, ["pre"], "M2  + pre-existing pressure trend       [pre-trend]")
        report(D, allb, ["dce", "pre"], "M3  + both")
        stable = np.abs(D["dce"]) < 1e-6
        if stable.sum() > 5000:
            frac = 100 * stable.mean()
            report(D, stable, ["pre"], f"M4  STABLE-DOSE bins only ({frac:.0f}% of bins)")
        else:
            print(f"   M4  stable-dose subgroup too small ({int(stable.sum())} bins)")


if __name__ == "__main__":
    sys.exit(main())
