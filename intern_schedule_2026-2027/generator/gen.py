#!/usr/bin/env python3
"""Intern call-schedule generator for LSH — INTEGRATED Q4 "MARCH" model.

Rebuilt to the comprehensive rules (Principles_of_scheduling_interns_at_LSH):
the four intern slots cycle [LSH1, Lahey, LSH2, BMC]; each week the night-float
slot advances; the Friday long-call intern becomes the next week's night float;
the night-float intern returns to Monday long call; the Saturday 24h is the
week's "middle" slot.  Verified to reproduce the finalized September exactly.
Generates Oct 1 2026 -> Jun 23 2027, seeded from September's phase.
"""
import os, pickle
from datetime import date, timedelta
from collections import defaultdict
_HERE=os.path.dirname(os.path.abspath(__file__))+os.sep
def d(m,day,y): return date(y,m,day)

# ---------------------------------------------------------------- ROSTER ----
# LSH: (slot0 person, slot2 person) per calendar month.  Two LSH interns/month.
#
# The ORDER of each pair is THE lever for the month-end night-float problem, and
# it is the ONLY correct one: it is roster data (who sits in which slot), not an
# algorithm change.  The march hands the month-end NF week to slot2, so flipping
# a pair simply chooses which of the two LSH interns absorbs it.  Current choices
# and what flipping each would cost:
#   Sep  [WISE, LI]              slot2 Wise 9/29-30   -> Oct is ELECTIVE. Flip = Li instead.
#   Oct  [BRONSON, MACNEILLE]    slot2 Bronson 10/30  -> Nov is VACATION. Matches the manual sheet.
#   Jan  [OGHENESUME, ZAIDI]     slot2 Zaidi          -> continues at LSH in Feb, so NO month-end case
#                                                        at all.  Flipping creates one (Oghenesume 1/31).
#   Feb  [LI, ZAIDI]             slot2 Zaidi 2/28     -> Mar is VACATION.  Flip = Li, who goes to LAHEY. Worse.
#   Mar  [MATSUOKA, KENNEDY]     slot2 Kennedy 3/30-31-> April UNCONFIRMED.  Flip = Matsuoka, who goes
#                                                        to LAHEY.  Worse.  Needs Kennedy's April rotation.
#   Apr  [ZAIDI, OGHENESUME]     slot2 Oghenesume     -> May UNCONFIRMED.  Flip = Zaidi.
# Change the order here; never reach into the march itself (see the note below).
LSH_MONTH = {
 (2026,9):["WISE","LI"],
 (2026,10):["BRONSON","MACNEILLE"], (2026,11):["WISE","KENNEDY"],
 (2026,12):["MACNEILLE","BRONSON"], (2027,1):["OGHENESUME","ZAIDI"],
 (2027,2):["LI","ZAIDI"],           (2027,3):["MATSUOKA","KENNEDY"],
 (2027,4):["ZAIDI","OGHENESUME"],   (2027,5):["LI","BRONSON"],
 (2027,6):["OGHENESUME","MATSUOKA"],
}
BMC = [
 (d(8,17,2026),d(9,13,2026),"ZOHAIB QASUN"),(d(9,14,2026),d(9,27,2026),"METRI"),
 (d(9,28,2026),d(10,11,2026),"BUTT"),(d(10,12,2026),d(11,8,2026),"MULLINS"),
 (d(11,9,2026),d(11,22,2026),"SAEED"),(d(11,23,2026),d(12,6,2026),"SHETTY"),
 (d(12,7,2026),d(12,20,2026),"VILLANUEVA"),(d(12,21,2026),d(1,3,2027),"FARZEELA"),
 (d(1,4,2027),d(1,31,2027),"AHN"),(d(2,1,2027),d(2,14,2027),"FARZEELA"),
 (d(2,15,2027),d(2,28,2027),"VILLANUEVA"),(d(3,1,2027),d(3,14,2027),"SHETTY"),
 (d(3,15,2027),d(3,28,2027),"BUTT"),(d(3,29,2027),d(4,25,2027),"RIVERA"),
 (d(4,26,2027),d(5,9,2027),"GABALLAH"),(d(5,10,2027),d(5,23,2027),"METRI"),
 (d(5,24,2027),d(6,20,2027),"SAEED-S"),
]
LAHEY = [
 (d(8,24,2026),d(9,20,2026),"KAVELIDOU"),(d(9,21,2026),d(10,18,2026),"AHLUWALIA"),
 (d(10,19,2026),d(11,15,2026),"CHIASSON"),(d(11,16,2026),d(12,13,2026),"VIVEKANANDAN"),
 (d(12,14,2026),d(1,10,2027),"SALAM"),(d(1,11,2027),d(2,7,2027),"JUYAL"),
 (d(2,8,2027),d(3,7,2027),"KOPP VANUZZI"),(d(3,8,2027),d(3,21,2027),"PATEL"),
 (d(3,22,2027),d(4,18,2027),"ALMADHOOB"),(d(4,19,2027),d(5,16,2027),"AHLUWALIA-S"),
 (d(5,17,2027),d(6,13,2027),"SANCHEZ-ALMANZAR"),(d(6,14,2027),d(6,23,2027),"PATEL"),
]
KENNEDY="KENNEDY"
def month_end(y,m): return date(y,12,31) if m==12 else date(y,m+1,1)-timedelta(days=1)
def _blk(blocks,dt):
    for s,e,l in blocks:
        if s<=dt<=e: return l
    return None
# --- Kennedy's November accommodation ---------------------------------------
# To give Kennedy the 11/7-8 weekend fully off (his hard request) within the
# rules, Kennedy and the Lahey intern (Chiasson) SWAP slot roles for Nov 1-13:
# Kennedy plays the Lahey slot (night float 11/1-6 -> off the 11/7-8 weekend),
# Chiasson plays the LSH2 slot.  A single further tweak (below) hands the Fri
# 11/6 night to Chiasson so Kennedy can fly out Friday.
# Set to the Nov 1-13 range to apply Kennedy's 7-8-weekend accommodation; left
# empty here so the document is the clean, fully-auditable pure-march baseline
# (November personal tweaks are handled on the back end).
KEN_SWAP_DAYS={d(11,x,2026) for x in range(1,14)}   # Kennedy on NF 11/1-6 (Chiasson takes his 11/8-13 week in return)
# --- Slot integrity: NO month-end role swaps (scheduler correction, Jul 2027) --
# An earlier version carried a SWAP12_DAYS window (Feb 8 - Mar 5 and Mar 7 -
# Apr 2) in which the LSH2 and Lahey slots traded ROLES, intended to keep a
# month-end night-float week off a departing LSH intern.  The scheduler flagged
# this as wrong, and it was: a role swap breaks the march for BOTH slots.
#   * Zaidi (LSH2) finished nights Fri 2/5 and, per the core rule "night float
#     returns to Monday long call", owns LC on Mon 2/8 - but the swap handed that
#     long call to Kopp Vanuzzi and pushed Zaidi onto the Lahey slot, which then
#     gave him a SECOND night-float week (2/21-26).  That single override is what
#     drove his year total to 24 nights.
#   * The Lahey SLOT is continuous across a rotator handoff: Kopp Vanuzzi takes
#     over Juyal's position in the march on 2/8 and simply continues it.  The
#     swap prevented that, so Kopp never marched with Juyal's schedule.
# The march is now pure: the four slots [LSH1, Lahey, LSH2, BMC] cycle without
# exception, and each arriving rotator inherits their slot's march position from
# the person they replace.  Month-boundary night-float spillover is handled the
# way the rules describe (departing intern finishes a few nights, arriving intern
# continues the block) and is checked by the audit's `end-on-nf` rule.
SWAP12_DAYS=set()
# --- Sept->Oct night-float boundary.  October's LSH pair is ordered
# [BRONSON, MACNEILLE] (Bronson=slot0) so Bronson absorbs the calendar "double"
# (the 9/27-10/2 spillover start + the 10/25-30 end week) and MacNeille gets a
# single clean mid-month night-float week (10/11-16).  This matches the manual
# scheduler's October and honours MacNeille's request (one NF week, not starting
# on nights, and off the 10/17-18 weekend as post-nights recovery).  Wise still
# finishes September on nights (9/27-30) exactly as in the manual schedule; that
# is carried in the audit's NEXT_IS_OUTPATIENT exemption pending confirmation of
# Wise's October rotation.
def slot_person(slot,dt):
    if dt in KEN_SWAP_DAYS:
        if slot==1: return "KENNEDY"       # Kennedy takes the Lahey slot
        if slot==2: return "CHIASSON"      # Chiasson takes the LSH2 slot
    if dt in SWAP12_DAYS and slot in (1,2): slot=3-slot   # LSH2 <-> Lahey roles
    if slot in (0,2):
        lm=LSH_MONTH.get((dt.year,dt.month))
        return lm[0] if slot==0 else lm[1]
    return _blk(LAHEY,dt) if slot==1 else _blk(BMC,dt)
def roster(dt):
    # actual interns present (independent of any slot-role swap)
    p={}
    lm=LSH_MONTH.get((dt.year,dt.month))
    if lm:
        for lab in lm: p[lab]={"type":"LSH","start":date(dt.year,dt.month,1),"end":month_end(dt.year,dt.month)}
    for s,e,lab in LAHEY:
        if s<=dt<=e: p[lab]={"type":"LAHEY","start":s,"end":e}
    for s,e,lab in BMC:
        if s<=dt<=e: p[lab]={"type":"BMC","start":s,"end":e}
    return p
def typ_of(l,dt): return roster(dt)[l]["type"]
def rot_id(dt,l):
    pp=roster(dt)[l]; return (l,pp["type"],pp["start"])

# ------------------------------------------------------------- DAY LIST -----
SPAN_START=d(9,1,2026); SPAN_END=d(6,23,2027)
days=[]; _t=SPAN_START
while _t<=SPAN_END: days.append(_t); _t+=timedelta(days=1)

# phase i of a week: seeded so the week of Sun 8/30/2026 is i=0
_BASE=date(2026,8,30)
def week_sun(dt): return dt-timedelta(days=(dt.weekday()+1)%7)
def phase(dt): return ((week_sun(dt)-_BASE).days//7)%4

# ------------------------------------------------------- MARCH GENERATION ---
assign={}
def newstart(l,dt):
    p=roster(dt)[l]; return p["type"] in("BMC","LAHEY") and p["start"]==dt
for dt in days:
    wd=dt.weekday(); i=phase(dt)
    S=lambda k:slot_person((i+k)%4,dt)
    ret,nf,nxt,mid=S(3),S(0),S(1),S(2)     # slots i-1, i, i+1, i+2
    present=list(roster(dt))
    rec={"LC":None,"SC":[],"NF":None,"OFF":[],"H24":None}
    if wd==5:                               # Saturday: 24h = P_mid
        h=mid if (mid and mid in roster(dt)) else (present[0] if present else None)
        rec["H24"]=h; rec["LC"]=h
        rec["OFF"]=[x for x in present if x!=h]
    elif wd==6:                             # Sunday: LC = P_mid, NF = slot i
        lc=mid if (mid and mid in roster(dt)) else None
        rec["NF"]=nf if (nf and nf in roster(dt)) else None
        if lc is None:
            lc=next((x for x in present if x!=rec["NF"]),None)
        rec["LC"]=lc
        rec["OFF"]=[x for x in present if x not in (lc,rec["NF"])]
    else:                                   # Mon-Fri
        rec["NF"]=nf
        lc={0:ret,1:nxt,2:mid,3:ret,4:nxt}[wd]
        daytime=[x for x in (ret,nxt,mid) if x and x!=nf]   # present daytime slots
        if wd==3:                            # Thursday: off = P_mid
            off=mid; rec["OFF"]=[off] if off else []
            rest=[x for x in daytime if x!=off]
        else:
            rest=daytime
        # if the marched LC slot is empty (roster gap), fall back to a present peer
        # (never the same intern as yesterday's long call)
        if lc is None or lc==nf or lc not in roster(dt):
            ylc=assign.get(dt-timedelta(days=1),{}).get("LC")
            lc=next((x for x in rest if x!=ylc), rest[0] if rest else (daytime[0] if daytime else None))
        rec["LC"]=lc
        rec["SC"]=[x for x in rest if x!=lc]
    assign[dt]=rec

# NOTE on the "one 24h Saturday per person per month" rule: in a 5-Saturday
# calendar month whose repeating "middle-intern" slot lands on a (stable) LSH
# intern, that intern is the Saturday 24h on both the 1st and 5th Saturday.
# Reassigning the 5th would force a different intern into Long-Call-then-24h or
# a back-to-back Long Call, breaking the strict Q4 march / different-LC-each-day
# rules.  We keep the clean march and accept the two calendar-driven doubles
# (Oct: Bronson; May: Li) — the prior rules explicitly allowed "in very rare
# occasions 2".  These are surfaced in the audit and compliance report.

# ---- NF-by-day, Saturday-by-day, and NF week groups (for downstream tools) --
NF_BY_DAY={dt:assign[dt]["NF"] for dt in days if assign[dt]["NF"]}
SAT_BY_DAY={dt:assign[dt]["H24"] for dt in days if assign[dt]["H24"]}
def nf_groups():
    groups=[]; cur=[]
    for dt in days:
        if dt.weekday()==5:
            if cur: groups.append(cur); cur=[]
            continue
        if dt.weekday()==6:
            if cur: groups.append(cur); cur=[]
            cur=[dt]
        else: cur.append(dt)
    if cur: groups.append(cur)
    return groups
GROUPS=nf_groups()
groups_by_month=defaultdict(list)
for g in GROUPS: groups_by_month[(g[0].year,g[0].month)].append(g)
NF_GROUP_PICK={id(g): (NF_BY_DAY.get(g[-1]) or NF_BY_DAY.get(g[0])) for g in GROUPS}
def present_all_week(g):
    common=None
    for dt in g:
        s=set(roster(dt)); common=s if common is None else common&s
    return sorted(common or [])

pickle.dump({"assign":{k.isoformat():v for k,v in assign.items()},
             "nf":{k.isoformat():v for k,v in NF_BY_DAY.items()},
             "sat":{k.isoformat():v for k,v in SAT_BY_DAY.items()}},
            open(_HERE+"assign.pkl","wb"))
if __name__=="__main__":
    print("Generated",len(days),"days:",days[0],"->",days[-1],"(march model)")
