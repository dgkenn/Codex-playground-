"""client.py -- credentialed PhysioNet loader for INSPIRE v1.4.2.

INSPIRE (doi:10.13026/93f2-3t63) is a restricted-access PhysioNet dataset
gated behind:
  1. A PhysioNet account (physionet.org/register).
  2. Completion and approval of the INSPIRE Data Use Agreement (DUA).
  3. Downloading the data locally (wget/curl from physionet.org/files/inspire/1.4.2/).

This module does NOT download data automatically.  It reads from a local
directory set via the environment variable ``INSPIRE_DATA_DIR`` (preferred) or
``inspire.data_dir`` in the study config.  If neither points to a directory
that contains at least the ``operations.csv`` file, ``available()`` returns
False and every ``load_table()`` call raises ``InspireNotAvailable``.

Environment variables
---------------------
INSPIRE_DATA_DIR   Absolute path to the local INSPIRE directory (required).
PHYSIONET_USER     PhysioNet username (stored for audit; never transmitted here).
PHYSIONET_PASS     PhysioNet password (stored for audit; never transmitted here).

The PHYSIONET_USER/PHYSIONET_PASS are NOT used for any network call in this
module -- they exist so that a companion ``download.sh`` script (not checked in)
can use wget --user / --password to pull the files before this code is invoked.

INSPIRE table catalogue (v1.4.2)
---------------------------------
operations.csv    -- one row per surgery: caseid, subjectid, optype, asa,
                     emergency, sex, age, height, weight, bmi, department,
                     opstart, opend, anstart, aneend, inhosp_death, icu_days,
                     hosp_days, (device flags: crrt, ecmo, iabp, ventilator)
vitals.csv        -- OR vitals at ~5-min intervals: caseid, time, mbp, sbp,
                     dbp, hr, spo2, etco2, rr, temp, fio2, peep, tv, pip,
                     compliance, minvol
labs.csv          -- lab results: caseid, time, name, result
                     names include: cr (creatinine, mg/dL), bun, na, k, hco3,
                     hgb, wbc, plt, inr, ast, alt, tbil, lac, pco2, po2, ph,
                     be (base excess); troponin coverage is INCOMPLETE -- verify
medications.csv   -- drug events: caseid, time, name, amount, unit, route
                     key names: phenylephrine, norepinephrine, epinephrine,
                     vasopressin, dopamine, dobutamine (pressors);
                     propofol, sevoflurane, desflurane, isoflurane (anesthetics)

NOTE: Column names above are best-effort from PhysioNet docs.  Validate against
the real header row on first access and update ``COLUMN_MAP`` in pfds_clinical.py.
"""
from __future__ import annotations

import csv
import os
from typing import Any


class InspireNotAvailable(RuntimeError):
    """Raised when INSPIRE data directory is not set or does not exist."""


_SENTINEL_FILE = "operations.csv"   # presence check for the data directory


def _data_dir(cfg: dict[str, Any] | None = None) -> str | None:
    """Resolve the INSPIRE data directory from env or config."""
    d = os.environ.get("INSPIRE_DATA_DIR", "").strip()
    if not d and cfg is not None:
        d = (cfg.get("inspire", {}) or {}).get("data_dir", "")
    return d if d else None


def available(cfg: dict[str, Any] | None = None) -> bool:
    """Return True only when INSPIRE data is locally accessible.

    Prints a diagnostic when False so that ``python cli.py preflight`` gives a
    clear action item without raising.
    """
    d = _data_dir(cfg)
    if not d:
        print(
            "[INSPIRE] NOT available: set INSPIRE_DATA_DIR to the local INSPIRE "
            "directory (physionet.org/content/inspire/1.4.2/). "
            "Requires PhysioNet account + DUA approval."
        )
        return False
    sentinel = os.path.join(d, _SENTINEL_FILE)
    if not os.path.isfile(sentinel):
        print(
            f"[INSPIRE] NOT available: INSPIRE_DATA_DIR={d!r} exists but "
            f"'{_SENTINEL_FILE}' not found. "
            "Has the data been downloaded? "
            "See vitaldb_aki/inspire/README.md for download instructions."
        )
        return False
    return True


def load_table(
    name: str,
    cfg: dict[str, Any] | None = None,
    *,
    max_rows: int | None = None,
) -> list[dict[str, str]]:
    """Load an INSPIRE CSV table by name (without the .csv extension).

    Parameters
    ----------
    name:     one of 'operations', 'vitals', 'labs', 'medications'
    cfg:      optional loaded config dict (may contain inspire.data_dir)
    max_rows: if set, read at most this many data rows (useful for testing)

    Returns
    -------
    List of row dicts {column_name: raw_string_value}.  All values are strings;
    callers should use ``_to_float`` / ``_to_int`` to parse numeric columns.

    Raises
    ------
    InspireNotAvailable  if the data directory is not set or does not exist.
    FileNotFoundError    if the requested table file does not exist.
    """
    d = _data_dir(cfg)
    if not d or not os.path.isfile(os.path.join(d, _SENTINEL_FILE)):
        raise InspireNotAvailable(
            "INSPIRE data not available. "
            "Set INSPIRE_DATA_DIR and ensure data is downloaded. "
            "See vitaldb_aki/inspire/README.md."
        )
    path = os.path.join(d, f"{name}.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"INSPIRE table '{name}' not found at {path!r}. "
            f"Known tables: operations, vitals, labs, medications."
        )
    rows: list[dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            if max_rows is not None and i >= max_rows:
                break
            rows.append(dict(row))
    return rows


def to_float(v: Any) -> float | None:
    """Parse a cell value to float; returns None for missing / non-numeric."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "na", "none", "null", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_int(v: Any) -> int | None:
    """Parse a cell value to int; returns None for missing / non-numeric."""
    f = to_float(v)
    return int(f) if f is not None else None
