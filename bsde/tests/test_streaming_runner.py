"""The streaming runner's guarantees, pinned. Every test here corresponds to a way an extraction has
actually been lost or corrupted in the sibling project.

The runner's value is entirely in what it promises when things go wrong: killed mid-run, resumed with a
changed candidate set, run twice concurrently in shards, handed a recording that fails to load. A runner
that only works on the happy path is a for-loop.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.candidates.registry import Candidate
from bsde.ingestion.base import Adapter, RecordingRef, shard_of, to_microvolts
from bsde.ingestion.runner import stream_features


# --- a fake adapter with fully known contents -------------------------------------------------------

class FakeAdapter(Adapter):
    """Deterministic synthetic recordings. `n_bad` of them raise on load."""

    units = "microvolts"

    def __init__(self, n=12, n_bad=0, dataset="fake", n_ch=4, n_samp=2500, sfreq=250.0):
        self.name, self.dataset = "fake", dataset
        self.n, self.n_bad, self.n_ch, self.n_samp, self.sfreq = n, n_bad, n_ch, n_samp, sfreq
        self.load_count = {}

    def list_recordings(self):
        refs = []
        for i in range(self.n):
            rid = f"rec{i:03d}"
            refs.append(RecordingRef(recording_id=rid, dataset=self.dataset,
                                     subject=f"sub{i // 2:03d}",       # two recordings per subject
                                     load=self._loader(rid, i), meta={"idx": i}))
        return refs

    def _loader(self, rid, i):
        def load():
            self.load_count[rid] = self.load_count.get(rid, 0) + 1
            if i < self.n_bad:
                raise OSError(f"planted read failure for {rid}")
            rng = np.random.default_rng(1000 + i)      # seeded by index: same bytes every run
            return (rng.normal(0, 10, (self.n_ch, self.n_samp)),
                    ["Fp1", "F3", "P3", "O1"][:self.n_ch], self.sfreq, {})
        return load


def _cand(name, fn, complexity=2):
    return Candidate(name=name, version="1.0", fn=fn, interpretation="test",
                     predictions={"unconscious_vs_awake": "higher"}, failure_conditions=["x"],
                     requires=("computational",), complexity=complexity)


def _cands():
    return [_cand("mean_abs", lambda d, c, s, m: float(np.mean(np.abs(d)))),
            _cand("std", lambda d, c, s, m: float(np.std(d)))]


def _read(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


# --- determinism -------------------------------------------------------------------------------------

def test_running_the_same_recording_twice_gives_byte_identical_rows(tmp_path):
    """Verifiable resumption depends on this: run twice, diff, expect nothing."""
    a, b = str(tmp_path / "a.csv"), str(tmp_path / "b.csv")
    stream_features(FakeAdapter(), _cands(), a, log=lambda *_: None)
    stream_features(FakeAdapter(), _cands(), b, log=lambda *_: None)
    assert open(a).read() == open(b).read()


# --- resumption --------------------------------------------------------------------------------------

def test_resuming_skips_completed_rows_and_does_not_refetch_them(tmp_path):
    """The expensive part is `load()`. Skipping the row but re-fetching the data would defeat the point."""
    out = str(tmp_path / "f.csv")
    ad = FakeAdapter(n=12)
    stream_features(ad, _cands(), out, limit=5, log=lambda *_: None)
    assert len(_read(out)) == 5
    assert sum(ad.load_count.values()) == 5

    ad2 = FakeAdapter(n=12)
    stats = stream_features(ad2, _cands(), out, log=lambda *_: None)
    rows = _read(out)
    assert len(rows) == 12, "resumed run must complete the remainder"
    assert stats["n_already_done"] == 5
    assert sum(ad2.load_count.values()) == 7, "already-done recordings must not be loaded again"
    assert len({r["recording_id"] for r in rows}) == 12, "no duplicate rows"


def test_a_row_survives_being_killed_because_every_row_is_fsynced(tmp_path):
    """Simulates SIGKILL by raising out of the loop after N rows. Whatever reached disk must be readable
    and must be a complete, parseable table — not a truncated final line."""
    out = str(tmp_path / "f.csv")
    ad = FakeAdapter(n=12)
    boom = {"n": 0}

    orig = ad.list_recordings

    def killing_list():
        refs = orig()
        for r in refs:
            inner = r.load

            def wrapped(inner=inner):
                boom["n"] += 1
                if boom["n"] > 4:
                    raise KeyboardInterrupt("simulated container reclamation")
                return inner()
            r.load = wrapped
        return refs

    ad.list_recordings = killing_list
    with pytest.raises(KeyboardInterrupt):
        stream_features(ad, _cands(), out, log=lambda *_: None)

    rows = _read(out)
    assert len(rows) == 4, "exactly the rows completed before the kill"
    assert all(r["status"] == "ok" and r["mean_abs"] for r in rows)
    # and the run resumes cleanly from there
    stats = stream_features(FakeAdapter(n=12), _cands(), out, log=lambda *_: None)
    assert stats["n_already_done"] == 4
    assert len(_read(out)) == 12


def test_resuming_with_a_different_candidate_set_is_refused(tmp_path):
    """Appending rows with different columns yields a file that parses fine and means nothing."""
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=3), _cands(), out, log=lambda *_: None)
    changed = _cands() + [_cand("extra", lambda d, c, s, m: 1.0)]
    with pytest.raises(ValueError, match="different column set"):
        stream_features(FakeAdapter(n=3), changed, out, log=lambda *_: None)


# --- failures are recorded, not swallowed --------------------------------------------------------------

def test_a_failing_recording_becomes_an_error_row_not_a_gap(tmp_path):
    """A silently skipped failure makes the table's row count disagree with the dataset's, with nothing to
    explain the gap — and makes a resumed run retry the same broken file forever."""
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=8, n_bad=3), _cands(), out, log=lambda *_: None)
    rows = _read(out)
    assert len(rows) == 8, "every recording gets a row, including the ones that failed"
    errs = [r for r in rows if r["status"] == "error"]
    assert len(errs) == 3
    assert all("OSError" in r["error"] for r in errs)
    assert all(r["mean_abs"] == "" for r in errs)
    # and a resume does not retry them
    ad = FakeAdapter(n=8, n_bad=3)
    stream_features(ad, _cands(), out, log=lambda *_: None)
    assert sum(ad.load_count.values()) == 0


def test_one_broken_candidate_does_not_lose_the_whole_row(tmp_path):
    out = str(tmp_path / "f.csv")
    cands = _cands() + [_cand("explodes", lambda d, c, s, m: 1 / 0)]
    stream_features(FakeAdapter(n=3), cands, out, log=lambda *_: None)
    rows = _read(out)
    assert len(rows) == 3
    for r in rows:
        assert r["status"] == "ok"
        assert r["mean_abs"] and r["std"], "the working candidates must still be recorded"
        assert r["explodes"] == ""
        assert "explodes:ZeroDivisionError" in r["error"]


# --- sharding ------------------------------------------------------------------------------------------

def test_shards_are_disjoint_and_complete(tmp_path):
    outs = [str(tmp_path / f"s{k}.csv") for k in range(4)]
    for k in range(4):
        stream_features(FakeAdapter(n=40), _cands(), outs[k], shard=k, n_shards=4, log=lambda *_: None)
    ids = [{r["recording_id"] for r in _read(o)} for o in outs]
    union = set().union(*ids)
    assert len(union) == 40, "shards together must cover every recording"
    assert sum(len(s) for s in ids) == 40, "and must not overlap"


def test_shard_assignment_does_not_depend_on_the_process(tmp_path):
    """Python salts string hashing per process, so `hash()` would reshuffle shards between runs, silently
    leaving gaps and overlaps. Only the randomised path would be affected, which is the worst case."""
    import subprocess
    code = ("import sys; sys.path.insert(0, %r);"
            "from bsde.ingestion.base import shard_of;"
            "print([shard_of('rec%%03d' %% i, 7) for i in range(20)])"
            % os.path.join(os.path.dirname(__file__), "..", "src"))
    a = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env={**os.environ, "PYTHONHASHSEED": "0"}).stdout
    b = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env={**os.environ, "PYTHONHASHSEED": "12345"}).stdout
    assert a and a == b, f"shard assignment changed with PYTHONHASHSEED:\n{a}{b}"


# --- units are part of the contract ----------------------------------------------------------------------

def test_units_are_declared_not_guessed():
    assert to_microvolts(np.array([1.0]), "volts")[0] == pytest.approx(1e6)
    assert to_microvolts(np.array([1.0]), "mV")[0] == pytest.approx(1e3)
    assert to_microvolts(np.array([5.0]), "microvolts")[0] == pytest.approx(5.0)
    with pytest.raises(ValueError, match="unknown source units"):
        to_microvolts(np.array([1.0]), "not_a_unit")
    with pytest.raises(ValueError, match="unknown source units"):
        to_microvolts(np.array([1.0]), "")


def test_dimensionless_units_raise_unless_explicitly_accepted():
    """I-CARE declares `/nu` -- WFDB normalized units. There is no conversion to microvolts, so the default
    must refuse; accepting it has to be a deliberate act that also carries the validity flag."""
    for u in ("nu", "normalized", "arbitrary", "au"):
        with pytest.raises(ValueError, match="DIMENSIONLESS"):
            to_microvolts(np.array([1.0]), u)
        assert to_microvolts(np.array([2.5]), u, allow_dimensionless=True)[0] == pytest.approx(2.5), \
            "dimensionless values must pass through UNSCALED -- any factor would be invented"


def test_a_dimensionless_recording_is_flagged_not_relabelled_as_microvolts():
    """The flag is the whole mechanism: an absolute-amplitude feature must be able to see that it cannot
    run. Silently labelling `nu` as microvolts is the failure this prevents."""
    from bsde.ingestion.base import DIMENSIONLESS_UNITS
    assert "nu" in DIMENSIONLESS_UNITS
    assert "microvolts" not in DIMENSIONLESS_UNITS
    assert "uv" not in DIMENSIONLESS_UNITS


def test_a_recording_ref_needs_an_id():
    with pytest.raises(ValueError, match="resume key"):
        RecordingRef(recording_id="", dataset="d", load=lambda: None)


def test_subject_defaults_to_recording_id_but_can_be_set():
    r = RecordingRef(recording_id="r1", dataset="d", load=lambda: None)
    assert r.subject == "r1"
    r2 = RecordingRef(recording_id="r1_ses2", dataset="d", load=lambda: None, subject="sub01")
    assert r2.subject == "sub01"


def test_subject_column_is_carried_into_the_feature_table(tmp_path):
    """Subject-level splitting is impossible downstream if the subject never reaches the table. The fake
    adapter puts two recordings per subject precisely so this can be checked."""
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=12), _cands(), out, log=lambda *_: None)
    rows = _read(out)
    subs = {r["subject"] for r in rows}
    assert len(subs) == 6 and len(rows) == 12, "12 recordings across 6 subjects must be visible as such"


# --- meta columns carry the state label --------------------------------------------------------------

def test_declared_meta_keys_become_columns_so_the_label_survives(tmp_path):
    """Without this the extraction has no outcome column. An adapter can parse `task-sed` out of a BIDS
    path into ref.meta, but if the row does not carry it the feature table is unlabelled and the whole
    stream has to be redone or reverse-engineered from the recording id."""
    class Tagged(FakeAdapter):
        def list_recordings(self):
            refs = super().list_recordings()
            for i, r in enumerate(refs):
                r.meta = {"task": "sed" if i % 2 else "awake", "acq": "rest"}
            return refs

    out = str(tmp_path / "f.csv")
    stream_features(Tagged(n=6), _cands(), out, log=lambda *_: None, meta_keys=["task", "acq"])
    rows = _read(out)
    assert "meta_task" in rows[0] and "meta_acq" in rows[0]
    assert {r["meta_task"] for r in rows} == {"awake", "sed"}
    assert all(r["meta_acq"] == "rest" for r in rows)


def test_a_missing_meta_key_is_blank_not_absent(tmp_path):
    """A blank cell is inspectable; a missing column silently changes the schema between datasets."""
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=3), _cands(), out, log=lambda *_: None, meta_keys=["task"])
    rows = _read(out)
    assert "meta_task" in rows[0]
    assert all(r["meta_task"] == "" for r in rows)


def test_meta_columns_participate_in_the_resume_schema_guard(tmp_path):
    """Adding a meta key changes the column set, so resuming must refuse rather than append a
    differently-shaped row."""
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=3), _cands(), out, log=lambda *_: None, meta_keys=["task"])
    with pytest.raises(ValueError, match="different column set"):
        stream_features(FakeAdapter(n=3), _cands(), out, log=lambda *_: None, meta_keys=["task", "acq"])


# --- definition drift ---------------------------------------------------------------------------------

def test_resuming_after_a_feature_definition_changed_is_refused(tmp_path, monkeypatch):
    """The bug this exists for: `f_lziv` was changed to resample to a common rate -- a correctness fix --
    while a stream was mid-flight. The column set stayed byte-identical, so the schema guard was silent, and
    resuming would have appended new-definition rows beside old-definition ones under the same heading."""
    import bsde.ingestion.runner as R
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=3), _cands(), out, log=lambda *_: None)

    real = R.definition_fingerprint
    monkeypatch.setattr(R, "definition_fingerprint",
                        lambda cands: {k: v + "-CHANGED" for k, v in real(cands).items()})
    with pytest.raises(ValueError, match="CODE defining these candidates changed"):
        R.stream_features(FakeAdapter(n=6), _cands(), out, log=lambda *_: None)


def test_definition_drift_can_be_accepted_deliberately(tmp_path, monkeypatch):
    """Escape hatch, but it must be explicit and it must warn -- silence here is the failure mode."""
    import bsde.ingestion.runner as R
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=3), _cands(), out, log=lambda *_: None)
    real = R.definition_fingerprint
    monkeypatch.setattr(R, "definition_fingerprint",
                        lambda cands: {k: v + "-CHANGED" for k, v in real(cands).items()})
    msgs = []
    R.stream_features(FakeAdapter(n=6), _cands(), out, log=msgs.append, allow_definition_drift=True)
    assert len(_read(out)) == 6
    assert any("definition drift accepted" in m for m in msgs), msgs


def test_an_unchanged_definition_resumes_normally(tmp_path):
    """The guard must not fire on an ordinary resume, or it would make resumption unusable."""
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=8), _cands(), out, limit=3, log=lambda *_: None)
    stats = stream_features(FakeAdapter(n=8), _cands(), out, log=lambda *_: None)
    assert stats["n_already_done"] == 3
    assert len(_read(out)) == 8


def test_a_manifest_is_written_next_to_the_table(tmp_path):
    import json as _json
    out = str(tmp_path / "f.csv")
    stream_features(FakeAdapter(n=2), _cands(), out, log=lambda *_: None)
    m = _json.load(open(out + ".manifest.json"))
    assert set(m["definitions"]) == {c.name for c in _cands()}
    assert "recording_id" in m["fields"]
    # the fingerprint must combine the declared claim with a code hash, not just one of them
    for v in m["definitions"].values():
        assert ":" in v and len(v.split(":")) == 2
