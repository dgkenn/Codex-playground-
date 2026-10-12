#!/usr/bin/env python3
"""TWO tests that attack the mechanism from angles nothing else in this project has: REVERSIBILITY, and killing
the cerebral-hypoperfusion rival.

=== TEST 1: REVERSIBILITY (on - off - on) ===

Everything so far asks what happens AFTER suppression begins. The complementary question is what happens after it
ENDS. If suppression causes vasodilation through a transient withdrawal of vasomotor tone, then pressure should
RECOVER once the suppressed state resolves. Observational data rarely offers a crossover; a within-patient
on-off-on pattern is the closest thing available, and a recovery signature is much harder to explain by
confounding than an onset association is, because a confounder would have to switch off on the same schedule.

    exposure   bins classified by their position relative to a suppression episode, using only the PAST for the
               "during" categories and only the past for offset timing as well:
                   DURING      suppression in bin t
                   OFF+1       first bin after a suppression run ended
                   OFF+2..3    2-3 bins after it ended
                   OFF+4..8    4-8 bins after
                   reference   bins with no suppression in the preceding 10 bins (a clean baseline, not merely
                               "not currently suppressed", which would be contaminated by recent episodes)
    outcome    forward change in MAP over the next k bins
    PREDICTION registered before running: the forward change is NEGATIVE during suppression and turns POSITIVE
               (recovery) in the bins after offset, returning toward zero as time from offset grows.
    FALSIFICATION: if pressure keeps falling after suppression ends, the association is not a transient causal
               effect of the state -- it is drift, or a marker of a patient trajectory that suppression merely
               labels.

=== TEST 2: THE CEREBRAL-HYPOPERFUSION RIVAL, KILLED BY RESTRICTION ===

The standard alternative in the literature is that low pressure causes suppression, via reduced cerebral
perfusion -- burst suppression "might be caused by hypotension resulting in a reduced cerebral circulation", and
suppression co-occurs with cerebral desaturation. Our forward-minus-backward asymmetry addresses direction in
general, but restriction addresses it decisively: cerebral autoregulation holds perfusion roughly constant above
a MAP of about 60-70 mmHg in most patients, so at MAP well ABOVE that threshold hypoperfusion cannot plausibly be
producing the suppression.

    The asymmetry is therefore re-estimated in bins stratified by CURRENT MAP:
        >= 90, 80-90, 70-80, < 70 mmHg
    PREDICTION: the asymmetry PERSISTS in the high-MAP strata. If it exists only below 70 mmHg, the rival
    hypothesis explains the data and ours does not.
    Note this is the mirror image of the retracted two-phenotype analysis, and it is NOT the same test: that one
    conditioned on MAP relative to the patient's own baseline and compared significance across strata; this one
    conditions on ABSOLUTE pressure relative to a physiological autoregulation threshold, and the between-stratum
    difference is bootstrapped rather than eyeballed.

Estimator throughout: within-case fixed effects, MAP(t) + dose + dCe + pre-trend over [t-3k, t-2k], MAP filtered
to a physiologic window, case-level cluster bootstrap.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
NBOOT = int(os.environ.get("NBOOT", "300"))
rng = np.random.default_rng(20260725)
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))


def _map_ok(raw):
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
                HD[cid][t] = [float(d["bs"]), _map_ok(d["mbp"]),
                              float(d["ce"]) if d["ce"] else np.nan]
            except Exception:
                pass
    return HD


def build(HD, k):
    cols = defaultdict(list); ci = {}
    for c, bd in HD.items():
        ts = sorted(t for t in bd if bd[t][2] == bd[t][2] and bd[t][2] >= 1.0)
        if len(ts) < 32:
            continue
        supp = {t: (bd[t][0] == bd[t][0] and bd[t][0] > 0) for t in ts}
        # bins since suppression last ended, using only the past
        since = {}
        last_end = None
        for i, t in enumerate(ts):
            if supp[t]:
                since[t] = 0                      # currently suppressed
                last_end = None
            else:
                if i > 0 and supp[ts[i - 1]]:
                    last_end = i
                since[t] = (i - last_end + 1) if last_end is not None else 10 ** 6
        for t in ts[20:]:
            tf = t + 30.0 * k; tb = t - 30.0 * k; tb2 = t - 60.0 * k; tb3 = t - 90.0 * k
            if tf not in bd or tb not in bd or tb2 not in bd or tb3 not in bd:
                continue
            bs, m, dose = bd[t]
            mf = bd[tf][1]; mb = bd[tb][1]; mb2 = bd[tb2][1]; mb3 = bd[tb3][1]; doseb = bd[tb][2]
            if not (m == m and mf == mf and mb == mb and mb2 == mb2 and mb3 == mb3
                    and dose == dose and doseb == doseb and bs == bs):
                continue
            if c not in ci:
                ci[c] = len(ci)
            s = since[t]
            cols["case"].append(ci[c])
            cols["during"].append(1.0 if s == 0 else 0.0)
            cols["off1"].append(1.0 if s == 1 else 0.0)
            cols["off23"].append(1.0 if 2 <= s <= 3 else 0.0)
            cols["off48"].append(1.0 if 4 <= s <= 8 else 0.0)
            cols["m0"].append(m); cols["dz"].append(dose)
            cols["dce"].append(dose - doseb); cols["pre"].append(mb2 - mb3)
            cols["df"].append(mf - m); cols["db"].append(mb - m)
            cols["bs"].append(1.0 if bs > 0 else 0.0)
    D = {a: np.asarray(b, np.float64) for a, b in cols.items()}
    D["case"] = D["case"].astype(np.int32); D["ncase"] = len(ci)
    return D


def fit(sub, expo, dy, w, ncase):
    mat = np.column_stack([sub[e] for e in expo] + [sub["m0"], sub["dz"], sub["dce"], sub["pre"], dy])
    sw = np.bincount(sub["case"], weights=w, minlength=ncase)
    sw = np.where(sw > 0, sw, 1.0)
    dm = np.empty_like(mat)
    for j in range(mat.shape[1]):
        mu = np.bincount(sub["case"], weights=w * mat[:, j], minlength=ncase) / sw
        dm[:, j] = mat[:, j] - mu[sub["case"]]
    X = dm[:, :-1]; y = dm[:, -1]
    try:
        return np.linalg.solve((X.T * w) @ X + 1e-10 * np.eye(X.shape[1]), (X.T * w) @ y)[:len(expo)]
    except np.linalg.LinAlgError:
        return None


def reversibility(D):
    expo = ["during", "off1", "off23", "off48"]
    labels = ["DURING suppression", "1 bin after it ends", "2-3 bins after", "4-8 bins after"]
    n = len(D["case"])
    span = (np.searchsorted(D["case"], np.arange(D["ncase"]), side="right")
            - np.searchsorted(D["case"], np.arange(D["ncase"]), side="left"))
    w1 = np.ones(n)
    pt = fit(D, expo, D["df"], w1, D["ncase"])
    if pt is None:
        print("   fit failed"); return
    boots = [[] for _ in expo]
    for _ in range(NBOOT):
        cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
        v = fit(D, expo, D["df"], np.repeat(cnt, span), D["ncase"])
        if v is None:
            continue
        for j in range(len(expo)):
            boots[j].append(v[j])
    print("\n=== TEST 1: REVERSIBILITY -- forward dMAP by position relative to a suppression episode ===")
    print("   reference = bins with NO suppression in the preceding 10 bins")
    for j, nm in enumerate(labels):
        if len(boots[j]) < 50:
            print(f"   {nm:24s} bootstrap failed"); continue
        lo, hi = np.percentile(boots[j], [2.5, 97.5])
        cnt_ = int(D[expo[j]].sum())
        print(f"   {nm:24s} {pt[j]:+7.3f} mmHg [{lo:+7.3f},{hi:+7.3f}] "
              f"{'*' if (lo>0 or hi<0) else 'ns'}   bins={cnt_}")
    print("   [prediction: negative DURING, turning POSITIVE after offset as pressure recovers]")


def autoreg(D):
    print("\n=== TEST 2: does the asymmetry survive ABOVE the autoregulation threshold? ===")
    print("   if suppression were caused by cerebral hypoperfusion it should vanish at high MAP")
    bands = [(90, 1e9, "MAP >= 90"), (80, 90, "MAP 80-90"), (70, 80, "MAP 70-80"), (0, 70, "MAP < 70")]
    span_all = None
    for lo_, hi_, nm in bands:
        msk = (D["m0"] >= lo_) & (D["m0"] < hi_)
        if msk.sum() < 20000:
            print(f"   {nm:12s} insufficient ({int(msk.sum())} bins)"); continue
        sub = {kk: D[kk][msk] for kk in ("case", "bs", "m0", "dz", "dce", "pre", "df", "db")}
        o = np.argsort(sub["case"], kind="stable")
        sub = {kk: v[o] for kk, v in sub.items()}
        span = (np.searchsorted(sub["case"], np.arange(D["ncase"]), side="right")
                - np.searchsorted(sub["case"], np.arange(D["ncase"]), side="left"))
        w1 = np.ones(len(sub["case"]))
        f = fit(sub, ["bs"], sub["df"], w1, D["ncase"])
        b = fit(sub, ["bs"], sub["db"], w1, D["ncase"])
        if f is None or b is None:
            print(f"   {nm:12s} fit failed"); continue
        bd = []
        for _ in range(NBOOT):
            cnt = np.bincount(rng.integers(0, D["ncase"], D["ncase"]), minlength=D["ncase"]).astype(np.float64)
            w = np.repeat(cnt, span)
            a2 = fit(sub, ["bs"], sub["df"], w, D["ncase"]); b2 = fit(sub, ["bs"], sub["db"], w, D["ncase"])
            if a2 is not None and b2 is not None:
                bd.append(a2[0] - b2[0])
        if len(bd) < 50:
            print(f"   {nm:12s} bootstrap failed"); continue
        l2, h2 = np.percentile(bd, [2.5, 97.5])
        d = f[0] - b[0]
        print(f"   {nm:12s} fwd={f[0]:+7.3f} bwd={b[0]:+7.3f}  fwd-bwd={d:+7.3f} [{l2:+7.3f},{h2:+7.3f}] "
              f"{'*' if (l2>0 or h2<0) else 'ns'}   bins={int(msk.sum())}")
    print("   [prediction: the asymmetry PERSISTS at MAP >= 80, where autoregulation protects perfusion]")


def main():
    cohort = os.environ.get("COHORT", "prop")
    k = int(os.environ.get("K", "4"))
    D = build(load(cohort), k)
    n = len(D.get("case", []))
    if n < 10000:
        print(f"insufficient rows ({n})"); return
    o = np.argsort(D["case"], kind="stable")
    for key in list(D.keys()):
        if key != "ncase":
            D[key] = D[key][o]
    print(f"cohort={cohort}  k=+/-{k} bins (+/-{30*k}s);  {n} bins, {D['ncase']} cases; {NBOOT} bootstrap reps")
    reversibility(D)
    autoreg(D)


if __name__ == "__main__":
    sys.exit(main())
