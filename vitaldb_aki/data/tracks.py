"""tracks.py -- per-case waveform / numeric track access (Sec 7C/7F, Sec 8).

The /cases table carries cumulative intraoperative totals, but the hypotension
features (Sec 7C: area-under-MAP-thresholds) and the PK exposure features (Sec 8:
effect-site concentration time-series, infusion integrals) need the per-case
time-series. VitalDB serves each track at  /<tid>  as a two-column CSV
(Time_seconds, value); the (caseid, tname) -> tid map comes from /trks.

This module builds that index once (cached) and downloads/caches individual
tracks under cache/tracks/<tid>.csv so the heavy feature stages are resumable and
offline-replayable. Times are seconds from casestart (== 0), matching /labs and
the KDIGO anchor.

stdlib only.
"""
from __future__ import annotations

import csv
import gzip
import http.client
import io
import os
import time
import urllib.request
from typing import Any

from vitaldb_aki.data.client import fetch_table


def _tid_index(cfg: dict[str, Any]) -> dict[tuple[str, str], str]:
    """Map (caseid, tname) -> tid from /trks (cached on the table layer)."""
    trks = fetch_table(cfg, "trks")
    return {(t["caseid"], t["tname"]): t["tid"] for t in trks}


_INDEX: dict[tuple[str, str], str] | None = None


def tid_for(cfg: dict[str, Any], caseid: str, tname: str) -> str | None:
    global _INDEX
    if _INDEX is None:
        _INDEX = _tid_index(cfg)
    return _INDEX.get((str(caseid), tname))


def available_tracks(cfg: dict[str, Any], caseid: str) -> list[str]:
    global _INDEX
    if _INDEX is None:
        _INDEX = _tid_index(cfg)
    return [tn for (cid, tn) in _INDEX if cid == str(caseid)]


def _fetch(url: str, retries: int = 6, timeout: int = 240) -> str:
    """Fetch a track, robust to the IncompleteRead truncation that hits the large
    500 Hz waveform tracks. Reads to EOF in a loop, and after two gzip failures
    falls back to identity (uncompressed) encoding -- gzip streams from the proxy
    are the usual truncation culprit on multi-MB responses."""
    last: Exception | None = None
    for attempt in range(retries):
        use_gzip = attempt < 2          # first two tries gzip; then uncompressed
        try:
            headers = {"User-Agent": "vitaldb-aki/1.0"}
            if use_gzip:
                headers["Accept-Encoding"] = "gzip"
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            chunks = []                 # drain to EOF tolerating a final short read
            try:
                while True:
                    b = resp.read(1 << 20)
                    if not b:
                        break
                    chunks.append(b)
            except http.client.IncompleteRead as ir:
                chunks.append(ir.partial)
                raise                    # partial data is unreliable -> retry
            raw = b"".join(chunks)
            if use_gzip:
                try:
                    return gzip.decompress(raw).decode("utf-8", "replace")
                except OSError:
                    return raw.decode("utf-8", "replace")
            return raw.decode("utf-8", "replace")
        except Exception as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(min(2 ** attempt, 16))
    raise RuntimeError(f"failed to fetch track {url}: {last}")


def download_track(cfg: dict[str, Any], caseid: str, tname: str,
                   refresh: bool = False) -> list[tuple[float, float]]:
    """Return [(t_seconds, value), ...] for one track, or [] if absent.

    Caches the raw CSV under cache/tracks/<tid>.csv. Non-numeric / blank samples
    are dropped (so callers get clean numeric series); physiologic-range filtering
    is the caller's job (artifacts like a zeroed arterial line are real in VitalDB).
    """
    tid = tid_for(cfg, caseid, tname)
    if not tid:
        return []
    tdir = os.path.join(cfg["data"]["cache_dir"], "tracks")
    os.makedirs(tdir, exist_ok=True)
    path = os.path.join(tdir, f"{tid}.csv")
    if refresh or not os.path.exists(path):
        text = _fetch(cfg["data"]["api_base"].rstrip("/") + "/" + tid)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    out: list[tuple[float, float]] = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header: Time, <tname>
        for row in reader:
            if len(row) < 2:
                continue
            try:
                out.append((float(row[0]), float(row[1])))
            except ValueError:
                continue
    return out


def first_available(cfg: dict[str, Any], caseid: str, tnames: list[str],
                    refresh: bool = False) -> tuple[str | None, list[tuple[float, float]]]:
    """Return (tname, series) for the first of `tnames` present for this case.
    Lets a feature prefer invasive ART_MBP and fall back to NIBP_MBP, etc."""
    for tn in tnames:
        series = download_track(cfg, caseid, tn, refresh=refresh)
        if series:
            return tn, series
    return None, []
