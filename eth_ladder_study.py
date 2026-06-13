"""eth_ladder_study.py -- Does the strand-prevention LADDER rescue the ETH 15-min box?

Re-tests ETH box profitability WITH the full strand-prevention ladder, the same way we
run BTC. Reuses the ladder_baseline_study harness (load_parquet_windows, run_p0,
full_metrics, walk engine) + box_policy_ab helpers (_live_open_ok, hedge_unpaired, tox_p).

Ladder rungs applied to ETH:
  R0 BUFFER     : open only when spread >= buf (1c base; 2c dynamic in high-|sig| windows)
  R1 PREVENT    : t36 guard (_live_open_ok: suppress thin-spread YES opens / adverse-sig)
  EDGE-SELECT   : open only mid-window k in [5,9] AND mid-vol window mean|sig| in [3,8] bps,
                  AND avoid deep-favorite legs (favorite prob > 0.70)
  R3 COMPLETE   : sell-cheap (<0.30) exit + chase-to-complete (pairing leg always taken)
  R4 MANAGE     : optional streak scale-down (tested on/off)
  BTC-GATE      : optional -- suppress ETH opens in toxic BTC-momentum windows.

IS = first 60%, OOS = last 40%.
Writes findings to stdout; ETH_LADDER.md authored from these numbers.
"""
from __future__ import annotations
import sys, math
sys.path.insert(0, '/tmp/eth_ladder')
import numpy as np

import ladder_baseline_study as L
from box_policy_ab import _live_open_ok, hedge_unpaired, tox_p

EDGE_K_LO, EDGE_K_HI = 5, 9
EDGE_SIG_LO, EDGE_SIG_HI = 3.0, 8.0   # window mean |sig| in bps
FAV_MAX = 0.70


def fav_prob(f):
    py = f['p'] if f['side'] == 'bid' else round(1.0 - f['p'], 4)
    return max(py, 1.0 - py)


def window_meansig(fills):
    s = [abs(f.get('sig', 0.0) or 0.0) for f in fills]
    return float(np.mean(s)) if s else 0.0


def btc_momentum_windows(thresh=8.0):
    """Return set of ws where BTC window mean|sig| is high (toxic-momentum regime)."""
    fb, wb = L.load_parquet_windows('btc')
    toxic = set()
    for ws in wb:
        if window_meansig(fb[ws]) > thresh:
            toxic.add(ws)
    return toxic


# ---- generalized walk with edge-select + buffer-dynamic + btc gate ----
def walk_eth(fills_per_ws, ws_list, *,
             buf=0.01, buf_dyn=0.02, dyn_sig=8.0,
             r1=True, edge=True, fav=True, r3=True, r4=False, r5=False,
             btc_toxic=None):
    """Walk ETH boxes under the ladder. Returns (pnl_per_window, strand_flags, n_opened)."""
    streak = L.StreakState((0.75, 0.50, 0.25)) if r4 else None
    pnl_arr = []; strand_arr = []; opened = 0
    for ws in ws_list:
        fills = fills_per_ws[ws]
        wsig = window_meansig(fills)
        mult = streak.multiplier() if streak else 1.0
        # window-level edge-select + btc gate gate the OPENS, not pairs
        win_blocked = False
        if edge and not (EDGE_SIG_LO <= wsig <= EDGE_SIG_HI):
            win_blocked = True
        if btc_toxic is not None and ws in btc_toxic:
            win_blocked = True
        eff_buf = buf_dyn if (buf_dyn is not None and wsig > dyn_sig) else buf

        net = 0; pnl = 0.0; open_leg = None; open_sz = 1.0
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net != 0 and abs(nn) < abs(net):
                # pairing leg -> always complete (chase-to-complete)
                pnl += mult * open_sz * (f['settle'] + (open_leg['settle'] if open_leg else 0))
                open_leg = None; open_sz = 1.0
            else:
                blocked = win_blocked
                if not blocked and eff_buf is not None and f.get('spread', 0.0) < eff_buf:
                    blocked = True
                if r1 and not blocked and not _live_open_ok(f, {}):
                    blocked = True
                if edge and not blocked and not (EDGE_K_LO <= f.get('k', 7) <= EDGE_K_HI):
                    blocked = True
                if fav and not blocked and fav_prob(f) > FAV_MAX:
                    blocked = True
                if blocked:
                    continue
                open_leg = f; open_sz = 1.0; opened += 1
            net = nn

        stranded = False
        if open_leg is not None:
            stranded = True
            p_yeq = open_leg['p'] if open_leg['side'] == 'bid' else round(1.0 - open_leg['p'], 4)
            if r3 and p_yeq < 0.30:
                pnl += mult * open_sz * open_leg.get('exit', open_leg['settle'])
            elif r5:
                pnl += mult * open_sz * hedge_unpaired(open_leg, h=150.0)
            else:
                pnl += mult * open_sz * open_leg['settle']
        pnl_arr.append(pnl); strand_arr.append(stranded)
        if streak:
            streak.update(stranded)
    return np.array(pnl_arr, float), np.array(strand_arr, bool), opened


def box_margins(fills_per_ws, ws_list):
    """Per-completed-box lock margin (naked, always-pair) + strand window flags."""
    margins = []; strand = 0
    for ws in ws_list:
        fills = fills_per_ws[ws]
        net = 0; open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1; nn = net + step
            if abs(nn) > 1: continue
            if net != 0 and abs(nn) < abs(net):
                if open_leg is not None:
                    margins.append(f['settle'] + open_leg['settle'])
                open_leg = None
            else:
                open_leg = f
            net = nn
        if open_leg is not None:
            strand += 1
    return np.array(margins, float), strand


def line(lbl, m, st=None, opened=None, nwin=None):
    extra = ''
    if st is not None and nwin:
        extra += f" strand={st/nwin*100:5.1f}%"
    if opened is not None:
        extra += f" opens={opened}"
    print(f"{lbl:<32} n={m['n']:5} net={m['nc']:+7.2f}c sh={m['sh']:+.3f} "
          f"cv95={m['cv95']:+7.2f}c win%={m['wr']:4.1f} t={m['ts']:+6.2f}{extra}")


def main():
    print("=" * 100)
    print("ETH + STRAND LADDER STUDY")
    print("=" * 100)

    fe, we = L.load_parquet_windows('eth')
    cut = int(len(we) * 0.6)
    ws_is, ws_oos = we[:cut], we[cut:]
    print(f"ETH windows={len(we)}  IS={len(ws_is)} OOS={len(ws_oos)}")

    # ---------- 1. NAKED BASELINE ----------
    print("\n--- 1. NAKED ETH BASELINE (P0 always-pair) ---")
    p0a, sta = L.run_p0(fe, we)
    p0i, sti = L.run_p0(fe, ws_is)
    p0o, sto = L.run_p0(fe, ws_oos)
    for lbl, x, st, wl in [("P0 ALL", p0a, sta, we), ("P0 IS", p0i, sti, ws_is), ("P0 OOS", p0o, sto, ws_oos)]:
        line(lbl, L.full_metrics(x, x, x), st.sum(), nwin=len(wl))
    # box lock-margin reference
    ma, _ = box_margins(fe, we)
    print(f"NAKED completed-box LOCK MARGIN: n={len(ma)} mean={ma.mean()*100:+.2f}c "
          f"neg%={(ma<0).mean()*100:.1f} p5={np.percentile(ma,5)*100:+.1f}c median={np.median(ma)*100:+.2f}c")

    # ---------- 3. TOXIC-FILL CHARACTERIZATION (do before ladder for context) ----------
    print("\n--- 3. TOXIC-FILL CHARACTERIZATION (completed-box margins, ALL) ---")
    rows = []
    for ws in we:
        fills = fe[ws]; wsig = window_meansig(fills)
        net = 0; open_leg = None
        for f in fills:
            step = 1 if f['side'] == 'bid' else -1; nn = net + step
            if abs(nn) > 1: continue
            if net != 0 and abs(nn) < abs(net):
                if open_leg is not None:
                    rows.append((f['settle'] + open_leg['settle'],
                                 open_leg.get('spread', 0.0), wsig,
                                 open_leg.get('k', 7), fav_prob(open_leg)))
                open_leg = None
            else:
                open_leg = f
            net = nn
    rows = np.array(rows, float)
    marg, spr, ws_sig, kk, favp = rows[:, 0], rows[:, 1], rows[:, 2], rows[:, 3], rows[:, 4]
    print(f"total boxes={len(marg)} overall mean={marg.mean()*100:+.2f}c")
    def grp(mask, name):
        if mask.sum() == 0:
            print(f"  {name:<34} n=0"); return
        print(f"  {name:<34} n={int(mask.sum()):5} ({mask.mean()*100:4.1f}%) mean={marg[mask].mean()*100:+7.2f}c neg%={(marg[mask]<0).mean()*100:4.1f}")
    grp(spr < 0.02, "thin spread (<2c)")
    grp(spr >= 0.02, "wide spread (>=2c)")
    grp(ws_sig > EDGE_SIG_HI, "high-|sig| window (>8bps)")
    grp((ws_sig >= EDGE_SIG_LO) & (ws_sig <= EDGE_SIG_HI), "mid-|sig| window (3-8bps)")
    grp(ws_sig < EDGE_SIG_LO, "low-|sig| window (<3bps)")
    grp(kk > EDGE_K_HI, "late slot (k>9)")
    grp((kk >= EDGE_K_LO) & (kk <= EDGE_K_HI), "mid slot (k5-9)")
    grp(kk < EDGE_K_LO, "early slot (k<5)")
    grp(favp > FAV_MAX, "deep favorite (>0.70)")
    grp(favp <= FAV_MAX, "non-favorite (<=0.70)")
    # combined ladder-pass region
    keep = (spr >= 0.01) & (ws_sig >= EDGE_SIG_LO) & (ws_sig <= EDGE_SIG_HI) & \
           (kk >= EDGE_K_LO) & (kk <= EDGE_K_HI) & (favp <= FAV_MAX)
    grp(keep, "LADDER-PASS region (all gates)")
    grp(~keep, "LADDER-BLOCKED region")

    # ---------- 2. LADDER ON ETH ----------
    print("\n--- 2. FULL LADDER ON ETH (R0+R1+edge+fav+R3) ---")
    full_kw = dict(buf=0.01, buf_dyn=0.02, r1=True, edge=True, fav=True, r3=True, r4=False, r5=False)
    fi, fsi, foi = walk_eth(fe, ws_is, **full_kw)
    fo, fso, foo = walk_eth(fe, ws_oos, **full_kw)
    line("FULL LADDER IS", L.full_metrics(fi, p0i, p0i), fsi.sum(), foi, len(ws_is))
    line("FULL LADDER OOS", L.full_metrics(fo, p0o, p0o), fso.sum(), foo, len(ws_oos))

    # ladder box lock-margin in the kept region
    print(f"LADDER-PASS box margin: mean={marg[keep].mean()*100:+.2f}c "
          f"neg%={(marg[keep]<0).mean()*100:.1f} (vs naked {marg.mean()*100:+.2f}c)")

    # ---------- LEAVE-ONE-OUT (OOS) ----------
    print("\n--- 2b. LEAVE-ONE-OUT ABLATION (OOS, vs full ladder) ---")
    base_net = L.full_metrics(fo, p0o, p0o)['nc']
    abls = [
        ("drop R0 buffer (buf=None)", dict(buf=None, buf_dyn=None)),
        ("drop R1 t36", dict(r1=False)),
        ("drop edge-select (k/vol)", dict(edge=False)),
        ("drop fav-avoidance", dict(fav=False)),
        ("drop R3 sell-cheap", dict(r3=False)),
        ("ADD R4 streak", dict(r4=True)),
    ]
    for nm, kw in abls:
        k2 = dict(full_kw); k2.update(kw)
        ao, aso, aoo = walk_eth(fe, ws_oos, **k2)
        m = L.full_metrics(ao, p0o, p0o)
        print(f"  {nm:<30} net={m['nc']:+7.2f}c (Δ{m['nc']-base_net:+6.2f}) sh={m['sh']:+.3f} "
              f"win%={m['wr']:4.1f} t={m['ts']:+6.2f} opens={aoo} strand={aso.sum()/len(ws_oos)*100:.1f}%")

    # ---------- single-rung (only that gate, vs P0) to see each rung's standalone effect ----------
    print("\n--- 2c. SINGLE-GATE ISOLATION (OOS, each gate alone on top of chase-complete) ---")
    singles = [
        ("naked chase-complete only", dict(buf=None, buf_dyn=None, r1=False, edge=False, fav=False, r3=False)),
        ("+R3 sell-cheap only", dict(buf=None, buf_dyn=None, r1=False, edge=False, fav=False, r3=True)),
        ("+R0 buffer>=1c only", dict(buf=0.01, buf_dyn=None, r1=False, edge=False, fav=False, r3=True)),
        ("+R0 buffer>=2c only", dict(buf=0.02, buf_dyn=None, r1=False, edge=False, fav=False, r3=True)),
        ("+R1 t36 only", dict(buf=None, buf_dyn=None, r1=True, edge=False, fav=False, r3=True)),
        ("+edge k/vol only", dict(buf=None, buf_dyn=None, r1=False, edge=True, fav=False, r3=True)),
        ("+fav-avoid only", dict(buf=None, buf_dyn=None, r1=False, edge=False, fav=True, r3=True)),
    ]
    for nm, kw in singles:
        ao, aso, aoo = walk_eth(fe, ws_oos, **kw)
        m = L.full_metrics(ao, p0o, p0o)
        print(f"  {nm:<30} net={m['nc']:+7.2f}c sh={m['sh']:+.3f} win%={m['wr']:4.1f} "
              f"t={m['ts']:+6.2f} opens={aoo} strand={aso.sum()/len(ws_oos)*100:.1f}%")

    # ---------- BTC momentum gate ----------
    print("\n--- 2d. BTC-MOMENTUM GATE (suppress ETH opens in high-|sig| BTC windows) ---")
    btc_tox = btc_momentum_windows(thresh=8.0)
    print(f"  BTC toxic windows: {len(btc_tox)}")
    go, gso, goo = walk_eth(fe, ws_oos, btc_toxic=btc_tox, **full_kw)
    mg = L.full_metrics(go, p0o, p0o)
    print(f"  full ladder + BTC-gate OOS: net={mg['nc']:+.2f}c (Δ{mg['nc']-base_net:+.2f}) "
          f"sh={mg['sh']:+.3f} win%={mg['wr']:.1f} t={mg['ts']:+.2f} opens={goo}")

    # ---------- BTC ladder comparison (run the BTC P0 + a comparable ladder) ----------
    print("\n--- BTC ladder reference (same edge+buffer ladder on BTC) ---")
    fb, wb = L.load_parquet_windows('btc')
    cutb = int(len(wb) * 0.6); wb_oos = wb[cutb:]
    p0b, _ = L.run_p0(fb, wb_oos)
    bo, bso, boo = walk_eth(fb, wb_oos, **full_kw)
    mb = L.full_metrics(bo, p0b, p0b)
    mb0 = L.full_metrics(p0b, p0b, p0b)
    print(f"  BTC P0 OOS:        net={mb0['nc']:+.2f}c win%={mb0['wr']:.1f} t={mb0['ts']:+.2f}")
    print(f"  BTC FULL LADDER OOS: net={mb['nc']:+.2f}c sh={mb['sh']:+.3f} win%={mb['wr']:.1f} "
          f"t={mb['ts']:+.2f} opens={boo} strand={bso.sum()/len(wb_oos)*100:.1f}%")

    print("\nDONE.")


if __name__ == '__main__':
    main()
