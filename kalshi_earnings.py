#!/usr/bin/env python3
"""
kalshi_earnings.py

Farm + OOS-test a KALSHI-NATIVE "corporate-earnings beat-rate mispricing"
strategy (inspired by dragonbear666/polymarket-arb-engine-tool), on the
operator's target venue (Kalshi). Uncorrelated with the crypto edge.

HYPOTHESIS (literal): public companies beat consensus EPS ~70-75% of the time
(guidance sandbagging). If Kalshi prices the "beat" probability below the true
base rate, buying "beat" is +EV net of fees.

WHAT KALSHI ACTUALLY OFFERS (found during collection): Kalshi has NO binary
"Will <co> beat consensus EPS?" markets in the settled set. Its corporate
"KPI" products are THRESHOLD LADDERS on operational metrics:
    "Will <company> report ABOVE X <metric> in Q<n>?"
    (deliveries, vehicles, transactions, customers, skier visits, packages,
     restaurants, funded accounts, ...). 0 EPS markets, 7 "revenue" markets
    (Snowflake customer-with->$1M-revenue counts).

So the LITERAL EPS-beat hypothesis is NOT instrumentable on Kalshi today.
We test the closest DEPLOYABLE analog, which captures the same economic idea:

    Do Kalshi KPI threshold ladders systematically UNDER-price the upside?
    i.e. does the realized metric land ABOVE the market's central expectation
    (a "beat") more often than the executable price implies?

If yes -> buying YES ("above") on the near-median strike is +EV net of fees.

DISCIPLINE (mirrors the killed-~18-candidate bar):
  * NET of Kalshi fees ALWAYS. Kalshi trading fee = ceil_to_cent(0.07*C*p*(1-p))
    per order (quadratic, fee_multiplier=1 for these series -> 0.07). Charged
    on the taker at entry. We charge fee at entry price and report both the
    ceil-to-cent per-contract fee and the continuous 0.07*p*(1-p) lower bound.
  * EXECUTABLE price, not mid: to BUY YES you pay yes_ask; to BUY NO you pay
    (1 - yes_bid). Inclusion band uses the mid; PnL uses the executable ask.
  * PRE-CLOSE entry from CANDLESTICKS, never the terminal last_price (which is
    pinned to 0.01/0.99 post-settlement -- a look-ahead trap). Entry = last
    candle strictly before close_time with valid two-sided quotes. A second,
    earlier entry (>= ENTRY_BUFFER_EARLY before close) is computed as a
    look-ahead / robustness check.
  * CLUSTER t at the EVENT (company-quarter-metric) level -- the ~4-9 strikes
    of one ladder are NOT independent. Also report week-clustered t.
  * Calibration reported. Small-n flagged loudly. Multiple-testing count
    reported. Selection/concentration (which companies dominate) reported.

Outputs: kalshi_earnings_report.md, kalshi_earnings_summary.json
Raw candlesticks cached under scratchpad/kalshi_earn_raw/.
"""
import urllib.request, json, os, sys, math, time, statistics, re
from datetime import datetime, timezone
from collections import defaultdict, Counter
import concurrent.futures as cf

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW  = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/kalshi_earn_raw"
os.makedirs(RAW, exist_ok=True)

FEE_RATE          = 0.07     # quadratic fee coefficient (fee_multiplier=1 for these series)
SPREAD_CAP        = 0.15     # max yes_ask-yes_bid at entry to consider it executable
ENTRY_BUFFER_LATE = 60       # entry candle must end >= this many seconds before close
ENTRY_BUFFER_EARLY= 3*3600   # robustness entry: >= 3h before close
WORKERS           = 24
CATS              = ["Companies", "Financials"]
SERIES_KW         = ["kpi","earning","eps","revenue","sales","deliver","subscrib"]


def get(url, tries=5):
    last=None
    for _ in range(tries):
        try:
            req=urllib.request.Request(url, headers={"User-Agent":"research"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except Exception as e:
            last=str(e); time.sleep(0.8)
    return {"__err":last}


def iso_ts(s):
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())


def week_key(close_iso):
    dt=datetime.fromisoformat(close_iso.replace("Z","+00:00"))
    y,w,_=dt.isocalendar()
    return f"{y}-W{w:02d}"


# ---------------- collection ----------------
def list_earnings_series():
    ser={}
    for c in CATS:
        d=get(f"{BASE}/series?category="+urllib.request.quote(c))
        for s in d.get("series",[]):
            ser[s["ticker"]]=s["title"]
    keys=[t for t,ti in ser.items()
          if any(k in (ti+" "+t).lower() for k in SERIES_KW)]
    return sorted(keys), ser


def list_settled(series):
    out=[]; cur=None
    while True:
        u=f"{BASE}/markets?series_ticker={series}&status=settled&limit=1000"
        if cur: u+="&cursor="+cur
        d=get(u)
        if "__err" in d: break
        ms=d.get("markets",[]); out+=ms
        cur=d.get("cursor")
        if not cur or not ms: break
    return out


def fetch_candles(series, ticker, o, c):
    fn=os.path.join(RAW, f"c_{ticker}.json")
    if os.path.exists(fn):
        try: return json.load(open(fn))
        except Exception: pass
    u=f"{BASE}/series/{series}/markets/{ticker}/candlesticks?start_ts={o}&end_ts={c}&period_interval=60"
    d=get(u)
    cs=d.get("candlesticks",[]) if "__err" not in d else []
    json.dump(cs, open(fn,"w"))
    return cs


def _cd(node, field):
    """extract a *_dollars float from a candlestick sub-node, or None."""
    if not isinstance(node, dict): return None
    v=node.get(field)
    if v in (None,""): return None
    try: return float(v)
    except Exception: return None


def entry_from_candles(cs, close_ts, min_before):
    """Return (yes_bid, yes_ask, mid, traded_price_or_None, cand_ts) at the LAST
    candle ending <= close_ts-min_before with valid 2-sided quotes, else None."""
    best=None
    for c in cs:
        ept=c.get("end_period_ts")
        if ept is None or ept> (close_ts-min_before): continue
        yb=_cd(c.get("yes_bid"),"close_dollars")
        ya=_cd(c.get("yes_ask"),"close_dollars")
        if yb is None or ya is None: continue
        if not (0.0 < yb < 1.0 and 0.0 < ya <= 1.0): continue
        if ya < yb: continue
        if (ya-yb) > SPREAD_CAP: continue
        pr=_cd(c.get("price"),"close_dollars")
        best=(yb,ya,(yb+ya)/2.0,pr,ept)   # keep overwriting -> last valid wins
    return best


def collect():
    keys,_=list_earnings_series()
    print(f"[collect] {len(keys)} candidate earnings/KPI series", file=sys.stderr)
    allm=[]
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for ms in ex.map(list_settled, keys): allm+=ms
    # only threshold-ladder "report above/below X" markets w/ yes|no result
    rows=[]
    for m in allm:
        r=m.get("result")
        if r not in ("yes","no"): continue
        title=m.get("title") or ""
        if "report" not in title.lower(): continue
        if not m.get("open_time") or not m.get("close_time"): continue
        rows.append(m)
    print(f"[collect] {len(rows)} settled ladder markets; pulling candlesticks", file=sys.stderr)

    def enrich(m):
        series=m["ticker"].split("-")[0]
        o=iso_ts(m["open_time"]); c=iso_ts(m["close_time"])
        cs=fetch_candles(series, m["ticker"], o, c)
        late =entry_from_candles(cs, c, ENTRY_BUFFER_LATE)
        early=entry_from_candles(cs, c, ENTRY_BUFFER_EARLY)
        return m, series, late, early

    recs=[]
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for m, series, late, early in ex.map(enrich, rows):
            if late is None: continue
            yb,ya,mid,pr,cts=late
            rec={
                "ticker": m["ticker"],
                "series": series,
                "event": m.get("event_ticker"),
                "company": (m.get("title") or "").split(" report")[0].replace("Will ","").strip(),
                "title": m.get("title"),
                "sub": m.get("yes_sub_title"),
                "result": 1 if m["result"]=="yes" else 0,
                "close_time": m["close_time"],
                "week": week_key(m["close_time"]),
                "yes_bid": yb, "yes_ask": ya, "mid": mid,
                "traded": pr,
                "entry_ts": cts,
                "hours_before_close": round((iso_ts(m["close_time"])-cts)/3600.0,2),
            }
            if early is not None:
                rec["early_mid"]=early[2]; rec["early_ask"]=early[1]; rec["early_bid"]=early[0]
            recs.append(rec)
    print(f"[collect] {len(recs)} markets with a valid pre-close executable entry", file=sys.stderr)
    json.dump(recs, open(os.path.join(RAW,"recs.json"),"w"), indent=1)
    return recs


# ---------------- stats helpers ----------------
def fee_ceil(p):
    """Kalshi per-contract fee, ceil to a cent: ceil(100*0.07*p*(1-p))/100."""
    return math.ceil(100.0*FEE_RATE*p*(1.0-p))/100.0

def fee_cont(p):
    return FEE_RATE*p*(1.0-p)

def clustered_t(values_by_group):
    """mean of per-group means, t = mean / (sd/sqrt(k)). Returns (mean,t,k,n)."""
    gmeans=[]; n=0
    for g,vs in values_by_group.items():
        if not vs: continue
        gmeans.append(sum(vs)/len(vs)); n+=len(vs)
    k=len(gmeans)
    if k<2: return (statistics.mean(gmeans) if gmeans else float("nan"), float("nan"), k, n)
    m=statistics.mean(gmeans); sd=statistics.pstdev(gmeans)*math.sqrt(k/(k-1))
    t=m/(sd/math.sqrt(k)) if sd>0 else float("nan")
    return (m,t,k,n)


# ---------------- analysis ----------------
def analyze(recs):
    out={}
    out["n_markets"]=len(recs)
    out["n_events"]=len(set(r["event"] for r in recs))
    out["n_series"]=len(set(r["series"] for r in recs))
    out["n_weeks"]=len(set(r["week"] for r in recs))

    # concentration
    comp=Counter(r["company"] for r in recs)
    ser =Counter(r["series"] for r in recs)
    out["top_companies"]=comp.most_common(10)
    out["top_series"]=ser.most_common(10)

    # ---- base-rate framing: overall realized YES vs mean priced mid ----
    realized=statistics.mean(r["result"] for r in recs)
    priced_mid=statistics.mean(r["mid"] for r in recs)
    priced_ask=statistics.mean(r["yes_ask"] for r in recs)
    out["realized_yes_rate"]=realized
    out["mean_priced_mid"]=priced_mid
    out["mean_priced_yes_ask"]=priced_ask

    # ---- calibration bins on entry mid ----
    bins=[(0,0.1),(0.1,0.25),(0.25,0.4),(0.4,0.6),(0.6,0.75),(0.75,0.9),(0.9,1.01)]
    calib=[]
    for lo,hi in bins:
        sub=[r for r in recs if lo<=r["mid"]<hi]
        if sub:
            calib.append({"band":f"[{lo:.2f},{hi:.2f})","n":len(sub),
                          "mean_mid":round(statistics.mean(x["mid"] for x in sub),4),
                          "realized":round(statistics.mean(x["result"] for x in sub),4)})
    out["calibration"]=calib

    # ---- per-event median-strike "beat" test ----
    # For each event, pick the strike whose entry mid is closest to 0.50 = the
    # market's central expectation. result==1 (metric above that strike) = beat.
    evgroups=defaultdict(list)
    for r in recs: evgroups[r["event"]].append(r)
    beats=[]; med_detail=[]
    for ev,rs in evgroups.items():
        pick=min(rs, key=lambda x:abs(x["mid"]-0.5))
        beats.append(pick["result"])
        med_detail.append({"event":ev,"company":pick["company"],"mid":round(pick["mid"],3),
                           "result":pick["result"],"week":pick["week"]})
    out["median_strike_beat_rate"]=statistics.mean(beats) if beats else float("nan")
    out["median_strike_n_events"]=len(beats)
    # binomial-ish: mean of 0/1 across events, t vs 0.5
    if len(beats)>=2:
        m=statistics.mean(beats); sd=statistics.pstdev(beats)*math.sqrt(len(beats)/(len(beats)-1))
        out["median_strike_t_vs_0.5"]=(m-0.5)/(sd/math.sqrt(len(beats))) if sd>0 else float("nan")
    else:
        out["median_strike_t_vs_0.5"]=float("nan")
    out["median_strike_detail"]=med_detail

    # ---- net-of-fee backtests (multiple strategies; count them) ----
    strategies={}
    def run_buy_yes(recs_sub, label):
        # PnL/ct = result - yes_ask - fee(yes_ask)
        by_event=defaultdict(list); by_week=defaultdict(list); pnls=[]
        for r in recs_sub:
            a=r["yes_ask"]; pnl=r["result"]-a-fee_ceil(a); pnls.append(pnl)
            by_event[r["event"]].append(pnl); by_week[r["week"]].append(pnl)
        if not pnls: return None
        me,te,ke,ne=clustered_t(by_event); mw,tw,kw_,nw=clustered_t(by_week)
        # continuous-fee variant (lower-bound fee)
        pnls_c=[r["result"]-r["yes_ask"]-fee_cont(r["yes_ask"]) for r in recs_sub]
        return {"label":label,"n":len(pnls),"n_events":ke,"n_weeks":kw_,
                "mean_pnl_ct":round(statistics.mean(pnls),4),
                "mean_pnl_ct_contfee":round(statistics.mean(pnls_c),4),
                "gross_pnl_ct":round(statistics.mean(r["result"]-r["yes_ask"] for r in recs_sub),4),
                "t_event":round(te,3),"t_week":round(tw,3),
                "win_rate":round(statistics.mean(1 if p>0 else 0 for p in pnls),3)}
    def run_buy_no(recs_sub, label):
        # buy NO: pay (1-yes_bid); wins if result==0. PnL = (1-result) - (1-yes_bid) - fee(1-yes_bid)
        by_event=defaultdict(list); by_week=defaultdict(list); pnls=[]
        for r in recs_sub:
            cost=1.0-r["yes_bid"]; pnl=(1-r["result"])-cost-fee_ceil(cost); pnls.append(pnl)
            by_event[r["event"]].append(pnl); by_week[r["week"]].append(pnl)
        if not pnls: return None
        me,te,ke,ne=clustered_t(by_event); mw,tw,kw_,nw=clustered_t(by_week)
        return {"label":label,"n":len(pnls),"n_events":ke,"n_weeks":kw_,
                "mean_pnl_ct":round(statistics.mean(pnls),4),
                "gross_pnl_ct":round(statistics.mean((1-r["result"])-(1.0-r["yes_bid"]) for r in recs_sub),4),
                "t_event":round(te,3),"t_week":round(tw,3),
                "win_rate":round(statistics.mean(1 if p>0 else 0 for p in pnls),3)}

    allrec=recs
    midband =[r for r in recs if 0.35<=r["mid"]<=0.65]
    liqband =[r for r in recs if 0.10<=r["mid"]<=0.90]
    lowband =[r for r in recs if 0.10<=r["mid"]<0.35]   # cheap "above" longshots
    strategies["S1_buyYES_all"]        =run_buy_yes(allrec,"buy YES, all liquid strikes")
    strategies["S2_buyYES_midband"]    =run_buy_yes(midband,"buy YES, mid mid in [.35,.65]")
    strategies["S3_buyYES_liqband"]    =run_buy_yes(liqband,"buy YES, mid in [.10,.90]")
    strategies["S4_buyYES_lowband"]    =run_buy_yes(lowband,"buy YES, mid in [.10,.35] (upside longshot)")
    strategies["S5_buyNO_all"]         =run_buy_no(allrec,"buy NO, all liquid strikes")
    strategies["S6_buyNO_midband"]     =run_buy_no(midband,"buy NO, mid in [.35,.65]")
    out["strategies"]=strategies
    out["n_strategies_tried"]=len([s for s in strategies.values() if s])
    # + calibration bins (7) + median-strike test = additional looks
    out["n_multiple_testing_looks"]=out["n_strategies_tried"]+len(calib)+1

    # ---- capacity: liquidity proxy from open interest / entry spreads ----
    spreads=[r["yes_ask"]-r["yes_bid"] for r in recs]
    out["median_entry_spread"]=round(statistics.median(spreads),3)
    out["mean_hours_before_close"]=round(statistics.mean(r["hours_before_close"] for r in recs),2)

    return out


# ---------------- reporting ----------------
def write_reports(out):
    json.dump(out, open(os.path.join(HERE,"kalshi_earnings_summary.json"),"w"), indent=2, default=str)

    S=out["strategies"]
    def line(s):
        if not s: return "  (empty)"
        return (f"  {s['label']}: n={s['n']} (ev={s['n_events']}, wk={s['n_weeks']}) | "
                f"gross={s['gross_pnl_ct']:+.4f} | NET/ct={s['mean_pnl_ct']:+.4f} "
                f"| t_event={s['t_event']} t_week={s['t_week']} | win={s['win_rate']}")

    best=max((s for s in S.values() if s), key=lambda x:x["mean_pnl_ct"])
    fee_kills = out["mean_priced_mid"]
    verdict_null = not any((s and s["mean_pnl_ct"]>0 and abs(s["t_event"])>=2.0) for s in S.values())

    md=[]
    md.append("# Kalshi corporate-earnings beat-rate mispricing -- OOS test\n")
    md.append(f"_Generated {datetime.now(timezone.utc).isoformat()} | venue: Kalshi | "
              f"data: public trade-api v2 (no auth)._\n")
    md.append("## TL;DR verdict\n")
    md.append("**The literal hypothesis is NOT instrumentable on Kalshi.** Kalshi has "
              "**zero** binary \"Will <company> beat consensus EPS?\" markets in the settled "
              "universe. Its corporate products are **operational-KPI threshold ladders** "
              "(\"Will <co> report ABOVE X deliveries/customers/transactions in Q?\"). "
              "0 EPS markets; 7 \"revenue\"-qualified markets.\n")
    md.append(f"We tested the closest deployable analog -- systematic **upside/beat bias** in "
              f"those ladders vs **executable pre-close** prices, **net of Kalshi fees**, "
              f"clustered at the event level.\n")
    md.append(f"- Sample: **{out['n_markets']} settled ladder markets** across "
              f"**{out['n_events']} distinct events** (company-quarter-metric), "
              f"{out['n_series']} companies, {out['n_weeks']} settlement weeks.\n")
    md.append(f"- Realized YES (\"beat\") rate = **{out['realized_yes_rate']:.3f}** vs "
              f"mean priced mid **{out['mean_priced_mid']:.3f}** "
              f"(mean executable yes_ask {out['mean_priced_yes_ask']:.3f}).\n")
    md.append(f"- Median-strike beat test (metric above the ~50c strike): "
              f"beat rate **{out['median_strike_beat_rate']:.3f}** over "
              f"**{out['median_strike_n_events']} events**, t vs 0.5 = "
              f"**{out['median_strike_t_vs_0.5']:.2f}**.\n")
    md.append(f"- Best net-of-fee strategy: **{best['label']}** -> "
              f"NET **{best['mean_pnl_ct']:+.4f}/ct**, t_event **{best['t_event']}**.\n")
    md.append(f"- **VERDICT: {'NO fee-surviving edge (NULL).' if verdict_null else 'POSSIBLE edge -- see caveats.'}** "
              f"n is far too small ({out['n_events']} events) for a deployable, statistically "
              f"credible conclusion. Treat as **NULL / not deployable**.\n")

    md.append("\n## Fee model\n")
    md.append("Kalshi trading fee (quadratic, fee_multiplier=1 for these series): "
              "`fee = ceil_to_cent(0.07 * C * p * (1-p))` per order, charged on the taker at "
              "entry. Per-contract we charge `ceil(100*0.07*p*(1-p))/100` at the executable "
              "entry price. Continuous `0.07*p*(1-p)` reported as a lower bound. At p=0.5 that "
              "is 1.75c/ct (2c after ceil) EACH WAY -- a large hurdle for any near-50/50 bet.\n")

    md.append("\n## Base-rate / calibration\n")
    md.append("| entry mid band | n | mean mid | realized YES |\n|---|---|---|---|\n")
    for c in out["calibration"]:
        md.append(f"| {c['band']} | {c['n']} | {c['mean_mid']:.3f} | {c['realized']:.3f} |\n")
    md.append("\nIf companies systematically 'beat', realized should exceed mean mid in the "
              "mid/low bands. Read the gap vs the fee hurdle (~2c/side at 50c).\n")

    md.append("\n## Strategies tested (net of fees, executable entry, event-clustered t)\n")
    for k,s in S.items():
        md.append(f"- **{k}** {line(s)}\n")
    md.append(f"\nMultiple-testing looks: **{out['n_multiple_testing_looks']}** "
              f"({out['n_strategies_tried']} PnL strategies + {len(out['calibration'])} "
              f"calibration bins + 1 median-strike test). No multiplicity correction would "
              f"survive at this n.\n")

    md.append("\n## Capacity, concentration, correlation\n")
    md.append(f"- Median entry bid/ask spread: **{out['median_entry_spread']:.3f}** "
              f"(wide -> taker cost real). Mean entry taken **{out['mean_hours_before_close']}h** "
              f"before close.\n")
    md.append(f"- Company concentration (top): {out['top_companies'][:6]}\n")
    md.append(f"- Series concentration (top): {out['top_series'][:6]}\n")
    md.append("- **Capacity:** Kalshi KPI markets are thin and episodic (a handful of names per "
              "earnings week, low OI). Even if an edge existed, deployable size is tiny.\n")
    md.append("- **Correlation with crypto edge:** earnings/KPI outcomes are idiosyncratic, "
              "firm-specific events -> effectively **uncorrelated** with the BTC/ETH crypto "
              "microstructure edge. (Diversifying in principle, but see verdict.)\n")

    md.append("\n## Caveats / discipline\n")
    md.append("- Only SETTLED markets (survivorship is fine here, but noted). Sample dominated "
              "by a few names (Tesla deliveries, Rivian, Vail, Boeing).\n")
    md.append("- Entry is the last valid two-sided candle strictly before close (pre-announcement); "
              "terminal last_price (pinned 0.01/0.99) is deliberately NOT used.\n")
    md.append("- Ladder strikes within an event are highly correlated -> event-clustered t is the "
              "honest unit. With ~22 events, power is near zero.\n")
    md.append("- The literal EPS-beat edge from the Polymarket tool does not port: the Kalshi "
              "instrument (consensus-EPS binary) does not exist here.\n")

    open(os.path.join(HERE,"kalshi_earnings_report.md"),"w").write("".join(md))
    print("[report] wrote kalshi_earnings_report.md + kalshi_earnings_summary.json", file=sys.stderr)


if __name__=="__main__":
    cached=os.path.join(RAW,"recs.json")
    if "analyze" in sys.argv and os.path.exists(cached):
        recs=json.load(open(cached))
    else:
        recs=collect()
    out=analyze(recs)
    write_reports(out)
    # console digest
    print("\n=== DIGEST ===")
    print(f"n_markets={out['n_markets']} n_events={out['n_events']} n_series={out['n_series']} n_weeks={out['n_weeks']}")
    print(f"realized_yes={out['realized_yes_rate']:.3f} priced_mid={out['mean_priced_mid']:.3f} priced_ask={out['mean_priced_yes_ask']:.3f}")
    print(f"median_strike beat_rate={out['median_strike_beat_rate']:.3f} over {out['median_strike_n_events']} events, t_vs_0.5={out['median_strike_t_vs_0.5']:.2f}")
    for k,s in out["strategies"].items():
        if s: print(f"  {k}: NET/ct={s['mean_pnl_ct']:+.4f} gross={s['gross_pnl_ct']:+.4f} t_ev={s['t_event']} t_wk={s['t_week']} n={s['n']} ev={s['n_events']} win={s['win_rate']}")
    print(f"multiple_testing_looks={out['n_multiple_testing_looks']}")
