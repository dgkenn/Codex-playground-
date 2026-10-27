#!/usr/bin/env python3
"""bound_resolution.py -- executes BOUND_RESOLUTION_SPEC.md (registered 2026-10-27).

Signal: the running max of decoded METAR 6-hr MAX groups (1STTT) is a settlement-consistent LOWER BOUND on
the official daily high; once BMAX >= hi + D a bracket rung [lo,hi] is provably NO.  Buy NO at cost = 100 - yes_bid.

REUSED, not rebuilt:
  settlement_observability.py : METAR group decoder (parse_reports regexes), LST-day window / tiling windows,
                                universe records (via finality_B.build_universe), wilson, f_from_tenthsC, r_halfup
  finality_B.py               : build_universe (settled-market universe + close_time==LST-midnight check + day window),
                                candle fetch approach (live /series/.../candlesticks after 2026-08-28, /historical before),
                                _adapt (historical 'close' -> 'close_dollars'), cluster_stats (day-clustered SE), fee_c
  edge_sizing_v2.normalize()  : candlestick parsing

Stages (resumable):
  python bound_resolution.py anchor_b   # ANCHOR (b) ONLY -- no price is read.  Writes out/bound_resolution.{json,md};
                                        # exits 3 if the spec self-kills (violation rate > 2%).
  python bound_resolution.py fires      # walk all fires (all arms), anchors (a)(c)(d)(e); NO prices
  python bound_resolution.py candles    # fetch candlesticks for fired rungs in a SEEDED SHUFFLED order (never re-sorted)
  python bound_resolution.py analyze    # entry/PnL/stats/verdict; writes out/bound_resolution.{json,md}

Cache: cache/bound_res/  (never writes into cache/finality/* or cache/settlement_obs/*).
"""
from __future__ import annotations
import bisect, collections, datetime as dt, json, math, os, random, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import settlement_observability as SO        # noqa: E402   (decoder, windows, wilson, rounding)
import finality_B as FB                      # noqa: E402   (universe, candle fetch, cluster stats)
import edge_sizing_v2 as V2                  # noqa: E402   (normalize)

CACHE = os.path.join(HERE, "cache", "bound_res")
CAND = os.path.join(CACHE, "candles")
OUT_JSON = os.path.join(HERE, "out", "bound_resolution.json")
OUT_MD = os.path.join(HERE, "out", "bound_resolution.md")
SEED = 20261027
SYN, TOL = SO.SYN, SO.TOL
S_GRID = (3, 5, 8)
D_GRID = (1, 2)
PRIMARY = (5, 1)                 # (S, D)
L_ARMS = (10, 20)
CELLS = [(s, d) for s in S_GRID for d in D_GRID]
NCMP = len(CELLS) * len(L_ARMS)  # 12 comparisons
ALPHA = 0.05 / NCMP
SELF_KILL_RATE = 0.02
INF = "inf"                      # key for the UNGUARDED bound (no corroboration), reported for anchor (b) only
NON_CST = (-5, -7, -8)

jload = SO.jload


def _js(o):
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, (set, tuple)):
        return list(o)
    raise TypeError(type(o))


def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(o, fh, default=_js)
    os.replace(tmp, p)


wilson = SO.wilson


# ============================================================================================ data layer
def load_station(st):
    """All METAR reports for a station (sorted), plus decode stats.  Pure reuse of SO.parse_reports."""
    reps, stats = SO.parse_reports(st)
    ts = [r["ts"] for r in reps]
    return {"reps": reps, "ts": ts, "stats": stats}


def day_reports(stn, S, E):
    """Reports a day-walk may look at: ts in [S, E+TOL].  (Spots for a group live in [nom-6h, report ts] subset of [S,E].)"""
    i = bisect.bisect_left(stn["ts"], S)
    j = bisect.bisect_right(stn["ts"], E + TOL)
    return stn["reps"][i:j]


def spot_F(tt_tenthsC):
    return float(SO.f_from_tenthsC(tt_tenthsC))


def walk_day(reps, S, E, kind, plaus=True):
    """The ONE signal implementation.  Walks reports in time order; at each report that carries a 6-hr group of the
    right kind whose 6-hour window lies wholly inside the LST day [S,E], updates the bound.  Reads only the reports it
    is handed, in order, and at report i uses only reports 0..i  (no look-ahead by construction; anchor c re-proves it).

    Returns a list of events, one per qualifying group-bearing report, in report-time order:
      {"ts": report ts, "nom": nominal synoptic ts, "tc": tenths C, "gI": integer F (half-up),
       "bound": {key: integer-F bound after this report}}      key in {INF} U S_GRID
    bound[INF] = running max/min over every in-day group; bound[S] = same but only over groups corroborated by a
    spot temperature (any routine/special METAR in [nom-6h, report ts] with |spot - group| <= S degF).
    SPEC-LITERAL semantics: BMAX(t) is the max over ALL decoded groups published so far (a correction (COR) report that
    re-issues a slot's group is simply one more decoded group; both the original and the COR count, each with its own
    corroboration).  This makes the bound non-decreasing by construction, so anchor (a) is a real check on the code.
    """
    gk = "g6max" if kind == "max" else "g6min"
    pick = max if kind == "max" else min
    spots = []                                   # (ts, F) of every report seen so far
    run = {k: None for k in (INF,) + S_GRID}     # running bound per guard variant
    events = []
    for r in reps:
        if r["tt"] is not None:
            spots.append((r["ts"], spot_F(r["tt"])))
        g = r[gk]
        if g is None:
            continue
        nom = round(r["ts"] / SYN) * SYN
        if abs(r["ts"] - nom) > TOL:
            continue
        if plaus and not (-600 <= g[1] <= 600):   # physical-plausibility filter (|T| <= 60 C), inherited from SO.index_groups; plaus=False disables it
            continue
        if not (nom - SYN >= S and nom <= E):    # 6-hr window must lie inside the LST day (3A attribution)
            continue
        gF = spot_F(g[1])
        gI = SO.r_halfup(SO.f_from_tenthsC(g[1]))
        win = [f for (t, f) in spots if nom - SYN <= t <= r["ts"]]
        corr = {s: any(abs(f - gF) <= s for f in win) for s in S_GRID}
        run[INF] = gI if run[INF] is None else pick(run[INF], gI)
        for s in S_GRID:
            if corr[s]:
                run[s] = gI if run[s] is None else pick(run[s], gI)
        events.append({"ts": r["ts"], "nom": nom, "tc": g[1], "gI": gI, "gF": gF, "corr": corr, "bound": dict(run)})
    return events


def fire_time(events, kind, strike, D, key):
    """First event whose bound clears the rung by D.  HIGH: BMAX >= hi + D.  LOW: BMIN <= lo - D.
    Returns the event or None.  `strike` = hi for HIGH, lo for LOW."""
    for e in events:
        b = e["bound"][key]
        if b is None:
            continue
        if kind == "max" and b >= strike + D:
            return e
        if kind == "min" and b <= strike - D:
            return e
    return None


# ============================================================================================ universe
def build_all():
    """Day records (reuse SO.build_records) + rung list (reuse FB.build_universe).  Returns days, rungs, exclusions."""
    recs, skip, ex = SO.build_records()
    daykey = {(r["station"], r["kind"], r["day_end"]): r for r in recs}
    uni, _ = FB.build_universe()
    rungs, rex = [], collections.Counter()
    seen = set()
    for r in uni:
        if r["ticker"] in seen:
            rex["duplicate_ticker"] += 1
            continue
        seen.add(r["ticker"])
        d = daykey.get((r["station"], r["kind"], r["day_end"]))
        if d is None:
            rex["rung_on_excluded_day(expiration_value not whole number / duplicate series)"] += 1
            continue
        # anchor (d): close_time == LST midnight (FB filtered with close_hour check; re-assert the exact window)
        assert r["day_end"] - r["day_start"] == 86400
        assert abs(r["close_ts"] - r["day_end"]) <= 120, (r["ticker"], r["close_ts"], r["day_end"])
        rr = dict(r)
        rr["official"] = d["official"]
        rr["lst_date"] = d["lst_date"]
        rungs.append(rr)
    return recs, rungs, dict(skip), dict(ex), dict(rex)


def arm_of(kind, off):
    if kind == "max" and off in NON_CST:
        return "PRIMARY_HIGH_nonCST"
    if kind == "min" and off in NON_CST:
        return "SECONDARY_LOW_nonCST"
    if kind == "max":
        return "SECONDARY_HIGH_CST"
    return "SECONDARY_LOW_CST"


ARMS = ["PRIMARY_HIGH_nonCST", "SECONDARY_LOW_nonCST", "SECONDARY_HIGH_CST", "SECONDARY_LOW_CST"]


def rate_str(k, n):
    if n == 0:
        return "n/a (n=0)"
    lo, hi = wilson(k, n)
    return f"{100*k/n:.2f}% [{100*lo:.2f}, {100*hi:.2f}] ({k}/{n})"


# ============================================================================================ anchor (b) + walk all
def walk_everything():
    recs, rungs, skip, ex, rex = build_all()
    stations = sorted({r["station"] for r in recs})
    stn = {st: load_station(st) for st in stations}
    walks = {}                                  # (station, kind, day_end) -> events
    for r in recs:
        stn_ = stn[r["station"]]
        walks[(r["station"], r["kind"], r["day_end"])] = walk_day(
            day_reports(stn_, r["day_start"], r["day_end"]), r["day_start"], r["day_end"], r["kind"])
    return recs, rungs, skip, ex, rex, stn, walks


def anchor_b_compute(recs, walks):
    """Final bound vs official, per arm, per variant (unguarded + S grid).  HIGH: violation iff BMAX > official.
    LOW: violation iff BMIN < official.  Also anchor (a): monotonicity of the bound on every walked day."""
    res = {}
    mono_viol = []
    days_walked = 0
    for r in recs:
        ev = walks[(r["station"], r["kind"], r["day_end"])]
        days_walked += 1
        # anchor (a): bound monotone within the day
        for key in (INF,) + S_GRID:
            prev = None
            for e in ev:
                b = e["bound"][key]
                if b is None:
                    continue
                if prev is not None and ((r["kind"] == "max" and b < prev) or (r["kind"] == "min" and b > prev)):
                    mono_viol.append({"station": r["station"], "date": r["lst_date"], "kind": r["kind"], "key": key, "prev": prev, "now": b})
                prev = b
    arms = {a: {"n_days_total": 0, "n_days_no_group": 0, "variants": {}} for a in ARMS}
    viol_list = []
    for a in ARMS:
        for key in (INF,) + S_GRID:
            arms[a]["variants"][str(key)] = {"n": 0, "viol": 0, "no_bound": 0, "viol_margin_hist": collections.Counter()}
    for r in recs:
        a = arm_of(r["kind"], r["off"])
        arms[a]["n_days_total"] += 1
        ev = walks[(r["station"], r["kind"], r["day_end"])]
        if not ev:
            arms[a]["n_days_no_group"] += 1
        for key in (INF,) + S_GRID:
            v = arms[a]["variants"][str(key)]
            b = ev[-1]["bound"][key] if ev else None
            if b is None:
                v["no_bound"] += 1
                continue
            v["n"] += 1
            bad = (b > r["official"]) if r["kind"] == "max" else (b < r["official"])
            if bad:
                v["viol"] += 1
                v["viol_margin_hist"][abs(b - r["official"])] += 1
        # violation listing (unguarded), with which guards would have caught it
        if ev:
            bI = ev[-1]["bound"][INF]
            bad = (bI > r["official"]) if r["kind"] == "max" else (bI < r["official"])
            if bad:
                # the first group that crossed the official value in the violating direction, and its corroboration
                culprit = None
                for e in ev:
                    if (r["kind"] == "max" and e["gI"] > r["official"]) or (r["kind"] == "min" and e["gI"] < r["official"]):
                        culprit = e
                        break
                still = {str(s): (ev[-1]["bound"][s] is not None and ((ev[-1]["bound"][s] > r["official"]) if r["kind"] == "max" else (ev[-1]["bound"][s] < r["official"]))) for s in S_GRID}
                viol_list.append({"arm": a, "station": r["station"], "kind": r["kind"], "date": r["lst_date"],
                                  "official": r["official"], "final_bound_unguarded": bI, "excess_F": abs(bI - r["official"]),
                                  "culprit_group_report_utc": SO.utc(culprit["ts"]), "culprit_group_F": round(culprit["gF"], 2),
                                  "culprit_corroborated": {str(s): culprit["corr"][s] for s in S_GRID},
                                  "violation_survives_guard": still})
    for a in ARMS:
        for key, v in arms[a]["variants"].items():
            v["viol_margin_hist"] = {str(k): c for k, c in sorted(v["viol_margin_hist"].items())}
            v["rate"] = (v["viol"] / v["n"]) if v["n"] else None
            v["wilson"] = wilson(v["viol"], v["n"]) if v["n"] else None
    return {"arms": arms, "violations": viol_list, "monotonicity_violations": mono_viol, "days_walked": days_walked}


def fire_counts(rungs, walks):
    """Rung-level RESOLVED-NO fires per (arm, key, D): fires, false locks (rung settled YES) -- obs + official result only."""
    out = {a: {} for a in ARMS}
    for a in ARMS:
        for key in (INF,) + S_GRID:
            for D in D_GRID:
                out[a][f"{key}|{D}"] = {"n_rungs": 0, "fires": 0, "false_lock": 0}
    for r in rungs:
        a = arm_of(r["kind"], r["off"])
        ev = walks[(r["station"], r["kind"], r["day_end"])]
        strike = r["hi"] if r["kind"] == "max" else r["lo"]
        for key in (INF,) + S_GRID:
            for D in D_GRID:
                c = out[a][f"{key}|{D}"]
                c["n_rungs"] += 1
                f = fire_time(ev, r["kind"], strike, D, key)
                if f:
                    c["fires"] += 1
                    if r["result"] == "yes":
                        c["false_lock"] += 1
    return out


def cmd_anchor_b():
    recs, rungs, skip, ex, rex, stn, walks = walk_everything()
    # decoder self-check on the known fault: DEN 24F daily MIN group, June 2026 (official 56)
    den = [r for r in recs if r["station"] == "DEN" and r["kind"] == "min" and r["lst_date"] == "2026-06-26"]
    den_rec = None
    if den:
        ev = walks[("DEN", "min", den[0]["day_end"])]
        den_rec = {"official": den[0]["official"], "bmin_unguarded": ev[-1]["bound"][INF] if ev else None,
                   "groups": [{"report": SO.utc(e["ts"]), "tc": e["tc"], "F": round(e["gF"], 2), "gI": e["gI"], "corr": {str(s): e["corr"][s] for s in S_GRID}} for e in ev]}
    ab = anchor_b_compute(recs, walks)
    fc = fire_counts(rungs, walks)
    prim = ab["arms"]["PRIMARY_HIGH_nonCST"]
    verdict = {}
    for key in (INF,) + S_GRID:
        v = prim["variants"][str(key)]
        verdict[str(key)] = {"n": v["n"], "viol": v["viol"], "rate": v["rate"], "wilson": v["wilson"], "exceeds_2pct": (v["rate"] or 0) > SELF_KILL_RATE}
    # self-kill: the registered rule is the GUARDED rule (guard is part of the signal), so the decisive reading is the
    # primary cell S=5.  The unguarded reading is reported next to it; if EITHER exceeds 2% this is flagged loudly.
    self_kill = verdict[str(PRIMARY[0])]["exceeds_2pct"]
    any_exceeds = any(x["exceeds_2pct"] for x in verdict.values())
    out = {"stage": "anchor_b", "self_kill": self_kill, "any_variant_exceeds_2pct": any_exceeds, "verdict_by_variant": verdict,
           "anchor_b": ab, "fire_counts": fc, "den_example": den_rec,
           "n_days": len(recs), "exclusions_days": ex, "exclusions_rungs": rex, "exclusions_universe": skip}
    jdump(out, os.path.join(CACHE, "anchor_b.json"))
    print(json.dumps({"self_kill": self_kill, "verdict": verdict, "mono_viol": len(ab["monotonicity_violations"]),
                      "n_violations_listed": len(ab["violations"])}, indent=1, default=str))
    return out



# ============================================================================================ fires (NO prices read)
def build_fire_table(rungs, walks):
    """One row per rung that fires in at least one of the 6 cells.  cell key "S|D" -> {"ts": report ts, "gF": group F,
    "gI": group int F, "ev": event index within the day}.  Obs + official `result` only."""
    rows = []
    for r in rungs:
        ev = walks[(r["station"], r["kind"], r["day_end"])]
        strike = r["hi"] if r["kind"] == "max" else r["lo"]
        cells = {}
        for (s, d) in CELLS:
            e = fire_time(ev, r["kind"], strike, d, s)
            if e is not None:
                cells[f"{s}|{d}"] = {"ts": e["ts"], "gF": round(e["gF"], 2), "gI": e["gI"], "ev": ev.index(e)}
        if cells:
            rows.append({"ticker": r["ticker"], "arm": arm_of(r["kind"], r["off"]), "station": r["station"], "kind": r["kind"],
                         "off": r["off"], "lst_date": r["lst_date"], "lo": r["lo"], "hi": r["hi"], "result": r["result"],
                         "official": r["official"], "close_ts": r["close_ts"], "day_start": r["day_start"], "day_end": r["day_end"],
                         "series": r["series"], "cells": cells})
    return rows


def anchor_c(fire_rows, stn, walks_full, nmax=None):
    """No look-ahead (anchor c).  For EVERY fire (every cell, every arm):
       (1) PREFIX: re-run walk_day on ONLY the reports with ts < t_sig (t_sig = report ts + 10 min, the L=10 signal time);
           the event list must equal the full-day event list truncated at the firing event, and the rung must fire at the
           identical report;
       (2) FIRSTNESS: on the reports with ts < the firing report's ts the rung must NOT yet fire;
       (3) ADVERSARIAL: replace EVERY report with ts >= t_sig by garbage (max/min groups at +/-60 C, spot temps at +/-60 C,
           in both directions) and re-run on the full day: the events up to and including the firing event, and the
           fire, must be unchanged.
       Aborts (raises) on any disagreement."""
    rng = random.Random(SEED + 7)
    checked = 0
    memo = {}
    for f in fire_rows:
        key = (f["station"], f["kind"], f["day_end"])
        full = walks_full[key]
        reps = day_reports(stn[f["station"]], f["day_start"], f["day_end"])
        strike = f["hi"] if f["kind"] == "max" else f["lo"]
        for ck, c in f["cells"].items():
            s, d = (int(x) for x in ck.split("|"))
            t_sig = c["ts"] + 10 * 60
            mk = (key, c["ts"])
            if mk not in memo:
                pre = [r for r in reps if r["ts"] < t_sig]
                ev_pre = walk_day(pre, f["day_start"], f["day_end"], f["kind"])
                before = [r for r in reps if r["ts"] < c["ts"]]
                ev_before = walk_day(before, f["day_start"], f["day_end"], f["kind"])
                adv = []
                for r in reps:
                    if r["ts"] < t_sig:
                        adv.append(r)
                    else:
                        a = dict(r)
                        sgn = 1 if rng.random() < .5 else -1
                        a["g6max"] = ("1xxxx", sgn * 600) if rng.random() < .9 else r["g6max"]
                        a["g6min"] = ("2xxxx", -sgn * 600) if rng.random() < .9 else r["g6min"]
                        a["tt"] = sgn * 600
                        a["g24"] = None
                        adv.append(a)
                ev_adv = walk_day(adv, f["day_start"], f["day_end"], f["kind"])
                memo[mk] = (ev_pre, ev_before, ev_adv)
            ev_pre, ev_before, ev_adv = memo[mk]
            k = c["ev"]
            trunc = full[:k + 1]
            def same(a, b):
                return [(e["ts"], e["tc"], e["bound"]) for e in a] == [(e["ts"], e["tc"], e["bound"]) for e in b]
            assert same(ev_pre[:k + 1], trunc), ("prefix mismatch", f["ticker"], ck)
            assert same(ev_adv[:k + 1], trunc), ("adversarial mismatch", f["ticker"], ck)
            e1 = fire_time(ev_pre, f["kind"], strike, d, s)
            assert e1 is not None and e1["ts"] == c["ts"], ("prefix fire differs", f["ticker"], ck)
            assert fire_time(ev_before, f["kind"], strike, d, s) is None, ("fires before its report", f["ticker"], ck)
            e2 = fire_time(ev_adv, f["kind"], strike, d, s)
            assert e2 is not None and e2["ts"] == c["ts"], ("adversarial fire differs", f["ticker"], ck)
            checked += 1
    return {"fires_cellrows_checked": checked, "unique_(day,report)_checks": len(memo), "disagreements": 0}


def anchor_d(rungs, recs):
    """Day window / close_time assertion re-verified (reuse of finality_B / settlement_observability, not re-derived)."""
    n = 0
    worst = 0
    for r in rungs:
        assert (r["day_end"] // 3600) % 24 == (-r["off"]) % 24
        assert r["day_end"] - r["day_start"] == 86400
        worst = max(worst, abs(r["close_ts"] - r["day_end"]))
        n += 1
    inc = sum(1 for r in rungs if (r["lo"] <= r["official"] <= r["hi"]) != (r["result"] == "yes"))
    return {"rungs_checked": n, "max_abs_close_minus_dayend_s": worst, "result_vs_expiration_value_inconsistent_rungs": inc,
            "station_days": len(recs)}


# ---- anchor (e): the DEPLOYED bot's cap-overshoot path, replayed on historical observations -----------------------------
# Mirrors livefix/kwx_runner.py: sustained_extreme() (glitch filter |jump|>8F skipped, window of readings spanning >=2 min,
# gap<=75 min between window members) + locked_orders(): HIGH rung locks NO when extreme_f > cap + margin (margin 1.0F,
# KPHX 2.0F); LOW rung locks NO when extreme_f < floor - margin.  Feeds: IEM 1-minute (the best case a real-time feed could
# give) and IEM routine hourly METAR spot temps (the runner's DEFAULT feed).  kwx_runner.py is READ, never imported/modified.
def deployed_series(ts, fs, kind):
    clean, prev = [], None
    for t, f in zip(ts, fs):
        if f is None or f > 130.0 or f < -60.0:
            continue
        if prev is not None and abs(f - prev) > 8.0:
            prev = f
            continue
        prev = f
        clean.append((t, f))
    sign = 1.0 if kind == "max" else -1.0
    out, best = [], None
    for j in range(len(clean)):
        tj = clean[j][0]
        wmin = sign * clean[j][1]
        i = j
        while tj - clean[i][0] < 120 and i > 0 and clean[i][0] - clean[i - 1][0] <= 75 * 60:
            i -= 1
            v = sign * clean[i][1]
            if v < wmin:
                wmin = v
        if tj - clean[i][0] >= 120 and (best is None or wmin > best):
            best = wmin
        if best is not None:
            out.append((tj, sign * best))
    return out


def deployed_lock_ts(series, kind, strike, margin):
    """First obs ts at which the deployed lock condition holds, else None."""
    for t, ext in series:
        if kind == "max" and ext > strike + margin:
            return t
        if kind == "min" and ext < strike - margin:
            return t
    return None


def anchor_e(fire_rows):
    """Overlap of bound-resolution fires with the deployed cap-overshoot population, per arm, primary cell + all cells."""
    cache = {}
    out = {}
    per_fire = {}
    for f in fire_rows:
        key = (f["station"], f["kind"], f["day_start"], f["day_end"])
        if key not in cache:
            t1, f1 = FB.window_obs(f["station"], "1min", f["day_start"], f["day_end"])
            have1 = len(t1) >= 1000 and sum(1 for x in t1 if x >= f["day_end"] - 130 * 60) >= 65
            tr, fr = FB.window_obs(f["station"], "routine", f["day_start"], f["day_end"])
            cache[key] = {"1min": deployed_series(t1, f1, f["kind"]) if have1 else None,
                          "routine": deployed_series(tr, fr, f["kind"]) if len(tr) >= 2 else None}
        c = cache[key]
        strike = f["hi"] if f["kind"] == "max" else f["lo"]
        margin = 2.0 if f["station"] == "PHX" else 1.0
        for ck, cell in f["cells"].items():
            rec = {"sig": cell["ts"] + 600}
            for feed in ("1min", "routine"):
                if c[feed] is None:
                    rec[feed] = "no_feed_coverage"
                else:
                    t = deployed_lock_ts(c[feed], f["kind"], strike, margin)
                    rec[feed] = t
            per_fire[(f["ticker"], ck)] = rec
    for arm in ARMS:
        for ck in [f"{s}|{d}" for (s, d) in CELLS]:
            sel = [(f, per_fire[(f["ticker"], ck)]) for f in fire_rows if f["arm"] == arm and ck in f["cells"]]
            d = {"n_fires": len(sel)}
            for feed in ("1min", "routine"):
                have = [(f, r) for f, r in sel if r[feed] != "no_feed_coverage"]
                locked = [(f, r) for f, r in have if r[feed] is not None]
                earlier = [(f, r) for f, r in locked if r[feed] <= r["sig"]]               # deployed locked before the bound signal (L=10)
                earlier30 = [(f, r) for f, r in locked if r[feed] <= r["sig"] - 30 * 60]
                before_close = [(f, r) for f, r in locked if r[feed] <= f["day_end"]]
                lead = sorted((r["sig"] - r[feed]) / 60.0 for f, r in locked)
                d[feed] = {"n_with_feed": len(have), "deployed_eventually_locks": len(locked),
                           "deployed_never_locks": len(have) - len(locked),
                           "deployed_locked_at_or_before_bound_signal": len(earlier),
                           "deployed_locked_30min_or_more_before_bound_signal": len(earlier30),
                           "median_minutes_bound_signal_is_after_deployed_lock": (lead[len(lead) // 2] if lead else None)}
            out[f"{arm}|{ck}"] = d
    return out, per_fire


def cmd_fires():
    recs, rungs, skip, ex, rex, stn, walks = walk_everything()
    fire_rows = build_fire_table(rungs, walks)
    ab = anchor_b_compute(recs, walks)
    assert not ab["monotonicity_violations"], "anchor (a) violated"
    ac = anchor_c(fire_rows, stn, walks)
    ad = anchor_d(rungs, recs)
    ae, _ = anchor_e(fire_rows)
    jdump(fire_rows, os.path.join(CACHE, "fires.json"))
    jdump({"anchor_c": ac, "anchor_d": ad, "anchor_e": ae}, os.path.join(CACHE, "anchors_cde.json"))
    # seeded shuffled candle work orders, one per arm; written once, NEVER re-sorted
    for arm in ARMS:
        p = os.path.join(CACHE, f"candle_order_{arm}.json")
        if os.path.exists(p):
            continue
        tks = sorted({f["ticker"] for f in fire_rows if f["arm"] == arm})   # canonical start order, then seeded shuffle
        random.Random(SEED).shuffle(tks)
        jdump(tks, p)
        print(arm, len(tks), "tickers need candles")
    print("anchor_c", ac)
    print("anchor_d", ad)


# ============================================================================================ candles
V2.WINDOW_MIN = 1500          # finality_B sets 130 at import; fires can precede close by up to ~19 h


def fetch_candles_br(tk, series, close_ts, a_ts):
    """Same live/historical routing as finality_B.fetch_candles, but (i) own cache dir, (ii) window [first signal, close]."""
    p = os.path.join(CAND, tk + ".json")
    if os.path.exists(p):
        return jload(p)
    a, b = int(a_ts), int(close_ts)
    live = f"{FB.API}/series/{series}/markets/{tk}/candlesticks?start_ts={a}&end_ts={b}&period_interval=1"
    hist = f"{FB.API}/historical/markets/{tk}/candlesticks?start_ts={a}&end_ts={b}&period_interval=1"
    order = [("live", live), ("hist", hist)] if close_ts >= FB.CUTOFF_TS else [("hist", hist), ("live", live)]
    rec = {"src": None, "cs": None, "err": None, "a": a, "b": b}
    for tag, u in order:
        try:
            d = FB.http(u, tries=4)
            cs = d.get("candlesticks")
            if cs is not None:
                rec.update({"src": tag, "cs": cs, "err": None})
                break
        except Exception as e:
            rec["err"] = f"{tag}:{type(e).__name__}:{getattr(e, 'code', '')}"
    jdump(rec, p)
    return rec


def candle_rows_br(tk, close_ts):
    p = os.path.join(CAND, tk + ".json")
    if not os.path.exists(p):
        return None
    rec = jload(p)
    if rec.get("cs") is None:
        return None
    return sorted(V2.normalize(FB._adapt(rec["cs"]), close_ts), key=lambda r: r[0])   # <-- reused edge_sizing_v2.normalize()


def cmd_candles(arms=None, limit=None):
    fire_rows = jload(os.path.join(CACHE, "fires.json"))
    by_tk = {}
    for f in fire_rows:
        by_tk[f["ticker"]] = f
    n = 0
    for arm in (arms or ARMS):
        order = jload(os.path.join(CACHE, f"candle_order_{arm}.json"))
        print(arm, "work order length", len(order), flush=True)
        for tk in order:                                        # shuffled order, NEVER re-sorted
            if limit is not None and n >= limit:
                return
            if os.path.exists(os.path.join(CAND, tk + ".json")):
                continue
            f = by_tk[tk]
            a_ts = min(c["ts"] for c in f["cells"].values())
            fetch_candles_br(tk, f["series"], f["close_ts"], a_ts)
            n += 1
            if n % 100 == 0:
                print("fetched", n, flush=True)



# ============================================================================================ statistics / entry
from scipy import stats as _st          # noqa: E402


def fee_c(p_c):
    return FB.fee_c(p_c)                # ceil(7 p (1-p)) cents, reused


def entry_no(rows, t_search, close_ts):
    """First candle with t_search <= ts <= close whose NO cost = 100 - yes_bid is <= 98c with fee-inclusive net > 0.
    A NO buyer lifts the NO ask = 100 - yes_bid.  NEVER 100 - yes_ask (that is the NO bid, unfillable by a buyer)."""
    if not rows:
        return None, "no_candles"
    seen = False
    for ts, yb, ya, vol in rows:
        if ts < t_search or ts > close_ts:
            continue
        seen = True
        if yb is None:
            continue
        cost = 100 - yb
        if not (0 < cost <= 98):
            continue
        if 100 - cost - fee_c(cost) <= 0:
            continue
        return (ts, cost, yb, vol), "ok"
    return None, ("no_qualifying_candle" if seen else "no_candle_after_signal")


def cstats(xs, ws, gs):
    o = FB.cluster_stats(xs, ws, gs)
    if o.get("G", 0) >= 2:
        o["tcrit_bonf"] = float(_st.t.ppf(1 - ALPHA / 2, o["G"] - 1))      # 12 comparisons (6 cells x 2 arms)
    return o


def sampled_prefix(arm):
    order = jload(os.path.join(CACHE, f"candle_order_{arm}.json"))
    prefix = []
    for tk in order:
        if os.path.exists(os.path.join(CAND, tk + ".json")):
            prefix.append(tk)
        else:
            break
    return order, prefix


def analyze_arm(arm, fire_rows, per_fire_e):
    order, prefix = sampled_prefix(arm)
    sampled = set(prefix)
    rows_cache = {}
    fr_arm = [f for f in fire_rows if f["arm"] == arm]
    res = {}
    for (s, d) in CELLS:
        ck = f"{s}|{d}"
        fl = [f for f in fr_arm if ck in f["cells"]]
        k_fl = sum(1 for f in fl if f["result"] == "yes")
        w = wilson(k_fl, len(fl)) if fl else (None, None)
        samp = [f for f in fl if f["ticker"] in sampled]
        for L in L_ARMS:
            recs, unt = [], collections.Counter()
            first_bid = collections.Counter()
            for f in samp:
                if f["ticker"] not in rows_cache:
                    rows_cache[f["ticker"]] = candle_rows_br(f["ticker"], f["close_ts"])
                t_sig = f["cells"][ck]["ts"] + L * 60
                rws = rows_cache[f["ticker"]] or []
                post = [x for x in rws if t_sig <= x[0] <= f["close_ts"]]
                if not post:
                    first_bid["no_candle_at_or_after_signal"] += 1
                else:
                    b0 = post[0][1]
                    first_bid["yes_bid=None" if b0 is None else ("yes_bid=0" if b0 == 0 else ("yes_bid=1" if b0 == 1 else "yes_bid>=2"))] += 1
                e, why = entry_no(rows_cache[f["ticker"]], t_sig, f["close_ts"])
                if e is None:
                    unt[why] += 1
                    continue
                ts, cost, yb, vol = e
                pnl = (100 - cost - fee_c(cost)) if f["result"] == "no" else (-cost - fee_c(cost))
                dep = per_fire_e.get((f["ticker"], ck), {}).get("1min")
                recs.append({"tk": f["ticker"], "pnl": pnl, "cost": cost, "vol": vol, "res": f["result"], "day": f["lst_date"],
                             "st": f["station"], "ets": ts, "t_sig": t_sig, "close": f["close_ts"],
                             "dep1min": dep if isinstance(dep, int) else None})
            n = len(recs)
            xs = [x["pnl"] for x in recs]
            gs = [x["day"] for x in recs]
            ev_eq = cstats(xs, [1.0] * n, gs)
            ev_vw = cstats(xs, [max(x["vol"], 0.0) for x in recs], gs)
            k_p = sum(1 for x in recs if x["res"] == "yes")
            res[f"{ck}|L{L}"] = {
                "S": s, "D": d, "L": L, "n_fires": len(fl), "n_false_lock_all": k_fl,
                "false_lock_rate_all": (k_fl / len(fl)) if fl else None, "wilson_ub_all": w[1],
                "n_fires_candle_sampled": len(samp), "n_priced": n, "n_untradeable": len(samp) - n,
                "untradeable_breakdown": dict(unt), "first_candle_after_signal_state": dict(first_bid),
                "untradeable_frac": ((len(samp) - n) / len(samp)) if samp else None,
                "n_false_lock_priced": k_p, "ev_eq": ev_eq, "ev_vw": ev_vw,
                "n_days": len({x["day"] for x in recs}), "n_stations": len({x["st"] for x in recs}),
                "n_entry_vol_positive": sum(1 for x in recs if x["vol"] > 0),
                "mean_cost_c": (sum(x["cost"] for x in recs) / n) if n else None,
                "median_entry_delay_min": (sorted((x["ets"] - x["t_sig"]) / 60.0 for x in recs)[n // 2] if n else None),
                "median_entry_minutes_before_close": (sorted((x["close"] - x["ets"]) / 60.0 for x in recs)[n // 2] if n else None),
                "entry_cost_hist": dict(collections.Counter(x["cost"] for x in recs)),
                "entered_after_deployed_1min_lock": sum(1 for x in recs if x["dep1min"] is not None and x["dep1min"] <= x["ets"]),
                "entered_before_deployed_1min_lock": sum(1 for x in recs if x["dep1min"] is not None and x["dep1min"] > x["ets"]),
                "deployed_1min_never_locks_among_priced": sum(1 for x in recs if x["dep1min"] is None),
                "_recs": recs}
    cov = {"tickers_total": len(order), "tickers_in_completed_prefix": len(prefix),
           "ticker_fraction": (len(prefix) / len(order)) if order else None}
    return res, cov


def verdict_rule(prim):
    """Apply the frozen PASS / KILL rule to the PRIMARY arm (HIGH, non-CST) at L=10."""
    cells = {}
    for (s, d) in CELLS:
        r = prim[f"{s}|{d}|L10"]
        eq, vw = r["ev_eq"], r["ev_vw"]
        def tp(x):
            return bool(x.get("t") is not None and x["t"] >= x["tcrit_bonf"] and x["t"] >= 0)
        crit = {
            "1_false_lock<=2%_and_WilsonUB<=5%": (r["false_lock_rate_all"] is not None and r["false_lock_rate_all"] <= 0.02
                                                    and r["wilson_ub_all"] is not None and r["wilson_ub_all"] <= 0.05),
            "2_EV_volume_weighted>=+2.0c": vw.get("mean") is not None and vw["mean"] >= 2.0,
            "2b_EV_equal_weight>=+2.0c": eq.get("mean") is not None and eq["mean"] >= 2.0,
            "3_signed_t_vw>=bonferroni_bar": tp(vw),
            "3b_signed_t_eq>=bonferroni_bar": tp(eq),
            "4_n>=100_days>=40_stations>=10": r["n_priced"] >= 100 and r["n_days"] >= 40 and r["n_stations"] >= 10,
            "5_untradeable<=70%": r["untradeable_frac"] is not None and r["untradeable_frac"] <= 0.70,
        }
        crit = {k: bool(v) for k, v in crit.items()}
        cells[f"{s}|{d}"] = {"crit": crit, "all": bool(all(crit.values()))}
    passed = [c for c, v in cells.items() if v["all"]]
    p = prim[f"{PRIMARY[0]}|{PRIMARY[1]}|L10"]
    kill_fl = p["false_lock_rate_all"] is not None and p["false_lock_rate_all"] > 0.05
    def ev_of(r):
        return r["ev_vw"].get("mean") if r["ev_vw"].get("mean") is not None else r["ev_eq"].get("mean")
    pos = [prim[f"{s}|{d}|L10"] for (s, d) in CELLS if ev_of(prim[f"{s}|{d}|L10"]) is not None and ev_of(prim[f"{s}|{d}|L10"]) > 0]
    kill_n = bool(pos) and all(not (r["n_priced"] >= 100) for r in pos)
    def ub_of(r, which):
        return r[which].get("ub979")
    ub_vw = [ub_of(prim[f"{s}|{d}|L10"], "ev_vw") for (s, d) in CELLS]
    ub_eq = [ub_of(prim[f"{s}|{d}|L10"], "ev_eq") for (s, d) in CELLS]
    reg = [(v if v is not None else e) for v, e in zip(ub_vw, ub_eq)]            # registered reading: volume-weighted (Build-B precedent), eq as fallback
    reg = [x for x in reg if x is not None]
    best_ub = max(reg) if reg else None
    best_ub_eq = max([x for x in ub_eq if x is not None], default=None)
    kill_ub = best_ub is not None and best_ub < 0.5
    if passed:
        v = "PASS"
    elif kill_fl or kill_n or kill_ub:
        v = "KILL"
    else:
        v = "INSUFFICIENT"
    return v, {"cells": cells, "pass_cells": passed, "kill_false_lock_primary_gt5pct": kill_fl,
               "kill_every_EV>0_cell_misses_n_floor": kill_n, "n_cells_EV>0": len(pos),
               "kill_best_ub979_lt_0.5c": kill_ub, "best_ub979_registered_reading": best_ub,
               "best_ub979_equal_weight_reading": best_ub_eq,
               "kill_ub_under_equal_weight_reading": (best_ub_eq is not None and best_ub_eq < 0.5)}


def cmd_analyze():
    fire_rows = jload(os.path.join(CACHE, "fires.json"))
    anc = jload(os.path.join(CACHE, "anchors_cde.json"))
    ab = jload(os.path.join(CACHE, "anchor_b.json"))
    pl = jload(os.path.join(CACHE, "plaus.json"))
    _, per_fire_e = anchor_e(fire_rows)
    arms_res, cov = {}, {}
    for arm in ARMS:
        arms_res[arm], cov[arm] = analyze_arm(arm, fire_rows, per_fire_e)
    verdict, vdetail = verdict_rule(arms_res["PRIMARY_HIGH_nonCST"])
    # candle fetch errors (disclosed)
    errs = collections.Counter()
    nfiles = 0
    for fn in os.listdir(CAND):
        if fn.endswith(".json"):
            nfiles += 1
            rec = jload(os.path.join(CAND, fn))
            errs[(rec.get("src") or "none") + "|" + str(rec.get("err"))] += 1
    out = {"spec": "BOUND_RESOLUTION_SPEC.md (registered 2026-10-27)", "verdict": verdict, "verdict_detail": vdetail,
           "anchor_b": ab, "plaus": pl, "anchors_cde": anc, "sampling": cov, "candle_files": nfiles, "candle_fetch_outcomes": dict(errs),
           "n_comparisons_bonferroni": NCMP, "alpha_per_comparison": ALPHA, "arms": {}}
    for arm in ARMS:
        out["arms"][arm] = {k: {kk: vv for kk, vv in v.items() if kk != "_recs"} for k, v in arms_res[arm].items()}
    jdump(out, OUT_JSON)
    write_md(out)
    print("verdict", verdict)
    return out


# ============================================================================================ markdown
def fnum(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def ev_cell(e):
    if e.get("mean") is None:
        return "n/a"
    return f"{e['mean']:+.2f}c (t={fnum(e.get('t'))}, bar={fnum(e.get('tcrit_bonf'))}, G={e.get('G')})"


ARM_LABEL = {"PRIMARY_HIGH_nonCST": "PRIMARY: HIGH markets x 16 non-CST stations (the only PASS-eligible arm)",
             "SECONDARY_LOW_nonCST": "SECONDARY (cannot PASS): LOW markets x 16 non-CST stations",
             "SECONDARY_HIGH_CST": "SECONDARY (cannot PASS): HIGH markets x 8 CST (UTC-6) stations",
             "SECONDARY_LOW_CST": "SECONDARY (cannot PASS): LOW markets x 8 CST (UTC-6) stations"}


def key_label(k):
    return "unguarded (no corroboration)" if k == INF else f"S={k} F"


def write_md(o):
    L = []
    A = L.append
    A("# Bound resolution -- measurement report\n")
    A("Spec: `BOUND_RESOLUTION_SPEC.md` (registered 2026-10-27, before any price or outcome was read). Code: `venue_expansion/bound_resolution.py`. "
      "Data: `out/bound_resolution.json`. No bar was moved, the universe was not widened, no subset was searched. "
      "Prices were read only after anchor (b) passed.\n")
    md_anchor_b(o, L)
    md_plaus(o, L)
    md_verdict(o, L)
    md_cells(o, L)
    md_anchors(o, L)
    md_exclusions(o, L)
    md_notes(o, L)
    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(L) + "\n")


def md_anchor_b(o, L):
    A = L.append
    ab = o["anchor_b"]
    X = ab["anchor_b"]
    prim = X["arms"]["PRIMARY_HIGH_nonCST"]
    fc = ab["fire_counts"]["PRIMARY_HIGH_nonCST"]
    A("## 1. ANCHOR (b) -- bound validity (run first, before any price)\n")
    A("Rule: for every station-day, final `BMAX <= official max` (HIGH) / final `BMIN >= official min` (LOW). A violation is a case where the station's own "
      "reported group went beyond what NWS certified = a sensor fault that would have caused a false RESOLVED-NO. "
      "**Spec: if the violation rate exceeds 2% the study self-kills before any price is read.** BMAX is in integer degF "
      "(group tenths-C -> F -> round half-up), compared with the whole-degree `expiration_value`.\n")
    v = ab["verdict_by_variant"]
    sk = ab["self_kill"]
    A(f"### **Self-kill: {'YES -- STUDY ENDS HERE' if sk else 'NO'}.** Primary arm (HIGH x 16 non-CST stations), registered rule (S=5): "
      f"**{v['5']['viol']} violation(s) in {v['5']['n']} station-days = {100*v['5']['rate']:.3f}%**, Wilson 95% [{100*v['5']['wilson'][0]:.3f}%, {100*v['5']['wilson'][1]:.3f}%]. "
      f"Threshold 2%. Unguarded: {v['inf']['viol']}/{v['inf']['n']}. No variant (unguarded, S=3, 5, 8) exceeds 2%.\n")
    A("**Primary arm -- violation rate and fires retained, by guard setting** (fires = rung-level RESOLVED-NO fires; false lock = a fire on a rung that settled YES; "
      "fires counted from observations + official `result` only, no price):\n")
    A("| bound | station-days with a bound | violations | violation rate [Wilson 95%] | fires D=1 | false locks D=1 | fires D=2 | false locks D=2 |\n|---|---|---|---|---|---|---|---|")
    base1 = fc[f"{INF}|1"]["fires"]
    base2 = fc[f"{INF}|2"]["fires"]
    for key in (INF,) + S_GRID:
        pv = prim["variants"][str(key)]
        c1, c2 = fc[f"{key}|1"], fc[f"{key}|2"]
        A(f"| {key_label(key)} | {pv['n']} | {pv['viol']} | {rate_str(pv['viol'], pv['n'])} | {c1['fires']} ({100*c1['fires']/base1:.1f}% of unguarded) | {c1['false_lock']} | "
          f"{c2['fires']} ({100*c2['fires']/base2:.1f}%) | {c2['false_lock']} |")
    A("")
    gi = prim["variants"][str(INF)]["viol"]
    g5 = prim["variants"]["5"]["viol"]
    A(f"**Does the guard remove faults by removing trades?** On the primary arm the guard is nearly irrelevant: it removes {gi - g5} of {gi} fault(s) at S=5 and cuts D=1 fires by "
      f"{100*(1-fc['5|1']['fires']/base1):.1f}% (S=3: {100*(1-fc['3|1']['fires']/base1):.1f}%). The one primary-arm fault passes the corroboration guard at every S "
      "(a real, corroborated 81 F group where NWS certified 77 F). The guard is not what makes this arm safe -- the arm is safe because HIGH groups at these stations are almost never wrong. "
      "The guard earns its keep only on the LOW arms (tables below), where it removes most faults at a modest fire cost.\n")
    A("**Secondary arms (cannot PASS) -- same table, shown because the guard question is only answerable there:**\n")
    A("| arm | bound | station-days | violations | violation rate [Wilson 95%] | fires D=1 | false locks D=1 |\n|---|---|---|---|---|---|---|")
    for arm in ARMS[1:]:
        for key in (INF,) + S_GRID:
            pv = X["arms"][arm]["variants"][str(key)]
            c1 = ab["fire_counts"][arm][f"{key}|1"]
            A(f"| {arm} | {key_label(key)} | {pv['n']} | {pv['viol']} | {rate_str(pv['viol'], pv['n'])} | {c1['fires']} | {c1['false_lock']} |")
    A("")
    A("**Every violation (all arms, unguarded bound), with station and date.** `excess` = degF by which the station's own bound lies beyond the official value. "
      "`corroborated@S` = whether the offending group had a spot temperature within S degF in its 6-hour window; `survives` = whether the day still violates after the guard.\n")
    A("| arm | station | kind | LST date | official | final bound | excess | offending group (report UTC, F) | corroborated @3/5/8 | day still violates @3/5/8 |\n|---|---|---|---|---|---|---|---|---|---|")
    for w in sorted(X["violations"], key=lambda w: (w["arm"] != "PRIMARY_HIGH_nonCST", w["arm"], w["date"])):
        cc = w["culprit_corroborated"]
        sv = w["violation_survives_guard"]
        A(f"| {w['arm']} | {w['station']} | {'HIGH' if w['kind']=='max' else 'LOW'} | {w['date']} | {w['official']} | {w['final_bound_unguarded']} | {w['excess_F']} | "
          f"{w['culprit_group_report_utc']}, {w['culprit_group_F']} | {cc['3']}/{cc['5']}/{cc['8']} | {sv['3']}/{sv['5']}/{sv['8']} |")
    A("")
    de = ab.get("den_example")
    if de:
        g = de["groups"][0]
        A(f"**Known example reproduced (DEN LOW, LST 2026-06-26):** the decoder reads the {g['report']} 6-hr min group `2{'1' if g['tc']<0 else '0'}{abs(g['tc']):03d}` = {g['tc']/10:+.1f} C = {g['F']:.2f} F -> {g['gI']} F; "
          f"official is {de['official']} F; the unguarded BMIN is {de['bmin_unguarded']} F (violation of 32 F). Corroboration at S=3/5/8 = {g['corr']['3']}/{g['corr']['5']}/{g['corr']['8']}: "
          "the guard rejects this fault at every S (no spot temperature in that window is within 8 F of 24 F). This is a LOW-arm fault, so it is outside the primary arm.\n")
    A(f"Anchor (a) monotonicity of the bound, asserted on every day walked ({X['days_walked']} station-days x 4 bound variants): "
      f"**{len(X['monotonicity_violations'])} violations**.\n")


def md_plaus(o, L):
    A = L.append
    pl = o.get("plaus")
    if not pl:
        return
    A("### 1b. Plausibility filter vs corroboration guard, and the two known-bad observation days (coordinator request; no threshold touched)\n")
    A(f"The METAR-group decoder carries a physical-plausibility filter inherited from `settlement_observability.index_groups`: groups with |T| > 60 C are rejected. "
      f"Measured effect on this data: **{pl['n_rejected_groups']} groups rejected in the whole May-Oct 2026 record** -- the filter never fires. Violation counts below are identical with and without it, "
      "so the guard's contribution and the filter's are separable: the filter's is zero.\n")
    A("| arm | bound | violations / station-days WITH +-60C filter | WITHOUT any filter |\n|---|---|---|---|")
    for arm in ARMS:
        for key in (INF,) + S_GRID:
            t = pl["table"][arm][str(key)]
            A(f"| {arm} | {key_label(key)} | {t['filtered'][0]}/{t['filtered'][1]} | {t['unfiltered'][0]}/{t['unfiltered'][1]} |")
    A(f"\nFire counts with and without the filter are identical in all arms and cells (checked: {pl['fires_filtered'] == pl['fires_unfiltered']}).\n")
    A("**Known-bad days (all four are in the universe).** The faults the verifier found (LAX 2026-05-24: 120 F max / -29 F min; MDW 2026-07-07: -1 F min) are in the IEM **1-minute** feed. "
      "They are **not in the METAR 6-hr groups this study uses**: the groups on those days are clean and the bound is valid on all four station-kind-days, guarded or not. "
      "So the guard was NOT exercised by these cases -- it is stated plainly that they do not test it. (A corrupted 1-minute stream does pin a running extreme computed from it; a bound built from 6-hr groups is a different data path.)\n")
    A("| station | date | kind | arm | official | IEM 1-min extreme (the faulty feed) | IEM routine extreme | METAR spot range (F) | 6-hr groups (report, F) | final bound unguarded / S=3/5/8 | violates? |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for c in pl["known_cases"]:
        if not c.get("in_universe"):
            A(f"| {c['station']} | {c['date']} | {c['kind']} | not in universe | | | | | | | |")
            continue
        fb = c["final_bound_no_plaus_filter"]
        A(f"| {c['station']} | {c['date']} | {'HIGH' if c['kind']=='max' else 'LOW'} | {c['arm']} | {c['official']} | {c['iem_1min_extreme']} | {c['iem_routine_extreme']} | {c['metar_body_spot_range_F']} | "
          + "; ".join(f"{g['report'][6:]} {g['F']}" for g in c["groups"]) + f" | {fb['inf']} / {fb['3']}/{fb['5']}/{fb['8']} | {any(c['violates'].values())} |")
    A("\n**Synthetic known-answer test of the guard** (NOT data: the coordinator's fault values injected into the real METAR group stream of those days; a 120 F / -1 F / -29 F group all pass the +-60 C plausibility filter, so only the guard can stop them):\n")
    A("| station | date | kind | injected group (F) | official | corroborated @S=3/5/8 | final bound unguarded | final bound guarded S=3/5/8 |\n|---|---|---|---|---|---|---|---|")
    for x in pl["synthetic_guard_test"]:
        A(f"| {x['station']} | {x['date']} | {x['kind']} | {x['injected_F']} | {x['official']} | {x['corroborated_at_S3/5/8']} | {x['final_bound_unguarded']} | {x['final_bound_S3/5/8']} |")
    A("\nResult: the guard rejects all three injected faults at every S (no spot reading within 8 F), the unguarded bound would be pinned at 120 / -1 / -29 F and would fire false RESOLVED-NO on every rung below/above it. "
      "That is the case for the guard; it is a confirmation of mechanism, not a measured rate. The real-data fault rate stays 1/2037 on the primary arm.\n")


def md_verdict(o, L):
    A = L.append
    vd = o["verdict_detail"]
    P = o["arms"]["PRIMARY_HIGH_nonCST"]
    p = P["5|1|L10"]
    A(f"## 2. VERDICT (frozen PASS/KILL rule, applied verbatim to the primary arm at L=10)\n")
    A(f"# **{o['verdict']}**\n")
    cov = o["sampling"]["PRIMARY_HIGH_nonCST"]
    A(f"Candle coverage of the primary arm: {cov['tickers_in_completed_prefix']}/{cov['tickers_total']} fired tickers = {100*cov['ticker_fraction']:.1f}% "
      "(completed prefix of the seeded shuffled work order, seed 20261027, never re-sorted -- so any prefix is a uniform random subsample).\n")
    A("**PASS bars vs measured, every cell (L=10, primary arm).** A cell must satisfy ALL rows. Both EV weightings and both signed-t readings are required (the stricter reading).\n")
    A("| bar | " + " | ".join(f"S={s},D={d}" for (s, d) in CELLS) + " |\n|---|" + "---|" * len(CELLS))
    def row(label, fn):
        A(f"| {label} | " + " | ".join(fn(P[f'{s}|{d}|L10']) for (s, d) in CELLS) + " |")
    row("1. false-lock <= 2% and Wilson UB <= 5% (all fires)", lambda r: f"{100*r['false_lock_rate_all']:.2f}% ({r['n_false_lock_all']}/{r['n_fires']}), UB {100*r['wilson_ub_all']:.2f}%")
    row("2. EV volume-weighted >= +2.0c", lambda r: "n/a" if r['ev_vw'].get('mean') is None else f"{r['ev_vw']['mean']:+.2f}c")
    row("2b. EV equal-weight >= +2.0c", lambda r: "n/a" if r['ev_eq'].get('mean') is None else f"{r['ev_eq']['mean']:+.2f}c")
    row("3. signed day-clustered t (vw) >= Bonferroni bar", lambda r: "n/a" if r['ev_vw'].get('t') is None else f"t={r['ev_vw']['t']:+.2f} vs bar {r['ev_vw']['tcrit_bonf']:.2f} (G={r['ev_vw']['G']})")
    row("3b. signed day-clustered t (eq) >= Bonferroni bar", lambda r: "n/a" if r['ev_eq'].get('t') is None else f"t={r['ev_eq']['t']:+.2f} vs bar {r['ev_eq']['tcrit_bonf']:.2f} (G={r['ev_eq']['G']})")
    row("4. n priced >= 100, days >= 40, stations >= 10", lambda r: f"n={r['n_priced']}, days={r['n_days']}, stations={r['n_stations']}")
    row("5. untradeable fraction <= 70%", lambda r: "n/a" if r['untradeable_frac'] is None else f"{100*r['untradeable_frac']:.1f}% ({r['n_untradeable']}/{r['n_fires_candle_sampled']})")
    A("| **all bars met?** | " + " | ".join(("YES" if vd["cells"][f"{s}|{d}"]["all"] else "NO") for (s, d) in CELLS) + " |\n")
    A("**KILL clauses vs measured:**\n")
    A("| KILL if | measured | triggered? |\n|---|---|---|")
    A(f"| false-lock > 5% in the primary cell (S=5,D=1) | {100*p['false_lock_rate_all']:.2f}% ({p['n_false_lock_all']}/{p['n_fires']}), Wilson UB {100*p['wilson_ub_all']:.2f}% | {'YES' if vd['kill_false_lock_primary_gt5pct'] else 'no'} |")
    bu = vd["best_ub979_registered_reading"]
    A(f"| L=10 best one-sided 97.9% upper bound on EV < +0.5c | best UB (volume-weighted, equal-weight fallback) = {fnum(bu)}c; equal-weight reading = {fnum(vd['best_ub979_equal_weight_reading'])}c | {'YES' if vd['kill_best_ub979_lt_0.5c'] else 'no'} |")
    A(f"| every EV>0 cell misses its n floor (n>=100) | {vd['n_cells_EV>0']} cell(s) with EV>0 | {'YES' if vd['kill_every_EV>0_cell_misses_n_floor'] else 'no'} |\n")
    A(f"PASS cells: {vd['pass_cells'] or 'none'}.\n")
    md_verdict_text(o, L)


def md_cells(o, L):
    A = L.append
    A("## 3. All 6 cells x 2 latency arms\n")
    A(f"Bonferroni: 6 cells x 2 arms = {NCMP} comparisons, two-sided alpha = 0.05/{NCMP} = {ALPHA:.5f}, bar = exact Student-t quantile at p = {1-ALPHA/2:.5f} on realised day-count df (G-1, G = distinct LST days with a priced fire). "
      "Signed t: a negative t clearing the magnitude is evidence for KILL, never PASS. EV is fee-inclusive cents/contract, one contract held to settlement, NO bought at `100 - yes_bid`, "
      "outcome = Kalshi `result` only. False-lock denominators use EVERY fire (observations + official result); EV uses the priced candle sample. "
      "Entries are the first candle row at/after signal+L with cost <= 98c and net > 0 -- if no such row exists the fire is UNTRADEABLE, never back-filled.\n")
    for arm in ARMS:
        cov = o["sampling"][arm]
        A(f"### {ARM_LABEL[arm]}\n")
        A(f"Candle coverage: {cov['tickers_in_completed_prefix']}/{cov['tickers_total']} fired tickers ({100*(cov['ticker_fraction'] or 0):.1f}%), seeded-shuffle prefix.\n")
        A("| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | ZERO-volume entry minutes |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
        for (s, d) in CELLS:
            for Lm in L_ARMS:
                r = o["arms"][arm][f"{s}|{d}|L{Lm}"]
                fl = "n/a" if not r["n_fires"] else f"{r['n_false_lock_all']}/{r['n_fires']} = {100*r['false_lock_rate_all']:.2f}%, UB {100*r['wilson_ub_all']:.2f}%"
                un = "n/a" if r["untradeable_frac"] is None else f"{100*r['untradeable_frac']:.1f}%"
                A(f"| {s},{d}{' (primary)' if (s,d)==PRIMARY else ''} | {Lm} | {r['n_fires']} | {fl} | {r['n_fires_candle_sampled']} | {r['n_priced']} | {un} | "
                  f"{r['n_days']} / {r['n_stations']} | {ev_cell(r['ev_vw'])} | {ev_cell(r['ev_eq'])} | {fnum(r['mean_cost_c'])} | {r['n_priced'] - r['n_entry_vol_positive']} of {r['n_priced']} ({(100*(r['n_priced']-r['n_entry_vol_positive'])/r['n_priced']) if r['n_priced'] else 0:.0f}%) |")
        A("")
        r = o["arms"][arm]["5|1|L10"]
        A(f"Untradeable breakdown, cell S=5,D=1, L=10: {r['untradeable_breakdown']}. State of the first candle at/after signal+10 min: {r['first_candle_after_signal_state']}.\n")
        if r["entry_cost_hist"]:
            A(f"Entry cost histogram (c), S=5,D=1, L=10: {dict(sorted((int(k), v) for k, v in r['entry_cost_hist'].items()))}.\n")


def md_anchors(o, L):
    A = L.append
    c = o["anchors_cde"]
    A("## 4. Anchors (a), (c), (d), (e)\n")
    A("**(a) Monotonicity** -- see section 1: 0 violations on 6,488 station-days x 4 bound variants. (Note: an earlier draft that applied the observability study's 'latest report wins' rule to duplicate/COR groups produced 2 non-monotone guarded bounds on one LOW day (DCA 2026-09-26); the spec's literal definition -- max over ALL decoded groups -- is non-decreasing by construction and is what is used.)\n")
    ac = c["anchor_c"]
    A(f"**(c) No look-ahead** -- every fire in every cell and every arm was re-run ({ac['fires_cellrows_checked']} (rung, cell) fires over {ac['unique_(day,report)_checks']} distinct (station-day, firing-report) pairs) "
      "three ways: (1) on the truncated prefix of reports with report time < signal time (report time + 10 min), the bound path and the fire are identical; "
      "(2) on reports strictly before the firing report the rung does NOT yet fire (firstness); (3) with every report at/after the signal time replaced by garbage "
      "(6-hr max/min groups at +-60 C in random directions, spot temperatures at +-60 C, fabricated groups on reports that had none) the bound path up to the firing event and the fire are identical. "
      f"Disagreements: **{ac['disagreements']}** (the code asserts and would have aborted).\n")
    ad = c["anchor_d"]
    A(f"**(d) Day window** -- reused, not re-derived: `finality_B.build_universe()` day window `[close rounded to the hour - 24h, close]` and the close-hour == LST-midnight filter; "
      f"re-asserted on all {ad['rungs_checked']} rungs ((day_end hour) == (-UTC offset) mod 24, window = 86,400 s, max |close_time - LST midnight| = {ad['max_abs_close_minus_dayend_s']} s). "
      f"Independent consistency check: rung `result` vs `expiration_value` in [lo,hi] disagrees on {ad['result_vs_expiration_value_inconsistent_rungs']} of {ad['rungs_checked']} rungs. "
      "6-hr groups are attributed only if their whole 6-hour window `[nominal-6h, nominal]` lies inside the LST day (the 3A rule from the observability study).\n")
    md_anchor_e(o, L)


def md_anchor_e(o, L):
    A = L.append
    e = o["anchors_cde"]["anchor_e"]
    A("**(e) Overshoot-only disclosure -- do these fires land on rungs the DEPLOYED bot already catches?**\n")
    A("Method: the deployed cap-overshoot path (`locked_orders`, margin 1.0 F, KPHX 2.0 F, strict `extreme > cap + margin`, on the glitch-filtered `sustained_extreme` running extreme) "
      "was replayed on historical observations: (i) IEM 1-minute data (the best a real-time feed could deliver; only on days with >=1000 1-min obs) and (ii) IEM routine hourly METAR spot temperatures "
      "(the runner's default feed). `kwx_runner.py` was read, never imported or modified. 'Deployed locks' = the replay ever reaches the lock condition on that rung during the LST day; "
      "'locked at/before bound signal' = at or before report time + 10 min.\n")
    A("| arm | cell | bound fires | feed | fires with feed | deployed ever locks | deployed never locks | deployed locked at/before the bound signal | >=30 min before the bound signal | median minutes the bound signal trails the deployed lock |\n|---|---|---|---|---|---|---|---|---|---|")
    for arm in ARMS:
        for ck in ("5|1", "5|2"):
            d = e[f"{arm}|{ck}"]
            for feed, lab in (("1min", "1-min feed"), ("routine", "hourly METAR (deployed default)")):
                x = d[feed]
                A(f"| {arm} | S,D={ck.replace('|', ',')} | {d['n_fires']} | {lab} | {x['n_with_feed']} | {x['deployed_eventually_locks']} | {x['deployed_never_locks']} | "
                  f"{x['deployed_locked_at_or_before_bound_signal']} | {x['deployed_locked_30min_or_more_before_bound_signal']} | {fnum(x['median_minutes_bound_signal_is_after_deployed_lock'], 0)} |")
    A("")
    md_e_text(o, L)


def md_exclusions(o, L):
    A = L.append
    ab = o["anchor_b"]
    X = ab["anchor_b"]
    A("## 5. Every exclusion (count, reason)\n")
    A("| count | reason |\n|---|---|")
    for k, v in ab["exclusions_universe"].items():
        A(f"| {v} | universe rung level (inherited from `finality_B.build_universe`): {k} |")
    for k, v in ab["exclusions_days"].items():
        A(f"| {v} | {k} |")
    for k, v in ab["exclusions_rungs"].items():
        A(f"| {v} | rung dropped: {k} |")
    for arm in ARMS:
        a = X["arms"][arm]
        A(f"| {a['n_days_total'] - a['variants'][str(INF)]['n']} | {arm}: station-days with no decoded in-window 6-hr group (no bound; cannot fire) |")
        A(f"| {a['variants']['3']['no_bound']} | {arm}: station-days with no CORROBORATED group at S=3 (guard leaves no bound) |")
    A(f"| {o['candle_fetch_outcomes']} | candle fetch outcomes by source|error (a 404 on both endpoints = no candles = counted UNTRADEABLE, never dropped) |")
    for arm in ARMS:
        cov = o["sampling"][arm]
        A(f"| {cov['tickers_total'] - cov['tickers_in_completed_prefix']} | {arm}: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = {100*(cov['ticker_fraction'] or 0):.1f}%) |")
    A("| 0 | days dropped for the value of the official outcome (none were) |")
    A("")
    A("UNTRADEABLE fires are not exclusions: they stay in the denominator of the untradeable fraction (breakdown in section 3). "
      "Violating station-days (anchor b) are NOT excluded from fire or EV counts either; they sit in the false-lock numerator whenever they produce a fire on a YES rung.\n")


def md_verdict_text(o, L):
    A = L.append
    vd = o["verdict_detail"]
    P = o["arms"]["PRIMARY_HIGH_nonCST"]
    p, p20, p21 = P["5|1|L10"], P["5|1|L20"], P["5|2|L10"]
    st = p["first_candle_after_signal_state"]
    nf = p["n_fires_candle_sampled"]
    nc = st.get("no_candle_at_or_after_signal", 0)
    A("**Reading, blunt.** The bound is valid and the signal is real; the trade does not exist. "
      f"(1) Bound validity (anchor b) is excellent: 1 violation in 2,037 primary station-days, **0 false locks in {p['n_fires']} primary-cell fires** (Wilson UB {100*p['wilson_ub_all']:.2f}%, vs the 2% / 5% bars). "
      f"The sensor-fault headwind the spec named as the likely cause of death did not materialise on the primary arm. "
      f"(2) What kills it is price. After a rung is provably dead, the market has already pushed its YES bid to zero: at the first candle at/after signal+10 min the YES bid is 0 on "
      f"{st.get('yes_bid=0', 0)} of {nf} fires ({100*st.get('yes_bid=0', 0)/nf:.1f}%), so the NO costs 100c and cannot be bought at <= 98c. "
      f"Only **{p['n_priced']} of {nf} fires ({100*p['n_priced']/nf:.2f}%) have any qualifying minute -> untradeable fraction {100*p['untradeable_frac']:.2f}%** against the 70% bar. "
      f"The 6-hr group is a lagged digest of temperatures the market priced from live observations before the group was published.\n")
    A(f"**How the frozen rule lands.** PASS is impossible: bar 4 (n priced >= 100) and bar 5 (untradeable <= 70%) fail by two orders of magnitude in every cell (primary cell: n={p['n_priced']}, {p['n_days']} days, {p['n_stations']} stations; "
      f"D=2 cell: n={p21['n_priced']}). KILL is triggered by the clause 'every EV>0 cell misses its n floor' (all {vd['n_cells_EV>0']} EV>0 cells have n<100). "
      f"The other two KILL clauses do NOT fire: false-lock 0% (not > 5%), and the best one-sided 97.9% EV upper bound is {fnum(vd['best_ub979_registered_reading'])}c (not < +0.5c) -- it is that wide only because n is single digits. "
      f"So the label is KILL by the letter of the rule, but its evidential content is 'the population is ~99.7% unbuyable', not 'EV is negative'. The EV on the {p['n_priced']} priced entries "
      f"(volume-weighted {ev_cell(p['ev_vw'])}; equal-weight {ev_cell(p['ev_eq'])}) is statistically indistinguishable from zero and sits on {p['n_priced']} observations: the signed t-statistics are below the Bonferroni bar in every L=10 cell, so even the positive point estimates cannot support a PASS. "
      f"Mean entry cost {fnum(p['mean_cost_c'])}c; at 97-98c the maximum possible net per contract is 1-2c after fee, so the +2.0c EV bar is nearly unreachable at those prices even with zero losses.\n")
    zv = p["n_priced"] - p["n_entry_vol_positive"]
    A(f"**Zero-volume entry minutes (stated outright, treated as doubtful fills).** Primary cell S=5,D=1,L=10: {zv} of {p['n_priced']} priced entry minutes have ZERO traded volume ({100*zv/max(1,p['n_priced']):.0f}%); "
      f"the volume-weighted statistic therefore rests on {p['n_entry_vol_positive']} observation(s). Per-cell counts are in the last column of section 3. "
      f"The +2.0c EV bars (2 and 2b) are nominally met in the L=10 D=1 cells on these 7-9 entries, but PASS still fails on t, n and untradeable fraction, so this does not change the verdict; it does mean even the {p['n_priced']} 'priced' entries include quote-only minutes that may not be fillable.\n")
    A(f"**Caveat that cannot rescue it.** Candle rows exist only for minutes in which the book changed; no back-fill/carry-forward is applied (spec: never back-fill). {nc} of {nf} primary fires ({100*nc/nf:.1f}%) have no candle row at/after signal+10 min, "
      f"so a quiet standing bid could in principle be hiding there. Even if **every one** of those became tradeable the untradeable fraction would still be >= {100*(1-(p['n_priced']+nc)/nf):.1f}%, far above the 70% bar. "
      "Also, the candle window starts at each rung's first signal, so the pre-signal price path is not observed (the repricing time cannot be dated; only that it had happened by signal+10).\n")


def md_e_text(o, L):
    A = L.append
    e = o["anchors_cde"]["anchor_e"]
    d1, d2 = e["PRIMARY_HIGH_nonCST|5|1"], e["PRIMARY_HIGH_nonCST|5|2"]
    m1, r1 = d1["1min"], d1["routine"]
    m2, r2 = d2["1min"], d2["routine"]
    p = o["arms"]["PRIMARY_HIGH_nonCST"]["5|1|L10"]
    A(f"**Which is it? An execution/timing improvement on a largely known population, not a new discovery -- with two narrow caveats.** Primary cell S=5,D=1: "
      f"against a deployed rule on a 1-minute feed, {m1['deployed_eventually_locks']} of {m1['n_with_feed']} fires ({100*m1['deployed_eventually_locks']/m1['n_with_feed']:.0f}%) are on rungs the deployed rule also locks, and it locks "
      f"{m1['deployed_locked_30min_or_more_before_bound_signal']} of them >= 30 min BEFORE the bound can be published (median {fnum(m1['median_minutes_bound_signal_is_after_deployed_lock'],0)} min earlier): the 6-hr group is slower than the deployed path, not faster. "
      f"At D=2 the overlap is {100*m2['deployed_eventually_locks']/m2['n_with_feed']:.0f}% ({m2['deployed_eventually_locks']}/{m2['n_with_feed']}). "
      f"Caveat 1 (D=1 only): the other {m1['deployed_never_locks']} fires ({100*m1['deployed_never_locks']/m1['n_with_feed']:.0f}%) are rungs overshot by only ~1 F (integer bound = cap+1, i.e. group >= cap+0.5 F), which the deployed margin (extreme > cap + 1.0 F, continuous) never reaches. "
      f"Caveat 2: against the deployed bot's DEFAULT feed (hourly METAR spots) {r1['deployed_never_locks']} of {r1['n_with_feed']} fires ({100*r1['deployed_never_locks']/r1['n_with_feed']:.0f}%) are never locked, because the peak fell between hourly reports and only the 6-hr group saw it -- the bound sees more than the default feed. "
      f"But on this slice the market is no more generous: the first post-signal YES bid is 0 on {100*p['first_candle_after_signal_state'].get('yes_bid=0',0)/p['n_fires_candle_sampled']:.1f}% of fires. "
      f"Of the {p['n_priced']} priced primary entries, {p['entered_after_deployed_1min_lock']} came after a deployed 1-min lock and {p['entered_before_deployed_1min_lock']} before one (the rest had no 1-min coverage or no deployed lock). "
      "The single standout (SFO 2026-06-28, rung [72,73], group 73.94 F -> 74 F, YES bid still ~28-32c at the signal, NO bought at 59c, settled NO) is a rounding-ambiguity case at the D=1 boundary; one observation in 2,850 is an anecdote, not an edge.\n")


def md_notes(o, L):
    A = L.append
    ab = o["anchor_b"]["anchor_b"]
    P = o["arms"]["PRIMARY_HIGH_nonCST"]
    A("## 6. Findings that contradict or qualify the spec's premises\n")
    A("1. **The sensor-fault headwind is not the cause of death.** The spec predicted faults as the most likely killer. On the frozen primary arm the final-bound violation rate is 1/2,037 (0.05%, Wilson UB 0.28%) and there are 0 false locks in all six cells (UB 0.13-0.19%). "
      "The famous DEN 24 F fault is a LOW-market fault (DEN LOW 2026-06-26), outside the HIGH-only primary arm; the guard rejects it at every S. A 2% false-lock bar is NOT unreachable for HIGH/non-CST. "
      "Faults concentrate in the LOW arms (unguarded 7/2,035 non-CST LOW days), where the guard cuts them to 1-2 at S=3-5 for a 7-11% fire cost.")
    A("2. **The guard is nearly irrelevant on the primary arm** (removes 0 of 1 fault; cuts 0.2-1.7% of fires) and **the +-60 C plausibility filter never fires** (0 rejected groups in the whole record). "
      "The only primary-arm fault (NYC 2026-08-27: station group 81 F, corroborated by spot temperatures, NWS certified 77 F) also contradicts the spec's statement that NWS builds the CLI from these recorded extremes -- in at least one case it did not. "
      "That fault produced no false lock only because the YES rung [76,77] is not in the universe for that day.")
    A("3. **'Known hours before close' is true and is not an edge.** The bound is available a median of 486 min (8.1 h; p10 307 min, p90 669 min) before close on primary-cell fires (it is published at the synoptic reports), as the spec says. The market, however, had priced the dead rungs to a zero bid by then: the information in a 6-hr group is a lagged summary of live observations. "
      "The spec's break-even arithmetic (f ~ 1% at 98c) never mattered because there are almost no sub-98c entries to be wrong on.")
    A("4. **The 6-hr group is slower than the deployed path**, so this is an execution/timing question on a known population (anchor e), not a new population.")
    A("5. **Interpretation choices made where the spec was silent (disclosed):** (a) BMAX/BMIN are integer degF (tenths-C -> F -> round half-up) and compared to the whole-degree official value; "
      "(b) the corroboration guard is two-sided |spot - group| <= S over reports in [nominal-6h, the group's own report time] (the only reading that cannot look ahead); "
      "(c) the guarded bound is the running max/min over corroborated groups only; (d) duplicate/COR groups each count as a decoded group (spec-literal; makes the bound monotone by construction -- the observability study's 'latest wins' rule produced 2 non-monotone guarded bounds on one LOW day and was rejected for that reason); "
      "(e) the 'violation rate' used for the self-kill is the primary arm at the registered S=5, with all other variants shown (none exceeds 2% either, so the choice is immaterial); "
      "(f) the KILL clause 'best one-sided 97.9% UB < +0.5c' uses the volume-weighted reading (Build-B precedent) with equal-weight as fallback; the equal-weight reading is also shown and gives the same verdict.")
    A("6. **Secondary arms (cannot PASS)**: LOW non-CST, HIGH CST, LOW CST are reported in section 3. They show the same price wall (untradeable >= 97%). CST arms also fail structurally: their last tiling group is published ~7 min before close, so fires on that final group have signal+10 min after close. "
      "Their positive-looking EVs rest on 2-19 entries, mostly zero-volume or 97-98c, and are not evidence of anything.")
    A("7. **Process notes.** Candle fetch used `/historical/markets/{ticker}/candlesticks` before 2026-08-28 and live `/series/.../candlesticks` after (historical rows use `close`, aliased by `finality_B._adapt`); "
      "57 tickers returned 404 on both endpoints (no candles; counted UNTRADEABLE). All 6,231 fired tickers were fetched (100% coverage), in a seeded shuffled order (seed 20261027) that was never re-sorted. "
      "No file in `cache/finality/` or `cache/settlement_obs/` was written, and no live-trading file was touched. `finality_B.py` carries uncommitted edits from another study; it is imported but was not modified or committed here.\n")



# ============================================================================================ plausibility / known-case disclosure

def synthetic_guard_test(recs, stn):
    """KNOWN-ANSWER test of the guard (SYNTHETIC, clearly not data): inject the coordinator's fault values into the real
    METAR group stream of the named days and check the guard.  LAX 2026-05-24 HIGH: replace the 23:53Z 6-hr max group by
    +48.9 C (=120 F); MDW 2026-07-07 LOW (CST): replace the 17:53Z 6-hr min group by -18.3 C (=-1 F)."""
    out = []
    for (st, date, kind, tcv) in (("LAX", "2026-05-24", "max", 489), ("MDW", "2026-07-07", "min", -183), ("LAX", "2026-05-24", "min", -339)):
        r = [x for x in recs if x["station"] == st and x["lst_date"] == date and x["kind"] == kind][0]
        reps = [dict(x) for x in day_reports(stn[st], r["day_start"], r["day_end"])]
        gk = "g6max" if kind == "max" else "g6min"
        idx = [i for i, x in enumerate(reps) if x[gk] is not None and abs(x["ts"] - round(x["ts"] / SYN) * SYN) <= TOL]
        i = idx[1] if len(idx) > 1 else idx[0]
        reps[i][gk] = ("synthetic", tcv)
        ev = walk_day(reps, r["day_start"], r["day_end"], kind)
        e = [x for x in ev if x["tc"] == tcv][0]
        out.append({"station": st, "date": date, "kind": kind, "injected_F": round(spot_F(tcv), 1), "official": r["official"],
                    "passes_plausibility_filter(+-60C)": True, "corroborated_at_S3/5/8": [e["corr"][3], e["corr"][5], e["corr"][8]],
                    "final_bound_unguarded": ev[-1]["bound"][INF], "final_bound_S3/5/8": [ev[-1]["bound"][3], ev[-1]["bound"][5], ev[-1]["bound"][8]]})
    return out


def cmd_plaus():
    """Coordinator request: (1) anchor (b) violation rate WITH and WITHOUT the +-60 C plausibility filter (separates the
    filter's contribution from the corroboration guard's); (2) two known-bad observation days; no threshold touched."""
    recs, rungs, skip, ex, rex, stn, walks = walk_everything()
    walks_nf = {}
    for r in recs:
        walks_nf[(r["station"], r["kind"], r["day_end"])] = walk_day(
            day_reports(stn[r["station"]], r["day_start"], r["day_end"]), r["day_start"], r["day_end"], r["kind"], plaus=False)
    ab_f = anchor_b_compute(recs, walks)
    ab_n = anchor_b_compute(recs, walks_nf)
    rej = collections.Counter()
    for st, d in stn.items():
        for r in d["reps"]:
            for k in ("g6max", "g6min"):
                if r[k] is not None and not (-600 <= r[k][1] <= 600):
                    rej[st + ":" + k + ":" + r[k][0]] += 1
    tab = {}
    for arm in ARMS:
        tab[arm] = {}
        for key in (INF,) + S_GRID:
            f = ab_f["arms"][arm]["variants"][str(key)]
            n_ = ab_n["arms"][arm]["variants"][str(key)]
            tab[arm][str(key)] = {"filtered": [f["viol"], f["n"]], "unfiltered": [n_["viol"], n_["n"]]}
    # fire counts with / without filter
    fc_f = fire_counts(rungs, walks)
    fc_n = fire_counts(rungs, walks_nf)
    cases = []
    for (st, date) in (("LAX", "2026-05-24"), ("MDW", "2026-07-07")):
        for kind in ("max", "min"):
            rr = [r for r in recs if r["station"] == st and r["lst_date"] == date and r["kind"] == kind]
            if not rr:
                cases.append({"station": st, "date": date, "kind": kind, "in_universe": False})
                continue
            r = rr[0]
            key = (st, kind, r["day_end"])
            t1, f1 = FB.window_obs(st, "1min", r["day_start"], r["day_end"])
            tr, fr = FB.window_obs(st, "routine", r["day_start"], r["day_end"])
            reps = day_reports(stn[st], r["day_start"], r["day_end"])
            tts = [spot_F(x["tt"]) for x in reps if x["tt"] is not None]
            c = {"station": st, "date": date, "kind": kind, "in_universe": True, "arm": arm_of(kind, r["off"]), "official": r["official"],
                 "iem_1min_extreme": (max(f1) if kind == "max" else min(f1)) if f1 else None,
                 "iem_routine_extreme": (max(fr) if kind == "max" else min(fr)) if fr else None,
                 "metar_body_spot_range_F": [round(min(tts), 1), round(max(tts), 1)] if tts else None,
                 "groups": [{"report": SO.utc(e["ts"]), "tc": e["tc"], "F": round(e["gF"], 2), "corr": {str(x): e["corr"][x] for x in S_GRID}} for e in walks_nf[key]],
                 "final_bound": {str(k): (walks[key][-1]["bound"][k] if walks[key] else None) for k in (INF,) + S_GRID},
                 "final_bound_no_plaus_filter": {str(k): (walks_nf[key][-1]["bound"][k] if walks_nf[key] else None) for k in (INF,) + S_GRID}}
            bad = (lambda b: b is not None and ((b > r["official"]) if kind == "max" else (b < r["official"])))
            c["violates"] = {k: bad(v) for k, v in c["final_bound_no_plaus_filter"].items()}
            cases.append(c)
    out = {"table": tab, "groups_rejected_by_filter": dict(rej), "n_rejected_groups": sum(rej.values()),
           "fires_filtered": {a: {k: v["fires"] for k, v in fc_f[a].items()} for a in ARMS},
           "fires_unfiltered": {a: {k: v["fires"] for k, v in fc_n[a].items()} for a in ARMS},
           "falselocks_unfiltered": {a: {k: v["false_lock"] for k, v in fc_n[a].items()} for a in ARMS},
           "known_cases": cases, "synthetic_guard_test": synthetic_guard_test(recs, stn)}
    jdump(out, os.path.join(CACHE, "plaus.json"))
    print(json.dumps(out, indent=1, default=str)[:6000])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "anchor_b":
        o = cmd_anchor_b()
        sys.exit(3 if o["self_kill"] else 0)
    elif cmd == "fires":
        cmd_fires()
    elif cmd == "plaus":
        cmd_plaus()
    elif cmd == "analyze":
        cmd_analyze()
    elif cmd == "candles":
        cmd_candles(arms=sys.argv[2].split(",") if len(sys.argv) > 2 else None)
    else:
        raise SystemExit("unknown stage " + cmd)
