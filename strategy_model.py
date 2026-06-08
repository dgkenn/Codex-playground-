"""strategy_model.py -- LEARN each top-10%-by-MM-score wallet's underlying algorithm from its trade tape
(data-api ?user=). Per wallet we measure the parameters that DEFINE the strategy, producing a model card
that, run as a rule, reproduces the wallet's behaviour. This is the "understand the algorithm" deliverable
(prospective trade-prediction fidelity is validated separately by copy_live_multi.py).

Per wallet (from ~1500 recent fills):
  scope     assets / tenors mix, markets, concurrency
  side      two-side balance index (1=perfect MM), buy/sell per token
  set       complete-set buy-sum (=1-discount) and sell-sum  -> the complete-set edge
  ladder    distribution of |price - that token's own VWAP| in ticks (p50/p90/p95) = how deep they quote
  clip      USDC + shares per order
  timing    fraction of fills in window phases (open/mid/late)
  hold      end set-balance (min/max of net Up/Dn) -> hold-balanced-to-resolution vs flatten
  learnability  parameter stability (how concentrated -> how well a fixed rule explains them)
Writes strategy_models.json + prints a comparison. python strategy_model.py
"""
from __future__ import annotations
import collections, json, math, statistics, time
import requests

D = "https://data-api.polymarket.com"


def pull(sess, w, maxn=1500):
    out, off = [], 0
    while len(out) < maxn:
        j = sess.get(D + "/trades", params={"user": w, "limit": 500, "offset": off}, timeout=20).json()
        if not isinstance(j, list) or not j:
            break
        out += j; off += 500
        if len(j) < 500:
            break
    return out


def pct(xs, q):
    return sorted(xs)[min(len(xs) - 1, int(q * len(xs)))] if xs else float("nan")


def model_for(tr):
    if not tr:
        return None
    bym = collections.defaultdict(list)
    for t in tr:
        bym[t["slug"]].append(t)
    nb = sum(t["side"] == "BUY" for t in tr); ns = len(tr) - nb
    assets = collections.Counter(t["slug"].split("-updown-")[0] for t in tr)
    tenors = collections.Counter(t["slug"].split("-updown-")[1].split("-")[0] for t in tr if "-updown-" in t["slug"])
    clips_usd = [float(t["price"]) * float(t["size"]) for t in tr]
    clips_sh = [float(t["size"]) for t in tr]
    # ladder proxy: |price - that token's own VWAP in the market| in ticks (no touch in tape)
    ladder = []
    buysum, sellsum, balance = [], [], []
    for slug, T in bym.items():
        for oi in (0, 1):
            leg = [t for t in T if t.get("outcomeIndex", 0) == oi]
            v = sum(float(t["size"]) for t in leg)
            if v <= 0:
                continue
            vwap = sum(float(t["price"]) * float(t["size"]) for t in leg) / v
            for t in leg:
                ladder.append(abs(float(t["price"]) - vwap) / 0.01)     # ticks from own VWAP
        ub = [(float(t["price"]), float(t["size"])) for t in T if t["side"] == "BUY" and t.get("outcomeIndex", 0) == 0]
        db = [(float(t["price"]), float(t["size"])) for t in T if t["side"] == "BUY" and t.get("outcomeIndex", 0) == 1]
        if ub and db:
            buysum.append(sum(p * s for p, s in ub) / sum(s for _, s in ub) + sum(p * s for p, s in db) / sum(s for _, s in db))
        eu = sum((float(t["size"]) if t["side"] == "BUY" else -float(t["size"])) for t in T if t.get("outcomeIndex", 0) == 0)
        ed = sum((float(t["size"]) if t["side"] == "BUY" else -float(t["size"])) for t in T if t.get("outcomeIndex", 0) == 1)
        if eu > 0 and ed > 0:
            balance.append(min(eu, ed) / max(eu, ed))
    # timing
    phase = collections.Counter()
    for slug, T in bym.items():
        win = 300 if "-5m-" in slug else 900
        try:
            ws = int(slug.rsplit("-", 1)[1])
        except Exception:
            continue
        for t in T:
            sec = int(t["timestamp"]) - ws
            phase["open" if sec < win * 0.2 else ("late" if sec > win * 0.8 else "mid")] += 1
    nph = max(1, sum(phase.values()))
    two = 1 - abs(nb - ns) / max(1, nb + ns)
    learn = 1 - min(1.0, (statistics.pstdev(clips_sh) / (statistics.mean(clips_sh) + 1e-9)) / 3)  # clip-CV based
    return {
        "trades": len(tr), "markets": len(bym),
        "assets": dict(assets), "tenors": dict(tenors),
        "two_side": round(two, 3), "buy": nb, "sell": ns,
        "set_buy_sum_med": round(statistics.median(buysum), 4) if buysum else None,
        "set_discount_c": round((1 - statistics.median(buysum)) * 100, 2) if buysum else None,
        "ladder_p50_tk": round(pct(ladder, .5), 1), "ladder_p90_tk": round(pct(ladder, .9), 1),
        "ladder_p95_tk": round(pct(ladder, .95), 1),
        "clip_usd_med": round(statistics.median(clips_usd), 1), "clip_sh_med": round(statistics.median(clips_sh), 1),
        "phase": {k: round(v / nph, 2) for k, v in phase.items()},
        "set_balance_med": round(statistics.median(balance), 2) if balance else None,
        "learnability": round(learn, 2),
    }


def main():
    mm = json.load(open("mm_score.json")); n = max(1, len(mm) // 10)
    wallets = [r["w"] for r in mm[:n]]
    sess = requests.Session(); models = {}
    print(f"learning algorithms for top-10% = {len(wallets)} wallets...\n")
    hdr = (f"{'wallet':>12}{'trd':>5}{'2side':>6}{'setΔc':>6}{'ladP50':>7}{'ladP95':>7}{'clip$':>6}"
           f"{'setbal':>7}{'open':>5}{'late':>5}{'learn':>6}")
    print(hdr)
    for w in wallets:
        m = model_for(pull(sess, w))
        if not m:
            print(f"{w[:10]:>12}  (no trades)"); continue
        models[w] = m
        print(f"{w[:10]:>12}{m['trades']:>5}{m['two_side']:>6.2f}{(m['set_discount_c'] or 0):>6.1f}"
              f"{m['ladder_p50_tk']:>7}{m['ladder_p95_tk']:>7}{m['clip_usd_med']:>6.1f}"
              f"{(m['set_balance_med'] or 0):>7.2f}{m['phase'].get('open',0):>5.2f}{m['phase'].get('late',0):>5.2f}{m['learnability']:>6.2f}")
    json.dump(models, open("strategy_models.json", "w"))
    print(f"\nwrote strategy_models.json ({len(models)} algorithms). setΔc=complete-set buy discount (cents); "
          f"ladP50/95=quote depth from own VWAP (ticks); setbal=hold-balanced-to-resolution; learn=parameter "
          f"stability (1=a fixed rule explains them well). These ARE the learned algorithms -> compare + mine "
          f"for our bot (strategy_compare.py); copy_live_multi.py validates prospective trade-prediction.")


if __name__ == "__main__":
    main()
