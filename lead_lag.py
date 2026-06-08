"""Does BTC spot LEAD the Polymarket token (so the token's move is partly predictable)?

Model-free test: from the joint (token Up-mid, BTC spot) tick series (~2s, ticks_*.jsonl),
cross-correlate spot CHANGES against token-mid CHANGES at various lags. If spot leads, the
peak correlation sits at a POSITIVE lag (spot change at t predicts token-mid change at t+lag),
and that lag/strength tells us whether it's exploitable -- and which way:
  * defensive (maker): reprice/pull when spot just moved, before we're picked off;
  * aggressive (taker): only if the predicted move beats the 0.07 taker fee + spread.

Per-window (cluster-aware) then aggregated; reports the lead lag, correlation, and the implied
single-step predictability R^2.  python lead_lag.py
"""
from __future__ import annotations
import glob, json
import numpy as np

STEP = 1          # seconds per tick (matches collector ~1s downsample; high-res WS spot)
MAXLAG = 8        # test spot leading mid by up to this many steps (=1s each)


def load():
    W = []
    for f in glob.glob("gha_data/ticks_r*.jsonl"):
        for ln in open(f):
            ln = ln.strip()
            if ln:
                try: W.append(json.loads(ln))
                except Exception: pass
    return W


def main():
    W = load()
    if not W:
        print("no ticks yet -- the instrumented collector writes ticks_*.jsonl at each settle.")
        return
    print(f"lead-lag: {len(W)} windows with tick series (~{STEP}s sampling)\n")
    # accumulate cross-correlation by lag across windows (lag>0 => spot LEADS token mid)
    lags = list(range(-MAXLAG, MAXLAG + 1))
    pooled = {k: [] for k in lags}        # pooled (dspot_t, dmid_{t+k}) pairs
    perwin_peak = []
    for w in W:
        ts = w["ticks"]
        if len(ts) < 30:
            continue
        t = np.array([a[0] for a in ts]); mid = np.array([a[1] for a in ts]); sp = np.array([a[2] for a in ts])
        dmid = np.diff(mid); dsp = np.diff(sp)
        if dsp.std() == 0 or dmid.std() == 0:
            continue
        best = (0, 0.0)
        for k in lags:
            # corr(dsp[t], dmid[t+k]) ; k>0 aligns a spot move with a LATER mid move
            if k >= 0:
                a, b = dsp[:len(dsp) - k], dmid[k:]
            else:
                a, b = dsp[-k:], dmid[:len(dmid) + k]
            n = min(len(a), len(b))
            if n < 20 or a[:n].std() == 0 or b[:n].std() == 0:
                continue
            c = float(np.corrcoef(a[:n], b[:n])[0, 1])
            pooled[k].append(c)
            if abs(c) > abs(best[1]):
                best = (k, c)
        perwin_peak.append(best)
    print(f"{'lag(steps)':>10} {'lag(s)':>7} {'mean corr':>10} {'windows':>8}")
    for k in lags:
        cs = pooled[k]
        if cs:
            tag = "  <- spot LEADS" if k > 0 else ("  (contemporaneous)" if k == 0 else "")
            print(f"{k:>10} {k*STEP:>7} {np.mean(cs):>+10.3f} {len(cs):>8}{tag}")
    if perwin_peak:
        peaks = [k for k, _ in perwin_peak]
        lead = sum(1 for k in peaks if k > 0); con = sum(1 for k in peaks if k == 0); lagk = sum(1 for k in peaks if k < 0)
        import statistics as st
        print(f"\nper-window PEAK-correlation lag: spot-leads={lead}  contemporaneous={con}  token-leads={lagk}  (n={len(peaks)})")
        print(f"  median peak lag = {st.median(peaks)*STEP:+.0f}s")
        # best positive-lag predictability (exploitable lead)
        posc = [np.mean(pooled[k]) for k in lags if k > 0 and pooled[k]]
        if posc:
            cmax = max(posc)
            print(f"  best spot-leads corr = {cmax:+.3f}  -> single-step predictability R^2 = {cmax**2:.3f}")
            print("  READ: a positive, consistent spot-leads corr => exploitable; R^2 says how much. "
                  "Contemporaneous/negative => no tradeable lead (everyone sees BTC at once).")


if __name__ == "__main__":
    main()
