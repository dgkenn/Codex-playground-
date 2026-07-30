"""Generic remote-ZIP reader: read individual members out of a ZIP archive served over HTTPS, using
Range requests, without ever fetching the whole archive.

WHY THIS EXISTS. The Chennu propofol dataset (`chennu.py`) ships as one 3.69 GB ZIP with 80 EEGLAB
`.set`/`.fdt` pairs inside it. Downloading it would violate the invariant in `base.py` (raw EEG never
lands on disk) twice over: once for the archive itself, once for the extracted `.fdt` files. A ZIP's
central directory is a flat table of (name, size, offset) at the END of the file, so the archive's member
list -- and then any one member's bytes -- can be fetched with a handful of small Range GETs.

THE ARCHITECTURE MATCHES `http_edf.py`: pure parsing functions (`parse_eocd`, `parse_central_directory`)
that take plain bytes and return plain dicts, so the ZIP-format logic is unit-tested against synthetic
in-memory archives with no network involved; a thin `RemoteZip` class does the HTTP and the caching.
`_urlopen`/`_http_get_range` are reused from `http_edf.py` rather than re-implemented, so the SSL/proxy
handling (CA bundle, `HTTPS_PROXY`) lives in exactly one place.

WHY A RANGE PROBE INSTEAD OF HEAD FOR THE TOTAL SIZE. The public `www.repository.cam.ac.uk` URL for this
archive 302-redirects to the `api.repository.cam.ac.uk` URL actually read here, and a HEAD request against
a redirecting URL can report the REDIRECT STUB's length, not the archive's -- measured, not assumed. A
`Range: bytes=0-0` GET forces a 206 response whose `Content-Range: bytes 0-0/<total>` header states the
real total unambiguously, so that is what `RemoteZip` uses to learn `total_size` when the caller does not
already know it.

DEFLATE IS NOT RANDOM-ACCESS, AND THIS IS WHY `read_member` TAKES A PREFIX WINDOW RATHER THAN AN ARBITRARY
OFFSET. A deflate stream can only be inflated forward from its start -- there is no seeking into the
middle of one without having decompressed everything before that point, because each token can reference
bytes anywhere in the preceding 32 KB window. So a window at the START of a compressed member is cheap (as
little of the compressed stream as covers it needs to be fetched and inflated), and a window in the MIDDLE
or END costs the same as reading the whole member. `read_member`'s `max_uncompressed_bytes` therefore
expresses "the first N decompressed bytes", not "bytes [a, b)" -- the caller (`chennu.py`) reads the first
`n_epochs` epochs of a recording for exactly this reason, not an arbitrary time window elsewhere in it.

ZIP64 IS NOT IMPLEMENTED. This archive (3.69 GB, under the 4 GiB Zip64 threshold) does not need it, and
using the 32-bit fields for a truly large archive would silently misread offsets rather than fail loudly.
`parse_eocd` detects a Zip64 EOCD locator record or a 0xFFFF/0xFFFFFFFF sentinel field and raises
`NotImplementedError` naming the reason, rather than proceeding on wrong numbers.
"""
from __future__ import annotations

import re
import struct
import zlib
from typing import Any, Dict, List, Optional

from bsde.ingestion.http_edf import _http_get_range, _urlopen

_EOCD_SIG = b"PK\x05\x06"
_EOCD_STRUCT = "<HHHHIIH"  # fields following the 4-byte signature
_EOCD_FIXED_SIZE = 22  # 4-byte signature + 18 bytes of fixed fields, before the variable comment
_ZIP64_EOCD_LOCATOR_SIG = b"PK\x06\x07"

_CD_SIG = b"PK\x01\x02"
_CD_STRUCT = "<HHHHHHIIIHHHHHII"  # fields following the 4-byte signature
_CD_FIXED_SIZE = 46

_LOCAL_HEADER_SIG = b"PK\x03\x04"
_LOCAL_HEADER_FIXED_SIZE = 30

# Generous first guess at how much trailing/leading data to fetch for the EOCD record and a local file
# header respectively. Both are upper bounds on real values (max ZIP comment is 65535 bytes; real
# filenames here are well under a few hundred bytes), never a hard limit -- if the guess is wrong the
# parser raises rather than silently misreading a truncated buffer.
_EOCD_TAIL_GUESS = 65536 + _EOCD_FIXED_SIZE
_LOCAL_HEADER_PROBE = 4096

_DEFAULT_CHUNK = 8 * 1024 * 1024  # fetch compressed bytes in 8 MB chunks while inflating a prefix window


def parse_eocd(tail: bytes) -> Dict[str, Any]:
    """Locate the End Of Central Directory record in the last bytes of a ZIP file. Pure function.

    `tail` should be (at least) the last `65536 + 22` bytes of the archive -- the maximum possible ZIP
    comment plus the fixed EOCD size -- so the record is guaranteed to be present if the archive has one.
    Returns `{n_entries, cd_size, cd_offset, comment_len, eocd_offset_in_tail}`.

    Raises `ValueError` if no EOCD signature is found (the buffer was too short, or this is not a ZIP).
    Raises `NotImplementedError` if a Zip64 EOCD locator or a Zip64 sentinel field (0xFFFF/0xFFFFFFFF) is
    seen -- this reader does not implement Zip64 and refuses to proceed on offsets it cannot trust.
    """
    idx = tail.rfind(_EOCD_SIG)
    if idx == -1:
        raise ValueError(
            "no End Of Central Directory (EOCD) record found in the supplied tail bytes "
            f"({len(tail)} bytes) -- this is not a ZIP file, or the tail window was too short "
            "(max ZIP comment is 65535 bytes; fetch at least 65557 trailing bytes).")
    if len(tail) - idx < _EOCD_FIXED_SIZE:
        raise ValueError(
            f"EOCD signature found at tail offset {idx} but only {len(tail) - idx} bytes follow it, "
            f"need at least {_EOCD_FIXED_SIZE}: the buffer was truncated.")

    (_disk_num, _cd_disk, _n_entries_this_disk, n_entries, cd_size, cd_offset,
     comment_len) = struct.unpack_from(_EOCD_STRUCT, tail, idx + 4)

    if _ZIP64_EOCD_LOCATOR_SIG in tail[:idx]:
        raise NotImplementedError(
            "Zip64 End Of Central Directory locator (PK\\x06\\x07) found before the EOCD record -- this "
            "archive uses Zip64 and this reader does not implement it. Reading it with the 32-bit EOCD "
            "fields would silently misread the central directory offset/size.")
    if n_entries == 0xFFFF or cd_size == 0xFFFFFFFF or cd_offset == 0xFFFFFFFF:
        raise NotImplementedError(
            "EOCD record carries a Zip64 sentinel value (0xFFFF or 0xFFFFFFFF) in an entry-count/size/"
            "offset field -- the real value lives in a Zip64 EOCD record this reader does not implement. "
            "This 3.69 GB archive does not need Zip64; a >4 GiB one would.")

    return dict(n_entries=n_entries, cd_size=cd_size, cd_offset=cd_offset,
                comment_len=comment_len, eocd_offset_in_tail=idx)


def parse_central_directory(cd: bytes) -> List[Dict[str, Any]]:
    """Parse a ZIP central directory (the exact `cd_size` bytes at `cd_offset`) into one dict per member.

    Pure function: no I/O. Each dict has `name`, `compress_size`, `uncompress_size`,
    `local_header_offset`, `method` (0 = stored, 8 = deflate), `crc32`. Filenames are read with their
    declared length prefix, so spaces (and anything else) in a name are handled with no special-casing.
    """
    out: List[Dict[str, Any]] = []
    pos = 0
    n = len(cd)
    while pos < n:
        if cd[pos:pos + 4] != _CD_SIG:
            raise ValueError(
                f"expected central directory file header signature at offset {pos}, "
                f"found {cd[pos:pos + 4]!r} -- central directory is corrupt or cd_size was wrong.")
        if pos + _CD_FIXED_SIZE > n:
            raise ValueError(f"central directory record truncated at offset {pos}")
        (_ver_made, _ver_needed, _flags, method, _mod_time, _mod_date, crc32, compress_size,
         uncompress_size, fname_len, extra_len, comment_len, _disk_start, _int_attr, _ext_attr,
         local_header_offset) = struct.unpack_from(_CD_STRUCT, cd, pos + 4)

        name_start = pos + _CD_FIXED_SIZE
        name = cd[name_start:name_start + fname_len].decode("utf-8", errors="replace")

        out.append(dict(name=name, compress_size=compress_size, uncompress_size=uncompress_size,
                         local_header_offset=local_header_offset, method=method, crc32=crc32))
        pos = name_start + fname_len + extra_len + comment_len
    return out


def _is_skipped_member(name: str) -> bool:
    """`__MACOSX/` resource-fork junk and `.DS_Store` are not real archive content."""
    if name.startswith("__MACOSX/"):
        return True
    return name.rsplit("/", 1)[-1] == ".DS_Store"


class RemoteZip:
    """Read one ZIP archive's directory and individual members over HTTP Range requests.

    Nothing here downloads the whole archive: `index()` fetches only the EOCD tail and the central
    directory; `read_member()` fetches only the one member's compressed bytes (optionally only a prefix
    of them -- see the module docstring on why deflate makes this a PREFIX, not an arbitrary offset).
    """

    def __init__(self, url: str, total_size: Optional[int] = None, timeout: float = 150.0) -> None:
        self.url = url
        self.timeout = timeout
        self._total_size = total_size
        self._members: Optional[List[Dict[str, Any]]] = None
        # Set by `read_member` after every call: compressed bytes actually transferred over the network,
        # for callers that want to report how little of a member they paid for.
        self.last_bytes_fetched = 0

    @property
    def total_size(self) -> int:
        if self._total_size is None:
            self._total_size = self._probe_total_size()
        return self._total_size

    def _probe_total_size(self) -> int:
        """Learn the archive's true size via a `bytes=0-0` range GET, reading `Content-Range`'s total.

        NOT a HEAD request -- see the module docstring: a HEAD on a URL that 302-redirects can report the
        redirect stub's length rather than the real target's.
        """
        import urllib.request
        req = urllib.request.Request(self.url, headers={"Range": "bytes=0-0"})
        with _urlopen(req, timeout=self.timeout) as resp:
            resp.read()
            content_range = resp.headers.get("Content-Range", "")
        m = re.match(r"bytes \d+-\d+/(\d+)", content_range)
        if not m:
            raise ValueError(
                f"range probe of {self.url!r} did not return a parseable Content-Range header "
                f"(got {content_range!r}) -- the server may not support Range requests.")
        return int(m.group(1))

    def index(self) -> List[Dict[str, Any]]:
        """Cached, sorted list of member dicts (see `parse_central_directory`), `__MACOSX__`/`.DS_Store`
        excluded. Costs two Range GETs total (EOCD tail, then the central directory itself)."""
        if self._members is not None:
            return self._members

        total = self.total_size
        tail_len = min(total, _EOCD_TAIL_GUESS)
        tail = _http_get_range(self.url, total - tail_len, tail_len, timeout=self.timeout)
        eocd = parse_eocd(tail)

        cd_bytes = _http_get_range(self.url, eocd["cd_offset"], eocd["cd_size"], timeout=self.timeout)
        entries = parse_central_directory(cd_bytes)
        if len(entries) != eocd["n_entries"]:
            raise ValueError(
                f"central directory declared {eocd['n_entries']} entries but parsing found "
                f"{len(entries)} -- cd_size/cd_offset from the EOCD record may be wrong.")

        members = [e for e in entries if not _is_skipped_member(e["name"])]
        self._members = sorted(members, key=lambda e: e["name"])  # sorted == deterministic listing
        return self._members

    def _member_by_name(self, name: str) -> Dict[str, Any]:
        for m in self.index():
            if m["name"] == name:
                return m
        raise KeyError(f"no such member {name!r} in this archive")

    def _local_data_offset(self, member: Dict[str, Any]) -> int:
        """A central directory entry's `local_header_offset` points at the LOCAL file header, not the
        data -- and the local header's filename/extra fields are not guaranteed to match the central
        directory's (extra fields in particular commonly differ), so it must be read and parsed, not
        assumed. `_LOCAL_HEADER_PROBE` bytes is comfortably more than any real local header here."""
        probe = _http_get_range(self.url, member["local_header_offset"], _LOCAL_HEADER_PROBE,
                                 timeout=self.timeout)
        if probe[:4] != _LOCAL_HEADER_SIG:
            raise ValueError(
                f"expected local file header signature at offset {member['local_header_offset']} for "
                f"member {member['name']!r}, found {probe[:4]!r}")
        fname_len, extra_len = struct.unpack_from("<HH", probe, 26)
        return member["local_header_offset"] + _LOCAL_HEADER_FIXED_SIZE + fname_len + extra_len

    def read_member(self, name: str, max_uncompressed_bytes: Optional[int] = None) -> bytes:
        """Fetch and decompress one member's bytes.

        If `max_uncompressed_bytes` is given, stops inflating (and stops fetching further compressed
        chunks) as soon as that many decompressed bytes exist, and returns exactly that many -- see the
        module docstring for why this is a PREFIX of the member, not an arbitrary window. Compressed bytes
        are fetched `_DEFAULT_CHUNK` at a time rather than all at once, so a small prefix of a large
        member costs a small fraction of its compressed size in network transfer.

        `self.last_bytes_fetched` is set to the number of COMPRESSED bytes actually transferred for this
        call, so a caller can report how much of the member's full compressed size it paid for.
        """
        member = self._member_by_name(name)
        data_offset = self._local_data_offset(member)
        method = member["method"]
        compress_size = member["compress_size"]

        if method == 0:  # stored -- no decompression, so a prefix window is just a shorter range GET
            want = compress_size if max_uncompressed_bytes is None else min(max_uncompressed_bytes, compress_size)
            data = _http_get_range(self.url, data_offset, want, timeout=self.timeout)
            self.last_bytes_fetched = len(data)
            return data

        if method != 8:  # 8 = deflate
            raise NotImplementedError(
                f"unsupported ZIP compression method {method} for member {name!r} "
                "-- only stored (0) and deflate (8) are implemented.")

        decompressor = zlib.decompressobj(-15)  # -15: raw deflate, no zlib/gzip header (per the ZIP spec)
        out = bytearray()
        pos = data_offset
        remaining = compress_size
        fetched = 0
        while remaining > 0:
            chunk_len = min(_DEFAULT_CHUNK, remaining)
            chunk = _http_get_range(self.url, pos, chunk_len, timeout=self.timeout)
            fetched += len(chunk)
            pos += len(chunk)
            remaining -= len(chunk)
            out += decompressor.decompress(chunk)
            if max_uncompressed_bytes is not None and len(out) >= max_uncompressed_bytes:
                break
        else:
            out += decompressor.flush()  # only reached if the loop ran to completion (whole member read)

        self.last_bytes_fetched = fetched
        if max_uncompressed_bytes is not None:
            return bytes(out[:max_uncompressed_bytes])
        return bytes(out)
