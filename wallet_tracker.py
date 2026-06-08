"""wallet_tracker.py -- periodic snapshot of the winning makers (watch-list) to catch strategy DRIFT.
Re-pulls each wallet's live state (portfolio value, activity-type mix, recent-trade behavior incl. the
complete-set buy discount) and appends a timestamped row to wallet_track.jsonl, printing the change vs
the previous snapshot. Run on a schedule (wallet-track.yml). python wallet_tracker.py

Watch-list = the top makers reverse-engineered in MAKERS.md (prefixes; resolved to full addresses at
runtime from a recent market). 0x20d2309cd9 is the t=4.9 outlier (WALLET_20d2.md)."""
from __future__ import annotations
import collections, json, statistics, time
import requests

D = "https://data-api.polymarket.com"
G = "https://gamma-api.polymarket.com"
WATCH = ["0x20d2309cd9", "0x674887d1ac", "0xdf7930e89a", "0x5e2b9261b0", "0x75cc3b63a2",
         "0x5c932f5090", "0x5d4aba8ad4", "0xed89b210fa"]
OUT = "wallet_track.jsonl"


def resolve(sess):
    """prefix -> full address, by scanning recent BTC+ETH 15m markets."""
    need = {p: None for p in WATCH}
    now = int(time.time())
    for asset in ("btc", "eth"):
        for k in range(1, 30):
            if all(need.values()):
                break
            ws = now - (now % 900) - 900 * k
            ev = sess.get(G + "/events", params={"slug": f"{asset}-updown-15m-{ws}"}, timeout=15).json()
            if not ev:
                continue
            cid = ev[0]["markets"][0]["conditionId"]
            for off in (0, 500, 1000, 1500):
                rows = sess.get(D + "/trades", params={"market": cid, "limit": 500, "offset": off}, timeout=20).json()
                if not isinstance(rows, list) or not rows:
                    break
                for t in rows:
                    for p in need:
                        if need[p] is None and t["proxyWallet"].startswith(p):
                            need[p] = t["proxyWallet"]
    return need


def snapshot(sess, w):
    val = sess.get(D + "/value", params={"user": w}, timeout=15).json()
    value = float(val[0]["value"]) if isinstance(val, list) and val else None
    act = sess.get(D + "/activity", params={"user": w, "limit": 500}, timeout=20).json()
    types = dict(collections.Counter(a.get("type") for a in act)) if isinstance(act, list) else {}
    tr = sess.get(D + "/trades", params={"user": w, "limit": 500}, timeout=20).json()
    s = {"value": value, "types": types}
    if isinstance(tr, list) and tr:
        span = max(1e-9, (tr[0]["timestamp"] - tr[-1]["timestamp"]) / 3600)
        s["trades_per_hr"] = round(len(tr) / span, 1)
        s["assets"] = dict(collections.Counter(t["slug"].rsplit("-updown-", 1)[0] for t in tr))
        s["clip"] = round(statistics.median(float(t["size"]) for t in tr), 1)
        nb = sum(t["side"] == "BUY" for t in tr)
        s["twosided"] = round(min(nb, len(tr) - nb) / len(tr), 2)
        # complete-set buy discount over its recent markets
        bym = collections.defaultdict(list)
        for t in tr:
            bym[t["slug"]].append(t)
        prem = []
        for T in bym.values():
            ub = [(float(t["price"]), float(t["size"])) for t in T if t["side"] == "BUY" and t.get("outcomeIndex", 0) == 0]
            db = [(float(t["price"]), float(t["size"])) for t in T if t["side"] == "BUY" and t.get("outcomeIndex", 0) == 1]
            if ub and db:
                uv = sum(p * z for p, z in ub) / sum(z for _, z in ub)
                dv = sum(p * z for p, z in db) / sum(z for _, z in db)
                prem.append(1 - (uv + dv))
        s["box_buy_prem"] = round(statistics.mean(prem), 4) if prem else None
    return s


def main():
    sess = requests.Session()
    full = resolve(sess)
    snaps = {}
    for p, w in full.items():
        if not w:
            print(f"{p}: unresolved (not seen recently)"); continue
        snaps[p] = snapshot(sess, w)
    # load previous
    prev = {}
    try:
        rows = [json.loads(l) for l in open(OUT)]
        for r in rows:
            prev[r["wallet"]] = r
    except FileNotFoundError:
        pass
    now = int(time.time())
    fh = open(OUT, "a")
    print(f"\n{'wallet':>12}{'value':>9}{'trd/hr':>7}{'clip':>6}{'2sd':>5}{'box%':>6}  types / drift")
    for p, s in snaps.items():
        rec = {"ts": now, "wallet": p, **s}
        fh.write(json.dumps(rec) + "\n")
        pv = prev.get(p, {})
        dv = ""
        if pv.get("value") is not None and s.get("value") is not None:
            dv = f"  Δvalue={s['value']-pv['value']:+.0f}"
        bp = s.get("box_buy_prem")
        print(f"{p:>12}{(s.get('value') or 0):>9.0f}{(s.get('trades_per_hr') or 0):>7.0f}"
              f"{(s.get('clip') or 0):>6.1f}{(s.get('twosided') or 0):>5.2f}"
              f"{(bp*100 if bp is not None else 0):>+6.1f}  {s.get('types',{})}{dv}")
    fh.close()
    print(f"\nappended {len(snaps)} snapshots -> {OUT}. box% = recent complete-set buy discount (the edge); "
          f"watch for it shrinking (competition) or behavior shifting (assets/clip/2sided drift).")


if __name__ == "__main__":
    main()
