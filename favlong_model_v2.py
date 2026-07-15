#!/usr/bin/env python3
"""favlong_model_v2.py -- can a BETTER fair-value model grow the FAVLONG OOS edge?

Keeps the taker mechanics of favlongshot_edge IDENTICAL (take the side the executable
price underprices by >= edge; +Kalshi fee KFEE=0.07*p*(1-p); clean market-settlement
label mid_close>0.5; pooled per-(asset,day) day-clustered t). ONLY the fair-value
probability model changes.

Variants tested (all causal / no look-ahead):
  VOL estimator for sigma:
    - baseline : pstdev of ALL causal log-returns up to decision idx  (favlongshot _causal_sigma)
    - trailing : pstdev of the LAST K causal log-returns (recent trailing tick window)
    - ewma     : EWMA(lambda) vol of causal tick log-returns (recent weighted more)
    - blend    : 0.5*baseline + 0.5*ewma
  MONEYNESS / drift:
    - arith    : z = (spot-strike)/(spot*sig*sqrt(tau))            (baseline)
    - logn     : z = ln(spot/strike)/(sig*sqrt(tau))              (lognormal)
    - logndrift: z = (ln(spot/strike) + (mu-0.5 sig^2)*tau)/(sig*sqrt(tau))  (causal drift mu)
  CALIBRATION (highest-value idea):
    - raw      : fair = NORM(z)
    - iso      : fit monotone isotonic map fairP_model -> empirical P(settle up) on TRAIN
                 (pooled across assets), apply on TEST. Corrects Gaussian mis-shape /
                 the favorite-longshot curve directly.

DISCIPLINE: decision_t=720, edge=0.03 fixed (matches the tuned baseline). All model
variants are ranked on TRAIN pooled day-clustered t; the SINGLE best is evaluated on
TEST exactly once. Multiple-testing count = number of variants scored on train.
Train = days<=2026-06-30 ; Test/OOS = days>2026-06-30. Offline research only.
"""
import math, statistics, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from favlongshot_edge import NORM, KFEE, load_asset

try:
    from sklearn.isotonic import IsotonicRegression
    HAVE_ISO = True
except Exception:
    HAVE_ISO = False

TRAIN_CUTOFF = "2026-06-30"
DECISION_T = 720
EDGE = 0.03
ASSETS = ["btc", "eth", "sol"]


# --------------------------------------------------------------------------- vol models
def _causal_logrets(tk, idx):
    sp = [tk[i][2] for i in range(idx + 1) if tk[i][2]]
    if len(sp) < 5:
        return None, None
    lr = [math.log(sp[i + 1] / sp[i]) for i in range(len(sp) - 1) if sp[i] > 0]
    if len(lr) < 4:
        return None, None
    dt = (tk[idx][0] - tk[0][0]) / max(1, len(lr))
    return lr, max(dt, 0.5)


def sigma_est(tk, idx, vol="baseline", K=90, lam=0.94):
    """Per-sqrt-second causal vol of spot under the chosen estimator. Returns (sig, mu_per_s)."""
    lr, dt = _causal_logrets(tk, idx)
    if lr is None:
        return None, None
    mu_per_s = statistics.mean(lr) / dt  # causal drift, per second
    base = statistics.pstdev(lr) / math.sqrt(dt)
    if vol == "baseline":
        sig = base
    elif vol == "trailing":
        tail = lr[-K:] if len(lr) >= 5 else lr
        sig = statistics.pstdev(tail) / math.sqrt(dt) if len(tail) >= 2 else base
    elif vol == "ewma":
        # EWMA variance of returns, recent weighted more (lambda decay on reversed series)
        m = statistics.mean(lr)
        var = 0.0
        w = 1.0
        wsum = 0.0
        for r in reversed(lr):          # most recent first, highest weight
            var += w * (r - m) ** 2
            wsum += w
            w *= lam
        var = var / wsum if wsum > 0 else statistics.pvariance(lr)
        sig = math.sqrt(var) / math.sqrt(dt)
    elif vol == "blend":
        m = statistics.mean(lr)
        var = 0.0; w = 1.0; wsum = 0.0
        for r in reversed(lr):
            var += w * (r - m) ** 2; wsum += w; w *= lam
        ew = math.sqrt(var / wsum) / math.sqrt(dt) if wsum > 0 else base
        sig = 0.5 * base + 0.5 * ew
    else:
        sig = base
    return sig, mu_per_s


def model_fair(tk, idx, spot, strike, tau, vol, money, sigma_mult=1.0):
    """Return raw model fair prob NORM(z), or None."""
    sig, mu = sigma_est(tk, idx, vol=vol)
    if not sig or sig <= 0:
        return None
    sig *= sigma_mult
    if money == "arith":
        z = (spot - strike) / (spot * sig * math.sqrt(tau))
    elif money == "logn":
        z = math.log(spot / strike) / (sig * math.sqrt(tau))
    elif money == "logndrift":
        num = math.log(spot / strike) + (mu - 0.5 * sig * sig) * tau
        z = num / (sig * math.sqrt(tau))
    else:
        z = (spot - strike) / (spot * sig * math.sqrt(tau))
    return NORM(z)


# --------------------------------------------------------------------------- data pass
def window_rows(data, days, vol, money, sigma_mult=1.0, decision_t=DECISION_T):
    """One causal pass. Yield per window: (day, fair_raw, outcome, bid, ask, fill_bid, fill_ask).
    Includes EVERY qualifying window (not just traded) so calibration sees the full dist."""
    rows = []
    for day in days:
        for tk, strike, out_proxy in data.get(day, []):
            mc = tk[-1][1]
            outcome = 1 if (mc is not None and mc > 0.5) else 0
            if out_proxy != outcome:                      # clean-label only
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
            fair = model_fair(tk, idx, spot, strike, tau, vol, money, sigma_mult)
            if fair is None:
                continue
            rows.append((day, fair, outcome, bid, ask))
    return rows


# --------------------------------------------------------------------------- calibration
def fit_isotonic(rows):
    """Fit monotone map model_fair -> empirical P(up) on train rows. Returns predictor fn."""
    if not rows:
        return None
    xs = [r[1] for r in rows]
    ys = [r[2] for r in rows]
    if HAVE_ISO:
        ir = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        ir.fit(xs, ys)
        return lambda p: float(ir.predict([min(max(p, 0.0), 1.0)])[0])
    # fallback: decile bucket means (monotone-ish)
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    nb = 12
    edges = [order[int(k * len(order) / nb)] for k in range(nb)] + [order[-1]]
    bnds = [xs[e] for e in edges]
    means = []
    for k in range(nb):
        lo, hi = bnds[k], bnds[k + 1]
        sel = [ys[i] for i in range(len(xs)) if lo <= xs[i] <= hi]
        means.append(statistics.mean(sel) if sel else 0.5)
    def pred(p):
        for k in range(nb):
            if p <= bnds[k + 1]:
                return means[k]
        return means[-1]
    return pred


# --------------------------------------------------------------------------- scoring
def daily_t(dm):
    dm = [m for m in dm if m is not None]
    if len(dm) < 2 or statistics.stdev(dm) == 0:
        return float("nan")
    return statistics.mean(dm) / (statistics.stdev(dm) / math.sqrt(len(dm)))


def score_rows(rows_by_asset, cal=None, edge=EDGE, fee=True):
    """Apply taker mechanics to precomputed rows. cal: optional calibration fn (per prob).
    Returns pooled dict + per-asset dict."""
    asset_day_means = []
    per_asset = {}
    for a, rows in rows_by_asset.items():
        per_day = defaultdict(list)
        for (day, fair, outcome, bid, ask) in rows:
            p = cal(fair) if cal else fair
            ev_buy, ev_sell = p - ask, bid - p
            if ev_buy >= ev_sell and ev_buy > edge:
                pl = outcome - ask - (KFEE(ask) if fee else 0)
            elif ev_sell > edge:
                pl = bid - outcome - (KFEE(bid) if fee else 0)
            else:
                continue
            per_day[day].append(pl)
        dmeans = {d: statistics.mean(v) for d, v in per_day.items() if v}
        for d in sorted(dmeans):
            asset_day_means.append(dmeans[d])
        allpl = [p for v in per_day.values() for p in v]
        per_asset[a] = dict(n=len(allpl),
                            mean=(statistics.mean(allpl) if allpl else float("nan")),
                            tclust=daily_t(list(dmeans.values())),
                            ndays=len(dmeans),
                            posdays=sum(1 for v in dmeans.values() if v > 0))
    pooled = dict(t=daily_t(asset_day_means), n=len(asset_day_means),
                  mean=(statistics.mean(asset_day_means) if asset_day_means else float("nan")),
                  pos=sum(1 for m in asset_day_means if m > 0))
    return pooled, per_asset


# --------------------------------------------------------------------------- main
def main():
    datasets = {a: load_asset(a) for a in ASSETS}
    all_days = {a: sorted(datasets[a]) for a in ASSETS}
    train_days = {a: [d for d in all_days[a] if d <= TRAIN_CUTOFF] for a in ASSETS}
    test_days = {a: [d for d in all_days[a] if d > TRAIN_CUTOFF] for a in ASSETS}

    VOLS = ["baseline", "trailing", "ewma", "blend"]
    MONEY = ["arith", "logn", "logndrift"]
    CALS = ["raw", "iso"]

    print("# FAVLONG model v2 -- fair-value model search (decision_t=720, edge=0.03)")
    print(f"# isotonic available: {HAVE_ISO}")
    print(f"# variants = {len(VOLS)}*{len(MONEY)}*{len(CALS)} = {len(VOLS)*len(MONEY)*len(CALS)} (multiple-testing count)\n")

    # Precompute raw rows per (vol,money) once for train & test (calibration reuses them).
    train_rows_cache = {}
    test_rows_cache = {}
    for vol in VOLS:
        for money in MONEY:
            train_rows_cache[(vol, money)] = {a: window_rows(datasets[a], train_days[a], vol, money) for a in ASSETS}
            test_rows_cache[(vol, money)] = {a: window_rows(datasets[a], test_days[a], vol, money) for a in ASSETS}

    results = []  # (label, train_pooled, cfg)
    for vol in VOLS:
        for money in MONEY:
            tr_rows = train_rows_cache[(vol, money)]
            for calname in CALS:
                cal = None
                if calname == "iso":
                    pooled_train_rows = [r for a in ASSETS for r in tr_rows[a]]
                    cal = fit_isotonic(pooled_train_rows)
                pooled, _ = score_rows(tr_rows, cal=cal)
                results.append((f"{vol}/{money}/{calname}", pooled, (vol, money, calname)))

    ranked = sorted(results, key=lambda r: (r[1]["t"] if r[1]["n"] >= 30 and not math.isnan(r[1]["t"]) else -9),
                    reverse=True)

    print("## ALL variants ranked by TRAIN pooled day-clustered t")
    print(f"{'variant':<28}{'train_t':>9}{'n':>6}{'mean$':>9}{'pos':>8}")
    for lbl, p, _ in ranked:
        print(f"{lbl:<28}{p['t']:>9.2f}{p['n']:>6}{p['mean']:>9.4f}{str(p['pos'])+'/'+str(p['n']):>8}")

    best_lbl, best_train, best_cfg = ranked[0]
    vol, money, calname = best_cfg
    print(f"\n## SELECTED (train-only): {best_lbl}  train t={best_train['t']:.2f} n={best_train['n']}")

    # ---- single TEST evaluation of the selected variant ----
    te_rows = test_rows_cache[(vol, money)]
    cal = None
    if calname == "iso":
        pooled_train_rows = [r for a in ASSETS for r in train_rows_cache[(vol, money)][a]]
        cal = fit_isotonic(pooled_train_rows)   # fit on TRAIN only, apply to TEST
    te_p, te_a = score_rows(te_rows, cal=cal)
    print(f"\n## SELECTED variant TEST (OOS) -- single evaluation")
    print(f"   pooled OOS t={te_p['t']:.2f}  n={te_p['n']}  mean=${te_p['mean']:.4f}  pos={te_p['pos']}/{te_p['n']}")
    for a in ASSETS:
        r = te_a[a]
        print(f"   {a}: OOS t={r['tclust']:.2f} n={r['n']} mean=${r['mean']:.4f} pos={r['posdays']}/{r['ndays']}")

    # ---- reference: reproduce tuned baseline (arith/baseline vol, sigma_mult 0.8, raw) OOS ----
    print("\n## REFERENCE: tuned baseline (arith / baseline-vol / sigma_mult=0.8 / raw / edge=0.03)")
    tb_te = {a: window_rows(datasets[a], test_days[a], "baseline", "arith", sigma_mult=0.8) for a in ASSETS}
    tb_p, tb_a = score_rows(tb_te, cal=None)
    print(f"   pooled OOS t={tb_p['t']:.2f}  n={tb_p['n']}  mean=${tb_p['mean']:.4f}  pos={tb_p['pos']}/{tb_p['n']}")
    for a in ASSETS:
        r = tb_a[a]
        print(f"   {a}: OOS t={r['tclust']:.2f} n={r['n']} mean=${r['mean']:.4f} pos={r['posdays']}/{r['ndays']}")

    # ---- also report every variant's TEST t (for the report table; NOT used for selection) ----
    print("\n## (disclosure) TEST t of ALL variants -- shown post-hoc, NOT the selection basis")
    print(f"{'variant':<28}{'test_t':>9}{'n':>6}{'mean$':>9}")
    for vol in VOLS:
        for money in MONEY:
            te_r = test_rows_cache[(vol, money)]
            for calname in CALS:
                cal = None
                if calname == "iso":
                    ptr = [r for a in ASSETS for r in train_rows_cache[(vol, money)][a]]
                    cal = fit_isotonic(ptr)
                p, _ = score_rows(te_r, cal=cal)
                print(f"{vol+'/'+money+'/'+calname:<28}{p['t']:>9.2f}{p['n']:>6}{p['mean']:>9.4f}")


if __name__ == "__main__":
    main()
