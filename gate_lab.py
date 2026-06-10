"""gate_lab.py -- backtest toxicity GATES on the recorded ungated fills, so the "benign-finding / toxic-
avoiding" function is improved by DATA, not by bolting on complexity (which this project has repeatedly
shown loses). The baseline variant logs every fill it WOULD take with the full feature vector at fill time
+ the realized markout-to-resolution (mo_res). For each candidate gate we simulate keep/drop and score:

    net = Σ_kept ( mo_res*sz + maker_rebate(p)*sz )      # rebate-inclusive (the deployable P&L)

A gate wins only if its net beats micro_gate (the deployed edge) -- ideally with the win holding OUT-OF-
SAMPLE (last 30% of windows). The calibrated ENSEMBLE fits a ridge markout model on IS features and gates
on predicted net>0, evaluated strictly OOS. python gate_lab.py

Each candidate maps to one of the 10 improvements (see comments)."""
from __future__ import annotations
import glob, json, math
import numpy as np
from dataio import jl_glob, jl_open

try:
    import fees
    REB = lambda p: float(fees.maker_rebate(p, rate=0.07))
except Exception:
    REB = lambda p: 0.25 * 0.07 * p * (1 - p)

FLOW_TOX = 200.0     # signed taker vol threshold (matches shadow_compare flow gate)


def load():
    """Load baseline fills AND attach an HONEST past-30s spot move (`_dpast30`) to each.

    LOOKAHEAD WARNING: the recorded `dspot30` field is the spot move 30s AFTER the fill (a markout
    companion -- shadow_compare samples spot at t+30). It must NEVER be used as a gating feature;
    doing so scored a fake t=+6.5 'btc-lead' edge here before the bias was caught (strategy_opt.py).
    The honest feature is built from PAST observations only: every decision record (fills and skips)
    carries (t, spot), giving a dense in-window spot tape."""
    rows, tape_pts = [], {}
    for fp in jl_glob("gha_data/fills_*.jsonl"):
        import re as _re
        m = _re.search(r"fills_([a-z]+)\d+m_", fp)
        asset = m.group(1) if m else "btc"
        for ln in jl_open(fp):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("spot") and r.get("t"):
                tape_pts.setdefault(asset, []).append((r["t"], r["spot"]))
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("mo_res") is not None:
                r["_asset"] = asset
                rows.append(r)
    tape = {}
    for asset, pts in tape_pts.items():
        pts.sort()
        tape[asset] = (np.array([t for t, _ in pts]), np.array([s for _, s in pts]))
    for r in rows:
        dpast = 0.0
        tt, ss = tape.get(r.get("_asset", "btc"), (None, None))
        if tt is not None and r.get("t"):
            i = int(np.searchsorted(tt, r["t"] - 30.0, side="right")) - 1
            if i >= 0 and (r["t"] - 30.0) - tt[i] <= 60.0:
                dpast = (r.get("spot") or ss[i]) - ss[i]
        r["_dpast30"] = dpast
    rows.sort(key=lambda r: (r.get("ws", 0), r.get("t", 0)))
    return rows


def reb_of(r):
    return REB(r["p"]) * r["sz"]


# MARKOUT TARGET. mo_res (to resolution) conflates adverse selection with the DIRECTIONAL outcome -- gating
# on it optimizes picking winners (directional betting, breaks delta-neutrality, overfits BTC paths), NOT
# toxicity. A maker who holds balanced sets to $1 has the directional part cancel; what it actually controls
# is SHORT-HORIZON markout (did the touch move against us right after the fill). So toxicity is judged on
# mo5/mo30; mo_res is shown only as the (noisy, directional) settle P&L.
def mk(r, horizon):
    v = r.get(horizon)
    return (v if v is not None else r.get("mo_res", 0.0)) * r["sz"]


def gross_of(r, horizon="mo5"):
    return mk(r, horizon)


def net_of(r, horizon="mo5"):
    return gross_of(r, horizon) + reb_of(r)


# --- toxicity signal helpers (signed so that >0 == ADVERSE for our resting side) ---
def tox(r):
    """recorded micro toxicity: (micro-price) if we SELL(ASK), (price-micro) if we BUY(BID). >0 = adverse."""
    t = r.get("tox")
    if t is not None:
        return t
    mp = r.get("micro"); p = r["p"]
    if mp is None:
        return 0.0
    return (mp - p) if r["side"] == "ASK" else (p - mp)


def flow_adv(r):
    """signed taker flow in the adverse direction for our side. ASK adverse if buyers lifting (flow>0)."""
    f = r.get("flow30") or 0.0
    return f if r["side"] == "ASK" else -f


def dspot_adv(r):
    """Spot move against our side over the PAST ~30s (honest `_dpast30` from load(); the recorded
    `dspot30` field is the FUTURE move -- using it here once produced a fake t=+6.5 lead 'edge').
    ASK adverse if spot just rose (token fair up)."""
    d = r.get("_dpast30") or 0.0
    up = r.get("up", 1)
    fair_move = (1.0 if up else -1.0) * d        # how the token's fair just moved
    return fair_move if r["side"] == "ASK" else -fair_move


def spread(r):
    bb, ba = r.get("bb"), r.get("ba")
    return (ba - bb) if (bb is not None and ba is not None) else 0.01


# --- candidate gates: return True to KEEP the fill (False = drop as toxic) ---
def g_nogate(r):
    return True


def g_micro(r):                       # the deployed edge: keep iff not micro-adverse
    return tox(r) <= 0.0


def g_micro_soft(r, c=0.002):         # #1 keep mildly-toxic (rebate beats tiny loss)
    return tox(r) <= c


def g_thresh(c):                      # #1 calibrated threshold (swept)
    return lambda r: tox(r) <= c


def g_adaptive(r, k=1.0):             # #2 spread/price-adaptive margin: stricter at p~0.5 & tight spread
    p = r.get("mid") or r["p"]
    fatness = 4.0 * p * (1 - p)                  # 1 at p=0.5, ->0 at tails
    margin = k * spread(r) * (1.0 - 0.5 * fatness)   # tighter spread & mid => smaller tolerance
    return tox(r) <= margin


def g_tau(r, c0=0.004, c1=-0.001):    # #3 tau-scaled: loose early, strict (even negative) late
    tau = r.get("tau", 450.0); frac = max(0.0, min(1.0, tau / 900.0))
    c = c1 + (c0 - c1) * frac                     # tau->0 => c1 (strict), tau big => c0 (loose)
    return tox(r) <= c


def g_flow_confirm(r):                # #4 pull only when micro AND flow agree it's adverse
    return not (tox(r) > 0.0 and flow_adv(r) > FLOW_TOX)


def g_vpin(r, thr=0.30):              # #5 VPIN-ish: normalized adverse flow imbalance
    f5 = r.get("flow5") or 0.0; tks = abs(r.get("tk_sz") or 0.0) + 1.0
    vp = (flow_adv(r)) / (abs(f5) + tks + 50.0)  # crude normalization
    return not (tox(r) > 0.0 and vp > thr)


def g_lead(r, bps=1.5):               # #6 BTC lead-lag: pull the side BTC just moved against
    spot = r.get("spot") or 0.0
    thr = spot * bps / 1e4 if spot else 1e9
    return not (dspot_adv(r) > thr)


def g_queue(r, qmax=150.0):           # #7 queue-position: back-of-deep-queue + adverse = toxic
    q = r.get("q_ahead") or 0.0
    return not (tox(r) > 0.0 and q > qmax)


def g_tksize(r, big=60.0):            # #8 trade-size: large adverse aggressor = informed
    return not (tox(r) > 0.0 and (r.get("tk_sz") or 0.0) > big)


def g_asym(r):                        # #9 asymmetric: SELL side historically more toxic -> stricter
    c = -0.001 if r["side"] == "ASK" else 0.002
    return tox(r) <= c


# --- evaluation (default toxicity horizon = mo5; net_res shown as the directional settle P&L) ---
def evaluate(rows, keep, horizon="mo5"):
    kept = [r for r in rows if keep(r)]
    nets = [net_of(r, horizon) for r in kept]
    grs = [gross_of(r, horizon) for r in kept]
    net_res = sum(gross_of(r, "mo_res") + reb_of(r) for r in kept)
    n = len(nets)
    return {"net": sum(nets), "gross": sum(grs), "net_res": net_res, "fills": n,
            "net_per": (sum(nets) / n) if n else 0.0,
            "kept_pct": 100.0 * n / len(rows) if rows else 0.0}


def per_window(rows, keep, horizon="mo5"):
    by = {}
    for r in rows:
        if keep(r):
            by[r["ws"]] = by.get(r["ws"], 0.0) + net_of(r, horizon)
    return by


def paired_t(a, b):                   # paired t of (a-b) per shared window
    ks = sorted(set(a) & set(b))
    d = [a[k] - b[k] for k in ks]
    n = len(d)
    if n < 2:
        return float("nan")
    m = sum(d) / n; sd = (sum((x - m) ** 2 for x in d) / (n - 1)) ** 0.5
    return m / (sd / math.sqrt(n)) if sd > 0 else float("nan")


# --- #10 calibrated ensemble: ridge-predict per-share markout, gate on predicted net>0 (OOS) ---
# TRAIN = SERVE: shadow_compare's live micro_cal zeroes q_ahead/tk_sz (unknowable at quote-decision
# time) and uses the PAST 30s dspot. Training on anything else fits weights the live gate then
# misapplies -- the original model was fit on the FUTURE dspot30 + real q_ahead/tk_sz (both leaked).
def features(r):
    p = r.get("mid") or r["p"]
    return [1.0, tox(r), flow_adv(r) / 100.0, dspot_adv(r), spread(r) * 100.0,
            4.0 * p * (1 - p), 0.0,
            0.0, r.get("tau", 450.0) / 900.0,
            1.0 if r["side"] == "ASK" else 0.0]


def ensemble(rows, lam=1.0, horizon="mo5"):
    """Ridge-predict SHORT-horizon (toxicity) markout from pre-fill features; gate on predicted net>0.
    Trained on mo5 (adverse selection), NOT mo_res, so it learns to dodge toxic fills rather than to bet
    direction. Strict OOS: fit on first 70% of windows, evaluate on the last 30%."""
    cut = int(len(rows) * 0.7)
    tr, te = rows[:cut], rows[cut:]
    X = np.array([features(r) for r in tr])
    y = np.array([(r.get(horizon) if r.get(horizon) is not None else r.get("mo_res", 0.0)) for r in tr])
    A = X.T @ X + lam * np.eye(X.shape[1])
    w = np.linalg.solve(A, X.T @ y)               # ridge weights on IS
    reb_rate = float(np.mean([REB(r["p"]) for r in tr]))
    def keep(r):
        pred_mo = float(np.dot(features(r), w))   # predicted per-share short-horizon markout
        return pred_mo + REB(r["p"]) > 0.0        # keep iff predicted per-share NET positive
    return w, te, keep


def main():
    rows = load()
    if not rows:
        print("no fills found in gha_data/. Pull the prospective data first:\n"
              "  git fetch origin gha-data && git checkout origin/gha-data -- gha_data/")
        return
    print(f"loaded {len(rows)} ungated baseline fills across {len(set(r['ws'] for r in rows))} windows\n")
    base_micro = per_window(rows, g_micro)
    cands = [
        ("nogate", g_nogate), ("micro (deployed)", g_micro), ("micro_soft .002", g_micro_soft),
        ("adaptive spread/p", g_adaptive), ("tau-scaled", g_tau), ("flow-confirm", g_flow_confirm),
        ("vpin", g_vpin), ("btc-lead", g_lead), ("queue-cond", g_queue), ("tk-size", g_tksize),
        ("asym side", g_asym),
    ]
    # #1 best swept threshold
    best_c, best_net = 0.0, -1e9
    for c in [x / 1000 for x in range(-6, 9)]:
        nt = evaluate(rows, g_thresh(c))["net"]
        if nt > best_net:
            best_net, best_c = nt, c
    cands.append((f"thresh* (c={best_c:+.3f})", g_thresh(best_c)))

    print("TOXICITY view: net/gross on SHORT-horizon mo5 (what a maker controls). net_res = directional")
    print("settle P&L (noisy; a balanced book cancels it -- shown only to expose directional overfit).\n")
    print(f"{'gate':>22} {'net(mo5)':>9} {'gross5':>8} {'net_res':>9} {'fills':>7} {'kept%':>6} {'t vs micro':>10}")
    print("-" * 84)
    res = []
    for name, keep in cands:
        e = evaluate(rows, keep); t = paired_t(per_window(rows, keep), base_micro)
        res.append((name, e, t))
    for name, e, t in sorted(res, key=lambda x: -x[1]["net"]):
        tt = f"{t:+.2f}" if t == t else "  --"
        print(f"{name:>22} {e['net']:>+9.2f} {e['gross']:>+8.2f} {e['net_res']:>+9.1f} {e['fills']:>7} "
              f"{e['kept_pct']:>5.0f}% {tt:>10}")

    # ensemble (OOS), trained on mo5 toxicity
    w, te, keep = ensemble(rows)
    e_ens = evaluate(te, keep); e_mic = evaluate(te, g_micro); e_none = evaluate(te, g_nogate)
    print("\n=== #10 CALIBRATED ENSEMBLE (ridge mo5-markout model, OUT-OF-SAMPLE last 30%) ===")
    print(f"  OOS window: {len(te)} fills")
    print(f"  {'gate':>16} {'net(mo5)':>9} {'gross5':>8} {'net_res':>9} {'fills':>7} {'net/fill':>9}")
    for nm, ee in [("nogate", e_none), ("micro", e_mic), ("ENSEMBLE", e_ens)]:
        print(f"  {nm:>16} {ee['net']:>+9.2f} {ee['gross']:>+8.2f} {ee['net_res']:>+9.1f} {ee['fills']:>7} {ee['net_per']:>+9.4f}")
    fn = ["bias", "tox", "flow", "dspot", "spread", "fat(p)", "q_ahead", "tk_sz", "tau", "is_ask"]
    print("  ridge weights (per-share markout sensitivity):")
    print("   " + "  ".join(f"{n}={v:+.4f}" for n, v in zip(fn, w)))
    # persist the fitted model so shadow_compare/live can run the calibrated gate (micro_cal) from data.
    json.dump({"features": fn, "weights": [float(x) for x in w], "strict_margin": -best_c if best_c < 0 else 0.002,
               "asym_ask": -0.001, "asym_bid": 0.002, "horizon": "mo5",
               "note": "keep fill iff dot(features,weights)+maker_rebate(p) > 0 (predicted short-markout net)"},
              open("gate_model.json", "w"), indent=2)
    print("\n  -> wrote gate_model.json (micro_cal loads this)")
    print("\nRead: keep a gate only if net beats 'micro (deployed)' AND it holds OOS. net/fill up + fills not")
    print("collapsed = real benign-finding; net up only by shedding fills = just over-gating (see WINNER_TWEAKS #3).")


if __name__ == "__main__":
    main()
