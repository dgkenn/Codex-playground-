"""
Q3: Two-rung split grounding for t27 (4@touch + 4@touch-1c vs 8@touch)
Uses fills_btc15m_*.jsonl from gha_data — each record = one fill/quote event
with fields: bb, ba, bsz, asz, tk_sz, q_ahead, side, p, sz, ws, res_up, tau
"""

import json, glob, math
import numpy as np

DATA_DIR = "/home/user/Codex-playground-/gha_data"
TOUCH_CONTRACTS = 8      # baseline all-at-touch
SPLIT_TOUCH     = 4      # split strategy: at touch
SPLIT_DEEP      = 4      # split strategy: at touch-1c
DEEP_VOL_PCTILE = 50     # "deep hours" = above median trade vol per window

# ── 1. Load all btc15m fills ──────────────────────────────────────────────────
files = sorted(glob.glob(f"{DATA_DIR}/fills_btc15m_*.jsonl"))
if not files:
    print("ERROR: no fills_btc15m_*.jsonl found")
    raise SystemExit(1)

rows = []
for path in files:
    with open(path) as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass

print(f"[info] Loaded {len(rows):,} fill records from {len(files)} files")

# ── 2. Group by window ────────────────────────────────────────────────────────
from collections import defaultdict
windows = defaultdict(list)
for r in rows:
    ws = r.get("ws")
    if ws:
        windows[ws].append(r)

print(f"[info] {len(windows)} unique windows")

# ── 3. Per-window analysis ────────────────────────────────────────────────────
# For each fill event in a window we have:
#   bb, ba   = best bid / ask at that moment
#   bsz, asz = displayed size at best bid / ask
#   tk_sz    = size of taker order that triggered this fill
#   q_ahead  = queue ahead of our order (contracts)
#   side     = "BID" or "ASK" (our side)
#   p        = fill price
#   sz       = fill size
#   reason   = "fill" / "quote" / ...
#
# Strategy simulation per quote event:
#   We treat each fill-reason record as a realized fill.
#   q_ahead = how many contracts in front of us at placement.
#   We are at the BACK of the queue at quote time.
#   Size at touch when we placed = bsz (at the moment of the fill event;
#   we use it as a proxy for queue depth since we don't have placement snapshot).
#
# Touch price (bid side example):
#   touch   = bb
#   touch-1 = bb - 0.01
#
# Strategy A (8@touch):
#   fills when tk_sz > q_ahead (taker blows past everyone in front)
#   contracts filled = min(8, max(0, tk_sz - q_ahead))   capped at 8
#
# Strategy B (4@touch + 4@touch-1c):
#   touch leg:   same as A but size=4
#   deep leg:    fills only when tk_sz > bsz (entire touch level swept)
#                i.e. sweep condition: tk_sz > bsz
#                contracts filled = min(4, max(0, tk_sz - bsz)) if sweep else 0
#
# Markout for deep leg (touch-1c fills on a sweep):
#   On a sweep, the touch price moves away.
#   We approximate adverse markout as -0.01 (one tick) because we filled at
#   touch-1c while the market moved through the touch level.
#   For touch-level fills (both strategies), markout = 0 (neutral prior;
#   we don't have forward price, so conservative = 0).
#
# PnL model (cents per contract):
#   touch fill:  +0 c markout (conservative), fee = 0 (CRYPTO15M maker)
#   deep fill:   -1 c markout (adverse sweep premium)
#   PnL = (touch_fills * 0) + (deep_fills * (-1))
#
# "Deep hours" proxy: windows where sum(sz for reason=="fill") > median

# Filter to fill records only for simulation
fill_records = [r for r in rows if r.get("reason") == "fill"]
print(f"[info] {len(fill_records):,} fill-reason records")

# Per-window volume (proxy for "deep hours")
win_vol = defaultdict(float)
for r in fill_records:
    win_vol[r["ws"]] += r.get("sz", 0.0)

all_vols = np.array(list(win_vol.values()))
median_vol = np.median(all_vols)
deep_windows = {ws for ws, v in win_vol.items() if v > median_vol}
print(f"[info] Median window fill vol = {median_vol:.1f} contracts; "
      f"{len(deep_windows)} 'deep' windows (>{median_vol:.1f}c filled)")


def simulate_window(records):
    """
    Given fill records for one window, return per-strategy metrics.
    Returns dict or None if insufficient data.
    """
    if len(records) < 1:
        return None

    n_fills   = 0
    a_fills   = 0.0   # Strategy A contracts filled
    b_t_fills = 0.0   # Strategy B touch-leg fills
    b_d_fills = 0.0   # Strategy B deep-leg fills
    sweeps    = 0     # events where tk_sz > bsz (sweep through touch)
    deep_mo_sum = 0.0 # sum of markout on deep fills (each = -1c)

    for r in records:
        tk_sz   = r.get("tk_sz")
        q_ahead = r.get("q_ahead")
        bsz     = r.get("bsz")
        asz     = r.get("asz")
        side    = r.get("side", "")
        bb      = r.get("bb")
        ba      = r.get("ba")

        # Need tk_sz and bsz/q_ahead
        if tk_sz is None or q_ahead is None:
            continue
        if bsz is None or bsz <= 0:
            continue

        n_fills += 1

        # Strategy A: 8 @ touch
        # fills = how many of our 8 contracts the taker reaches
        overshoot_a = max(0.0, tk_sz - q_ahead)
        a_filled = min(TOUCH_CONTRACTS, overshoot_a)

        # Strategy B touch leg: 4 @ touch
        overshoot_bt = max(0.0, tk_sz - q_ahead)
        bt_filled = min(SPLIT_TOUCH, overshoot_bt)

        # Strategy B deep leg: 4 @ touch-1c
        # fills only if sweep: tk_sz > bsz (entire level consumed)
        is_sweep = (tk_sz > bsz)
        if is_sweep:
            sweeps += 1
            # how much reaches touch-1c: tk_sz - bsz (but we are back of queue there too)
            # conservative: assume we are first in queue at touch-1c (best case)
            overshoot_deep = max(0.0, tk_sz - bsz)
            bd_filled = min(SPLIT_DEEP, overshoot_deep)
            deep_mo_sum += bd_filled * (-1.0)   # -1c per contract on sweep fill
        else:
            bd_filled = 0.0

        a_fills   += a_filled
        b_t_fills += bt_filled
        b_d_fills += bd_filled

    if n_fills == 0:
        return None

    p_sweep = sweeps / n_fills
    # P(any fill) per fill-event  (at least 1 contract filled from our 8/4+4)
    # Strategy A: P(a_filled > 0) ~ P(tk_sz > q_ahead)
    # Strategy B: P(bt_filled > 0 OR bd_filled > 0)
    # We compute over the records:
    a_any = sum(1 for r in records
                if r.get("tk_sz") is not None and r.get("q_ahead") is not None
                and r.get("bsz") and
                min(TOUCH_CONTRACTS, max(0, r["tk_sz"] - r["q_ahead"])) > 0) / n_fills

    b_any_list = []
    for r in records:
        if r.get("tk_sz") is None or r.get("q_ahead") is None or not r.get("bsz"):
            continue
        bt = min(SPLIT_TOUCH, max(0, r["tk_sz"] - r["q_ahead"]))
        bd = min(SPLIT_DEEP, max(0, r["tk_sz"] - r["bsz"])) if r["tk_sz"] > r["bsz"] else 0
        b_any_list.append(1 if (bt + bd) > 0 else 0)
    b_any = np.mean(b_any_list) if b_any_list else 0.0

    # Expected fills per event
    e_a_fills   = a_fills   / n_fills
    e_bt_fills  = b_t_fills / n_fills
    e_bd_fills  = b_d_fills / n_fills
    e_b_fills   = e_bt_fills + e_bd_fills

    # Markout for deep fills: -1c per contract
    e_deep_mo   = deep_mo_sum / n_fills   # c per fill-event

    # E[PnL c per event]:
    # Strategy A: touch fills only, markout=0 (conservative)
    e_pnl_a = e_a_fills * 0.0
    # Strategy B: touch fills markout=0, deep fills markout=-1c
    e_pnl_b = e_bt_fills * 0.0 + e_deep_mo

    # E[markout c per deep fill] (conditional on a deep fill occurring)
    if e_bd_fills > 0:
        cond_deep_mo = e_deep_mo / e_bd_fills
    else:
        cond_deep_mo = float("nan")

    return dict(
        n_events   = n_fills,
        p_sweep    = p_sweep,
        a_any      = a_any,
        b_any      = b_any,
        e_a_fills  = e_a_fills,
        e_b_fills  = e_b_fills,
        e_bd_fills = e_bd_fills,
        cond_deep_mo = cond_deep_mo,
        e_pnl_a    = e_pnl_a,
        e_pnl_b    = e_pnl_b,
    )


# Group fill records by window
win_fill_records = defaultdict(list)
for r in fill_records:
    win_fill_records[r["ws"]].append(r)

# ── 4. Aggregate results ──────────────────────────────────────────────────────
def aggregate(ws_set, label):
    results = []
    for ws in ws_set:
        recs = win_fill_records.get(ws, [])
        if not recs:
            continue
        res = simulate_window(recs)
        if res:
            results.append(res)
    if not results:
        print(f"[warn] No results for {label}")
        return
    n_w = len(results)

    def avg(key): return np.mean([r[key] for r in results])
    def nanmean(key):
        vals = [r[key] for r in results if not math.isnan(r[key])]
        return np.mean(vals) if vals else float("nan")

    print(f"\n{'='*60}")
    print(f"  {label}  ({n_w} windows with fills)")
    print(f"{'='*60}")
    print(f"{'Metric':<42} {'8@touch':>10} {'4+4 split':>10}")
    print(f"{'-'*62}")
    print(f"{'P(any fill per event)':<42} {avg('a_any'):>10.3f} {avg('b_any'):>10.3f}")
    print(f"{'E[contracts filled per event]':<42} {avg('e_a_fills'):>10.3f} {avg('e_b_fills'):>10.3f}")
    print(f"{'P(sweep reaches touch-1c)':<42} {avg('p_sweep'):>10.3f} {'same':>10}")
    e_bd = avg('e_bd_fills')
    print(f"{'E[deep-leg contracts filled/event]':<42} {'N/A':>10} {e_bd:>10.3f}")
    cdmo = nanmean('cond_deep_mo')
    print(f"{'E[markout c | deep fill]':<42} {'N/A':>10} {cdmo:>10.2f}")
    print(f"{'E[PnL c per event] (conservative mk=0)':<42} {avg('e_pnl_a'):>10.4f} {avg('e_pnl_b'):>10.4f}")
    print(f"{'-'*62}")
    pnl_diff = avg('e_pnl_b') - avg('e_pnl_a')
    print(f"  PnL delta (split - all-touch): {pnl_diff:+.4f} c/event")
    fill_diff = avg('e_b_fills') - avg('e_a_fills')
    print(f"  Fill-count delta (split - all-touch): {fill_diff:+.4f} contracts/event")
    return dict(
        n_windows=n_w,
        p_sweep=avg('p_sweep'),
        a_any=avg('a_any'), b_any=avg('b_any'),
        e_a_fills=avg('e_a_fills'), e_b_fills=avg('e_b_fills'),
        e_bd_fills=avg('e_bd_fills'), cond_deep_mo=cdmo,
        e_pnl_a=avg('e_pnl_a'), e_pnl_b=avg('e_pnl_b'),
    )


# All windows
all_ws = set(win_fill_records.keys())
res_all  = aggregate(all_ws,   "ALL WINDOWS")

# Deep hours only
res_deep = aggregate(deep_windows & all_ws, "DEEP HOURS (above-median fill volume)")

# ── 5. Verdict ────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  VERDICT")
print("="*60)

if res_all and res_deep:
    p_sw_all  = res_all['p_sweep']
    p_sw_deep = res_deep['p_sweep']
    e_bd_deep = res_deep['e_bd_fills']
    cdmo_deep = res_deep['cond_deep_mo']
    fill_gain = res_deep['e_b_fills'] - res_deep['e_a_fills']
    pnl_gain  = res_deep['e_pnl_b'] - res_deep['e_pnl_a']

    print(f"\n  Sweep rate (all):         {p_sw_all:.1%}")
    print(f"  Sweep rate (deep hours):  {p_sw_deep:.1%}")
    print(f"  Deep-leg E[fills/event]:  {e_bd_deep:.4f} contracts")
    print(f"  Deep-leg cond markout:    {cdmo_deep:.2f} c/contract (on sweep)")
    print(f"  Fill-count gain (split):  {fill_gain:+.4f} contracts/event")
    print(f"  PnL gain (split):         {pnl_gain:+.4f} c/event (markout= -1c model)")
    print()

    if p_sw_deep < 0.05:
        verdict = "WEAK SUPPORT for split: sweep rate too low to generate meaningful deep fills."
    elif e_bd_deep < 0.10 and abs(pnl_gain) < 0.01:
        verdict = "NEUTRAL: deep-leg fills are rare; PnL impact is negligible either way."
    elif pnl_gain > 0:
        verdict = "MARGINAL SUPPORT: split has higher fill count but deep-leg markout is adverse."
    else:
        verdict = "AGAINST split: adverse markout on sweeps makes split worse in expectation."

    print(f"  {verdict}")

print()
print("="*60)
print("  HONEST CAVEATS")
print("="*60)
print("""
  1. QUEUE POSITION PROXY: q_ahead in fills_btc15m is the queue ahead
     of our order *at fill time*, not at placement. For simulating
     back-of-queue at placement we would need placement-time book depth.
     This analysis likely UNDERESTIMATES q_ahead and thus OVERSTATES
     fill probability for both strategies.

  2. TOUCH-1c MARKOUT ON SWEEPS IS MODEL-ASSUMED AT -1c: We have no
     forward-price series at sub-second resolution in these files.
     The -1c figure is a structural prior (you filled deep because the
     market moved against you). Actual adverse selection could be larger.
     Positive markout on sweeps is not impossible but historically
     unlikely for market-order-driven sweep events.

  3. DEEP-HOURS FILTER IS A COARSE PROXY: "above median fill volume"
     is not the same as "post >= 8 contracts traded in the first half
     of the window." The true t27 trigger condition requires intra-window
     volume timing data not available in these aggregated fill records.
     Results should be re-validated when proper intra-window ticks are
     available (ticks_btc15m_*.jsonl has mid-price ticks, not order-flow
     volume splits).
""")
