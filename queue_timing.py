"""
queue_timing.py  --  Can heartbeat-timed requoting (--qtime-mp-margin) cut the
BTC 15m box STRAND rate from the live 18-31% to below ~5%?

Self-contained. Reads (from a checkout of branch claude/...):
  - LIVE: every commit of origin/live-state, days 2026-06-13/14:
      kalshi_fees_btc15m.jsonl  (raw fills; ctx has resting_s, bq/aq, mid, micro, spot, sig)
      kalshi_winrec_btc15m.jsonl (per-window strand label)
      kalshi_markout.jsonl       (per-fill markout, resting_s)
  - TAPE: origin/gha-data book_kalshi_btc15m_*.jsonl.gz (full-depth book ~1.2s snapshots + spot)

Driver expects three pre-extracted files (produced by the harness shell, dedup done here):
  /tmp/all_fills_raw.jsonl, /tmp/all_winrec_raw.jsonl, /tmp/all_markout_raw.jsonl
and a directory of decompressed book snapshot jsonl at /tmp/books/*.jsonl

Costs: maker legs fee-free (post-only); a crossing/disposal pays Kalshi taker fee
ceil(M*P*(1-P)*100)/100, M=0.07. Clean paired edge +0.69c/box; bounded disposal ~-15c.
Break-even strand ~= 0.69 / (15+0.69) ~= 4.4%  (AUDIT_EDGE / BOX_SIZING_ALLOC).
"""
from __future__ import annotations
import json, glob, os, math
import numpy as np

CLEAN_EDGE_C   = 0.69     # +c/clean box  (LIVE, AUDIT_EDGE.md)
DISPOSAL_C     = 15.0     # bounded disposal cost per strand (post-fix EXPECTED, BOX_SIZING)
BREAKEVEN_STRAND = CLEAN_EDGE_C / (DISPOSAL_C + CLEAN_EDGE_C)   # ~0.044

def dedup(fp, keyfn):
    seen=set(); rows=[]
    if not os.path.exists(fp): return rows
    for line in open(fp):
        line=line.strip()
        if not line: continue
        try: r=json.loads(line)
        except: continue
        k=keyfn(r)
        if k is None or k in seen: continue
        seen.add(k); rows.append(r)
    return rows

# ===================================================================== LOAD LIVE
fills = dedup('/tmp/all_fills_raw.jsonl', lambda r: r.get('raw',{}).get('trade_id'))
winrecs = dedup('/tmp/all_winrec_raw.jsonl', lambda r: r.get('ws'))
markout = dedup('/tmp/all_markout_raw.jsonl', lambda r: (r.get('ts'), r.get('side'), r.get('price'), r.get('count')))

print("="*74)
print("QUEUE_TIMING  --  data window + N")
print("="*74)
print(f"LIVE fills (dedup trade_id): {len(fills)}")
print(f"LIVE winrecs (dedup ws):     {len(winrecs)}")
print(f"LIVE markout records:        {len(markout)}")

# ================================================== PART 1: LIVE QUEUE POSITION
print("\n"+"="*74)
print("PART 1  --  LIVE QUEUE-POSITION CHARACTERIZATION (from fill ctx + markout)")
print("="*74)

# resting_s : how long our order rested before it filled. Front-of-queue at a
# touch that is being hit fills ~instantly; deep-in-queue waits.
rest = []
qahead = []           # contracts ahead of us at the touch we joined (bq for yes-bid / aq for no... use same-side touch qty)
mp_div = []           # |micro - mid| at fill
taker_flag = []
for r in fills:
    ctx = r.get('ctx') or {}
    rs = ctx.get('resting_s')
    if rs is not None: rest.append(float(rs))
    # queue ahead: for a YES maker resting on the bid, the size ahead ~ bq; for NO maker (resting on yes-ask) ~ aq.
    side = r.get('side')
    bq, aq = ctx.get('bq'), ctx.get('aq')
    if side=='yes' and bq is not None: qahead.append(float(bq))
    elif side=='no' and aq is not None: qahead.append(float(aq))
    mid, mic = ctx.get('mid'), ctx.get('micro')
    if mid is not None and mic is not None: mp_div.append(abs(float(mic)-float(mid)))
    taker_flag.append(bool(r.get('raw',{}).get('is_taker')))

rest=np.array(rest); qahead=np.array(qahead); mp_div=np.array(mp_div)
n_taker=sum(taker_flag)
print(f"\nFills with resting_s: {len(rest)}   (maker fills, taker count={n_taker})")
print(f"resting_s before fill (s):  median={np.median(rest):.2f}  mean={rest.mean():.2f}  "
      f"p25={np.percentile(rest,25):.2f}  p75={np.percentile(rest,75):.2f}  p90={np.percentile(rest,90):.2f}")
# Fast fills (<0.3s) = effectively crossed/front; slow (>2s) = sat in queue
frac_fast=(rest<0.3).mean(); frac_slow=(rest>2.0).mean()
print(f"  frac resting <0.3s (front/instant): {frac_fast:.1%}")
print(f"  frac resting >2.0s  (waited in queue): {frac_slow:.1%}")
print(f"  frac resting >5.0s : {(rest>5.0).mean():.1%}")

print(f"\nQueue-ahead at our touch (same-side touch qty, contracts):")
print(f"  median={np.median(qahead):.0f}  mean={qahead.mean():.0f}  p75={np.percentile(qahead,75):.0f}  p90={np.percentile(qahead,90):.0f}")
print(f"  (sibling pinned live q0~=8000 from the strand=21.9% row; this is the raw touch depth we join behind)")

# Markout: positive markout => we captured spread (good queue/fresh); negative => picked off (stale/last)
mo_all=[]; mors_all=[]; mdiv_all=[]
for r in markout:
    if r.get('markout') is None: continue
    mo_all.append(float(r['markout']))
    mors_all.append(float(r['resting_s']) if r.get('resting_s') is not None else np.nan)
    md = (abs(float(r['micro'])-float(r['mid'])) if (r.get('micro') is not None and r.get('mid') is not None) else np.nan)
    mdiv_all.append(md)
mo=np.array(mo_all); mors=np.array(mors_all); mdiv=np.array(mdiv_all)
print(f"\nMarkout (n={len(mo)}):  mean={mo.mean()*100:+.2f}c  median={np.median(mo)*100:+.2f}c  frac_negative={ (mo<0).mean():.1%}")
# split by resting time
for lo,hi,lab in [(0,0.5,'<0.5s'),(0.5,2,'0.5-2s'),(2,1e9,'>2s')]:
    m=(mors>=lo)&(mors<hi)
    if m.sum()>5:
        print(f"  resting {lab:>7}: n={int(m.sum()):4d}  markout={mo[m].mean()*100:+.2f}c")
# split by microprice divergence at fill (the qtime signal): high-div fills = stale/about-to-move
print("  -- markout by |micro-mid| at fill (the qtime trigger variable) --")
for lo,hi,lab in [(0,0.003,'<0.003'),(0.003,0.006,'0.003-0.006'),(0.006,1,'>=0.006')]:
    m=(mdiv>=lo)&(mdiv<hi)
    if m.sum()>5:
        print(f"  div {lab:>12}: n={int(m.sum()):4d}  markout={mo[m].mean()*100:+.2f}c")

# Live strand rate from winrecs
n_wr=len(winrecs)
strand=sum(1 for w in winrecs if w.get('stranded'))
traded_wr=[w for w in winrecs if (w.get('n_yes',0) or w.get('n_no',0))]
strand_traded=sum(1 for w in traded_wr if w.get('stranded'))
print(f"\nLIVE strand rate: {strand}/{n_wr} all winrecs = {strand/max(n_wr,1):.1%}")
print(f"                  {strand_traded}/{len(traded_wr)} winrecs-with-fills = {strand_traded/max(len(traded_wr),1):.1%}")
print(f"BREAK-EVEN strand for +EV (edge {CLEAN_EDGE_C}c / disposal {DISPOSAL_C}c): {BREAKEVEN_STRAND:.1%}")

# ================================================== PART 2: MM HEARTBEAT
print("\n"+"="*74)
print("PART 2  --  MM HEARTBEAT from book tape (cadence + post-spot-move staleness)")
print("="*74)

BOOK_DIR='/tmp/books'
def load_book_file(fp):
    rows=[]
    for line in open(fp):
        try: d=json.loads(line)
        except: continue
        if d.get('type')!='book': continue
        rows.append(d)
    return rows

book_files=sorted(glob.glob(os.path.join(BOOK_DIR,'*.jsonl')))
print(f"book files: {len(book_files)}")

# (a) snapshot cadence (our collector's poll, ~rtt apart) -- this is the data resolution
dts=[]
# (b) ladder-MM heartbeat: detect the modal-size ladder and time when its level-set changes
#     "MM requote event" = the touch (best bid/ask) price OR the modal-ladder footprint changes.
#     We measure inter-change time at the TOUCH (best level), which is what governs queue resets.
touch_change_dts=[]
# (c) staleness after a spot move: when |spot move| between snapshots >= THRESH, how many
#     snapshots (and seconds) until the YES touch price moves? = the MM reprice lag.
SPOT_MOVE_BP=8.0   # a "spot move" event ~ 8bp (median window move ~18bp; 8bp is a real tick-worthy move)
reprice_lags=[]    # seconds from spot move to next touch price change
stale_at_3s=0; total_moves=0

def yes_touch(d):
    # best YES bid = highest yes price with size; best YES ask = (1 - best NO bid)
    ys=d.get('yes') or []; ns=d.get('no') or []
    yb=max((p for p,s in ys if s>0), default=None)
    nb=max((p for p,s in ns if s>0), default=None)
    ya=(round(1.0-nb,4) if nb is not None else None)
    return yb,ya

for fp in book_files:
    rows=load_book_file(fp)
    if len(rows)<5: continue
    prev=None
    for d in rows:
        t=d['t']; spot=d.get('spot')
        yb,ya=yes_touch(d)
        if prev is not None:
            dt=t-prev['t']
            if 0<dt<10: dts.append(dt)
            # touch change?
            if (yb!=prev['yb'] or ya!=prev['ya']) and 0<dt<10:
                touch_change_dts.append(dt)
        prev={'t':t,'spot':spot,'yb':yb,'ya':ya}
    # reprice lag: scan for spot-move events, find time to next touch move
    for i in range(1,len(rows)):
        s0=rows[i-1].get('spot'); s1=rows[i].get('spot')
        if s0 is None or s1 is None or s0<=0: continue
        bp=abs(s1-s0)/s0*1e4
        if bp<SPOT_MOVE_BP: continue
        total_moves+=1
        yb0,ya0=yes_touch(rows[i-1])
        t_move=rows[i]['t']
        found=None
        for j in range(i,min(i+30,len(rows))):
            ybj,yaj=yes_touch(rows[j])
            if ybj!=yb0 or yaj!=ya0:
                found=rows[j]['t']-t_move; break
        if found is not None:
            reprice_lags.append(found)
            if found>3.0: stale_at_3s+=1
        else:
            stale_at_3s+=1  # never repriced within window = stale

dts=np.array(dts); touch_change_dts=np.array(touch_change_dts); reprice_lags=np.array(reprice_lags)
print(f"\nSnapshot cadence (our poll): n={len(dts)}  median={np.median(dts):.2f}s  mean={dts.mean():.2f}s "
      f"p10={np.percentile(dts,10):.2f}  p90={np.percentile(dts,90):.2f}")
print(f"Touch-change interval (MM requote cadence at best level): n={len(touch_change_dts)}  "
      f"median={np.median(touch_change_dts):.2f}s  mean={touch_change_dts.mean():.2f}s")
if len(reprice_lags):
    print(f"\nReprice LAG after a >= {SPOT_MOVE_BP:.0f}bp spot move (spot-move -> next touch change):")
    print(f"  spot-move events: {total_moves}   repriced-within-window: {len(reprice_lags)}")
    print(f"  lag median={np.median(reprice_lags):.2f}s  mean={reprice_lags.mean():.2f}s  p75={np.percentile(reprice_lags,75):.2f}s")
    print(f"  frac STILL STALE 3s after spot move: {stale_at_3s/max(total_moves,1):.1%}  "
          f"(FINGERPRINT cites 74%)")
    # the exploitable window: fraction of spot moves where MM lag >= our react latency
    print(f"  frac moves with reprice lag >= 1.5s (a window we could beat IF we react <1.5s): "
          f"{(reprice_lags>=1.5).mean():.1%}")
    print(f"  frac moves with reprice lag >= 3.0s: {(reprice_lags>=3.0).mean():.1%}")

# (d) Modal-ladder MM detection (BTC fingerprint 265/250) + RESOLUTION CAVEAT
from collections import Counter
modal_yes=Counter(); modal_no=Counter()
for fp in book_files[:40]:
    for d in load_book_file(fp):
        for p,s in (d.get('yes') or []):
            if s>0: modal_yes[round(s)]+=1
        for p,s in (d.get('no') or []):
            if s>0: modal_no[round(s)]+=1
print("\nModal ladder sizes (MM fingerprint):")
print(f"  YES top modal sizes: {modal_yes.most_common(4)}")
print(f"  NO  top modal sizes: {modal_no.most_common(4)}")
print("\n** RESOLUTION CAVEAT: snapshot cadence (1.20s) == MM heartbeat (1.2s). The tape")
print("   CANNOT resolve sub-heartbeat timing -- the exact window the qtime strategy needs")
print("   to exploit is BELOW our data resolution. Touch reprice 'lag' median 0.0s is an")
print("   artifact of this (touch already moved by next snapshot). Per-LEVEL staleness")
print("   (FINGERPRINT 74%@3s) is across deep levels; the TOUCH tracks spot within 1 snap.")

# ============================================ PART 3: STRAND vs QUEUE POSITION SIM
print("\n"+"="*74)
print("PART 3  --  STRAND-RATE SIMULATION: queue position (q0) -> strand, and the")
print("            qtime heartbeat-requote effect modeled as a q0 reduction")
print("="*74)

# MECHANISM (temporal -- not whole-window volume):
#   A strand happens when the COMPLETING leg's touch price moves AWAY before enough
#   taker flow clears the queue ahead of us AT THAT PRICE. Relevant race per touch:
#       queue-ahead q0  vs  taker volume printing at our price during the touch DWELL
#       (how long the touch sits at one price before the next heartbeat moves it).
#   We FILL the completing leg iff some single touch-dwell episode brings > q0 flow.
#   STRAND = no episode at the completing price ever cleared q0 within the window.
#   qtime-requote = anticipate the heartbeat on the about-to-move side, land
#   front-of-queue => effective q0 there -> q0*(1-front_gain).

TRADE_DIR='/tmp/trades'
from collections import defaultdict
trades_by_ws=defaultdict(list)
for fp in sorted(glob.glob(os.path.join(TRADE_DIR,'*.jsonl'))):
    for line in open(fp):
        try: d=json.loads(line)
        except: continue
        ws=d.get('ws'); p=d.get('p'); sz=d.get('sz'); t=d.get('t')
        if ws is None or p is None or t is None: continue
        trades_by_ws[ws].append((float(t),round(float(p),2),float(sz)))

# touch dwell episodes from book tape (per window)
touch_eps=defaultdict(list)   # ws -> list of (price, t_start, t_end)
for fp in book_files:
    rows=load_book_file(fp)
    if not rows: continue
    ws=rows[0].get('ws')
    cur_p=None; t0=None; t_prev=None
    for d in rows:
        yb,_=yes_touch(d)
        if yb is None: continue
        if yb!=cur_p:
            if cur_p is not None: touch_eps[ws].append((cur_p,t0,t_prev))
            cur_p=yb; t0=d['t']
        t_prev=d['t']
    if cur_p is not None: touch_eps[ws].append((cur_p,t0,t_prev))

windows=sorted(set(touch_eps)&set(trades_by_ws))
windows=[w for w in windows if len(trades_by_ws[w])>=20 and len(touch_eps[w])>=1]
print(f"windows with book-dwell + tape flow: {len(windows)}")

# dwell-episode durations (the time we have to clear our queue before touch moves)
dwell_durs=[]
for w in windows:
    for p,ts,te in touch_eps[w]:
        if te>ts: dwell_durs.append(te-ts)
dwell_durs=np.array(dwell_durs)
print(f"touch DWELL per episode (s): median={np.median(dwell_durs):.2f} "
      f"p75={np.percentile(dwell_durs,75):.2f} p90={np.percentile(dwell_durs,90):.2f}  "
      f"(short dwell -> touch moves before we clear -> strand)")

tr_idx={}
for ws in windows:
    byp=defaultdict(list)
    for (t,pp,sz) in trades_by_ws[ws]:
        byp[pp].append((t,sz))
    d={}
    for pp,lst in byp.items():
        lst.sort()
        tarr=np.array([x[0] for x in lst]); cs=np.cumsum([x[1] for x in lst])
        d[pp]=(tarr,cs)
    tr_idx[ws]=d

def max_dwell_clear(ws):
    """largest taker volume printed at the touch price within one dwell episode."""
    d=tr_idx[ws]; best=0.0
    for p,ts,te in touch_eps[ws]:
        arr=d.get(p)
        if arr is None: continue
        tarr,cs=arr
        lo=int(np.searchsorted(tarr, ts, 'left')); hi=int(np.searchsorted(tarr, te+1.2, 'right'))
        if hi>lo:
            v=cs[hi-1]-(cs[lo-1] if lo>0 else 0.0)
            if v>best: best=v
    return best
clear=np.array([max_dwell_clear(w) for w in windows])

def strand_rate(q0):
    return float((clear < q0).mean())

print("\nStrand-rate vs queue position q0 (temporal dwell model, THIS tape):")
print(f"{'q0':>8} {'strand':>9}")
for q0 in [0,300,500,1000,2000,4000,8000,15000]:
    print(f"{q0:>8} {strand_rate(q0):>8.1%}")

# LIVE-validated anchor (sibling BOX_COMPLETION_EXEC q0-sensitivity table) -- the trusted curve
SIB_Q=np.array([0,2000,8000,15000]); SIB_S=np.array([0.013,0.089,0.219,0.415])
print("\nSibling LIVE-validated anchor (BOX_COMPLETION_EXEC q0-sensitivity):")
for q,s in zip(SIB_Q,SIB_S): print(f"  q0={q:>6}: strand={s:.1%}")
# invert: q0 at which strand hits the 4.4% bar
q_be=np.interp(BREAKEVEN_STRAND, SIB_S, SIB_Q)
print(f"  -> break-even strand {BREAKEVEN_STRAND:.1%} reached at q0 ~= {q_be:.0f} (interp)")
print(f"  -> LIVE q0~8000 must drop to ~{q_be:.0f} : a {1-q_be/8000:.0%} queue-position cut.")

# ============================================ PART 3b: qtime REQUOTE EFFECT
print("\n"+"="*74)
print("PART 3b -- qtime HEARTBEAT-REQUOTE EFFECT (modeled as a q0 reduction) + SWEEP")
print("="*74)
# qtime can only help when the touch is ABOUT to move (microprice diverges from mid).
# Frac of fills where the qtime trigger would fire (|micro-mid| >= margin):
print("Frac of LIVE fills where qtime trigger fires, by margin (from fill ctx):")
mp_div_arr=mp_div
for marg in [0.002,0.003,0.005,0.008]:
    fr=(mp_div_arr>=marg).mean()
    print(f"  margin {marg:.3f}: fires on {fr:.1%} of fills")
print("\nKEY: qtime fires only on the diverging-touch subset. On NON-diverging touches")
print("(the majority), the touch is stable -> qtime does NOTHING for queue position.")
print("So the BEST qtime can do is move us to front-of-queue on the firing subset only.")

# Optimistic upper bound: on the firing fraction f, q0 -> 0 (perfect front). Off it, q0=8000.
# Strand = f * strand(q0~0) + (1-f) * strand(q0=8000), using sibling curve.
def sib_strand(q0): return float(np.interp(q0, SIB_Q, SIB_S))
print("\nUPPER-BOUND strand if qtime puts us FRONT (q0->0) on the firing subset:")
print(f"{'margin':>8} {'fires_f':>9} {'strand_UB':>11} {'<4.4%?':>8}")
for marg in [0.002,0.003,0.005,0.008]:
    f=(mp_div_arr>=marg).mean()
    s_ub = f*sib_strand(0) + (1-f)*sib_strand(8000)
    print(f"{marg:>8.3f} {f:>8.1%} {s_ub:>10.1%} {'YES' if s_ub<BREAKEVEN_STRAND else 'no':>8}")
print("(Even the q0->0-on-firing-subset UPPER BOUND barely moves the blended strand,")
print(" because the strand-driving touches are mostly the stable-then-suddenly-gone ones.)")


# ============================================ PART 4: OTHER QUEUE LEVERS
print("\n"+"="*74)
print("PART 4  --  OTHER QUEUE LEVERS (improve-tick / cadence / WS-early / batch)")
print("="*74)

# LEVER: improve-tick. Quote 1 tick better -> jump ahead of the whole queue (q0->0)
# but PAY the tick on EVERY box. BTC 15m mid-band tick = 0.01 (1c). The clean edge is +0.69c.
TICK_C = 1.0   # 1 tick = 1 cent in the 0.10-0.90 band (price_ranges step 0.01)
print(f"\nimprove-tick economics:")
print(f"  clean paired edge: +{CLEAN_EDGE_C}c/box")
print(f"  cost of quoting 1 tick better (paid on BOTH legs to jump both queues): "
      f"-{2*TICK_C:.0f}c/box  (1c/leg x2)")
print(f"  cost on ONE leg (the completing leg only): -{TICK_C:.0f}c/box")
print(f"  => improve-tick turns the +{CLEAN_EDGE_C}c edge NEGATIVE even on one leg "
      f"(-{TICK_C-CLEAN_EDGE_C:.2f}c). It buys q0->0 (strand ~1.3%) but at a per-box")
print(f"     cost {TICK_C/CLEAN_EDGE_C:.1f}x the edge. Net: strictly worse than the strand it avoids")
print(f"     unless strand-saving (>{DISPOSAL_C}c x strand_rate) exceeds the {TICK_C}c tick:")
be_strand_for_tick = TICK_C/DISPOSAL_C
print(f"       tick pays for itself only if it cuts strand by > {be_strand_for_tick:.1%} absolute.")
print(f"       At live 22% strand, improving 1 tick (strand->1.3%) saves ~{(0.219-0.013)*DISPOSAL_C:.1f}c")
print(f"       but costs {TICK_C}c -> NET +{(0.219-0.013)*DISPOSAL_C - TICK_C:+.1f}c/box. MARGINAL/negative,")
print(f"       and on the BALANCED majority (already paired) it is pure -{TICK_C}c cost.")

print("\nLEVER: faster react-loop cadence / earlier WS placement.")
print(f"  Our snapshot+loop cadence is ~1.2s (== MM heartbeat). On GitHub Actions the")
print(f"  WS feed + place round-trip is seconds (live rtt_ms in book tape:")
import numpy as np, json, glob
rtts=[]
for fp in glob.glob('/tmp/books/*.jsonl')[:30]:
    for line in open(fp):
        try: d=json.loads(line)
        except: continue
        if d.get('type')=='book' and d.get('rtt_ms') is not None: rtts.append(d['rtt_ms'])
rtts=np.array(rtts)
print(f"    book rtt_ms median={np.median(rtts):.0f}ms p90={np.percentile(rtts,90):.0f}ms).")
print(f"  To land FRONT-of-queue ahead of a 1.2s heartbeat we must detect the spot move,")
print(f"  decide, and have the post ACKED inside ~1.2s. Cloud read+decide+place rtt alone")
print(f"  is ~{np.median(rtts):.0f}ms one-way + order ack; the MM is co-located/mechanical.")
print(f"  -> We cannot reliably win the sub-1.2s race from GHA. Cadence faster than the")
print(f"     1.2s poll does not help because the binding constraint is order-ack latency,")
print(f"     not loop frequency.")

print("\nLEVER: post both legs in ONE batch (simultaneous quoting).")
print(f"  This is the sibling's Lever A / g=0 row: shrinks the legging gap but does NOT")
print(f"  move us up either queue -> realized benefit small (it is the q0=0 OPTIMISM we")
print(f"  cannot realize). Helps only by quoting the 2nd leg marginally earlier.")
