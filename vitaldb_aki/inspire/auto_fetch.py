"""auto_fetch.py -- idempotent INSPIRE auto-fetcher for PhysioNet credentialed data.

This module polls PhysioNet for INSPIRE data access and downloads when ready.
It is designed to integrate into the VitalDB study pipeline as a non-fatal,
early step (step 0 or right after cohort) that checks access cheaply with a
ranged request, downloads when approved, and logs status without blocking the
pipeline.

Protocol:
  1. If DOWNLOAD_COMPLETE sentinel exists -> skip (idempotent, return "already_downloaded")
  2. Test access with a 1-byte ranged HEAD/GET request (HTTP 200/206 = approved)
  3. If not approved -> return status "gated" and do nothing (normal until PhysioNet approves)
  4. If approved -> download via wget (resumable), unzip, write sentinel
  5. Return {"status":"downloaded"} on success, {"status":"error","msg":...} on failure

Governance:
  - auto_fetch ONLY downloads; it does NOT run validation/outcome unlocking
  - Validation (vitaldb_aki/inspire/validate.py) runs ONLY after freeze step
  - Per STRATEGY_PFDS.md: PFDS-Clinical must be frozen + hash-pinned on VitalDB
    before INSPIRE outcomes are unlocked (prevents outcome peeking)

Network resilience:
  - Wraps network calls in try/except; logs errors without raising
  - Returns {"status":"error","msg":...} on network/auth failures
  - Safe to re-run; already-downloaded data is skipped
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


def _test_access(physionet_url: str = "https://physionet.org/content/inspire/get-zip/1.4.2/") -> tuple[bool, int | None]:
    """Test access to PhysioNet INSPIRE data via cheap ranged request.

    Uses curl with .netrc credentials. Returns (access_granted, http_code).
    HTTP 200/206 -> access granted; other codes -> gated.
    """
    try:
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "--netrc",
                "-L",
                "-r", "0-0",           # 1-byte ranged request (cheap)
                "-o", "/dev/null",     # discard output
                "-w", "%{http_code}",  # return HTTP code
                physionet_url,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        http_code = int(result.stdout.strip()) if result.stdout.strip() else None
        return http_code in (200, 206), http_code
    except Exception as e:
        logger.debug(f"_test_access failed: {e}")
        return False, None


def _download_and_unzip(
    physionet_url: str,
    dest_dir: str,
    zip_filename: str = "inspire_1.4.2.zip",
) -> tuple[bool, str | None]:
    """Download INSPIRE via wget (resumable) and unzip into dest_dir.

    Returns (success, error_msg).
    """
    zip_path = os.path.join(dest_dir, zip_filename)
    os.makedirs(dest_dir, exist_ok=True)

    try:
        # Download with -c (resume) flag
        cmd = [
            "wget",
            "--netrc",
            "-c",                      # resumable
            "-O", zip_path,
            physionet_url,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,              # 1 hour timeout for full download
        )
        if result.returncode != 0:
            return False, f"wget failed with code {result.returncode}: {result.stderr}"

        # Unzip
        import zipfile
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(dest_dir)
        except Exception as e:
            return False, f"unzip failed: {e}"

        return True, None
    except subprocess.TimeoutExpired:
        return False, "download timed out (>1 hour)"
    except Exception as e:
        return False, str(e)


def auto_fetch(
    cfg: dict[str, Any] | None = None,
    dest: str | None = None,
    physionet_url: str = "https://physionet.org/content/inspire/get-zip/1.4.2/",
) -> dict[str, Any]:
    """Auto-fetch INSPIRE data from PhysioNet when access is granted.

    Idempotent: if DOWNLOAD_COMPLETE sentinel exists, returns immediately.
    Cheap to run: tests access with a 1-byte ranged request before downloading.
    Non-fatal: returns status dict; never raises exceptions.

    Args:
        cfg: config dict (unused, for future compatibility)
        dest: destination directory (default: vitaldb_aki/cache/inspire_raw/)
        physionet_url: PhysioNet INSPIRE zip URL

    Returns:
        {
            "status": "already_downloaded" | "gated" | "downloaded" | "error",
            "http": <http_code>,  # only if gated
            "path": <dest_dir>,   # only if downloaded
            "msg": <error_msg>,   # only if error
        }
    """
    # Default destination
    if dest is None:
        # Resolve relative to repo root
        _here = os.path.dirname(os.path.abspath(__file__))
        _vitaldb_aki = os.path.dirname(_here)
        _repo_root = os.path.dirname(_vitaldb_aki)
        dest = os.path.join(_repo_root, "vitaldb_aki", "cache", "inspire_raw")

    sentinel_path = os.path.join(dest, "DOWNLOAD_COMPLETE")

    # Step 1: Idempotence check
    if os.path.exists(sentinel_path):
        return {"status": "already_downloaded"}

    # Step 2: Test access cheaply
    try:
        access_granted, http_code = _test_access(physionet_url)
    except Exception as e:
        return {"status": "error", "msg": f"access test failed: {e}"}

    # Step 3: If not approved, return gated status
    if not access_granted:
        return {"status": "gated", "http": http_code}

    # Step 4: Download and unzip
    success, error_msg = _download_and_unzip(physionet_url, dest)

    if not success:
        return {"status": "error", "msg": error_msg}

    # Step 5: Write sentinel and return success
    try:
        with open(sentinel_path, "w") as fh:
            fh.write("INSPIRE download completed successfully.\n")
    except Exception as e:
        return {"status": "error", "msg": f"failed to write sentinel: {e}"}

    return {"status": "downloaded", "path": dest}


if __name__ == "__main__":
    # Standalone test
    result = auto_fetch()
    print(json.dumps(result, indent=2))
