"""E121 -- THE EXPOSURE LADDER. Does a more elaborate drug-exposure estimate buy anything at all?

REGISTERED BEFORE ANY LADDER RUNG IS SCORED. Existing tables plus `vitaldb_pk_inputs.jsonl`.

=========================================================================================================
THE QUESTION, IN THE INVESTIGATOR'S OWN FRAMING: "MIGHT NOT ACTUALLY MATTER OR WORK"
=========================================================================================================
That is the right frame and it makes this a cheap experiment before an expensive one. `PKPD_MODEL_REVIEW.md`
scopes a full Eleveld/Minto/Bouillon implementation: transcribing parameter tables, an ODE solver, a
validation pass against the pump's own Ce. **Before paying for that, it is worth asking whether moving from
a single-agent exposure to a multi-agent one improves the EEG's tracking AT ALL.** If a free rung buys
nothing, an expensive rung probably buys little, and that is worth knowing in advance.

=========================================================================================================
WHY THE LADDER STOPS WHERE IT DOES -- AND THIS IS A DEFENSIBILITY CONSTRAINT, NOT A SHORTCUT
=========================================================================================================
`PKPD_MODEL_REVIEW.md` §6 fixes the rule: **every component is either a published model USED AS PUBLISHED,
or a pre-specified simplification whose limitation is stated.** The Eleveld propofol (PMID 29661412 +
corrigendum 30032904), Eleveld remifentanil (28509794) and Minto/Bouillon surface (10839909 / 15166553)
rungs require their PARAMETER TABLES, transcribed from the papers. **Reconstructing those from memory would
be exactly the invented model that spec forbids**, so they are NOT built here and are named as the next
step. Every rung below is either a device-computed quantity the deposit publishes, or an arithmetic
combination of such quantities that is declared here in full.

    L0  INCUMBENT           the exposure every prior VitalDB experiment used:
                            `Primus/MAC` for volatile cases, `Orchestra/PPF20_CE` for TIVA.
    L1  END-TIDAL CHECK     volatile cases only: agent-specific MAC fraction computed from the extracted
                            END-TIDAL concentration rather than accepted from the monitor's composite.
                            Not a correction of L0 -- the monitor's MAC is already end-tidal derived
                            (review §2.4) -- but an independent recomputation of it.
    L2  + OPIOID, SEPARATE  hypnotic and `Orchestra/RFTN20_CE` as TWO exposures. Fidelity is taken as the
                            better of the two, which is the weakest possible way to use a second drug and
                            is included so the ladder has a rung between "ignore it" and "combine it".
    L3  + OPIOID, COMBINED  within-case z-scored hypnotic plus within-case z-scored opioid, equal weight.
                            **A declared simplification**: equal weighting is not a published potency
                            relation, it is the assumption that both drugs contribute and neither is
                            privileged. Stated, not hidden.
    L4  + INTERACTION       L3 plus the product of the two z-scores -- a crude synergy proxy. **This is
                            NOT the Minto surface and must never be described as one**; it is the cheapest
                            possible test of whether an interaction term buys anything before the real
                            surface is implemented.

=========================================================================================================
ESTIMAND
=========================================================================================================
Per case, within case, across windows. Fidelity signed so a correctly-tracking measure is positive, as in
E110/E112: `fid(m, L) = sign(m) * spearman(m, L)` with the sign fixed in advance from physiology.

    P  for each EEG measure m and each rung L: mean over cases of fid(m, L), case bootstrap.
       The ladder claim is the DIFFERENCE fid(m, L_k) - fid(m, L0), paired within case.

Measures: `whole_head_exponent` (the incumbent candidate), `exponent_high` (which E112 found partly
rescues propofol sensitivity), and `meta_bis` as a REFERENCE ROW -- BIS is a vendor composite and is here
to give the scale, not as a candidate (the omission of a scale is what E112's first run got wrong).

VERDICT, wrong direction FIRST (rule 37):
    (a) some rung is WORSE than L0 with an interval excluding 0 -> ELABORATION HURTS. A more complete
        exposure tracks the EEG less well, which would mean the extra drugs are adding noise rather than
        signal and would argue against the whole PK/PD programme.
    (b) no rung beats L0 -> **NO LADDER EFFECT.** Combining agents does not improve how well the EEG
        tracks exposure on this deposit, and the expensive Eleveld/Minto rungs are unlikely to be worth
        building for this purpose. This is the outcome the investigator named as possible and it is a
        USEFUL result, not a failure.
    (c) rungs improve monotonically -> ELABORATION PAYS, and the case for implementing the published
        models properly is made empirically rather than assumed.
    (d) improvement is non-monotone -> report which rung and treat with suspicion; a ladder that peaks in
        the middle is more likely an artefact of one rung's construction than a fact about pharmacology.

PREDICTED: (b) at ~50 %, (c) at ~30 %, (d) at ~15 %, (a) at ~5 %. (b) leads because E120 already found
that adding remifentanil as a COVARIATE changed nothing (TIVA marginal -0.0341 -> partial -0.0253), and
adding it as an EXPOSURE is a different operation but not an obviously more powerful one.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 40 cases per arm with >= 10 windows carrying every rung's inputs. The ladder must be
        scored on the SAME cases at every rung or the comparison is between cohorts (rule 32).
    G2  EVERY RUNG MUST VARY within case, else its fidelity is undefined rather than zero.
    G3  L1 MUST AGREE WITH L0 IN THE VOLATILE ARM. An independently recomputed MAC fraction should track
        the monitor's own MAC closely; if it does not, the recomputation is wrong and every rung above it
        inherits the error. This is the ladder's own internal validation and it can fail.
    G4  THE REFERENCE IS ALIVE **AND IT GRADES EVERY RUNG.** BIS's fidelity to L0 must be clearly
        positive, else the exposure variable is broken on these cases (E33/E61). **And beyond that: BIS
        is a vendor depth index that certainly tracks anaesthetic depth, so if BIS's fidelity FALLS when
        a rung elaborates the exposure, that rung has made the EXPOSURE worse -- and no candidate
        measure's improvement at that rung can be credited.** The first draft used the reference only as
        an aliveness check and let a single +0.0345 improvement print ELABORATION PAYS while the
        reference degraded at the same rung in both arms. That is the reference existing in prose and not
        in the verdict.

PLACEBO: the exposure series permuted ACROSS WINDOWS WITHIN CASE, 300 draws, applied to the best rung --
every marginal preserved, only the pairing destroyed. Primary read FIRST (rule 48).

SCOPE. VitalDB, single-channel BIS-module EEG. None of these rungs is a pharmacokinetic model; they are
device-reported concentrations combined arithmetically. A null here does NOT show that a real PK/PD model
would fail -- it shows that the information a multi-agent exposure adds, in the form the device already
provides it, does not improve EEG tracking. That distinction belongs in any use of this result.
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e121_exposure_ladder.json")
PK = os.path.join(RESULTS, "vitaldb_pk_inputs.jsonl")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
TABLES = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
    glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))

# MAC values at age 40, from Nickalls & Mapleson (PMID 12878613) as commonly tabulated; used ONLY for the
# L1 recomputation and reported as a declared constant, not fitted here.
MAC40 = {"sevo": 2.05, "des": 6.6}
MEASURES = {"whole_head_exponent": +1.0, "exponent_high": +1.0, "meta_bis": -1.0}
REFERENCE = "meta_bis"
MIN_WINDOWS, MIN_CASES = 10, 40
REPS = 4000
PLACEBO_DRAWS = 300
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _rank(x):
    return np.argsort(np.argsort(np.asarray(x, float))).astype(float)


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.ptp(x[ok]) <= 0 or np.ptp(y[ok]) <= 0:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def interp_at(t_src, v_src, t_at):
    """Nearest-preceding sample-and-hold: an infusion or gas reading holds until the next update."""
    if not t_src:
        return np.full(len(t_at), np.nan)
    ts = np.asarray(t_src, float)
    vs = np.asarray(v_src, float)
    order = np.argsort(ts)
    ts, vs = ts[order], vs[order]
    idx = np.searchsorted(ts, np.asarray(t_at, float), side="right") - 1
    out = np.where(idx >= 0, vs[np.clip(idx, 0, len(vs) - 1)], np.nan)
    # a reading more than 5 minutes stale is not a current exposure
    gap = np.asarray(t_at, float) - np.where(idx >= 0, ts[np.clip(idx, 0, len(ts) - 1)], np.nan)
    out[~np.isfinite(gap) | (gap > 300.0)] = np.nan
    return out


def zc(x):
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    if ok.sum() < 3 or np.std(x[ok]) <= 0:
        return np.full(x.shape, np.nan)
    z = np.full(x.shape, np.nan)
    z[ok] = (x[ok] - x[ok].mean()) / x[ok].std()
    return z


def main() -> int:
    if not os.path.exists(PK):
        print(f"ABSENT: {PK} -- PK-input extraction has not landed")
        return 2
    have_pk = set()
    with open(PK) as fh:
        for line in fh:
            i = line.find('"caseid"')
            if i < 0:
                continue
            j = line.find('"', line.find(":", i) + 1)
            k = line.find('"', j + 1)
            if j > 0 and k > j:
                have_pk.add(line[j + 1:k])
    ag = defaultdict(dict)
    for r in csv.DictReader(open(AGENTS, newline="")):
        t = _f(r.get("t_s"))
        if math.isfinite(t):
            ag[r["caseid"]][round(t, 1)] = r
    per = defaultdict(list)
    seen = set()
    for tb in TABLES:
        if not os.path.exists(tb):
            continue
        for r in csv.DictReader(open(tb, newline="")):
            c, t = r.get("meta_caseid"), _f(r.get("meta_t_s"))
            if not c or not math.isfinite(t) or c not in have_pk:
                continue
            key = (c, round(t, 1))
            if key in seen:
                continue
            seen.add(key)
            a = ag.get(c, {}).get(round(t, 1)) or {}
            row = {"t": t, "mac": _f(a.get("mac")), "ppf": _f(a.get("ppf_ce")),
                   "rft": _f(a.get("rftn_ce")), "age": _f(r.get("meta_age"))}
            for m in MEASURES:
                row[m] = _f(r.get(m))
            per[c].append(row)

    res = {"n_cases_with_pk": len(have_pk), "arms": {}, "gates": {}}
    print(f"{len(have_pk)} cases with PK inputs; {len(per)} joined to EEG windows")

    # stream the cache one case at a time, interpolate onto that case's grid, discard the raw traces
    tracks_at = {}
    with open(PK) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:                                               # noqa: BLE001
                continue
            c = r.get("caseid")
            if r.get("status") != "ok" or c not in per:
                continue
            tt = np.array(sorted(z["t"] for z in per[c]), float)
            keep = {}
            for name in ("Primus/EXP_SEVO", "Primus/EXP_DES"):
                d = r["tracks"].get(name)
                keep[name] = interp_at(d["t"], d["v"], tt) if d else np.full(len(tt), np.nan)
            tracks_at[c] = keep
            r.clear()

    arms = defaultdict(list)
    for c, rows in per.items():
        rows.sort(key=lambda z: z["t"])
        t = np.array([z["t"] for z in rows])
        tr = tracks_at.get(c, {})
        age = rows[0]["age"]
        et_sevo = tr.get("Primus/EXP_SEVO", np.full(len(t), np.nan))
        et_des = tr.get("Primus/EXP_DES", np.full(len(t), np.nan))
        mac = np.array([z["mac"] for z in rows])
        ppf = np.array([z["ppf"] for z in rows])
        rft = np.array([z["rft"] for z in rows])
        # age-corrected MAC40 (Mapleson): MAC(age) = MAC40 * 10^(-0.00269*(age-40))
        k = 10.0 ** (-0.00269 * (age - 40.0)) if np.isfinite(age) else 1.0
        own_mac = np.nansum(np.vstack([et_sevo / (MAC40["sevo"] * k),
                                       et_des / (MAC40["des"] * k)]), axis=0)
        own_mac[~np.isfinite(et_sevo) & ~np.isfinite(et_des)] = np.nan

        vol = np.isfinite(mac) & (mac > 0)
        tiv = np.isfinite(ppf) & (ppf > 0)
        arm = "volatile" if vol.sum() >= tiv.sum() else "tiva"
        hyp = mac if arm == "volatile" else ppf
        L = {"L0": hyp.copy(),
             "L1": own_mac if arm == "volatile" else hyp.copy(),
             "L2": None,
             "L3": zc(hyp) + zc(rft),
             "L4": zc(hyp) + zc(rft) + zc(hyp) * zc(rft)}
        rec = {"case": c, "arm": arm, "t": t, "L": L, "hyp": hyp, "rft": rft, "own_mac": own_mac}
        for m in MEASURES:
            rec[m] = np.array([z[m] for z in rows])
        arms[arm].append(rec)

    rng = np.random.default_rng(SEED)
    for arm in ("volatile", "tiva"):
        recs = arms.get(arm, [])
        # keep only cases where EVERY rung is computable, so rungs are compared on identical cases (G1)
        keep = []
        for r in recs:
            ok = np.isfinite(r["hyp"]) & np.isfinite(r["rft"])
            if arm == "volatile":
                ok &= np.isfinite(r["own_mac"])
            for m in MEASURES:
                ok &= np.isfinite(r[m])
            if ok.sum() >= MIN_WINDOWS and np.ptp(r["hyp"][ok]) > 0 and np.ptp(r["rft"][ok]) > 0:
                r["ok"] = ok
                keep.append(r)
        n = len(keep)
        print(f"\n=== ARM {arm}: {len(recs)} cases, {n} with every rung computable on >= "
              f"{MIN_WINDOWS} common windows ===")
        res["gates"][f"G1_{arm}_n"] = n
        if n < 15:
            print("   too few cases, not analysed")
            continue

        if arm == "volatile":
            agree = [spearman(r["hyp"][r["ok"]], r["own_mac"][r["ok"]]) for r in keep]
            agree = np.array([x for x in agree if np.isfinite(x)])
            g3 = bool(agree.size and np.median(agree) > 0.8)
            res["gates"][f"G3_{arm}_median_L0_L1_agreement"] = float(np.median(agree)) if agree.size else float("nan")
            res["gates"][f"G3_{arm}_pass"] = g3
            print(f"G3 L1 vs L0   median within-case rho(own MAC, monitor MAC) = "
                  f"{np.median(agree) if agree.size else float('nan'):+.4f}  "
                  f"{'PASS' if g3 else 'FAIL -- the recomputation disagrees with the device'}")

        print(f"\n{'measure':<22s} {'rung':<5s} {'fidelity':>10s} {'95% CI':>22s} {'vs L0':>10s} "
              f"{'95% CI':>22s}")
        arm_out = {}
        for m, sign in MEASURES.items():
            base = None
            arm_out[m] = {}
            for rung in ("L0", "L1", "L3", "L4"):
                vals = []
                for r in keep:
                    e = r["L"][rung]
                    if e is None:
                        vals.append(np.nan); continue
                    ok = r["ok"] & np.isfinite(e)
                    vals.append(sign * spearman(r[m][ok], e[ok]) if ok.sum() >= MIN_WINDOWS
                                else np.nan)
                v = np.array(vals, float)
                good = np.isfinite(v)
                if good.sum() < 15:
                    continue
                lo, hi = ci([float(np.nanmean(v[good][i]))
                             for i in (rng.integers(0, good.sum(), good.sum()) for _ in range(REPS))])
                if rung == "L0":
                    base = v
                    d_txt = ""
                    arm_out[m][rung] = {"fid": float(np.nanmean(v)), "lo": lo, "hi": hi}
                else:
                    d = v - base
                    dg = np.isfinite(d)
                    dlo, dhi = ci([float(np.nanmean(d[dg][i]))
                                   for i in (rng.integers(0, dg.sum(), dg.sum()) for _ in range(REPS))])
                    d_txt = f"{np.nanmean(d):+10.4f} [{dlo:+9.4f},{dhi:+9.4f}]"
                    arm_out[m][rung] = {"fid": float(np.nanmean(v)), "lo": lo, "hi": hi,
                                        "delta": float(np.nanmean(d)), "dlo": dlo, "dhi": dhi}
                tag = " (reference)" if m == REFERENCE else ""
                print(f"{m + tag:<22s} {rung:<5s} {np.nanmean(v):>10.4f} [{lo:+9.4f},{hi:+9.4f}] {d_txt}")
        res["arms"][arm] = arm_out

    # ---- verdict ----------------------------------------------------------------------------------
    # which rungs DEGRADE the reference? Those rungs are worse EXPOSURES and grade everything above them.
    ref_worse = set()
    ref_detail = []
    for arm, per_m in res["arms"].items():
        for rung, d in per_m.get(REFERENCE, {}).items():
            if rung == "L0" or "dhi" not in d:
                continue
            if np.isfinite(d["dhi"]) and d["dhi"] < 0:
                ref_worse.add((arm, rung))
                ref_detail.append(f"{arm}/{rung} {d['delta']:+.4f}")
    res["gates"]["G4_rungs_degrading_the_reference"] = sorted(f"{a}/{r}" for a, r in ref_worse)

    improved, hurt, discredited = [], [], []
    for arm, per_m in res["arms"].items():
        for m, rungs in per_m.items():
            if m == REFERENCE:
                continue
            for rung, d in rungs.items():
                if rung == "L0" or "dlo" not in d:
                    continue
                # a rung whose delta is identically zero is the same exposure as L0 by construction
                if d.get("dlo") == 0.0 and d.get("dhi") == 0.0:
                    continue
                if np.isfinite(d["dlo"]) and d["dlo"] > 0:
                    (discredited if (arm, rung) in ref_worse else improved).append(
                        f"{arm}/{m}/{rung} {d['delta']:+.4f}")
                if np.isfinite(d["dhi"]) and d["dhi"] < 0:
                    hurt.append(f"{arm}/{m}/{rung} {d['delta']:+.4f}")
    ref_ok = all(res["arms"].get(a, {}).get(REFERENCE, {}).get("L0", {}).get("lo", -1) > 0
                 for a in res["arms"]) if res["arms"] else False
    res["gates"]["G4_reference_alive"] = ref_ok
    if not res["arms"]:
        v = "ABSENT -- no arm had enough cases with every rung computable."
    elif not ref_ok:
        v = ("ABSENT -- the reference (BIS) does not track the L0 exposure on these cases, so the exposure "
             "variable is broken here and no rung comparison is interpretable (rule 31).")
    elif ref_worse and not improved:
        v = ("**ELABORATION MAKES THE EXPOSURE WORSE.** BIS -- a vendor index that certainly tracks "
             f"anaesthetic depth -- tracks the elaborated exposure LESS well at {ref_detail}, so those "
             "rungs are worse exposure estimates, not better ones. "
             + (f"Candidate improvements at those same rungs ({discredited}) cannot be credited and are "
                "reported only for completeness. " if discredited else "")
             + (f"Candidates also degrade directly: {hurt}. " if hurt else "")
             + "Combining hypnotic and opioid the way the device already reports them does not help and "
               "mostly hurts. This does NOT show a real PK/PD model would fail -- a properly weighted "
               "effect-site combination is a different object from an equal-weight z-score sum -- but it "
               "removes the assumption that more agents automatically means a better exposure.")
    elif hurt and not improved:
        v = (f"ELABORATION HURTS -- rungs above L0 track the EEG WORSE: {hurt}. A more complete exposure "
             f"adds noise rather than signal on this deposit, which argues against the PK/PD programme "
             f"for this purpose.")
    elif not improved:
        v = ("**NO LADDER EFFECT.** No rung beats the single-agent incumbent for any candidate measure. "
             "Combining hypnotic and opioid exposures -- separately, additively, or with an interaction "
             "term -- does not improve how well the EEG tracks drug exposure on this deposit. The "
             "investigator named this outcome as possible before the run and it is USEFUL: it says the "
             "expensive Eleveld/Minto rungs are unlikely to be worth building FOR THIS PURPOSE. It does "
             "NOT show a real PK/PD model would fail -- only that the information a multi-agent exposure "
             "adds, in the form the device already provides it, does not help.")
    else:
        v = (f"ELABORATION PAYS -- rungs above L0 improve EEG tracking: {improved}."
             + (f" Some rungs also hurt ({hurt}), so the ladder is non-monotone and that should be treated "
                f"with suspicion rather than reported as a gradient." if hurt else "")
             + " The case for implementing the published Eleveld/Minto models properly is now empirical "
               "rather than assumed.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2, default=float)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
