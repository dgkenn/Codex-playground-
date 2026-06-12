"""Counterparty-avoidance deep dive. Targets MARKOUT<0 (adverse selection), not per-leg settle.
Adds the NEW take-size feature (size of the crossing taker that caused each fill). IS/OOS 60/40 by ws.
Compact output only."""
import numpy as np, pandas as pd
from box_policy_ab import _vpin_buckets, _vpin_at, tox_p as box_tox_p

np.seterr(all="ignore")

def collect_fills_plus(hist, tap, q0=0.0):
    """collect_fills + take_size(crossing taker sz) + vpin + microprice proxy, per fill."""
    common = sorted(set(hist.index) & set(tap.index))
    recs = []
    for w in common:
        h = hist.loc[w]; t = tap.loc[w]
        res = float(h.res_up)
        bid = np.asarray(h.bid_path, float); ask = np.asarray(h.ask_path, float)
        mid = np.asarray(h.mid_path, float); spot = np.asarray(h.spot_path, float)
        spot_l = np.concatenate([[np.nan], spot[:-1]])
        t_arr = np.asarray(t.t, float); p_arr = np.asarray(t.p, float)
        sz_arr = np.asarray(t.sz, float); buy_arr = np.asarray(t.buy, bool)
        bt, bi = _vpin_buckets(t_arr, sz_arr, buy_arr)
        for k in range(2, 13):
            b0, a0, m0 = bid[k], ask[k], mid[k]
            if np.isnan(b0) or np.isnan(a0) or not (0.03 <= m0 <= 0.97):
                continue
            s_now, s_then = spot_l[k], spot_l[max(k - 3, 0)]
            mv = (s_now / s_then - 1) * 1e4 if (s_now > 0 and s_then > 0) else 0.0
            m_next = mid[k + 1] if (k + 1 < 15 and not np.isnan(mid[k + 1])) else m0
            spread = a0 - b0; tau = (15 - k) / 15.0
            # microprice proxy: where is mid vs touch (size-weighted lean unavailable -> use mid-in-spread)
            micro = (m0 - b0) / spread if spread > 1e-9 else 0.5    # 0=at bid,1=at ask
            pl, ph = w + 60 * (k - 1), w + 60 * k
            pj0, pj1 = np.searchsorted(t_arr, pl), np.searchsorted(t_arr, ph)
            flow = float(np.sum(np.where(buy_arr[pj0:pj1], sz_arr[pj0:pj1], -sz_arr[pj0:pj1]))) / 1000.0
            lo, hi = w + 60 * (k + 1), w + 60 * (k + 2)
            i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
            qb = qa = q0; done_b = done_a = False
            for i in range(i0, i1):
                if done_b and done_a: break
                p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
                if not done_b and not buy and p <= b0 + 1e-9:
                    if qb >= sz: qb -= sz
                    else:
                        v = _vpin_at(bt, bi, t_arr[i])
                        recs.append((w, "bid", b0, res - b0, (m_next - b0), mv, spread, tau, flow,
                                     sz, v, micro)); done_b = True
                if not done_a and buy and p >= a0 - 1e-9:
                    if qa >= sz: qa -= sz
                    else:
                        v = _vpin_at(bt, bi, t_arr[i])
                        recs.append((w, "ask", a0, a0 - res, (a0 - m_next), -mv, spread, tau, -flow,
                                     sz, v, 1.0 - micro)); done_a = True
    return pd.DataFrame(recs, columns=["ws","side","p","settle","markout","sig_adv","spread","tau",
                                       "flow_adv","take_size","vpin","micro"])

def auc(label, score):
    label = np.asarray(label, bool); score = np.asarray(score, float)
    m = ~np.isnan(score); label, score = label[m], score[m]
    n1 = label.sum(); n0 = len(label) - n1
    if n1 == 0 or n0 == 0: return np.nan
    order = np.argsort(score); ranks = np.empty(len(score)); ranks[order] = np.arange(1, len(score) + 1)
    # average ties
    s_sorted = score[order]
    i = 0
    while i < len(s_sorted):
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]: j += 1
        if j > i:
            avg = (i + 1 + j + 1) / 2.0
            ranks[order[i:j+1]] = avg
        i = j + 1
    return (ranks[label].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)

def fit_logit(X, y, l2=1.0, iters=300):
    X = np.asarray(X, float); y = np.asarray(y, float)
    mu = X.mean(0); sd = X.std(0); sd[sd < 1e-9] = 1.0
    Xs = (X - mu) / sd
    Xs = np.column_stack([np.ones(len(Xs)), Xs])
    w = np.zeros(Xs.shape[1])
    for _ in range(iters):
        z = Xs @ w; p = 1 / (1 + np.exp(-z)); p = np.clip(p, 1e-6, 1 - 1e-6)
        g = Xs.T @ (p - y) + l2 * np.r_[0, w[1:]]
        W = p * (1 - p)
        H = Xs.T @ (Xs * W[:, None]) + l2 * np.diag(np.r_[0, np.ones(Xs.shape[1]-1)])
        try: w = w - np.linalg.solve(H, g)
        except np.linalg.LinAlgError: break
    return w, mu, sd

def pred_logit(w, mu, sd, X):
    Xs = (np.asarray(X, float) - mu) / sd
    Xs = np.column_stack([np.ones(len(Xs)), Xs])
    return 1 / (1 + np.exp(-np.clip(Xs @ w, -30, 30)))

# ---------------- load ----------------
hist = pd.read_parquet("hist_kalshi_btc15m.parquet").set_index("ws")
tap = pd.read_parquet("trades_kalshi_btc15m.parquet").set_index("ws")
df = collect_fills_plus(hist, tap, 0.0)
df["vpin"] = df.vpin.fillna(df.vpin.median())   # 97 NaN (early-window, no buckets yet)
df["abs_p05"] = np.abs(df.p - 0.5)
df["tox"] = (df.markout < 0).astype(int)
n = len(df)
wins = np.sort(df.ws.unique()); cut = wins[int(len(wins) * 0.6)]
IS = (df.ws < cut).to_numpy(); OOS = ~IS

print(f"=== DATA: {n} fills, {df.ws.nunique()} windows | IS {IS.sum()} / OOS {OOS.sum()} (60/40 by ws) ===")
print(f"take_size: median {df.take_size.median():.0f}, q90 {df.take_size.quantile(.9):.0f}, "
      f"frac>=50 {(df.take_size>=50).mean():.3f}, frac 1-11 {((df.take_size>=1)&(df.take_size<=11)).mean():.3f}")

# ---------------- 1. PRIZE ----------------
print("\n=== 1. PRIZE (markout adverse-selection drag; settle is box mechanics, reported for context) ===")
def prize(mask, tag):
    d = df[mask]
    tot_mk = d.markout.sum() * 100; frac_neg = (d.markout < 0).mean()
    print(f"  {tag}: fills {len(d)}  P(mk<0) {frac_neg:.3f}  mean mk {d.markout.mean()*100:+.3f}c  "
          f"total mk {tot_mk:+.1f}c  mean settle {d.settle.mean()*100:+.2f}c")
prize(np.ones(n, bool), "ALL ")
prize(IS, "IS  "); prize(OOS, "OOS ")
# drag from the toxic (mk<0) fills only = the avoidable pool; realistic prize avoids a FRACTION of it
neg = df.markout < 0
print(f"  toxic pool (mk<0): {neg.sum()} fills carry {df.markout[neg].sum()*100:+.1f}c; "
      f"good (mk>0) {(~neg).sum()} fills give {df.markout[~neg].sum()*100:+.1f}c")
# stranding: a fill never pairs within its window/side. Approx: window with net YES!=NO -> unpaired legs.
def strand_drag(d):
    drag = 0.0; nstr = 0
    for w, g in d.groupby("ws"):
        nb = (g.side == "bid").sum(); na = (g.side == "ask").sum()
        unp = abs(nb - na)
        if unp:
            # the marginal (last) legs on the heavier side are stranded; their markout is the risk
            heavy = "bid" if nb > na else "ask"
            legs = g[g.side == heavy]
            drag += legs.markout.tail(unp).sum(); nstr += unp
    return nstr, drag * 100
ns, sd_ = strand_drag(df)
print(f"  STRANDING: {ns} unpaired legs ({ns/n:.3f} of fills); their markout drag {sd_:+.1f}c "
      f"(directional risk, not box-hedged)")

# ---------------- 2. FEATURE RANKING (AUC for predicting mk<0, OOS) ----------------
print("\n=== 2. FEATURE-AUC for P(markout<0), OOS half ===")
feats = {"take_size": df.take_size, "vpin": df.vpin, "flow_adv": df.flow_adv.abs(),
         "sig_adv": df.sig_adv, "abs_p05": df.abs_p05, "spread": df.spread,
         "k": (15 - 15*df.tau), "micro": df.micro}
y = df.tox.to_numpy()
rows = []
for nm, s in feats.items():
    a = auc(y[OOS], s.to_numpy()[OOS])
    # direction: AUC<0.5 means inverse; report max(a,1-a) with sign
    rows.append((nm, a, max(a, 1 - a)))
rows.sort(key=lambda r: -r[2])
for nm, a, ad in rows:
    print(f"  {nm:>10}: AUC {a:.3f}  (directional {ad:.3f})")
# collinearity take_size vs vpin
c1 = df[["take_size","vpin","flow_adv"]].corr().round(3)
print(f"  corr take_size~vpin {c1.loc['take_size','vpin']:+.3f}  take_size~|flow| "
      f"{df.take_size.corr(df.flow_adv.abs()):+.3f}")

# ---------------- 3. OPTIMAL COMBINED GATE (logit) vs current tox_p ----------------
print("\n=== 3. COMBINED LOGIT (mk<0 label) OOS AUC vs current tox_p ===")
base_cols = ["sig_adv","abs_p05","spread","tau","flow_adv","vpin"]  # micro dropped: degenerate (mid==spread center)
Xb = df[base_cols].to_numpy()
wB, muB, sdB = fit_logit(Xb[IS], y[IS], l2=2.0)
pB = pred_logit(wB, muB, sdB, Xb)
auc_base = auc(y[OOS], pB[OOS])
# + take_size
plus_cols = base_cols + ["take_size"]
Xp = df[plus_cols].to_numpy()
wP, muP, sdP = fit_logit(Xp[IS], y[IS], l2=2.0)
pP = pred_logit(wP, muP, sdP, Xp)
auc_plus = auc(y[OOS], pP[OOS])
# current deployed tox_p (fit on settle<0, lacks take_size, lacks vpin/micro)
tp = np.array([box_tox_p({"side": r.side, "p": r.p if r.side=="bid" else round(1-r.p,4),
                          "flow": r.flow_adv*1000, "sig": r.sig_adv, "tau": r.tau,
                          "spread": r.spread}) for r in df.itertuples()])
auc_curtox = auc(y[OOS], tp[OOS])
print(f"  current tox_p (settle-fit, no take_size): OOS AUC {auc_curtox:.3f}")
print(f"  combined logit WITHOUT take_size:         OOS AUC {auc_base:.3f}")
print(f"  combined logit WITH take_size:            OOS AUC {auc_plus:.3f}  (delta {auc_plus-auc_base:+.3f})")

# ---------------- 4. AVOIDANCE FRONTIER (box pairing economics) ----------------
print("\n=== 4. AVOIDANCE FRONTIER: net SETTLE/window under box pairing, gate=skip if score>thr ===")
import box_policy_ab as ab
# rebuild per-window fill dicts once for run_policy with a take_size-aware open gate
def build_window_dicts():
    common = sorted(set(hist.index) & set(tap.index))
    out = {}
    for w in common:
        h = hist.loc[w]
        res = float(h.res_up)
        bid = np.asarray(h.bid_path, float); ask = np.asarray(h.ask_path, float)
        spot = np.asarray(h.spot_path, float)
        depth = np.full(15, np.nan)
        t = tap.loc[w]
        tape = (np.asarray(t.t,float), np.asarray(t.p,float), np.asarray(t.sz,float), np.asarray(t.buy,bool))
        out[w] = ab.window_fills(w, res, bid, ask, spot, depth, tape, oi_slope=None, q0=0.0)
    return out
# Instead of full rebuild (slow), use df rows: emulate run_policy pairing per window with a skip mask.
def policy_net(skip_mask):
    """Box pairing: per window walk fills in order, cap |net|<=1, hold to settle. skip=don't open."""
    tot = 0.0
    sk = skip_mask
    idx = 0
    for w, g in df.groupby("ws"):
        net = 0; pnl = 0.0
        for ridx, r in zip(g.index, g.itertuples()):
            step = 1 if r.side == "bid" else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            pairing = (net != 0 and abs(nn) < abs(net))
            if not pairing and sk[ridx]:
                continue
            net = nn; pnl += r.settle
        tot += pnl
    return tot * 100 / df.ws.nunique()

# attach OOS-fit combined-with-take_size score, sweep threshold
score = pP   # combined logit WITH take_size
sk_none = np.zeros(n, bool)
base_net_oos = None
# compute net on OOS windows only
oos_ws = set(df.ws[OOS].unique())
def policy_net_oos(skip_series):
    tot = 0.0; nw = 0
    for w, g in df.groupby("ws"):
        if w not in oos_ws: continue
        nw += 1; net = 0; pnl = 0.0
        for ridx, r in zip(g.index, g.itertuples()):
            step = 1 if r.side == "bid" else -1
            nn = net + step
            if abs(nn) > 1: continue
            pairing = (net != 0 and abs(nn) < abs(net))
            if not pairing and skip_series[ridx]: continue
            net = nn; pnl += r.settle
        tot += pnl
    return tot * 100 / max(nw, 1)
skarr = pd.Series(False, index=df.index)
no_gate = policy_net_oos(skarr)
print(f"  NO GATE (baseline): OOS net settle {no_gate:+.3f}c/window, vol kept 1.000")
best = (no_gate, 1.0, None)
for thr in [0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70,0.75]:
    m = pd.Series(score > thr, index=df.index)
    keep = 1 - (m & OOS).sum() / OOS.sum()
    net = policy_net_oos(m)
    star = ""
    if net > best[0]: best = (net, keep, thr); star = "  <-"
    print(f"  thr {thr:.2f}: vol_kept {keep:.3f}  OOS net {net:+.3f}c/win{star}")
print(f"  OOS-OPTIMAL combined-gate: thr {best[2]} -> {best[0]:+.3f}c/win "
      f"(vs {no_gate:+.3f} no-gate, gain {best[0]-no_gate:+.3f}c/win)")

# ---------------- 5. vs existing trials t18/t29/t31/t32 ----------------
print("\n=== 5. EXISTING GATES (OOS net settle/window, same box pairing) ===")
def gate_net_oos(open_ok_row):
    sk = pd.Series([not open_ok_row(r) for r in df.itertuples()], index=df.index)
    return policy_net_oos(sk)
# t18 tox_p<0.65 (uses current settle-fit tox_p)
t18 = gate_net_oos(lambda r: box_tox_p({"side": r.side, "p": r.p if r.side=="bid" else round(1-r.p,4),
        "flow": r.flow_adv*1000, "sig": r.sig_adv, "tau": r.tau, "spread": r.spread}) < 0.65)
# t29 favorite-only opens: leg own-cost >= 0.45 (bid uses p, ask uses 1-p... here p is YES-equiv; leg cost)
def fav(r):
    cost = r.p if r.side == "bid" else (1 - r.p)
    return cost >= 0.45
t29 = gate_net_oos(fav)
# t31 face-contrarian: open only when fill is contrarian to recent flow (flow_adv<0 = leaning against takers)
t31 = gate_net_oos(lambda r: r.flow_adv < 0)
# t32 vpin open gate <=0.40
t32 = gate_net_oos(lambda r: (np.isnan(r.vpin)) or (r.vpin <= 0.40))
print(f"  t18 tox_p<0.65:        {t18:+.3f}c/win")
print(f"  t29 favorite-only:     {t29:+.3f}c/win")
print(f"  t31 face-contrarian:   {t31:+.3f}c/win")
print(f"  t32 vpin<=0.40:        {t32:+.3f}c/win")
print(f"  NEW combined gate:     {best[0]:+.3f}c/win  (thr {best[2]})")
print(f"  no-gate baseline:      {no_gate:+.3f}c/win")

# ---------------- 6. ROBUSTNESS: score on MARKOUT (honest adverse-sel target, not noisy settle) ----------------
print("\n=== 6. ROBUSTNESS: net MARKOUT kept (OOS), gate=skip if combined-score>thr ===")
mk = df.markout.to_numpy()
oos = OOS
tot_mk_nogate = mk[oos].sum() * 100 / OOS.sum() * 1158  # per-window scaling not needed; report per-fill mean
print(f"  NO GATE: OOS mean markout {mk[oos].mean()*100:+.4f}c/fill, total {mk[oos].sum()*100:+.0f}c")
for thr in [0.45,0.50,0.55,0.60,0.65,0.70]:
    keepm = (pP <= thr) & oos
    if keepm.sum() == 0: continue
    print(f"  thr {thr:.2f}: vol_kept {keepm.sum()/oos.sum():.3f}  kept-mean-mk {mk[keepm].mean()*100:+.4f}c/fill  "
          f"total kept {mk[keepm].sum()*100:+.0f}c")
# t31 on markout
t31m = df.flow_adv < 0
print(f"  t31 contrarian (flow<0): OOS kept {(t31m&oos).sum()/oos.sum():.3f}  "
      f"mean-mk {mk[t31m&oos].mean()*100:+.4f}c  total {mk[t31m&oos].sum()*100:+.0f}c")
# take_size alone as a gate (skip large informed takes)
for ts in [50, 100, 200]:
    g = (df.take_size < ts) & oos
    print(f"  take_size<{ts}: OOS kept {g.sum()/oos.sum():.3f}  mean-mk {mk[g].mean()*100:+.4f}c  "
          f"total {mk[g].sum()*100:+.0f}c")
# split markout by take-size bucket (the fingerprint claim: 50+ informed -2.2c, 1-11 naive +0.5c)
print("  --- markout by take-size bucket (the fingerprint claim) ---")
for lo,hi,nm in [(1,11,'small 1-11'),(11,50,'mid 11-50'),(50,1e9,'large 50+')]:
    b = (df.take_size>=lo)&(df.take_size<hi)
    print(f"    {nm:>10}: n {b.sum():5d}  mean-mk {mk[b].mean()*100:+.4f}c  P(mk<0) {(mk[b]<0).mean():.3f}")
