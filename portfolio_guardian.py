"""portfolio_guardian.py -- PORTFOLIO-LEVEL risk rail (read-only judge + emergency-off switch).

WHY THIS EXISTS: kalshi_trader.py's safety rails are all PER-ASSET -- a $6 sticky loss-limit per
sleeve, sentinel `.kalshi_killed_<asset>15m` -- plus one global LIVE_SWITCH that only a human (or
a per-asset kill) flips. Crypto sleeves are correlated: a bad hour can trip several per-asset
limits without any single one of them seeing the whole picture -- $6 x 4 sleeves = $24, 48% of a
$50 bankroll, before anything says "stop everything." And nothing at all watches account balance
ACROSS DAYS. This script is that missing judge: an independent, READ-ONLY process (same
ground-truth auth as equity_snap.py, its daily-snapshot sibling) that looks at the account's own
balance/position history and, when it doesn't like what it sees, pulls the one global lever --
LIVE_SWITCH=off -- durably, via the exact GET-sha-then-PUT contents-API pattern kalshi_trader.py's
remote_switch_kill() already uses for the same purpose (reused here by import, with a
self-contained fallback if kalshi_trader ever fails to import -- same reason equity_snap.py has
one: this audit tool must never depend on the trader module staying importable).

RULES (the three constants below ARE the spec -- edit these, not the logic around them):
  DAILY_DD_FRAC  (a) balance down more than this fraction vs the most recent PRIOR-DAY snapshot
                 (the last row recorded on the most recent gha_data/equity_<date>.jsonl dated
                 strictly before today) -> CRITICAL.
  TOTAL_DD_FRAC  (b) balance down more than this fraction vs the highest balance_cents ever
                 recorded across ALL historical snapshot rows -> CRITICAL.
  EXPOSURE_FRAC  (c) current open-position notional (sum of |market_exposure| cents across open
                 positions, fetched fresh) exceeds this fraction of current balance -> WARN only.
                 A busy-but-healthy book can legitimately carry a lot of resting notional; this is
                 a "go look at it" signal, not a "stop trading" one, so it never flips the switch.

ON CRITICAL: flips LIVE_SWITCH=off durably (remote_switch_kill's GET-sha/PUT-off/retry pattern)
AND sends a Telegram alert stating exactly which rule(s) tripped, the numbers, and the re-arm
command (./live_switch.sh on). ON WARN (no CRITICAL): Telegram only, switch untouched.

READ-ONLY / NEVER-TRADES BY CONSTRUCTION: the only Kalshi calls here are GET /portfolio/balance
and GET /portfolio/positions -- the identical two endpoints equity_snap.py uses, same auth, no
order-placing code anywhere in this file. The ONLY write this file can ever issue anywhere is the
single contents-API PUT inside remote_switch_kill(), and that PUT can only ever encode the literal
byte string "off". This file must NEVER gain a code path that writes "on" -- re-arming is a
deliberate human action (./live_switch.sh on), never automatic.

SAFE NO-OP: if KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY_PATH (or the pem file itself) are absent,
prints "no secrets, skipping" and exits 0 -- identical fail-closed posture to equity_snap.py.

    python portfolio_guardian.py
"""
from __future__ import annotations

import base64
import glob
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Rule constants (documented above; this IS the spec)
# ---------------------------------------------------------------------------
DAILY_DD_FRAC = 0.15   # (a) CRITICAL: balance down >15% vs most recent prior-day snapshot
TOTAL_DD_FRAC = 0.30   # (b) CRITICAL: balance down >30% vs the highest balance ever recorded
EXPOSURE_FRAC = 0.50   # (c) WARN only: open notional >50% of current balance

DEFAULT_BRANCH = "claude/polymarket-bot-live-ready-vw7ut5"

# ---------------------------------------------------------------------------
# Auth: reuse kalshi_trader's signer/caller -- IDENTICAL pattern to equity_snap.py, including the
# fallback (only ever performs GET requests; see _api() docstring in the fallback).
# ---------------------------------------------------------------------------
try:
    from kalshi_trader import _api, _load_private_key  # noqa: F401  (READ-ONLY use: GET calls only)
except Exception:
    BASE = "https://api.elections.kalshi.com/trade-api/v2"

    def _load_private_key():
        path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
        if not path or not os.path.exists(path):
            return None
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        with open(path, "rb") as fh:
            return load_pem_private_key(fh.read(), password=None)

    def _sign(private_key, method: str, path: str) -> dict:
        """Kalshi RSA-PSS headers (mirrors kalshi_trader._sign)."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        ts = str(int(time.time() * 1000))
        msg = (ts + method.upper() + path).encode()
        sig = private_key.sign(msg, padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ), hashes.SHA256())
        return {
            "KALSHI-ACCESS-KEY": os.environ.get("KALSHI_API_KEY_ID", ""),
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "Content-Type": "application/json",
        }

    def _api(sess, private_key, method, path_suffix, body=None, params=None, timeout=8):
        """READ-ONLY fallback caller -- this file only ever invokes it with method='GET'."""
        if method != "GET":
            raise ValueError(f"portfolio_guardian fallback _api only supports GET (got {method!r})")
        url = BASE + path_suffix
        headers = _sign(private_key, method, "/trade-api/v2" + path_suffix)
        r = sess.get(url, headers=headers, params=params, timeout=timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None


def _telegram_send(msg: str) -> bool:
    """Fire-and-wait Telegram send; False (no-op, no exception) if env unset or the send fails."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": msg[:4000]}, timeout=8)
        return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Durable kill: reuse kalshi_trader.remote_switch_kill -- IDENTICAL pattern/signature, with a
# self-contained fallback (default alert_fn is the local _telegram_send above, not notify.py, so
# this file has zero hard dependency on notify.py's importability either).
# ---------------------------------------------------------------------------
try:
    from kalshi_trader import remote_switch_kill  # noqa: F401
except Exception:
    def remote_switch_kill(gh_token, remote_switch_url, reason, sess=None, retries=3,
                           backoff_s=1.5, alert_fn=None):
        """Fallback durable sticky-kill (mirrors kalshi_trader.remote_switch_kill exactly): GET the
        LIVE_SWITCH file's current sha via the GitHub contents API, then PUT content="off" using
        that sha. Clean no-op (False, zero network calls) without gh_token/remote_switch_url, or
        if the url isn't an api.github.com contents URL. On total failure after `retries`
        attempts, fires alert_fn with a message flagging the switch may still be on."""
        sess = sess or requests
        alert_fn = alert_fn or _telegram_send
        if not (gh_token and remote_switch_url and "api.github.com" in remote_switch_url):
            return False
        parsed = urllib.parse.urlsplit(remote_switch_url)
        branch = (urllib.parse.parse_qs(parsed.query).get("ref") or [None])[0]
        put_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        hdrs = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
        last_err = "unknown error"
        for attempt in range(retries):
            try:
                g = sess.get(remote_switch_url, headers=hdrs, timeout=8)
                if g.status_code != 200:
                    last_err = f"GET {g.status_code}"
                else:
                    sha = (g.json() or {}).get("sha")
                    if not sha:
                        last_err = "GET 200 but response had no sha"
                    else:
                        body = {
                            "message": f"PORTFOLIO GUARDIAN sticky kill: {reason}"[:200],
                            "content": base64.b64encode(b"off").decode("ascii"),
                            "sha": sha,
                        }
                        if branch:
                            body["branch"] = branch
                        p = sess.put(put_url, headers=hdrs, json=body, timeout=8)
                        if 200 <= p.status_code < 300:
                            return True
                        last_err = f"PUT {p.status_code}: {str(getattr(p, 'text', ''))[:120]}"
            except Exception as e:
                last_err = f"{type(e).__name__}: {str(e)[:100]}"
            if attempt < retries - 1:
                time.sleep(backoff_s * (2 ** attempt))
        try:
            alert_fn(f"⚠️ [portfolio_guardian] switch-off PUT FAILED after {retries} "
                     f"attempts ({last_err}) -- LIVE_SWITCH may still be 'on'. Flip it manually: "
                     "./live_switch.sh off")
        except Exception:
            pass
        return False


def _have_secrets() -> bool:
    if not os.environ.get("KALSHI_API_KEY_ID"):
        return False
    pem_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    return bool(pem_path) and os.path.exists(pem_path)


def _rows_by_date(out_dir: str = "gha_data") -> dict:
    """{date_str: [row, ...]} for every gha_data/equity_<date>.jsonl file, rows in file order
    (oldest -> newest within a day). The equity-snapshot cron now runs several times a day, so a
    single date file can hold multiple rows -- callers that want "the balance as of date X" must
    take the LAST row for that date, not assume one row per file."""
    out = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "equity_*.jsonl"))):
        base = os.path.basename(path)
        if not (base.startswith("equity_") and base.endswith(".jsonl")):
            continue
        date = base[len("equity_"):-len(".jsonl")]
        rows = []
        try:
            with open(path) as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        rows.append(json.loads(ln))
                    except Exception:
                        continue
        except Exception:
            continue
        if rows:
            out[date] = rows
    return out


def _prior_day_baseline(rows_by_date: dict, today: str):
    """The LAST row of the most recent date strictly before `today`. None if no prior day has any
    recorded snapshot yet (e.g. day 1 of the guardian's existence) -- DAILY_DD is then skipped."""
    prior_dates = sorted(d for d in rows_by_date if d < today)
    if not prior_dates:
        return None
    return rows_by_date[prior_dates[-1]][-1]


def _max_balance_ever(rows_by_date: dict):
    """Highest balance_cents seen across every historical row (all dates, all times of day). None
    if there is no history yet -- TOTAL_DD is then skipped."""
    best = None
    for rows in rows_by_date.values():
        for r in rows:
            try:
                b = int(r.get("balance_cents", 0) or 0)
            except Exception:
                continue
            if best is None or b > best:
                best = b
    return best


def _notional_cents(open_positions) -> int:
    """Sum of |market_exposure| cents across open positions -- the same field kalshi_trader.py
    already reads as the position's cost basis (`_infer_win_cost_from_position`)."""
    total = 0
    for p in open_positions:
        try:
            total += abs(int(p.get("market_exposure") or 0))
        except Exception:
            continue
    return total


def _evaluate_rules(balance_cents: int, notional_cents: int, rows_by_date: dict, today: str):
    """Pure rule engine, no I/O -- easy to unit-drive with synthetic rows_by_date dicts. Returns
    (criticals: list[str], warns: list[str])."""
    criticals = []
    warns = []

    if balance_cents <= 0:
        criticals.append(f"balance is ${balance_cents / 100:.2f} (<= $0)")

    prior = _prior_day_baseline(rows_by_date, today)
    if prior is not None:
        try:
            prior_bal = int(prior.get("balance_cents", 0) or 0)
        except Exception:
            prior_bal = 0
        if prior_bal > 0:
            dd = (prior_bal - balance_cents) / prior_bal
            if dd > DAILY_DD_FRAC:
                criticals.append(
                    f"DAILY_DD: balance ${balance_cents / 100:.2f} is down {dd * 100:.1f}% vs "
                    f"prior-day snapshot ${prior_bal / 100:.2f} (limit {DAILY_DD_FRAC * 100:.0f}%)")

    max_ever = _max_balance_ever(rows_by_date)
    if max_ever and max_ever > 0:
        dd_total = (max_ever - balance_cents) / max_ever
        if dd_total > TOTAL_DD_FRAC:
            criticals.append(
                f"TOTAL_DD: balance ${balance_cents / 100:.2f} is down {dd_total * 100:.1f}% vs "
                f"the highest balance ever recorded ${max_ever / 100:.2f} "
                f"(limit {TOTAL_DD_FRAC * 100:.0f}%)")

    if balance_cents > 0:
        exp_frac = notional_cents / balance_cents
        if exp_frac > EXPOSURE_FRAC:
            warns.append(
                f"EXPOSURE: open notional ${notional_cents / 100:.2f} is {exp_frac * 100:.1f}% of "
                f"balance ${balance_cents / 100:.2f} (limit {EXPOSURE_FRAC * 100:.0f}%)")

    return criticals, warns


def _remote_switch_url() -> str:
    """REMOTE_SWITCH_URL env if set (matches kalshi_trader's --remote-switch-url convention);
    else construct it from GITHUB_REPOSITORY + BRANCH -- the same two env vars the workflow
    already exports -- exactly like live.yml does:
    https://api.github.com/repos/<owner>/<repo>/contents/LIVE_SWITCH?ref=<branch>"""
    url = os.environ.get("REMOTE_SWITCH_URL", "")
    if url:
        return url
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        return ""
    branch = os.environ.get("BRANCH", DEFAULT_BRANCH)
    return f"https://api.github.com/repos/{repo}/contents/LIVE_SWITCH?ref={branch}"


def main() -> int:
    if not _have_secrets():
        print("no secrets, skipping")
        return 0

    try:
        priv = _load_private_key()
    except SystemExit as e:
        print(f"no secrets, skipping ({e})")
        return 0
    if priv is None:
        print("no secrets, skipping")
        return 0

    sess = requests.Session()

    sc_b, bal = _api(sess, priv, "GET", "/portfolio/balance")
    if sc_b < 200 or sc_b >= 300 or not isinstance(bal, dict):
        print(f"[portfolio_guardian] balance fetch FAILED (status {sc_b}); skipping this check")
        return 1

    sc_p, pos = _api(sess, priv, "GET", "/portfolio/positions", params={"limit": 1000})
    if sc_p < 200 or sc_p >= 300 or not isinstance(pos, dict):
        print(f"[portfolio_guardian] positions fetch FAILED (status {sc_p}); skipping this check")
        return 1

    balance_cents = int(bal.get("balance", 0) or 0)
    all_positions = pos.get("market_positions") or []
    open_positions = [p for p in all_positions if int(p.get("position", 0) or 0) != 0]
    notional_cents = _notional_cents(open_positions)

    rows_by_date = _rows_by_date("gha_data")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    criticals, warns = _evaluate_rules(balance_cents, notional_cents, rows_by_date, today)

    if criticals:
        reason = "; ".join(criticals)
        gh_tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        url = _remote_switch_url()
        flipped = False
        try:
            flipped = remote_switch_kill(gh_tok, url, f"portfolio_guardian: {reason}", sess=sess)
        except Exception as e:
            print(f"[portfolio_guardian] remote_switch_kill raised unexpectedly: "
                  f"{type(e).__name__}: {e}")
        status = ("LIVE_SWITCH flipped OFF (durable commit confirmed)" if flipped else
                   "LIVE_SWITCH flip NOT confirmed (no GH_TOKEN/url configured, or the PUT "
                   "failed -- verify/flip manually with ./live_switch.sh off)")
        msg = ("\U0001F6A8 PORTFOLIO GUARDIAN -- CRITICAL\n"
               f"{reason}\n"
               f"{status}.\n"
               "Re-arm ONLY after investigating: ./live_switch.sh on")
        _telegram_send(msg)
        print(f"[portfolio_guardian] CRITICAL: {reason} | {status}")
    elif warns:
        reason = "; ".join(warns)
        msg = f"⚠️ PORTFOLIO GUARDIAN -- WARN\n{reason}"
        _telegram_send(msg)
        print(f"[portfolio_guardian] WARN: {reason}")
    else:
        print(f"[portfolio_guardian] OK balance=${balance_cents / 100:.2f} "
              f"notional=${notional_cents / 100:.2f} n_open={len(open_positions)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
