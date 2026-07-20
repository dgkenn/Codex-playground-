#!/usr/bin/env python3
"""synoptic_feed.py -- Synoptic Data real-time feed adapter for the K-WX runner (Tier-2 item 5).

Plugs into kwx_runner via set_feed(): exposes running_extreme(station, lst_date, offset, kind) using
Synoptic's 1-min HF-ASOS temperatures (the fast DETECTION feed the 3.3-min-half-life edge needs), plus a
precip method for the rain sleeve and a latency probe to MEASURE the feed's real lag on our stations.

Token: SYNOPTIC_TOKEN env var first (so a GitHub Actions secret can feed it without writing files), then
the gitignored .synoptic_token file (one line). NEVER echo/commit/log the token value. Get one from the
14-day trial at synopticdata.com. Batch ALL stations into ONE request (Synoptic returns many stids per
call), so the trial's "1 simultaneous response" concurrency limit does NOT bind -- one poll, all 20 stations.

API (v2): GET https://api.synopticdata.com/v2/stations/timeseries
  ?stid=KDEN,KMIA,...&vars=air_temp&recent=120&obtimezone=utc&units=temp|F&token=...
Returns STATION[].OBSERVATIONS.{date_time[], air_temp_set_1[]}. Precip: vars=precip_accum_one_hour etc.
The parser is SHAPE-TOLERANT because the exact var names/HF-network flags may differ on the live trial API:
it accepts the plausible air-temp spellings (air_temp / air_temperature / temp[erature] x _set_N / _value_N,
including derived '_set_1d'), tolerates a missing/renamed key or STID on ONE station without dropping the
whole batch, and retries bounded on 5xx/timeouts (mirrors aviationweather_metar's pattern). The probe prints
what actually comes back so you can confirm resolution + latency on day 1 of the trial.

Usage:
  python synoptic_feed.py probe KDEN,KMIA,KLAS   # MEASURE latency + resolution (the key trial test)
  python synoptic_feed.py selftest               # offline: parser vs canned response-shape variants
"""
import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error, ssl, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
TOKEN_PATH = os.path.join(HERE, ".synoptic_token")
API = "https://api.synopticdata.com/v2/stations/timeseries"
_ALIAS = {"NYC": "KNYC"}   # Central Park


def have_token():
    """True if a Synoptic token is available (env var OR file) -- the cheap opt-in check callers gate on."""
    return bool(os.environ.get("SYNOPTIC_TOKEN", "").strip()) or os.path.exists(TOKEN_PATH)


_minted = {}   # apikey-credential -> minted token, cached in-process (legs are short-lived)


def _token():
    # ENV first: a GitHub Actions secret can feed the token without ever writing a file to the (public)
    # repo checkout. File second: the original gitignored local path. NEVER log/echo the value.
    tok = os.environ.get("SYNOPTIC_TOKEN", "").strip()
    if not tok and os.path.exists(TOKEN_PATH):
        tok = open(TOKEN_PATH).read().strip()
    if not tok:
        raise RuntimeError("no SYNOPTIC_TOKEN env var and no .synoptic_token file (trial token; both gitignored)")
    return _minted.get(tok, tok)


def _try_mint_from_apikey(cred):
    """Synoptic has two credential kinds: an account APIKEY that mints TOKENs via /v2/auth, and the
    tokens the data API actually accepts. If the operator pastes the APIKEY as SYNOPTIC_TOKEN (the
    natural mistake -- the signup page shows the key first), data calls 401. On that 401 the caller
    tries this exchange once: success caches apikey->token in-process and the call is retried; failure
    returns False and the original 401 propagates. Never logs either value."""
    if cred in _minted:
        return False               # already exchanged this credential; a 401 now is a real auth failure
    try:
        q = urllib.parse.urlencode({"apikey": cred})
        req = urllib.request.Request(f"https://api.synopticdata.com/v2/auth?{q}",
                                     headers={"Accept": "application/json"})
        data = json.load(urllib.request.urlopen(req, timeout=15, context=_CTX))
        tok = (data or {}).get("TOKEN")
        if tok:
            _minted[cred] = tok.strip()
            return True
    except Exception:
        pass                        # sanitized: no re-raise, no logging -- credential must never leak
    return False


def _sid(station):
    s = _ALIAS.get(station, station)
    return s if (s.startswith("K") or len(s) != 3) else "K" + s


# Plausible air-temp variable spellings the live trial API might use (the doc comment above warned the
# exact names may need a tweak): base name x _set_N / _value_N suffix, incl. derived sets like _set_1d.
# Matched by stripping the suffix so e.g. dew_point_temperature is NOT mistaken for air temp.
_TEMP_NAMES = {"air_temp", "air_temperature", "temp", "temperature"}
_SERIES_SUFFIX = re.compile(r"_(?:set|value)_\d+[a-z]?$", re.I)


def _series_keys(obs):
    """Pick (time_key, value_key) from one station's OBSERVATIONS dict, tolerating renamed keys.
    Prefers an air-temp-spelled series; falls back to any suffixed series (covers the precip vars)."""
    tk = next((k for k in obs if "date_time" in k.lower()), None)
    cands = [k for k in obs if k != tk and isinstance(obs.get(k), (list, tuple))]
    temps = [k for k in cands if _SERIES_SUFFIX.sub("", k.lower()) in _TEMP_NAMES]
    vk = temps[0] if temps else next((k for k in cands if _SERIES_SUFFIX.search(k)), None)
    return tk, vk


def parse_timeseries_response(data):
    """SHAPE-TOLERANT parse of a Synoptic timeseries response -> {stid: [(utc_dt, value), ...]} ascending.

    Tolerance is PER-STATION: a station with a missing/renamed value key, missing STID, or malformed
    points contributes nothing (or its good points only) but NEVER drops the rest of the batch -- one
    weird station in the 20-city poll must not blind the runner to the other 19."""
    out = {}
    for st in data.get("STATION", []) or []:
        try:
            if not isinstance(st, dict):
                continue
            stid = st.get("STID") or st.get("stid")
            obs = st.get("OBSERVATIONS") or st.get("observations") or {}
            if not stid or not isinstance(obs, dict) or not obs:
                continue
            tk, vk = _series_keys(obs)
            times = obs.get(tk, []) if tk else []
            vals = obs.get(vk, []) if vk else []
            series = []
            for t, v in zip(times, vals):
                if v is None:
                    continue
                try:
                    when = dt.datetime.fromisoformat(str(t).replace("Z", "+00:00"))
                    series.append((when, float(v)))
                except (ValueError, TypeError):
                    continue          # one malformed point never kills the station
            series.sort()
            out[stid] = series
        except Exception:
            continue                  # one malformed station never kills the batch
    return out


def fetch_timeseries(stations, var="air_temp", recent_min=120, units="temp|F", timeout=20):
    """One batched call -> {stid: [(utc_dt, value), ...]} ascending. `stations` = list of ids.
    Bounded retries with backoff on 5xx/timeouts (mirrors aviationweather_metar; seen there: sporadic 502).
    Errors are re-raised SANITIZED so the token (in the query string) can never leak into logs."""
    stids = ",".join(_sid(s) for s in stations)

    def _req():
        q = urllib.parse.urlencode({"stid": stids, "vars": var, "recent": int(recent_min),
                                    "obtimezone": "utc", "units": units, "token": _token()})
        return urllib.request.Request(f"{API}?{q}", headers={"Accept": "application/json"})

    data, last_err = None, None
    for attempt in range(4):
        try:
            data = json.load(urllib.request.urlopen(_req(), timeout=timeout, context=_CTX))
            break
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 401 and _try_mint_from_apikey(_token()):
                continue              # credential was an APIKEY: token minted+cached, retry same attempt
            if e.code not in (500, 502, 503, 504):
                raise RuntimeError(f"synoptic API error: {last_err}") from None  # 4xx = not transient
            time.sleep(1.5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = type(e).__name__
            time.sleep(1.5 * (attempt + 1))
    if data is None:
        raise RuntimeError(f"synoptic fetch failed after retries ({last_err})")
    return parse_timeseries_response(data)


class SynopticFeed:
    """Drop-in for kwx_runner.set_feed(). 1-min air_temp running max/min over an LST day."""
    name = "synoptic-hf"

    def __init__(self):
        self._cache = {}

    def running_extreme(self, station, lst_date, offset, kind):
        d = dt.date.fromisoformat(lst_date) if isinstance(lst_date, str) else lst_date
        start_local = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
        start_utc = start_local - dt.timedelta(hours=offset)
        end_utc = start_utc + dt.timedelta(hours=24)
        series = fetch_timeseries([station]).get(_sid(station), [])
        obs = [(t, f) for t, f in series if start_utc <= t < end_utc]
        if not obs:
            return None
        temps = [f for _, f in obs]
        return {"extreme_f": (max(temps) if kind == "max" else min(temps)),
                "obs": [(t.isoformat(), round(f, 2)) for t, f in obs]}


def probe(stations):
    """The KEY trial test: measure real latency + resolution. Prints, per station, newest-obs age and the
    median spacing between obs (=resolution). This is what tells you if Synoptic hits the 2-5 min band."""
    now = None  # Date.now unavailable in some sandboxes; use the response's own newest ts as reference
    ts_data = fetch_timeseries(stations, recent_min=90)
    print(f"{'station':8}{'n_obs':>6}{'resolution(min)':>16}{'newest_utc':>22}{'age_vs_prev_min':>16}")
    for s in stations:
        series = ts_data.get(_sid(s), [])
        if not series:
            print(f"{s:8}{'0':>6}   NO DATA")
            continue
        spacings = [ (series[i][0]-series[i-1][0]).total_seconds()/60 for i in range(1, len(series)) ]
        res = sorted(spacings)[len(spacings)//2] if spacings else float('nan')
        newest = series[-1][0]
        print(f"{s:8}{len(series):>6}{res:>16.1f}{newest.isoformat():>22}")
    print("\n-> resolution ~1.0 min = HF-ASOS working. Compare newest_utc to the ACTUAL current UTC time")
    print("   (date -u) to get true latency; that decides which act@k band we land in (need <=5 min).")


def selftest():
    """OFFLINE unit tests for the shape-tolerant parser: canned response variants the live trial API might
    serve (the header's 'var names may need one tweak' risk). No network, no token. Exit 0 iff all pass."""
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    ts = ["2026-07-19T20:00:00Z", "2026-07-19T20:01:00Z"]
    # 1) canonical v2 shape: air_temp_set_1
    r = parse_timeseries_response({"STATION": [
        {"STID": "KDEN", "OBSERVATIONS": {"date_time": ts, "air_temp_set_1": [95.0, 96.1]}}]})
    check("canonical air_temp_set_1 parses", r.get("KDEN") and [v for _, v in r["KDEN"]] == [95.0, 96.1])
    # 2) alternate spelling: air_temperature_value_1 (plausible live-API rename)
    r = parse_timeseries_response({"STATION": [
        {"STID": "KMIA", "OBSERVATIONS": {"date_time": ts, "air_temperature_value_1": [88.0, 88.5]}}]})
    check("alternate air_temperature_value_1 parses", r.get("KMIA") and r["KMIA"][-1][1] == 88.5)
    # 3) derived set (air_temp_set_1d) + dew point present -- must pick air temp, not dew point
    r = parse_timeseries_response({"STATION": [{"STID": "KLAS", "OBSERVATIONS": {
        "date_time": ts, "dew_point_temperature_set_1d": [60.0, 60.0], "air_temp_set_1d": [104.0, 105.0]}}]})
    check("derived _set_1d picked over dew_point", r.get("KLAS") and r["KLAS"][-1][1] == 105.0)
    # 4) per-station tolerance: one broken station (no OBSERVATIONS / no STID) never drops the batch
    r = parse_timeseries_response({"STATION": [
        {"STID": "KBAD"},                                  # missing OBSERVATIONS entirely
        {"OBSERVATIONS": {"date_time": ts, "air_temp_set_1": [70.0, 71.0]}},   # missing STID
        {"STID": "KOK", "OBSERVATIONS": {"date_time": ts, "air_temp_set_1": [90.0, 91.0]}}]})
    check("broken stations skipped, good station kept", list(r) == ["KOK"] and len(r["KOK"]) == 2)
    # 5) malformed points (None value, junk timestamp) skipped without killing the station
    r = parse_timeseries_response({"STATION": [{"STID": "KSEA", "OBSERVATIONS": {
        "date_time": ["garbage", ts[1]], "air_temp_set_1": [None, 72.0]}}]})
    check("malformed points skipped, good point kept", r.get("KSEA") == [
        (dt.datetime(2026, 7, 19, 20, 1, tzinfo=dt.timezone.utc), 72.0)])
    # 6) non-temp var (precip) still found via the suffix fallback
    r = parse_timeseries_response({"STATION": [{"STID": "KHOU", "OBSERVATIONS": {
        "date_time": ts, "precip_accum_one_hour_set_1": [0.0, 0.1]}}]})
    check("precip var found via suffix fallback", r.get("KHOU") and r["KHOU"][-1][1] == 0.1)
    # 7) token resolution order: env var must win over (absent) file, and have_token() must see it
    old = os.environ.get("SYNOPTIC_TOKEN")
    try:
        os.environ["SYNOPTIC_TOKEN"] = "unit-test-token"
        check("env token accepted first", _token() == "unit-test-token" and have_token())
    finally:
        (os.environ.pop("SYNOPTIC_TOKEN", None) if old is None
         else os.environ.__setitem__("SYNOPTIC_TOKEN", old))
    print(("ALL PASS" if not fails else f"FAILURES: {fails}"))
    return 0 if not fails else 1


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    elif len(sys.argv) >= 3 and sys.argv[1] == "probe":
        probe(sys.argv[2].split(","))
    else:
        print("usage: synoptic_feed.py probe KDEN,KMIA,KLAS   (needs SYNOPTIC_TOKEN env or .synoptic_token)\n"
              "       synoptic_feed.py selftest               (offline parser tests)")
