#!/usr/bin/env python3
"""perp_forward.py -- FORWARD-VALIDATION HARNESS for the PERP<->15m-BINARY BASIS (edge (a),
perp_strategy_design.md sec 1). Collect-then-forward, same discipline as favlong_forward.py.

WHAT (edge a): the Kalshi crypto perp and the Kalshi 15m binary price the SAME underlying on the
SAME venue and SAME clock (co-collected `binmid` stream). The perp gives a continuous implied spot;
the binary gives a risk-neutral implied spot. When they disagree beyond costs one leg is rich -> put
on a DELTA-NEUTRAL basis trade, hold to the binary's 0/1 SETTLE (self-settling, no mark ambiguity),
book realized P&L post-cost. This harness FREEZES the entry/exit/sizing config BEFORE forward day 1
(perp_forward_config.json), scores each COMPLETE forward day idempotently into perp_forward_log.jsonl,
and prints the pooled + per-asset day-clustered gate (PASS >=10 fwd days & pooled t>=2; KILL t<0).

KEY OPEN QUESTION (measured, not assumed): edge (a)'s signal (binary mispriced vs perp-implied spot)
may be CORRELATED with FAVLONG (which trades the binary vs a BRTI-spot vol model; perp index ~= BRTI
spot). If edge (a) is just a hedged FAVLONG it is NOT a diversifier. This harness computes FAVLONG's
per-day realized P&L on the same days and reports the day-level correlation -- a FIRST-CLASS output
(the orthogonality verdict).

HOW binary-implied-spot is derived (single-strike 15m up/down market; DOCUMENTED):
  The feed carries no dollar strike (the ticker suffix is just the close-minute; the open YES mid is
  NOT 0.5 -> the strike is a pre-set level, not the open spot). So we use the FAVLONG fair-value
  INVERSION with the strike K0 CALIBRATED ONCE per window from the earliest window tick:
    - implied_spot_perp(t) = perp_mid(t)/contract_size          (dollars)
    - sigma(t) = causal realized vol of implied_spot_perp within the window up to t (no look-ahead)
    - z*(t)   = probit(yes_mid(t))                               (binary's std-normal quantile)
    - S_bin(t) = K0 / (1 - z*(t)*sigma(t)*sqrt(tau))             (invert P(up)=NORM((S-K0)/(S*a)))
    - K0 fixed once at the anchor tick t0 (t0-ws<=anchor_max_s) by forcing S_bin(t0)=S_perp(t0):
        K0 = S_perp(t0) * (1 - z*(t0)*sigma(t0)*sqrt(tau0)).
      => basis is 0 at the anchor by construction; the SIGNAL is intra-window perp<->binary divergence
      (open->decision), which the trade bets reverts by settle. This is the minimal assumption that
      places both instruments on the same dollar axis without an external strike.
    - basis_bps(t) = 1e4*(implied_spot_perp(t)/S_bin(t) - 1).

EDGE (b) funding-carry STUB: Kalshi perp funding_rate is currently 0.0 (verified 2026-07-15, all
assets). There is NOTHING to harvest -> NO carry trade is simulated. This harness LOGS the per-day
funding series (min/max/mean funding_rate) so a sign flip is caught; revisit edge (b) only if funding
turns non-zero. See print at end.

GATE (perp_strategy_design.md sec Gate; do not relax): pooled per-(asset,day) day-clustered t>=2 over
>=10 FORWARD days (strictly AFTER freeze_date), per-asset AND pooled, frozen params, no refit, only
COMPLETE days (strictly before today UTC).

Usage:
  python perp_forward.py            # fetch gha-data, score new COMPLETE forward days, print gates+corr
  python perp_forward.py --report   # print gate/correlation from the existing log (no fetch)
  python perp_forward.py --selftest # score whatever real day(s) exist IGNORING the forward filter,
                                     # to prove the pipeline runs on day-1 minimal data (NOT gated;
                                     # writes to a scratch log, never perp_forward_log.jsonl)
Stdlib only (GHA runner has no numpy/sklearn). Read-only: no keys, no orders, no live config.
"""
import subprocess, gzip, json, re, math, statistics, os, sys, time, bisect
from datetime import datetime, timezone
from collections import defaultdict

import favlongshot_edge as fav   # reuse the VALIDATED FAVLONG math for the correlation leg

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(HERE, "perp_forward_config.json")
LOG = os.path.join(HERE, "perp_forward_log.jsonl")
SELFTEST_LOG = os.path.join(HERE, "perp_forward_selftest.jsonl")

SQRT2PI = math.sqrt(2.0 * math.pi)
NORM = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
PHI = lambda z: math.exp(-0.5 * z * z) / SQRT2PI


# ---- frozen config -------------------------------------------------------------------------------
def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


CFG = load_config()
EDGE = CFG["edge"]
FREEZE_DATE = CFG["freeze_date"]
FORWARD_START = CFG["forward_start"]
GATE_MIN_DAYS = CFG["gate_min_days"]
GATE_T = CFG["gate_t"]
ASSETS_BASIS = CFG["assets_basis"]
ASSETS_FAVLONG = CFG["assets_favlong"]


# ---- inverse normal CDF (Acklam rational approx; stdlib has erf but not its inverse) --------------
def inv_norm_cdf(p):
    if p <= 0.0:
        return -1e9
    if p >= 1.0:
        return 1e9
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# ---- git plumbing (mirror favlong_forward.py) ----------------------------------------------------
def _sh_bytes(*a):
    return subprocess.run(a, capture_output=True).stdout


def _git_fetch_gha_data(retries=5):
    for i in range(retries):
        r = subprocess.run(["git", "fetch", "--depth=1", "origin", "gha-data"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return True
        sys.stderr.write(f"git fetch gha-data failed ({i+1}/{retries}): {r.stderr.strip()[:200]}\n")
        time.sleep(min(2 ** i, 30))
    return False


# ---- data build: per (asset, day) -> list of window dicts ----------------------------------------
def build_perp(asset):
    """Reconstruct aligned perp + 15m-binary windows for one asset from origin/gha-data.
    Returns {day: [window, ...]} where window = dict(ws, cs, perp=[(rt,S_perp,S_index,fr)],
    bin=[(rt,yb,ya,mid)])   (rt = seconds into the 900s window). Merges all runtags per day."""
    listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/gha-data"],
                             capture_output=True, text=True).stdout.splitlines()
    perp_files = [f for f in listing if re.search(rf"ticks_kalshi_perp_{asset}_", f)]
    bin_files = [f for f in listing if re.search(rf"ticks_kalshi_perp_binmid_{asset}_", f)]

    # perp ticks by day: (t_epoch, S_perp, S_index, funding_rate, contract_size)
    perp_by_day = defaultdict(list)
    for f in perp_files:
        m = re.search(r"(2026-\d\d-\d\d)", f)
        if not m:
            continue
        try:
            txt = gzip.decompress(_sh_bytes("git", "show", f"origin/gha-data:{f}")).decode()
        except Exception:
            continue
        for l in txt.splitlines():
            try:
                d = json.loads(l)
            except Exception:
                continue
            cs = d.get("contract_size")
            mid = d.get("mid")
            if not cs or mid is None:
                continue
            idx = d.get("index")
            fr = (d.get("funding") or {}).get("funding_rate")
            perp_by_day[m.group(1)].append(
                (d["t"], mid / cs, (idx / cs) if idx is not None else None, fr, cs))

    # binary ticks by (day, ws): (t_epoch, yes_bid, yes_ask, mid)
    bin_by_day_ws = defaultdict(lambda: defaultdict(list))
    for f in bin_files:
        m = re.search(r"(2026-\d\d-\d\d)", f)
        if not m:
            continue
        try:
            txt = gzip.decompress(_sh_bytes("git", "show", f"origin/gha-data:{f}")).decode()
        except Exception:
            continue
        for l in txt.splitlines():
            try:
                d = json.loads(l)
            except Exception:
                continue
            ws = d.get("ws")
            if ws is None:
                continue
            bin_by_day_ws[m.group(1)][ws].append(
                (d["t"], d.get("yes_bid"), d.get("yes_ask"), d.get("mid")))

    data = {}
    for day, ws_map in bin_by_day_ws.items():
        perp = sorted(perp_by_day.get(day, []))
        pt = [p[0] for p in perp]            # perp epoch times (sorted) for nearest-lookup
        windows = []
        for ws, brows in ws_map.items():
            brows = sorted(brows)
            cs = perp[0][4] if perp else None
            # align each binary tick to the nearest perp tick within align_tol_s
            binseq, perpseq = [], []
            for (t, yb, ya, mid) in brows:
                rt = t - ws
                if rt < 0 or rt > 900:
                    continue
                j = bisect.bisect_left(pt, t)
                best = None
                for k in (j - 1, j):
                    if 0 <= k < len(perp):
                        dtk = abs(perp[k][0] - t)
                        if best is None or dtk < best[0]:
                            best = (dtk, k)
                if best is None or best[0] > CFG["align_tol_s"]:
                    continue
                pk = perp[best[1]]
                if None in (yb, ya, mid):
                    continue
                binseq.append((rt, yb, ya, mid))
                perpseq.append((rt, pk[1], pk[2], pk[3]))   # rt, S_perp, S_index, funding_rate
            if len(binseq) < 6:
                continue
            windows.append(dict(ws=ws, cs=cs, bin=binseq, perp=perpseq))
        if windows:
            data[day] = windows
    return data


def _causal_sigma(rts, spots, idx):
    """Per-sqrt-second realized vol of perp implied spot using ONLY ticks up to idx (no look-ahead).
    Mirrors favlongshot_edge._causal_sigma but on the perp implied-spot series."""
    sp = [spots[i] for i in range(idx + 1) if spots[i]]
    if len(sp) < 5:
        return None
    lr = [math.log(sp[i + 1] / sp[i]) for i in range(len(sp) - 1) if sp[i] > 0 and sp[i + 1] > 0]
    if len(lr) < 4:
        return None
    dt = (rts[idx] - rts[0]) / max(1, len(lr))
    return statistics.pstdev(lr) / math.sqrt(max(dt, 0.5))


# ---- edge (a) per-window trade simulation --------------------------------------------------------
def _score_window(w):
    """Simulate ONE delta-neutral basis trade in a window, held to binary settle. Returns per-trade
    P&L in $ per $1 spot-delta notional (return units), or None if no qualifying entry. Also returns
    diagnostics. DOCUMENTED derivation of the binary-implied spot is in the module header."""
    binseq, perpseq = w["bin"], w["perp"]
    rts = [p[0] for p in perpseq]
    Sperp = [p[1] for p in perpseq]

    # anchor tick (earliest within anchor_max_s) -> calibrate K0
    anchor = None
    for i, rt in enumerate(rts):
        if rt <= CFG["anchor_max_s"]:
            anchor = i
    if anchor is None or anchor < 4:
        return None
    a_rt = rts[anchor]
    a_S = Sperp[anchor]
    a_p = min(max(binseq[anchor][3], 1e-4), 1 - 1e-4)
    a_sig = _causal_sigma(rts, Sperp, anchor)
    if not a_sig or a_S is None or a_S <= 0:
        return None
    a_tau = 900 - a_rt
    if a_tau < CFG["tau_floor_s"]:
        return None
    a_z = inv_norm_cdf(a_p)
    a_aa = a_sig * math.sqrt(a_tau)
    denom = 1 - a_z * a_aa
    if abs(denom) < 1e-9:
        return None
    K0 = a_S * denom                       # dollar strike calibrated: basis==0 at anchor

    # settle: binary 0/1 from last window mid; perp settle spot from last aligned tick near close
    last_bin = None
    for r in reversed(binseq):
        if r[0] >= CFG["settle_min_s"]:
            last_bin = r
            break
    if last_bin is None:
        last_bin = binseq[-1]
    settle01 = 1 if last_bin[3] > 0.5 else 0
    S_perp_settle = Sperp[-1]

    # scan decision band for the FIRST qualifying entry
    for i, rt in enumerate(rts):
        if rt < CFG["decision_lo_s"] or rt > CFG["decision_hi_s"]:
            continue
        S = Sperp[i]
        if S is None or S <= 0:
            continue
        tau = 900 - rt
        if tau < CFG["tau_floor_s"]:
            continue
        p = min(max(binseq[i][3], 1e-4), 1 - 1e-4)
        if abs(p - 0.5) >= CFG["atm_band"]:
            continue                       # keep binary delta well-defined / sizing bounded
        sig = _causal_sigma(rts, Sperp, i)
        if not sig:
            continue
        aa = sig * math.sqrt(tau)
        z = inv_norm_cdf(p)
        d2 = 1 - z * aa
        if abs(d2) < 1e-9:
            continue
        S_bin = K0 / d2
        if S_bin <= 0:
            continue
        basis_bps = 1e4 * (S / S_bin - 1)
        if abs(basis_bps) < CFG["entry_thr_bps"]:
            continue

        # ---- delta-neutral entry (sign = sign(basis); basis>0 => perp rich) ----
        sgn = 1.0 if basis_bps > 0 else -1.0     # +1: SHORT perp, LONG YES ; -1: LONG perp, SHORT YES
        yb, ya = binseq[i][1], binseq[i][2]
        if None in (yb, ya):
            continue
        # binary sizing: neutral to a 1% spot move -> n_bin = (sig*sqrt(tau))/phi(z), capped
        ph = PHI(z)
        if ph < 1e-6:
            continue
        n_bin = min(aa / ph, CFG["nbin_cap"])

        # perp leg P&L on $1 spot notional (short if sgn>0). round-trip taker = 2 fills.
        perp_ret = -sgn * (S_perp_settle / S - 1.0)
        perp_cost = 2 * CFG["perp_taker_bps"] / 1e4
        perp_pnl = perp_ret - perp_cost

        # binary leg P&L, $ per unit contract * n_bin (spot-equivalent), + Kalshi fee on entry price
        kf = CFG["kalshi_fee_coef"]
        if sgn > 0:                              # LONG YES: buy at ask
            entry_px = ya
            bin_pnl = n_bin * ((settle01 - entry_px) - kf * entry_px * (1 - entry_px))
        else:                                    # SHORT YES: sell at bid
            entry_px = yb
            bin_pnl = n_bin * ((entry_px - settle01) - kf * entry_px * (1 - entry_px))

        pnl = perp_pnl + bin_pnl
        return dict(pnl=pnl, basis_bps=basis_bps, sgn=sgn, entry_rt=rt, n_bin=n_bin,
                    settle01=settle01, perp_pnl=perp_pnl, bin_pnl=bin_pnl, S=S, S_bin=S_bin)
    return None


def score_day_basis(data, asset, day):
    """Score edge (a) for one (asset, day): one trade per qualifying window, held to settle.
    Always returns a record (n_trades=0 marks a complete day with no qualifying trade)."""
    pls = []
    for w in data.get(day, []):
        res = _score_window(w)
        if res is not None:
            pls.append(res["pnl"])
    fund_stats = _funding_stats(data, day)
    if not pls:
        return dict(edge=EDGE, asset=asset, day=day, n_trades=0, mean_pnl=None, day_pnl=0.0,
                    winrate=None, favlong_day_pnl=None, funding=fund_stats, config_freeze=FREEZE_DATE)
    return dict(edge=EDGE, asset=asset, day=day, n_trades=len(pls),
                mean_pnl=statistics.mean(pls), day_pnl=sum(pls),
                winrate=sum(1 for p in pls if p > 0) / len(pls),
                favlong_day_pnl=None, funding=fund_stats, config_freeze=FREEZE_DATE)


def _funding_stats(data, day):
    """Edge (b) STUB: summarize the per-day funding_rate series (no carry trade is simulated)."""
    frs = []
    for w in data.get(day, []):
        for (rt, Sp, Si, fr) in w["perp"]:
            if fr is not None:
                frs.append(fr)
    if not frs:
        return dict(n=0, min=None, max=None, mean=None)
    return dict(n=len(frs), min=min(frs), max=max(frs), mean=statistics.mean(frs))


# ---- FAVLONG per-day P&L (the correlation leg) ---------------------------------------------------
_FAV_CACHE = {}


def favlong_day_pnl(asset, day):
    """FAVLONG's realized per-day total P&L on the same day, via the VALIDATED favlongshot_edge.score
    (its own 15m tick archive). Returns None if no FAVLONG trades that day / asset not in universe."""
    if asset not in ASSETS_FAVLONG:
        return None
    if asset not in _FAV_CACHE:
        try:
            _FAV_CACHE[asset] = fav.build_asset(asset)
        except Exception as e:
            sys.stderr.write(f"favlong build_asset({asset}) failed: {e}\n")
            _FAV_CACHE[asset] = {}
    r = fav.score(_FAV_CACHE[asset], [day])
    return r["total"] if r else None


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = statistics.pstdev(xs)
    sy = statistics.pstdev(ys)
    if sx == 0 or sy == 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    return cov / (sx * sy)


# ---- log I/O -------------------------------------------------------------------------------------
def load_log(path=LOG):
    recs = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        recs.append(json.loads(line))
                    except Exception:
                        continue
    return recs


def append_records(new_recs, path=LOG):
    with open(path, "a") as f:
        for r in new_recs:
            f.write(json.dumps(r) + "\n")


# ---- gate + correlation reporting ----------------------------------------------------------------
def compute_gate(recs, asset=None):
    """Pooled per-(asset,day) day-clustered t over traded edge-(a) forward records.
    asset=None -> pooled across all basis assets; else that asset only."""
    traded = [r for r in recs if r.get("edge") == EDGE and r.get("n_trades", 0) > 0
              and r.get("mean_pnl") is not None
              and (asset is None or r.get("asset") == asset)]
    means = [r["mean_pnl"] for r in traded]
    days = sorted({r["day"] for r in traded})
    ndays = len(days)
    n = len(means)
    total = sum(r.get("day_pnl", 0.0) or 0.0 for r in traded)
    t = float("nan")
    mean = float("nan")
    if n >= 1:
        mean = statistics.mean(means)
    if n > 1 and statistics.stdev(means) > 0:
        t = statistics.mean(means) / (statistics.stdev(means) / math.sqrt(n))
    if ndays == 0:
        status = "CLOCK-NOT-STARTED"
    elif ndays < GATE_MIN_DAYS:
        status = "not-yet"
    elif not math.isnan(t) and t >= GATE_T:
        status = "PASSED"
    elif not math.isnan(t) and t < 0:
        status = "FAILED"
    else:
        status = "not-yet"
    return dict(status=status, ndays=ndays, n=n, t=t, mean=mean, total=total, days=days,
                n_pos=sum(1 for m in means if m > 0))


def correlation_report(recs):
    """Day-level correlation of edge (a) per-day P&L vs FAVLONG per-day P&L (the orthogonality
    verdict). Uses favlong_day_pnl stored in the records; computes pooled + per-asset Pearson r."""
    pairs = defaultdict(list)     # asset -> [(day, edgea_pnl, fav_pnl)]
    for r in recs:
        if r.get("edge") != EDGE:
            continue
        fp = r.get("favlong_day_pnl")
        if fp is None:
            continue
        pairs[r["asset"]].append((r["day"], r.get("day_pnl", 0.0), fp))
    lines = []
    pooled_x, pooled_y = [], []
    for asset in sorted(pairs):
        rows = pairs[asset]
        xs = [x[1] for x in rows]
        ys = [x[2] for x in rows]
        pooled_x += xs
        pooled_y += ys
        rho = _pearson(xs, ys)
        lines.append((asset, len(rows), rho))
    pooled_rho = _pearson(pooled_x, pooled_y)
    return pooled_rho, len(pooled_x), lines


def funding_report(recs):
    """Edge (b) stub summary: are any funding_rates non-zero across logged days?"""
    allmin, allmax, n = [], [], 0
    for r in recs:
        f = r.get("funding") or {}
        if f.get("n"):
            n += f["n"]
            if f.get("min") is not None:
                allmin.append(f["min"])
            if f.get("max") is not None:
                allmax.append(f["max"])
    if n == 0:
        return None
    return dict(n=n, min=min(allmin) if allmin else None, max=max(allmax) if allmax else None)


def print_report(recs):
    print("\n=== PERP<->BINARY BASIS (edge a) forward gate ===")
    print(f"config[FROZEN {FREEZE_DATE}]: entry={CFG['entry_thr_bps']}bps exit={CFG['exit_thr_bps']}bps "
          f"band=[{int(CFG['decision_lo_s'])},{int(CFG['decision_hi_s'])}]s atm<{CFG['atm_band']} "
          f"perp_taker={CFG['perp_taker_bps']}bps  hold-to-binary-settle")
    print(f"forward_start (exclusive): {FORWARD_START}   gate: >={GATE_MIN_DAYS} fwd days & pooled t>={GATE_T}")

    g = compute_gate(recs, asset=None)
    if g["ndays"] == 0:
        print("POOLED: CLOCK-NOT-STARTED -- no COMPLETE forward day (> "
              f"{FORWARD_START}, < today UTC) with a qualifying trade logged yet.")
    else:
        tstr = "nan" if math.isnan(g["t"]) else f"{g['t']:+.2f}"
        print(f"POOLED: {g['status']}  fwd-days={g['ndays']} (need >={GATE_MIN_DAYS})  "
              f"asset-day pts={g['n']} ({g['n_pos']} pos)  mean=${g['mean']:+.5f}/unit  "
              f"day-clustered t={tstr}  total=${g['total']:+.4f}")
        print(f"  days: {', '.join(g['days'])}")
    for asset in ASSETS_BASIS:
        ga = compute_gate(recs, asset=asset)
        if ga["ndays"] == 0:
            continue
        tstr = "nan" if math.isnan(ga["t"]) else f"{ga['t']:+.2f}"
        print(f"  [{asset}] {ga['status']}  fwd-days={ga['ndays']}  pts={ga['n']}  "
              f"mean=${ga['mean']:+.5f}/unit  t={tstr}")

    # ---- FAVLONG correlation (FIRST-CLASS OUTPUT: orthogonality verdict) ----
    print("\n=== ORTHOGONALITY: edge (a) vs FAVLONG (day-level P&L correlation) ===")
    pooled_rho, npts, lines = correlation_report(recs)
    ndistinct = len({r["day"] for r in recs
                     if r.get("edge") == EDGE and r.get("favlong_day_pnl") is not None})
    if npts < 6 or ndistinct < 3:
        rstr = "n/a" if pooled_rho is None else f"{pooled_rho:+.3f}"
        print(f"PENDING -- have {npts} asset-day pts over {ndistinct} distinct day(s); "
              f"need >=6 pts AND >=3 days before a verdict (a single day is just cross-asset noise). "
              f"provisional r={rstr}. Populates as forward days accrue.")
    else:
        rstr = "nan" if pooled_rho is None else f"{pooled_rho:+.3f}"
        verdict = "n/a"
        if pooled_rho is not None:
            if abs(pooled_rho) < 0.3:
                verdict = "LOW correlation -> looks like a genuine DIVERSIFIER (orthogonal to FAVLONG)"
            elif abs(pooled_rho) < 0.6:
                verdict = "MODERATE correlation -> partially overlaps FAVLONG; discount its diversification"
            else:
                verdict = "HIGH correlation -> likely a hedged FAVLONG restatement, NOT a diversifier"
        print(f"POOLED day-level Pearson r = {rstr} over {npts} asset-days -> {verdict}")
        for asset, n, rho in lines:
            rs = "n/a" if rho is None else f"{rho:+.3f}"
            print(f"  [{asset}] r={rs} over {n} days")

    # ---- edge (b) funding stub ----
    print("\n=== EDGE (b) funding-carry STUB ===")
    fr = funding_report(recs)
    if fr is None:
        print("no funding samples logged yet.")
    else:
        print(f"funding_rate over {fr['n']} samples: min={fr['min']} max={fr['max']}  "
              + ("ALL ZERO -> nothing to harvest; NO carry trade (revisit if this turns non-zero)."
                 if (fr['min'] == 0.0 and fr['max'] == 0.0) else
                 "NON-ZERO funding detected -> REVISIT edge (b) carry per design sec 2."))


# ---- runners -------------------------------------------------------------------------------------
def _score_and_attach(datasets, asset, day):
    rec = score_day_basis(datasets[asset], asset, day)
    rec["favlong_day_pnl"] = favlong_day_pnl(asset, day)
    return rec


def run(fetch=True):
    if fetch and not _git_fetch_gha_data():
        sys.stderr.write("WARN: could not fetch origin gha-data; scoring against local refs.\n")
    datasets = {}
    for asset in ASSETS_BASIS:
        try:
            datasets[asset] = build_perp(asset)
        except Exception as e:
            sys.stderr.write(f"build_perp({asset}) failed: {e}\n")
            datasets[asset] = {}
    recs = load_log()
    keys = {(r["edge"], r["asset"], r["day"]) for r in recs}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new = []
    for asset in ASSETS_BASIS:
        for day in sorted(datasets[asset]):
            if not (FORWARD_START < day < today):   # COMPLETE forward days only
                continue
            if (EDGE, asset, day) in keys:
                continue
            rec = _score_and_attach(datasets, asset, day)
            new.append(rec)
            keys.add((EDGE, asset, day))
            mp = rec["mean_pnl"]
            mps = "n/a" if mp is None else f"${mp:+.5f}/unit"
            print(f"scored {asset} {day}: n_trades={rec['n_trades']} mean={mps} "
                  f"day_pnl=${rec['day_pnl']:+.4f} favlong=${rec['favlong_day_pnl']}")
    if new:
        append_records(new)
        recs += new
        print(f"appended {len(new)} new record(s) to {LOG}")
    else:
        print("no new complete forward days to score (clock may not have started, or all logged).")
    print_report(recs)


def selftest(fetch=True):
    """Prove the pipeline runs end-to-end on whatever real data exists RIGHT NOW, ignoring the
    forward filter. Writes to a SCRATCH log (never the real forward log). NOT gate-eligible."""
    if fetch and not _git_fetch_gha_data():
        sys.stderr.write("WARN: could not fetch origin gha-data; using local refs.\n")
    if os.path.exists(SELFTEST_LOG):
        os.remove(SELFTEST_LOG)
    recs = []
    for asset in ASSETS_BASIS:
        try:
            data = build_perp(asset)
        except Exception as e:
            print(f"build_perp({asset}) failed: {e}")
            continue
        nwin = sum(len(v) for v in data.values())
        print(f"[selftest] {asset}: days={sorted(data)} aligned-windows={nwin}")
        for day in sorted(data):
            rec = score_day_basis(data, asset, day)
            rec["favlong_day_pnl"] = favlong_day_pnl(asset, day)
            recs.append(rec)
            mp = rec["mean_pnl"]
            mps = "n/a" if mp is None else f"${mp:+.5f}/unit"
            print(f"  {asset} {day}: n_trades={rec['n_trades']} mean={mps} "
                  f"day_pnl=${rec['day_pnl']:+.4f} favlong_day_pnl={rec['favlong_day_pnl']} "
                  f"funding={rec['funding']}")
    append_records(recs, path=SELFTEST_LOG)
    print(f"\n[selftest] wrote {len(recs)} scratch record(s) to {SELFTEST_LOG} "
          "(NOT the forward log; NOT gate-eligible).")
    print("[selftest] --- report view of the scratch data (forward gate still PENDING by design) ---")
    print_report(recs)


def main():
    if "--report" in sys.argv[1:]:
        recs = load_log()
        if not recs:
            print(f"no log yet at {LOG} -- forward clock has not started.")
        print_report(recs)
        return
    if "--selftest" in sys.argv[1:]:
        selftest(fetch="--no-fetch" not in sys.argv[1:])
        return
    run(fetch="--no-fetch" not in sys.argv[1:])


if __name__ == "__main__":
    main()
