"""OpenNeuro adapter: list a dataset's public S3 mirror over plain HTTPS, stream EDF files by byte range.

OpenNeuro mirrors every dataset to a public, anonymously-readable S3 bucket (`s3://openneuro.org/<accession>/...`,
also reachable as `https://openneuro.org/crn/datasets/<accession>/...` through the web app). No credentials
are needed or used here -- listing and fetching both go through the bucket's plain HTTPS REST endpoint,
`https://s3.amazonaws.com/openneuro.org/...`, which S3 serves unauthenticated for public buckets.

LISTING. S3's `ListObjectsV2` is a REST GET returning XML (`?list-type=2&prefix=...`), parsed here with
`xml.etree.ElementTree` from the stdlib -- no AWS SDK. A listing can be paginated (`IsTruncated` +
`NextContinuationToken`); `parse_list_objects_v2_xml` and `list_all_keys` handle that loop explicitly rather
than assuming one page covers a dataset, since a BIDS-EEG dataset with many subjects/sessions routinely
exceeds S3's 1000-key page size.

LOADING. EDF files are loaded via `read_edf_window_http` from `http_edf.py` -- the byte-range window reader
is written once there and reused here, rather than re-implemented, per the instruction to factor it out.

SUBJECT. `subject` is REQUIRED to come from the BIDS path (`sub-XXX`), not left to default to
`recording_id`. BIDS datasets routinely have several sessions and runs per subject
(`sub-01_ses-01_task-rest_eeg.edf`, `sub-01_ses-02_task-rest_eeg.edf`, ...); defaulting subject to
recording_id would silently turn subject-level splitting into recording-level splitting and understate
every confidence interval, exactly the failure `RecordingRef.__post_init__` warns about for datasets where
that default is NOT safe.
"""
from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional, Sequence, Tuple

from bsde.ingestion.base import Adapter, RecordingRef
from bsde.ingestion.http_edf import _urlopen, read_edf_window_http

_S3_ENDPOINT = "https://s3.amazonaws.com"
_S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

_SUBJECT_RE = None  # compiled lazily below to keep the module import cheap


def _subject_re():
    global _SUBJECT_RE
    if _SUBJECT_RE is None:
        import re
        _SUBJECT_RE = re.compile(r"(sub-[A-Za-z0-9]+)")
    return _SUBJECT_RE


def subject_from_bids_key(key: str) -> str:
    """Extract the BIDS `sub-XXX` entity from an object key/path. Raises if absent -- a non-BIDS key here
    means the accession or prefix is wrong, not that recording-level splitting is an acceptable fallback."""
    m = _subject_re().search(key)
    if not m:
        raise ValueError(f"no 'sub-XXX' entity found in BIDS key {key!r}")
    return m.group(1)


def parse_list_objects_v2_xml(xml_text: str) -> Tuple[List[str], Optional[str], bool]:
    """Parse one page of an S3 `ListObjectsV2` response. Pure function: no network.

    Returns (keys on this page, next continuation token or None, is_truncated). Tolerates responses with
    or without the S3 XML namespace declared, since hand-written test fixtures may omit it.
    """
    root = ET.fromstring(xml_text)

    def findall(tag: str):
        found = root.findall(f"{_S3_NS}{tag}")
        return found if found else root.findall(tag)

    def find(tag: str):
        el = root.find(f"{_S3_NS}{tag}")
        return el if el is not None else root.find(tag)

    keys = []
    for contents in findall("Contents"):
        key_el = contents.find(f"{_S3_NS}Key")
        if key_el is None:
            key_el = contents.find("Key")
        if key_el is not None and key_el.text:
            keys.append(key_el.text)

    truncated_el = find("IsTruncated")
    is_truncated = bool(truncated_el is not None and truncated_el.text and truncated_el.text.strip().lower() == "true")

    token_el = find("NextContinuationToken")
    next_token = token_el.text if (token_el is not None and token_el.text) else None
    return keys, next_token, is_truncated


def _fetch_listing_page(bucket: str, prefix: str, continuation_token: Optional[str] = None,
                         endpoint: str = _S3_ENDPOINT, timeout: float = 30.0) -> str:
    params = {"list-type": "2", "prefix": prefix}
    if continuation_token:
        params["continuation-token"] = continuation_token
    url = f"{endpoint}/{bucket}/?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    with _urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def list_all_keys(bucket: str, prefix: str, endpoint: str = _S3_ENDPOINT, timeout: float = 30.0) -> List[str]:
    """List every key under `prefix`, following continuation tokens across as many pages as needed."""
    keys: List[str] = []
    token: Optional[str] = None
    while True:
        xml_text = _fetch_listing_page(bucket, prefix, token, endpoint=endpoint, timeout=timeout)
        page_keys, token, truncated = parse_list_objects_v2_xml(xml_text)
        keys.extend(page_keys)
        if not truncated or not token:
            break
    return keys


class OpenNeuroS3Adapter(Adapter):
    """Stream EDF recordings from an OpenNeuro dataset's public S3 mirror, anonymously, over HTTPS.

    `recording_id` is the full object key (e.g. `ds005620/sub-03/ses-01/eeg/sub-03_..._eeg.edf`), which is
    already stable and unique -- never an enumeration index over the (paginated) listing.
    """

    units = "microvolts"

    def __init__(self, accession: str, dataset: Optional[str] = None, suffix: str = "_eeg.edf",
                 window_s: float = 300.0) -> None:
        self.accession = accession
        self.dataset = dataset or accession
        self.name = f"openneuro_s3:{self.accession}"
        self.suffix = suffix
        self.window_s = window_s

    def list_recordings(self) -> List[RecordingRef]:
        prefix = f"{self.accession}/"
        keys = [k for k in list_all_keys("openneuro.org", prefix) if k.endswith(self.suffix)]
        out = []
        for key in sorted(keys):  # sorted == deterministic order, independent of S3 listing order/paging
            url = f"{_S3_ENDPOINT}/openneuro.org/{key}"
            out.append(RecordingRef(
                recording_id=key, dataset=self.dataset,
                subject=subject_from_bids_key(key),
                load=self._make_loader(url),
                meta={"url": url, "key": key, "format": "edf"}))
        return out

    def _make_loader(self, url: str):
        def load():
            return read_edf_window_http(url, window_s=self.window_s)
        return load
