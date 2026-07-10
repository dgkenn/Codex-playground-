import os
_HERE=os.path.dirname(os.path.abspath(__file__))+os.sep
#!/usr/bin/env python3
import pickle, importlib.util
from datetime import date, timedelta
from collections import defaultdict, Counter
BASE=_HERE
spec=importlib.util.spec_from_file_location("gen",BASE+"gen.py"); gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
data=pickle.load(open(BASE+"assign.pkl","rb"))
A={date.fromisoformat(k):v for k,v in data["assign"].items()}
NF={date.fromisoformat(k):v for k,v in data["nf"].items()}
days=sorted(A)
errs=[]; warns=[]
def E(m): errs.append(m)
def W(m): warns.append(m)
def WD(wd): return ["MON","TUE","WED","THU","FRI","SAT","SUN"][wd]
def status(dt,lab):
    r=A[dt]
    if lab==r["NF"]: return "NF"
    if lab==r["H24"]: return "24H"
    if lab==r["LC"]: return "LC"
    if lab in r["SC"]: return "SC"
    if lab in r["OFF"]: return "OFF"
    return "-"

for dt in days:
    r=A[dt]; wd=dt.weekday(); present=set(gen.roster(dt)); n=len(present)
    working=set(filter(None,[r["LC"],r["NF"],r["H24"]]))|set(r["SC"])
    for l in working|set(r["OFF"]):
        if l not in present: E(f"{dt} {l} assigned but not present")
    acct=working|set(r["OFF"])
    if present-acct: E(f"{dt} {WD(wd)} unaccounted present: {present-acct}")
    if not r["LC"] and wd!=5 and n>=1: E(f"{dt} no LC")
    if r["NF"] and (r["NF"]==r["LC"] or r["NF"] in r["SC"]): E(f"{dt} double-assign NF+day {r['NF']}")
    if r["LC"] in r["SC"]: E(f"{dt} LC in SC")
    if wd==5:
        if r["SC"] or r["NF"]: E(f"{dt} SAT has SC/NF")
        if r["LC"]!=r["H24"]: E(f"{dt} SAT LC!=24h")
    if wd==6 and r["SC"]: E(f"{dt} SUN has SC")
    if wd==6 and not r["NF"] and n>=3: E(f"{dt} SUN missing NF")
    # SC counts (only when full 4-person pool)
    daytime=[l for l in present if l!=r["NF"]]
    if wd in (0,1,2,4) and n==4:
        if len(r["SC"])!=2: W(f"{dt} {WD(wd)} SC={len(r['SC'])} want2 ({r['SC']})")
        if r["OFF"]: W(f"{dt} {WD(wd)} OFF on non-Thu weekday: {r['OFF']}")
    if wd==3 and n==4:
        if len(r["OFF"])!=1: W(f"{dt} THU off={len(r['OFF'])} want1")

# NF: one person per week, present all week, consecutive, no Sat
for g in gen.GROUPS:
    labs={NF[dt] for dt in g}
    if len(labs)!=1: E(f"NF week {g[0]}..{g[-1]} multiple {labs}")
    lab=list(labs)[0]
    for dt in g:
        if lab not in gen.roster(dt): E(f"NF {lab} absent {dt}")
for dt in days:
    if dt.weekday()==5 and dt in NF: E(f"NF on SAT {dt}")
# Sat 24h -> off Sunday
for dt in days:
    if dt.weekday()==5:
        s=A[dt]["H24"]; nxt=dt+timedelta(days=1); prv=dt-timedelta(days=1)
        if nxt in A and s in gen.roster(nxt) and s not in A[nxt]["OFF"]:
            E(f"Sat24h {s} {dt} not off Sunday {nxt}")
        # 24h intern must NOT have done NF the Friday before (post-NF rest)
        if NF.get(prv)==s: E(f"Sat24h {s} {dt} also did NF Friday {prv}")
        # 24h intern must NOT start NF the Sunday after
        if NF.get(nxt)==s: E(f"Sat24h {s} {dt} also starts NF Sunday {nxt}")

# new BMC/Lahey never start on LC/NF
for dt in days:
    for lab,p in gen.roster(dt).items():
        if p["type"] in ("BMC","LAHEY") and p["start"]==dt:
            st=status(dt,lab)
            if st in ("LC","NF"): E(f"NEW-START {lab} {p['type']} {dt} on {st}")

# >=1 day off per 7-day present week
wk=days[0]-timedelta(days=days[0].weekday()); cur=wk
while cur<=days[-1]:
    wd7=[cur+timedelta(days=i) for i in range(7) if gen.SPAN_START<=cur+timedelta(days=i)<=gen.SPAN_END]
    if len(wd7)==7:
        common=None
        for dt in wd7:
            s=set(gen.roster(dt)); common=s if common is None else common&s
        for lab in (common or []):
            if sum(1 for dt in wd7 if status(dt,lab)=="OFF")==0:
                W(f"{cur} week {lab} 0 days off")
    cur+=timedelta(days=7)

# ---- rotation coverage: each rotation gets >=1 of {NF, Sat} ----
rot={}
for dt in days:
    for lab,p in gen.roster(dt).items():
        rot.setdefault((lab,p["type"],p["start"]),p)
nf_by_rot=Counter(); sat_by_rot=Counter()
for g in gen.GROUPS: nf_by_rot[(lambda k:k)(gen.rot_id(g[0],NF[g[0]]))]+=1
for dt in days:
    if dt.weekday()==5: sat_by_rot[gen.rot_id(dt,A[dt]["H24"])]+=1

# =================== REPORTS ===================
print("="*70)
print("ROTATION NF / SAT COVERAGE  (want each: >=1 of the two; LSH ideally 1+1)")
print("="*70)
neither=[]
for k in sorted(rot,key=lambda k:(rot[k]['start'],k[0])):
    lab,typ,st=k; p=rot[k]; nf=nf_by_rot.get(k,0); sa=sat_by_rot.get(k,0)
    fl=""
    if nf==0 and sa==0: fl=" <== NEITHER"; neither.append(k)
    if nf>1: fl+=f" NFx{nf}"
    if sa>1: fl+=f" SATx{sa}"
    print(f"  {lab:16} {typ:6} {st}..{p['end']}  NF={nf} SAT={sa}{fl}")

print("\n"+"="*70); print("PER-INTERN LOAD (whole span)"); print("="*70)
load=defaultdict(lambda:Counter())
wknd_off=defaultdict(int); wknd_work=defaultdict(int)
for dt in days:
    for lab in gen.roster(dt):
        load[lab][status(dt,lab)]+=1
        if dt.weekday() in (5,6):
            if status(dt,lab)=="OFF": wknd_off[lab]+=1
            elif status(dt,lab)!="-": wknd_work[lab]+=1
print(f"  {'INTERN':16}{'typ':6}{'NF':>4}{'24H':>4}{'LC':>4}{'SC':>4}{'OFF':>5}{'WkndWk':>7}{'WkndOff':>8}")
def prof(lab):
    # find any type
    for dt in days:
        if lab in gen.roster(dt): return gen.roster(dt)[lab]['type']
    return "?"
for lab in sorted(load,key=lambda l:(prof(l),l)):
    c=load[lab]
    print(f"  {lab:16}{prof(lab):6}{c['NF']:>4}{c['24H']:>4}{c['LC']:>4}{c['SC']:>4}{c['OFF']:>5}{wknd_work[lab]:>7}{wknd_off[lab]:>8}")

print("\n"+"="*70); print("KENNEDY DETAIL (Nov & Mar)"); print("="*70)
for (yy,mm) in [(2026,11),(2027,3)]:
    c=Counter();
    dd=date(yy,mm,1)
    while dd.month==mm:
        if "KENNEDY" in gen.roster(dd): c[status(dd,"KENNEDY")]+=1
        dd+=timedelta(days=1)
    print(f"  {date(yy,mm,1):%B %Y}: {dict(c)}")

print("\n"+"="*70)
print(f"HARD ERRORS: {len(errs)}")
for e in errs: print("  ERR",e)
print(f"SOFT WARNINGS: {len(warns)}")
for w in warns[:60]: print("  warn",w)
if len(warns)>60: print(f"  (+{len(warns)-60} more)")
print(f"NEITHER-covered rotations: {len(neither)} -> {neither}")
