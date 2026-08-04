"""phenotype_bar.py -- the "real phenotype" admission gate (Sec 9).

A cluster is admitted as a phenotype only if ALL hold:
  (1) resampling-stable above threshold;
  (2) cross-site reproducible -- re-emerges on the held-out hospital at the ARI
      threshold;
  (3) survives the site audit (does not align with site identity).

Firewall note: gate (2) is evaluated on the HELD-OUT hospital, which is locked in
Phase 1. So Phase 1 can take a cluster no further than "provisional" (gates 1 &
3 passed, within-discovery LOSO reproducible); the held-out ARI is computed
post-unlock -- using EEG only, no outcome -- and promotes "provisional" to
"confirmed" before the single Phase-2 outcome test runs.
"""
from __future__ import annotations

from typing import Any


def per_cluster_site_alignment(labels, sites) -> dict[int, dict[str, float]]:
    """For each cluster, the fraction of members from its single most-common
    site, compared to that site's base rate. A cluster that is far purer than
    base rate is a site artifact (gate 3 reject signal, Sec 8/9)."""
    import numpy as np

    labels = np.asarray(labels)
    sites = np.asarray(sites)
    base = {s: float((sites == s).mean()) for s in set(sites.tolist())}
    out: dict[int, dict[str, float]] = {}
    for c in sorted(set(labels.tolist())):
        members = sites[labels == c]
        if members.size == 0:
            continue
        vals, counts = np.unique(members, return_counts=True)
        top = int(counts.argmax())
        dom_site = vals[top]
        dom_frac = float(counts[top] / members.size)
        out[int(c)] = {
            "dominant_site_fraction": dom_frac,
            "dominant_site_base_rate": base[dom_site],
            "enrichment": dom_frac - base[dom_site],
        }
    return out


def apply_phenotype_bar(
    *,
    stability: float,
    site_alignment: dict[int, dict[str, float]],
    cfg: dict[str, Any],
    cross_site: dict[int, dict[str, Any]] | None = None,
    loso_min_ari: float | None = None,
) -> dict[str, Any]:
    """Combine the three gates into a per-cluster admission decision.

    `stability`    -- clustering-level resampling stability (mean ARI).
    `site_alignment` -- per-cluster output of `per_cluster_site_alignment`.
    `cross_site`   -- per-cluster {"ari", "pass"} on the held-out hospital, or
                      None while still in Phase 1 (-> "provisional").
    `loso_min_ari` -- optional within-discovery leave-one-site-out floor.
    """
    stab_min = cfg["clustering"]["stability_min"]
    purity_reject = cfg.get("audits", {}).get("site_purity_reject", 0.80)
    stable = stability >= stab_min
    loso_ok = loso_min_ari is None or loso_min_ari >= cfg["sites"][
        "reproducibility_ari_threshold"]

    decisions: dict[int, dict[str, Any]] = {}
    for c, align in site_alignment.items():
        site_artifact = align["dominant_site_fraction"] >= purity_reject
        reasons = []
        if not stable:
            reasons.append("unstable")
        if not loso_ok:
            reasons.append("loso_fail")
        if site_artifact:
            reasons.append("site_aligned")

        if reasons:
            status = "rejected"
        elif cross_site is None:
            status = "provisional"           # Phase-1 ceiling (held-out locked)
        elif cross_site.get(c, {}).get("pass"):
            status = "confirmed"
        else:
            status = "rejected"
            reasons.append("cross_site_fail")

        decisions[c] = {
            "status": status,
            "reasons": reasons,
            "stability": stability,
            "dominant_site_fraction": align["dominant_site_fraction"],
            "cross_site_ari": (cross_site or {}).get(c, {}).get("ari"),
        }

    admitted = [c for c, d in decisions.items()
                if d["status"] in ("provisional", "confirmed")]
    return {
        "stable": stable,
        "stability": stability,
        "stability_min": stab_min,
        "decisions": decisions,
        "admitted": sorted(admitted),
        "n_admitted": len(admitted),
    }
