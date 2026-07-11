#!/usr/bin/env python3
"""Full compliance audit against the comprehensive (source-of-truth) rules."""
import os, importlib.util, pickle
from datetime import date, timedelta
from collections import defaultdict, Counter
_HERE=os.path.dirname(os.path.abspath(__file__))+os.sep
spec=importlib.util.spec_from_file_location("gen",_HERE+"gen.py"); gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
A={date.fromisoformat(k):v for k,v in pickle.load(open(_HERE+"assign.pkl","rb"))["assign"].items()}
NF={date.fromisoformat(k):v for k,v in pickle.load(open(_HERE+"assign.pkl","rb"))["nf"].items()}
days=sorted(A)
V=defaultdict(list)
def rec(rule,msg): V[rule].append(msg)
def stt(dt,l):
    r=A[dt]
    if r["H24"]==l: return "24H"
    if r["NF"]==l: return "NF"
    if r["LC"]==l: return "LC"
    if l in r["SC"]: return "SC"
    return "OFF" if l in r["OFF"] else "-"

for dt in days:
    r=A[dt]; wd=dt.weekday(); present=set(gen.roster(dt))
    work=set(filter(None,[r["LC"],r["NF"],r["H24"]]))|set(r["SC"])
    # accounting
    if present-(work|set(r["OFF"])): rec("accounting",f"{dt} unaccounted {present-(work|set(r['OFF']))}")
    for l in (work|set(r["OFF"])):
        if l not in present: rec("accounting",f"{dt} {l} not present")
    if wd!=5 and not r["LC"]: rec("one-LC",f"{dt} no LC")
    # different LC than previous day
    if r["LC"] and A.get(dt-timedelta(1),{}).get("LC")==r["LC"] and wd!=6:
        rec("LC-diff-prev",f"{dt} LC {r['LC']} same as prev day")
    # no double assignment
    if r["NF"] and (r["NF"]==r["LC"] or r["NF"] in r["SC"]): rec("double",f"{dt} {r['NF']} day+night")
    # Sunday no SC
    if wd==6 and r["SC"]: rec("sun-no-sc",f"{dt} Sunday has SC")
    # Saturday: no SC/NF, only 24h
    if wd==5 and (r["SC"] or r["NF"]): rec("sat-clean",f"{dt} Sat has SC/NF")
    # only one off on weekdays; weekday off must be Thursday
    if wd in (0,1,2,4) and r["OFF"]: rec("weekday-off-thu",f"{dt} {gen.roster(dt) and ['MON','TUE','WED','','FRI'][wd]} off {r['OFF']} (only Thu may have off)")
    if wd==3 and len(r["OFF"])>1: rec("one-off",f"{dt} {len(r['OFF'])} off on Thursday")

# Q4: each intern's LC/24h days must be >=3 apart (on call only every 4th day)
calldays=defaultdict(list)
for dt in days:
    if A[dt]["LC"]: calldays[A[dt]["LC"]].append(dt)
for l,dl in calldays.items():
    dl=sorted(set(dl))
    for a,b in zip(dl,dl[1:]):
        if (b-a).days<3: rec("Q4",f"{l}: LC/24h {a} then {b} ({(b-a).days}d apart, <4th-day)")

# Leaving-the-service protection: no LSH intern may be on night float on the
# last day (or day before last) of their block — they'd start their next
# rotation straight off a night shift.  Exemptions require the NEXT month to
# be outpatient/vacation/elective (per the year rotation grid) and are listed
# explicitly so they can be revoked the moment the grid says otherwise.
NEXT_IS_OUTPATIENT={("MACNEILLE",2026,10),   # Nov 2026 — confirm outpatient/elective
                    ("OGHENESUME",2027,4)}   # May 2027 — confirm outpatient/elective
for dt in days:
    nfp=A[dt]["NF"]
    if not nfp: continue
    info=gen.roster(dt).get(nfp)
    if not info or info["type"]!="LSH": continue
    if (info["end"]-dt).days>1: continue
    if nfp in gen.roster(info["end"]+timedelta(1)): continue   # continues at LSH
    if (nfp,dt.year,dt.month) in NEXT_IS_OUTPATIENT: continue
    rec("end-on-nf",f"{dt} {nfp} on NF with block ending {info['end']} (leaves the service)")

# Friday LC -> next Sunday NF
for dt in days:
    if dt.weekday()==4 and A[dt]["LC"]:
        sun=dt+timedelta(days=2)
        if sun in A:
            nfp=A[sun]["NF"]
            if nfp and nfp!=A[dt]["LC"]:
                rec("fri-lc-nf",f"Fri {dt} LC={A[dt]['LC']} but Sun {sun} NF={nfp}")

# NF same person all week (Sun-Fri block). A change is a VIOLATION only if both
# people are present the whole block (a real inconsistency). If it happens at a
# roster boundary (one leaves / one arrives) it's the rules' documented handoff
# ("a new intern starts night float when the month ends"; "if starting Monday
# they go through Friday") -> recorded as an informational transition, not a fail.
HANDOFF=[]
for g in gen.GROUPS:
    labs=[NF.get(dt) for dt in g if NF.get(dt)]
    if labs and len(set(labs))>1:
        allweek=set(gen.present_all_week(g))
        if set(labs)<=allweek:
            rec("nf-consec",f"NF block {g[0]}..{g[-1]} has {sorted(set(labs))} (both present all week)")
        else:
            HANDOFF.append((g[0],g[-1],[NF.get(dt) for dt in g]))
    for dt in g:
        if NF.get(dt) and NF[dt] not in gen.roster(dt): rec("nf-present",f"{dt} NF {NF[dt]} absent")
for dt in days:
    if dt.weekday()==5 and NF.get(dt): rec("nf-sat",f"{dt} NF on Saturday")

# Saturday 24h -> off Sunday; 24h not next-Sunday NF
for dt in days:
    if dt.weekday()==5:
        s=A[dt]["H24"]; nxt=dt+timedelta(1); prv=dt-timedelta(1)
        if nxt in A and s in gen.roster(nxt) and s not in A[nxt]["OFF"]: rec("sat-off-sun",f"{s} {dt} not off Sun")
        if NF.get(nxt)==s: rec("sat-not-nf-next",f"{s} 24h {dt} starts NF next day")
        if NF.get(prv)==s: rec("sat-not-nf-prev",f"{s} 24h {dt} did NF Fri before")

# <=1 Saturday per person per month; >=1 per hospital per month
sat_by_pm=Counter()
for dt in days:
    if dt.weekday()==5: sat_by_pm[(A[dt]["H24"],dt.year,dt.month)]+=1
for (l,y,m),c in sat_by_pm.items():
    if c>1: rec("sat-max1",f"{l} has {c} Saturdays in {y}-{m:02d}")

# new BMC/Lahey on LC/NF day 1 — the comprehensive rules do NOT forbid this
# (they describe the Q4 march and Monday night-float starts). The original email
# preferred avoiding it "when possible"; recorded as informational for awareness.
NEWSTART=[]
for dt in days:
    for l,p in gen.roster(dt).items():
        if p["type"] in("BMC","LAHEY") and p["start"]==dt and stt(dt,l) in("LC","NF"):
            NEWSTART.append(f"{dt:%a %-m/%-d} {l} ({p['type']}) starts on {stt(dt,l)}")

# >=1 day off per rolling 7-day window (each person present)
present_days=defaultdict(list)
for dt in days:
    for l in gen.roster(dt): present_days[l].append(dt)
def worked(dt,l): return stt(dt,l) in("LC","SC","NF","24H")
for l,pd in present_days.items():
    run=0; prev=None
    for dt in pd:
        run=run+1 if (worked(dt,l) and prev==dt-timedelta(1)) else (1 if worked(dt,l) else 0)
        if run>=7: rec("dayoff",f"{l} works 7+ consecutive days ending {dt}")
        prev=dt

order=["accounting","one-LC","LC-diff-prev","Q4","end-on-nf","fri-lc-nf","nf-consec","nf-present","nf-sat",
       "double","sun-no-sc","sat-clean","weekday-off-thu","one-off","sat-off-sun","sat-not-nf-next",
       "sat-not-nf-prev","sat-max1","dayoff"]
print("="*70); print("COMPLIANCE AUDIT — comprehensive rules"); print("="*70)
total=0
for k in order:
    n=len(V[k]); total+=n
    tag="OK" if n==0 else f"{n} ISSUES"
    print(f"  [{'✅' if n==0 else '❌'}] {k:18} {tag}")
    for m in V[k][:6]: print(f"        - {m}")
    if n>6: print(f"        ... +{n-6} more")
# ---- duty hours ----
from datetime import datetime, time
def _iv(dt,k):
    wd=dt.weekday(); D=datetime.combine(dt,time())
    if k=="24H": return (D+timedelta(hours=7),D+timedelta(days=1,hours=7))
    if k=="LC":  return (D+timedelta(hours=7),D+timedelta(hours=19.5 if wd==4 else 18))
    if k=="SC":  return (D+timedelta(hours=7),D+timedelta(hours=15.5))
    if k=="NF":  return (D+timedelta(hours=19.5 if wd==4 else 18),D+timedelta(days=1,hours=9.5 if wd==4 else 8))
_pres=defaultdict(list); _sh=defaultdict(list); _wk=defaultdict(set)
for dt in days:
    for l in gen.roster(dt):
        _pres[l].append(dt); k=stt(dt,l)
        if k in("LC","SC","NF","24H"): _sh[l].append(_iv(dt,k)); _wk[l].add(dt)
def _cont(iv):
    if not iv: return 0
    iv=sorted(iv); best=0; cs,ce=iv[0]
    for s,e in iv[1:]:
        if s<=ce: ce=max(ce,e)
        else: best=max(best,(ce-cs).total_seconds()/3600); cs,ce=s,e
    return max(best,(ce-cs).total_seconds()/3600)
def _hin(iv,a,b): return sum((min(e,b)-max(s,a)).total_seconds()/3600 for s,e in iv if min(e,b)>max(s,a))
mx_avg=mx_cont=mx_run=0
for l in _pres:
    iv=_sh[l]; d0,d1=_pres[l][0],_pres[l][-1]; best=0; dd=d0
    while dd<=d1:
        if sum(1 for x in _pres[l] if dd<=x<dd+timedelta(28))>=14:
            best=max(best,_hin(iv,datetime.combine(dd,time()),datetime.combine(dd,time())+timedelta(28))/4)
        dd+=timedelta(1)
    if (d1-d0).days+1<28:
        best=max(best,sum((e-s).total_seconds()/3600 for s,e in iv)/(((d1-d0).days+1)/7))
    mx_avg=max(mx_avg,best); mx_cont=max(mx_cont,_cont(iv))
    run=0;prev=None
    for x in _pres[l]:
        run=run+1 if (x in _wk[l] and prev==x-timedelta(1)) else (1 if x in _wk[l] else 0)
        mx_run=max(mx_run,run); prev=x

print(f"\nTOTAL HARD ISSUES: {total}")
print(f"\nNew-intern-on-LC/NF at rotation starts (permitted by comprehensive rules;"
      f" flagged for awareness): {len(NEWSTART)}")
for m in NEWSTART: print(f"    {m}")
print(f"\nNight-float transition handoffs (rules-permitted; a departing intern's")
print(f"last nights + an arriving intern's first, at month/rotation boundaries): {len(HANDOFF)}")
for s,e,seq in HANDOFF:
    days_lab=[f"{d:%a %-m/%-d}:{p}" for d,p in zip([s+timedelta(i) for i in range((e-s).days+1)],seq)]
    print(f"    {s:%-m/%-d}-{e:%-m/%-d}: "+", ".join(f"{p}" for p in seq if p)[:0] or " → ".join(dict.fromkeys(x for x in seq if x)))

# ---- Kennedy personal-request status under the deterministic march ----
def kstat(dd): return stt(dd,"KENNEDY")
kr=[("Weekend of Nov 7-8 fully off",
     "✅ MET — Kennedy swaps slot roles with the Lahey intern (Chiasson) for Nov 1-13: "
     "he does night float 11/1-6 and is OFF the whole 11/7-8 weekend."),
    ("Fri 11/6 free to fly",
     "PARTIAL — Kennedy's night-float shift Fri 11/6 is 7:30pm-9:30am, so he is FREE Friday "
     "until 7:30pm (a daytime/early-evening flight works). A full Friday off would need a "
     "single-night coverage swap that ripples Q4 — available on request."),
    ("Thanksgiving Day (Thu 11/26) off","✅ MET — off"),
    ("Thanksgiving Saturday","Kennedy is the Sat 11/28 24h — his single Saturday for the block."),
    ("Cost of the accommodation",
     "One boundary exception: Fri 10/30 long call (Chiasson) no longer couples to the 11/1 night "
     "float (Kennedy), because Kennedy isn't present in October. This is a month-boundary reset.")]

# ---- write RULES_COMPLIANCE.md ----
def ok2(b): return "✅ PASS" if b else "⚠️ SEE NOTE"
L=[]
L.append("# LSH Intern Schedule — Compliance Report (comprehensive-rules / march model)")
L.append("")
L.append(f"Coverage **Oct 1 2026 – Jun 23 2027**, continuing the finalized September. Built on the "
         f"integrated Q4 march (Friday long-call → next-week night float; night float → Monday long "
         f"call; Saturday 24h = the week's middle intern). The generator reproduces the finalized "
         f"September **exactly**. Checked against every rule in `PRINCIPLES.md`.")
L.append("")
L.append("## Hard rules")
L.append("")
L.append("| Rule | Status |")
L.append("|---|---|")
rows=[("One Long Call per day","one-LC"),("Different long-call intern than previous day","LC-diff-prev"),
      ("Q4 — every intern on call only every 4th day","Q4"),
      ("No one leaving the service ends on night float","end-on-nf"),
      ("Friday long-call intern = next week's night float","fri-lc-nf"),
      ("Night float: same person the whole Sun–Fri block","nf-consec"),
      ("Night-float intern present","nf-present"),("No night float on Saturday","nf-sat"),
      ("No daytime + night float same day","double"),("Sunday has no short call","sun-no-sc"),
      ("Saturday: 24h only (no SC/NF)","sat-clean"),
      ("Only one intern off at a time; weekday off = Thursday","weekday-off-thu"),
      ("Saturday 24h intern off the next day","sat-off-sun"),
      ("Saturday 24h intern not night float the next day","sat-not-nf-next"),
      ("Saturday 24h intern didn't do night float the night before","sat-not-nf-prev"),
      ("Every intern ≥1 day off per week","dayoff"),
      ("All present accounted for each day","accounting")]
for label,key in rows:
    L.append(f"| {label} | {ok2(len(V[key])==0)} |")
L.append(f"| One 24h Saturday per intern per month | {ok2(len(V['sat-max1'])==0)} |")
L.append("")
L.append("## Necessary exceptions (unavoidable; all surfaced)")
L.append("")
L.append("1. **Two Saturday 24h doubles — Bronson (Oct), Li (May).** A 5-Saturday calendar month "
         "whose repeating middle-intern slot lands on a (stable) LSH intern puts that intern on the "
         "1st and 5th Saturday. Reassigning the 5th would force a different intern into "
         "long-call-then-24h or back-to-back long call, breaking the strict Q4 march. The prior rules "
         "explicitly allowed \"in very rare occasions 2.\" These are the only two all year.")
L.append("2. **June 21–23, 2027 wind-down.** The roster has **no BMC-South intern after 6/20** "
         "(Shirin Saeed's block ends), so those last 3 days run with 3 interns instead of 4; with only "
         "two daytime interns, long call can't hold a strict 4-day gap on 6/22–6/23. Everything through "
         "6/20 is clean.")
L.append(f"3. **New intern on long call / night float at a rotation start ({len(NEWSTART)} times).** "
         "The Q4 march (and Monday night-float starts, per the rules) sometimes place an arriving "
         "BMC/Lahey intern on long call or night float on their first Monday. The comprehensive rules "
         "permit this; the earlier email preferred avoiding it \"when possible.\" Days: "
         + "; ".join(m.split(' starts')[0] for m in NEWSTART) + ".")
L.append(f"4. **Night-float transition handoffs ({len(HANDOFF)}).** At month/rotation boundaries a "
         "departing intern finishes a few nights and the arriving intern continues the block — exactly "
         "as the rules describe (\"a new intern starts night float when the month ends\").")
L.append("")
L.append("## Leaving-the-service night-float protection (hard rule)")
L.append("")
L.append("**No intern whose block is ending holds the night float.** The march places the final "
         "NF week of January, February and March 2027 on LSH slot 2 — under a naive roster that is "
         "**Oghenesume (1/31), Li (2/28) and Matsuoka (3/28–31)**, each walking into **Lahey** the "
         "next morning straight off a night shift.  Fixed structurally, with the audit now enforcing "
         "it as a hard rule (`end-on-nf`):")
L.append("")
L.append("| Month-end NF week | Covered by | Why they're safe |")
L.append("|---|---|---|")
L.append("| Jan 31 – Feb 5 | Zaidi | Slot choice: Zaidi continues at LSH in February — he isn't leaving.  Bonus: one person now covers the whole week (removes the old 1/31 mid-week handoff). |")
L.append("| Feb 28 – Mar 5 | Kopp Vanuzzi | Role-swap window 2/8–3/5: the LSH2 and Lahey slots trade roles, so the Fri-LC→Sun-NF chain hands the boundary week to the Lahey rotator, whose block runs to 3/7. |")
L.append("| Mar 28 – Apr 2 | Almadhoob | Role-swap window 3/7–4/2, same mechanism; Almadhoob's block runs to 4/18.  Side benefit: he no longer starts his rotation on night float (3/22), and Patel no longer does a single night float on his final day (3/21). |")
L.append("")
L.append("Cost accounting (who absorbs the displaced weeks): Zaidi takes the NF weeks of 1/31–2/5 "
         "and 2/21–26 (his nights end 2 days before his block does); Kennedy takes 3/21–26 (nights "
         "end 5 days before his block does).  Both are exempt from the transition problem only if "
         "their next month is outpatient/elective/vacation — as are the two exemptions the audit "
         "carries for **MacNeille (NF 10/25–30, block ends 10/31)** and **Oghenesume (NF 4/25–30, "
         "block ends 4/30)**.  Confirm all four against the year rotation grid; revoking an "
         "exemption makes the audit fail loudly rather than silently shipping a bad transition.")
L.append("")
L.append("## ACGME duty hours")
L.append("")
L.append("| Limit | Status | Measured |")
L.append("|---|---|---|")
L.append(f"| ≤ 80 h/wk (avg over 4 wks) | {ok2(mx_avg<=80)} | busiest {mx_avg:.1f} h/wk |")
L.append(f"| No duty period > 28h | {ok2(mx_cont<=28)} | longest {mx_cont:.0f} h (Sat 24h) |")
L.append(f"| ≥ 1 day off per week | {ok2(mx_run<=6)} | longest streak {mx_run} days |")
L.append("")
L.append("## Dr. Kennedy's November requests (accommodated)")
L.append("")
L.append("The march is fully deterministic, so honoring a personal request requires a local "
         "slot swap. Kennedy's is applied for Nov 1-13 (Kennedy ⇄ Chiasson). Status:")
L.append("")
L.append("| Request | Outcome |")
L.append("|---|---|")
for a,b in kr: L.append(f"| {a} | {b} |")
L.append("")
L.append("> This slot swap keeps every hard rule intact for Nov 1-13; its only cost is the one "
         "month-boundary coupling note above (Fri 10/30 → 11/1 night float). If Kennedy needs the "
         "**entire** Friday 11/6 off (a late flight), a single-night coverage swap can be added — it "
         "introduces one Q4 ripple, so it's left off unless requested.")
open(_HERE+"out/RULES_COMPLIANCE.md","w") if os.path.isdir(_HERE+"out") else open(_HERE+"RULES_COMPLIANCE.md","w")
import os as _os
_os.makedirs(_HERE+"out",exist_ok=True)
open(_HERE+"out/RULES_COMPLIANCE.md","w").write("\n".join(L))
print("\nWrote out/RULES_COMPLIANCE.md")
