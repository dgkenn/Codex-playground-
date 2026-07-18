#!/usr/bin/env python3
"""kalshi_exec.py -- Kalshi order-execution client for the K-WX weather-nowcast bot.

SAFETY POSTURE (non-negotiable): PROPOSE-ONLY by DEFAULT. This module SIMULATES fills unless
BOTH of these are true:
  1. a credentials file exists at .kalshi_creds  (gitignored; you create it -- see below), AND
  2. the environment variable KWX_LIVE == "1"     (an explicit, deliberate opt-in).
If either is missing, every order is a DRY-RUN: it is logged and a simulated fill is returned, but
NO request is ever sent to Kalshi. There is no code path that places a live order without both gates.
This matches the program charter: no live capital without explicit human authorization.

Live auth (only when you deliberately enable it) uses Kalshi's RSA-signed scheme: an access-key id +
an RSA private key, signing `timestamp(ms) + METHOD + path` with RSA-PSS-SHA256, sent as headers
KALSHI-ACCESS-KEY / KALSHI-ACCESS-TIMESTAMP / KALSHI-ACCESS-SIGNATURE. Create .kalshi_creds as JSON:
    {"access_key_id": "<your-key-id>", "private_key_pem": "-----BEGIN RSA PRIVATE KEY-----\\n..."}
(or {"private_key_path": "/abs/path/to/key.pem"}). The file is gitignored. RSA signing needs
`cryptography` (pip install cryptography) -- only imported on the live path, so dry-run has no deps.

Usage (all dry-run unless the two gates are set):
    from kalshi_exec import KalshiExec
    ex = KalshiExec()                      # DRY_RUN unless gated live
    r = ex.buy_yes("KXHIGHNY-26JUL17-T90", count=10, max_price_cents=95)
    print(r)   # {'status':'DRY_RUN'|'live', 'filled': n, 'avg_price': ..., ...}
"""
import json, os, time, base64, urllib.request, urllib.error, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
KBASE = "https://api.elections.kalshi.com/trade-api/v2"
CREDS_PATH = os.path.join(HERE, ".kalshi_creds")


class KalshiExec:
    def __init__(self, base=KBASE, log_path=os.path.join(HERE, "kwx_exec_log.jsonl")):
        self.base = base
        self.log_path = log_path
        self._priv = None
        self._key_id = None
        # LIVE requires BOTH gates. Absent either -> permanently dry-run for this instance.
        self.live = (os.environ.get("KWX_LIVE") == "1") and os.path.exists(CREDS_PATH)
        if self.live:
            self._load_creds()  # may flip self.live back to False if creds unusable

    # ---- credential loading (live path only) ----
    def _load_creds(self):
        try:
            creds = json.load(open(CREDS_PATH))
            self._key_id = creds["access_key_id"]
            pem = creds.get("private_key_pem")
            if not pem and creds.get("private_key_path"):
                pem = open(creds["private_key_path"]).read()
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            self._priv = load_pem_private_key(pem.encode() if isinstance(pem, str) else pem, password=None)
        except Exception as e:
            # Any failure -> stay in dry-run rather than risk a malformed live attempt.
            print(f"[kalshi_exec] creds load failed ({e}); staying DRY_RUN")
            self.live = False

    def _sign(self, ts_ms, method, path):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        msg = f"{ts_ms}{method}{path}".encode()
        # Kalshi's scheme: RSA-PSS, MGF1-SHA256, salt_length = digest length (matches Kalshi's SDK example).
        sig = self._priv.sign(
            msg,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(sig).decode()

    def _headers(self, method, path):
        ts = str(int(time.time() * 1000))
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self._key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": self._sign(ts, method, path),
        }

    def _log(self, rec):
        rec = {**rec, "ts": int(time.time() * 1000), "live": self.live}
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")

    # ---- public: place a YES buy (taker, immediate-or-cancel at a price cap) ----
    def buy_yes(self, ticker, count, max_price_cents, dry_fill_price=None):
        """Buy `count` YES contracts at up to `max_price_cents`. DRY-RUN unless gated live.

        dry_fill_price (cents) lets a simulator/backtest inject the price it believes fillable; if
        None, the dry-run assumes a fill at max_price_cents (conservative)."""
        order = {
            "ticker": ticker, "action": "buy", "side": "yes",
            "count": int(count), "type": "limit", "yes_price": int(max_price_cents),
            "time_in_force": "immediate_or_cancel",
        }
        if not self.live:
            fill = int(dry_fill_price if dry_fill_price is not None else max_price_cents)
            r = {"status": "DRY_RUN", "ticker": ticker, "requested": count,
                 "filled": int(count), "avg_price_cents": fill, "order": order}
            self._log(r)
            return r
        # ---- live path (only reached when KWX_LIVE=1 AND creds present) ----
        path = "/trade-api/v2/portfolio/orders"
        body = json.dumps(order).encode()
        req = urllib.request.Request(self.base.replace("/trade-api/v2", "") + path,
                                     data=body, method="POST",
                                     headers=self._headers("POST", path))
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=10, context=_CTX))
            r = {"status": "live", "ticker": ticker, "requested": count, "response": resp}
        except urllib.error.HTTPError as e:
            r = {"status": "live_error", "ticker": ticker, "code": e.code, "body": e.read().decode()[:300]}
        self._log(r)
        return r

    def buy_no(self, ticker, count, max_price_cents, dry_fill_price=None):
        """Buy `count` NO contracts (for the 'locked NO' rungs). Mirror of buy_yes."""
        order = {
            "ticker": ticker, "action": "buy", "side": "no",
            "count": int(count), "type": "limit", "no_price": int(max_price_cents),
            "time_in_force": "immediate_or_cancel",
        }
        if not self.live:
            fill = int(dry_fill_price if dry_fill_price is not None else max_price_cents)
            r = {"status": "DRY_RUN", "ticker": ticker, "side": "no", "requested": count,
                 "filled": int(count), "avg_price_cents": fill, "order": order}
            self._log(r)
            return r
        path = "/trade-api/v2/portfolio/orders"
        body = json.dumps(order).encode()
        req = urllib.request.Request(self.base.replace("/trade-api/v2", "") + path,
                                     data=body, method="POST", headers=self._headers("POST", path))
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=10, context=_CTX))
            r = {"status": "live", "ticker": ticker, "side": "no", "requested": count, "response": resp}
        except urllib.error.HTTPError as e:
            r = {"status": "live_error", "ticker": ticker, "code": e.code, "body": e.read().decode()[:300]}
        self._log(r)
        return r


if __name__ == "__main__":
    ex = KalshiExec()
    print("LIVE ENABLED:", ex.live, "(needs KWX_LIVE=1 AND .kalshi_creds)")
    print("dry-run demo:", ex.buy_yes("KXHIGHNY-26JUL17-T90", count=10, max_price_cents=95, dry_fill_price=88))
