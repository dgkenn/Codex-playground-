"""strategy_opt.py -- systematic gate-composition search over the FULL fill tape, with the project's
anti-overfit discipline baked in. combo_lab enumerated 4 cores x 2 filters; the tape carries more
exploitable structure that gate_lab scored only in isolation (side-asymmetry t=+7.6, BTC-lead t=+6.5,
tau-scaling t=+3.4). This searches their COMPOSITIONS:

    keep iff  tox <= base + amp*fat(mid) + asym(side) + ts*(tau/900 - 0.5)*2
              AND not (BTC moved against our side > lead_bps over 30s)
              AND not (band_lo <= mid < band_hi)            [optional toxic-zone skip]
              AND not (spread >= 2 ticks)                   [optional]

(amp=0.002, everything else 0 == the deployed `ufat`.)

PROTOCOL (selection bias is the enemy with ~10k combos on 2.2 days):
  fold A = first ~40% of windows, B = next ~30%, C = most recent ~30% (untouched holdout).
  1. SELECT on A+B: must beat deployed ufat (paired per-(asset,ws) net) on BOTH folds, with
     positive mo5 net on both (real toxicity-avoidance, not directional luck).
  2. CONFIRM the top-K survivors on C only. Winner must beat ufat on C too -- otherwise the verdict
     is "ufat stands" and we say so.
  3. Battery on the winner: per-asset, per-fold, parameter-neighborhood flatness, bootstrap CI of
     the paired diff. A winner that lives on one asset/fold or sits on a parameter cliff is rejected.

Scored exactly like combo_lab: per-(asset,ws) deployable net = sum_kept(mo_res*sz + rebate(p)*sz),
windows with all fills dropped count as 0.  python strategy_opt.py
"""
from __future__ import annotations

import glob
import itertools
import json
import re

import numpy as np

try:
    import fees
    REB = lambda p: fees.maker_rebate(p, rate=0.07)
except Exception:
    REB = lambda p: 0.25 * 0.07 * p * (1 - p)


# ---------------------------------------------------------------- load tape -> column arrays
# LOOKAHEAD WARNING: the recorded `dspot30` is the spot move 30s AFTER the fill (a markout
# companion -- shadow_compare samples spot at t+30). Gating on it is using the future; gate_lab's
# original "btc-lead" candidate had exactly this bias. The honest lead feature below is built from
# PAST observations only: every decision record (fills AND skips) carries (t, spot), giving a dense
# in-window spot tape; dpast30 = spot(t) - last spot observation at or before t-30s.
def load():
    cols = {k: [] for k in ("tox", "mid", "ask", "tau", "dspot_adv", "spot", "spread",
                            "sz", "p", "mo_res", "mo5", "wkey")}
    wkeys = {}
    spot_tape = {}                      # asset -> [(t, spot)] from ALL decision records
    raw = []                            # (asset, record) for fills, second pass
    for fp in sorted(glob.glob("gha_data/fills_*.jsonl")):
        m = re.search(r"fills_([a-z]+)\d+m_", fp)
        asset = m.group(1) if m else "btc"
        for ln in open(fp):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("spot") and r.get("t"):
                spot_tape.setdefault(asset, []).append((r["t"], r["spot"]))
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("mo_res") is not None:
                raw.append((asset, r))
    tape = {}
    for asset, pts in spot_tape.items():
        pts.sort()
        tape[asset] = (np.array([t for t, _ in pts]), np.array([s for _, s in pts]))
    n_lead = 0
    for asset, r in raw:
        mp, p, side = r.get("micro"), r["p"], r["side"]
        tox = r.get("tox")
        if tox is None:
            tox = 0.0 if mp is None else ((mp - p) if side == "ASK" else (p - mp))
        # honest PAST 30s spot move (0 = no observation old enough -> no signal -> never gates)
        dpast = 0.0
        tt, ss = tape.get(asset, (None, None))
        if tt is not None:
            i = np.searchsorted(tt, r["t"] - 30.0, side="right") - 1
            if i >= 0 and (r["t"] - 30.0) - tt[i] <= 60.0:     # stale anchor (>90s old) = no signal
                dpast = (r.get("spot") or ss[i]) - ss[i]
                n_lead += 1
        fair_move = (1.0 if r.get("up", 1) else -1.0) * dpast
        dadv = fair_move if side == "ASK" else -fair_move
        bb, ba = r.get("bb"), r.get("ba")
        k = (asset, r["ws"])
        if k not in wkeys:
            wkeys[k] = len(wkeys)
        cols["tox"].append(tox)
        cols["mid"].append(r.get("mid") or p)
        cols["ask"].append(1.0 if side == "ASK" else 0.0)
        cols["tau"].append(r.get("tau", 450.0))
        cols["dspot_adv"].append(dadv)
        cols["spot"].append(r.get("spot") or 0.0)
        cols["spread"].append((ba - bb) if (bb is not None and ba is not None) else 0.01)
        cols["sz"].append(r["sz"])
        cols["p"].append(p)
        cols["mo_res"].append(r["mo_res"])
        cols["mo5"].append(r.get("mo5") if r.get("mo5") is not None else 0.0)
        cols["wkey"].append(wkeys[k])
    arr = {k: np.asarray(v, dtype=(np.int64 if k == "wkey" else np.float64)) for k, v in cols.items()}
    arr["asset"] = np.array([a for (a, _) in sorted(wkeys, key=wkeys.get)])      # per-window asset
    arr["ws"] = np.array([w for (_, w) in sorted(wkeys, key=wkeys.get)])         # per-window ws
    print(f"  (honest past-30s lead feature available on {n_lead}/{len(raw)} fills)")
    return arr


# ---------------------------------------------------------------- evaluation
def fold_masks(ws_per_window):
    """A/B/C window-index masks by time (40/30/30 of distinct ws values)."""
    uniq = np.sort(np.unique(ws_per_window))
    ca, cb = uniq[int(len(uniq) * 0.4)], uniq[int(len(uniq) * 0.7)]
    return (ws_per_window < ca), (ws_per_window >= ca) & (ws_per_window < cb), (ws_per_window >= cb)


def window_nets(keep, D, val):
    """per-window sums of `val` over kept fills (length = n_windows; dropped-all windows = 0)."""
    return np.bincount(D["wkey"][keep], weights=val[keep], minlength=len(D["ws"]))


def calmar(nets_in_ws_order):
    cum = np.cumsum(nets_in_ws_order)
    mdd = float(np.max(np.maximum.accumulate(cum) - cum))
    tot = float(cum[-1]) if len(cum) else 0.0
    if mdd <= 1e-9:
        return float("inf") if tot > 0 else 0.0
    return tot / mdd


def paired_t(d):
    d = np.asarray(d, dtype=float)
    n = len(d)
    if n < 5 or d.std(ddof=1) == 0:
        return float("nan")
    return float(d.mean() / (d.std(ddof=1) / np.sqrt(n)))


def keep_mask(D, base, amp, ask_adj, bid_adj, ts, lead_bps, band, spread_f):
    fat = 4.0 * D["mid"] * (1.0 - D["mid"])
    margin = base + amp * fat + np.where(D["ask"] > 0, ask_adj, bid_adj)
    if ts:
        margin = margin + ts * (D["tau"] / 900.0 - 0.5) * 2.0       # loose early, strict late
    keep = D["tox"] <= margin
    if lead_bps:
        keep &= ~(D["dspot_adv"] > D["spot"] * lead_bps / 1e4)
    if band is not None:
        lo, hi = band
        keep &= ~((D["mid"] >= lo) & (D["mid"] < hi))
    if spread_f:
        keep &= D["spread"] < 0.015
    return keep


GRID = {
    "base": (-0.002, -0.001, 0.0, 0.001),
    "amp": (0.0, 0.001, 0.002, 0.003, 0.004),
    "asym": ((0.0, 0.0), (-0.001, 0.002), (-0.002, 0.001), (-0.003, 0.002)),
    "ts": (0.0, 0.001, 0.0025),
    "lead": (0.0, 1.0, 1.5, 2.5),
    "band": (None, (0.30, 0.55), (0.25, 0.55), (0.30, 0.60), (0.35, 0.55)),
    "spread": (False, True),
}
UFAT = dict(base=0.0, amp=0.002, ask_adj=0.0, bid_adj=0.0, ts=0.0, lead_bps=0.0,
            band=None, spread_f=False)


def name_of(c):
    bits = [f"b{c['base']:+.3f}", f"a{c['amp']:.3f}"]
    if c["ask_adj"] or c["bid_adj"]:
        bits.append(f"as({c['ask_adj']:+.3f}/{c['bid_adj']:+.3f})")
    if c["ts"]:
        bits.append(f"tau{c['ts']:.4f}")
    if c["lead_bps"]:
        bits.append(f"lead{c['lead_bps']:g}")
    if c["band"]:
        bits.append(f"band{c['band'][0]:.2f}-{c['band'][1]:.2f}")
    if c["spread_f"]:
        bits.append("sprd1")
    return "+".join(bits)


def main():
    D = load()
    n_f, n_w = len(D["tox"]), len(D["ws"])
    net_val = D["mo_res"] * D["sz"] + REB(D["p"]) * D["sz"]
    mo5_val = D["mo5"] * D["sz"] + REB(D["p"]) * D["sz"]
    mA, mB, mC = fold_masks(D["ws"])
    order = np.argsort(D["ws"], kind="stable")           # window time order (Calmar paths)
    print(f"{n_f} fills | {n_w} (asset,ws) windows | folds A/B/C = "
          f"{int(mA.sum())}/{int(mB.sum())}/{int(mC.sum())} windows\n")

    def evl(keep):
        wn = window_nets(keep, D, net_val)
        w5 = window_nets(keep, D, mo5_val)
        return wn, w5

    ufat_keep = keep_mask(D, **UFAT)
    ufat_wn, ufat_w5 = evl(ufat_keep)

    combos = []
    for base, amp, (aj, bj), ts, lead, band, spf in itertools.product(
            GRID["base"], GRID["amp"], GRID["asym"], GRID["ts"], GRID["lead"],
            GRID["band"], GRID["spread"]):
        combos.append(dict(base=base, amp=amp, ask_adj=aj, bid_adj=bj, ts=ts,
                           lead_bps=lead, band=band, spread_f=spf))
    print(f"searching {len(combos)} gate compositions (SELECT on A+B, CONFIRM on holdout C)...")

    survivors = []
    for c in combos:
        keep = keep_mask(D, **c)
        wn, w5 = evl(keep)
        d = wn - ufat_wn
        tA, tB = paired_t(d[mA]), paired_t(d[mB])
        # SELECT: beat ufat on BOTH selection folds; toxicity-real (mo5 net > 0) on both
        if not (tA > 0 and tB > 0 and d[mA].mean() > 0 and d[mB].mean() > 0
                and w5[mA].mean() > 0 and w5[mB].mean() > 0):
            continue
        score = min(tA, tB)                              # weakest-fold strength = selection score
        survivors.append((score, c, wn, w5, d))
    survivors.sort(key=lambda x: -x[0])
    print(f"{len(survivors)} survive the A+B paired screen (vs deployed ufat)\n")

    # ---- CONFIRM on the untouched holdout C ----
    K = 12
    print(f"top {K} by weakest-selection-fold t, CONFIRMED on holdout C:")
    print(f"{'composition':>52} {'selT':>5} | {'C net/w':>8} {'ufatC':>7} {'C pairT':>7} "
          f"{'C mo5/w':>8} {'C Calmar':>8} {'kept%':>6}")
    print("-" * 110)
    uC = ufat_wn[mC].mean()
    ucal = calmar(ufat_wn[order][mC[order]])
    rows_out = []
    for score, c, wn, w5, d in survivors[:K]:
        tC = paired_t(d[mC])
        cal = calmar(wn[order][mC[order]])
        kept = 100.0 * keep_mask(D, **c).mean()
        rows_out.append((c, wn, w5, d, tC, cal))
        print(f"{name_of(c):>52} {score:>5.1f} | {wn[mC].mean():>+8.2f} {uC:>+7.2f} {tC:>+7.1f} "
              f"{w5[mC].mean():>+8.2f} {cal:>8.1f} {kept:>5.0f}%")
    print(f"{'(deployed ufat reference)':>52} {'--':>5} | {uC:>+8.2f} {uC:>+7.2f} {'--':>7} "
          f"{ufat_w5[mC].mean():>+8.2f} {ucal:>8.1f} {100.0*ufat_keep.mean():>5.0f}%")

    # winner = best holdout Calmar among those that ALSO beat ufat on C (mean and t>0)
    fin = [r for r in rows_out if r[3][mC].mean() > 0 and r[4] > 0 and r[2][mC].mean() > 0]
    if not fin:
        print("\nVERDICT: no composition that wins selection ALSO beats ufat on the holdout -> "
              "the deployed `ufat` stands as the best strategy in this search space.")
        return
    fin.sort(key=lambda r: -r[5])
    c, wn, w5, d, tC, cal = fin[0]
    print(f"\n=== WINNER: {name_of(c)} ===")
    print(f"  holdout C: net/win {wn[mC].mean():+.2f} vs ufat {uC:+.2f} (paired t {tC:+.1f}), "
          f"Calmar {cal:.1f} vs {ucal:.1f}, mo5/win {w5[mC].mean():+.2f}")

    # ---- battery ----
    print("\n[battery 1] per-fold paired diff vs ufat (net/win):")
    for nm, mm in (("A", mA), ("B", mB), ("C", mC)):
        print(f"   fold {nm}: diff {d[mm].mean():+.2f}/win  t={paired_t(d[mm]):+.1f}")
    print("[battery 2] per-asset paired diff vs ufat (all folds):")
    for asset in ("btc", "eth", "sol", "xrp"):
        am = D["asset"] == asset
        if am.sum() > 5:
            print(f"   {asset}: diff {d[am].mean():+.2f}/win  t={paired_t(d[am]):+.1f}  (n={int(am.sum())})")
    print("[battery 3] parameter-neighborhood flatness (holdout net/win at +/- one grid step):")
    for pname, vals in (("base", GRID["base"]), ("amp", GRID["amp"]), ("ts", GRID["ts"]),
                        ("lead_bps", GRID["lead"])):
        cur = c[pname]
        i = vals.index(cur) if cur in vals else None
        nb = []
        for j in ((i - 1, i + 1) if i is not None else ()):
            if 0 <= j < len(vals):
                cc = dict(c); cc[pname] = vals[j]
                nb.append(f"{vals[j]}: {window_nets(keep_mask(D, **cc), D, net_val)[mC].mean():+.2f}")
        print(f"   {pname}={cur} -> neighbors {{{', '.join(nb)}}}")
    rng = np.random.default_rng(7)
    boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"[battery 4] bootstrap 95% CI of paired diff (all windows): [{lo:+.2f}, {hi:+.2f}] "
          f"({100.0*np.mean(np.array(boots) > 0):.0f}% of resamples positive)")
    print("\nRead: adopt the winner only if every battery line holds (all folds +, no one-asset wonder,")
    print("flat neighborhood, CI excluding 0). Then wire it as a shadow A/B variant first -- the standing")
    print("discipline: prospective confirmation before the deployed default changes.")


if __name__ == "__main__":
    main()
