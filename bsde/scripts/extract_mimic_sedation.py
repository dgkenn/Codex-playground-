"""Challenge D substrate: RASS, the clinician's GOAL RASS, and sedative infusions from MIMIC-IV.

WHY. `PROGRAMME_ROADMAP.md` Challenge D needs a FORWARD transport test of the DOSE-I pharmacology model,
and the investigator identified MIMIC-IV as the substrate. It is maximally different from DOSE-I on every
axis the construct-match rule claims to predict:

    DOSE-I                                   MIMIC-IV
    bolus propofol, mono-sedation            multi-drug INFUSION
    MOAA/S, 1-5, scored every few minutes    RASS, -5..+4, charted a few times a day
    ~20 minutes of procedural sedation       days of ICU care
    94 recordings                            tens of thousands of stays

E122 measured what there is to transport: an exposure model reaches out-of-bag rho 0.4595 against MOAA/S.
Whether that survives this move is the question, and it is a prediction the rule must make BEFORE the run.

**AND `Goal Richmond-RAS Scale` (228299) IS PULLED FOR A SPECIFIC REASON.** E127 killed E126 by showing
the residual LEADS the concentration direction — clinicians withhold drug from a patient who already looks
deeper than expected, which reproduces a hysteresis signature with no hysteresis in it. DOSE-I records no
target depth, so the confound could only be detected, never removed. **MIMIC records the clinician's
intended depth**, which is the variable that separates "responding to observed state" from "drug effect".

WHAT IS PULLED
    chartevents  228096 Richmond-RAS Scale        the state measure
                 228299 Goal Richmond-RAS Scale   the clinician's target
    inputevents  222168 Propofol            mg    rate + amount + start/end
                 221668 Midazolam           mg
                 221712 Ketamine            mg
                 221744 Fentanyl            mg
                 225150 Dexmedetomidine     mcg
                 225942 Fentanyl Concentrate mg
    icustays                                      stay boundaries and identifiers

HOW, AND WHY IT IS STREAMED. `chartevents.csv.gz` is multi-gigabyte and this sandbox has a fixed writable
allowance — landing it would fail, and `df` would mislead about why. The file is therefore consumed as an
HTTP stream through an incremental gzip decompressor, parsed line by line, and every row whose `itemid` is
not wanted is discarded immediately. Nothing but the filtered output touches disk. `--limit-rows` bounds a
smoke run.

**Two itemids only, out of 4,095.** The filter is applied on a raw string containment test before CSV
parsing, because parsing 300 million rows to discard 299.99 million of them is the slow way round.

SCOPE. This script extracts. It fits nothing and makes no claim; the transport experiment is separate and
is registered before this finishes.

    python bsde/scripts/extract_mimic_sedation.py --limit-rows 2000000   # smoke
    python bsde/scripts/extract_mimic_sedation.py
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import zlib
import os
import re
import sys
import urllib.parse
import urllib.request
import http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
BASE = "https://physionet.org/files/mimiciv/3.1/"

RASS_ITEMS = {"228096": "rass", "228299": "rass_goal"}
DRUG_ITEMS = {"222168": "propofol", "221668": "midazolam", "221712": "ketamine",
              "221744": "fentanyl", "225150": "dexmedetomidine", "225942": "fentanyl_conc"}


def _session():
    """PhysioNet needs a Django session cookie; HTTP Basic returns 403 on file paths (measured, see
    `docs/DEPOSIT_ACCESS_STATUS.md`). Credentials come from the environment, never from this file."""
    u = os.environ.get("PHYSIONET_USER")
    p = os.environ.get("PHYSIONET_PASSWORD")
    if not (u and p):
        # Fall back to ~/.netrc, which `bdsp_bootstrap.sh` materialises at mode 600 OUTSIDE the repo.
        # Reading it here keeps credentials out of every command line that launches this script.
        try:
            import netrc
            auth = netrc.netrc().authenticators("physionet.org")
            if auth:
                u, _acct, p = auth
        except Exception:                                                  # noqa: BLE001
            pass
    if not (u and p):
        raise SystemExit("set PHYSIONET_USER and PHYSIONET_PASSWORD in the environment "
                         "(see docs/CREDENTIALS.md); this script holds no credential")
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0"), ("Referer", "https://physionet.org/login/")]
    h = op.open("https://physionet.org/login/", timeout=60).read().decode("utf8", "replace")
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', h).group(1)
    op.open(urllib.request.Request("https://physionet.org/login/",
            data=urllib.parse.urlencode({"csrfmiddlewaretoken": tok,
                                         "username": u, "password": p}).encode()), timeout=60)
    if not any(c.name == "sessionid" for c in cj):
        raise SystemExit("PhysioNet login produced no session cookie")
    return op


def stream_gz_lines(op, url, chunk=1 << 20):
    """Yield decoded lines from a remote .gz without ever holding the whole file.

    An incremental decompressor is used rather than `gzip.open` on the response, because the latter seeks
    and PhysioNet's responses are not seekable."""
    d = zlib.decompressobj(zlib.MAX_WBITS | 16)   # gzip wrapper; gzip has no decompressobj
    tail = b""
    r = op.open(url, timeout=600)
    while True:
        buf = r.read(chunk)
        if not buf:
            break
        out = d.decompress(buf)
        if not out:
            continue
        out = tail + out
        *lines, tail = out.split(b"\n")
        for ln in lines:
            yield ln.decode("utf8", "replace")
    if tail:
        yield tail.decode("utf8", "replace")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit-rows", type=int, default=0)
    ap.add_argument("--out-prefix", default=os.path.join(RESULTS, "mimic_"))
    a = ap.parse_args(argv)
    op = _session()

    # ---- small tables first, so a failure is cheap -------------------------------------------------
    stays_path = a.out_prefix + "icustays.csv"
    if not os.path.exists(stays_path):
        n = 0
        with open(stays_path, "w", newline="") as fh:
            w = None
            for i, ln in enumerate(stream_gz_lines(op, BASE + "icu/icustays.csv.gz")):
                if not ln.strip():
                    continue
                row = next(csv.reader([ln]))
                if w is None:
                    w = csv.writer(fh); w.writerow(row); continue
                w.writerow(row); n += 1
        print(f"icustays: {n} rows -> {stays_path}", flush=True)

    # ---- inputevents: the drug record --------------------------------------------------------------
    drug_path = a.out_prefix + "sedative_inputevents.csv"
    if not os.path.exists(drug_path):
        kept = seen = 0
        hdr = None
        with open(drug_path, "w", newline="") as fh:
            w = csv.writer(fh)
            for ln in stream_gz_lines(op, BASE + "icu/inputevents.csv.gz"):
                if not ln.strip():
                    continue
                if hdr is None:
                    hdr = next(csv.reader([ln]))
                    ix = hdr.index("itemid")
                    w.writerow(hdr + ["drug"])
                    continue
                seen += 1
                # raw containment test before parsing -- parsing every row to discard most is the slow way
                if not any(k in ln for k in DRUG_ITEMS):
                    continue
                row = next(csv.reader([ln]))
                d = DRUG_ITEMS.get(row[ix])
                if d:
                    w.writerow(row + [d]); kept += 1
                if a.limit_rows and seen >= a.limit_rows:
                    break
                if seen % 2_000_000 == 0:
                    print(f"   inputevents {seen:,} scanned, {kept:,} kept", flush=True)
        print(f"sedative inputevents: {kept:,} of {seen:,} -> {drug_path}", flush=True)

    # ---- chartevents: RASS and the goal ------------------------------------------------------------
    rass_path = a.out_prefix + "rass.csv"
    if not os.path.exists(rass_path):
        kept = seen = 0
        hdr = None
        with open(rass_path, "w", newline="") as fh:
            w = csv.writer(fh)
            for ln in stream_gz_lines(op, BASE + "icu/chartevents.csv.gz"):
                if not ln.strip():
                    continue
                if hdr is None:
                    hdr = next(csv.reader([ln]))
                    ix = hdr.index("itemid")
                    w.writerow(hdr + ["kind"])
                    continue
                seen += 1
                if not any(k in ln for k in RASS_ITEMS):
                    continue
                row = next(csv.reader([ln]))
                k = RASS_ITEMS.get(row[ix])
                if k:
                    w.writerow(row + [k]); kept += 1
                if a.limit_rows and seen >= a.limit_rows:
                    break
                if seen % 10_000_000 == 0:
                    print(f"   chartevents {seen:,} scanned, {kept:,} kept", flush=True)
        print(f"RASS rows: {kept:,} of {seen:,} scanned -> {rass_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
