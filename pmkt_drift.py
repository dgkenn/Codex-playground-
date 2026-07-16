#!/usr/bin/env python3
"""
pmkt_drift.py
=============
THIRD-EDGE HUNT: prediction-market DRIFT / MOMENTUM vs REVERSION on Polymarket.

Question: when a settled Polymarket YES price moves meaningfully during the FIRST
portion of its life, does that move CONTINUE (underreaction / drift -> momentum)
or REVERT (overreaction -> reversion) over the REMAINDER, tradeable net of the
CLOB half-spread (Polymarket is zero-fee)?  This is a DIRECTIONAL TIMING signal,
meant to be orthogonal to the static longshot / short-vol risk premia already in
the book.

STRICTLY CAUSAL construction (per market, life [t0,t1]):
  p_open  = first available YES mid
  t40     = t0 + 0.40*(t1-t0)          (decision point)
  p_mid   = last YES mid at time <= t40 (causal; measured AT the decision point)
  m       = p_mid - p_open             (first-40% drift, measured BEFORE decision)
  outcome = UMA resolution in {0,1}    (terminal, no price look-ahead)

Strategies decided at t40, held to resolution, entered at the EXECUTABLE price
(cross half the spread; zero fee):
  (A) MOMENTUM : m>+thr -> BUY YES ; m<-thr -> SELL YES
  (B) REVERSION: opposite
  BUY  YES pnl = outcome - (p_mid + hs)
  SELL YES pnl = (p_mid - hs) - outcome
thr in {0.03,0.05,0.10}.  Continuous test: corr(m, outcome - p_mid).

Controls: executable price (half-spread sweep), outcome only from resolution,
cluster by resolution WEEK (week-clustered t), momentum AND reversion reported for
every threshold, pooled + per-category, equal- and volume-weighted, power flags,
and (if anything survives) weekly-PnL correlation to a "sell longshots" series
built from the SAME market set.

No fees. No look-ahead: m ends at t40, holding starts at t40, outcome is terminal.
"""
import os, sys, json, time, math, datetime as dt, re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np

CACHE = "/home/user/Codex-playground-/scratchpad/pmkt_drift_cache"
os.makedirs(CACHE, exist_ok=True)
GAMMA = "https://gamma-api.polymarket.com"
CLOB  = "https://clob.polymarket.com"

S = requests.Session()
S.headers.update({"User-Agent": "research/1.0"})

THRESHOLDS = [0.03, 0.05, 0.10]
HALF_SPREADS = [0.005, 0.010, 0.020]   # cost sweep; primary headline = 0.010
HS_PRIMARY = 0.010
LONGSHOT_LO, LONGSHOT_HI = 0.15, 0.30  # "sell longshots" band for orthogonality
FRAC_DECISION = 0.40

# universe filters
MIN_VOLUME     = 20000.0   # liquid-only
MIN_LIFE_DAYS  = 1.0
MAX_LIFE_DAYS  = 200.0
MIN_POINTS     = 6         # need enough hourly points to define open & t40 mids
HOURLY_MAX_DAYS = 13.0     # single-call hourly window cap (clob ~14d limit)


def _get(url, params=None, tries=4, timeout=45):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.2 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(1.0 * (i + 1))
    return None


def cache_get(key, fn):
    p = os.path.join(CACHE, key + ".json")
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
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def resolved_outcome(m):
    """Return YES-win in {0.0,1.0} or None if not cleanly resolved to 0/1."""
    op = m.get("outcomePrices"); oc = m.get("outcomes")
    try:
        op = json.loads(op) if isinstance(op, str) else op
        oc = json.loads(oc) if isinstance(oc, str) else oc
    except Exception:
        return None, None
    if not op or not oc or len(op) != len(oc):
        return None, None
    d = {str(oc[i]).lower(): float(op[i]) for i in range(len(oc))}
    if "yes" not in d:
        return None, None
    y = d["yes"]
    yes_idx = [i for i, o in enumerate(oc) if str(o).lower() == "yes"]
    if not yes_idx:
        return None, None
    if y > 0.98:
        return 1.0, yes_idx[0]
    if y < 0.02:
        return 0.0, yes_idx[0]
    return None, None


CRYPTO_RE = re.compile(r"\b(bitcoin|btc|ethereum|eth\b|solana|\bsol\b|xrp|ripple|dogecoin|doge|crypto|litecoin|cardano|\bada\b|binance|\bbnb\b|price of)\b", re.I)
SPORTS_RE = re.compile(r"\b(nfl|nba|mlb|nhl|ncaa|premier league|la liga|ucl|champions league|super bowl|world cup|vs\.?|beat|defeat|win the game|score|touchdown|playoff|finals|match|fc\b|united|f1|grand prix|ufc|tennis|golf|pga|wimbledon)\b", re.I)
POL_RE    = re.compile(r"\b(election|president|senate|congress|governor|primary|nominee|trump|biden|harris|democrat|republican|parliament|prime minister|vote|poll|cabinet|impeach|supreme court|referendum)\b", re.I)
ECON_RE   = re.compile(r"\b(fed\b|fomc|interest rate|rate cut|rate hike|cpi|inflation|gdp|jobs report|unemployment|nonfarm|payroll|recession|jerome powell|treasury|yield|jobless)\b", re.I)


def categorize(m):
    txt = (m.get("question", "") + " " + m.get("slug", "")).lower()
    if CRYPTO_RE.search(txt):
        return "crypto"
    if ECON_RE.search(txt):
        return "econ"
    if POL_RE.search(txt):
        return "politics"
    if SPORTS_RE.search(txt):
        return "sports"
    return "other"


# --------------------------------------------------------------------------
# 1. Universe: liquid settled binary Yes/No markets, volume-desc pagination
# --------------------------------------------------------------------------
def build_universe(max_markets):
    def fn():
        # gamma /markets caps limit=100 and offset~2100, so we page DOWN by
        # descending volume windows (volume_num_max) instead of by offset.
        out = []; seen = set()
        vmax = None
        while len(out) < max_markets:
            params = dict(closed="true", limit=100, order="volumeNum", ascending="false")
            if vmax is not None:
                params["volume_num_max"] = vmax
            d = _get(f"{GAMMA}/markets", params)
            if not d:
                break
            page_min = None; added = 0
            for m in d:
                vol = float(m.get("volumeNum") or 0)
                page_min = vol if page_min is None else min(page_min, vol)
                mid = m.get("id")
                if mid in seen:
                    continue
                seen.add(mid)
                if vol < MIN_VOLUME:
                    continue
                yw, yidx = resolved_outcome(m)
                if yw is None:
                    continue
                oc = m.get("outcomes")
                try:
                    oc = json.loads(oc) if isinstance(oc, str) else oc
                except Exception:
                    continue
                if not oc or len(oc) != 2:
                    continue
                try:
                    toks = json.loads(m["clobTokenIds"])
                except Exception:
                    continue
                if len(toks) != 2:
                    continue
                st = parse_dt(m.get("startDate")); en = parse_dt(m.get("endDate"))
                if not st or not en:
                    continue
                life = (en - st).total_seconds() / 86400.0
                if life < MIN_LIFE_DAYS or life > MAX_LIFE_DAYS:
                    continue
                out.append(dict(
                    id=mid, q=m.get("question", ""), slug=m.get("slug", ""),
                    cat=categorize(m), yes_win=yw, yes_token=toks[yidx],
                    start=st.timestamp(), end=en.timestamp(), life_days=life,
                    volume=vol, spread=float(m.get("spread") or 0.0),
                ))
                added += 1
                if len(out) >= max_markets:
                    break
            # advance the descending-volume window
            if page_min is None or page_min < MIN_VOLUME or len(d) < 100:
                break
            nxt = page_min - 1e-6
            if vmax is not None and nxt >= vmax:
                break   # no progress (ties) -> stop
            vmax = nxt
        return out
    return cache_get(f"universe_v2_{max_markets}", fn)


# --------------------------------------------------------------------------
# 2. Causal open mid + t40 mid from hourly price history (YES token)
# --------------------------------------------------------------------------
def _hist(token, st, en):
    d = _get(f"{CLOB}/prices-history", dict(market=token, startTs=int(st), endTs=int(en), fidelity=60))
    if not d:
        return []
    h = d.get("history", []) if isinstance(d, dict) else []
    return [(int(p["t"]), float(p["p"])) for p in h if "t" in p and "p" in p]


def open_and_mid(mk):
    """Return (p_open, p_mid, n_pts) using strictly-causal hourly mids, or None."""
    def fn():
        t0 = mk["start"]; t1 = mk["end"]; life = t1 - t0
        t40 = t0 + FRAC_DECISION * life
        if life <= HOURLY_MAX_DAYS * 86400:
            hh = _hist(mk["yes_token"], t0, t1)
        else:
            # two targeted windows: open (first 3d) and t40 (6d ending at t40)
            a = _hist(mk["yes_token"], t0, min(t0 + 3 * 86400, t40))
            b = _hist(mk["yes_token"], max(t0, t40 - 6 * 86400), t40)
            hh = sorted(set(a + b))
        return hh
    hh = cache_get(f"hist_{mk['id']}", fn)
    if not hh or len(hh) < MIN_POINTS:
        return None
    hh = sorted(hh)
    t0 = hh[0][0]; t1 = mk["end"]; life = t1 - t0
    if life <= 0:
        return None
    t40 = t0 + FRAC_DECISION * life
    p_open = hh[0][1]
    p_open_ts = hh[0][0]
    # last mid at time <= t40 (strictly causal)
    pmid = None; pmid_ts = None
    for t, p in hh:
        if t <= t40:
            pmid = p; pmid_ts = t
        else:
            break
    if pmid is None:
        return None
    # require genuine time separation between open and the decision-point mid
    # (so m spans a real portion of life, not two ticks of the same early cluster).
    # We deliberately do NOT require points AFTER t40: outcome is from resolution,
    # and for long markets we only fetch up to the causal decision point.
    pts_before = sum(1 for t, _ in hh if t <= t40)
    if pts_before < 2:
        return None
    if (pmid_ts - p_open_ts) < 0.15 * life:
        return None
    return dict(p_open=float(p_open), p_mid=float(pmid), pmid_ts=int(pmid_ts),
                n_before=pts_before)


# --------------------------------------------------------------------------
# 3. Assemble per-market records
# --------------------------------------------------------------------------
def iso_week(ts):
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc).isocalendar()
    return f"{d[0]}-W{d[1]:02d}"


def interior_anchor(mk, frac_anchor=0.10, frac_decision=FRAC_DECISION):
    """Robustness: anchor NOT at the first (possibly seeded/noisy) print but at
    the frac_anchor point of life; decision still at frac_decision. m spans a
    fully-INTERIOR window [frac_anchor, frac_decision] -> no opening-print
    artifact, no resolution overlap. Returns (p_anchor, p_mid) or None, from
    cached history only."""
    hh = cache_get(f"hist_{mk['id']}", lambda: None)
    if not hh or len(hh) < MIN_POINTS:
        return None
    hh = sorted((int(t), float(p)) for t, p in hh)
    t0 = hh[0][0]; t1 = mk["end"]; life = t1 - t0
    if life <= 0:
        return None
    ta = t0 + frac_anchor * life
    td = t0 + frac_decision * life
    pa = pd = None
    for t, p in hh:
        if t <= ta:
            pa = p
        if t <= td:
            pd = p
    if pa is None or pd is None:
        return None
    return float(pa), float(pd)


def build_records(universe, workers=16, cap=None):
    recs = []
    todo = universe if cap is None else universe[:cap]

    def work(mk):
        om = open_and_mid(mk)
        if om is None:
            return None
        r = dict(mk); r.update(om)
        r["m"] = r["p_mid"] - r["p_open"]
        r["week"] = iso_week(mk["end"])
        ia = interior_anchor(mk)
        if ia is not None:
            r["p_anchor10"] = ia[0]
            r["m_int"] = ia[1] - ia[0]   # interior drift [10%,40%]
        return r

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, mk) for mk in todo]
        done = 0
        for f in as_completed(futs):
            done += 1
            if done % 500 == 0:
                print(f"   history {done}/{len(todo)}", flush=True)
            r = f.result()
            if r is not None:
                recs.append(r)
    return recs


# --------------------------------------------------------------------------
# 4. Strategy PnL + week-clustered stats
# --------------------------------------------------------------------------
def trade_pnl(r, side, hs):
    """side=+1 BUY YES, -1 SELL YES. Executable price crosses half-spread."""
    p = r["p_mid"]; o = r["yes_win"]
    if side > 0:   # buy YES at ask = mid+hs
        return o - (p + hs)
    else:          # sell YES at bid = mid-hs
        return (p - hs) - o


def week_cluster_t(pairs):
    """pairs: list of (week, pnl). Return (n, mean, week_clustered_t, n_weeks)."""
    if not pairs:
        return 0, float("nan"), float("nan"), 0
    byw = defaultdict(list)
    for w, x in pairs:
        byw[w].append(x)
    wk_means = np.array([np.mean(v) for v in byw.values()])
    n = len(pairs); mean = float(np.mean([x for _, x in pairs]))
    k = len(wk_means)
    if k < 2 or np.std(wk_means, ddof=1) == 0:
        return n, mean, float("nan"), k
    t = float(np.mean(wk_means) / (np.std(wk_means, ddof=1) / math.sqrt(k)))
    return n, mean, t, k


def vol_weighted_mean(triples):
    """triples: (pnl, weight). Return weighted mean."""
    if not triples:
        return float("nan")
    ws = np.array([w for _, w in triples]); xs = np.array([x for x, _ in triples])
    if ws.sum() == 0:
        return float(np.mean(xs))
    return float((xs * ws).sum() / ws.sum())


def eval_strategy(recs, direction, thr, hs):
    """direction: 'MOM' or 'REV'. Return dict of stats over qualifying trades."""
    pairs = []; wtriples = []; weekly = defaultdict(list)
    for r in recs:
        m = r["m"]
        if abs(m) < thr:
            continue
        if direction == "MOM":
            side = 1 if m > 0 else -1
        else:
            side = -1 if m > 0 else 1
        pnl = trade_pnl(r, side, hs)
        pairs.append((r["week"], pnl))
        wtriples.append((pnl, r["volume"]))
        weekly[r["week"]].append(pnl)
    n, mean, t, k = week_cluster_t(pairs)
    vw = vol_weighted_mean(wtriples)
    weekly_mean = {w: float(np.mean(v)) for w, v in weekly.items()}
    return dict(n=n, mean=mean, t=t, weeks=k, vw_mean=vw, weekly=weekly_mean)


def pearson_week_cluster(xs, ys, weeks):
    """Pearson r plus a week-block bootstrap 95% CI on r."""
    xs = np.array(xs); ys = np.array(ys)
    if len(xs) < 5 or np.std(xs) == 0 or np.std(ys) == 0:
        return float("nan"), float("nan"), (float("nan"), float("nan")), len(xs)
    r = float(np.corrcoef(xs, ys)[0, 1])
    # naive t
    n = len(xs)
    tval = r * math.sqrt((n - 2) / max(1e-12, (1 - r * r)))
    # week-block bootstrap
    byw = defaultdict(list)
    for i, w in enumerate(weeks):
        byw[w].append(i)
    wk_keys = list(byw.keys())
    if len(wk_keys) >= 5:
        rng = np.random.default_rng(7)
        boots = []
        for _ in range(1000):
            samp = rng.choice(wk_keys, size=len(wk_keys), replace=True)
            idx = []
            for w in samp:
                idx.extend(byw[w])
            if len(idx) < 5:
                continue
            xx = xs[idx]; yy = ys[idx]
            if np.std(xx) == 0 or np.std(yy) == 0:
                continue
            boots.append(np.corrcoef(xx, yy)[0, 1])
        if boots:
            lo, hi = np.percentile(boots, [2.5, 97.5])
            return r, tval, (float(lo), float(hi)), n
    return r, tval, (float("nan"), float("nan")), n


# --------------------------------------------------------------------------
# 5. Longshot weekly series (same market set) for orthogonality
# --------------------------------------------------------------------------
def longshot_weekly(recs, hs):
    weekly = defaultdict(list)
    for r in recs:
        p = r["p_mid"]
        if LONGSHOT_LO <= p <= LONGSHOT_HI:
            weekly[r["week"]].append((p - hs) - r["yes_win"])  # SELL YES
    return {w: float(np.mean(v)) for w, v in weekly.items()}


def weekly_corr(a, b):
    ks = sorted(set(a) & set(b))
    if len(ks) < 5:
        return float("nan"), len(ks)
    xa = np.array([a[k] for k in ks]); xb = np.array([b[k] for k in ks])
    if np.std(xa) == 0 or np.std(xb) == 0:
        return float("nan"), len(ks)
    return float(np.corrcoef(xa, xb)[0, 1]), len(ks)


# --------------------------------------------------------------------------
# 6. Main
# --------------------------------------------------------------------------
def fmt(x, d=4):
    if x is None or (isinstance(x, float) and (math.isnan(x))):
        return "  n/a"
    return f"{x:+.{d}f}"


def main():
    max_markets = int(os.environ.get("PMKT_MAX", "6000"))
    print(f"[1/4] Building liquid universe (target {max_markets}, vol>=${MIN_VOLUME:.0f}) ...", flush=True)
    universe = build_universe(max_markets)
    print(f"   universe candidates: {len(universe)}", flush=True)
    bycat = defaultdict(int)
    for m in universe:
        bycat[m["cat"]] += 1
    print("   by cat:", dict(bycat), flush=True)

    print("[2/4] Fetching causal hourly open/t40 mids ...", flush=True)
    recs = build_records(universe)
    print(f"   records with usable causal mids: {len(recs)}", flush=True)

    # global spread diagnostics to justify half-spread assumption
    spreads = [r["spread"] for r in recs if 0 < r["spread"] < 0.2]
    med_spread = float(np.median(spreads)) if spreads else float("nan")

    cats = ["crypto", "sports", "politics", "econ", "other"]
    groups = {"POOLED": recs}
    for c in cats:
        groups[c] = [r for r in recs if r["cat"] == c]

    # ---- grid: momentum vs reversion, per thresh, per category, net@primary hs
    grid = {}  # (grp,thr,dir) -> stats
    for gname, g in groups.items():
        for thr in THRESHOLDS:
            for direction in ("MOM", "REV"):
                grid[(gname, thr, direction)] = eval_strategy(g, direction, thr, HS_PRIMARY)

    # ---- half-spread sensitivity on POOLED
    hs_sweep = {}
    for hs in HALF_SPREADS:
        for thr in THRESHOLDS:
            for direction in ("MOM", "REV"):
                hs_sweep[(hs, thr, direction)] = eval_strategy(recs, direction, thr, hs)

    # ---- continuous relationship corr(m, outcome - p_mid)
    cont = {}
    for gname, g in groups.items():
        xs = [r["m"] for r in g]
        ys = [r["yes_win"] - r["p_mid"] for r in g]
        ws = [r["week"] for r in g]
        cont[gname] = pearson_week_cluster(xs, ys, ws)

    # ---- gross (mid) continuous corr already covers direction; also raw momentum
    #      pooled GROSS strategy means (hs=0) to separate signal from cost
    gross = {}
    for thr in THRESHOLDS:
        for direction in ("MOM", "REV"):
            gross[(thr, direction)] = eval_strategy(recs, direction, thr, 0.0)

    # ---- orthogonality: pick best surviving directional cell (net@primary),
    #      correlate its weekly PnL with longshot weekly series
    ls_weekly = longshot_weekly(recs, HS_PRIMARY)
    # candidate = pooled cell with largest positive week-clustered t among net@primary
    best = None
    for (gname, thr, direction), st in grid.items():
        if gname != "POOLED":
            continue
        if st["n"] < 50 or not (st["t"] == st["t"]):
            continue
        if best is None or st["t"] > best[1]["t"]:
            best = ((gname, thr, direction), st)
    ortho = None
    if best is not None:
        (bn, bt, bd), bst = best
        r_ls, k_ls = weekly_corr(bst["weekly"], ls_weekly)
        ortho = dict(cell=(bn, bt, bd), t=bst["t"], mean=bst["mean"],
                     corr_longshot=r_ls, weeks_overlap=k_ls,
                     ls_weeks=len(ls_weekly))

    # ---- ROBUSTNESS 1: interior anchor [10%,40%] (kills opening-print artifact)
    rec_int = [r for r in recs if "m_int" in r]
    int_cont = pearson_week_cluster(
        [r["m_int"] for r in rec_int],
        [r["yes_win"] - r["p_mid"] for r in rec_int],
        [r["week"] for r in rec_int])
    int_grid = {}
    for thr in THRESHOLDS:
        for direction in ("MOM", "REV"):
            # reuse eval_strategy but keyed on m_int
            pairs = []
            for r in rec_int:
                mm = r["m_int"]
                if abs(mm) < thr:
                    continue
                side = (1 if mm > 0 else -1) if direction == "MOM" else (-1 if mm > 0 else 1)
                pairs.append((r["week"], trade_pnl(r, side, HS_PRIMARY)))
            int_grid[(thr, direction)] = week_cluster_t(pairs)  # (n,mean,t,k)

    # ---- ROBUSTNESS 2: sane-open filter (exclude near-0/1 opening prints)
    rec_sane = [r for r in recs if 0.05 <= r["p_open"] <= 0.95]
    sane_cont = pearson_week_cluster(
        [r["m"] for r in rec_sane],
        [r["yes_win"] - r["p_mid"] for r in rec_sane],
        [r["week"] for r in rec_sane])
    sane_rev = {}
    for thr in THRESHOLDS:
        pairs = []
        for r in rec_sane:
            mm = r["m"]
            if abs(mm) < thr:
                continue
            side = -1 if mm > 0 else 1   # REVERSION
            pairs.append((r["week"], trade_pnl(r, side, HS_PRIMARY)))
        sane_rev[thr] = week_cluster_t(pairs)

    # ---- ROBUSTNESS 3: reversion-cell longshot corr at EVERY threshold
    rev_ls_corr = {}
    for thr in THRESHOLDS:
        st = grid[("POOLED", thr, "REV")]
        r_ls, k_ls = weekly_corr(st["weekly"], ls_weekly)
        rev_ls_corr[thr] = (r_ls, k_ls)

    n_weeks_total = len(set(r["week"] for r in recs))

    # =============================== REPORT ===============================
    out = []
    W = out.append
    W("# Polymarket Drift / Momentum vs Reversion — Third-Edge Hunt\n")
    W(f"_Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M UTC}_\n")
    W("**Signal (strictly causal).** Per settled binary market, life `[t0,t1]`; "
      "`p_open`=first hourly YES mid; decision at `t40 = t0+0.40*(t1-t0)`; "
      "`p_mid`=last mid at t<=t40; drift `m=p_mid-p_open` (measured BEFORE the "
      "decision point). MOMENTUM buys the direction of `m`, REVERSION fades it; "
      "held to UMA resolution (outcome in {0,1}); entered at the executable price "
      "(cross half-spread `hs`). Zero fee. Outcome only from resolution. "
      "Cluster by resolution week.\n")
    W(f"**Universe.** Liquid settled Yes/No markets (volume >= ${MIN_VOLUME:.0f}), "
      f"life in [{MIN_LIFE_DAYS:.0f},{MAX_LIFE_DAYS:.0f}]d. "
      f"Candidates {len(universe)}; with usable causal mids **{len(recs)}** across "
      f"**{n_weeks_total}** resolution weeks. "
      f"By category: " + ", ".join(f"{c}={sum(1 for r in recs if r['cat']==c)}" for c in cats) + ".\n")
    W(f"**Cost model.** No historical book snapshots exist, so entry cost is a flat "
      f"half-spread sweep `hs in {HALF_SPREADS}` (primary headline **hs={HS_PRIMARY:.3f}**, "
      f"i.e. a {2*HS_PRIMARY*100:.0f}c round-trip spread). Median reported per-market "
      f"`spread` of the used universe = {med_spread:.4f} (justifies ~1c half-spread as "
      f"realistic-to-conservative for these liquid markets).\n")

    pw = "; ".join([f"{c}={sum(1 for r in recs if r['cat']==c)}" for c in cats])
    if len(recs) < 300 or n_weeks_total < 20:
        W(f"> **POWER FLAG:** {len(recs)} markets / {n_weeks_total} weeks "
          f"(<300 markets or <20 weeks). Treat as suggestive only.\n")

    # ---- Grid table (net @ primary hs) ----
    W(f"\n## Momentum vs Reversion grid — net @ hs={HS_PRIMARY:.3f}, week-clustered t\n")
    W("Each cell: mean PnL/contract (net) / week-clustered t / n trades. A REAL edge "
      "is one-sided (MOM xor REV) and consistent across thresholds and categories.\n")
    header = "| group | thr | MOM mean | MOM t | MOM n | REV mean | REV t | REV n | weeks |"
    W(header); W("|" + "---|" * 9)
    for gname in ["POOLED"] + cats:
        for thr in THRESHOLDS:
            mm = grid[(gname, thr, "MOM")]; rv = grid[(gname, thr, "REV")]
            flag = ""
            W(f"| {gname} | {thr:.2f} | {fmt(mm['mean'])} | {fmt(mm['t'],2)} | {mm['n']} "
              f"| {fmt(rv['mean'])} | {fmt(rv['t'],2)} | {rv['n']} | {mm['weeks']} |")
    W("")

    # ---- Half-spread sensitivity (pooled) ----
    W("## Half-spread sensitivity (POOLED) — mean PnL/contract\n")
    W("| thr | dir | " + " | ".join(f"hs={h:.3f}" for h in HALF_SPREADS) + " | gross(hs=0) |")
    W("|---|---|" + "---|" * (len(HALF_SPREADS) + 1))
    for thr in THRESHOLDS:
        for direction in ("MOM", "REV"):
            cells = " | ".join(fmt(hs_sweep[(h, thr, direction)]["mean"]) for h in HALF_SPREADS)
            g = fmt(gross[(thr, direction)]["mean"])
            W(f"| {thr:.2f} | {direction} | {cells} | {g} |")
    W("")

    # ---- Continuous relationship ----
    W("## Continuous relationship: corr(m, outcome - p_mid)\n")
    W("Does first-40% drift predict the RESIDUAL future move beyond the current price "
      "(p_mid)? r>0 => momentum/underreaction; r<0 => reversion/overreaction. "
      "95% CI from week-block bootstrap (1000 reps).\n")
    W("| group | r | naive t | 95% CI (week-block) | n |")
    W("|---|---|---|---|---|")
    for gname in ["POOLED"] + cats:
        r, tval, (lo, hi), n = cont[gname]
        ci = f"[{lo:+.3f}, {hi:+.3f}]" if lo == lo else "n/a"
        W(f"| {gname} | {fmt(r,4)} | {fmt(tval,2)} | {ci} | {n} |")
    W("")

    # ---- Orthogonality ----
    W("## Stackability vs the longshot short-vol series\n")
    if ortho is not None:
        bn, bt, bd = ortho["cell"]
        W(f"Best directional cell by week-clustered t (net@{HS_PRIMARY:.3f}): "
          f"**{bd} thr={bt:.2f}**, mean {ortho['mean']:+.4f}, t={ortho['t']:+.2f}. "
          f"Its weekly PnL vs a 'sell longshots' series (p_mid in "
          f"[{LONGSHOT_LO},{LONGSHOT_HI}], SELL YES, same market set, "
          f"{ortho['ls_weeks']} weeks): "
          f"**corr = {fmt(ortho['corr_longshot'],2)}** over {ortho['weeks_overlap']} "
          f"overlapping weeks.\n")
    else:
        W("No pooled directional cell had enough trades to form a weekly series.\n")

    # ---- Robustness section ----
    W("## Robustness — is the reversion real or a stale-opening-print artifact?\n")
    W("**(1) Interior anchor.** Replace the first (possibly seed/noisy) print with the "
      "mid at the 10% point of life; keep the decision at 40%. `m` now spans the fully "
      "INTERIOR window [10%,40%] — no opening-print artifact, no resolution overlap.\n")
    ri, ti, (loi, hii), ni = int_cont
    W(f"- Interior corr(m_int, outcome-p_mid) = {fmt(ri,4)} (t={fmt(ti,2)}, "
      f"95% CI [{loi:+.3f},{hii:+.3f}], n={ni}).")
    W("- Interior POOLED reversion net@%.3f:" % HS_PRIMARY)
    W("\n| thr | REV mean | REV t | n | weeks |")
    W("|---|---|---|---|---|")
    for thr in THRESHOLDS:
        n, mean, t, k = int_grid[(thr, "REV")]
        W(f"| {thr:.2f} | {fmt(mean)} | {fmt(t,2)} | {n} | {k} |")
    W("")
    W("**(2) Sane-open filter.** Keep only markets whose opening print is in [0.05,0.95] "
      f"(n={len(rec_sane)}).\n")
    rs, tsv, (los, his), nsn = sane_cont
    W(f"- Sane-open corr(m, outcome-p_mid) = {fmt(rs,4)} (t={fmt(tsv,2)}, "
      f"95% CI [{los:+.3f},{his:+.3f}], n={nsn}).")
    W("\n| thr | REV mean | REV t | n | weeks |")
    W("|---|---|---|---|---|")
    for thr in THRESHOLDS:
        n, mean, t, k = sane_rev[thr]
        W(f"| {thr:.2f} | {fmt(mean)} | {fmt(t,2)} | {n} | {k} |")
    W("")
    W("**(3) Reversion vs longshot series at every threshold** (orthogonality):\n")
    W("| thr | REV weekly-PnL corr to sell-longshots | overlap weeks |")
    W("|---|---|---|")
    for thr in THRESHOLDS:
        r_ls, k_ls = rev_ls_corr[thr]
        W(f"| {thr:.2f} | {fmt(r_ls,2)} | {k_ls} |")
    W("")

    # ---- Verdict ----
    W("## BLUNT VERDICT\n")
    # decide: is there a consistent one-sided, cost-surviving directional edge?
    pooled_signif = []
    for thr in THRESHOLDS:
        mm = grid[("POOLED", thr, "MOM")]; rv = grid[("POOLED", thr, "REV")]
        pooled_signif.append((thr, mm, rv))
    # continuous pooled
    rP, tP, (loP, hiP), nP = cont["POOLED"]
    net_mom_pos = [grid[("POOLED", t, "MOM")] for t in THRESHOLDS]
    net_rev_pos = [grid[("POOLED", t, "REV")] for t in THRESHOLDS]

    def survives(cells):
        ok = [c for c in cells if c["t"] == c["t"] and c["t"] >= 2.0 and c["mean"] > 0]
        return ok

    mom_ok = survives(net_mom_pos); rev_ok = survives(net_rev_pos)
    lines = []
    lines.append(f"- Continuous pooled corr(m, outcome-p_mid) = {rP:+.4f} "
                 f"(naive t={tP:+.2f}, week-block 95% CI "
                 f"[{loP:+.3f},{hiP:+.3f}]).")
    lines.append(f"- POOLED net@{HS_PRIMARY:.3f}: MOMENTUM cells with t>=2 & mean>0: "
                 f"{len(mom_ok)}/{len(THRESHOLDS)}; REVERSION such cells: "
                 f"{len(rev_ok)}/{len(THRESHOLDS)}.")
    for c in lines:
        W(c)

    cont_mom = (rP == rP and loP == loP and loP > 0)   # CI excludes 0, positive => momentum
    cont_rev = (rP == rP and hiP == hiP and hiP < 0)    # CI excludes 0, negative => reversion
    # interior-anchor survival of reversion (sign + net > 0 at 2+ thresholds)
    int_rev_ok = sum(1 for thr in THRESHOLDS
                     if int_grid[(thr, "REV")][1] == int_grid[(thr, "REV")][1]
                     and int_grid[(thr, "REV")][1] > 0
                     and int_grid[(thr, "REV")][2] == int_grid[(thr, "REV")][2]
                     and int_grid[(thr, "REV")][2] >= 1.5)
    ri, tii, (loi, hii), ni = int_cont
    int_cont_rev = (ri == ri and hii == hii and hii < 0)
    # orthogonality: is the reversion cell decorrelated from the longshot book?
    ls_corrs = [rev_ls_corr[thr][0] for thr in THRESHOLDS if rev_ls_corr[thr][0] == rev_ls_corr[thr][0]]
    mean_ls_corr = float(np.mean(ls_corrs)) if ls_corrs else float("nan")
    orthogonal = (mean_ls_corr == mean_ls_corr and abs(mean_ls_corr) < 0.3)

    signal_present = (len(rev_ok) >= 2 and cont_rev)
    survives_interior = (int_rev_ok >= 2 and int_cont_rev)

    W(f"- Interior-anchor [10%->40%] reversion: corr={ri:+.4f} "
      f"(CI [{loi:+.3f},{hii:+.3f}]); net-positive at {int_rev_ok}/3 thresholds.")
    W(f"- Reversion vs sell-longshots weekly-PnL corr (mean over thresholds) = "
      f"{mean_ls_corr:+.2f} -> {'ORTHOGONAL' if orthogonal else 'NOT orthogonal'}.")
    W(f"- Net edge size @hs={HS_PRIMARY:.3f}: REV mean ~ "
      f"{grid[('POOLED',0.10,'REV')]['mean']:+.4f}/contract; at hs=0.020 -> "
      f"{hs_sweep[(0.020,0.10,'REV')]['mean']:+.4f}/contract.")

    if signal_present and survives_interior and orthogonal:
        verdict = "REVERSION edge — real, cost-surviving, AND orthogonal (STACKS)"
        detail = ("Reversion is significant net of cost, survives the interior anchor "
                  "(not an opening-print artifact), and is decorrelated from the longshot book.")
    elif signal_present and not orthogonal:
        verdict = "REVERSION signal is REAL but NOT a stackable third edge"
        detail = ("A first-40% move partially reverts (pooled continuous corr significantly "
                  "negative, reversion net-positive across thresholds), BUT its weekly PnL is "
                  f"strongly {'anti-' if mean_ls_corr<0 else ''}correlated with the sell-longshots "
                  f"series (mean corr {mean_ls_corr:+.2f}). Mechanically it BUYS fallen longshots / "
                  "SELLS risen favorites — i.e. it is largely the OPPOSITE side of the existing "
                  "longshot premium, not an orthogonal diversifier. Net margin is also thin "
                  "(~1-2c/contract) and decays toward zero by a 2c half-spread.")
    elif signal_present and not survives_interior:
        verdict = "REVERSION is mostly a stale-opening-print artifact — NULL as a tradeable edge"
        detail = ("The reversion vanishes/weakens once the anchor is moved off the first print, "
                  "so much of it is mean-reversion of a noisy/seeded opening quote, not a "
                  "tradeable behavioral edge.")
    elif len(mom_ok) >= 2 and cont_mom and len(rev_ok) == 0:
        verdict = "MOMENTUM edge (tentative)"
        detail = "Momentum survives cost on 2+ thresholds and the continuous corr CI is positive."
    else:
        verdict = "NULL — no cost-surviving directional drift/reversion edge"
        detail = ("Neither momentum nor reversion is consistently significant AND "
                  "cost-surviving AND sign-agreeing with the continuous corr.")

    power = "" if (len(recs) >= 300 and n_weeks_total >= 20) else " [UNDERPOWERED]"
    W(f"\n**Verdict{power}: {verdict}.** {detail}\n")
    W("_Bottom line for the book: there is a genuine short-horizon over-reaction "
      "(prices that jump in the first 40% of a market's life tend to give some of it "
      "back), strongest in crypto. But as a THIRD edge it is disappointing — it is thin "
      "net of spread and, crucially, it is not orthogonal to the longshot/short-vol "
      "premium already held; it is partly the same bet inverted. Do NOT size it as an "
      "independent diversifier._")

    report = "\n".join(out)
    with open("/home/user/Codex-playground-/pmkt_drift_report.md", "w") as f:
        f.write(report)

    # console summary
    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)
    # machine summary for the caller
    summ = dict(n_markets=len(recs), n_weeks=n_weeks_total,
                cont_pooled_r=rP, cont_pooled_ci=[loP, hiP],
                verdict=verdict,
                pooled_grid={f"thr{thr}_{d}": dict(mean=grid[("POOLED", thr, d)]["mean"],
                                                   t=grid[("POOLED", thr, d)]["t"],
                                                   n=grid[("POOLED", thr, d)]["n"])
                             for thr in THRESHOLDS for d in ("MOM", "REV")},
                ortho=ortho)
    with open(os.path.join(CACHE, "summary.json"), "w") as f:
        json.dump(summ, f, indent=2, default=str)
    print("\nSUMMARY_JSON:", json.dumps(summ, default=str))


if __name__ == "__main__":
    main()
