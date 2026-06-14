"""Run all regime/crowding-timing filters as scaling overlays on the locked best-config
momentum strategy. For each filter we sweep a small threshold grid (resist overfit),
choose the IS-best, and report OOS18 / REC12 / PREV12 Sharpe + OOS maxDD, plus the FULL
robustness profile across thresholds (plateau-vs-spike test).

Gate semantics: g(t) in [-1,1] multiplies the (already dollar-neutral) book.
  g=1 full on, g=0 flat (sit out), g<0 flip the book.
All regime signals observable at entry t (shifted where own-equity is used). Costs reflow.
"""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
import mom_backtest as mb
import regime_backtest as rb

px, vol = mb.load_panel()
END = px.index.max()
IS_END = END - pd.DateOffset(months=18)

SCHEME = sys.argv[1] if len(sys.argv) > 1 else "equal"
COST = 9.0

BASE = rb.base_book(px, vol, mb.sig_riskadj, lb=10, top_n=15, scheme=SCHEME, cost_bps=COST)
BASE_NET = BASE["net_base"].copy()  # for own-equity regime


def sh(r):
    return mb.stats(r)["sharpe"]


def win_stats(g):
    w = rb.windows(g)
    out = {}
    for k in ("FULL", "IS", "OOS18", "REC12", "PREV12"):
        out[k] = sh(rb.slc(g, *w[k]))
    out["OOS_DD"] = rb.maxdd(rb.slc(g, *w["OOS18"]))
    out["REC_DD"] = rb.maxdd(rb.slc(g, *w["REC12"]))
    out["exp"] = g.loc[g.index >= END - pd.DateOffset(months=12), "gate"].abs().mean()
    return out


gate_from_threshold = rb.gate_from_threshold


def eval_gate(gate):
    g = rb.apply_gate(BASE, gate, cost_bps=COST)
    return g, win_stats(g)


print(f"\n############ SCHEME = {SCHEME}  (base = riskadj-10d top15, {COST}bps) ############")
gbase, sbase = eval_gate(pd.Series(1.0, index=px.index))
print(f"BASE (no gate):  FULL {sbase['FULL']:+.2f} IS {sbase['IS']:+.2f} OOS18 {sbase['OOS18']:+.2f} "
      f"REC12 {sbase['REC12']:+.2f} PREV12 {sbase['PREV12']:+.2f} | OOSdd {sbase['OOS_DD']*100:+.0f}% RECdd {sbase['REC_DD']*100:+.0f}%")


def sweep(name, level, grid, mode="above_on"):
    """Print threshold sweep with IS-pick highlighted. Returns the rows."""
    print(f"\n=== {name}  (mode={mode}) ===")
    print(f"{'thr':>10} | {'IS':>6} {'OOS18':>6} {'REC12':>6} {'PREV12':>6} | {'OOSdd':>6} {'RECdd':>6} {'exp':>4}")
    rows = []
    for thr in grid:
        gate = gate_from_threshold(level, thr, mode=mode)
        g, st = eval_gate(gate)
        rows.append((thr, st))
        print(f"{thr:>10.4g} | {st['IS']:+6.2f} {st['OOS18']:+6.2f} {st['REC12']:+6.2f} {st['PREV12']:+6.2f} | "
              f"{st['OOS_DD']*100:+5.0f}% {st['REC_DD']*100:+5.0f}% {st['exp']:>4.2f}")
    is_best = max(rows, key=lambda r: r[1]["IS"])
    print(f"  -> IS-best thr={is_best[0]:.4g}: OOS18 {is_best[1]['OOS18']:+.2f} (base {sbase['OOS18']:+.2f}), "
          f"REC12 {is_best[1]['REC12']:+.2f} (base {sbase['REC12']:+.2f})")
    return rows


# ---- build regime level series ----
btcvol20 = rb.btc_realized_vol(px, 20)
bvol20 = rb.basket_realized_vol(px, 20)
disp = rb.xs_dispersion(px, lb=10)
trend100 = rb.btc_trend(px, 100)
trend50 = rb.btc_trend(px, 50)
brd = rb.breadth(px, 10)

# normalize dispersion / vol to rolling percentile so thresholds are interpretable & robust
def roll_pctile(s, win=252):
    return s.rolling(win, min_periods=60).apply(lambda x: (x.iloc[-1] >= x).mean(), raw=False)

disp_pct = roll_pctile(disp)
btcvol_pct = roll_pctile(btcvol20)

# 1. BTC realized vol (test both directions)
sweep("1a BTC vol-20 percentile: ON when LOW vol", btcvol_pct, [0.5,0.6,0.7,0.8,0.9], mode="below_on")
sweep("1b BTC vol-20 percentile: ON when HIGH vol", btcvol_pct, [0.1,0.2,0.3,0.4,0.5], mode="above_on")

# 2. Cross-sectional dispersion (momentum classically needs dispersion)
sweep("2a Dispersion percentile: ON when HIGH disp", disp_pct, [0.1,0.2,0.3,0.4,0.5], mode="above_on")
sweep("2b Dispersion percentile: ON when LOW disp", disp_pct, [0.5,0.6,0.7,0.8], mode="below_on")

# 3. BTC trend (risk-on when above MA)
sweep("3a BTC>MA100: ON when uptrend", trend100, [-0.10,-0.05,0.0,0.05], mode="above_on")
sweep("3b BTC>MA100: ON when DOWNtrend", trend100, [-0.05,0.0,0.05,0.10], mode="below_on")
sweep("3c BTC>MA50: ON when uptrend", trend50, [-0.05,0.0,0.05], mode="above_on")

# 4. Breadth
sweep("4a Breadth: ON when broad-up", brd, [0.4,0.5,0.6,0.7], mode="above_on")
sweep("4b Breadth: ON when broad-DOWN", brd, [0.3,0.4,0.5,0.6], mode="below_on")

# 5. Own-equity rolling Sharpe (turn off after losing streak) -- needs gate indexed by ENTRY
#    Build a per-rebalance net series indexed by ENTRY date, compute rolling sharpe, shift.
base_by_entry = pd.Series(BASE["net_base"].values, index=pd.DatetimeIndex(BASE["entry"].values))
osr8 = (base_by_entry.rolling(8).mean() / base_by_entry.rolling(8).std()).shift(1)
osr4 = (base_by_entry.rolling(4).mean() / base_by_entry.rolling(4).std()).shift(1)
sweep("5a Own rolling-Sharpe(8): ON when own-Sharpe>=thr", osr8, [-0.3,0.0,0.2,0.4], mode="above_on")
sweep("5b Own rolling-Sharpe(4): ON when own-Sharpe>=thr", osr4, [-0.3,0.0,0.2,0.4], mode="above_on")
# own drawdown
eq = (1+base_by_entry).cumprod(); odd = (eq/eq.cummax()-1).shift(1)
sweep("5c Own drawdown: OFF when DD worse than thr (ON when DD>=thr)", odd, [-0.25,-0.15,-0.10,-0.05], mode="above_on")

# 6. Vol-target overlay (continuous): scale = target_vol / realized own vol (shifted)
print("\n=== 6 Vol-targeting overlay (continuous gate = clip(target/realized_own_vol,0,cap)) ===")
ann = np.sqrt(52)
own_vol = (base_by_entry.rolling(8).std()*ann).shift(1)
print(f"{'target':>8} {'cap':>4} | {'IS':>6} {'OOS18':>6} {'REC12':>6} {'PREV12':>6} | {'OOSdd':>6} {'RECdd':>6} {'exp':>4}")
for tgt in (0.30,0.40,0.50):
    for cap in (1.0,1.5):
        scale = (tgt/own_vol).clip(0,cap)
        # gate indexed by entry-date series -> reindex to panel dates via entry mapping in apply_gate
        gate = scale.reindex(pd.DatetimeIndex(px.index).tz_localize(None)).ffill()
        gate.index = px.index
        g,st = eval_gate(gate.fillna(1.0))
        print(f"{tgt:>8.2f} {cap:>4.1f} | {st['IS']:+6.2f} {st['OOS18']:+6.2f} {st['REC12']:+6.2f} {st['PREV12']:+6.2f} | "
              f"{st['OOS_DD']*100:+5.0f}% {st['REC_DD']*100:+5.0f}% {st['exp']:>4.2f}")
