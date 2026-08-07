#!/usr/bin/env python3
"""E250-E259 -- a ten-part battery on the completed VitalDB ventilation-landmarked table.

PRE-REGISTRATION. Every prediction below was written and committed before the corresponding statistic
existed. Predictions are stated as directional claims with a named way to be wrong, per repo convention.

COHORT, shared by all ten: the 56,731-window table (56,237 `ok`), 2,589 single-agent cases,
sevo 1,274 / des 412 / ppf 903, 21 windows of 10 s at -300..+300 s about the RECOVERY landmark.

SCOPE, carried unchanged and not softened: the state label is the AIRWAY RECORD -- measured respiratory
rate against the ventilator's set rate. A brainstem BEHAVIOURAL OUTPUT, not consciousness. Recovery only.

NULLS. Leakage-type statistics use 2,000-draw patient-level permutation nulls rather than E248's 20,000.
That is a deliberate resolution choice for a battery and it is stated: it resolves p to ~0.0005, which is
ample for every threshold used here, and no verdict below turns on a margin smaller than the Monte Carlo
error (rule 46). Where a verdict would be close, the item says so.

======================================================================================================
E250 -- IS THE LEAKAGE AXIS THE SAME AS THE STATE AXIS?  *the central Challenge A question*

Challenge A asks for a representation that tracks state while MINIMISING drug identification. That is
only possible if the two are dissociable. Across the 19 candidates, correlate per-candidate leakage
(E248's P1, max over the three arm pairs) against per-candidate state tracking (E249's P2, |signed mean|).

PREDICTION: **POSITIVE, Spearman >= +0.4.** The measures that track the ventilation transition are the
same ones that identify the agent, because both are driven by where the drug puts the spectrum. If so,
no candidate in this panel can satisfy Challenge A, and the challenge is blocked on the INVENTORY rather
than on statistics.
WRONG IF: the correlation is near zero or negative, which would mean a low-leakage / high-tracking corner
exists and should be named.
GATE: both axes must vary across candidates (rule 53) -- IQR > 0 on each.

E251 -- BIS, THE COMMERCIAL INCUMBENT, THROUGH THE IDENTICAL LEAKAGE PATH

`meta_bis` is finite in 45,986 of 56,237 windows and >= 15 windows in 1,982 cases. Run it through E248's
exact P1 machinery.

PREDICTION: **BIS leaks at or above the MEDIAN candidate in all three arm pairs.** Kuizenga 2019 puts the
index at 46.7 for propofol against 68 for sevoflurane at matched behavioural depth -- a drug-dependent
offset is leakage by definition, and BIS is a proprietary composite of the same spectral quantities.
WRONG IF: BIS leaks below the median candidate, which would make the incumbent more agent-invariant than
our panel and would be the most important negative in this battery.
GATE (rule 53): BIS must track the ventilation transition in these cases, or a leakage comparison is
between two cohorts rather than two agents.

E252 -- THE PLACEBO LANDMARK FOR P2, WHICH E248 AND E249 NEVER RAN

E249 established that the state axis is alive. It never asked whether a FAKE landmark reproduces it.
Rule 64: a contrast split at an extremum is a time split in disguise, and only a random-split placebo
shows it. Re-run P2 with each case's landmark replaced by a uniformly drawn time inside its own window
span, preserving window count and every other aspect.

PREDICTION: **P2 collapses to within its null** -- |signed mean| < 0.05 for every candidate, against
observed values up to 0.3629.
WRONG IF: the placebo reproduces a substantial fraction of P2, which would mean E249's G1 was reading a
within-case time trend (electrode drift, temperature, cumulative artefact) rather than the transition,
and would retroactively withdraw G1.

E253 -- DOES THE STATE AXIS SURVIVE THE MONITOR'S OWN MUSCLE CHANNEL?

E22, E70 and E100 each turned out to be measuring muscle. E249 showed muscle tracks this transition
strongly (`emg_beta_gamma_fraction` +0.3386), which is expected -- the patient starts breathing. Rule 57
says our `emg_index` is a weak proxy and must not be used as ground truth; `meta_emg` is the BIS
monitor's own EMG output, a real instrument.
Within each patient, regress the candidate on the after-indicator with `meta_emg` as a covariate; report
the after-coefficient's sign consistency across patients, with and without the covariate.

PREDICTION: **`whole_head_exponent` retains >= 70 % of its sign consistency; `spectral_edge_95` and
`emg_beta_gamma_fraction` lose more, retaining < 70 %.** The aperiodic exponent is a broadband slope and
should be the most muscle-robust of the strong trackers.
WRONG IF: the exponent attenuates as much as the muscle-adjacent measures, which would put E249's
headline tracker in the same class as the artefact measures.

E254 -- IS LEAKAGE IN THE LEVEL OR IN THE CHANGE? (rule 12's decomposition)

Split each patient's candidate into (i) the pre-landmark median and (ii) post-median minus pre-median.
Run each through the P1 path separately.

PREDICTION: **leakage is concentrated in the LEVEL.** The level's leakage exceeds the change's in at
least 2 of 3 arm pairs for the majority of candidates. Agents differ in where they park the spectrum,
not primarily in how it moves through the return of spontaneous breathing.
WRONG IF: the change carries as much or more, which would mean agents differ in their DYNAMICS and would
be a substantially more interesting claim, and a harder one for any invariance method to remove.

E255 -- DOES LEAKAGE SURVIVE CONDITIONING ON STATE?

Compute leakage separately from pre-landmark windows only and post-landmark windows only.

PREDICTION: **present in both, and within 30 % of each other** for the top candidates -- the signature of
a level offset (E254) rather than a state-dependent effect.
WRONG IF: leakage appears in only one side, which would tie agent identity to a particular state and
change what "matched state" has to mean.

E256 -- HOW MANY INDEPENDENT STATE-TRACKING AXES? (rule 60, rule 68)

This project has repeatedly found its inventory collapses to one arousal axis. Correlate the per-patient
P2 AUCs across the candidates that passed G1, and report the leading eigenvalue's share.

PREDICTION: **one dominant axis, PC1 >= 50 % of variance.**
WRONG IF: PC1 < 50 %, which would be the first evidence in this programme of genuine multi-dimensionality
in state tracking and would deserve its own experiment rather than a line in a battery.

E257 -- THE 330-CASE COVERAGE GAP: IS IT ARM-RELATED? (owed, rule 14)

2,930 landmarked cases -> 2,600 with any usable window -> 2,589 after MIN_WIN. Drop rate by arm runs
sevo 13.57 % / des 10.43 % / ppf 9.34 %. Test the spread against a permutation null over arm labels, and
compare dropped against kept on age, BMI and anaesthesia duration.

PREDICTION: **the spread is real (permutation p < 0.05) and tracks anaesthesia duration** -- sevoflurane
cases run longer, so the fixed +-300 s grid more often runs past the record end.
WRONG IF: the spread is within its null, in which case the exclusion is benign and the caveat can be
dropped; or it is real but unrelated to duration, which would need a different explanation.

E258 -- IS LEAKAGE MODIFIED BY AGE?

E109 found BIS/exponent within-case discordance grows with age (+0.2592 [+0.1367, +0.3761]). Split at the
median age and recompute leakage in each stratum.

PREDICTION: **leakage is larger in the older stratum** for the majority of candidates.
WRONG IF: equal or reversed. Note in advance that the strata halve n, so the null floor rises by ~sqrt(2)
and only sizeable differences will be readable -- this item is powered to detect a large modification,
not a subtle one, and it says so rather than discovering it afterwards.

E259 -- RULE 90: DOES THE ESTIMATOR INCONSISTENCY IN THE APERIODIC FAMILY SHOW UP?

`whole_head_exponent` passes `loglog_robust` explicitly; `subband_exponents` (`exponent_low`,
`exponent_high`) does not and inherits the peak-biased `loglog_ols` default. Their docstring claims
"deliberately identical machinery". Correlate the three across patients.

PREDICTION: **`exponent_low` and `exponent_high` correlate with each other more than either does with
`whole_head_exponent`**, i.e. the family splits by ESTIMATOR rather than by frequency band.
WRONG IF: the correlation structure is ordered by band instead (low-with-whole > low-with-high), which
would mean the estimator difference is not doing visible work and rule 90's exposure is smaller than the
audit implied.

    python -m bsde.experiments.e250_battery
"""
from __future__ import annotations

import argparse, csv, glob, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
ARMS = ("sevo", "des", "ppf")
PAIRS = (("sevo", "des"), ("sevo", "ppf"), ("des", "ppf"))
MIN_WIN = 15
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def midranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def auc(pos, neg):
    pos = [x for x in pos if math.isfinite(x)]
    neg = [x for x in neg if math.isfinite(x)]
    if not pos or not neg:
        return float("nan")
    r = midranks(pos + neg)
    s = sum(r[:len(pos)])
    return (s - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def leak(va, vb, rng, reps):
    va = [x for x in va if math.isfinite(x)]
    vb = [x for x in vb if math.isfinite(x)]
    if len(va) < 5 or len(vb) < 5:
        return float("nan"), float("nan"), float("nan")
    obs = abs(auc(va, vb) - 0.5)
    pool = va + vb
    n1 = len(va)
    null = []
    for _ in range(reps):
        rng.shuffle(pool)
        a = auc(pool[:n1], pool[n1:])
        if math.isfinite(a):
            null.append(abs(a - 0.5))
    null.sort()
    p = sum(1 for v in null if v >= obs) / len(null) if null else float("nan")
    return obs, (null[int(0.95 * len(null))] if null else float("nan")), p


def patient_auc(vals, is_after):
    keep = [(v, a) for v, a in zip(vals, is_after) if math.isfinite(v)]
    if len(keep) < 4:
        return float("nan"), float("nan")
    v = [x[0] for x in keep]
    a = [x[1] for x in keep]
    n1 = sum(1 for x in a if x)
    n2 = len(a) - n1
    if not n1 or not n2:
        return float("nan"), float("nan")
    r = midranks(v)
    s = sum(rr for rr, aa in zip(r, a) if aa)
    n = len(r)
    mu = sum(r) / n
    pv = sum((x - mu) ** 2 for x in r) / n
    return ((s - n1 * (n1 + 1) / 2.0) / (n1 * n2),
            (n1 * n2 / (n - 1.0) * pv) / (n1 * n2) ** 2 if n > 1 else 0.0)


def spearman(x, y):
    pts = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(pts) < 4:
        return float("nan")
    rx = midranks([p[0] for p in pts])
    ry = midranks([p[1] for p in pts])
    return pearson(rx, ry)


def pearson(x, y):
    pts = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(pts) < 3:
        return float("nan")
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def median(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def load(args):
    lm = {}
    for p in sorted(glob.glob(args.landmarks)):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ARMS:
                lm[r["caseid"]] = r
    rows, cols = [], None
    for p in sorted(glob.glob(args.features)):
        rd = csv.DictReader(open(p))
        if cols is None:
            cols = [c for c in (rd.fieldnames or []) if not c.startswith("meta_") and c not in SKIP]
        for r in rd:
            if r.get("status") == "ok" and r.get("meta_caseid") in lm:
                rows.append(r)
    fin = {c: sum(1 for r in rows if math.isfinite(f(r.get(c)))) for c in cols}
    cols = [c for c in cols if fin[c] >= 0.20 * len(rows)]
    by = {}
    for r in rows:
        by.setdefault(r["meta_caseid"], []).append(r)
    all_by = dict(by)
    by = {k: v for k, v in by.items() if len(v) >= MIN_WIN}
    return lm, by, all_by, cols


def clinical():
    import gzip, io, urllib.request
    req = urllib.request.Request("https://api.vitaldb.net/cases", headers={"User-Agent": "bsde/1.0"})
    blob = urllib.request.urlopen(req, timeout=300).read()
    if blob[:2] == b"\x1f\x8b":
        blob = gzip.decompress(blob)
    out = {}
    for r in csv.DictReader(io.StringIO(blob.decode("utf-8-sig", "replace"))):
        ae, as_ = f(r.get("aneend")), f(r.get("anestart"))
        out[r["caseid"]] = {"age": f(r.get("age")), "bmi": f(r.get("bmi")),
                            "opdur_s": (ae - as_) if math.isfinite(ae) and math.isfinite(as_)
                            else float("nan")}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=os.path.join(RESULTS, "vitaldb_ventwin.s*.csv"))
    ap.add_argument("--landmarks", default=os.path.join(RESULTS, "vitaldb_vent_landmarks.s*.csv"))
    ap.add_argument("--p1", default=os.path.join(RESULTS, "e248_agent_leakage.json"))
    ap.add_argument("--p2", default=os.path.join(RESULTS, "e249_gate_completion.json"))
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=250)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e250_battery.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    R = {}

    lm, by, all_by, cols = load(a)
    clin = clinical()
    arm = {k: lm[k]["arm"] for k in by}
    if a.smoke:
        ks = sorted(arm); vs = [arm[k] for k in ks]; rng.shuffle(vs); arm = dict(zip(ks, vs))
        print("[SMOKE] arm labels permuted (rule 26)")
    rec = {k for k in by if lm[k].get("rec_ok") == "1"}
    t0 = {k: f(lm[k]["t_rec_s"]) for k in rec}
    print(f"[cohort] {len(by)} cases, {len(cols)} candidates, {len(rec)} with recovery landmark")

    # per-patient pre/post medians and the after-indicator, built once
    pre, post, lvl, chg, p2auc = {}, {}, {}, {}, {}
    emg_by = {}
    for cid in rec:
        rs = by[cid]
        offs = [f(r.get("meta_t_s")) - t0[cid] for r in rs]
        for c in cols + ["meta_bis", "meta_emg"]:
            vb = [f(r.get(c)) for r, o in zip(rs, offs) if o < 0]
            va = [f(r.get(c)) for r, o in zip(rs, offs) if o > 0]
            pre.setdefault(c, {})[cid] = median(vb)
            post.setdefault(c, {})[cid] = median(va)
            lvl.setdefault(c, {})[cid] = median(vb)
            chg.setdefault(c, {})[cid] = median(va) - median(vb)
            vals = [f(r.get(c)) for r in rs]
            aft = [o > 0 for o in offs]
            if a.smoke:
                aft = list(aft); rng.shuffle(aft)
            au, _ = patient_auc(vals, aft)
            p2auc.setdefault(c, {})[cid] = au
        emg_by[cid] = [f(r.get("meta_emg")) for r in rs]

    p1doc = json.load(open(a.p1)) if os.path.exists(a.p1) else None
    p2doc = json.load(open(a.p2)) if os.path.exists(a.p2) else None

    # ---------------------------------------------------------------- E250
    print("\n" + "=" * 92 + "\nE250 -- is the leakage axis the same as the state axis?")
    lk, st, names = [], [], []
    for c in cols:
        if not p1doc or not p2doc or c not in p2doc["p2"]:
            continue
        mx = max(p1doc["pairs"][n]["features"][c]["obs"] for n in p1doc["pairs"]
                 if c in p1doc["pairs"][n]["features"])
        s = abs(p2doc["p2"][c].get("obs", float("nan")))
        if math.isfinite(mx) and math.isfinite(s):
            lk.append(mx); st.append(s); names.append(c)
    rho = spearman(lk, st)
    iqr = lambda v: (sorted(v)[int(.75 * len(v))] - sorted(v)[int(.25 * len(v))]) if len(v) > 3 else 0
    gate = iqr(lk) > 0 and iqr(st) > 0
    print(f"  n={len(names)}  Spearman(leakage, state tracking) = {rho:+.4f}   "
          f"gate(both vary): {'PASS' if gate else 'FAIL'}")
    print(f"  PREDICTED >= +0.40  ->  {'MET' if math.isfinite(rho) and rho >= 0.40 else 'NOT MET'}")
    lo = [n for n, l, s in zip(names, lk, st) if l < median(lk) and s > median(st)]
    print(f"  low-leakage / high-tracking corner: {lo if lo else 'EMPTY'}")
    R["E250"] = {"rho": rho, "n": len(names), "gate": gate, "corner": lo,
                 "leakage": dict(zip(names, lk)), "state": dict(zip(names, st))}

    # ---------------------------------------------------------------- E251
    print("\n" + "=" * 92 + "\nE251 -- BIS through the identical leakage path")
    bis_cases = [c for c in rec if math.isfinite(lvl["meta_bis"][c])]
    bs = [p2auc["meta_bis"][c] - 0.5 for c in bis_cases
          if math.isfinite(p2auc["meta_bis"][c])]
    bis_state = sum(bs) / len(bs) if bs else float("nan")
    alive = abs(bis_state) > 0.05
    print(f"  BIS state tracking (signed mean AUC-0.5) = {bis_state:+.4f} over {len(bs)} cases"
          f"  -> aliveness gate {'PASS' if alive else 'FAIL'}")
    e251 = {"bis_state": bis_state, "n": len(bs), "alive": alive, "pairs": {}}
    for x, y in PAIRS:
        ax = [lvl["meta_bis"][c] for c in bis_cases if arm[c] == x]
        ay = [lvl["meta_bis"][c] for c in bis_cases if arm[c] == y]
        obs, p95, p = leak(ax, ay, rng, a.reps)
        med = median([p1doc["pairs"][f"{x}_vs_{y}"]["features"][c]["obs"] for c in cols
                      if c in p1doc["pairs"][f"{x}_vs_{y}"]["features"]]) if p1doc else float("nan")
        print(f"  {x}_vs_{y:5s} BIS leakage {obs:.4f} (null95 {p95:.4f}, p={p:.4f}) | "
              f"median candidate {med:.4f} -> BIS {'>=' if obs >= med else '<'} median")
        e251["pairs"][f"{x}_vs_{y}"] = {"obs": obs, "null_p95": p95, "p": p, "median_candidate": med,
                                        "n": [len(ax), len(ay)]}
    met = all(v["obs"] >= v["median_candidate"] for v in e251["pairs"].values()
              if math.isfinite(v["median_candidate"]))
    print(f"  PREDICTED BIS >= median candidate in all three  ->  {'MET' if met else 'NOT MET'}")
    e251["prediction_met"] = met
    R["E251"] = e251

    # ---------------------------------------------------------------- E252
    print("\n" + "=" * 92 + "\nE252 -- placebo landmark for P2")
    worst = 0.0
    e252 = {}
    top = sorted(cols, key=lambda c: -abs(p2doc["p2"][c]["obs"]) if p2doc and c in p2doc["p2"] else 0)[:6]
    for c in top:
        terms = []
        for cid in rec:
            rs = by[cid]
            ts = sorted(f(r.get("meta_t_s")) for r in rs)
            if len(ts) < 4:
                continue
            fake = rng.uniform(ts[1], ts[-2])
            au, _ = patient_auc([f(r.get(c)) for r in rs],
                                [f(r.get("meta_t_s")) > fake for r in rs])
            if math.isfinite(au):
                terms.append(au - 0.5)
        v = sum(terms) / len(terms) if terms else float("nan")
        real = p2doc["p2"][c]["obs"] if p2doc else float("nan")
        e252[c] = {"placebo": v, "real": real}
        worst = max(worst, abs(v))
        print(f"  {c:28s} placebo {v:+.4f}   real {real:+.4f}")
    ok = worst < 0.05
    print(f"  PREDICTED every |placebo| < 0.05  ->  {'MET' if ok else 'NOT MET'} (worst {worst:.4f})")
    R["E252"] = {"detail": e252, "worst_abs": worst, "prediction_met": ok}

    # ---------------------------------------------------------------- E253
    print("\n" + "=" * 92 + "\nE253 -- does the state axis survive the monitor's own EMG channel?")
    e253 = {}
    for c in ("whole_head_exponent", "spectral_edge_95", "emg_beta_gamma_fraction",
              "multiscale_entropy_slope"):
        if c not in cols:
            continue
        raw_sign, adj_sign, n = 0, 0, 0
        for cid in rec:
            rs = by[cid]
            offs = [f(r.get("meta_t_s")) - t0[cid] for r in rs]
            y = [f(r.get(c)) for r in rs]
            e = [f(r.get("meta_emg")) for r in rs]
            aft = [1.0 if o > 0 else 0.0 for o in offs]
            keep = [i for i in range(len(y)) if math.isfinite(y[i]) and math.isfinite(e[i])]
            if len(keep) < 8:
                continue
            yy = [y[i] for i in keep]; ee = [e[i] for i in keep]; aa = [aft[i] for i in keep]
            if len(set(aa)) < 2:
                continue
            b_raw = pearson(aa, yy)
            # partial correlation of (after, y) given emg
            r_ay, r_ae, r_ye = pearson(aa, yy), pearson(aa, ee), pearson(yy, ee)
            den = math.sqrt(max(1e-12, (1 - r_ae ** 2) * (1 - r_ye ** 2)))
            b_adj = (r_ay - r_ae * r_ye) / den if math.isfinite(den) and den > 0 else float("nan")
            if math.isfinite(b_raw) and math.isfinite(b_adj):
                n += 1
                raw_sign += 1 if b_raw > 0 else 0
                adj_sign += 1 if b_adj > 0 else 0
        if not n:
            continue
        raw_c = abs(raw_sign / n - 0.5) * 2
        adj_c = abs(adj_sign / n - 0.5) * 2
        ret = adj_c / raw_c if raw_c > 0 else float("nan")
        e253[c] = {"raw_consistency": raw_c, "adj_consistency": adj_c, "retained": ret, "n": n}
        print(f"  {c:28s} raw {raw_c:.4f} -> emg-adjusted {adj_c:.4f}   retained {ret:.3f}  n={n}")
    wh = e253.get("whole_head_exponent", {}).get("retained", float("nan"))
    others = [v["retained"] for k, v in e253.items() if k != "whole_head_exponent"]
    met = math.isfinite(wh) and wh >= 0.70
    print(f"  PREDICTED whole_head_exponent retains >= 0.70  ->  {'MET' if met else 'NOT MET'}")
    R["E253"] = {"detail": e253, "prediction_met": met}

    # ---------------------------------------------------------------- E254
    print("\n" + "=" * 92 + "\nE254 -- is leakage in the LEVEL or the CHANGE? (rule 12)")
    e254, lvl_wins = {}, 0
    for c in cols:
        d = {}
        for x, y in PAIRS:
            la, _, _ = leak([lvl[c][i] for i in rec if arm[i] == x],
                            [lvl[c][i] for i in rec if arm[i] == y], rng, 400)
            ca, _, _ = leak([chg[c][i] for i in rec if arm[i] == x],
                            [chg[c][i] for i in rec if arm[i] == y], rng, 400)
            d[f"{x}_vs_{y}"] = {"level": la, "change": ca}
        n_lvl = sum(1 for v in d.values()
                    if math.isfinite(v["level"]) and math.isfinite(v["change"])
                    and v["level"] > v["change"])
        e254[c] = {"pairs": d, "level_wins": n_lvl}
        if n_lvl >= 2:
            lvl_wins += 1
    print(f"  level out-leaks change in >=2 of 3 pairs for {lvl_wins} of {len(cols)} candidates")
    for c in sorted(e254, key=lambda k: -e254[k]["level_wins"])[:5]:
        d = e254[c]["pairs"]
        print(f"    {c:28s} " + "  ".join(f"{k.split('_vs_')[0][:4]}/{k.split('_vs_')[1][:4]}:"
              f"L{d[k]['level']:.3f}/C{d[k]['change']:.3f}" for k in d))
    met = lvl_wins > len(cols) / 2
    print(f"  PREDICTED level dominates for a majority  ->  {'MET' if met else 'NOT MET'}")
    R["E254"] = {"level_wins": lvl_wins, "n_candidates": len(cols), "prediction_met": met,
                 "detail": e254}

    # ---------------------------------------------------------------- E255
    print("\n" + "=" * 92 + "\nE255 -- does leakage survive conditioning on state?")
    e255 = {}
    for c in sorted(cols, key=lambda k: -R["E250"]["leakage"].get(k, 0))[:6]:
        d = {}
        for x, y in PAIRS:
            pa, _, _ = leak([pre[c][i] for i in rec if arm[i] == x],
                            [pre[c][i] for i in rec if arm[i] == y], rng, 400)
            qa, _, _ = leak([post[c][i] for i in rec if arm[i] == x],
                            [post[c][i] for i in rec if arm[i] == y], rng, 400)
            d[f"{x}_vs_{y}"] = {"pre": pa, "post": qa,
                                "ratio": (min(pa, qa) / max(pa, qa)) if max(pa, qa) > 0 else float("nan")}
        e255[c] = d
        print(f"  {c:28s} " + "  ".join(f"{k[:9]}: pre {v['pre']:.3f} post {v['post']:.3f} "
              f"(r={v['ratio']:.2f})" for k, v in d.items()))
    ratios = [v["ratio"] for c in e255 for v in e255[c].values() if math.isfinite(v["ratio"])]
    frac = sum(1 for r in ratios if r >= 0.70) / len(ratios) if ratios else float("nan")
    print(f"  PREDICTED pre and post within 30% of each other  ->  "
          f"{frac:.2f} of {len(ratios)} comparisons satisfy it")
    R["E255"] = {"detail": e255, "fraction_within_30pct": frac}

    # ---------------------------------------------------------------- E256
    print("\n" + "=" * 92 + "\nE256 -- how many independent state-tracking axes?")
    live = [c for c in cols if p2doc and c in p2doc["p2"]
            and p2doc["p2"][c].get("margin", -1) >= 0.10]
    ids = [i for i in rec if all(math.isfinite(p2auc[c][i]) for c in live)]
    M = [[p2auc[c][i] for c in live] for i in ids]
    k = len(live)
    if k >= 2 and len(ids) > k:
        mu = [sum(row[j] for row in M) / len(M) for j in range(k)]
        sd = [math.sqrt(sum((row[j] - mu[j]) ** 2 for row in M) / len(M)) or 1.0 for j in range(k)]
        Z = [[(row[j] - mu[j]) / sd[j] for j in range(k)] for row in M]
        C = [[sum(Z[r][i] * Z[r][j] for r in range(len(Z))) / len(Z) for j in range(k)]
             for i in range(k)]
        v = [1.0] * k
        for _ in range(300):
            w = [sum(C[i][j] * v[j] for j in range(k)) for i in range(k)]
            nrm = math.sqrt(sum(x * x for x in w)) or 1.0
            v = [x / nrm for x in w]
        lam = sum(v[i] * sum(C[i][j] * v[j] for j in range(k)) for i in range(k))
        share = lam / k
        print(f"  {k} live candidates, {len(ids)} patients; PC1 eigenvalue {lam:.3f} "
              f"of {k} -> {share:.1%} of variance")
        met = share >= 0.50
        print(f"  PREDICTED PC1 >= 50%  ->  {'MET' if met else 'NOT MET'}")
        R["E256"] = {"k": k, "n": len(ids), "pc1_eigenvalue": lam, "pc1_share": share,
                     "prediction_met": met}

    # ---------------------------------------------------------------- E257
    print("\n" + "=" * 92 + "\nE257 -- is the coverage gap arm-related?")
    landmarked = {x: [c for c in lm if lm[c]["arm"] == x] for x in ARMS}
    kept_ids = set(by)
    rate = {x: 1 - sum(1 for c in landmarked[x] if c in kept_ids) / len(landmarked[x]) for x in ARMS}
    obs_spread = max(rate.values()) - min(rate.values())
    allc = [c for x in ARMS for c in landmarked[x]]
    labs = [x for x in ARMS for _ in landmarked[x]]
    drop = {c: (c not in kept_ids) for c in allc}
    null = []
    for _ in range(a.reps):
        rng.shuffle(labs)
        r = {}
        for x in ARMS:
            idx = [allc[i] for i in range(len(allc)) if labs[i] == x]
            r[x] = sum(1 for c in idx if drop[c]) / len(idx)
        null.append(max(r.values()) - min(r.values()))
    null.sort()
    p = sum(1 for v in null if v >= obs_spread) / len(null)
    print(f"  drop rate by arm: " + ", ".join(f"{k}={v:.4f}" for k, v in rate.items()))
    print(f"  spread {obs_spread:.4f}   permutation null 95th {null[int(0.95*len(null))]:.4f}   "
          f"p = {p:.4f}")
    dur_d = median([clin.get(c, {}).get("opdur_s", float("nan")) for c in allc if drop[c]])
    dur_k = median([clin.get(c, {}).get("opdur_s", float("nan")) for c in allc if not drop[c]])
    age_d = median([clin.get(c, {}).get("age", float("nan")) for c in allc if drop[c]])
    age_k = median([clin.get(c, {}).get("age", float("nan")) for c in allc if not drop[c]])
    print(f"  anaesthesia duration  dropped {dur_d:.0f}s  vs kept {dur_k:.0f}s")
    print(f"  age                   dropped {age_d:.0f}   vs kept {age_k:.0f}")
    met = p < 0.05
    print(f"  PREDICTED spread real (p<0.05) and tied to duration  ->  "
          f"p {'MET' if met else 'NOT MET'}")
    R["E257"] = {"rate": rate, "spread": obs_spread, "p": p, "null_p95": null[int(0.95 * len(null))],
                 "opdur_dropped": dur_d, "opdur_kept": dur_k, "age_dropped": age_d, "age_kept": age_k,
                 "prediction_met": met}

    # ---------------------------------------------------------------- E258
    print("\n" + "=" * 92 + "\nE258 -- is leakage modified by age?")
    ages = {c: clin.get(c, {}).get("age", float("nan")) for c in rec}
    amed = median(list(ages.values()))
    old = {c for c in rec if math.isfinite(ages[c]) and ages[c] >= amed}
    yng = {c for c in rec if math.isfinite(ages[c]) and ages[c] < amed}
    print(f"  median age {amed:.0f}; older n={len(old)}, younger n={len(yng)}")
    e258, older_bigger, tot = {}, 0, 0
    for c in sorted(cols, key=lambda k: -R["E250"]["leakage"].get(k, 0))[:8]:
        d = {}
        for x, y in PAIRS:
            o, _, _ = leak([lvl[c][i] for i in old if arm[i] == x],
                           [lvl[c][i] for i in old if arm[i] == y], rng, 400)
            g, _, _ = leak([lvl[c][i] for i in yng if arm[i] == x],
                           [lvl[c][i] for i in yng if arm[i] == y], rng, 400)
            d[f"{x}_vs_{y}"] = {"old": o, "young": g}
            if math.isfinite(o) and math.isfinite(g):
                tot += 1
                older_bigger += 1 if o > g else 0
        e258[c] = d
        print(f"  {c:26s} " + "  ".join(f"{k[:9]}: old {v['old']:.3f} yng {v['young']:.3f}"
                                        for k, v in d.items()))
    frac = older_bigger / tot if tot else float("nan")
    met = frac > 0.5
    print(f"  older larger in {older_bigger}/{tot} = {frac:.2f}  ->  "
          f"PREDICTION {'MET' if met else 'NOT MET'}")
    R["E258"] = {"median_age": amed, "n_old": len(old), "n_young": len(yng),
                 "fraction_older_larger": frac, "prediction_met": met, "detail": e258}

    # ---------------------------------------------------------------- E259
    print("\n" + "=" * 92 + "\nE259 -- rule 90: does the aperiodic family split by ESTIMATOR?")
    trio = [c for c in ("whole_head_exponent", "exponent_low", "exponent_high") if c in cols]
    if len(trio) == 3:
        ids = [i for i in rec if all(math.isfinite(lvl[c][i]) for c in trio)]
        g = lambda c: [lvl[c][i] for i in ids]
        r_lh = spearman(g("exponent_low"), g("exponent_high"))
        r_wl = spearman(g("whole_head_exponent"), g("exponent_low"))
        r_wh = spearman(g("whole_head_exponent"), g("exponent_high"))
        print(f"  n={len(ids)}")
        print(f"  low  ~ high (same estimator, different band) : {r_lh:+.4f}")
        print(f"  whole ~ low  (diff estimator, nested band)   : {r_wl:+.4f}")
        print(f"  whole ~ high (diff estimator, nested band)   : {r_wh:+.4f}")
        met = math.isfinite(r_lh) and abs(r_lh) > max(abs(r_wl), abs(r_wh))
        print(f"  PREDICTED |low~high| > both whole-pairs  ->  {'MET' if met else 'NOT MET'}")
        R["E259"] = {"n": len(ids), "low_high": r_lh, "whole_low": r_wl, "whole_high": r_wh,
                     "prediction_met": met}

    print("\n" + "=" * 92)
    for k in sorted(R):
        v = R[k].get("prediction_met")
        print(f"  {k}: prediction {'MET' if v else 'NOT MET' if v is False else 'descriptive'}")
    if not a.smoke:
        json.dump(R, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    else:
        print("\n[SMOKE] complete; nothing above is a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
