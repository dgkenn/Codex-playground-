#!/usr/bin/env python3
"""box_sizing_alloc.py -- growth-optimal SIZING + CAPITAL ALLOCATION across the live Kalshi box book.

Answers the recurring "what $/day at $X bankroll" question for the two-market box book:
  KXBTC15M (15-min BTC box, VALIDATED live) + KXBTCD (hourly BTC box, SCREENED).

Models per-box P&L as a MIXTURE (clean box vs toxic strand), derives the growth-optimal
contracts-per-box at $10/$100/$1k under the fill-rate ceiling + loss-limit, allocates capital
across the two (disjoint-settlement) markets, and reports realistic $/day + saturation + ruin.

Inputs (live-validated vs screened are tagged inline). All economics in CENTS/contract unless $.
Self-contained; numpy only. Run: python box_sizing_alloc.py
"""
import numpy as np

rng = np.random.default_rng(7)

# =============================================================================
# 1. INPUTS  (LIVE = measured on origin/live-state; SCREEN = tape/REST screen)
# =============================================================================
# --- KXBTC15M live decomposition (BOX_COMPLETION_EXEC.md: 96 settled mkts, 771 fills) ---
# Balanced (completed) boxes: net ~ +0.0..+0.69c.  Use the clean paired edge the live passive
# boxes actually printed: +0.69c/box (AUDIT_EDGE.md: 62 boxes +0.69c/box; matches/exceeds bktst).
CLEAN_EDGE_15M   = 0.69     # c/box  LIVE (paired/balanced realized)
# Toxic strand fraction. LIVE strand rate 21.9% (==q0~8000 tape). Of stranded windows, ~16/21 toxic.
# But the question asks: per-BOX toxic share. Live ALL-settled toxic share = 31% (the brutal-bar #).
# We model p_toxic on the LIVE distribution. Post-fix (give-cap 0.25 + post-complete freeze 1.5s,
# C1+C2) is EXPECTED to bound the loss AND cut the over-fill strand class (14/16 toxic = over-fills).
P_TOX_15M_LIVE   = 0.31     # LIVE pre-fix per-box toxic share (BRUTAL BAR -- size for THIS)
P_TOX_15M_POSTFX = 0.18     # post-fix expected: C2 removes the over-fill class; residual ~strand rate
# Toxic loss: pre-fix avg -25c/box (naked -50..-61c on tiny boxes). Post-fix BOUNDED by give-cap:
# dispose at <= -25c worst, ~-12..-15c typical. Use bounded mean and worst.
TOX_LOSS_15M_PRE   = -25.0  # c/box  LIVE pre-fix avg stranded
TOX_LOSS_15M_BOUND = -15.0  # c/box  post-fix expected (bounded disposal, BOX_DISPOSAL_EV)
TOX_LOSS_15M_WORST = -25.0  # c/box  post-fix worst single box (give-cap 0.25 = 25c)

# --- KXBTCD hourly box (SCREEN: KALSHI_TENOR_EXPANSION.md, 20 settled hours) ---
CLEAN_EDGE_D     = 1.0      # c/box  SCREEN conservative deploy (median screen +1.5c; 20/20 completed)
# No live strand data. The hourly has 4x window + deeper 2-sided ATM book => LOWER strand than 15M.
# But it is UNVALIDATED. State a haircut assumption: apply 15M-class queue toxicity, discounted.
P_TOX_D_ASSUMED  = 0.12     # ASSUMED (screen says <10%; we haircut UP for queue realism)
TOX_LOSS_D       = -20.0    # c/box  ASSUMED (same bounded-disposal class, slightly worse=longer tenor)

# --- Fill-rate / capacity (the BINDING constraint) ---
# LIVE 15M: taker-print limited, ~6-10 contracts/window fill (live fees: 6 contracts/window observed;
# REST sample min fillable $21 ~= 21-40 contracts at ATM). Doc ceiling: ~$10-27/day gross.
FILL_CEIL_15M    = 10       # contracts/window (LIVE taker-print cap; conservative end of 6-10)
WINDOWS_15M      = 96       # /day (LIVE)
# HOURLY: far deeper (886k contracts/hr, $14k resting). Per-window capacity much higher; the
# screen sized $50-200/window => ~100-400 contracts/window. Cap at a queue-realistic level.
FILL_CEIL_D      = 200      # contracts/window (SCREEN, queue-haircut: << the 886k flow)
WINDOWS_D        = 24       # /day (SCREEN)

# --- Account / risk ---
DAILY_LOSS_LIMIT = 12.0     # $  Stage-A loss-limit (SIZING.md). Shared across markets (one account).
CONTRACT_NOTIONAL = 1.0     # $  a box ties up ~$1 of capital (YES+NO ~ $1 total) per box-contract.

BANKROLLS = [10, 100, 1000]

# =============================================================================
# 2. PER-BOX P&L MIXTURE  -> mean & variance
# =============================================================================
def mixture_stats(clean, p_tox, tox_loss, tox_worst=None):
    """Per-box P&L (cents): clean w.p. (1-p_tox), toxic w.p. p_tox."""
    mean = (1 - p_tox) * clean + p_tox * tox_loss
    ex2  = (1 - p_tox) * clean**2 + p_tox * tox_loss**2
    var  = ex2 - mean**2
    return mean, var, np.sqrt(var)

print("="*78)
print("1-2.  PER-BOX P&L MIXTURE (cents/box)")
print("="*78)
scenarios = {
    "15M LIVE pre-fix (brutal bar)" : (CLEAN_EDGE_15M, P_TOX_15M_LIVE,   TOX_LOSS_15M_PRE),
    "15M post-fix (expected)"       : (CLEAN_EDGE_15M, P_TOX_15M_POSTFX, TOX_LOSS_15M_BOUND),
    "HOURLY KXBTCD (screen+haircut)": (CLEAN_EDGE_D,   P_TOX_D_ASSUMED,  TOX_LOSS_D),
}
stats = {}
for name,(c,p,l) in scenarios.items():
    m,v,s = mixture_stats(c,p,l)
    stats[name] = (m,v,s)
    print(f"  {name:32s} p_tox={p:.0%}  mean={m:+.2f}c  std={s:.1f}c  (clean {c:+.2f}, tox {l:+.0f})")

m15, v15, s15 = stats["15M post-fix (expected)"]
m15pre = stats["15M LIVE pre-fix (brutal bar)"][0]
mD,  vD,  sD  = stats["HOURLY KXBTCD (screen+haircut)"]
print()
print(f"  => 15M post-fix mean {m15:+.2f}c/box  (pre-fix {m15pre:+.2f}c/box -- thin/negative w/o fix)")
print(f"  => HOURLY mean       {mD:+.2f}c/box")

# =============================================================================
# 3. KELLY / FRACTIONAL SIZING  (growth-optimal contracts-per-box)
# =============================================================================
# A box-contract ties ~$1 capital and pays the mixture above. This is NOT classic Kelly (the bet
# isn't "win b / lose 1"); it's a small-mean, fat-negative-tail per-unit return.  Growth rate for
# sizing n contracts/box on bankroll B, per box:  E[log(1 + n*X/B)] where X is per-box $ P&L.
# We maximize over n (integer), capped by the fill-rate ceiling and the loss-limit.
def box_pnl_dollars(clean, p_tox, tox_loss, size):
    """Monte-Carlo per-box $ P&L for `size` contracts (cents->$ /100)."""
    u = rng.random(size if isinstance(size,int) else 1)
    return size * (np.where(rng.random() < p_tox, tox_loss, clean)) / 100.0

def growth_rate(B, n, clean, p_tox, tox_loss, n_boxes_day, trials=20000):
    """Expected daily log-growth E[log(1 + day_pnl/B)] for n contracts/box, n_boxes_day boxes/day."""
    # day P&L = sum over boxes of n * X_box (cents)/100.  Vectorized MC.
    tox = rng.random((trials, n_boxes_day)) < p_tox
    perbox = np.where(tox, tox_loss, clean) * n / 100.0   # $ per box
    day = perbox.sum(axis=1)
    # apply daily loss-limit (stop trading for the day once -limit hit): floor the loss
    day = np.maximum(day, -DAILY_LOSS_LIMIT)
    g = np.log1p(np.clip(day / B, -0.999, None))
    return g.mean(), day.mean(), day.std()

# Loss-limit-implied size cap (Busseti-Ryu-Boyd / SIZING.md): N_max = floor(L/(1.645*sigma_w*sqrt(Nw)))
# Here per-box std in $ = size*s/100; daily std ~ size*s/100*sqrt(boxes). We solve for size cap.
def loss_limit_size_cap(s_cents, n_boxes, L=DAILY_LOSS_LIMIT, z=1.645):
    daily_std_per_contract = (s_cents/100.0) * np.sqrt(n_boxes)
    return max(1, int(np.floor(L / (z * daily_std_per_contract))))

print()
print("="*78)
print("3.  GROWTH-OPTIMAL SIZE per bankroll (15M post-fix), w/ binding-constraint id")
print("="*78)
boxes15_day = 6 * 96 // 10  # ~ boxes/window * windows; live ~3-6 boxes/window. Use fill-limited.
# Fill-limited boxes/day: at size n, contracts/window <= FILL_CEIL. boxes/window ~ FILL_CEIL/(2*n)
# (each box = 1 YES + 1 NO leg of size n). We instead reason in CONTRACTS to keep it concrete.
for B in BANKROLLS:
    # candidate sizes 1..FILL_CEIL (contracts per side per window-ish). Evaluate growth.
    best = None
    cap_fill = FILL_CEIL_15M
    cap_loss = loss_limit_size_cap(s15, WINDOWS_15M)
    cap_bank = max(1, int(B * 1.0 // 1))  # ~$1 capital per contract; need n*windows in flight modest
    for n in range(1, max(2, min(cap_fill, 60))+1):
        g, dmean, dstd = growth_rate(B, n, CLEAN_EDGE_15M/100*100, P_TOX_15M_POSTFX,
                                     TOX_LOSS_15M_BOUND, WINDOWS_15M)
        if best is None or g > best[1]:
            best = (n, g, dmean, dstd)
    n_star = best[0]
    # which constraint binds?
    binds = min([("fill", cap_fill), ("loss-limit", cap_loss), ("bankroll/log-growth", n_star)],
                key=lambda x: x[1])
    print(f"  B=${B:<5d} growth-opt n*={n_star:>2d} c/box | caps: fill={cap_fill} loss-limit={cap_loss} "
          f"| BINDING={binds[0]} (={binds[1]}) | day P&L ${best[2]:+.2f} +/- {best[3]:.2f}")

# =============================================================================
# 4. REALISTIC $/day + SATURATION + TRAJECTORY  (two-market book)
# =============================================================================
print()
print("="*78)
print("4.  REALISTIC $/day  (fill-rate-saturated)")
print("="*78)
# 15M: gross $/day = windows * contracts/window * net_c/box(post-fix) ... but per-box mean is in
# c/box and each "box" = 1 contract pair. contracts/window capped at FILL_CEIL_15M.
def daily_dollars(windows, fill_ceil, mean_c, size):
    contracts = min(size, fill_ceil)              # contracts/window actually fillable
    return windows * contracts * mean_c / 100.0   # $/day

# At saturation each market runs at its fill ceiling:
d15_sat = daily_dollars(WINDOWS_15M, FILL_CEIL_15M, m15, FILL_CEIL_15M)
d15_pre = daily_dollars(WINDOWS_15M, FILL_CEIL_15M, m15pre, FILL_CEIL_15M)
dD_sat  = daily_dollars(WINDOWS_D,  FILL_CEIL_D,  mD,  FILL_CEIL_D)
print(f"  15M post-fix @ ceiling ({FILL_CEIL_15M} c/win x {WINDOWS_15M} win): ${d15_sat:+.2f}/day "
      f"(pre-fix ${d15_pre:+.2f}/day)")
print(f"  HOURLY @ ceiling ({FILL_CEIL_D} c/win x {WINDOWS_D} win, screen): ${dD_sat:+.2f}/day")
print(f"  COMBINED book at saturation: ${d15_sat+dD_sat:+.2f}/day  (disjoint settlement => additive)")
print()
# Capital required to run at ceiling: contracts in flight ~ fill_ceil * (windows concurrently open).
# 15M: ~1-2 windows open at once * 10 c * $1 = ~$10-20 working capital -> saturates ~$100 (doc).
# HOURLY: 1 window open * 200 c * $1 = ~$200 working capital.
cap_sat_15M = FILL_CEIL_15M * 2 * 1.0 * 5   # buffer for settlement lag / multiple open
cap_sat_D   = FILL_CEIL_D   * 1 * 1.0 * 2
print(f"  Working capital to saturate: 15M ~${cap_sat_15M:.0f}, HOURLY ~${cap_sat_D:.0f}; "
      f"book SATURATES ~${cap_sat_15M+cap_sat_D:.0f}")
print()
# Per-bankroll realized (size limited by min(fill, bankroll/contract)):
print("  Per-bankroll $/day (15M only / + hourly):")
for B in BANKROLLS:
    n15 = min(FILL_CEIL_15M, max(1, int(B // 2)))      # ~$2 working capital per c/window (lag buffer)
    d15 = daily_dollars(WINDOWS_15M, FILL_CEIL_15M, m15, n15)
    # hourly only kicks in once bankroll covers its larger per-window size
    nD  = min(FILL_CEIL_D, max(0, int((B - cap_sat_15M) // 2)))
    dD  = daily_dollars(WINDOWS_D, FILL_CEIL_D, mD, nD) if nD>0 else 0.0
    print(f"    B=${B:<5d}: 15M n={n15:>3d} -> ${d15:+.2f}/day | +hourly n={nD:>3d} -> "
          f"${d15+dD:+.2f}/day combined")

# =============================================================================
# 5. RISK OF RUIN  (toxic tail, bounded -25c, loss-limit)
# =============================================================================
print()
print("="*78)
print("5.  RISK OF RUIN / DRAWDOWN  (MC over compounding days)")
print("="*78)
def simulate_path(B0, size15, days=60, paths=4000):
    """Compound daily P&L; ruin = bankroll < $1 (can't fund a box) OR drawdown > 90%."""
    end = np.empty(paths); ruined = 0; maxdd = np.zeros(paths)
    for p in range(paths):
        B = B0; peak = B0; dd = 0.0; dead=False
        for _ in range(days):
            n = min(size15, FILL_CEIL_15M, max(0,int(B//2)))
            if n < 1: dead=True; break
            tox = rng.random(WINDOWS_15M) < P_TOX_15M_POSTFX
            perbox = np.where(tox, TOX_LOSS_15M_BOUND, CLEAN_EDGE_15M) * n / 100.0
            day = perbox.sum()
            day = max(day, -DAILY_LOSS_LIMIT)
            B += day
            peak = max(peak, B); dd = max(dd, (peak-B)/peak)
            if B < 1: dead=True; break
        end[p]=max(B,0); maxdd[p]=dd
        if dead or B < B0*0.10: ruined += 1
    return end, ruined/paths, maxdd

for B in BANKROLLS:
    n15 = min(FILL_CEIL_15M, max(1, int(B // 2)))
    end, ruin, dd = simulate_path(B, n15, days=60, paths=3000)
    print(f"  B=${B:<5d} size={n15:>2d}c/box, 60d: P(ruin<10%bk)={ruin:.1%}  "
          f"median end ${np.median(end):.0f}  p5 ${np.percentile(end,5):.0f}  maxDD p95 {np.percentile(dd,95):.0%}")

# =============================================================================
# 6. BREAK-EVEN SENSITIVITY  (the load-bearing number: what p_tox makes the book +EV)
# =============================================================================
print()
print("="*78)
print("6.  BREAK-EVEN p_tox  (mean per-box P&L = 0)")
print("="*78)
# mean = (1-p)*clean + p*tox = 0  ->  p* = clean/(clean - tox)
for name,(c,p,l) in scenarios.items():
    pstar = c / (c - l)
    print(f"  {name:32s} clean={c:+.2f} tox={l:+.0f} -> BREAK-EVEN p_tox={pstar:.1%} "
          f"(currently {p:.0%} => {'+EV' if p<pstar else 'NEGATIVE'})")
print()
print("  15M needs the fixes to drive p_tox below ~%.0f%% (at tox=-15c) to be +EV." %
      (100*CLEAN_EDGE_15M/(CLEAN_EDGE_15M+15)))
print("  Live pre-fix p_tox=31%% >> break-even => DO NOT scale until live re-test confirms <~4-5%%.")
print()
# What if the fixes hit their TARGET (strand<10%, disposal -12c) -- best realistic case:
mb, vb, sb = mixture_stats(CLEAN_EDGE_15M, 0.10, -12.0)
print(f"  BEST-realistic-case 15M (p_tox=10%%, tox=-12c): mean={mb:+.2f}c/box "
      f"=> ${daily_dollars(WINDOWS_15M, FILL_CEIL_15M, mb, FILL_CEIL_15M):+.2f}/day @ ceiling")
mb4, _, _ = mixture_stats(CLEAN_EDGE_15M, 0.04, -12.0)
print(f"  TARGET-case 15M (p_tox=4%%, tox=-12c): mean={mb4:+.2f}c/box "
      f"=> ${daily_dollars(WINDOWS_15M, FILL_CEIL_15M, mb4, FILL_CEIL_15M):+.2f}/day @ ceiling")

print()
print("DONE. See BOX_SIZING_ALLOC.md for the written verdict + assumptions table.")
