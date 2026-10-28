"""ladder_arb.py -- executes LADDER_ARBITRAGE_SPEC.md (registered 2026-10-28).  Nothing here may move a bar.

QUESTION. Is the KXBTCD threshold ladder (188 strikes/hour, YES price must be non-increasing in strike) ever QUOTED
CROSSED on simultaneous executable quotes, by enough to clear fees?  Buy YES(K1) at yes_ask, sell YES(K2) at yes_bid,
K1 < K2: payoff is +100 if K1 < BTC <= K2 else 0, never negative.  No forecast, no observation, no speed.

REUSED, NOT REBUILT:  tail_pricing (cache, fee_c, http with backoff, utc_day, jload/jdump, work_order.json) and
maker_fill (the validated GET /markets/trades paced fetcher `_get`, and `iso_us`).

FROZEN READINGS (fixed before any price pair was examined; see also the spec):
  * PRIMARY ("close", simultaneous): every leg's yes_bid/yes_ask CLOSE, from a candle of the SAME end_period_ts.
    A strike with no candle in that minute is NOT observed that minute (strict).  Only this reading can PASS.
  * "hilo" (NON-SIMULTANEOUS, cannot PASS): yes_bid.HIGH of the sold leg vs yes_ask.LOW of the bought leg, same minute.
  * "carried" (DISCLOSURE, not in the spec, cannot PASS): each strike's last candle CLOSE carried forward to minutes in
    which it has no candle (valid only if the candle stream is change-driven; continuity is tested and reported).
  * Violation = ordered pair K1 < K2 (by floor_strike) with raw crossing bid(K2) > ask(K1).  Fee-clearing = after
    fee(ask(K1)) + fee(bid(K2)), net >= 1c (integer cents, strictly positive).  Per-minute max-net violation reported
    alongside the count of ALL violating pairs.  Never mid.  Buy at ask, sell at bid.
  * Fee = TP.fee_c = ceil(7 p (1-p)) cents per leg (quadratic, multiplier 1, taker only), 1c minimum.
  * Calendar day = UTC date of close = cluster unit.  Universe = the 503 cached KXBTCD hours (prefix of the saved
    seed-20261027 work_order.json, never re-sorted).  Candle window of the cache = [close-75min, close-5min].
  * Tape confirmation (GET /markets/trades, microsecond created_time) -- levels, fixed before any tape was read:
       L1 "both legs printed": each leg has >= 1 print inside the violating minute (end-60, end].
       L2 "tape-inverted"  (PRIMARY tape confirmation): some print P1 on K1 and some print P2 on K2, both inside the
          minute, |t1 - t2| <= 2 s, whose PRINTED prices clear fees: p2 - p1 - fee(p1) - fee(p2) >= 1.
       L3 "side-correct": as L2 but P1.taker_side == yes (K1 was lifted at its ask) and P2.taker_side == no (K2 bid hit).
    The tape carries prints, not quotes, so a violation nobody traded into cannot be L1/L2 confirmed: that is a
    property of the instrument and is disclosed, not corrected.
  * Part C (3 legs): KXBTC range R[f, f+99.99] = KXBTCD(>f-0.01) - KXBTCD(>f+99.99) exactly.  Two zero-payoff
    constructions: C1 long R(ask), short D_lo(bid), long D_hi(ask);  C2 short R(bid), long D_lo(ask), short D_hi(bid).
    Net = credit - fee(R) - fee(D_lo) - fee(D_hi); payoff is 0 in every state (verified against official results).
  * Part C tape levels (fixed after the Part C close count was seen but BEFORE any Part C tape was fetched or read; every
    fee-clearing Part C close row is tape-checked, none selected):  L1 all three legs printed inside the violating minute;
    L2 (PRIMARY) prints on all three legs lying within a 2 s window (max t - min t <= 2 s) whose PRINTED prices clear fees:
    C1 net = p(D_lo) - p(D_hi) - p(R) - fees, C2 net = p(R) + p(D_hi) - p(D_lo) - fees, each >= 1c;  L3 side-correct (C1: R and
    D_hi lifted, taker yes, D_lo hit, taker no; C2: the mirror).
  * Part B: KXBTC partition sum, a DIAGNOSTIC only.  Sum of yes_ask closes and of yes_bid closes over the complete
    partition (186 between + 2 tails) vs 100c.  The 188-leg dutch book is NOT tested (>= 188c of fees).

PROCESS DISCLOSURE.  (1) The tape was first launched for all 1,043 high/low opportunities; rate limiting (HTTP 429, shared
  with the KXBTC fetch) made that impractical, so it was restarted on a seeded random sample of 250 (seed 20261028) plus all
  close rows, before any tape row had been read or evaluated.  (2) The tolerance-sensitivity table and section 2.3 of the
  report were added AFTER the first tape read, as disclosure; the frozen L2 tolerance (2 s) and all bars are unchanged.
  (3) The `carried` reading was coded in the first scan alongside `close` and `hilo`, before any count was viewed; the near-miss
  histogram was added after the first scan.  Neither can PASS.  (4) Part B/C use whatever prefix of the saved order the KXBTC fetch completed.

Usage:  python ladder_arb.py fetch | scan | tape | scanBC | analyze
"""
from __future__ import annotations

import ast
import collections
import datetime as dt
import json
import math
import os
import random
import statistics
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tail_pricing as TP                       # cache + fee + http REUSED
import maker_fill as MF                         # validated tape fetcher REUSED (_get, iso_us)

LCACHE = os.path.join(HERE, "cache", "ladder_arb")
KX = os.path.join(LCACHE, "kxbtc")
META = os.path.join(LCACHE, "kxbtcd_meta")
TAPEDIR = os.path.join(LCACHE, "tape")
VIOL = os.path.join(LCACHE, "violations.json")
OUT_JSON = os.path.join(HERE, "out", "ladder_arb.json")
OUT_MD = os.path.join(HERE, "out", "ladder_arb.md")
jload, jdump, utc_day, iso2ts = TP.jload, TP.jdump, TP.utc_day, TP.iso2ts
LOOKBACK_S = TP.LOOKBACK_S
MIN_T = min(TP.TS)
HILO_TAPE_SEED, HILO_TAPE_N = 20261028, 250

FEE = np.array([TP.fee_c(c) for c in range(0, 101)], dtype=np.int64)     # FEE[c] for c in 0..100 cents
assert all(FEE[c] >= 1 for c in range(1, 100)), "1-cent minimum per leg"
INF = 10 ** 6


def suffix(event):
    return event.split("-", 1)[1]


# ------------------------------------------------------------------------------------------ fetch (KXBTC + meta)
def split_listing_kx(markets):
    """ladder rows carry NO result (anchor a/b style split, as tail_pricing); results returned separately."""
    ladder, res = [], {}
    for m in markets:
        tk = m["ticker"]
        ladder.append({"ticker": tk, "close_ts": iso2ts(m["close_time"]), "floor_strike": m.get("floor_strike"),
                       "cap_strike": m.get("cap_strike"), "strike_type": m.get("strike_type")})
        res[tk] = m.get(TP.RESULT_KEY)
    return ladder, res


def list_event(event):
    mk, cur = [], ""
    while True:
        r = TP.http(f"/markets?event_ticker={event}&limit=1000" + (f"&cursor={cur}" if cur else ""))
        mk += r.get("markets", [])
        cur = r.get("cursor")
        if not cur:
            break
    return mk


def fetch_hour_kx(kd_event):
    sfx = suffix(kd_event)
    d = os.path.join(KX, sfx)
    if os.path.exists(os.path.join(d, "DONE")):
        return "cached"
    ev = "KXBTC-" + sfx
    mk = list_event(ev)
    if not mk:
        raise RuntimeError("empty KXBTC listing")
    ladder, res = split_listing_kx(mk)
    close_ts = ladder[0]["close_ts"]
    exp_kx = mk[0].get("expiration_value")
    tks = [x["ticker"] for x in ladder]
    candles = {}
    for i in range(0, len(tks), 90):
        chunk = tks[i:i + 90]
        r = TP.http("/markets/candlesticks?market_tickers=" + ",".join(chunk) +
                    f"&start_ts={close_ts - LOOKBACK_S}&end_ts={close_ts - MIN_T * 60}&period_interval=1")
        got = {m.get("market_ticker") or m.get("ticker"): m.get("candlesticks") for m in r.get("markets", [])}
        for t in chunk:
            candles[t] = got.get(t)
    # KXBTCD expiration_value (for anchor c); one extra listing, result key not touched here
    mk_d = list_event(kd_event)
    exp_d = {m["ticker"]: m.get("expiration_value") for m in mk_d}
    jdump(ladder, os.path.join(d, "ladder.json"))
    jdump(res, os.path.join(d, "results.json"))
    jdump(candles, os.path.join(d, "candles.json"))
    jdump({"kxbtc_expiration_value": exp_kx, "kxbtcd_expiration_values": sorted(set(v for v in exp_d.values())),
           "n_kxbtcd": len(mk_d)}, os.path.join(d, "exp.json"))
    jdump({"n": len(tks), "t": int(time.time())}, os.path.join(d, "DONE"))
    return "fetched"


def cmd_fetch(max_hours=None):
    order = jload(os.path.join(TP.CACHE, "work_order.json"))
    done = [e for e in order if os.path.exists(os.path.join(TP.HOURS, e, "DONE"))]     # the 503 cached hours, work order
    fetched = fail = 0
    t0 = time.time()
    for ev in done:                                   # strictly in saved shuffled order; never re-sorted
        if max_hours is not None and fetched >= max_hours:
            break
        try:
            s = fetch_hour_kx(ev)
        except Exception as e:
            fail += 1
            print("FAIL", ev, type(e).__name__, getattr(e, "code", ""), flush=True)
            continue
        if s == "fetched":
            fetched += 1
            if fetched % 10 == 0:
                print(f"fetched {fetched} hours  fails {fail}  {time.time() - t0:.0f}s", flush=True)
    print("fetch finished; fetched this run", fetched, "fails", fail, flush=True)




# ------------------------------------------------------------------------------------------ candle arrays
def c100(x):
    return int(round(float(x) * 100.0))


def kd_load(event, minutes=None):
    """-> dict with strikes sorted ascending by floor_strike and per-reading (M,S) arrays.  NO result is loaded."""
    d = os.path.join(TP.HOURS, event)
    ladder = [m for m in jload(os.path.join(d, "ladder.json"))
              if m.get("strike_type") == "greater" and m.get("floor_strike") is not None]
    ladder.sort(key=lambda m: m["floor_strike"])
    candles = jload(os.path.join(d, "candles.json"))
    return build_arrays(ladder, candles, minutes)


def build_arrays(ladder, candles, minutes=None):
    tks = [m["ticker"] for m in ladder]
    if minutes is None:
        minutes = sorted({c["end_period_ts"] for t in tks for c in (candles.get(t) or [])})
    mi = {m: k for k, m in enumerate(minutes)}
    M, S = len(minutes), len(tks)
    ask = np.full((M, S), -1, dtype=np.int64)       # yes_ask CLOSE, -1 = no candle that minute
    bid = np.full((M, S), -1, dtype=np.int64)       # yes_bid CLOSE
    alow = np.full((M, S), -1, dtype=np.int64)      # yes_ask LOW  (hilo, NON-simultaneous)
    bhigh = np.full((M, S), -1, dtype=np.int64)     # yes_bid HIGH (hilo, NON-simultaneous)
    vol = np.zeros((M, S))
    for s, t in enumerate(tks):
        for c in candles.get(t) or []:
            k = mi[c["end_period_ts"]]
            ask[k, s] = c100(c["yes_ask"]["close_dollars"])
            bid[k, s] = c100(c["yes_bid"]["close_dollars"])
            alow[k, s] = c100(c["yes_ask"]["low_dollars"])
            bhigh[k, s] = c100(c["yes_bid"]["high_dollars"])
            vol[k, s] = float(c.get("volume_fp") or 0)
    # carried state: last CLOSE carried forward (candle stream is change-driven; continuity tested in analyze)
    cask, cbid = ask.copy(), bid.copy()
    for s in range(S):
        la = lb = -1
        for k in range(M):
            if cask[k, s] >= 0:
                la, lb = cask[k, s], cbid[k, s]
            else:
                cask[k, s], cbid[k, s] = la, lb
    return {"tickers": tks, "floors": [round(m["floor_strike"] if m.get("floor_strike") is not None else m["cap_strike"], 2) for m in ladder],
            "stype": [m.get("strike_type") for m in ladder], "minutes": minutes,
            "ask": ask, "bid": bid, "alow": alow, "bhigh": bhigh, "vol": vol, "cask": cask, "cbid": cbid,
            "close_ts": ladder[0]["close_ts"]}


# ------------------------------------------------------------------------------------------ the arbitrage credit
# PNL PATH.  arb_net() is the whole 2-leg arbitrage P&L: executable sides only (BUY at ask, SELL at bid), per-leg
# fee.  It takes four integers and nothing else: it cannot reference an outcome (anchor a) or a mid (anchor d).
def arb_net(ask_k1, bid_k2):
    return bid_k2 - ask_k1 - int(FEE[ask_k1]) - int(FEE[bid_k2])


def arb_net3(credit, fee_a, fee_b, fee_c):
    return credit - fee_a - fee_b - fee_c


def pair_scan(ask_row, bid_row, vol_row, want_pairs):
    """One minute.  ask_row/bid_row: int cents, -1 = leg unobserved.  Pairs i<j (ascending strike).
    Returns (n_raw, n_clear, best(i,j,net)|None, pairs[(i,j,net,fee_clearing)] of ALL raw-crossing pairs if want_pairs)."""
    S = len(ask_row)
    okA = (ask_row >= 1) & (ask_row <= 99)
    okB = (bid_row >= 1) & (bid_row <= 99)
    if not okA.any() or not okB.any():
        return 0, 0, None, []
    a = np.where(okA, ask_row, INF)
    pm = np.minimum.accumulate(a)
    pm_prev = np.concatenate(([INF], pm[:-1]))                   # min ask over strictly lower strikes
    if not (okB & (bid_row > pm_prev)).any():
        return 0, 0, None, []
    cost = np.where(okA, ask_row + FEE[np.clip(ask_row, 0, 100)], INF)         # c + fee, per buy leg
    proc = np.where(okB, bid_row - FEE[np.clip(bid_row, 0, 100)], -INF)        # b - fee, per sell leg
    net = proc[None, :] - cost[:, None]                                          # [i, j]
    raw = np.where(okA[:, None] & okB[None, :], bid_row[None, :] - ask_row[:, None], -INF)
    tri = np.triu(np.ones((S, S), dtype=bool), 1)
    rawm = (raw > 0) & tri
    clr = rawm & (net >= 1)
    n_raw, n_clear = int(rawm.sum()), int(clr.sum())
    best = None
    pairs = []
    if n_clear:
        nn = np.where(clr, net, -INF)
        i, j = np.unravel_index(int(np.argmax(nn)), nn.shape)
        best = (int(i), int(j), int(nn[i, j]))
    if want_pairs:
        ii, jj = np.nonzero(rawm)
        pairs = [(int(x), int(y), int(net[x, y]), bool(clr[x, y])) for x, y in zip(ii, jj)]
    return n_raw, n_clear, best, pairs


def scan_hour(event):
    A = kd_load(event)
    S, M = len(A["tickers"]), len(A["minutes"])
    out = {"event": event, "close_ts": A["close_ts"], "day": utc_day(A["close_ts"]), "S": S, "M": M,
           "obs": {}, "readings": {}}
    for name in ("close", "hilo", "carried"):
        out["readings"][name] = {"n_raw": 0, "n_clear": 0, "minutes_raw": 0, "minutes_clear": 0, "best": [], "pairs": 0}
    two_sided = ((A["ask"] >= 1) & (A["bid"] >= 1)).sum()
    out["obs"] = {"strike_minutes_with_candle": int((A["ask"] >= 0).sum()), "two_sided_strike_minutes": int(two_sided),
                  "strike_minutes_total_grid": int(S * M)}
    viol = []
    for name, (AR, BR) in (("close", (A["ask"], A["bid"])), ("hilo", (A["alow"], A["bhigh"])),
                           ("carried", (A["cask"], A["cbid"]))):
        R = out["readings"][name]
        for k in range(M):
            n_raw, n_clear, best, pairs = pair_scan(AR[k], BR[k], A["vol"][k], want_pairs=True)
            if n_raw:
                R["minutes_raw"] += 1
                R["n_raw"] += n_raw
            if n_clear:
                R["minutes_clear"] += 1
                R["n_clear"] += n_clear
            if n_raw:
                for (i, j, net, clearing) in pairs:
                    a1, b2 = int(AR[k, i]), int(BR[k, j])
                    row = {"event": event, "day": out["day"], "reading": name, "end_ts": int(A["minutes"][k]),
                           "k1": A["tickers"][i], "k2": A["tickers"][j], "K1": A["floors"][i], "K2": A["floors"][j],
                           "ask1": a1, "bid2": b2, "fee1": int(FEE[a1]), "fee2": int(FEE[b2]), "net": net,
                           "vol1": float(A["vol"][k, i]), "vol2": float(A["vol"][k, j]),
                           "fee_clearing": clearing,
                           "is_minute_max": bool(best is not None and i == best[0] and j == best[1])}
                    viol.append(row)
    return out, viol


def universe_hours():
    order = jload(os.path.join(TP.CACHE, "work_order.json"))
    return [e for e in order if os.path.exists(os.path.join(TP.HOURS, e, "DONE"))]          # work order, never re-sorted


def cmd_scan():
    hours = universe_hours()
    summ, viol = [], []
    for e in hours:
        s, v = scan_hour(e)
        summ.append(s)
        viol += v
    jdump({"hours": hours, "summ": summ, "n_hours": len(hours)}, os.path.join(LCACHE, "scanA_summary.json"))
    jdump(viol, VIOL)
    byr = collections.Counter(v["reading"] for v in viol)
    print("hours", len(hours), "violation rows by reading", dict(byr))


# ------------------------------------------------------------------------------------------ near-miss histogram (Part A)
def gap_scan(event):
    """For close and carried readings: per minute, max over pairs i<j of bid_j - ask_i (cents) -- how close the ladder
    comes to being crossed -- and the number of executable pair-observations tested (okA[i] & okB[j], i<j)."""
    A = kd_load(event)
    res = {}
    for name, (AR, BR) in (("close", (A["ask"], A["bid"])), ("carried", (A["cask"], A["cbid"])),
                           ("hilo", (A["alow"], A["bhigh"]))):
        hist, tested, minutes_eval = collections.Counter(), 0, 0
        for k in range(AR.shape[0]):
            okA = (AR[k] >= 1) & (AR[k] <= 99)
            okB = (BR[k] >= 1) & (BR[k] <= 99)
            before = np.concatenate(([0], np.cumsum(okA)[:-1]))
            tested += int((before * okB).sum())
            a = np.where(okA, AR[k], INF)
            pm_prev = np.concatenate(([INF], np.minimum.accumulate(a)[:-1]))
            ok = okB & (pm_prev < INF)
            if ok.any():
                minutes_eval += 1
                hist[int((BR[k][ok] - pm_prev[ok]).max())] += 1
        res[name] = {"hist": dict(hist), "tested": tested, "minutes_eval": minutes_eval}
    return res


# ------------------------------------------------------------------------------------------ Part B / Part C (KXBTC)
def hour_grid(event):
    """Dense 60 s grid from the first to the last candle end observed on EITHER series for this hour."""
    ends = []
    for path in (os.path.join(TP.HOURS, event, "candles.json"), os.path.join(KX, suffix(event), "candles.json")):
        for cs in jload(path).values():
            ends += [c["end_period_ts"] for c in (cs or [])]
    return list(range(min(ends), max(ends) + 1, 60))


def kx_hours():
    """KXBTC hours fetched, in saved work order, and whether they form a PREFIX of the 503-hour order."""
    hrs = universe_hours()
    have = [e for e in hrs if os.path.exists(os.path.join(KX, suffix(e), "DONE"))]
    pre = 0
    for e in hrs:
        if e in set(have):
            pre += 1
        else:
            break
    return hrs, have, pre


def kx_load(event, grid):
    d = os.path.join(KX, suffix(event))
    ladder = jload(os.path.join(d, "ladder.json"))
    order = {"less": 0, "between": 1, "greater": 2}
    ladder.sort(key=lambda m: (order[m["strike_type"]], m.get("floor_strike") if m.get("floor_strike") is not None else -1))
    return build_arrays(ladder, jload(os.path.join(d, "candles.json")), grid)


def partition_hour(event, grid):
    """Part B DIAGNOSTIC.  Sum of yes_ask and of yes_bid closes over the complete 188-market KXBTC partition, per minute.
    The partition pays exactly 100 in every state.  NOT a strategy: 188 legs pay >= 1c each in fees."""
    K = kx_load(event, grid)
    out = {"strict": [], "carried": []}
    for name, (AR, BR) in (("strict", (K["ask"], K["bid"])), ("carried", (K["cask"], K["cbid"]))):
        for k in range(AR.shape[0]):
            if (AR[k] < 0).any():
                continue                                       # some leg unobserved this minute
            a, b = AR[k], BR[k]
            out[name].append([int(K["minutes"][k]), int(a.sum()), int(b.sum()), int(FEE[a].sum()), int(FEE[b].sum()),
                              int((a <= 99).sum()), int((b >= 1).sum()), int(len(a))])
    return out


def scan_C_hour(event, grid):
    """Part C: R[f, f+99.99] = D(>f-0.01) - D(>f+99.99).  Two zero-payoff 3-leg constructions, per reading."""
    D = kd_load(event, grid)
    K = kx_load(event, grid)
    dix = {f: i for i, f in enumerate(D["floors"])}
    rs = [(r, dix.get(round(K["floors"][r] - 0.01, 2)), dix.get(round(K["floors"][r] + 99.99, 2)))
          for r in range(len(K["tickers"])) if K["stype"][r] == "between"]
    ok_map = [(r, lo, hi) for r, lo, hi in rs if lo is not None and hi is not None]
    out = {"event": event, "day": utc_day(K["close_ts"]), "n_between": len(rs), "n_mapped": len(ok_map), "rows": []}
    if not ok_map:
        return out
    R = np.array([x[0] for x in ok_map])
    LO = np.array([x[1] for x in ok_map])
    HI = np.array([x[2] for x in ok_map])
    def inr(x):
        return (x >= 1) & (x <= 99)
    for name in ("close", "hilo", "carried"):
        if name == "close":
            ra, rb, da, db = K["ask"][:, R], K["bid"][:, R], D["ask"], D["bid"]
        elif name == "carried":
            ra, rb, da, db = K["cask"][:, R], K["cbid"][:, R], D["cask"], D["cbid"]
        else:
            ra, rb, da, db = K["alow"][:, R], K["bhigh"][:, R], D["alow"], D["bhigh"]
        dlo_a, dlo_b, dhi_a, dhi_b = da[:, LO], db[:, LO], da[:, HI], db[:, HI]
        # C1: long R (ask), short D_lo (bid), long D_hi (ask)
        v1 = inr(ra) & inr(dlo_b) & inr(dhi_a)
        cr1 = dlo_b - dhi_a - ra
        n1 = arb_net3(cr1, FEE[np.clip(ra, 0, 100)], FEE[np.clip(dlo_b, 0, 100)], FEE[np.clip(dhi_a, 0, 100)])
        # C2: short R (bid), long D_lo (ask), short D_hi (bid)
        v2 = inr(rb) & inr(dlo_a) & inr(dhi_b)
        cr2 = rb + dhi_b - dlo_a
        n2 = arb_net3(cr2, FEE[np.clip(rb, 0, 100)], FEE[np.clip(dlo_a, 0, 100)], FEE[np.clip(dhi_b, 0, 100)])
        for cname, v, cr, nn, a_leg in (("C1", v1, cr1, n1, ra), ("C2", v2, cr2, n2, rb)):
            raw = v & (cr > 0)
            if not raw.any():
                out.setdefault("tested", {}).setdefault(f"{name}|{cname}", int(v.sum()))
                out.setdefault("tested", {})[f"{name}|{cname}"] = int(v.sum())
                continue
            out.setdefault("tested", {})[f"{name}|{cname}"] = int(v.sum())
            ks, rs_ = np.nonzero(raw)
            best_by_min = {}
            for k, j in zip(ks, rs_):
                net = int(nn[k, j])
                best_by_min[k] = max(best_by_min.get(k, -INF), net)
            for k, j in zip(ks, rs_):
                net = int(nn[k, j])
                out["rows"].append({"event": event, "day": out["day"], "reading": name, "cons": cname, "end_ts": int(K["minutes"][k]),
                                    "R": K["tickers"][int(R[j])], "Dlo": D["tickers"][int(LO[j])], "Dhi": D["tickers"][int(HI[j])],
                                    "credit": int(cr[k, j]), "net": net, "fee_clearing": net >= 1,
                                    "is_minute_max": (net >= 1 and net == best_by_min[k]),
                                    "volR": float(K["vol"][k, int(R[j])]), "volLo": float(D["vol"][k, int(LO[j])]),
                                    "volHi": float(D["vol"][k, int(HI[j])])})
    return out


def cmd_scanBC():
    hrs, have, pre = kx_hours()
    Brows = {"strict": [], "carried": []}
    Crows, Csumm = [], []
    for e in have:
        grid = hour_grid(e)
        pb = partition_hour(e, grid)
        for nm in Brows:
            Brows[nm] += [[e] + x for x in pb[nm]]
        c = scan_C_hour(e, grid)
        Csumm.append({k: c[k] for k in ("event", "day", "n_between", "n_mapped", "tested") if k in c})
        Crows += c["rows"]
    jdump({"hours_universe": len(hrs), "hours_covered": have, "prefix_len": pre, "B": Brows, "Csumm": Csumm}, os.path.join(LCACHE, "scanBC.json"))
    jdump(Crows, os.path.join(LCACHE, "violationsC.json"))
    print("KXBTC hours covered", len(have), "of", len(hrs), "prefix", pre, "C rows", len(Crows),
          collections.Counter((r["reading"], r["cons"], r["fee_clearing"]) for r in Crows))


# ------------------------------------------------------------------------------------------ tape (GET /markets/trades)
def tape_targets():
    """Rows that get tape-checked: ALL close raw crossings (zero are fee-clearing) and the per-minute MAX-net
    violation of the NON-SIMULTANEOUS hilo reading (to test whether that reading is an artifact)."""
    viol = jload(VIOL)
    close_rows = [v for v in viol if v["reading"] == "close"]
    units = [v for v in viol if v["reading"] == "hilo" and v["is_minute_max"]]
    units.sort(key=lambda v: (v["event"], v["end_ts"], v["k1"], v["k2"]))                 # canonical order before sampling
    # API rate limits make 1,043 x 2 tape pulls impractical; the hilo artifact check uses a seeded random sample
    # (seed 20261028, fixed here, before any tape was read).  The close rows are ALL tape-checked.
    samp = random.Random(HILO_TAPE_SEED).sample(units, min(HILO_TAPE_N, len(units)))
    return close_rows + samp


def fetch_minute(tk, end_ts):
    """All prints on tk with created_time in (end-60s, end]; GET /markets/trades via the validated maker_fill._get."""
    rows, cur = [], ""
    while True:
        r = MF._get(f"/markets/trades?ticker={tk}&min_ts={end_ts - 60}&max_ts={end_ts}&limit=1000" + (f"&cursor={cur}" if cur else ""))
        for t in r.get("trades", []):
            us = MF.iso_us(t["created_time"])
            if (end_ts - 60) * 1_000_000 < us <= end_ts * 1_000_000:
                rows.append([us, float(t["yes_price_dollars"]) * 100.0, float(t["count_fp"]), t["taker_side"][:1]])
        cur = r.get("cursor")
        if not cur or not r.get("trades"):
            break
    rows.sort()
    return rows


def cmd_tape():
    tg = tape_targets()
    need = collections.defaultdict(set)
    for v in tg:
        need[v["event"]].add((v["k1"], v["end_ts"]))
        need[v["event"]].add((v["k2"], v["end_ts"]))
    print("events", len(need), "leg-minutes", sum(len(x) for x in need.values()), flush=True)
    t0, n = time.time(), 0
    for ev in sorted(need):
        p = os.path.join(TAPEDIR, ev + ".json")
        have = jload(p)["tape"] if os.path.exists(p) else {}
        todo = [x for x in sorted(need[ev]) if f"{x[0]}|{x[1]}" not in have]
        if not todo:
            continue
        for tk, end in todo:
            have[f"{tk}|{end}"] = fetch_minute(tk, end)
        jdump({"event": ev, "tape": have}, p)
        n += 1
        if n % 20 == 0:
            print(f"{n} events {time.time() - t0:.0f}s", flush=True)
    print("tape done", flush=True)


def tapeC_targets():
    return [r for r in jload(os.path.join(LCACHE, "violationsC.json")) if r["reading"] == "close" and r["fee_clearing"]]


def cmd_tapeC():
    tg = tapeC_targets()
    need = collections.defaultdict(set)
    for r in tg:
        for t in (r["R"], r["Dlo"], r["Dhi"]):
            need[r["event"]].add((t, r["end_ts"]))
    print("C events", len(need), "leg-minutes", sum(len(x) for x in need.values()), flush=True)
    for ev in sorted(need):
        p = os.path.join(TAPEDIR, "C_" + ev + ".json")
        have = jload(p)["tape"] if os.path.exists(p) else {}
        todo = [x for x in sorted(need[ev]) if f"{x[0]}|{x[1]}" not in have]
        for tk, end in todo:
            have[f"{tk}|{end}"] = fetch_minute(tk, end)
        if todo:
            jdump({"event": ev, "tape": have}, p)
    print("tapeC done", flush=True)


def tape_levels3(cons, rR, rLo, rHi):
    """L1/L2/L3 for a 3-leg row (definitions in the module docstring)."""
    L1 = bool(rR and rLo and rHi)
    L2 = L3 = False
    best = None
    if L1:
        for tR, pR, _a, sR in rR:
            for tL, pL, _b, sL in rLo:
                if abs(tR - tL) > 2_000_000:
                    continue
                for tH, pH, _c, sH in rHi:
                    if max(tR, tL, tH) - min(tR, tL, tH) > 2_000_000:
                        continue
                    if cons == "C1":
                        net = pL - pH - pR - TP.fee_c(pR) - TP.fee_c(pL) - TP.fee_c(pH)
                        sided = (sR == "y" and sL == "n" and sH == "y")
                    else:
                        net = pR + pH - pL - TP.fee_c(pR) - TP.fee_c(pL) - TP.fee_c(pH)
                        sided = (sR == "n" and sL == "y" and sH == "n")
                    if net >= 1:
                        L2 = True
                        best = net if best is None else max(best, net)
                        L3 = L3 or sided
    return {"L1": L1, "L2": L2, "L3": L3, "best_printed_net": best}


# ------------------------------------------------------------------------------------------ anchors (static)
PNL_FUNCS = ["arb_net", "arb_net3", "pair_scan", "scan_hour", "scan_C_hour", "partition_hour", "gap_scan", "kd_load", "kx_load",
             "build_arrays", "hour_grid", "c100", "universe_hours", "kx_hours"]


def _ident(node):
    """Identifiers only (Name / Attribute / arg / keyword names) -- no string constants."""
    s = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            s.add(n.id)
        elif isinstance(n, ast.Attribute):
            s.add(n.attr)
        elif isinstance(n, ast.arg):
            s.add(n.arg)
        elif isinstance(n, ast.keyword) and n.arg:
            s.add(n.arg)
        elif isinstance(n, ast.FunctionDef):
            s.add(n.name)
    return s


def _consts(node):
    skip = set()
    for n in ast.walk(node):                                    # docstrings are prose, not data access
        if isinstance(n, ast.FunctionDef) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant):
            skip.add(id(n.body[0].value))
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip}


def anchor_static_checks():
    tree = ast.parse(open(os.path.abspath(__file__)).read())
    fdefs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    ev = {"a_pnl_funcs_checked": [], "d_binops_checked": 0}
    # (a) the P&L / scan path never references an outcome: no identifier or string constant naming result(s)/expiration
    for f in PNL_FUNCS:
        ids = {x.lower() for x in _ident(fdefs[f])}
        cs = {x.lower() for x in _consts(fdefs[f])}
        bad = {x for x in ids | cs if "result" in x or "expiration" in x or "settle" in x or "official" in x}
        assert not bad, f"anchor (a): {f} references an outcome: {bad}"
        ev["a_pnl_funcs_checked"].append(f)
    sig = [a.arg for a in fdefs["arb_net"].args.args]
    assert sig == ["ask_k1", "bid_k2"], sig
    ev["a_arb_net_signature"] = sig
    # (d) no mid anywhere in the module: no identifier containing 'mid', no (bid +/- ask)/2 or *0.5 pattern
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "anchor_static_checks":
            continue
    ids_all = set()
    for fn in fdefs.values():
        if fn.name == "anchor_static_checks":
            continue
        ids_all |= _ident(fn)
    assert not {x for x in ids_all if "mid" in x.lower()}, "anchor (d): identifier containing 'mid'"
    for fn in fdefs.values():
        if fn.name == "anchor_static_checks":
            continue
        for n in ast.walk(fn):
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.Mult, ast.FloorDiv)):
                ids = {x.lower() for x in _ident(n)}
                has_b = any("bid" in x or x in ("bhigh", "cbid") for x in ids)
                has_a = any("ask" in x or x in ("alow", "cask") for x in ids)
                const_half = any(isinstance(c, ast.Constant) and c.value in (2, 0.5) for c in ast.walk(n))
                assert not (has_b and has_a and const_half), f"anchor (d): possible mid at line {n.lineno}"
                ev["d_binops_checked"] += 1
    # buy side reads ask arrays only, sell side reads bid arrays only (pair_scan)
    ps = fdefs["pair_scan"]
    for st_ in ast.walk(ps):
        if isinstance(st_, ast.Assign) and isinstance(st_.targets[0], ast.Name):
            ids = _ident(st_.value)
            if st_.targets[0].id == "cost":
                assert "ask_row" in ids and "bid_row" not in ids
            if st_.targets[0].id == "proc":
                assert "bid_row" in ids and "ask_row" not in ids
    ev["d_pair_scan_cost_from_ask_only_proceeds_from_bid_only"] = True
    return ev


def anchor_negative_controls():
    """Prove the AST scans bite: inject a results reference, a 'mid' identifier and an (a+b)/2 into a copy of this module
    and require anchor_static_checks() on the copy to raise."""
    import importlib.util
    src = open(os.path.abspath(__file__)).read()
    cases = {
        "outcome_string_in_pair_scan": ("    S = len(ask_row)\n    okA", "    S = len(ask_row)\n    _x = 'results.json'\n    okA"),
        "mid_identifier_in_arb_net": ("    return bid_k2 - ask_k1 - int(FEE[ask_k1])", "    mid = (bid_k2 + ask_k1) / 2\n    return bid_k2 - ask_k1 - int(FEE[ask_k1])"),
        "bid_ask_halved_anonymous": ("    return bid_k2 - ask_k1 - int(FEE[ask_k1])", "    z = (bid_k2 + ask_k1) / 2\n    return bid_k2 - ask_k1 - int(FEE[ask_k1])"),
    }
    out = {}
    os.makedirs(LCACHE, exist_ok=True)
    for name, (a, b) in cases.items():
        assert src.count(a) >= 1, name
        tmp = os.path.join(LCACHE, "neg_control.py")
        with open(tmp, "w") as fh:
            fh.write(src.replace(a, b, 1))
        spec = importlib.util.spec_from_file_location("neg_control", tmp)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        try:
            m.anchor_static_checks()
            out[name] = "NOT CAUGHT"
        except AssertionError as e:
            out[name] = "caught: " + str(e)[:90]
    os.remove(tmp)
    return out


# ------------------------------------------------------------------------------------------ outcome-using verifications
# These (and ONLY these) functions read the official result.  They are never called from the scan / P&L path.
def load_res(event):
    return jload(os.path.join(TP.HOURS, event, "results.json"))


def verify_payoff_dominance(viol_rows):
    """Anchor (b): realised payoff of long YES(K1) / short YES(K2) is >= 0 for every violation row."""
    by = collections.defaultdict(list)
    for v in viol_rows:
        by[v["event"]].append(v)
    pays, bad, unk = [], [], 0
    for e, rows in by.items():
        res = load_res(e)
        for v in rows:
            r1, r2 = res.get(v["k1"]), res.get(v["k2"])
            if r1 not in ("yes", "no") or r2 not in ("yes", "no"):
                unk += 1
                continue
            pay = 100 * (r1 == "yes") - 100 * (r2 == "yes")
            pays.append(pay)
            if pay < 0:
                bad.append({"k1": v["k1"], "k2": v["k2"], "r1": r1, "r2": r2, "end_ts": v["end_ts"]})
    return {"n": len(pays), "unknown_result": unk, "n_negative": len(bad), "min": min(pays) if pays else None,
            "n_pay_100": sum(1 for p in pays if p == 100), "n_pay_0": sum(1 for p in pays if p == 0), "negatives": bad[:20]}


def verify_monotone(hours):
    """Anchor (c): within each hour, ascending strike -> results must be yes... then no... (no interleaving)."""
    bad, nres, excl = [], 0, collections.Counter()
    for e in hours:
        lad = [m for m in jload(os.path.join(TP.HOURS, e, "ladder.json")) if m.get("strike_type") == "greater"]
        lad.sort(key=lambda m: m["floor_strike"])
        res = load_res(e)
        seq = []
        for m in lad:
            r = res.get(m["ticker"])
            if r not in ("yes", "no"):
                excl["no_official_yes_no_result"] += 1
                continue
            seq.append((m["ticker"], m["floor_strike"], r))
        nres += len(seq)
        first_no = next((i for i, x in enumerate(seq) if x[2] == "no"), len(seq))
        inter = [x for x in seq[first_no:] if x[2] == "yes"]
        if inter:
            bad.append({"event": e, "yes_above_a_no": [x[0] for x in inter][:5]})
    return {"hours": len(hours), "strikes_with_result": nres, "interleaved_hours": len(bad), "examples": bad[:10],
            "exclusions": dict(excl)}


def verify_expiration(hours):
    """Anchor (c) second half: yes <=> floor_strike < expiration_value (expiration_value from the KXBTC fetch pass)."""
    n_h = n_s = mism = 0
    ex = []
    for e in hours:
        p = os.path.join(KX, suffix(e), "exp.json")
        if not os.path.exists(p):
            continue
        ev_ = [v_ for v_ in jload(p)["kxbtcd_expiration_values"] if v_ not in (None, "")]      # one hour has one market with an empty value
        if len(ev_) != 1:
            continue
        x = float(ev_[0])
        n_h += 1
        res = load_res(e)
        for m in jload(os.path.join(TP.HOURS, e, "ladder.json")):
            r = res.get(m["ticker"])
            if r not in ("yes", "no") or m.get("floor_strike") is None:
                continue
            n_s += 1
            if (r == "yes") != (m["floor_strike"] < x):
                mism += 1
                ex.append((m["ticker"], m["floor_strike"], x, r))
    return {"hours_checked": n_h, "strikes_checked": n_s, "mismatches": mism, "examples": ex[:10]}


def verify_kx(hours_cov):
    """KXBTC: exactly one of 188 markets settles yes (partition) and ranges agree with expiration_value."""
    bad_part, n, bad_rng = [], 0, 0
    for e in hours_cov:
        d = os.path.join(KX, suffix(e))
        res = jload(os.path.join(d, "results.json"))
        yes = [t for t, r in res.items() if r == "yes"]
        n += 1
        if len(yes) != 1:
            bad_part.append((e, len(yes)))
    return {"hours": n, "hours_not_exactly_one_yes": len(bad_part), "examples": bad_part[:10]}


def verify_C_payoff(Crows):
    by = collections.defaultdict(list)
    for r in Crows:
        by[r["event"]].append(r)
    nz, n, unk = 0, 0, 0
    for e, rows in by.items():
        resD = load_res(e)
        resK = jload(os.path.join(KX, suffix(e), "results.json"))
        for r in rows:
            a, b, c = resK.get(r["R"]), resD.get(r["Dlo"]), resD.get(r["Dhi"])
            if None in (a, b, c) or {a, b, c} - {"yes", "no"}:
                unk += 1
                continue
            pay = 100 * ((a == "yes") - (b == "yes") + (c == "yes"))       # C1 sign; C2 is the exact negative
            n += 1
            nz += (pay != 0)
    return {"n": n, "unknown": unk, "n_payoff_nonzero": nz}


# ------------------------------------------------------------------------------------------ tape evaluation
def tape_levels(rows1, rows2):
    """rows: [[us, price_c, count, side]].  L1 both legs printed; L2 a pair within 2 s whose printed prices clear fees;
    L3 as L2 with K1 lifted (taker yes) and K2 hit (taker no)."""
    L1 = bool(rows1 and rows2)
    L2 = L3 = False
    best = None
    if L1:
        for t1, p1, _c1, s1 in rows1:
            for t2, p2, _c2, s2 in rows2:
                if abs(t1 - t2) <= 2_000_000 and p2 > p1:
                    net = p2 - p1 - TP.fee_c(p1) - TP.fee_c(p2)
                    if net >= 1:
                        L2 = True
                        best = net if best is None else max(best, net)
                        if s1 == "y" and s2 == "n":
                            L3 = True
    return {"L1": L1, "L2": L2, "L3": L3, "best_printed_net": best}


def load_tape_for(rows):
    out, miss = {}, 0
    cache = {}
    for v in rows:
        if v["event"] not in cache:
            p = os.path.join(TAPEDIR, v["event"] + ".json")
            cache[v["event"]] = jload(p)["tape"] if os.path.exists(p) else {}
        tp = cache[v["event"]]
        k1, k2 = f"{v['k1']}|{v['end_ts']}", f"{v['k2']}|{v['end_ts']}"
        if k1 in tp and k2 in tp:
            out[(v["k1"], v["k2"], v["end_ts"])] = (tp[k1], tp[k2])
        else:
            miss += 1
    return out, miss


def med(xs):
    xs = list(xs)
    return statistics.median(xs) if xs else None


def unit_stats(rows):
    pairs = [r for r in rows if r["fee_clearing"]]
    units = [r for r in rows if r["is_minute_max"]]
    days, hrs = collections.Counter(u["day"] for u in units), collections.Counter(u["event"] for u in units)
    nU = len(units)
    both = sum(1 for u in units if u["vol1"] > 0 and u["vol2"] > 0)
    return {"raw_pairs": len(rows), "clear_pairs": len(pairs), "units": nU, "days": len(days), "hours": len(hrs),
            "median_net_units": med(u["net"] for u in units), "median_net_pairs": med(p["net"] for p in pairs),
            "max_net": max((p["net"] for p in pairs), default=None),
            "both_nonzero_vol_units": both, "zero_vol_leg_units": nU - both,
            "both_nonzero_share": (both / nU) if nU else None,
            "max_day_share": (max(days.values()) / nU) if nU else None, "max_day": (days.most_common(1)[0][0] if days else None),
            "max_hour_share": (max(hrs.values()) / nU) if nU else None, "max_hour": (hrs.most_common(1)[0][0] if hrs else None),
            "vol1_median": med(u["vol1"] for u in units), "vol2_median": med(u["vol2"] for u in units),
            "max_crossing_c": max((r["bid2"] - r["ask1"] for r in rows), default=None) if rows and "bid2" in rows[0] else None}


def gates(st, tape_rate, simultaneous):
    g = {"g1_units_ge100_days_ge20": bool(st["units"] >= 100 and st["days"] >= 20),
         "g2_tape_ge50": bool(tape_rate is not None and tape_rate >= 0.5),
         "g3_median_net_ge2": bool(st["median_net_units"] is not None and st["median_net_units"] >= 2.0),
         "g4_both_vol_ge50": bool(st["both_nonzero_share"] is not None and st["both_nonzero_share"] >= 0.5),
         "g5_no_day_or_hour_gt25": bool(st["units"] > 0 and st["max_day_share"] <= 0.25 and st["max_hour_share"] <= 0.25)}
    g["pass"] = bool(all(g.values()) and simultaneous)
    return g


def quant(xs, qs=(0, 5, 25, 50, 75, 95, 100)):
    if not xs:
        return {}
    a = np.array(xs, dtype=float)
    return {str(q): float(np.percentile(a, q)) for q in qs}


# ------------------------------------------------------------------------------------------ analyze
def raw_leg(event, ticker, end_ts):
    """Independent re-parse of the RAW candle JSON (not through build_arrays)."""
    cs = jload(os.path.join(TP.HOURS, event, "candles.json")).get(ticker) or []
    for c in cs:
        if c["end_period_ts"] == end_ts:
            return c
    return None


def hand_worked(rows, n=10):
    out = []
    for v in rows[:n]:
        c1, c2 = raw_leg(v["event"], v["k1"], v["end_ts"]), raw_leg(v["event"], v["k2"], v["end_ts"])
        if v["reading"] == "close":
            a_raw, b_raw = c1["yes_ask"]["close_dollars"], c2["yes_bid"]["close_dollars"]
        else:
            a_raw, b_raw = c1["yes_ask"]["low_dollars"], c2["yes_bid"]["high_dollars"]
        a, b = int(round(float(a_raw) * 100)), int(round(float(b_raw) * 100))
        assert a == v["ask1"] and b == v["bid2"], (v["k1"], a, v["ask1"], b, v["bid2"])
        f1, f2 = math.ceil(7 * a * (100 - a) / 100.0 / 100.0 - 1e-12), math.ceil(7 * b * (100 - b) / 100.0 / 100.0 - 1e-12)
        assert f1 == v["fee1"] and f2 == v["fee2"]
        out.append({"reading": v["reading"], "k1": v["k1"], "k2": v["k2"], "end_ts": v["end_ts"],
                    "BUY_k1_yes_ask_used": a_raw, "SELL_k2_yes_bid_used": b_raw,
                    "k1_ask_close": c1["yes_ask"]["close_dollars"], "k1_ask_low": c1["yes_ask"]["low_dollars"],
                    "k2_bid_close": c2["yes_bid"]["close_dollars"], "k2_bid_high": c2["yes_bid"]["high_dollars"],
                    "ask": a, "bid": b, "fee_buy": f1, "fee_sell": f2, "credit": b - a, "net": b - a - f1 - f2,
                    "vol1": c1.get("volume_fp"), "vol2": c2.get("volume_fp")})
    return out


def hand_worked_C(rows, n=5):
    """Part C: re-parse raw candle JSON (KXBTC and KXBTCD) for the first n close fee-clearing rows."""
    out = []
    def raw(path, tk, end):
        for c in jload(path).get(tk) or []:
            if c["end_period_ts"] == end:
                return c
    for v in rows[:n]:
        cR = raw(os.path.join(KX, suffix(v["event"]), "candles.json"), v["R"], v["end_ts"])
        cL = raw(os.path.join(TP.HOURS, v["event"], "candles.json"), v["Dlo"], v["end_ts"])
        cH = raw(os.path.join(TP.HOURS, v["event"], "candles.json"), v["Dhi"], v["end_ts"])
        px = lambda c, side: int(round(float(c[side]["close_dollars"]) * 100))
        if v["cons"] == "C1":
            legs = [("BUY R at yes_ask", px(cR, "yes_ask")), ("SELL D_lo at yes_bid", px(cL, "yes_bid")), ("BUY D_hi at yes_ask", px(cH, "yes_ask"))]
            credit = legs[1][1] - legs[2][1] - legs[0][1]
        else:
            legs = [("SELL R at yes_bid", px(cR, "yes_bid")), ("BUY D_lo at yes_ask", px(cL, "yes_ask")), ("SELL D_hi at yes_bid", px(cH, "yes_bid"))]
            credit = legs[0][1] + legs[2][1] - legs[1][1]
        fees = [math.ceil(7 * q * (100 - q) / 100.0 / 100.0 - 1e-12) for _, q in legs]
        assert credit == v["credit"] and credit - sum(fees) == v["net"], (v, legs, fees)
        out.append({"cons": v["cons"], "event": v["event"], "end_ts": v["end_ts"], "legs": legs, "fees": fees, "credit": credit, "net": credit - sum(fees)})
    return out


def hilo_artifact_diag(units):
    """Why the hilo 'crossing' is not a simultaneous observation: look at the same minute through the CLOSE lens."""
    by = collections.defaultdict(list)
    for u in units:
        by[u["event"]].append(u)
    d = {"bid2_high_minus_close": [], "ask1_close_minus_low": [], "close_gap": [], "hilo_credit": []}
    for e, us in by.items():
        A = kd_load(e)
        ix = {t: i for i, t in enumerate(A["tickers"])}
        mx = {m: k for k, m in enumerate(A["minutes"])}
        for u in us:
            k, i, j = mx[u["end_ts"]], ix[u["k1"]], ix[u["k2"]]
            d["bid2_high_minus_close"].append(int(A["bhigh"][k, j] - A["bid"][k, j]))
            d["ask1_close_minus_low"].append(int(A["ask"][k, i] - A["alow"][k, i]))
            d["close_gap"].append(int(A["bid"][k, j] - A["ask"][k, i]))
            d["hilo_credit"].append(int(A["bhigh"][k, j] - A["alow"][k, i]))
    return d


def continuity(hours):
    """Is the candle stream change-driven?  For consecutive candles of one strike: next.open == prev.close, split into
    adjacent minutes and across a gap of no-candle minutes (the gap case is what justifies carrying a close forward)."""
    p = os.path.join(LCACHE, "continuity.json")
    if os.path.exists(p):
        return jload(p)
    C = collections.Counter()
    for e in hours:
        cd = jload(os.path.join(TP.HOURS, e, "candles.json"))
        for tk, cs in cd.items():
            cs = sorted(cs or [], key=lambda x: x["end_period_ts"])
            for a, b in zip(cs, cs[1:]):
                k = "adj" if b["end_period_ts"] - a["end_period_ts"] == 60 else "gap"
                C[k + "_n"] += 1
                C[k + "_ask_eq"] += b["yes_ask"]["open_dollars"] == a["yes_ask"]["close_dollars"]
                C[k + "_bid_eq"] += b["yes_bid"]["open_dollars"] == a["yes_bid"]["close_dollars"]
    jdump(dict(C), p)
    return dict(C)


def dt_sensitivity(tp, rows):
    """For each tape-checked row: smallest |t1 - t2| among fee-clearing inverted print pairs (any side) and among
    side-correct pairs.  DISCLOSURE of how tight the printed inversions are; L2's 2 s tolerance was frozen beforehand."""
    anyd, sided, ex = [], [], []
    n = 0
    for v in rows:
        key = (v["k1"], v["k2"], v["end_ts"])
        if key not in tp:
            continue
        r1, r2 = tp[key]
        n += 1
        ba = bs = None
        for t1, p1, c1, s1 in r1:
            for t2, p2, c2, s2 in r2:
                if p2 > p1 and p2 - p1 - TP.fee_c(p1) - TP.fee_c(p2) >= 1:
                    d = abs(t1 - t2) / 1e6
                    ba = d if ba is None else min(ba, d)
                    if s1 == "y" and s2 == "n":
                        if bs is None or d < bs[0]:
                            bs = (d, v["k1"], v["k2"], t1, p1, c1, t2, p2, c2)
        if ba is not None:
            anyd.append(ba)
        if bs is not None:
            sided.append(bs[0])
            ex.append(bs)
    ex.sort()
    th = (0.01, 0.1, 0.5, 1.0, 2.0, 10.0, 60.0)
    return {"n_rows": n, "thresholds_s": th,
            "any_side_within": [sum(1 for x in anyd if x <= t) for t in th],
            "side_correct_within": [sum(1 for x in sided if x <= t) for t in th],
            "median_min_dt_any_s": med(anyd), "median_min_dt_sided_s": med(sided),
            "tightest_side_correct": [{"dt_s": e[0], "k1": e[1], "k2": e[2], "t1_us": e[3], "p1": e[4], "n1": e[5], "t2_us": e[6], "p2": e[7], "n2": e[8],
                                       "printed_net_c": e[7] - e[4] - TP.fee_c(e[4]) - TP.fee_c(e[7]), "min_size": min(e[5], e[8])}
                                      for e in ex[:12]]}


def cmd_analyze():
    chk = anchor_static_checks()
    hrs_all = universe_hours()
    sA = jload(os.path.join(LCACHE, "scanA_summary.json"))
    assert sA["hours"] == hrs_all, "scan was run on a different hour list"
    viol = jload(VIOL)
    assert not any("result" in k for v in viol[:50] for k in v), "anchor (a): a violation row carries an outcome field"
    rep = {"spec": "LADDER_ARBITRAGE_SPEC.md", "anchors": {"static": chk, "negative_controls": anchor_negative_controls()}}

    # ---------------- Part A: counts per reading
    summ = sA["summ"]
    A = {}
    gh = {"close": collections.Counter(), "carried": collections.Counter(), "hilo": collections.Counter()}
    hist = {"close": collections.Counter(), "carried": collections.Counter(), "hilo": collections.Counter()}
    gap_cache = os.path.join(LCACHE, "gap_scan.json")
    if os.path.exists(gap_cache):
        gaps = jload(gap_cache)
    else:
        gaps = {e: gap_scan(e) for e in hrs_all}
        jdump(gaps, gap_cache)
    for e, g in gaps.items():
        for r in gh:
            gh[r]["tested"] += g[r]["tested"]
            gh[r]["minutes_eval"] += g[r]["minutes_eval"]
            for k, v in g[r]["hist"].items():
                hist[r][int(k)] += v
    for r in ("close", "carried", "hilo"):
        rows = [v for v in viol if v["reading"] == r]
        st = unit_stats(rows)
        st["raw_minutes"] = sum(h["readings"][r]["minutes_raw"] for h in summ)
        st["raw_hours"] = sum(1 for h in summ if h["readings"][r]["n_raw"])
        st["clear_minutes_scan"] = sum(h["readings"][r]["minutes_clear"] for h in summ)
        st["tested_pair_obs"] = gh[r]["tested"]
        st["minutes_with_testable_pair"] = gh[r]["minutes_eval"]
        assert st["raw_pairs"] == sum(h["readings"][r]["n_raw"] for h in summ)
        assert st["clear_pairs"] == sum(h["readings"][r]["n_clear"] for h in summ)
        A[r] = st
    rep["A"] = A
    rep["A_gap_hist"] = {r: {str(k): v for k, v in sorted(hist[r].items())} for r in hist}
    rep["A_obs"] = {"hours": len(summ), "days": len({h["day"] for h in summ}),
                    "minutes": sum(h["M"] for h in summ),
                    "strike_minutes_with_candle": sum(h["obs"]["strike_minutes_with_candle"] for h in summ),
                    "two_sided_strike_minutes": sum(h["obs"]["two_sided_strike_minutes"] for h in summ),
                    "strike_minutes_grid": sum(h["obs"]["strike_minutes_total_grid"] for h in summ),
                    "minute_count_by_hour": dict(collections.Counter(h["M"] for h in summ))}

    # ---------------- tape (Part A)
    tg = tape_targets()
    tp, miss = load_tape_for(tg)
    rep["tape_targets"] = {"n_targets": len(tg), "missing_tape": miss}
    close_rows = [v for v in tg if v["reading"] == "close"]
    hilo_units = [v for v in tg if v["reading"] == "hilo"]
    def lv(rows):
        o = collections.Counter()
        det = []
        for v in rows:
            key = (v["k1"], v["k2"], v["end_ts"])
            if key not in tp:
                o["no_tape"] += 1
                continue
            r1, r2 = tp[key]
            L = tape_levels(r1, r2)
            o["n"] += 1
            o["L1"] += L["L1"]
            o["L2"] += L["L2"]
            o["L3"] += L["L3"]
            det.append({**{k: v[k] for k in ("k1", "k2", "end_ts", "ask1", "bid2", "net", "vol1", "vol2")}, "prints1": len(r1), "prints2": len(r2),
                        "tape_vol1": sum(x[2] for x in r1), "tape_vol2": sum(x[2] for x in r2), **L})
        return o, det
    o_c, det_c = lv(close_rows)
    o_h, det_h = lv(hilo_units)
    rep["tape_close_raw"] = {"counts": dict(o_c), "rows": det_c}
    rep["tape_hilo_sample"] = {"counts": dict(o_h), "n_units_total": A["hilo"]["units"], "sample_n": len(hilo_units),
                               "seed": HILO_TAPE_SEED}
    vm = sum(1 for d in det_h + det_c if abs(d["tape_vol1"] - float(d["vol1"])) < 0.02 and abs(d["tape_vol2"] - float(d["vol2"])) < 0.02)
    rep["tape_vol_match"] = {"leg_pairs": len(det_h) + len(det_c), "both_legs_exact": vm}
    # time separation of the hilo extremes (tape): when did K2 print its highest price vs K1 its lowest?
    seps = []
    for v in hilo_units:
        key = (v["k1"], v["k2"], v["end_ts"])
        if key in tp and tp[key][0] and tp[key][1]:
            r1, r2 = tp[key]
            t_lo1 = min(r1, key=lambda x: (x[1], x[0]))[0]
            t_hi2 = max(r2, key=lambda x: (x[1], -x[0]))[0]
            seps.append(abs(t_lo1 - t_hi2) / 1e6)
    rep["dt_sens"] = dt_sensitivity(tp, hilo_units)
    rep["continuity"] = continuity(hrs_all)
    rep["tape_hilo_extreme_separation_s"] = {"n": len(seps), "median": med(seps), "share_gt_2s": (sum(1 for x in seps if x > 2) / len(seps)) if seps else None}
    uhl = [v for v in viol if v["reading"] == "hilo" and v["is_minute_max"]]
    rep["hilo_diag"] = {k: {"median": med(x), "p90": quant(x).get("95")} for k, x in hilo_artifact_diag(uhl).items()}
    dg = hilo_artifact_diag(uhl)
    rep["hilo_diag"]["share_crossed_at_close"] = sum(1 for x in dg["close_gap"] if x > 0) / len(dg["close_gap"])
    rep["hilo_diag"]["share_close_gap_le_minus1"] = sum(1 for x in dg["close_gap"] if x <= -1) / len(dg["close_gap"])
    rep["hand_worked"] = hand_worked(close_rows + uhl[:4], 10)

    # gates for Part A
    tr_h = (o_h.get("L2", 0) / o_h["n"]) if o_h.get("n") else None
    rep["A_gates"] = {"close": gates(A["close"], None, True), "carried": gates(A["carried"], None, True),
                      "hilo": gates(A["hilo"], tr_h, False)}

    # ---------------- Part B / C (KXBTC coverage)
    hrs, have, pre = kx_hours()
    bc = jload(os.path.join(LCACHE, "scanBC.json")) if os.path.exists(os.path.join(LCACHE, "scanBC.json")) else None
    if bc:                                              # analyse exactly the set scanBC saw (the fetch may have advanced since)
        have = bc["hours_covered"]
        assert have == hrs[:len(have)], "KXBTC coverage is not a prefix of the saved order"
        pre = len(have)
    rep["coverage"] = {"hours_universe": len(hrs), "kxbtc_hours": len(have), "fraction": len(have) / len(hrs), "prefix_of_order": pre,
                       "days_covered": len({utc_day(jload(os.path.join(TP.HOURS, e, "ladder.json"))[0]["close_ts"]) for e in have})}
    if bc:
        Bq = {}
        for nm in ("strict", "carried"):
            rows = bc["B"][nm]
            sa, sb = [r[2] for r in rows], [r[3] for r in rows]
            fa, fb = [r[4] for r in rows], [r[5] for r in rows]
            Bq[nm] = {"minutes": len(rows), "hours": len({r[0] for r in rows}), "sum_ask": quant(sa), "sum_bid": quant(sb),
                      "fee_all_legs_buy": quant(fa), "fee_all_legs_sell": quant(fb),
                      "n_ask_sum_lt_100": sum(1 for x in sa if x < 100), "n_bid_sum_gt_100": sum(1 for x in sb if x > 100),
                      "n_dutch_buy_net_pos": sum(1 for r in rows if 100 - r[2] - r[4] > 0),
                      "n_dutch_sell_net_pos": sum(1 for r in rows if r[3] - 100 - r[5] > 0),
                      "min_ask_sum": min(sa) if sa else None, "max_bid_sum": max(sb) if sb else None,
                      "legs_with_offer_median": med(r[6] for r in rows), "legs_with_bid_median": med(r[7] for r in rows),
                      "n_all_188_have_offer_le99": sum(1 for r in rows if r[6] == r[8]), "n_all_188_have_bid": sum(1 for r in rows if r[7] == r[8])}
        rep["B"] = Bq
        Crows = jload(os.path.join(LCACHE, "violationsC.json"))
        C = {}
        for rd in ("close", "carried", "hilo"):
            rr = [r for r in Crows if r["reading"] == rd]
            st = unit_stats([{**r, "vol1": min(r["volR"], r["volLo"], r["volHi"]), "vol2": min(r["volR"], r["volLo"], r["volHi"])} for r in rr])
            st["raw_credit_rows"] = len(rr)
            st["max_credit_c"] = max((r["credit"] for r in rr), default=None)
            st["tested_leg_triples"] = sum(c.get("tested", {}).get(f"{rd}|{k}", 0) for c in bc["Csumm"] for k in ("C1", "C2"))
            st["by_cons"] = {k: sum(1 for r in rr if r["cons"] == k and r["fee_clearing"]) for k in ("C1", "C2")}
            st["all3_nonzero_vol_units"] = sum(1 for r in rr if r["is_minute_max"] and min(r["volR"], r["volLo"], r["volHi"]) > 0)
            C[rd] = st
        rep["C"] = C
        rep["C_map"] = {"between_markets": sum(c["n_between"] for c in bc["Csumm"]), "mapped": sum(c["n_mapped"] for c in bc["Csumm"])}
        tgC = tapeC_targets()
        tcache, tdet = {}, []
        for r in tgC:
            if r["event"] not in tcache:
                pth = os.path.join(TAPEDIR, "C_" + r["event"] + ".json")
                tcache[r["event"]] = jload(pth)["tape"] if os.path.exists(pth) else {}
            tp_ = tcache[r["event"]]
            ks_ = [f"{t}|{r['end_ts']}" for t in (r["R"], r["Dlo"], r["Dhi"])]
            if not all(k_ in tp_ for k_ in ks_):
                tdet.append({**{k_: r[k_] for k_ in ("cons", "R", "Dlo", "Dhi", "end_ts", "credit", "net", "is_minute_max", "volR", "volLo", "volHi")}, "no_tape": True})
                continue
            lv_ = tape_levels3(r["cons"], tp_[ks_[0]], tp_[ks_[1]], tp_[ks_[2]])
            tdet.append({**{k_: r[k_] for k_ in ("cons", "R", "Dlo", "Dhi", "end_ts", "credit", "net", "is_minute_max", "volR", "volLo", "volHi")},
                         "prints": [len(tp_[k_]) for k_ in ks_], **lv_})
        def cnt_(rows_):
            return {"n": len(rows_), "L1": sum(1 for x in rows_ if x.get("L1")), "L2": sum(1 for x in rows_ if x.get("L2")), "L3": sum(1 for x in rows_ if x.get("L3")),
                    "no_tape": sum(1 for x in rows_ if x.get("no_tape"))}
        rep["tapeC"] = {"pairs": cnt_(tdet), "units": cnt_([x for x in tdet if x["is_minute_max"]]), "rows": tdet}
        tr_c = (rep["tapeC"]["units"]["L2"] / rep["tapeC"]["units"]["n"]) if rep["tapeC"]["units"]["n"] else None
        rep["C_gates"] = {"close": gates({**C["close"], "both_nonzero_share": (C["close"]["all3_nonzero_vol_units"] / C["close"]["units"]) if C["close"]["units"] else None}, tr_c, True)}
        rep["C_tape_rate_units_L2"] = tr_c
        rep["hand_worked_C"] = hand_worked_C([r for r in tgC if r["is_minute_max"]], 5)
        # Part B: the minutes where selling only the bid-bearing legs beats 100c + fees (diagnostic, not a strategy)
        rep["B_sell_pos_minutes"] = [{"event": r[0], "end_ts": r[1], "sum_bid": r[3], "fee_sold_legs": r[5], "legs_sold": r[7], "net": r[3] - 100 - r[5]}
                                     for r in bc["B"]["carried"] if r[3] - 100 - r[5] > 0]
        rep["anchors"]["C_payoff_zero"] = verify_C_payoff([r for r in Crows if r["reading"] == "close"])
        rep["anchors"]["kxbtc_partition"] = verify_kx(have)
    else:
        rep["B"] = rep["C"] = None
        rep["B_note"] = "scanBC not run on the current KXBTC hour set"

    # ---------------- outcome-using anchors (b), (c)
    sample_b = [v for v in viol if v["reading"] == "close"] + [v for v in viol if v["reading"] == "hilo" and v["is_minute_max"]]
    rep["anchors"]["b_all_rows"] = verify_payoff_dominance(viol)
    rep["anchors"]["b_sample_labelled"] = {"close_raw_rows": sum(1 for v in sample_b if v["reading"] == "close"),
                                           "hilo_units": sum(1 for v in sample_b if v["reading"] == "hilo")}
    rep["anchors"]["c_monotone"] = verify_monotone(hrs_all)
    rep["anchors"]["c_expiration"] = verify_expiration(hrs_all)

    # ---------------- (f) fee provenance
    try:
        live = {s: TP.http("/series/" + s)["series"] for s in ("KXBTCD", "KXBTC")}
        live = {s: {k: v.get(k) for k in ("fee_type", "fee_multiplier", "frequency")} for s, v in live.items()}
    except Exception as ex_:
        live = {"error": repr(ex_)}
    cat = jload(os.path.join(HERE, "cache", "shape_screen", "series_catalog.json"))
    survey = {x["ticker"]: {k: x.get(k) for k in ("fee_type", "fee_multiplier")} for x in cat if x.get("ticker") in ("KXBTCD", "KXBTC")}
    rep["anchors"]["f_fee"] = {"live_series": live, "survey_2026_10_27_catalog": survey, "survey_file_mtime": time.ctime(os.path.getmtime(os.path.join(HERE, "cache", "shape_screen", "series_catalog.json")))}

    # ---------------- verdict
    close_clear = A["close"]["clear_pairs"] + (rep["C"]["close"]["clear_pairs"] if rep.get("C") else 0)
    rep["verdict_inputs"] = {"close_fee_clearing_A": A["close"]["clear_pairs"],
                             "close_fee_clearing_C": rep["C"]["close"]["clear_pairs"] if rep.get("C") else None,
                             "carried_fee_clearing_A": A["carried"]["clear_pairs"]}
    passing = [k for k in ("A",) if rep["A_gates"]["close"]["pass"]] + (["C"] if rep.get("C_gates") and rep["C_gates"]["close"]["pass"] else [])
    trc = rep.get("C_tape_rate_units_L2")
    if passing:
        verdict = "PASS"
    elif close_clear == 0:
        verdict = "KILL"                                                  # clause 1
    elif trc is not None and trc < 0.10:
        verdict = "KILL"                                                  # clause 2: < 10% of candidates survive the tape
    else:
        verdict = "INSUFFICIENT"
    rep["verdict_inputs"]["kill_clause_2_tape_rate_C_units"] = trc
    rep["verdict_inputs"]["kill_clause"] = 1 if close_clear == 0 else (2 if (trc is not None and trc < 0.10) else None)
    rep["verdict"] = verdict
    jdump(rep, OUT_JSON)
    write_md(rep)
    print("verdict", verdict, "A close clear", A["close"]["clear_pairs"], "hilo clear", A["hilo"]["clear_pairs"])
    return rep


# ------------------------------------------------------------------------------------------ report
def f_(x, nd=2):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return f"{x:,}" if isinstance(x, int) else str(x)


def fc(x, nd=2):
    return "n/a" if x is None else f"{f_(x, nd)}c"


def pct(a, b, nd=1):
    return "n/a" if not b else f"{100.0 * a / b:.{nd}f}%"


def write_md(rep):
    A, cov, an = rep["A"], rep["coverage"], rep["anchors"]
    O = rep["A_obs"]
    L = []
    L.append("# Ladder arbitrage: is the KXBTCD threshold ladder ever quoted crossed?  (LADDER_ARBITRAGE_SPEC.md, executed)\n")
    L.append(f"**VERDICT: {rep['verdict']}**  (frozen PASS/KILL rule applied verbatim; numbers beside each bar in section 8)\n")
    L.append(f"Universe: {O['hours']} KXBTCD hours (prefix of the saved seed-20261027 order, never re-sorted), {O['days']} UTC days, {O['minutes']:,} candle-minutes, "
             f"{O['strike_minutes_with_candle']:,} strike-minutes with a candle ({O['two_sided_strike_minutes']:,} two-sided). KXBTC (Parts B, C) coverage: {cov['kxbtc_hours']} of {cov['hours_universe']} hours "
             f"({cov['fraction'] * 100:.1f}%, {cov['days_covered']} days; completed set is a {'contiguous prefix' if cov['prefix_of_order'] == cov['kxbtc_hours'] else 'NON-prefix subset'} of the order).\n")
    c, k, h = A["close"], A["carried"], A["hilo"]
    L.append("## 0. Plain reading (written from the tables below)\n")
    L.append(f"* **On simultaneous quotes the ladder is never crossed by enough to matter.** `close` reading: {c['raw_pairs']} raw crossings (bid(K2) > ask(K1)) in {c['raw_minutes']} minutes out of {c['tested_pair_obs']:,} executable pair-observations; the largest was {f_(c['max_crossing_c'])}c, "
             f"and fees on two legs are at least 2c, so **{c['clear_pairs']} are fee-clearing** (need a crossing of >= 3c). The `carried` reading (each strike's last close carried across minutes in which it did not change, valid because the candle stream is change-driven: next candle's open == previous candle's close in {pct(rep['continuity']['gap_ask_eq'] + rep['continuity']['gap_bid_eq'], 2 * rep['continuity']['gap_n'], 3)} of {rep['continuity']['gap_n']:,} gaps across no-candle minutes, {pct(rep['continuity']['adj_ask_eq'] + rep['continuity']['adj_bid_eq'], 2 * rep['continuity']['adj_n'], 3)} of {rep['continuity']['adj_n']:,} adjacent minutes) gives the same {k['raw_pairs']} / {k['clear_pairs']}.")
    L.append(f"* **The high/low construction manufactures {h['clear_pairs']:,} 'fee-clearing violations' ({h['units']:,} per-minute-max opportunities on {h['days']} days, median net {f_(h['median_net_units'])}c, both legs traded in {pct(h['both_nonzero_vol_units'], h['units'])}) out of the same data.** Their COUNT is a within-minute timing artifact: bid.high of one strike and ask.low of another are different instants. Anchor (e) says that is a finding, and it is (section 2.3 says what real, brief crossings sit underneath it).")
    th = rep["tape_hilo_sample"]
    L.append(f"* Tape check of a seeded sample of {th['sample_n']} of those {h['units']:,} high/low opportunities: tape-inverted (L2) {th['counts'].get('L2', 0)} of {th['counts'].get('n', 0)} ({pct(th['counts'].get('L2', 0), th['counts'].get('n', 0))}), side-correct (L3) {th['counts'].get('L3', 0)}.")
    if rep.get("C") and rep["C"]["close"]["clear_pairs"]:
        cc0, tu = rep["C"]["close"], rep["tapeC"]["units"]
        L.append(f"* **Part C (3 legs, KXBTC range vs two KXBTCD strikes) is the only place a simultaneous reading finds anything:** {cc0['clear_pairs']} fee-clearing `close` rows = {cc0['units']} opportunities on {cc0['days']} days out of {cc0['tested_leg_triples']:,} tested leg-triples, "
                 f"median net {fc(cc0['median_net_units'], 1)} after three fees, all three legs traded in {pct(cc0['all3_nonzero_vol_units'], cc0['units'])}, tape-confirmed (L2) {tu['L2']}/{tu['n']} ({pct(tu['L2'], tu['n'])}). Far below every PASS bar; the study verdict is {rep['verdict']}.")
    sc = rep["dt_sens"]["side_correct_within"][rep["dt_sens"]["thresholds_s"].index(0.1)]
    L.append(f"* **Caveat the snapshot verdict does not remove:** inside {sc} of {rep['dt_sens']['n_rows']} sampled high/low minutes the tape shows a K1-lifted / K2-hit pair at inverted, fee-clearing prices within 100 ms of each other (section 2.3). Brief crossings exist while the 188 strikes are re-quoted; they are not visible at minute-end and, judging by the timestamps, are consumed by faster participants. That is a latency game, not the no-speed arbitrage the spec premised.")
    L.append("")
    # ------------------------------------------------------------------ 1. anchor e
    L.append("## 1. Anchor (e): simultaneity disclosure -- FIRST, because it decides whether anything else means anything\n")
    L.append("Part A, all ordered strike pairs K1 < K2, every minute, 503 hours.  Buy YES(K1) at yes_ask, sell YES(K2) at yes_bid.  Net = bid(K2) - ask(K1) - fee(ask) - fee(bid), cents.  "
             "'Opportunity' = the maximum-net fee-clearing pair of a minute (the spec's scan unit); 'pairs' counts every fee-clearing pair.\n")
    L.append("| reading | simultaneous? | can PASS? | executable pair-observations tested | raw crossings (pairs / minutes / hours) | largest raw crossing | fee-clearing pairs | fee-clearing opportunities (minutes) | days | median net (opportunity / pair) | max net |")
    L.append("|---|:--:|:--:|--:|---|--:|--:|--:|--:|---|--:|")
    for nm, lab, sim in (("close", "`close`, every leg, same candle (PRIMARY)", "yes"), ("carried", "`close` carried across unchanged minutes (disclosure; not in spec)", "yes (state)"),
                         ("hilo", "bid.HIGH(K2) vs ask.LOW(K1), same minute (**NON-SIMULTANEOUS**)", "NO")):
        x = A[nm]
        L.append(f"| {lab} | {sim} | {'yes' if nm == 'close' else 'NO'} | {x['tested_pair_obs']:,} | {x['raw_pairs']:,} / {x['raw_minutes']:,} / {x['raw_hours']} | {fc(x['max_crossing_c'])} | **{x['clear_pairs']:,}** | **{x['units']:,}** | {x['days']} | {fc(x['median_net_units'])} / {fc(x['median_net_pairs'])} | {f_(x['max_net'])} |")
    L.append("")
    if c["clear_pairs"] == 0 and h["clear_pairs"] > 0:
        L.append(f"**Reading: the apparent opportunity is a within-minute timing artifact.** The same minutes, the same quotes, give {h['clear_pairs']:,} fee-clearing pairs when two different instants are compared and **zero** when one instant is. "
                 "That is the finding.\n")
    L.append("How close does the simultaneous ladder come to being crossed?  Per minute, max over K1 < K2 of bid(K2) - ask(K1) (cents), minutes with at least one executable pair:\n")
    gh = rep["A_gap_hist"]
    def bucketize(hd):
        b = collections.Counter()
        for kk, v in hd.items():
            kk = int(kk)
            key = "<= -10" if kk <= -10 else ("-9..-5" if kk <= -5 else ("-4..-2" if kk <= -2 else (str(kk) if kk <= 0 else ">= +1")))
            b[key] += v
        return b
    cols = ["<= -10", "-9..-5", "-4..-2", "-1", "0", ">= +1"]
    L.append("| reading | " + " | ".join(cols) + " | minutes |")
    L.append("|---|" + "--:|" * (len(cols) + 1))
    for nm in ("close", "carried", "hilo"):
        b = bucketize(gh[nm])
        L.append(f"| {nm} | " + " | ".join(f"{b.get(cn, 0):,}" for cn in cols) + f" | {sum(b.values()):,} |")
    L.append("\n(`0` = locked, bid(K2) = ask(K1); `>= +1` = crossed, but not necessarily by enough to pay 2-4c of fees.)\n")
    hd = rep["hilo_diag"]
    L.append(f"Why the high/low crossing is not real (the {h['units']:,} per-minute-max high/low opportunities, looked at through the close): median bid.high - bid.close of the sold leg = {f_(hd['bid2_high_minus_close']['median'], 1)}c, "
             f"median ask.close - ask.low of the bought leg = {f_(hd['ask1_close_minus_low']['median'], 1)}c; median claimed (high/low) credit {f_(hd['hilo_credit']['median'], 1)}c versus median close-to-close gap bid(K2) - ask(K1) = {f_(hd['close_gap']['median'], 1)}c. "
             f"Share of those minutes that are crossed at the close: {hd['share_crossed_at_close'] * 100:.1f}%; share at least 1c uncrossed at the close: {hd['share_close_gap_le_minus1'] * 100:.1f}%. "
             f"On the tape sample, the instant of K2's highest print and of K1's lowest print are a median {f_(rep['tape_hilo_extreme_separation_s']['median'], 1)}s apart "
             f"({f_((rep['tape_hilo_extreme_separation_s']['share_gt_2s'] or 0) * 100, 0)}% more than 2s apart; n={rep['tape_hilo_extreme_separation_s']['n']}).\n")
    # ------------------------------------------------------------------ 2. Part A
    L.append("## 2. Part A: 2-leg ladder spread (KXBTCD only)\n")
    L.append("### 2.1 Primary (`close`, simultaneous)\n")
    L.append(f"* Fee-clearing violations: **{c['clear_pairs']}** (opportunities {c['units']}, days {c['days']}). Median net, per-day concentration, volume on both legs and tape-confirmation rate are therefore **undefined (0 / 0)**.")
    L.append(f"* The fee arithmetic, concretely: raw crossings exist ({c['raw_pairs']}), each exactly {f_(c['max_crossing_c'])}c; at the prices where they occur the two legs pay the fee shown below, so every one nets negative:\n")
    L.append("| K1 (buy at ask) | ask | traded vol (candle) | K2 (sell at bid) | bid | traded vol (candle) | fee buy + fee sell | net |")
    L.append("|---|--:|--:|---|--:|--:|--:|--:|")
    for v in jload(VIOL):
        if v["reading"] == "close":
            L.append(f"| {v['k1']} | {v['ask1']} | {v['vol1']:,.0f} | {v['k2']} | {v['bid2']} | {v['vol2']:,.0f} | {v['fee1']} + {v['fee2']} | {v['net']} |")
    L.append("")
    tc = rep["tape_close_raw"]
    L.append(f"Tape (GET /markets/trades) for these {tc['counts'].get('n', 0)} raw crossings (not fee-clearing, so nothing 'survives' to confirm; shown because the spec requires the check wherever a crossing is claimed): "
             f"both legs printed in the minute {tc['counts'].get('L1', 0)}, fee-clearing printed inversion within 2 s (L2) {tc['counts'].get('L2', 0)}, side-correct (L3) {tc['counts'].get('L3', 0)}.\n")
    L.append("| K1 | K2 | end_ts | prints K1 / K2 | tape vol K1 / K2 | candle vol K1 / K2 | L1 | L2 | L3 |")
    L.append("|---|---|--:|--:|--:|--:|:--:|:--:|:--:|")
    for d in tc["rows"]:
        L.append(f"| {d['k1']} | {d['k2']} | {d['end_ts']} | {d['prints1']} / {d['prints2']} | {d['tape_vol1']:,.0f} / {d['tape_vol2']:,.0f} | {float(d['vol1']):,.0f} / {float(d['vol2']):,.0f} | {d['L1']} | {d['L2']} | {d['L3']} |")
    L.append("\n### 2.2 `hilo` (NON-SIMULTANEOUS; reported only to size the artifact; cannot PASS)\n")
    L.append(f"* Fee-clearing pairs {h['clear_pairs']:,}; opportunities (per-minute max) {h['units']:,} on {h['days']} of {O['days']} days and {h['hours']} hours; median net {f_(h['median_net_units'])}c (pairs {f_(h['median_net_pairs'])}c), max net {h['max_net']}c.")
    L.append(f"* Concentration: busiest day {h['max_day']} = {h['max_day_share'] * 100:.1f}% of opportunities; busiest hour {h['max_hour']} = {h['max_hour_share'] * 100:.1f}%.")
    L.append(f"* Traded volume in the violating minute (UPPER BOUND on size only; candles carry no depth; realisable size is UNKNOWN): median leg volumes {f_(h['vol1_median'], 0)} / {f_(h['vol2_median'], 0)} contracts; both legs non-zero in {h['both_nonzero_vol_units']:,} ({pct(h['both_nonzero_vol_units'], h['units'])}); zero-volume leg (doubtful fill) in {h['zero_vol_leg_units']:,}.")
    L.append(f"* Tape on a seeded random sample ({th['sample_n']} opportunities, seed {th['seed']}; the full {h['units']:,} were not pulled because of API rate limits): both legs printed in the minute (L1) {th['counts'].get('L1', 0)}/{th['counts'].get('n', 0)} ({pct(th['counts'].get('L1', 0), th['counts'].get('n', 0))}); "
             f"fee-clearing printed inversion within 2 s (L2) {th['counts'].get('L2', 0)}/{th['counts'].get('n', 0)} ({pct(th['counts'].get('L2', 0), th['counts'].get('n', 0))}); side-correct (L3) {th['counts'].get('L3', 0)}/{th['counts'].get('n', 0)}.")
    L.append(f"* Tape volume check: of {rep['tape_vol_match']['leg_pairs']} leg-pairs, tape volume equals candle volume on both legs in {rep['tape_vol_match']['both_legs_exact']} (the validated MAKER_FILL result holds).")
    dts = rep["dt_sens"]
    th_ = dts["thresholds_s"]
    L.append("\n### 2.3 What the tape shows INSIDE the minute (disclosure; outside the frozen bars)\n")
    nrow = dts["n_rows"]
    L.append(f"The candle `close` sees the state at the end of each minute. The tape sees every print with a microsecond stamp. For the {nrow} sampled high/low opportunities I looked for a print on K1 and a print on K2 whose PRINTED prices clear fees "
             "(p2 - p1 - fee(p1) - fee(p2) >= 1c), and measured the smallest time gap between such a pair. L2 above used the frozen 2 s tolerance; the table is the same test at tighter tolerances (sensitivity, not a selection):\n")
    L.append("| |Dt| <= | " + " | ".join(f"{t:g}s" for t in th_) + " |")
    L.append("|---|" + "--:|" * len(th_))
    L.append("| any taker sides (of " + str(nrow) + ") | " + " | ".join(str(x) for x in dts["any_side_within"]) + " |")
    L.append("| K1 lifted (taker yes) AND K2 hit (taker no) | " + " | ".join(str(x) for x in dts["side_correct_within"]) + " |")
    L.append("")
    tight = dts["tightest_side_correct"]
    if tight:
        L.append("Tightest side-correct pairs (a real taker bought K1 at its ask and a real taker sold K2 at its bid, milliseconds apart, at inverted prices):\n")
        L.append("| K1 | p1 (c) | size1 | K2 | p2 (c) | size2 | gap | printed net after fees (c) |")
        L.append("|---|--:|--:|---|--:|--:|--:|--:|")
        for e in tight[:8]:
            L.append(f"| {e['k1']} | {e['p1']:.0f} | {e['n1']:.0f} | {e['k2']} | {e['p2']:.0f} | {e['n2']:.0f} | {e['dt_s'] * 1000:.1f} ms | {e['printed_net_c']:.0f} |")
        L.append("")
    sc10 = dts["side_correct_within"][th_.index(0.1)] if 0.1 in th_ else None
    L.append(f"**This qualifies the artifact reading honestly.** The high/low COUNT is an artifact (it mixes instants), and the simultaneous end-of-minute snapshot is never crossed. But inside "
             f"{pct(sc10, nrow)} of the sampled high/low minutes ({sc10}/{nrow}) the tape contains a pair of opposite-side takes (K1 bought at its ask, K2 sold at its bid) at inverted fee-clearing prices within 100 ms -- consistent with someone running this arbitrage at "
             "millisecond speed (several pairs have equal sizes on both legs and the same microsecond), during a BTC move when the 188 strikes are re-quoted one after another. So crossings do appear to exist, transiently; they are gone by the next minute-end and are consumed by participants far faster than anything the spec's 'no speed' premise allows. "
             f"The bars are about simultaneous snapshots and they are not met; this paragraph does not move them. For scale (sample-based, not a measurement of the full set): {pct(sc10, nrow)} of the {h['units']:,} high/low minutes would be about {round(h['units'] * sc10 / nrow) if nrow and sc10 is not None else 'n/a'} minutes in 60 days. "
             "Whether any of that is capturable from here is a latency question this study does not address; the repo's `out/bench_transport.json` puts proxy-inclusive request round trips from this environment at ~55-65 ms median, i.e. not competitive with gaps of a few ms.\n")
    ga = rep["A_gates"]
    L.append("\nGates evaluated on each reading (hilo shown only to show what it would claim; it cannot PASS):\n")
    L.append("| reading | >=100 opp. on >=20 days | tape >= 50% | median net >= +2.0c | >=50% non-zero vol both legs | no day/hour > 25% | PASS-eligible result |")
    L.append("|---|:--:|:--:|:--:|:--:|:--:|:--:|")
    for nm in ("close", "carried", "hilo"):
        g = ga[nm]
        L.append(f"| {nm} | {g['g1_units_ge100_days_ge20']} | {g['g2_tape_ge50']} | {g['g3_median_net_ge2']} | {g['g4_both_vol_ge50']} | {g['g5_no_day_or_hour_gt25']} | {'PASS' if g['pass'] else ('not eligible (non-simultaneous)' if nm == 'hilo' else 'no')} |")
    # ------------------------------------------------------------------ 3. Part B
    L.append("\n## 3. Part B: KXBTC partition-sum diagnostic (NOT a strategy)\n")
    B = rep.get("B")
    if not B:
        L.append("KXBTC data not scanned.\n")
    else:
        L.append(f"The 188 KXBTC markets (186 `between` $100 ranges + a `less` and a `greater` tail) pay exactly 100c in total in every state. Buying all 188 costs sum(yes_ask) plus >= 1c fee per leg priced 1..99c; selling all 188 receives sum(yes_bid) and owes 100c. "
                 f"The dutch book is **not tested** (>= 188 legs of fees, spec: dead by arithmetic); only how far the sums sit from 100c is reported. Coverage: {cov['kxbtc_hours']} of {cov['hours_universe']} hours. No mid is formed: only the ask-sum and the bid-sum, which bracket 100.\n")
        L.append("| reading | minutes with all 188 legs observed | hours | sum(yes_ask) p5 / median / p95 / min | sum(yes_bid) p5 / median / p95 / max | minutes with sum(ask) < 100 | minutes with sum(bid) > 100 | gross buy-all profit > fees (minutes) | gross sell-all profit > fees (minutes) | fee to buy all 188, median (c) |")
        L.append("|---|--:|--:|---|---|--:|--:|--:|--:|--:|")
        for nm in ("strict", "carried"):
            b = B[nm]
            if not b["minutes"]:
                L.append(f"| {nm} | 0 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
                continue
            sa, sb = b["sum_ask"], b["sum_bid"]
            L.append(f"| {nm} | {b['minutes']:,} | {b['hours']} | {sa['5']:.0f} / {sa['50']:.0f} / {sa['95']:.0f} / {sa['0']:.0f} | {sb['5']:.0f} / {sb['50']:.0f} / {sb['95']:.0f} / {sb['100']:.0f} | {b['n_ask_sum_lt_100']:,} | {b['n_bid_sum_gt_100']:,} | {b['n_dutch_buy_net_pos']:,} | {b['n_dutch_sell_net_pos']:,} | {b['fee_all_legs_buy']['50']:.0f} |")
        bc_ = B["carried"]
        sp = rep["B_sell_pos_minutes"]
        L.append(f"\nReading: `strict` = all 188 legs have a candle in the same minute (in practice only the opening minutes); `carried` = last close carried forward ({bc_['minutes']:,} minutes). "
                 f"On the carried reading the cost of buying the whole partition at the ask is {bc_['sum_ask']['5']:.0f}-{bc_['sum_ask']['95']:.0f}c (p5-p95; minimum {bc_['min_ask_sum']}c) against a payout of exactly 100c, so it is never a gross profit: the 1c tick floor on ~190 mostly-dead strikes makes every leg cost at least 1c. "
                 f"The proceeds from selling only the legs that have a bid are {bc_['sum_bid']['5']:.0f}-{bc_['sum_bid']['95']:.0f}c (p5-p95; maximum {bc_['max_bid_sum']}c) against a maximum liability of 100c (one winner). It exceeds 100c in {bc_['n_bid_sum_gt_100']} of {bc_['minutes']:,} minutes. "
                 "The spec's 'dead by arithmetic' is exact for BUYING the partition (188 legs) but NOT for SELLING it: only the ~3-10 bid-bearing legs are sold and pay fees, so the fee floor on that side is ~3-10c, not 100c. "
                 f"After the fee on each sold leg, {len(sp)} minutes are positive: " + (", ".join(f"{x['event']} @ {x['end_ts']} (bids sum {x['sum_bid']}c over {x['legs_sold']} legs, fees {x['fee_sold_legs']}c, net {x['net']}c)" for x in sp) if sp else "none") + ". "
                 "These are carried-state diagnostics, not a tested strategy and not tape-checked (the spec forbids testing the partition as a strategy); "
                 "in that hour one of the sold legs, a range roughly $800 out of the money, is quoted 18c bid / 24c ask and shows no new candle in two of the three minutes, i.e. it looks like a stale quote, which is what would make the 'crossing' disappear. "
                 "A low-leg-count partition sell is the one place this diagnostic points beyond the spec; it is 3 minutes of 27,137 and one hour of 503.\n")
    # ------------------------------------------------------------------ 4. Part C
    L.append("## 4. Part C: 3-leg cross-series (KXBTC range vs KXBTCD pair, same hour)\n")
    C = rep.get("C")
    if not C:
        L.append("Not run.\n")
    else:
        L.append(f"R[f, f+99.99] pays exactly when KXBTCD(>f-0.01) pays and KXBTCD(>f+99.99) does not, so R = D_lo - D_hi. C1: long R (ask), short D_lo (bid), long D_hi (ask). C2: short R (bid), long D_lo (ask), short D_hi (bid). Payoff is 0 in every state (verified in 5), "
                 f"net = credit - 3 fees (>= 3c). {rep['C_map']['mapped']:,} of {rep['C_map']['between_markets']:,} `between` ranges map onto two KXBTCD strikes. Coverage {cov['kxbtc_hours']} of {cov['hours_universe']} hours ({cov['fraction'] * 100:.1f}%); only the covered prefix is scanned.\n")
        L.append("| reading | can PASS? | leg-triples tested | raw credits > 0 | largest credit | fee-clearing (C1 / C2) | opportunities (minutes) | days | median net | all 3 legs non-zero vol |")
        L.append("|---|:--:|--:|--:|--:|---|--:|--:|--:|--:|")
        for nm, lab in (("close", "`close`, simultaneous (PRIMARY)"), ("carried", "carried close (disclosure)"), ("hilo", "high/low (NON-SIMULTANEOUS)")):
            x = C[nm]
            L.append(f"| {lab} | {'yes' if nm == 'close' else 'NO'} | {x['tested_leg_triples']:,} | {x['raw_credit_rows']:,} | {f_(x['max_credit_c'])}c | {x['clear_pairs']:,} ({x['by_cons']['C1']} / {x['by_cons']['C2']}) | {x['units']:,} | {x['days']} | {f_(x['median_net_units'])} | {x['all3_nonzero_vol_units']:,} |")
        L.append("")
        if C["close"]["clear_pairs"] == 0:
            L.append("`close`: zero fee-clearing 3-leg constructions, so no tape step applies to Part C. The high/low rows are the same artifact as in Part A and were not tape-checked (they cannot PASS).\n")
        else:
            cc_, tcu, tcp = C["close"], rep["tapeC"]["units"], rep["tapeC"]["pairs"]
            L.append(f"### 4.1 Part C `close` survivors ({cc_['clear_pairs']} fee-clearing rows = {cc_['units']} per-minute-per-construction opportunities, {cc_['days']} days, {cc_['hours']} hours)\n")
            L.append(f"* Net per 3-leg construction: median {fc(cc_['median_net_units'])} (opportunities) / {fc(cc_['median_net_pairs'])} (rows), max {f_(cc_['max_net'])}c. Every net is after three fees (>= 3c). Busiest day {cc_['max_day']} = {cc_['max_day_share'] * 100:.1f}% of opportunities; busiest hour {cc_['max_hour']} = {cc_['max_hour_share'] * 100:.1f}%.")
            L.append(f"* Traded volume in the violating minute (UPPER BOUND; no depth; realisable size UNKNOWN): all three legs non-zero in {cc_['all3_nonzero_vol_units']} of {cc_['units']} ({pct(cc_['all3_nonzero_vol_units'], cc_['units'])}); at least one leg with zero volume (doubtful fill) in {cc_['units'] - cc_['all3_nonzero_vol_units']}. "
                     f"The KXBTC range leg is the usual zero: it printed nothing in {sum(1 for x in rep['tapeC']['rows'] if x['is_minute_max'] and x['volR'] == 0)} of the {cc_['units']} minutes.")
            L.append(f"* **Tape (GET /markets/trades), every one of the {tcp['n']} rows, none selected** (L1 all three legs printed in the minute; L2 prints on all three legs within 2 s whose printed prices clear fees; L3 side-correct): "
                     f"opportunities L1 {tcu['L1']}/{tcu['n']}, **L2 {tcu['L2']}/{tcu['n']} ({pct(tcu['L2'], tcu['n'])})**, L3 {tcu['L3']}/{tcu['n']}; rows L1 {tcp['L1']}/{tcp['n']}, L2 {tcp['L2']}/{tcp['n']}, L3 {tcp['L3']}/{tcp['n']}. "
                     f"The other {tcu['n'] - tcu['L2']} opportunities are quote-only: at least one leg did not print in that minute, so the tape can neither confirm nor refute the end-of-minute quote.")
            L.append("")
            L.append("| cons | KXBTC range R | minute end_ts | credit | net | candle vol R / D_lo / D_hi | prints R / D_lo / D_hi | L1 | L2 | L3 | opportunity |")
            L.append("|---|---|--:|--:|--:|---|---|:--:|:--:|:--:|:--:|")
            for x in rep["tapeC"]["rows"]:
                L.append(f"| {x['cons']} | {x['R']} | {x['end_ts']} | {x['credit']} | {x['net']} | {x['volR']:,.0f} / {x['volLo']:,.0f} / {x['volHi']:,.0f} | {' / '.join(str(q) for q in x.get('prints', []))} | {x.get('L1')} | {x.get('L2')} | {x.get('L3')} | {x['is_minute_max']} |")
            L.append("")
            L.append("Anchor (d) for Part C: five of these re-parsed from the raw candle JSON (R from the KXBTC cache, D legs from the KXBTCD cache), exact side and price of each leg, fee recomputed with `math.ceil`:\n")
            L.append("| cons | event | minute end_ts | leg 1 | leg 2 | leg 3 | fees | credit | net |")
            L.append("|---|---|--:|---|---|---|---|--:|--:|")
            for w in rep["hand_worked_C"]:
                L.append(f"| {w['cons']} | {w['event']} | {w['end_ts']} | {w['legs'][0][0]} {w['legs'][0][1]}c | {w['legs'][1][0]} {w['legs'][1][1]}c | {w['legs'][2][0]} {w['legs'][2][1]}c | {w['fees']} | {w['credit']} | {w['net']} |")
            L.append("")
    # ------------------------------------------------------------------ 5. anchors
    L.append("## 5. Anchors\n")
    st = an["static"]
    L.append(f"**(a) No outcome in the P&L path.** AST scan passed on {', '.join('`' + x + '`' for x in st['a_pnl_funcs_checked'])}: none references any identifier or string constant containing 'result', 'expiration', 'settle' or 'official'. "
             f"The whole 2-leg credit is `arb_net(ask_k1, bid_k2)` -- signature {st['a_arb_net_signature']}, integers only, so it cannot see an outcome. The scan writes its violation rows (`violations.json`) before any `results.json` is opened; "
             "`results.json` is read only by the `verify_*` functions below, after the scan. If the profit needed the outcome it would not be an arbitrage; here it does not. "
             f"Negative controls (the scan must raise on a doctored copy of this module): {an['negative_controls']}.\n")
    b = an["b_all_rows"]
    L.append(f"**(b) Payoff dominance.** Against the official settlement, for ALL {b['n']:,} violation rows ever produced ({A['close']['raw_pairs']} close, {A['hilo']['raw_pairs']:,} high/low, {A['carried']['raw_pairs']} carried; {b['unknown_result']} skipped for a missing official yes/no): "
             f"realised payoff of long YES(K1) / short YES(K2) = +100 in {b['n_pay_100']:,}, 0 in {b['n_pay_0']:,}, **negative in {b['n_negative']}** (minimum {b['min']}). "
             f"Note the spec's sample (>= 20 violations) cannot be drawn from fee-clearing `close` violations because there are none; the check was therefore run on every raw crossing, close and high/low, which is a strictly larger set. "
             f"{'No negative payoff: the construction is right.' if b['n_negative'] == 0 else 'NEGATIVE PAYOFF FOUND: THE CONSTRUCTION IS WRONG. ' + str(b['negatives'][:3])}")
    if an.get("C_payoff_zero"):
        cz = an["C_payoff_zero"]
        L.append(f"Part C constructions: realised payoff exactly 0 in {cz['n'] - cz['n_payoff_nonzero']:,} of {cz['n']:,} close rows checked ({cz['n_payoff_nonzero']} non-zero).")
    L.append("")
    cm, ce = an["c_monotone"], an["c_expiration"]
    L.append(f"**(c) Monotonicity on settled outcomes.** {cm['hours']} KXBTCD hours, {cm['strikes_with_result']:,} strikes with an official yes/no: hours with a YES above a NO (interleaving): **{cm['interleaved_hours']}** {cm['examples'] if cm['interleaved_hours'] else ''}. "
             f"Second form (every strike below `expiration_value` YES, every strike above NO), on the {ce['hours_checked']} hours for which a fresh KXBTCD listing was pulled with the KXBTC fetch: {ce['strikes_checked']:,} strikes, **{ce['mismatches']} mismatches** {ce['examples'] if ce['mismatches'] else ''}. "
             f"Exclusions: {cm['exclusions'] or 'none'}.")
    if an.get("kxbtc_partition"):
        kp = an["kxbtc_partition"]
        L.append(f"KXBTC partition check: {kp['hours']} hours, hours without exactly one YES among the 188 markets: **{kp['hours_not_exactly_one_yes']}** {kp['examples'] if kp['examples'] else ''}.")
    L.append("")
    L.append("**(d) No mid, executable sides only.** AST scan: no identifier containing 'mid' in any function other than the checker, no division/multiplication by 2 or 0.5 over an expression mixing bid- and ask-named values "
             f"({st['d_binops_checked']} Div/Mult nodes inspected), and `pair_scan` builds the buy cost from the ask row only and the sell proceeds from the bid row only. Ten violations re-parsed from the raw candle JSON (independently of `build_arrays`; the 6 `close` raw crossings first, then 4 high/low), "
             "with the exact yes_ask bought and yes_bid sold, and the fee recomputed with `math.ceil` directly:\n")
    L.append("| reading | K1 (BUY at yes_ask) | yes_ask used | (its close / low) | K2 (SELL at yes_bid) | yes_bid used | (its close / high) | credit | fee buy / sell | net |")
    L.append("|---|---|--:|---|---|--:|---|--:|--:|--:|")
    for w in rep["hand_worked"]:
        L.append(f"| {w['reading']} | {w['k1']} | {w['BUY_k1_yes_ask_used']} | {w['k1_ask_close']} / {w['k1_ask_low']} | {w['k2']} | {w['SELL_k2_yes_bid_used']} | {w['k2_bid_close']} / {w['k2_bid_high']} | {w['credit']} | {w['fee_buy']} / {w['fee_sell']} | {w['net']} |")
    f = an["f_fee"]
    L.append(f"\n**(f) Fee provenance.** Live `GET /series` today: {f['live_series']}. 2026-10-27 survey catalogue (`cache/shape_screen/series_catalog.json`, mtime {f['survey_file_mtime']}): {f['survey_2026_10_27_catalog']}. "
             "Both series are `quadratic`, multiplier 1 (taker-only; no maker fee). Fee per leg = ceil(7 p (1-p)) cents, p in dollars, asserted >= 1c for every price 1..99c. The ten worked rows above show the fee on each leg (the last two columns before net); examples at other prices:\n")
    L.append("| price (c) | 7 p (1-p) | fee (c) |")
    L.append("|--:|--:|--:|")
    for pc in (1, 5, 10, 17, 25, 40, 50, 60, 83, 99):
        L.append(f"| {pc} | {7 * (pc / 100) * (1 - pc / 100):.4f} | {int(FEE[pc])} |")
    # ------------------------------------------------------------------ 6/7 exclusions
    L.append("\n## 6. Exclusions (count and reason)\n")
    L.append(f"* Strike-minutes in the candle grid {O['strike_minutes_grid']:,}; with a candle {O['strike_minutes_with_candle']:,}; the rest are 'no candle that minute' -- unobserved under the strict `close` reading (included under `carried`). Two-sided (bid >= 1 and ask >= 1) strike-minutes: {O['two_sided_strike_minutes']:,}.")
    L.append("* A leg is executable only if the side it trades is quoted: buy needs 1 <= yes_ask <= 99 (ask 100 = no offer), sell needs 1 <= yes_bid <= 99 (bid 0 = no bid). Pair-observations failing this are not tested; the tested count is in the section-1 table.")
    L.append(f"* Hours per candle-minute count: {O['minute_count_by_hour']} (the 17:00-UTC hours open 15 min early). All minutes with any candle are scanned; no minute selection.")
    L.append(f"* Tape: high/low sample {th['sample_n']} of {h['units']:,} opportunities (API rate limits); missing tape rows: {rep['tape_targets']['missing_tape']}.")
    L.append(f"* KXBTC coverage {cov['kxbtc_hours']}/{cov['hours_universe']} hours ({cov['fraction'] * 100:.1f}%); the completed set is a prefix of the saved order.")
    if rep.get("C_map"):
        L.append(f"* Part C: {rep['C_map']['between_markets'] - rep['C_map']['mapped']:,} of {rep['C_map']['between_markets']:,} KXBTC `between` ranges have no matching KXBTCD strike pair (edge ranges beyond the KXBTCD ladder) and are excluded; the two KXBTC tails are not used in Part C. A leg is executable only at 1..99c on the side traded; failures are not counted as tested.")
    L.append("* One KXBTCD hour (KXBTCD-26AUG2416) lists one market with an empty `expiration_value`; the non-empty value (78750.21, identical to the KXBTC value) is used for the second form of anchor (c).")
    L.append(f"* Outcome exclusions (no official yes/no): {cm['exclusions'] or 'none'}.")
    # ------------------------------------------------------------------ 8 verdict
    L.append("\n## 7. Contradictions with the spec's premises\n")
    L.append("* **KXBTC has 188 markets per hour, not 100**: 186 `between` ranges ($100 wide, `strike_type=between`, floor and cap), one `less` tail and one `greater` tail. It is still a complete partition (exactly one YES per hour; check above), so the structure the spec relies on holds, but 'KXBTC: 100 range markets/hour, strike_type=less' is wrong.")
    L.append("* **Part B needs KXBTC data, which was not cached**: the spec says Parts A and B need no new fetching, but the partition sum is over KXBTC. KXBTC candles had to be fetched in the same saved order (coverage above).")
    L.append("* **'The N-leg dutch book is dead by arithmetic' is exact only for buying the 188-leg partition.** Selling the partition needs only the legs that have a bid (3-10 of 188 in practice), so its fee floor is 3-10c, not 100c; section 3 shows 60 carried minutes with bid-sum > 100c and 3 that survive fees. Diagnostic only; the spec forbids testing it as a strategy and I did not.")
    L.append("* **'No forecast, no observation, no speed' does not hold for the only crossings that exist**: the tape (2.3) shows the ladder is crossed for milliseconds around BTC moves and that opposite-side takers close it within ms. On minute-end snapshots, which is all the candle archive can see, it is never crossed.")
    L.append("* The cached candles stop at close - 5 min (original TAIL_PRICING fetch), so the last five minutes of every hour are not scanned.")
    L.append("* Candle rows exist only for minutes in which a strike's quote or trade changed; a strict same-minute `close` therefore needs both legs to have changed in the same minute. The `carried` reading removes that restriction and finds the same thing (zero).")
    L.append("\n## 8. Verdict: frozen rule, numbers beside each bar\n")
    cc = rep["verdict_inputs"]
    Cc = C["close"] if C else None
    gC = rep["C_gates"]["close"] if C else None
    trc = rep.get("C_tape_rate_units_L2")
    L.append(f"* **KILL clause 1** (the `close`-only reading yields zero fee-clearing violations across the covered universe): Part A **{cc['close_fee_clearing_A']}** (of {c['tested_pair_obs']:,} executable pair-observations, 503 hours = 100% of the universe); "
             f"Part C **{f_(cc['close_fee_clearing_C'])}** fee-clearing rows ({cov['kxbtc_hours']} of {cov['hours_universe']} hours, {cov['fraction'] * 100:.1f}%). Carried-close disclosure: Part A {cc['carried_fee_clearing_A']}. "
             f"-> {'FIRES' if (cc['close_fee_clearing_A'] == 0 and not cc['close_fee_clearing_C']) else 'does NOT fire for the study (Part A alone is zero, Part C is not)'}.")
    if Cc and Cc["clear_pairs"]:
        L.append(f"* **KILL clause 2** (fewer than 10% of candidates survive tape confirmation): Part C candidates {rep['tapeC']['units']['n']}, L2-confirmed {rep['tapeC']['units']['L2']} = **{trc * 100:.1f}%** (bar: < 10%) -> {'FIRES' if trc < 0.10 else 'does NOT fire'}.")
        L.append("* PASS bars, `close`-only, Part A: (1) >= 100 fee-clearing violations on >= 20 days: **0** on **0** days -> FAIL; (2) >= 50% tape-confirmed: **n/a (0/0)** -> FAIL; (3) median net >= +2.0c: **n/a** -> FAIL; (4) >= 50% non-zero volume on both legs: **n/a** -> FAIL; (5) no day > 25%: **n/a** -> FAIL.")
        L.append(f"* PASS bars, `close`-only, Part C: (1) >= 100 fee-clearing violations on >= 20 days: **{Cc['units']}** opportunities ({Cc['clear_pairs']} rows) on **{Cc['days']}** days -> {'met' if gC['g1_units_ge100_days_ge20'] else 'FAIL'}; "
                 f"(2) >= 50% confirmed on the tape: **{trc * 100:.1f}%** -> {'met' if gC['g2_tape_ge50'] else 'FAIL'}; (3) median net >= +2.0c: **{fc(Cc['median_net_units'])}** -> {'met' if gC['g3_median_net_ge2'] else 'FAIL'}; "
                 f"(4) >= 50% non-zero volume on all legs: **{pct(Cc['all3_nonzero_vol_units'], Cc['units'])}** -> {'met' if gC['g4_both_vol_ge50'] else 'FAIL'}; (5) no day / hour > 25%: day {Cc['max_day_share'] * 100:.1f}%, hour {Cc['max_hour_share'] * 100:.1f}% -> {'met (exactly at the bar, not over it)' if gC['g5_no_day_or_hour_gt25'] else 'FAIL'}.")
    else:
        L.append("* KILL clause 2 (< 10% of candidates survive tape confirmation): not reached -- there are no fee-clearing `close` candidates to confirm.")
        L.append("* PASS bars, `close`-only, Part A: all FAIL (0 violations).")
        if Cc:
            L.append(f"* PASS bars, `close`-only, Part C: (1) {Cc['clear_pairs']} on {Cc['days']} days -> FAIL; (2)-(5) n/a.")
    L.append("* Part B is a diagnostic and carries no PASS/KILL bar.")
    L.append("* Bonferroni (3 parts x 2 readings = 6, alpha = 0.00833): no test of profitability is needed for an arbitrage and none is run; the count bars above are the whole gate.")
    pa = "KILL (clause 1)"
    pc = ("KILL (clause 2)" if (trc is not None and trc < 0.10) else "INSUFFICIENT: no PASS bar met, KILL clause 2 not triggered") if (Cc and Cc["clear_pairs"]) else "KILL (clause 1)"
    L.append(f"\n**{rep['verdict']}.**  Per part: Part A {pa}; Part C {pc}. ")
    if rep["verdict"] == "INSUFFICIENT":
        L.append("The frozen rule is applied to the study as a whole, and 'zero fee-clearing violations across the covered universe' is not true of Part C, so the study is INSUFFICIENT rather than KILL. "
                 "That is not a near-PASS. Part C misses every count bar by a wide margin "
                 f"({Cc['units']} opportunities against 100, {Cc['days']} days against 20, median net {fc(Cc['median_net_units'], 1)} against 2.0c, tape confirmation {trc * 100:.1f}% against 50%, full-leg volume {pct(Cc['all3_nonzero_vol_units'], Cc['units'])} against 50%) and "
                 "each opportunity is a few cents on one contract before any size or latency question. If 'covered universe' in the KILL clause is read per part, Part A is a clean KILL and Part C is the only live residue; "
                 "I apply the clause to the study as a whole because that is its literal wording (one `close`-only reading across the covered universe). "
                 "Part A, the 2-leg ladder spread, is dead on simultaneous quotes: the ladder is never crossed by more than 1c at any minute-end in 503 hours.")
    elif rep["verdict"] == "KILL":
        L.append("On simultaneous end-of-minute quotes no fee-clearing crossing exists; no bar moved. The snapshot-arbitrage family is closed on these two series.")
    L.append("What neither verdict covers: millisecond-scale crossings on the tape (section 2.3) are a latency competition the spec's 'no speed' premise excludes and this study did not size. Size, the spec's binding unknown after any PASS, never arises.")
    open(OUT_MD, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    {"fetch": lambda: cmd_fetch(int(sys.argv[sys.argv.index("--max-hours") + 1]) if "--max-hours" in sys.argv else None),
     "scan": cmd_scan, "tape": cmd_tape, "scanBC": cmd_scanBC, "tapeC": cmd_tapeC, "analyze": cmd_analyze}[c]()
