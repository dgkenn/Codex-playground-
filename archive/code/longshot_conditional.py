#!/usr/bin/env python3
"""
Hunt for a high-EV sub-slice of the confirmed longshot short-vol edge.

We SELL far-OTM weekly BTC/ETH longshots (entry YES mid in [0.15,0.30]) on
zero-fee Polymarket. Base seller PnL/contract = (entry - half_spread) - yes_win.

Question: do observable ENTRY-TIME features select a sub-population that is
much more overpriced (2x+ the edge) and still positive at realistic
YES-buy-volume-weighted fills? Discipline: TRAIN (first 60% weeks) picks the
rule, TEST (last 40% weeks) evaluates it ONCE. Count every rule tried.
"""
import json, math, datetime as dt
from collections import defaultdict

ROWS = json.load(open('/home/user/Codex-playground-/scratchpad/advsel_rows.json'))

def pnl(r):
    return (r['entry'] - r['half_spread']) - r['yes_win']

def week_key(ts):
    iso = dt.datetime.utcfromtimestamp(ts).isocalendar()
    return (iso[0], iso[1])

for r in ROWS:
    r['pnl'] = pnl(r)
    r['wk'] = week_key(r['end'])
    r['dow'] = dt.datetime.utcfromtimestamp(r['end']).weekday()  # 0=Mon

# ---- cluster-robust (by week) t-stat for a weighted mean --------------------
def cluster_stats(rows, weight='equal'):
    """Return (mean, cluster_robust_t, n) for weighted mean of pnl, clustered by week.
    weight='equal' -> w=1; else w = row[weight] (e.g. yes_buy_shares)."""
    if not rows:
        return (float('nan'), float('nan'), 0)
    if weight == 'equal':
        w = [1.0]*len(rows)
    else:
        w = [max(r[weight], 0.0) for r in rows]
    W = sum(w)
    if W <= 0:
        return (float('nan'), float('nan'), len(rows))
    beta = sum(wi*r['pnl'] for wi, r in zip(w, rows)) / W
    # cluster scores
    scores = defaultdict(float)
    for wi, r in zip(w, rows):
        scores[r['wk']] += wi*(r['pnl'] - beta)
    G = len(scores)
    ss = sum(s*s for s in scores.values())
    var = ss / (W*W)
    # small-cluster correction
    if G > 1:
        var *= G/(G-1)
    se = math.sqrt(var) if var > 0 else float('nan')
    t = beta/se if se and se == se and se > 0 else float('nan')
    return (beta, t, len(rows))

def worst_week(rows, weight='equal'):
    """Return worst per-week weighted mean pnl (blow-up / tail check)."""
    byw = defaultdict(list)
    for r in rows:
        byw[r['wk']].append(r)
    worst = None; worstwk=None
    for wk, rs in byw.items():
        if weight == 'equal':
            m = sum(r['pnl'] for r in rs)/len(rs)
        else:
            W = sum(max(r[weight],0.0) for r in rs)
            if W<=0: continue
            m = sum(max(r[weight],0.0)*r['pnl'] for r in rs)/W
        if worst is None or m < worst:
            worst = m; worstwk = wk
    return worst, worstwk

# ---- TRAIN / TEST split by time (chronological weeks) -----------------------
weeks_sorted = sorted(set(r['wk'] for r in ROWS))
nw = len(weeks_sorted)
cut = int(round(nw*0.6))
train_weeks = set(weeks_sorted[:cut])
test_weeks = set(weeks_sorted[cut:])
TRAIN = [r for r in ROWS if r['wk'] in train_weeks]
TEST  = [r for r in ROWS if r['wk'] in test_weeks]

def summarize(rows, label):
    e = cluster_stats(rows, 'equal')
    v = cluster_stats(rows, 'yes_buy_shares')
    ww_e = worst_week(rows, 'equal')
    return dict(label=label, n=e[2], eq_mean=e[0], eq_t=e[1],
                bv_mean=v[0], bv_t=v[1], worst_eq=ww_e[0], worst_wk=ww_e[1])

print(f"Weeks total={nw}  train={len(train_weeks)}  test={len(test_weeks)}")
print(f"TRAIN markets={len(TRAIN)}  TEST markets={len(TEST)}\n")

BASE_ALL   = summarize(ROWS, 'BASELINE all')
BASE_TRAIN = summarize(TRAIN, 'BASELINE train')
BASE_TEST  = summarize(TEST,  'BASELINE test')

def fmt(d):
    return (f"n={d['n']:4d}  eq={d['eq_mean']*100:+6.2f}c t={d['eq_t']:5.2f}  "
            f"bv={d['bv_mean']*100:+6.2f}c t={d['bv_t']:5.2f}  "
            f"worstwk={d['worst_eq']*100:+6.1f}c")

print("=== BASELINE (unconditional) ===")
for d in (BASE_ALL, BASE_TRAIN, BASE_TEST):
    print(f"{d['label']:16s} {fmt(d)}")
print()

# =====================================================================
# Define candidate conditioning rules. Each rule = a selector function.
# We build them by tercile thresholds computed ON TRAIN ONLY (no leakage).
# =====================================================================
def tercile_thresholds(rows, key):
    vals = sorted(r[key] for r in rows)
    n=len(vals)
    return vals[n//3], vals[2*n//3]

RULES = []  # (name, selector, direction_desc)

# 1. Retail-demand intensity features: high tercile vs low tercile
for key in ['yes_buy_shares', 'yes_buy_dollars', 'n_yes_buy', 'volume']:
    lo, hi = tercile_thresholds(TRAIN, key)
    RULES.append((f"{key}_HIGH(>={hi:.1f})", (lambda k,h: (lambda r: r[k]>=h))(key,hi)))
    RULES.append((f"{key}_LOW(<={lo:.1f})",  (lambda k,l: (lambda r: r[k]<=l))(key,lo)))

# 2. Entry price sub-band (moneyness)
RULES.append(("entry_0.15-0.20", lambda r: 0.15<=r['entry']<0.20))
RULES.append(("entry_0.20-0.25", lambda r: 0.20<=r['entry']<0.25))
RULES.append(("entry_0.25-0.30", lambda r: 0.25<=r['entry']<=0.30))
RULES.append(("entry_deep<0.225", lambda r: r['entry']<0.225))
RULES.append(("entry_shallow>=0.225", lambda r: r['entry']>=0.225))

# 3. Day-of-week / resolution timing
for d in range(7):
    dn = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d]
    cnt = sum(1 for r in ROWS if r['dow']==d)
    if cnt >= 20:
        RULES.append((f"resolves_{dn}", (lambda dd: (lambda r: r['dow']==dd))(d)))

# 4. Interactions: high demand AND deep OTM
lo_s, hi_s = tercile_thresholds(TRAIN, 'yes_buy_shares')
lo_d, hi_d = tercile_thresholds(TRAIN, 'yes_buy_dollars')
RULES.append(("hi_shares_AND_deep",
              (lambda h: (lambda r: r['yes_buy_shares']>=h and r['entry']<0.225))(hi_s)))
RULES.append(("hi_dollars_AND_deep",
              (lambda h: (lambda r: r['yes_buy_dollars']>=h and r['entry']<0.225))(hi_d)))
RULES.append(("hi_shares_AND_shallow",
              (lambda h: (lambda r: r['yes_buy_shares']>=h and r['entry']>=0.225))(hi_s)))
# demand per dollar of strike distance: shares relative to volume (lottery share)
for r in ROWS:
    r['buy_frac'] = r['yes_buy_dollars']/r['volume'] if r['volume']>0 else 0.0
lo_bf, hi_bf = tercile_thresholds(TRAIN, 'buy_frac')
RULES.append((f"buy_frac_HIGH(>={hi_bf:.3f})", (lambda h:(lambda r:r['buy_frac']>=h))(hi_bf)))
RULES.append((f"buy_frac_LOW(<={lo_bf:.3f})",  (lambda l:(lambda r:r['buy_frac']<=l))(lo_bf)))

N_RULES = len(RULES)

# ---- Evaluate every rule on TRAIN; record lift vs train baseline ------------
results = []
for name, sel in RULES:
    tr = [r for r in TRAIN if sel(r)]
    te = [r for r in TEST if sel(r)]
    if len(tr) < 25:   # need minimal power in train
        continue
    dtr = summarize(tr, name)
    dte = summarize(te, name)
    lift_eq_tr = dtr['eq_mean'] - BASE_TRAIN['eq_mean']
    lift_bv_tr = dtr['bv_mean'] - BASE_TRAIN['bv_mean']
    results.append((name, dtr, dte, lift_eq_tr, lift_bv_tr))

# sort by train buy-vol-weighted mean (the realistic-fill metric)
results.sort(key=lambda x: -x[1]['bv_mean'])

print(f"=== {N_RULES} candidate rules defined; {len(results)} passed n>=25 in train ===\n")
print("--- ALL RULES: TRAIN then TEST (eq=equal-wt, bv=yes-buy-vol-wt) ---")
hdr = f"{'rule':26s} | {'TRAIN':38s} | lift | {'TEST':38s}"
print(hdr); print("-"*len(hdr))
for name, dtr, dte, le, lb in results:
    trs = (f"n={dtr['n']:3d} eq{dtr['eq_mean']*100:+5.1f}(t{dtr['eq_t']:4.1f}) "
           f"bv{dtr['bv_mean']*100:+5.1f}(t{dtr['bv_t']:4.1f})")
    tes = (f"n={dte['n']:3d} eq{dte['eq_mean']*100:+5.1f}(t{dte['eq_t']:4.1f}) "
           f"bv{dte['bv_mean']*100:+5.1f}(t{dte['bv_t']:4.1f})")
    print(f"{name:26s} | {trs:38s} | bv{lb*100:+4.1f} | {tes}")

# ---- Select the single best rule ON TRAIN by realistic-fill criteria --------
# Criterion: maximize TRAIN buy-vol-weighted mean, require it to also beat
# baseline buy-vol EV in train and have bv_t>2. Then evaluate ONCE on TEST.
candidates = [x for x in results
              if x[1]['bv_mean'] > BASE_TRAIN['bv_mean'] and x[1]['bv_t'] > 2.0
              and x[1]['n'] >= 40]
print("\n=== SELECTION (train buy-vol EV > baseline, bv_t>2, n>=40) ===")
if not candidates:
    print("No rule beats baseline buy-vol EV with bv_t>2 in TRAIN.")
    best = None
else:
    candidates.sort(key=lambda x: -x[1]['bv_mean'])
    best = candidates[0]
    name, dtr, dte, le, lb = best
    print(f"SELECTED: {name}")
    print(f"  TRAIN: {fmt(dtr)}  lift_bv={lb*100:+.2f}c  lift_eq={le*100:+.2f}c")
    print(f"  TEST : {fmt(dte)}")
    print(f"  TEST lift vs baseline_test:  eq={ (dte['eq_mean']-BASE_TEST['eq_mean'])*100:+.2f}c"
          f"  bv={ (dte['bv_mean']-BASE_TEST['bv_mean'])*100:+.2f}c")

# ---- Consistency scan: which rules beat baseline at buy-vol in BOTH splits? --
print("\n=== CONSISTENCY: rules with TRAIN bv-lift>+1c AND TEST bv > baseline_test ===")
base_te_bv = BASE_TEST['bv_mean']
survivors = []
for name, dtr, dte, le, lb in results:
    train_lift = dtr['bv_mean'] - BASE_TRAIN['bv_mean']
    test_lift  = dte['bv_mean'] - base_te_bv
    if train_lift > 0.01 and test_lift > 0.0:
        survivors.append((name, train_lift, test_lift))
if survivors:
    for name, tl, te in survivors:
        print(f"  {name:26s} train_bv_lift={tl*100:+.1f}c  test_bv_lift={te*100:+.1f}c")
else:
    print("  NONE. No rule that looks overpriced in train stays overpriced vs")
    print("  baseline in test at buy-vol-weighted fills. Conditioning = noise.")

# Also: do the TEST winners come from TRAIN winners or losers? (overfit tell)
top_test = sorted(results, key=lambda x:-x[2]['bv_mean'])[:5]
print("\n  Top-5 TEST buy-vol rules and what their TRAIN buy-vol lift was:")
for name,dtr,dte,le,lb in top_test:
    print(f"    {name:26s} test_bv={dte['bv_mean']*100:+.1f}c  <- train_bv_lift={lb*100:+.1f}c")

# ---- Save machine-readable summary ------------------------------------------
out = dict(
    n_rules_tried=N_RULES,
    baseline=dict(all=BASE_ALL, train=BASE_TRAIN, test=BASE_TEST),
    rules=[dict(name=n, train=dtr, test=dte, lift_eq_train=le, lift_bv_train=lb)
           for n,dtr,dte,le,lb in results],
    selected=(best[0] if best else None),
)
json.dump(out, open('/home/user/Codex-playground-/scratchpad/longshot_cond_out.json','w'),
          indent=2, default=str)
print("\nsaved scratchpad/longshot_cond_out.json")
