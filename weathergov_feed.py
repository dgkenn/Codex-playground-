#!/usr/bin/env python3
"""weathergov_feed.py -- FREE real-time obs feed for the K-WX runner (api.weather.gov, no signup).

The zero-cost substitute for the paid Synoptic HF-ASOS feed. Measured: 5-MINUTE resolution at ~15-20 min
latency for most of our 20 stations (some fall back to hourly). That is too slow to catch the FAST fires
(3.3-min gap half-life), but it still catches the ~6-7 SLOWER-repricing fires/day -- and those still pay
~+0.15/ct (per Track A's latency table). On a SMALL bankroll you are capital-limited, not fire-limited
(catching all 26 fires/day at 0-min would need ~$62/day of deployment, more than a $50 account), so ~6-7
fires/day is plenty -> the free feed yields essentially the same ~5%/day at $50 as the paid feed. Upgrade
to synoptic_feed.SynopticFeed only when scaling past a few hundred dollars, where extra throughput pays.

Same interface as MetarFeed/SynopticFeed: running_extreme(station, lst_date, offset, kind).
api.weather.gov requires a descriptive User-Agent with contact info (set WX_CONTACT env or edit below).
Temperatures are Celsius in the API -> converted to F. NYC -> KNYC (Central Park).

Usage:
  python weathergov_feed.py KMIA 2026-07-18 -5     # running max/min for an LST day (degF)
"""
import urllib.request, json, ssl, os, sys, datetime as dt

_CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else None
_UA = f"kwx-weather-nowcast ({os.environ.get('WX_CONTACT', 'research@example.com')})"
_ALIAS = {"NYC": "KNYC"}


def _sid(station):
    s = _ALIAS.get(station, station)
    return s if (s.startswith("K") or len(s) != 3) else "K" + s


def _c_to_f(c):
    return c * 9.0 / 5.0 + 32.0


def fetch_obs(station, start_utc, end_utc, timeout=25):
    """Return [(utc_dt, temp_f), ...] ascending for [start,end). Uses start/end query (ISO8601)."""
    sid = _sid(station)
    q = f"start={start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    url = f"https://api.weather.gov/stations/{sid}/observations?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/geo+json"})
    data = json.load(urllib.request.urlopen(req, timeout=timeout, context=_CTX))
    out = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        t = p.get("timestamp")
        tv = (p.get("temperature") or {}).get("value")
        if t is None or tv is None:
            continue
        try:
            when = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
        except Exception:
            continue
        out.append((when, _c_to_f(float(tv))))
    out.sort()
    return out


class WeatherGovFeed:
    """Drop-in for kwx_runner.set_feed(). FREE 5-min api.weather.gov obs -> LST-day running max/min."""
    name = "weathergov-free"

    def running_extreme(self, station, lst_date, offset, kind):
        d = dt.date.fromisoformat(lst_date) if isinstance(lst_date, str) else lst_date
        start_local = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
        start_utc = start_local - dt.timedelta(hours=offset)
        end_utc = start_utc + dt.timedelta(hours=24)
        obs = fetch_obs(station, start_utc, end_utc)
        if not obs:
            return None
        temps = [f for _, f in obs]
        return {"extreme_f": (max(temps) if kind == "max" else min(temps)),
                "obs": [(t.isoformat(), round(f, 2)) for t, f in obs]}


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        st, date_s, off = sys.argv[1], sys.argv[2], float(sys.argv[3])
        f = WeatherGovFeed()
        for kind in ("max", "min"):
            r = f.running_extreme(st, date_s, off, kind)
            if r:
                print(f"{st} {date_s} LST running {kind}: {r['extreme_f']:.1f}F over {r['n_obs'] if 'n_obs' in r else len(r['obs'])} obs")
            else:
                print(f"{st} {date_s}: no obs")
    else:
        print("usage: weathergov_feed.py KMIA 2026-07-18 -5")
