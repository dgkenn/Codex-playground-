#!/usr/bin/env python3
"""Get the data: extract missing itemids from raw MIMIC-IV gz sources into compact CSVs.
- chemistry lactate 53154 (second method vs blood-gas lactate 50813 -> cross-method lactate pair)
- vasopressors from inputevents (start/end/rate) -> ADRENAL eligibility, dose-intensity, shock defs
- invasive/non-invasive ventilation from procedureevents -> PEPTIC/ADRENAL vent criterion
Writes hadm_id-keyed rows only. Disk-sparing.
"""
import gzip, csv, sys

SD='/home/user/Codex-playground-/scratchpad/'
LAB=SD+'labevents.csv.gz'
INP=SD+'inputevents.csv.gz'
PROC='/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad/procedureevents.csv.gz'

VASO={'221906':'norepi','221289':'epi','229617':'epi','221749':'phenyl','229630':'phenyl',
      '229632':'phenyl','221662':'dopamine','222315':'vasopressin','221653':'dobutamine'}
VENT={'225792':'invasive','225794':'noninvasive'}

def extract_lab():
    out=open(SD+'lab_lactatechem.csv','w',newline=''); w=csv.writer(out); w.writerow(['hadm_id','charttime','valuenum'])
    n=k=0
    with gzip.open(LAB,'rt') as f:
        r=csv.reader(f); h=next(r); ix={x:i for i,x in enumerate(h)}
        ii,ih,ic,iv=ix['itemid'],ix['hadm_id'],ix['charttime'],ix['valuenum']
        for row in r:
            n+=1
            if row[ii]=='53154' and row[iv] and row[ih]:
                w.writerow([row[ih],row[ic],row[iv]]); k+=1
            if n%10_000_000==0: sys.stderr.write(f'  lab {n:,} kept {k:,}\n'); sys.stderr.flush()
    out.close(); sys.stderr.write(f'LAB DONE {n:,} kept {k:,}\n')

def extract_inp():
    out=open(SD+'vaso.csv','w',newline=''); w=csv.writer(out); w.writerow(['hadm_id','starttime','endtime','drug','rate','rateuom','weight'])
    n=k=0
    with gzip.open(INP,'rt') as f:
        r=csv.reader(f); h=next(r); ix={x:i for i,x in enumerate(h)}
        ii=ix['itemid'];ih=ix['hadm_id'];ist=ix['starttime'];ie=ix['endtime']
        irate=ix['rate'];iru=ix['rateuom'];iw=ix['patientweight']
        for row in r:
            n+=1
            if row[ii] in VASO and row[ih]:
                w.writerow([row[ih],row[ist],row[ie],VASO[row[ii]],row[irate],row[iru],row[iw]]); k+=1
            if n%5_000_000==0: sys.stderr.write(f'  inp {n:,} kept {k:,}\n'); sys.stderr.flush()
    out.close(); sys.stderr.write(f'INP DONE {n:,} kept {k:,}\n')

def extract_proc():
    out=open(SD+'vent.csv','w',newline=''); w=csv.writer(out); w.writerow(['hadm_id','starttime','endtime','kind'])
    n=k=0
    with gzip.open(PROC,'rt') as f:
        r=csv.reader(f); h=next(r); ix={x:i for i,x in enumerate(h)}
        ii=ix['itemid'];ih=ix['hadm_id'];ist=ix['starttime'];ie=ix['endtime']
        for row in r:
            n+=1
            if row[ii] in VENT and row[ih]:
                w.writerow([row[ih],row[ist],row[ie],VENT[row[ii]]]); k+=1
    out.close(); sys.stderr.write(f'PROC DONE {n:,} kept {k:,}\n')

if __name__=='__main__':
    extract_proc()   # fast first
    extract_inp()
    extract_lab()    # slowest last
    print('ALL EXTRACTION DONE')
