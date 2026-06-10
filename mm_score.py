"""mm_score.py -- rank wallets by a MARKET-MAKER score (not P&L, not win-rate), per the success criteria
for post-Jan-2026 15-min crypto MMs (rebate + spread capture, NOT direction). Reads makers_trades.jsonl
(makers_scan.py cache) + pulls /value, /activity for the top candidates.

Per wallet we compute (proxies where the tape lacks a field; each labeled):
  two_side      Balance Index = 1 - |buys-sells|/(buys+sells)            (formula #5; ~1 = true MM)
  pos_usd       avg trade size in USDC                                    (MM: small $50-500)
  trades_day    inventory rotation                                       (MM: ~100-500, not 1000s/not <10)
  win_rate      fraction of markets with positive settled P&L            (MM: 55-70%, NOT 98%)
  pnl           settled P&L (cash + inventory*resolution), gross         (proxy for $ over the sample)
  conc          BTC+ETH+SOL share of volume                              (MM concentrate on top assets)
  liq_share     wallet vol / total market vol, avg over its markets      (proxy for executed-liq share; >5% dominant)
  rebate_px     est rebate = 0.20 * sum(0.07*p*(1-p)*size) on fills      (proxy daily-rebate; tape has no flag)
  reb_pnl       rebate_px / |pnl|                                        (MM: >0.4 rebate-driven)
  maxdd         max drawdown of the cumulative per-market P&L curve
  MM_SCORE = (rebate_px * liq_share * two_side) / (pos_usd * maxdd)      (per the user's formula; *active)
All wallets in the live tape are post-Mar-2026 active (activity factor=1). python mm_score.py
"""
from __future__ import annotations
import collections, json, math, sys
import requests

CACHE = "makers_trades.jsonl"
D = "https://data-api.polymarket.com"
TOP_ASSETS = {"btc", "eth", "sol"}


def _maxdd(seq):
    peak = cum = 0.0; dd = 0.0
    for x in seq:
        cum += x; peak = max(peak, cum); dd = max(dd, peak - cum)
    return dd


def main():
    W = collections.defaultdict(lambda: {"pnls": [], "buys": 0, "sells": 0, "usd": [], "fee": 0.0,
                                         "asset_vol": collections.Counter(), "shares": [], "n": 0})
    mkt_vol = collections.defaultdict(float)          # total volume per market (for liq share)
    rows = [json.loads(l) for l in open(CACHE)] if __import__("os").path.exists(CACHE) else []
    for r in rows:
        for w, side, sz, pr, oi, ts in r["trades"]:
            mkt_vol[r["cid"]] += pr * sz
    for r in rows:
        res = r["res_up"]; asset = r["asset"]
        perm = collections.defaultdict(lambda: {"cash": 0.0, "up": 0.0, "dn": 0.0, "b": 0, "s": 0, "usd": [], "fee": 0.0, "vol": 0.0})
        for w, side, sz, pr, oi, ts in r["trades"]:
            d = perm[w]; buy = side == "BUY"
            d["cash"] += (-pr * sz if buy else pr * sz)
            d["up" if oi == 0 else "dn"] += sz if buy else -sz
            d["b"] += buy; d["s"] += not buy; d["usd"].append(pr * sz); d["vol"] += pr * sz
            d["fee"] += 0.20 * (0.07 * pr * (1 - pr)) * sz        # est maker-rebate proxy
        for w, d in perm.items():
            a = W[w]; a["pnls"].append(d["cash"] + d["up"] * res + d["dn"] * (1 - res))
            a["buys"] += d["b"]; a["sells"] += d["s"]; a["usd"] += d["usd"]; a["fee"] += d["fee"]
            a["asset_vol"][asset] += d["vol"]; a["n"] += 1
            if mkt_vol[r["cid"]] > 0:
                a["shares"].append(d["vol"] / mkt_vol[r["cid"]])
    out = []
    for w, a in W.items():
        tot = a["buys"] + a["sells"]
        if a["n"] < 10 or tot < 20:
            continue
        two = 1 - abs(a["buys"] - a["sells"]) / tot
        pos = sum(a["usd"]) / len(a["usd"])
        pnl = sum(a["pnls"]); winr = sum(p > 0 for p in a["pnls"]) / a["n"]
        conc = sum(v for k, v in a["asset_vol"].items() if k in TOP_ASSETS) / max(1e-9, sum(a["asset_vol"].values()))
        liq = sum(a["shares"]) / len(a["shares"]) if a["shares"] else 0.0
        reb = a["fee"]; reb_pnl = reb / abs(pnl) if abs(pnl) > 1 else float("inf")
        dd = max(1.0, _maxdd(a["pnls"]))
        score = (reb * liq * two) / (pos * dd) * 1000      # *active(=1); *1000 for readable scale
        out.append({"w": w, "score": score, "two": two, "pos": pos, "tpm": a["n"], "trades": tot,
                    "win": winr, "pnl": pnl, "conc": conc, "liq": liq, "reb": reb, "reb_pnl": reb_pnl, "dd": dd})
    # MM filter per the rubric: two-sided, small clips, healthy rotation, BTC/ETH/SOL concentrated, not 98% win
    mm = [r for r in out if r["two"] > 0.6 and r["pos"] < 500 and r["conc"] > 0.6 and r["win"] < 0.9]
    mm.sort(key=lambda r: -r["score"])
    print(f"wallets scored={len(out)}  MM-qualified (2side>.6, clip<$500, conc>.6, win<90%)={len(mm)}\n")
    print(f"{'wallet':>12}{'MMscore':>8}{'2side':>6}{'pos$':>6}{'mkts':>5}{'win%':>5}{'pnl':>7}{'conc':>5}{'liq%':>6}{'reb$':>6}{'reb/pnl':>8}")
    for r in mm[:25]:
        print(f"{r['w'][:10]:>12}{r['score']:>8.2f}{r['two']:>6.2f}{r['pos']:>6.0f}{r['tpm']:>5}{100*r['win']:>5.0f}"
              f"{r['pnl']:>+7.0f}{r['conc']:>5.2f}{100*r['liq']:>6.1f}{r['reb']:>6.1f}{r['reb_pnl']:>8.2f}")
    json.dump(mm, open("mm_score.json", "w"))
    print(f"\nwrote mm_score.json. MMscore = (reb*liq*2side)/(pos*maxdd)*1000. reb$/liq are PROXIES (tape "
          f"has no maker/taker flag or rebate-USDC feed); reb/pnl>0.4 = rebate-driven MM; win 55-70% = true MM.")


if __name__ == "__main__":
    main()
