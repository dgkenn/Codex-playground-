"""Tests for the reference register. The two invariants matter more than the happy path."""
import json, os, subprocess, sys, tempfile

MOD = "bsde.preregistry.register"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC = os.path.join(ROOT, "src")


def run(*args, expect=0):
    env = dict(os.environ, PYTHONPATH=SRC)
    p = subprocess.run([sys.executable, "-m", MOD, *args], capture_output=True, text=True, env=env)
    assert p.returncode == expect, f"exit {p.returncode} (wanted {expect}): {p.stderr}"
    return p


def _new(f, i="E01", gates=("G1 the incumbent is alive",), inc="BIS"):
    args = ["new", "--file", f, "--id", i, "--question", "q", "--primary", "p", "--incumbent", inc]
    for g in gates:
        args += ["--gate", g]
    return run(*args)


def test_new_row_is_always_registered():
    """A register whose rows can be born with a verdict measures nothing."""
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "r.jsonl")
        _new(f)
        row = json.loads(open(f).read().strip())
        assert row["outcome"] == "registered"
        assert row["outcome_detail"] == ""
        assert row["gates"] == ["G1 the incumbent is alive"]


def test_duplicate_id_refused():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "r.jsonl")
        _new(f)
        run("new", "--file", f, "--id", "E01", "--question", "q", "--primary", "p", expect=1)


def test_outcome_attaches_and_only_mutates_outcome_fields():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "r.jsonl")
        _new(f)
        before = json.loads(open(f).read().strip())
        run("outcome", "--file", f, "--id", "E01", "--outcome", "gate_failed", "--detail", "G1 refused")
        after = json.loads(open(f).read().strip())
        assert after["outcome"] == "gate_failed" and after["outcome_detail"] == "G1 refused"
        for k in before:
            if k not in ("outcome", "outcome_detail"):
                assert after[k] == before[k], f"{k} changed"


def test_unknown_outcome_refused():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "r.jsonl")
        _new(f)
        run("outcome", "--file", f, "--id", "E01", "--outcome", "great", expect=1)


def test_outcome_for_unknown_id_refused():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "r.jsonl")
        _new(f)
        run("outcome", "--file", f, "--id", "NOPE", "--outcome", "positive", expect=1)


def test_verify_flags_missing_incumbent_and_gates_without_erroring():
    """Defects are reported but are not structural errors -- the register records them as data."""
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "r.jsonl")
        _new(f, i="E02", gates=(), inc="")
        p = run("verify", "--file", f)
        assert "no incumbent named" in p.stdout
        assert "no gates" in p.stdout
