"""run_per_organ.py -- per-organ evaluation driver (secondary analysis).

Loops the incremental-value harness (run.py) over the composite PRIMARY outcome
and each of the seven per-organ SECONDARY labels, tabulating results so we can
see which feature additions (PK, A-line, etc.) help which organ system.

For each target:
  * call vitaldb_aki.models.run.run() with target={target}
  * catch exceptions (some organs may have too few events, or CV fold failures)
  * record per target: n, n_events, per-feature-set AUROC + AUPRC,
    the pk_vs_comprehensive ΔAUROC + DeLong p (primary incremental contrast),
    and negative-control AUROC
  * write results to cache_dir/per_organ_results.json and
    vitaldb_aki/docs/PER_ORGAN_RESULTS.md (markdown table)
"""
from __future__ import annotations

import json
import os
from typing import Any

import numpy as np


def _safe_get(d: dict, *keys, default=None):
    """Safely navigate nested dict, returning default if any key missing."""
    current = d
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return default
    return current if current is not None else default


def run_all(cfg: dict[str, Any], model_name: str = "logreg", seed: int = 0) -> dict[str, Any]:
    """
    Run incremental-value harness over composite and all per-organ targets.

    Args:
        cfg: loaded config dict (see vitaldb_aki/config.yaml)
        model_name: "logreg" or "gbm"
        seed: random seed for reproducibility

    Returns:
        results dict with per-target metrics, written to JSON and markdown
    """
    # Lazy import to avoid circular dependencies and keep module lightweight
    from vitaldb_aki.models.run import run as run_harness

    # Pre-registered targets: composite primary + seven per-organ secondaries
    targets = [
        "composite",
        "organ_renal",
        "organ_hepatocellular",
        "organ_cholestatic",
        "organ_coagulation_plt",
        "organ_coagulation_inr",
        "organ_hypoperfusion",
        "organ_mortality",
    ]

    results: dict[str, Any] = {
        "model": model_name,
        "seed": seed,
        "targets": {},
        "errors": {},
    }

    for target in targets:
        try:
            # Run the incremental-value harness for this target
            run_result = run_harness(cfg, model_name=model_name, seed=seed, target=target)

            # Extract relevant fields: n, n_events, per-set AUROC/AUPRC
            target_results = {
                "n": run_result.get("n"),
                "n_events": run_result.get("n_events"),
                "sets": {},
            }

            # Per-feature-set discrimination metrics
            for set_name, set_metrics in run_result.get("sets", {}).items():
                target_results["sets"][set_name] = {
                    "auroc": _safe_get(set_metrics, "auroc"),
                    "auprc": _safe_get(set_metrics, "auprc"),
                    "prevalence": _safe_get(set_metrics, "prevalence"),
                }

            # Primary incremental contrast: pk_vs_comprehensive
            pk_vs_comp = None
            for contrast in run_result.get("incremental_value", []):
                if contrast.get("primary"):  # pk_vs_comprehensive is marked primary
                    pk_vs_comp = {
                        "delta_auroc": contrast.get("delta_auroc"),
                        "delong_p": contrast.get("delong_p"),
                        "delta_auroc_ci95": contrast.get("delta_auroc_ci95"),
                    }
                    break
            if pk_vs_comp:
                target_results["pk_vs_comprehensive"] = pk_vs_comp

            # Negative control AUROC (shuffled labels)
            target_results["negative_control_auroc"] = _safe_get(
                run_result, "negative_control", "auroc_shuffled"
            )

            results["targets"][target] = target_results

        except Exception as e:
            # Catch and record errors (too few events, CV fold failures, etc.)
            error_msg = f"{type(e).__name__}: {str(e)}"
            results["errors"][target] = error_msg

    # Write JSON results to cache
    cache_dir = cfg["data"]["cache_dir"]
    json_out = os.path.join(cache_dir, "per_organ_results.json")
    os.makedirs(cache_dir, exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    # Write markdown table
    md_out = os.path.join(os.path.dirname(__file__), "..", "docs", "PER_ORGAN_RESULTS.md")
    os.makedirs(os.path.dirname(md_out), exist_ok=True)

    md_lines = [
        "# Per-Organ Incremental-Value Results",
        "",
        "Secondary analysis: evaluation of incremental value of PK features across",
        f"composite (primary) and per-organ (secondary) outcomes.",
        "",
        f"Model: {model_name}, Seed: {seed}",
        "",
        "## Results Table",
        "",
    ]

    # Build markdown table header
    header = [
        "| Target",
        "N",
        "N Events",
        "Prev",
        "Standard AUROC",
        "Comp AUROC",
        "PK AUROC",
        "Δ(PK-Comp) AUROC",
        "DeLong p",
        "Neg-Ctrl AUROC",
        "Notes |",
    ]
    md_lines.append("".join(header))

    # Separator
    sep = ["|" + "-" * 50 + "|"] * len(header)
    md_lines.append("".join(sep))

    # Rows
    for target in targets:
        if target in results["targets"]:
            tr = results["targets"][target]
            n = tr.get("n", "—")
            n_events = tr.get("n_events", "—")
            prevalence = tr["sets"].get("standard", {}).get("prevalence")
            prev_str = f"{prevalence:.3f}" if prevalence is not None else "—"

            standard_auroc = tr["sets"].get("standard", {}).get("auroc")
            standard_str = f"{standard_auroc:.3f}" if standard_auroc is not None else "—"

            comp_auroc = tr["sets"].get("comprehensive", {}).get("auroc")
            comp_str = f"{comp_auroc:.3f}" if comp_auroc is not None else "—"

            pk_auroc = tr["sets"].get("pk", {}).get("auroc")
            pk_str = f"{pk_auroc:.3f}" if pk_auroc is not None else "—"

            pk_vs_comp = tr.get("pk_vs_comprehensive", {})
            delta_auroc = pk_vs_comp.get("delta_auroc")
            delta_str = f"{delta_auroc:+.3f}" if delta_auroc is not None else "—"

            delong_p = pk_vs_comp.get("delong_p")
            p_str = f"{delong_p:.4f}" if delong_p is not None else "—"

            neg_ctrl = tr.get("negative_control_auroc")
            neg_ctrl_str = f"{neg_ctrl:.3f}" if neg_ctrl is not None else "—"

            notes = ""
            if n_events and n and n_events < 10:
                notes = "Few events"

            row = (
                f"| {target:30s} "
                f"| {n:7} "
                f"| {n_events:8} "
                f"| {prev_str:6s} "
                f"| {standard_str:13s} "
                f"| {comp_str:10s} "
                f"| {pk_str:8s} "
                f"| {delta_str:14s} "
                f"| {p_str:8s} "
                f"| {neg_ctrl_str:14s} "
                f"| {notes} |"
            )
            md_lines.append(row)

        elif target in results["errors"]:
            error = results["errors"][target]
            md_lines.append(f"| {target:30s} | ERROR: {error} |")

    md_lines.extend(["", "## Notes", ""])
    if results["errors"]:
        md_lines.append("### Failed Targets")
        md_lines.append("")
        for target, error in results["errors"].items():
            md_lines.append(f"- **{target}**: {error}")

    with open(md_out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md_lines))

    print(f"\n✓ Results written to {json_out}")
    print(f"✓ Markdown table written to {md_out}")

    return results


if __name__ == "__main__":
    from common.config import load_yaml

    cfg = load_yaml("vitaldb_aki/config.yaml")
    results = run_all(cfg, model_name="logreg", seed=0)
