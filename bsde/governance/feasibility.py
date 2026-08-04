"""The pre-registration feasibility probe: the six checks that killed six designs, run BEFORE registering.

WHY THIS EXISTS. Of the first thirteen registered designs, **eight died on machinery or coverage rather
than on their hypothesis** — four `gate_failed`, two `absent`, two `blocked`. That is not bad luck. Every
one of those failures was detectable in advance from columns that carry no candidate value at all:

    E21  `BIS/BIS` writes a literal 0.0 while the sensor is detached   -> a Counter on the label column
    E22  every BIS >= 80 window is a facial-EMG artefact               -> P(label) by artefact-channel decile
    E27  base rate 4.0 % against a floor of 5 %                        -> arithmetic on the label alone
    E29  within-pair opioid change is 104 % of chance                  -> a median on two clinical columns
    E31  19 patients in a stratum against a floor of 20                -> a count
    E32  the low MAC tercile has median MAC of 0.00                    -> a quantile on the exposure

**None of those six looks at a candidate.** They are facts about the label, the exposure and the clinical
record, which is exactly the class of information a design may consult before it is registered — the same
class that licensed E22's P4 amendment. So running them costs nothing in integrity and would have saved six
registrations.

WHAT IT IS NOT. It is **not** a way to shop for a design that will pass. It reports numbers; it does not
choose thresholds, and it must be run and its output recorded BEFORE the registration is written, so that
the registration's floors are set knowing the coverage rather than the reverse. A probe run after a gate
fails, used to pick the setting that would have passed, is the exact move `DISCOVERY_LOOP.md` §2 forbids —
E29's nine-cell sweep is the worked example of refusing it.

THE ONE RULE THAT MAKES IT SAFE: **the probe may read the label, the exposure, artefact channels and the
clinical record. It may never read a candidate column.** `probe()` takes the candidate names only so it can
assert they are absent from everything it touches.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from typing import Dict, List, Optional, Sequence

import numpy as np


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def sentinel_check(values: np.ndarray, name: str = "label") -> dict:
    """Is one exact value repeated far more than a continuous measurement should repeat it?

    E21's defect in general form. `BIS/BIS` wrote a literal 0.0 whenever the sensor was detached, and 0 is
    inside the index's valid range, so it read as the deepest possible state. **A populated column is not a
    valid one.** Any single exact value holding more than `FLAG_FRACTION` of a supposedly continuous
    distribution is a sentinel until shown otherwise.
    """
    FLAG_FRACTION = 0.05
    v = values[np.isfinite(values)]
    if not v.size:
        return {"column": name, "n": 0, "verdict": "empty"}
    c = Counter(v.tolist())
    top, n_top = c.most_common(1)[0]
    frac = n_top / v.size
    return {"column": name, "n": int(v.size), "modal_value": float(top),
            "modal_fraction": float(frac),
            "suspected_sentinel": bool(frac > FLAG_FRACTION),
            "verdict": ("SENTINEL SUSPECTED — one exact value holds "
                        f"{frac:.1%} of a continuous column" if frac > FLAG_FRACTION
                        else "no single value dominates")}


def artefact_confound(label: np.ndarray, artefact: np.ndarray, n_bins: int = 10,
                      label_name: str = "label", artefact_name: str = "artefact") -> dict:
    """Does the label track an artefact channel? E22's defect in general form.

    Reports P(label is positive) per decile of the artefact channel. E22's responsive arm ran 0 % across
    eight deciles and 27.6 % in the tenth — the arm was muscle. E26's comparator ran the other way and was
    clean. **The direction matters as much as the strength**, so both are returned.
    """
    m = np.isfinite(label) & np.isfinite(artefact)
    if m.sum() < n_bins * 5:
        return {"verdict": "too few rows to bin", "n": int(m.sum())}
    lab, art = label[m], artefact[m]
    q = np.quantile(art, np.linspace(0, 1, n_bins + 1))
    cells = []
    for i in range(n_bins):
        sel = (art >= q[i]) & ((art <= q[i + 1]) if i == n_bins - 1 else (art < q[i + 1]))
        cells.append(float(lab[sel].mean()) if sel.any() else float("nan"))
    finite = [c for c in cells if np.isfinite(c)]
    spread = (max(finite) - min(finite)) if finite else float("nan")
    rising = bool(len(finite) > 1 and finite[-1] > finite[0])
    return {"label": label_name, "artefact": artefact_name, "n": int(m.sum()),
            "fraction_by_decile": cells, "spread": spread, "rises_with_artefact": rising,
            "verdict": ("LABEL TRACKS THE ARTEFACT — it rises across artefact deciles"
                        if rising and spread > 0.10 else
                        "label falls with the artefact (the physiologically safe direction)"
                        if not rising and spread > 0.10 else
                        "no strong gradient across artefact deciles")}


def exposure_shape(exposure: np.ndarray, name: str = "exposure") -> dict:
    """Where does the exposure actually sit? E32's defect in general form.

    A correlation spans an off-state perfectly happily; only a design that SPLITS the axis has to look at
    where the axis is. Four experiments correlated against MAC before one stratified on it and found the
    bottom third had a median of 0.00 — half the arm was vaporiser-off.
    """
    v = exposure[np.isfinite(exposure)]
    if not v.size:
        return {"column": name, "n": 0, "verdict": "empty"}
    q = np.quantile(v, [0, 0.25, 0.5, 0.75, 1.0])
    zero_frac = float(np.mean(v == 0.0))
    lo_tercile_median = float(np.median(v[v <= np.quantile(v, 1 / 3)]))
    return {"column": name, "n": int(v.size), "quantiles": [float(x) for x in q],
            "zero_fraction": zero_frac, "low_tercile_median": lo_tercile_median,
            "verdict": ("EXPOSURE IS LARGELY OFF — a stratified design will have a degenerate low stratum"
                        if zero_frac > 0.25 else "exposure is distributed across its range")}


def within_subject_variation(values: np.ndarray, subject: np.ndarray, min_distinct: int = 3,
                             name: str = "exposure") -> dict:
    """How many subjects actually vary? Rule 32, which this project has now paid for five times.

    A subject held at one value contributes nothing to a within-subject contrast, and averaging their
    undefined statistic in as a zero dilutes the estimate with subjects who could not have contributed.
    """
    n_ok = 0
    per = []
    for s in np.unique(subject):
        v = values[(subject == s) & np.isfinite(values)]
        d = int(np.unique(v).size)
        per.append(d)
        n_ok += int(d >= min_distinct)
    return {"column": name, "n_subjects": int(np.unique(subject).size),
            "n_with_variation": n_ok, "median_distinct_values": float(np.median(per)) if per else 0.0,
            "verdict": (f"{n_ok} subjects vary; set any floor knowing this"
                        if n_ok else "NO subject varies — a within-subject contrast is impossible")}


def base_rate(label: np.ndarray, band=(0.05, 0.95)) -> dict:
    """The base rate, and whether an AUC computed on it will be interpretable. E27's defect."""
    v = label[np.isfinite(label)]
    if not v.size:
        return {"n": 0, "verdict": "empty"}
    r = float(v.mean())
    return {"n": int(v.size), "base_rate": r, "inside_band": bool(band[0] <= r <= band[1]),
            "verdict": (f"base rate {r:.1%} is inside {band}" if band[0] <= r <= band[1]
                        else f"BASE RATE {r:.1%} IS OUTSIDE {band} — an AUC here is unstable")}


def label_collinear_with_position(label: np.ndarray, group: np.ndarray) -> dict:
    """Is the label a function of WHERE IN THE RECORD a row sits rather than of anything measured?

    E33's defect. It sampled the 121 s before each loss of consciousness and asked "is LOC within 60 s",
    so the base rate was 61/121 = 50.4 % **by construction** and the outcome was near-deterministic in
    position. Any feature drifting monotonically through two minutes predicts that, and what is predicted is
    the clock. The base-rate check passed it, because a base rate inside a band says an AUC is interpretable
    and says nothing about the label being collinear with the row index.

    Reports the AUC of position-within-group for the label. **Near 1.0 or 0.0 means the design is measuring
    time, whatever else it is also measuring.**
    """
    from bsde.verifier.stats import auc as _auc
    pos = np.concatenate([np.arange((group == g).sum(), dtype=float) / max(1, (group == g).sum() - 1)
                          for g in dict.fromkeys(group.tolist())])
    m = np.isfinite(label)
    if len(np.unique(label[m])) < 2:
        return {"verdict": "label is constant"}
    a = float(_auc(label[m], pos[m]))
    return {"auc_of_position": a, "distance_from_chance": abs(a - 0.5),
            "verdict": ("LABEL IS COLLINEAR WITH POSITION — this design predicts the clock"
                        if abs(a - 0.5) > 0.35 else
                        "position carries some information about the label; check the placebo carefully"
                        if abs(a - 0.5) > 0.15 else
                        "label is not strongly explained by position in the record")}


def probe(csv_path: str, label_col: str, exposure_col: Optional[str] = None,
          artefact_col: Optional[str] = None, subject_col: str = "subject",
          candidate_cols: Sequence[str] = (), status_ok: str = "ok") -> dict:
    """Run every applicable check on a table and return a report.

    `candidate_cols` is used ONLY to assert that no candidate column was consulted — the probe raises if a
    caller passes a candidate as the label, exposure or artefact, because that would turn a feasibility
    check into a peek at the result.
    """
    for role, col in (("label", label_col), ("exposure", exposure_col), ("artefact", artefact_col)):
        if col and col in candidate_cols:
            raise ValueError(f"{col!r} is a candidate column and was passed as the {role}. "
                             "The probe may not read a candidate — that is the rule that makes it safe.")
    rows = [r for r in csv.DictReader(open(csv_path, newline="")) if r.get("status", status_ok) == status_ok]
    if not rows:
        return {"table": os.path.basename(csv_path), "verdict": "no usable rows"}
    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)          # noqa: E731
    subj = np.array([r.get(subject_col, "") for r in rows])
    lab = col(label_col)
    rep = {"table": os.path.basename(csv_path), "n_rows": len(rows),
           "n_subjects": int(np.unique(subj).size),
           "sentinel": sentinel_check(lab, label_col)}
    if artefact_col:
        # binarise the label at its median only for the artefact gradient, so the check works for a
        # continuous label as well as a binary one
        binlab = (lab > np.nanmedian(lab)).astype(float)
        binlab[~np.isfinite(lab)] = np.nan
        rep["artefact_confound"] = artefact_confound(binlab, col(artefact_col),
                                                     label_name=label_col, artefact_name=artefact_col)
    if exposure_col:
        rep["exposure_shape"] = exposure_shape(col(exposure_col), exposure_col)
        rep["within_subject_variation"] = within_subject_variation(col(exposure_col), subj,
                                                                   name=exposure_col)
    if set(np.unique(lab[np.isfinite(lab)]).tolist()) <= {0.0, 1.0}:
        rep["base_rate"] = base_rate(lab)
    return rep


def render(rep: dict) -> List[str]:
    out = [f"FEASIBILITY PROBE — {rep.get('table')} "
           f"({rep.get('n_rows')} rows, {rep.get('n_subjects')} subjects)",
           "   Reads the label, exposure, artefact channels and clinical record ONLY. No candidate column.",
           ""]
    for key in ("sentinel", "artefact_confound", "exposure_shape", "within_subject_variation",
                "base_rate"):
        d = rep.get(key)
        if not d:
            continue
        out.append(f"   {key}")
        for k, v in d.items():
            if k == "verdict":
                continue
            if isinstance(v, list):
                v = "[" + " ".join(f"{x:.2f}" if isinstance(x, float) else str(x) for x in v) + "]"
            elif isinstance(v, float):
                v = f"{v:.4g}"
            out.append(f"      {k:26s} {v}")
        out.append(f"      -> {d.get('verdict')}")
        out.append("")
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("usage: feasibility.py TABLE.csv LABEL_COL [EXPOSURE_COL] [ARTEFACT_COL]")
        return 2
    rep = probe(argv[0], argv[1],
                exposure_col=argv[2] if len(argv) > 2 else None,
                artefact_col=argv[3] if len(argv) > 3 else None)
    print("\n".join(render(rep)))
    print(json.dumps(rep, default=float)[:0])          # keeps json import honest without noisy output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
