"""
multi_asset_study.py — Compact multi-asset tape replay study.
Covers BTC, ETH, SOL, XRP using the same parquet/logic as informed_detectors.py
Sections: A-G per CLAUDE.md spec. All output is tabular/compact.
"""
import os, sys, warnings
os.chdir("/home/user/Codex-playground-")
sys.path.insert(0, '/home/user/Codex-playground-')
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from informed_detectors import build as build_features, vpin_buckets, vpin_at, detectors

# ── Frozen gate thresholds from box_policy_ab.py ──────────────────────────────
VPIN_THRESH = 0.40
_COMBO_INTERCEPT = -1.097821
_COMBO_FEATS = ["vpin", "take_n", "d1_maxrun", "d2_lambda", "d1_nruns", "d4_roundfrac", "d5_sweep"]
_COMBO_MEANS = {"vpin": 0.420709, "take_n": 1195.595024, "d1_maxrun": 25.951139,
                "d2_lambda": 0.083574, "d1_nruns": 0.289674, "d4_roundfrac": 0.158329,
                "d5_sweep": 7.621103}
_COMBO_STDS =  {"vpin": 0.188093, "take_n": 1572.059825, "d1_maxrun": 18.508967,
                "d2_lambda": 0.181745, "d1_nruns": 0.064831, "d4_roundfrac": 0.089765,
                "d5_sweep": 4.795740}
_COMBO_COEFS = {"vpin": 0.139545, "take_n": -0.926797, "d1_maxrun": -0.052450,
                "d2_lambda": 0.177854, "d1_nruns": 0.046305, "d4_roundfrac": -0.006626,
                "d5_sweep": -0.024818}
_COMBO_THRESH = 0.3656
K = 7  # decision minute

ASSETS = ["btc", "eth", "sol", "xrp"]

# ── helpers ──────────────────────────────────────────────────────────────────
def combo_tox_p_row(row):
    vals = {f: row.get(f, np.nan) for f in _COMBO_FEATS}
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in vals.values()):
        return np.nan
    z = _COMBO_INTERCEPT
    for feat in _COMBO_FEATS:
        z += _COMBO_COEFS[feat] * (vals[feat] - _COMBO_MEANS[feat]) / _COMBO_STDS[feat]
    return 1.0 / (1.0 + np.exp(-z))

def maxdd(seq):
    """Max drawdown from a cumulative PnL series."""
    cum = np.cumsum(seq)
    peak = np.maximum.accumulate(cum)
    dd = cum - peak
    return float(dd.min()) if len(dd) else 0.0

def simulate_window(ws, h, tap):
    """
    Run fill simulation for a single window (minutes 2-12, q0=0).
    Returns list of fill-dicts with: side, settle, k, tau, vpin, stranded_tag,
      combo_tox_p, fill_time_in_window (seconds from ws).
    Also returns box_pnl (P0 always-pair), strand_count, any_fill.
    """
    bid = np.asarray(h.bid_path, float)
    ask = np.asarray(h.ask_path, float)
    t_arr = np.asarray(tap.t, float)
    p_arr = np.asarray(tap.p, float)
    sz_arr = np.asarray(tap.sz, float)
    buy_arr = np.asarray(tap.buy, bool)

    bt, bi = vpin_buckets(t_arr, sz_arr, buy_arr)

    fills = []
    for k in range(2, 13):
        b0, a0 = bid[k], ask[k]
        if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
            continue
        spread = a0 - b0
        tau = (15 - k) / 15.0
        # causal detectors
        msk = t_arr < (ws + 60 * k)
        dv = detectors(ws, t_arr[msk], p_arr[msk], sz_arr[msk], buy_arr[msk])
        # vpin at decision minute
        vp = vpin_at(bt, bi, ws + 60 * k)

        lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
        i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
        done_b = done_a = False
        fill_b_time = fill_a_time = None
        for i in range(i0, i1):
            if done_b and done_a:
                break
            p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
            if not done_b and not buy and p <= b0 + 1e-9:
                done_b = True; fill_b_time = t_arr[i] - ws
            if not done_a and buy and p >= a0 - 1e-9:
                done_a = True; fill_a_time = t_arr[i] - ws

        # only count windows where at least one leg filled
        if not done_b and not done_a:
            continue

        # determine settlement result (binary: res=1 if settle>b0, i.e. YES=1)
        # We don't have res directly — simulate from subsequent taker flow at end of window
        # Use the final bid/ask at minute 14 as proxy for expected settlement:
        # settle=1 means YES pays $1; bid fills settle=1-b0 if yes; ask fills settle=a0-res
        # For strand cost: if done_b but not done_a => YES leg stranded, settles at 0 or 1
        # We'll record raw settle at end using mid_path if available, else 0.5 proxy
        mid = np.asarray(h.mid_path, float)
        # End-of-window settlement proxy: mid at minute 14
        mid_end = mid[14] if len(mid) > 14 and not np.isnan(mid[14]) else 0.5
        # Actual Kalshi settlement is binary: need to determine 0 or 1
        # Use the last known ask/bid path near expiry as settlement probability
        # For realistic simulation use the actual settle from the tape:
        # We approximate: res=1 if ask[14]>0.5 else 0 (or use mid_path[-1])
        # Better: find the last trade price in the window to estimate settle
        # Most accurate: use settle from the hist parquet if available
        # hist has bid_path, ask_path, mid_path - mid at end is best proxy
        res_prob = mid_end

        settle_bid = res_prob - b0       # YES leg: win if res=1
        settle_ask = a0 - res_prob       # NO leg: win if res=0
        stranded = int(done_b != done_a)

        # combo tox score
        row_vals = dict(vpin=vp, **{k2: dv[k2] for k2 in
                        ["take_n","d1_maxrun","d2_lambda","d1_nruns","d4_roundfrac","d5_sweep"]})
        ctp = combo_tox_p_row(row_vals)

        if done_b:
            fills.append(dict(ws=ws, side='bid', settle=settle_bid, k=k, tau=tau,
                              spread=spread, vpin=vp, combo_tox_p=ctp,
                              stranded=stranded, fill_time=fill_b_time,
                              tksize=1.0, det_vpin=vp,
                              **{f"det_{k2}": dv[k2] for k2 in
                                 ["take_n","d1_maxrun","d2_lambda","d1_nruns","d4_roundfrac","d5_sweep"]}))
        if done_a:
            fills.append(dict(ws=ws, side='ask', settle=settle_ask, k=k, tau=tau,
                              spread=spread, vpin=vp, combo_tox_p=ctp,
                              stranded=stranded, fill_time=fill_a_time,
                              tksize=1.0, det_vpin=vp,
                              **{f"det_{k2}": dv[k2] for k2 in
                                 ["take_n","d1_maxrun","d2_lambda","d1_nruns","d4_roundfrac","d5_sweep"]}))
    return fills

def run_p0_policy(fills):
    """Always-pair policy (P0): accept fill iff |net|<=1. Returns (pnl, strands, paired_wins)."""
    net = 0; pnl = 0.0; strands = 0; pairs = 0
    open_side = None
    for f in fills:
        step = 1 if f['side'] == 'bid' else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        if net != 0 and abs(nn) < abs(net):
            # this fill PAIRS the open leg -> it's a box
            pairs += 1
        net = nn
        pnl += f['settle']
        if net == 0:
            open_side = None
        else:
            open_side = f['side']

    # if net != 0 at end, one leg is stranded
    if net != 0:
        strands += 1
    return pnl, strands

def load_asset_data(asset):
    """Load hist and trades parquet, return merged per-window iterator."""
    hist = pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws")
    tap = pd.read_parquet(f"trades_kalshi_{asset}15m.parquet").set_index("ws")
    common = sorted(set(hist.index) & set(tap.index))
    return hist, tap, common

# ── Main analysis ─────────────────────────────────────────────────────────────
print("Loading data and running simulations...")
print("(This may take a few minutes for all 4 assets)\n")

results = {}  # asset -> dict of metrics

for asset in ASSETS:
    print(f"  Processing {asset}...", end=" ", flush=True)
    try:
        hist, tap, common = load_asset_data(asset)
    except Exception as e:
        print(f"ERROR: {e}")
        results[asset] = None
        continue

    n_windows = len(common)
    split_idx = int(n_windows * 0.6)
    is_ws = set(common[:split_idx])
    oos_ws = set(common[split_idx:])

    all_fills = []
    window_stats = []  # per-window: ws, n_fills, pnl_p0, strands, is_flag, hour

    for ws in common:
        h = hist.loc[ws]
        t = tap.loc[ws]
        fills = simulate_window(ws, h, t)
        if not fills:
            continue
        pnl, strands = run_p0_policy(fills)
        hour = pd.Timestamp(ws, unit='s', tz='UTC').hour
        window_stats.append(dict(
            ws=ws, n_fills=len(fills), pnl=pnl, strands=strands,
            is_flag=(ws in is_ws), hour=hour
        ))
        for f in fills:
            f['is_flag'] = (ws in is_ws)
            f['hour'] = hour
            all_fills.append(f)

    wdf = pd.DataFrame(window_stats)
    fdf = pd.DataFrame(all_fills)

    results[asset] = dict(
        n_windows=n_windows,
        split_idx=split_idx,
        wdf=wdf,
        fdf=fdf,
        hist=hist,
        tap=tap,
        common=common
    )
    print(f"done ({n_windows} windows, {len(wdf)} with fills)")

print()

# ── SECTION B: Baseline policy table IS/OOS ──────────────────────────────────
print("=" * 80)
print("B) BASELINE POLICY TABLE (P0: always-pair, strict |net|<=1, q0=0)")
print("=" * 80)

header = f"{'Metric':<30}" + "".join(f"{a:>10}" for a in ASSETS)
print(header)
print("-" * (30 + 10*len(ASSETS)))

def asset_row(label, vals):
    return f"{label:<30}" + "".join(f"{v:>10}" for v in vals)

metrics_is = {}
metrics_oos = {}

for asset in ASSETS:
    r = results.get(asset)
    if r is None:
        for d in [metrics_is, metrics_oos]:
            d[asset] = {k: "ERR" for k in ['windows','fills_pw','pair_rate','strands_pw',
                                             'mean_strand','net_pw','maxdd']}
        continue

    wdf = r['wdf']
    fdf = r['fdf']

    for split_label, mask_flag, d in [("IS", True, metrics_is), ("OOS", False, metrics_oos)]:
        wf = wdf[wdf.is_flag == mask_flag]
        ff = fdf[fdf.is_flag == mask_flag] if len(fdf) else pd.DataFrame()

        nw = len(wf)
        fills_pw = len(ff) / nw if nw > 0 else 0
        total_strands = wf.strands.sum()
        strands_pw = total_strands / nw if nw > 0 else 0
        # pair_rate: fraction of fills that are paired (both legs in a window)
        # windows with strands=0 are fully paired; count box completions
        paired_windows = (wf.strands == 0).sum()
        pair_rate = paired_windows / nw if nw > 0 else 0
        # mean strand cost: average pnl of windows with strands (these are bad windows)
        stranded_pnl = wf[wf.strands > 0].pnl.mean() if total_strands > 0 else 0.0
        net_pw = wf.pnl.mean() if nw > 0 else 0
        mdd = maxdd(wf.pnl.values)

        d[asset] = dict(
            windows=nw,
            fills_pw=f"{fills_pw:.2f}",
            pair_rate=f"{pair_rate:.3f}",
            strands_pw=f"{strands_pw:.3f}",
            mean_strand=f"{stranded_pnl:.4f}",
            net_pw=f"{net_pw:.4f}",
            maxdd=f"{mdd:.3f}"
        )

for split_label, d in [("IS (60%)", metrics_is), ("OOS (40%)", metrics_oos)]:
    print(f"\n  {split_label}")
    for key, label in [('windows','Windows'), ('fills_pw','Fills/window'),
                        ('pair_rate','Pair rate'), ('strands_pw','Strands/window'),
                        ('mean_strand','Mean strand cost'), ('net_pw','Net c/window'),
                        ('maxdd','MaxDD')]:
        vals = [d[a][key] if d.get(a) else "N/A" for a in ASSETS]
        print(asset_row(f"  {label}", vals))

# ── SECTION C: Strand asymmetry ───────────────────────────────────────────────
print()
print("=" * 80)
print("C) STRAND ASYMMETRY (which leg is toxic when stranded)")
print("=" * 80)
print(f"{'Metric':<35}" + "".join(f"{a:>10}" for a in ASSETS))
print("-" * (35 + 10*len(ASSETS)))

for key, label in [
    ('bid_strand_pnl', 'YES (bid) strand mean settle'),
    ('ask_strand_pnl', 'NO (ask) strand mean settle'),
    ('bid_strand_n', 'YES strand count'),
    ('ask_strand_n', 'NO strand count'),
    ('bid_neg_rate', 'YES strand loss rate'),
    ('ask_neg_rate', 'NO strand loss rate'),
]:
    vals = []
    for asset in ASSETS:
        r = results.get(asset)
        if r is None:
            vals.append("ERR")
            continue
        fdf = r['fdf']
        if len(fdf) == 0:
            vals.append("N/A")
            continue
        # stranded fills are those in windows with strands>0
        # for simplicity, use stranded=1 flag on fill
        sf = fdf[fdf.stranded == 1]
        bid_sf = sf[sf.side == 'bid']
        ask_sf = sf[sf.side == 'ask']
        if key == 'bid_strand_pnl':
            vals.append(f"{bid_sf.settle.mean():.4f}" if len(bid_sf) > 0 else "0")
        elif key == 'ask_strand_pnl':
            vals.append(f"{ask_sf.settle.mean():.4f}" if len(ask_sf) > 0 else "0")
        elif key == 'bid_strand_n':
            vals.append(str(len(bid_sf)))
        elif key == 'ask_strand_n':
            vals.append(str(len(ask_sf)))
        elif key == 'bid_neg_rate':
            vals.append(f"{(bid_sf.settle < 0).mean():.3f}" if len(bid_sf) > 0 else "N/A")
        elif key == 'ask_neg_rate':
            vals.append(f"{(ask_sf.settle < 0).mean():.3f}" if len(ask_sf) > 0 else "N/A")
    print(f"{label:<35}" + "".join(f"{v:>10}" for v in vals))

# ── SECTION D: Capacity analysis ──────────────────────────────────────────────
print()
print("=" * 80)
print("D) CAPACITY ANALYSIS (flow-based max contracts/window, implied $/day)")
print("=" * 80)
print(f"{'Metric':<35}" + "".join(f"{a:>10}" for a in ASSETS))
print("-" * (35 + 10*len(ASSETS)))

capacity_data = {}
for asset in ASSETS:
    r = results.get(asset)
    if r is None:
        capacity_data[asset] = {}
        continue
    tap = r['tap']
    common = r['common']
    # median contracts traded per minute across all windows
    per_window_vol = []
    per_minute_vol = []
    for ws in common[:500]:  # sample for speed
        try:
            t = tap.loc[ws]
            t_arr = np.asarray(t.t, float)
            sz_arr = np.asarray(t.sz, float)
            per_window_vol.append(sz_arr.sum())
            if len(t_arr) > 0:
                dur = t_arr[-1] - t_arr[0]
                if dur > 0:
                    per_minute_vol.append(sz_arr.sum() / (dur / 60.0))
        except:
            pass

    med_vol_window = np.median(per_window_vol) if per_window_vol else 0
    med_vol_per_min = np.median(per_minute_vol) if per_minute_vol else 0
    # Max sustainable: front-of-queue, you can capture ~5% of flow at touch
    # Conservative: 2% of window volume
    max_contracts = med_vol_window * 0.02
    # OOS net c/window * max_contracts * 96 windows/day * 1 contract = $/day
    oos_net = float(metrics_oos[asset]['net_pw']) if metrics_oos.get(asset) else 0
    try:
        oos_net_f = float(metrics_oos[asset]['net_pw'])
    except:
        oos_net_f = 0.0
    # implied $/day at 1 contract max_contracts sizing with gated strategy
    # (using OOS net as the per-window expectation)
    implied_day = oos_net_f * 96 * max_contracts  # rough: per-window net * windows * contracts
    capacity_data[asset] = dict(
        med_vol_window=med_vol_window,
        med_vol_per_min=med_vol_per_min,
        max_contracts=max_contracts,
        implied_day=implied_day
    )

for key, label, fmt in [
    ('med_vol_window', 'Median vol/window (contracts)', '{:.0f}'),
    ('med_vol_per_min', 'Median vol/min (contracts)', '{:.0f}'),
    ('max_contracts', 'Est max contracts/window (2%)', '{:.1f}'),
    ('implied_day', 'Implied $/day (OOS rate, 96w/d)', '{:.2f}'),
]:
    vals = []
    for asset in ASSETS:
        d = capacity_data.get(asset, {})
        v = d.get(key)
        vals.append(fmt.format(v) if v is not None else "N/A")
    print(f"{label:<35}" + "".join(f"{v:>10}" for v in vals))

# BTC-only vs total comparison
print()
btc_day = capacity_data.get('btc', {}).get('implied_day', 0)
total_day = sum(v.get('implied_day', 0) for v in capacity_data.values())
print(f"  BTC-only $/day (OOS, 2% cap):  {btc_day:.2f}")
print(f"  All-4-asset total $/day:        {total_day:.2f}")
print(f"  Multiplier vs BTC-only:         {total_day/btc_day:.2f}x" if btc_day != 0 else "  N/A")

# ── SECTION E: Gate transfer ──────────────────────────────────────────────────
print()
print("=" * 80)
print("E) GATE TRANSFER (OOS baseline vs VPIN<=0.40 vs combo_tox<=0.3656)")
print("=" * 80)

for asset in ASSETS:
    r = results.get(asset)
    if r is None:
        print(f"  {asset}: ERROR")
        continue

    wdf = r['wdf']
    fdf = r['fdf']
    if len(fdf) == 0:
        print(f"  {asset}: no fills")
        continue

    # OOS only
    wdf_oos = wdf[~wdf.is_flag]
    fdf_oos = fdf[~fdf.is_flag]

    if len(wdf_oos) == 0:
        print(f"  {asset}: no OOS data")
        continue

    # Baseline
    baseline_net = wdf_oos.pnl.mean()
    baseline_strand = wdf_oos.strands.sum() / len(wdf_oos)
    baseline_keep = 1.0

    # VPIN gate: keep windows where vpin<=0.40 (use fill-level vpin, most conservative = first fill's vpin)
    # We apply gate at window level: keep window if mean vpin of fills <= threshold
    fdf_oos_agg = fdf_oos.groupby('ws').agg(mean_vpin=('vpin','mean'), mean_combo=('combo_tox_p','mean')).reset_index()
    wdf_oos2 = wdf_oos.merge(fdf_oos_agg, on='ws', how='left')

    vpin_mask = wdf_oos2.mean_vpin <= VPIN_THRESH
    combo_mask = wdf_oos2.mean_combo <= _COMBO_THRESH

    # Handle NaN (missing features -> keep window, same as gate no-op)
    vpin_mask = vpin_mask.fillna(True)
    combo_mask = combo_mask.fillna(True)

    vpin_net = wdf_oos2[vpin_mask].pnl.mean() if vpin_mask.sum() > 0 else np.nan
    vpin_strand = wdf_oos2[vpin_mask].strands.sum() / vpin_mask.sum() if vpin_mask.sum() > 0 else np.nan
    vpin_keep = vpin_mask.mean()

    combo_net = wdf_oos2[combo_mask].pnl.mean() if combo_mask.sum() > 0 else np.nan
    combo_strand = wdf_oos2[combo_mask].strands.sum() / combo_mask.sum() if combo_mask.sum() > 0 else np.nan
    combo_keep = combo_mask.mean()

    print(f"\n  {asset.upper()} (OOS: {len(wdf_oos)} windows)")
    print(f"  {'Gate':<20} {'Net/win':>10} {'Strand/win':>12} {'Keep%':>8} {'DD':>8}")
    print(f"  {'-'*58}")
    mdd_base = maxdd(wdf_oos.pnl.values)
    mdd_vpin = maxdd(wdf_oos2[vpin_mask].pnl.values) if vpin_mask.sum() > 1 else 0
    mdd_combo = maxdd(wdf_oos2[combo_mask].pnl.values) if combo_mask.sum() > 1 else 0
    print(f"  {'Baseline':<20} {baseline_net:>10.4f} {baseline_strand:>12.4f} {baseline_keep:>8.1%} {mdd_base:>8.3f}")
    print(f"  {'VPIN<=0.40':<20} {vpin_net:>10.4f} {vpin_strand:>12.4f} {vpin_keep:>8.1%} {mdd_vpin:>8.3f}")
    print(f"  {'combo<=0.3656':<20} {combo_net:>10.4f} {combo_strand:>12.4f} {combo_keep:>8.1%} {mdd_combo:>8.3f}")

# ── SECTION F: Last-120s hazard + hour-of-day ─────────────────────────────────
print()
print("=" * 80)
print("F) LAST-120s HAZARD: fills in last 120s of window (k>=12) vs earlier")
print("=" * 80)
print(f"{'Metric':<35}" + "".join(f"{a:>10}" for a in ASSETS))
print("-" * (35 + 10*len(ASSETS)))

for key, label in [
    ('late_settle', 'Late (k>=12) mean settle'),
    ('early_settle', 'Early (k<12) mean settle'),
    ('late_neg_rate', 'Late loss rate'),
    ('early_neg_rate', 'Early loss rate'),
    ('late_frac', 'Fraction of fills that are late'),
]:
    vals = []
    for asset in ASSETS:
        r = results.get(asset)
        if r is None:
            vals.append("ERR")
            continue
        fdf = r['fdf']
        if len(fdf) == 0:
            vals.append("N/A")
            continue
        late = fdf[fdf.k >= 12]
        early = fdf[fdf.k < 12]
        if key == 'late_settle':
            vals.append(f"{late.settle.mean():.4f}" if len(late) > 0 else "N/A")
        elif key == 'early_settle':
            vals.append(f"{early.settle.mean():.4f}" if len(early) > 0 else "N/A")
        elif key == 'late_neg_rate':
            vals.append(f"{(late.settle < 0).mean():.3f}" if len(late) > 0 else "N/A")
        elif key == 'early_neg_rate':
            vals.append(f"{(early.settle < 0).mean():.3f}" if len(early) > 0 else "N/A")
        elif key == 'late_frac':
            vals.append(f"{len(late)/len(fdf):.3f}" if len(fdf) > 0 else "N/A")
    print(f"{label:<35}" + "".join(f"{v:>10}" for v in vals))

# Hour-of-day patterns
print()
print("  Hour-of-day OOS net/window (UTC):")
print(f"  {'Hour':<8}" + "".join(f"{a:>10}" for a in ASSETS))
print(f"  {'-'*(8+10*len(ASSETS))}")

# Get unique hours
all_hours = sorted(range(0, 24, 4))  # report every 4 hours
for hour_bin in all_hours:
    hours_range = range(hour_bin, hour_bin + 4)
    vals = []
    for asset in ASSETS:
        r = results.get(asset)
        if r is None:
            vals.append("ERR")
            continue
        wdf = r['wdf']
        wdf_oos = wdf[~wdf.is_flag]
        h_mask = wdf_oos.hour.isin(hours_range)
        h_wdf = wdf_oos[h_mask]
        if len(h_wdf) == 0:
            vals.append("N/A")
        else:
            vals.append(f"{h_wdf.pnl.mean():.4f}")
    print(f"  {hour_bin:02d}-{hour_bin+4:02d}h  " + "".join(f"{v:>10}" for v in vals))

# ── SECTION G: Fee verification ───────────────────────────────────────────────
print()
print("=" * 80)
print("G) FEE VERIFICATION STATUS (from KALSHI.md + live fills)")
print("=" * 80)
print("""
  Confirmed from KALSHI.md (line 190-193):
  "The fee landscape, resolved: all four CRYPTO15M series share identical fee config
  (fee_type=quadratic, fee_multiplier=1) and one contract certification; BTC AND ETH
  maker fee = $0.00 proven on real fills (ETH at p=0.42/0.45/0.59 — mid prices where a
  charged maker fee would be clearly non-zero); SOL/XRP share identical config -> the
  whole CRYPTO15M family is fee-exempt."

  Status by asset:
  BTC:  CONFIRMED $0 maker fee (16 real fills, 2026-06-10, confirmed via FEE TRIPWIRE)
  ETH:  CONFIRMED $0 maker fee (real fills at p=0.42/0.45/0.59)
  SOL:  INFERRED $0 (identical fee_type=quadratic, fee_multiplier=1 config; no live fills yet)
  XRP:  INFERRED $0 (identical fee_type=quadratic, fee_multiplier=1 config; no live fills yet)

  Risk note: $0 may be a rounding artifact (1-lot formula rounds to 0) rather than explicit
  exemption. Multi-lot sizing should re-verify. FEE TRIPWIRE active on BTC live trader.
""")

print("=" * 80)
print("DONE")
print("=" * 80)
