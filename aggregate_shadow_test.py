"""aggregate_shadow_test.py -- Self-contained test harness for aggregate_shadow.py.

Regression coverage for the under-counting bug (see aggregate_shadow.py's module docstring):
paper-collect.yml's "per-run summary" step ran `aggregate_shadow.py` against a `gha_data/` that
only ever held ONE run's fresh files, so the "daily rollup" SUMMARY.txt silently reflected ~8-12
windows instead of the day's ~340. The fix (build_corpus) merges local files with a read-only
pull of the trailing history from the `gha-data` branch. These tests exercise build_corpus and
the SUMMARY.txt text format directly, with NO network access (mock subprocess / --no-fetch only).

Run: python aggregate_shadow_test.py
Exits 0 only if ALL tests PASS.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest.mock as mock
from contextlib import redirect_stdout

import aggregate_shadow as ag

# ---------------------------------------------------------------------------
# Test result tracking (mirrors kalshi_safeguards_test.py / portfolio_guardian_test.py)
# ---------------------------------------------------------------------------

_results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}] {name}: {detail}")


def _row(asset, ws, resolved=True, tenor=15):
    r = {"ws": ws, "asset": asset, "tenor_min": tenor,
         "resolved_up": 1 if resolved else None,
         "baseline": {"net": 1.0, "gross": 1.0},
         "micro_gate": {"net": 1.5, "gross": 1.5}}
    return json.dumps(r)


def _write_fixture(root: str, files: dict[str, list[str]]) -> None:
    os.makedirs(root, exist_ok=True)
    for name, lines in files.items():
        with open(os.path.join(root, name), "w") as fh:
            fh.write("\n".join(lines) + "\n")


# ===========================================================================
# TEST 1 -- de-duped union across overlapping runids/assets == the real census
# ===========================================================================

def test_dedup_union_two_runids_two_assets_one_day():
    name = "T1: two-runid/two-asset/one-day de-duped union"
    tmp = tempfile.mkdtemp(prefix="ag_test_")
    try:
        base_ws = 1782000000
        WS = [base_ws + i * 900 for i in range(6)]
        day_dir = os.path.join(tmp, "gha_data", "2026-07-01")
        _write_fixture(day_dir, {
            "shadow_windows_kalshi_btc15m_r1.jsonl":
                [_row("btc", WS[0]), _row("btc", WS[1]), _row("btc", WS[2])],
            "shadow_windows_kalshi_btc15m_r2.jsonl":
                [_row("btc", WS[1]), _row("btc", WS[2]), _row("btc", WS[3]),
                 _row("btc", WS[4], resolved=False)],
            "shadow_windows_kalshi_eth15m_r1.jsonl":
                [_row("eth", WS[0]), _row("eth", WS[1])],
            "shadow_windows_kalshi_eth15m_r3.jsonl":
                [_row("eth", WS[4]), _row("eth", WS[5])],
        })
        # Ground truth: manual union of distinct RESOLVED (asset, tenor, ws) keys across every
        # file, computed independently of build_corpus's own logic.
        expected_keys = {("btc", 15, WS[0]), ("btc", 15, WS[1]), ("btc", 15, WS[2]),
                          ("btc", 15, WS[3]), ("eth", 15, WS[0]), ("eth", 15, WS[1]),
                          ("eth", 15, WS[4]), ("eth", 15, WS[5])}

        by_ws, n_sources = ag.build_corpus(roots=[os.path.join(tmp, "gha_data")], no_fetch=True)

        got_keys = set(by_ws.keys())
        ok = got_keys == expected_keys and n_sources == 4
        detail = f"n_windows={len(got_keys)} (want {len(expected_keys)}), n_sources={n_sources} (want 4)"
        if got_keys != expected_keys:
            detail += f"; missing={expected_keys - got_keys} extra={got_keys - expected_keys}"
        record(name, ok, detail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# TEST 2 -- overlapping runs never double-count a shared (asset, ws)
# ===========================================================================

def test_overlap_first_wins_no_double_count():
    name = "T2: overlapping runs collapse to ONE window, not two"
    tmp = tempfile.mkdtemp(prefix="ag_test_")
    try:
        ws = 1782000900
        day_dir = os.path.join(tmp, "gha_data", "2026-07-01")
        _write_fixture(day_dir, {
            "shadow_windows_kalshi_btc15m_rA.jsonl": [_row("btc", ws)],
            "shadow_windows_kalshi_btc15m_rB.jsonl": [_row("btc", ws)],   # same window, 2nd run
        })
        by_ws, _ = ag.build_corpus(roots=[os.path.join(tmp, "gha_data")], no_fetch=True)
        ok = len(by_ws) == 1 and ("btc", 15, ws) in by_ws
        record(name, ok, f"n_windows={len(by_ws)} (want 1)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# TEST 3 -- --no-fetch (and a local full checkout) never shell out to git
# ===========================================================================

def test_no_fetch_skips_subprocess():
    name = "T3: --no-fetch never invokes git"
    tmp = tempfile.mkdtemp(prefix="ag_test_")
    try:
        day_dir = os.path.join(tmp, "gha_data", "2026-07-01")
        _write_fixture(day_dir, {"shadow_windows_kalshi_btc15m_r1.jsonl": [_row("btc", 1782000000)]})
        with mock.patch("subprocess.run", side_effect=AssertionError("git must not be invoked")) as m:
            ag.build_corpus(roots=[os.path.join(tmp, "gha_data")], no_fetch=True)
        record(name, not m.called, f"subprocess.run called={m.called}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_local_day_dirs_skip_remote_fetch_even_without_no_fetch():
    name = "T4: a local full checkout (day-dirs present) skips the remote pull too"
    tmp = tempfile.mkdtemp(prefix="ag_test_")
    try:
        day_dir = os.path.join(tmp, "gha_data", "2026-07-01")
        _write_fixture(day_dir, {"shadow_windows_kalshi_btc15m_r1.jsonl": [_row("btc", 1782000000)]})
        with mock.patch("subprocess.run", side_effect=AssertionError("git must not be invoked")) as m:
            ag.build_corpus(roots=[os.path.join(tmp, "gha_data")], no_fetch=False)
        record(name, not m.called, f"subprocess.run called={m.called}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# TEST 5 -- remote fetch failure degrades gracefully (never raises)
# ===========================================================================

def test_remote_fetch_failure_is_non_fatal():
    name = "T5: a failing git fetch degrades to local-only data, no crash"
    tmp = tempfile.mkdtemp(prefix="ag_test_")
    try:
        # NOTE: no day-dirs under this root (flat), so build_corpus WILL attempt the remote pull
        # unless no_fetch -- here we leave no_fetch=False and force the git call to fail, to prove
        # the failure is swallowed (this is exactly the "offline/sandboxed" runtime scenario).
        flat_dir = os.path.join(tmp, "gha_data")
        _write_fixture(flat_dir, {"shadow_windows_kalshi_btc15m_r1.jsonl": [_row("btc", 1782000000)]})
        with mock.patch("subprocess.run", side_effect=OSError("no git binary / offline")):
            try:
                by_ws, n_sources = ag.build_corpus(roots=[flat_dir], no_fetch=False)
                ok = len(by_ws) == 1 and n_sources == 1
                record(name, ok, f"n_windows={len(by_ws)} n_sources={n_sources} (no exception raised)")
            except Exception as e:
                record(name, False, f"raised {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# TEST 6 -- SUMMARY.txt text format stays parseable by dashboard.py's parser
# ===========================================================================

def test_report_format_backward_compatible():
    name = "T6: _report() output stays parseable by dashboard.py's format"
    tmp = tempfile.mkdtemp(prefix="ag_test_")
    try:
        base_ws = 1782000000
        rows = []
        for i in range(20):        # enough windows for the paired-t / day-clustered sections to render
            ws = base_ws + i * 900
            rows.append(json.dumps({
                "ws": ws, "asset": "btc", "tenor_min": 15, "resolved_up": 1,
                "baseline": {"net": 1.0, "gross": 1.0},
                "micro_gate": {"net": 1.0 + 0.01 * i, "gross": 1.0 + 0.01 * i},
            }))
        day_dir = os.path.join(tmp, "gha_data", "2026-07-01")
        _write_fixture(day_dir, {"shadow_windows_kalshi_btc15m_r1.jsonl": rows})

        by_ws, n_sources = ag.build_corpus(roots=[os.path.join(tmp, "gha_data")], no_fetch=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ag._report(by_ws, n_sources)
        text = buf.getvalue()

        checks = {
            'starts with "shadow comparison over N de-duped windows | files=M"':
                text.splitlines()[0].startswith("shadow comparison over") and "de-duped windows" in text.splitlines()[0]
                and "files=" in text.splitlines()[0],
            'has a window-level header line starting with "variant"':
                any(ln.split()[:1] == ["variant"] for ln in text.splitlines() if ln.strip()),
            'has the day-clustered header ("clust t" + "variant")':
                any("clust t" in ln and "variant" in ln for ln in text.splitlines()),
            'has a deploy-watch or DECAY-ALERT line (dashboard.py regex: ^(DECAY-ALERT.*|deploy-watch:.*)$)':
                any(ln.startswith("DECAY-ALERT") or ln.startswith("deploy-watch:") for ln in text.splitlines()),
        }
        ok = all(checks.values())
        detail = "; ".join(f"{'OK' if v else 'MISSING'}: {k}" for k, v in checks.items())
        record(name, ok, detail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    test_dedup_union_two_runids_two_assets_one_day()
    test_overlap_first_wins_no_double_count()
    test_no_fetch_skips_subprocess()
    test_local_day_dirs_skip_remote_fetch_even_without_no_fetch()
    test_remote_fetch_failure_is_non_fatal()
    test_report_format_backward_compatible()

    print()
    print("=" * 70)
    print(f"{'TEST':<55} {'RESULT'}")
    print("-" * 70)
    all_pass = True
    for name, passed, detail in _results:
        tag = "PASS" if passed else "FAIL"
        print(f"  {name:<53} {tag}")
        if not passed:
            all_pass = False
            print(f"    DETAIL: {detail}")
    print("=" * 70)

    if all_pass:
        print(f"ALL {len(_results)} TESTS PASSED")
        sys.exit(0)
    else:
        n_fail = sum(1 for _, p, _ in _results if not p)
        print(f"{n_fail}/{len(_results)} TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
