#!/usr/bin/env python3
"""
longshot_timing.py
==================
STUDY: is the Polymarket longshot / short-vol SELL premium richer at a different
ENTRY TIME in a market's life?  We already SELL far-OTM longshots (zero-fee) and
currently enter in the FIRST HALF of life.  Question: does entering LATER (closer
to resolution) give a better edge-per-trade and/or a better ANNUALIZED return
(shorter remaining hold = capital freed sooner)?  There should be a sweet spot:
too early = less information; too late = price has mechanically converged toward
the outcome so no premium is left.

Populations (the two CONFIRMED edges):
  CRYPTO : weekly "Will Bitcoin/Ethereum be above $X on <date>?" (~7-day), Gamma
           series 45 (BTC) + 42 (ETH), closed events.
  ECON   : recurring macro-release BUCKET events (CPI/PPI/jobs/GDP/Fed/...), closed
           events with >=4 mutually-exclusive bucket markets.

Method (per market):
  * Pull the FULL hourly YES-mid price path (clob prices-history, fidelity=60).
  * LONGSHOT QUALIFICATION (no peeking): the market's YES mid touches the
    [0.10,0.35] band at SOME tick in the FIRST 40% of life.
  * For each entry fraction f in {0.20,0.35,0.50,0.65,0.80}: the CAUSAL entry price
    is the YES mid at the last tick at/BEFORE f*life.  "still in-band at f" = that
    entry price is itself in [0.10,0.35] (this is the tradeable population at f).
  * Executable SELL price = entry_mid - half_spread (we cannot reconstruct the
    historical best-bid from a mid-only path, so we subtract a conservative fixed
    half-spread estimate per family).  Zero fee.
  * SELL-edge/contract = (entry_mid - half_spread) - outcome ; outcome from UMA
    resolution only (1 if settled YES else 0).
  * YES-BUY taker volume near f (from data-api trades) is the correct fill weight:
    the size a YES-seller could actually sell into.

Reported per entry fraction, CRYPTO and ECON separately:
  n in-band, mean edge/ct, week-clustered t, YES-BUY-vol-weighted mean + week-clustered t,
  mean remaining hold (days), and ANNUALIZED return-on-capital
  = (edge / (1-entry_price)) / ((1-f) * horizon_years).   [capital per contract selling
  YES ~ buying NO at (1-entry)].  Plus the fraction that MAXIMIZES risk-adjusted return.

Anti-artifact discipline (we have killed ~6 candidates on exactly these):
  causal entry (no future price); outcome only from resolution; YES-BUY volume
  weighting (not total); week-clustered t; executable BID (mid - half-spread), not
  optimistic mid; explicit watch on mechanical convergence at very late f (price->outcome
  => spurious "edge"); small-n fractions flagged.

Public Polymarket API only, read-only, NO orders, NO capital.
"""
import os, sys, json, time, math, re, datetime as dt
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np

CACHE = "/home/user/Codex-playground-/scratchpad/lstiming_cache"
os.makedirs(CACHE, exist_ok=True)
GAMMA = "https://gamma-api.polymarket.com"
CLOB  = "https://clob.polymarket.com"
DATA  = "https://data-api.polymarket.com"

# ---- study parameters ----
BAND_LO, BAND_HI = 0.10, 0.35          # longshot band
QUAL_FRAC        = 0.40                 # must touch band within first 40% of life (no peek)
FRACTIONS        = [0.20, 0.35, 0.50, 0.65, 0.80]
HALF_SPREAD      = {"crypto": 0.010, "econ": 0.015}   # conservative fixed half-spread estimate
VOL_WIN          = 0.10                 # YES-buy volume weight window: [f-0.10, f+0.10]*life around entry
DATE_CUTOFF      = "2025-06-01"         # fresh sample: only markets resolving on/after this
MIN_N_FLAG       = 30                   # flag fractions with fewer in-band markets than this
YEAR_SEC         = 365.25 * 86400.0

S = requests.Session(); S.headers.update({"User-Agent": "research/1.0"})


def _get(url, params=None, tries=4, timeout=40):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.3 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(1.1 * (i + 1))
    return None


def cache_get(key, fn):
    p = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".json")
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            pass
    v = fn()
    if v is not None:
        tmp = p + ".tmp"
        with open(tmp, "w") as f:
            json.dump(v, f)
        os.replace(tmp, p)
    return v


def parse_dt(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def iso_week(ts):
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def strike_from(m):
    g = (m.get("groupItemTitle") or "").replace(",", "").replace("$", "").strip()
    try:
        return float(g)
    except Exception:
        mt = re.search(r"\$?([0-9]+(?:\.[0-9]+)?)(k|K)?", (m.get("question") or "").replace(",", ""))
        if mt:
            v = float(mt.group(1))
            if mt.group(2):
                v *= 1000
            return v
    return None


def resolved_outcome(m):
    """yes_win in {0.0,1.0} or None if not cleanly resolved to 0/1."""
    if (m.get("umaResolutionStatus") or "").lower() != "resolved" and not m.get("closed"):
        return None
    op, oc = m.get("outcomePrices"), m.get("outcomes")
    try:
        op = json.loads(op) if isinstance(op, str) else op
        oc = json.loads(oc) if isinstance(oc, str) else oc
    except Exception:
        return None
    if not op or not oc:
        return None
    d = {str(oc[i]).lower(): float(op[i]) for i in range(min(len(oc), len(op)))}
    y = d.get("yes")
    if y is None:
        return None
    if y > 0.98:
        return 1.0
    if y < 0.02:
        return 0.0
    return None


# ---------------------------------------------------------------- universe
def build_crypto():
    markets = []
    for sid, asset in [(45, "BTC"), (42, "ETH")]:
        def fn(sid=sid):
            out, off = [], 0
            while True:
                d = _get(f"{GAMMA}/events", dict(series_id=sid, closed="true", limit=100, offset=off))
                if not d:
                    break
                out += d; off += 100
                if len(d) < 100:
                    break
            return out
        evs = cache_get(f"cry_events_{sid}", fn) or []
        for e in evs:
            if not e.get("closed"):
                continue
            start, end = parse_dt(e.get("startDate")), parse_dt(e.get("endDate"))
            if not start or not end:
                continue
            if end.isoformat() < DATE_CUTOFF:
                continue
            life_d = (end - start).total_seconds() / 86400.0
            if not (2.0 <= life_d <= 10.0):      # isolate the ~7d weekly (drop intraday & long)
                continue
            mks = e.get("markets", [])
            if len(mks) < 5:
                continue
            for m in mks:
                if "above" not in (m.get("question") or "").lower():
                    continue
                yw = resolved_outcome(m)
                if yw is None:
                    continue
                try:
                    toks = json.loads(m["clobTokenIds"])
                except Exception:
                    continue
                if len(toks) < 2:
                    continue
                markets.append(dict(pop="crypto", asset=asset, slug=e.get("slug"),
                                    question=m.get("question"), conditionId=m.get("conditionId"),
                                    yes_token=toks[0], strike=strike_from(m), yes_win=yw,
                                    start=start.timestamp(), end=end.timestamp(), life_days=life_d))
    return markets


ECON_Q = ["CPI", "inflation", "PPI", "jobs report", "unemployment", "JOLTS",
          "Fed decision", "GDP", "nonfarm", "core PCE", "retail sales", "payrolls"]


def build_econ():
    markets, seen = [], set()
    for q in ECON_Q:
        d = cache_get(f"econ_search_{q}",
                      lambda q=q: _get(f"{GAMMA}/public-search", dict(q=q, limit_per_type=60)))
        evs = (d or {}).get("events", []) if isinstance(d, dict) else []
        for e in evs:
            slug = e.get("slug")
            if not slug or slug in seen or not e.get("closed"):
                continue
            mks = e.get("markets", [])
            if len(mks) < 4:                     # need a real mutually-exclusive bucket structure
                continue
            start, end = parse_dt(e.get("startDate") or e.get("createdAt")), parse_dt(e.get("endDate"))
            if not start or not end or end <= start:
                continue
            if end.isoformat() < DATE_CUTOFF:
                continue
            life_d = (end - start).total_seconds() / 86400.0
            if life_d < 1.0 or life_d > 90.0:    # recurring releases, not long-dated one-offs
                continue
            seen.add(slug)
            for m in mks:
                yw = resolved_outcome(m)
                if yw is None:
                    continue
                try:
                    toks = json.loads(m["clobTokenIds"])
                except Exception:
                    continue
                if len(toks) < 2:
                    continue
                markets.append(dict(pop="econ", asset="ECON", slug=slug,
                                    question=m.get("question"), conditionId=m.get("conditionId"),
                                    yes_token=toks[0], strike=None, yes_win=yw,
                                    start=start.timestamp(), end=end.timestamp(), life_days=life_d))
    return markets


# ---------------------------------------------------------------- price path + trades
def price_history(token, start, end):
    key = f"ph_{token}_{int(start)}_{int(end)}"
    def fn():
        d = _get(f"{CLOB}/prices-history",
                 dict(market=token, startTs=int(start), endTs=int(end), fidelity=60))
        return (d or {}).get("history", []) if isinstance(d, dict) else []
    h = cache_get(key, fn) or []
    return sorted([(float(p["t"]), float(p["p"])) for p in h if "t" in p and "p" in p])


def yesbuy_trades(conditionId):
    """list of (ts, yesbuy_size). yesbuy = taker buys YES exposure:
       (outcome Yes & side BUY) or (outcome No & side SELL)."""
    key = f"tr_{conditionId}"
    def fn():
        out, off = [], 0
        for _ in range(6):
            d = _get(f"{DATA}/trades", dict(market=conditionId, limit=500, offset=off))
            if not d:
                break
            out += d
            if len(d) < 500:
                break
            off += 500
        return out
    raw = cache_get(key, fn) or []
    ev = []
    for t in raw:
        side = (t.get("side") or "").upper()
        oc = (t.get("outcome") or "").lower()
        sz = float(t.get("size") or 0)
        ts = int(t.get("timestamp") or 0)
        if sz <= 0 or ts <= 0:
            continue
        if (oc == "yes" and side == "BUY") or (oc == "no" and side == "SELL"):
            ev.append((ts, sz))
    return ev


def entry_at(hist, t_target):
    """CAUSAL: YES mid at the last tick at/before t_target; None if none exist."""
    px = None
    for t, p in hist:
        if t <= t_target:
            px = p
        else:
            break
    return px


def eval_market(mk):
    hist = price_history(mk["yes_token"], mk["start"], mk["end"])
    if len(hist) < 3:
        return None
    st, en = mk["start"], mk["end"]
    life = en - st
    if life <= 0:
        return None
    # longshot qualification: touches band within first QUAL_FRAC of life (no peek)
    q_cut = st + QUAL_FRAC * life
    if not any(t <= q_cut and BAND_LO <= p <= BAND_HI for t, p in hist):
        return None
    trades = yesbuy_trades(mk["conditionId"])
    tot_vol = sum(s for _, s in trades) or 0.0
    hs = HALF_SPREAD[mk["pop"]]
    out = dict(mk_meta=dict(pop=mk["pop"], asset=mk["asset"], week=iso_week(en),
                            life_days=mk["life_days"]),
               by_frac={})
    for f in FRACTIONS:
        t_tgt = st + f * life
        mid = entry_at(hist, t_tgt)
        if mid is None:
            continue
        in_band = BAND_LO <= mid <= BAND_HI
        sell_px = mid - hs
        edge = sell_px - mk["yes_win"]
        # YES-buy volume near entry (fill weight); fall back to total so market isn't dropped
        lo, hi = st + (f - VOL_WIN) * life, st + (f + VOL_WIN) * life
        w = sum(s for ts, s in trades if lo <= ts <= hi)
        w_used = w if w > 0 else tot_vol
        rem_hold_yr = max(1e-9, (1 - f) * life / YEAR_SEC)
        cap = max(1e-9, 1 - mid)
        roc = (edge / cap) / rem_hold_yr
        out["by_frac"][f] = dict(in_band=in_band, mid=mid, sell_px=sell_px, edge=edge,
                                 outcome=mk["yes_win"], w=w_used, w_near=w,
                                 hold_days=(1 - f) * mk["life_days"], roc=roc)
    return out


# ---------------------------------------------------------------- stats
def wc_t(week_means):
    xs = list(week_means.values())
    k = len(xs)
    if k < 2:
        return float("nan"), k
    sd = np.std(xs, ddof=1)
    if sd == 0:
        return float("nan"), k
    return float(np.mean(xs) / (sd / math.sqrt(k))), k


def summarize(results, pop):
    rows = []
    for f in FRACTIONS:
        recs = [(r["mk_meta"], r["by_frac"][f]) for r in results
                if f in r["by_frac"] and r["by_frac"][f]["in_band"]]
        n = len(recs)
        if n == 0:
            rows.append(dict(f=f, n=0)); continue
        edges = np.array([d["edge"] for _, d in recs])
        rocs = np.array([d["roc"] for _, d in recs])
        holds = np.array([d["hold_days"] for _, d in recs])
        ws = np.array([d["w"] for _, d in recs])
        mids = np.array([d["mid"] for _, d in recs])
        yes_rate = float(np.mean([d["outcome"] for _, d in recs]))
        # equal-weight week-clustered
        wk = defaultdict(list)
        for meta, d in recs:
            wk[meta["week"]].append(d["edge"])
        wmeans = {k: float(np.mean(v)) for k, v in wk.items()}
        t_eq, kk = wc_t(wmeans)
        # YES-buy-volume-weighted, week-clustered (weighted mean within week, then t across weeks)
        wkw = defaultdict(lambda: [0.0, 0.0])
        wkr = defaultdict(lambda: [0.0, 0.0])   # weighted roc within week
        for meta, d in recs:
            wkw[meta["week"]][0] += d["edge"] * d["w"]
            wkw[meta["week"]][1] += d["w"]
            wkr[meta["week"]][0] += d["roc"] * d["w"]
            wkr[meta["week"]][1] += d["w"]
        wmeans_w = {k: (a / b if b > 0 else 0.0) for k, (a, b) in wkw.items()}
        t_w, _ = wc_t(wmeans_w)
        vw_edge = float(np.sum(edges * ws) / np.sum(ws)) if np.sum(ws) > 0 else float("nan")
        vw_roc = float(np.sum(rocs * ws) / np.sum(ws)) if np.sum(ws) > 0 else float("nan")
        rows.append(dict(
            f=f, n=n, weeks=kk, mean_edge=float(np.mean(edges)),
            t_eq=t_eq, vw_edge=vw_edge, t_w=t_w,
            mean_mid=float(np.mean(mids)), yes_rate=yes_rate,
            hold_days=float(np.mean(holds)),
            roc=float(np.mean(rocs)), vw_roc=vw_roc,
            roc_med=float(np.median(rocs))))
    return rows


def fmt_table(rows, pop):
    hs = HALF_SPREAD[pop]
    lines = []
    lines.append(f"POPULATION = {pop.upper()}   (executable SELL = mid - half_spread={hs:.3f}, zero fee)")
    hdr = (f"{'f':>5} {'n':>5} {'wks':>4} {'edge/ct':>9} {'t_eq':>6} "
           f"{'vw_edge':>8} {'t_bv':>6} {'mid':>5} {'yes%':>5} {'hold_d':>7} "
           f"{'ann_ROC':>8} {'vw_ROC':>8}")
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for r in rows:
        if r["n"] == 0:
            lines.append(f"{r['f']:>5.2f} {0:>5}   (no in-band markets)")
            continue
        flag = " *low-n" if r["n"] < MIN_N_FLAG else ""
        lines.append(
            f"{r['f']:>5.2f} {r['n']:>5} {r['weeks']:>4} {r['mean_edge']:>+9.4f} {r['t_eq']:>6.2f} "
            f"{r['vw_edge']:>+8.4f} {r['t_w']:>6.2f} {r['mean_mid']:>5.2f} {r['yes_rate']*100:>5.1f} "
            f"{r['hold_days']:>7.2f} {r['roc']:>+8.2f} {r['vw_roc']:>+8.2f}{flag}")
    return "\n".join(lines)


def pick_sweetspot(rows):
    cand = [r for r in rows if r.get("n", 0) >= MIN_N_FLAG and not math.isnan(r.get("t_w", float("nan")))]
    if not cand:
        cand = [r for r in rows if r.get("n", 0) > 0 and not math.isnan(r.get("t_w", float("nan")))]
    if not cand:
        return None
    best_t = max(cand, key=lambda r: r["t_w"])
    best_roc = max(cand, key=lambda r: (r["vw_roc"] if not math.isnan(r["vw_roc"]) else r["roc"]))
    return best_t, best_roc


def run():
    t0 = time.time()
    print("[build] crypto universe ...", flush=True)
    cry = build_crypto()
    print(f"  crypto candidate markets: {len(cry)}", flush=True)
    print("[build] econ universe ...", flush=True)
    eco = build_econ()
    print(f"  econ candidate markets: {len(eco)}", flush=True)

    out = {}
    for pop, uni in [("crypto", cry), ("econ", eco)]:
        print(f"[eval] {pop}: fetching paths+trades for {len(uni)} markets ...", flush=True)
        results = []
        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {ex.submit(eval_market, mk): mk for mk in uni}
            done = 0
            for fu in as_completed(futs):
                done += 1
                if done % 200 == 0:
                    print(f"    {pop} {done}/{len(uni)}  qualified so far={len(results)}", flush=True)
                try:
                    r = fu.result()
                except Exception:
                    r = None
                if r:
                    results.append(r)
        print(f"  {pop}: {len(results)} longshot-qualified markets "
              f"(touched [{BAND_LO},{BAND_HI}] in first {int(QUAL_FRAC*100)}% of life)", flush=True)
        rows = summarize(results, pop)
        out[pop] = dict(rows=rows, n_qual=len(results), n_uni=len(uni))
        print("\n" + fmt_table(rows, pop) + "\n", flush=True)
        sw = pick_sweetspot(rows)
        if sw:
            bt, br = sw
            print(f"  [{pop}] max risk-adjusted (buy-vol week-clustered t): f={bt['f']:.2f} "
                  f"(t_bv={bt['t_w']:.2f}, edge/ct={bt['mean_edge']:+.4f}, ann_ROC={bt['roc']:+.2f})")
            print(f"  [{pop}] max annualized ROC-on-capital: f={br['f']:.2f} "
                  f"(vw_ROC={br['vw_roc']:+.2f}, t_bv={br['t_w']:.2f})\n", flush=True)
    print(f"[done] {time.time()-t0:.0f}s")
    # dump machine-readable
    with open("/home/user/Codex-playground-/scratchpad/lstiming_out.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    return out


if __name__ == "__main__":
    run()
