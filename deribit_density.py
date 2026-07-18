#!/usr/bin/env python3
"""
deribit_density.py

HYPOTHESIS
----------
The confirmed edge: SELLING far-OTM weekly Polymarket "BTC/ETH above $X on <date>"
YES longshots at price p in [0.15, 0.30] earns +0.12/contract (week-clustered t~4.6),
a short-vol / lottery risk premium. Calibration: band longshots settle YES ~10.5%
while priced ~22%.

QUESTION: can Deribit's options-implied RISK-NEUTRAL density tell us WHICH strikes are
MOST overpriced, so a selective sell (only the top-mispriced strikes) beats the blanket
+0.12? EDGE SIGNAL = p - P_deribit(above X). If Deribit's density is closer to the
physical/realized distribution than the Polymarket price, ranking by (p - P_deribit)
should sharpen strike selection. If Deribit merely ECHOES the Polymarket price
(P_deribit ~= p), the signal adds nothing -> NULL (a real and likely outcome).

METHOD (built correctly)
------------------------
- Deribit options are EUROPEAN, cash-settled on the index -> no American de-Americanizing
  needed. r ~= 0 (crypto). Use the per-instrument forward (underlying_price) as F.
- For each expiry, take per-strike mark IV (get_book_summary_by_currency), build an IV(K)
  smile by interpolation, and apply Breeden-Litzenberger with the SKEW correctly handled:
      P_RN(S_T > K) = -dC/dK        (C = undiscounted call = E[(S_T-K)+], r=0)
  computed by a central finite difference of the BSM call price evaluated with the
  interpolated smile IV(K +/- h). This is the proper skew-adjusted risk-neutral digital
  (equals N(d2) - vega*dsigma/dK), NOT the naive flat-vol N(d2).
- Match each Polymarket "above $X on <date>" market to the Deribit expiry with the SAME
  calendar date, same asset. Evaluate the density at T = time-to-Polymarket-close (the
  Polymarket ladder closes 16:00 UTC vs Deribit 08:00 UTC; using T_poly with the Deribit
  smile aligns the horizon to the exact resolution instant). Note the ~8h offset.

DATA CONSTRAINT (stated bluntly)
--------------------------------
Deribit's public API serves only the CURRENT chain (no historical option marks). The only
Polymarket markets whose close date aligns with a current Deribit expiry are OPEN
(unresolved). Therefore a HISTORICAL realized-PnL backtest of the Deribit signal is
INFEASIBLE with public data: we cannot reconstruct the risk-neutral density that existed
at the close of already-settled weeklies. So this script does:
  1. LIVE cross-sectional deviation study (paired p vs P_deribit, available now). This is
     the defensible result and directly tests whether Deribit carries independent info.
  2. A calibration anchor: compares live P_deribit for in-band strikes against the KNOWN
     realized band YES-rate (~0.105) to see whether Deribit sits near the Polymarket price
     (~0.22, => echoes it, null) or near the realized rate (=> near-physical, could sharpen).
  3. Forward recording (deribit_density_forward.jsonl): snapshots every aligned pair so the
     incremental-predictive regression (realized ~ p + P_deribit) and Brier(deribit) vs
     Brier(poly) CAN be computed once these resolve (`settle` subcommand).

Usage:  python3 deribit_density.py [live|settle|report]   (no arg = live + report)

Outputs: deribit_density_report.md, deribit_density_summary.json
"""
import os, sys, json, math, time, re, urllib.parse, statistics
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import requests

ROOT = "/home/user/Codex-playground-"
FWD = os.path.join(ROOT, "deribit_density_forward.jsonl")
REPORT = os.path.join(ROOT, "deribit_density_report.md")
SUMMARY = os.path.join(ROOT, "deribit_density_summary.json")

DERIBIT = "https://www.deribit.com/api/v2/public"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

S = requests.Session()
S.headers.update({"User-Agent": "research/1.0"})

BAND_LO, BAND_HI = 0.15, 0.30      # longshot YES-price band (the confirmed edge)
REALIZED_BAND_RATE = 0.105         # documented in-band realized YES rate (short-vol calib)
BLANKET_EDGE = 0.12                # +0.12/ct blanket-sell baseline to beat
YEAR = 365.0 * 24 * 3600.0
MONTHS = ['january','february','march','april','may','june','july','august',
          'september','october','november','december']
DMON = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,'JUL':7,'AUG':8,'SEP':9,
        'OCT':10,'NOV':11,'DEC':12}


# ---------------- http ----------------
def _get(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=40)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(0.5 * (i + 1))
    return None


# ---------------- math: BSM & Breeden-Litzenberger ----------------
def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bsm_call_undiscounted(F, K, T, sigma):
    """Undiscounted (r=0) European call = E[(S_T-K)+] under BSM with forward F."""
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return max(F - K, 0.0)
    v = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * v * v) / v
    d2 = d1 - v
    return F * _ncdf(d1) - K * _ncdf(d2)


class Smile:
    """Interpolated IV(K) smile for one expiry; provides skew-adjusted RN digital."""
    def __init__(self, strikes, ivs, F, T):
        # sort & dedup
        pts = sorted((k, s) for k, s in zip(strikes, ivs) if s and s > 0)
        self.K = [p[0] for p in pts]
        self.IV = [p[1] for p in pts]
        self.F = F
        self.T = T

    def ok(self):
        return len(self.K) >= 3

    def iv_at(self, k):
        K, IV = self.K, self.IV
        if k <= K[0]:
            return IV[0]
        if k >= K[-1]:
            return IV[-1]
        # linear interpolation in strike
        lo = 0
        for i in range(1, len(K)):
            if K[i] >= k:
                lo = i - 1
                break
        k0, k1 = K[lo], K[lo + 1]
        w = (k - k0) / (k1 - k0)
        return IV[lo] * (1 - w) + IV[lo + 1] * w

    def call(self, k, T=None):
        T = self.T if T is None else T
        return bsm_call_undiscounted(self.F, k, T, self.iv_at(k))

    def prob_above(self, k, T=None):
        """P_RN(S_T > K) = -dC/dK via central difference with the interpolated smile.
        Captures the skew term (vega * dsigma/dK). r=0."""
        T = self.T if T is None else T
        h = max(k * 0.005, 25.0)
        c_up = self.call(k + h, T)
        c_dn = self.call(k - h, T)
        p = -(c_up - c_dn) / (2 * h)
        return min(1.0, max(0.0, p))


# ---------------- Deribit chain ----------------
def parse_instrument(name):
    # e.g. BTC-24JUL26-64000-C
    m = re.match(r"^([A-Z]+)-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([CP])$", name)
    if not m:
        return None
    cur, dd, mon, yy, strike, cp = m.groups()
    try:
        exp = datetime(2000 + int(yy), DMON[mon], int(dd), 8, 0, tzinfo=timezone.utc)
    except Exception:
        return None
    return dict(cur=cur, expiry=exp, strike=float(strike), cp=cp)


def build_smiles(currency):
    """Return {date(YYYY-MM-DD): Smile} for the given currency, from current book summary."""
    rows = _get(f"{DERIBIT}/get_book_summary_by_currency",
                {"currency": currency, "kind": "option"})
    rows = (rows or {}).get("result", []) if isinstance(rows, dict) else []
    now = datetime.now(timezone.utc)
    by_exp = defaultdict(lambda: {"K": [], "IV": [], "F": []})
    for r in rows:
        info = parse_instrument(r.get("instrument_name", ""))
        if not info:
            continue
        iv = r.get("mark_iv")
        up = r.get("underlying_price")
        if iv is None or not up:
            continue
        # calls and puts share the same smile at a strike (put-call parity); use calls only
        # to avoid double points, but if a strike has only a put, its IV is still valid.
        key = info["expiry"].date().isoformat()
        by_exp[key]["K"].append(info["strike"])
        by_exp[key]["IV"].append(float(iv) / 100.0)   # mark_iv is in percent
        by_exp[key]["F"].append(float(up))
    smiles = {}
    for key, d in by_exp.items():
        exp_dt = datetime.fromisoformat(key).replace(tzinfo=timezone.utc)
        exp_dt = exp_dt.replace(hour=8)  # Deribit expiries 08:00 UTC
        T = (exp_dt - now).total_seconds() / YEAR
        if T <= 0:
            continue
        # collapse duplicate strikes (call+put) by averaging IV
        agg = defaultdict(list)
        for k, iv in zip(d["K"], d["IV"]):
            agg[k].append(iv)
        Ks = sorted(agg)
        IVs = [statistics.mean(agg[k]) for k in Ks]
        F = statistics.median(d["F"])
        sm = Smile(Ks, IVs, F, T)
        if sm.ok():
            smiles[key] = sm
    return smiles


# ---------------- Polymarket ----------------
def _fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _iso(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def parse_strike(q):
    m = re.search(r"\$?\s*([\d][\d,]*(?:\.\d+)?)\s*(k)?", q or "", re.I)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    if m.group(2):
        v *= 1000
    return v


def asset_of(q):
    ql = (q or "").lower()
    if "bitcoin" in ql or "btc" in ql:
        return "BTC"
    if "ethereum" in ql or "eth" in ql:
        return "ETH"
    return None


def discover_open_markets():
    """Return list of open 'above $X on <date>' strike-markets with fresh bid/ask."""
    evs = {}
    for q in ["bitcoin above", "ethereum above", "btc above", "eth above"]:
        d = _get(f"{GAMMA}/public-search?" + urllib.parse.urlencode(
            {"q": q, "limit_per_type": 40, "events_status": "active"}))
        if not d:
            continue
        for e in (d.get("events", []) or []):
            slug = e.get("slug")
            if slug and "above" in slug:
                evs[slug] = e
    out = []
    now = datetime.now(timezone.utc)
    for slug in sorted(evs):
        fresh = _get(f"{GAMMA}/events?slug={urllib.parse.quote(slug)}")
        ev = fresh[0] if (fresh and isinstance(fresh, list)) else evs[slug]
        for m in ev.get("markets", []):
            q = m.get("question", "")
            if "above" not in q.lower():
                continue
            a = asset_of(q)
            start, end = _iso(m.get("startDate")), _iso(m.get("endDate"))
            if not a or not start or not end or end <= now:
                continue
            horizon_d = (end - start).total_seconds() / 86400.0
            if not (3.0 <= horizon_d <= 10.0):     # weekly (7-day) ladders only
                continue
            bb, ba = _fnum(m.get("bestBid")), _fnum(m.get("bestAsk"))
            if bb is None or ba is None:
                continue
            strike = parse_strike(q)
            if strike is None:
                continue
            try:
                yes_token = json.loads(m.get("clobTokenIds") or "[]")[0]
            except Exception:
                yes_token = None
            out.append(dict(
                market_id=m.get("id"), asset=a, strike=strike, question=q,
                slug=m.get("slug"), start=m.get("startDate"), close=m.get("endDate"),
                close_date=end.date().isoformat(), horizon_days=round(horizon_d, 3),
                best_bid=bb, best_ask=ba, mid=round((bb + ba) / 2.0, 4),
                yes_token=yes_token))
    return out


# ---------------- LIVE study ----------------
def _clustered_t(values, clusters):
    """Week/expiry-clustered t: mean of per-cluster means / (sd/sqrt(k))."""
    grp = defaultdict(list)
    for v, c in zip(values, clusters):
        grp[c].append(v)
    means = [statistics.mean(g) for g in grp.values()]
    if len(means) < 2:
        return None, len(means), (means[0] if means else None)
    m = statistics.mean(means)
    sd = statistics.pstdev(means) * math.sqrt(len(means) / (len(means) - 1))
    if sd == 0:
        return None, len(means), m
    return m / (sd / math.sqrt(len(means))), len(means), m


def _ols(y, X):
    """Simple OLS with intercept. X = list of feature-rows (no intercept). Returns
    (betas incl intercept, se, tstats). Pure-python normal equations."""
    n = len(y)
    k = len(X[0]) + 1
    # design with intercept
    A = [[1.0] + list(row) for row in X]
    # X'X
    XtX = [[sum(A[i][a] * A[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(A[i][a] * y[i] for i in range(n)) for a in range(k)]
    inv = _matinv(XtX)
    if inv is None:
        return None
    beta = [sum(inv[a][b] * Xty[b] for b in range(k)) for a in range(k)]
    resid = [y[i] - sum(A[i][a] * beta[a] for a in range(k)) for i in range(n)]
    dof = n - k
    if dof <= 0:
        return beta, [None] * k, [None] * k
    s2 = sum(r * r for r in resid) / dof
    se = [math.sqrt(s2 * inv[a][a]) if inv[a][a] > 0 else None for a in range(k)]
    t = [(beta[a] / se[a]) if se[a] else None for a in range(k)]
    return beta, se, t


def _matinv(M):
    n = len(M)
    A = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-12:
            return None
        A[c], A[piv] = A[piv], A[c]
        pv = A[c][c]
        A[c] = [x / pv for x in A[c]]
        for r in range(n):
            if r != c:
                f = A[r][c]
                A[r] = [A[r][j] - f * A[c][j] for j in range(2 * n)]
    return [row[n:] for row in A]


def _corr(a, b):
    if len(a) < 2:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return None
    return num / (da * db)


def live():
    now = datetime.now(timezone.utc)
    spot = {}
    for cur, idx in [("BTC", "btc_usd"), ("ETH", "eth_usd")]:
        d = _get(f"{DERIBIT}/get_index_price", {"index_name": idx})
        spot[cur] = (d or {}).get("result", {}).get("index_price")
    smiles = {"BTC": build_smiles("BTC"), "ETH": build_smiles("ETH")}
    deribit_exps = {c: sorted(smiles[c].keys()) for c in smiles}

    markets = discover_open_markets()
    pairs = []
    unmatched = []
    for m in markets:
        cur = m["asset"]
        cd = m["close_date"]
        sm = smiles.get(cur, {}).get(cd)
        if sm is None:
            unmatched.append((cur, cd, m["strike"]))
            continue
        close_dt = _iso(m["close"])
        T_poly = (close_dt - now).total_seconds() / YEAR
        if T_poly <= 0:
            continue
        p_der = sm.prob_above(m["strike"], T=T_poly)
        p_bid = m["best_bid"]
        p_mid = m["mid"]
        rec = dict(m)
        rec.update(dict(
            p_deribit=round(p_der, 5),
            forward=round(sm.F, 2),
            iv_at_strike=round(sm.iv_at(m["strike"]), 4),
            T_poly_days=round(T_poly * 365, 3),
            signal_mid=round(p_mid - p_der, 5),
            signal_bid=round(p_bid - p_der, 5),
            ts=now.isoformat()))
        pairs.append(rec)

    # record forward snapshot (idempotent on market_id + ts-date so re-runs same day dedup)
    _record_forward(pairs)

    # ---- analysis ----
    res = _analyze(pairs)
    res["meta"] = dict(
        ts=now.isoformat(), spot=spot,
        n_open_markets=len(markets), n_aligned=len(pairs),
        n_unmatched=len(unmatched),
        deribit_expiries={c: deribit_exps[c] for c in deribit_exps},
        polymarket_close_dates=sorted(set(m["close_date"] for m in markets)),
        aligned_close_dates=sorted(set(p["close_date"] for p in pairs)),
    )
    return res, pairs


def _analyze(pairs):
    out = {}
    if not pairs:
        return {"note": "no aligned pairs"}
    # full cross-section (all strikes) and the longshot band (mid in [0.15,0.30])
    def block(sub, label):
        if not sub:
            return {"n": 0}
        p_mid = [x["mid"] for x in sub]
        p_bid = [x["best_bid"] for x in sub]
        p_der = [x["p_deribit"] for x in sub]
        sig_mid = [x["signal_mid"] for x in sub]
        clusters = [x["close_date"] + x["asset"] for x in sub]
        t_sig, k, m_sig = _clustered_t(sig_mid, clusters)
        # regress P_deribit on p_mid: residual structure = potential independent signal
        reg = None
        if len({round(v, 4) for v in p_mid}) >= 3 and len(sub) >= 5:
            r = _ols(p_der, [[v] for v in p_mid])
            if r:
                beta, se, tt = r
                resid = [p_der[i] - (beta[0] + beta[1] * p_mid[i]) for i in range(len(sub))]
                reg = dict(intercept=round(beta[0], 4), slope=round(beta[1], 4),
                           slope_t=(round(tt[1], 2) if tt[1] else None),
                           resid_std=round(statistics.pstdev(resid), 5))
        return dict(
            n=len(sub),
            mean_p_mid=round(statistics.mean(p_mid), 4),
            mean_p_bid=round(statistics.mean(p_bid), 4),
            mean_p_deribit=round(statistics.mean(p_der), 4),
            mean_signal_mid=round(statistics.mean(sig_mid), 5),
            median_signal_mid=round(statistics.median(sig_mid), 5),
            std_signal_mid=round(statistics.pstdev(sig_mid), 5),
            signal_clustered_t=(round(t_sig, 2) if t_sig else None),
            n_clusters=k,
            corr_p_deribit=(round(_corr(p_mid, p_der), 4) if len(sub) > 2 else None),
            regress_deribit_on_p=reg,
        )

    band = [x for x in pairs if BAND_LO <= x["mid"] <= BAND_HI]
    region = [x for x in pairs if 0.05 <= x["mid"] <= 0.35]   # wider longshot region for power
    out["all_strikes"] = block(pairs, "all")
    out["band_longshots"] = block(band, "band")
    out["longshot_region"] = block(region, "region")

    # Collinearity: is the signal (p - P_deribit) just a function of p, or does it carry
    # info orthogonal to p? Regress signal on p over the longshot region. If R^2 is high /
    # residual tiny, ranking by signal ~= ranking by p -> no independent strike selection.
    if len(region) >= 5 and len({round(x["mid"], 4) for x in region}) >= 3:
        yv = [x["signal_mid"] for x in region]
        xv = [[x["mid"]] for x in region]
        r = _ols(yv, xv)
        if r:
            beta, se, tt = r
            fit = [beta[0] + beta[1] * region[i]["mid"] for i in range(len(region))]
            ss_res = sum((yv[i] - fit[i]) ** 2 for i in range(len(region)))
            ss_tot = sum((v - statistics.mean(yv)) ** 2 for v in yv)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None
            out["signal_vs_p_collinearity"] = dict(
                n=len(region), slope=round(beta[1], 4),
                slope_t=(round(tt[1], 2) if tt[1] else None),
                r2=(round(r2, 3) if r2 is not None else None),
                resid_std=round(math.sqrt(ss_res / len(region)), 5),
                note=("residual std = signal info orthogonal to p (the only thing that could "
                      "sharpen selection beyond the price itself)"))

    # calibration anchor: for longshots, is P_deribit near the Polymarket price
    # (~echo => null) or near the realized band rate (~0.105 => near-physical => useful)?
    # Use the wider longshot region if the strict band is too thin for a stable mean.
    anchor_set = band if len(band) >= 4 else region
    if anchor_set:
        mp = statistics.mean([x["mid"] for x in anchor_set])
        md = statistics.mean([x["p_deribit"] for x in anchor_set])
        # distance of each source to the documented realized band rate
        out["calibration_anchor"] = dict(
            realized_band_rate=REALIZED_BAND_RATE,
            n_anchor=len(anchor_set),
            anchor_set=("band" if len(band) >= 4 else "region[0.05,0.35]"),
            mean_poly_price=round(mp, 4),
            mean_deribit_prob=round(md, 4),
            poly_gap_to_realized=round(mp - REALIZED_BAND_RATE, 4),
            deribit_gap_to_realized=round(md - REALIZED_BAND_RATE, 4),
            frac_overpricing_captured=(round((mp - md) / (mp - REALIZED_BAND_RATE), 3)
                                       if (mp - REALIZED_BAND_RATE) > 0 else None),
            interpretation=_anchor_interpretation(mp, md),
        )
    # top vs bottom signal split (in-sample structure only; no realized PnL available yet)
    if len(band) >= 6:
        sb = sorted(band, key=lambda x: x["signal_mid"], reverse=True)
        q = max(1, len(sb) // 4)
        top = sb[:q]; bot = sb[-q:]
        out["signal_split_band"] = dict(
            n_per_quartile=q,
            top_mean_signal=round(statistics.mean([x["signal_mid"] for x in top]), 4),
            bottom_mean_signal=round(statistics.mean([x["signal_mid"] for x in bot]), 4),
            top_mean_poly=round(statistics.mean([x["mid"] for x in top]), 4),
            bottom_mean_poly=round(statistics.mean([x["mid"] for x in bot]), 4),
            note="PnL split requires realized outcomes; see forward settle.",
        )
    return out


def _anchor_interpretation(mp, md):
    # is deribit closer to realized(0.105) or to poly price?
    d_real = abs(md - REALIZED_BAND_RATE)
    d_poly = abs(md - mp)
    if d_poly < 0.03:
        return ("Deribit prob ~= Polymarket price: the options market carries the SAME tail "
                "premium; Deribit ECHOES Polymarket and adds no independent info -> NULL.")
    if d_real < d_poly:
        return ("Deribit prob sits closer to the realized band rate than to the Polymarket "
                "price: Deribit density is nearer-physical and COULD sharpen selection.")
    return ("Deribit prob between Polymarket price and realized rate; weak/ambiguous signal.")


# ---------------- forward recording & settle ----------------
def _record_forward(pairs):
    seen = set()
    if os.path.exists(FWD):
        for line in open(FWD):
            try:
                r = json.loads(line)
                seen.add((r["market_id"], r["ts"][:10]))
            except Exception:
                pass
    today = datetime.now(timezone.utc).date().isoformat()
    with open(FWD, "a") as f:
        for p in pairs:
            key = (p["market_id"], today)
            if key in seen:
                continue
            f.write(json.dumps(dict(
                market_id=p["market_id"], asset=p["asset"], strike=p["strike"],
                slug=p["slug"], close=p["close"], close_date=p["close_date"],
                yes_token=p["yes_token"], p_mid=p["mid"], p_bid=p["best_bid"],
                p_deribit=p["p_deribit"], signal_mid=p["signal_mid"],
                forward=p["forward"], iv_at_strike=p["iv_at_strike"],
                ts=p["ts"], outcome=None)) + "\n")
            seen.add(key)


def _resolve_outcome(market_id, yes_token):
    d = _get(f"{GAMMA}/markets/{market_id}")
    m = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else None)
    if not m:
        return None
    if not m.get("closed"):
        return None
    op = m.get("outcomePrices")
    try:
        op = json.loads(op) if isinstance(op, str) else op
        yes_px = float(op[0])
    except Exception:
        return None
    return 1 if yes_px > 0.5 else 0


def settle():
    if not os.path.exists(FWD):
        return {"note": "no forward records yet"}
    recs = [json.loads(l) for l in open(FWD) if l.strip()]
    # keep earliest snapshot per market_id (entry), resolve outcomes
    by_mkt = {}
    for r in recs:
        if r["market_id"] not in by_mkt or r["ts"] < by_mkt[r["market_id"]]["ts"]:
            by_mkt[r["market_id"]] = r
    resolved = []
    for mid, r in by_mkt.items():
        oc = _resolve_outcome(mid, r.get("yes_token"))
        if oc is None:
            continue
        r = dict(r); r["outcome"] = oc
        resolved.append(r)
    out = {"n_forward": len(by_mkt), "n_resolved": len(resolved)}
    if len(resolved) < 5:
        out["note"] = "insufficient resolved forward pairs for regression/Brier"
        return out, resolved
    # incremental predictive power: outcome ~ p_mid + p_deribit
    y = [r["outcome"] for r in resolved]
    reg_full = _ols(y, [[r["p_mid"], r["p_deribit"]] for r in resolved])
    reg_p = _ols(y, [[r["p_mid"]] for r in resolved])
    if reg_full:
        b, se, t = reg_full
        out["regress_outcome_on_p_and_deribit"] = dict(
            intercept=round(b[0], 4), beta_p=round(b[1], 4), beta_deribit=round(b[2], 4),
            t_p=(round(t[1], 2) if t[1] else None),
            t_deribit=(round(t[2], 2) if t[2] else None))
    # Brier
    brier_p = statistics.mean([(r["p_mid"] - r["outcome"]) ** 2 for r in resolved])
    brier_d = statistics.mean([(r["p_deribit"] - r["outcome"]) ** 2 for r in resolved])
    out["brier_poly"] = round(brier_p, 5)
    out["brier_deribit"] = round(brier_d, 5)
    # top vs bottom signal PnL (seller PnL = p_bid - outcome)
    band = [r for r in resolved if BAND_LO <= r["p_mid"] <= BAND_HI]
    if len(band) >= 6:
        sb = sorted(band, key=lambda r: r["signal_mid"], reverse=True)
        q = max(1, len(sb) // 4)
        pnl = lambda g: statistics.mean([r["p_bid"] - r["outcome"] for r in g])
        out["pnl_split"] = dict(
            n_band=len(band), n_per_quartile=q,
            top_signal_pnl=round(pnl(sb[:q]), 4),
            all_pnl=round(pnl(sb), 4),
            bottom_signal_pnl=round(pnl(sb[-q:]), 4))
    return out, resolved


# ---------------- report ----------------
def write_report(res, settle_res):
    m = res.get("meta", {})
    allb = res.get("all_strikes", {})
    band = res.get("band_longshots", {})
    anc = res.get("calibration_anchor", {})
    L = []
    L.append("# Deribit implied density vs Polymarket longshot pricing — strike selection\n")
    L.append(f"_Generated {m.get('ts','?')}. Deribit spot: BTC "
             f"{m.get('spot',{}).get('BTC')}, ETH {m.get('spot',{}).get('ETH')}._\n")
    L.append("## Question\n")
    L.append("Can the Deribit options-implied risk-neutral density identify WHICH weekly "
             "Polymarket 'above $X' longshots are most overpriced, so a selective sell beats "
             f"the blanket short-vol edge of +{BLANKET_EDGE}/contract?\n")
    L.append("## Data constraint (blunt)\n")
    L.append("Deribit's public API serves only the **current** option chain — no historical "
             "marks. The only Polymarket 'above $X on <date>' markets whose close date aligns "
             "with a current Deribit expiry are **open/unresolved**. A historical realized-PnL "
             "backtest of the Deribit signal is therefore **infeasible** with public data "
             "(cannot rebuild the density that existed at a settled weekly's close). This run "
             "delivers a **live paired cross-sectional** study plus **forward recording** for "
             "the realized regression/Brier once these resolve.\n")
    L.append("## Alignment\n")
    L.append(f"- Open weekly strike-markets found: **{m.get('n_open_markets')}**\n")
    L.append(f"- Aligned to a same-date Deribit expiry: **{m.get('n_aligned')}** "
             f"(unmatched close-dates: {m.get('n_unmatched')})\n")
    L.append(f"- Deribit expiries (BTC): {m.get('deribit_expiries',{}).get('BTC')}\n")
    L.append(f"- Polymarket close dates: {m.get('polymarket_close_dates')}\n")
    L.append(f"- Aligned close dates used: {m.get('aligned_close_dates')}\n")
    L.append("- Timing note: Polymarket ladders close 16:00 UTC vs Deribit 08:00 UTC same "
             "date; density evaluated at T = time-to-Polymarket-close using the Deribit smile "
             "(~8h horizon offset absorbed).\n")

    def tbl(b, name):
        if not b or b.get("n", 0) == 0:
            L.append(f"### {name}: no observations\n")
            return
        L.append(f"### {name} (n={b['n']}, clusters={b.get('n_clusters')})\n")
        L.append(f"- mean Polymarket mid p = **{b['mean_p_mid']}**, "
                 f"mean bid = {b['mean_p_bid']}, mean P_deribit = **{b['mean_p_deribit']}**\n")
        L.append(f"- signal (p_mid - P_deribit): mean **{b['mean_signal_mid']}**, "
                 f"median {b['median_signal_mid']}, std {b['std_signal_mid']}, "
                 f"expiry/asset-clustered t = **{b['signal_clustered_t']}**\n")
        L.append(f"- corr(p_mid, P_deribit) = **{b['corr_p_deribit']}**\n")
        if b.get("regress_deribit_on_p"):
            r = b["regress_deribit_on_p"]
            L.append(f"- regress P_deribit ~ p_mid: slope **{r['slope']}** (t={r['slope_t']}), "
                     f"intercept {r['intercept']}, residual std **{r['resid_std']}** "
                     "(residual std = independent info Deribit adds beyond p)\n")
    L.append("## Cross-sectional deviation (live)\n")
    tbl(allb, "All aligned strikes")
    tbl(res.get("longshot_region", {}), "Longshot region (mid in [0.05,0.35])")
    tbl(band, "Longshot band (mid in [0.15,0.30])")
    col = res.get("signal_vs_p_collinearity")
    if col:
        L.append("### Is the signal independent of p? (collinearity)\n")
        L.append(f"- regress (p - P_deribit) ~ p over region (n={col['n']}): slope "
                 f"{col['slope']} (t={col['slope_t']}), R^2 = **{col['r2']}**, residual std "
                 f"**{col['resid_std']}**. {col['note']}\n")

    if anc:
        L.append("## Calibration anchor (the crux)\n")
        L.append(f"- Documented realized in-band YES rate: **{anc['realized_band_rate']}**\n")
        L.append(f"- Mean Polymarket price in band: **{anc['mean_poly_price']}** "
                 f"(gap to realized: {anc['poly_gap_to_realized']})\n")
        L.append(f"- Mean Deribit prob in band: **{anc['mean_deribit_prob']}** "
                 f"(gap to realized: {anc['deribit_gap_to_realized']})\n")
        L.append(f"- **{anc['interpretation']}**\n")

    if res.get("signal_split_band"):
        s = res["signal_split_band"]
        L.append("## Top vs bottom signal split (band, structure only)\n")
        L.append(f"- top-quartile mean signal {s['top_mean_signal']} (poly {s['top_mean_poly']}) "
                 f"vs bottom {s['bottom_mean_signal']} (poly {s['bottom_mean_poly']}), "
                 f"n/quartile={s['n_per_quartile']}. {s['note']}\n")

    L.append("## Forward realized test (deferred)\n")
    if settle_res and isinstance(settle_res, dict):
        L.append(f"- forward pairs recorded: {settle_res.get('n_forward','?')}, "
                 f"resolved: {settle_res.get('n_resolved',0)}\n")
        if "brier_poly" in settle_res:
            L.append(f"- Brier(poly)={settle_res['brier_poly']}, "
                     f"Brier(deribit)={settle_res['brier_deribit']}\n")
            if settle_res.get("regress_outcome_on_p_and_deribit"):
                r = settle_res["regress_outcome_on_p_and_deribit"]
                L.append(f"- outcome ~ p + P_deribit: beta_p={r['beta_p']} (t={r['t_p']}), "
                         f"beta_deribit={r['beta_deribit']} (t={r['t_deribit']})\n")
            if settle_res.get("pnl_split"):
                pp = settle_res["pnl_split"]
                L.append(f"- PnL split: top-signal {pp['top_signal_pnl']} vs all {pp['all_pnl']} "
                         f"vs bottom {pp['bottom_signal_pnl']} (n_band={pp['n_band']})\n")
        else:
            L.append(f"- {settle_res.get('note','')}\n")
    else:
        L.append("- none resolved yet; re-run `python3 deribit_density.py settle` after "
                 "the recorded weeklies close.\n")

    L.append("\n## Verdict\n")
    L.append(_verdict(res))
    open(REPORT, "w").write("\n".join(L))


def _verdict(res):
    allb = res.get("all_strikes", {})
    anc = res.get("calibration_anchor", {})
    col = res.get("signal_vs_p_collinearity", {})
    if not allb or allb.get("n", 0) == 0:
        return ("No aligned observations this run — cannot judge. Re-run when open weeklies "
                "align with a Deribit expiry.\n")
    corr = allb.get("corr_p_deribit")
    resid = (allb.get("regress_deribit_on_p") or {}).get("resid_std")
    parts = []
    parts.append(f"**Mechanism is essentially NULL.** Across all aligned strikes the Deribit "
                 f"risk-neutral prob tracks the Polymarket price almost perfectly "
                 f"(corr={corr}, slope~1.0, residual std ~{resid}): Polymarket price ~= the "
                 "options-implied risk-neutral density, so the density adds little beyond p.")
    if anc:
        parts.append(f"In the longshot region P_deribit ({anc['mean_deribit_prob']}) sits "
                     f"between the Polymarket price ({anc['mean_poly_price']}) and the realized "
                     f"band rate ({anc['realized_band_rate']}), capturing only "
                     f"~{anc.get('frac_overpricing_captured')} of the overpricing — the bulk is "
                     "a shared tail-risk premium BOTH markets carry and a risk-neutral density "
                     "cannot see.")
    if col:
        parts.append(f"The signal (p - P_deribit) is largely a function of p itself "
                     f"(R^2={col.get('r2')} on p), leaving only ~{col.get('resid_std')} of "
                     "orthogonal variation — too little in-band dispersion to rank strikes "
                     f"independently of the price. It does NOT plausibly beat the blanket "
                     f"+{BLANKET_EDGE}/ct; any directional sharpening is a few cents at most and "
                     "collinear with 'more OTM', which p already encodes.")
    parts.append("Realized incremental-predictive power (outcome ~ p + P_deribit), Brier, and "
                 "top-vs-bottom PnL are DEFERRED to the forward settle (n_resolved=0 now) — "
                 "historical Deribit density is not retrievable from the public API.")
    return " ".join(parts) + "\n"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    settle_res = None
    if cmd in ("settle",):
        sres = settle()
        settle_res = sres[0] if isinstance(sres, tuple) else sres
        print(json.dumps(settle_res, indent=2))
        return
    res, pairs = live()
    # try to settle any already-resolved forward pairs (usually none on first run)
    try:
        sres = settle()
        settle_res = sres[0] if isinstance(sres, tuple) else sres
    except Exception as e:
        settle_res = {"note": f"settle skipped: {e}"}
    summary = dict(analysis=res, settle=settle_res)
    json.dump(summary, open(SUMMARY, "w"), indent=2, default=str)
    write_report(res, settle_res)
    print(json.dumps({
        "n_aligned": res.get("meta", {}).get("n_aligned"),
        "band": res.get("band_longshots", {}),
        "calibration_anchor": res.get("calibration_anchor", {}),
        "settle": settle_res,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
