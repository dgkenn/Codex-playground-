#!/usr/bin/env python3
"""kwx_goal_status.py -- one-screen digest status, recomputed live. Fail-soft, mirrors kwx_paper_gate.PASS.

Companion files (kwx_gate_status.txt, kwx_runner_state.json, kwx_near_miss.jsonl, .kwx_halt,
p4k_params.json) are looked up relative to a repo root, NOT this script's own directory -- this script
may be copied/vendored (e.g. into a build/ scratch dir) while the live state files stay in the repo.
Resolution order: --repo CLI arg > $KWX_REPO_ROOT env var > walk up from this script's directory looking
for kwx_gate_status.txt > this script's own directory (last-resort, old behavior). Every lookup stays
fail-soft: a missing/unreadable file prints its default rather than raising, but a wrong root will now
print honest "?"/defaults instead of silently reading nothing from an empty scratch directory.
"""
import json, os, sys, datetime as dt


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def resolve_repo_root(argv):
    for i, a in enumerate(argv):
        if a == "--repo" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--repo="):
            return a.split("=", 1)[1]
    env = os.environ.get("KWX_REPO_ROOT")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    for _ in range(6):
        if os.path.exists(os.path.join(d, "kwx_gate_status.txt")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return here  # last resort: old behavior, so this still runs standalone from a checkout


def _count_missed(missed):
    """Schema-flexible: handles {ticker: date} (one entry per key, current kwx_runner_state.json shape)
    as well as {date: [tickers]} (one entry per list item), so a future schema change doesn't silently
    turn this into a wrong small number instead of the true ticker count."""
    if not missed:
        return 0
    sample = next(iter(missed.values()))
    if isinstance(sample, list):
        return sum(len(v) for v in missed.values())
    return len(missed)


def _next_gate_line(n_fired, params):
    """Best-effort staged NEXT GATE text: uses p4k_params.json's bankroll_rungs (if found) to advance
    past the Stage-0 paper gate once fires exist, instead of always printing the same hardcoded line
    regardless of progress. Falls back to the paper-gate text if params aren't available or n_fired
    hasn't cleared it yet -- fail-soft, never raises."""
    paper_gate = "n>=30 settled fires, win>=99%, EV/ct>=+0.12, t>=3 [kwx_paper_gate.PASS]"
    if n_fired < 30 or not params:
        return paper_gate
    rungs = params.get("bankroll_rungs") or []
    for r in rungs:
        if r.get("gate_metric") == "n_live_fires" and n_fired < r.get("gate_threshold", float("inf")):
            return f"{r['gate_metric']}>={r['gate_threshold']} for {r['name']} ({r['range']}) [wx_scaling_schedule.md]"
    return "all n_live_fires bankroll-rung gates cleared -- see p4k_params.json bankroll_rungs for the next non-fire-count gate (e.g. depth_adaptive policy decision)"


def status_fields(root=None):
    """Compute every field the CLI printout and the digest one-liner both need, once. Fail-soft
    throughout (mirrors the module docstring); never raises."""
    root = root or resolve_repo_root(sys.argv[1:] if len(sys.argv) > 1 else [])
    gate_txt = _safe(lambda: open(os.path.join(root, "kwx_gate_status.txt")).read(), "")
    verdict = next((l.split("VERDICT: ", 1)[1] for l in gate_txt.splitlines() if "VERDICT:" in l), "no status file yet")
    state = _safe(lambda: json.load(open(os.path.join(root, "kwx_runner_state.json"))), {})
    n_fired = len(state.get("fired", {}))
    n_missed = _count_missed(state.get("missed", {}))
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()

    def _count_near_miss_today():
        n = 0
        with open(os.path.join(root, "kwx_near_miss.jsonl")) as f:
            for line in f:
                row = json.loads(line)
                d = row.get("date") or _safe(lambda: dt.datetime.fromtimestamp(row["ts"] / 1000, dt.timezone.utc).date().isoformat(), None)
                if d == today:
                    n += 1
        return n

    nm = _safe(_count_near_miss_today, "?")
    halted = os.path.exists(os.path.join(root, ".kwx_halt"))
    params = _safe(lambda: json.load(open(os.path.join(root, "p4k_params.json"))), None)
    return {
        "root": root, "verdict": verdict, "n_fired": n_fired, "n_missed": n_missed,
        "nm": nm, "halted": halted, "next_gate": _next_gate_line(n_fired, params),
    }


def summary_line(root=None):
    """One-line condensed status for kwx_daily_digest.py's guarded-import block (finding #7 / repo
    ask: 'ONE fail-soft goal-status line'). Fail-soft: on any internal error, returns a placeholder
    string rather than raising -- the caller's own try/except still guards the import itself."""
    def _build():
        f = status_fields(root)
        stage = "0-paper-gate" if f["n_fired"] == 0 else f"1+-live({f['n_fired']} fired)"
        if f["halted"]:
            return f"stage={stage} HALTED (kill-switch on)"
        return f"stage={stage} near-misses-today={f['nm']} missed={f['n_missed']} next-gate=[{f['next_gate']}]"
    return _safe(_build, "goal-status unavailable")


def main():
    f = status_fields()
    root, n_fired, nm, n_missed = f["root"], f["n_fired"], f["nm"], f["n_missed"]
    stage_txt = "0 -- pre-canary paper gate" if n_fired == 0 else f"1+ live, {n_fired} fired"
    blocking_txt = "KILL-SWITCH HALTED" if f["halted"] else f"{n_fired} settled; {nm} near-misses today, {n_missed} missed not converting"
    print("=== K-WX GOAL STATUS ($4k/mo path) ===")
    print(f"CURRENT STAGE : {stage_txt} ({f['verdict']})")
    print(f"NEXT GATE     : {f['next_gate']}")
    print(f"BLOCKING ON   : {blocking_txt}")
    if root != os.path.dirname(os.path.abspath(__file__)):
        print(f"(repo root    : {root})")


if __name__ == "__main__":
    main()
