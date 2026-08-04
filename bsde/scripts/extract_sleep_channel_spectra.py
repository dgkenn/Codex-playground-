"""Per-channel low-frequency power on the Sleep-EDFx five-stage windows -- frontal and posterior SEPARATELY.

WHY. E93 and E95 placed REM at **0.629 of the way from wake to N3** on a whole-head aperiodic coordinate,
past N1 and nearer N2 than wake. That matches the AROUSAL ordering and contradicts the EXPERIENCE ordering,
in which REM sits with wake -- and REM is the stage where those two come apart.

Siclari et al., *Nature Neuroscience* 2017 (**PMID 28394322**, record verified through E-utilities) report
that dreaming occurs in both REM and NREM sleep and that "reports of dream experience were associated with
local decreases in low-frequency activity in posterior cortical regions". **Our coordinate is a whole-head
average, so it is structurally incapable of expressing a posterior-local effect** -- the reduction throws
away exactly the locality their result rests on.

Sleep-EDFx ships two derivations, `EEG Fpz-Cz` and `EEG Pz-Oz`, on all 142 subjects across all five
stages. This pass keeps them SEPARATE so a posterior-versus-frontal contrast is computable at all. Every
existing sleep table medians across channels and cannot support one.

WHAT IS EMITTED, per window, per channel:

    rel_delta   relative power 1-4 Hz
    rel_low     relative power 0.5-8 Hz -- a WIDER operationalisation of "low-frequency", emitted because
                the Siclari abstract says "low-frequency" without naming a band and the full text has not
                been read here. Which of the two is primary is declared in E100, before either is used.
    exponent    aperiodic exponent, 1-40 Hz, so the per-channel result is comparable to the whole-head
                coordinate it is being tested against rather than being a different quantity.

THE WINDOWS ARE NOT RECOMPUTED. `sleep_edfx_five_stage_worklist.json` is the committed record of exactly
which (subject, stage, start_seconds, window_s) the existing tables came from; this reads the same list and
joins on `recording_id`, so a silent mismatch is impossible.

CHANNELS ARE MATCHED ON THEIR FULL LABEL, not a substring (rule 61). A window whose two expected
derivations are not both present is refused rather than guessed at.

    python bsde/scripts/extract_sleep_channel_spectra.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.ingestion.sleep_edfx import read_edf_window_http                 # noqa: E402

WORKLIST = os.path.join(HERE, "..", "results", "sleep_edfx_five_stage_worklist.json")
OUT = os.path.join(HERE, "..", "results", "sleep_edfx_channel_spectra.csv")
FRONTAL_LABEL, POSTERIOR_LABEL = "EEG Fpz-Cz", "EEG Pz-Oz"
FIELDS = ["recording_id", "subject", "label",
          "frontal_rel_delta", "posterior_rel_delta",
          "frontal_rel_low", "posterior_rel_low",
          "frontal_exponent", "posterior_exponent", "sfreq", "n_samples"]


def channel_measures(x, sfreq):
    from bsde.features.aperiodic import fit_aperiodic, welch_psd
    from bsde.features.spectral import relative_band_power
    out = {}
    f, p = welch_psd(np.asarray(x, float), float(sfreq), window_s=4.0, overlap=0.5)
    out["rel_delta"] = float(relative_band_power(f, p, 1.0, 4.0))
    out["rel_low"] = float(relative_band_power(f, p, 0.5, 8.0))
    try:
        out["exponent"] = float(fit_aperiodic(f, p, 1.0, 40.0, "loglog_robust")["exponent"])
    except Exception:                                                      # noqa: BLE001
        out["exponent"] = float("nan")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    rows = json.load(open(os.path.abspath(WORKLIST)))
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {r["recording_id"] for r in csv.DictReader(fh)}
    todo = [r for r in rows if r["recording_id"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(rows)} windows in the worklist, {len(done)} done, {len(todo)} to fetch", flush=True)

    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    n_ok = n_err = 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, r in enumerate(todo, 1):
            try:
                data, ch, sf, _ = read_edf_window_http(
                    r["url"], window_s=r["window_s"], start_seconds=r["start_seconds"],
                    channel_regex="^EEG")
                names = [c.strip() for c in ch]
                if FRONTAL_LABEL not in names or POSTERIOR_LABEL not in names:
                    raise ValueError(f"expected both derivations, got {names}")
                d = np.asarray(data, float)
                fr = channel_measures(d[names.index(FRONTAL_LABEL)], sf)
                po = channel_measures(d[names.index(POSTERIOR_LABEL)], sf)
                w.writerow({"recording_id": r["recording_id"], "subject": r["subject"],
                            "label": r["label"],
                            "frontal_rel_delta": f"{fr['rel_delta']:.8g}",
                            "posterior_rel_delta": f"{po['rel_delta']:.8g}",
                            "frontal_rel_low": f"{fr['rel_low']:.8g}",
                            "posterior_rel_low": f"{po['rel_low']:.8g}",
                            "frontal_exponent": f"{fr['exponent']:.8g}",
                            "posterior_exponent": f"{po['exponent']:.8g}",
                            "sfreq": f"{float(sf):.4g}", "n_samples": int(d.shape[1])})
                n_ok += 1
            except Exception as e:                                         # noqa: BLE001
                n_err += 1
                if n_err <= 5:
                    print(f"   FAIL {r['recording_id']}: {type(e).__name__}: {e}", flush=True)
            fh.flush()
            if i % 25 == 0 or i == len(todo):
                print(f"   [{i}/{len(todo)}] ok={n_ok} err={n_err}", flush=True)
    print(f"   wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
