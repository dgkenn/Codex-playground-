#!/usr/bin/env python3
"""
Ward-vs-ICU classifier from MIMIC-IV hosp/transfers.csv (columns: subject_id,hadm_id,
transfer_id,eventtype,careunit,intime,outtime).

Builds a per-hadm_id list of (careunit, intime_epoch_hours, outtime_epoch_hours) intervals and
exposes is_icu(hadm, epoch_hours) -> bool: True iff that timestamp falls inside an interval whose
careunit matches the ICU pattern. Emergency Department and Medicine/Med-Surg/etc. wards are
non-ICU (ward) by construction (they don't match the ICU regex). Intervals are kept sorted per
hadm for a fast (linear/binary) lookup; open-ended outtimes (still admitted) extend to +inf.

Usage:
    from ward_classify import load_transfers, is_icu
    tx = load_transfers()                 # dict hadm -> sorted list of (t0, t1, is_icu_bool)
    is_icu(tx, hadm_id, epoch_hours)       # -> True/False/None (None = no transfer record covers t)
"""
import csv
import re
from datetime import datetime

ICU_RE = re.compile(r'intensive care|icu|ccu|cardiac vascular intensive', re.IGNORECASE)

SD = '/home/user/Codex-playground-/scratchpad/'


def ep(s):
    """Parse a MIMIC timestamp string to epoch hours (float)."""
    if not s:
        return None
    try:
        return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp() / 3600.0
    except Exception:
        return None


def load_transfers(path=None):
    """
    Load transfers.csv -> dict hadm_id -> sorted list of (t0_hours, t1_hours, is_icu_bool).
    Rows with unparseable intime are skipped. Missing/blank outtime (still in that unit, or the
    last transfer of the stay) is treated as open-ended (+inf) so is_icu() can still resolve it.
    Guards a missing file by returning {} (caller should treat that as SKIP).
    """
    path = path or (SD + 'transfers.csv')
    d = {}
    try:
        f = open(path)
    except FileNotFoundError:
        return d
    r = csv.reader(f)
    hdr = next(r, None)
    if not hdr:
        f.close()
        return d
    idx = {n: i for i, n in enumerate(hdr)}
    i_hadm = idx.get('hadm_id')
    i_unit = idx.get('careunit')
    i_in = idx.get('intime')
    i_out = idx.get('outtime')
    if i_hadm is None or i_in is None:
        f.close()
        return d
    for row in r:
        try:
            hadm = row[i_hadm]
        except IndexError:
            continue
        if not hadm:
            continue
        t0 = ep(row[i_in]) if i_in is not None and i_in < len(row) else None
        if t0 is None:
            continue
        t1 = ep(row[i_out]) if i_out is not None and i_out < len(row) else None
        if t1 is None:
            t1 = float('inf')
        careunit = row[i_unit] if i_unit is not None and i_unit < len(row) else ''
        icu = bool(ICU_RE.search(careunit)) if careunit else False
        d.setdefault(hadm, []).append((t0, t1, icu))
    f.close()
    for k in d:
        d[k].sort(key=lambda iv: iv[0])
    return d


def is_icu(transfers, hadm, epoch_hours):
    """
    True if epoch_hours falls within an ICU careunit interval for this hadm; False if it falls
    within a non-ICU (ward/ED) interval; None if hadm is unknown or no interval covers the time
    (caller should treat None conservatively, e.g. exclude from the ward/ICU split).
    """
    ivs = transfers.get(hadm)
    if not ivs:
        return None
    for t0, t1, icu in ivs:
        if t0 <= epoch_hours <= t1:
            return icu
    # fall back: nearest-preceding interval (handles boundary rounding / gaps between records)
    best = None
    for t0, t1, icu in ivs:
        if t0 <= epoch_hours and (best is None or t0 > best[0]):
            best = (t0, t1, icu)
    return best[2] if best else None


if __name__ == '__main__':
    tx = load_transfers()
    n_hadm = len(tx)
    n_iv = sum(len(v) for v in tx.values())
    print(f'loaded transfers for {n_hadm:,} hadm_ids, {n_iv:,} intervals')
    if tx:
        sample_hadm = next(iter(tx))
        t0 = tx[sample_hadm][0][0]
        print(f'sample hadm={sample_hadm} is_icu(t0)={is_icu(tx, sample_hadm, t0)}')
