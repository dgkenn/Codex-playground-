"""heldout_guard.py -- the access gate around the held-out hospital (Sec 6).

Binding rule: while `phase == 1`, no held-out-site data may be loaded by any
code path. Unlock is an explicit, logged, hash-stamped action that is only
permitted once the four pipeline objects have been frozen and verified (Sec 3).

This module is intentionally small and dependency-free so it can sit at the
bottom of every data-loading call stack. Any loader that touches site data MUST
route the site label through `HeldoutGuard.check_site_access` first.
"""
from __future__ import annotations

import os
from typing import Any

from common.hashing import hash_object, verify
from common.logging_utils import audit_log


class FirewallBreach(RuntimeError):
    """Raised when code attempts to cross the discovery/confirmation firewall."""


class HeldoutGuard:
    """Enforces held-out-site isolation according to the config `phase` flag."""

    def __init__(self, cfg: dict[str, Any], log_path: str | None = None):
        self.cfg = cfg
        # Coerce phase to a strict int so `phase: "1"` (YAML string), 1.0, etc.
        # cannot silently slip past the `phase == 1` block (audit CRITICAL #1).
        try:
            self.phase = int(cfg.get("phase"))
        except (TypeError, ValueError) as exc:
            raise FirewallBreach(
                f"config.phase must be an integer 1 or 2, got {cfg.get('phase')!r}"
            ) from exc
        if self.phase not in (1, 2):
            raise FirewallBreach(f"config.phase must be 1 or 2, got {self.phase}")
        self.discovery = set(cfg.get("sites", {}).get("discovery") or [])
        self.held_out = cfg.get("sites", {}).get("held_out")
        self.log_path = log_path or os.path.join(
            cfg.get("log_dir", "artifacts/logs"), "firewall.log"
        )
        if self.held_out is None:
            raise FirewallBreach("config does not define sites.held_out")
        if self.held_out in self.discovery:
            raise FirewallBreach(
                f"held_out {self.held_out!r} is also a discovery site"
            )

    # -- the gate -----------------------------------------------------------
    def is_held_out(self, site: str) -> bool:
        return site == self.held_out

    def check_site_access(self, site: str, *, context: str = "") -> str:
        """Return `site` if access is permitted; else raise FirewallBreach.

        In Phase 1 the held-out hospital is hard-blocked. The attempt is logged
        either way so a breach attempt is never silent.
        """
        # A missing/blank site label must never pass silently: a held-out row
        # with a nulled hospital field would otherwise slip through (audit #10).
        if site is None or str(site).strip() == "":
            audit_log(self.log_path, "firewall_block_null_site",
                      phase=self.phase, context=context)
            raise FirewallBreach(
                f"refusing a recording with missing/blank hospital label "
                f"(context={context!r}); cannot prove it is not the held-out site."
            )
        if self.phase == 1 and self.is_held_out(site):
            audit_log(
                self.log_path,
                "firewall_block",
                site=site,
                phase=self.phase,
                context=context,
            )
            raise FirewallBreach(
                f"PHASE 1: refusing to load held-out site {site!r} "
                f"(context={context!r}). Unlock requires phase==2 + verified "
                "frozen manifest."
            )
        return site

    # -- unlock -------------------------------------------------------------
    def unlock_held_out(self, frozen_manifest: dict[str, Any]) -> dict[str, Any]:
        """Permit held-out access. Requires phase==2 and a verified manifest.

        Returns the audit record (which carries the frozen-pipeline hash). The
        manifest must pin all four frozen objects (Sec 3); see
        `phase2.freeze.build_manifest`.
        """
        if self.phase != 2:
            raise FirewallBreach(
                f"unlock requires phase==2, config has phase=={self.phase}"
            )
        required = {
            "checkpoint_sha256",
            "harmonization_hash",
            "correction_transform_hash",
            "assignment_fn_hash",
        }
        missing = required - set(frozen_manifest)
        if missing:
            raise FirewallBreach(
                f"frozen manifest incomplete; missing {sorted(missing)}"
            )
        if any(str(frozen_manifest[k]).upper().startswith("TO-CONFIRM")
               for k in required):
            raise FirewallBreach(
                "frozen manifest still contains TO-CONFIRM placeholders"
            )
        pipeline_hash = hash_object(frozen_manifest)
        record = audit_log(
            self.log_path,
            "heldout_unlock",
            site=self.held_out,
            frozen_pipeline_hash=pipeline_hash,
            manifest=frozen_manifest,
        )
        return record

    def verify_frozen(self, manifest: dict[str, Any], expected_hash: str) -> bool:
        """Confirm a manifest matches the hash stamped at Phase-1 close."""
        return verify(manifest, expected_hash)
