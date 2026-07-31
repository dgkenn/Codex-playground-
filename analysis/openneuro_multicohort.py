#!/usr/bin/env python3
"""Extract the shared feature set from the free OpenNeuro cohorts, for the multi-cohort normative reference.

PRE-REGISTRATION for the extraction. Written before any feature value from these cohorts existed. The
experiments that consume this table (E47, E48) are registered in `analysis/normative_multicohort.py`.

WHY MORE THAN ONE COHORT. `EXISTING_NORMATIVE_MODELS.md` established that no existing normative EEG
database models an aperiodic measure, so the reference has to be built. A reference built in ONE deposit
cannot be checked -- every claim about it would be circular. Several independent cohorts give three things
that one cannot:

  1. an external check on the age/sex curve (does it reproduce out of sample?);
  2. a MEASURED between-cohort disagreement, which is the noise floor any downstream claim must clear --
     and, for Challenge A, an empirically derived equivalence margin instead of an opinion;
  3. real batch effects (three different references, three amplifiers, three durations) against which a
     proposed harmonisation can actually be tested.

COHORTS, verified live through the OpenNeuro GraphQL API and the public S3 mirror, all free and
uncredentialed. Every one carries age and sex in `participants.tsv`:

    ds005385  608 subj  20-70  376F/232M  BrainAmp, FCz ref,      1000 Hz, 184 s  EyesOpen + EyesClosed
    ds003775  111 subj  17-71   69F/ 42M  BioSemi, average ref,   1024 Hz, 240 s  eyes closed, 2 sessions
    ds004504   88 subj  44-79   44F/ 44M  linked-ears ref,         500 Hz, 600 s  eyes closed; 29 controls
    ds004148   60 subj  18-28   32F/ 28M                                          eyes closed/open
    ds005514  295 subj   5-20  192M/103F  Healthy Brain Network                   PAEDIATRIC anchor

THE HARMONISED CONDITION IS EYES CLOSED, because it is the only condition all of them share -- ds003775 and
ds004504 have no eyes-open recording at all. It is also the standard condition for normative qEEG, so this
is a convergence rather than a compromise. ds005385's eyes-open blocks are extracted separately by
`ds005385_extract.py` and are used for E44, not for the reference.

`ds004504` CARRIES A DIAGNOSIS COLUMN (`Group`: A = Alzheimer's 36, F = frontotemporal 23, C = control 29).
**Only `C` may enter the reference.** The other 59 are retained in the output with their group recorded, as
a held-out abnormal set -- a normative reference that cannot separate controls from dementia is not worth
freezing, and that check is free once the rows exist.

NO RE-REFERENCING, deliberately: see `eeg_features_common.py`. Removing the batch effects by construction
would guarantee a null for the very test this table exists to support.

    python analysis/openneuro_multicohort.py --out /tmp/eeg_probe/multicohort_features.csv
    python analysis/openneuro_multicohort.py --cohorts ds003775 --limit 3     # smoke
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import math
import re
import sys
import shutil
import tempfile
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eeg_features_common import features_from_file, ANALYSIS_S                          # noqa: E402

S3 = "https://s3.amazonaws.com/openneuro.org"

COHORTS = {
    # id: (task substrings to accept, file extensions, note)
    "ds003775": (("resteyesc",), (".edf",), "SRM resting, BioSemi 64, average ref"),
    "ds004504": (("eyesclosed",), (".set",), "AD/FTD/control, 19ch 10-20, linked ears"),
    "ds004148": (("eyesclosed", "EC"), (".edf", ".set", ".bdf"), "test-retest young adults"),
    "ds005385": (("EyesClosed",), (".edf",), "Dortmund Vital, eyes-closed blocks only"),
    # STATE cohorts -- these carry an anaesthetic contrast in the filename and exist to test E50's
    # registered prediction (that exponent_low and exponent_high AGREE in sign across deposits where
    # whole_head_exponent flipped). They are BrainVision.
    "ds005620": (("awake", "sed"), (".vhdr",), "repeated-awakening PROPOFOL sedation; task-awake/sed"),
    "ds004148": (("eyesclosed",), (".vhdr",), "test-retest young adults 18-28, eyes closed"),
    # AROUSAL WITHOUT A DRUG, and it is the contrast Challenge A has never had. 71 subjects, TWO sessions
    # (normal sleep vs sleep deprivation, order counterbalanced and recorded per subject), BOTH eyes-closed
    # and eyes-open, plus PVT vigilance and KSS/SSS sleepiness scores per session. Every other state cohort
    # here changes arousal with a drug; this one changes it with none, which is what makes a
    # drug-response / state-response ratio computable at all. EEGLAB .set + .fdt, CC0.
    # NOT part of the normative reference: it is a STATE cohort and must be extracted to its own table.
    "ds004902": (("eyesclosed", "eyesopen"), (".set",), "sleep deprivation vs normal sleep, 71 subj x 2 ses"),
}
"""ds005514 (Healthy Brain Network, 295 subjects, ages 5-20, 198.7 GB) is the paediatric anchor and is
deliberately NOT in the default set: at ~670 MB per subject it would dominate the transfer budget. It is
enabled explicitly with --cohorts ds005514 once the adult cohorts are in, and it matters because the
aperiodic exponent's steepest age dependence is in childhood -- an adult-only reference would extrapolate
into the range where the curve is most non-linear."""


def _get(url, timeout=120, nbytes=None):
    """Fetch a URL, optionally only its first `nbytes` via an HTTP Range request."""
    req = urllib.request.Request(url)
    if nbytes:
        req.add_header("Range", f"bytes=0-{nbytes - 1}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _prefix_bytes(vhdr_path):
    """How many bytes of a BrainVision `.eeg` cover `ANALYSIS_S` seconds -- or None if unsafe.

    WHY THIS IS SOUND HERE AND NOT IN GENERAL. Two properties of these files make a byte prefix a valid
    TIME prefix, and both are checked rather than assumed. `DataOrientation=MULTIPLEXED` means samples are
    interleaved channel-by-channel per time point, so truncating at a whole sample frame yields a shorter
    but otherwise identical recording. And these headers carry NO `DataPoints` field, so mne infers the
    length from the `.eeg` file size and reads a truncated file cleanly instead of erroring or padding.
    If either property is absent the function returns None and the full file is fetched.

    The saving is the difference between running this cohort and not: ds005620 is 65 channels at 5000 Hz,
    so a 600 s recording is 780 MB of which the analysis uses 180 s. Across its 202 recordings the full
    deposit is roughly 80 GB.
    """
    try:
        txt = open(vhdr_path, "r", errors="replace").read()
    except OSError:
        return None
    def field(name):
        m = re.search(rf"^{name}=(.+)$", txt, re.M)
        return m.group(1).strip() if m else None
    if (field("DataFormat") or "").upper() != "BINARY":
        return None
    if (field("DataOrientation") or "").upper() != "MULTIPLEXED":
        return None
    if field("DataPoints"):
        return None                     # length is declared; truncating would contradict the header
    width = {"IEEE_FLOAT_32": 4, "INT_16": 2, "UINT_16": 2, "INT_32": 4}.get(
        (field("BinaryFormat") or "").upper())
    nch = field("NumberOfChannels")
    si = field("SamplingInterval")
    if not (width and nch and si):
        return None
    try:
        nch = int(nch); sf = 1e6 / float(si)
    except ValueError:
        return None
    if not (nch > 0 and sf > 0):
        return None
    frames = int(math.ceil((ANALYSIS_S + 2.0) * sf))     # +2 s margin against off-by-one at the edge
    return frames * nch * width


def _participants(ds):
    txt = _get(f"{S3}/{ds}/participants.tsv").decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(txt), delimiter="\t"))
    out = {}
    for r in rows:
        pid = r.get("participant_id", "").strip()
        if not pid:
            continue
        age = r.get("age") or r.get("Age") or r.get("AGE") or ""
        sex = r.get("sex") or r.get("Gender") or r.get("gender") or r.get("Sex") or ""
        grp = r.get("Group") or r.get("group") or r.get("diagnosis") or ""
        out[pid] = {"age": age.strip(), "sex": sex.strip().upper()[:1], "group": grp.strip()}
    return out


def _list_keys(ds):
    """Full S3 key listing for a dataset, following continuation tokens."""
    keys, token = [], None
    while True:
        url = f"{S3}/?list-type=2&prefix={ds}/&max-keys=1000"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token, safe="")
        body = _get(url).decode("utf-8", "replace")
        keys += re.findall(r"<Key>(.*?)</Key>", body)
        m = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", body)
        if not m:
            break
        token = m.group(1)
    return keys


EXCLUDE_TREES = ("derivatives", "sourcedata", "code", "stimuli", "phenotype")
"""Top-level trees that must never be read.

**ds004504 ships a `derivatives/` tree whose files have IDENTICAL basenames to the raw ones** -- 88
preprocessed copies beside 88 raw. Matching on basename alone pulled in both, and the first smoke run wrote
`sub-001` twice with different values (exponent_low 2.282 vs 2.301) because one row was raw and one was
ICA-cleaned. Nothing in the output would have said so.

Mixing a cohort's own preprocessing into a normative reference makes a PIPELINE difference part of the
POPULATION model. **The reference uses raw recordings only, put through this repo's single feature path**,
precisely so that each deposit's local preprocessing choices do not become an uncontrolled batch factor --
which is the opposite of what a harmonisation study wants."""


def _targets(ds):
    """Recordings for one cohort: raw only, one per (subject, session, basename), collisions fatal."""
    tasks, exts, _note = COHORTS[ds]
    out, seen = [], {}
    for k in _list_keys(ds):
        if not k.endswith(tuple(e for e in exts)):
            continue
        parts = k.split("/")
        # Require the canonical BIDS raw layout: <ds>/sub-XXX/[ses-YYY/]eeg/<file>
        if len(parts) < 4 or not parts[1].startswith("sub-"):
            continue
        if any(p in EXCLUDE_TREES for p in parts):
            continue
        base = parts[-1]
        if "_eeg" not in base or not any(t in base for t in tasks):
            continue
        sub = base.split("_")[0]
        ses = ""
        m = re.search(r"_ses-([A-Za-z0-9]+)_", base)
        if m:
            ses = m.group(1)
        key = (sub, ses, base)
        if key in seen:
            raise RuntimeError(
                f"{ds}: two files map to the same (subject, session, name) {key}:\n"
                f"   {seen[key]}\n   {k}\n"
                "Refusing to continue -- silently averaging two versions of one recording is exactly the "
                "failure this check exists to prevent.")
        seen[key] = k
        out.append((sub, ses, base, k))
    return sorted(out)


def _check_schema(path, fields):
    """Abort if an existing output file's header does not match the columns we are about to write.

    **This is a data-integrity guard, not a nicety.** A resumed run after a schema change appended 65-column
    rows underneath a 53-column header, and every value in those rows was shifted: `sfreq` read 10 (the
    channel count), `duration_s` read 1.13, `lempel_ziv` read 2.415 -- a value the statistic cannot produce,
    which is the only reason it was noticed. Nothing else in the pipeline would have rejected them.

    The autonomous loop restarts these extractors, so this path is exercised routinely and must fail loudly
    rather than corrupt the table. Rule 5: a silent mismatch is not evidence of a match.
    """
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        return
    with open(path) as fh:
        existing = next(csv.reader(fh), None)
    if existing and list(existing) != list(fields):
        only_new = [c for c in fields if c not in (existing or [])]
        only_old = [c for c in (existing or []) if c not in fields]
        raise SystemExit(
            f"\nSCHEMA MISMATCH in {path}\n"
            f"   existing header : {len(existing)} columns\n"
            f"   this run writes : {len(fields)} columns\n"
            f"   new columns     : {only_new}\n"
            f"   dropped columns : {only_old}\n"
            "Appending would shift every value in the new rows. Delete the file to re-extract, or move it "
            "aside and merge deliberately. Refusing to continue.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="/tmp/eeg_probe/multicohort_features.csv")
    ap.add_argument("--cohorts", nargs="*", default=["ds003775", "ds004504", "ds004148"])
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    done = set()
    if os.path.exists(a.out):
        with open(a.out) as fh:
            for r in csv.DictReader(fh):
                done.add((r["cohort"], r["subject"], r["session"], r["file"]))
        print(f"resuming: {len(done)} recordings already present", flush=True)

    fh = w = None
    n_ok = n_fail = 0
    t0 = time.time()
    for ds in a.cohorts:
        if ds not in COHORTS:
            print(f"unknown cohort {ds}; known: {list(COHORTS)}")
            return 2
        parts = _participants(ds)
        tg = _targets(ds)
        print(f"{ds}: {len(parts)} participants, {len(tg)} matching recordings", flush=True)
        for sub, ses, base, key in tg:
            if (ds, sub, ses, base) in done:
                continue
            p = parts.get(sub, {"age": "", "sex": "", "group": ""})
            tmpdir = tempfile.mkdtemp(prefix="mc_")
            local = os.path.join(tmpdir, base)          # ORIGINAL basename: BrainVision needs it
            try:
                with urllib.request.urlopen(f"{S3}/{key}", timeout=300) as r, open(local, "wb") as dl:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        dl.write(chunk)
                # Multi-file formats: EEGLAB .set may keep data in a sibling .fdt; BrainVision .vhdr
                # ALWAYS needs .eeg and .vmrk and references them by name from inside the header.
                stem, ext = os.path.splitext(key)
                for sib in {".set": (".fdt",), ".vhdr": (".eeg", ".vmrk")}.get(ext, ()):
                    dest = os.path.join(tmpdir, os.path.basename(stem) + sib)
                    try:
                        nbytes = _prefix_bytes(local) if (ext == ".vhdr" and sib == ".eeg") else None
                        open(dest, "wb").write(_get(f"{S3}/{stem}{sib}", timeout=600, nbytes=nbytes))
                    except Exception:                                        # noqa: BLE001
                        pass                        # .fdt is optional; a missing .eeg fails loudly below
                feats = features_from_file(local)
            except Exception as exc:                                         # noqa: BLE001
                n_fail += 1
                print(f"   FAIL {ds} {sub} {ses}: {type(exc).__name__}: {exc}", flush=True)
                continue
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
            mt = re.search(r"_task-([A-Za-z0-9]+)", base)
            ma = re.search(r"_acq-([A-Za-z0-9]+)", base)
            row = {"cohort": ds, "subject": sub, "session": ses, "file": base,
                   "task": mt.group(1) if mt else "", "acq": ma.group(1) if ma else "",
                   "age": p["age"], "sex": p["sex"], "group": p["group"]}
            row.update(feats)
            if w is None:
                _check_schema(a.out, list(row.keys()))
                write_header = not os.path.exists(a.out) or os.path.getsize(a.out) == 0
                fh = open(a.out, "a", newline="")
                w = csv.DictWriter(fh, fieldnames=list(row.keys()))
                if write_header:
                    w.writeheader()
            w.writerow(row)
            fh.flush()
            n_ok += 1
            if n_ok % 10 == 0:
                el = time.time() - t0
                print(f"   {n_ok} ok / {n_fail} fail   {el / n_ok:.1f} s each", flush=True)
            if a.limit and n_ok >= a.limit:
                break
        if a.limit and n_ok >= a.limit:
            break

    print(f"\n{n_ok} written, {n_fail} failed -> {a.out}")
    print("NOT committed: derived subject-level tables live under /tmp/eeg_probe only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
