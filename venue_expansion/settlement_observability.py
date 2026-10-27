#!/usr/bin/env python3
"""settlement_observability.py -- executes SETTLEMENT_OBSERVABILITY_SPEC.md (frozen 2026-10-27).

A MEASUREMENT of four data feeds against the official Kalshi `expiration_value` (NWS CLI).  No prices,
no trading rule, no parameters tuned against the official value.

Reused, NOT re-derived (spec anchor a): from finality_B.py
  * build_universe()  -- settled-market universe (live /markets UNION /historical/markets), the verified
                         station->standard-offset map, the `close_time == LST midnight` check
                         (close_hour_does_not_match_standard_offset skip), the LST day window
                         [day_start, day_end] = [close rounded to hour - 24h, close rounded to hour]
  * window_obs()/obs_series(), pick_source rules -- cached IEM 1-minute and routine hourly observations
Own cache: cache/settlement_obs/  (never writes into cache/finality/*).

Stages:  python settlement_observability.py fetch     (METAR text per station-month, daily.json per station-month)
         python settlement_observability.py analyze   (writes out/settlement_observability.{json,md})
"""
from __future__ import annotations
import collections, datetime as dt, json, math, os, random, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import finality_B as FB                      # noqa: E402  (module-level code there is definitions only)

CACHE = os.path.join(HERE, "cache", "settlement_obs")
OUT_JSON = os.path.join(HERE, "out", "settlement_observability.json")
OUT_MD = os.path.join(HERE, "out", "settlement_observability.md")
IEMR = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
IEMD = "https://mesonet.agron.iastate.edu/api/1/daily.json"
UA = "settlement-observability-research/1.0 (read-only measurement; contact dgkenn@bu.edu)"
SEED = 20261027

# IEM network per station (state ASOS network; verified live for MDW/NYC/EWR 2026-10-27, rest verified by the
# fetch stage -- a station returning zero rows is reported, not silently dropped).
NETWORK = {"ATL": "GA_ASOS", "AUS": "TX_ASOS", "BOS": "MA_ASOS", "DCA": "VA_ASOS", "DEN": "CO_ASOS",
           "DFW": "TX_ASOS", "EWR": "NJ_ASOS", "HOU": "TX_ASOS", "LAS": "NV_ASOS", "LAX": "CA_ASOS",
           "MDW": "IL_ASOS", "MIA": "FL_ASOS", "MSP": "MN_ASOS", "MSY": "LA_ASOS", "NYC": "NY_ASOS",
           "OKC": "OK_ASOS", "PHL": "PA_ASOS", "PHX": "AZ_ASOS", "SAN": "CA_ASOS", "SAT": "TX_ASOS",
           "SDF": "KY_ASOS", "SEA": "WA_ASOS", "SFO": "CA_ASOS", "TTN": "NJ_ASOS"}
MONTHS = [(2026, m) for m in range(5, 11)]          # May..Oct 2026 (universe closes 2026-05-23 .. 2026-10-20)
END_CAP = dt.date(2026, 10, 23)                      # exclusive; observations cached by finality end 2026-10-22

# ----------------------------------------------------------------------------------------------- http
_last = [0.0]
def http_text(url, tries=6, gap=1.2, timeout=180):
    for i in range(tries):
        d = time.time() - _last[0]
        if d < gap:
            time.sleep(gap - d)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                return fh.read().decode("utf-8", "replace")
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (400, 404, 422) or i == tries - 1:
                raise
            time.sleep(min(90, 3 * 2 ** i))

def jload(p):
    with open(p) as fh:
        return json.load(fh)

def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(o, fh)
    os.replace(tmp, p)

def month_range(y, m):
    a = dt.date(y, m, 1)
    b = dt.date(y + (m == 12), m % 12 + 1, 1)
    return a, min(b, END_CAP)

def stations():
    return sorted({v[0] for v in FB.SERIES_MAP.values()})

def fetch_metar(st, y, m):
    p = os.path.join(CACHE, "metar", f"{st}_{y}{m:02d}.json")
    if os.path.exists(p):
        return jload(p)
    a, b = month_range(y, m)
    u = (f"{IEMR}?station={st}&data=metar&year1={a.year}&month1={a.month}&day1={a.day}"
         f"&year2={b.year}&month2={b.month}&day2={b.day}&tz=UTC&format=onlycomma&latlon=no"
         "&report_type=3&report_type=4")
    txt = http_text(u)
    rows = []
    for l in txt.splitlines():
        p3 = l.split(",", 2)
        if len(p3) < 3 or p3[0] == "station":
            continue
        rows.append([p3[1], p3[2]])
    jdump({"url": u, "n": len(rows), "rows": rows}, p)
    return jload(p)

def fetch_daily(st, y, m):
    p = os.path.join(CACHE, "daily", f"{st}_{y}{m:02d}.json")
    if os.path.exists(p):
        return jload(p)
    u = f"{IEMD}?station={st}&network={NETWORK[st]}&year={y}&month={m}"
    txt = http_text(u)
    d = json.loads(txt)
    keep = [{k: r.get(k) for k in ("station", "date", "max_tmpf", "min_tmpf", "tmpf_est")} for r in d.get("data", [])]
    jdump({"url": u, "n": len(keep), "rows": keep}, p)
    return jload(p)

def cmd_fetch():
    # seeded shuffled order, never re-sorted (any truncated prefix is a uniform random subsample of stations)
    sts = stations()
    random.Random(SEED).shuffle(sts)
    jdump(sts, os.path.join(CACHE, "station_order.json"))
    for st in sts:
        for (y, m) in MONTHS:
            r = fetch_metar(st, y, m)
            d = fetch_daily(st, y, m)
            print(st, y, m, "metar_rows", r["n"], "daily_rows", d["n"], flush=True)


# ============================================================================================== decoding
# Groups are matched ONLY as whitespace-delimited tokens AFTER the first `RMK`, anchored (fullmatch).
#   1STTT  6-hour max   (S: 0 +, 1 -; TTT tenths degC)
#   2STTT  6-hour min
#   4SxxxSnnn  24-hour max/min (9 chars)
# Not matched (by construction): 5xxxx pressure tendency, T-group `T0289 0194`, 6xxxx/7xxxx precip, 9xxxx, SLPnnn.
RE6MAX = re.compile(r"1([01])(\d{3})")
RE6MIN = re.compile(r"2([01])(\d{3})")
RE24 = re.compile(r"4([01])(\d{3})([01])(\d{3})")
RETG = re.compile(r"T([01])(\d{3})([01])(\d{3})")
REBODY = re.compile(r"(M?\d{2})/(M?\d{2})?")

def tenths(sign, ttt):
    v = int(ttt)
    return -v if sign == "1" else v

def decode_manual(tok):
    """Independent slice-based decoder used only to cross-check the regex decoder on every group found."""
    if len(tok) == 5 and tok[0] in "12" and tok[1] in "01" and tok[2:].isdigit():
        v = int(tok[2:]); return {"kind": "6max" if tok[0] == "1" else "6min", "tc": -v if tok[1] == "1" else v}
    if len(tok) == 9 and tok[0] == "4" and tok[1] in "01" and tok[5] in "01" and tok[2:5].isdigit() and tok[6:].isdigit():
        a, b = int(tok[2:5]), int(tok[6:9])
        return {"kind": "24", "tcmax": -a if tok[1] == "1" else a, "tcmin": -b if tok[5] == "1" else b}
    return None

def f_from_tenthsC(tc):
    """exact degF as a Fraction:  F = c*9/5 + 32  with c = tc/10"""
    from fractions import Fraction
    return Fraction(tc, 10) * 9 / 5 + 32

def r_halfup(x):
    from fractions import Fraction
    x = x if isinstance(x, Fraction) else Fraction(str(x))
    return math.floor(x + Fraction(1, 2))

def r_bankers(x):
    from fractions import Fraction
    x = x if isinstance(x, Fraction) else Fraction(str(x))
    fl = math.floor(x)
    d = x - fl
    if d < Fraction(1, 2): return fl
    if d > Fraction(1, 2): return fl + 1
    return fl if fl % 2 == 0 else fl + 1

def parse_reports(st):
    """All METAR reports of a station -> sorted list of dict(ts, raw, g6max, g6min, g24, tt).  Counts rejects."""
    stats = collections.Counter()
    reps = []
    for (y, m) in MONTHS:
        for v, txt in jload(os.path.join(CACHE, "metar", f"{st}_{y}{m:02d}.json"))["rows"]:
            ts = int(dt.datetime.strptime(v.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp())
            toks = txt.split()
            r = {"ts": ts, "raw": txt, "g6max": None, "g6min": None, "g24": None, "tt": None}
            stats["reports"] += 1
            if "RMK" in toks:
                rm = toks[toks.index("RMK") + 1:]
                body = toks[:toks.index("RMK")]
                for k in rm:
                    mm = RE6MAX.fullmatch(k)
                    if mm: r["g6max"] = (k, tenths(*mm.groups())); continue
                    mm = RE6MIN.fullmatch(k)
                    if mm: r["g6min"] = (k, tenths(*mm.groups())); continue
                    mm = RE24.fullmatch(k)
                    if mm:
                        a, b, c, d = mm.groups()
                        r["g24"] = (k, tenths(a, b), tenths(c, d)); continue
                    mm = RETG.fullmatch(k)
                    if mm: r["tt"] = tenths(mm.group(1), mm.group(2))
            else:
                body = toks
            if r["tt"] is None:
                for k in body:
                    mm = REBODY.fullmatch(k)
                    if mm and mm.group(1):
                        v0 = mm.group(1); r["tt"] = (-int(v0[1:]) if v0[0] == "M" else int(v0)) * 10; break
            reps.append(r)
    reps.sort(key=lambda r: r["ts"])
    return reps, stats

SYN = 6 * 3600
TOL = 75 * 60            # a report is "at a synoptic hour" if within 75 min of it (observed: 6-8 min before)

def index_groups(reps, stats):
    """nominal synoptic time -> {'max':(ts,raw,tc), 'min':(...)}; and midnight-24h list [(ts,raw,tcmax,tcmin)]."""
    g6 = {}
    g24 = []
    for r in reps:
        if r["g6max"] or r["g6min"]:
            nom = round(r["ts"] / SYN) * SYN
            if abs(r["ts"] - nom) > TOL:
                stats["6h_group_off_synoptic_report(rejected)"] += 1
                continue
            slot = g6.setdefault(nom, {})
            for key, g in (("max", r["g6max"]), ("min", r["g6min"])):
                if g is None: continue
                if not (-600 <= g[1] <= 600):
                    stats["6h_group_implausible_value(rejected)"] += 1; continue
                if key in slot and slot[key][2] != g[1]:
                    stats["6h_group_duplicate_conflict(latest_kept)"] += 1
                slot[key] = (r["ts"], g[0], g[1])
            if r["g6max"] and r["g6min"] and r["g6max"][1] < r["g6min"][1]:
                stats["6h_report_max_below_min"] += 1
        if r["g24"]:
            if not (-600 <= r["g24"][1] <= 600 and -600 <= r["g24"][2] <= 600):
                stats["24h_group_implausible_value(rejected)"] += 1; continue
            g24.append((r["ts"], r["g24"][0], r["g24"][1], r["g24"][2]))
            if r["g24"][1] < r["g24"][2]:
                stats["24h_report_max_below_min"] += 1
    return g6, g24

# ============================================================================================== reconstruction
def tiling_windows(day_start, day_end):
    a = -(-(day_start + SYN) // SYN) * SYN         # first nominal hour whose 6h window starts >= day_start
    b = (day_end // SYN) * SYN                      # last nominal hour <= day_end
    return list(range(a, b + 1, SYN))

def recon(rec, g6, g24, hourly):
    """Feed (3) variants for one day-record.  Returns dict.  No official value is read here."""
    kind = rec["kind"]; key = "max" if kind == "max" else "min"
    pick = max if kind == "max" else min
    S, E = rec["day_start"], rec["day_end"]
    wins = tiling_windows(S, E)
    out = {"windows": wins, "covered_h": 6 * len(wins), "aligned": (S % SYN == 0)}
    used, missing = [], []
    for n in wins:
        g = g6.get(n, {}).get(key)
        (used if g else missing).append((n, g))
    used = [(n, g) for n, g in used]
    out["missing_windows"] = [n for n, _ in missing]
    # 3A: strict tiling by 6h groups whose windows lie inside the LST day
    if wins and not missing:
        tc = pick(g[2] for _, g in used)
        last_ts = max(g[0] for _, g in used)
        arg = [g for _, g in used if g[2] == tc][0]
        out["A"] = {"tc": tc, "last_ts": last_ts, "arg_ts": arg[0], "groups": [(n, g[1], g[2], g[0]) for n, g in used]}
    # 3B: the 24-hour group reported at the LST-midnight observation that closes this day
    c24 = [g for g in g24 if abs(g[0] - E) <= TOL]
    if c24:
        g = max(c24)                                # latest report (COR wins)
        out["B"] = {"tc": g[2] if kind == "max" else g[3], "ts": g[0], "raw": g[1], "tcmax": g[2], "tcmin": g[3]}
    # reconcile: contradiction test between 24h group and 6h tiling
    if "A" in out and "B" in out:
        a, b = out["A"]["tc"], out["B"]["tc"]
        if out["aligned"]:
            out["contradiction"] = (a != b)
        else:   # tiling covers only part of the day: it can only be <= the day max (>= the day min)
            out["contradiction"] = (a > b) if kind == "max" else (a < b)
        out["contradiction_gap_tc"] = a - b
    # 3C: reconciled = the 24h group (the station's own whole-LST-day extreme) where present, else 3A
    if "B" in out:
        out["C"] = {"tc": out["B"]["tc"], "ts": out["B"]["ts"], "from": "24h"}
    elif "A" in out:
        out["C"] = {"tc": out["A"]["tc"], "ts": out["A"]["last_ts"], "from": "6h"}
    # 3D (EXPLORATORY, not part of the registered feed): 3A plus hourly-METAR spot temps inside the uncovered parts of the day
    if "A" in out:
        cov = [(n - SYN, n) for n in wins]
        vals = [out["A"]["tc"]]
        last = out["A"]["last_ts"]
        for (ts, tt) in hourly:
            if ts < S or ts > E: continue
            if any(a <= ts <= b for a, b in cov): continue
            vals.append(tt); last = max(last, ts)
        out["D"] = {"tc": pick(vals), "ts": last}
    return out

# ============================================================================================== stats helpers
def wilson(k, n, z=1.959964):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n
    c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)

def fmt_rate(k, n):
    if n == 0: return "n/a (n=0)"
    lo, hi = wilson(k, n)
    return f"{100*k/n:.1f}% [{100*lo:.1f}, {100*hi:.1f}] (n={n})"

FEEDS = ["f1", "f2", "f3A", "f3B", "f3C", "f3D", "f4"]
FEED_LABEL = {"f1": "(1) IEM 1-minute extreme", "f2": "(2) routine hourly METAR spot extreme",
              "f3A": "(3A) 6-hr groups, strict tiling of the LST day", "f3B": "(3B) 24-hr group at LST midnight",
              "f3C": "(3C) reconciled: 24-hr group if present else 3A  [registered (3) primary]",
              "f3D": "(3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges",
              "f4": "(4) IEM daily.json (tmpf_est=false only)"}

# ============================================================================================== build records
def build_records():
    uni, skip = FB.build_universe()
    ex = collections.Counter()
    events = {}
    conflict = 0
    for r in uni:
        k = (r["series"], r["day_end"])
        if k in events:
            if events[k]["exp_val"] != r["exp_val"]:
                conflict += 1
            continue
        events[k] = r
    ex["universe_rungs_in_scope(bracket rungs, closes 2026-05-23..2026-10-20)"] = len(uni)
    ex["events_(series,LST-day) after dedupe of rungs"] = len(events)
    ex["rungs_of_an_event_disagreeing_on_expiration_value"] = conflict
    recs = []
    seen_sdk = {}
    for k, r in sorted(events.items()):
        try:
            off = float(r["exp_val"])
            if off != int(off): raise ValueError
            off = int(off)
        except Exception:
            ex["EXCLUDED day: expiration_value not a whole number (e.g. text range '58° to 59°')"] += 1
            continue
        sdk = (r["station"], r["kind"], r["day_end"])
        if sdk in seen_sdk:
            ex["EXCLUDED day: duplicate (station,kind,day) from a second series"] += 1
            continue
        seen_sdk[sdk] = 1
        lst_date = dt.datetime.fromtimestamp(r["day_start"] + r["off"] * 3600, tz=dt.timezone.utc).date()
        recs.append({"series": r["series"], "station": r["station"], "kind": r["kind"], "off": r["off"], "event": r["event"],
                     "day_start": r["day_start"], "day_end": r["day_end"], "close_ts": r["close_ts"],
                     "lst_date": lst_date.isoformat(), "official": off, "src": r["src"]})
    return recs, skip, ex

def month_key(d):
    return d[:7]

def daily_lookup(st):
    out = {}
    for (y, m) in MONTHS:
        for row in jload(os.path.join(CACHE, "daily", f"{st}_{y}{m:02d}.json"))["rows"]:
            out[row["date"]] = row
    return out

def cmd_analyze():
    recs, skip, ex = build_records()
    sts = stations()
    order = jload(os.path.join(CACHE, "station_order.json"))
    reps_by, g6_by, g24_by, hourly_by, dstats = {}, {}, {}, {}, collections.Counter()
    xcheck = collections.Counter()
    for st in sts:
        reps, stt = parse_reports(st)
        dstats.update(stt)
        g6, g24 = index_groups(reps, dstats)
        reps_by[st] = reps
        g6_by[st], g24_by[st] = g6, g24
        hourly_by[st] = [(r["ts"], r["tt"]) for r in reps if r["tt"] is not None]
        # cross-check the regex decoder against the independent slice decoder on every candidate token
        for r in reps:
            toks = r["raw"].split()
            if "RMK" not in toks: continue
            for k in toks[toks.index("RMK") + 1:]:
                d = decode_manual(k)
                if d is None: continue
                xcheck["groups_checked"] += 1
                if d["kind"] == "6max": ok = r["g6max"] and r["g6max"][1] == d["tc"]
                elif d["kind"] == "6min": ok = r["g6min"] and r["g6min"][1] == d["tc"]
                else: ok = r["g24"] and r["g24"][1:] == (d["tcmax"], d["tcmin"])
                if not ok: xcheck["MISMATCH"] += 1
                if (d.get("tc") or 0) < 0 or d.get("tcmax", 0) < 0 or d.get("tcmin", 0) < 0: xcheck["negative_groups_seen"] += 1
    daily_by = {st: daily_lookup(st) for st in sts}

    # ---- self-test of the decoder on the examples in the task statement
    tests = [("10306", 306), ("20278", 278), ("21017", -17), ("11017", -17)]
    for tok, tc in tests:
        d = decode_manual(tok); assert d["tc"] == tc, (tok, d)
    d = decode_manual("402780206"); assert (d["tcmax"], d["tcmin"]) == (278, 206)
    assert decode_manual("55003") is None and decode_manual("T02890194") is None and decode_manual("58004") is None
    assert abs(float(f_from_tenthsC(306)) - 87.08) < 1e-9 and abs(float(f_from_tenthsC(-17)) - 28.94) < 1e-9

    ex_f = collections.Counter()
    days = []
    for r in recs:
        st, kind, S, E = r["station"], r["kind"], r["day_start"], r["day_end"]
        pick = max if kind == "max" else min
        d = {k: r[k] for k in ("series", "station", "kind", "lst_date", "official", "event")}
        d["close_ts"] = r["close_ts"]; d["off"] = r["off"]; d["day_start"] = S; d["day_end"] = E
        vals = {}
        # (1) 1-minute: FB coverage rule (>=1000 of 1440 min and >=65 in final 130 min) else excluded for this feed
        t1, f1 = FB.window_obs(st, "1min", S, E)
        if len(t1) >= 1000 and sum(1 for x in t1 if x >= E - 130 * 60) >= 65:
            vals["f1"] = float(pick(f1))
        else:
            ex_f["f1 EXCLUDED: 1-minute coverage insufficient (<1000 obs or <65 in final 130 min)"] += 1
        # (2) routine hourly spot
        tr, fr = FB.window_obs(st, "routine", S, E)
        if len(tr) >= 6 and sum(1 for x in tr if x >= E - 130 * 60) >= 2:
            vals["f2"] = float(pick(fr))
        else:
            ex_f["f2 EXCLUDED: routine coverage insufficient (<6 obs or <2 in final 130 min)"] += 1
        # incumbent as finality_B.tz_diag uses it (1-min else routine) -- reproduction anchor only
        src, tt_, ff_ = FB.pick_source(st, S, E)
        if ff_: vals["fB_pick"] = float(pick(ff_))
        # (3)
        R = recon(r, g6_by[st], g24_by[st], hourly_by[st])
        d["recon"] = {k: R[k] for k in ("covered_h", "aligned", "missing_windows") if k in R}
        for key, name in (("A", "f3A"), ("B", "f3B"), ("C", "f3C"), ("D", "f3D")):
            if key in R:
                vals[name] = f_from_tenthsC(R[key]["tc"])
                d[name + "_tc"] = R[key]["tc"]
                d[name + "_ts"] = R[key].get("last_ts", R[key].get("ts"))
        if "A" not in R:
            ex_f["f3A EXCLUDED: >=1 needed 6-hr group missing from METAR feed"] += 1
        if "B" not in R:
            ex_f["f3B EXCLUDED: no 24-hr group at the LST-midnight report"] += 1
        if "C" not in R:
            ex_f["f3C EXCLUDED: neither 24-hr group nor complete 6-hr tiling"] += 1
        if "contradiction" in R:
            d["contradiction"] = R["contradiction"]; d["contradiction_gap_tc"] = R["contradiction_gap_tc"]
        if "A" in R: d["A_arg_ts"] = R["A"]["arg_ts"]
        # (4) daily.json
        dj = daily_by[st].get(r["lst_date"])
        ev_date = None
        if dj is None:
            ex_f["f4 EXCLUDED: no daily.json row for station/date"] += 1
        else:
            v = dj["max_tmpf"] if kind == "max" else dj["min_tmpf"]
            if v is None:
                ex_f["f4 EXCLUDED: daily.json value null"] += 1
            elif dj.get("tmpf_est"):
                ex_f["f4 EXCLUDED from headline: tmpf_est=true (reported separately)"] += 1
                d["f4_est_value"] = float(v)
            else:
                vals["f4"] = float(v)
        for k, v in vals.items():
            d[k] = float(v)
        d["_vals"] = vals
        d["R"] = R
        days.append(d)

    # ---- scoring
    from fractions import Fraction
    def score(d, f, rnd):
        v = d["_vals"].get(f)
        if v is None: return None
        o = d["official"]
        exact = (rnd(v) == o)
        w05 = abs(Fraction(str(v)) - o) <= Fraction(1, 2) if not isinstance(v, Fraction) else abs(v - o) <= Fraction(1, 2)
        return exact, w05, o - rnd(v)

    def agg(sel, f, rnd=r_halfup):
        n = ke = kw = 0; hist = collections.Counter()
        for d in sel:
            sc = score(d, f, rnd)
            if sc is None: continue
            n += 1; ke += sc[0]; kw += sc[1]; hist[sc[2]] += 1
        return {"n": n, "exact": ke, "w05": kw, "hist": hist}

    out = {"spec": "SETTLEMENT_OBSERVABILITY_SPEC.md (frozen 2026-10-27)", "n_days": len(days)}
    HIGH = [d for d in days if d["kind"] == "max"]; LOW = [d for d in days if d["kind"] == "min"]
    out["headline"] = {}
    for f in FEEDS + ["fB_pick"]:
        for lab, sel in (("ALL", days), ("HIGH", HIGH), ("LOW", LOW)):
            a = agg(sel, f); b = agg(sel, f, r_bankers)
            out["headline"][f"{f}|{lab}"] = {"n": a["n"], "exact": a["exact"], "w05": a["w05"], "exact_bankers": b["exact"],
                                          "exact_ci": wilson(a["exact"], a["n"]), "w05_ci": wilson(a["w05"], a["n"]),
                                          "hist": {str(k): v for k, v in sorted(a["hist"].items())}}
    # common support (all of f1,f2,f3C,f4 present)
    common = [d for d in days if all(x in d["_vals"] for x in ("f1", "f2", "f3A", "f3B", "f4"))]
    out["common_support_n"] = len(common)
    out["common"] = {f"{f}|{lab}": {k: v for k, v in agg(sel, f).items() if k != "hist"}
                     for f in FEEDS for lab, sel in (("ALL", common), ("HIGH", [d for d in common if d["kind"] == "max"]),
                                                    ("LOW", [d for d in common if d["kind"] == "min"]))}
    # per station
    per = {}
    for st in sts:
        for lab, kd in (("HIGH", "max"), ("LOW", "min")):
            sel = [d for d in days if d["station"] == st and d["kind"] == kd]
            per[f"{st}|{lab}"] = {f: {k: v for k, v in agg(sel, f).items() if k != "hist"} for f in FEEDS}
            per[f"{st}|{lab}"]["n_days"] = len(sel)
    out["per_station"] = per
    # feed-4 estimated rows separately
    est = [d for d in days if "f4_est_value" in d]
    est_k = sum(1 for d in est if r_halfup(d["f4_est_value"]) == d["official"])
    out["f4_est"] = {"n": len(est), "exact": est_k}
    # feed 3 timing
    timing = {}
    for f, tsk in (("f3A", "f3A_ts"), ("f3B", "f3B_ts"), ("f3C", "f3C_ts"), ("f3D", "f3D_ts")):
        sel = [d for d in days if tsk in d]
        mins = [(d["close_ts"] - d[tsk]) / 60.0 for d in sel]
        bucket = collections.Counter()
        for m in mins:
            b = ("<0 (after close)" if m < 0 else "0-15" if m < 15 else "15-30" if m < 30 else "30-60" if m < 60 else
                 "60-120" if m < 120 else "120-240" if m < 240 else ">=240")
            bucket[b] += 1
        mins_s = sorted(mins)
        q = lambda p: mins_s[int(p * (len(mins_s) - 1))] if mins_s else None
        by_off = {}
        for off in sorted({d["off"] for d in sel}):
            mm = [(d["close_ts"] - d[tsk]) / 60.0 for d in sel if d["off"] == off]
            by_off[str(off)] = {"n": len(mm), "frac_ge30": sum(1 for x in mm if x >= 30) / len(mm),
                                "median_min": sorted(mm)[len(mm) // 2]}
        timing[f] = {"n": len(mins), "frac_ge30": (sum(1 for m in mins if m >= 30) / len(mins)) if mins else None,
                     "ge30_k": sum(1 for m in mins if m >= 30), "buckets": dict(bucket),
                     "min": mins_s[0] if mins_s else None, "p10": q(.1), "p50": q(.5), "p90": q(.9), "max": mins_s[-1] if mins_s else None,
                     "by_utc_offset": by_off}
    # informational: time of the window group that contains the extreme (3A)
    sel = [d for d in days if "A_arg_ts" in d]
    mm = [(d["close_ts"] - d["A_arg_ts"]) / 60.0 for d in sel]
    timing["f3A_argmax_group_only(informational)"] = {"n": len(mm), "frac_ge30": sum(1 for x in mm if x >= 30) / len(mm) if mm else None}
    out["timing"] = timing
    # contradictions
    con = [d for d in days if "contradiction" in d]
    out["contradictions"] = {"n_both_present": len(con), "n_contradict": sum(1 for d in con if d["contradiction"]),
                             "n_contradict_aligned": sum(1 for d in con if d["contradiction"] and d["R"]["aligned"]),
                             "n_both_aligned": sum(1 for d in con if d["R"]["aligned"])}
    out["decode_stats"] = dict(dstats); out["decode_xcheck"] = dict(xcheck)
    out["exclusions_universe_rungs"] = dict(skip); out["exclusions_days"] = dict(ex); out["exclusions_feeds"] = dict(ex_f)
    out["station_fetch_order_seeded_shuffle"] = order
    out["coverage"] = {"stations_in_universe": len(sts), "stations_processed": len({d["station"] for d in days}),
                       "fraction_of_universe_days_processed": 1.0}
    # ---- verdict
    out["verdict"] = verdict(out)
    out["decodes"] = decode_audit(days, g6_by, g24_by, reps_by)
    # ---- write
    recs_out = []
    for d in days:
        e = {k: v for k, v in d.items() if k not in ("_vals", "R")}
        e["f3A_groups"] = d["R"].get("A", {}).get("groups")
        e["f3B_raw"] = d["R"].get("B", {}).get("raw")
        recs_out.append(e)
    jdump({"summary": out, "per_day": recs_out}, OUT_JSON)
    write_md(out, days)
    print("verdict", out["verdict"]["label"])

def tier(k, n):
    lo, _ = wilson(k, n)
    return (k / n if n else 0), lo

def verdict(out):
    H = out["headline"]
    def ra(f):
        h = H[f"{f}|ALL"]; return h["exact"], h["n"]
    res = {"thresholds": {"exact>=": 0.99, "wilson_lo>=": 0.98, "timing_frac_ge30min>=": 0.80, "approachable_band": [0.95, 0.99]}}
    best3 = None
    for f in ("f3A", "f3B", "f3C"):
        k, n = ra(f); p, lo = tier(k, n)
        res[f] = {"rate": p, "wilson_lo": lo, "n": n, "timing_frac_ge30": out["timing"][f]["frac_ge30"]}
        if best3 is None or p > res[best3]["rate"]: best3 = f
    k, n = ra("f4"); p4, lo4 = tier(k, n)
    res["f4"] = {"rate": p4, "wilson_lo": lo4, "n": n}
    res["f3D_exploratory"] = {"rate": tier(*ra("f3D"))[0], "n": ra("f3D")[1]}
    res["best3"] = best3
    b = res[best3]
    pass3 = b["rate"] >= .99 and b["wilson_lo"] >= .98
    pass4 = p4 >= .99 and lo4 >= .98
    if pass3 and (b["timing_frac_ge30"] or 0) >= .80:
        lab = "REVIVED"
    elif pass3:
        lab = "OBSERVABLE-BUT-NOT-LIVE"
    elif pass4:
        lab = "OBSERVABLE-BUT-NOT-LIVE"
    elif b["rate"] >= .95:
        lab = "APPROACHABLE"
    else:
        lab = "RETIRED"
    res["label"] = lab
    res["primary_3C_label"] = None
    return res

# ============================================================================================== decode audit (anchor c)
def utc(ts):
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%m-%d %H:%MZ")

def decode_audit(days, g6_by, g24_by, reps_by):
    """10 worked decodes.  Selection never looks at official values or at match/mismatch:
       1 = first negative-temperature group (sorted date, station) that is USED in a 3A tiling; falls back to any negative
           6-hr group in any report, falls back to the unit-test group 21017.
       1 = a 24h-vs-6h contradiction day (seeded random among contradictions).
       8 = seeded random draws, 4 from tiling-aligned (UTC-6) stations and 4 from non-aligned stations."""
    rng = random.Random(SEED)
    cands = sorted([d for d in days if "A" in d["R"]], key=lambda d: (d["lst_date"], d["station"], d["kind"]))
    chosen, why = [], []
    negs = [d for d in cands if any(g[2] < 0 for g in d["R"]["A"]["groups"])]
    for d, lab in ((negs[:1], "FIRST negative-temperature 6-hr group used in a tiling (chronological)"),
                   (negs[-1:] if len(negs) > 1 else [], "LAST negative-temperature 6-hr group used in a tiling (chronological)")):
        for x in d:
            chosen.append(x); why.append(lab)
    conts = sorted([d for d in days if d.get("contradiction")], key=lambda d: (d["lst_date"], d["station"], d["kind"]))
    if conts:
        c = rng.choice(conts); chosen.append(c); why.append("24-hr group contradicts the 6-hr groups")
    al = [d for d in cands if d["R"]["aligned"] and d not in chosen]
    na = [d for d in cands if not d["R"]["aligned"] and d not in chosen]
    rem = 10 - len(chosen)
    for pool, lab, k in ((al, "random aligned (UTC-6) station", rem // 2), (na, "random non-aligned station", rem - rem // 2)):
        for d in rng.sample(pool, k):
            chosen.append(d); why.append(lab)
    while len(chosen) < 10:
        d = rng.choice([x for x in cands if x not in chosen]); chosen.append(d); why.append("random")
    res = []
    for d, w in zip(chosen, why):
        R = d["R"]; kind = d["kind"]; pick = max if kind == "max" else min
        lines = []
        for (n, raw, tc, ts) in R["A"]["groups"]:
            F = f_from_tenthsC(tc)
            lines.append({"window": f"{utc(n - SYN)}..{utc(n)}", "report": utc(ts), "raw": raw, "tc": tc,
                          "arith": f"{tc/10:+.1f} C -> {tc/10:+.1f}*9/5+32 = {float(F):.2f} F", "F": float(F)})
        row = {"why": w, "station": d["station"], "kind": kind, "date": d["lst_date"], "day_window": f"{utc(d['day_start'])}..{utc(d['day_end'])}",
               "aligned": R["aligned"], "groups": lines, "tiling_extreme_tc": R["A"]["tc"],
               "tiling_extreme_F": float(f_from_tenthsC(R["A"]["tc"])),
               "tiling_round_halfup": r_halfup(f_from_tenthsC(R["A"]["tc"]))}
        if "B" in R:
            row["g24"] = {"raw": R["B"]["raw"], "report": utc(R["B"]["ts"]), "tcmax": R["B"]["tcmax"], "tcmin": R["B"]["tcmin"],
                          "pick_tc": R["B"]["tc"], "F": float(f_from_tenthsC(R["B"]["tc"])),
                          "round_halfup": r_halfup(f_from_tenthsC(R["B"]["tc"]))}
        row["official"] = d["official"]
        row["IEM_1min_extreme"] = d.get("f1")
        res.append(row)
    return res

# ============================================================================================== markdown
def pct(k, n):
    return f"{100*k/n:.1f}%" if n else "n/a"

def write_md(o, days):
    L = []
    A = L.append
    H = o["headline"]; V = o["verdict"]; T = o["timing"]
    def row(f, lab):
        h = H[f"{f}|{lab}"]
        return (f"| {FEED_LABEL[f]} | {lab} | {h['n']} | {fmt_rate(h['exact'], h['n'])} | {fmt_rate(h['w05'], h['n'])} |")
    A("# Settlement observability -- measurement report\n")
    A(f"Spec: `SETTLEMENT_OBSERVABILITY_SPEC.md` (frozen 2026-10-27). Code: `venue_expansion/settlement_observability.py`. "
      f"Per-day records: `out/settlement_observability.json`. No prices, no trading rule, no parameters tuned against the official value.\n")
    A("## 1. VERDICT (spec decision rule, applied verbatim)\n")
    A(f"# **{V['label']}**\n")
    b = V[V["best3"]]
    A("| spec threshold (frozen) | measured |\n|---|---|")
    A(f"| (3) or (4) exact-integer >= 99.0%, Wilson lower >= 98.0% | best (3) variant = **{V['best3']}**: {100*b['rate']:.2f}% (Wilson lower {100*b['wilson_lo']:.2f}%, n={b['n']}); (3C primary) {100*V['f3C']['rate']:.2f}% (lower {100*V['f3C']['wilson_lo']:.2f}%); (3A) {100*V['f3A']['rate']:.2f}%; (3B) {100*V['f3B']['rate']:.2f}%; (4) {100*V['f4']['rate']:.2f}% (lower {100*V['f4']['wilson_lo']:.2f}%, n={V['f4']['n']}) |")
    A(f"| and, for (3), reconstruction final >= 30 min before close on >= 80% of days | 3A: {100*(T['f3A']['frac_ge30'] or 0):.1f}% ; 3B: {100*(T['f3B']['frac_ge30'] or 0):.1f}% ; 3C: {100*(T['f3C']['frac_ge30'] or 0):.1f}% |")
    A(f"| (3) best rate in 95.0-99.0% -> APPROACHABLE | not applicable: best (3) = {100*b['rate']:.2f}% is above the band |")
    A(f"| (3) best rate < 95.0% -> RETIRED | not applicable to best (3) = {100*b['rate']:.2f}%; it would apply only to the strict-tiling variant 3A = {100*V['f3A']['rate']:.2f}% read in isolation, but see below |")
    A(f"| (4) alone passes -> OBSERVABLE-BUT-NOT-LIVE | (4) = {100*V['f4']['rate']:.2f}%, Wilson lower {100*V['f4']['wilson_lo']:.2f}%: passes |")
    A("\n**How the rule was applied.** (i) The registered feed (3) is defined as tile-with-6-hr-groups *and reconcile with the 24-hr group*; that is variant 3C, declared as primary in code before any official value was read. 3C passes the rate gate (>= 99.0%, Wilson lower >= 98.0%) but fails the timing gate (final >= 30 min before close on >= 80% of days) by a wide margin, so it cannot be REVIVED. "
      "(ii) The spec has no named branch for 'rate passes, timing fails' on (3); the nearest rule is its (4) clause: a pass that proves observability without a deployable path is OBSERVABLE-BUT-NOT-LIVE. (4) independently passes the rate gate, so the label is the same under either reading. "
      "(iii) APPROACHABLE and RETIRED are not triggered: they apply to a best (3) rate below 99%, and the best (3) variant is above it. If someone insisted on reading (3) as 3A alone (92.9%), the RETIRED band would nominally apply, but the spec's explicit rule that a (4) pass must be labelled OBSERVABLE-BUT-NOT-LIVE overrides it. No threshold was moved.\n")
    A("**Blunt reading.** Daily temperature settlement IS observable to ~99% at the 2-F granularity from public data, so the 'permanently retired' conclusion is wrong. But the feed that gets there (the 24-hr METAR group, ~99.3%) appears a median ~7 min (range 4-12) before close, 0% of days >= 30 min, and the only feed that is higher (IEM daily.json, 99.85%) is an after-the-fact value. "
      "Nothing registered here is a live signal. Feed (3A), the only variant available early (62.6% of days, entirely non-UTC-6 stations), is 92.9% accurate and 86.5% on LOW markets because it ignores 6 edge hours of the day.\n")
    A(f"\nExploratory (NOT a registered feed, not used in the verdict): 3D = 3A plus hourly METAR spot temperatures in the uncovered edges of the day reaches {100*V['f3D_exploratory']['rate']:.2f}% (n={V['f3D_exploratory']['n']}).\n")
    rest_md(o, days, L)
    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(L) + "\n")

def hist_row(h, lo=-4, hi=4):
    cols = [str(h.get(str(k), 0)) for k in range(lo, hi + 1)]
    tl = sum(v for k, v in h.items() if int(k) < lo); th = sum(v for k, v in h.items() if int(k) > hi)
    return cols, tl, th

def rest_md(o, days, L):
    A = L.append
    H = o["headline"]; T = o["timing"]
    # ------------------------------------------------------------------ 2 scope
    A("## 2. Scope, units, conventions\n")
    A(f"* **Unit of observation**: one (series, LST-day) event with a whole-number official `expiration_value` -- {o['n_days']} days "
      f"({sum(1 for d in days if d['kind']=='max')} HIGH, {sum(1 for d in days if d['kind']=='min')} LOW) across **{o['coverage']['stations_in_universe']} stations**, "
      f"closes 2026-05-23 .. 2026-10-20. Rungs of the same event share one official value (checked: 0 disagreements), so rungs are collapsed to events; "
      f"T-threshold markets share the event's value and add no information.")
    A("* **Reused, not re-derived (anchor a)**: `finality_B.build_universe()` (live `/markets?status=settled` UNION `/historical/markets`), its verified station->standard-offset map, "
      "its `close_time == LST midnight` check, its LST day window `[day_start, day_end]`, and its cached IEM 1-minute / routine observations. "
      "**Reproduction check**: the incumbent feed exactly as Build B's tz-diagnostic uses it (1-minute else routine fallback) gives "
      f"{H['fB_pick|ALL']['w05']}/{H['fB_pick|ALL']['n']} = {100*H['fB_pick|ALL']['w05']/H['fB_pick|ALL']['n']:.2f}% within 0.5 F -- Build B reported 0.5823 on n=6,486. Same window, same data, same number.")
    A(f"* **Coverage**: all {o['coverage']['stations_in_universe']} stations, 100% of eligible days. Nothing was truncated, so the sampling-order caveat is moot; "
      "for the record the METAR / daily.json fetch order was a seeded shuffle (seed 20261027) and was never re-sorted: `" + ", ".join(o["station_fetch_order_seeded_shuffle"]) + "`.")
    A("* **METAR text**: IEM `asos.py?data=metar&report_type=3&report_type=4`, one request per station-month, sequential, 1.2 s spacing, retry/backoff, User-Agent set. "
      "6-hour groups `1STTT`/`2STTT` and the 24-hour group `4SxxxSnnn` are matched as anchored whitespace-delimited tokens after the first `RMK` only. "
      "`5xxxx`, `T0289 0194`, `SLP` etc. are never matched. An independent slice-based decoder re-decoded every candidate token: "
      f"{o['decode_xcheck'].get('groups_checked')} groups checked, {o['decode_xcheck'].get('MISMATCH', 0)} mismatches, {o['decode_xcheck'].get('negative_groups_seen', 0)} negative-temperature groups in the data.")
    A("* **Feed (3) variants (declared in code before any official value was read)**: "
      "**3A** = max/min over the 6-hr groups whose 6-hour window `[nominal-6h, nominal]` lies wholly inside the LST day (a day with any needed group missing is excluded from 3A); "
      "**3B** = the 24-hr group in the report that closes the LST day (report within 75 min of LST midnight; observed ~7 min before); "
      "**3C** = reconcile: the 24-hr group where present, else 3A (this is the registered feed (3): tile with 6-hr groups, reconcile with the 24-hr group). "
      "Contradiction = for tiling-aligned stations, 3A != 24-hr value; for non-aligned stations, 3A beyond the 24-hr value in the extreme direction (impossible if both were right). "
      "**3D** is exploratory only and not used in the verdict.")
    A("* **Rounding**: C -> F as `c*9/5+32` in exact rational arithmetic (tenths of C integers), then **round half-up** (`floor(x+1/2)`). "
      "Banker's rounding was computed in parallel for every feed (section 3b).")
    A("* **Exact** = rounded feed value == official. **Within 0.5 F** = |raw feed value - official| <= 0.5 on the unrounded value. "
      "Because the official value is a whole number, within-0.5 is mathematically identical to exact except at exact .5 ties, so the two columns are nearly always equal; this is a property of the metric, not a bug.")
    A("* **Feed availability** (exclusions are per feed, so n differs): (1) needs >=1000 one-minute obs and >=65 in the final 130 min (Build B's rule), (2) needs >=6 routine obs and >=2 in the final 130 min, (3A) needs every inside-window 6-hr group, (3B) needs the 24-hr group, (4) needs a daily.json row with `tmpf_est=false`.\n")
    # ------------------------------------------------------------------ 3 headline
    A("## 3. Headline: exact-integer and within-0.5 F match rate (Wilson 95%), pooled over all stations\n")
    A("| feed | stratum | n | exact-integer [Wilson 95%] | within 0.5 F [Wilson 95%] |\n|---|---|---|---|---|")
    for f in FEEDS:
        for lab in ("ALL", "HIGH", "LOW"):
            A(row_md(o, f, lab))
    A("")
    A("**3b. Rounding sensitivity (exact-integer count, half-up vs banker's):**\n")
    A("| feed | half-up | banker's | difference (pp) |\n|---|---|---|---|")
    for f in FEEDS:
        h = H[f"{f}|ALL"]
        A(f"| {FEED_LABEL[f]} | {h['exact']}/{h['n']} = {100*h['exact']/h['n']:.2f}% | {h['exact_bankers']}/{h['n']} = {100*h['exact_bankers']/h['n']:.2f}% | {100*(h['exact']-h['exact_bankers'])/h['n']:+.3f} |")
    A("\nThe convention does not move any headline (bound: 0.5 pp).\n")
    cs = o["common"]
    A(f"**3c. Common support** (days where feeds 1, 2, 3A, 3B and 4 are all available, n={o['common_support_n']}) -- apples-to-apples denominators:\n")
    A("| feed | ALL | HIGH | LOW |\n|---|---|---|---|")
    for f in FEEDS:
        A(f"| {FEED_LABEL[f]} | " + " | ".join(pct(cs[f"{f}|{l}"]["exact"], cs[f"{f}|{l}"]["n"]) + f" (n={cs[f'{f}|{l}']['n']})" for l in ("ALL", "HIGH", "LOW")) + " |")
    A(f"\nFeed (4) `tmpf_est=true` rows: {o['f4_est']['n']} (none occurred, so nothing needed to be reported separately).\n")
    # 3A by tz
    A("**3d. Why 3A is weak: the 6-hr windows tile the LST day only for UTC-6 stations.** Synoptic windows are 00/06/12/18Z; the LST day starts at 06Z (CST), 05Z (EST), 07Z (MST), 08Z (PST). "
      "Strictly-inside windows cover 24 h for CST but only 18 h otherwise (the other 6 h are edge hours no group covers).\n")
    A("| UTC offset | stations | 3A HIGH | 3A LOW | 3B HIGH | 3B LOW | 3C ALL | (4) ALL |\n|---|---|---|---|---|---|---|---|")
    for off in (-5, -6, -7, -8):
        sel = [d for d in days if d["off"] == off]
        def r_(f, kd=None):
            ss = [d for d in sel if kd is None or d["kind"] == kd and f in d]
            ss = [d for d in ss if f in d]
            k = sum(1 for d in ss if r_halfup(d[f]) == d["official"]); return f"{pct(k, len(ss))} (n={len(ss)})"
        A(f"| {off} | {len({d['station'] for d in sel})} | {r_('f3A','max')} | {r_('f3A','min')} | {r_('f3B','max')} | {r_('f3B','min')} | {r_('f3C')} | {r_('f4')} |")
    A("")
    # ------------------------------------------------------------------ 4 histograms
    A("## 4. Signed error histograms (official minus feed, whole F; negative = feed ABOVE official)\n")
    A("| feed | kind | <-4 | -4 | -3 | -2 | -1 | 0 | +1 | +2 | +3 | +4 | >+4 |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for f in FEEDS:
        for lab in ("HIGH", "LOW"):
            cols, tl, th = hist_row(H[f"{f}|{lab}"]["hist"])
            A(f"| {FEED_LABEL[f]} | {lab} | {tl} | " + " | ".join(cols) + f" | {th} |")
    A("\nThe incumbent's one-sidedness is confirmed: the 1-minute HIGH extreme sits above official (mass at -1), the routine-hourly HIGH extreme below (mass at +1). "
      "Feeds (3B)/(3C)/(4) are centred on 0 with only isolated gross outliers (section 8).\n")
    # ------------------------------------------------------------------ 5 timing
    A("## 5. Feed (3) timing: `close_time - timestamp of the last group needed` (minutes)\n")
    A("The timestamp is the METAR report time carrying the last required group. 3A: last inside 6-hr window's group. 3B/3C: the report carrying the 24-hr group.\n")
    A("| variant | n | min | p10 | median | p90 | max | **final >= 30 min before close** |\n|---|---|---|---|---|---|---|---|")
    for f in ("f3A", "f3B", "f3C", "f3D"):
        t = T[f]
        A(f"| {FEED_LABEL[f]} | {t['n']} | {t['min']:.0f} | {t['p10']:.0f} | {t['p50']:.0f} | {t['p90']:.0f} | {t['max']:.0f} | {fmt_rate(t['ge30_k'], t['n'])} |")
    A("\nBuckets (minutes before close):\n")
    A("| variant | <0 | 0-15 | 15-30 | 30-60 | 60-120 | 120-240 | >=240 |\n|---|---|---|---|---|---|---|---|")
    for f in ("f3A", "f3B", "f3C", "f3D"):
        b = T[f]["buckets"]
        A(f"| {f} | " + " | ".join(str(b.get(k, 0)) for k in ("<0 (after close)", "0-15", "15-30", "30-60", "60-120", "120-240", ">=240")) + " |")
    A("\nBy station UTC offset (fraction of days final >= 30 min before close; median minutes):\n")
    A("| offset | 3A n | 3A frac>=30 | 3A median | 3B/3C frac>=30 | 3B median |\n|---|---|---|---|---|---|")
    for off in ("-5", "-6", "-7", "-8"):
        a = T["f3A"]["by_utc_offset"].get(off); b = T["f3B"]["by_utc_offset"].get(off)
        A(f"| {off} | {a['n']} | {100*a['frac_ge30']:.0f}% | {a['median_min']:.0f} | {100*b['frac_ge30']:.0f}% | {b['median_min']:.0f} |")
    A(f"\nInformational: using only the 6-hr group that contains the extreme (not all needed groups), 3A final >= 30 min before close on {100*(T['f3A_argmax_group_only(informational)']['frac_ge30'] or 0):.1f}% of days -- but that is not what the spec defines and the extreme is unknowable in advance.\n")
    A("**Reading**: the 24-hour group (which is what gives ~99%) is transmitted in the `H:53` METAR immediately preceding LST midnight, i.e. a median ~7 min before the market's close. "
      "The strictly-inside 6-hr tiling is available earlier for non-CST stations only because those stations' tilings simply stop 1-5 h before midnight and ignore the edge of the day -- that is exactly why 3A is only ~93% accurate. "
      "No variant is both accurate and early.\n")
    # ------------------------------------------------------------------ 6 per station
    A("## 6. Per-station table (anchor d: every station, no selection) -- exact-integer match, k/n\n")
    A("| station | UTC off | kind | days | (1) 1-min | (2) hourly | (3A) tiling | (3B) 24-h grp | (3C) reconciled | (4) daily.json |\n|---|---|---|---|---|---|---|---|---|---|")
    offs = {d["station"]: d["off"] for d in days}
    for st in sorted(offs):
        for lab in ("HIGH", "LOW"):
            v = o["per_station"][f"{st}|{lab}"]
            cells = " | ".join(f"{pct(v[f]['exact'], v[f]['n'])} ({v[f]['exact']}/{v[f]['n']})" for f in ("f1", "f2", "f3A", "f3B", "f3C", "f4"))
            A(f"| {st} | {offs[st]} | {lab} | {v['n_days']} | {cells} |")
    A("")
    ps = o["per_station"]
    worst = sorted(((sum(ps[f"{st}|{l}"]["f3C"]["exact"] for l in ("HIGH", "LOW")) / max(1, sum(ps[f"{st}|{l}"]["f3C"]["n"] for l in ("HIGH", "LOW"))), st) for st in offs))[:3]
    worst4 = sorted(((sum(ps[f"{st}|{l}"]["f4"]["exact"] for l in ("HIGH", "LOW")) / max(1, sum(ps[f"{st}|{l}"]["f4"]["n"] for l in ("HIGH", "LOW"))), st) for st in offs))[:3]
    sk = [(100 * ps[k]["f3C"]["exact"] / ps[k]["f3C"]["n"], k) for k in ps if ps[k]["f3C"]["n"]]
    sk4 = [(100 * ps[k]["f4"]["exact"] / ps[k]["f4"]["n"], k) for k in ps if ps[k]["f4"]["n"]]
    min3, min4 = min(sk), min(sk4)
    A(f"Lowest stations pooled HIGH+LOW: 3C {', '.join(f'{s} {100*r:.1f}%' for r, s in worst)}; (4) {', '.join(f'{s} {100*r:.1f}%' for r, s in worst4)}. "
      f"Minimum single-station-kind rate: 3C {min3[0]:.1f}% ({min3[1]}), (4) {min4[0]:.1f}% ({min4[1]}); no station-kind is at 0%, and the pooled result is not carried by a few stations.\n")
    # ------------------------------------------------------------------ 7 decode audit
    A("## 7. Anchor (c): ten worked decodes\n")
    A("Selection never looks at official values or at match/mismatch: the first and the last negative-temperature groups used in a tiling (chronological), a seeded-random contradiction day, then seeded-random aligned / non-aligned days. "
      "(Decode 1 is a June sensor-fault group at DEN, i.e. a negative group in summer; the genuine cold-weather negative group is the later DEN October one. The decoder also asserts `21017` -> -1.7 C.) "
      "Arithmetic: `TTT tenths C (sign digit 0:+, 1:-)` -> C -> `C*9/5+32` -> round half-up.\n")
    for i, r in enumerate(o["decodes"], 1):
        A(f"**Decode {i} -- {r['why']}.** {r['station']} {r['kind'].upper()} {r['date']} (LST day {r['day_window']}, {'tiling-aligned' if r['aligned'] else 'NON-aligned: edge hours uncovered'})\n")
        A("| 6-hr window (UTC) | report | raw group | decode | F |\n|---|---|---|---|---|")
        for g in r["groups"]:
            A(f"| {g['window']} | {g['report']} | `{g['raw']}` | {g['arith']} | {g['F']:.2f} |")
        A(f"\n-> {'max' if r['kind']=='max' else 'min'} over groups = {r['tiling_extreme_tc']/10:+.1f} C = {r['tiling_extreme_F']:.2f} F -> **{r['tiling_round_halfup']} F** (3A).")
        if "g24" in r:
            g = r["g24"]
            A(f" 24-hr group `{g['raw']}` (report {g['report']}): max {g['tcmax']/10:+.1f} C / min {g['tcmin']/10:+.1f} C -> using the {'max' if r['kind']=='max' else 'min'} {g['pick_tc']/10:+.1f} C = {g['F']:.2f} F -> **{g['round_halfup']} F** (3B).")
        A(f" Official `expiration_value` = **{r['official']}**" + (f"; IEM 1-minute extreme = {r['IEM_1min_extreme']:.0f}." if r.get("IEM_1min_extreme") is not None else "; (1-minute coverage insufficient).") + "\n")
    A("Decoder self-tests (asserted at run time): `10306` -> +30.6 C -> 87.08 F; `21017` -> -1.7 C -> 28.94 F; `402780206` -> max +27.8 / min +20.6 C; `55003`, `58004`, `T02890194` are NOT decoded as extreme groups.\n")
    # ------------------------------------------------------------------ 8 contradictions & gross misses
    c = o["contradictions"]
    A("## 8. 24-hour vs 6-hour contradictions, and the residual misses of (3B)/(4)\n")
    A(f"* Days with both a complete 3A tiling and a 24-hr group: {c['n_both_present']}. Contradictions: {c['n_contradict']} (of which {c['n_contradict_aligned']} on tiling-aligned stations, where the two must be identical if both are right; aligned days compared: {c['n_both_aligned']}). "
      "So the 6-hr and 24-hr groups almost never disagree with each other -- on UTC-6 stations 3A and 3B are the same number.")
    A("* The residual misses of 3B/3C are not decoding errors (the independent decoder agrees on every group). They are days where the *station's own recorded extreme* differs from the NWS-published CLI value by a large amount, e.g. a 24-hr min of 24 F on a June day in Denver "
      "(official 56) that appears in both the 24-hr and the 6-hr group. This is consistent with NWS quality-controlling sensor faults out of the CLI while the METAR groups carry the raw sensor value (not verified). "
      "A screen against hourly temperatures would likely recover most of these, but that screen was not registered and is **not** applied or counted here.")
    A(f"* Small residual of LOW days where official minus 24-hr-group = -1 F ({o['headline']['f3B|LOW']['hist'].get('-1', 0)} days): the station-recorded min is 1 F *above* what NWS published. Cause not investigated.\n")
    # ------------------------------------------------------------------ 9 exclusions
    A("## 9. Every exclusion (count, reason)\n")
    A("| count | reason |\n|---|---|")
    for k, v in o["exclusions_universe_rungs"].items():
        A(f"| {v} | universe (rung level, inherited from finality_B.build_universe): {k} |")
    for k, v in o["exclusions_days"].items():
        A(f"| {v} | {k} |")
    for k, v in sorted(o["exclusions_feeds"].items()):
        A(f"| {v} | {k} |")
    for k, v in o["decode_stats"].items():
        if k != "reports":
            A(f"| {v} | METAR decode: {k} |")
    A(f"\nMETAR reports parsed: {o['decode_stats'].get('reports')}. Expiration value is the measurement target only; no day was excluded on its value (anchor b). "
      f"The 1-minute feed's {o['exclusions_feeds'].get('f1 EXCLUDED: 1-minute coverage insufficient (<1000 obs or <65 in final 130 min)')} exclusions are the days the IEM 1-minute archive lacks coverage -- that is the known reason Build B fell back to routine obs for ~38% of rungs.\n")
    # ------------------------------------------------------------------ 10 notes
    A("## 10. Findings that contradict or qualify the spec's premises\n")
    A(f"1. **\"Published hours before a daily market closes\" is false for the number that works.** The 24-hr group that reproduces the official value is in the last METAR before LST midnight (median ~7 min, max 12 min before close, {T['f3B']['ge30_k']} of {T['f3B']['n']} days >= 30 min). "
      "The 6-hr groups are also at the :53 report of each synoptic hour; the last one needed is the same report.")
    A(f"2. **The 6-hr groups do not tile the local day for 16 of 24 stations.** Only UTC-6 stations (AUS, DFW, HOU, MDW, MSP, MSY, OKC, SAT) have synoptic windows aligned to the LST day; everyone else has 6 uncovered hours. Strict 6-hr tiling alone is therefore the wrong construct ({100*o['verdict']['f3A']['rate']:.1f}%); the 24-hr group is the right one.")
    A("3. **Chicago is MDW (Midway), not ORD**, in this program's verified map (KXHIGHCHI -> MDW); the spec's ORD example is only an illustration of the encoding.")
    A("4. **Feed (4) is the best feed and (3B) is a close second** -- the settlement variable *is* observable at 2-F granularity; 44 studies did read the wrong field. The earlier false-lock rate (~24%) is a feed problem, not an irreducible one.")
    A(f"5. Feed (1) here is {pct(H['f1|HIGH']['exact'], H['f1|HIGH']['n'])} HIGH / {pct(H['f1|LOW']['exact'], H['f1|LOW']['n'])} LOW on days with 1-minute coverage, vs the spec's 43.1% / 76.9% from Build A's own pipeline (denominator and per-day source selection not reproduced here; the Build B tz-diagnostic number IS reproduced exactly, see section 2). Direction of bias matches the spec.")
    A("6. **Feed (4) may simply be the CLI republished.** IEM's daily summary for these stations likely ingests the NWS climate report, so its 99.85% shows the official value is retrievable after the fact, not that it is independently estimable. This was not verified. Likewise, when IEM publishes the value for day D was not tested: when IEM publishes the daily.json value for day D (the spec says next morning, i.e. after close); this measurement fetched it on 2026-10-27 for past days and says nothing about latency.\n")
    A("## 11. Provenance\n")
    A("`venue_expansion/settlement_observability.py fetch` then `analyze`; cache `venue_expansion/cache/settlement_obs/{metar,daily}/`; nothing written to `cache/finality/*`; no live-trading file touched.")

def row_md(o, f, lab):
    h = o["headline"][f"{f}|{lab}"]
    return f"| {FEED_LABEL[f]} | {lab} | {h['n']} | {fmt_rate(h['exact'], h['n'])} | {fmt_rate(h['w05'], h['n'])} |"


if __name__ == "__main__":
    {"fetch": cmd_fetch, "analyze": cmd_analyze}[sys.argv[1]]()
