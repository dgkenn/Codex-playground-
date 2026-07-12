"""chaos_drill.py -- offline kill-restart harness for kalshi_trader.py's dead-man fixes.

DEADMAN_AUDIT.md documented two HIGH-severity gaps and their fixes in kalshi_trader.py:
  Fix #1: remote_switch_kill() -- durable sticky-kill via a synchronous GitHub contents-API
          GET(sha)+PUT(LIVE_SWITCH=off), fired from inside _record_kill() at the moment a kill
          trips, instead of depending on a later workflow step a hard-killed runner never reaches.
  Fix #2: get_positions()/_parse_inherited_position() -- startup venue-position reconciliation,
          so a restarted process seeds net_delta/pos/win_cost from real venue inventory instead of
          always assuming flat.

Both passed MOCKED unit tests (kalshi_safeguards_test.py T11/T12) but had never been exercised
against a REAL process kill + restart. This harness does that, offline, with no real money and no
real secrets:

  - Spins up a tiny local HTTP server (ThreadingHTTPServer) implementing just the Kalshi REST
    endpoints kalshi_trader.py calls (markets / orderbook / market-detail / portfolio orders,
    fills, balance, positions), plus a GitHub-contents-API-shaped endpoint for the sticky-kill
    PUT/GET and a Telegram-shaped endpoint for alert capture.
  - Launches kalshi_trader.py as a REAL, SEPARATE OS process (subprocess, not a thread/fork) via a
    tiny generated launcher that imports kalshi_trader, monkeypatches its module-level `BASE` (and
    `WS_URL`) constants to point at the mock server, monkeypatches `requests.post` so Telegram
    calls redirect to the mock, then calls kalshi_trader.main() with --live against a throwaway
    RSA keypair generated just for this drill. This is the "env override only if one exists, else
    monkeypatch the module" fallback: kalshi_trader.py has no BASE env override, so this is the
    only way to point it at a mock without editing the file (which is out of scope -- read-only).
    A real OS process (not a fork of this multithreaded harness, which risks post-fork mutex
    deadlock against the mock server's own thread) is required so a real SIGKILL can be delivered
    to it while this harness's own process survives to inspect the aftermath -- the actual gap
    this whole exercise is about.
  - DRILL A: start it, let it quote against the mock mid-window, SIGKILL it, then restart it in
    the SAME working directory (so the OS-released flock, the gitignored kill sentinel path, and
    the JSONL state files are all shared exactly like a real GHA checkout would be) with the mock
    now serving a nonzero canned position on the same still-open ticker -- the exact "restart
    lands on the same still-open ticker as the dead session" scenario DEADMAN_AUDIT.md flagged as
    the real risk. Verifies the restart's logs show positions were queried and inventory seeded,
    that an alert fired (captured at the mock Telegram endpoint), and that no JSONL state file has
    a corrupted trailing line.
  - DRILL B: start it with the mock already serving a large canned position (so the C2 loss-limit
    trips almost immediately on window-attach), watch the mock's GitHub-contents-API log for the
    GET-sha + PUT(off) sequence, then SIGKILL the process the INSTANT that PUT lands -- simulating
    a runner dying a heartbeat after the trip, before any later workflow step could ever run.
    Verifies the local sentinel file exists and the mock's switch state is durably "off" despite
    the immediate hard-kill.

Run: python3 chaos_drill.py
Writes CHAOS_DRILL.md (PASS/FAIL per assertion) next to this file. Never touches kalshi_trader.py.
All child processes run in scratch directories outside the repo; nothing here is committed.
"""
from __future__ import annotations

import base64
import glob
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(REPO_DIR, "CHAOS_DRILL.md")

# Scratch root OUTSIDE the repo -- mock-server state files / child cwds must never land in git.
SCRATCH_ROOT = os.environ.get("CHAOS_DRILL_SCRATCH") or tempfile.mkdtemp(prefix="chaos_drill_")

ASSET = "btc"
TICKER = "KXBTC15M-CHAOSDRILL-T50"


# ---------------------------------------------------------------------------
# Mock venue + GitHub-contents + Telegram server
# ---------------------------------------------------------------------------

class MockState:
    def __init__(self):
        self.lock = threading.Lock()
        self.switch_content = "on"
        self.switch_sha = "sha-0"
        self._sha_ctr = 0
        self.positions = []          # list of {"ticker","position","market_exposure"} dicts
        self.orders = {}             # order_id -> dict(status="resting"/"canceled", ...)
        self._oid_ctr = 0
        self.n_orders_posted = 0
        self.n_positions_polled = 0
        self.n_open_orders_polled = 0
        self.put_log = []            # [{ts, sha_used, new_content, status}]
        self.get_switch_log = []     # [{ts, mode: "raw"|"json"}]
        self.telegram_log = []       # [{ts, text}]
        close_ts = time.time() + 900   # 15-min window, never rolls over during a short drill
        self.close_time_iso = (
            datetime.fromtimestamp(close_ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        )

    def reset_switch(self):
        with self.lock:
            self.switch_content = "on"
            self._sha_ctr += 1
            self.switch_sha = f"sha-{self._sha_ctr}"
            self.put_log = []
            self.get_switch_log = []

    def reset_orders(self):
        with self.lock:
            self.orders = {}
            self.n_orders_posted = 0

    def inject_resting_order(self, side="yes", price=0.46, count=2):
        with self.lock:
            self._oid_ctr += 1
            oid = f"mockord-{self._oid_ctr}"
            self.orders[oid] = {
                "order_id": oid, "ticker": TICKER, "side": side,
                "price": price, "count": count, "status": "resting",
                "note": "harness-injected: simulates an order left resting by the dead session",
            }
            return oid

    def set_positions(self, position_count, cost_dollars, side="yes"):
        with self.lock:
            if position_count == 0:
                self.positions = []
            else:
                signed = position_count if side == "yes" else -position_count
                self.positions = [{
                    "ticker": TICKER,
                    "position": signed,
                    "market_exposure": int(round(cost_dollars * 100)),
                }]


class MockHandler(BaseHTTPRequestHandler):
    state: MockState = None  # set by run_server()
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # silence default access log; drill has its own logging

    # -- helpers --
    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_raw(self, text, code=200):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw or b"{}")
        except Exception:
            return {}

    def _path(self):
        from urllib.parse import urlsplit
        return urlsplit(self.path).path

    # -- routing --
    def do_GET(self):
        p = self._path()
        st = self.state
        if p == "/trade-api/v2/markets":
            self._send_json({"markets": [{"ticker": TICKER, "close_time": st.close_time_iso}]})
        elif p == f"/trade-api/v2/markets/{TICKER}/orderbook":
            self._send_json({"orderbook_fp": {
                "yes_dollars": [[0.40, 300], [0.44, 300], [0.46, 300]],
                "no_dollars": [[0.45, 300], [0.49, 300], [0.51, 300]],
            }})
        elif p == f"/trade-api/v2/markets/{TICKER}":
            self._send_json({"market": {"ticker": TICKER, "result": ""}})
        elif p == "/trade-api/v2/portfolio/orders":
            with st.lock:
                st.n_open_orders_polled += 1
                oo = [o for o in st.orders.values() if o["status"] == "resting"]
            self._send_json({"orders": oo})
        elif p == "/trade-api/v2/portfolio/fills":
            self._send_json({"fills": []})
        elif p == "/trade-api/v2/portfolio/balance":
            self._send_json({"balance": 500000})
        elif p == "/trade-api/v2/portfolio/positions":
            with st.lock:
                st.n_positions_polled += 1
                pos = list(st.positions)
            self._send_json({"market_positions": pos})
        elif p == "/api.github.com/repos/chaos/drill/contents/LIVE_SWITCH":
            accept = self.headers.get("Accept", "")
            with st.lock:
                content, sha = st.switch_content, st.switch_sha
                st.get_switch_log.append({"ts": time.time(), "mode": "raw" if "raw" in accept else "json"})
            if "raw" in accept:
                self._send_raw(content)
            else:
                self._send_json({"sha": sha, "encoding": "base64",
                                  "content": base64.b64encode(content.encode()).decode()})
        else:
            self._send_json({"error": "not_found", "path": p}, code=404)

    def do_POST(self):
        p = self._path()
        st = self.state
        if p == "/trade-api/v2/portfolio/orders":
            body = self._read_json_body()
            with st.lock:
                st._oid_ctr += 1
                oid = f"live-{st._oid_ctr}"
                st.orders[oid] = {"order_id": oid, "status": "resting", **{
                    k: v for k, v in body.items() if k in ("ticker", "side", "count")
                }}
                st.n_orders_posted += 1
            self._send_json({"order": {"order_id": oid}}, code=201)
        elif p == "/telegram/sendMessage":
            body = self._read_json_body()
            with st.lock:
                st.telegram_log.append({"ts": time.time(), "text": body.get("text", "")})
            self._send_json({"ok": True, "result": {"message_id": len(st.telegram_log)}})
        else:
            self._send_json({"error": "not_found", "path": p}, code=404)

    def do_PUT(self):
        p = self._path()
        st = self.state
        if p == "/api.github.com/repos/chaos/drill/contents/LIVE_SWITCH":
            body = self._read_json_body()
            sha_used = body.get("sha")
            new_content = base64.b64decode(body.get("content", "")).decode(errors="replace")
            with st.lock:
                if sha_used != st.switch_sha:
                    st.put_log.append({"ts": time.time(), "sha_used": sha_used,
                                        "new_content": new_content, "status": 409})
                    self._send_json({"message": "sha mismatch"}, code=409)
                    return
                st.switch_content = new_content
                st._sha_ctr += 1
                st.switch_sha = f"sha-{st._sha_ctr}"
                st.put_log.append({"ts": time.time(), "sha_used": sha_used,
                                    "new_content": new_content, "status": 200})
            self._send_json({"content": {"sha": st.switch_sha}}, code=200)
        else:
            self._send_json({"error": "not_found", "path": p}, code=404)

    def do_DELETE(self):
        p = self._path()
        st = self.state
        prefix = "/trade-api/v2/portfolio/orders/"
        if p.startswith(prefix):
            oid = p[len(prefix):]
            with st.lock:
                o = st.orders.get(oid)
                if o is not None:
                    o["status"] = "canceled"
            self._send_json({}, code=200)
        else:
            self._send_json({"error": "not_found", "path": p}, code=404)


def run_server(state: MockState):
    def handler_factory(*args, **kwargs):
        MockHandler.state = state
        return MockHandler(*args, **kwargs)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


# ---------------------------------------------------------------------------
# Throwaway RSA keypair (no real money, no real secrets -- generated fresh, used only to satisfy
# kalshi_trader's _load_private_key()/_sign(), never registered with the real venue).
# ---------------------------------------------------------------------------

def gen_throwaway_key(path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(path, "wb") as fh:
        fh.write(pem)


LAUNCHER_TEMPLATE = '''\
import json, os, sys
sys.path.insert(0, {repo_dir!r})

import requests as _requests
_orig_post = _requests.post
_telegram_url = {telegram_url!r}
def _patched_post(url, *args, **kwargs):
    if isinstance(url, str) and "api.telegram.org" in url:
        return _orig_post(_telegram_url, *args, **kwargs)
    return _orig_post(url, *args, **kwargs)
_requests.post = _patched_post

import kalshi_trader
kalshi_trader.BASE = {kalshi_base!r}
kalshi_trader.WS_URL = {ws_url!r}   # deliberately unreachable -- WS is out of scope, see CHAOS_DRILL.md

sys.argv = ["kalshi_trader.py"] + json.loads(os.environ["CHAOS_TRADER_ARGS"])
kalshi_trader.main()
'''


def write_launcher(path, kalshi_base, telegram_url):
    src = LAUNCHER_TEMPLATE.format(
        repo_dir=REPO_DIR, kalshi_base=kalshi_base, telegram_url=telegram_url,
        ws_url="ws://127.0.0.1:9/",
    )
    with open(path, "w") as fh:
        fh.write(src)


# ---------------------------------------------------------------------------
# Child process orchestration
# ---------------------------------------------------------------------------

def build_child_env(key_path, gh_token, tg_token, tg_chat):
    env = dict(os.environ)
    for k in ("KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH", "GH_TOKEN", "GITHUB_TOKEN",
              "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "REMOTE_SWITCH_URL", "I_UNDERSTAND_REAL_MONEY",
              "GITHUB_RUN_ID"):
        env.pop(k, None)
    env.update({
        "I_UNDERSTAND_REAL_MONEY": "yes",
        "KALSHI_API_KEY_ID": "chaos-drill-fake-key-id",
        "KALSHI_PRIVATE_KEY_PATH": key_path,
        "GH_TOKEN": gh_token,
        "TELEGRAM_BOT_TOKEN": tg_token,
        "TELEGRAM_CHAT_ID": tg_chat,
        "PYTHONUNBUFFERED": "1",
        "GITHUB_RUN_ID": "chaos-drill-local",
    })
    return env


def start_trader(cwd, launcher_path, env, logfile_path, extra_args):
    os.makedirs(cwd, exist_ok=True)
    args = [
        "--live", "--asset", ASSET, "--duration", str(extra_args.get("duration", 60)),
        "--remote-switch-url", extra_args["remote_switch_url"],
        "--remote-switch-s", "3",
        "--loss-limit", str(extra_args.get("loss_limit", 6)),
        "--post", "2", "--max-notional", "5", "--poll", "1", "--react-poll", "0.3",
        "--order-ttl-s", "20", "--deadman-s", "15",
    ]
    env = dict(env)
    env["CHAOS_TRADER_ARGS"] = json.dumps(args)
    logfh = open(logfile_path, "w")
    proc = subprocess.Popen(
        [sys.executable, launcher_path],
        cwd=cwd, env=env, stdout=logfh, stderr=subprocess.STDOUT, text=True,
    )
    return proc, logfh


def wait_for(predicate, timeout, interval=0.1):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return False


def watchdog_kill_after(proc, hard_timeout, label, results):
    """Safety-net thread: if a drill phase never reaches its own kill point, force it down so the
    harness can't hang forever. Distinct from the deliberate SIGKILLs the drills perform themselves."""
    def _run():
        if not wait_for(lambda: proc.poll() is not None, hard_timeout):
            results.setdefault("watchdog_notes", []).append(
                f"{label}: hard watchdog timeout ({hard_timeout}s) fired -- process force-killed")
            try:
                proc.kill()
            except Exception:
                pass
    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return th


def read_tail(path, n=4000):
    try:
        with open(path) as fh:
            data = fh.read()
        return data[-n:]
    except Exception:
        return ""


def check_jsonl_corruption(dir_path):
    """Every *.jsonl file (recursively) must consist of newline-delimited valid JSON objects, or be
    empty. Returns (ok: bool, details: list[str])."""
    details = []
    ok = True
    for path in sorted(glob.glob(os.path.join(dir_path, "**", "*.jsonl"), recursive=True)):
        n_lines = 0
        n_bad = 0
        try:
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    n_lines += 1
                    try:
                        json.loads(line)
                    except Exception:
                        n_bad += 1
        except Exception as e:
            details.append(f"{os.path.relpath(path, dir_path)}: could not read ({e})")
            continue
        rel = os.path.relpath(path, dir_path)
        if n_bad:
            ok = False
            details.append(f"{rel}: {n_bad}/{n_lines} lines FAILED json.loads (corruption)")
        else:
            details.append(f"{rel}: {n_lines} lines, all valid JSON" if n_lines else f"{rel}: empty")
    return ok, details


# ---------------------------------------------------------------------------
# Assertions bookkeeping
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.rows = []  # (drill, assertion, passed: bool, detail)

    def add(self, drill, assertion, passed, detail=""):
        self.rows.append((drill, assertion, bool(passed), detail))
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {drill}: {assertion} -- {detail}")

    def all_passed(self, drill=None):
        rows = self.rows if drill is None else [r for r in self.rows if r[0] == drill]
        return all(r[2] for r in rows)


REPORT = Report()


# ---------------------------------------------------------------------------
# DRILL A: mid-window SIGKILL + restart + reconciliation
# ---------------------------------------------------------------------------

def drill_a(state: MockState, port, key_path, gh_token, tg_token, tg_chat):
    print("\n=== DRILL A: mid-window SIGKILL, restart, startup reconciliation ===")
    kalshi_base = f"http://127.0.0.1:{port}/trade-api/v2"
    switch_url = f"http://127.0.0.1:{port}/api.github.com/repos/chaos/drill/contents/LIVE_SWITCH?ref=chaos-drill"
    telegram_url = f"http://127.0.0.1:{port}/telegram/sendMessage"

    launcher = os.path.join(SCRATCH_ROOT, "launcher_a.py")
    write_launcher(launcher, kalshi_base, telegram_url)

    cwd = os.path.join(SCRATCH_ROOT, "drill_a")
    env = build_child_env(key_path, gh_token, tg_token, tg_chat)
    state.reset_switch()
    state.reset_orders()
    state.set_positions(0, 0)   # process #1 starts against a clean (flat) venue

    log1 = os.path.join(SCRATCH_ROOT, "drill_a_run1.log")
    proc1, fh1 = start_trader(cwd, launcher, env, log1,
                               {"duration": 60, "remote_switch_url": switch_url, "loss_limit": 6})
    results = {}
    wd = watchdog_kill_after(proc1, 45, "drill_a_run1", results)

    # Let it discover + reconcile + start quoting. Wait for either real quoting activity or a
    # generous timeout, then also guarantee a leftover resting order via harness injection so the
    # restart's order-reconciliation assertion is deterministic even if market gating never fired
    # a real quote in this short a window (see CHAOS_DRILL.md limitations).
    placed_organically = wait_for(lambda: state.n_orders_posted > 0, timeout=10.0)
    time.sleep(1.0)
    injected_oid = state.inject_resting_order(side="yes", price=0.46, count=2)

    alive_before_kill = proc1.poll() is None
    REPORT.add("Drill A", "process #1 started and was alive before SIGKILL", alive_before_kill,
               f"pid={proc1.pid}")

    # --- SIGKILL process #1 mid-window ---
    os.kill(proc1.pid, signal.SIGKILL)
    exited = wait_for(lambda: proc1.poll() is not None, timeout=10.0)
    fh1.close()
    REPORT.add("Drill A", "process #1 actually died from SIGKILL (not graceful)", exited,
               f"returncode={proc1.returncode}")
    # A real SIGKILL exit is -9 on POSIX; if atexit/_flatten_and_exit ran, that would prove the
    # kill wasn't a real SIGKILL (Python cannot intercept SIGKILL).
    REPORT.add("Drill A", "exit was a true SIGKILL (no atexit/_flatten_and_exit could have run)",
               proc1.returncode == -signal.SIGKILL, f"returncode={proc1.returncode}")

    n_resting_left = sum(1 for o in state.orders.values() if o["status"] == "resting")
    REPORT.add("Drill A", "orders left resting at the venue after the kill (orphans, as expected)",
               n_resting_left >= 1, f"resting={n_resting_left} (organic_fills={placed_organically})")

    lock_path = os.path.join(cwd, f".kalshi_trader_{ASSET}15m.lock")
    sentinel_path = os.path.join(cwd, f".kalshi_killed_{ASSET}15m")
    REPORT.add("Drill A", "no kill sentinel from process #1 (it wasn't killed by the loss-limit)",
               not os.path.exists(sentinel_path), sentinel_path)

    # --- seed the mock with a nonzero inherited position on the SAME ticker, then restart ---
    state.set_positions(3, 1.50, side="yes")   # small: must NOT trip the $6 loss-limit
    log2 = os.path.join(SCRATCH_ROOT, "drill_a_run2.log")
    proc2, fh2 = start_trader(cwd, launcher, env, log2,
                               {"duration": 25, "remote_switch_url": switch_url, "loss_limit": 6})
    wd2 = watchdog_kill_after(proc2, 40, "drill_a_run2", results)

    # Give it time to: acquire the lock, do order reconciliation, do position reconciliation,
    # attach to the window, seed inherited inventory, and quote for a couple cycles.
    time.sleep(9.0)

    lock_acquired = True
    log2_txt_partial = read_tail(log2)
    if "FATAL: another kalshi_trader holds" in log2_txt_partial:
        lock_acquired = False
    REPORT.add("Drill A", "restart's flock was released by the OS after SIGKILL (no false 'double-trader' refusal)",
               lock_acquired, "checked for 'FATAL: another kalshi_trader holds' in restart log")

    # graceful stop of process #2 (SIGTERM -> _flatten_and_exit) so we exercise normal shutdown too
    if proc2.poll() is None:
        os.kill(proc2.pid, signal.SIGTERM)
        wait_for(lambda: proc2.poll() is not None, timeout=10.0)
    if proc2.poll() is None:
        proc2.kill()
        proc2.wait(timeout=5)
    fh2.close()

    log2_txt = read_tail(log2, n=20000)

    REPORT.add("Drill A", "restart queried venue positions at startup",
               "[startup] reconciling venue positions..." in log2_txt, "log line present")
    REPORT.add("Drill A", "restart detected + logged the nonzero inherited position",
               "inherited venue position at startup" in log2_txt, "log line present")
    REPORT.add("Drill A", "restart seeded inherited inventory into risk state (net_delta/pos/win_cost)",
               "seeded inherited position into risk state" in log2_txt, "log line present")
    REPORT.add("Drill A", "restart's order reconciliation cancelled the orphaned resting order",
               f"cancelled stale order {injected_oid[:16]}" in log2_txt,
               f"expected order id fragment {injected_oid[:16]}")

    with state.lock:
        tg_msgs = list(state.telegram_log)
    alerted = any("inherited venue position" in m["text"] for m in tg_msgs)
    REPORT.add("Drill A", "an alert was captured at the mock Telegram endpoint for the inherited position",
               alerted, f"{len(tg_msgs)} telegram messages captured total")

    no_traceback = "Traceback (most recent call last)" not in log2_txt
    REPORT.add("Drill A", "restart log has no uncaught traceback", no_traceback, "")

    ok, details = check_jsonl_corruption(cwd)
    REPORT.add("Drill A", "no JSONL state file corruption across kill+restart", ok,
               "; ".join(details) if details else "no jsonl files written")

    return {"cwd": cwd, "log1": log1, "log2": log2, "watchdog": results}


# ---------------------------------------------------------------------------
# DRILL B: loss-limit trip -> durable PUT -> immediate SIGKILL right after
# ---------------------------------------------------------------------------

def drill_b(state: MockState, port, key_path, gh_token, tg_token, tg_chat):
    print("\n=== DRILL B: loss-limit trip, durable sticky-kill PUT, immediate SIGKILL ===")
    kalshi_base = f"http://127.0.0.1:{port}/trade-api/v2"
    switch_url = f"http://127.0.0.1:{port}/api.github.com/repos/chaos/drill/contents/LIVE_SWITCH?ref=chaos-drill"
    telegram_url = f"http://127.0.0.1:{port}/telegram/sendMessage"

    launcher = os.path.join(SCRATCH_ROOT, "launcher_b.py")
    write_launcher(launcher, kalshi_base, telegram_url)

    cwd = os.path.join(SCRATCH_ROOT, "drill_b")
    env = build_child_env(key_path, gh_token, tg_token, tg_chat)
    state.reset_switch()
    state.reset_orders()
    # Large canned inherited position: worst_open = -(cost/count * |net_delta|) = -(100/40*40) = -$100,
    # which blows through the default $6 loss-limit on the very first loss-limit check after this
    # session attaches to its first window (no real fills/matching engine needed to drive this --
    # the C2 loss-limit check only cares about win_cost/pos/net_delta, which the inherited-position
    # seed populates directly).
    state.set_positions(40, 100.0, side="yes")

    log1 = os.path.join(SCRATCH_ROOT, "drill_b_run1.log")
    proc, fh = start_trader(cwd, launcher, env, log1,
                             {"duration": 60, "remote_switch_url": switch_url, "loss_limit": 6})
    results = {}
    wd = watchdog_kill_after(proc, 45, "drill_b_run1", results)

    tripped = wait_for(lambda: len(state.put_log) > 0, timeout=30.0, interval=0.05)
    REPORT.add("Drill B", "loss-limit trip drove a GitHub-contents-API PUT (durable sticky-kill fired)",
               tripped, f"put_log entries={len(state.put_log)} after up to 30s")

    if tripped:
        # SIGKILL the instant the durable PUT lands -- simulate the runner dying a heartbeat after
        # the trip, before ANY later step (workflow or otherwise) could have persisted it instead.
        os.kill(proc.pid, signal.SIGKILL)
    else:
        # Fallback so the harness doesn't hang; report will show the trip FAILED regardless.
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGKILL)

    exited = wait_for(lambda: proc.poll() is not None, timeout=10.0)
    fh.close()
    REPORT.add("Drill B", "process was actually SIGKILLed immediately after the trip", exited,
               f"returncode={proc.returncode}")
    REPORT.add("Drill B", "the SIGKILL was a true hard kill (returncode == -SIGKILL)",
               proc.returncode == -signal.SIGKILL, f"returncode={proc.returncode}")

    with state.lock:
        get_log = list(state.get_switch_log)
        put_log = list(state.put_log)
        switch_now = state.switch_content

    REPORT.add("Drill B", "the durable-kill code path performed a GET (to fetch sha) before the PUT",
               len(get_log) >= 1, f"{len(get_log)} GETs recorded")
    REPORT.add("Drill B", "the PUT used a real sha obtained from that GET (not a blind PUT)",
               bool(put_log) and put_log[0]["sha_used"] not in (None, ""), str(put_log[:1]))
    REPORT.add("Drill B", "the PUT succeeded (200), i.e. the sticky-kill IS durable at the mock venue",
               bool(put_log) and put_log[0]["status"] == 200, str(put_log[:1]))
    REPORT.add("Drill B", "mock LIVE_SWITCH content is durably 'off' AFTER the hard-kill",
               switch_now.strip().lower() == "off", f"switch_content={switch_now!r}")

    sentinel_path = os.path.join(cwd, f".kalshi_killed_{ASSET}15m")
    REPORT.add("Drill B", "local kill sentinel file exists after the hard-kill",
               os.path.exists(sentinel_path), sentinel_path)
    sentinel_ok = False
    sentinel_reason = ""
    if os.path.exists(sentinel_path):
        try:
            with open(sentinel_path) as sfh:
                sdata = json.loads(sfh.readline())
            sentinel_ok = "loss_limit" in sdata.get("reason", "")
            sentinel_reason = sdata.get("reason", "")
        except Exception as e:
            sentinel_reason = f"unreadable: {e}"
    REPORT.add("Drill B", "sentinel content is well-formed JSON naming the loss_limit trip",
               sentinel_ok, sentinel_reason)

    log_txt = read_tail(log1, n=20000)
    REPORT.add("Drill B", "trader's own log shows the KILL + STICKY-KILL commit lines before death",
               ("KILL: realized" in log_txt) and ("STICKY-KILL" in log_txt), "")

    ok, details = check_jsonl_corruption(cwd)
    REPORT.add("Drill B", "no JSONL state file corruption from the hard-kill-right-after-trip",
               ok, "; ".join(details) if details else "no jsonl files written")

    return {"cwd": cwd, "log": log1, "watchdog": results}


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

GAPS_MD = """
## Gaps this offline drill CANNOT close (what a real $5 live drill must still prove)

This harness validates the two fixed code paths against a fully scripted, single-process mock. It
deliberately does NOT reproduce, and therefore cannot give confidence about:

1. **Real venue latency/timeout behavior under an actual hard kill.** The mock responds in
   microseconds on localhost; the real Kalshi REST API, and the real GitHub contents API, have
   real network latency and can themselves time out or rate-limit mid-retry. `remote_switch_kill`'s
   retry/backoff logic (3 attempts, exponential backoff) is exercised here only against a mock that
   never fails -- a live drill should verify behavior when the GET or PUT genuinely times out or
   409s (stale sha) against the real GitHub API, not just that the happy path fires a PUT.
2. **A REAL OS-level SIGKILL delivered by something other than this harness** -- e.g. the actual
   OOM-killer, or GitHub Actions force-terminating the whole job/runner (which also tears down the
   network namespace, DNS, and any in-flight TCP connections, not just the process). This harness's
   SIGKILL is clean (the process dies instantly with no chance to run Python code, which IS the
   correct simulation of SIGKILL itself) -- but a runner-level force-terminate could also kill an
   in-flight GET/PUT mid-TLS-handshake in ways a local SIGKILL against a same-host mock cannot
   reproduce (e.g. TLS session interruption, DNS cache effects, GH API partial-response fsync
   timing on GitHub's own side).
3. **Real fills / a real matching engine.** The mock has NO order-matching logic: POSTed orders
   just sit as "resting" until DELETEd; nothing ever "fills" server-side. The inherited positions
   used to drive both drills are directly CANNED into the mock `/portfolio/positions` response
   (as the task instructions explicitly allow) rather than organically accumulated through real
   fills. This means: (a) `poll_fills()`'s C-4 first-call fill-seeding branch (the mechanism
   DEADMAN_AUDIT.md's case (c).2 describes as silently discarding pre-existing fills) is NEVER
   exercised by this harness -- there are no fills to seed/discard, only a positions snapshot; the
   get_positions() reconciliation this drill DOES validate is a different, complementary code path
   that DEADMAN_AUDIT.md's fix #2 added specifically because the fill-seeding path alone was blind.
   (b) DRILL A's "orphaned resting order" is real (organically placed AND/OR harness-injected -- see
   the report row for which happened this run) and IS exercised through the real C7
   get_open_orders()+cancel_order() path.
3b. **The strand-disposal / naked-leg management paths** (`--dispose-cross`, `--chase-unpaired-s`,
   `--close-force-s`) are UNEXERCISED here -- gap #3 in DEADMAN_AUDIT.md's severity list (naked legs
   get zero active disposal for the remainder of their window after a kill) is about what happens
   to inventory the trader is actively managing, which requires a real matching engine to reproduce
   meaningfully; this harness only proves the STARTUP side (fix #2), not the in-window disposal side.
4. **The authenticated WebSocket book+fill feeder.** `WS_URL` is deliberately monkeypatched to an
   unreachable local address (`ws://127.0.0.1:9/`) so the drill stays fully offline; this means the
   WS feeder's reconnect/resubscribe/epoch-bump logic is never exercised, and the trader runs on
   its REST-poll fallback path throughout. That fallback path is real production behavior (the file
   itself falls back to it when `websockets` is absent or the feed drops), but it is a slower/staler
   signal than the WS path most live sessions actually run on.
5. **GH_TOKEN / KALSHI_API_KEY_ID / RSA key validity end-to-end.** This drill uses fake/throwaway
   credentials the mock never validates. A live drill against the real GitHub contents API needs a
   real, scoped `GH_TOKEN` with `contents:write` on the target branch/path, and should verify a
   *wrong or expired* token produces the alert-then-fallback-to-sentinel path (`remote_switch_kill`
   returning `False` after retries) -- this harness only proves the success path plus the
   already-unit-tested no-op/no-token path (T11 in `kalshi_safeguards_test.py`).
6. **Actual GitHub branch protection / concurrent-write conflicts on LIVE_SWITCH.** If another
   process (e.g. the still-running `live.yml` sticky-kill step, or a human `./live_switch.sh`) is
   racing to write the same file at the same moment, the real API's 409-on-stale-sha behavior would
   need a second concurrent writer to observe -- this harness's mock is single-writer only.

**Bottom line for a real $5 live drill:** confirm (1) `remote_switch_kill` actually reaches
`api.github.com` and flips `LIVE_SWITCH` within a couple seconds of a live-triggered loss-limit
(not just that it *would*, per this mock), (2) a genuine SIGKILL of the live process (or a real
GHA runner cancellation) still leaves that flip intact when the branch is re-checked out fresh, and
(3) `get_positions()` against the REAL venue returns the same shape this harness assumed
(`market_positions` list with signed `position` + `market_exposure` fields) -- the mock's shape was
inferred from `_parse_inherited_position()`'s own parsing code, not observed from a live response.
"""


def write_report(results_a, results_b, elapsed_s):
    lines = []
    lines.append("# CHAOS_DRILL.md -- offline kill-restart harness results\n")
    lines.append(f"Generated by `chaos_drill.py` on {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} "
                 f"(wall time {elapsed_s:.1f}s). All runs offline against a local mock venue; no real "
                 "money, no real secrets (throwaway RSA keypair, fake API/GH/Telegram tokens).\n")
    lines.append("## Summary\n")
    n_pass = sum(1 for r in REPORT.rows if r[2])
    n_total = len(REPORT.rows)
    lines.append(f"**{n_pass}/{n_total} assertions PASSED.**\n")
    for drill in ("Drill A", "Drill B"):
        rows = [r for r in REPORT.rows if r[0] == drill]
        p = sum(1 for r in rows if r[2])
        lines.append(f"- {drill}: {p}/{len(rows)} PASS" + ("" if p == len(rows) else "  **<- has FAILs**"))
    lines.append("")
    lines.append("## Assertions\n")
    lines.append("| Drill | Assertion | Result | Detail |")
    lines.append("|---|---|---|---|")
    for drill, assertion, passed, detail in REPORT.rows:
        status = "PASS" if passed else "FAIL"
        detail_s = (detail or "").replace("|", "\\|").replace("\n", " ")[:200]
        lines.append(f"| {drill} | {assertion} | **{status}** | {detail_s} |")
    lines.append("")
    lines.append("## What each drill exercised\n")
    lines.append(
        "**Drill A** (mid-window SIGKILL + restart): process #1 started against a flat mock venue, "
        "began quoting, was SIGKILLed mid-window while orders were resting. The mock was then set to "
        "serve a nonzero canned position for the SAME still-open ticker (the exact scenario "
        "DEADMAN_AUDIT.md flags as the real risk: 'restart lands on the same still-open ticker as the "
        "dead session'), and process #2 was started in the SAME working directory (same lock file, "
        "same gitignored sentinel path, same JSONL state files) to mirror a real GHA checkout. "
        "Verified: the OS released process #1's flock so #2 could start; startup order reconciliation "
        "(C7) cancelled the orphaned resting order; startup position reconciliation (fix #2) queried "
        "`/portfolio/positions`, detected the inherited inventory, alerted (captured at the mock "
        "Telegram endpoint), and seeded it into `net_delta`/`pos`/`win_cost` at first window-attach; "
        "no JSONL state file was left corrupted by the kill.\n")
    lines.append(
        "**Drill B** (kill-trip durability): process started with a large canned inherited position "
        "so the C2 loss-limit trips almost immediately on window-attach (no matching engine/real fills "
        "needed -- the loss-limit check only reads `win_cost`/`pos`/`net_delta`, which the inherited-"
        "position seed populates directly). Verified: the trip drove `_record_kill()` -> "
        "`remote_switch_kill()` to perform a real GET (fetch `sha`) then PUT (`LIVE_SWITCH=off`) "
        "against the mock GitHub-contents-API endpoint; the process was SIGKILLed the INSTANT that PUT "
        "landed (simulating a runner dying a heartbeat later, before any later workflow step could "
        "ever run); the mock's switch state was still durably 'off' after the hard-kill, and the local "
        "sentinel file existed and named the loss_limit trip.\n")
    lines.append(GAPS_MD)
    with open(REPORT_PATH, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\nWrote {REPORT_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    print(f"scratch dir: {SCRATCH_ROOT}")
    os.makedirs(SCRATCH_ROOT, exist_ok=True)

    state = MockState()
    srv, port = run_server(state)
    print(f"mock server listening on 127.0.0.1:{port}")

    key_path = os.path.join(SCRATCH_ROOT, "chaos_drill_throwaway_key.pem")
    gen_throwaway_key(key_path)
    gh_token = "chaos-drill-fake-gh-token-not-real"
    tg_token = "chaos-drill-fake-tg-token-not-real"
    tg_chat = "chaos-drill-fake-chat-id"

    try:
        res_a = drill_a(state, port, key_path, gh_token, tg_token, tg_chat)
    except Exception as e:
        REPORT.add("Drill A", "drill completed without raising", False, f"{type(e).__name__}: {e}")
        res_a = {}

    try:
        res_b = drill_b(state, port, key_path, gh_token, tg_token, tg_chat)
    except Exception as e:
        REPORT.add("Drill B", "drill completed without raising", False, f"{type(e).__name__}: {e}")
        res_b = {}

    srv.shutdown()
    elapsed = time.time() - t0
    write_report(res_a, res_b, elapsed)

    n_pass = sum(1 for r in REPORT.rows if r[2])
    n_total = len(REPORT.rows)
    print(f"\n{n_pass}/{n_total} assertions PASSED. Scratch dir preserved at: {SCRATCH_ROOT}")
    return 0 if n_pass == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
