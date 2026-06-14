"""COMBINATION + ROBUSTNESS: does multi-factor beat momentum-alone?

Two combination schemes over the factors that PAY OOS:
  (A) equal-risk-weight z-score blend: combined_score = sum_f sign_f * z(score_f),
      then rank the combined score cross-sectionally -> one L/S book (true factor
      blend at the SCORE level, lower turnover than summing separate books).
  (B) inverse-vol / risk-parity blend of the separate factor RETURN streams
      (allocate ∝ 1/trailing-vol of each factor's pnl).

We compare every config to MOMENTUM-ALONE on OOS Sharpe AND maxDD, and on a
RECENT-regime holdout (last 18 months). Robustness: weight-grid plateau, and the
overfit test (does adding a factor that doesn't pay OOS hurt?).

Costs/window/conventions identical to multifactor.py.
"""
import os, glob, json, itertools
import numpy as np
import pandas as pd
from multifactor import (load_prices, load_funding, perf, split, score_to_weights,
                         backtest_weights, zscore, f_mom, f_lowvol, f_rev, f_size, f_carry,
                         COST_BPS_BASE, IS_FRAC, ANN, RECENT_MONTHS)

C, V = load_prices()
rets = C.pct_change()
F = load_funding(C)

SCORES = {
    "MOM": f_mom(C),
    "LOWVOL": f_lowvol(C),
    "REV": f_rev(C),
    "SIZE": f_size(C, V),
}
if F is not None and F.shape[1] >= 4:
    SCORES["CARRY"] = f_carry(F).reindex(columns=C.columns)


def combo_net(weights_dict, reb=7, cost_bps=COST_BPS_BASE):
    """Score-level equal-risk blend: combined z-score with given factor weights.
    If CARRY participates, restrict the whole book to the funding-data window so the
    blend is NOT silently diluted to MOM-only in the pre-funding years."""
    z = None
    for f, wt in weights_dict.items():
        if wt == 0:
            continue
        zf = zscore(SCORES[f]) * wt
        z = zf if z is None else z.add(zf, fill_value=0.0)
    w = score_to_weights(z)
    net = backtest_weights(w, rets, reb, cost_bps)
    if "CARRY" in weights_dict and weights_dict.get("CARRY", 0) != 0:
        fund_dates = SCORES["CARRY"].dropna(how="all").index
        if len(fund_dates):
            net = net.where(net.index >= fund_dates.min())
    return net


def recent_idx(idx):
    cutoff = idx.max() - pd.DateOffset(months=RECENT_MONTHS)
    return idx[idx >= cutoff]


def stats_block(net, label, common_start=None):
    net = net.dropna()
    idx = net.index
    is_idx, oos_idx = split(idx)
    rec = recent_idx(idx)
    o, r = perf(net.loc[oos_idx]), perf(net.loc[rec])
    row = dict(config=label,
               oos_sharpe=round(o["sharpe"], 3), oos_maxdd=round(o["maxdd"], 3),
               oos_ann=round(o["ann"], 3),
               recent_sharpe=round(r["sharpe"], 3), recent_maxdd=round(r["maxdd"], 3),
               recent_ann=round(r["ann"], 3))
    if common_start is not None:
        cw = net.loc[net.index >= common_start]
        c = perf(cw)
        row["cw_sharpe"] = round(c["sharpe"], 3)
        row["cw_maxdd"] = round(c["maxdd"], 3)
        row["cw_ann"] = round(c["ann"], 3)
    return row


def main():
    rows = []

    # common window = the carry-factor window (so MOM vs MOM+CARRY is apples-to-apples)
    common_start = None
    if "CARRY" in SCORES:
        cstart = combo_net({"CARRY": 1}).dropna().index.min()
        common_start = cstart
        print("Common window (carry-aligned) starts:", cstart.date())

    # baseline: momentum alone
    mom_only = combo_net({"MOM": 1})
    rows.append(stats_block(mom_only, "MOM-only (baseline)", common_start))

    # individual factors already done in multifactor.py; here we test BLENDS.
    # Determine which factors pay OOS standalone (>0.3) from saved standalone.json
    sa = json.load(open("/tmp/cx_multifactor/standalone.json"))
    paying = [d["factor"] for d in sa["standalone"] if d["oos_sharpe"] and d["oos_sharpe"] > 0.30]
    print("Factors paying OOS standalone (>0.30):", paying)

    # Always test MOM + each candidate partner pairwise (common window decides), plus
    # blend of MOM with the standalone-paying partners.
    candidates = [f for f in SCORES if f != "MOM"]
    for f in candidates:
        rows.append(stats_block(combo_net({"MOM": 1, f: 1}), f"MOM+{f} (EW)", common_start))
    others = [f for f in paying if f != "MOM"]
    if len(others) >= 2:
        ew = {f: 1 for f in paying}
        rows.append(stats_block(combo_net(ew), "MOM+paying (EW z-blend)", common_start))
    if "CARRY" in SCORES:
        pay_plus_carry = {f: 1 for f in set(paying + ["MOM", "CARRY"])}
        rows.append(stats_block(combo_net(pay_plus_carry),
                                "MOM+paying+CARRY (EW z-blend)", common_start))

    # OVERFIT test: add NON-paying price factors to the blend, see if it hurts
    nonpay = [d["factor"] for d in sa["standalone"]
              if d["factor"] in SCORES and (not d["oos_sharpe"] or d["oos_sharpe"] <= 0.30)]
    allw = {f: 1 for f in list(SCORES) if f != "CARRY"}  # all price factors EW
    rows.append(stats_block(combo_net(allw),
                            f"ALL price factors EW (incl non-paying {nonpay})", common_start))

    # ROBUSTNESS: MOM weight grid vs CARRY (or first paying partner) - plateau check
    grid_rows = []
    partner = "CARRY" if "CARRY" in SCORES else (others[0] if others else None)
    if partner:
        for wm in [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
            s = stats_block(combo_net({"MOM": wm, partner: 1.0}),
                            f"MOM*{wm}+{partner}", common_start)
            grid_rows.append(s)

    # inverse-vol blend of factor RETURN streams (scheme B) over MOM + paying partners
    rpfac = list(set(paying + ["MOM"]))
    nets = {f: combo_net({f: 1}) for f in rpfac}
    nd = pd.DataFrame(nets).dropna()
    invvol_w = 1.0 / nd.rolling(60).std()
    invvol_w = invvol_w.div(invvol_w.sum(axis=1), axis=0)
    rp = (nd * invvol_w.shift(1)).sum(axis=1)
    rows.append(stats_block(rp, f"Risk-parity (inv-vol) blend {rpfac}", common_start))

    out = dict(baseline_and_blends=rows, weight_grid=grid_rows, paying=paying, nonpaying=nonpay)
    json.dump(out, open("/tmp/cx_multifactor/combine.json", "w"), indent=2)

    print("\n===== COMBINATIONS vs MOM-only (10bps weekly) =====")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n===== ROBUSTNESS: MOM-weight grid =====")
    if grid_rows:
        print(pd.DataFrame(grid_rows).to_string(index=False))


if __name__ == "__main__":
    main()
