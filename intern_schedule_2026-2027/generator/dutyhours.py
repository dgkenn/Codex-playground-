#!/usr/bin/env python3
"""ACGME duty-hour audit of the generated schedule:
  (1) <= 80 clinical hours/week, averaged over any 4 consecutive weeks;
  (2) no single continuous duty period > 28 hours;
  (3) >= 1 day (24h) free of clinical duty per week, averaged over 4 weeks.
Shift clock-times come from the program's own sheet headers.
"""
import os, importlib.util, pickle
from datetime import date, datetime, timedelta, time
_HERE=os.path.dirname(os.path.abspath(__file__))+os.sep
spec=importlib.util.spec_from_file_location("gen",_HERE+"gen.py"); gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
if not os.path.exists(_HERE+"assign.pkl"):
    import subprocess; subprocess.run(["python3",_HERE+"gen.py"],check=True)
A={date.fromisoformat(k):v for k,v in pickle.load(open(_HERE+"assign.pkl","rb"))["assign"].items()}
days=sorted(A)

def status(dt,l):
    r=A[dt]
    if r["H24"]==l: return "24H"
    if r["NF"]==l: return "NF"
    if r["LC"]==l: return "LC"
    if l in r["SC"]: return "SC"
    return "OFF" if l in r["OFF"] else "-"

def interval(dt,kind):
    """Return (start_datetime, end_datetime) for a shift, per the sheet headers."""
    wd=dt.weekday()
    D=datetime.combine(dt,time())
    if kind=="24H":  # Saturday 24h: 7:00a Sat -> 7:00a Sun
        return (D+timedelta(hours=7), D+timedelta(days=1,hours=7))
    if kind=="LC":   # Sun-Thu 7:00a-6:00p (11h); Fri 7:00a-7:30p (12.5h)
        end=19.5 if wd==4 else 18.0
        return (D+timedelta(hours=7), D+timedelta(hours=end))
    if kind=="SC":   # 7:00a-4:00p (9h)
        return (D+timedelta(hours=7), D+timedelta(hours=16))
    if kind=="NF":   # Sun-Thu 6:00p-8:00a (14h); Fri 7:30p-9:30a (14h)
        if wd==4: return (D+timedelta(hours=19.5), D+timedelta(days=1,hours=9.5))
        return (D+timedelta(hours=18), D+timedelta(days=1,hours=8))
    return None

# presence window + shift intervals per person
people=set()
for dt in days: people|=set(gen.roster(dt))
present_days={p:[dt for dt in days if p in gen.roster(dt)] for p in people}
shifts={p:[] for p in people}          # list of (start,end)
worked_day={p:set() for p in people}   # calendar days with any clinical duty
for dt in days:
    for p in gen.roster(dt):
        k=status(dt,p)
        if k in ("LC","SC","NF","24H"):
            shifts[p].append(interval(dt,k)); worked_day[p].add(dt)

def merged_max(intervals):
    """Longest continuous duty block (touching/overlapping shifts merge)."""
    if not intervals: return 0.0
    iv=sorted(intervals); best=0.0; cs,ce=iv[0]
    for s,e in iv[1:]:
        if s<=ce:            # contiguous or overlapping -> same block
            ce=max(ce,e)
        else:
            best=max(best,(ce-cs).total_seconds()/3600); cs,ce=s,e
    return max(best,(ce-cs).total_seconds()/3600)

def hours_in(intervals, w0, w1):
    """Clinical hours overlapping [w0,w1)."""
    tot=0.0
    for s,e in intervals:
        lo=max(s,w0); hi=min(e,w1)
        if hi>lo: tot+=(hi-lo).total_seconds()/3600
    return tot

NAME={ "MACNEILLE":"Stephen MacNeille","BRONSON":"Isaac Bronson","WISE":"Julien Wise","KENNEDY":"Dean Kennedy","ZAIDI":"Humza Zaidi","OGHENESUME":"Oghenewoma Oghenesume","LI":"Anna Li","MATSUOKA":"Kazune Matsuoka","BUTT":"Aqsa Butt","MULLINS":"Haley Mullins","SAEED":"Usman Saeed","SHETTY":"Kalasha Shetty","VILLANUEVA":"Ricardo Villanueva Gaona","FARZEELA":"Fnu Farzeela","AHN":"Hyojin Ahn","RIVERA":"Angel Maisonet Rivera","GABALLAH":"Bassel Gaballah","METRI":"Nicole Metri","SAEED-S":"Shirin Saeed","AHLUWALIA":"Srishti Ahluwalia","CHIASSON":"Megan Chiasson","VIVEKANANDAN":"Suja Vivekanandan","SALAM":"Muhammed Salam","JUYAL":"Shruti Juyal","KOPP VANUZZI":"Fabio Kopp Vanuzzi","PATEL":"Tirth Pareshbhai Patel","ALMADHOOB":"Mohamed Almadhoob","AHLUWALIA-S":"Saumya Ahluwalia","SANCHEZ-ALMANZAR":"Daniel Sanchez-Almanzar"}
def typ(p):
    for dt in present_days[p]: return gen.roster(dt)[p]["type"]

rows=[]; v_hours=[]; v_cont=[]; v_off=[]
for p in sorted(people, key=lambda p:(typ(p),p)):
    pres=present_days[p]; d0,d1=pres[0],pres[-1]
    iv=shifts[p]
    # (1) 80h avg over 4 weeks: max over all 28-day windows anchored in presence
    max28avg=0.0; win=[]
    d=d0
    while d<=d1:
        w0=datetime.combine(d,time()); w1=w0+timedelta(days=28)
        # only score windows that lie (mostly) within presence: require >=14 present days
        pd=sum(1 for x in pres if d<=x<d+timedelta(days=28))
        if pd>=14:
            max28avg=max(max28avg, hours_in(iv,w0,w1)/4.0)
        d+=timedelta(days=1)
    # if rotation shorter than 4 weeks, average over whole rotation (weekly rate)
    span_days=(d1-d0).days+1
    total=sum((e-s).total_seconds()/3600 for s,e in iv)
    whole_avg=total/(span_days/7)
    eff_avg=max28avg if span_days>=28 else whole_avg
    # (2) max continuous
    cont=merged_max(iv)
    # (3) min days off in any rolling 7-day window fully inside presence
    min_off=99
    d=d0
    while d+timedelta(days=6)<=d1:
        wd=[d+timedelta(days=i) for i in range(7)]
        off=sum(1 for x in wd if x not in worked_day[p])
        min_off=min(min_off,off); d+=timedelta(days=1)
    if min_off==99: min_off=sum(1 for x in pres if x not in worked_day[p])
    # max single 7-day hours (context)
    max7=0.0; d=d0
    while d<=d1:
        w0=datetime.combine(d,time())
        max7=max(max7, hours_in(iv,w0,w0+timedelta(days=7))); d+=timedelta(days=1)
    rows.append((NAME.get(p,p),typ(p),eff_avg,max7,cont,min_off))
    if eff_avg>80.0+1e-6: v_hours.append((p,round(eff_avg,1)))
    if cont>28.0+1e-6: v_cont.append((p,round(cont,1)))
    if min_off<1: v_off.append((p,min_off))

print(f"{'Intern':22}{'role':7}{'4wk-avg h/wk':>13}{'peak 7d h':>11}{'max cont h':>12}{'min days off/wk':>16}")
for nm,t,a,m7,c,mo in rows:
    flag=""
    if a>80: flag+=" !80h"
    if c>28: flag+=" !28h"
    if mo<1: flag+=" !dayoff"
    print(f"{nm:22}{t:7}{a:13.1f}{m7:11.1f}{c:12.1f}{mo:16d}{flag}")
print()
print("80h/wk (4-wk avg) violations:", v_hours or "NONE")
print(">28h continuous violations:", v_cont or "NONE")
print("<1 day off/wk violations:", v_off or "NONE")
print(f"\nMax 4-wk avg any intern: {max(r[2] for r in rows):.1f} h/wk")
print(f"Max continuous any intern: {max(r[4] for r in rows):.1f} h  (the Saturday 24h shift)")
print(f"Min days-off/wk any intern: {min(r[5] for r in rows)}")
