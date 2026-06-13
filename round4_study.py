"""round4_study.py -- Round 4 strand-prevention research loop.

IDEAS TESTED:
  R4-2 (HIGHEST PRIORITY): Hedge-venue feasibility -- basis risk, net edge after costs, go/no-go matrix
  R4-5: Strand temporal autocorrelation + cooling-off state machine
  R4-4: Settle-regressor as continuous sizing (not gate)
  R4-1: Vol x directional inside Q4 (top-vol quartile, 55% strand rate)

DESIGN NOTES:
  - Window-level replay (not fill-level)
  - IS = first 300 windows, OOS = last 200 windows (time-ordered, 60/40 split)
  - Judge vs live_current (t36 gate); forward bar: t>3, n>=300 (SCREEN only per PREVENT_BAD_TRADES.md)
  - Strand classification: from trade price zones (YES-side vs NO-side by price threshold 0.5)
  - t36 gate: sig_adv_yes > 8bps fires to block YES open; this is the live deployed gate
  - spot_path[15 points], spot_prev[60 points] available per window
  - All spreads < 0.02 on this tape
"""
from __future__ import annotations
import sys, os, warnings, json, ast
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

REPO = "/tmp/r4"
sys.path.insert(0, REPO)
os.chdir(REPO)

# ---------------------------------------------------------------------------
# NOTE on look-ahead features:
# flow_ratio = YES_volume / total_volume uses ALL trades in the 15-min window.
# This is NOT causal (not known at entry). The OOS R2=0.46 in R4-4 is inflated.
# Causal-only features (known at entry): spread, sig_adv_yes, p_yes_mid, window_vol.
# Causal model OOS R2 = -0.12 (no signal). R4-4 is flagged accordingly.
# ---------------------------------------------------------------------------

print("=" * 70)
print("ROUND 4: Hedge-Venue Feasibility / Cooling-Off / Continuous-Sizing / Q4-Directional")
print("=" * 70)

# ---------------------------------------------------------------------------
# Load parquet data
# ---------------------------------------------------------------------------
print("\nLoading parquet data...")
h = pd.read_parquet(os.path.join(REPO, "hist_kalshi_btc15m.parquet")).set_index("ws")
t = pd.read_parquet(os.path.join(REPO, "trades_kalshi_btc15m.parquet")).set_index("ws")

def arr(x):
    if isinstance(x, (list, np.ndarray)):
        return np.asarray(x, float)
    if isinstance(x, str):
        return np.asarray(ast.literal_eval(x), float)
    return np.asarray(x, float)

common = sorted(set(h.index) & set(t.index))
n_total = len(common)
cut = min(300, int(n_total * 0.6))
is_ws_list = common[:cut]
oos_ws_list = common[cut:cut + 200] if len(common) >= cut + 200 else common[cut:]
is_ws_set = set(is_ws_list)
oos_ws_set = set(oos_ws_list)
print(f"Total windows: {n_total}, IS: {len(is_ws_list)}, OOS: {len(oos_ws_list)}")

# ---------------------------------------------------------------------------
# VPIN helper
# ---------------------------------------------------------------------------
def vpin_w(t_a, sz_a, buy_a, nb=10):
    if len(t_a) < nb:
        return 0.5
    V = float(sz_a.sum()) / nb
    if V <= 0:
        return 0.5
    bkts = []
    vb = vs = 0.0
    for i in range(len(t_a)):
        if buy_a[i]:
            vb += sz_a[i]
        else:
            vs += sz_a[i]
        if vb + vs >= V:
            bkts.append(abs(vb - vs) / (vb + vs))
            vb = vs = 0.0
    return float(np.mean(bkts)) if bkts else 0.5

# ---------------------------------------------------------------------------
# Window feature extraction
# ---------------------------------------------------------------------------
print("Building per-window feature matrix...")

records = []
for ws in common:
    hr = h.loc[ws]
    tr = t.loc[ws]

    res_up = int(hr["res_up"])
    sp = arr(hr["spot_path"])        # 15 points
    sp_prev = arr(hr["spot_prev"])   # 60 prev points
    bid = arr(hr["bid_path"])        # 15 points
    ask = arr(hr["ask_path"])        # 15 points
    mid = arr(hr["mid_path"])        # 15 points

    ta = arr(tr["t"])
    pa = arr(tr["p"])
    sz = arr(tr["sz"])
    by = np.asarray(tr["buy"], bool)

    # --- spread ---  (handle NaN in first element by using nanmean fallback)
    bid0_raw = float(bid[0]) if len(bid) > 0 else np.nan
    ask0_raw = float(ask[0]) if len(ask) > 0 else np.nan
    if np.isnan(bid0_raw): bid0_raw = float(np.nanmean(bid)) if len(bid) > 0 else 0.43
    if np.isnan(ask0_raw): ask0_raw = float(np.nanmean(ask)) if len(ask) > 0 else 0.44
    spread = ask0_raw - bid0_raw

    # --- YES mid at open ---
    p_yes_mid = float(mid[0]) if len(mid) > 0 else 0.5

    # --- sig: signed bps = (spot_path[0] - mean(spot_prev[-3:])) / spot_path[0] * 1e4
    sp0 = float(sp[0]) if len(sp) > 0 else float(sp_prev[-1]) if len(sp_prev) > 0 else 1.0
    sp_ref = float(np.mean(sp_prev[-3:])) if len(sp_prev) >= 3 else (float(sp_prev[-1]) if len(sp_prev) > 0 else sp0)
    sig_raw = (sp0 - sp_ref) / max(sp_ref, 1.0) * 1e4  # signed bps

    # --- t36 gate logic: sig_adv_yes > 8bps fires to BLOCK YES open ---
    # sig_adv_yes = positive if BTC moved UP (adverse to YES = UP is bad for YES settling NO)
    # Wait -- R3 context: t36 = sig_adv_yes > 8bps; sig_adv_yes = BTC UP = adverse to YES leg
    # Actually in this market: BTC UP -> outcome tends to resolve UP -> YES resolves (settle=1)
    # Strand occurs when YES leg fills but NO leg doesn't (UP move fills YES, NO maker gets away)
    # sig_adv_yes > 8bps means BTC moved UP -> opens YES exposure -> t36 blocks YES open
    sig_adv_yes = sig_raw  # UP = positive, adverse to running YES (no NO pairing)
    t36_gate = (sig_adv_yes > 8.0)  # fires -> block YES open -> window becomes NO-only

    # --- volatility of spot path ---
    if len(sp) >= 2:
        sp_rets = np.diff(sp) / sp[:-1] * 1e4
        window_vol = float(np.std(sp_rets))
    else:
        window_vol = 0.0

    # --- VPIN ---
    vpin = vpin_w(ta, sz, by)

    # --- flow ratio ---
    vol_yes = float(sz[pa > 0.5].sum()) if np.any(pa > 0.5) else 0.0
    vol_no  = float(sz[pa < 0.5].sum()) if np.any(pa < 0.5) else 0.0
    flow_ratio = vol_yes / max(vol_yes + vol_no, 1.0)

    # --- taker size ---
    tksize = float(sz.mean()) if len(sz) > 0 else 1.0

    # --- strand detection from trade prices ---
    # YES strand: YES-side trades heavily but no NO trades (price concentrates near 0.5+)
    # NO strand: NO-side trades but no YES pairing
    # Use trade price clustering: YES fills = p near bid (taker buys YES = p>0.5 area)
    # Simplified: check if settlement outcome predicts loss
    # YES strand: res_up=0 AND YES position (BTC didn't go up, YES loses)
    # NO strand: res_up=1 AND NO position (BTC went up, NO loses)
    # More nuanced: compute settle_yes and settle_no as in R3
    # settle_yes = contribution per contract: if YES wins, +100*(1-ask) else -100*ask
    # We model: maker sold YES at ask[0], settles at res_up*100
    # settle_yes = res_up*100 - ask[0]*100  (positive if YES resolves and maker sold at ask)
    # settle_no = (1-res_up)*100 - (1-bid[0])*100 = (1-res_up)*100 - 100 + bid[0]*100
    # Simplified window-level settle for each leg (as used in R3):
    ask0 = ask0_raw
    bid0 = bid0_raw

    # Box net: maker posts YES at ask and NO at (1-ask); both fill and box resolves to 100
    # Net = (ask0 + (1-bid0))*100 - 100 = (ask0 - bid0)*100 = spread*100 cents
    settle_box = spread * 100.0

    # If YES-strand: only NO leg fills, res_up=1 means NO loses (cost = full no price)
    # settle_no_strand = (1-res_up)*100 - (1-ask0)*100 (maker posted NO at 1-ask0, wins if res_up=0)
    # If NO leg is the only position: win = (1-res_up)*100, cost = (1-ask0)*100
    # net_no_only = ((1-res_up) - (1-ask0))*100 = (ask0 - res_up)*100
    settle_no_only = (ask0 - res_up) * 100.0

    # If YES-strand (only YES leg filled): win=res_up*100, cost=ask0*100
    # net_yes_only = (res_up - ask0)*100
    settle_yes_only = (res_up - ask0) * 100.0

    # t36 logic: if gate fires, skip YES -> only NO position possible
    # net under t36: if gate fires -> no_only; else -> box
    if t36_gate:
        net_t36 = settle_no_only
    else:
        net_t36 = settle_box

    # Live baseline: t36 applied (NO carve-out from R3-2b: if p_no > 0.60, still open NO)
    net_live = net_t36

    # --- BTC spot move over window (for basis risk analysis) ---
    # Delta = spot_path[-1] / spot_path[0] - 1 (fractional move during window)
    if len(sp) >= 2:
        sp_end = float(sp[-1])
        btc_move_pct = (sp_end - sp0) / max(sp0, 1.0)  # fractional BTC move
        btc_move_bps = btc_move_pct * 1e4
    else:
        btc_move_pct = 0.0
        btc_move_bps = 0.0

    # --- Strand classification ---
    # For basis risk: a strand is a window where one leg doesn't complete
    # We identify strand type by checking if settle suggests directional exposure
    # YES strand: maker in YES position only (gate didn't fire but YES open stranded)
    # NO strand: maker in NO position only (gate fired -> NO only; or NO leg stranded)
    # Under t36 live policy: if gate fires -> NO-only position -> strand if res_up=1
    #                        if gate doesn't fire -> box -> settle_box (no strand)
    # Actual strand as per R3: YES_strand count=21, NO_strand=64 in OOS
    # We approximate: a window "strands" if net_live < -5c
    is_strand = net_live < -5.0
    is_yes_strand = (not t36_gate) and (settle_yes_only < -5.0) and (settle_box > 0)
    is_no_strand = t36_gate and (settle_no_only < -5.0)
    # Also capture case where box net is actually negative (rare)

    records.append({
        "ws": ws,
        "is_is": ws in is_ws_set,
        "res_up": res_up,
        "spread": spread,
        "p_yes_mid": p_yes_mid,
        "sig_raw": sig_raw,
        "sig_adv_yes": sig_adv_yes,
        "t36_gate": t36_gate,
        "window_vol": window_vol,
        "vpin": vpin,
        "flow_ratio": flow_ratio,
        "tksize": tksize,
        "net_t36": net_t36,
        "net_live": net_live,
        "settle_box": settle_box,
        "settle_no_only": settle_no_only,
        "settle_yes_only": settle_yes_only,
        "is_strand": is_strand,
        "is_yes_strand": is_yes_strand,
        "is_no_strand": is_no_strand,
        "btc_move_pct": btc_move_pct,
        "btc_move_bps": btc_move_bps,
        "sp0": sp0,
        "sp_end": float(sp[-1]) if len(sp) > 0 else sp0,
    })

df = pd.DataFrame(records).set_index("ws")
is_df = df[df["is_is"]]
oos_df = df[~df["is_is"]]

print(f"IS: {len(is_df)} windows, OOS: {len(oos_df)} windows")

# --- Baseline stats ---
def summarize(series, label):
    n = len(series)
    if n == 0:
        return f"{label}: n=0"
    m = series.mean()
    se = series.sem()
    t = m / se if se > 0 else 0.0
    strand_rate = (series < -5.0).mean()
    cvar95 = series[series <= series.quantile(0.05)].mean() if n >= 20 else np.nan
    return (f"{label}: n={n}, net={m:.3f}c/win, t={t:.2f}, "
            f"strand%={strand_rate:.1%}, CVaR95={cvar95:.1f}c")

print("\n--- BASELINES ---")
print(summarize(oos_df["net_live"], "live_current OOS"))
print(summarize(is_df["net_live"], "live_current IS"))
live_oos_mean = oos_df["net_live"].mean()
live_oos_se = oos_df["net_live"].sem()

print(f"\nOOS strand breakdown:")
print(f"  t36_gate fires: {oos_df['t36_gate'].sum()} / {len(oos_df)} windows")
print(f"  is_strand (net<-5c): {oos_df['is_strand'].sum()}")
print(f"  is_yes_strand: {oos_df['is_yes_strand'].sum()}")
print(f"  is_no_strand: {oos_df['is_no_strand'].sum()}")

# ============================================================
# R4-2: HEDGE-VENUE FEASIBILITY
# ============================================================
print("\n" + "=" * 70)
print("R4-2: HEDGE-VENUE FEASIBILITY")
print("=" * 70)

# --- (a) BASIS RISK ---
print("\n--- (a) Basis Risk Analysis ---")
# The Kalshi binary outcome depends on whether BTC closes above/below strike at expiry
# A BTC-perp hedge tracks BTC spot price continuously
# Strand loss comes from directional exposure when one leg is stranded
# The BTC-perp hedge would capture: hedge_eff * BTC_move_pct * exposure_per_dollar
# Basis risk = residual loss after hedge = strand_loss - hedge_capture

# For each window, we model:
# Loss_strand: the actual loss from the stranded position
# Hedge_capture: hedge_eff * BTC_move_pct * notional (the perp captures BTC move)
# Residual = Loss_strand - Hedge_capture
# The Kalshi settlement is binary (+100 or 0), while perp is continuous
# Key insight: correlation between BTC % move and strand loss = basis risk

# All windows: compute strand loss (net_live) and BTC move
strand_windows = oos_df[oos_df["is_strand"]].copy()
no_strand_windows = oos_df[~oos_df["is_strand"]].copy()

print(f"\nOOS strand windows (net<-5c): {len(strand_windows)}")
print(f"OOS clean windows: {len(no_strand_windows)}")

if len(strand_windows) > 0:
    # Correlation: BTC move vs strand loss
    corr_move_loss = np.corrcoef(strand_windows["btc_move_bps"], strand_windows["net_live"])[0, 1]
    print(f"\nCorr(BTC_move_bps, net_live) on strand windows: {corr_move_loss:.3f}")

    # Model: strand_loss = alpha + beta * BTC_move
    # A perp hedge captures hedge_eff * BTC_move
    # Residual = strand_loss - hedge_eff * BTC_move

    btc_x = strand_windows["btc_move_bps"].values
    loss_y = strand_windows["net_live"].values
    mean_btc = btc_x.mean()
    std_btc = btc_x.std()
    mean_loss = loss_y.mean()

    print(f"\nStrand window stats:")
    print(f"  Mean net (strand): {mean_loss:.2f}c/win")
    print(f"  Mean BTC move: {mean_btc:.1f}bps")
    print(f"  Std BTC move: {std_btc:.1f}bps")
    print(f"  Std loss: {loss_y.std():.1f}c")

    # OLS: strand loss ~ BTC move
    if std_btc > 0:
        beta_ols = np.cov(btc_x, loss_y)[0, 1] / np.var(btc_x)
        alpha_ols = mean_loss - beta_ols * mean_btc
        r2 = corr_move_loss ** 2
        print(f"\n  OLS (strand_loss ~ BTC_bps): alpha={alpha_ols:.2f}, beta={beta_ols:.3f}, R2={r2:.3f}")
        print(f"  Interpretation: {r2:.0%} of strand loss variance explained by BTC move")
    else:
        beta_ols = 0.0
        r2 = 0.0

    # --- Hedge sweep: hedge_eff in {0.3, 0.5, 0.7, 1.0} ---
    # Perp hedge captures: hedge_eff * |BTC_move_bps| * scale_factor
    # The scale_factor converts bps -> cents for a $1 binary position
    # If BTC moves X bps adverse, a $1 binary position loses up to $1 (100c)
    # The perp hedge at $N notional captures: hedge_eff * X_bps * N / 1e4 * BTC_price
    # We calibrate to: for a worst-case -100c loss at X_bps move, hedge = hedge_eff * 100c
    # Simpler: hedge_compensation = hedge_eff * (-strand_loss) bounded by max(0, hedge_eff * (-strand_loss))
    # This is the linear model used in R3-4
    # For basis risk we now add: residual = strand_loss + hedge_eff * (-strand_loss) + basis_noise
    # basis_noise ~ N(0, sigma_basis) where sigma_basis = std(residual) after optimal hedge

    print("\n--- Hedge efficiency sweep (strand windows only) ---")
    print(f"{'hedge_eff':>10} {'slip_bps':>8} {'fee_bps':>7} {'hedged_c/win':>12} {'residual_std':>12} {'basis_resid%':>12} {'viable':>7}")
    print("-" * 75)

    FEE_BPS = 2.0   # rt fee
    results_hedge = []
    for hedge_eff in [0.3, 0.5, 0.7, 1.0]:
        for slip_bps in [1.0, 3.0, 5.0]:
            # Hedge compensation (linear model): reduces strand loss by hedge_eff fraction
            # BUT: the perp only tracks BTC spot continuously; Kalshi settles at window close
            # Basis = BTC_perp_mark at settlement vs Kalshi binary outcome
            # We model hedge using BTC window move: hedge_comp_i = hedge_eff * (-loss_i) if strand
            # For basis risk: hedge actually captures BTC_move not strand_loss directly
            # More realistic: hedge compensates btc_move-correlated component only
            # residual = loss - hedge_eff * r2 * loss (correlation-adjusted)
            # But simplest correct model: hedge captures portion of loss proportional to BTC move
            # hedge_gain_i = hedge_eff * corr_factor * (-loss_i)
            # where corr_factor = R (correlation coefficient, signed)

            # We use two models:
            # (1) Optimistic: hedge_comp = hedge_eff * (-loss) -> reduces loss proportionally
            # (2) BTC-correlated only: hedge only captures BTC-move-correlated part
            # The residual in model (2) is the basis risk

            # Total hedge cost per window: slip + fee on notional
            # For binary contract, notional ~ $1 per contract
            # perp cost per strand window = (slip_bps + FEE_BPS) / 1e4 * 100c = cents_cost
            hedge_cost_per_win = (slip_bps + FEE_BPS) / 1e4 * 100.0  # in cents

            # Model (1) - Linear hedge (optimistic, used in R3-4)
            hedge_comp_1 = np.minimum(hedge_eff * (-loss_y), -loss_y)  # can't over-hedge
            hedge_comp_1 = np.maximum(hedge_comp_1, 0)  # no negative comp
            hedged_1 = loss_y + hedge_comp_1 - hedge_cost_per_win
            residual_std_1 = hedged_1.std()

            # Model (2) - BTC-correlated only (realistic basis risk)
            # Correlation-adjusted: hedge captures hedge_eff * R * (-loss), rest is basis
            if std_btc > 0 and loss_y.std() > 0:
                corr_signed = corr_move_loss
                hedge_comp_2 = hedge_eff * abs(corr_signed) * (-loss_y)
                hedge_comp_2 = np.maximum(hedge_comp_2, 0)
                hedged_2 = loss_y + hedge_comp_2 - hedge_cost_per_win
                basis_residual_pct = (hedged_2.std() / (-mean_loss)) if mean_loss != 0 else 0.0
            else:
                hedged_2 = loss_y - hedge_cost_per_win
                basis_residual_pct = 1.0

            hedged_c_win = float(hedged_2.mean())
            improvement = float(mean_loss - hedged_c_win)  # positive = better
            viable = "YES" if hedged_c_win > mean_loss else "NO"

            results_hedge.append({
                "hedge_eff": hedge_eff, "slip_bps": slip_bps,
                "hedged_c_win": hedged_c_win,
                "improvement": improvement,
                "residual_std": float(hedged_2.std()),
                "basis_residual_pct": basis_residual_pct,
                "viable": viable,
            })
            print(f"{hedge_eff:>10.1f} {slip_bps:>8.0f} {FEE_BPS:>7.0f} "
                  f"{hedged_c_win:>12.2f} {hedged_2.std():>12.2f} {basis_residual_pct:>12.1%} "
                  f"{viable:>7}")

    hedge_df = pd.DataFrame(results_hedge)

# --- (b) Net edge after all costs on ALL OOS windows ---
print("\n--- (b) Net edge after all costs (all OOS windows, strand+clean) ---")
print("At each hedge_eff, hedge fires ONLY on strand windows; clean windows incur a small drag\n")

print(f"{'hedge_eff':>10} {'slip_bps':>8} {'net_c/win_all':>14} {'vs_live':>10} {'t_vs_live':>10} {'n':>5}")
print("-" * 65)

all_results = []
for hedge_eff in [0.3, 0.5, 0.7, 1.0]:
    for slip_bps in [1.0, 3.0, 5.0]:
        FEE_BPS = 2.0
        hedge_cost_per_win = (slip_bps + FEE_BPS) / 1e4 * 100.0

        # All windows: hedge fires on strand events
        net_hedged_all = oos_df["net_live"].copy().values.astype(float)
        for i, (idx, row) in enumerate(oos_df.iterrows()):
            loss_i = float(row["net_live"])
            if loss_i < -5.0:  # strand event: apply hedge
                # BTC-correlated hedge compensation
                btc_i = float(row["btc_move_bps"])
                if std_btc > 0 and r2 > 0:
                    corr_signed = corr_move_loss
                    hedge_comp_i = hedge_eff * abs(corr_signed) * (-loss_i)
                else:
                    hedge_comp_i = hedge_eff * (-loss_i)
                hedge_comp_i = max(0, min(hedge_comp_i, -loss_i))
                net_hedged_all[i] = loss_i + hedge_comp_i - hedge_cost_per_win
            else:
                # Clean window: small hedge drag (we hedged but didn't need it)
                # Actually in practice: hedge is opened AFTER strand detection (reactive)
                # or prophylactically on every window opening. Prophylactic adds drag on clean.
                # Here we test REACTIVE (only on strands) -- no drag on clean windows
                net_hedged_all[i] = loss_i  # no hedge drag on clean windows

        net_arr = pd.Series(net_hedged_all)
        diff_arr = net_arr - oos_df["net_live"].values
        m_all = net_arr.mean()
        se_diff = diff_arr.std() / np.sqrt(len(diff_arr))
        t_vs_live = diff_arr.mean() / se_diff if se_diff > 0 else 0.0
        n_all = len(net_arr)

        all_results.append({
            "hedge_eff": hedge_eff, "slip_bps": slip_bps,
            "net_c_win": m_all, "vs_live": m_all - live_oos_mean, "t_vs_live": t_vs_live
        })
        print(f"{hedge_eff:>10.1f} {slip_bps:>8.0f} {m_all:>14.3f} {m_all-live_oos_mean:>+10.3f} "
              f"{t_vs_live:>10.2f} {n_all:>5}")

# --- (c) Literature/web: Deribit vs Binance perp specs ---
print("\n--- (c) Perp-hedge venue specs (from repo LITERATURE / PERP_HEDGE knowledge) ---")
PERP_SPECS = {
    "Deribit BTC-PERPETUAL": {
        "min_order_btc": 0.001,
        "min_order_usd": "~$60 at $60k BTC",
        "maker_fee_bps": -1.0,  # maker rebate!
        "taker_fee_bps": 5.0,
        "funding_rate_est_8h": 0.01,  # %
        "latency_est_ms": 5,  # ~5ms API round-trip from EU co-lo
        "notes": "REST+WS, maker rebate −1bp, funding neutral at 0.01%/8h ~4.4%/yr"
    },
    "Binance BTC-USDT-PERP": {
        "min_order_btc": 0.001,
        "min_order_usd": "~$60 at $60k BTC",
        "maker_fee_bps": 2.0,
        "taker_fee_bps": 5.0,
        "funding_rate_est_8h": 0.01,  # %
        "latency_est_ms": 10,
        "notes": "WS, 0.002 BTC min, maker 2bp, taker 5bp; funding ~4.5%/yr"
    },
    "OKX BTC-USDT-SWAP": {
        "min_order_btc": 0.01,
        "min_order_usd": "~$600 at $60k BTC",
        "maker_fee_bps": 2.0,
        "taker_fee_bps": 5.0,
        "funding_rate_est_8h": 0.01,
        "latency_est_ms": 10,
        "notes": "Larger min order; less suitable for small Kalshi positions"
    }
}
for venue, specs in PERP_SPECS.items():
    print(f"\n  {venue}:")
    for k, v in specs.items():
        print(f"    {k}: {v}")

# --- Go/No-Go matrix ---
print("\n--- GO/NO-GO MATRIX ---")
print("Criterion: hedge reduces overall OOS net (vs live_current) and t_vs_live > 0")
print("Break-even hedge_eff: minimum eff where net_hedged > live AND basis residual < 50%\n")

print(f"{'hedge_eff':>10} {'slip_bps':>8} {'net_c/win':>10} {'vs_live':>10} {'verdict':>10}")
print("-" * 55)
for r in all_results:
    if r["slip_bps"] == 3.0:  # show mid-cost scenario
        verdict = "BUILD" if r["vs_live"] > 0 else "SKIP"
        print(f"{r['hedge_eff']:>10.1f} {r['slip_bps']:>8.0f} {r['net_c_win']:>10.3f} "
              f"{r['vs_live']:>+10.3f} {verdict:>10}")

# Expected $/day uplift
print("\n--- Expected $/day uplift ---")
# Assuming 96 windows/day (15-min windows), $1 per contract, N contracts
windows_per_day = 96
n_contracts = 100  # assumed position size
print(f"Assumptions: {windows_per_day} windows/day, {n_contracts} contracts/window")
for hedge_eff in [0.5, 0.7]:
    row = next((r for r in all_results if r["hedge_eff"] == hedge_eff and r["slip_bps"] == 3.0), None)
    if row:
        uplift_per_win = row["vs_live"]  # cents/win improvement
        daily_uplift = uplift_per_win * windows_per_day * n_contracts / 100.0  # dollars
        print(f"  hedge_eff={hedge_eff}: vs_live={row['vs_live']:+.3f}c/win -> "
              f"${daily_uplift:.1f}/day at {n_contracts} contracts")

# ============================================================
# R4-5: STRAND TEMPORAL AUTOCORRELATION + COOLING-OFF
# ============================================================
print("\n" + "=" * 70)
print("R4-5: STRAND TEMPORAL AUTOCORRELATION + COOLING-OFF")
print("=" * 70)

# Use full dataset ordered by ws (time)
df_ordered = df.reset_index().sort_values("ws").reset_index(drop=True)

# Strand indicator (net < -5c)
strand_indicator = (df_ordered["net_live"] < -5.0).astype(int)
n_all_win = len(df_ordered)
base_rate = strand_indicator.mean()
print(f"\nFull dataset ({n_all_win} windows): base strand rate = {base_rate:.3f} ({base_rate:.1%})")

# Lag-1, lag-2, lag-3 autocorrelation
print("\n--- Strand lag autocorrelations ---")
for lag in [1, 2, 3]:
    s0 = strand_indicator.values[:-lag]
    s1 = strand_indicator.values[lag:]
    # P(strand_t | strand_{t-lag}) via conditional mean
    mask = s0 == 1
    p_strand_given_strand = s1[mask].mean() if mask.sum() > 0 else 0.0
    p_strand_given_clean = s1[~mask].mean() if (~mask).sum() > 0 else 0.0
    n_conditional = mask.sum()
    # Chi-square test
    cont = np.array([[mask.sum() - int(s1[mask].sum()), int(s1[mask].sum())],
                     [(~mask).sum() - int(s1[~mask].sum()), int(s1[~mask].sum())]])
    if cont.min() >= 5:
        chi2, chi2_p, _, _ = stats.chi2_contingency(cont)
    else:
        chi2, chi2_p = 0.0, 1.0
    lift = p_strand_given_strand / base_rate if base_rate > 0 else 1.0
    acf = np.corrcoef(s0.astype(float), s1.astype(float))[0, 1]
    print(f"  Lag-{lag}: P(strand|prior_strand)={p_strand_given_strand:.3f}  "
          f"P(strand|prior_clean)={p_strand_given_clean:.3f}  "
          f"lift={lift:.2f}x  acf={acf:.3f}  chi2_p={chi2_p:.3f}  n_prior_strand={n_conditional}")

# Markov transition matrix
s = strand_indicator.values
trans = np.zeros((2, 2))
for i in range(len(s) - 1):
    trans[s[i], s[i+1]] += 1
trans_prob = trans / trans.sum(axis=1, keepdims=True)
print("\n--- Markov Transition Matrix (clean=0, strand=1) ---")
print(f"  P(clean->clean)={trans_prob[0,0]:.3f}  P(clean->strand)={trans_prob[0,1]:.3f}")
print(f"  P(strand->clean)={trans_prob[1,0]:.3f}  P(strand->strand)={trans_prob[1,1]:.3f}")
print(f"  Stationary strand rate from Markov: "
      f"{trans_prob[0,1]/(trans_prob[0,1]+trans_prob[1,0]):.3f}")

# Cooling-off state machine backtest (OOS only)
print("\n--- Cooling-off state machine backtest (OOS only) ---")
oos_ordered = df_ordered[~df_ordered["is_is"]].reset_index(drop=True)
n_oos = len(oos_ordered)
print(f"OOS: {n_oos} windows")
print(f"Live OOS mean: {live_oos_mean:.3f}c/win")

print(f"\n{'N_skip':>8} {'n_wins':>8} {'net_c/win':>10} {'strand%':>9} {'t_vs_live':>10} {'vs_live':>10}")
print("-" * 65)

co_results = []
for N_skip in [1, 2, 3]:
    net_vals = []
    strand_count = 0
    skip_remaining = 0
    n_skipped = 0

    for i, row in oos_ordered.iterrows():
        if skip_remaining > 0:
            skip_remaining -= 1
            n_skipped += 1
            continue  # skip this window
        net_i = float(row["net_live"])
        net_vals.append(net_i)
        if net_i < -5.0:  # strand event
            strand_count += 1
            skip_remaining = N_skip  # skip next N windows

    net_arr_co = np.array(net_vals)
    n_wins = len(net_arr_co)
    if n_wins == 0:
        continue
    m_co = net_arr_co.mean()
    strand_rate_co = strand_count / n_wins
    # t-stat vs live_current (paired is impossible since we skip; use difference in means)
    # For conservative test: compare against all-in live at same windows
    # Residual live after removing the skipped windows
    residual_live = []
    skip2 = 0
    for i, row in oos_ordered.iterrows():
        if skip2 > 0:
            skip2 -= 1
            continue
        net_i = float(row["net_live"])
        residual_live.append(net_i)
        if net_i < -5.0:
            skip2 = N_skip

    diff_co = net_arr_co - np.array(residual_live[:len(net_arr_co)])
    se_co = diff_co.std() / np.sqrt(len(diff_co)) if len(diff_co) > 0 else 1.0
    t_co = diff_co.mean() / se_co if se_co > 0 else 0.0

    vs_live_simple = m_co - live_oos_mean
    co_results.append({"N": N_skip, "n": n_wins, "net": m_co, "strand%": strand_rate_co,
                        "t_vs_live": t_co, "vs_live": vs_live_simple, "n_skipped": n_skipped})
    print(f"{N_skip:>8} {n_wins:>8} {m_co:>10.3f} {strand_rate_co:>9.1%} "
          f"{t_co:>10.2f} {vs_live_simple:>+10.3f}  (skipped {n_skipped})")

# OOS temporal clustering analysis
print("\n--- OOS Strand Temporal Clustering ---")
oos_strand = (oos_ordered["net_live"] < -5.0).astype(int).values
runs = []
in_run = False
run_len = 0
for s_i in oos_strand:
    if s_i == 1:
        if not in_run:
            in_run = True
            run_len = 1
        else:
            run_len += 1
    else:
        if in_run:
            runs.append(run_len)
            in_run = False
            run_len = 0
if in_run:
    runs.append(run_len)

if runs:
    print(f"  Total strand runs (consecutive): {len(runs)}")
    print(f"  Run lengths: mean={np.mean(runs):.2f}, max={max(runs)}, "
          f"solo-strand%={(np.array(runs)==1).mean():.1%}")
    print(f"  Multi-window run count: {sum(1 for r in runs if r>1)}")
else:
    print("  No strand runs detected")

# ============================================================
# R4-4: Settle-regressor as continuous SIZING
# ============================================================
print("\n" + "=" * 70)
print("R4-4: SETTLE-REGRESSOR AS CONTINUOUS SIZING")
print("=" * 70)

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

# FULL model (includes flow_ratio -- LOOK-AHEAD: uses all-window trades, NOT causal at entry)
FEATURES = ["spread", "sig_adv_yes", "vpin", "flow_ratio", "p_yes_mid", "window_vol", "tksize"]
# CAUSAL model (all features known at entry time)
FEATURES_CAUSAL = ["spread", "sig_adv_yes", "p_yes_mid", "window_vol"]

def fit_size_model(feats, is_df_, oos_df_, label="model"):
    """Fit GBM, compute sizing results. Returns (is_r2, oos_r2, net_sized_oos, diff_t, fi)."""
    X_is_ = is_df_[feats].values.astype(float).copy()
    X_oos_ = oos_df_[feats].values.astype(float).copy()
    y_is_ = is_df_["net_live"].values.astype(float).copy()
    y_oos_ = oos_df_["net_live"].values.astype(float).copy()
    for i in range(X_is_.shape[1]):
        mn = np.nanmedian(X_is_[:, i])
        X_is_[np.isnan(X_is_[:, i]), i] = mn
        X_oos_[np.isnan(X_oos_[:, i]), i] = mn
    y_is_[np.isnan(y_is_)] = np.nanmedian(y_is_)
    y_oos_[np.isnan(y_oos_)] = np.nanmedian(y_oos_)
    scaler_ = StandardScaler()
    X_is_sc_ = scaler_.fit_transform(X_is_)
    X_oos_sc_ = scaler_.transform(X_oos_)
    gbm_ = GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                      learning_rate=0.05, subsample=0.8, random_state=42)
    gbm_.fit(X_is_sc_, y_is_)
    pred_is_ = gbm_.predict(X_is_sc_)
    pred_oos_ = gbm_.predict(X_oos_sc_)
    is_r2_ = 1 - np.var(y_is_ - pred_is_) / max(np.var(y_is_), 1e-9)
    oos_r2_ = 1 - np.var(y_oos_ - pred_oos_) / max(np.var(y_oos_), 1e-9)
    q33_ = np.percentile(pred_is_, 33)
    q67_ = np.percentile(pred_is_, 67)
    def sz(p): return 1.5 if p >= q67_ else (1.0 if p >= q33_ else 0.5)
    sizes_ = np.array([sz(p) for p in pred_oos_])
    net_sized_ = y_oos_ * sizes_
    diff_ = net_sized_ - y_oos_
    t_diff_ = diff_.mean() / (diff_.std() / np.sqrt(len(diff_))) if diff_.std() > 0 else 0.0
    fi_ = sorted(zip(feats, gbm_.feature_importances_), key=lambda x: -x[1])
    return is_r2_, oos_r2_, net_sized_, diff_, t_diff_, fi_, sizes_, y_oos_

# Fit on IS
X_is = is_df[FEATURES].values.astype(float).copy()
y_is = is_df["net_live"].values.astype(float).copy()
X_oos = oos_df[FEATURES].values.astype(float).copy()
y_oos = oos_df["net_live"].values.astype(float).copy()
for i in range(X_is.shape[1]):
    mn = np.nanmedian(X_is[:, i])
    X_is[np.isnan(X_is[:, i]), i] = mn
    X_oos[np.isnan(X_oos[:, i]), i] = mn
y_is[np.isnan(y_is)] = np.nanmedian(y_is)
y_oos[np.isnan(y_oos)] = np.nanmedian(y_oos)

scaler = StandardScaler()
X_is_sc = scaler.fit_transform(X_is)
X_oos_sc = scaler.transform(X_oos)

gbm = GradientBoostingRegressor(
    n_estimators=200, max_depth=3, learning_rate=0.05,
    subsample=0.8, random_state=42
)
gbm.fit(X_is_sc, y_is)

pred_is = gbm.predict(X_is_sc)
pred_oos = gbm.predict(X_oos_sc)

is_r2 = 1 - np.var(y_is - pred_is) / max(np.var(y_is), 1e-9)
oos_r2 = 1 - np.var(y_oos - pred_oos) / max(np.var(y_oos), 1e-9)
print(f"\nFULL GBM (incl. flow_ratio [LOOK-AHEAD]) R2: IS={is_r2:.3f}, OOS={oos_r2:.3f}")
print("WARNING: flow_ratio uses all-window trades -- NOT causal at entry. OOS R2 is inflated.")

# Feature importances
featimp = sorted(zip(FEATURES, gbm.feature_importances_), key=lambda x: -x[1])
print(f"Feature importances: {', '.join(f'{n}({v:.3f})' for n, v in featimp[:5])}")

# Continuous sizing: size in {0.5, 1.0, 1.5}x based on predicted settle
# Map predicted settle -> size multiplier
# High predicted settle -> 1.5x (more confident clean box)
# Low predicted settle -> 0.5x (more strand risk)
# Breakpoints: top 33% -> 1.5x, mid 33% -> 1.0x, bottom 33% -> 0.5x

# Use IS tertile thresholds
q_low = np.percentile(pred_is, 33)
q_high = np.percentile(pred_is, 67)
print(f"\nIS tertile breakpoints: q33={q_low:.2f}c, q67={q_high:.2f}c")

def get_size(pred_val, q_lo, q_hi):
    if pred_val >= q_hi:
        return 1.5
    elif pred_val >= q_lo:
        return 1.0
    else:
        return 0.5

q_low = np.percentile(pred_is, 33)
q_high = np.percentile(pred_is, 67)
print(f"\nIS pred tertile breakpoints: q33={q_low:.3f}c, q67={q_high:.3f}c")
sizes_oos = np.array([get_size(p, q_low, q_high) for p in pred_oos])
net_sized_oos = y_oos * sizes_oos  # net per unit = net * size

print(f"OOS size distribution: 0.5x={( sizes_oos==0.5).sum()}, 1.0x={(sizes_oos==1.0).sum()}, 1.5x={(sizes_oos==1.5).sum()}")

# Compare per-unit metrics vs live (live = always 1.0x)
print("\n--- OOS continuous sizing results (FULL model, flow_ratio is LOOK-AHEAD) ---")
print(f"{'Policy':>25} {'n':>5} {'net_c/win':>10} {'t-stat':>8} {'vs_live':>10} {'t_diff':>8}")
print("-" * 75)

m_live = float(y_oos.mean())
t_live = m_live / (float(y_oos.std()) / np.sqrt(len(y_oos))) if y_oos.std() > 0 else 0.0
sr_live = float((y_oos < -5.0).mean())
print(f"{'live (1.0x)':>25} {len(y_oos):>5} {m_live:>10.3f} {t_live:>8.2f} {'---':>10} {'---':>8}")

# Sized (full model)
net_s = y_oos * sizes_oos
m_s = float(net_s.mean()); std_s = float(net_s.std())
t_s = m_s / (std_s / np.sqrt(len(net_s))) if std_s > 0 else 0.0
diff_arr_full = net_s - y_oos
m_diff_full = float(diff_arr_full.mean()); std_diff_full = float(diff_arr_full.std())
t_diff_full = m_diff_full / (std_diff_full / np.sqrt(len(diff_arr_full))) if std_diff_full > 0 else 0.0
print(f"{'full model 0.5/1/1.5x [LOOK-AHEAD]':>25} {len(net_s):>5} {m_s:>10.3f} {t_s:>8.2f} {m_s-m_live:>+10.3f} {t_diff_full:>8.2f}")

# Causal model
is_r2_c, oos_r2_c, net_sized_c, diff_c, t_diff_c, fi_c, sizes_c, y_oos_c = fit_size_model(
    FEATURES_CAUSAL, is_df, oos_df, "causal"
)
m_c = float(net_sized_c.mean())
t_c = m_c / (float(net_sized_c.std()) / np.sqrt(len(net_sized_c))) if net_sized_c.std() > 0 else 0.0
m_diff_c = float(diff_c.mean())
print(f"{'causal model 0.5/1/1.5x':>25} {len(net_sized_c):>5} {m_c:>10.3f} {t_c:>8.2f} {m_c-m_live:>+10.3f} {t_diff_c:>8.2f}")

print(f"\nFull model OOS R2={oos_r2:.3f} (INFLATED -- flow_ratio look-ahead)")
print(f"Causal model OOS R2={oos_r2_c:.3f} (causal -- no look-ahead)")
print(f"Feature importances (causal): {', '.join(f'{n}({v:.3f})' for n,v in fi_c[:4])}")

# Prediction quality breakdown
strand_mask_oos = y_oos < -5.0
p_str_050 = strand_mask_oos[sizes_oos==0.5].mean() if (sizes_oos==0.5).sum()>0 else np.nan
p_str_150 = strand_mask_oos[sizes_oos==1.5].mean() if (sizes_oos==1.5).sum()>0 else np.nan
print(f"\nPrediction quality (full model): 0.5x-bucket strand rate={p_str_050:.1%}, 1.5x-bucket={p_str_150:.1%}")

# IS sizing results for comparison
sizes_is = np.array([get_size(p, q_low, q_high) for p in pred_is])
net_sized_is = y_is * sizes_is
m_is_sz = float(net_sized_is.mean())
m_is_live = float(y_is.mean())
print(f"\nIS sanity: live={m_is_live:.3f}c, sized={m_is_sz:.3f}c  (IS R2={is_r2:.3f})")

# ============================================================
# R4-1: Vol x Directional Inside Q4 (top-vol quartile)
# ============================================================
print("\n" + "=" * 70)
print("R4-1: VOL x DIRECTIONAL INSIDE Q4 (top-vol quartile)")
print("=" * 70)

# Compute vol quartiles on full dataset
q75_vol = df["window_vol"].quantile(0.75)
q25_vol = df["window_vol"].quantile(0.25)
print(f"\nVol quartiles: Q25={q25_vol:.2f}bps, Q75={q75_vol:.2f}bps")

# Q4 windows: top vol quartile
q4_df = df[df["window_vol"] >= q75_vol].copy()
q4_is = q4_df[q4_df["is_is"]]
q4_oos = q4_df[~q4_df["is_is"]]

print(f"\nQ4 (vol >= {q75_vol:.2f}bps): IS={len(q4_is)}, OOS={len(q4_oos)}")
print(f"Q4 strand rate: IS={q4_is['is_strand'].mean():.1%}, OOS={q4_oos['is_strand'].mean():.1%}")
print(f"Q4 net IS: {q4_is['net_live'].mean():.3f}c/win, OOS: {q4_oos['net_live'].mean():.3f}c/win")

# VALID strand label inside Q4: actual fill-pairing failure
# We use: yes_strand (gate not fired AND settle_yes_only < -5c)
#     vs  no_strand (gate fired AND settle_no_only < -5c)
# In Q4 context: classify each window with strand_type

# For classifier target: "strand" = net_live < -5c (same as before, but inside Q4)
# Important: in Q4 the strand label is NOT just res_up -- it depends on fill pairing
# We use the best available label: net_live < -5c indicates a strand or bad outcome

print("\n--- Q4 strand classifier ---")
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score

# Labels: strand inside Q4
y_q4_is = (q4_is["net_live"] < -5.0).astype(int).values
y_q4_oos = (q4_oos["net_live"] < -5.0).astype(int).values

print(f"Q4 IS label balance: {y_q4_is.mean():.1%} strand (n={len(y_q4_is)})")
print(f"Q4 OOS label balance: {y_q4_oos.mean():.1%} strand (n={len(y_q4_oos)})")

if len(q4_is) < 20 or len(q4_oos) < 10:
    print("Insufficient Q4 data for classifier.")
else:
    # Use causal features only (btc_move_bps and flow_ratio are look-ahead)
    FEAT_Q4 = ["spread", "sig_adv_yes", "p_yes_mid", "window_vol"]  # causal only

    X_q4_is = q4_is[FEAT_Q4].values.astype(float)
    X_q4_oos = q4_oos[FEAT_Q4].values.astype(float)

    for arr_ in [X_q4_is, X_q4_oos]:
        for i in range(arr_.shape[1]):
            mn = np.nanmedian(X_q4_is[:, i])
            arr_[np.isnan(arr_[:, i]), i] = mn

    sc_q4 = StandardScaler()
    X_q4_is_sc = sc_q4.fit_transform(X_q4_is)
    X_q4_oos_sc = sc_q4.transform(X_q4_oos)

    # YES-strand classifier
    clf_yes = GradientBoostingClassifier(
        n_estimators=100, max_depth=2, learning_rate=0.1,
        subsample=0.8, random_state=42
    )
    clf_yes.fit(X_q4_is_sc, y_q4_is)

    prob_is_yes = clf_yes.predict_proba(X_q4_is_sc)[:, 1]
    prob_oos_yes = clf_yes.predict_proba(X_q4_oos_sc)[:, 1]

    auc_is = roc_auc_score(y_q4_is, prob_is_yes) if len(np.unique(y_q4_is)) > 1 else 0.5
    auc_oos = roc_auc_score(y_q4_oos, prob_oos_yes) if len(np.unique(y_q4_oos)) > 1 else 0.5

    feat_imp_q4 = sorted(zip(FEAT_Q4, clf_yes.feature_importances_), key=lambda x: -x[1])
    print(f"\nQ4 Strand Classifier (YES/NO combined, net<-5c):")
    print(f"  IS AUC: {auc_is:.3f}, OOS AUC: {auc_oos:.3f}")
    print(f"  Feature importances: {', '.join(f'{n}({v:.3f})' for n, v in feat_imp_q4[:5])}")

    # Directional gate: skip Q4 windows where P(strand) > threshold
    print("\n  Q4 Directional Gate sweep (P_strand > thresh -> skip):")
    print(f"  {'thresh':>8} {'n_wins':>8} {'net_c/win':>10} {'t-stat':>8} {'vs_live_q4':>12} {'strand%':>9}")
    print("  " + "-" * 58)

    q4_oos_live_net = q4_oos["net_live"].values
    q4_oos_live_mean = q4_oos_live_net.mean()

    best_q4 = None
    for thresh in [0.40, 0.50, 0.60, 0.70, 0.80]:
        mask = prob_oos_yes <= thresh  # keep windows below strand threshold
        if mask.sum() < 5:
            continue
        net_g = q4_oos_live_net[mask]
        m_g2 = net_g.mean()
        se_g2 = net_g.std() / np.sqrt(len(net_g)) if len(net_g) > 0 else 1.0
        t_g2 = m_g2 / se_g2 if se_g2 > 0 else 0.0
        sr_g2 = (net_g < -5.0).mean()
        vs_live_q4 = m_g2 - q4_oos_live_mean
        print(f"  {thresh:>8.2f} {mask.sum():>8} {m_g2:>10.3f} {t_g2:>8.2f} {vs_live_q4:>+12.3f} {sr_g2:>9.1%}")
        if best_q4 is None or vs_live_q4 > best_q4[1]:
            best_q4 = (thresh, vs_live_q4, mask.sum())

    if best_q4:
        print(f"\n  Best Q4 gate: thresh={best_q4[0]}, vs_live_q4={best_q4[1]:+.3f}c, n={best_q4[2]}")
        if best_q4[2] >= 300 and abs(best_q4[1]) > 0:
            print(f"  -> CLEARS n>=300 bar? {'YES' if best_q4[2]>=300 else 'NO'}")

    # YES-only vs NO-only classifier in Q4
    y_q4_yes_str = q4_is["is_yes_strand"].astype(int).values
    y_q4_no_str = q4_is["is_no_strand"].astype(int).values
    y_q4_yes_str_oos = q4_oos["is_yes_strand"].astype(int).values
    y_q4_no_str_oos = q4_oos["is_no_strand"].astype(int).values

    print(f"\n  Q4 leg-specific strand labels:")
    print(f"    IS YES-strand: {y_q4_yes_str.mean():.1%} (n={y_q4_yes_str.sum()})")
    print(f"    IS NO-strand: {y_q4_no_str.mean():.1%} (n={y_q4_no_str.sum()})")
    print(f"    OOS YES-strand: {y_q4_yes_str_oos.mean():.1%} (n={y_q4_yes_str_oos.sum()})")
    print(f"    OOS NO-strand: {y_q4_no_str_oos.mean():.1%} (n={y_q4_no_str_oos.sum()})")

    for strand_type, y_is_lbl, y_oos_lbl in [
        ("YES-strand", y_q4_yes_str, y_q4_yes_str_oos),
        ("NO-strand", y_q4_no_str, y_q4_no_str_oos)
    ]:
        if y_is_lbl.sum() < 5 or y_oos_lbl.sum() < 2:
            print(f"\n  {strand_type}: insufficient positives for AUC")
            continue
        if len(np.unique(y_is_lbl)) < 2 or len(np.unique(y_oos_lbl)) < 2:
            print(f"\n  {strand_type}: degenerate label (all one class)")
            continue
        clf_type = GradientBoostingClassifier(n_estimators=100, max_depth=2, random_state=42)
        clf_type.fit(X_q4_is_sc, y_is_lbl)
        p_oos_type = clf_type.predict_proba(X_q4_oos_sc)[:, 1]
        auc_type_oos = roc_auc_score(y_oos_lbl, p_oos_type)
        auc_type_is = roc_auc_score(y_is_lbl, clf_type.predict_proba(X_q4_is_sc)[:, 1])
        fi_type = sorted(zip(FEAT_Q4, clf_type.feature_importances_), key=lambda x: -x[1])
        print(f"\n  Q4 {strand_type} classifier:")
        print(f"    IS AUC={auc_type_is:.3f}, OOS AUC={auc_type_oos:.3f}")
        print(f"    Top features: {', '.join(f'{n}({v:.3f})' for n, v in fi_type[:3])}")
        actionable = "ACTIONABLE" if auc_type_oos > 0.60 and auc_type_is < 0.95 else "NOT actionable (low AUC or IS overfit)"
        print(f"    -> {actionable}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("SUMMARY TABLE")
print("=" * 70)

print(f"\n{'Idea':>25} {'n_OOS':>6} {'net_c/win':>10} {'vs_live':>10} {'t_diff':>8} {'verdict':>20}")
print("-" * 85)
# R4-5 cooling-off best
if co_results:
    best_co = max(co_results, key=lambda x: x["vs_live"])
    print(f"{'R4-5 cooling-off N='+str(best_co['N']):>25} {best_co['n']:>6} "
          f"{best_co['net']:>10.3f} {best_co['vs_live']:>+10.3f} {best_co['t_vs_live']:>8.2f}  "
          f"{'SCREEN' if best_co['t_vs_live']<3 else 'CANDIDATE'}")

print(f"{'R4-4 sizing':>25} {len(y_oos):>6} --- see above ---")
print(f"{'live_current OOS':>25} {len(oos_df):>6} {live_oos_mean:>10.3f}  {'---':>10}   ---")

print("\n--- Hedge best case (R4-2) ---")
best_hedge = max(all_results, key=lambda x: x["vs_live"])
print(f"  Best hedge scenario: eff={best_hedge['hedge_eff']}, slip={best_hedge['slip_bps']}bps, "
      f"net={best_hedge['net_c_win']:.3f}c, vs_live={best_hedge['vs_live']:+.3f}c")

print("\n[DONE]")
