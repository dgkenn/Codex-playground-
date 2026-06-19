"""tuh_fetch.py -- TUH EEG Corpus transport (external replication, Sec 15).

The Temple University Hospital EEG Corpus is the gold-standard EXTERNAL
validation set: a finding on HEEDB is a hypothesis until it replicates on TUH
(Sec 15). TUH is a *different health system*, so it is never part of the
discovery/held-out split -- it is applied AFTER the frozen pipeline is published,
as its own corpus.

Access model (per the NEDC credentialing email): rsync over SSH with a key
registered with NEDC:

    rsync -auvxL -e "ssh -i ~/.ssh/id_ed25519" \
        nedc-tuh-eeg@www.isip.piconepress.com:data/tuh_eeg/TEST .

Auth is the credentialed user's OWN ssh key -- never stored in this repo. Like
the BDSP transport, each EDF is rsynced to scratch only while its
`open_recording` context is open, then deleted ("delete our data when you are
done using it" -- NEDC).

The shell-out is injectable (`runner`) so command construction is unit-testable
without network, ssh, or rsync installed.
"""
from __future__ import annotations

import os
import subprocess
from typing import Any, Callable, Iterable

from pipeline.stream_fetch import RecordingRef, _BDSPClient, _parse_catalog

# A runner takes an argv list and returns (returncode, stdout, stderr).
Runner = Callable[[list[str]], "tuple[int, str, str]"]


def _default_runner(cmd: list[str]) -> tuple[int, str, str]:  # pragma: no cover - real shell-out
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError as exc:
        # rsync/ssh not installed on this host.
        return 127, "", f"{exc} (install rsync + openssh-client)"


class TUHRsyncClient(_BDSPClient):
    """rsync-over-SSH transport for the TUH EEG Corpus (external replication)."""

    def __init__(self, cfg: dict[str, Any], runner: Runner | None = None):
        super().__init__(cfg)
        self.tcfg = cfg["external_replication"]["tuh"]
        self.runner = runner or _default_runner

    # -- ssh / rsync plumbing ----------------------------------------------
    def _ssh_opt(self) -> str:
        key = os.path.expanduser(self.tcfg["ssh_key"])
        # accept-new auto-trusts the host key on first contact (non-interactive);
        # BatchMode prevents any password prompt from hanging automation.
        return f"ssh -i {key} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

    def _remote(self, path: str) -> str:
        user, host = self.tcfg["user"], self.tcfg["host"]
        return f"{user}@{host}:{path}"

    def rsync_cmd(self, remote_path: str, dest: str) -> list[str]:
        """Build the exact NEDC rsync command (argv form)."""
        return ["rsync", "-auvxL", "-e", self._ssh_opt(),
                self._remote(remote_path), dest]

    def _rsync(self, remote_path: str, dest: str) -> str:
        os.makedirs(dest, exist_ok=True)
        rc, out, err = self.runner(self.rsync_cmd(remote_path, dest))
        if rc != 0:
            raise RuntimeError(f"rsync failed (rc={rc}) for {remote_path}: {err or out}")
        return os.path.join(dest, os.path.basename(remote_path.rstrip("/")))

    # -- connectivity probe (Picone's TEST file) ---------------------------
    def test_connection(self, dest: str | None = None) -> dict[str, Any]:
        """Run the documented TEST-file rsync to verify credentials + reach.

        Mirrors the NEDC onboarding check; returns {ok, cmd, returncode, ...}.
        """
        dest = dest or self.tcfg.get("scratch_dir", "/tmp/tuh_scratch")
        os.makedirs(dest, exist_ok=True)
        cmd = self.rsync_cmd(self.tcfg.get("test_path", "data/tuh_eeg/TEST"), dest)
        rc, out, err = self.runner(cmd)
        return {"ok": rc == 0, "returncode": rc,
                "cmd": " ".join(cmd), "stdout": out, "stderr": err,
                "downloaded": os.path.join(dest, "TEST") if rc == 0 else None}

    # -- catalog / recordings ----------------------------------------------
    def list_recordings(self, hospital: str = "TUH") -> Iterable[RecordingRef]:
        """Yield recordings from a LOCAL manifest of EDF paths (one row each).

        TUH is a single corpus (no hospital split); `hospital` is fixed to "TUH".
        The manifest (a TSV the user generates, e.g. by rsyncing the file list)
        carries acquisition metadata only.
        """
        manifest = self.tcfg.get("manifest")
        if not manifest or not os.path.exists(manifest):
            raise FileNotFoundError(
                "external_replication.tuh.manifest must point to a local TSV of "
                "EDF paths (+ acquisition metadata). Generate it from the corpus "
                "listing at isip.piconepress.com/projects/nedc/html/tuh_eeg/."
            )
        with open(manifest, "rb") as fh:
            rows = _parse_catalog(fh.read(), self.tcfg.get("manifest_format", "tsv"))
        cols = self.tcfg.get("manifest_columns", {})
        for r in rows:
            yield RecordingRef(
                recording_id=str(r.get(cols.get("recording_id", "recording_id"), "")),
                patient_id=str(r.get(cols.get("patient_id", "patient_id"), "")),
                hospital="TUH",
                sampling_rate=_f(r.get(cols.get("sampling_rate", "sfreq"))),
                age=_f(r.get(cols.get("age", "age"))),
                sex=r.get(cols.get("sex", "sex")) or None,
                uri=r.get(cols.get("object_key", "edf_path")) or None,
            )

    def open_stream(self, ref: RecordingRef):  # pragma: no cover - needs mne + ssh
        import mne
        scratch = self.tcfg.get("scratch_dir", "/tmp/tuh_scratch")
        local = self._rsync(ref.uri, scratch)
        raw = mne.io.read_raw_edf(local, preload=False, verbose=False)
        try:
            raw._fetch_tmp = local
        except Exception:
            pass
        return raw

    def download_shard(self, refs: list[RecordingRef], dest: str) -> str:  # pragma: no cover - needs ssh
        shard = os.path.join(dest, "shard")
        for ref in refs:
            self._rsync(ref.uri, shard)
        return shard


def _f(v):
    if v in ("", None):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
