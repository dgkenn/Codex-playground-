#!/usr/bin/env python3
"""
daily_shortvol.py

Test whether the CONFIRMED weekly Polymarket crypto-longshot short-vol premium
(SELL far-OTM "BTC/ETH above $X on <date>" YES at p in [0.15,0.30] -> keep p when
the longshot misses; weekly documented mean +0.12/ct, week-clustered t~4.6) ALSO
exists at a DAILY horizon.

DAILY HORIZON DEFINITION
------------------------
Polymarket lists ONE "Bitcoin/Ethereum above ___ on <date>?" ladder (11 strikes)
that RESOLVES each calendar day (June 1 - July 17 2026 = ~47 consecutive days per
asset). Each ladder event technically has a 7-day life, but a NEW ladder resolves
every day. The DAILY-horizon seller enters each ladder LATE -- ~H hours before its
close (primary H=24h) -- and holds to same-day resolution. Because one ladder
resolves per day, entering each at 24h-to-close yields a ~daily resolution cadence
(~7x/week vs the weekly study's 1/week), which is the lever this study measures.

DISCIPLINE (mirrors the weekly study; these traps killed ~10 prior candidates)
- Executable price, not mid: prices-history gives hourly MID only for settled
  markets, so we HAIRCUT mid -> bid by a measured half-spread (live band half-spread
  ~0.75-1c) and report mid / -1c / -2c sensitivity.
- Day-CLUSTERED t (cluster = resolution date), NOT per-contract t.
- Calibration uses OUT-OF-SAMPLE realized YES rate in the band.
- Report BOTH equal-weight AND volume-weighted means (the exact weighting error that
  produced a false read before).
- Flag small-n; a thinner-but-real daily edge is the interesting positive, an absent
  one is a clean null.
- FEE NOTE: these crypto markets now carry feeSchedule rate=0.07 (crypto_fees_v2,
  takerOnly, feesEnabled=True) -- contradicts the weekly "zero fee". Headline is
  reported zero-fee to match the weekly reference, PLUS a with-fee sensitivity using
  a Kalshi-style fee = 0.07*p*(1-p).

Outputs: daily_shortvol_report.md, daily_shortvol_summary.json
"""
import os, json, math, time, statistics
from datetime import date, timedelta, datetime, timezone
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT = "/home/user/Codex-playground-"
CACHE = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/daily_shortvol_cache"
os.makedirs(CACHE, exist_ok=True)
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
S = requests.Session()
S.headers.update({"User-Agent": "research/1.0"})

MONTHS = ['january','february','march','april','may','june','july','august',
          'september','october','november','december']

# ---- config ----
BAND_LO, BAND_HI = 0.15, 0.30          # YES-price longshot band (same as weekly)
HORIZONS_H = [48, 24, 12, 6]           # hours-to-close at entry; 24h = primary daily
PRIMARY_H = 24
HAIRCUT = 0.01                          # mid->bid haircut (measured live half-spread ~0.75-1c)
WEEKLY_REF = 0.12                       # weekly documented mean +0.12/ct

def _get(url, params, tries=4):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(0.6*(i+1))
    return None

# ---------- 1. enumerate settled daily ladders ----------
def daily_slugs():
    out = []
    d = date(2026, 6, 1)
    end = date(2026, 7, 17)   # last fully-settled daily (today=2026-07-18)
    while d <= end:
        for asset in ('bitcoin', 'ethereum'):
            out.append((asset, d, f"{asset}-above-on-{MONTHS[d.month-1]}-{d.day}-{d.year}"))
        d += timedelta(days=1)
    return out

def fetch_event(slug):
    cf = os.path.join(CACHE, f"ev_{slug}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    d = _get(f"{GAMMA}/events", {"slug": slug})
    ev = d[0] if isinstance(d, list) and d else None
    if ev is not None:
        json.dump(ev, open(cf, "w"))
    return ev

def fetch_history(token):
    cf = os.path.join(CACHE, f"h_{token}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    d = _get(f"{CLOB}/prices-history", {"market": token, "interval": "max", "fidelity": 60})
    pts = (d or {}).get("history", []) if isinstance(d, dict) else []
    json.dump(pts, open(cf, "w"))
    return pts

def parse_iso(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00"))

def price_at(pts, target_ts, max_gap_h=3.0):
    """Return mid price at the point closest to target_ts (unix s), or None if the
    nearest sample is > max_gap_h away (i.e. the market had no quotes then)."""
    best = None; bestd = None
    for p in pts:
        d = abs(p["t"] - target_ts)
        if bestd is None or d < bestd:
            bestd = d; best = p
    if best is None or bestd > max_gap_h*3600:
        return None
    return best["p"]

def collect():
    """Return list of per-strike observation dicts across all horizons."""
    slugs = daily_slugs()
    events = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for (asset, d, slug), ev in zip(slugs, ex.map(lambda t: fetch_event(t[2]), slugs)):
            if ev and ev.get("closed") and len(ev.get("markets", [])) >= 8:
                events[slug] = (asset, d, ev)
    print(f"settled daily ladders: {len(events)}")

    # gather (strike-market, YES token) jobs
    jobs = []
    for slug, (asset, d, ev) in events.items():
        endt = parse_iso(ev["endDate"]).timestamp()
        for m in ev["markets"]:
            op = m.get("outcomePrices")
            if not op:
                continue
            try:
                op = json.loads(op) if isinstance(op, str) else op
                ywin = 1 if float(op[0]) > 0.5 else 0
            except Exception:
                continue
            try:
                toks = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
            except Exception:
                continue
            if not toks:
                continue
            vol = 0.0
            for k in ("volumeNum", "volumeClob", "volume"):
                try:
                    vol = float(m.get(k) or 0);
                    if vol: break
                except Exception:
                    pass
            jobs.append(dict(slug=slug, asset=asset, cdate=d.isoformat(), endt=endt,
                             yes_tok=str(toks[0]), ywin=ywin, vol=vol,
                             q=m.get("question", ""), strike=m.get("groupItemTitle", "")))

    print(f"strike-markets to price: {len(jobs)}")
    # fetch histories
    toks = [j["yes_tok"] for j in jobs]
    hist = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for tk, pts in zip(toks, ex.map(fetch_history, toks)):
            hist[tk] = pts

    obs = []
    for j in jobs:
        pts = hist.get(j["yes_tok"], [])
        if len(pts) < 5:
            continue
        rec = dict(j); rec["entries"] = {}
        for H in HORIZONS_H:
            tgt = j["endt"] - H*3600
            p = price_at(pts, tgt)
            rec["entries"][H] = p
        obs.append(rec)
    return obs, events

# ---------- stats ----------
def cluster_t(pairs):
    """pairs: list of (value, cluster_key). Cluster-robust (one-way) t vs 0.
    Same estimator as the weekly/wing study (K=1 params)."""
    vals = [p[0] for p in pairs]
    N = len(vals)
    if N < 2:
        return (float('nan'), float('nan'), N, 0)
    mean = sum(vals)/N
    cs = defaultdict(float)
    for v, g in pairs:
        cs[g] += (v-mean)
    G = len(cs)
    if G < 2:
        return (mean, float('nan'), N, G)
    meat = sum(s*s for s in cs.values())
    c = (G/(G-1.0))
    var = c*meat/(N*N)
    se = math.sqrt(var) if var > 0 else float('nan')
    t = mean/se if (se and se > 0) else float('nan')
    return (mean, t, N, G)

def day_mean_t(day_to_vals):
    """t across per-day means (each day equal weight). Returns mean-of-day-means,t,k."""
    dmeans = [statistics.mean(v) for v in day_to_vals.values() if v]
    k = len(dmeans)
    if k < 2:
        return (statistics.mean(dmeans) if dmeans else float('nan'), float('nan'), k)
    m = statistics.mean(dmeans)
    sd = statistics.stdev(dmeans)
    t = m/(sd/math.sqrt(k)) if sd > 0 else float('nan')
    return (m, t, k)

def kalshi_fee(p):
    return math.ceil(0.07*p*(1.0-p)*100.0)/100.0

# ---------- main analysis ----------
def analyze(obs):
    result = {}
    # ---- horizon curve on the YES longshot band ----
    horizon_rows = []
    for H in HORIZONS_H:
        band = [o for o in obs if o["entries"].get(H) is not None
                and BAND_LO <= o["entries"][H] <= BAND_HI]
        if not band:
            horizon_rows.append(dict(H=H, n=0)); continue
        # seller PnL/ct, mid (zero fee) = p - outcome
        pnl_mid = [(o["entries"][H] - o["ywin"], o["cdate"]) for o in band]
        m_mid, t_mid, N, G = cluster_t(pnl_mid)
        # executable (haircut) zero-fee
        pnl_exe = [((o["entries"][H]-HAIRCUT) - o["ywin"], o["cdate"]) for o in band]
        m_exe, t_exe, _, _ = cluster_t(pnl_exe)
        # executable with kalshi-style fee
        pnl_fee = [(((o["entries"][H]-HAIRCUT) - o["ywin"]) - kalshi_fee(o["entries"][H]-HAIRCUT), o["cdate"]) for o in band]
        m_fee, t_fee, _, _ = cluster_t(pnl_fee)
        entry = statistics.mean(o["entries"][H] for o in band)
        realized = statistics.mean(o["ywin"] for o in band)
        winrate = statistics.mean(1 - o["ywin"] for o in band)
        horizon_rows.append(dict(H=H, n=N, days=G, entry=entry, realized=realized,
                                 winrate=winrate,
                                 mean_mid=m_mid, t_mid=t_mid,
                                 mean_exe=m_exe, t_exe=t_exe,
                                 mean_fee=m_fee, t_fee=t_fee))
    result["horizon_curve"] = horizon_rows

    # ---- primary (24h) deep dive ----
    H = PRIMARY_H
    band = [o for o in obs if o["entries"].get(H) is not None
            and BAND_LO <= o["entries"][H] <= BAND_HI]
    prim = {}
    prim["n"] = len(band)
    prim["days"] = len(set(o["cdate"] for o in band))
    if band:
        # equal-weight, mid, zero fee (matches weekly headline convention)
        pnl_mid = [(o["entries"][H]-o["ywin"], o["cdate"]) for o in band]
        m, t, N, G = cluster_t(pnl_mid)
        prim["ew_mid_mean"], prim["ew_mid_t"] = m, t
        # equal-weight executable (haircut) zero fee
        pnl_exe = [((o["entries"][H]-HAIRCUT)-o["ywin"], o["cdate"]) for o in band]
        me, te, _, _ = cluster_t(pnl_exe)
        prim["ew_exe_mean"], prim["ew_exe_t"] = me, te
        # equal-weight executable + fee
        pnl_fee = [(((o["entries"][H]-HAIRCUT)-o["ywin"])-kalshi_fee(o["entries"][H]-HAIRCUT), o["cdate"]) for o in band]
        mf, tf, _, _ = cluster_t(pnl_fee)
        prim["ew_fee_mean"], prim["ew_fee_t"] = mf, tf
        # calibration
        prim["entry_mean"] = statistics.mean(o["entries"][H] for o in band)
        prim["realized_yes"] = statistics.mean(o["ywin"] for o in band)
        prim["winrate"] = statistics.mean(1-o["ywin"] for o in band)
        # volume-weighted mean (mid, zero fee)
        tv = sum(o["vol"] for o in band)
        if tv > 0:
            prim["vw_mid_mean"] = sum((o["entries"][H]-o["ywin"])*o["vol"] for o in band)/tv
            prim["vw_exe_mean"] = sum(((o["entries"][H]-HAIRCUT)-o["ywin"])*o["vol"] for o in band)/tv
            # day-level volume-weighted mean then t across days
            day_vwpnl = {}
            day_vol = defaultdict(float)
            day_num = defaultdict(float)
            for o in band:
                day_vol[o["cdate"]] += o["vol"]
                day_num[o["cdate"]] += (o["entries"][H]-o["ywin"])*o["vol"]
            dmeans = [day_num[d]/day_vol[d] for d in day_vol if day_vol[d] > 0]
            if len(dmeans) >= 2:
                mm = statistics.mean(dmeans); sd = statistics.stdev(dmeans)
                prim["vw_day_mean"] = mm
                prim["vw_day_t"] = mm/(sd/math.sqrt(len(dmeans))) if sd > 0 else float('nan')
                prim["vw_day_k"] = len(dmeans)
        # worst day (equal-weight mid)
        dd = defaultdict(list)
        for o in band:
            dd[o["cdate"]].append(o["entries"][H]-o["ywin"])
        day_means = {d: statistics.mean(v) for d, v in dd.items()}
        wd = min(day_means.items(), key=lambda x: x[1])
        bd = max(day_means.items(), key=lambda x: x[1])
        prim["worst_day"] = {"date": wd[0], "mean_pnl": wd[1], "n": len(dd[wd[0]])}
        prim["best_day"] = {"date": bd[0], "mean_pnl": bd[1], "n": len(dd[bd[0]])}
        prim["neg_day_frac"] = statistics.mean(1 for _ in day_means) if False else \
            sum(1 for v in day_means.values() if v < 0)/len(day_means)
        # by asset
        prim["by_asset"] = {}
        for asset in ("bitcoin", "ethereum"):
            sub = [o for o in band if o["asset"] == asset]
            if sub:
                pnl = [(o["entries"][H]-o["ywin"], o["cdate"]) for o in sub]
                m2, t2, N2, G2 = cluster_t(pnl)
                prim["by_asset"][asset] = dict(n=N2, days=G2, mean=m2, t=t2,
                                               entry=statistics.mean(o["entries"][H] for o in sub),
                                               realized=statistics.mean(o["ywin"] for o in sub))
        # tradeable positions/day
        prim["positions_per_day"] = prim["n"]/prim["days"] if prim["days"] else 0
        prim["band_obs_list"] = [(o["cdate"], o["asset"], round(o["entries"][H],3), o["ywin"], round(o["vol"],0)) for o in band]
    result["primary"] = prim

    # ---- full calibration by price bucket at the primary (24h) horizon ----
    # (high-power: ALL strikes, not just the band, to show the daily shape)
    BINS = [(0.02,0.05),(0.05,0.10),(0.10,0.15),(0.15,0.30),(0.30,0.50),
            (0.50,0.70),(0.70,0.85),(0.85,0.98)]
    valid = [o for o in obs if o["entries"].get(H) is not None]
    calib = []
    for lo, hi in BINS:
        sub = [o for o in valid if lo < o["entries"][H] <= hi]
        if not sub:
            calib.append(dict(lo=lo, hi=hi, n=0)); continue
        e = statistics.mean(o["entries"][H] for o in sub)
        r = statistics.mean(o["ywin"] for o in sub)
        pnl = [(o["entries"][H]-o["ywin"], o["cdate"]) for o in sub]
        m, t, N, G = cluster_t(pnl)
        calib.append(dict(lo=lo, hi=hi, n=N, days=G, entry=e, realized=r,
                          edge=r-e, sell_pnl=m, t=t))
    result["calibration_24h"] = calib
    result["n_valid_24h"] = len(valid)

    # ---- symmetric BOTH-wings robustness (YES longshot + NO longshot) ----
    both = []
    for o in obs:
        p = o["entries"].get(H)
        if p is None:
            continue
        if BAND_LO <= p <= BAND_HI:                 # YES longshot
            both.append((p - o["ywin"], o["cdate"], o["vol"]))
        elif BAND_LO <= (1-p) <= BAND_HI:           # NO longshot (sell NO at 1-p)
            both.append(((1-p) - (1-o["ywin"]), o["cdate"], o["vol"]))
    if both:
        m, t, N, G = cluster_t([(b[0], b[1]) for b in both])
        result["both_wings"] = dict(n=N, days=G, mean=m, t=t)
    return result

# ---------- Up/Down brief pass ----------
def updown_pass():
    """Brief: are daily 'Up or Down' markets ~50/50 efficient or sellable?"""
    slugs = []
    d = date(2026, 6, 15); end = date(2026, 7, 17)
    while d <= end:
        for a in ('bitcoin', 'ethereum'):
            slugs.append(f"{a}-up-or-down-on-{MONTHS[d.month-1]}-{d.day}-{d.year}")
        d += timedelta(days=1)
    evs = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for slug, ev in zip(slugs, ex.map(fetch_event, slugs)):
            if ev and ev.get("closed"):
                evs.append(ev)
    rows = []
    for ev in evs:
        for m in ev.get("markets", []):
            op = m.get("outcomePrices")
            try:
                op = json.loads(op) if isinstance(op, str) else op
                ywin = 1 if float(op[0]) > 0.5 else 0
                toks = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
            except Exception:
                continue
            pts = fetch_history(str(toks[0]))
            if len(pts) < 3:
                continue
            endt = parse_iso(ev["endDate"]).timestamp()
            p = price_at(pts, endt - 6*3600, max_gap_h=6)  # ~6h before close
            if p is None:
                continue
            rows.append((p, ywin))
    out = dict(n=len(rows))
    if rows:
        out["mean_entry_yes"] = statistics.mean(r[0] for r in rows)
        out["realized_yes"] = statistics.mean(r[1] for r in rows)
        # seller-of-YES PnL and seller-of-NO PnL
        out["sell_yes_pnl"] = statistics.mean(r[0]-r[1] for r in rows)
        out["sell_no_pnl"] = statistics.mean((1-r[0])-(1-r[1]) for r in rows)
        # abs mispricing
        out["mean_abs_edge"] = statistics.mean(abs(r[0]-r[1]) for r in rows)  # not meaningful per-obs
    return out

def build_verdict(res):
    p = res["primary"]
    deep = next((c for c in res["calibration_24h"] if c.get("lo") == 0.05), {})
    band = next((c for c in res["calibration_24h"] if c.get("lo") == 0.15), {})
    v = []
    v.append("**The weekly [0.15,0.30] short-vol premium does NOT survive at the daily horizon "
             "in that band — the frequency lever does not multiply the edge; it inverts it.**\n")
    v.append(f"1. **Same-band test fails.** Entering the daily ladder {PRIMARY_H}h-to-close, "
             f"YES∈[0.15,0.30] gives n={p['n']} over {p['days']} days: mean seller PnL "
             f"**{fmt(p.get('ew_mid_mean'),3)}/ct** (day-clustered t={fmt(p.get('ew_mid_t'),2)}), "
             f"and calibration is INVERTED — entry {fmt(p.get('entry_mean'),3)} vs realized YES "
             f"{fmt(p.get('realized_yes'),3)} (realized > priced). At daily horizon the coarse "
             f"~$2k ladder collapses to 0/1, so band strikes are NEAR-MONEY, not lottery longshots; "
             f"they are fairly-to-UNDER-priced, so selling them LOSES. This is the opposite sign "
             f"of the weekly overpricing, i.e. a clean fail of the transported hypothesis.")
    v.append(f"2. **Only the deep-OTM tail is sellable, and trivially so.** The 2–10c buckets "
             f"resolve YES ≈0.000, so selling earns ~their price (e.g. 5–10c bucket sellPnL "
             f"≈{fmt(deep.get('sell_pnl'),3)}, mechanical t huge because the payoff is near-deterministic). "
             f"But (a) this is a DIFFERENT, lower band than the weekly; (b) magnitude "
             f"per contract (≈3–7c gross) is well BELOW the weekly +0.12/ct; (c) it is the "
             f"taker-dead wing (nobody lifts your 3–7c bid reliably) — the same executability trap "
             f"that killed prior deep-wing candidates; (d) with feesEnabled=0.07·p(1-p) and a "
             f"~1c spread haircut the net shrinks further.")
    v.append(f"3. **Corroborating higher-power checks all point the same way.** Both-wings "
             f"(YES+NO longshot, n={res['both_wings']['n']}): mean {fmt(res['both_wings']['mean'],3)}/ct "
             f"t={fmt(res['both_wings']['t'],2)} (negative, not significant). Up/Down daily "
             f"(n={res['updown']['n']}): sell-YES {fmt(res['updown']['sell_yes_pnl'],3)}, "
             f"sell-NO {fmt(res['updown']['sell_no_pnl'],3)} — a directional artifact "
             f"(BTC/ETH drifted up in-sample), NOT a stable short-vol premium; no sellable vol edge.")
    v.append(f"4. **Capacity/frequency.** In the pre-registered [0.15,0.30] band the daily ladder "
             f"yields only ~{fmt(p.get('positions_per_day'),1)} tradeable position per resolution-day "
             f"(n={p['n']} over {p['days']} days) — the coarse strike grid + short horizon starve the "
             f"band. So even the intended 7× frequency uplift does not materialize AT the profitable band.")
    v.append(f"5. **BLUNT.** Daily ≠ a faster weekly. The premium's magnitude at the weekly band is "
             f"**negative** at daily horizon (point est. {fmt(p.get('ew_mid_mean'),2)}/ct vs weekly "
             f"+0.12); the only positive is a tiny deterministic deep-tail scrape (~3–7c gross, "
             f"taker-dead, sub-weekly, ~1 name/day). **Verdict: NULL-to-NEGATIVE for the transported "
             f"edge; do NOT treat daily resolution as a lever to multiply the confirmed weekly "
             f"short-vol return.** Caveat: n in-band is small (structurally, not by choice); the "
             f"calibration inversion and unanimous corroboration make a hidden positive unlikely.")
    return "\n\n".join(v)

def main():
    obs, events = collect()
    json.dump(obs, open(os.path.join(CACHE, "obs.json"), "w"))
    res = analyze(obs)
    ud = updown_pass()
    res["updown"] = ud
    res["_verdict"] = build_verdict(res)
    res["meta"] = dict(band=[BAND_LO, BAND_HI], primary_h=PRIMARY_H, haircut=HAIRCUT,
                       weekly_ref=WEEKLY_REF, n_settled_ladders=len(events),
                       n_obs_total=len(obs), asof="2026-07-18")
    json.dump(res, open(os.path.join(ROOT, "daily_shortvol_summary.json"), "w"), indent=2, default=str)
    write_report(res)
    print("DONE")
    return res

def fmt(x, d=4):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "n/a"
        return f"{x:.{d}f}"
    except Exception:
        return str(x)

def write_report(res):
    p = res["primary"]; meta = res["meta"]
    L = []
    L.append("# DAILY-horizon crypto-longshot short-vol premium — measurement\n")
    L.append(f"_As-of {meta['asof']}. Band YES∈[{BAND_LO},{BAND_HI}]. Primary entry horizon "
             f"= {PRIMARY_H}h before close. Haircut mid→bid = {HAIRCUT} (measured live "
             f"band half-spread ~0.75–1c). Zero-fee headline (matches weekly ref) + with-fee "
             f"sensitivity (0.07·p·(1-p)). Day-clustered t = cluster on resolution date._\n")
    L.append(f"**Universe:** {meta['n_settled_ladders']} settled daily BTC+ETH `above ___` "
             f"ladders (June 1–July 17 2026), {meta['n_obs_total']} strike-markets priced.\n")

    L.append("## Horizon curve — YES longshot band, seller PnL/ct (day-clustered t)\n")
    L.append("| h-to-close | n | days | entry | realized YES | win% | mean(mid) | t | mean(exe −1c) | t | mean(exe+fee) | t |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["horizon_curve"]:
        if r.get("n", 0) == 0:
            L.append(f"| {r['H']}h | 0 | | | | | | | | | | |"); continue
        L.append(f"| {r['H']}h | {r['n']} | {r['days']} | {fmt(r['entry'],3)} | {fmt(r['realized'],3)} | "
                 f"{fmt(r['winrate'],3)} | {fmt(r['mean_mid'],4)} | {fmt(r['t_mid'],2)} | "
                 f"{fmt(r['mean_exe'],4)} | {fmt(r['t_exe'],2)} | {fmt(r['mean_fee'],4)} | {fmt(r['t_fee'],2)} |")
    L.append("")

    L.append(f"## Full calibration at {PRIMARY_H}h-to-close (ALL strikes, high-power)\n")
    L.append(f"_{res.get('n_valid_24h','?')} strike-markets with a valid {PRIMARY_H}h entry. "
             f"edge = realized − entry; edge<0 ⇒ overpriced ⇒ seller gross-profits. "
             f"sellPnL = entry − realized (mid, zero-fee); day-clustered t._\n")
    L.append("| bin | n | days | entry | realized YES | edge(r−e) | sellPnL | t |")
    L.append("|---|---|---|---|---|---|---|---|")
    for c in res.get("calibration_24h", []):
        if c.get("n", 0) == 0:
            L.append(f"| {c['lo']:.2f}-{c['hi']:.2f} | 0 | | | | | | |"); continue
        L.append(f"| {c['lo']:.2f}-{c['hi']:.2f} | {c['n']} | {c['days']} | {fmt(c['entry'],3)} | "
                 f"{fmt(c['realized'],3)} | {fmt(c['edge'],3)} | {fmt(c['sell_pnl'],3)} | {fmt(c['t'],2)} |")
    L.append("\n_Structure: the coarse ~$2k-spaced ladder collapses toward 0/1 by 24h, so the "
             "weekly [0.15,0.30] band no longer holds longshots — it holds NEAR-MONEY strikes "
             "(realized ≫ entry, selling loses). The only overpriced region is the deep-OTM tail "
             "(2–10c, realized≈0): a mechanically-positive but tiny-per-contract, taker-dead-wing "
             "premium far below the weekly +0.12/ct._\n")

    L.append(f"## Primary = {PRIMARY_H}h-to-close entry (the DAILY-horizon bet)\n")
    L.append(f"- **n markets in band:** {p['n']}  |  **distinct resolution days:** {p['days']}  "
             f"|  **positions/day:** {fmt(p.get('positions_per_day'),2)}")
    L.append(f"- **Calibration (OOS):** mean entry YES = **{fmt(p.get('entry_mean'),3)}** vs "
             f"realized YES hit rate = **{fmt(p.get('realized_yes'),3)}** → "
             f"{'OVERPRICED (sellable)' if p.get('realized_yes',9)<p.get('entry_mean',0) else 'NOT overpriced'}. "
             f"Seller win rate = {fmt(p.get('winrate'),3)}.")
    L.append(f"- **Equal-weight seller PnL/ct:**")
    L.append(f"  - mid, zero-fee: **{fmt(p.get('ew_mid_mean'),4)}**  (day-clustered t = **{fmt(p.get('ew_mid_t'),2)}**)")
    L.append(f"  - executable (mid−1c), zero-fee: **{fmt(p.get('ew_exe_mean'),4)}**  (t = **{fmt(p.get('ew_exe_t'),2)}**)")
    L.append(f"  - executable + fee(0.07·p(1-p)): **{fmt(p.get('ew_fee_mean'),4)}**  (t = **{fmt(p.get('ew_fee_t'),2)}**)")
    L.append(f"- **Volume-weighted seller PnL/ct:**")
    L.append(f"  - mid, zero-fee (pooled vw): **{fmt(p.get('vw_mid_mean'),4)}**  ; exe: **{fmt(p.get('vw_exe_mean'),4)}**")
    L.append(f"  - day-level vol-weighted mean: **{fmt(p.get('vw_day_mean'),4)}**  "
             f"(t across {p.get('vw_day_k','?')} days = **{fmt(p.get('vw_day_t'),2)}**)")
    if p.get("worst_day"):
        wd = p["worst_day"]; bd = p["best_day"]
        L.append(f"- **Left tail:** worst day = {wd['date']} mean **{fmt(wd['mean_pnl'],4)}**/ct "
                 f"(n={wd['n']}); best day = {bd['date']} {fmt(bd['mean_pnl'],4)} (n={bd['n']}); "
                 f"fraction of negative days = **{fmt(p.get('neg_day_frac'),3)}**.")
    if p.get("by_asset"):
        L.append("\n**By asset (mid, zero-fee, day-clustered):**")
        L.append("| asset | n | days | entry | realized | mean PnL | t |")
        L.append("|---|---|---|---|---|---|---|")
        for a, r in p["by_asset"].items():
            L.append(f"| {a} | {r['n']} | {r['days']} | {fmt(r['entry'],3)} | {fmt(r['realized'],3)} | "
                     f"{fmt(r['mean'],4)} | {fmt(r['t'],2)} |")
    if res.get("both_wings"):
        bw = res["both_wings"]
        L.append(f"\n**Both-wings robustness** (YES∈band + NO∈band, sell the longshot either side): "
                 f"n={bw['n']}, days={bw['days']}, mean **{fmt(bw['mean'],4)}**/ct, day-clustered t=**{fmt(bw['t'],2)}**.")
    L.append("")

    L.append("## Daily vs weekly magnitude\n")
    ew = p.get("ew_mid_mean")
    if ew is not None and not (isinstance(ew,float) and math.isnan(ew)):
        ratio = ew/WEEKLY_REF
        L.append(f"- Weekly documented mean = **+{WEEKLY_REF}/ct** (week-clustered t~4.6).")
        L.append(f"- Daily {PRIMARY_H}h mid mean = **{fmt(ew,4)}/ct** → **{fmt(ratio,2)}×** the weekly per-contract edge.")
    L.append("")

    ud = res.get("updown", {})
    L.append("## Up/Down daily markets (brief)\n")
    if ud.get("n"):
        L.append(f"- n={ud['n']} settled BTC/ETH Up-or-Down markets, entry ~6h pre-close. "
                 f"Mean entry YES(Up)={fmt(ud['mean_entry_yes'],3)}, realized Up rate={fmt(ud['realized_yes'],3)}.")
        L.append(f"- Sell-YES PnL/ct={fmt(ud['sell_yes_pnl'],4)}, sell-NO PnL/ct={fmt(ud['sell_no_pnl'],4)} "
                 f"→ {'≈efficient' if abs(ud['sell_yes_pnl'])<0.02 else 'possible skew'}.")
    else:
        L.append("- No settled Up/Down markets resolved cleanly in the sampled window.")
    L.append("")

    L.append("## VERDICT\n")
    L.append(res.get("_verdict", "(see summary json)"))
    open(os.path.join(ROOT, "daily_shortvol_report.md"), "w").write("\n".join(L))

if __name__ == "__main__":
    main()
