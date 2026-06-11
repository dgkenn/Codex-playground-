"""box_policy_ab.py -- PROSPECTIVE A/B of the pairing policy on FORWARD collector data.

The 20k-fill historical tape gave an ambiguous read on whether SELECTIVE HOLDING of a favorable
unpaired leg beats ALWAYS-PAIRING (two backtests disagreed; P2 looked good on Calmar but was a
2-sigma, 50%-win-rate directional bet). So we do not decide on the in-sample tape. Instead we let
the live SHADOW COLLECTOR accumulate brand-new windows and score the two policies on data collected
AFTER the policy was specified (the pre-registration date in P2_PROSPECTIVE.md). Once the
pre-registered significance bar is cleared, we decide. This script is that scorer.

Policies (applied to the SAME reconstructed maker fills per window; held to settlement; cap |net|<=1):
  P0 ALWAYS-PAIR   : the live default. Accept a fill iff it keeps |net|<=1 (so an unpaired leg is
                     completed by the opposite side as soon as it fills -> locks the box).
  P2 SIGNAL-HOLD   : like P0, but when a leg is unpaired and a PAIRING fill arrives, HOLD (skip the
                     pair, let the leg ride to settlement) iff that leg's decision-time spot signal
                     was favorable (sig_adv <= 0); otherwise pair. The candidate "tie-breaker".

Fills are reconstructed from the collector's own forward streams with the EXACT logic of
kalshi_sizing.collect_fills (queue q0=0 = front-of-queue, honest stale spot signal), so this is the
same measurement, just on prospective data.

    python box_policy_ab.py [--asset btc] [--dir overnight_data gha_data ...] [--report]

Appends one paired record per NEW window to box_policy_ledger_<asset>.jsonl (dedup by ws), then
prints the running paired t-test and the pre-registered verdict.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os

import numpy as np

# Pre-registered decision rule (frozen in P2_PROSPECTIVE.md; do not tune to the data):
MIN_WINDOWS = 300       # need at least this many forward windows before a DEPLOY decision
T_BAR = 3.0             # DEPLOY bar: paired diff (trial-P0) t-stat must exceed this (positive)
DD_MULT = 1.25          # AND trial max-drawdown <= DD_MULT * P0 max-drawdown (risk-of-ruin guard)
# ALERT tier (the "two-sigma rule" -- be made aware so we can take action; NOT auto-deploy):
ALERT_T = 2.0           # |paired t| past 2-sigma raises an alert (either direction)
ALERT_N = 100           # ...once at least this many forward windows are scored (avoid tiny-n noise)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def iter_gz(fp):
    """Yield JSON records from a gzip JSONL file, tolerating a TRUNCATED tail (the live collector
    may be reaped mid-write, leaving an incomplete gzip stream / partial last line)."""
    try:
        with gzip.open(fp, "rt") as fh:
            for ln in fh:
                try:
                    yield json.loads(ln)
                except Exception:
                    continue
    except (EOFError, OSError, gzip.BadGzipFile):
        return   # keep whatever we read before the truncation point


def _rglob(d, pat):
    """Recursive glob -- the gha-data branch date-partitions files into gha_data/YYYY-MM-DD/."""
    return glob.glob(os.path.join(d, "**", pat), recursive=True) + glob.glob(os.path.join(d, pat))


def load_window_books(paths, asset):
    """ws -> list of (t, best_yes_bid, best_no_bid, spot) from the book stream (best = last level)."""
    books = {}
    res = {}
    for d in paths:
        for fp in set(_rglob(d, f"book_kalshi_{asset}15m_*.jsonl.gz")):
            for r in iter_gz(fp):
                if r.get("type") != "book":
                    continue
                yb = r.get("yes") or []; nb = r.get("no") or []
                if not yb or not nb:
                    continue
                books.setdefault(r["ws"], []).append(
                    (r["t"], float(yb[-1][0]), float(nb[-1][0]), _f(r.get("spot"))))
        # settlement from shadow_windows
        for fp in set(_rglob(d, f"shadow_windows_kalshi_{asset}15m_*.jsonl")):
            for ln in open(fp):
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                ru = r.get("resolved_up")
                if ru in (0, 1):
                    res[r["ws"]] = int(ru)
    return books, res


def load_trades(paths, asset):
    """ws -> sorted arrays (t, p_yes, sz, buy) from the taker tape."""
    tr = {}
    for d in paths:
        for fp in set(_rglob(d, f"trades_kalshi_{asset}15m_*.jsonl.gz")):
            for r in iter_gz(fp):
                if "p" not in r or "sz" not in r:
                    continue
                tr.setdefault(r["ws"], []).append(
                    (r.get("ts_exch") or r["t"], float(r["p"]), float(r["sz"]),
                     r.get("side") == "BUY"))
    out = {}
    for ws, rows in tr.items():
        rows.sort()
        out[ws] = (np.array([x[0] for x in rows], float), np.array([x[1] for x in rows], float),
                   np.array([x[2] for x in rows], float), np.array([x[3] for x in rows], bool))
    return out


def per_minute_touch(samples, ws):
    """Resample book samples to per-minute (k=0..14) last-before-boundary bid/ask/spot arrays."""
    bid = np.full(15, np.nan); ask = np.full(15, np.nan); spot = np.full(15, np.nan)
    samples = sorted(samples)
    for k in range(15):
        bound = ws + 60 * (k + 1)
        last = None
        for s in samples:
            if s[0] <= bound:
                last = s
            else:
                break
        if last is not None:
            ybb, nbb, sp = last[1], last[2], last[3]
            bid[k] = ybb; ask[k] = round(1.0 - nbb, 4)
            if sp is not None:
                spot[k] = sp
    return bid, ask, spot


def window_fills(ws, res, bid, ask, spot, tape, q0=0.0):
    """Reconstruct maker fills (kalshi_sizing.collect_fills logic). Returns list of
    (side 'bid'|'ask', settle, sig_adv) in time order."""
    spot_l = np.concatenate([[np.nan], spot[:-1]])
    t_arr, p_arr, sz_arr, buy_arr = tape
    recs = []
    for k in range(2, 13):
        b0, a0 = bid[k], ask[k]
        if np.isnan(b0) or np.isnan(a0) or not (0.03 <= (b0 + a0) / 2 <= 0.97):
            continue
        s_now, s_then = spot_l[k], spot_l[max(k - 3, 0)]
        mv = (s_now / s_then - 1) * 1e4 if (s_now and s_then and s_now > 0 and s_then > 0) else 0.0
        lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
        i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
        qb = qa = q0; done_b = done_a = False
        for i in range(i0, i1):
            if done_b and done_a:
                break
            p, sz, buy = p_arr[i], sz_arr[i], buy_arr[i]
            if not done_b and not buy and p <= b0 + 1e-9:
                if qb >= sz:
                    qb -= sz
                else:
                    recs.append(("bid", res - b0, mv)); done_b = True
            if not done_a and buy and p >= a0 - 1e-9:
                if qa >= sz:
                    qa -= sz
                else:
                    recs.append(("ask", a0 - res, -mv)); done_a = True
    return recs


def policy_pnl(fills, signal_hold):
    """Walk fills, cap |net|<=1, return summed settle. signal_hold=False -> P0; True -> P2."""
    net = 0; pnl = 0.0; held_sig = None
    for side, settle, sig in fills:
        step = 1 if side == "bid" else -1
        nn = net + step
        if abs(nn) > 1:
            continue
        accept = True
        if signal_hold and net != 0 and abs(nn) < abs(net):   # this fill would PAIR an unpaired leg
            if held_sig is not None and held_sig <= 0:         # leg's signal favorable -> HOLD it
                accept = False
        if accept:
            if net == 0 and nn != 0:
                held_sig = sig                                 # opened a leg; remember its signal
            net = nn; pnl += settle
    return pnl


# ------------------------------------------------------------------------------------------------
# TRIAL-STRATEGY REGISTRY. The live default is P0 (always-pair). Every entry here is a CANDIDATE
# scored vs P0 on FORWARD collector data and held to the two-sigma alert + pre-registered deploy bar.
# To prospectively test a new policy idea, add  name -> fn(fills)->pnl  here; it auto-inherits the
# accumulation, the 2-sigma alert, and the deploy gate. No live code changes until it clears the bar.
def pol_p0(fills):
    return policy_pnl(fills, signal_hold=False)


TRIALS = {
    "p2_signal_hold": lambda fills: policy_pnl(fills, signal_hold=True),
}


def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 8 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def maxdd(series):
    cum = np.cumsum(series)
    return float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--dir", nargs="+", default=["overnight_data", "gha_data"])
    ap.add_argument("--report", action="store_true", help="just report from the ledger(s), scan nothing")
    ap.add_argument("--ledger", default=None,
                    help="ledger to APPEND new windows to (default box_policy_ledger_<asset>.jsonl). "
                         "On GHA use a run-scoped path under gha_data/ so each run commits a fragment.")
    ap.add_argument("--alert", action="store_true",
                    help="on a 2-sigma crossing, emit a GitHub warning, append STRATEGY_ALERTS.txt, "
                         "and push a notify.alert (Telegram). Use in the periodic report job.")
    a = ap.parse_args()
    ledger = a.ledger or f"box_policy_ledger_{a.asset}.jsonl"

    # Aggregate ALL ledger fragments (cwd + each --dir) so run-scoped GHA fragments combine; dedup by ws.
    seen = {}
    frag_paths = [ledger] + [p for d in a.dir if os.path.isdir(d)   # recursive: gha-data dates the dirs
                             for p in glob.glob(os.path.join(d, "**", f"box_policy_ledger_{a.asset}*.jsonl"),
                                                recursive=True)]
    for fpath in dict.fromkeys(frag_paths):
        if os.path.exists(fpath):
            for ln in open(fpath):
                try:
                    r = json.loads(ln); seen[r["ws"]] = r
                except Exception:
                    pass

    added = 0
    if not a.report:
        books, res = load_window_books([d for d in a.dir if os.path.isdir(d)], a.asset)
        trades = load_trades([d for d in a.dir if os.path.isdir(d)], a.asset)
        with open(ledger, "a") as out:
            for ws in sorted(books):
                if ws in seen or ws not in res or ws not in trades:
                    continue
                bid, ask, spot = per_minute_touch(books[ws], ws)
                fills = window_fills(ws, res[ws], bid, ask, spot, trades[ws])
                if not fills:
                    continue
                rec = {"ws": ws, "res": res[ws], "n_fills": len(fills),
                       "p0": round(pol_p0(fills), 6),
                       "trials": {name: round(fn(fills), 6) for name, fn in TRIALS.items()}}
                out.write(json.dumps(rec) + "\n"); seen[ws] = rec; added += 1

    rows = sorted(seen.values(), key=lambda r: r["ws"])
    n = len(rows)
    print(f"TRIAL-STRATEGY PROSPECTIVE A/B ({a.asset}) -- {n} forward windows (+{added} new this run)")
    if n == 0:
        print("  no scored windows yet; let the collector accumulate."); return
    p0 = np.array([r["p0"] for r in rows]); dd0 = maxdd(p0)
    print(f"  P0 always-pair (LIVE baseline): net/win {p0.mean()*100:+.2f}c  maxDD {dd0*100:.0f}c  n={n}")

    # union of all trial names ever seen (old ledgers stored a flat 'p2' field -> migrate)
    names = set()
    for r in rows:
        names.update((r.get("trials") or {}).keys())
        if "p2" in r:
            names.add("p2_signal_hold")
    alerts = []
    for name in sorted(names):
        pt = np.array([(r.get("trials") or {}).get(name,
                        r.get("p2") if name == "p2_signal_hold" else np.nan) for r in rows], float)
        m = ~np.isnan(pt)
        if m.sum() < 8:
            continue
        diff = pt[m] - p0[m]
        t = tstat(diff); ddt = maxdd(pt[m]); nn = int(m.sum())
        print(f"  [{name}] net/win {pt[m].mean()*100:+.2f}c  maxDD {ddt*100:.0f}c | "
              f"diff {diff.mean()*100:+.3f}c/win  paired t={t:+.2f} (n={nn})")
        # two-sigma ALERT tier
        if nn >= ALERT_N and not np.isnan(t) and abs(t) > ALERT_T:
            alerts.append((name, t, nn))
        # pre-registered DEPLOY tier
        if nn >= MIN_WINDOWS and not np.isnan(t) and t > T_BAR and ddt <= DD_MULT * dd0 + 1e-9:
            print(f"      *** {name} CLEARS THE DEPLOY BAR (n>={MIN_WINDOWS}, t>{T_BAR}, DD ok) "
                  f"-> bring to operator ***")

    if alerts:
        lines = [f"{name}: paired t={t:+.2f} over n={nn} (2-sigma {'+' if t>0 else '-'})"
                 for name, t, nn in alerts]
        banner = (f"[STRATEGY ALERT] {a.asset}: trial strategy crossed the 2-sigma bar -- review "
                  f"for action.\n  " + "\n  ".join(lines))
        print("\n" + banner)
        if a.alert:
            for name, t, nn in alerts:               # GitHub Actions annotation (shows on the run)
                print(f"::warning title=Strategy crossed 2-sigma::{name} t={t:+.2f} n={nn} ({a.asset})")
            try:                                     # committed trail + phone push (Telegram via notify)
                with open("STRATEGY_ALERTS.txt", "a") as fh:
                    fh.write(f"{__import__('datetime').datetime.utcnow().isoformat()}Z  {banner}\n")
            except Exception:
                pass
            try:
                import notify
                notify.alert(banner)
            except Exception:
                pass
    else:
        print("\n  no trial strategy past the 2-sigma alert bar yet -- accumulating.")


if __name__ == "__main__":
    main()
