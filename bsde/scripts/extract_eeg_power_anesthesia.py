"""Challenge A and C substrate: MGH multitaper spectra with BEHAVIOURAL consciousness labels, two agents.

WHY THIS DEPOSIT, AND WHY NOW. `docs/CHALLENGE_A_AUDIT_2026_08_01.md` closed E139-E142 with a structural
statement: no reachable deposit has loss AND recovery AND two anaesthetics, so Challenge A's brief cannot
be tested as written. `eeg-power-anesthesia` 1.0.0 (MGH, granted 2026-08-03) does not fully solve that,
but it improves on every axis that made the Krause table weak:

    Krause (E35/E36/E139-E142)              eeg-power-anesthesia
    15 patients in the drug contrast        44 OR cases, 10 volunteers
    dex vs propofol, disjoint patients      sevo vs propofol, disjoint cases (rx_sorted_case_ids.yml)
    OAA/S, scored by an observer            LOC = P(response to click AND verbal cue) < 5%   -- behavioural
    NO recovery in any patient              ROC recorded for every VOLUNTEER (P(response) back above 5%)
    13 derived features, no raw             100-bin multitaper spectra, so features are computed here
    no quality series                       per-window EEGquality boolean for every OR case

**The state label is not read off the EEG.** That removes the circularity caveat E133 and E136 both had to
declare for sleep staging, and it is stronger than the Krause OAA/S because response probability to a
stimulus is an operational threshold rather than a rater's judgement.

WHAT IT CANNOT DO, stated before anything is extracted so no design assumes otherwise:
  * **Spectra only.** No raw traces, so no phase measure. E36's PHASE family (wPLI variants) is not
    computable here at all, and neither is irreversibility, Lempel-Ziv or PAC. Any replication of the
    family split is confined to the AMPLITUDE half.
  * **No dose or concentration record**, so E122's "does the EEG add over pharmacology" cannot be asked.
  * **OR cohort has no ROC** -- recording stops at end of surgery -- and its LOC is *surgery start*, a
    proxy the deposit's own documentation flags: epochs between induction and surgery start are NaN
    precisely because the true LOC time is unknowable retrospectively.
  * **The volunteer cohort is propofol only.** So loss-and-recovery and two-agents remain in different
    arms, exactly as before. What is new is that both arms are in ONE deposit, one pipeline, one
    frequency axis -- which E49 established is the thing cross-deposit comparison cannot buy at any n.

WHAT IS COMPUTED. One row per 2 s epoch: relative band powers (linear scale, converted back from dB
before any ratio is taken), spectral edge 95, spectral entropy, an aperiodic slope fitted over 1-40 Hz,
alpha peak frequency and prominence, and total power. Plus the deposit's own label, time and quality flag.
Nothing is aggregated per case here -- aggregation is an analysis decision and rule 10 says a per-subject
reduction is look-ahead until proven otherwise, so it belongs in the experiment, not the extractor.

DISK. The Sdb files total roughly 800 MB as text and this sandbox has a fixed writable allowance. Each
case is streamed, reduced and discarded; nothing but the feature table touches disk. The output is
patient-derived and is written to a gitignored path.

RESUMABLE. Re-reads its own output and fetches only the cases not already present.

    python bsde/scripts/extract_eeg_power_anesthesia.py --limit 2
"""
from __future__ import annotations

import argparse
import csv
import http.cookiejar
import io
import os
import re
import sys
import urllib.parse
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
BASE = "https://physionet.org/files/eeg-power-anesthesia/1.0.0/"
OUT = os.path.join(RESULTS, "mgh_power_windows.csv")

BANDS = {"delta": (0.5, 4.0), "theta": (4.0, 8.0), "alpha": (8.0, 13.0),
         "beta": (13.0, 30.0), "gamma": (30.0, 49.5)}
FIELDS = ["case", "cohort", "arm", "t", "label", "quality", "total_power_db",
          "rel_delta", "rel_theta", "rel_alpha", "rel_beta", "rel_gamma",
          "spectral_edge_95", "spectral_entropy", "exponent_1_40", "alpha_peak_hz", "alpha_prom_db"]


def session():
    """PhysioNet Django session. Credentials from the environment, else ~/.netrc; never from this file."""
    u = os.environ.get("PHYSIONET_USER")
    p = os.environ.get("PHYSIONET_PASSWORD")
    if not (u and p):
        try:
            import netrc
            a = netrc.netrc().authenticators("physionet.org")
            if a:
                u, _acct, p = a
        except Exception:                                                      # noqa: BLE001
            pass
    if not (u and p):
        raise SystemExit("set PHYSIONET_USER / PHYSIONET_PASSWORD (see docs/CREDENTIALS.md)")
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0"), ("Referer", "https://physionet.org/login/")]
    h = op.open("https://physionet.org/login/", timeout=60).read().decode("utf8", "replace")
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', h).group(1)
    op.open(urllib.request.Request("https://physionet.org/login/", data=urllib.parse.urlencode(
        {"csrfmiddlewaretoken": tok, "username": u, "password": p}).encode()), timeout=60)
    if not any(c.name == "sessionid" for c in cj):
        raise SystemExit("PhysioNet login produced no session cookie")
    return op


def _get(op, path, timeout=900):
    return op.open(BASE + path, timeout=timeout).read().decode("utf8", "replace")


def _vec(txt):
    return np.array([float(x) for x in txt.split() if x.strip()], float)


def arms(op):
    """pure_propofol / pure_sevo / mixed, from the deposit's own yml. Parsed, not guessed."""
    y = _get(op, "OR/rx_sorted_case_ids.yml")
    out, cur = {}, None
    for ln in y.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.endswith(":") and not s.startswith("-"):
            cur = s[:-1].strip()
            continue
        m = re.match(r"^-\s*(.+?)\s*$", s)
        if m and cur:
            out[m.group(1).strip().strip("'\"")] = cur
    return out


def features(S_db, f):
    """Per-epoch features from a (n_freq, n_time) dB spectrogram. dB is undone before any ratio."""
    P = np.power(10.0, np.asarray(S_db, float) / 10.0)          # dB -> linear power
    P = np.where(np.isfinite(P), P, np.nan)
    tot = np.nansum(P, axis=0)
    out = {"total_power_db": 10.0 * np.log10(np.where(tot > 0, tot, np.nan))}
    for name, (lo, hi) in BANDS.items():
        m = (f >= lo) & (f < hi)
        out["rel_" + name] = np.nansum(P[m], axis=0) / np.where(tot > 0, tot, np.nan)
    c = np.nancumsum(P, axis=0) / np.where(tot > 0, tot, np.nan)
    idx = np.argmax(c >= 0.95, axis=0)
    out["spectral_edge_95"] = f[np.clip(idx, 0, len(f) - 1)]
    q = P / np.where(tot > 0, tot, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["spectral_entropy"] = -np.nansum(q * np.log(np.where(q > 0, q, np.nan)), axis=0) / np.log(len(f))
    fit = (f >= 1.0) & (f <= 40.0)
    lf = np.log10(f[fit])
    A = np.c_[np.ones(len(lf)), lf]
    lp = np.log10(np.where(P[fit] > 0, P[fit], np.nan))
    ok = np.isfinite(lp).all(axis=0)
    slope = np.full(P.shape[1], np.nan)
    if ok.any():
        beta, *_ = np.linalg.lstsq(A, lp[:, ok], rcond=None)
        slope[ok] = -beta[1]                                    # positive = steeper 1/f
    out["exponent_1_40"] = slope
    am = (f >= 8.0) & (f <= 13.0)
    bm = ((f >= 4.0) & (f < 8.0)) | ((f > 13.0) & (f <= 20.0))
    ai = np.argmax(np.where(np.isfinite(S_db[am]), S_db[am], -np.inf), axis=0)
    out["alpha_peak_hz"] = f[am][np.clip(ai, 0, am.sum() - 1)]
    out["alpha_prom_db"] = (np.nanmax(S_db[am], axis=0) - np.nanmedian(S_db[bm], axis=0))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cohort", choices=["OR", "Volunteer", "both"], default="both")
    a = ap.parse_args(argv)

    op = session()
    rx = arms(op)
    print(f"drug arms parsed: " +
          ", ".join(f"{k}={sum(1 for v in rx.values() if v == k)}" for k in sorted(set(rx.values()))),
          flush=True)

    listing = {}
    for sub in (["OR", "Volunteer"] if a.cohort == "both" else [a.cohort]):
        b = op.open(BASE + sub + "/", timeout=120).read().decode("utf8", "replace")
        ids = sorted({m.group(1) for m in
                      (re.match(r"^(.+)_Sdb\.csv$", x) for x in re.findall(r'href="([^"?]+)"', b))
                      if m})
        listing[sub] = ids
        print(f"{sub}: {len(ids)} cases", flush=True)

    done = set()
    if os.path.exists(a.out) and os.path.getsize(a.out) > 0:
        for r in csv.DictReader(open(a.out, newline="")):
            done.add((r["cohort"], r["case"]))
    todo = [(c, i) for c in listing for i in listing[c] if (c, i) not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(done)} case-rows already present, {len(todo)} to fetch -> {a.out}", flush=True)

    new = not os.path.exists(a.out) or os.path.getsize(a.out) == 0
    with open(a.out, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for n, (cohort, case) in enumerate(todo, 1):
            try:
                f = _vec(_get(op, f"{cohort}/{case}_f.csv"))
                t = _vec(_get(op, f"{cohort}/{case}_t.csv"))
                lab = _vec(_get(op, f"{cohort}/{case}_l.csv"))
                qual = (_vec(_get(op, f"{cohort}/{case}_EEGquality.csv"))
                        if cohort == "OR" else np.ones(len(t)))
                S = np.loadtxt(io.StringIO(_get(op, f"{cohort}/{case}_Sdb.csv")), delimiter=",")
                if S.shape[0] != len(f):                     # (freq, time) is the documented orientation
                    S = S.T
                assert S.shape == (len(f), len(t)), f"{S.shape} vs ({len(f)},{len(t)})"
                ft = features(S, f)
                arm = rx.get(case, "volunteer_propofol" if cohort == "Volunteer" else "unknown")
                for i in range(len(t)):
                    w.writerow({"case": case, "cohort": cohort, "arm": arm,
                                "t": f"{t[i]:g}", "label": f"{lab[i]:g}", "quality": f"{qual[i]:g}",
                                **{k: f"{v[i]:.6g}" for k, v in ft.items()}})
                fh.flush()
                nl = int(np.sum(lab == 1))
                nu = int(np.sum(lab == 0))
                print(f"   [{n}/{len(todo)}] {cohort}/{case} arm={arm} {len(t)} epochs "
                      f"(conscious {nl}, unconscious {nu}, nan {len(lab) - nl - nu})", flush=True)
            except Exception as e:                                             # noqa: BLE001
                print(f"   [{n}/{len(todo)}] {cohort}/{case} ERROR {type(e).__name__}: {e}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
