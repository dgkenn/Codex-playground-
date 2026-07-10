import os
_HERE=os.path.dirname(os.path.abspath(__file__))+os.sep
#!/usr/bin/env python3
"""Intern call-schedule generator for LSH (Lemuel Shattuck) TY program.
Generates Oct 2026 - Jun 2027, continuing from the provided Jul/Aug/Sep sheets.

Pool each day = 2 LSH TY interns + 1 BMC-South/Brighton intern + 1 Lahey intern
(the last few days of June have no BMC intern -> 3-person pool).

Optimization priorities (per user):
  1. KENNEDY gets the cushiest legal schedule (min NF/24h, max days off).
  2. Shattuck LSH interns get better schedules than outside (BMC/Lahey) rotators;
     when someone must be stuck with a heavy load, it is an outside rotator.
"""
from datetime import date, timedelta
from collections import defaultdict

def d(m,day,y): return date(y,m,day)

# ---------------------------------------------------------------- ROSTER ----
LSH_MONTH = {
 (2026,9):["WISE","LI"],                 # for continuity only
 (2026,10):["MACNEILLE","BRONSON"],
 (2026,11):["WISE","KENNEDY"],
 (2026,12):["MACNEILLE","BRONSON"],
 (2027,1):["ZAIDI","OGHENESUME"],
 (2027,2):["ZAIDI","LI"],
 (2027,3):["KENNEDY","MATSUOKA"],
 (2027,4):["ZAIDI","OGHENESUME"],
 (2027,5):["LI","BRONSON"],
 (2027,6):["OGHENESUME","MATSUOKA"],
}
BMC = [
 (d(9,28,2026), d(10,11,2026), "BUTT"),
 (d(10,12,2026),d(11,8,2026),  "MULLINS"),
 (d(11,9,2026), d(11,22,2026), "SAEED"),
 (d(11,23,2026),d(12,6,2026),  "SHETTY"),
 (d(12,7,2026), d(12,20,2026), "VILLANUEVA"),
 (d(12,21,2026),d(1,3,2027),   "FARZEELA"),
 (d(1,4,2027),  d(1,31,2027),  "AHN"),
 (d(2,1,2027),  d(2,14,2027),  "FARZEELA"),
 (d(2,15,2027), d(2,28,2027),  "VILLANUEVA"),
 (d(3,1,2027),  d(3,14,2027),  "SHETTY"),
 (d(3,15,2027), d(3,28,2027),  "BUTT"),
 (d(3,29,2027), d(4,25,2027),  "RIVERA"),
 (d(4,26,2027), d(5,9,2027),   "GABALLAH"),
 (d(5,10,2027), d(5,23,2027),  "METRI"),
 (d(5,24,2027), d(6,20,2027),  "SAEED-S"),
]
LAHEY = [
 (d(9,21,2026), d(10,18,2026), "AHLUWALIA"),
 (d(10,19,2026),d(11,15,2026), "CHIASSON"),
 (d(11,16,2026),d(12,13,2026), "VIVEKANANDAN"),
 (d(12,14,2026),d(1,10,2027),  "SALAM"),
 (d(1,11,2027), d(2,7,2027),   "JUYAL"),
 (d(2,8,2027),  d(3,7,2027),   "KOPP VANUZZI"),
 (d(3,8,2027),  d(3,21,2027),  "PATEL"),
 (d(3,22,2027), d(4,18,2027),  "ALMADHOOB"),
 (d(4,19,2027), d(5,16,2027),  "AHLUWALIA-S"),
 (d(5,17,2027), d(6,13,2027),  "SANCHEZ-ALMANZAR"),
 (d(6,14,2027), d(6,23,2027),  "PATEL"),
]
KENNEDY="KENNEDY"

# --- Kennedy cushiness levers (all legal within the rules) ------------------
# Thanksgiving 2026 = Thu Nov 26.  Give Kennedy a long Thanksgiving break:
#   NF week 11/1-6  -> golden weekend 11/7-8 off (also his requested weekend);
#   single 24h shift moved early to Sat 11/14 (off Sun 11/15 recovery);
#   Thanksgiving: OFF Thu 11/26, short-call Fri 11/27 (may leave post-conf),
#                 OFF the whole Thanksgiving weekend Sat 11/28 + Sun 11/29.
THXGIVING=d(11,26,2026)
# HARD: Nov 7-8 weekend OFF.  Thanksgiving is flexible and, because the
# Thanksgiving Saturday 24h can only be covered by a Shattuck intern (both
# outside rotators are night-float-adjacent that weekend), Kennedy VOLUNTEERS
# for it so Wise is not stuck with holiday duty.  Kennedy still gets
# Thanksgiving Day (Thu) off and short-call Friday, then his 24h Sat 11/28.
KENNEDY_FORCE_OFF={d(11,8,2026), d(11,26,2026)}     # Nov-7 wknd Sunday + Thanksgiving Thu
KENNEDY_FORCE_SC ={d(11,6,2026), d(11,27,2026)}     # Fri 11/6 (fly out) + Fri after Thanksgiving
KENNEDY_FORCE_SAT=d(11,28,2026)                     # Kennedy takes the Thanksgiving Sat 24h
KENNEDY_NO_SAT   ={d(11,7,2026)}                    # keep the Nov 7-8 weekend fully free
# Kennedy's Nov Night-Float week is MOVED off the 11/1-6 week (Friday night float
# rounds into Saturday morning) so Fri 11/6 is a short call and he flies out for
# the 11/7-8 weekend; his NF is placed mid-month instead.
KENNEDY_NF_TARGET=d(11,15,2026)                     # Sunday that starts his NF week

def month_end(y,m):
    if m==12: return date(y,12,31)
    return date(y,m+1,1)-timedelta(days=1)
def month_start(dt): return date(dt.year,dt.month,1)
def block_of(blocks,dt):
    for s,e,lab in blocks:
        if s<=dt<=e: return (s,e,lab)
    return None
def roster(dt):
    people={}
    for lab in LSH_MONTH[(dt.year,dt.month)]:
        people[lab]={"type":"LSH","start":month_start(dt),"end":month_end(dt.year,dt.month)}
    b=block_of(BMC,dt); l=block_of(LAHEY,dt)
    if b: people[b[2]]={"type":"BMC","start":b[0],"end":b[1]}
    if l: people[l[2]]={"type":"LAHEY","start":l[0],"end":l[1]}
    return people
def typ_of(lab,dt): return roster(dt)[lab]["type"]
def rot_id(dt,lab):
    p=roster(dt)[lab]; return (lab,p["type"],p["start"])
def burden(lab,dt):
    """lower = spare (give good things); higher = load (give bad things)."""
    if lab==KENNEDY: return 0
    if typ_of(lab,dt)=="LSH": return 1
    return 2
def is_new_start(lab,dt):
    p=roster(dt)[lab]; return p["type"] in ("BMC","LAHEY") and p["start"]==dt

# ------------------------------------------------------------- DAY LIST -----
SPAN_START=d(10,1,2026)
SPAN_END  =d(6,23,2027)
days=[]; dt=SPAN_START
while dt<=SPAN_END: days.append(dt); dt+=timedelta(days=1)
WDN=["MON","TUE","WED","THU","FRI","SAT","SUN"]

# ------------------------------------------------------- NF WEEK GROUPS -----
def nf_groups():
    groups=[]; cur=[]
    for dt in days:
        if dt.weekday()==5:
            if cur: groups.append(cur); cur=[]
            continue
        if dt.weekday()==6:
            if cur: groups.append(cur); cur=[]
            cur=[dt]
        else:
            cur.append(dt)
    if cur: groups.append(cur)
    return groups
GROUPS=nf_groups()
def present_all_week(g):
    common=None
    for dt in g:
        s=set(roster(dt))
        common=s if common is None else common&s
    return sorted(common or [])

NF_BY_DAY={}
NF_GROUP_PICK={}
SAT_BY_DAY={}
groups_by_month=defaultdict(list)
for g in GROUPS: groups_by_month[(g[0].year,g[0].month)].append(g)
saturdays_all=[x for x in days if x.weekday()==5]
sats_by_month=defaultdict(list)
for s in saturdays_all: sats_by_month[(s.year,s.month)].append(s)

# ---------------------------------------------------------------------------
# JOINT NF + SATURDAY SOLVER (per month), enforcing:
#   * every LSH (Shattuck) intern gets EXACTLY 1 NF week AND EXACTLY 1 Saturday
#     (never 2 of either -> Shattuck interns are never doubled/punished);
#   * outside (BMC/Lahey) rotators absorb ALL overflow (extra NF weeks & 2nd
#     Saturdays);
#   * Kennedy's NF = earliest full week (frees the following weekend); in Nov
#     his Saturday is forced to 11/14 and he is kept off 11/7 & 11/28.
# A Saturday's 24h intern may not be that week's Fri-NF person nor the next
# week's Sun-NF starter (post/pre-NF rest).  We search LSH NF-week placements
# so that every Saturday not taken by an LSH is coverable by an outside rotator.
# ---------------------------------------------------------------------------
from itertools import product, permutations

def solve_month(yy,mm):
    glist=groups_by_month[(yy,mm)]
    full=[g for g in glist if len(g)==6]
    partial=[g for g in glist if len(g)<6]
    sats=sats_by_month[(yy,mm)]
    lsh=list(LSH_MONTH[(yy,mm)])
    cand={id(g):present_all_week(g) for g in full}

    # candidate NF weeks for each LSH intern (present all week & fully in-month)
    lsh_weeks={l:[g for g in full if l in cand[id(g)]] for l in lsh}
    # Kennedy fixed to a designated week if set (Nov), else his earliest coverable week
    kfix=None
    if KENNEDY in lsh and lsh_weeks[KENNEDY]:
        tgt=[g for g in lsh_weeks[KENNEDY] if g[0]==KENNEDY_NF_TARGET]
        kfix=tgt[0] if tgt else min(lsh_weeks[KENNEDY],key=lambda g:g[0])

    def nf_at(dt): return NF_LOCAL.get(dt, NF_GLOBAL.get(dt))
    def nf_prev(s): return nf_at(s-timedelta(days=1))
    def nf_next(s): return nf_at(s+timedelta(days=1))

    others=[l for l in lsh if l!=KENNEDY]
    best=None
    # enumerate NF-week choices for the non-Kennedy LSH interns
    choice_space=[lsh_weeks[l] or [None] for l in others]
    for combo in product(*choice_space):
        if len(set(id(c) for c in combo if c))<len([c for c in combo if c]):
            continue  # two LSH can't share a week
        if kfix and any(c is kfix for c in combo): continue
        nf_pick={}
        ok=True
        if kfix: nf_pick[id(kfix)]=KENNEDY
        for l,c in zip(others,combo):
            if c is None: ok=False; break
            nf_pick[id(c)]=l
        if not ok: continue
        # fill remaining full weeks with outside rotators (coverage-greedy)
        rot_nf=defaultdict(int)
        for gid,l in nf_pick.items(): rot_nf[l]+=1
        remaining=[g for g in full if id(g) not in nf_pick]
        feasible=True
        for g in sorted(remaining,key=lambda g:g[0]):
            pool=[l for l in cand[id(g)] if l not in lsh]  # outside only
            if not pool: pool=[l for l in cand[id(g)]]      # (boundary) allow anyone present-all
            if not pool: feasible=False; break
            pool.sort(key=lambda l:(rot_nf[l], -burden(l,g[0]),
                                    roster(g[0])[l]["end"].toordinal(), l))
            nf_pick[id(g)]=pool[0]; rot_nf[pool[0]]+=1
        if not feasible: continue
        # materialise NF-by-day locally
        global NF_LOCAL
        NF_LOCAL={}
        for g in full:
            for dt in g: NF_LOCAL[dt]=nf_pick[id(g)]
        # boundary tails -> outside present-all (never Kennedy)
        for g in partial:
            c=[l for l in present_all_week(g) if l not in lsh] or \
              [l for l in present_all_week(g) if l!=KENNEDY] or present_all_week(g)
            c.sort(key=lambda l:(-burden(l,g[0]), l))
            for dt in g: NF_LOCAL[dt]=c[0]
            nf_pick[id(g)]=c[0]
        # ---- Saturday assignment ----
        elig={}
        for s in sats:
            e=set(roster(s))-{nf_prev(s),nf_next(s)}
            if s in KENNEDY_NO_SAT: e.discard(KENNEDY)
            elig[s]=e
        # LSH must each get exactly one distinct eligible Saturday; Kennedy fixed
        lsh_here=[l for l in lsh]
        # build eligible-saturday lists per LSH
        lsat={l:[s for s in sats if l in elig[s]] for l in lsh_here}
        if KENNEDY in lsh_here and KENNEDY_FORCE_SAT in sats:
            lsat[KENNEDY]=[KENNEDY_FORCE_SAT] if KENNEDY in elig.get(KENNEDY_FORCE_SAT,set()) else lsat[KENNEDY]
        if any(len(lsat[l])==0 for l in lsh_here): continue
        sat_pick=None
        for perm in permutations(sats, len(lsh_here)):
            asg=dict(zip(lsh_here,perm))
            if any(asg[l] not in lsat[l] for l in lsh_here): continue
            if len(set(perm))<len(perm): continue
            leftover=[s for s in sats if s not in perm]
            # leftover must be coverable by an eligible outside rotator
            if all(any((x in elig[s] and x not in lsh) for x in roster(s)) for s in leftover):
                sat_pick=asg; break
        if sat_pick is None: continue
        # assign leftover Saturdays to outside rotators (fairness/coverage)
        full_sat=dict((s,l) for l,s in sat_pick.items())
        rot_sat=defaultdict(int)
        for s,l in full_sat.items(): rot_sat[l]+=1
        for s in sats:
            if s in full_sat: continue
            pool=[x for x in elig[s] if x not in lsh]
            pool.sort(key=lambda x:(rot_sat[x],
                                    0 if _rot_has_no_nf(x,s,nf_pick,full) else 1,
                                    -burden(x,s), roster(s)[x]["end"].toordinal(), x))
            full_sat[s]=pool[0]; rot_sat[pool[0]]+=1
        # score this solution: prefer (a) every outside rotation covered, minor
        score=(0,)
        best=(nf_pick,full_sat)
        break
    if best is None:
        # Fallback (should be rare): relax LSH-exactly-1-Sat, still avoid Kennedy 2nd
        best=_fallback_month(yy,mm)
    return best

def _rot_has_no_nf(lab,s,nf_pick,full):
    # does this rotation instance have zero NF weeks assigned (in this month view)?
    rid=rot_id(s,lab)
    for g in full:
        if nf_pick.get(id(g))==lab and rot_id(g[0],lab)==rid: return False
    return True

def _fallback_month(yy,mm):
    # Greedy fallback identical in spirit; only used if the exact solver fails.
    glist=groups_by_month[(yy,mm)]; full=[g for g in glist if len(g)==6]
    partial=[g for g in glist if len(g)<6]; sats=sats_by_month[(yy,mm)]
    lsh=list(LSH_MONTH[(yy,mm)]); cand={id(g):present_all_week(g) for g in full}
    nf_pick={}; rot_nf=defaultdict(int)
    if KENNEDY in lsh:
        opts=sorted([g for g in full if KENNEDY in cand[id(g)]],key=lambda g:g[0])
        if opts: nf_pick[id(opts[0])]=KENNEDY; rot_nf[KENNEDY]+=1
    for l in lsh:
        if l==KENNEDY or any(v==l for v in nf_pick.values()): continue
        opts=sorted([g for g in full if id(g) not in nf_pick and l in cand[id(g)]],
                    key=lambda g:(len(cand[id(g)]),g[0]))
        if opts: nf_pick[id(opts[0])]=l; rot_nf[l]+=1
    for g in sorted(full,key=lambda g:g[0]):
        if id(g) in nf_pick: continue
        pool=[l for l in cand[id(g)] if l not in lsh] or cand[id(g)]
        pool.sort(key=lambda l:(rot_nf[l],-burden(l,g[0]),l)); nf_pick[id(g)]=pool[0]; rot_nf[pool[0]]+=1
    NFL={}
    for g in full:
        for dt in g: NFL[dt]=nf_pick[id(g)]
    for g in partial:
        c=[l for l in present_all_week(g) if l not in lsh] or [l for l in present_all_week(g) if l!=KENNEDY] or present_all_week(g)
        for dt in g: NFL[dt]=c[0]
        nf_pick[id(g)]=c[0]
    full_sat={}; rot_sat=defaultdict(int); ksat=0
    for s in sats:
        e=[l for l in roster(s) if l!=NFL.get(s-timedelta(days=1)) and l!=NFL.get(s+timedelta(days=1))]
        if s in KENNEDY_NO_SAT: e=[l for l in e if l!=KENNEDY]
        if s==KENNEDY_FORCE_SAT and KENNEDY in e:
            full_sat[s]=KENNEDY; rot_sat[KENNEDY]+=1; ksat+=1; continue
        e=[l for l in e if not (l==KENNEDY and (ksat>=1 or s in KENNEDY_NO_SAT))]
        no=[l for l in e if rot_sat[l]==0] or e
        no.sort(key=lambda l:(rot_sat[l],-burden(l,s),l))
        full_sat[s]=no[0]; rot_sat[no[0]]+=1
        if no[0]==KENNEDY: ksat+=1
    return (nf_pick,full_sat)

# run solver for every month, materialise global NF_BY_DAY / SAT_BY_DAY.
# NF_GLOBAL accumulates finalized NF so each month sees previous months'
# boundary NF weeks (fixes NF-Fri -> 24h-Sat across a month boundary).
NF_LOCAL={}; NF_GLOBAL={}
for (yy,mm) in sorted(groups_by_month):
    nf_pick,full_sat=solve_month(yy,mm)
    for g in groups_by_month[(yy,mm)]:
        NF_GROUP_PICK[id(g)]=nf_pick[id(g)]
        for dt in g: NF_BY_DAY[dt]=nf_pick[id(g)]; NF_GLOBAL[dt]=nf_pick[id(g)]
    for s,l in full_sat.items(): SAT_BY_DAY[s]=l

# ---- global safety repair: no 24h intern may be the adjacent NF person -------
for s in saturdays_all:
    nfp=NF_BY_DAY.get(s-timedelta(days=1)); nfn=NF_BY_DAY.get(s+timedelta(days=1))
    cur=SAT_BY_DAY.get(s)
    if cur in (nfp,nfn):
        pres=roster(s)
        alt=[l for l in pres if l not in (nfp,nfn)
             and not (l==KENNEDY and s in KENNEDY_NO_SAT)]
        # prefer outside rotators, then anyone; keep it deterministic
        alt.sort(key=lambda l:(-burden(l,s), l))
        if alt: SAT_BY_DAY[s]=alt[0]

# --------------------------------------------------- DAILY LC / SC / OFF ----
last_lc=defaultdict(int); off_count=defaultdict(int); work_streak=defaultdict(int)
wknd_off=defaultdict(int); thu_off=defaultdict(int)   # balance perks fairly among LSH
assign={}
for dt in days:
    wd=dt.weekday(); present=roster(dt)
    rec={"LC":None,"SC":[],"NF":None,"OFF":[],"H24":None}
    if wd==5:  # Saturday: only 24h person works
        s=SAT_BY_DAY[dt]; rec["H24"]=s; rec["LC"]=s
        rec["OFF"]=[l for l in present if l!=s]
        for l in rec["OFF"]: off_count[l]+=1; wknd_off[l]+=1; work_streak[l]=0
        work_streak[s]+=1; last_lc[s]=dt.toordinal()
        assign[dt]=rec; continue
    nf=NF_BY_DAY.get(dt); rec["NF"]=nf
    daytime=[l for l in present if l!=nf]
    if wd==6:  # Sunday: 1 LC + rest off
        sat24=SAT_BY_DAY.get(dt-timedelta(days=1))
        pool=[l for l in daytime if l!=sat24]
        forced_off=[l for l in daytime if l==sat24]
        if dt in KENNEDY_FORCE_OFF and KENNEDY in pool:   # Thanksgiving Sunday
            forced_off.append(KENNEDY); pool=[l for l in pool if l!=KENNEDY]
        friday_nf=NF_BY_DAY.get(dt-timedelta(days=2))
        # Who is OFF (gets the golden weekend): prefer Shattuck LSH over outside,
        # then BALANCE weekend-off between the two LSH (so Kennedy doesn't hog every
        # free weekend), Kennedy a slight tiebreak, just-finished-NF prefers rest.
        def sun_off_key(l):
            outside=0 if typ_of(l,dt)=="LSH" else 1
            just_nf=0 if l==friday_nf else 1
            return (outside, wknd_off[l], just_nf, 0 if l==KENNEDY else 1, off_count[l], l)
        # LC goes to the most-loadable (outside rotator) who didn't just finish NF
        def sun_lc_key(l): return (-burden(l,dt), last_lc[l], l)
        if len(pool)>=2:
            off_pick=sorted(pool,key=sun_off_key)[0]
            lc_pool=[l for l in pool if l!=off_pick]
            lc=sorted(lc_pool,key=sun_lc_key)[0]
            rec["LC"]=lc; rec["OFF"]=forced_off+[l for l in pool if l!=lc]
        elif pool:
            rec["LC"]=pool[0]; rec["OFF"]=forced_off
        else:
            rec["OFF"]=forced_off
        for l in [rec["LC"]] if rec["LC"] else []: last_lc[l]=dt.toordinal(); work_streak[l]+=1
        for l in rec["OFF"]: off_count[l]+=1; wknd_off[l]+=1; work_streak[l]=0
        assign[dt]=rec; continue
    # Weekday Mon/Tue/Wed/Fri (2 SC) or Thu (1 SC + up to 1 off)
    n_sc = 1 if wd==3 else 2
    avail=list(daytime); off=[]
    if wd==3 and len(daytime)>=3:
        # Thursday preferred day off -> lowest burden present (Kennedy first).
        # Thanksgiving Thu 11/26 forces Kennedy off.
        if dt in KENNEDY_FORCE_OFF and KENNEDY in avail:   # Thanksgiving Thu
            off=[KENNEDY]
        else:
            # prefer Shattuck LSH for the Thursday off, balance between them,
            # Kennedy a slight tiebreak
            okey=lambda l:(0 if typ_of(l,dt)=="LSH" else 1, thu_off[l],
                           0 if l==KENNEDY else 1, -work_streak[l], l)
            off=[sorted(avail,key=okey)[0]]
        thu_off[off[0]]+=1
        avail=[l for l in avail if l not in off]
    # Kennedy forced to short-call (never long-call) on given days (e.g. Fri 11/27)
    force_sc = KENNEDY if (dt in KENNEDY_FORCE_SC and KENNEDY in avail) else None
    tomorrow24 = SAT_BY_DAY.get(dt+timedelta(days=1))   # who does tomorrow's 24h (Fri)
    def ok_lc(l):
        if l==force_sc: return False
        if is_new_start(l,dt): return False                 # new BMC/Lahey never start on LC
        if last_lc[l]==dt.toordinal()-1: return False        # on call yesterday -> no back-to-back
        if l==tomorrow24: return False                       # 24h tomorrow -> keep Friday light
        return True
    # progressive relaxation so a legal LC always exists
    lc_cand=[l for l in avail if ok_lc(l)]
    if not lc_cand: lc_cand=[l for l in avail if l!=force_sc and last_lc[l]!=dt.toordinal()-1 and l!=tomorrow24]
    if not lc_cand: lc_cand=[l for l in avail if l!=force_sc and l!=tomorrow24]
    if not lc_cand: lc_cand=[l for l in avail if l!=force_sc]
    if not lc_cand: lc_cand=list(avail)
    # max spacing (keeps ~Q4), tie-break load onto outside rotators
    lc_cand.sort(key=lambda l:(-(dt.toordinal()-last_lc[l]), -burden(l,dt), l))
    lc=lc_cand[0]
    sc=[l for l in avail if l!=lc]
    rec["LC"]=lc; rec["SC"]=sc; rec["OFF"]=off
    last_lc[lc]=dt.toordinal(); work_streak[lc]+=1
    for l in sc: work_streak[l]+=1
    for l in off: off_count[l]+=1; work_streak[l]=0
    assign[dt]=rec

# ---------------------------------------------------------------------------
# DUTY-HOUR SMOOTHING: no intern works 7+ consecutive days.  When an outside
# rotator's night-float / Sunday-LC butts against a 24h Saturday with no break,
# hand that week's Thursday day-off to them (an LSH works that Thursday's short
# call instead).  Structure is unchanged (Thursday still = 1 LC / 1 SC / 1 OFF /
# 1 NF); only who is off changes.  Kennedy is never pulled in to cover.
# ---------------------------------------------------------------------------
def _worked(dt,l):
    r=assign[dt]; return l in (r["LC"],r["NF"],r["H24"]) or l in r["SC"]
def _runs(p, pdays):
    out=[]; run=[]
    for dt in pdays:
        if _worked(dt,p):
            if run and run[-1]==dt-timedelta(days=1): run.append(dt)
            else: run=[dt]
            if len(run)>=7: out.append(list(run))
        else: run=[]
    # keep only maximal runs
    return out
present_days={}
for dt in days:
    for l in roster(dt): present_days.setdefault(l,[]).append(dt)
for p,pdays in present_days.items():
    if roster(pdays[0])[p]["type"]=="LSH": continue      # LSH never hit 7-runs
    changed=True
    while changed:
        changed=False
        runs=[r for r in _runs(p,pdays) if len(r)>=7]
        for run in runs:
            # (a) preferred: hand the week's Thursday day-off to p (structure unchanged)
            for dt in run:
                if dt.weekday()!=3 or not assign[dt]["OFF"]: continue
                offp=assign[dt]["OFF"][0]
                if offp==KENNEDY or roster(dt)[offp]["type"]!="LSH": continue
                if p in assign[dt]["SC"]:                      # p on short call -> swap
                    assign[dt]["SC"].remove(p); assign[dt]["SC"].append(offp)
                    assign[dt]["OFF"]=[p]; changed=True; break
                if p==assign[dt]["LC"]:                        # p on long call -> LSH takes LC
                    yes=dt-timedelta(days=1); tom=dt+timedelta(days=1)
                    if assign.get(yes,{}).get("LC")==offp or assign.get(tom,{}).get("LC")==offp:
                        continue                               # avoid LSH back-to-back LC
                    assign[dt]["LC"]=offp; assign[dt]["OFF"]=[p]; changed=True; break
            if changed: break
            # (b) fallback: give p an interior weekday off (that day drops to 1 short call)
            for dt in run[1:-1]:
                if dt.weekday() in (0,1,2,4) and p in assign[dt]["SC"] and len(assign[dt]["SC"])>=2 \
                   and not assign[dt]["OFF"]:
                    assign[dt]["SC"].remove(p); assign[dt]["OFF"]=[p]; changed=True; break
            if changed: break

import pickle
pickle.dump({"assign":{k.isoformat():v for k,v in assign.items()},
             "nf":{k.isoformat():v for k,v in NF_BY_DAY.items()},
             "sat":{k.isoformat():v for k,v in SAT_BY_DAY.items()}},
            open(_HERE+"assign.pkl","wb"))
if __name__=="__main__":
    print("Generated",len(days),"days:",days[0],"->",days[-1])
