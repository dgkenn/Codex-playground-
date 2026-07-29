"""Sleep-EDF Expanded: hypnogram parsing and a per-window labelled adapter.

WHY THIS EXISTS. Everything else in `bsde.ingestion` streams a fixed window per recording with no ground
truth attached -- useful for measurement-property work (E01) but incapable of testing whether a candidate
tracks STATE at all. Sleep-EDF ships a companion hypnogram for every polysomnography recording, scored by a
human against R&K / AASM criteria. That is a real label, and wake-vs-deep-sleep is a within-subject contrast:
the same electrodes, the same night, the same person, awake at one point and in N3 at another. It is the
first labelled contrast this project can run without waiting on a credentialed dataset.

THE PAIRING RULE (verified 2026-07-29 against the live PhysioNet directory listing, not assumed). A
`*-PSG.edf` file and its hypnogram do NOT share a basename with "PSG" substituted for "Hypnogram" -- e.g.
`SC4001E0-PSG.edf` pairs with `SC4001EC-Hypnogram.edf`, `SC4011E0-PSG.edf` with `SC4011EH-Hypnogram.edf`, and
telemetry follows the same pattern (`ST7011J0-PSG.edf` / `ST7011JP-Hypnogram.edf`). The rule that actually
holds: the PSG basename and the hypnogram basename agree on every character EXCEPT THE LAST ONE (which
encodes the scorer/annotator, not the recording). `find_hypnogram_filename` implements exactly that and
nothing string-substituted, per a directory listing fetched at run time -- there is no way to derive the
hypnogram name from the PSG name alone.

THE STAGE MAPPING (a scientific choice, stated once here rather than buried in a script). Sleep-EDF's
hypnograms use the classic Rechtschaffen & Kales stages: W, 1, 2, 3, 4, R, plus "MOVEMENT TIME" and "?" for
unscored epochs. AASM (the modern scoring standard) merges R&K stages 3 and 4 into a single N3 ("slow-wave
sleep") stage, on the grounds that the 3/4 boundary (an arbitrary percentage of delta wave coverage per
epoch) does not correspond to a physiological discontinuity. `N3 = {"Sleep stage 3", "Sleep stage 4"}` below
encodes that merge. WAKE = {"Sleep stage W"} only -- it deliberately excludes "Movement time" (artefact, not
a described stage) and "Sleep stage ?" (unscored, not a described stage).

TAL FORMAT. EDF+ packs annotations into a pseudo-signal literally labelled "EDF Annotations", whose "samples"
are not sample values at all but raw bytes of one or more concatenated Time-stamped Annotation Lists (TALs):

    onset[+-][\\x15duration]\\x14(annotation-text\\x14)*\\x00

repeated back-to-back, zero-padded to fill the record. The FIRST TAL in every data record is a mandatory
"timekeeping annotation" carrying an onset and no text (`+0\\x14\\x14\\x00`) -- it is parsed like any other
TAL and simply yields no (onset, duration, label) triple, because its annotation-text list is empty.
`parse_hypnogram_edf` was written after fetching one real hypnogram
(`sleep-cassette/SC4001EC-Hypnogram.edf`) and printing its raw bytes; the format above is what was observed,
not assumed from the spec text alone.
"""
from __future__ import annotations

import re
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

from bsde.ingestion.base import Adapter, RecordingRef
from bsde.ingestion.http_edf import _urlopen, parse_edf_header, read_edf_window_http  # shared plumbing

Annotation = Tuple[float, float, str]

# The scientific mapping, declared once. See the module docstring for why 3+4 merge into N3 and why
# "Movement time" / "Sleep stage ?" are excluded from both sets.
WAKE = frozenset({"Sleep stage W"})
N3 = frozenset({"Sleep stage 3", "Sleep stage 4"})

_HREF_EDF_RE = re.compile(r'href="([^"?/]+\.edf)"', re.I)


# --- pure parsing: no network below this line, until the fetch helpers at the bottom -------------------

def _parse_tal_stream(text: str) -> List[Annotation]:
    """Parse a concatenated TAL byte stream (already decoded as latin1 text) into (onset, duration, label)
    triples. Pure function. The timekeeping annotation at the start of each record (empty text) yields
    nothing, by construction: its annotation-text list, once split, contains only empty strings.
    """
    out: List[Annotation] = []
    for chunk in text.split("\x00"):
        if not chunk:
            continue
        parts = chunk.split("\x14")
        onset_field = parts[0]
        if not onset_field or onset_field[0] not in "+-":
            continue  # not a TAL onset (e.g. a stray padding fragment); nothing to recover
        if "\x15" in onset_field:
            onset_str, dur_str = onset_field.split("\x15", 1)
        else:
            onset_str, dur_str = onset_field, ""
        try:
            onset = float(onset_str)
            duration = float(dur_str) if dur_str else 0.0
        except ValueError:
            continue
        for label in parts[1:]:
            if label:
                out.append((onset, duration, label))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def parse_hypnogram_edf(blob: bytes) -> List[Annotation]:
    """Parse an EDF+ hypnogram file's annotations into (onset_s, duration_s, stage_label) triples.

    Pure function: `blob` is the whole file's bytes, already fetched. Reuses `parse_edf_header` (the same
    header parser `http_edf.py` uses for signal EDFs) to locate the "EDF Annotations" signal(s) and their
    per-record byte spans, then hands the concatenated bytes to `_parse_tal_stream`.
    """
    if len(blob) < 256:
        raise ValueError(f"EDF blob truncated: {len(blob)} bytes, need at least 256 for the main header")
    main = blob[:256]
    ns = int(main[252:256].decode(errors="replace").strip() or 0)
    if ns <= 0:
        raise ValueError("bad EDF: number of signals (ns) is 0")
    sh = blob[256: 256 + ns * 256]
    meta = parse_edf_header(main, sh)
    labels = meta["labels"]
    ann_idx = [i for i, lab in enumerate(labels) if lab.strip() == "EDF Annotations"]
    if not ann_idx:
        raise ValueError(f"no 'EDF Annotations' signal found among {labels!r}; this is not an EDF+ "
                         "annotation file")

    nsamp = meta["n_samples_per_record"]
    record_bytes = meta["record_bytes"]
    if record_bytes <= 0:
        raise ValueError("bad EDF: zero-length data record")
    data = blob[meta["data_offset"]:]
    got_records = len(data) // record_bytes
    if got_records == 0:
        raise ValueError("no complete EDF data record in the hypnogram file")

    # Per-signal sample offset within one record (in SAMPLES, i.e. 2-byte units -- same layout decode_edf_
    # window relies on).
    sample_offset: Dict[int, int] = {}
    idx = 0
    for i in range(ns):
        sample_offset[i] = idx
        idx += nsamp[i]

    ann_bytes = bytearray()
    for r in range(got_records):
        rec_start = r * record_bytes
        for i in ann_idx:
            byte_off = rec_start + sample_offset[i] * 2
            byte_len = nsamp[i] * 2
            ann_bytes += data[byte_off: byte_off + byte_len]
    return _parse_tal_stream(bytes(ann_bytes).decode("latin1"))


def stage_blocks(annots: Sequence[Annotation], stage_set: Sequence[str]) -> List[Tuple[float, float]]:
    """Merge contiguous annotations whose label is in `stage_set` into (start, end) blocks.

    "Contiguous" means back-to-back in time with no gap (within floating-point tolerance) AND no
    intervening annotation of a different stage occupying the gap -- both show up identically here as a
    non-zero distance between one matched annotation's end and the next matched annotation's onset, since
    non-matching annotations are filtered out before merging, not skipped over.
    """
    stages = frozenset(stage_set)
    matched = sorted(((o, d, lab) for o, d, lab in annots if lab in stages), key=lambda t: t[0])
    blocks: List[Tuple[float, float]] = []
    for onset, duration, _ in matched:
        end = onset + duration
        if blocks and abs(onset - blocks[-1][1]) < 1e-6:
            blocks[-1] = (blocks[-1][0], end)
        else:
            blocks.append((onset, end))
    return blocks


def longest_block(annots: Sequence[Annotation], stage_set: Sequence[str]) -> Optional[Tuple[float, float]]:
    """The single longest contiguous block of `stage_set`, or None if the stage never occurs."""
    blocks = stage_blocks(annots, stage_set)
    if not blocks:
        return None
    return max(blocks, key=lambda b: b[1] - b[0])


# --- directory discovery: the PSG<->Hypnogram pairing rule ---------------------------------------------

def parse_directory_listing(html: str) -> List[str]:
    """Extract `.edf` filenames from a PhysioNet directory-listing HTML page. Pure function."""
    return sorted(set(_HREF_EDF_RE.findall(html)))


def find_hypnogram_filename(psg_filename: str, directory_filenames: Sequence[str]) -> str:
    """Which of `directory_filenames` is the hypnogram for `psg_filename`.

    THE RULE, verified against the live PhysioNet listing (see module docstring): the PSG basename and its
    hypnogram's basename are identical except for their LAST character. String-substituting "PSG" ->
    "Hypnogram" does not work -- the trailing letter differs too (`SC4001E0` -> `SC4001EC`, not
    `SC4001EC` derived by substitution) -- so this must be resolved against an actual directory listing,
    never guessed.
    """
    if not psg_filename.endswith("-PSG.edf"):
        raise ValueError(f"{psg_filename!r} does not look like a PSG file (expected a '-PSG.edf' suffix)")
    psg_base = psg_filename[: -len("-PSG.edf")]
    prefix = psg_base[:-1]
    candidates = []
    for fn in directory_filenames:
        if not fn.endswith("-Hypnogram.edf"):
            continue
        hyp_base = fn[: -len("-Hypnogram.edf")]
        if len(hyp_base) == len(psg_base) and hyp_base[:-1] == prefix:
            candidates.append(fn)
    if not candidates:
        raise ValueError(f"no hypnogram in the directory listing matches {psg_filename!r} "
                         f"(prefix {prefix!r}); {len(directory_filenames)} .edf files listed")
    if len(candidates) > 1:
        raise ValueError(f"{len(candidates)} hypnograms match {psg_filename!r}: {sorted(candidates)}; "
                         "expected exactly one")
    return candidates[0]


# --- network: the only functions here that touch HTTP ---------------------------------------------------

def fetch_directory_listing(dir_url: str, timeout: float = 30.0) -> str:
    """GET a directory index page. `dir_url` must end in '/'."""
    req = urllib.request.Request(dir_url)
    with _urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_whole(url: str, timeout: float = 30.0) -> bytes:
    """GET a whole small file (hypnograms are a few KB). Never used for the multi-MB PSG signal files --
    those go through `read_edf_window_http`'s byte-range path."""
    req = urllib.request.Request(url)
    with _urlopen(req, timeout=timeout) as resp:
        return resp.read()


def discover_hypnogram_url(psg_url: str, directory_html: str) -> str:
    """Combine `find_hypnogram_filename` with the PSG url's own directory to build the hypnogram's URL."""
    dir_url = psg_url.rsplit("/", 1)[0] + "/"
    psg_filename = psg_url.rsplit("/", 1)[-1]
    filenames = parse_directory_listing(directory_html)
    hyp_filename = find_hypnogram_filename(psg_filename, filenames)
    return dir_url + hyp_filename


# --- the labelled-window adapter -------------------------------------------------------------------------

class LabelledEDFWindowAdapter(Adapter):
    """One `RecordingRef` per (recording, stage) row, each with ITS OWN `start_seconds`.

    WHY THIS EXISTS RATHER THAN `HttpEDFAdapter`. `HttpEDFAdapter` takes one `start_seconds` for the whole
    adapter -- fine when every recording is read from the same offset, wrong here, where a wake window and
    an N3 window for the SAME recording sit at different, individually-computed offsets. Every row therefore
    carries its own url/start_seconds/window_s rather than sharing the adapter's.

    `rows` is a list of dicts, each:
        {"url", "start_seconds", "window_s", "label", "subject", "recording_id", "meta"}

    `recording_id` MUST encode the stage (e.g. `SC4001E0-PSG@W`, `SC4001E0-PSG@N3`) so the two rows for one
    recording are distinguishable and independently resumable in the streaming runner's output table.

    `subject` MUST be the recording's base id WITHOUT the stage suffix (e.g. `SC4001E0-PSG` for BOTH of
    that recording's rows). This is the single correctness property the whole within-subject design rests
    on: `base.py`'s `RecordingRef` uses `subject` for subject-level splitting, and if the wake row and the
    N3 row of one person were given different subjects, every downstream confidence interval would be
    computed as though they came from two independent people -- too narrow, and silently so.
    """

    units = "microvolts"

    def __init__(self, rows: Sequence[Dict[str, Any]], dataset: str,
                 channel_regex: "str | None" = None) -> None:
        self.rows = list(rows)
        self.dataset = dataset
        self.name = f"labelled_edf:{dataset}"
        # Sleep-EDF PSGs mix 100 Hz EEG with 1 Hz EOG/EMG/thermistor/respiration/event channels; '^EEG '
        # keeps only the two coherent-rate EEG derivations. See decode_edf_window's docstring.
        self.channel_regex = channel_regex

    def list_recordings(self) -> List[RecordingRef]:
        out = []
        for row in sorted(self.rows, key=lambda r: r["recording_id"]):  # deterministic, input-order-free
            meta = dict(row.get("meta") or {})
            meta.update(label=row["label"], url=row["url"],
                       start_seconds=row["start_seconds"], window_s=row["window_s"])
            out.append(RecordingRef(
                recording_id=row["recording_id"], dataset=self.dataset,
                subject=row["subject"], load=self._make_loader(row), meta=meta))
        return out

    def _make_loader(self, row: Dict[str, Any]):
        url, start_seconds, window_s = row["url"], row["start_seconds"], row["window_s"]
        channel_regex = self.channel_regex

        def load():
            return read_edf_window_http(url, window_s=window_s, start_seconds=start_seconds,
                                        channel_regex=channel_regex)
        return load
