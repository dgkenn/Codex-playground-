"""Run each risk overlay across its parameter grid (plateau check) + best combined.
Reports FULL (full-cycle) and REC12 (recent 12mo HARD holdout) + PREV12. 40 bps RT.
"""
import mlo_backtest as mb
import mlo_risk as mr

px, vol = mb.load_spot()
pool = list(px.columns)
BASE = dict(lb=10, top_n=15, k=5, cost_bps=40, partial=0.7, gate_ma=100)


def rl(tag, **kw):
    cfg = dict(BASE); cfg.update(kw)
    _, rep = mr.report(px, vol, pool, **cfg)
    if rep is None:
        print(f"{tag:30s} (empty)"); return
    print(mr.line(tag, rep))


print("=" * 130)
print("BASELINE")
rl("BASE k5 gate100")

print("=" * 130)
print("1. VOL-TARGETING (vol_lb=20, max_lev=1.0)")
for vt in [0.30, 0.40, 0.50, 0.60]:
    rl(f"  voltgt={vt:.0%}", vol_target=vt)
print("  -- vol_lb sensitivity at vt=0.40 --")
for vlb in [10, 20, 30]:
    rl(f"  vt40 vol_lb={vlb}", vol_target=0.40, vol_lb=vlb)

print("=" * 130)
print("2. ABSOLUTE / DUAL MOMENTUM (keep name only if own lb-ret > thresh)")
for th in [0.0, 0.02, 0.05]:
    rl(f"  abs own>{th:.0%}", abs_mom=True, abs_thresh=th)
rl("  abs own>BTC own", abs_mom=True, abs_vs_btc=True)

print("=" * 130)
print("3. FASTER / TIERED DE-RISK (stack on slow gate100)")
for fm in [20, 30, 50]:
    rl(f"  +fast<{fm} binary", fast_ma=fm, fast_mode="binary")
for fm in [20, 30, 50]:
    rl(f"  +fast<{fm} tier0.5", fast_ma=fm, fast_mode="tier", tier_frac=0.5)
rl("  +fast<30 tier0.33", fast_ma=30, fast_mode="tier", tier_frac=0.33)

print("=" * 130)
print("4. CONCENTRATION (k hold count + per-name cap)")
for kk in [3, 5, 7, 10]:
    rl(f"  k={kk}", k=kk)
print("  -- per-name caps at k=5 --")
for cap in [0.25, 0.30, 0.40]:
    rl(f"  k5 cap={cap:.0%}", name_cap=cap)
print("  -- bigger book + cap --")
rl("  k8 cap0.20", k=8, name_cap=0.20)
rl("  k10 cap0.15", k=10, name_cap=0.15)

print("=" * 130)
print("5. PER-POSITION TRAILING STOP / TIME STOP")
for sp in [0.10, 0.15, 0.20, 0.25]:
    rl(f"  trail stop={sp:.0%}", stop_pct=sp)
for ts in [3, 4, 5]:
    rl(f"  time stop={ts}d", time_stop_days=ts)
