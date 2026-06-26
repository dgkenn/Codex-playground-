"""client.py -- robust, cached access to the VitalDB open API (Sec 4).

VitalDB is OPEN data (no credentials, no DUA), so the three clinical tables can be
pulled directly and cached to local disk. Responses are gzip-encoded and large
(/labs is ~900k rows), so this client:
  * sends Accept-Encoding: gzip and transparently decompresses,
  * retries on transient IncompleteRead / network errors (exponential backoff),
  * caches each table as a plain CSV under data.cache_dir so downstream stages
    (and tests) run offline and deterministically.

Only stdlib is used here (urllib/csv/gzip) so cohort construction has no heavy
deps; pandas is imported lazily by callers that want a DataFrame.
"""
from __future__ import annotations

import csv
import gzip
import io
import os
import time
import urllib.request
from typing import Any


def _fetch_url(url: str, retries: int = 4, timeout: int = 240) -> str:
    """GET `url`, decompress gzip, retry transient failures with backoff."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "vitaldb-aki/1.0", "Accept-Encoding": "gzip"}
            )
            raw = urllib.request.urlopen(req, timeout=timeout).read()
            try:
                return gzip.decompress(raw).decode("utf-8", "replace")
            except OSError:
                return raw.decode("utf-8", "replace")
        except Exception as exc:  # transient network / IncompleteRead
            last = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to fetch {url} after {retries} tries: {last}")


def _cache_path(cfg: dict[str, Any], name: str) -> str:
    cdir = cfg["data"]["cache_dir"]
    os.makedirs(cdir, exist_ok=True)
    return os.path.join(cdir, f"{name}.csv")


def fetch_table(cfg: dict[str, Any], name: str, refresh: bool = False) -> list[dict]:
    """Return a VitalDB table (`cases` | `labs` | `trks`) as a list of row dicts.

    Caches the raw CSV under data.cache_dir on first pull; subsequent calls read
    the cache unless `refresh=True`. The UTF-8 BOM on the header is stripped.
    """
    url = cfg["data"][f"{name}_url"]
    path = _cache_path(cfg, name)
    if refresh or not os.path.exists(path):
        text = _fetch_url(url)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = [h.lstrip("﻿") for h in next(reader)]
        return [dict(zip(header, row)) for row in reader if row]


def fetch_cases(cfg: dict[str, Any], refresh: bool = False) -> list[dict]:
    return fetch_table(cfg, "cases", refresh=refresh)


def fetch_labs(cfg: dict[str, Any], refresh: bool = False) -> list[dict]:
    return fetch_table(cfg, "labs", refresh=refresh)


def creatinine_by_case(cfg: dict[str, Any], refresh: bool = False) -> dict[str, list[tuple[float, float]]]:
    """Map caseid -> sorted [(dt_seconds, creatinine_mgdl), ...] from /labs.

    dt is seconds from casestart (== 0); negative dt is preoperative. Only the
    `cr` analyte is returned (not crp/ccr). Non-numeric results are dropped.
    """
    labs = fetch_labs(cfg, refresh=refresh)
    out: dict[str, list[tuple[float, float]]] = {}
    for r in labs:
        if r.get("name") != "cr":
            continue
        try:
            dt = float(r["dt"])
            val = float(r["result"])
        except (KeyError, ValueError):
            continue
        out.setdefault(r["caseid"], []).append((dt, val))
    for cid in out:
        out[cid].sort(key=lambda x: x[0])
    return out


def to_float(v: Any) -> float | None:
    """Parse a VitalDB cell to float, treating '' / 'nan' / None as missing."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "na", "none"):
        return None
    try:
        return float(s)
    except ValueError:
        return None
