"""pair_rate_study.py -- Kalshi maker-box pairing-rate lever study.

Goal: raise P(both fill) from 0.89 baseline toward 0.98; maximize net c/win.
IS = first 60%, OOS = last 40% of common windows sorted by time.

For every policy we report: P(both), #boxes, mean lock c, net c/win.
Net c/win = mean over active windows (windows with >=1 box or strand).

10 levers:
  COMPLETION:
   1. Immediate 1c improve   (post leg-2 at a0-1c instantly after leg-1)
   2. Escalating improve     (1c immediate, 2c after 3min, 3c after 6min)
   3. Taker-complete give Xc (cross to take at a0-give_c; lock=spread-give_c)
   4. Deadline force T sec   (taker-complete give=1c in last T seconds)
  ENTRY-SELECTION:
   5. Book-depth thin        (completing-side L1 depth < D; overnight_data)
   6. Both-sides thin        (both sides L1 depth < D)
   7. Time-of-window k<=K    (only enter in early part of window)
   8. Flow-balance gate      (|taker_imbal| < threshold)
   9. Volume-churn gate      (vol_k < Xth percentile)
  10. Spread/tilt band       (spread<=3c AND |mid-0.5|<0.35)

COMBINATION: entry + completion PnL-optimal and max-P(both).
"""
import os, sys, gzip, json, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.chdir("/tmp/pair")

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
h = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
t = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")

common = sorted(set(h.index) & set(t.index))
n = len(common)
cut = int(n * 0.6)
is_ws  = set(common[:cut])
oos_ws = set(common[cut:])
print(f"Windows: {n}  IS: {len(is_ws)}  OOS: {len(oos_ws)}")

def arr(x): return np.asarray(x, float)

# ─────────────────────────────────────────────────────────────────────────────
# Load book-depth data (overnight_data for levers 5 & 6)
# ─────────────────────────────────────────────────────────────────────────────
book_dir = "/tmp/pair/overnight_data"
book_depth_avg = {}   # ws -> {yes_ask_depth, no_ask_depth}

if os.path.isdir(book_dir):
    book_files = [f for f in os.listdir(book_dir) if f.endswith(".jsonl.gz")]
    raw_depths = {}
    for fname in book_files:
        try:
            with gzip.open(os.path.join(book_dir, fname), "rt") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        if rec.get("type") != "book":
                            continue
                        ws = rec.get("ws")
                        if ws is None:
                            continue
                        yes_book = rec.get("yes", [])
                        no_book  = rec.get("no", [])
                        # YES ask depth: sum of ask-side sizes (asks = higher prices)
                        # In Kalshi YES book: bids are prices people pay for YES,
                        # asks are prices to buy YES from sellers.
                        # L1 depth proxy: total volume at best ask level
                        def l1_ask_depth(book):
                            asks = [(p, s) for p, s in (x if len(x)==2 else (0,0) for x in book)
                                    if p > 0.5]  # ask side = above mid
                            if not asks:
                                return float("nan")
                            best_ask = min(p for p, s in asks)
                            return sum(s for p, s in asks if p <= best_ask + 0.01)
                        yd = l1_ask_depth(yes_book)
                        nd = l1_ask_depth(no_book)
                        if ws not in raw_depths:
                            raw_depths[ws] = {"y": [], "n": []}
                        if not np.isnan(yd): raw_depths[ws]["y"].append(yd)
                        if not np.isnan(nd): raw_depths[ws]["n"].append(nd)
                    except:
                        pass
        except:
            pass
    for ws, d in raw_depths.items():
        book_depth_avg[ws] = {
            "yes_ask_depth": np.mean(d["y"]) if d["y"] else float("nan"),
            "no_ask_depth":  np.mean(d["n"]) if d["n"] else float("nan"),
        }
    print(f"Book depth windows: {len(book_depth_avg)}")

# Depth thresholds
all_yd = [v["yes_ask_depth"] for v in book_depth_avg.values() if not np.isnan(v["yes_ask_depth"])]
depth_p25 = np.percentile(all_yd, 25) if all_yd else 5.0
depth_p50 = np.percentile(all_yd, 50) if all_yd else 15.0
print(f"Depth thresholds: p25={depth_p25:.1f}  p50={depth_p50:.1f}")

# ─────────────────────────────────────────────────────────────────────────────
# Core replay: extract per-(ws,k) events with full metadata
# ─────────────────────────────────────────────────────────────────────────────
# For each event we compute:
#   baseline: got_b, got_a -> box or strand with PnL
#   improve_complete[improve_c]: can a taker buy/sell complete at a0-improve_c (for YES)?
#   taker_complete[give_c]: same as improve (give_c = improvement from our posted price)
#   timing of completions for deadline lever
#   taker_imbal, vol_k for entry gates

events = []

for ws in common:
    h_row = h.loc[ws]; t_row = t.loc[ws]
    bid  = arr(h_row["bid_path"])
    ask  = arr(h_row["ask_path"])
    vol  = arr(h_row["vol_path"])
    res  = int(h_row["res_up"])

    t_arr   = arr(t_row["t"])
    p_arr   = arr(t_row["p"])
    sz_arr  = arr(t_row["sz"])
    buy_arr = arr(t_row["buy"]).astype(bool)

    split = "IS" if ws in is_ws else "OOS"
    ws_end = ws + 15*60

    for k in range(2, 13):
        b0 = bid[k]; a0 = ask[k]
        if np.isnan(b0) or np.isnan(a0):
            continue
        mid      = (b0 + a0) / 2.0
        spread_c = (a0 - b0) * 100

        if not (0.03 <= mid <= 0.97):
            continue
        # NOTE: we test spread>=1c in baseline but also test no-filter in raw; use it as feature

        # Fill minute k+1
        lo = ws + 60*(k+1); hi = ws + 60*(k+2)
        i0 = int(np.searchsorted(t_arr, lo))
        i1 = int(np.searchsorted(t_arr, hi))

        got_b = got_a = False
        t_bid_fill = t_ask_fill = float("nan")
        for i in range(i0, i1):
            p = float(p_arr[i]); buy = bool(buy_arr[i]); tf = float(t_arr[i])
            if not got_b and not buy and p <= b0 + 1e-9:
                got_b = True; t_bid_fill = tf
            if not got_a and buy and p >= a0 - 1e-9:
                got_a = True; t_ask_fill = tf
            if got_b and got_a:
                break

        # Prior-minute flow balance
        pl = ws + 60*k; ph = ws + 60*(k+1)
        pi0 = int(np.searchsorted(t_arr, pl)); pi1 = int(np.searchsorted(t_arr, ph))
        bv = sv = 0.0
        for i in range(pi0, pi1):
            sz = float(sz_arr[i]); buy = bool(buy_arr[i])
            if buy: bv += sz
            else: sv += sz
        taker_imbal = abs(bv - sv) / max(bv + sv, 1.0)

        # Volume at k-slot
        vol_k = float(vol[k]) if not np.isnan(vol[k]) else 0.0

        # Completion search for YES-strand (need taker BUY at a0 - improve_c)
        # and NO-strand (need taker SELL at b0 + improve_c)
        # For "completion-improve": improve_c in {1,2,3}c = lower our ask (yes) or raise our bid (no)
        # to attract more completions. Lock = spread - improve_c
        # We search ALL remaining trades in the window (starting from fill minute i0)
        IMPROVE = [1, 2, 3]

        # Pre-search completions for YES-strand (taker BUY at >= a0 - ic/100)
        ycomp = {}  # ic -> (t_fill, price) or None
        ncomp = {}  # ic -> (t_fill, price) or None
        for ic in IMPROVE:
            a_prime = a0 - ic / 100.0
            b_prime = b0 + ic / 100.0
            yc = nc = None
            for i_s in range(i0, len(t_arr)):
                if t_arr[i_s] >= ws_end:
                    break
                p_s = float(p_arr[i_s]); buy_s = bool(buy_arr[i_s]); tf_s = float(t_arr[i_s])
                if yc is None and buy_s and p_s >= a_prime - 1e-9:
                    yc = (tf_s, p_s)
                if nc is None and not buy_s and p_s <= b_prime + 1e-9:
                    nc = (tf_s, p_s)
                if yc is not None and nc is not None:
                    break
            ycomp[ic] = yc
            ncomp[ic] = nc

        ev = {
            "ws": ws, "split": split, "k": k,
            "b0": b0, "a0": a0, "mid": mid, "spread_c": spread_c,
            "res": res,
            "got_b": got_b, "got_a": got_a,
            "t_bid_fill": t_bid_fill, "t_ask_fill": t_ask_fill,
            "taker_imbal": taker_imbal, "vol_k": vol_k,
            "ycomp": ycomp, "ncomp": ncomp,
        }
        events.append(ev)

print(f"Events extracted: {len(events)}")

# ─────────────────────────────────────────────────────────────────────────────
# Compute baseline PnL fields for each event
# ─────────────────────────────────────────────────────────────────────────────
def baseline_pnl(ev):
    b0, a0, res = ev["b0"], ev["a0"], ev["res"]
    gb, ga = ev["got_b"], ev["got_a"]
    is_box    = gb and ga
    is_strand = (gb and not ga) or (ga and not gb)
    lock_c    = (a0 - b0) * 100 if is_box else float("nan")
    if gb and not ga:
        strand_pnl_c = (res - b0) * 100
    elif ga and not gb:
        strand_pnl_c = (a0 - res) * 100
    else:
        strand_pnl_c = float("nan")
    return is_box, is_strand, lock_c, strand_pnl_c

for ev in events:
    ev["is_box"], ev["is_strand"], ev["lock_c"], ev["strand_pnl_c"] = baseline_pnl(ev)

# ─────────────────────────────────────────────────────────────────────────────
# Policy evaluation engine
# ─────────────────────────────────────────────────────────────────────────────
def eval_policy(evs, label=""):
    """Evaluate a list of events (each must have is_box, is_strand, lock_c, strand_pnl_c, ws).
    Returns dict with P(both), #boxes, #strands, mean_lock_c, net_c/win.
    net_c/win = mean per active window (windows with >=1 box or strand event).
    """
    n_box = n_strand = 0
    lock_sum = lock_cnt = 0
    ws_pnl = {}
    for ev in evs:
        wb, ws_ = ev["is_box"], ev["is_strand"]
        if not wb and not ws_:
            continue
        w = ev["ws"]
        if w not in ws_pnl:
            ws_pnl[w] = 0.0
        if wb:
            n_box += 1
            ws_pnl[w] += ev["lock_c"]
            lock_sum += ev["lock_c"]
            lock_cnt += 1
        elif ws_:
            n_strand += 1
            ws_pnl[w] += ev["strand_pnl_c"]
    n_total = n_box + n_strand
    p_both  = n_box / n_total if n_total > 0 else float("nan")
    ml      = lock_sum / lock_cnt if lock_cnt > 0 else float("nan")
    nc      = np.mean(list(ws_pnl.values())) if ws_pnl else float("nan")
    return {
        "label": label,
        "p_both": round(p_both, 4),
        "n_boxes": n_box, "n_strands": n_strand, "n_total": n_total,
        "n_windows": len(ws_pnl),
        "mean_lock_c": round(ml, 2),
        "net_c_win": round(nc, 3),
    }

def split_eval(evs_all, mod_fn=None, label=""):
    """Apply optional mod_fn (transforms event list), then split IS/OOS."""
    evs = mod_fn(evs_all) if mod_fn else evs_all
    is_evs  = [e for e in evs if e["split"] == "IS"]
    oos_evs = [e for e in evs if e["split"] == "OOS"]
    return {
        "label": label,
        "is":  eval_policy(is_evs,  f"{label}_IS"),
        "oos": eval_policy(oos_evs, f"{label}_OOS"),
    }

# ─────────────────────────────────────────────────────────────────────────────
# BASELINE
# ─────────────────────────────────────────────────────────────────────────────
active_evs = [e for e in events if e["is_box"] or e["is_strand"]]

baseline = split_eval(active_evs, label="BASELINE")
b_is  = baseline["is"]
b_oos = baseline["oos"]

print(f"\n{'='*70}")
print("BASELINE (no levers)")
print(f"{'='*70}")
for r in [b_is, b_oos]:
    print(f"  {r['label']}: P(both)={r['p_both']:.4f}  #boxes={r['n_boxes']}  "
          f"#strands={r['n_strands']}  mean_lock={r['mean_lock_c']:.2f}c  "
          f"net_c/win={r['net_c_win']:.3f}c  n_windows={r['n_windows']}")

# ─────────────────────────────────────────────────────────────────────────────
# Helper: apply completion improve to an event (mutate copy)
# ─────────────────────────────────────────────────────────────────────────────
def apply_improve_to_ev(ev, improve_c, min_lock_c=0, t_earliest=None):
    """Try to complete a strand by posting at improved price.
    YES-strand: post ask at a0-improve_c; lock = spread - improve_c
    NO-strand:  post bid at b0+improve_c; lock = spread - improve_c
    t_earliest: if set, only use completions that arrive after this time.
    Returns new event dict (copy) with updated fields.
    """
    ne = dict(ev)
    if not ev["is_strand"]:
        return ne
    b0, a0, res = ev["b0"], ev["a0"], ev["res"]
    spread_c = ev["spread_c"]
    lock_new = spread_c - improve_c

    if lock_new < min_lock_c:
        return ne  # below floor

    if ev["got_b"] and not ev["got_a"]:
        # YES-strand -> try YES ask completion at a0 - improve_c
        yc = ev["ycomp"].get(improve_c)
        if yc is not None:
            t_fill, _ = yc
            if t_earliest is None or t_fill >= t_earliest:
                ne = dict(ev)
                ne["is_box"]       = True
                ne["is_strand"]    = False
                ne["lock_c"]       = lock_new
                ne["strand_pnl_c"] = float("nan")
    elif ev["got_a"] and not ev["got_b"]:
        # NO-strand -> try NO bid completion at b0 + improve_c
        nc = ev["ncomp"].get(improve_c)
        if nc is not None:
            t_fill, _ = nc
            if t_earliest is None or t_fill >= t_earliest:
                ne = dict(ev)
                ne["is_box"]       = True
                ne["is_strand"]    = False
                ne["lock_c"]       = lock_new
                ne["strand_pnl_c"] = float("nan")
    return ne

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 1: Immediate 1c improve
# ─────────────────────────────────────────────────────────────────────────────
def l1_mod(evs):
    return [apply_improve_to_ev(e, 1) for e in evs]

r1 = split_eval(active_evs, l1_mod, "L1_immediate_1c_improve")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 2: Escalating improve
# ─────────────────────────────────────────────────────────────────────────────
def l2_mod(evs):
    out = []
    for e in evs:
        if not e["is_strand"]:
            out.append(e); continue
        ws_val = e["ws"]; k = e["k"]
        t_strand_start = ws_val + 60*(k+1)   # start of fill minute
        ne = e
        # Try 1c immediately
        ne = apply_improve_to_ev(ne, 1)
        if ne["is_box"]:
            out.append(ne); continue
        # Try 2c after 3min
        ne2 = apply_improve_to_ev(e, 2, t_earliest=t_strand_start + 3*60)
        if ne2["is_box"]:
            out.append(ne2); continue
        # Try 3c after 6min
        ne3 = apply_improve_to_ev(e, 3, t_earliest=t_strand_start + 6*60)
        out.append(ne3)
    return out

r2 = split_eval(active_evs, l2_mod, "L2_escalating_improve")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 3: Taker-complete with lock floor
# Cross spread to take at (a0 - give_c); lock = spread - give_c
# give_c = how many cents we sacrifice from our spread to guarantee fill
# At give_c=0: only cross if fill exists at a0 (passive, same as baseline)
# At give_c=1: accept 1c lower price; 2c -> 2c lower, etc.
# ─────────────────────────────────────────────────────────────────────────────
def l3_mod(evs, give_c):
    return [apply_improve_to_ev(e, give_c) for e in evs]

r3 = {}
for give_c in [1, 2, 3]:
    r3[give_c] = split_eval(active_evs,
                             lambda evs, gc=give_c: l3_mod(evs, gc),
                             f"L3_taker_give{give_c}c")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 4: Deadline force-complete (last T sec, give=1c)
# ─────────────────────────────────────────────────────────────────────────────
def l4_mod(evs, T_sec, give_c=1):
    out = []
    for e in evs:
        if not e["is_strand"]:
            out.append(e); continue
        ws_val = e["ws"]
        deadline = ws_val + 15*60 - T_sec
        ne = apply_improve_to_ev(e, give_c, t_earliest=deadline)
        out.append(ne)
    return out

r4 = {}
for T in [30, 60, 90, 120]:
    r4[T] = split_eval(active_evs,
                        lambda evs, T_=T: l4_mod(evs, T_),
                        f"L4_deadline_{T}s")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 5: Book-depth thin (completing side)
# ─────────────────────────────────────────────────────────────────────────────
def l5_mod(evs, depth_thresh):
    out = []
    for e in evs:
        ws_val = e["ws"]
        if ws_val not in book_depth_avg:
            out.append(e); continue  # no data -> keep
        d = book_depth_avg[ws_val]
        if e["is_strand"]:
            # For strands: check if the completing side is thin (already happened, so gate is moot)
            # For entry gate: check completing side depth at entry
            if e["got_b"] and not e["got_a"]:
                depth = d["yes_ask_depth"]  # YES ask = what we need to complete
            else:
                depth = d["no_ask_depth"]
        else:
            # For boxes: check both sides
            depth = max(d["yes_ask_depth"], d["no_ask_depth"])
        if np.isnan(depth) or depth < depth_thresh:
            out.append(e)
    return out

r5 = {}
for thresh in [depth_p25, depth_p50]:
    r5[thresh] = split_eval(active_evs,
                              lambda evs, th=thresh: l5_mod(evs, th),
                              f"L5_depth_thin_{thresh:.0f}")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 6: Both-sides thin
# ─────────────────────────────────────────────────────────────────────────────
def l6_mod(evs, depth_thresh):
    out = []
    for e in evs:
        ws_val = e["ws"]
        if ws_val not in book_depth_avg:
            out.append(e); continue
        d = book_depth_avg[ws_val]
        yd = d["yes_ask_depth"]; nd = d["no_ask_depth"]
        if (np.isnan(yd) or yd < depth_thresh) and (np.isnan(nd) or nd < depth_thresh):
            out.append(e)
    return out

r6 = {}
for thresh in [depth_p25, depth_p50]:
    r6[thresh] = split_eval(active_evs,
                              lambda evs, th=thresh: l6_mod(evs, th),
                              f"L6_both_thin_{thresh:.0f}")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 7: Time-of-window gate (k <= K)
# ─────────────────────────────────────────────────────────────────────────────
r7 = {}
for K in [5, 7, 9]:
    r7[K] = split_eval(active_evs,
                        lambda evs, K_=K: [e for e in evs if e["k"] <= K_],
                        f"L7_k_le_{K}")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 8: Flow-balance gate (|taker_imbal| < threshold)
# ─────────────────────────────────────────────────────────────────────────────
r8 = {}
for thresh in [0.20, 0.35, 0.50]:
    r8[thresh] = split_eval(active_evs,
                              lambda evs, th=thresh: [e for e in evs if e["taker_imbal"] <= th],
                              f"L8_flow_bal_{int(thresh*100)}pct")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 9: Volume-churn gate
# ─────────────────────────────────────────────────────────────────────────────
vols = [e["vol_k"] for e in active_evs]
vol_p25 = np.percentile(vols, 25); vol_p50 = np.percentile(vols, 50)
vol_p75 = np.percentile(vols, 75)

r9 = {}
for pct, thresh in [(25, vol_p25), (50, vol_p50), (75, vol_p75)]:
    r9[pct] = split_eval(active_evs,
                          lambda evs, th=thresh: [e for e in evs if e["vol_k"] <= th],
                          f"L9_vol_gate_p{pct}")

# ─────────────────────────────────────────────────────────────────────────────
# LEVER 10: Spread/tilt band
# ─────────────────────────────────────────────────────────────────────────────
r10 = {}
for (max_sp, max_tilt) in [(3, 0.30), (3, 0.40), (4, 0.35)]:
    key = f"{max_sp}c_t{int(max_tilt*100)}"
    r10[key] = split_eval(
        active_evs,
        lambda evs, ms=max_sp, mt=max_tilt: [
            e for e in evs if e["spread_c"] <= ms and abs(e["mid"] - 0.5) <= mt
        ],
        f"L10_sp{max_sp}c_tilt{int(max_tilt*100)}")

# ─────────────────────────────────────────────────────────────────────────────
# COMBINATION POLICIES
# ─────────────────────────────────────────────────────────────────────────────
def combo_pnl_opt(evs):
    """PnL-optimal: k<=9, spread<=3c, imbal<=0.35, then 1c improve completion."""
    filtered = [e for e in evs
                if e["k"] <= 9 and e["spread_c"] <= 3 and e["taker_imbal"] <= 0.35]
    return [apply_improve_to_ev(e, 1) for e in filtered]

def combo_max_pboth(evs):
    """Max P(both): k<=7, spread<=2c, imbal<=0.20, then 2c improve completion."""
    filtered = [e for e in evs
                if e["k"] <= 7 and e["spread_c"] <= 2 and e["taker_imbal"] <= 0.20]
    return [apply_improve_to_ev(e, 2) for e in filtered]

def combo_full(evs):
    """Full combination: k<=9, spread<=3c, imbal<=0.35, depth p50 thin, then 1c+deadline."""
    filtered = [e for e in evs
                if e["k"] <= 9 and e["spread_c"] <= 3 and e["taker_imbal"] <= 0.35]
    # Apply 1c improve
    step1 = [apply_improve_to_ev(e, 1) for e in filtered]
    # Then deadline force at 2c in last 60s for remaining strands
    return l4_mod(step1, 60, give_c=2)

r_combo_pnl  = split_eval(active_evs, combo_pnl_opt,  "COMBO_PnL_Optimal")
r_combo_max  = split_eval(active_evs, combo_max_pboth, "COMBO_Max_P(both)")
r_combo_full = split_eval(active_evs, combo_full,      "COMBO_Full")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY TABLE
# ─────────────────────────────────────────────────────────────────────────────
def fmt_row(label, oos, b_oos):
    p    = oos["p_both"]; nb = oos["n_boxes"]; lk = oos["mean_lock_c"]; nc = oos["net_c_win"]
    dp   = p - b_oos["p_both"]
    dnc  = nc - b_oos["net_c_win"]
    stars = "***" if dp > 0.02 else ("**" if dp > 0.01 else ("*" if dp > 0.005 else ""))
    return (label, p, nb, lk, nc, dp, dnc, stars)

rows = []
for tag, r in [
    ("L1_immediate_1c", r1),
    ("L2_escalating",   r2),
]:
    rows.append(fmt_row(tag, r["oos"], b_oos))

for gc, r in sorted(r3.items()):
    rows.append(fmt_row(f"L3_taker_give{gc}c", r["oos"], b_oos))

for T, r in sorted(r4.items()):
    rows.append(fmt_row(f"L4_deadline_{T}s", r["oos"], b_oos))

for th, r in sorted(r5.items()):
    rows.append(fmt_row(f"L5_depth_thin_{th:.0f}", r["oos"], b_oos))

for th, r in sorted(r6.items()):
    rows.append(fmt_row(f"L6_both_thin_{th:.0f}", r["oos"], b_oos))

for K, r in sorted(r7.items()):
    rows.append(fmt_row(f"L7_k_le_{K}", r["oos"], b_oos))

for th, r in sorted(r8.items()):
    rows.append(fmt_row(f"L8_flow_bal_{int(th*100)}pct", r["oos"], b_oos))

for pct, r in sorted(r9.items()):
    rows.append(fmt_row(f"L9_vol_p{pct}", r["oos"], b_oos))

for key, r in sorted(r10.items()):
    rows.append(fmt_row(f"L10_{key}", r["oos"], b_oos))

# Sort by net_c_win descending
rows_sorted = sorted(rows, key=lambda x: x[4], reverse=True)

print(f"\n{'='*100}")
print("FULL LEVER TABLE (OOS)")
print(f"{'='*100}")
print(f"{'Lever':<35} {'P(both)':>8} {'#boxes':>7} {'lock_c':>7} {'net_c/w':>9} {'dP':>8} {'dNet':>8} {'sig':>5}")
print("-"*100)
print(f"{'BASELINE':<35} {b_oos['p_both']:>8.4f} {b_oos['n_boxes']:>7} "
      f"{b_oos['mean_lock_c']:>7.2f} {b_oos['net_c_win']:>9.3f}")
print("-"*100)
for label, p, nb, lk, nc, dp, dnc, stars in rows_sorted:
    print(f"{label:<35} {p:>8.4f} {nb:>7} {lk:>7.2f} {nc:>9.3f} "
          f"{dp:>+8.4f} {dnc:>+8.3f} {stars:>5}")

print()
print("COMBINATIONS:")
for r in [r_combo_pnl, r_combo_max, r_combo_full]:
    oo = r["oos"]
    print(f"  {r['label']:<35} P(both)={oo['p_both']:.4f}  #boxes={oo['n_boxes']}  "
          f"lock={oo['mean_lock_c']:.2f}c  net_c/win={oo['net_c_win']:.3f}c")

# ─────────────────────────────────────────────────────────────────────────────
# RANKED TABLE (for PAIR_RATE.md)
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("RANKED 10-LEVER TABLE (OOS, one best variant per lever)")
print(f"{'='*80}")

# Pick best OOS net_c/win variant for each numbered lever
lever_best = {}
for label, p, nb, lk, nc, dp, dnc, stars in rows:
    lever_num = label.split("_")[0]  # L1, L2, etc.
    if lever_num not in lever_best or nc > lever_best[lever_num][4]:
        lever_best[lever_num] = (label, p, nb, lk, nc, dp, dnc, stars)

print(f"{'Lever':<35} {'P(both)OOS':>11} {'net_c/win':>10} {'#boxes':>7} {'dP':>8} {'dNet':>8}")
print("-"*80)
print(f"{'BASELINE':<35} {b_oos['p_both']:>11.4f} {b_oos['net_c_win']:>10.3f} {b_oos['n_boxes']:>7}")
for num in ["L1","L2","L3","L4","L5","L6","L7","L8","L9","L10"]:
    if num in lever_best:
        label, p, nb, lk, nc, dp, dnc, stars = lever_best[num]
        print(f"{label:<35} {p:>11.4f} {nc:>10.3f} {nb:>7} {dp:>+8.4f} {dnc:>+8.3f}")

# ─────────────────────────────────────────────────────────────────────────────
# FINAL NUMBERS FOR REPORT
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("KEY NUMBERS FOR PAIR_RATE.md")
print(f"{'='*70}")
print(f"Baseline IS:  P(both)={b_is['p_both']:.4f}  net_c/win={b_is['net_c_win']:.3f}c  "
      f"#boxes={b_is['n_boxes']}  #strands={b_is['n_strands']}")
print(f"Baseline OOS: P(both)={b_oos['p_both']:.4f}  net_c/win={b_oos['net_c_win']:.3f}c  "
      f"#boxes={b_oos['n_boxes']}  #strands={b_oos['n_strands']}")

print(f"\nCombo PnL-Optimal:")
print(f"  IS:  P(both)={r_combo_pnl['is']['p_both']:.4f}  net={r_combo_pnl['is']['net_c_win']:.3f}c  "
      f"#boxes={r_combo_pnl['is']['n_boxes']}")
print(f"  OOS: P(both)={r_combo_pnl['oos']['p_both']:.4f}  net={r_combo_pnl['oos']['net_c_win']:.3f}c  "
      f"#boxes={r_combo_pnl['oos']['n_boxes']}")

print(f"\nCombo Max-P(both):")
print(f"  IS:  P(both)={r_combo_max['is']['p_both']:.4f}  net={r_combo_max['is']['net_c_win']:.3f}c  "
      f"#boxes={r_combo_max['is']['n_boxes']}")
print(f"  OOS: P(both)={r_combo_max['oos']['p_both']:.4f}  net={r_combo_max['oos']['net_c_win']:.3f}c  "
      f"#boxes={r_combo_max['oos']['n_boxes']}")

print(f"\nCombo Full:")
print(f"  IS:  P(both)={r_combo_full['is']['p_both']:.4f}  net={r_combo_full['is']['net_c_win']:.3f}c  "
      f"#boxes={r_combo_full['is']['n_boxes']}")
print(f"  OOS: P(both)={r_combo_full['oos']['p_both']:.4f}  net={r_combo_full['oos']['net_c_win']:.3f}c  "
      f"#boxes={r_combo_full['oos']['n_boxes']}")

# ─────────────────────────────────────────────────────────────────────────────
# Additional analysis: strand timing and give tradeoff
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("STRAND ANALYSIS")
print(f"{'='*70}")
strands_oos = [e for e in active_evs if e["split"] == "OOS" and e["is_strand"]]
yes_strands = [e for e in strands_oos if e["got_b"] and not e["got_a"]]
no_strands  = [e for e in strands_oos if e["got_a"] and not e["got_b"]]
print(f"OOS strands: {len(strands_oos)}  YES: {len(yes_strands)}  NO: {len(no_strands)}")

yes_pnl = [e["strand_pnl_c"] for e in yes_strands]
no_pnl  = [e["strand_pnl_c"] for e in no_strands]
print(f"YES strand mean PnL: {np.mean(yes_pnl):.2f}c  NO strand mean PnL: {np.mean(no_pnl):.2f}c")

# Improve completion rates by give_c
print("\nCompletion rate and mean lock by improve_c (OOS strands):")
for ic in [1, 2, 3]:
    yes_compl = sum(1 for e in yes_strands if e["ycomp"].get(ic) is not None)
    no_compl  = sum(1 for e in no_strands  if e["ncomp"].get(ic) is not None)
    yes_locks = [e["spread_c"] - ic for e in yes_strands if e["ycomp"].get(ic) is not None]
    no_locks  = [e["spread_c"] - ic for e in no_strands  if e["ncomp"].get(ic) is not None]
    yr = yes_compl/max(len(yes_strands),1); nr = no_compl/max(len(no_strands),1)
    yl = np.mean(yes_locks) if yes_locks else float("nan")
    nl = np.mean(no_locks) if no_locks else float("nan")
    print(f"  give/improve={ic}c: YES {yes_compl}/{len(yes_strands)}={yr:.1%} lock={yl:.2f}c | "
          f"NO {no_compl}/{len(no_strands)}={nr:.1%} lock={nl:.2f}c")

print("\nDone.")
