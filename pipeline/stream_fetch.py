"""stream_fetch.py -- per-recording streaming / batch-and-delete (Sec 0, 4).

The cardinal rule: never hold more than one shard of raw signal on disk. Two
access modes are supported, selected by `data.access_mode`:

  * "stream"           -- yield a handle that reads the recording lazily; the
                          caller consumes it and nothing lands on disk.
  * "batch_and_delete" -- download one shard to scratch, yield its members,
                          then delete the shard before fetching the next.

The actual BDSP transport is an adapter boundary (`_BDSPClient`). It is left as
a thin, well-documented seam: wiring it to the Brain Data Science Platform's
credentialed API is the only site-specific I/O in the whole pipeline.
"""
from __future__ import annotations

import contextlib
import os
import shutil
from dataclasses import dataclass
from typing import Any, Iterable, Iterator

from guards.heldout_guard import HeldoutGuard


@dataclass(frozen=True)
class RecordingRef:
    """Identity + acquisition metadata for one EEG recording.

    Phase-1 safe: carries EEG-acquisition metadata only -- no outcome, no ICD,
    no medications, no report text (Sec 0, 13).
    """
    recording_id: str
    patient_id: str
    hospital: str
    device: str | None = None
    sampling_rate: float | None = None
    montage: str | None = None
    n_channels: int | None = None
    duration_s: float | None = None
    care_setting: str | None = None
    age: float | None = None
    sex: str | None = None
    uri: str | None = None


class _BDSPClient:
    """Adapter boundary to the Brain Data Science Platform.

    Replace the method bodies with credentialed BDSP calls. They are isolated
    here so the rest of the pipeline never imports transport details.
    """

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg

    def list_recordings(self, hospital: str) -> Iterable[RecordingRef]:  # pragma: no cover - I/O seam
        raise NotImplementedError(
            "Wire _BDSPClient.list_recordings to the credentialed BDSP catalog. "
            "It must return RecordingRef objects with acquisition metadata only."
        )

    def open_stream(self, ref: RecordingRef):  # pragma: no cover - I/O seam
        raise NotImplementedError(
            "Wire _BDSPClient.open_stream to return a lazy raw reader "
            "(e.g. an mne.io.Raw with preload=False)."
        )

    def download_shard(self, refs: list[RecordingRef], dest: str) -> str:  # pragma: no cover - I/O seam
        raise NotImplementedError(
            "Wire _BDSPClient.download_shard for batch_and_delete mode."
        )


def iter_qualifying_recordings(
    cfg: dict[str, Any], guard: HeldoutGuard, client: _BDSPClient | None = None
) -> Iterator[RecordingRef]:
    """Yield eligible recordings from the *discovery* sites only (Phase 1).

    Every site label is routed through the firewall guard, so a held-out
    recording can never enter the Phase-1 stream even if the catalog returns it.
    Applies the one-recording-per-patient and age eligibility rules (Sec 5).
    """
    client = client or _BDSPClient(cfg)
    min_age = cfg.get("cohort", {}).get("primary_min_age_years", 18)
    seen_patients: set[str] = set()

    sites = list(cfg.get("sites", {}).get("discovery") or [])
    for hospital in sites:
        guard.check_site_access(hospital, context="stream_fetch")
        for ref in client.list_recordings(hospital):
            guard.check_site_access(ref.hospital, context="stream_fetch:ref")
            if ref.age is not None and ref.age < min_age:
                continue
            if ref.patient_id in seen_patients:  # earliest-qualifying upstream
                continue
            seen_patients.add(ref.patient_id)
            yield ref


@contextlib.contextmanager
def open_recording(cfg: dict[str, Any], ref: RecordingRef, client: _BDSPClient):
    """Context manager that yields a lazy raw reader and guarantees cleanup.

    In batch_and_delete mode the shard is removed on exit; in stream mode the
    reader is simply closed. Either way nothing raw survives the `with` block --
    the disk-sparing contract (Sec 0).
    """
    mode = cfg.get("data", {}).get("access_mode", "stream")
    scratch = cfg.get("data", {}).get("scratch_dir", "/tmp/heedb_scratch")
    raw = None
    shard_dir = None
    try:
        if mode == "batch_and_delete":
            os.makedirs(scratch, exist_ok=True)
            shard_dir = client.download_shard([ref], scratch)
        raw = client.open_stream(ref)
        yield raw
    finally:
        if raw is not None and hasattr(raw, "close"):
            with contextlib.suppress(Exception):
                raw.close()
        # Per-recording temp file downloaded by a transport (stream mode).
        tmp = getattr(raw, "_fetch_tmp", None)
        if tmp and os.path.exists(tmp):
            with contextlib.suppress(Exception):
                os.remove(tmp)
        if shard_dir and os.path.isdir(shard_dir):
            shutil.rmtree(shard_dir, ignore_errors=True)  # delete before next


def make_client(cfg: dict[str, Any]) -> "_BDSPClient":
    """Factory: a real BDSP S3 client when `data.source == 'BDSP'` and an S3
    access point is configured; a LocalEDFClient when `data.source == 'local_edf'`;
    otherwise the abstract base (which raises until wired). Keeps run_pass1
    transport-agnostic."""
    if cfg.get("data", {}).get("source") == "BDSP" and cfg.get("data", {}).get("s3"):
        return BDSPS3Client(cfg)
    if cfg.get("data", {}).get("source") == "local_edf":
        return LocalEDFClient(cfg)
    return _BDSPClient(cfg)


class LocalEDFClient(_BDSPClient):
    """Concrete transport for a LOCAL directory of EDF files (no network I/O).

    Designed for integration tests and offline development: the user supplies
    their own EDF files; this client reads acquisition metadata from a small
    manifest in the config and serves the files via `mne.io.read_raw_edf`.

    Configuration
    -------------
    Set ``cfg["data"]["source"] = "local_edf"`` and supply a manifest under
    ``cfg["data"]["local_edf"]``::

        data:
          source: local_edf
          local_edf:
            dir: /path/to/edf_files          # optional base dir (ignored when
                                              # each entry has an absolute path)
            recordings:
              - recording_id: rec001
                patient_id:   pt001
                hospital:     MGH
                age:          45.0
                sex:          M
                sampling_rate: 200.0
                file:         rec001.edf     # relative to `dir`, OR absolute

    Disk-sparing contract
    ---------------------
    These are the *user's own files* (not temporary S3 fetches), so
    ``open_recording`` must NOT delete them on context exit.  We signal this by
    leaving ``raw._fetch_tmp = None`` on every opened Raw object -- the cleanup
    branch in ``open_recording`` then skips the delete step, exactly as it does
    for the BDSP stream-mode client when the raw hasn't been written to scratch.
    """

    def __init__(self, cfg: dict[str, Any]):
        super().__init__(cfg)
        local_cfg = cfg.get("data", {}).get("local_edf", {})
        self._base_dir: str = str(local_cfg.get("dir", ""))
        self._recordings: list[dict] = list(local_cfg.get("recordings", []))

    # -- catalog ------------------------------------------------------------
    def list_recordings(self, hospital: str) -> Iterable[RecordingRef]:
        """Yield RecordingRefs for every manifest entry whose hospital matches."""
        for entry in self._recordings:
            if entry.get("hospital") != hospital:
                continue
            file_path = str(entry.get("file", ""))
            if not os.path.isabs(file_path) and self._base_dir:
                file_path = os.path.join(self._base_dir, file_path)
            yield RecordingRef(
                recording_id=str(entry.get("recording_id", "")),
                patient_id=str(entry.get("patient_id", "")),
                hospital=str(entry.get("hospital", "")),
                device=entry.get("device"),
                sampling_rate=float(entry["sampling_rate"]) if entry.get("sampling_rate") is not None else None,
                montage=entry.get("montage"),
                n_channels=int(entry["n_channels"]) if entry.get("n_channels") is not None else None,
                duration_s=float(entry["duration_s"]) if entry.get("duration_s") is not None else None,
                care_setting=entry.get("care_setting"),
                age=float(entry["age"]) if entry.get("age") is not None else None,
                sex=entry.get("sex"),
                uri=file_path,
            )

    # -- fetch --------------------------------------------------------------
    def open_stream(self, ref: RecordingRef):
        """Return an mne Raw reader for the local EDF file at ``ref.uri``.

        Data is loaded into memory (``preload=True``) so that in-place mne
        operations required by ``apply_harmonization`` -- in particular
        ``set_eeg_reference``, ``notch_filter``, and ``filter`` -- work
        without further load calls.  For local files this is acceptable
        because the source is a user's own download (not an S3 temp shard)
        and the ``open_recording`` context manager releases the Raw object
        (and therefore its memory) as soon as the harmonization is done.

        The raw object's ``_fetch_tmp`` attribute is set to ``None`` so that
        ``open_recording``'s cleanup branch does NOT delete the source file --
        local EDF files belong to the user and must not be auto-deleted.
        """
        try:
            import mne
        except ImportError as exc:
            raise ImportError(
                "mne is required for LocalEDFClient. "
                "Install with: pip install mne"
            ) from exc

        if not ref.uri:
            raise ValueError(
                f"recording {ref.recording_id!r} has no file path (uri is empty)"
            )
        # preload=True: required for set_eeg_reference / notch_filter / filter
        raw = mne.io.read_raw_edf(ref.uri, preload=True, verbose=False)
        # Signal to open_recording's cleanup: this is a user-owned file, do NOT delete.
        try:
            raw._fetch_tmp = None
        except Exception:
            pass
        return raw


class BDSPS3Client(_BDSPClient):
    """Concrete BDSP transport over the credentialed S3 access point.

    Implements the documented BDSP access model (bdsp.io/about/howto_accessdata):
    data lives in S3 behind a credentialed *access point*; the caller is
    authenticated by the approved user's OWN AWS credentials (resolved by boto3's
    standard chain -- env vars, ~/.aws/credentials, or an instance role). No keys
    are read from, or stored in, this repo.

    Disk-sparing: each EDF is fetched to scratch only for as long as the
    `open_recording` context is open, then deleted. boto3 + mne are imported
    lazily; an injected `s3` client (any object exposing `get_object` /
    `list_objects_v2`) makes the catalog logic unit-testable without AWS.
    """

    def __init__(self, cfg: dict[str, Any], s3=None):
        super().__init__(cfg)
        self.s3cfg = cfg["data"]["s3"]
        self._s3 = s3
        self._catalog: list[RecordingRef] | None = None

    # -- boto3 client (lazy) ------------------------------------------------
    def s3(self):
        if self._s3 is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - env dependent
                raise ImportError(
                    "boto3 is required for BDSP S3 access "
                    "(`pip install boto3`)."
                ) from exc
            self._s3 = boto3.client("s3", region_name=self.s3cfg.get("region"))
        return self._s3

    # -- catalog ------------------------------------------------------------
    def _load_catalog(self) -> list[RecordingRef]:
        """Read the one-row-per-recording catalog from the access point and map
        it to RecordingRefs (acquisition metadata only)."""
        if self._catalog is not None:
            return self._catalog
        ap = self.s3cfg["access_point"]
        key = self.s3cfg.get("catalog_key")
        cols = self.s3cfg.get("catalog_columns", {})
        body = self.s3().get_object(Bucket=ap, Key=key)["Body"].read()
        rows = _parse_catalog(body, self.s3cfg.get("catalog_format", "tsv"))
        refs: list[RecordingRef] = []
        for r in rows:
            refs.append(RecordingRef(
                recording_id=str(r.get(cols.get("recording_id", "recording_id"), "")),
                patient_id=str(r.get(cols.get("patient_id", "patient_id"), "")),
                hospital=str(r.get(cols.get("hospital", "site"), "")),
                device=_opt(r, cols.get("device", "device")),
                sampling_rate=_optf(r, cols.get("sampling_rate", "sfreq")),
                care_setting=_opt(r, cols.get("care_setting", "care_setting")),
                age=_optf(r, cols.get("age", "age")),
                sex=_opt(r, cols.get("sex", "sex")),
                duration_s=_optf(r, cols.get("duration_s", "duration_s")),
                uri=_opt(r, cols.get("object_key", "edf_path")),
            ))
        self._catalog = refs
        return refs

    def list_recordings(self, hospital: str) -> Iterable[RecordingRef]:
        """Yield catalog rows for one hospital (acquisition metadata only)."""
        for ref in self._load_catalog():
            if ref.hospital == hospital:
                yield ref

    # -- fetch --------------------------------------------------------------
    def _download(self, ref: RecordingRef, dest_dir: str) -> str:
        ap = self.s3cfg["access_point"]
        if not ref.uri:
            raise ValueError(f"recording {ref.recording_id} has no object_key/uri")
        os.makedirs(dest_dir, exist_ok=True)
        local = os.path.join(dest_dir, os.path.basename(ref.uri))
        self.s3().download_file(ap, ref.uri, local)
        return local

    def open_stream(self, ref: RecordingRef):  # pragma: no cover - needs mne + S3
        import mne

        scratch = self.cfg.get("data", {}).get("scratch_dir", "/tmp/heedb_scratch")
        local = self._download(ref, scratch)
        raw = mne.io.read_raw_edf(local, preload=False, verbose=False)
        # Tag the temp path so open_recording deletes it on context exit.
        try:
            raw._fetch_tmp = local
        except Exception:
            pass
        return raw

    def download_shard(self, refs: list[RecordingRef], dest: str) -> str:  # pragma: no cover - needs S3
        shard_dir = os.path.join(dest, "shard")
        for ref in refs:
            self._download(ref, shard_dir)
        return shard_dir


# ---- catalog helpers ------------------------------------------------------
def _parse_catalog(body: bytes, fmt: str) -> list[dict]:
    fmt = (fmt or "tsv").lower()
    if fmt in ("tsv", "csv"):
        import csv
        import io
        delim = "\t" if fmt == "tsv" else ","
        text = body.decode("utf-8")
        return list(csv.DictReader(io.StringIO(text), delimiter=delim))
    if fmt == "parquet":
        import io
        import pyarrow.parquet as pq
        return pq.read_table(io.BytesIO(body)).to_pylist()
    raise ValueError(f"unknown catalog_format {fmt!r}")


def _opt(row: dict, key: str):
    v = row.get(key)
    return None if v in ("", None) else v


def _optf(row: dict, key: str):
    v = row.get(key)
    if v in ("", None):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
