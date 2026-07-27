#!/usr/bin/env python3
"""Extract pH (50820) and pCO2 (50818) blood-gas from local labevents.csv.gz
for the faithful BICAR-ICU 3-way gate (pH<=7.20 AND PaCO2<=45 AND HCO3<=20).
Also extract labevents flag+comments for K/Hb/HCO3/Na/glucose to check hemolysis screening."""
import gzip, csv, sys

WANT = {'50820':'ph', '50818':'pco2'}
FLAGCHECK = {'50971':'k_flag', '50822':'kbg_flag'}  # chem K + bloodgas K, WITH flag/comments this time

out = {v: open(f'lab_{v}.csv','w',newline='') for v in WANT.values()}
wr = {k: csv.writer(out[v]) for k,v in WANT.items()}
for v in WANT.values(): pass
for k,v in WANT.items(): wr[k].writerow(['hadm_id','charttime','valuenum'])

outf = {v: open(f'labflag_{v}.csv','w',newline='') for v in FLAGCHECK.values()}
wrf = {k: csv.writer(outf[v]) for k,v in FLAGCHECK.items()}
for k,v in FLAGCHECK.items(): wrf[k].writerow(['hadm_id','charttime','valuenum','flag','comments'])

n=k=0
with gzip.open('labevents.csv.gz','rt') as f:
    r=csv.reader(f); h=next(r); ix={x:i for i,x in enumerate(h)}
    ii,ih,ic,iv=ix['itemid'],ix['hadm_id'],ix['charttime'],ix['valuenum']
    ifl,icm=ix['flag'],ix['comments']
    for row in r:
        n+=1
        it=row[ii]
        if it in WANT and row[iv] and row[ih]:
            wr[it].writerow([row[ih],row[ic],row[iv]]); k+=1
        if it in FLAGCHECK and row[ih]:
            wrf[it].writerow([row[ih],row[ic],row[iv],row[ifl],row[icm]])
        if n%20_000_000==0: sys.stderr.write(f'{n:,} kept {k:,}\n'); sys.stderr.flush()
for f_ in list(out.values())+list(outf.values()): f_.close()
sys.stderr.write(f'DONE {n:,} kept {k:,}\n')
