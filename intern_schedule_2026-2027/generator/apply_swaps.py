#!/usr/bin/env python3
"""Apply resident swaps / days-off on top of the finalized schedule and check
that every rule still holds.

HOW TO USE  (as simple as it gets):
  1. Open  swaps.txt  and add one line per change, e.g.
        swap 2026-11-14 KENNEDY WISE     # trade whatever each is doing that day
        swap 2026-11-08:2026-11-13 KENNEDY CHIASSON   # a whole night-float week
        off  2027-03-12 MATSUOKA         # give Matsuoka the day off (someone off covers)
     Lines starting with # are ignored.  Dates: YYYY-MM-DD (or a start:end range).
  2. Run:   python3 apply_swaps.py
  3. Read the report: it says PASS, or lists exactly what the swap would break.
     A fresh document  Intern_Schedule_with_swaps.html  is written either way.
"""
import os, importlib.util, copy
from datetime import date, timedelta
from collections import defaultdict, Counter, deque
_HERE=os.path.dirname(os.path.abspath(__file__))+os.sep
spec=importlib.util.spec_from_file_location("gen",_HERE+"gen.py"); gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
roster=gen.roster; days=gen.days

# ------------------------------------------------------------------ helpers --
def role_loc(rec,x):
    if rec["H24"]==x: return ("H24",)
    if rec["LC"]==x:  return ("LC",)
    if rec["NF"]==x:  return ("NF",)
    if x in rec["SC"]: return ("SC",rec["SC"].index(x))
    if x in rec["OFF"]: return ("OFF",rec["OFF"].index(x))
    return None
def place(rec,x,loc):
    if loc[0]=="H24": rec["H24"]=x; rec["LC"]=x        # Saturday: LC mirrors 24h
    elif loc[0] in ("LC","NF"): rec[loc[0]]=x
    else: rec[loc[0]][loc[1]]=x
def resolve(name, dt):
    """Match a typed name to an intern present that day (case-insensitive)."""
    up=name.strip().upper()
    present=roster(dt)
    for lab in present:
        cands={lab, lab.replace("-S",""), gen.__dict__.get("NAME",{}).get(lab,"")}
        if up==lab or up==lab.replace("-S","") : return lab
    # unique last-name / prefix match
    hits=[lab for lab in present if lab.startswith(up) or lab.replace("-S","")==up]
    if len(hits)==1: return hits[0]
    return None
def parse_date(s):
    s=s.strip()
    for fmt in ("%Y-%m-%d","%m/%d/%Y","%m/%d/%y"):
        try:
            from datetime import datetime; return datetime.strptime(s,fmt).date()
        except ValueError: pass
    return None

# ---------------------------------------------------------- rule checker -----
def violations(A):
    """Return a set of 'rule: detail' strings for everything currently broken."""
    V=set()
    NF={dt:A[dt]["NF"] for dt in A if A[dt]["NF"]}
    def stt(dt,l):
        r=A[dt]
        if r["H24"]==l:return "24H"
        if r["NF"]==l:return "NF"
        if r["LC"]==l:return "LC"
        if l in r["SC"]:return "SC"
        return "OFF" if l in r["OFF"] else "-"
    for dt in days:
        r=A[dt]; wd=dt.weekday(); present=set(roster(dt))
        work=set(filter(None,[r["LC"],r["NF"],r["H24"]]))|set(r["SC"])
        if present-(work|set(r["OFF"])): V.add(f"accounting: {dt} unaccounted {present-(work|set(r['OFF']))}")
        for l in work|set(r["OFF"]):
            if l not in present: V.add(f"accounting: {dt} {l} not present")
        if wd!=5 and not r["LC"]: V.add(f"one-LC: {dt} no long call")
        if r["LC"] and A.get(dt-timedelta(1),{}).get("LC")==r["LC"] and wd!=6:
            V.add(f"LC-diff-prev: {dt} long call {r['LC']} same as previous day")
        if r["NF"] and (r["NF"]==r["LC"] or r["NF"] in r["SC"]): V.add(f"double: {dt} {r['NF']} day+night")
        if wd==6 and r["SC"]: V.add(f"sunday-no-SC: {dt} Sunday has short call")
        if wd==5 and (r["SC"] or r["NF"]): V.add(f"saturday: {dt} Sat has SC/NF")
        if wd in (0,1,2,4) and r["OFF"]: V.add(f"weekday-off: {dt} off on a non-Thursday weekday {r['OFF']}")
        if wd==3 and len(r["OFF"])>1: V.add(f"one-off: {dt} more than one off on Thursday")
    # Q4
    call=defaultdict(list)
    for dt in days:
        if A[dt]["LC"]: call[A[dt]["LC"]].append(dt)
    for l,dl in call.items():
        dl=sorted(set(dl))
        for a,b in zip(dl,dl[1:]):
            if (b-a).days<3: V.add(f"Q4: {l} on call {a} then {b} (<4th day)")
    # Friday LC -> Sunday NF
    for dt in days:
        if dt.weekday()==4 and A[dt]["LC"]:
            sun=dt+timedelta(2)
            if sun in A and A[sun]["NF"] and A[sun]["NF"]!=A[dt]["LC"]:
                V.add(f"fri-LC-NF: Fri {dt} LC={A[dt]['LC']} but Sun {sun} NF={A[sun]['NF']}")
    # NF one person per Sun-Fri block (only flag if both present all week)
    for g in gen.GROUPS:
        labs=[NF.get(dt) for dt in g if NF.get(dt)]
        if labs and len(set(labs))>1 and set(labs)<=set(gen.present_all_week(g)):
            V.add(f"NF-week: {g[0]}..{g[-1]} has {sorted(set(labs))}")
    # Saturday 24h rules + <=1/month
    satc=Counter()
    for dt in days:
        if dt.weekday()==5:
            s=A[dt]["H24"]; nxt=dt+timedelta(1); prv=dt-timedelta(1); satc[(s,dt.year,dt.month)]+=1
            if nxt in A and s in roster(nxt) and s not in A[nxt]["OFF"]: V.add(f"sat-off-sun: {s} {dt} not off Sunday")
            if NF.get(nxt)==s: V.add(f"sat-nf-next: {s} 24h {dt} then NF Sunday")
            if NF.get(prv)==s: V.add(f"sat-nf-prev: {s} 24h {dt} after NF Friday")
    for (l,y,m),c in satc.items():
        if c>1: V.add(f"sat-max1: {l} has {c} Saturdays in {y}-{m:02d}")
    # >=1 day off in any 7 consecutive days
    pd=defaultdict(list)
    for dt in days:
        for l in roster(dt): pd[l].append(dt)
    for l,dl in pd.items():
        run=0;prev=None
        for dt in dl:
            w=stt(dt,l) in("LC","SC","NF","24H")
            run=run+1 if (w and prev==dt-timedelta(1)) else (1 if w else 0)
            if run>=7: V.add(f"dayoff: {l} works 7+ straight ending {dt}")
            prev=dt
    return V

# ------------------------------------------------------------- apply swaps ---
def daterange(a,b):
    d=a
    while d<=b: yield d; d+=timedelta(1)

def main():
    A=copy.deepcopy(gen.assign)
    base_V=violations(A)
    path=_HERE+"swaps.txt"
    if not os.path.exists(path):
        open(path,"w").write("# One change per line. Examples:\n"
            "# swap 2026-11-14 KENNEDY WISE\n"
            "# swap 2026-11-08:2026-11-13 KENNEDY CHIASSON\n"
            "# off  2027-03-12 MATSUOKA\n")
        print("Created a blank swaps.txt — add your lines and run again."); return
    print("="*64); print("APPLYING SWAPS"); print("="*64)
    applied=0
    for ln,raw in enumerate(open(path),1):
        line=raw.split("#")[0].strip()
        if not line: continue
        parts=line.split()
        cmd=parts[0].lower()
        try:
            if cmd=="swap" and len(parts)==4:
                drange,a,b=parts[1],parts[2],parts[3]
                d0,_,d1=drange.partition(":"); s=parse_date(d0); e=parse_date(d1) if d1 else s
                for dt in daterange(s,e):
                    la=resolve(a,dt); lb=resolve(b,dt)
                    if not la or not lb:
                        print(f"  line {ln}: {dt} could not find {a if not la else b} "
                              f"(present: {sorted(roster(dt))})"); continue
                    ra=role_loc(A[dt],la); rb=role_loc(A[dt],lb)
                    if not ra or not rb: print(f"  line {ln}: {dt} role not found"); continue
                    place(A[dt],la,rb); place(A[dt],lb,ra)
                    print(f"  {dt}: swapped {la} <-> {lb}")
                    applied+=1
            elif cmd=="off" and len(parts)==3:
                dt=parse_date(parts[1]); who=resolve(parts[2],dt)
                if not who: print(f"  line {ln}: {parts[2]} not present {dt}"); continue
                offs=[x for x in A[dt]["OFF"]]
                if who in offs: print(f"  {dt}: {who} already off"); continue
                if not offs:
                    print(f"  line {ln}: {dt} nobody is off to cover {who} "
                          f"(only Thursdays have an off slot) — use an explicit swap instead"); continue
                cover=offs[0]
                ra=role_loc(A[dt],who); rb=role_loc(A[dt],cover)
                place(A[dt],who,rb); place(A[dt],cover,ra)
                print(f"  {dt}: {who} off; {cover} covers")
                applied+=1
            else:
                print(f"  line {ln}: could not understand -> {line}")
        except Exception as ex:
            print(f"  line {ln}: error ({ex}) -> {line}")

    new_V=sorted(violations(A)-base_V)
    fixed=sorted(base_V-violations(A))
    print("\n"+"="*64)
    if applied==0:
        print("No changes applied.")
    elif not new_V:
        print("RESULT:  PASS  — all rules still hold after your swaps.")
    else:
        print(f"RESULT:  {len(new_V)} rule issue(s) introduced by these swaps:")
        for v in new_V: print("   x  "+v)
        print("\n  (A whole night-float week or a 24h shift usually needs the WHOLE block")
        print("   swapped, not a single day — swap the date range if you see NF-week/Q4 flags.)")
    if fixed: print("  (also note: these swaps removed pre-existing items: "+", ".join(fixed)+")")

    render(A)
    print("\nWrote Intern_Schedule_with_swaps.html")

# ------------------------------------------------------------- render HTML ---
def render(A):
    DIS={"AHLUWALIA":"AHLUWALIA Sr","AHLUWALIA-S":"AHLUWALIA Sa","SAEED":"SAEED U","SAEED-S":"SAEED Sh"}
    def g(l): return "" if l is None else DIS.get(l,l)
    DN=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    H=['<h1>LSH Intern Schedule - with swaps applied</h1>']
    for (yy,mm) in [(2026,10),(2026,11),(2026,12),(2027,1),(2027,2),(2027,3),(2027,4),(2027,5),(2027,6)]:
        ms=date(yy,mm,1); me=min(gen.month_end(yy,mm),gen.SPAN_END)
        H.append(f'<h2>{ms:%B %Y}</h2><table><tr><th>Day</th><th>Date</th><th>Long Call</th><th>Short Call</th><th>Night Float / Sat 24h</th></tr>')
        dt=ms
        while dt<=me:
            r=A[dt]; wd=dt.weekday(); cls="sat" if wd==5 else("sun" if wd==6 else "")
            if wd==5: lc,sc,nf=g(r["H24"]),"",g(r["H24"])+" (24H)"
            elif wd==6: lc,sc,nf=g(r["LC"]),"",g(r["NF"])
            else: lc,sc,nf=g(r["LC"]),", ".join(g(x) for x in r["SC"]),g(r["NF"])
            H.append(f'<tr class="{cls}"><td>{DN[wd]}</td><td>{dt.day}</td><td>{lc}</td><td>{sc}</td><td>{nf}</td></tr>')
            dt+=timedelta(1)
        H.append('</table>')
    css=("<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px}"
         "h2{border-bottom:2px solid #4472c4;margin-top:26px}table{border-collapse:collapse;font-size:13px;width:100%;max-width:780px}"
         "th,td{border:1px solid #ccc;padding:4px 8px}th{background:#4472c4;color:#fff}"
         "tr.sat td{background:#fce4d6;font-weight:600}tr.sun td{background:#fff2cc;font-weight:600}"
         "@media(prefers-color-scheme:dark){body{background:#191a1c;color:#e6e6e6}td{border-color:#444}"
         "tr.sat td{background:#5a3a2a}tr.sun td{background:#4a431f}}</style>")
    doc=('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
         '<meta name="viewport" content="width=device-width, initial-scale=1">'
         '<title>Schedule with swaps</title>'+css+"</head><body>"+"\n".join(H)+"</body></html>")
    doc=doc.encode("ascii","replace").decode("ascii")
    open(_HERE+"../Intern_Schedule_with_swaps.html","w",encoding="ascii").write(doc)

if __name__=="__main__":
    main()
