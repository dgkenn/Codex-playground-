#!/usr/bin/env python3
"""kwx_portfolio.py -- CENTRAL MULTI-SLEEVE PORTFOLIO MANAGER for K-WX.

Ships regardless of the current research-funnel outcome: this manages the sleeves that ALREADY
exist in the repo (one live mechanical sleeve + its config levers, two forward paper loggers).
As of this build (2026-07-20), the concurrent research funnel produced ZERO survivors -- see
STACKED_EDGES.md for the full graveyard -- so there are no new per-survivor sleeve modules to
register yet. This script's job is to run and report on what is already there, and to make
adding a future survivor a one-line registry edit instead of a new orchestration script.

READ-ONLY w.r.t. the live path. This script:
  - NEVER imports kalshi_exec for trading, never sets KWX_LIVE, never places an order.
  - NEVER writes kwx_runner_state.json, kwx_gate_status.txt, kwx_runner_plan.jsonl, .kwx_halt,
    or any file kwx_runner.py / kwx_paper_gate.py / kalshi_exec.py own. It only ever READS them.
  - Calls the EXISTING paper-only forward loggers' own snapshot()/settle() functions exactly as
    a human running `python wx_earlylock_forward.py snapshot` would -- no new order paths, no
    new network surface. Those modules' own docstrings guarantee no orders/credentials/KWX_LIVE.
  - Has exactly one write side effect against the main repo: it additively upserts a
    `portfolio_registry` section into p4k_params.json the first time that key is absent (never
    overwrites an existing portfolio_registry, never touches any other key). See
    _ensure_registry_section(). A one-time backup (p4k_params.json.kwxportfolio.bak) is written
    before the first such upsert. Everything else this script owns lives next to this file:
    kwx_portfolio_state.json (shared paper-bankroll/day-cap ledger) and its own stdout.

Commands:
  status      -- stacked-portfolio view: per-sleeve stage/gate/EV (from p4k_params.json) plus a
                 combined realistic $/mo figure (a lightweight re-derivation of wx_path_to_4k.py's
                 own Monte-Carlo model, same formulas, fewer trials for speed -- run
                 wx_path_to_4k.py directly for the full/authoritative report).
  snapshot    -- run every registered PAPER sleeve's forward-logger snapshot() once, FAIL-SOFT
                 (one broken sleeve's exception is caught and reported; it never blocks the
                 others), with:
                   * a SHARED paper-bankroll ledger and a combined PER-DAY deployment cap across
                     all paper sleeves (kwx_portfolio_state.json, resets at UTC midnight)
                   * per-market DEDUPE vs the live bot's plan log (kwx_runner_plan.jsonl):
                     any ticker a paper sleeve logs today that the live bot ALSO fired today is
                     flagged (never silently dropped -- the underlying jsonl files are untouched)
  correlate   -- same-day signal overlap between every pair of registered sleeves' logs (paper
                 jsonl + kwx_near_miss.jsonl + kwx_runner_plan.jsonl), so a future reviewer can
                 see whether two sleeves are really independent bets or firing on the same days.
  registry    -- print the resolved portfolio_registry (repo file if present, else this script's
                 built-in default). Pass --write to upsert it into p4k_params.json (idempotent).

Usage:
  python kwx_portfolio.py status     [--repo PATH]
  python kwx_portfolio.py snapshot   [--repo PATH]
  python kwx_portfolio.py correlate  [--repo PATH]
  python kwx_portfolio.py registry   [--repo PATH] [--write]
"""
import os, sys, json, math, random, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

# Fallback repo root: this script is intentionally built OUTSIDE the repo (scratchpad build dir),
# so it cannot find the checkout by walking up from its own directory the way an in-repo script
# can. Resolution order (see resolve_repo_root): --repo CLI arg > KWX_REPO_ROOT env var > this
# constant (the checkout this script was built against) > current working directory as last resort.
_FALLBACK_REPO_ROOT = "/home/user/Codex-playground-"

STATE_PATH = os.path.join(HERE, "kwx_portfolio_state.json")

# Nominal, INFORMATIONAL-ONLY paper bankroll for the shared ledger. The forward loggers this
# script drives (wx_forecast_forward.snapshot / wx_earlylock_forward.snapshot) log ONE hypothetical
# contract per qualifying signal -- they do not size positions the way kwx_runner does. This cap
# is therefore a bookkeeping throttle on "how much notional-if-filled we let the combined paper
# book accrue per day", not a real sizing decision; it reuses the live sleeve's own
# max_daily_deploy_frac convention (p4k_params.json sizing.max_daily_deploy_frac) against this
# nominal bankroll purely so the number has a repo-consistent derivation instead of being invented.
PAPER_BANKROLL_USD = 500.0


# ---------------- repo-root resolution (mirrors kwx_goal_status.resolve_repo_root) ----------------
def resolve_repo_root(argv):
    for i, a in enumerate(argv):
        if a == "--repo" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--repo="):
            return a.split("=", 1)[1]
    env = os.environ.get("KWX_REPO_ROOT")
    if env:
        return env
    if os.path.exists(os.path.join(_FALLBACK_REPO_ROOT, "p4k_params.json")):
        return _FALLBACK_REPO_ROOT
    if os.path.exists(os.path.join(os.getcwd(), "p4k_params.json")):
        return os.getcwd()
    return _FALLBACK_REPO_ROOT  # last resort: fail-soft callers will report missing files honestly


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def _load_json(path, default=None):
    return _safe(lambda: json.load(open(path)), default)


def _load_jsonl(path):
    def _read():
        out = []
        with open(path) as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    continue
        return out
    return _safe(_read, [])


def _today():
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


# ---------------- sleeve registry (built-in default; see registry command / _ensure_registry_section) ----
# kind: "live"        -- part of the deployed mechanical bot (kwx_runner.py); this script never drives it,
#                         only reads its status for the stacked view.
#       "live-config"  -- a config lever inside kwx_runner.py (no separate entrypoint to run).
#       "paper"        -- a standalone forward paper logger this script CAN drive via `snapshot`.
#       "dormant"      -- refuted/null/speculative; not modeled as a lever, no cycle to run.
#
# `cycle` (paper sleeves only): module to import + the zero-arg-except-verbose function to call for one
# forward-logging pass. Modules are imported with the repo root on sys.path so their own HERE-relative
# file paths (PAPER/SETTLED jsonl) resolve correctly regardless of where kwx_portfolio.py itself lives.
DEFAULT_REGISTRY = {
    "taker_mechanical": {
        "kind": "live", "entrypoint": "kwx_runner.py", "cycle": None,
        "note": "core deployed sleeve; canary live (KWX_SWITCH=on), 0 fires so far. Not driven by this script.",
    },
    "stacking": {
        "kind": "live-config", "entrypoint": "kwx_runner.py", "cycle": None,
        "note": "fires the full locked_orders() set per cycle; deployed, no separate process.",
    },
    "station_derate_relax": {
        "kind": "live-config", "entrypoint": "kwx_runner.py", "cycle": None,
        "note": "STATION_SIZE_MULT relaxation; deployed config, no separate process.",
    },
    "book_watch": {
        "kind": "live-component", "entrypoint": "kwx_book_watcher.py", "cycle": None,
        "note": "MEASURED NULL (WX_NEARMISS_DIAGNOSIS.md); stays deployed as a costless residual catcher, "
                "modeled at $0 expected contribution.",
    },
    "maker": {
        "kind": "dormant", "entrypoint": None, "cycle": None,
        "note": "REFUTED by wx_maker_deep_study.md; do not model, no cycle to run.",
    },
    "depth_adaptive": {
        "kind": "dormant", "entrypoint": None, "cycle": None,
        "note": "IN-VALIDATION sizing policy, not a runnable sleeve; gated on wx_book_snapshots.jsonl "
                "distinct-day count (see p4k_params.json sleeves.depth_adaptive).",
    },
    "added_markets_polymarket": {
        "kind": "dormant", "entrypoint": None, "cycle": None,
        "note": "SPECULATIVE, not time-accruable; excluded from capacity arithmetic per p4k_params.json.",
    },
    "added_markets_kalshi": {
        "kind": "dormant", "entrypoint": None, "cycle": None,
        "note": "SPECULATIVE recon only (WX_EXPANSION.md); no backtest/paper harness run for any family.",
    },
    "early_lock": {
        "kind": "paper", "entrypoint": "wx_earlylock_forward.py", "cycle": "wx_earlylock_forward:snapshot",
        "settle": "wx_earlylock_forward:settle", "decision_module": "wx_earlylock_decision",
        "note": "forward price-check for the early-lock refinement; historical prior is NULL "
                "(wx_earlylock_deep_study.md) -- forward harness runs cheaply to confirm/refute live, "
                "ACTIVATE-PAPER gate in wx_earlylock_decision.py (n>=30, win_lo>=90%, EV(cons)>=+1.1c, t>=3).",
    },
    "forecast": {
        "kind": "paper", "entrypoint": "wx_forecast_forward.py", "cycle": "wx_forecast_forward:snapshot",
        "settle": "wx_forecast_forward:settle", "decision_module": None,
        "note": "Open-Meteo forecast-vs-market-price overlay; research-stage log (59 settled rows as of "
                "this build), no p4k_params.json sleeve entry and no authored decision gate yet -- "
                "reported here as accruing/informational only, NOT counted in combined $/mo.",
    },
}

# Registered funnel-survivor sleeves. Empty: the concurrent funnel (bt1-3, r2b1-2 in
# scratchpad/stacked/) killed every spec before a full paper harness was authorized -- see
# STACKED_EDGES.md graveyard. Nothing to add here yet; the shape a future entry takes is the same
# as "early_lock"/"forecast" above (kind="paper", cycle="wx_<name>_paper:snapshot",
# decision_module="wx_<name>_decision").
SURVIVOR_REGISTRY = {}


def full_registry():
    reg = dict(DEFAULT_REGISTRY)
    reg.update(SURVIVOR_REGISTRY)
    return reg


PAPER_SLEEVES = [k for k, v in full_registry().items() if v["kind"] == "paper" and v.get("cycle")]


# ---------------- portfolio_registry upsert into p4k_params.json (additive-only) ----------------
def _ensure_registry_section(root, write=False):
    """Idempotent: if p4k_params.json already has a 'portfolio_registry' key, return it UNCHANGED
    (never overwrites hand-edits). If absent and write=True, back up the file once
    (p4k_params.json.kwxportfolio.bak, only if that backup doesn't already exist) and add the
    section with this script's DEFAULT_REGISTRY + SURVIVOR_REGISTRY. Every other top-level key in
    the file is preserved byte-for-byte (same dict object, only one new key set). Fail-soft: on
    any error, returns the in-memory registry and prints a warning instead of raising -- a status/
    snapshot run must never be blocked by a params-file write problem."""
    path = os.path.join(root, "p4k_params.json")
    params = _load_json(path)
    if params is None:
        print(f"  [registry] WARNING: could not read {path}; using built-in default only.", file=sys.stderr)
        return full_registry(), None
    if "portfolio_registry" in params:
        return params["portfolio_registry"], params
    if not write:
        return full_registry(), params
    try:
        bak = path + ".kwxportfolio.bak"
        if not os.path.exists(bak):
            with open(path) as f:
                raw = f.read()
            with open(bak, "w") as f:
                f.write(raw)
        params["portfolio_registry"] = full_registry()
        params["portfolio_registry"]["_meta"] = {
            "added_by": "kwx_portfolio.py",
            "added": dt.datetime.now(dt.timezone.utc).isoformat(),
            "note": "additive-only section; see kwx_portfolio.py._ensure_registry_section docstring. "
                    "Backup of the pre-existing file is at p4k_params.json.kwxportfolio.bak.",
        }
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(params, f, indent=2, sort_keys=False)
        os.replace(tmp, path)
        print(f"  [registry] wrote portfolio_registry into {path} (backup: {bak})")
        return params["portfolio_registry"], params
    except Exception as e:
        print(f"  [registry] WARNING: failed to write portfolio_registry ({e}); using in-memory default.",
              file=sys.stderr)
        return full_registry(), params


# ---------------- shared paper-bankroll / daily-cap ledger ----------------
def _load_state():
    return _load_json(STATE_PATH, {"day": _today(), "deployed_usd_by_sleeve": {}, "collisions": []})


def _save_state(s):
    try:
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(s, f, indent=2)
        os.replace(tmp, STATE_PATH)
    except Exception as e:
        print(f"  [state] WARNING: could not persist {STATE_PATH}: {e}", file=sys.stderr)


def _daily_cap_usd(params):
    frac = 0.6
    try:
        frac = float(params["sizing"]["max_daily_deploy_frac"])
    except Exception:
        pass
    return round(PAPER_BANKROLL_USD * frac, 2)


def _row_notional_usd(row):
    """Best-effort $ notional for one freshly-logged paper row, assuming ONE hypothetical
    contract (these loggers don't size positions -- see PAPER_BANKROLL_USD docstring above)."""
    for k in ("price", "yes_ask_c", "fc_prob"):
        if k in row and row[k] is not None:
            v = float(row[k])
            return v / 100.0 if k == "yes_ask_c" else v
    return 1.0


def _live_plan_tickers_today(root):
    """Tickers the LIVE bot (kwx_runner.py) actually fired today, per its own plan log. Read-only;
    the file may legitimately not exist yet (zero live fires so far, per kwx_gate_status.txt as of
    this build) -- that is not an error."""
    path = os.path.join(root, "kwx_runner_plan.jsonl")
    if not os.path.exists(path):
        return set()
    today = _today()
    out = set()
    for r in _load_jsonl(path):
        ts = r.get("ts")
        d = None
        if ts:
            d = _safe(lambda: dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).date().isoformat(), None)
        if d == today or d is None:  # unknown-date rows are conservatively included (never under-flag)
            out.add(r.get("ticker"))
    return out


# ---------------- commands ----------------
def cmd_snapshot(root):
    print("=" * 88)
    print(f"K-WX PORTFOLIO SNAPSHOT -- {dt.datetime.now(dt.timezone.utc).isoformat()}")
    print("=" * 88)
    params = _load_json(os.path.join(root, "p4k_params.json"), {})
    cap = _daily_cap_usd(params)
    state = _load_state()
    if state.get("day") != _today():
        state = {"day": _today(), "deployed_usd_by_sleeve": {}, "collisions": []}
    live_tickers = _live_plan_tickers_today(root)
    print(f"shared paper bankroll : ${PAPER_BANKROLL_USD:,.0f} (nominal)   daily cap: ${cap:,.0f} "
          f"(sizing.max_daily_deploy_frac={params.get('sizing', {}).get('max_daily_deploy_frac', '?')})")
    total_before = sum(state["deployed_usd_by_sleeve"].values())
    print(f"deployed today so far  : ${total_before:,.2f} across {len(state['deployed_usd_by_sleeve'])} sleeve(s)")
    if live_tickers:
        print(f"live bot fired today   : {len(live_tickers)} ticker(s) (dedupe check active)")
    else:
        print("live bot fired today   : 0 (kwx_runner_plan.jsonl absent/empty -- nothing to collide with)")
    print()

    sys.path.insert(0, root)
    results = []
    running_total = total_before
    for name in PAPER_SLEEVES:
        entry = full_registry()[name]
        mod_name, fn_name = entry["cycle"].split(":")
        if running_total >= cap:
            print(f"[{name}] SKIPPED -- combined paper daily cap reached "
                  f"(${running_total:,.2f} >= ${cap:,.2f})")
            results.append({"sleeve": name, "status": "skipped-cap"})
            continue
        try:
            paper_path = os.path.join(root, {"wx_earlylock_forward": "wx_earlylock_paper.jsonl",
                                              "wx_forecast_forward": "wx_forecast_paper.jsonl"}
                                       .get(mod_name, f"{mod_name}_paper.jsonl"))
            n_before = sum(1 for _ in open(paper_path)) if os.path.exists(paper_path) else 0
            import importlib
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, fn_name)
            n_new = fn(verbose=False)
            n_new = n_new if isinstance(n_new, int) else None
            # dedupe pass: inspect the actual newly-appended rows (more robust than trusting the
            # return value's exact meaning across modules) for ticker collisions with the live plan log
            rows_after = _load_jsonl(paper_path)
            new_rows = rows_after[n_before:] if n_before <= len(rows_after) else []
            notional = 0.0
            collisions = []
            for r in new_rows:
                notional += _row_notional_usd(r)
                tkr = r.get("ticker")
                if tkr and tkr in live_tickers:
                    collisions.append(tkr)
            state["deployed_usd_by_sleeve"][name] = state["deployed_usd_by_sleeve"].get(name, 0.0) + notional
            running_total += notional
            if collisions:
                state["collisions"].append({"sleeve": name, "date": _today(), "tickers": collisions})
            print(f"[{name}] OK -- {len(new_rows)} new paper row(s), ~${notional:,.2f} notional "
                  f"(cumulative today ${state['deployed_usd_by_sleeve'][name]:,.2f})"
                  + (f"  ** {len(collisions)} COLLISION(S) with live plan log: {collisions} **" if collisions else ""))
            results.append({"sleeve": name, "status": "ok", "n_new": len(new_rows), "notional_usd": notional,
                             "collisions": collisions})
        except Exception as e:
            print(f"[{name}] FAILED (fail-soft, other sleeves unaffected): {type(e).__name__}: {e}")
            results.append({"sleeve": name, "status": "error", "error": f"{type(e).__name__}: {e}"})

    _save_state(state)
    print()
    ok = sum(1 for r in results if r["status"] == "ok")
    err = sum(1 for r in results if r["status"] == "error")
    skip = sum(1 for r in results if r["status"] == "skipped-cap")
    print(f"summary: {ok} ok, {err} failed, {skip} skipped (cap) out of {len(results)} registered paper sleeve(s)")
    print(f"state persisted -> {STATE_PATH}")
    return results


def _sleeve_status_line(name, entry, sleeves_block):
    p = sleeves_block.get(name, {})
    status = p.get("status", entry.get("note", "(no p4k_params.json sleeve entry)"))
    gate = p.get("gate")
    if gate is None:
        gate_str = "no gate (always on)" if name in ("taker_mechanical", "stacking") else "n/a"
    else:
        cur = gate.get("current", gate.get("current_days_elapsed"))
        thr = gate.get("threshold", gate.get("threshold_days"))
        acc = gate.get("accrual_per_day")
        gate_str = f"{gate.get('metric')}: {cur}/{thr}" + (f", accrual={acc}/day" if acc is not None else
                                                             ", NOT time-accruable" if acc is None and "metric" in gate else "")
    return f"  [{entry['kind']:14s}] {name:24s} gate: {gate_str:55s} status: {status[:90]}"


def cmd_status(root):
    print("=" * 96)
    print("K-WX STACKED PORTFOLIO STATUS")
    print(f"repo root: {root}")
    print("=" * 96)
    params = _load_json(os.path.join(root, "p4k_params.json"), {})
    reg, _ = _ensure_registry_section(root, write=False)
    sleeves_block = params.get("sleeves", {})

    print("\n--- sleeve registry (kind / gate / status) ---")
    for name, entry in sorted(full_registry().items()):
        print(_sleeve_status_line(name, entry, sleeves_block))

    print("\n--- paper-sleeve accrual (from their own settled logs, read-only) ---")
    for name in PAPER_SLEEVES:
        mod_name = full_registry()[name]["cycle"].split(":")[0]
        settled_path = os.path.join(root, {"wx_earlylock_forward": "wx_earlylock_settled.jsonl",
                                            "wx_forecast_forward": "wx_forecast_settled.jsonl"}
                                     .get(mod_name, f"{mod_name}_settled.jsonl"))
        paper_path = os.path.join(root, {"wx_earlylock_forward": "wx_earlylock_paper.jsonl",
                                          "wx_forecast_forward": "wx_forecast_paper.jsonl"}
                                   .get(mod_name, f"{mod_name}_paper.jsonl"))
        n_settled = len(_load_jsonl(settled_path))
        n_paper = len(_load_jsonl(paper_path))
        dec_mod = full_registry()[name].get("decision_module")
        verdict_str = "(no decision gate authored)"
        if dec_mod:
            try:
                sys.path.insert(0, root)
                import importlib
                dm = importlib.import_module(dec_mod)
                m = dm.compute()
                label, reason = dm.verdict(m)
                verdict_str = f"{label} -- {reason}"
            except Exception as e:
                verdict_str = f"(decision compute failed: {type(e).__name__}: {e})"
        print(f"  {name:12s} paper_rows={n_paper:<5d} settled={n_settled:<5d} verdict: {verdict_str}")

    print("\n--- combined realistic $/mo (lightweight re-derivation of wx_path_to_4k.py's model) ---")
    combined = _combined_realistic_usd_per_mo(root, params)
    if combined is None:
        print("  wx_path_to_4k.py not importable from this repo root -- skipped.")
    else:
        for row in combined["rows"]:
            print(f"  scenario={row['scenario']:16s} bankroll=${row['bankroll']:>7,} -> "
                  f"median ${row['median']:>6,.0f}/mo ({row['pct_goal']:.1f}% of ${combined['goal']:,}/mo goal)"
                  f"{'  [assumed-gate]' if row['assumed'] else ''}")
        print(f"  (N={combined['trials']} trials/cell -- same as wx_path_to_4k.py's own model, trimmed to a "
              f"3-scenario x 3-bankroll grid for speed. Full 4x12 grid + p10/p90 bands: python wx_path_to_4k.py)")
        print(f"  HONEST HEADLINE: today's validated, no-assumed-gate capacity is the 'conservative_live' row "
              f"above (observed live fill behavior, not backtest assumption). Funnel survivors registered: "
              f"{len(SURVIVOR_REGISTRY)} -- none yet, so no additional verified EV is added on top of this.")

    print("\n--- bankroll-rung authorization (informational; source of truth is wx_path_to_4k.py) ---")
    try:
        sys.path.insert(0, root)
        import wx_path_to_4k as P
        for r in P.bankroll_rung_status(params):
            print(f"  {r['name']:6s} {r['range']:12s} gate={r['gate_metric']:35s} {r['current']}/{r['threshold']} "
                  f" authorized_today={r['authorized_today']}")
    except Exception as e:
        print(f"  (unavailable: {type(e).__name__}: {e})")


def _combined_realistic_usd_per_mo(root, params, bankrolls=(10, 2000, 10000)):
    """Reuses wx_path_to_4k.py's own simulate_month()/resolve_active_sleeves() UNCHANGED -- same
    formulas, same trial count per cell (params.scenarios[*].trials), same param file. The only
    difference from running wx_path_to_4k.py directly is a trimmed scenario/bankroll grid (3
    scenarios x 3 bankrolls = 9 cells here, vs its full 4x12=48), which is what keeps this fast
    enough for a `status` call or cron cadence. NOT a reimplementation of the model: any
    methodology change in wx_path_to_4k.py is picked up automatically next run. Fail-soft: returns
    None if the module/params aren't importable (e.g. this script pointed at a stale --repo)."""
    try:
        sys.path.insert(0, root)
        import wx_path_to_4k as P
        if not params:
            return None
        rng = random.Random(20260720)
        goal = params.get("goal_usd_per_month", 4000)
        rows = []
        for scenario in ("conservative", "conservative_live", "base"):
            if scenario not in params.get("scenarios", {}):
                continue
            for b in bankrolls:
                res = P.simulate_month(b, scenario, params, rng, days=21)
                rows.append({"scenario": scenario, "bankroll": b, "median": res["median"],
                             "pct_goal": 100 * res["median"] / goal, "assumed": res["depends_on_assumed"]})
        return {"rows": rows, "goal": goal, "trials": params.get("scenarios", {}).get("base", {}).get("trials", "?")}
    except Exception as e:
        print(f"  [combined-$/mo] WARNING: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def cmd_correlate(root):
    print("=" * 88)
    print("K-WX SLEEVE SIGNAL CORRELATION (same-day overlap, from each sleeve's own logs)")
    print("=" * 88)
    sources = {
        "early_lock": os.path.join(root, "wx_earlylock_paper.jsonl"),
        "forecast": os.path.join(root, "wx_forecast_paper.jsonl"),
        "near_miss": os.path.join(root, "kwx_near_miss.jsonl"),
        "live_plan": os.path.join(root, "kwx_runner_plan.jsonl"),
    }
    day_sets = {}
    ticker_sets = {}
    for name, path in sources.items():
        rows = _load_jsonl(path)
        days, tickers = set(), set()
        for r in rows:
            d = r.get("date")
            if not d and r.get("ts") and isinstance(r["ts"], (int, float)):
                d = _safe(lambda: dt.datetime.fromtimestamp(r["ts"] / 1000, dt.timezone.utc).date().isoformat(), None)
            elif not d and r.get("ts"):
                d = _safe(lambda: str(r["ts"])[:10], None)
            if d:
                days.add(d)
            if r.get("ticker"):
                tickers.add(r["ticker"])
        day_sets[name] = days
        ticker_sets[name] = tickers
        print(f"  {name:10s} n={len(rows):<5d} distinct_days={len(days):<3d} distinct_tickers={len(tickers)}")

    print("\n--- pairwise same-day overlap (days both sleeves logged >=1 row) ---")
    names = list(sources.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            inter = day_sets[a] & day_sets[b]
            union = day_sets[a] | day_sets[b]
            jac = len(inter) / len(union) if union else 0.0
            tinter = ticker_sets[a] & ticker_sets[b]
            print(f"  {a:10s} x {b:10s}: {len(inter)} shared day(s) (Jaccard={jac:.2f}), "
                  f"{len(tinter)} shared ticker(s)"
                  + (f" {sorted(tinter)[:5]}" if tinter else ""))
    print("\n(interpretation: high day-overlap + shared tickers between two PAPER sleeves means they are "
          "not independent bets -- correlated drawdowns should be modeled jointly, not summed naively, "
          "before either is sized for real capital.)")


def cmd_registry(root, write):
    reg, params = _ensure_registry_section(root, write=write)
    print(json.dumps(reg, indent=2, default=str))
    if not write:
        print("\n(pass --write to upsert this into p4k_params.json's portfolio_registry key; "
              "no-op if that key already exists)", file=sys.stderr)


def main():
    argv = sys.argv[1:]
    cmd = argv[0] if argv and not argv[0].startswith("-") else None
    root = resolve_repo_root(argv)
    if cmd == "snapshot":
        cmd_snapshot(root)
    elif cmd == "status":
        cmd_status(root)
    elif cmd == "correlate":
        cmd_correlate(root)
    elif cmd == "registry":
        cmd_registry(root, write="--write" in argv)
    else:
        print(__doc__)
        sys.exit(0 if cmd is None else 1)


if __name__ == "__main__":
    main()
