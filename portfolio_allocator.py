"""portfolio_allocator.py -- fractional-Kelly capital allocator across every sleeve in
sleeve_ledger.py. ALERT-ONLY: this script never writes to any trader's config, env, or CLI
flags. It only prints a recommendation (and, for the live crypto sleeve, the delta against
what's actually deployed) so a human decides whether to act on it -- see kalshi_trader.py's
--max-notional/--loss-limit, which are hand-set flags in .github/workflows/live.yml, not read
from anywhere this script writes.

METHODOLOGY (documented in full because every number here is an estimate on thin data):

1. PER-SLEEVE MEAN/VOL, JAMES-STEIN-FLAVORED SHRINKAGE
   Raw per-day mean and (sample, ddof=1) stdev of realized $ pnl come straight out of
   sleeve_ledger. Both are then shrunk toward a zero-edge prior with weight n/(n+K) -- more
   trailing days means less shrinkage, exactly the behavior classical James-Stein estimators
   have (shrink each unit's estimate toward a prior in proportion to how little you trust the
   unit's own sample). This is a SIMPLIFIED, single-unit analogue of true James-Stein (which
   shrinks toward the GRAND MEAN across >=3 comparable units using a data-driven shrinkage
   intensity from Stein's unbiased risk estimate) -- there usually aren't >=3 sleeves with
   enough history for that here, and sleeves are structurally different strategies where a
   shared grand mean isn't a meaningful null. So instead each sleeve shrinks toward a FIXED
   zero-mean prior with a fixed pseudo-count K (a tunable "how many days of data would it take
   to trust the sleeve's own mean" belief), which mimics the qualitative n-dependent shrinkage
   without needing a cross-sleeve population:
       mean_shrunk = mean_raw * n / (n + K_MEAN)                    K_MEAN = 10 (days)
       var_shrunk  = (n * var_raw + K_VAR * prior_var) / (n + K_VAR) K_VAR  = 10 (days)
       prior_var   = (VOL_PRIOR_FRAC * avg_notional_usd)^2   if the sleeve has any notional
                     (VOL_PRIOR_FRAC * PRIOR_BANKROLL_FRAC * bankroll)^2   otherwise (0-row sleeve)
   VOL_PRIOR_FRAC=0.05 is a placeholder ("daily pnl vol ~ 5% of $ deployed") pending more
   history -- there is no fitted basis for it yet, it exists only so a 0-history sleeve doesn't
   get an infinite/zero Sharpe.
   sharpe_shrunk = mean_shrunk / sqrt(var_shrunk)  (0 if var_shrunk == 0)

2. PAIRWISE CORRELATION
   Sample Pearson correlation on overlapping calendar days when >=MIN_OVERLAP_DAYS(=5) exist.
   Below that: rho=0.7 for two crypto_mm_* sleeves (documented prior -- box-harvester sleeves
   on different assets share the same market-structure/regime risk, so treating them as
   near-independent would understate concentration risk); rho=0.0 for every other thin/no-
   overlap pair (no basis to assume co-movement between, say, WTI paper and CPI paper, so the
   conservative default is "no assumed diversification benefit, no assumed extra concentration
   either"). Diagonal is always 1.0 (verbatim shrunk variance).

3. FRACTIONAL KELLY
   Multi-asset continuous-approximation Kelly: f* = Sigma^-1 * mu, mu/Sigma expressed as
   fractions of bankroll (mean_shrunk/bankroll, var_shrunk/bankroll^2, off-diag from rho).
   A small ridge (RIDGE=1e-6 * trace(Sigma)/n) is added to the diagonal before inversion so a
   near-singular thin-data covariance matrix doesn't blow up. Negative raw weights are clipped
   to 0 (a sleeve with a non-positive shrunk edge gets no allocation -- there is no "short a
   sleeve" primitive). The result is scaled by QUARTER_KELLY=0.25 (never full Kelly -- the
   standard practitioner haircut for parameter uncertainty, doubly justified here given how
   thin the inputs are), then hard capped: <=15% of bankroll per sleeve, <=40% of bankroll
   deployed in total (scaled down proportionally if the sum exceeds it after per-sleeve
   capping). This is a single-pass approximation of a box-constrained QP, not an exact solve --
   adequate for an alert-only preview, not a claim of optimality.

4. LIVE vs PAPER
   Paper sleeves (is_live=False) get $0 of the ACTUAL recommended allocation (nothing here ever
   controls real money) but their Kelly-implied $ amount is still computed and shown as
   "would-be" -- exactly so a promotion decision (paper -> live) can preview its capital
   footprint before it happens.

5. LIVE CRYPTO SLEEVE: IMPLIED PER-WINDOW LIMITS vs DEPLOYED
   kalshi_trader.py's --max-notional/--loss-limit are static CLI flags (currently 5 / 6, see
   .github/workflows/live.yml), not sized by this script. As a purely informational cross-check,
   this tool maps the recommended $ allocation onto the SAME units by treating the recommended
   allocation as the implied max-notional (both are "how much of bankroll this sleeve is allowed
   to have deployed at once") and applying the CURRENTLY DEPLOYED loss-limit/max-notional ratio
   (6/5 = 1.2x) to get an implied loss-limit. >2x divergence either direction from what's
   actually deployed is flagged REBALANCE-SUGGESTED -- an alert string only, never applied.

    python3 portfolio_allocator.py [--bankroll 50]
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import numpy as np

import sleeve_ledger

K_MEAN = 10.0                 # pseudo-days of zero-mean prior (JS-flavored shrinkage)
K_VAR = 10.0                  # pseudo-days of prior-variance weight
VOL_PRIOR_FRAC = 0.05         # prior daily-vol ~ 5% of $ notional deployed (placeholder)
PRIOR_BANKROLL_FRAC = 0.10    # 0-history sleeves: prior notional proxy = 10% of bankroll
MIN_OVERLAP_DAYS = 5          # below this, fall back to the correlation priors
RHO_CRYPTO_PRIOR = 0.7        # crypto_mm_* pairs, thin/no overlap
RHO_DEFAULT_PRIOR = 0.0       # every other thin/no-overlap pair
QUARTER_KELLY = 0.25
PER_SLEEVE_CAP_FRAC = 0.15    # of bankroll
TOTAL_CAP_FRAC = 0.40         # of bankroll
DEPLOYED_MAX_NOTIONAL = 5.0   # currently live .github/workflows/live.yml --max-notional
DEPLOYED_LOSS_LIMIT = 6.0     # currently live .github/workflows/live.yml --loss-limit
REBALANCE_FLAG_MULT = 2.0     # divergence threshold vs deployed


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _sample_var(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def sleeve_stats(rows: list[dict], bankroll: float) -> dict:
    """One entry per sleeve: {n_days, mean_raw, var_raw, mean_shrunk, var_shrunk, sharpe,
    avg_notional, is_live, dates: {date: pnl_usd}}."""
    grouped = sleeve_ledger.by_sleeve(rows)
    out = {}
    for name, srows in grouped.items():
        pnls = [r["pnl_usd"] for r in srows]
        notionals = [r["notional_usd"] for r in srows]
        n = len(pnls)
        mean_raw = _mean(pnls)
        var_raw = _sample_var(pnls)
        avg_notional = _mean(notionals) if notionals else 0.0
        prior_var = (VOL_PRIOR_FRAC * avg_notional) ** 2 if avg_notional > 0 else \
            (VOL_PRIOR_FRAC * PRIOR_BANKROLL_FRAC * bankroll) ** 2
        mean_shrunk = mean_raw * n / (n + K_MEAN)
        var_shrunk = (n * var_raw + K_VAR * prior_var) / (n + K_VAR)
        sharpe = mean_shrunk / (var_shrunk ** 0.5) if var_shrunk > 0 else 0.0
        out[name] = {
            "n_days": n, "mean_raw": mean_raw, "var_raw": var_raw,
            "avg_notional": avg_notional, "mean_shrunk": mean_shrunk, "var_shrunk": var_shrunk,
            "sharpe": sharpe, "is_live": srows[0]["is_live"] if srows else False,
            "dates": {r["date"]: r["pnl_usd"] for r in srows},
        }
    return out


def pairwise_rho(a: str, stats_a: dict, b: str, stats_b: dict) -> tuple[float, str]:
    """(rho, provenance) -- 'sample' if computed from overlapping days, else 'prior'."""
    common = sorted(set(stats_a["dates"]) & set(stats_b["dates"]))
    if len(common) >= MIN_OVERLAP_DAYS:
        xs = [stats_a["dates"][d] for d in common]
        ys = [stats_b["dates"][d] for d in common]
        vx, vy = _sample_var(xs), _sample_var(ys)
        if vx > 0 and vy > 0:
            mx, my = _mean(xs), _mean(ys)
            cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)
            rho = cov / (vx ** 0.5 * vy ** 0.5)
            return max(-1.0, min(1.0, rho)), f"sample (n={len(common)})"
    both_crypto = a.startswith("crypto_mm_") and b.startswith("crypto_mm_")
    return (RHO_CRYPTO_PRIOR if both_crypto else RHO_DEFAULT_PRIOR), "prior (thin/no overlap)"


def build_cov(sleeves: list[str], stats: dict) -> tuple[np.ndarray, np.ndarray, dict]:
    n = len(sleeves)
    mu = np.array([stats[s]["mean_shrunk"] for s in sleeves])
    sigma = np.array([stats[s]["var_shrunk"] ** 0.5 for s in sleeves])
    cov = np.zeros((n, n))
    rho_meta = {}
    for i in range(n):
        cov[i, i] = sigma[i] ** 2
        for j in range(i + 1, n):
            rho, prov = pairwise_rho(sleeves[i], stats[sleeves[i]], sleeves[j], stats[sleeves[j]])
            cov[i, j] = cov[j, i] = rho * sigma[i] * sigma[j]
            rho_meta[(sleeves[i], sleeves[j])] = (rho, prov)
    return mu, cov, rho_meta


def kelly_weights(mu: np.ndarray, cov: np.ndarray, bankroll: float) -> np.ndarray:
    """f* = Sigma^-1 mu in bankroll-fraction units; ridge-regularized; negatives clipped."""
    n = len(mu)
    if n == 0:
        return np.zeros(0)
    mu_frac = mu / bankroll
    cov_frac = cov / (bankroll ** 2)
    trace = np.trace(cov_frac)
    ridge = 1e-6 * (trace / n if trace > 0 else 1.0)
    cov_reg = cov_frac + ridge * np.eye(n)
    try:
        f_raw = np.linalg.solve(cov_reg, mu_frac)
    except np.linalg.LinAlgError:
        f_raw = np.linalg.pinv(cov_reg) @ mu_frac
    return np.clip(f_raw, 0.0, None)


def apply_constraints(f_quarter: np.ndarray) -> np.ndarray:
    f = np.clip(f_quarter, 0.0, PER_SLEEVE_CAP_FRAC)
    total = f.sum()
    if total > TOTAL_CAP_FRAC:
        f = f * (TOTAL_CAP_FRAC / total)
    return f


def allocate(bankroll: float) -> dict:
    rows = sleeve_ledger.load_all()
    stats = sleeve_stats(rows, bankroll)
    sleeves = sorted(stats)
    if not sleeves:
        return {"bankroll": bankroll, "sleeves": [], "rows": [], "thin_data": True}

    mu, cov, rho_meta = build_cov(sleeves, stats)
    f_raw = kelly_weights(mu, cov, bankroll)
    f_quarter = f_raw * QUARTER_KELLY
    f_final = apply_constraints(f_quarter)

    total_days = sum(stats[s]["n_days"] for s in sleeves)
    thin_data = total_days < 30 or max((stats[s]["n_days"] for s in sleeves), default=0) < 14

    out_rows = []
    for i, s in enumerate(sleeves):
        st = stats[s]
        alloc_usd = float(f_final[i]) * bankroll
        is_live = st["is_live"]
        row = {
            "sleeve": s, "is_live": is_live, "n_days": st["n_days"],
            "mean_per_day": st["mean_shrunk"], "vol_per_day": st["var_shrunk"] ** 0.5,
            "sharpe": st["sharpe"], "kelly_raw_frac": float(f_raw[i]),
            "kelly_quarter_frac": float(f_quarter[i]), "final_frac": float(f_final[i]),
            "alloc_usd": alloc_usd if is_live else 0.0,
            "would_be_usd": alloc_usd,
        }
        out_rows.append(row)

    return {"bankroll": bankroll, "sleeves": out_rows, "rho_meta": rho_meta,
            "thin_data": thin_data, "total_days": total_days}


def crypto_notional_check(alloc_result: dict) -> list[dict]:
    """For each live crypto_mm_<asset> sleeve, implied --max-notional/--loss-limit vs deployed."""
    out = []
    for row in alloc_result.get("sleeves", []):
        if not row["sleeve"].startswith("crypto_mm_") or not row["is_live"]:
            continue
        implied_notional = row["alloc_usd"]
        implied_loss_limit = implied_notional * (DEPLOYED_LOSS_LIMIT / DEPLOYED_MAX_NOTIONAL)
        divergence = (implied_notional / DEPLOYED_MAX_NOTIONAL) if DEPLOYED_MAX_NOTIONAL else float("inf")
        flag = divergence >= REBALANCE_FLAG_MULT or divergence <= 1.0 / REBALANCE_FLAG_MULT
        out.append({
            "sleeve": row["sleeve"], "implied_max_notional": implied_notional,
            "implied_loss_limit": implied_loss_limit,
            "deployed_max_notional": DEPLOYED_MAX_NOTIONAL, "deployed_loss_limit": DEPLOYED_LOSS_LIMIT,
            "divergence_x": divergence, "flag": "REBALANCE-SUGGESTED" if flag else "in-range",
        })
    return out


def _print_report(res: dict) -> None:
    bankroll = res["bankroll"]
    print(f"portfolio_allocator.py -- ALERT-ONLY, never auto-applies. bankroll=${bankroll:.2f}")
    if not res["sleeves"]:
        print("no sleeve data at all (cold start) -- nothing to allocate. "
              "Run sleeve_ledger.py once real settlements exist.")
        return
    if res["thin_data"]:
        print("NOTE: data is too thin for anything but priors right now (max sleeve history "
              f"< 14 days, or < 30 sleeve-days total observed = {res['total_days']}). Every "
              "mean/vol/correlation below leans heavily on the documented priors, not signal. "
              "Treat allocations as a structural sanity-check, not a real edge estimate.")

    print(f"\n{'sleeve':<20}{'live':>6}{'n_days':>8}{'mean/day':>11}{'vol/day':>10}"
          f"{'sharpe':>8}{'kelly(1/4)':>12}{'alloc_usd':>11}{'would_be':>11}")
    for r in res["sleeves"]:
        print(f"{r['sleeve']:<20}{'Y' if r['is_live'] else 'N':>6}{r['n_days']:>8}"
              f"{r['mean_per_day']:>11.4f}{r['vol_per_day']:>10.4f}{r['sharpe']:>8.3f}"
              f"{r['kelly_quarter_frac']:>12.4f}{r['alloc_usd']:>11.4f}{r['would_be_usd']:>11.4f}")
    total_live_alloc = sum(r["alloc_usd"] for r in res["sleeves"])
    total_would_be = sum(r["would_be_usd"] for r in res["sleeves"])
    print(f"{'TOTAL':<20}{'':>6}{'':>8}{'':>11}{'':>10}{'':>8}{'':>12}"
          f"{total_live_alloc:>11.4f}{total_would_be:>11.4f}")
    print(f"(caps: <={PER_SLEEVE_CAP_FRAC:.0%} bankroll/sleeve, <={TOTAL_CAP_FRAC:.0%} bankroll "
          f"total deployed, quarter-Kelly)")

    checks = crypto_notional_check(res)
    if checks:
        print("\n== live crypto sleeve: implied per-window limits vs deployed ==")
        for c in checks:
            print(f"  {c['sleeve']}: implied --max-notional={c['implied_max_notional']:.2f} "
                  f"(deployed {c['deployed_max_notional']:.2f}) | implied --loss-limit="
                  f"{c['implied_loss_limit']:.2f} (deployed {c['deployed_loss_limit']:.2f}) | "
                  f"divergence={c['divergence_x']:.2f}x -> {c['flag']}")
        print("  (alert-only -- this NEVER writes to live.yml or any trader flag; a human decides.)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bankroll", type=float, default=50.0)
    args = ap.parse_args()
    res = allocate(args.bankroll)
    _print_report(res)


if __name__ == "__main__":
    main()
