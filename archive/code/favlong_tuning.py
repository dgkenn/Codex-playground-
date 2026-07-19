#!/usr/bin/env python3
"""favlong_tuning.py -- DISCIPLINED hyperparameter + sizing study for the FAVLONG edge.

Protocol (statistical honesty is the point):
  1. Grid is defined BELOW, BEFORE any test evaluation.
  2. Select the SINGLE best config by POOLED (btc+eth+sol) TRAIN day-clustered t
     (pool per-(asset,day) means, exactly as favlongshot_edge.main does).
  3. Evaluate that ONE config on TEST exactly once.
  4. Sizing study on the selected config (flat / edge-prop / fractional-Kelly).

Reuses caches via FAVLONG_CACHE. Does NOT rebuild data. Offline research only.
"""
import math, statistics, os, sys, itertools
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from favlongshot_edge import NORM, KFEE, load_asset, _causal_sigma

TRAIN_CUTOFF = "2026-06-30"

# ---------------------------------------------------------------------------
# GRID -- fixed before looking at test.
GRID_DECISION_T = [600, 660, 690, 720, 750, 780]
GRID_EDGE       = [0.03, 0.05, 0.07, 0.10]
GRID_SIGMA_MULT = [0.8, 1.0, 1.2]
GRID_PRICEFILT  = [None, (0.05, 0.95)]   # None or (lo,hi) band on executable fill price
# ---------------------------------------------------------------------------


def trades(data, days, decision_t, edge, sigma_mult=1.0, pricefilt=None, fee=True, lag=0):
    """Yield per-day lists of trade dicts (pl, fair, price, side, depth) -- one pass, no look-ahead."""
    per_day = defaultdict(list)
    for day in days:
        for tk, strike, out_proxy in data.get(day, []):
            mc = tk[-1][1]
            outcome = 1 if (mc is not None and mc > 0.5) else 0
            if out_proxy != outcome:                     # clean-label only
                continue
            idx = None
            for i, x in enumerate(tk):
                if x[0] <= decision_t:
                    idx = i
                else:
                    break
            if idx is None or idx < 5:
                continue
            t, mid, spot, bid, ask = tk[idx][:5]
            if None in (spot, bid, ask):
                continue
            tau = 900 - t
            if tau < 30:
                continue
            sig = _causal_sigma(tk, idx)
            if not sig:
                continue
            sig *= sigma_mult
            z = (spot - strike) / (spot * sig * math.sqrt(tau)) if sig > 0 else 0
            fair = NORM(z)
            ev_buy, ev_sell = fair - ask, bid - fair
            fr = tk[min(idx + lag, len(tk) - 1)]
            fb, fa = fr[3], fr[4]
            fbq, faq = fr[5], fr[6]
            if None in (fb, fa):
                continue
            if ev_buy >= ev_sell and ev_buy > edge:
                price, side, depth = fa, "buy", faq
                if pricefilt and not (pricefilt[0] <= price <= pricefilt[1]):
                    continue
                pl = outcome - fa - (KFEE(fa) if fee else 0)
            elif ev_sell > edge:
                price, side, depth = fb, "sell", fbq
                if pricefilt and not (pricefilt[0] <= price <= pricefilt[1]):
                    continue
                pl = fb - outcome - (KFEE(fb) if fee else 0)
            else:
                continue
            per_day[day].append(dict(pl=pl, fair=fair, price=price, side=side,
                                     depth=(depth if depth else 0)))
    return per_day


def daily_t(day_means):
    dm = [m for m in day_means if m is not None]
    if len(dm) < 2 or statistics.stdev(dm) == 0:
        return float("nan")
    return statistics.mean(dm) / (statistics.stdev(dm) / math.sqrt(len(dm)))


def score_config(datasets, days_by_asset, decision_t, edge, sigma_mult, pricefilt):
    """Pooled per-(asset,day) mean-pl stats for a config over the given days."""
    asset_day_means = []
    per_asset = {}
    for a, data in datasets.items():
        days = days_by_asset[a]
        pd = trades(data, days, decision_t, edge, sigma_mult, pricefilt)
        dmeans = {d: statistics.mean([x["pl"] for x in v]) for d, v in pd.items() if v}
        for d in sorted(dmeans):
            asset_day_means.append(dmeans[d])
        allpl = [x["pl"] for v in pd.values() for x in v]
        per_asset[a] = dict(n=len(allpl),
                            mean=(statistics.mean(allpl) if allpl else float("nan")),
                            tclust=daily_t(list(dmeans.values())),
                            ndays=len(dmeans),
                            posdays=sum(1 for v in dmeans.values() if v > 0))
    pooled = dict(t=daily_t(asset_day_means),
                  n=len(asset_day_means),
                  mean=(statistics.mean(asset_day_means) if asset_day_means else float("nan")),
                  pos=sum(1 for m in asset_day_means if m > 0))
    return pooled, per_asset


def main():
    assets = ["btc", "eth", "sol"]
    datasets = {a: load_asset(a) for a in assets}
    all_days = {a: sorted(datasets[a]) for a in assets}
    train_days = {a: [d for d in all_days[a] if d <= TRAIN_CUTOFF] for a in assets}
    test_days = {a: [d for d in all_days[a] if d > TRAIN_CUTOFF] for a in assets}

    grid = list(itertools.product(GRID_DECISION_T, GRID_EDGE, GRID_SIGMA_MULT, GRID_PRICEFILT))
    print(f"# grid size = {len(grid)} configs; selection on TRAIN pooled day-clustered t only\n")

    results = []
    for dt, ed, sm, pf in grid:
        pooled, _ = score_config(datasets, train_days, dt, ed, sm, pf)
        results.append(((dt, ed, sm, pf), pooled))
    # rank by train pooled t (require a reasonable sample so we don't pick a tiny-n fluke)
    ranked = sorted(results, key=lambda r: (r[1]["t"] if r[1]["n"] >= 30 and not math.isnan(r[1]["t"]) else -9),
                    reverse=True)

    print("## TOP 10 TRAIN configs (by pooled day-clustered t)")
    print(f"{'decision_t':>10}{'edge':>6}{'sig':>5}{'pricefilt':>12}{'train_t':>9}{'n':>5}{'mean$':>9}{'pos':>6}")
    for (dt, ed, sm, pf), p in ranked[:10]:
        print(f"{dt:>10}{ed:>6}{sm:>5}{str(pf):>12}{p['t']:>9.2f}{p['n']:>5}{p['mean']:>9.4f}"
              f"{str(p['pos'])+'/'+str(p['n']):>6}")

    best_cfg, best_train = ranked[0]
    dt, ed, sm, pf = best_cfg
    print(f"\n## SELECTED (train-only): decision_t={dt} edge={ed} sigma_mult={sm} pricefilt={pf}")
    print(f"   train pooled t={best_train['t']:.2f} n={best_train['n']} mean=${best_train['mean']:.4f} "
          f"pos={best_train['pos']}/{best_train['n']}")

    # baseline for comparison on train + test
    base_cfg = (720, 0.05, 1.0, None)
    base_tr_p, _ = score_config(datasets, train_days, *base_cfg)
    base_te_p, base_te_a = score_config(datasets, test_days, *base_cfg)
    print(f"\n## BASELINE (720,0.05,1.0,None): train t={base_tr_p['t']:.2f}  "
          f"TEST t={base_te_p['t']:.2f} n={base_te_p['n']} mean=${base_te_p['mean']:.4f} "
          f"pos={base_te_p['pos']}/{base_te_p['n']}")

    # ---- THE ONE test evaluation of the selected config ----
    te_p, te_a = score_config(datasets, test_days, dt, ed, sm, pf)
    print(f"\n## SELECTED config TEST (OOS) -- single evaluation")
    print(f"   pooled OOS t={te_p['t']:.2f}  n={te_p['n']}  mean=${te_p['mean']:.4f}  "
          f"pos={te_p['pos']}/{te_p['n']}")
    for a in assets:
        r = te_a[a]
        print(f"   {a}: OOS t={r['tclust']:.2f} n={r['n']} mean=${r['mean']:.4f} "
              f"pos={r['posdays']}/{r['ndays']}")

    # =====================================================================
    # SIZING STUDY on the selected config
    # =====================================================================
    print("\n\n=== SIZING STUDY (selected config, TEST/OOS) ===")

    def sized_daily(datasets, days_by_asset, cfg, mode, cap=100, kelly_frac=0.25):
        """Return per-(asset,day) total-$ under a sizing rule. size in contracts."""
        dt, ed, sm, pf = cfg
        asset_day_tot = []
        per_asset_days = defaultdict(list)
        for a, data in datasets.items():
            pd = trades(data, days_by_asset[a], dt, ed, sm, pf)
            for d, v in pd.items():
                tot = 0.0
                for x in v:
                    pl = x["pl"]
                    depth = min(x["depth"], cap) if x["depth"] > 0 else cap
                    if mode == "flat":
                        size = 1
                    elif mode == "edgeprop":
                        # edge magnitude vs price, scaled to [0,cap]
                        e = abs(x["fair"] - x["price"])
                        size = max(1, min(cap, round(e / 0.05 * 20)))
                        size = min(size, depth)
                    elif mode == "kelly":
                        # binary Kelly: f = (p*b - (1-p)) / b, b = (1-price)/price for buy
                        p = x["fair"] if x["side"] == "buy" else (1 - x["fair"])
                        price = x["price"]
                        b = (1 - price) / price if price > 0 else 0
                        if b <= 0:
                            f = 0
                        else:
                            f = (p * b - (1 - p)) / b
                        f = max(0.0, f) * kelly_frac
                        size = max(1, min(cap, round(f * cap)))
                        size = min(size, depth)
                    else:
                        size = 1
                    tot += pl * size
                asset_day_tot.append(tot)
                per_asset_days[a].append((d, tot))
        return asset_day_tot, per_asset_days

    for mode in ["flat", "edgeprop", "kelly"]:
        tot, per = sized_daily(datasets, test_days, best_cfg, mode)
        t = daily_t(tot)
        print(f"  POOLED {mode:9s}: OOS daily-$ t={t:.2f}  mean=${statistics.mean(tot):+.3f}/asset-day  "
              f"total=${sum(tot):+.1f}  n={len(tot)}")

    print("\n  -- BTC-only sized (OOS) --")
    for mode in ["flat", "edgeprop", "kelly"]:
        tot, per = sized_daily({"btc": datasets["btc"]}, {"btc": test_days["btc"]}, best_cfg, mode)
        t = daily_t(tot)
        print(f"  BTC {mode:9s}: OOS daily-$ t={t:.2f}  mean=${statistics.mean(tot):+.3f}/day  "
              f"total=${sum(tot):+.1f}  n={len(tot)}")

    # also baseline config sized, for honest comparison
    print("\n  -- baseline config (720,0.05) sized, POOLED OOS (for comparison) --")
    for mode in ["flat", "edgeprop", "kelly"]:
        tot, _ = sized_daily(datasets, test_days, base_cfg, mode)
        print(f"  base {mode:9s}: OOS daily-$ t={daily_t(tot):.2f}  mean=${statistics.mean(tot):+.3f}  total=${sum(tot):+.1f}")


if __name__ == "__main__":
    main()
