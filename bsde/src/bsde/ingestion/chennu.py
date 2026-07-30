"""Chennu propofol-sedation EEGLAB adapter: streams `.set`/`.fdt` pairs out of one 3.69 GB remote ZIP via
HTTP Range requests (`remote_zip.RemoteZip`), never downloading the archive and never writing raw EEG to
disk -- the invariant in `base.py`.

DATASET. 20 subjects x 4 conditions (sedation_level 1=baseline .. 4=recovery), ~7 minutes per recording,
91 channels, filtered 0.5-45 Hz, segmented into 10 s epochs, cleaned, average-referenced, EEGLAB format.
80 `.set` (header/metadata, small) + 80 `.fdt` (float32 sample data, large) pairs live inside
`Sedation-RestingState/<name>.set` / `.fdt`, alongside `datainfo.mat`, `__MACOSX/` junk and `.DS_Store`
(the latter two are skipped by `RemoteZip.index()` already).

SUBJECT GROUPING, DERIVED FROM THE LABEL DATA -- NOT ASSUMED. `dataset_name` values in
`results/chennu_labels.csv` look like `02-2010-anest 20100210 135.003`: a subject index, a `-`, then a
date/time-derived recording tag that is DIFFERENT for every one of a subject's four sessions (it is not
just the sedation level -- see e.g. subject `14`'s four dates: 0324/0324/0324/0324 but different clock
times, and subject `22`'s third and fourth rows differ in both date and time). The token before the FIRST
`-` is the only field that repeats exactly four times per subject. Verified against all 80 rows: this rule
(`name.split("-", 1)[0]`) yields exactly 20 distinct subjects with exactly 4 rows each -- see
`tests/test_remote_zip_chennu.py::test_subject_grouping_is_20x4_on_real_labels`. A wrong rule here would
silently convert this within-subject sedation-level design into a between-subject one.

UNITS ARE AN ASSUMPTION, NOT A DOCUMENTED FACT. Neither the deposit's description page nor the `.set`
files themselves state a physical unit for `EEG.data`. EEGLAB's own convention (and every published EEGLAB
tutorial/dataset this project has seen) is microvolts, so `units = "microvolts"` is declared and passed
through `to_microvolts` as a no-op scale (matching `base.py`'s rule that the conversion happens in exactly
one place and is declared, never guessed from magnitude). If this assumption is wrong by a fixed factor,
it changes absolute-amplitude features -- band power, an amplitude-thresholded Lempel-Ziv binarisation --
but NOT the aperiodic exponent or any other scale-invariant feature (same reasoning as `base.py`'s
dimensionless-units case, just for a wrong constant rather than no constant at all).

WHY ONLY `n_epochs` EPOCHS ARE READ. The `.fdt` layout is column-major (nbchan varies fastest, then time
sample, then epoch -- see `decode_fdt`), so the FIRST `n_epochs` epochs are a contiguous PREFIX of the
file. Combined with `RemoteZip.read_member`'s prefix-only random access (deflate is not seekable -- see
`remote_zip.py`), that is what makes reading a handful of epochs out of a large member cheap: only the
compressed bytes covering that prefix are ever fetched.

CORRECTION AGAINST THE ORIGINAL PRE-REGISTRATION: EVERY REAL `.set` FILE IS MATLAB v7.3, NOT v5. The task
that produced this module assumed scipy's `loadmat` (v5) would be the normal path and v7.3 (HDF5) an edge
case to refuse rather than guess at. Verified directly against the live archive: all 80 `.set` files begin
with the text `MATLAB 7.3 MAT-file, Platform: MACI64, Created on: ...` (not the `\\x89HDF...` byte-0 magic
the original task text expected -- MATLAB's v7.3 container puts a fixed 512-byte plain-text "user block"
first, and the real HDF5 signature `\\x89HDF\\r\\n\\x1a\\n` only appears at byte offset 512). So this
module implements the v7.3 path for real, via `h5py` reading directly from an in-memory `BytesIO` (h5py
accepts any file-like object -- no temp file, the no-disk invariant holds); the scipy v5 path is kept for
completeness (and is exercised by the offline tests, which build ordinary v5 `.set` bytes) but no real file
in this deposit takes it. `_is_matlab_v73` checks BOTH signatures, in case a future `.set` omits the text
preamble. Also `h5py` is an ADDITIONAL RUNTIME DEPENDENCY not declared in `pyproject.toml` (matching this
project's existing pattern of using `scipy.io` without declaring it there either): install with
`pip install h5py`.
"""
from __future__ import annotations

import csv
import io
import os
from typing import Any, Dict, List, Optional

import numpy as np

from bsde.ingestion.base import Adapter, RecordingRef, to_microvolts
from bsde.ingestion.remote_zip import RemoteZip

CHENNU_ARCHIVE_URL = (
    "https://api.repository.cam.ac.uk/server/api/core/bitstreams/"
    "e94a6722-da5b-4e53-8673-5e8ec106e0f7/content")

_DEFAULT_LABELS_CSV = "results/chennu_labels.csv"

_LABEL_FIELDS = ("sedation_level", "plasma_propofol_ug_per_L", "mean_reaction_time_ms", "n_correct_of_40")

_MAT_V73_TEXT_PREFIX = b"MATLAB 7.3 "
_HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"
_HDF5_SIGNATURE_OFFSET = 512  # MATLAB v7.3's fixed HDF5 "user block" size, verified against the real files


def _is_matlab_v73(blob: bytes) -> bool:
    """True if `blob` is a MATLAB v7.3 (HDF5-based) .mat/.set file, or a plain HDF5 file.

    Checks the plain-text preamble (`MATLAB 7.3 MAT-file, ...`) FIRST because that is what every real file
    in this deposit actually has at offset 0 -- not an HDF5 magic at offset 0, which is the naive guess and
    is wrong for THIS format specifically (MATLAB's v7.3 writer reserves a fixed 512-byte text "user
    block" before the real HDF5 superblock). Falls back to the real HDF5 signature at its fixed offset
    (512) in case some v7.3 writer omits the text block, and finally to offset 0 for a plain HDF5 file with
    no MATLAB preamble at all (e.g. a test fixture built directly with `h5py.File`, or a hypothetical
    non-MATLAB producer of this format).
    """
    if blob[:len(_MAT_V73_TEXT_PREFIX)] == _MAT_V73_TEXT_PREFIX:
        return True
    end = _HDF5_SIGNATURE_OFFSET + len(_HDF5_SIGNATURE)
    if blob[_HDF5_SIGNATURE_OFFSET:end] == _HDF5_SIGNATURE:
        return True
    return blob[:len(_HDF5_SIGNATURE)] == _HDF5_SIGNATURE


def _h5_decode_matlab_char_array(h5file, ref) -> str:
    """Dereference an HDF5 object reference to a MATLAB char array/string and decode it.

    EEGLAB's v7.3 writer stores every MATLAB string (channel labels, the external-data filename) as a
    column vector of uint16 character codes, one code per row -- not as an HDF5 string type.
    """
    codes = h5file[ref][()].flatten()
    return "".join(chr(int(c)) for c in codes)


def _parse_eeglab_set_v73(blob: bytes) -> Dict[str, Any]:
    """The real path for every file in this deposit -- see the module docstring's correction note."""
    import h5py

    with h5py.File(io.BytesIO(blob), "r") as f:
        if "EEG" not in f:
            raise ValueError(f"no top-level 'EEG' group in this v7.3 .set file; found keys {list(f.keys())}")
        eeg = f["EEG"]

        nbchan = int(np.asarray(eeg["nbchan"]).flatten()[0])
        pnts = int(np.asarray(eeg["pnts"]).flatten()[0])
        trials = int(np.asarray(eeg["trials"]).flatten()[0])
        srate = float(np.asarray(eeg["srate"]).flatten()[0])

        labels_ds = eeg["chanlocs"]["labels"]  # (nbchan, 1) array of HDF5 object references
        ch_names = [_h5_decode_matlab_char_array(f, labels_ds[i][0]) for i in range(labels_ds.shape[0])]
        if len(ch_names) != nbchan:
            raise ValueError(f"EEG.chanlocs has {len(ch_names)} entries but EEG.nbchan={nbchan}")

        data_ds = eeg["data"]  # here (unlike chanlocs' fields) this is the char array directly, no ref
        fdt_name = "".join(chr(int(c)) for c in np.asarray(data_ds).flatten())
        if not fdt_name.lower().endswith(".fdt"):
            raise NotImplementedError(
                f"EEG.data decoded to {fdt_name!r}, not a .fdt filename -- this v7.3 .set file may embed "
                "its samples inline rather than externally, which is not handled here.")

    return dict(nbchan=nbchan, pnts=pnts, trials=trials, srate=srate, ch_names=ch_names, fdt_name=fdt_name)


def _parse_eeglab_set_v5(blob: bytes) -> Dict[str, Any]:
    """MATLAB v5 path via scipy.io.loadmat. Kept for completeness and exercised by the offline tests, but
    no real file in this deposit is v5 -- see the module docstring's correction note."""
    import scipy.io
    mat = scipy.io.loadmat(io.BytesIO(blob), squeeze_me=True, struct_as_record=False)
    if "EEG" not in mat:
        raise ValueError(f"no top-level 'EEG' struct in this .set file; found keys {sorted(mat)}")
    eeg = mat["EEG"]

    nbchan = int(eeg.nbchan)
    pnts = int(eeg.pnts)
    trials = int(eeg.trials)
    srate = float(eeg.srate)

    chanlocs = eeg.chanlocs
    if isinstance(chanlocs, np.ndarray):
        ch_names = [str(c.labels) for c in chanlocs]
    else:
        ch_names = [str(chanlocs.labels)]
    if len(ch_names) != nbchan:
        raise ValueError(f"EEG.chanlocs has {len(ch_names)} entries but EEG.nbchan={nbchan}")

    data_field = eeg.data
    if not isinstance(data_field, str):
        raise NotImplementedError(
            f"EEG.data is a {type(data_field).__name__}, not an external filename string -- this .set "
            "file stores samples inline rather than in a companion .fdt file; not handled here.")

    return dict(nbchan=nbchan, pnts=pnts, trials=trials, srate=srate, ch_names=ch_names,
                fdt_name=data_field)


def parse_eeglab_set(blob: bytes) -> Dict[str, Any]:
    """Parse an EEGLAB `.set` file's header/metadata fields from raw bytes. Pure function: no I/O.

    Returns `{nbchan, pnts, trials, srate, ch_names, fdt_name}`. `fdt_name` is `EEG.data` when the data is
    stored externally (true of every real file in this deposit) -- the filename of the companion `.fdt`.

    Dispatches on `_is_matlab_v73`: every real `.set` in this deposit is v7.3 (HDF5) and is read with
    `h5py`; a v5 file (scipy.io.loadmat) is also supported for completeness. Raises `NotImplementedError`
    if `EEG.data` is not an external filename (the recording would have to embed its samples inline in the
    `.set` file), which is not the layout this deposit uses.
    """
    if _is_matlab_v73(blob):
        return _parse_eeglab_set_v73(blob)
    return _parse_eeglab_set_v5(blob)


def decode_fdt(raw: bytes, nbchan: int, pnts: int) -> np.ndarray:
    """Decode raw EEGLAB `.fdt` bytes into `(nbchan, n_complete_timepoints)` microvolt-scale float64.

    An EEGLAB `.fdt` is float32 little-endian, written from a MATLAB array of shape
    `(nbchan, pnts, trials)` in COLUMN-MAJOR order: all channels at t=0, then all channels at t=1, ...
    within one epoch, epochs consecutive. Flattening the trailing `(pnts, trials)` dimensions of a
    Fortran-order array is the same byte layout as flattening `pnts` alone repeated `trials` times, so
    `raw` reshapes directly to `(nbchan, n_timepoints)` with `n_timepoints = pnts * n_epochs_present` --
    no separate epoch axis is needed here; the caller keeps track of epoch boundaries if it cares.

    `pnts` is the PER-EPOCH sample count from `EEG.pnts` and is used only to assert that the decoded
    timepoint count is a whole number of epochs (pass 0 to skip that check) -- not to size the reshape,
    which is driven entirely by `len(raw)`.

    Raises rather than pads: a byte count that is not a whole number of float32 values, or not a whole
    number of `nbchan`-channel timepoints, or (when `pnts` is nonzero) not a whole number of `pnts`-sample
    epochs, all raise `ValueError`. A partially-fetched network response should never silently become a
    truncated-but-plausible-looking array.
    """
    if nbchan <= 0:
        raise ValueError(f"nbchan must be positive, got {nbchan}")
    n_bytes = len(raw)
    if n_bytes % 4 != 0:
        raise ValueError(f"{n_bytes} bytes is not a whole number of float32 values (4 bytes each)")
    bytes_per_timepoint = nbchan * 4
    if n_bytes % bytes_per_timepoint != 0:
        raise ValueError(
            f"{n_bytes} bytes ({n_bytes // 4} float32 values) is not a whole number of timepoints for "
            f"nbchan={nbchan} ({bytes_per_timepoint} bytes/timepoint) -- refusing to pad a partial "
            "trailing timepoint.")
    n_timepoints = n_bytes // bytes_per_timepoint
    if pnts and n_timepoints % pnts != 0:
        raise ValueError(
            f"{n_timepoints} decoded timepoints is not a whole number of {pnts}-sample epochs -- nbchan "
            "may be wrong, or the fetched byte range does not align to epoch boundaries.")

    flat = np.frombuffer(raw, dtype="<f4", count=n_timepoints * nbchan)
    return flat.reshape((nbchan, n_timepoints), order="F").astype(np.float64)


def _load_labels(labels_csv: str) -> Dict[str, Dict[str, float]]:
    """Load `chennu_labels.csv`, keyed by `dataset_name`. Skips the file's leading `#`-comment lines."""
    with open(labels_csv, newline="") as f:
        data_lines = [line for line in f if not line.startswith("#")]
    rows = csv.DictReader(data_lines)
    out: Dict[str, Dict[str, float]] = {}
    for row in rows:
        out[row["dataset_name"]] = {field: float(row[field]) for field in _LABEL_FIELDS}
    return out


def _subject_from_dataset_name(name: str) -> str:
    """The token before the first `-` in `dataset_name` (e.g. `02` from `02-2010-anest 20100210
    135.003`) -- see the module docstring for why this, and not any other prefix, is the subject key."""
    return name.split("-", 1)[0]


class ChennuRemoteZipAdapter(Adapter):
    """Streams the Chennu propofol EEGLAB recordings directly out of the remote ZIP archive.

    `recording_id` is a `.set` member's basename without extension (e.g. `02-2010-anest 20100210
    135.003`), which is exactly the `dataset_name` key in the label CSV and stable across runs/machines --
    never an enumeration index (`base.py`'s rule). `subject` is derived per `_subject_from_dataset_name`
    so a subject's four sedation-level recordings are grouped, not split across shards.
    """

    units = "microvolts"  # ASSUMPTION from EEGLAB convention -- see module docstring

    def __init__(self, url: str = CHENNU_ARCHIVE_URL, labels_csv: str = _DEFAULT_LABELS_CSV,
                 n_epochs: int = 4, dataset: str = "chennu_propofol", timeout: float = 150.0) -> None:
        self.url = url
        self.labels_csv = labels_csv
        self.n_epochs = n_epochs
        self.dataset = dataset
        self.name = f"chennu_remote_zip:{dataset}"
        self.timeout = timeout
        self._zip = RemoteZip(url, timeout=timeout)

    def list_recordings(self) -> List[RecordingRef]:
        labels = _load_labels(self.labels_csv)
        members = self._zip.index()
        set_names = sorted(m["name"] for m in members if m["name"].lower().endswith(".set"))

        out = []
        for name in set_names:  # sorted == deterministic order, independent of central-directory order
            base = os.path.basename(name)
            rid = base[:-4] if base.lower().endswith(".set") else base
            if rid not in labels:
                raise KeyError(
                    f"no label row for {rid!r} in {self.labels_csv} -- {len(set_names)} .set members "
                    f"found but only {len(labels)} label rows loaded; dataset_name must match a .set "
                    "member's basename (without extension) exactly.")
            label_row = labels[rid]
            out.append(RecordingRef(
                recording_id=rid, dataset=self.dataset,
                subject=_subject_from_dataset_name(rid),
                load=self._make_loader(name, label_row),
                meta=dict(label_row, n_epochs_used=self.n_epochs, set_member=name,
                          format="eeglab_set_fdt")))  # pre-load target; load()'s own meta_out below
                                                        # reports the actual clamped count too, since
                                                        # available epoch count varies per recording.
        return out

    def _make_loader(self, set_member_name: str, label_row: Dict[str, float]):
        def load():
            set_blob = self._zip.read_member(set_member_name)
            meta_set = parse_eeglab_set(set_blob)
            nbchan, pnts, srate = meta_set["nbchan"], meta_set["pnts"], meta_set["srate"]
            trials = meta_set["trials"]
            ch_names = meta_set["ch_names"]

            # The .fdt lives alongside the .set inside the same archive directory; EEG.data carries only
            # the basename (no directory), which is why we rejoin it against the .set member's own dir
            # rather than assuming a naming convention.
            set_dir = set_member_name.rsplit("/", 1)[0] if "/" in set_member_name else ""
            fdt_basename = os.path.basename(meta_set["fdt_name"])
            fdt_member = f"{set_dir}/{fdt_basename}" if set_dir else fdt_basename

            # Different recordings can retain different numbers of epochs after artifact rejection
            # (`trials` varies), so clamp rather than requesting more than exists -- and report BOTH the
            # requested and the actually-used count, so a clamp is visible rather than silently absorbed.
            n_epochs_used = min(self.n_epochs, trials)
            n_bytes_wanted = nbchan * pnts * n_epochs_used * 4
            raw = self._zip.read_member(fdt_member, max_uncompressed_bytes=n_bytes_wanted)
            data = decode_fdt(raw, nbchan, pnts)
            data_uV = to_microvolts(data, self.units)

            meta_out = dict(label_row)
            meta_out.update(
                n_epochs_requested=self.n_epochs, n_epochs_used=n_epochs_used, n_epochs_available=trials,
                source_units=self.units, nbchan=nbchan, pnts_per_epoch=pnts, set_member=set_member_name,
                fdt_member=fdt_member, format="eeglab_set_fdt",
                bytes_fetched_fdt=self._zip.last_bytes_fetched)
            return data_uV, ch_names, float(srate), meta_out
        return load
