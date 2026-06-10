"""Track A: pull a broad cross-section of RESOLVED Polymarket markets across
categories (esp. zero/low-fee: geopolitics 0, sports 0.03, politics 0.04) with their
market-implied probability over life (CLOB prices-history) + resolution, for the
calibration / favorite-longshot battery.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import pandas as pd
import requests

G = "https://gamma-api.polymarket.com"
PH = "https://clob.polymarket.com/prices-history"
CATS = {"sports": "sports", "politics": "politics", "geopolitics": "geopolitics",
        "economy": "economics", "crypto": "crypto", "tech": "tech", "pop-culture": "culture"}
CAP = 500          # resolved markets per category (first pass)


def iso(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def price_at(hist, frac):
    if not hist:
        return None
    t0, t1 = hist[0]["t"], hist[-1]["t"]
    if t1 <= t0:
        return hist[-1]["p"]
    target = t0 + frac * (t1 - t0)
    return min(hist, key=lambda x: abs(x["t"] - target))["p"]


def main():
    sess = requests.Session()
    rows = []
    for tag, feecat in CATS.items():
        seen = set(); got = 0; off = 0
        while got < CAP and off < 4000:
            try:
                evs = sess.get(G + "/events", params={"tag_slug": tag, "closed": "true",
                               "limit": 100, "offset": off, "order": "endDate", "ascending": "false"},
                               timeout=30).json()
            except Exception:
                break
            if not isinstance(evs, list) or not evs:
                break
            off += 100
            for e in evs:
                for m in e.get("markets", []):
                    cid = m.get("conditionId")
                    if not cid or cid in seen:
                        continue
                    outs = m.get("outcomes"); pr = m.get("outcomePrices"); tk = m.get("clobTokenIds")
                    if not (outs and pr and tk):
                        continue
                    outs = json.loads(outs); pr = json.loads(pr); tk = json.loads(tk)
                    if len(outs) != 2 or set(pr) != {"0", "1"}:
                        continue
                    seen.add(cid)
                    yes_res = 1 if pr[0] == "1" else 0
                    try:
                        h = sess.get(PH, params={"market": tk[0], "interval": "max", "fidelity": 60},
                                     timeout=30).json().get("history", [])
                    except Exception:
                        h = []
                    if len(h) < 5:
                        continue
                    rows.append({"tag": tag, "fee_cat": feecat, "condition_id": cid,
                                 "yes_token": str(tk[0]), "resolved_yes": yes_res,
                                 "p_mid": price_at(h, 0.5), "p_late": price_at(h, 0.9),
                                 "p_early": price_at(h, 0.1), "n_pts": len(h),
                                 "life_h": round((h[-1]["t"] - h[0]["t"]) / 3600, 1)})
                    got += 1
                    if got >= CAP:
                        break
                if got >= CAP:
                    break
            print(f"  {tag}: {got} markets...", flush=True)
        print(f"{tag}: collected {got}")
    df = pd.DataFrame(rows)
    df.to_parquet("markets_calib.parquet", index=False)
    print(f"\nwrote markets_calib.parquet: {len(df)} markets across {df['tag'].nunique()} tags")
    print(df.groupby("tag").size().to_string())


if __name__ == "__main__":
    main()
