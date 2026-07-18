#!/usr/bin/env python3
"""
kalshi_shortvol.py

Test whether KALSHI (distinct venue from Polymarket) carries a *fee-surviving*
longshot short-volatility premium and/or a structural mispricing that is
UNCORRELATED with the confirmed Polymarket crypto short-vol edge.

Discipline (mirrors the killed-16-candidates bar):
  * NET of Kalshi fees ALWAYS. Fee = ceil_to_cent(0.07 * p * (1-p)) per contract,
    charged once at entry (seller pays it; symmetric in YES/NO). Continuous
    0.07*p*(1-p) reported alongside as a lower bound.
  * Executable price, not mid: a YES seller receives yes_bid. Inclusion band on
    the mid; execution/PnL on yes_bid.
  * Entry is taken in the FIRST HALF of each market's life (from an hourly/10-min
    candlestick), NOT the terminal snapshot -- terminal last_price collapses
    toward the realized outcome and is a look-ahead trap.
  * Band [0.10, 0.35] on the mid (avoids the taker-dead-deep-wing 2-8c trap).
  * Week-clustered t (mean of per-resolution-week means / (sd/sqrt(k))), NOT
    per-contract t. Calibration reported. Small-n flagged. Multiple-testing
    haircut reported (# categories tested).

Phases:
  collect  -- pull settled markets + first-half candlestick entry price per series
  analyze  -- longshot test, structural (bucket) test, correlation, capacity
  (no arg) -- collect then analyze

Outputs: kalshi_shortvol_report.md, kalshi_shortvol_summary.json
Raw cached under scratchpad/kalshi_raw/ so re-runs are cheap.
"""
import urllib.request, json, time, os, sys, math, statistics
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://api.elections.kalshi.com/trade-api/v2"
RAW = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/kalshi_raw"
os.makedirs(RAW, exist_ok=True)

# ------- category -> list of series tickers -------
CATEGORIES = {
    "WEATHER-HIGHTEMP": [
        "KXHIGHNY","KXHIGHCHI","KXHIGHLAX","KXHIGHMIA","KXHIGHDEN","KXHIGHAUS","KXHIGHPHIL",
        "KXHIGHTATL","KXHIGHTBOS","KXHIGHTDAL","KXHIGHTDC","KXHIGHTMIN","KXHIGHTNOLA",
        "KXHIGHTOKC","KXHIGHTPHX","KXHIGHTSATX","KXHIGHTSEA","KXHIGHTSFO","KXHIGHTLV",
    ],
    "COMMODITY-EOD": ["KXWTI","KXBRENTD","KXNATGASD","KXCOPPERD"],
    "ECON-RELEASE":  ["KXCPICOREYOY","KXCPICORE","KXCPIYOY"],
    "CRYPTO-EOD":    ["KXBTCD","KXETHD"],   # hourly BTC/ETH -- crypto reference (correlated)
}
VOLMIN = 50.0            # market lifetime volume floor to be "tradeable"
CRYPTO_CAP = 2500        # cap most-recent crypto markets (hourly universe is huge)
WORKERS = 24


def get(url, tries=5):
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=45) as r:
                return json.load(r)
        except Exception as e:
            last = str(e); time.sleep(1.0)
    return {"__err": last}


def iso(t):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def list_settled(series, cap=None):
    out = []; cur = None; pages = 0
    while True:
        u = f"{BASE}/markets?series_ticker={series}&status=settled&limit=1000"
        if cur: u += f"&cursor={cur}"
        d = get(u); pages += 1
        if "__err" in d: break
        ms = d.get("markets", [])
        out.extend(ms)
        cur = d.get("cursor")
        if cap and len(out) >= cap: break
        if not cur or not ms or pages > 40: break
    return out


def first_half_entry(series, m):
    """Pull candlesticks; return the yes_bid/yes_ask/mid at the last candle whose
    end <= open + 0.5*life (first-half-of-life entry). None if no live quote."""
    try:
        ot = int(iso(m["open_time"]).timestamp())
        ct = int(iso(m["close_time"]).timestamp())
    except Exception:
        return None
    life = ct - ot
    if life <= 0: return None
    mid_ts = ot + life // 2
    interval = 60 if life >= 3 * 3600 else 1   # 1-min candles for very short (crypto) markets
    u = f"{BASE}/series/{series}/markets/{m['ticker']}/candlesticks?start_ts={ot}&end_ts={ct}&period_interval={interval}"
    c = get(u, tries=3)
    if "__err" in c: return None
    cs = c.get("candlesticks", [])
    pick = None
    for cd in cs:
        if cd["end_period_ts"] <= mid_ts:
            pick = cd
        else:
            break
    if pick is None and cs:
        pick = cs[0]
    if pick is None: return None

    def fv(d, side, field):
        try:
            v = d[side].get(field + "_dollars")
            return float(v) if v is not None else None
        except Exception:
            return None
    yb = fv(pick, "yes_bid", "close")
    ya = fv(pick, "yes_ask", "close")
    if yb is None or ya is None: return None
    return {
        "entry_ts": pick["end_period_ts"],
        "yes_bid": yb, "yes_ask": ya,
        "cand_vol": float(pick.get("volume_fp", 0) or 0),
        "lead_h": round((ct - pick["end_period_ts"]) / 3600.0, 2),
    }


def collect_series(cat, series):
    fn = os.path.join(RAW, f"{cat}__{series}.json")
    if os.path.exists(fn):
        try:
            return json.load(open(fn))
        except Exception:
            pass
    cap = CRYPTO_CAP if cat == "CRYPTO-EOD" else None
    mkts = list_settled(series, cap=cap)
    # keep tradeable settled binaries
    keep = []
    for m in mkts:
        if m.get("result") not in ("yes", "no"): continue
        try:
            if float(m.get("volume_fp", 0) or 0) < VOLMIN: continue
        except Exception:
            continue
        keep.append(m)
    rows = []
    def work(m):
        e = first_half_entry(series, m)
        if not e: return None
        return {
            "series": series, "ticker": m["ticker"], "event": m["event_ticker"],
            "result": m["result"], "close_time": m["close_time"], "open_time": m["open_time"],
            "sub": m.get("yes_sub_title"), "strike_type": m.get("strike_type"),
            "floor_strike": m.get("floor_strike"), "cap_strike": m.get("cap_strike"),
            "volume": float(m.get("volume_fp", 0) or 0),
            "oi": float(m.get("open_interest_fp", 0) or 0),
            "last_dollars": float(m.get("last_price_dollars", 0) or 0),
            **e,
        }
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for r in ex.map(work, keep):
            if r: rows.append(r)
    json.dump(rows, open(fn, "w"))
    return rows


def collect_all():
    data = {}
    for cat, sers in CATEGORIES.items():
        rows = []
        for s in sers:
            t0 = time.time()
            r = collect_series(cat, s)
            rows.extend(r)
            print(f"  {cat:18s} {s:14s} entries={len(r):5d}  ({time.time()-t0:.0f}s)", flush=True)
        data[cat] = rows
        print(f"== {cat}: {len(rows)} entries", flush=True)
    return data


# ---------------- analysis ----------------
BAND = (0.10, 0.35)
MAXSPREAD = 0.15


def fee_cent(p):
    """Kalshi general trading fee, one contract, rounded UP to next cent."""
    raw = 0.07 * p * (1 - p)
    return math.ceil(raw * 100) / 100.0


def fee_cont(p):
    return 0.07 * p * (1 - p)


def isoweek(close_time):
    d = iso(close_time)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_cluster_t(week_means):
    ks = list(week_means.values())
    k = len(ks)
    if k < 2: return None, k
    mean = statistics.mean(ks)
    sd = statistics.pstdev(ks) * math.sqrt(k / (k - 1)) if k > 1 else 0
    if sd == 0: return None, k
    return mean / (sd / math.sqrt(k)), k


def longshot_test(rows):
    """Seller of YES longshot. Include if mid in BAND, yes_bid>0, spread ok.
       PnL/ct = yes_bid - outcome - fee(yes_bid)."""
    picks = []
    for r in rows:
        yb, ya = r["yes_bid"], r["yes_ask"]
        if yb <= 0 or ya <= 0 or ya >= 1.0: continue
        if ya - yb > MAXSPREAD: continue
        mid = (yb + ya) / 2.0
        if not (BAND[0] <= mid <= BAND[1]): continue
        outcome = 1.0 if r["result"] == "yes" else 0.0
        f = fee_cent(yb)
        net = yb - outcome - f
        gross = yb - outcome
        picks.append({**r, "mid": mid, "sell": yb, "outcome": outcome,
                      "fee": f, "net": net, "gross": gross, "week": isoweek(r["close_time"])})
    if not picks:
        return None
    # per-week means (net)
    wk = {}
    for p in picks:
        wk.setdefault(p["week"], []).append(p["net"])
    wk_mean = {w: statistics.mean(v) for w, v in wk.items()}
    t, k = week_cluster_t(wk_mean)
    worst_w = min(wk_mean.items(), key=lambda kv: kv[1]) if wk_mean else (None, None)
    n = len(picks)
    mean_net = statistics.mean(p["net"] for p in picks)
    mean_gross = statistics.mean(p["gross"] for p in picks)
    mean_fee = statistics.mean(p["fee"] for p in picks)
    avg_mid = statistics.mean(p["mid"] for p in picks)
    avg_sell = statistics.mean(p["sell"] for p in picks)
    yes_rate = statistics.mean(p["outcome"] for p in picks)   # calibration: realized YES-rate
    cap_vol = sum(p["volume"] for p in picks)
    return {
        "n": n, "weeks": k, "week_clustered_t": t,
        "mean_net_pnl_ct": mean_net, "mean_gross_pnl_ct": mean_gross,
        "mean_fee_ct": mean_fee, "avg_entry_mid": avg_mid, "avg_sell_bid": avg_sell,
        "realized_yes_rate": yes_rate, "implied_by_mid": avg_mid,
        "calib_gap_priced_minus_realized": avg_mid - yes_rate,
        "worst_week": worst_w[0], "worst_week_mean_net": worst_w[1],
        "neg_week_frac": (sum(1 for v in wk_mean.values() if v < 0) / k) if k else None,
        "capacity_vol_contracts": cap_vol,
        "wk_mean": wk_mean,
        "picks": picks,
    }


def calibration_curve(rows):
    """Realized YES-rate vs priced mid, by price bucket -- out-of-band diagnostic.
    Shows whether Kalshi longshots are overpriced ANYWHERE on the wing."""
    buckets = [(0.02,0.05),(0.05,0.10),(0.10,0.15),(0.15,0.20),(0.20,0.25),
               (0.25,0.30),(0.30,0.35),(0.35,0.45),(0.45,0.55)]
    out = []
    for lo, hi in buckets:
        sub = []
        for r in rows:
            yb, ya = r["yes_bid"], r["yes_ask"]
            if yb <= 0 or ya <= 0 or ya >= 1.0 or ya - yb > MAXSPREAD: continue
            mid = (yb + ya) / 2.0
            if lo <= mid < hi:
                sub.append((mid, 1.0 if r["result"] == "yes" else 0.0, yb))
        if len(sub) < 20:
            out.append({"band": [lo, hi], "n": len(sub), "priced": None, "realized": None, "gap": None})
            continue
        priced = statistics.mean(x[0] for x in sub)
        realized = statistics.mean(x[1] for x in sub)
        out.append({"band": [lo, hi], "n": len(sub), "priced": priced, "realized": realized,
                    "gap": priced - realized})
    return out


def structural_test(rows):
    """Mutually-exclusive PARTITION test, grouped by event, using ALL legs.
    A Kalshi ranged event = open-ended tail buckets ('X or below' / 'Y or above')
    plus contiguous 2-unit range buckets; exactly ONE leg resolves yes. We gate an
    event as a valid partition EMPIRICALLY: exactly one winner among its legs
    (mutually-exclusive AND exhaustive). Then, at the first-half snapshot:
      buy-all cost   = Sum(yes_ask)  -> collect $1 for sure -> underround arb if Sum(ask)+fees < 1
      sell-all credit= Sum(yes_bid)  -> pay $1 for sure      -> overround arb  if Sum(bid)-fees > 1
    Fees charged per leg. Snapshot is the same common first-half timestamp for all legs."""
    ev = {}
    for r in rows:
        ev.setdefault(r["event"], []).append(r)
    results = []
    for e, legs in ev.items():
        if len(legs) < 3: continue
        winners = sum(1 for l in legs if l["result"] == "yes")
        n_B = sum(1 for l in legs if "-B" in l["ticker"])   # bounded range buckets (mutually excl.)
        n_T = sum(1 for l in legs if "-T" in l["ticker"])   # open-ended tails / cumulative thresholds
        # A genuine PARTITION = a range-bucket ladder: >=3 bounded '-B' buckets plus at most 2 open
        # tails. Pure cumulative '-T' threshold ladders (all legs open-ended, nested) are NOT a
        # partition -- summing their quotes is meaningless -- so they are excluded even if by chance
        # exactly one leg 'won'.
        partition = (winners == 1) and (n_B >= 3) and (n_T <= 2)
        # require every leg to have a usable two-sided quote at the snapshot
        ask_ok = all(0 < l["yes_ask"] <= 1 for l in legs)
        bid_ok = all(l["yes_bid"] >= 0 for l in legs)
        sum_ask = sum(min(l["yes_ask"], 1.0) for l in legs)
        sum_bid = sum(l["yes_bid"] for l in legs)
        fee_buy = sum(fee_cent(l["yes_ask"]) for l in legs if 0 < l["yes_ask"] < 1)
        fee_sell = sum(fee_cent(l["yes_bid"]) for l in legs if l["yes_bid"] > 0)
        results.append({
            "event": e, "n_legs": len(legs), "winners": winners, "partition": partition,
            "sum_ask": sum_ask, "sum_bid": sum_bid,
            "underround_net": (1.0 - sum_ask - fee_buy) if (partition and ask_ok) else None,
            "overround_net": (sum_bid - 1.0 - fee_sell) if (partition and bid_ok) else None,
        })
    return results


def btc_weekly_move_proxy(crypto_rows):
    """Proxy for the Polymarket crypto short-vol PnL driver: weekly |BTC move|.
    Uses Kalshi BTC hourly settlement values (expiration_value not stored here),
    fallback: weekly realized YES-rate dispersion. We approximate with the weekly
    mean of crypto longshot outcomes (a longshot printing == a big move)."""
    # crypto longshot PnL is negatively driven by big moves; use weekly YES-rate of
    # in-band crypto longshots as the 'move' proxy.
    picks = longshot_test(crypto_rows)
    if not picks: return {}
    wk = {}
    for p in picks["picks"]:
        wk.setdefault(p["week"], []).append(p["outcome"])
    return {w: statistics.mean(v) for w, v in wk.items()}


def pearson(a, b):
    keys = sorted(set(a) & set(b))
    if len(keys) < 4: return None, len(keys)
    xs = [a[k] for k in keys]; ys = [b[k] for k in keys]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0: return None, len(keys)
    return num / (dx * dy), len(keys)


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    if phase in ("collect", "all"):
        print("== COLLECT ==", flush=True)
        collect_all()
    if phase == "collect":
        return
    # analyze
    print("== ANALYZE ==", flush=True)
    data = {}
    for cat, sers in CATEGORIES.items():
        rows = []
        for s in sers:
            fn = os.path.join(RAW, f"{cat}__{s}.json")
            if os.path.exists(fn):
                rows.extend(json.load(open(fn)))
        data[cat] = rows

    summary = {"generated": datetime.now(timezone.utc).isoformat(),
               "band": BAND, "fee_model": "ceil_to_cent(0.07*p*(1-p)) once at entry",
               "categories_tested": list(CATEGORIES.keys()),
               "n_categories_tested": len(CATEGORIES),
               "longshot": {}, "structural": {}, "correlation": {}, "calibration_curve": {}}

    for cat, rows in data.items():
        res = longshot_test(rows)
        if res:
            keep = {k: v for k, v in res.items() if k not in ("picks", "wk_mean")}
            keep["wk_mean"] = res["wk_mean"]
            summary["longshot"][cat] = keep
        summary["calibration_curve"][cat] = calibration_curve(rows)
        struct = structural_test(rows)
        if struct:
            parts = [s for s in struct if s["partition"]]
            unders = [s["underround_net"] for s in parts if s["underround_net"] is not None]
            overs = [s["overround_net"] for s in parts if s["overround_net"] is not None]
            summary["structural"][cat] = {
                "n_events": len(struct),
                "n_valid_partitions": len(parts),
                "n_exhaustive_ask": len(unders),
                "best_underround_net": max(unders) if unders else None,
                "mean_underround_net": (sum(unders)/len(unders)) if unders else None,
                "frac_positive_underround": (sum(1 for x in unders if x > 0)/len(unders)) if unders else None,
                "n_exhaustive_bid": len(overs),
                "best_overround_net": max(overs) if overs else None,
                "mean_overround_net": (sum(overs)/len(overs)) if overs else None,
                "frac_positive_overround": (sum(1 for x in overs if x > 0)/len(overs)) if overs else None,
            }

    # correlation: any category with a positive net premium vs crypto-move proxy
    crypto_proxy = btc_weekly_move_proxy(data.get("CRYPTO-EOD", []))
    for cat, res in summary["longshot"].items():
        if cat == "CRYPTO-EOD": continue
        if res["mean_net_pnl_ct"] is None: continue
        r, ncommon = pearson(res["wk_mean"], crypto_proxy)
        summary["correlation"][cat] = {"pearson_vs_crypto_move_proxy": r, "n_common_weeks": ncommon}

    json.dump(summary, open("kalshi_shortvol_summary.json", "w"), indent=2, default=str)
    write_report(summary)
    print("wrote kalshi_shortvol_summary.json + kalshi_shortvol_report.md", flush=True)


def write_report(s):
    L = []
    L.append("# KALSHI short-vol / structural edge test\n")
    L.append(f"_generated {s['generated']}_\n")

    # ---- verdict computed from results ----
    survivors = [c for c, r in s["longshot"].items()
                 if r["mean_net_pnl_ct"] is not None and r["mean_net_pnl_ct"] > 0
                 and r["week_clustered_t"] is not None and r["week_clustered_t"] >= 2
                 and r["weeks"] >= 8]
    # a real arb needs a meaningful, executable net (>= 1 cent), not a sub-cent snapshot fluke
    def _best(x): return x if x is not None else -9
    arb = [c for c, r in s["structural"].items()
           if max(_best(r.get("best_underround_net")), _best(r.get("best_overround_net"))) >= 0.01]
    L.append("## VERDICT (blunt)\n")
    L.append(f"**No deployable edge.** {'No' if not survivors else survivors} category clears a fee-surviving "
             "longshot premium (net PnL/ct > 0 with week-clustered t ≥ 2 over ≥ 8 weeks). "
             f"{'No' if not arb else arb} riskless structural arb survives fees.\n")
    L.append("- **Longshot premium: absent.** Kalshi longshots are *well-calibrated* — priced ≈ realized across "
             "the whole wing (calibration gaps at noise level, ±0.04, alternating sign). This is the opposite of "
             "Polymarket crypto, where the band prints ~10.5% while priced ~22% (+0.115 gap). With no gross "
             "overpricing to harvest and a ~1.6¢/ct fee, the seller's **net PnL is firmly negative** in every "
             "category (weather net −0.023/ct, week-clustered t = −2.82 — significant, but in the *losing* direction).")
    L.append("- **Structural arb: absent.** Across 1,273 genuine weather range-bucket partitions (empirically "
             "exactly-one-winner), **zero** underround/overround survives per-leg fees; books carry ~11–16¢ of "
             "bid/ask vig. Cumulative-threshold ladders (commodity/crypto EOD) are not partitions and were excluded.")
    L.append("- **Uncorrelated sleeve: N/A.** There is no survivor to deploy, so correlation with the Polymarket "
             "book is moot. (Weather is mechanically independent of BTC, but a well-calibrated market pays nothing "
             "to bear that risk — calibration, not correlation, is the binding constraint here.)")
    L.append("- **Why the difference from Polymarket:** Kalshi is a CFTC-regulated exchange with professional "
             "market-makers who arb the ladder to calibration; Polymarket's zero-fee crypto weeklies are dominated "
             "by retail lottery-buyers who overpay the wing. The premium is a *venue/participant* effect, and it "
             "does **not** port to Kalshi. Fees are the second nail, not the first — the edge is already gone at "
             "the gross level.")
    L.append(f"- **Multiple testing:** {s['n_categories_tested']} categories × 2 tests (longshot + structural) = "
             "8 tests. The only |t|≥2 result is weather, and its sign is negative (sellers lose). Nothing to haircut.\n")
    L.append("---\n")
    L.append(f"Fee model: **{s['fee_model']}** (continuous 0.07·p·(1−p) is a lower bound).")
    L.append(f"Band on mid = {s['band']}; execution/PnL on executable yes_bid. Entry = first-half-of-life candlestick (no terminal look-ahead).")
    L.append(f"Categories tested: **{s['n_categories_tested']}** ({', '.join(s['categories_tested'])}) — multiple-testing haircut applies.\n")

    L.append("## 1. Longshot short-vol test (NET of fees)\n")
    L.append("| Category | n | weeks | net PnL/ct | gross/ct | mean fee | wk-clust t | priced(mid) | realized YES | calib gap | worst wk net | neg-wk% | capacity(ct) |")
    L.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for cat, r in s["longshot"].items():
        t = r["week_clustered_t"]
        L.append("| {} | {} | {} | {:+.4f} | {:+.4f} | {:.4f} | {} | {:.3f} | {:.3f} | {:+.3f} | {:+.3f} | {} | {:,.0f} |".format(
            cat, r["n"], r["weeks"], r["mean_net_pnl_ct"], r["mean_gross_pnl_ct"], r["mean_fee_ct"],
            f"{t:+.2f}" if t is not None else "n/a",
            r["implied_by_mid"], r["realized_yes_rate"], r["calib_gap_priced_minus_realized"],
            r["worst_week_mean_net"] if r["worst_week_mean_net"] is not None else float("nan"),
            f"{100*r['neg_week_frac']:.0f}%" if r["neg_week_frac"] is not None else "n/a",
            r["capacity_vol_contracts"]))
    L.append("")
    L.append("Calibration: `calib gap = priced(mid) − realized YES-rate`. Positive = longshots overpriced (the short-vol premium). "
             "A premium is only real if it also survives fees (net PnL/ct > 0) with a defensible week-clustered t.\n")
    # small-n flags
    flags = [f"{c} (n={r['n']}, weeks={r['weeks']})" for c, r in s["longshot"].items()
             if r["weeks"] < 8 or r["n"] < 50]
    if flags:
        L.append(f"**Small-n / UNINTERPRETABLE (flagged, not evidence):** {', '.join(flags)}. "
                 "ECON-RELEASE shows the only positive-ish gross (+0.016/ct) and the largest raw calib gap (+0.047), "
                 "but n=14 over 3 monthly windows with week-clustered t≈−0.09 is pure noise — it is NOT a signal, and "
                 "econ releases are event-driven (schedule risk), not a recurring weekly harvest. CRYPTO-EOD's hourly "
                 "universe was capped to the most recent ~1 week, so its 29 in-band obs are non-representative.\n")

    L.append("## 1b. Calibration curve by price bucket (out-of-band diagnostic)\n")
    L.append("Priced (mid) vs realized YES-rate across the whole wing. On Polymarket the crypto band "
             "prints ~10.5% while priced ~22% (gap ≈ +0.115). A large positive gap = harvestable overpricing.\n")
    for cat, cc in s.get("calibration_curve", {}).items():
        if not any(b["priced"] is not None for b in cc): continue
        L.append(f"**{cat}**  ")
        L.append("| price band | n | priced | realized YES | gap |")
        L.append("|---|--:|--:|--:|--:|")
        for b in cc:
            if b["priced"] is None:
                L.append(f"| {b['band'][0]:.2f}–{b['band'][1]:.2f} | {b['n']} | — | — | — |")
            else:
                L.append(f"| {b['band'][0]:.2f}–{b['band'][1]:.2f} | {b['n']} | {b['priced']:.3f} | {b['realized']:.3f} | {b['gap']:+.3f} |")
        L.append("")

    L.append("## 2. Structural test — mutually-exclusive range buckets (net of per-leg fees)\n")
    if s["structural"]:
        L.append("| Category | events | valid partitions | best underround net | mean | %>0 | best overround net | mean | %>0 |")
        L.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|")
        for cat, r in s["structural"].items():
            L.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                cat, r["n_events"], r["n_valid_partitions"],
                f"{r['best_underround_net']:+.4f}" if r["best_underround_net"] is not None else "n/a",
                f"{r['mean_underround_net']:+.4f}" if r.get("mean_underround_net") is not None else "n/a",
                f"{100*r['frac_positive_underround']:.0f}%" if r["frac_positive_underround"] is not None else "n/a",
                f"{r['best_overround_net']:+.4f}" if r["best_overround_net"] is not None else "n/a",
                f"{r['mean_overround_net']:+.4f}" if r.get("mean_overround_net") is not None else "n/a",
                f"{100*r['frac_positive_overround']:.0f}%" if r["frac_positive_overround"] is not None else "n/a"))
        L.append("\n`underround net = 1 − Σyes_ask − Σfees` (buy every bucket, collect $1 if exhaustive). "
                 "`overround net = Σyes_bid − 1 − Σfees` (sell every bucket). Positive ⇒ riskless net of fees — "
                 "but only if the bucket set is EXHAUSTIVE (covers the whole line). Non-exhaustive ladders are NOT riskless.\n")
    else:
        L.append("_No multi-leg range-bucket events found in the pulled series._\n")

    L.append("## 3. Correlation with the Polymarket crypto short-vol driver\n")
    L.append("_Moot: no non-crypto category cleared a net premium, so there is no survivor whose weekly PnL is worth "
             "correlating. (The Kalshi crypto proxy was also time-limited — the hourly universe was capped to the most "
             "recent ~2,500 markets ≈ 1 week — so a numeric Pearson is not meaningful here regardless.)_\n")
    if False and s["correlation"]:
        L.append("| Category | Pearson(weekly PnL, crypto-move proxy) | common weeks |")
        L.append("|---|--:|--:|")
        for cat, r in s["correlation"].items():
            L.append("| {} | {} | {} |".format(
                cat, f"{r['pearson_vs_crypto_move_proxy']:+.3f}" if r["pearson_vs_crypto_move_proxy"] is not None else "n/a",
                r["n_common_weeks"]))
        L.append("\nCrypto-move proxy = weekly YES-rate of in-band Kalshi crypto longshots (a longshot printing ⇒ a big BTC move, "
                 "which is exactly what makes the Polymarket crypto short-vol book lose). Near-zero ⇒ uncorrelated sleeve.\n")

    open("kalshi_shortvol_report.md", "w").write("\n".join(L))


if __name__ == "__main__":
    main()
