#!/usr/bin/env python3
"""Byte-range EDF reader for HEEDB BIDS files on S3.

WHY: ICU cEEG recordings are ~1 GB each; downloading a cohort is infeasible. EDF is a simple, fixed-layout
format, so we can HTTP-range only the header plus a bounded sample window and decode it ourselves. Sampling the
SAME window length from every recording keeps the OR/EMU vs ICU comparison fair.

EDF layout: 256-byte main header | ns*256-byte signal headers | data records (int16 LE, per-signal blocks).
"""
import io, struct, numpy as np
def _s3():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", region_name="us-east-1", config=Config(s3={'payload_signing_enabled': False}))
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
def _rng(s3, key, start, length):
    return s3.get_object(Bucket=AP, Key=key, Range=f"bytes={start}-{start+length-1}")["Body"].read()
def read_edf_window(key, max_seconds=600, s3=None, want=None, start_frac=0.0, start_seconds=None):
    """Return (data[n_ch, n_samp] in uV, fs, ch_names). Reads only what's needed."""
    s3 = s3 or _s3()
    h = _rng(s3, key, 0, 256)
    if h[:8].strip() not in (b"0", b"EDF+C", b"0       ".strip()):
        pass  # version field is '0' for EDF; tolerate variants
    n_hdr = int(h[184:192].decode(errors="replace").strip() or 0)
    n_rec = int(h[236:244].decode(errors="replace").strip() or 0)
    rec_dur = float(h[244:252].decode(errors="replace").strip() or 1)
    ns = int(h[252:256].decode(errors="replace").strip() or 0)
    if ns <= 0: raise ValueError("bad EDF: ns=0")
    sh = _rng(s3, key, 256, ns * 256)
    # EDF signal-header field offsets (all blocks are contiguous, ns entries each):
    #   0:label(16) 16n:transducer(80) 96n:phys_dim(8) 104n:phys_min(8) 112n:phys_max(8)
    #   120n:dig_min(8) 128n:dig_max(8) 136n:prefilter(80) 216n:n_samples(8) 224n:reserved(32)
    def blk(off_mult, width):
        base = off_mult * ns
        return [sh[base + i*width: base + (i+1)*width].decode(errors="replace").strip() for i in range(ns)]
    def fnum(vals, default):
        out = []
        for v in vals:
            try: out.append(float(v))
            except: out.append(default)
        return out
    labels = blk(0, 16)
    pmin = fnum(blk(104, 8), -32768.0)
    pmax = fnum(blk(112, 8),  32767.0)
    dmin = fnum(blk(120, 8), -32768.0)
    dmax = fnum(blk(128, 8),  32767.0)
    nsamp = [int(float(x)) if x else 0 for x in blk(216, 8)]
    nsamp = [n if n > 0 else 1 for n in nsamp]
    rec_bytes = 2 * sum(nsamp)
    data_off = 256 + ns*256
    total = n_rec if n_rec > 0 else 10**9
    want_recs = min(total, max(1, int(max_seconds / rec_dur)))
    # skip into the recording: hookup/impedance artifact dominates the first minutes
    if start_seconds is not None:
        skip = int(start_seconds / rec_dur)
    else:
        skip = int(total * start_frac)
    skip = max(0, min(skip, max(0, total - want_recs)))
    raw = _rng(s3, key, data_off + skip * rec_bytes, want_recs * rec_bytes)
    got_recs = len(raw) // rec_bytes
    if got_recs == 0: raise ValueError("no complete data record fetched")
    arr = np.frombuffer(raw[:got_recs*rec_bytes], dtype="<i2").reshape(got_recs, -1)
    out = {}
    idx = 0
    for i, lab in enumerate(labels):
        n = nsamp[i]
        block = arr[:, idx:idx+n].astype(np.float32).ravel()
        idx += n
        # digital -> physical (uV)
        span_d = (dmax[i] - dmin[i]) or 1.0
        gain = (pmax[i] - pmin[i]) / span_d
        out[lab] = (block - dmin[i]) * gain + pmin[i]
    fs = [nsamp[i]/rec_dur for i in range(ns)]
    names = labels
    if want:
        keep = [i for i,l in enumerate(names) if any(w.lower() in l.lower() for w in want)]
        if keep:
            names = [names[i] for i in keep]
            fs = [fs[i] for i in keep]
            out = {names[j]: out[labels[keep[j]]] for j in range(len(keep))}
    L = min(len(v) for v in out.values())
    X = np.vstack([out[n][:L] for n in names])
    return X, (fs[0] if fs else 200.0), names, dict(n_rec=n_rec, rec_dur=rec_dur, got_recs=got_recs, ns=ns)
def bs_burden(x, fs, thresh_uv=10.0, frame_s=0.1, min_run_s=0.5):
    """Amplitude-threshold burst-suppression burden on one channel (same rule validated on VitalDB)."""
    x = x[~np.isnan(x)]
    if len(x) < fs*10: return np.nan
    fr = max(1, int(frame_s*fs)); n = len(x)//fr
    if n < 10: return np.nan
    seg = x[:n*fr].reshape(n, fr)
    supp = (seg.max(axis=1) - seg.min(axis=1)) < thresh_uv
    run = 0; out = supp.copy()
    need = max(1, int(min_run_s/frame_s))
    for i in range(n):
        if supp[i]: run += 1
        else:
            if run < need: out[max(0,i-run):i] = False
            run = 0
    return float(out.mean())
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else "EEG/bids/S0001/sub-S0001111189188/ses-1/eeg/sub-S0001111189188_ses-1_task-EEG_eeg.edf"
    X, fs, names, meta = read_edf_window(key, max_seconds=300)
    print(f"key={key.split('/')[-1]}")
    print(f"  meta={meta}  fs={fs}  n_ch={len(names)}")
    print(f"  channels={names[:12]}")
    print(f"  shape={X.shape}  amp p1/p99 = {np.nanpercentile(X,1):.1f}/{np.nanpercentile(X,99):.1f} uV")
    fr = [i for i,n in enumerate(names) if any(k in n.upper() for k in ("FP1","FP2","F3","F4"))]
    ch = fr[0] if fr else 0
    print(f"  BS burden on {names[ch]}: {bs_burden(X[ch], fs):.4f}")
