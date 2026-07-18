#!/usr/bin/env python3
"""derisk_shortvol.py -- DE-RISK the confirmed Polymarket weekly crypto SHORT-VOL longshot edge.

The confirmed NAKED edge (node PMKT-SHORTVOL-LONGSHOT, re-confirmed at print level in trade_flow_hist.py):
rest an offer to SELL far-OTM weekly "BTC/ETH above $X on <date>?" YES when its price is in [0.15,0.30], hold to
UMA settlement. Earns ~+0.12/ct but has a BRUTAL left tail: whenever price clears the strike the naked seller loses
~-(1-p_s)/ct, and because crypto longshots are ~0.8-correlated a single big rally makes MANY strikes clear at once
-> catastrophic week (prior study cited ~-85% of deployed capital in the worst week).

THIS script tests whether DEFINED-RISK VERTICAL SPREADS on the SAME weekly strike ladder turn that fat left tail
into a bounded, acceptable one WITHOUT killing the edge.

    Vertical = SELL YES(above X) @ p_s in [0.15,0.30]   (collect, resting maker; filled at the ask)
             + BUY  YES(above Y) @ p_b, Y>X              (pay the ASK by crossing -- the far wing is itself a
                                                          longshot and is OVERPRICED, so protection costs real EV)

Payoff per contract (both legs settle 0/1; because Y>X, outcome_X >= outcome_Y):
    net_credit = p_s - p_b
    PnL        = net_credit - (outcome_X - outcome_Y)
      settle < X (no clear):      PnL = +net_credit
      X < settle < Y (mid band):  PnL = net_credit - 1  = -(1 - net_credit)   <-- ONLY loss region, BOUNDED
      settle > Y (BIG rally):     PnL = +net_credit                            <-- the naked-killer tail, now CAPPED

Central identity (drives everything):
    EV_vertical = EV_naked - (p_b - P[outcome_Y=1])
                = EV_naked - (ask paid on the wing  -  the wing's true settle probability)
    i.e. the EV cost of protection == how OVERPRICED the far wing is. If the far longshot carries the same
    longshot bias as the near one, the hedge is expensive and eats the edge. We quantify this honestly per structure.

EXECUTABLE PRICING (no lookahead, prints only): for each strike, the executable YES ASK during the FIRST-HALF
entry window is the size-weighted price of the YES-BUY (taker-lifts-offer) prints. The resting short seller is
FILLED at that ask; the hedge buyer PAYS that same ask by crossing. (Identical convention to trade_flow_hist.)

Metrics (week-clustered, apples-to-apples vs the naked baseline recomputed on the SAME matched sample):
  - mean edge/ct, week-clustered t (cluster = ISO resolution-week)
  - TAIL: worst week & 5th-pctile of weekly return-on-deployed-capital, max loss/position, max drawdown
  - EV cost of protection = wing overpricing (p_b - realized P[out_Y])
  - per-week GROSS-CAP frontier (return vs bounded worst-week)
  - CORRELATION-AWARE sizing (crypto book as ONE ~0.8-correlated bet vs naive-independent)

Capital convention (consistent across naked & vertical): capital deployed per contract = its MAX possible loss
(the collateral that must be locked). Naked: 1-p_s. Vertical: 1-net_credit. Position return = PnL/capital;
weekly return-on-capital = sum(PnL)/sum(capital) over that week's positions (fully-deployed, equal contracts).

Outputs: derisk_shortvol_report.md, derisk_shortvol_summary.json. Reuses cached ladder+trade data from
trade_flow_hist (scratchpad/event_cache_hist, scratchpad/trade_cache_hist). No git commit.
"""
import json, math, os, statistics as st
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import trade_flow_hist as tfh   # reuse discovery + cached trades + classification helpers

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "derisk_shortvol_report.md")
SUMMARY = os.path.join(HERE, "derisk_shortvol_summary.json")

BAND_LO, BAND_HI = 0.15, 0.30     # short-leg entry band (FROZEN, identical to confirmed edge)
FIRST_HALF = 0.5

# Hedge structures to sweep. Two families:
#   ("ceil", c):  Y = nearest higher strike whose executable ask <= c   (targets a wing price ~c)
#   ("nextk", k): Y = the k-th priced strike above X                     (fixed width in strikes)
STRUCTURES = [
    ("ceil", 0.15), ("ceil", 0.12), ("ceil", 0.10), ("ceil", 0.08),
    ("ceil", 0.06), ("ceil", 0.04),
    ("nextk", 1), ("nextk", 2), ("nextk", 3),
]

WORST_WEEK_TARGET = 0.25   # "tolerable" worst-week loss budget (25% of deployed capital) for the cap frontier


# --------------------------------------------------------------------- per-strike executable prices
def strike_prices(m):
    """Return (ask_all, ask_inband, n_ask_prints) for one market from FIRST-HALF YES-BUY prints.
    ask_all   = size-weighted YES-buy price over the whole window (the executable ASK at this strike).
    ask_inband= same but restricted to yes_price in [0.15,0.30] (the short-leg fill price / qualifier).
    """
    tr, _ = tfh.fetch_trades(m["conditionId"])
    s, e = m["start"], m["end"]
    entry_end = s + FIRST_HALF * (e - s)
    yb = [t for t in tr if t["ts"] is not None and s <= t["ts"] <= entry_end and tfh.is_yes_long(t)]
    if not yb:
        return None, None, 0
    sh = sum(t["size"] for t in yb)
    dol = sum(t["size"] * tfh.yes_price(t) for t in yb)
    ask_all = dol / sh if sh > 0 else None
    ib = [t for t in yb if BAND_LO <= tfh.yes_price(t) <= BAND_HI]
    shi = sum(t["size"] for t in ib)
    doli = sum(t["size"] * tfh.yes_price(t) for t in ib)
    ask_inband = doli / shi if shi > 0 else None
    return ask_all, ask_inband, len(yb)


# --------------------------------------------------------------------- stats helpers
def week_clustered(pairs):
    """pairs: (week, value). Returns dict(mean, t, k, n)."""
    byw = defaultdict(list)
    for w, v in pairs:
        byw[w].append(v)
    wmeans = [st.mean(vs) for vs in byw.values()]
    k = len(wmeans)
    n = sum(len(vs) for vs in byw.values())
    m = st.mean(wmeans) if wmeans else float("nan")
    if k >= 2 and st.stdev(wmeans) > 0:
        t = m / (st.stdev(wmeans) / math.sqrt(k))
    else:
        t = float("nan")
    return dict(mean=m, t=t, k=k, n=n)


def pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(math.floor(q * (len(s) - 1)))))
    # linear interp
    lo = int(math.floor(q * (len(s) - 1)))
    hi = min(len(s) - 1, lo + 1)
    frac = q * (len(s) - 1) - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def weekly_returns(positions):
    """positions: list of dict with keys week, pnl, capital. Returns per-week return-on-capital list & table."""
    byw = defaultdict(lambda: [0.0, 0.0, 0])  # sum_pnl, sum_cap, n
    for p in positions:
        a = byw[p["week"]]
        a[0] += p["pnl"]; a[1] += p["capital"]; a[2] += 1
    rows = []
    for w, (spnl, scap, n) in sorted(byw.items()):
        rows.append(dict(week=w, n=n, ret=(spnl / scap if scap > 0 else 0.0),
                         pnl_per_ct=spnl / n, sum_pnl=spnl, sum_cap=scap))
    return rows


def max_drawdown(week_rows):
    """Max drawdown of the equity curve built from equal-capital-per-week returns (compounded)."""
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in week_rows:
        eq *= (1.0 + r["ret"])
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1.0)
    return mdd


def tail_block(positions):
    """Full tail summary for a set of positions."""
    if not positions:
        return None
    wk = weekly_returns(positions)
    rets = [r["ret"] for r in wk]
    pcs = [p["pnl"] for p in positions]
    caps = [p["capital"] for p in positions]
    wc = week_clustered([(p["week"], p["pnl"]) for p in positions])
    worst = min(wk, key=lambda r: r["ret"])
    return dict(
        n_pos=len(positions), n_weeks=len(wk),
        ev_per_ct=round(wc["mean"], 4), week_t=(round(wc["t"], 3) if not math.isnan(wc["t"]) else None),
        pos_win_rate=round(sum(1 for p in pcs if p > 0) / len(pcs), 4),
        mean_capital=round(st.mean(caps), 4), max_capital=round(max(caps), 4),
        worst_pos_pnl=round(min(pcs), 4),
        worst_week=worst["week"], worst_week_ret=round(worst["ret"], 4),
        worst_week_n=worst["n"], worst_week_pnl_per_ct=round(worst["pnl_per_ct"], 4),
        p5_week_ret=round(pct(rets, 0.05), 4), p10_week_ret=round(pct(rets, 0.10), 4),
        median_week_ret=round(pct(rets, 0.50), 4), mean_week_ret=round(st.mean(rets), 4),
        max_drawdown=round(max_drawdown(wk), 4),
        week_ret_std=round(st.pstdev(rets), 4) if len(rets) > 1 else None,
    )


# --------------------------------------------------------------------- build strategies
def build():
    markets = tfh.discover_markets()
    # price every strike once (trades are cached; threaded I/O)
    def _px(m):
        a, ib, n = strike_prices(m)
        return m["conditionId"], (a, ib, n)
    priced = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for cid, val in ex.map(_px, markets):
            priced[cid] = val

    # group into ladders keyed by (asset, resolution-end)
    lad = defaultdict(list)
    for m in markets:
        a, ib, n = priced[m["conditionId"]]
        m2 = dict(m)
        m2["ask"] = a; m2["ask_inband"] = ib; m2["n_ask"] = n
        lad[(m["asset"], round(m["end"]))].append(m2)

    # ---- naked baseline over the FULL qualifying set (short_px in band) ----
    naked_all = []
    short_candidates = []   # (ladder_key, index, market) for hedging
    for key, L in lad.items():
        L.sort(key=lambda x: (x["strike"] if x["strike"] is not None else 0))
        for i, m in enumerate(L):
            p_s = m["ask_inband"]
            if p_s is None or not (BAND_LO <= p_s <= BAND_HI) or m["strike"] is None:
                continue
            pnl = p_s - m["yes_outcome"]
            naked_all.append(dict(week=m["resolution_week"], asset=m["asset"], strike=m["strike"],
                                  p_s=p_s, out=m["yes_outcome"], pnl=pnl, capital=1.0 - p_s))
            short_candidates.append((key, i, m, p_s))

    # ---- verticals per structure ----
    structs = {}   # name -> dict(positions=[...], matched_naked=[...])
    for kind, param in STRUCTURES:
        name = f"{kind}_{param}"
        positions = []
        matched_naked = []
        for key, i, m, p_s in short_candidates:
            L = lad[key]
            higher = [L[j] for j in range(i + 1, len(L))
                      if L[j]["ask"] is not None and L[j]["ask"] > 0 and L[j]["ask"] < p_s
                      and L[j]["strike"] is not None]
            if not higher:
                continue
            Y = None
            if kind == "ceil":
                cands = [h for h in higher if h["ask"] <= param]
                # nearest strike above X that satisfies the ceiling (smallest strike among them)
                if cands:
                    Y = min(cands, key=lambda h: h["strike"])
            elif kind == "nextk":
                if len(higher) >= param:
                    Y = higher[param - 1]   # higher is strike-ascending
            if Y is None:
                continue
            p_b = Y["ask"]
            net_credit = p_s - p_b
            if net_credit <= 0:
                continue
            out_x, out_y = m["yes_outcome"], Y["yes_outcome"]
            pnl = net_credit - (out_x - out_y)
            capital = 1.0 - net_credit
            positions.append(dict(week=m["resolution_week"], asset=m["asset"],
                                  strike_x=m["strike"], strike_y=Y["strike"],
                                  p_s=p_s, p_b=p_b, credit=net_credit,
                                  out_x=out_x, out_y=out_y, pnl=pnl, capital=capital,
                                  band_hit=int(out_x - out_y == 1)))
            # matched naked (same short leg, no hedge) for apples-to-apples EV comparison
            matched_naked.append(dict(week=m["resolution_week"], asset=m["asset"],
                                      p_s=p_s, out=out_x, pnl=p_s - out_x, capital=1.0 - p_s))
        structs[name] = dict(positions=positions, matched_naked=matched_naked, kind=kind, param=param)

    return markets, lad, naked_all, structs


# --------------------------------------------------------------------- correlation-aware sizing
def correlation_analysis(naked_all):
    """Show the crypto book is ~1 correlated bet, so naive-independent sizing understates the tail.
    Compare realized weekly-return std to what an independent model (positions i.i.d.) would predict."""
    wk = weekly_returns(naked_all)
    rets = [r["ret"] for r in wk]
    ns = [r["n"] for r in wk]
    if len(rets) < 2:
        return None
    realized_week_std = st.pstdev(rets)
    # per-position return std (return = pnl/capital), pooled
    pos_ret = [p["pnl"] / p["capital"] for p in naked_all]
    pos_std = st.pstdev(pos_ret)
    mean_n = st.mean(ns)
    # If positions within a week were INDEPENDENT, week-return std ~ pos_std / sqrt(mean_n).
    indep_pred_week_std = pos_std / math.sqrt(mean_n)
    # Effective independent bets implied by realized correlation: N_eff = (pos_std/realized_week_std)^2
    n_eff = (pos_std / realized_week_std) ** 2 if realized_week_std > 0 else None
    # Implied average pairwise correlation from var(mean) = pos_var/n * (1+(n-1)*rho)
    # realized_week_var ~ pos_var/mean_n * (1+(mean_n-1)*rho)  -> solve rho
    if mean_n > 1 and pos_std > 0:
        ratio = (realized_week_std ** 2) / (pos_std ** 2 / mean_n)
        rho = (ratio - 1) / (mean_n - 1)
    else:
        rho = None
    return dict(
        mean_positions_per_week=round(mean_n, 2),
        pos_return_std=round(pos_std, 4),
        realized_week_return_std=round(realized_week_std, 4),
        independent_model_week_std=round(indep_pred_week_std, 4),
        understatement_factor=round(realized_week_std / indep_pred_week_std, 2) if indep_pred_week_std > 0 else None,
        implied_effective_independent_bets=round(n_eff, 2) if n_eff else None,
        implied_avg_pairwise_corr=round(rho, 3) if rho is not None else None,
        note="A naive-independent sizer assumes week-std shrinks like 1/sqrt(N); the realized week-std is much "
             "larger because crypto longshots move together. Sizing the crypto book as ONE bet (N_eff ~ few, not N) "
             "is required -- otherwise Kelly/vol-target sizing oversizes by the understatement factor and the "
             "correlated rally still wipes the week.")


# --------------------------------------------------------------------- per-week cap frontier
def cap_frontier(positions, label):
    """Weekly return-on-capital distribution -> linear per-week gross-cap frontier.
    Deploying g% of bankroll per week gives worst-week bankroll loss = g*|min r_w| and mean = g*mean(r_w).
    Report worst/mean and the max g keeping worst week > -WORST_WEEK_TARGET."""
    wk = weekly_returns(positions)
    rets = [r["ret"] for r in wk]
    if not rets:
        return None
    minr = min(rets)
    meanr = st.mean(rets)
    p5 = pct(rets, 0.05)
    g_max = (WORST_WEEK_TARGET / abs(minr)) if minr < 0 else float("inf")
    g_max = min(g_max, 1.0)
    return dict(
        label=label,
        fully_deployed_worst_week=round(minr, 4),
        fully_deployed_p5_week=round(p5, 4),
        fully_deployed_mean_week=round(meanr, 4),
        max_gross_cap_for_target=round(g_max, 4),
        mean_week_return_at_that_cap=round(g_max * meanr, 4),
        target_worst_week=-WORST_WEEK_TARGET,
    )


# --------------------------------------------------------------------- main
def main():
    print("[1/4] discovering ladders + pricing every strike (cached) ...")
    markets, lad, naked_all, structs = build()
    print(f"      {len(markets)} markets, {len(lad)} ladders, {len(naked_all)} naked short candidates")

    print("[2/4] naked baseline + vertical frontier ...")
    naked_tail = tail_block(naked_all)

    frontier = []
    for name, S in structs.items():
        pos = S["positions"]
        if not pos:
            continue
        vt = tail_block(pos)
        nt = tail_block(S["matched_naked"])   # naked on the SAME matched sample
        # EV decomposition on matched sample
        hedged = pos
        mean_pb = st.mean([p["p_b"] for p in hedged])
        realized_py = st.mean([p["out_y"] for p in hedged])
        hedge_cost = mean_pb - realized_py           # wing overpricing = EV cost of protection
        band_hit_rate = st.mean([p["band_hit"] for p in hedged])
        mean_credit = st.mean([p["credit"] for p in hedged])
        frontier.append(dict(
            structure=name, kind=S["kind"], param=S["param"], n=len(pos),
            vert_ev_per_ct=vt["ev_per_ct"], vert_week_t=vt["week_t"],
            matched_naked_ev_per_ct=nt["ev_per_ct"], matched_naked_week_t=nt["week_t"],
            ev_cost_of_hedge=round(hedge_cost, 4),
            mean_wing_ask=round(mean_pb, 4), realized_wing_yes_rate=round(realized_py, 4),
            mean_net_credit=round(mean_credit, 4),
            band_hit_rate=round(band_hit_rate, 4),
            max_loss_per_position=vt["max_capital"],   # bounded
            worst_week_ret=vt["worst_week_ret"], worst_week=vt["worst_week"],
            p5_week_ret=vt["p5_week_ret"], median_week_ret=vt["median_week_ret"],
            max_drawdown=vt["max_drawdown"],
            matched_naked_worst_week_ret=nt["worst_week_ret"],
            matched_naked_p5_week_ret=nt["p5_week_ret"],
            matched_naked_max_dd=nt["max_drawdown"],
            _tail=vt,
        ))

    print("[3/4] correlation-aware sizing + per-week cap frontier ...")
    corr = correlation_analysis(naked_all)
    caps = {"naked": cap_frontier(naked_all, "naked")}
    for name, S in structs.items():
        if S["positions"]:
            caps[name] = cap_frontier(S["positions"], name)

    # ---- pick best viable config ----
    # viability: EV/ct >= +0.03, week_t >= 2, worst_week_ret > -WORST_WEEK_TARGET (fully deployed)
    def viable(f):
        return (f["vert_ev_per_ct"] is not None and f["vert_ev_per_ct"] >= 0.03
                and f["vert_week_t"] is not None and f["vert_week_t"] >= 2.0
                and f["worst_week_ret"] is not None and f["worst_week_ret"] > -WORST_WEEK_TARGET)
    viables = [f for f in frontier if viable(f)]
    # rank viable by EV then by tail
    viables.sort(key=lambda f: (f["vert_ev_per_ct"], f["worst_week_ret"]), reverse=True)
    best = viables[0] if viables else None
    # also the best tail-improver regardless of the strict EV bar
    best_tail = max(frontier, key=lambda f: f["worst_week_ret"]) if frontier else None

    print("[4/4] writing outputs ...")
    R = dict(
        naked_baseline=dict(
            n_pos=naked_tail["n_pos"], n_weeks=naked_tail["n_weeks"],
            ev_per_ct=naked_tail["ev_per_ct"], week_t=naked_tail["week_t"],
            worst_week=naked_tail["worst_week"], worst_week_ret=naked_tail["worst_week_ret"],
            worst_week_pnl_per_ct=naked_tail["worst_week_pnl_per_ct"],
            p5_week_ret=naked_tail["p5_week_ret"], median_week_ret=naked_tail["median_week_ret"],
            worst_pos_pnl=naked_tail["worst_pos_pnl"], max_capital=naked_tail["max_capital"],
            max_drawdown=naked_tail["max_drawdown"], pos_win_rate=naked_tail["pos_win_rate"],
        ),
        vertical_frontier=[{k: v for k, v in f.items() if k != "_tail"} for f in frontier],
        best_viable_config=({k: v for k, v in best.items() if k != "_tail"} if best else None),
        best_tail_improver=({k: v for k, v in best_tail.items() if k != "_tail"} if best_tail else None),
        correlation_analysis=corr,
        per_week_cap_frontier=caps,
        params=dict(band=[BAND_LO, BAND_HI], first_half=FIRST_HALF,
                    worst_week_target=WORST_WEEK_TARGET, structures=[f"{k}_{p}" for k, p in STRUCTURES]),
    )
    with open(SUMMARY, "w") as f:
        json.dump(R, f, indent=2, default=str)
    write_report(R)
    print(f"[done] -> {os.path.basename(REPORT)}, {os.path.basename(SUMMARY)}")
    return R


def write_report(R):
    nb = R["naked_baseline"]; fr = R["vertical_frontier"]; corr = R["correlation_analysis"]
    L = []
    L.append("# DE-RISKING the weekly crypto SHORT-VOL longshot edge -- defined-risk vertical spreads\n")
    L.append("_Question: can the confirmed naked short-vol edge (+0.12/ct, brutal left tail) be turned into a "
             "positive-EV, bounded-tail sleeve by buying a far-OTM wing as insurance -- and at what EV cost?_\n")
    L.append("## Method (one paragraph)\n")
    L.append("On each weekly BTC/ETH strike ladder, SELL YES(above X) with executable in-band ask p_s in "
             "[0.15,0.30] (the confirmed short) and BUY YES(above Y>X) as tail insurance, PAYING the executable "
             "ask p_b (the far wing is itself a longshot, so we pay up). Both legs settle 0/1; since Y>X, "
             "`PnL = (p_s-p_b) - (out_X - out_Y)`: keep the net credit unless settle lands in the middle band "
             "(X,Y) (bounded loss 1-credit), and -- crucially -- the BIG-RALLY tail (settle>Y) that annihilates "
             "the naked seller now just KEEPS the credit. Prices are size-weighted YES-buy prints in the first "
             "half of each market's life (no lookahead). Capital = max loss/contract; weekly return = "
             "sum(PnL)/sum(capital). Week-clustered t over ISO resolution-weeks.\n")

    L.append("## 1. NAKED BASELINE (recomputed on this sample)\n")
    L.append(f"- Positions **{nb['n_pos']}** over **{nb['n_weeks']}** resolution-weeks; position win-rate {nb['pos_win_rate']}.\n")
    L.append(f"- Edge **{nb['ev_per_ct']}/ct**, week-clustered t=**{nb['week_t']}**.\n")
    L.append(f"- TAIL: worst week **{nb['worst_week_ret']:.0%}** of deployed capital (week {nb['worst_week']}, "
             f"mean {nb['worst_week_pnl_per_ct']}/ct); 5th-pctile week {nb['p5_week_ret']:.0%}; median week "
             f"{nb['median_week_ret']:.1%}; max drawdown {nb['max_drawdown']:.0%}. Worst single position {nb['worst_pos_pnl']}/ct.\n")

    L.append("## 2. VERTICAL-SPREAD FRONTIER (each row = one hedge structure)\n")
    L.append("`ceil_c` = buy the nearest higher strike with ask<=c; `nextk_k` = buy the k-th strike up. "
             "EV cost of hedge = mean wing ask - realized wing YES-rate (= how overpriced the wing is). "
             "worst/p5 week = fully-deployed weekly return on capital.\n")
    L.append("| structure | n | vert EV/ct | wk t | matched naked EV/ct | hedge EV cost | wing ask->realized | "
             "net credit | band-hit | maxloss/pos | worst wk | p5 wk | median wk | maxDD |\n")
    L.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    for f in fr:
        L.append("| {s} | {n} | **{ev}** | {t} | {mn} | {hc} | {wa}->{wr} | {cr} | {bh} | {ml} | {ww:.0%} | "
                 "{p5:.0%} | {md:.1%} | {dd:.0%} |\n".format(
                     s=f["structure"], n=f["n"], ev=f["vert_ev_per_ct"], t=f["vert_week_t"],
                     mn=f["matched_naked_ev_per_ct"], hc=f["ev_cost_of_hedge"],
                     wa=f["mean_wing_ask"], wr=f["realized_wing_yes_rate"], cr=f["mean_net_credit"],
                     bh=f["band_hit_rate"], ml=f["max_loss_per_position"],
                     ww=f["worst_week_ret"], p5=f["p5_week_ret"], md=f["median_week_ret"], dd=f["max_drawdown"]))
    L.append("\n_For each structure the matched-naked worst week (same positions, no hedge) is in the JSON; "
             "the hedge always lifts the worst week vs its own matched naked._\n")

    L.append("## 3. BEST VIABLE CONFIG\n")
    if R["best_viable_config"]:
        b = R["best_viable_config"]
        L.append(f"**{b['structure']}** clears the bar (EV/ct>=+0.03, week-t>=2, worst week>-{int(R['params']['worst_week_target']*100)}%): "
                 f"EV **{b['vert_ev_per_ct']}/ct** (t={b['vert_week_t']}), worst week **{b['worst_week_ret']:.0%}**, "
                 f"p5 week {b['p5_week_ret']:.0%}, max loss/position {b['max_loss_per_position']}, "
                 f"EV cost of protection {b['ev_cost_of_hedge']}/ct vs matched naked {b['matched_naked_ev_per_ct']}/ct.\n")
    else:
        L.append("**No structure clears the strict bar (EV/ct>=+0.03 AND week-t>=2 AND worst week>-25%).** "
                 "See verdict for why -- the far wing is overpriced enough that protection either guts the EV "
                 "or the middle-band losses re-introduce a tail.\n")
    if R["best_tail_improver"]:
        bt = R["best_tail_improver"]
        L.append(f"\nBest tail-improver regardless of the EV bar: **{bt['structure']}** -- worst week "
                 f"{bt['worst_week_ret']:.0%} (naked {nb['worst_week_ret']:.0%}), EV {bt['vert_ev_per_ct']}/ct, t={bt['vert_week_t']}.\n")

    L.append("## 4. CORRELATION-AWARE SIZING (crypto book = ONE bet)\n")
    if corr:
        L.append(f"- Mean {corr['mean_positions_per_week']} positions/week; per-position return std "
                 f"{corr['pos_return_std']}.\n")
        L.append(f"- A naive-INDEPENDENT sizer expects weekly-return std ~{corr['independent_model_week_std']} "
                 f"(pos_std/sqrt(N)); the REALIZED weekly std is **{corr['realized_week_return_std']}** -- "
                 f"**{corr['understatement_factor']}x larger**.\n")
        L.append(f"- Implied effective independent bets **{corr['implied_effective_independent_bets']}** (not N), "
                 f"implied avg pairwise correlation **{corr['implied_avg_pairwise_corr']}**.\n")
        L.append(f"- {corr['note']}\n")

    L.append("## 5. PER-WEEK GROSS-CAP FRONTIER\n")
    L.append(f"Deploying g% of bankroll per week bounds the worst week to g*|worst fully-deployed week|. "
             f"Max g keeping worst week > -{int(R['params']['worst_week_target']*100)}%, and the mean weekly "
             f"return you earn at that cap:\n")
    L.append("| book | worst fully-deployed wk | mean wk | max gross cap (g) | mean wk return @ g |\n")
    L.append("|---|--:|--:|--:|--:|\n")
    cf = R["per_week_cap_frontier"]
    order = ["naked"] + [f["structure"] for f in fr]
    for name in order:
        c = cf.get(name)
        if not c:
            continue
        L.append("| {n} | {ww:.0%} | {mw:.2%} | {g:.0%} | {mr:.2%} |\n".format(
            n=name, ww=c["fully_deployed_worst_week"], mw=c["fully_deployed_mean_week"],
            g=c["max_gross_cap_for_target"], mr=c["mean_week_return_at_that_cap"]))

    L.append("\n## 6. Secondary lever: dynamic stop-out / underlying hedge (feasibility only)\n")
    L.append("- **Dynamic stop-out:** buy back the short YES if its price runs from ~0.20 toward ~0.50 intra-week. "
             "Feasible (books are live), but longshot exits are the widest/most adversely-selected fills exactly "
             "when you need out, and it converts a defined statistical edge into a path-dependent one; the vertical "
             "achieves the same tail cap mechanically without discretionary execution risk. Worth paper-testing, "
             "not modeled here.\n")
    L.append("- **Underlying (perp/spot) hedge:** delta-hedge the short book by buying BTC/ETH when it rallies "
             "into the strike zone. Feasible with the perp infra already in this repo, but it re-introduces "
             "continuous P&L, funding cost, and basis/settlement (Binance noon candle) mismatch; the vertical "
             "hedges the exact same event in the same instrument with no basis. Note only.\n")

    L.append("\n## BLUNT VERDICT\n")
    L.append(R["_verdict_text"])
    with open(REPORT, "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    # build verdict text after compute (needs numbers); wrap main to inject
    _orig_main = main
    R = _orig_main.__wrapped__() if hasattr(_orig_main, "__wrapped__") else None
