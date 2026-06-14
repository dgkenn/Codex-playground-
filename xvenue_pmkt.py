"""xvenue_pmkt.py -- SCREEN Polymarket btc-updown-5m as a bigger crypto edge vs the
capacity-capped Kalshi 15m maker box (~$10-27/day ceiling).

Analyzes:
  1. Polymarket box/spread/depth from staged snapshots (pmkt_data/*.jsonl.gz) + live touch-depth probe.
  2. Cross-venue mispricing: Kalshi 15m implied P(up) vs Polymarket 5m implied P(up) at matched time.
  3. Directional efficiency of the Polymarket 5m mid (favorite-longshot / fair-value gap).
  4. Capacity / feasibility table.

CAVEAT: up_bsz/up_asz in the snapshots is the SUM of ALL book levels (see pmkt_collect.book_top),
NOT top-of-book. Executable maker/taker size is the TOUCH depth, which a live probe shows is ~$30-650,
two orders of magnitude smaller than the headline ~40k 'depth'. This is decisive for capacity.

Usage: python xvenue_pmkt.py [--probe N]   (N live windows to probe touch depth; default 0/offline)
"""
from __future__ import annotations
import gzip, glob, json, sys, time
import numpy as np
import pandas as pd

PMKT_GLOB = "pmkt_data/*.jsonl.gz"
KALSHI_BTC = "hist_kalshi_btc15m.parquet"


def load_pmkt():
    rows = []
    for fn in sorted(glob.glob(PMKT_GLOB)):
        with gzip.open(fn, "rt") as f:
            for line in f:
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    for c in ["up_bid", "up_ask", "down_bid", "down_ask", "up_bsz", "up_asz", "t", "end"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def section(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def pmkt_box_spread(df):
    section("1. POLYMARKET btc-updown-5m: SPREAD / BOX / 'DEPTH'")
    n = len(df)
    clean = df.dropna(subset=["up_bid", "up_ask", "down_bid", "down_ask"])
    print(f"snapshots: {n}  clean(4-quote): {len(clean)}  windows(slugs): {df['slug'].nunique()}")
    span_h = (df["t"].max() - df["t"].min()) / 3600
    print(f"time span: {span_h:.1f} h  ({df['t'].min():.0f}..{df['t'].max():.0f})")

    upsp = (clean.up_ask - clean.up_bid)
    print(f"\nUP spread (c):  mean {upsp.mean()*100:.2f}  median {upsp.median()*100:.2f}  "
          f"p10 {upsp.quantile(.1)*100:.2f}  p90 {upsp.quantile(.9)*100:.2f}  (tick=1c)")
    frac1c = (np.isclose(upsp, 0.01)).mean()
    print(f"frac at exactly 1c (touching): {frac1c:.3f}")

    # TAKER box: buy up_ask + down_ask, collateral $1 -> profit 1 - cost
    box_buy = clean.up_ask + clean.down_ask
    print(f"\nTAKER box cost (up_ask+down_ask): mean {box_buy.mean():.4f} median {box_buy.median():.4f} "
          f"min {box_buy.min():.4f}")
    print(f"  frac < 1.00 (free arb): {(box_buy < 1.0).mean():.4f}  "
          f"frac <= 0.99: {(box_buy <= 0.99).mean():.4f}")

    # MAKER box: rest bids on both up+down; if BOTH fill, cost = up_bid+down_bid, redeem $1
    box_mk = clean.up_bid + clean.down_bid
    edge = 1.0 - box_mk
    print(f"\nMAKER box (sum of bids = cost if both fill): mean {box_mk.mean():.4f} median {box_mk.median():.4f}")
    print(f"  implied gross edge (1 - sum_bids): mean {edge.mean()*100:.3f}c  median {edge.median()*100:.3f}c")
    print(f"  frac sum_bids > 1.0 (negative-edge / crossed): {(box_mk > 1.0).mean():.4f}")
    pos = edge[edge > 0]
    print(f"  among positive-edge snaps ({len(pos)}/{len(clean)}={len(pos)/len(clean):.2f}): "
          f"mean edge {pos.mean()*100:.3f}c")

    # 'depth' (SUM of all levels) -- NOT executable at touch
    print(f"\n'DEPTH' fields (SUM of ALL book levels, per collector):")
    print(f"  up_bsz: mean {df.up_bsz.mean():.0f} median {df.up_bsz.median():.0f} "
          f"p10 {df.up_bsz.quantile(.1):.0f}")
    print(f"  up_asz: mean {df.up_asz.mean():.0f} median {df.up_asz.median():.0f}")
    print("  NOTE: this is whole-book sum across ~45-54 price levels; executable TOUCH depth is tiny "
          "(live probe below).")
    return clean


def cross_venue(pm):
    section("2. CROSS-VENUE: Kalshi 15m P(up) vs Polymarket 5m P(up) at matched time")
    try:
        k = pd.read_parquet(KALSHI_BTC)
    except Exception as e:
        print("kalshi parquet load failed:", e); return
    # Kalshi rows: ws (window start), mid_path per-minute over 15m. Build (epoch -> mid).
    krows = []
    for _, r in k.iterrows():
        ws = int(r.ws)
        mids = r.mid_path
        if mids is None: continue
        for i, m in enumerate(list(mids)):
            krows.append((ws + i * 60, float(m)))  # ~per-minute samples
    kdf = pd.DataFrame(krows, columns=["epoch", "k_mid"]).sort_values("epoch")
    print(f"kalshi mid samples: {len(kdf)}  epoch {kdf.epoch.min()}..{kdf.epoch.max()}")

    # Polymarket: implied P(up) = up mid = (up_bid+up_ask)/2 ; timestamp t
    pm = pm.copy()
    pm["p_up"] = (pm.up_bid + pm.up_ask) / 2
    pm["epoch"] = pm.t.astype(int)
    pm = pm.sort_values("epoch")
    print(f"pmkt P(up) samples: {len(pm)}  epoch {pm.epoch.min()}..{pm.epoch.max()}")

    # time overlap?
    lo = max(kdf.epoch.min(), pm.epoch.min()); hi = min(kdf.epoch.max(), pm.epoch.max())
    print(f"\nTIME OVERLAP between venues: {'NONE' if lo > hi else f'{hi-lo} s'}  "
          f"(kalshi ends {kdf.epoch.max()}, pmkt starts {pm.epoch.min()})")
    if lo > hi:
        print("  -> Kalshi history and Polymarket snapshots DO NOT overlap in time.")
        print("  -> Cannot measure a contemporaneous cross-venue spread from staged data.")
        print("  -> Would need SIMULTANEOUS collection on both venues (concrete next step).")
        return
    # if overlap, merge_asof within 30s
    m = pd.merge_asof(pm[["epoch", "p_up"]], kdf, on="epoch", tolerance=30, direction="nearest").dropna()
    if len(m):
        d = (m.p_up - m.k_mid)
        print(f"matched pairs: {len(m)}  spread P_pm-P_k: mean {d.mean()*100:.2f}c std {d.std()*100:.2f}c "
              f"|mean| {d.abs().mean()*100:.2f}c")


def directional(pm):
    section("3. POLYMARKET 5m DIRECTIONAL / FAIR-VALUE EFFICIENCY")
    # Resolution: per window, did up win? infer from terminal mid near window end.
    pm = pm.copy()
    pm["p_up"] = (pm.up_bid + pm.up_ask) / 2
    pm["ttl"] = pm.end - pm.t  # seconds to expiry
    res = {}
    for slug, g in pm.groupby("slug"):
        g = g.sort_values("t")
        last = g.iloc[-1]
        # if last snapshot is within 20s of end and mid extreme -> infer outcome
        if last.ttl <= 30:
            res[slug] = 1 if last.p_up >= 0.5 else 0
    print(f"windows with terminal snapshot (<=30s to expiry) for outcome proxy: {len(res)}/{pm.slug.nunique()}")
    if not res:
        print("  insufficient terminal coverage to infer outcomes -> directional efficiency UNTESTABLE here.")
        # still report mid distribution / longshot zone
    # Calibration: bucket early mid vs realized (proxy)
    rows = []
    for slug, g in pm.groupby("slug"):
        if slug not in res: continue
        g = g.sort_values("t")
        early = g[g.ttl >= 60]  # >=60s to go
        if len(early) == 0: continue
        rows.append((early.p_up.mean(), res[slug]))
    if rows:
        dd = pd.DataFrame(rows, columns=["pmid", "win"])
        print(f"calib sample windows: {len(dd)}")
        for lo, hi in [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]:
            b = dd[(dd.pmid >= lo) & (dd.pmid < hi)]
            if len(b):
                print(f"  mid [{lo:.1f},{hi:.1f}): n={len(b):3d}  mean_mid {b.pmid.mean():.3f}  "
                      f"realized_up {b.win.mean():.3f}  gap {b.win.mean()-b.pmid.mean():+.3f}")
    print("  CAVEAT: outcome is a mid-proxy (no settlement feed); favorite-longshot read is indicative only.")


def probe_touch(nwin):
    section(f"LIVE PROBE: top-of-book (TOUCH) depth on {nwin} windows")
    import requests
    GAMMA = "https://gamma-api.polymarket.com"; CLOB = "https://clob.polymarket.com"
    got = 0; samples = []
    for k in range(nwin * 3):
        nb = int(time.time()) // 300 * 300
        slug = f"btc-updown-5m-{nb}"
        try:
            r = requests.get(f"{GAMMA}/markets", params={"slug": slug}, timeout=8).json()
            if not r: time.sleep(5); continue
            tok = json.loads(r[0]["clobTokenIds"])[0]
            ob = requests.get(f"{CLOB}/book", params={"token_id": tok}, timeout=8).json()
            bids = sorted([(float(b["price"]), float(b["size"])) for b in ob.get("bids", [])], reverse=True)
            asks = sorted([(float(a["price"]), float(a["size"])) for a in ob.get("asks", [])])
            if bids and asks:
                bb, bbs = bids[0]; ba, bas = asks[0]
                samples.append((bb, bbs, ba, bas, sum(s for _, s in bids), sum(s for _, s in asks)))
                print(f"  {slug} bestbid={bb}x{bbs:.0f} bestask={ba}x{bas:.0f} "
                      f"touch_$bid={bbs*bb:.0f} touch_$ask={bas*ba:.0f} sumbook={sum(s for _,s in bids):.0f}")
                got += 1
        except Exception as e:
            print("  probe err", e)
        if got >= nwin: break
        time.sleep(20)
    if samples:
        tb = np.array([s[1] * s[0] for s in samples]); ta = np.array([s[3] * s[2] for s in samples])
        print(f"\nTOUCH $ at best bid: median ${np.median(tb):.0f}  best ask: median ${np.median(ta):.0f}")


if __name__ == "__main__":
    nprobe = 0
    if "--probe" in sys.argv:
        nprobe = int(sys.argv[sys.argv.index("--probe") + 1])
    df = load_pmkt()
    clean = pmkt_box_spread(df)
    cross_venue(clean)
    directional(clean)
    if nprobe:
        probe_touch(nprobe)
