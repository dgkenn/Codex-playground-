#!/usr/bin/env python3
"""Forward CLV / calibration harness for Kalshi weather vs NBM.

WHY: A single point-in-time snapshot cannot prove edge -- when Kalshi disagrees with NBM
we don't know who is right. We need to (a) log Kalshi book + NBM fair value at fixed times,
(b) record the NWS CLI settlement, (c) measure calibration of NBM-implied probs and whether
trading the deviation beats close (CLV) and beats settlement (realized PnL net of fee+spread).

Run on a schedule (e.g. cron every 1-2h). Each run appends one row per (event,bracket):
  ts, city, station, event, bracket, lo, hi, nbm_high, nbm_sigma, nbm_p,
  k_yes_bid, k_yes_ask, k_mid, depth_bid, depth_ask
After settlement, a second pass joins the NWS CLI actual high and computes:
  - Brier / log-loss of nbm_p vs outcome  (is the model calibrated?)
  - PnL of a rule: BUY bracket when nbm_p - ask > THRESH (clears fee), settle at 0/100
  - CLV: entry mid vs final pre-settlement mid

DATA NEEDED for a verdict: >= 150-300 settled (event,bracket) buy-signals across >= 30-45
trading days and >= 6 cities, to estimate net edge with a tight enough CI. Tail brackets are
rarer signals, so collecting tail-specific stats needs the longer end of that range.

Fee model: Kalshi taker fee = round(0.07 * P * (1-P), 2) per contract, per side. Maker = 0.
"""
import requests, csv, os, time, re
from datetime import datetime, timedelta
from compare_kalshi_nbm import (CITIES, get_nbs, latest_cyc, parse_high,
                                kalshi_brackets, bracket_bounds, bracket_prob)

OUT = os.environ.get('CLV_LOG', 'weather_clv_log.csv')
FEE = lambda p: round(0.07*p*(1-p), 2)   # per-contract taker fee, p in [0,1]

def snapshot_row(days_ahead=1):
    today = datetime.utcnow().date()
    tgt = today + timedelta(days=days_ahead)
    ds = today.strftime('%Y%m%d')
    cyc = latest_cyc(ds)[-1]
    txt = get_nbs(ds, cyc)
    evdate = tgt.strftime('%y%b%d').upper()
    ts = datetime.utcnow().isoformat()
    rows = []
    for city,(stn,series) in CITIES.items():
        high,sig = parse_high(txt, stn, tgt)
        if high is None: continue
        event = f'{series}-{evdate}'
        try: brs = kalshi_brackets(event)
        except Exception: continue
        for m in brs:
            lo,hi = bracket_bounds(m)
            p = bracket_prob(lo,hi,high,sig)
            yb,ya = m['yb'],m['ya']
            mid = ((yb+ya)/2) if (yb is not None and ya is not None) else ''
            rows.append([ts,city,stn,event,m['sub'],lo,hi,high,sig,round(p,4),
                         yb,ya,mid,'','', cyc])
    return rows

def append(rows):
    new = not os.path.exists(OUT)
    with open(OUT,'a',newline='') as f:
        w=csv.writer(f)
        if new:
            w.writerow(['ts','city','station','event','bracket','lo','hi','nbm_high',
                        'nbm_sigma','nbm_p','k_yes_bid','k_yes_ask','k_mid',
                        'actual_high','settled','nbm_cycle'])
        w.writerows(rows)

if __name__=='__main__':
    import sys
    n = int(sys.argv[1]) if len(sys.argv)>1 else 1
    rows = snapshot_row(n)
    append(rows)
    print(f'logged {len(rows)} bracket-rows to {OUT} (days_ahead={n})')

    # Second pass (was spec'd in this docstring, never wired up before): settle any historical
    # rows whose markets have since closed/finalized, in place on OUT, so the SAME file/commit
    # step the workflow already ships (kalshi-weather.yml) carries scoreable rows -- no workflow
    # change needed. Best-effort: never fails the collector run (a Kalshi API hiccup here should
    # not block logging today's snapshot, which already happened above).
    try:
        from weather_settle import settle_log
        settle_log(OUT)
    except Exception as e:
        print(f'weather_settle pass skipped/failed (non-fatal): {e}')
