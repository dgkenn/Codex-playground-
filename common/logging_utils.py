"""Append-only audit logging.

Integrity-relevant actions (held-out unlock, freeze, the single Phase-2 test)
must leave a tamper-evident trail (Sec 0, 3, 18). Every record is a one-line
JSON object appended to a log file, stamped with UTC time and -- where relevant
-- the frozen-pipeline hash. The log is never rewritten in place.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_log(log_path: str | os.PathLike, event: str, **fields: Any) -> dict:
    """Append one JSON record to `log_path` and return it.

    Creates parent directories as needed. Each record is self-describing so the
    log can be replayed to reconstruct exactly what happened and when.
    """
    record = {"ts_utc": _utc_now(), "event": event, **fields}
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    return record


def read_log(log_path: str | os.PathLike) -> list[dict]:
    if not os.path.exists(log_path):
        return []
    out: list[dict] = []
    with open(log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
