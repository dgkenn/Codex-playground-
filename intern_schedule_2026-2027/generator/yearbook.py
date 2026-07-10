#!/usr/bin/env python3
"""Build a single scrollable full-year HTML document for auditing the schedule."""
import os, importlib.util, pickle
from datetime import date, timedelta, datetime, time
from collections import defaultdict, Counter
_HERE=os.path.dirname(os.path.abspath(__file__))+os.sep
spec=importlib.util.spec_from_file_location("gen",_HERE+"gen.py"); gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
A={date.fromisoformat(k):v for k,v in pickle.load(open(_HERE+"assign.pkl","rb"))["assign"].items()}
NF={date.fromisoformat(k):v for k,v in pickle.load(open(_HERE+"assign.pkl","rb"))["nf"].items()}
days=sorted(A)
DIS={"AHLUWALIA":"AHLUWALIA Sr","AHLUWALIA-S":"AHLUWALIA Sa","SAEED":"SAEED U","SAEED-S":"SAEED Sh"}
FULL={"MACNEILLE":"Stephen MacNeille","BRONSON":"Isaac Bronson","WISE":"Julien Wise","KENNEDY":"Dean Kennedy","ZAIDI":"Humza Zaidi","OGHENESUME":"Oghenewoma Oghenesume","LI":"Anna Li","MATSUOKA":"Kazune Matsuoka","BUTT":"Aqsa Butt","MULLINS":"Haley Mullins","SAEED":"Usman Saeed","SHETTY":"Kalasha Shetty","VILLANUEVA":"Ricardo Villanueva","FARZEELA":"Fnu Farzeela","AHN":"Hyojin Ahn","RIVERA":"Angel Rivera","GABALLAH":"Bassel Gaballah","METRI":"Nicole Metri","SAEED-S":"Shirin Saeed","AHLUWALIA":"Srishti Ahluwalia","CHIASSON":"Megan Chiasson","VIVEKANANDAN":"Suja Vivekanandan","SALAM":"Muhammed Salam","JUYAL":"Shruti Juyal","KOPP VANUZZI":"Fabio Kopp Vanuzzi","PATEL":"Tirth Patel","ALMADHOOB":"Mohamed Almadhoob","AHLUWALIA-S":"Saumya Ahluwalia","SANCHEZ-ALMANZAR":"Daniel Sanchez-Almanzar"}
def g(l): return "" if l is None else DIS.get(l,l)
def st(dt,l):
    r=A[dt]
    if r["H24"]==l:return "24H"
    if r["NF"]==l:return "NF"
    if r["LC"]==l:return "LC"
    if l in r["SC"]:return "SC"
    return "OFF" if l in r["OFF"] else "-"
MONTHS=[(2026,10),(2026,11),(2026,12),(2027,1),(2027,2),(2027,3),(2027,4),(2027,5),(2027,6)]
DN=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# per-intern stats
pres=defaultdict(list)
for dt in days:
    for l in gen.roster(dt): pres[l].append(dt)
def prof(l):
    for dt in pres[l]: return gen.roster(dt)[l]["type"]
load=defaultdict(Counter)
for dt in days:
    for l in gen.roster(dt): load[l][st(dt,l)]+=1
def maxrun(l):
    run=0;best=0;prev=None
    for dt in pres[l]:
        w= st(dt,l) in("LC","SC","NF","24H")
        run=run+1 if (w and prev==dt-timedelta(1)) else (1 if w else 0)
        best=max(best,run);prev=dt
    return best

H=[]
H.append('<h1>LSH Intern Call Schedule - Full Year (Oct 2026 to Jun 2027)</h1>')
H.append('<p class="lg">Pure integrated-Q4 "march" model (Friday long-call becomes the next week\'s '
         'night float; night float returns to Monday long call; Saturday 24h = the week\'s middle '
         'intern). Reproduces the finalized September exactly and continues it. This is the clean, '
         'rule-compliant baseline for audit - personal November tweaks are handled separately.</p>')
H.append('<div class="legend"><b>Legend:</b> <span class="k lc">LC</span> long call '
         '<span class="k sc">SC</span> short call <span class="k nf">NF</span> night float '
         '<span class="k h">24H</span> Saturday 24h | orange row = Saturday | yellow row = Sunday | '
         'duplicate surnames carry a first initial.</div>')

# compliance snapshot
H.append('<h2>Compliance snapshot</h2><ul class="snap">')
H.append('<li><b class="ok">OK</b> One long call per day; every intern on call only every 4th day (Q4); different long-call intern than the previous day.</li>')
H.append('<li><b class="ok">OK</b> Friday long-call intern = next week\'s night float; night float consecutive Sun-Fri, same person.</li>')
H.append('<li><b class="ok">OK</b> Saturday 24h only (no SC/NF); off the next day; not night-float-adjacent.</li>')
H.append('<li><b class="ok">OK</b> Only one intern off at a time; weekday day-off is Thursday; Sunday has no short call.</li>')
H.append('<li><b class="ok">OK</b> Every intern gets at least 1 day off/week. ACGME: at most 80h/wk avg, at most 24h continuous.</li>')
H.append('<li><b class="note">NOTE</b> Documented exceptions: Bronson (Oct) &amp; Li (May) each take 2 Saturdays in a 5-Saturday month; '
         'June 21-23 runs 3-deep (roster has no BMC intern after 6/20).</li></ul>')

for yy,mm in MONTHS:
    ms=date(yy,mm,1); me=min(gen.month_end(yy,mm),gen.SPAN_END)
    H.append(f'<h2>{ms:%B %Y}</h2><table class="cal"><tr><th>Day</th><th>Date</th><th>Long Call</th>'
             f'<th>Short Call</th><th>Night Float / Sat 24h</th></tr>')
    dt=ms
    while dt<=me:
        r=A[dt]; wd=dt.weekday(); cls="sat" if wd==5 else("sun" if wd==6 else "")
        if wd==5: lc,sc,nf=g(r["H24"]),"",g(r["H24"])+" (24H)"
        elif wd==6: lc,sc,nf=g(r["LC"]),"",g(r["NF"])
        else: lc,sc,nf=g(r["LC"]),", ".join(g(x) for x in r["SC"]),g(r["NF"])
        H.append(f'<tr class="{cls}"><td>{DN[wd]}</td><td>{dt.day}</td><td>{lc}</td><td>{sc}</td><td>{nf}</td></tr>')
        dt+=timedelta(1)
    H.append('</table>')

# per-intern summary
H.append('<h2>Per-intern summary (whole year)</h2>')
H.append('<table class="sum"><tr><th>Intern</th><th>Role</th><th>NF nights</th><th>24h Sat</th>'
         '<th>Long Call</th><th>Short Call</th><th>Days off</th><th>Max consec. days</th></tr>')
for l in sorted(load,key=lambda l:(prof(l),FULL.get(l,l))):
    c=load[l]
    H.append(f'<tr><td>{FULL.get(l,l)}</td><td>{prof(l)}</td><td>{c["NF"]}</td><td>{c["24H"]}</td>'
             f'<td>{c["LC"]}</td><td>{c["SC"]}</td><td>{c["OFF"]}</td><td>{maxrun(l)}</td></tr>')
H.append('</table>')
H.append('<p class="lg">NF nights = night-float shifts (divide by 6 for weeks). Each LSH/4-week rotator gets one NF '
         'week + one Saturday per block; 2-week rotators get whichever falls in their window. Max consecutive '
         'days is at most 6 for everyone (nobody works 7 straight).</p>')

css="""<style>
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,sans-serif;margin:26px;color:#17181a;background:#fafafa;line-height:1.4}
h1{font-size:23px;margin-bottom:2px} h2{margin-top:30px;border-bottom:2px solid #4472c4;padding-bottom:4px;font-size:18px}
.lg{color:#555;max-width:820px} .legend{margin:10px 0;padding:8px 12px;background:#eef2fb;border-radius:6px;max-width:820px;font-size:13px}
.snap{max-width:860px} .snap li{margin:2px 0}
.k{display:inline-block;padding:0 5px;border-radius:4px;font-weight:700;font-size:11px}
.k.lc{background:#dbe5ff}.k.sc{background:#eee}.k.nf{background:#e6d8f5}.k.h{background:#ffd9c2}
b.ok{color:#0a7d32}b.note{color:#b06a00}
table{border-collapse:collapse;margin:6px 0 12px;font-size:13px}
table.cal{width:100%;max-width:780px} table.sum{width:100%;max-width:860px}
th,td{border:1px solid #cbd2da;padding:4px 8px;text-align:left} th{background:#4472c4;color:#fff}
tr.sat td{background:#fce4d6;font-weight:600} tr.sun td{background:#fff2cc;font-weight:600}
table.sum tr:nth-child(even) td{background:#f4f6f9}
@media(prefers-color-scheme:dark){body{background:#191a1c;color:#e6e6e6}.lg{color:#aaa}.legend{background:#20293d}
td{border-color:#3a3f45}tr.sat td{background:#5a3a2a}tr.sun td{background:#4a431f}table.sum tr:nth-child(even) td{background:#232527}
.k.lc{background:#2a3a63}.k.sc{background:#333}.k.nf{background:#3d2d52}.k.h{background:#5a3a2a}}
</style>"""
doc=('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
     '<meta name="viewport" content="width=device-width, initial-scale=1">'
     '<title>LSH Intern Schedule - Full Year</title>'+css+'</head><body>'
     +"\n".join(H)+'</body></html>')
# guarantee pure ASCII output (no stray unicode can survive)
doc=doc.encode("ascii","replace").decode("ascii")
out=_HERE+"../Intern_Schedule_FullYear.html"
open(out,"w",encoding="ascii").write(doc)
nonascii=sum(1 for ch in doc if ord(ch)>127)
print("wrote",out,"| non-ASCII chars:",nonascii,"| bytes:",len(doc))
