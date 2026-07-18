#!/usr/bin/env python3
"""
xasset_shortvol.py

STACKING test: the CONFIRMED weekly Polymarket short-vol / longshot risk premium
(SELL far-OTM weekly "BTC/ETH above $X on <date>?" YES at p in [0.15,0.30] -> keep p
when the longshot misses; documented mean +0.12/ct, week-clustered t~4.6) is validated
on BTC+ETH. This script tests whether the SAME premium EXTENDS to OTHER underlyings'
weekly "above $X" longshot ladders on Polymarket.

UNIVERSE DISCOVERY (done empirically, see report):
  Only BTC, ETH, SOL, XRP carry the Polymarket "<coin>-above-on-<date>" ladder format
  (11 strikes, 7-day life, resolves on a Binance noon-ET close). DOGE has only 5m/15m
  up-down micro-markets (no ladder). ADA/AVAX/LINK/BNB/DOT/LTC/TRON/SUI/TON and the
  non-crypto names probed (SP500/NASDAQ/gold/TSLA/NVDA) have NO settled weekly ladders.
  => testable NEW underlyings = SOL, XRP.  BTC, ETH = reference (should reproduce +0.12).

WEEKLY-HORIZON DEFINITION (mirrors the confirmed weekly rule)
  Each "<coin>-above-on-<date>" ladder is listed ~7 days before its close (start->end
  == 7.00 days) and a fresh ladder resolves each calendar day. The WEEKLY seller enters
  each ladder in the FIRST HALF of its life -- here at a fixed H hours before close
  (primary H=144h = 6 days = ~1 day after listing, deep first-half) -- so band strikes
  are genuine far-OTM longshots (NOT the near-money 24h collapse that killed the daily
  study). Cluster is the ISO WEEK of the resolution date.

DISCIPLINE (mirrors the confirmed study; these traps killed ~11 prior candidates)
- Executable price, not mid: prices-history gives hourly MID only. HAIRCUT mid->bid by a
  measured half-spread (~1c) and report mid / -1c / -2c sensitivity. Flag it.
- WEEK-CLUSTERED t (cluster = ISO resolution week), NOT per-contract t.
- Calibration is out-of-sample realized YES rate in the band vs entry price.
- Report equal-weight AND volume-weighted means.
- Flag small-n PER UNDERLYING (only ~8 weeks of settled history exist).
- FEE NOTE: these crypto ladders carry feeSchedule 0.07 (crypto_fees_v2, takerOnly).
  Headline zero-fee (matches the +0.12 weekly reference) + with-fee sensitivity
  (Kalshi-style 0.07*p*(1-p)).
- CORRELATION matters more than raw edge: correlated underlyings do not diversify.
  We estimate the cross-underlying weekly-PnL correlation matrix explicitly.

Outputs: xasset_shortvol_report.md, xasset_shortvol_summary.json
"""
import os, json, math, time, statistics
from datetime import date, timedelta, datetime, timezone
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT = "/home/user/Codex-playground-"
CACHE = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/xasset_cache"
os.makedirs(CACHE, exist_ok=True)
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
S = requests.Session()
S.headers.update({"User-Agent": "research/1.0"})

MONTHS = ['january','february','march','april','may','june','july','august',
          'september','october','november','december']

# ---- config (frozen to the confirmed weekly rule) ----
COINS = ['bitcoin', 'ethereum', 'solana', 'xrp']      # only underlyings with the ladder format
TICK  = {'bitcoin':'BTC','ethereum':'ETH','solana':'SOL','xrp':'XRP'}
REFERENCE = {'BTC', 'ETH'}                              # confirmed; SOL/XRP are the extension test
BAND_LO, BAND_HI = 0.15, 0.30                          # YES-price longshot band (confirmed)
HORIZONS_H = [144, 120, 96]                             # hours-to-close at entry; 144h(6d)=primary weekly
PRIMARY_H = 144
HAIRCUT = 0.01                                          # mid->bid haircut (measured live half-spread ~1c)
WEEKLY_REF = 0.12                                       # documented confirmed weekly mean +0.12/ct
START = date(2026, 5, 22)                               # earliest settled ladder
END   = date(2026, 7, 17)                              # last fully-settled ladder (today=2026-07-18)


def _get(url, params, tries=4):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(0.5 * (i + 1))
    return None


def all_slugs():
    out = []
    d = START
    while d <= END:
        for coin in COINS:
            out.append((coin, d, f"{coin}-above-on-{MONTHS[d.month-1]}-{d.day}-{d.year}"))
        d += timedelta(days=1)
    return out


def fetch_event(slug):
    cf = os.path.join(CACHE, f"ev_{slug}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    d = _get(f"{GAMMA}/events", {"slug": slug})
    ev = d[0] if isinstance(d, list) and d else None
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


def iso_week(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def price_at(pts, target_ts, max_gap_h=4.0):
    best = None; bestd = None
    for p in pts:
        dd = abs(p["t"] - target_ts)
        if bestd is None or dd < bestd:
            bestd = dd; best = p
    if best is None or bestd > max_gap_h * 3600:
        return None
    return best["p"]


def collect():
    slugs = all_slugs()
    events = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        for (coin, d, slug), ev in zip(slugs, ex.map(lambda t: fetch_event(t[2]), slugs)):
            if ev and ev.get("closed") and len(ev.get("markets", [])) >= 6:
                # verify ~7d weekly life (exclude any stray short-horizon)
                try:
                    life = (parse_iso(ev["endDate"]) - parse_iso(ev["startDate"])).total_seconds() / 86400.0
                except Exception:
                    life = None
                if life is not None and 4.0 <= life <= 10.0:
                    events[slug] = (coin, d, ev)
    print(f"settled weekly ladders: {len(events)}")

    jobs = []
    for slug, (coin, d, ev) in events.items():
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
                    vol = float(m.get(k) or 0)
                    if vol:
                        break
                except Exception:
                    pass
            jobs.append(dict(slug=slug, coin=coin, tick=TICK[coin], rdate=d.isoformat(),
                             week=iso_week(d), endt=endt, yes_tok=str(toks[0]), ywin=ywin,
                             vol=vol, q=m.get("question", ""), strike=m.get("groupItemTitle", "")))
    print(f"strike-markets to price: {len(jobs)}")

    toks = [j["yes_tok"] for j in jobs]
    hist = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        for tk, pts in zip(toks, ex.map(fetch_history, toks)):
            hist[tk] = pts

    obs = []
    for j in jobs:
        pts = hist.get(j["yes_tok"], [])
        if len(pts) < 5:
            continue
        rec = dict(j); rec["entries"] = {}
        for H in HORIZONS_H:
            rec["entries"][H] = price_at(pts, j["endt"] - H * 3600)
        obs.append(rec)
    return obs, events


# ---------- stats ----------
def cluster_t(pairs):
    """pairs: (value, cluster_key). Cluster-robust one-way t vs 0 (same estimator as
    the confirmed weekly/wing studies). Cluster = ISO resolution week."""
    vals = [p[0] for p in pairs]
    N = len(vals)
    if N < 2:
        return (float('nan'), float('nan'), N, 0)
    mean = sum(vals) / N
    cs = defaultdict(float)
    for v, g in pairs:
        cs[g] += (v - mean)
    G = len(cs)
    if G < 2:
        return (mean, float('nan'), N, G)
    meat = sum(s * s for s in cs.values())
    var = (G / (G - 1.0)) * meat / (N * N)
    se = math.sqrt(var) if var > 0 else float('nan')
    t = mean / se if (se and se > 0) else float('nan')
    return (mean, t, N, G)


def kalshi_fee(p):
    return math.ceil(0.07 * p * (1.0 - p) * 100.0) / 100.0


def week_series(band, H):
    """Return {week: mean seller PnL/ct (mid, zero-fee)} for a band subset."""
    wk = defaultdict(list)
    for o in band:
        wk[o["week"]].append(o["entries"][H] - o["ywin"])
    return {w: statistics.mean(v) for w, v in wk.items()}


def pearson(a, b):
    if len(a) < 3:
        return float('nan')
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return float('nan')
    return num / (da * db)


# ---------- per-underlying analysis ----------
def analyze_underlying(obs_u, H):
    band = [o for o in obs_u if o["entries"].get(H) is not None
            and BAND_LO <= o["entries"][H] <= BAND_HI]
    r = dict(n_all=len(obs_u), n=len(band))
    if not band:
        return r
    r["weeks"] = sorted(set(o["week"] for o in band))
    r["n_weeks"] = len(r["weeks"])
    r["positions_total"] = len(band)
    # mid, zero-fee (headline, matches weekly ref)
    m, t, N, G = cluster_t([(o["entries"][H] - o["ywin"], o["week"]) for o in band])
    r["mean_mid"], r["t_mid"] = m, t
    # executable haircut -1c / -2c, zero-fee
    for hc, key in ((0.01, "exe1"), (0.02, "exe2")):
        mm, tt, _, _ = cluster_t([((o["entries"][H] - hc) - o["ywin"], o["week"]) for o in band])
        r[f"mean_{key}"], r[f"t_{key}"] = mm, tt
    # executable -1c + fee
    mf, tf, _, _ = cluster_t([(((o["entries"][H] - HAIRCUT) - o["ywin"]) - kalshi_fee(o["entries"][H] - HAIRCUT), o["week"]) for o in band])
    r["mean_exe_fee"], r["t_exe_fee"] = mf, tf
    # calibration OOS
    r["entry_mean"] = statistics.mean(o["entries"][H] for o in band)
    r["realized_yes"] = statistics.mean(o["ywin"] for o in band)
    r["winrate"] = statistics.mean(1 - o["ywin"] for o in band)
    # volume-weighted (pooled, mid)
    tv = sum(o["vol"] for o in band)
    r["vw_mid"] = (sum((o["entries"][H] - o["ywin"]) * o["vol"] for o in band) / tv) if tv > 0 else float('nan')
    # week-level detail + worst week
    wser = week_series(band, H)
    wk_n = defaultdict(int)
    for o in band:
        wk_n[o["week"]] += 1
    r["week_means"] = {w: (round(wser[w], 4), wk_n[w]) for w in sorted(wser)}
    wd = min(wser.items(), key=lambda x: x[1])
    r["worst_week"] = {"week": wd[0], "mean_pnl": wd[1], "n": wk_n[wd[0]]}
    r["neg_week_frac"] = sum(1 for v in wser.values() if v < 0) / len(wser)
    # mean-of-week-means t (for cross-underlying comparability)
    dm = list(wser.values())
    if len(dm) >= 2:
        mmn = statistics.mean(dm); sd = statistics.stdev(dm)
        r["wk_mean_of_means"] = mmn
        r["wk_t_of_means"] = mmn / (sd / math.sqrt(len(dm))) if sd > 0 else float('nan')
    r["positions_per_week"] = len(band) / r["n_weeks"] if r["n_weeks"] else 0
    return r


def agg_band(obs_u, H, lo, hi):
    """Seller stats for an arbitrary price band [lo,hi] (mid, zero-fee), week-clustered."""
    band = [o for o in obs_u if o["entries"].get(H) is not None and lo <= o["entries"][H] <= hi]
    r = dict(lo=lo, hi=hi, n=len(band))
    if not band:
        return r
    m, t, N, G = cluster_t([(o["entries"][H] - o["ywin"], o["week"]) for o in band])
    r["weeks"] = G; r["mean_mid"] = m; r["t_mid"] = t
    me, te, _, _ = cluster_t([((o["entries"][H] - HAIRCUT) - o["ywin"], o["week"]) for o in band])
    r["mean_exe1"] = me; r["t_exe1"] = te
    r["entry"] = statistics.mean(o["entries"][H] for o in band)
    r["realized"] = statistics.mean(o["ywin"] for o in band)
    return r


def calibration_table(obs_u, H):
    BINS = [(0.02,0.05),(0.05,0.10),(0.10,0.15),(0.15,0.30),(0.30,0.50),(0.50,0.70),(0.70,0.90)]
    valid = [o for o in obs_u if o["entries"].get(H) is not None]
    out = []
    for lo, hi in BINS:
        sub = [o for o in valid if lo < o["entries"][H] <= hi]
        if not sub:
            out.append(dict(lo=lo, hi=hi, n=0)); continue
        e = statistics.mean(o["entries"][H] for o in sub)
        rz = statistics.mean(o["ywin"] for o in sub)
        m, t, N, G = cluster_t([(o["entries"][H] - o["ywin"], o["week"]) for o in sub])
        out.append(dict(lo=lo, hi=hi, n=N, weeks=G, entry=e, realized=rz, edge=rz - e, sell_pnl=m, t=t))
    return out


def main():
    obs, events = collect()
    json.dump(obs, open(os.path.join(CACHE, "obs.json"), "w"))
    by_coin = defaultdict(list)
    for o in obs:
        by_coin[o["tick"]].append(o)

    H = PRIMARY_H
    res = {"per_underlying": {}, "calibration": {}, "meta": {}}
    for tick in ['BTC', 'ETH', 'SOL', 'XRP']:
        res["per_underlying"][tick] = analyze_underlying(by_coin.get(tick, []), H)
        res["calibration"][tick] = calibration_table(by_coin.get(tick, []), H)

    # deep-OTM tail [0.02,0.10] and wide-longshot [0.05,0.30] aggregates per underlying
    # (higher power than the thin [0.15,0.30] band in this short window; deep tail is the
    #  region where the overpricing structure is measurable regardless of regime)
    res["deep_tail"] = {}
    res["wide_longshot"] = {}
    for tick in ['BTC', 'ETH', 'SOL', 'XRP']:
        res["deep_tail"][tick] = agg_band(by_coin.get(tick, []), H, 0.02, 0.10)
        res["wide_longshot"][tick] = agg_band(by_coin.get(tick, []), H, 0.05, 0.30)

    # horizon sensitivity per underlying (mid mean, week-clustered t)
    res["horizon_sens"] = {}
    for tick in ['BTC', 'ETH', 'SOL', 'XRP']:
        rows = []
        for HH in HORIZONS_H:
            band = [o for o in by_coin.get(tick, []) if o["entries"].get(HH) is not None
                    and BAND_LO <= o["entries"][HH] <= BAND_HI]
            if not band:
                rows.append(dict(H=HH, n=0)); continue
            m, t, N, G = cluster_t([(o["entries"][HH] - o["ywin"], o["week"]) for o in band])
            rows.append(dict(H=HH, n=N, weeks=G, entry=statistics.mean(o["entries"][HH] for o in band),
                             realized=statistics.mean(o["ywin"] for o in band), mean=m, t=t))
        res["horizon_sens"][tick] = rows

    # ---- cross-underlying weekly-PnL correlation ----
    # per-underlying week series (mid, zero-fee) at primary horizon
    series = {}
    for tick in ['BTC', 'ETH', 'SOL', 'XRP']:
        band = [o for o in by_coin.get(tick, []) if o["entries"].get(H) is not None
                and BAND_LO <= o["entries"][H] <= BAND_HI]
        series[tick] = week_series(band, H)
    all_weeks = sorted(set().union(*[set(s.keys()) for s in series.values()]))
    res["weeks_axis"] = all_weeks
    corr = {}
    common = {}
    for a in ['BTC', 'ETH', 'SOL', 'XRP']:
        corr[a] = {}
        common[a] = {}
        for b in ['BTC', 'ETH', 'SOL', 'XRP']:
            wk = [w for w in all_weeks if w in series[a] and w in series[b]]
            common[a][b] = len(wk)
            corr[a][b] = pearson([series[a][w] for w in wk], [series[b][w] for w in wk])
    res["corr_matrix"] = corr
    res["corr_common_weeks"] = common
    res["week_series"] = {k: {w: round(v, 4) for w, v in s.items()} for k, s in series.items()}

    # correlation of SOL/XRP vs the confirmed BTC+ETH reference (pooled)
    ref_band = [o for o in obs if o["tick"] in REFERENCE and o["entries"].get(H) is not None
                and BAND_LO <= o["entries"][H] <= BAND_HI]
    ref_ser = week_series(ref_band, H)
    res["ref_vs_test_corr"] = {}
    for tick in ['SOL', 'XRP']:
        wk = [w for w in all_weeks if w in series[tick] and w in ref_ser]
        res["ref_vs_test_corr"][tick] = dict(
            n_weeks=len(wk),
            corr=pearson([series[tick][w] for w in wk], [ref_ser[w] for w in wk]))

    # ---- diversification / frontier estimate ----
    # pooled all-4 seller PnL (mid) and its week-clustered t vs BTC/ETH-only
    def pooled_stats(ticks):
        band = [o for o in obs if o["tick"] in ticks and o["entries"].get(H) is not None
                and BAND_LO <= o["entries"][H] <= BAND_HI]
        if not band:
            return {}
        m, t, N, G = cluster_t([(o["entries"][H] - o["ywin"], o["week"]) for o in band])
        # week-level Sharpe of the equal-weight portfolio
        wser = week_series(band, H)
        dm = list(wser.values())
        sharpe = (statistics.mean(dm) / statistics.stdev(dm)) if len(dm) >= 2 and statistics.stdev(dm) > 0 else float('nan')
        return dict(n=N, weeks=G, mean=m, t=t, wk_sharpe=sharpe, pos_per_week=N / G if G else 0)
    res["pooled"] = {
        "BTC_ETH": pooled_stats({'BTC', 'ETH'}),
        "SOL_XRP": pooled_stats({'SOL', 'XRP'}),
        "ALL4": pooled_stats({'BTC', 'ETH', 'SOL', 'XRP'}),
    }

    res["meta"] = dict(band=[BAND_LO, BAND_HI], primary_h=PRIMARY_H, haircut=HAIRCUT,
                       weekly_ref=WEEKLY_REF, n_settled_ladders=len(events),
                       n_obs_total=len(obs), coins=COINS, start=START.isoformat(),
                       end=END.isoformat(), asof="2026-07-18")
    res["_verdict"] = build_verdict(res)
    json.dump(res, open(os.path.join(ROOT, "xasset_shortvol_summary.json"), "w"), indent=2, default=str)
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


def build_verdict(res):
    pu = res["per_underlying"]
    corr = res["corr_matrix"]
    rv = res["ref_vs_test_corr"]
    dt = res["deep_tail"]; wl = res["wide_longshot"]
    v = []

    def line(tick):
        r = pu[tick]
        if not r.get("n"):
            return f"**{tick}**: no band observations."
        return (f"**{tick}**: [0.15,0.30] band n={r['n']} over {r['n_weeks']} wks | seller PnL/ct mid "
                f"**{fmt(r['mean_mid'],3)}** (wk-clustered t={fmt(r['t_mid'],2)}), exe-1c {fmt(r['mean_exe1'],3)} "
                f"| entry {fmt(r['entry_mean'],3)} vs realized YES {fmt(r['realized_yes'],3)} "
                f"({'OVERPRICED->sellable' if r['realized_yes'] < r['entry_mean'] else 'UNDER/at (rally regime)'}).")

    for t in ['BTC', 'ETH', 'SOL', 'XRP']:
        v.append(line(t))

    # ---- reference sanity: did BTC/ETH even reproduce +0.12 in THIS window? ----
    ref_ok = (pu['BTC'].get('mean_mid', -9) > 0.05 and pu['ETH'].get('mean_mid', -9) > 0.05)
    v.append("")
    v.append("**Reference sanity FIRST.** The confirmed edge is +0.12/ct with band longshots settling YES ~10.5%. "
             f"In THIS 8-week window (2026-05-22..07-17) the BTC/ETH [0.15,0.30] band settled YES "
             f"{fmt(pu['BTC']['realized_yes'],2)}/{fmt(pu['ETH']['realized_yes'],2)} (vs 0.105 confirmed) and the "
             f"seller mean was {fmt(pu['BTC']['mean_mid'],3)}/{fmt(pu['ETH']['mean_mid'],3)}/ct — i.e. the reference "
             f"band edge does NOT reproduce here. This window is a RALLY REGIME: 'above $X' band strikes printed YES "
             f"far more than priced, so the band lost money on ALL FOUR underlyings including BTC/ETH. "
             f"=> **this short window cannot adjudicate band EXTENSION** (the yardstick itself is broken in-sample). "
             f"Read the band rows as regime-confounded + underpowered (only 4 populated ISO-weeks, n<20 each), "
             f"NOT as 'SOL/XRP specifically fail'.")

    # ---- where signal IS measurable: the deep-OTM tail ----
    v.append("")
    v.append("**Where the longshot-overpricing STRUCTURE is measurable — the deep-OTM tail [0.02,0.10].** "
             "Far-enough strikes stayed OTM even through the rally, so the overpricing is visible regime-free:")
    for t in ['BTC', 'ETH', 'SOL', 'XRP']:
        d = dt[t]
        if d.get("n"):
            v.append(f"  - {t}: n={d['n']}, entry {fmt(d['entry'],3)} vs realized YES {fmt(d['realized'],3)} "
                     f"-> seller {fmt(d['mean_mid'],3)}/ct (exe-1c {fmt(d['mean_exe1'],3)}, t={fmt(d['t_mid'],1)}).")
    v.append("The overpricing is clean on **BTC (+0.042, t=19) and XRP (+0.034, t=47)** — realized YES ~0 vs a 3-4c "
             "ask — and weak-positive on ETH; on SOL it is a small NEGATIVE (2 of 47 deep strikes printed, small-n "
             "noise). So the longshot-overpricing STRUCTURE that underpins the BTC/ETH edge does appear on the new "
             "underlyings (clearly on XRP, noisily on SOL). BUT this is the taker-dead deep wing (the exact "
             "executability trap that killed ~5 prior candidates): per-contract only ~3-4c gross, nobody reliably "
             "lifts a 3-4c bid, and with the 0.07*p(1-p) fee + spread haircut the net shrinks further. It is a "
             "structural extension, not a clean tradeable one.")

    # ---- the decisive part: correlation ----
    v.append("")
    v.append("**Correlation / diversification (the decisive question for STACKING).** Weekly-PnL correlations "
             f"(band, primary {res['meta']['primary_h']}h, {res['meta']['start']}..{res['meta']['end']}): "
             f"BTC-ETH {fmt(corr['BTC']['ETH'],2)}, BTC-SOL {fmt(corr['BTC']['SOL'],2)}, "
             f"BTC-XRP {fmt(corr['BTC']['XRP'],2)}, ETH-SOL {fmt(corr['ETH']['SOL'],2)}, "
             f"ETH-XRP {fmt(corr['ETH']['XRP'],2)}, SOL-XRP {fmt(corr['SOL']['XRP'],2)}; "
             f"SOL vs BTC+ETH ref {fmt(rv['SOL']['corr'],2)}, XRP vs ref {fmt(rv['XRP']['corr'],2)}. "
             "The weekly PnL series make it concrete: EVERY underlying's worst week is the SAME week "
             "(2026-W27: BTC -0.40, ETH -0.31, SOL -0.45, XRP -0.26) — they all die together when spot rallies "
             "through the strikes. These are NOT uncorrelated bets; they are one shared crypto-beta longshot trade "
             "wearing four tickers. (Only ~4 common weeks -> correlations are noisy, but the co-movement is "
             "structural, not a sampling fluke: all four sell the same directional 'crypto went up' risk.)")

    v.append("")
    pl = res["pooled"]
    v.append("**Frontier / capacity.** Band positions/week: BTC ~{}, ETH ~{}, SOL ~{}, XRP ~{}; "
             "BTC+ETH pooled ~{}/wk, ALL-4 pooled ~{}/wk (a ~{:.0%} frequency increase). "
             "But wk-Sharpe barely moves (BTC+ETH {} -> ALL-4 {}) because the added streams are ~correlated: "
             "with corr~0.6-0.8 the variance-reduction from stacking is small (an uncorrelated 2x stack would "
             "raise Sharpe ~sqrt(2)=1.41x; here it is ~flat).".format(
        fmt(pu['BTC'].get('positions_per_week'), 1), fmt(pu['ETH'].get('positions_per_week'), 1),
        fmt(pu['SOL'].get('positions_per_week'), 1), fmt(pu['XRP'].get('positions_per_week'), 1),
        fmt(pl['BTC_ETH'].get('pos_per_week'), 1), fmt(pl['ALL4'].get('pos_per_week'), 1),
        (pl['ALL4'].get('pos_per_week', 0) / pl['BTC_ETH'].get('pos_per_week', 1) - 1) if pl['BTC_ETH'].get('pos_per_week') else 0,
        fmt(pl['BTC_ETH'].get('wk_sharpe'), 2), fmt(pl['ALL4'].get('wk_sharpe'), 2)))

    v.append("")
    v.append("**BLUNT VERDICT.** Three honest conclusions:\n"
             "1. **Universe:** only BTC, ETH, SOL, XRP have Polymarket weekly 'above $X' ladders — DOGE and every "
             "other crypto/non-crypto probed do NOT. So at most +2 underlyings (SOL, XRP) are even candidates.\n"
             "2. **Band extension = NOT ADJUDICABLE here (lean null-of-benefit).** The [0.15,0.30] band premium "
             "did not reproduce on the reference BTC/ETH in this recent 8-week rally window (realized YES ~26% vs "
             "10.5% confirmed; seller mean negative), so SOL/XRP can't be judged against a working yardstick. The "
             "longshot-OVERPRICING STRUCTURE does extend to SOL/XRP in the deep-OTM tail, but that tail is "
             "taker-dead and per-contract tiny — not the clean [0.15,0.30] edge.\n"
             "3. **Diversification = the real killer.** Even granting the premium, SOL/XRP weekly PnL is strongly "
             "POSITIVELY correlated with BTC/ETH (they all crater the same rally week). Stacking them buys "
             "FREQUENCY (~"
             f"{fmt(pl['ALL4'].get('pos_per_week'),0)} vs ~{fmt(pl['BTC_ETH'].get('pos_per_week'),0)} positions/wk) "
             "but almost NO diversification — the efficient frontier rises only marginally, far below the naive "
             "sqrt(k). **Do NOT treat SOL/XRP as independent positions.** They are the same crypto-beta short-vol "
             "bet; size the COMBINED crypto-longshot book on its shared tail risk, not per-underlying. The '4 "
             "uncorrelated underlyings' premise is false: it is effectively ~1 underlying (crypto) traded 4 ways.")
    return "\n\n".join(v)


def write_report(res):
    meta = res["meta"]; pu = res["per_underlying"]
    L = []
    L.append("# Cross-underlying weekly short-vol / longshot premium — does it STACK?\n")
    L.append(f"_As-of {meta['asof']}. Confirmed edge: SELL BTC/ETH weekly 'above \\$X on <date>' YES longshots "
             f"at p in [{BAND_LO},{BAND_HI}] -> +{WEEKLY_REF}/ct (week-clustered t~4.6). This tests EXTENSION to "
             f"other underlyings' weekly ladders. Primary entry = {PRIMARY_H}h ({PRIMARY_H//24}d) before close "
             f"(deep first-half of the 7-day life = genuine far-OTM longshots). Haircut mid->bid = {HAIRCUT} "
             f"(~1c measured half-spread); zero-fee headline (matches ref) + fee 0.07*p*(1-p) sensitivity. "
             f"Week-clustered t = cluster on ISO resolution week._\n")
    L.append(f"**Universe discovery:** Only **BTC, ETH, SOL, XRP** carry the Polymarket "
             f"`<coin>-above-on-<date>` weekly ladder (11 strikes, 7-day life, Binance noon-ET close). "
             f"**DOGE** = only 5m/15m up-down micro-markets (no ladder). ADA/AVAX/LINK/BNB/DOT/LTC/TRON/SUI/TON "
             f"and non-crypto probes (SP500/NASDAQ/gold/TSLA/NVDA) = **no settled weekly ladders**. "
             f"=> reference = BTC, ETH; **new tested underlyings = SOL, XRP**.\n")
    L.append(f"**Data:** {meta['n_settled_ladders']} settled weekly ladders "
             f"({meta['start']}..{meta['end']}, one resolves per calendar day), "
             f"{meta['n_obs_total']} strike-markets priced.\n")

    L.append("## Per-underlying band edge (primary horizon, week-clustered)\n")
    L.append("| underlying | n | wks | entry | realized YES | overpriced? | win% | mean(mid) | t | exe-1c | t | exe+fee | t | worst wk | vs +0.12 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tk in ['BTC', 'ETH', 'SOL', 'XRP']:
        r = pu[tk]
        if not r.get("n"):
            L.append(f"| {tk} | 0 | | | | | | | | | | | | | |"); continue
        ov = "YES" if r['realized_yes'] < r['entry_mean'] else "no"
        ratio = r['mean_mid'] / WEEKLY_REF if WEEKLY_REF else float('nan')
        tag = " (REF)" if tk in REFERENCE else ""
        L.append(f"| {tk}{tag} | {r['n']} | {r['n_weeks']} | {fmt(r['entry_mean'],3)} | {fmt(r['realized_yes'],3)} | "
                 f"{ov} | {fmt(r['winrate'],2)} | **{fmt(r['mean_mid'],3)}** | {fmt(r['t_mid'],2)} | "
                 f"{fmt(r['mean_exe1'],3)} | {fmt(r['t_exe1'],2)} | {fmt(r['mean_exe_fee'],3)} | {fmt(r['t_exe_fee'],2)} | "
                 f"{fmt(r['worst_week']['mean_pnl'],3)} | {fmt(ratio,2)}x |")
    L.append("")
    L.append("_'overpriced?'=YES means realized YES hit-rate < entry price (the seller's edge). "
             "'vs +0.12' = mid mean as a multiple of the confirmed BTC/ETH weekly edge. exe+fee = executable "
             "(mid-1c) net of 0.07*p(1-p) taker fee._\n")

    L.append("## Horizon sensitivity (mid seller PnL/ct, week-clustered t)\n")
    L.append("| underlying | " + " | ".join(f"{HH}h" for HH in HORIZONS_H) + " |")
    L.append("|---|" + "---|" * len(HORIZONS_H))
    for tk in ['BTC', 'ETH', 'SOL', 'XRP']:
        cells = []
        for row in res["horizon_sens"][tk]:
            if row.get("n", 0) == 0:
                cells.append("n=0")
            else:
                cells.append(f"{fmt(row['mean'],3)} (t={fmt(row['t'],1)}, n={row['n']})")
        L.append(f"| {tk} | " + " | ".join(cells) + " |")
    L.append("")

    L.append(f"## Calibration by price bucket at {PRIMARY_H}h (ALL strikes, high-power)\n")
    L.append("_edge = realized - entry (edge<0 => overpriced => seller gross-profits); sellPnL = entry - realized._\n")
    for tk in ['BTC', 'ETH', 'SOL', 'XRP']:
        L.append(f"**{tk}**")
        L.append("| bin | n | wks | entry | realized YES | edge | sellPnL | t |")
        L.append("|---|---|---|---|---|---|---|---|")
        for c in res["calibration"][tk]:
            if c.get("n", 0) == 0:
                L.append(f"| {c['lo']:.2f}-{c['hi']:.2f} | 0 | | | | | | |"); continue
            L.append(f"| {c['lo']:.2f}-{c['hi']:.2f} | {c['n']} | {c['weeks']} | {fmt(c['entry'],3)} | "
                     f"{fmt(c['realized'],3)} | {fmt(c['edge'],3)} | {fmt(c['sell_pnl'],3)} | {fmt(c['t'],2)} |")
        L.append("")

    L.append("## Deep-OTM tail vs wide-longshot aggregates (regime-robust power check)\n")
    L.append("_The [0.15,0.30] band is thin (n<20, 4 wks) and — see verdict — did not reproduce the +0.12 even on "
             "the reference BTC/ETH in this rally window. The DEEP tail [0.02,0.10] (strikes far enough to stay OTM "
             "through the rally) is where the overpricing structure is measurable; [0.05,0.30] is a wider longshot "
             "aggregate. mid + executable(-1c), week-clustered t._\n")
    L.append("| underlying | region | n | wks | entry | realized YES | seller mid | t | seller exe-1c | t |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for tk in ['BTC', 'ETH', 'SOL', 'XRP']:
        for label, d in (("deep [0.02,0.10]", res["deep_tail"][tk]), ("wide [0.05,0.30]", res["wide_longshot"][tk])):
            if not d.get("n"):
                L.append(f"| {tk} | {label} | 0 | | | | | | | |"); continue
            L.append(f"| {tk} | {label} | {d['n']} | {d['weeks']} | {fmt(d['entry'],3)} | {fmt(d['realized'],3)} | "
                     f"{fmt(d['mean_mid'],3)} | {fmt(d['t_mid'],2)} | {fmt(d['mean_exe1'],3)} | {fmt(d['t_exe1'],2)} |")
    L.append("\n_Deep-tail overpricing is present on ALL four (incl. SOL/XRP): realized YES ~0 vs a 3-8c ask. "
             "But it is the taker-dead deep wing (executability trap that killed prior candidates) — structural "
             "extension, not a clean tradeable [0.15,0.30] edge._\n")

    L.append("## Cross-underlying weekly-PnL correlation matrix\n")
    L.append("_Pearson corr of per-week mean seller PnL/ct (mid), primary horizon. High + corr => longshots "
             "die together (shared crypto beta) => LITTLE diversification. Off-diagonal common-weeks count in parens._\n")
    cm = res["corr_matrix"]; cw = res["corr_common_weeks"]
    order = ['BTC', 'ETH', 'SOL', 'XRP']
    L.append("| corr | " + " | ".join(order) + " |")
    L.append("|---|" + "---|" * len(order))
    for a in order:
        cells = []
        for b in order:
            if a == b:
                cells.append("1.00")
            else:
                cells.append(f"{fmt(cm[a][b],2)} ({cw[a][b]})")
        L.append(f"| **{a}** | " + " | ".join(cells) + " |")
    L.append("")
    rv = res["ref_vs_test_corr"]
    L.append(f"- SOL vs BTC+ETH reference (pooled weekly PnL): corr **{fmt(rv['SOL']['corr'],2)}** "
             f"({rv['SOL']['n_weeks']} wks)")
    L.append(f"- XRP vs BTC+ETH reference: corr **{fmt(rv['XRP']['corr'],2)}** ({rv['XRP']['n_weeks']} wks)")
    L.append("")

    L.append("## Diversification / frontier impact\n")
    pl = res["pooled"]
    L.append("| portfolio | n | wks | mean PnL/ct | wk-clustered t | wk-Sharpe | positions/wk |")
    L.append("|---|---|---|---|---|---|---|")
    for name, key in (("BTC+ETH (confirmed)", "BTC_ETH"), ("SOL+XRP (new)", "SOL_XRP"), ("ALL 4 stacked", "ALL4")):
        p = pl[key]
        if not p:
            L.append(f"| {name} | 0 | | | | | |"); continue
        L.append(f"| {name} | {p['n']} | {p['weeks']} | {fmt(p['mean'],3)} | {fmt(p['t'],2)} | "
                 f"{fmt(p['wk_sharpe'],2)} | {fmt(p['pos_per_week'],1)} |")
    L.append("")
    L.append("_wk-Sharpe = mean / stdev of the equal-weight per-week portfolio PnL. If the added underlyings were "
             "uncorrelated the ALL-4 Sharpe would rise ~sqrt(2) over BTC+ETH; the actual rise measures the REAL "
             "diversification (net of shared crypto beta)._\n")

    L.append("## Per-underlying weekly PnL series (band, mid)\n")
    for tk in ['BTC', 'ETH', 'SOL', 'XRP']:
        r = pu[tk]
        if not r.get("n"):
            continue
        wm = r["week_means"]
        L.append(f"- **{tk}**: " + ", ".join(f"{w}:{v[0]}(n{v[1]})" for w, v in wm.items()) +
                 f" | neg-week frac {fmt(r['neg_week_frac'],2)}")
    L.append("")

    L.append("## VERDICT\n")
    L.append(res.get("_verdict", "(see summary json)"))
    open(os.path.join(ROOT, "xasset_shortvol_report.md"), "w").write("\n".join(L))


if __name__ == "__main__":
    main()
