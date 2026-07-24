#!/usr/bin/env python3
"""HEEDB DISCOVERY ARM — iatrogenic vs pathological burst suppression, decisive mortality contrast.
Runs the moment BDSP credentials are restored. De-identified outputs only (aggregate stats; no PII rows/dates
printed or committed). Staged: `python heedb_bs_discovery.py describe` first (pull+schema), then `... analyze`.

Design: among BS-containing EEGs, split by sedative-attributable (drug-induced) vs non-drug (pathological, e.g.
anoxic). Decisive-first test: is mortality LOWER for drug-induced BS than pathological BS AT MATCHED BS burden?
If yes -> 'BS is a marker of its cause, not intrinsically harmful' (ENGAGES-debate resolution). Montage-robust.
"""
import sys, os, io, csv, gzip
AP="arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
REGION="us-east-1"
META="EEG/HEEDB_Metadata/"; EEGMETA="EEG/eeg-metadata/"
WORK="/tmp/eeg_probe/heedb"   # local de-identified working dir (gitignored; not committed)
# BS-causing sedatives (ATC) and pathological-BS diagnoses (ICD-10)
SEDATIVE_ATC={"N01AX10":"propofol","N05CD08":"midazolam","N05CA01":"pentobarbital","N01AF03":"thiopental",
              "N03AA02":"phenobarbital","N01AX03":"ketamine","N01AB08":"sevoflurane","N01AB06":"isoflurane"}
ANOXIC_ICD=("G93.1","G93.5","I46","P91.6","G93.40","G92")  # anoxic brain injury / post-arrest / HIE

def s3():
    import boto3
    from botocore.config import Config
    # prefer physionet profile if present, else default chain (env)
    try:
        sess=boto3.Session(profile_name="physionet")
        sess.client("sts").get_caller_identity()
    except Exception:
        sess=boto3.Session()
    return sess.client("s3", region_name=REGION, config=Config(s3={'payload_signing_enabled':False}))

def get_csv(cl, key):
    o=cl.get_object(Bucket=AP, Key=key)
    raw=o["Body"].read()
    if key.endswith(".gz"): raw=gzip.decompress(raw)
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8","replace"))))

def ls(cl, prefix):
    keys=[]; tok=None
    while True:
        kw=dict(Bucket=AP, Prefix=prefix, MaxKeys=1000)
        if tok: kw["ContinuationToken"]=tok
        r=cl.list_objects_v2(**kw)
        keys+=[o["Key"] for o in r.get("Contents",[])]
        if not r.get("IsTruncated"): break
        tok=r.get("NextContinuationToken")
    return keys

def describe():
    os.makedirs(WORK, exist_ok=True)
    cl=s3()
    print("== metadata objects ==")
    for k in ls(cl, META)[:40]: print("  ", k)
    print("== eeg-metadata (per-site catalogs) ==")
    site_csvs=[k for k in ls(cl, EEGMETA) if k.endswith(".csv")]
    for k in site_csvs[:20]: print("  ", k)
    # describe schemas (columns only — no PII values)
    for key in [META+"HEEDB_patients.csv", META+"HEEDB_Medication_ATC.csv",
                META+"HEEDB_ICD10_for_Neurology.csv"] + site_csvs[:1]:
        try:
            rows=get_csv(cl, key)
            print(f"\n-- {key}: {len(rows)} rows; columns: {list(rows[0].keys()) if rows else 'EMPTY'}")
        except Exception as e:
            print(f"\n-- {key}: ERR {type(e).__name__} {str(e)[:80]}")
    print("\n[next] adapt analyze() to the real column names printed above, then run `analyze`.")

def analyze():
    """Decisive mortality-contrast. Column names below are best-guess from HEEDB_UNLOCK.md; reconcile via describe()."""
    cl=s3()
    site_csvs=[k for k in ls(cl, EEGMETA) if k.endswith(".csv")]
    # 1) recordings: SiteID, BDSPPatientID, DurationInSeconds, ServiceName, DateOfDeath, (BS annotation flag if present)
    recs=[]
    for k in site_csvs:
        recs+=get_csv(cl, k)
    print(f"recordings: {len(recs)}")
    # 2) medications (ATC) per patient -> sedative exposure
    meds=get_csv(cl, META+"HEEDB_Medication_ATC.csv")
    # 3) ICD-10 -> anoxic/structural
    icd=get_csv(cl, META+"HEEDB_ICD10_for_Neurology.csv")
    # NOTE: exact keys reconciled after describe(); this skeleton documents the intended logic:
    #  - BS-containing EEGs: report-findings BS flag OR detect from signal (EEG/bids/) for a targeted subset.
    #  - drug-induced = sedative ATC administered within the EEG window; pathological = none / anoxic ICD.
    #  - decisive: mortality(drug-induced BS) vs mortality(pathological BS) at matched BS burden (stratified/adjusted).
    print("[analyze] skeleton — fill keys from describe() output, then compute the stratified mortality contrast.")

if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "describe"
    {"describe":describe, "analyze":analyze}.get(mode, describe)()
