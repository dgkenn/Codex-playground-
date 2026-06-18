#!/usr/bin/env python3
"""
kalshi_longshot_capacity2.py
============================
Does the longshot-OVERPRICING maker edge (sell overpriced longshots, rest NO when
YES mid < 0.20) survive in HIGH-VOLUME Kalshi markets, where capacity -- not edge --
would be the binding constraint?

The soft-market study (KALSHI_MAKER_*.md) found a real +EV edge (+0.97c/contract @17sigma
net of adverse selection+fee) but capped at ~$30-150/month because soft markets are tiny
(~$300-800 lifetime notional, 3-4 contract touch nibbles).

The favorite-longshot literature says the bias is BIGGEST in thin markets and SMALLER
(more efficient) in deep ones. This script tests that tradeoff directly:

  TARGETS: deep Kalshi longshot markets --
    - political/election "will win" longshots (Politics)
    - major sports FUTURES (championship/MVP/award/draft longshots -- many low-prob legs
      with real volume) (Sports)
    - headline/recurring event tails (Fed/CPI thresholds, "will X happen") (Economics)

  MEASURE, for the highest-VOLUME settled longshot legs (mid-life YES mid < 0.20,
  single-outcome binary, exclude MVE):
    (1) longshot overpricing bias: realized YES-rate vs mid-life mid, by volume quartile
        -> does the bias survive in deep markets?
    (2) executable depth: $ notional per market, lifetime, and resulting $/month ceiling
        if you harvested only the high-volume longshots
    (3) compare to the ~$30-150/mo soft-market ceiling -- 2x? 10x? or bias vanishes?

  FEE CAVEAT: flagship sports/econ series fee_type=quadratic_with_maker_fees charge makers
  25% of taker fee. We record fee_type per series and split results
  zero-maker-fee (quadratic) vs maker-fee (penalized).

Public API only (no auth). base = https://api.elections.kalshi.com/trade-api/v2
"""
import urllib.request, urllib.parse, json, datetime, time, math, sys
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "kalshi-longshot-capacity2/1.0"}

# Candidate DEEP longshot series. Hand-picked across the three target families to keep
# API load bounded while covering the deepest known longshot books. Each is a series whose
# settled markets are single-outcome binary legs that include many low-prob (<0.20) legs.
SERIES = {
    # --- Sports FUTURES (many longshot legs, real volume) ---
    "KXNBATOPPICK":   ("Sports", "NBA draft lottery winner"),
    "KXNBA":          ("Sports", "NBA champion"),          # quadratic_with_maker_fees
    "KXNBAMVP":       ("Sports", "NBA MVP"),               # maker fee
    "KXNFLMVP":       ("Sports", "NFL MVP"),               # maker fee
    "KXNCAAF":        ("Sports", "NCAAF champion"),        # maker fee
    "KXMLBWS":        ("Sports", "MLB World Series"),
    "KXNFLFIRSTPICK": ("Sports", "NFL first draft pick"),
    "KXATP":          ("Sports", "ATP tournament winner"),
    "KXNBAEAST":      ("Sports", "NBA East champion"),     # maker fee
    "KXNBAWEST":      ("Sports", "NBA West champion"),     # maker fee
    # --- Politics "will win / will be" longshots ---
    "KXSECCOM":       ("Politics", "Next Sec of Commerce"),
    "KXASSOCAG":      ("Politics", "Associate Attorney General"),
    "KXNEWROLEGS":    ("Politics", "Goldman new CEO"),
    "KXPRESPARTY":    ("Politics", "Party winning presidency"),
    "KXSENATE":       ("Politics", "US Senate control"),
    "KXSPEAKER":      ("Politics", "Speaker of the House"),
    # --- Economics threshold tails (deep, recurring) ---
    "KXCPIYOY":       ("Economics", "CPI inflation YoY"),  # maker fee
    "KXFEDDECISION":  ("Economics", "Fed meeting decision"),  # maker fee
    "KXFED":          ("Economics", "Fed funds rate"),    # maker fee
    "KXCPI":          ("Economics", "CPI"),               # maker fee
    "KXACPI":         ("Economics", "US annual inflation"),
    "ACPICORE":       ("Economics", "Annual core inflation"),
    "FXEURO":         ("Economics", "EUR/USD"),
    "KXUSTYLD":       ("Economics", "Treasury yield"),
}

# Longshot definition
LONGSHOT_MAX = 0.20      # YES mid-life mid below this = longshot leg
# Maker realism haircuts (same as soft-market capacity study, for apples-to-apples).
QUEUE_CAPTURE = 0.25
TOUCH_PRESENCE = 0.60
SIDE_ENGAGE = 0.50       # maker on one side captures ~half the two-sided flow
CAPTURE_FRAC = QUEUE_CAPTURE * TOUCH_PRESENCE * SIDE_ENGAGE  # ~7.5% of life volume
# Maker fee on quadratic_with_maker_fees: ~25% of taker fee. Taker fee on Kalshi ~
# 0.07 * price * (1-price) per contract (quadratic). At p=0.10 that's ~0.0063/contract;
# maker pays 25% -> ~0.0016/contract. We apply per-leg below using its mid price.
EDGE_GROSS = 0.0097      # +0.97c/contract net adverse-selection (zero-fee), from advsel study


def get(path, params=None, retries=4):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # 4xx are deterministic (bad range/params) -- do not retry/backoff.
            if 400 <= e.code < 500:
                raise
            last = e
            time.sleep(1.2 * (2 ** i))
        except Exception as e:
            last = e
            time.sleep(1.2 * (2 ** i))
    raise last


def fv(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def ts(s):
    return int(datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def series_fee(tk):
    try:
        d = get("/series/" + tk)
        sr = d.get("series", d)
        return sr.get("fee_type", "quadratic")
    except Exception:
        return "unknown"


def settled_markets(tk, cap=120):
    out, cursor = [], None
    while True:
        p = {"series_ticker": tk, "status": "settled", "limit": 200}
        if cursor:
            p["cursor"] = cursor
        try:
            d = get("/markets", p)
        except Exception:
            break
        out.extend(d.get("markets", []))
        cursor = d.get("cursor")
        if not cursor or len(out) >= cap:
            break
    return out


def midlife_mid(tk, m):
    """Return (mid_life_yes_mid, life_volume_contracts) from candlesticks.
    mid_life_yes_mid = (yes_bid.close + yes_ask.close)/2 at the candle nearest the
    temporal midpoint of [open, close] that has a valid two-sided quote."""
    try:
        st, en = ts(m["open_time"]), ts(m["close_time"])
    except Exception:
        return None, 0.0
    if en <= st:
        return None, 0.0
    # Pick candle granularity by lifespan to bound payload: hourly for <=7d markets,
    # daily (1440) for season-long futures. Mid-life mid is robust to either.
    life_days = (en - st) / 86400.0
    period = 60 if life_days <= 7 else 1440
    try:
        c = get(f"/series/{tk}/markets/{m['ticker']}/candlesticks",
                {"start_ts": st, "end_ts": en, "period_interval": period})
    except Exception:
        return None, 0.0
    cs = c.get("candlesticks", [])
    if not cs:
        return None, 0.0
    mid_ts = (st + en) / 2.0
    life_vol = 0.0
    best = None
    best_dist = None
    for cd in cs:
        life_vol += fv(cd.get("volume_fp"))
        yb = cd.get("yes_bid", {})
        ya = cd.get("yes_ask", {})
        b = fv(yb.get("close_dollars"))
        a = fv(ya.get("close_dollars"))
        if b <= 0 and a <= 0:
            continue
        # require a sane two-sided quote
        if b > 0 and a > 0 and a >= b and a <= 1.0:
            mid = (a + b) / 2.0
            t = fv(cd.get("end_period_ts"))
            dist = abs(t - mid_ts)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = mid
    return best, life_vol


def main():
    rows = []        # per-leg: cat, series, ticker, fee, mid, life_vol, result(1/0)
    fee_cache = {}
    for tk, (cat, _desc) in SERIES.items():
        fee = fee_cache.get(tk) or series_fee(tk)
        fee_cache[tk] = fee
        ms = settled_markets(tk)
        n_long = 0
        for m in ms:
            if m.get("mve_collection_ticker"):
                continue
            if m.get("market_type") != "binary":
                continue
            res = m.get("result")
            if res not in ("yes", "no"):
                continue
            mid, lifevol = midlife_mid(tk, m)
            if mid is None:
                continue
            if mid >= LONGSHOT_MAX or mid <= 0.0:
                continue
            n_long += 1
            rows.append({
                "cat": cat, "series": tk, "ticker": m["ticker"], "fee": fee,
                "mid": mid, "life_vol": lifevol, "y": 1 if res == "yes" else 0,
            })
        sys.stderr.write(f"{tk} ({cat}) fee={fee}: {len(ms)} settled, {n_long} longshot legs\n")
        sys.stderr.flush()
    out = {"n_legs": len(rows), "rows": rows}
    with open("/tmp/cap2/_longshot_legs.json", "w") as fh:
        json.dump(out, fh)
    analyze(rows)


def wmean(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else 0.0


def bias_block(rows, label):
    if not rows:
        print(f"  {label}: (no legs)")
        return
    n = len(rows)
    mean_mid = sum(r["mid"] for r in rows) / n
    realized = sum(r["y"] for r in rows) / n
    bias = mean_mid - realized      # >0 => overpriced (priced higher than it resolves)
    # binomial SE on realized rate vs mean_mid as the null
    p = mean_mid
    se = math.sqrt(max(p * (1 - p), 1e-9) / n)
    z = bias / se if se > 0 else 0.0
    tot_vol = sum(r["life_vol"] for r in rows)
    print(f"  {label}: n={n}  mean_mid={mean_mid:.4f}  realized_YES={realized:.4f}  "
          f"OVERPRICE_bias={bias*100:+.2f}c  z={z:.1f}  life_vol_sum={tot_vol:,.0f}")
    return {"n": n, "mean_mid": mean_mid, "realized": realized, "bias": bias,
            "z": z, "tot_vol": tot_vol}


def analyze(rows):
    print("\n" + "=" * 78)
    print("KALSHI HIGH-VOLUME LONGSHOT OVERPRICING -- BIAS vs VOLUME TRADEOFF")
    print("=" * 78)
    print(f"Total longshot legs (mid-life YES mid < {LONGSHOT_MAX}): {len(rows)}")
    if not rows:
        return

    # Overall
    print("\n[1] OVERALL longshot overpricing (mean_mid - realized_YES):")
    bias_block(rows, "ALL legs")

    # Split by fee type
    print("\n[2] BY FEE TYPE (maker-fee series penalized):")
    zero = [r for r in rows if r["fee"] == "quadratic"]
    mfee = [r for r in rows if r["fee"] == "quadratic_with_maker_fees"]
    bias_block(zero, "zero-maker-fee (quadratic)")
    bias_block(mfee, "maker-fee (quadratic_with_maker_fees)")

    # Split by category
    print("\n[3] BY CATEGORY:")
    for cat in ("Sports", "Politics", "Economics"):
        bias_block([r for r in rows if r["cat"] == cat], cat)

    # THE KEY TRADEOFF: bias by life-volume quartile
    print("\n[4] BIAS vs VOLUME (quartiles by leg life-volume) -- does bias survive depth?")
    sv = sorted(rows, key=lambda r: r["life_vol"])
    n = len(sv)
    q = max(1, n // 4)
    for i, lab in enumerate(["Q1 (thinnest)", "Q2", "Q3", "Q4 (deepest)"]):
        seg = sv[i * q:(i + 1) * q] if i < 3 else sv[3 * q:]
        if seg:
            vlo, vhi = seg[0]["life_vol"], seg[-1]["life_vol"]
            bias_block(seg, f"{lab} [vol {vlo:,.0f}-{vhi:,.0f}]")

    # Same tradeoff, zero-fee only (the tradable universe)
    print("\n[5] BIAS vs VOLUME -- ZERO-MAKER-FEE legs only (the tradable universe):")
    sv = sorted(zero, key=lambda r: r["life_vol"])
    n = len(sv)
    q = max(1, n // 4)
    quart_stats = []
    for i, lab in enumerate(["Q1 (thinnest)", "Q2", "Q3", "Q4 (deepest)"]):
        seg = sv[i * q:(i + 1) * q] if i < 3 else sv[3 * q:]
        if seg:
            vlo, vhi = seg[0]["life_vol"], seg[-1]["life_vol"]
            st = bias_block(seg, f"{lab} [vol {vlo:,.0f}-{vhi:,.0f}]")
            if st:
                st["seg"] = seg
                quart_stats.append(st)

    # CAPACITY: $/month, split by fee type, using a concrete annual harvest window.
    print("\n[6b] CAPACITY by fee type -- annualized $/month (CAPTURE_FRAC=%.1f%%):" %
          (CAPTURE_FRAC * 100))
    print("    volume_fp = actual contracts (verified vs summed trade count_fp).")
    for fee_lab, fee_rows in (("zero-maker-fee", zero), ("maker-fee", mfee)):
        if not fee_rows:
            continue
        tot_vol = sum(r["life_vol"] for r in fee_rows)
        capt = tot_vol * CAPTURE_FRAC
        # Net edge/contract: zero-fee = +0.97c (advsel study). Maker-fee = +0.97c minus
        # 25% of taker fee. Taker fee ~= 0.07*p*(1-p); at the avg longshot mid that's
        # tiny but we apply it per-leg.
        if fee_lab == "zero-maker-fee":
            edge = capt * EDGE_GROSS
            mf_note = ""
        else:
            # per-leg maker fee = 0.25 * 0.07 * p*(1-p)
            net = 0.0
            for r in fee_rows:
                p = r["mid"]
                mfee_c = 0.25 * 0.07 * p * (1 - p)
                net += r["life_vol"] * CAPTURE_FRAC * max(EDGE_GROSS - mfee_c, 0.0)
            edge = net
            mf_note = " (after 25%-of-taker maker fee)"
        # These legs are seasonal/annual -> assume ~1 settlement cycle/year => /12 for $/mo.
        print(f"    {fee_lab}: n={len(fee_rows)} legs, life_vol={tot_vol:,.0f} contracts, "
              f"capturable={capt:,.0f}")
        print(f"       lifetime gross harvest = ${edge:,.0f}{mf_note}; "
              f"if these recur ~annually => ~${edge/12:,.0f}/month")

    # CAPACITY: $/month if you harvested only the high-volume zero-fee longshots
    print("\n[6] CAPACITY -- $/month from harvesting high-volume zero-fee longshots:")
    print("    Model: capturable contracts/leg = life_vol * CAPTURE_FRAC (%.1f%%)" %
          (CAPTURE_FRAC * 100))
    print("    Net edge/contract = +0.97c (zero-fee) from adverse-selection study.")
    # Use top-quartile (deepest) zero-fee legs as the high-volume harvest universe.
    if quart_stats:
        deep = quart_stats[-1]["seg"]
        tot_vol = sum(r["life_vol"] for r in deep)
        n_legs = len(deep)
        # how long do these markets live, on average? approximate by category cadence;
        # we estimate legs/month available. Sports futures legs settle ~ once/season;
        # use realized leg turnover: total capturable $ / typical harvest window.
        capturable = tot_vol * CAPTURE_FRAC
        edge_dollars = capturable * EDGE_GROSS
        # bias-adjusted edge: if realized overprice bias is B (in $), the per-contract
        # edge for SELLING the longshot NO is min(spread-edge, bias). Use measured bias
        # of the deepest quartile as a sanity cap.
        b = quart_stats[-1]["bias"]
        print(f"    Deepest-quartile zero-fee legs: n={n_legs}, "
              f"summed life_vol={tot_vol:,.0f} contracts")
        print(f"    Capturable contracts (lifetime, all these legs) = {capturable:,.0f}")
        print(f"    Gross harvest @0.97c = ${edge_dollars:,.0f} TOTAL over all these legs' lives")
        print(f"    Measured overprice bias in deepest quartile = {b*100:+.2f}c/contract")
        # Translate to $/month: these legs span the full data window. Estimate window.
        # Sports futures are seasonal (settle ~annually); we annualize crudely.
        print(f"    NOTE: these legs span ~1-2 settlement cycles; see .md for $/month framing.")

    # Per-series depth summary for the deepest series
    print("\n[7] DEEPEST legs (top 15 by life-volume):")
    for r in sorted(rows, key=lambda r: -r["life_vol"])[:15]:
        notional = r["life_vol"] * r["mid"]
        print(f"    {r['ticker']:<28} {r['cat']:<10} fee={r['fee']:<28} "
              f"mid={r['mid']:.3f} y={r['y']} life_vol={r['life_vol']:,.0f} "
              f"~${notional:,.0f} notional")


if __name__ == "__main__":
    main()
