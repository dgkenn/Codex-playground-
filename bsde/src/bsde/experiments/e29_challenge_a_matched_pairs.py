#!/usr/bin/env python3
"""E29 — Challenge A, fourth attempt: hold the phase of the case constant BY DESIGN, not by a control.

REGISTERED AFTER E25'S RESULT WAS KNOWN, AND THAT IS STATED FIRST BECAUSE IT CHANGES HOW THIS FILE SHOULD BE
READ. E25's primary was withdrawn by its own placebo: remifentanil correlated with `exponent_high` at 87.7 %
(volatile) and 168.7 % (propofol) of the hypnotic's own correlation. The diagnosis was co-titration —
remifentanil is given alongside the hypnotic, both follow the phase of the operation, and a within-subject
correlation over a whole case cannot separate them.

**This is not E25 re-run hoping for a different answer.** It is a different design, aimed at the specific
confound E25 demonstrated, and the thing that makes the distinction real is that **the primary candidate,
its declared direction, and the arms are all carried over unchanged.** What changes is the contrast: instead
of correlating dose across a whole case, it compares **pairs of windows from the same patient that are close
in TIME and far apart in DOSE.** Case phase is then nearly constant inside every unit of analysis, by
construction rather than by adjustment — which is also why no collider is being conditioned on (rule 13):
nothing post-exposure enters the model, the pairing is on the exposure's own timing.

E25's P4 is the reason this is worth doing at all. Its acceptance condition PASSED: at matched MAC,
sevoflurane versus desflurane gave a drug probe of |AUC - 0.5| = 0.006 against a depth legibility of 0.063.
**Whatever tracks depth here is not a pharmacology detector.** The open question is only whether it tracks
depth or the clock, and that is exactly what pairing answers.

THE PAIRING RULE, fixed here.
    A pair is two windows from the same patient with |Δt| <= `MAX_DT_S` and |Δdose| >= the arm's threshold.
    volatile   dose = `Primus/MAC`,          threshold `MIN_DMAC`
    propofol   dose = `Orchestra/PPF20_CE`,  threshold `MIN_DPPF`
Both windows must survive the EMG <= `EMG_MAX` muscle filter that E25 established and E22 died without.

REGISTERED PREDICTIONS, in evaluation order. A failed gate makes the downstream verdict ABSENT (rule 31).

    P1  MACHINERY GATE, three parts, using no candidate.
        (a) COVERAGE — at least `MIN_PATIENTS` patients per arm with at least `MIN_PAIRS` qualifying pairs.
        (b) **THE PAIRING MUST ACTUALLY DO ITS JOB, and this is the gate that matters.** Within pairs, the
            median |Δ remifentanil| must be at most `RFTN_RATIO_MAX` of the median |Δ remifentanil| between
            arbitrary same-patient windows. If the pairs do not hold the opioid closer than chance does,
            the design has not separated dose from case phase and everything after it is E25 again with
            more steps. **This is checked before any candidate value is read, and it can fail.**
        (c) The pairs must span both directions of dose change, at least `MIN_DIRECTION_FRACTION` each way,
            so the statistic is not a one-sided drift in disguise.

    P2  THE PRIMARY. Across qualifying pairs, the fraction in which `exponent_high` moves in its declared
        direction with dose — a within-patient sign statistic, averaged per patient, then bootstrapped over
        patients. Its interval must exclude 0.5, in **each arm**.

    P3  CROSS-DRUG CONSISTENCY, unchanged from E25: same side of 0.5 in both arms, and the smaller
        |fraction - 0.5| at least half the larger.

    P4  THE PLACEBO, GATING (rule 34). The identical statistic with dose replaced by remifentanil — pairs
        re-formed on |Δ remifentanil| instead. It must be weaker than the primary. A COMPARISON against the
        real effect, never an absolute threshold (rule 37).

    P5  THE TIME-DIRECTION CONTROL, also gating, and it is the one E25 did not have. Pairs re-formed on
        |Δt| alone — same patient, same time separation, **no dose requirement** — scored by whether the
        candidate moves with the LATER window. If the candidate separates windows by time as strongly as by
        dose, the pairing has not removed the clock and P2 is withdrawn.

    NOTE ON THE OTHER CANDIDATES. The primary is one pre-declared candidate. The rest are context with
    UNADJUSTED intervals and would have to pass `verifier/multiplicity.py` before becoming a claim.

    FALSIFICATION: P2's interval includes 0.5 in either arm, or P3's arms disagree in side, or P4 or P5
    fails. Each is a result, and P4 or P5 failing means the pairing did not achieve what it was built for.

SCOPE AND LIMITS.
  * **Dose is not consciousness.** Carried over from E25 verbatim and it still governs every sentence here.
  * **Pairs are not independent** — one window can appear in many. The bootstrap resamples PATIENTS, so the
    interval is honest about that, but the per-patient point estimate is still an average over a
    correlated set and should not be read as though it came from `n_pairs` observations.
  * **A short |Δt| with a large |Δdose| is not a random subsample of the case.** It selects moments when the
    anaesthetist changed something quickly, which is when stimulation changes — so surgical stimulus is
    concentrated in exactly these pairs. P5 controls the clock, not the stimulus, and no covariate in this
    deposit measures the stimulus directly. **This is the residual confound and it is not solved here.**
  * One site, one monitor, two frontal channels, 128 Hz; maintenance only.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                          # noqa: E402
from bsde.candidates.seed import seed_registry                                          # noqa: E402
from bsde.verifier.stats import cluster_bootstrap_ci                                    # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
OUT = os.path.join(RESULTS, "e29_challenge_a_matched_pairs.json")

ARMS = (("volatile", "mac"), ("propofol", "ppf_ce"))
MAX_DT_S = 600.0
MIN_DMAC = 0.20
MIN_DPPF = 1.00
EMG_MAX = 35.0
MIN_PAIRS = 3
MIN_PATIENTS = 20
RFTN_RATIO_MAX = 0.70
MIN_DIRECTION_FRACTION = 0.25
CROSS_ARM_MIN_RATIO = 0.50
PRIMARY = "exponent_high"
GATE_MIN_CASES = 240
REPORT = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "multiscale_entropy_slope", "critical_slowing_ar1")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _pairs(idx, t, z, min_dz, max_dt):
    """All (i, j) from one patient with |Δt| <= max_dt and Δz >= min_dz, oriented so j has the HIGHER dose."""
    out = []
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            i, j = idx[a], idx[b]
            if abs(t[i] - t[j]) > max_dt:
                continue
            dz = z[j] - z[i]
            if not np.isfinite(dz) or abs(dz) < min_dz:
                continue
            out.append((i, j) if dz > 0 else (j, i))
    return out


def _sign_fraction(pairs, x, direction):
    """Fraction of pairs where x moves as declared from the LOWER-dose window to the HIGHER-dose one."""
    hits = n = 0
    for lo, hi in pairs:
        a, b = x[lo], x[hi]
        if not (np.isfinite(a) and np.isfinite(b)) or a == b:
            continue
        n += 1
        rose = b > a
        hits += int(rose if direction == "higher" else (not rose))
    return (hits / n) if n else float("nan"), n


def _per_patient(pairs_by_sub, x, direction):
    subs, vals = [], []
    for s, prs in pairs_by_sub.items():
        fr, n = _sign_fraction(prs, x, direction)
        if n >= MIN_PAIRS and np.isfinite(fr):
            subs.append(s)
            vals.append(fr)
    return np.array(subs), np.array(vals, float)


def _registered_order() -> None:
    print("   Registered order of evaluation, fixed here and not re-openable:")
    print(f"     P1 GATE  coverage; the pairing must hold remifentanil closer than chance "
          f"(<= {RFTN_RATIO_MAX:.0%}); both dose directions present")
    print(f"     P2       {PRIMARY} moves with dose within pairs, interval excluding 0.5, in EACH arm")
    print("     P3       same side of 0.5 in both arms, smaller effect >= half the larger")
    print("     P4 GATE  remifentanil-paired placebo must be weaker than the dose-paired primary")
    print("     P5 GATE  time-only pairs must be weaker — if not, the pairing did not remove the clock")


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    grid = os.path.abspath(args[args.index("--grid") + 1]) if "--grid" in args else GRID
    agents = os.path.abspath(args[args.index("--agents") + 1]) if "--agents" in args else AGENTS
    seed_registry()
    print("E29 — Challenge A by matched pairs: same patient, close in time, far apart in dose")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    print("   CLAIM SCOPE: anaesthetic DOSE, never consciousness. Carried over from E25 unchanged.")
    if not (os.path.exists(grid) and os.path.exists(agents)):
        print(f"\n   *** absent: {[os.path.basename(p) for p in (grid, agents) if not os.path.exists(p)]}")
        _registered_order()
        return 2

    dose_by = {r["recording_id"]: r for r in csv.DictReader(open(agents, newline=""))}
    rows = [r for r in csv.DictReader(open(grid, newline=""))
            if r.get("status") == "ok" and r["recording_id"] in dose_by]
    n_cases = len({r.get("meta_caseid", "") for r in rows})
    if n_cases < GATE_MIN_CASES:
        print(f"\n   *** {n_cases} joined cases, below the floor of {GATE_MIN_CASES}. Nothing reported.")
        _registered_order()
        return 2

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)                     # noqa: E731
    dcol = lambda k: np.array([_f(dose_by[r["recording_id"]].get(k, "")) for r in rows], float)  # noqa: E731,E501
    subj = np.array([r.get("subject", "") for r in rows])
    t = col("meta_t_s")
    emg = col("meta_emg")
    off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    agents_present = np.array([r.get("meta_agents_present", "") for r in rows])
    mac, ppf, rftn = dcol("mac"), dcol("ppf_ce"), dcol("rftn_ce")
    dose = {"mac": mac, "ppf_ce": ppf}
    thr = {"mac": MIN_DMAC, "ppf_ce": MIN_DPPF}
    volatile = np.array(["sevoflurane" in g or "desflurane" in g for g in agents_present])
    arm_mask = {"volatile": volatile, "propofol": ~volatile}
    clean = ~off & np.isfinite(emg) & (emg <= EMG_MAX) & np.isfinite(t)

    print(f"\n   joined {len(rows)} rows over {n_cases} cases; "
          f"{int(clean.sum())} survive the EMG <= {EMG_MAX:.0f} filter")

    built, rftn_pairs, time_pairs = {}, {}, {}
    for arm, key in ARMS:
        by_sub, by_sub_r, by_sub_t = {}, {}, {}
        for s in np.unique(subj[arm_mask[arm] & clean]):
            idx = np.flatnonzero((subj == s) & arm_mask[arm] & clean & np.isfinite(dose[key]))
            if idx.size < 2:
                continue
            p = _pairs(idx, t, dose[key], thr[key], MAX_DT_S)
            if p:
                by_sub[s] = p
            ir = idx[np.isfinite(rftn[idx])]
            pr = _pairs(ir, t, rftn, 1.0, MAX_DT_S) if ir.size >= 2 else []
            if pr:
                by_sub_r[s] = pr
            pt = _pairs(idx, t, t, 120.0, MAX_DT_S)     # paired on TIME alone, no dose requirement
            if pt:
                by_sub_t[s] = pt
        built[arm], rftn_pairs[arm], time_pairs[arm] = by_sub, by_sub_r, by_sub_t

    # ------------------------------------------------------------------ P1
    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE (no candidate): coverage, and whether the pairing actually holds the case")
    print("=" * 100)
    cells, cov_ok, hold_ok, dir_ok = {}, [], [], []
    print(f"   {'arm':12s} {'pats':>6s} {'pairs':>7s} {'med |dt|':>9s} {'med |dDose|':>12s} "
          f"{'med |dRemi| in pairs':>21s} {'vs any-pair':>12s} {'ratio':>7s}")
    for arm, key in ARMS:
        prs = built[arm]
        pats = [s for s, p in prs.items() if len(p) >= MIN_PAIRS]
        flat = [(i, j) for s in pats for (i, j) in prs[s]]
        if not flat:
            print(f"   {arm:12s} {0:6d} {0:7d}   no qualifying pairs")
            cov_ok.append(False), hold_ok.append(False), dir_ok.append(False)
            continue
        dts = np.array([abs(t[i] - t[j]) for i, j in flat])
        dzs = np.array([abs(dose[key][i] - dose[key][j]) for i, j in flat])
        dr = np.array([abs(rftn[i] - rftn[j]) for i, j in flat])
        dr = dr[np.isfinite(dr)]
        anyp = []
        for s in pats:
            idx = np.flatnonzero((subj == s) & arm_mask[arm] & clean & np.isfinite(rftn))
            for a in range(len(idx)):
                for b in range(a + 1, len(idx)):
                    anyp.append(abs(rftn[idx[a]] - rftn[idx[b]]))
        anyp = np.array(anyp, float)
        ratio = (float(np.median(dr)) / float(np.median(anyp))
                 if dr.size and anyp.size and np.median(anyp) > 0 else float("nan"))
        # both directions of dose change present, so the statistic is not one-sided drift
        ups = float(np.mean([dose[key][j] > dose[key][i] for i, j in flat]))
        c_ok = len(pats) >= MIN_PATIENTS
        h_ok = np.isfinite(ratio) and ratio <= RFTN_RATIO_MAX
        d_ok = MIN_DIRECTION_FRACTION <= ups <= 1 - MIN_DIRECTION_FRACTION
        cov_ok.append(c_ok), hold_ok.append(h_ok), dir_ok.append(d_ok)
        cells[arm] = {"n_patients": len(pats), "n_pairs": len(flat),
                      "median_dt": float(np.median(dts)), "median_ddose": float(np.median(dzs)),
                      "median_dremi_in_pairs": float(np.median(dr)) if dr.size else float("nan"),
                      "median_dremi_any": float(np.median(anyp)) if anyp.size else float("nan"),
                      "ratio": ratio, "frac_dose_up": ups}
        print(f"   {arm:12s} {len(pats):6d} {len(flat):7d} {np.median(dts):9.0f} "
              f"{np.median(dzs):12.2f} {np.median(dr) if dr.size else float('nan'):21.2f} "
              f"{np.median(anyp) if anyp.size else float('nan'):12.2f} {ratio:7.1%}")
        print(f"   {'':12s} dose rises in {ups:.0%} of pairs "
              f"(needs {MIN_DIRECTION_FRACTION:.0%}-{1 - MIN_DIRECTION_FRACTION:.0%})")
    p1 = bool(all(cov_ok) and all(hold_ok) and all(dir_ok))
    print(f"\n   coverage {all(cov_ok)}   pairing-holds-remifentanil {all(hold_ok)}   "
          f"both-directions {all(dir_ok)}   ->   P1 {'PASSED' if p1 else '*** FAILED'}")
    if not p1 and not all(hold_ok):
        print("   NOTE: if the pairing does not hold the opioid closer than chance, this design has not")
        print("   separated dose from case phase and would be E25 again with more steps. That is the")
        print("   failure this gate exists to catch, and it is caught before any candidate is read.")
    state = {"experiment": "E29", "p1": {"arms": cells, "passed": p1}}
    if not p1:
        print("\n   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    # ------------------------------------------------------------------ P2
    rng = np.random.default_rng(20260730)
    direction = REGISTRY.get(PRIMARY).predicted("unconscious_vs_awake") or "higher"
    print("\n" + "=" * 100)
    print(f"P2 — PRIMARY: does {PRIMARY} move with dose WITHIN pairs? (declared direction {direction!r})")
    print("=" * 100)
    x = col(PRIMARY)
    per_arm = {}
    print(f"   {'arm':12s} {'pats':>6s} {'fraction moving as declared':>28s} {'95% CI':>22s}")
    for arm, _ in ARMS:
        subs, vals = _per_patient(built[arm], x, direction)
        if subs.size < MIN_PATIENTS:
            print(f"   {arm:12s} {subs.size:6d}   too few evaluable patients")
            continue
        lo, hi, _ = cluster_bootstrap_ci(lambda i: float(np.mean(vals[i])), subs, rng, reps=2000)
        per_arm[arm] = {"fraction": float(np.mean(vals)), "ci": [float(lo), float(hi)],
                        "n_patients": int(subs.size)}
        print(f"   {arm:12s} {subs.size:6d} {np.mean(vals):28.3f} "
              f"{f'[{lo:.3f}, {hi:.3f}]':>22s}")
    bad = [a for a, d in per_arm.items() if d["ci"][0] <= 0.5 <= d["ci"][1]]
    p2 = bool(len(per_arm) == len(ARMS) and not bad)
    print(f"\n   P2 {'PASSED' if p2 else '*** FAILED'}"
          + (f" — interval includes 0.5 in {bad}" if bad else ""))
    state["p2"] = {"direction": direction, "per_arm": per_arm, "passed": p2}

    # ------------------------------------------------------------------ P3
    print("\n" + "=" * 100)
    print("P3 — CROSS-DRUG CONSISTENCY: same side of 0.5, smaller effect >= half the larger")
    print("=" * 100)
    if len(per_arm) < 2:
        print("   fewer than two reportable arms — ABSENT (rule 31).")
        p3, state["p3"] = None, {"passed": None}
    else:
        sides = {a: (0 if (d["ci"][0] <= 0.5 <= d["ci"][1]) else int(np.sign(d["fraction"] - 0.5)))
                 for a, d in per_arm.items()}
        mags = [abs(d["fraction"] - 0.5) for d in per_arm.values()]
        ratio = min(mags) / max(mags) if max(mags) > 0 else float("nan")
        same = len(set(sides.values())) == 1 and 0 not in sides.values()
        p3 = bool(same and np.isfinite(ratio) and ratio >= CROSS_ARM_MIN_RATIO)
        for a in per_arm:
            print(f"   {a:12s} fraction {per_arm[a]['fraction']:.3f}   side {sides[a]:+d}")
        print(f"   same side {same}; magnitude ratio {ratio:.1%}   P3 {'PASSED' if p3 else '*** FAILED'}")
        state["p3"] = {"sides": sides, "ratio": float(ratio), "passed": p3}

    # ------------------------------------------------------------------ P4 and P5
    gates = {}
    for tag, pairs_map, label in (("p4", rftn_pairs, "remifentanil-paired placebo"),
                                  ("p5", time_pairs, "time-only pairs (no dose requirement)")):
        print("\n" + "=" * 100)
        print(f"{tag.upper()} — {label}: must be WEAKER than the dose-paired primary")
        print("=" * 100)
        res, oks = {}, []
        for arm, _ in ARMS:
            if arm not in per_arm:
                continue
            subs, vals = _per_patient(pairs_map[arm], x, direction)
            if subs.size < MIN_PATIENTS:
                print(f"   {arm:12s} only {subs.size} evaluable patients; ABSENT for this arm")
                continue
            frac = float(np.mean(vals))
            weaker = abs(frac - 0.5) < abs(per_arm[arm]["fraction"] - 0.5)
            oks.append(weaker)
            res[arm] = {"fraction": frac, "n_patients": int(subs.size), "weaker": bool(weaker)}
            print(f"   {arm:12s} fraction {frac:.3f} (|Δ| {abs(frac - 0.5):.3f}) against the primary's "
                  f"{per_arm[arm]['fraction']:.3f} (|Δ| {abs(per_arm[arm]['fraction'] - 0.5):.3f})   "
                  f"{'weaker — ok' if weaker else '*** NOT weaker'}")
        gates[tag] = bool(oks) and all(oks)
        state[tag] = {"per_arm": res, "passed": gates[tag] if oks else None}
        if not oks:
            gates[tag] = None
            print("   ABSENT for every arm — the primary is UNGATED and provisional (rule 31).")
        else:
            print(f"\n   {tag.upper()} {'PASSED' if gates[tag] else '*** FAILED — the primary is WITHDRAWN'}")

    # ------------------------------------------------------------------ context
    print("\n" + "=" * 100)
    print("CONTEXT — other candidates, UNADJUSTED, not claims")
    print("=" * 100)
    print(f"   {'candidate':26s}" + "".join(f"{a:>14s}" for a, _ in ARMS))
    ctx = {}
    for cname in REPORT:
        xc = col(cname)
        d = REGISTRY.get(cname).predicted("unconscious_vs_awake") or "higher"
        line, vals = f"   {cname:26s}", {}
        for arm, _ in ARMS:
            subs, v = _per_patient(built[arm], xc, d)
            if subs.size < MIN_PATIENTS:
                line += f"{'—':>14s}"
                continue
            vals[arm] = float(np.mean(v))
            line += f"{np.mean(v):14.3f}"
        ctx[cname] = vals
        print(line)
    state["context"] = ctx

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if gates.get("p5") is False:
        print("   WITHDRAWN by the time-only control: pairing did not remove the clock.")
        verdict = "withdrawn_by_time_control"
    elif gates.get("p4") is False:
        print("   WITHDRAWN by the remifentanil placebo, as E25 was. Pairing did not separate the drugs.")
        verdict = "withdrawn_by_placebo"
    elif gates.get("p4") is None or gates.get("p5") is None:
        print("   UNGATED — a control could not be evaluated, so P2 is provisional (rule 31).")
        verdict = "ungated"
    elif p2 and p3:
        print("   Challenge A is MET ON THE DOSE AXIS with case phase held constant by design: within the")
        print("   same patient, minutes apart, the candidate tracks the anaesthetic that was given, in both")
        print("   a volatile and a propofol arm, and beats both a co-titrated-drug control and a time-only")
        print("   control. **A statement about anaesthetic dose, not about consciousness.** Residual")
        print("   confound named in the scope note: surgical stimulation is concentrated in these pairs and")
        print("   nothing in this deposit measures it.")
        verdict = "met_on_dose_axis"
    else:
        print("   Not met: the paired contrast did not clear P2 or P3.")
        verdict = "not_met"
    state["verdict"] = verdict
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
