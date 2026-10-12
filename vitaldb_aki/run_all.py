"""run_all.py -- idempotent, restart-resilient full study runner.

Runs the VitalDB postoperative organ-injury study end-to-end, skipping any step
whose output already exists and is fresh.  Safe to re-run; a completed run just
regenerates RESULTS.md.

Steps (in order)
----------------
0. inspire_autofetch  -- auto_fetch() INSPIRE from PhysioNet (non-fatal; logs status)
1. cohort_composite   -- build_composite_cohort() -> cohort_composite.csv
2. matrix             -- build_matrix()            -> feature_matrix.csv
3. harness            -- run() for each model x target combination
4. multitask          -- run_multitask()           -> multitask_results.json
5. hypotension        -- run_analysis()            -> hypotension_treatment_results.json
6. consolidate        -- (re)write RESULTS.md + run_all_status.json (always)

Usage
-----
    python3 vitaldb_aki/run_all.py [--force <step>]

Lock
----
A PID lock file at cache_dir/run_all.lock prevents concurrent runs.  Stale
locks (> 2 h old) are silently ignored.

Force
-----
    --force matrix      Delete the matrix marker + run the step again.
    --force cohort      Delete cohort csv + rebuild.
    --force all         Delete all step markers and start fresh.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import traceback
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Config is always relative to the package root; resolve from run_all.py's dir.
_CONFIG_PATH = os.path.join(_HERE, "config.yaml")


def _load_cfg() -> dict[str, Any]:
    import yaml  # type: ignore
    with open(_CONFIG_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    # cache_dir is stored relative to repo root in config.yaml
    cfg["data"]["cache_dir"] = os.path.join(_ROOT, cfg["data"]["cache_dir"])
    return cfg


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging(cache_dir: str) -> logging.Logger:
    os.makedirs(cache_dir, exist_ok=True)
    log_path = os.path.join(cache_dir, "run_all.log")
    logger = logging.getLogger("run_all")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------

_LOCK_STALE_S = 7200  # 2 hours

def _acquire_lock(cache_dir: str, logger: logging.Logger) -> bool:
    """Write a PID lock.  Returns True if acquired, False if blocked."""
    lock_path = os.path.join(cache_dir, "run_all.lock")
    if os.path.exists(lock_path):
        age = time.time() - os.path.getmtime(lock_path)
        if age < _LOCK_STALE_S:
            try:
                with open(lock_path) as fh:
                    pid = fh.read().strip()
            except OSError:
                pid = "unknown"
            logger.warning("Lock exists (pid=%s, age=%.0fs) -- another run may be active; exiting.", pid, age)
            return False
        logger.info("Stale lock found (age=%.0fs) -- ignoring.", age)
    with open(lock_path, "w") as fh:
        fh.write(str(os.getpid()))
    return True


def _release_lock(cache_dir: str) -> None:
    try:
        os.remove(os.path.join(cache_dir, "run_all.lock"))
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------

STEPS = ["inspire_autofetch", "cohort_composite", "matrix", "harness", "multitask", "hypotension", "consolidate"]


def _load_status(cache_dir: str) -> dict[str, str]:
    path = os.path.join(cache_dir, "run_all_status.json")
    if os.path.exists(path):
        try:
            with open(path) as fh:
                return json.load(fh)
        except Exception:
            pass
    return {s: "pending" for s in STEPS}


def _save_status(cache_dir: str, status: dict[str, str]) -> None:
    path = os.path.join(cache_dir, "run_all_status.json")
    with open(path, "w") as fh:
        json.dump(status, fh, indent=2)


# ---------------------------------------------------------------------------
# Step 0: INSPIRE auto-fetch (non-fatal)
# ---------------------------------------------------------------------------

def step_inspire_autofetch(cfg: dict, cache_dir: str, logger: logging.Logger) -> bool:
    """Poll PhysioNet for INSPIRE data and download when access is granted.

    This step is non-fatal: if gated/unavailable, it logs and continues.
    The result status is added to run_all_status.json for visibility.

    Returns True always (never blocks the pipeline).
    """
    logger.info("Step inspire_autofetch: RUNNING ...")
    try:
        from vitaldb_aki.inspire.auto_fetch import auto_fetch
        result = auto_fetch(cfg=cfg, dest=None)  # dest defaults to cache/inspire_raw/
        status = result.get("status", "unknown")
        if status == "already_downloaded":
            logger.info("Step inspire_autofetch: DONE (already downloaded)")
        elif status == "gated":
            http = result.get("http")
            logger.info("Step inspire_autofetch: GATED (HTTP %s) -- PhysioNet access not yet approved", http)
        elif status == "downloaded":
            path = result.get("path", "?")
            logger.info("Step inspire_autofetch: DONE (downloaded to %s)", path)
        elif status == "error":
            msg = result.get("msg", "unknown error")
            logger.warning("Step inspire_autofetch: ERROR (non-fatal) -- %s", msg)
        else:
            logger.info("Step inspire_autofetch: DONE (status=%s)", status)
        return True  # always succeed (non-fatal step)
    except Exception:
        logger.warning("Step inspire_autofetch: EXCEPTION (non-fatal)\n%s", traceback.format_exc())
        return True  # always succeed (non-fatal step)


# ---------------------------------------------------------------------------
# Step 1: cohort composite
# ---------------------------------------------------------------------------

def step_cohort(cfg: dict, cache_dir: str, logger: logging.Logger, force: bool) -> bool:
    out = os.path.join(cache_dir, "cohort_composite.csv")
    if os.path.exists(out) and not force:
        logger.info("Step cohort_composite: SKIP (output exists)")
        return True
    if force and os.path.exists(out):
        os.remove(out)
    logger.info("Step cohort_composite: RUNNING ...")
    try:
        from vitaldb_aki.cohort.build_composite import build_composite_cohort
        result = build_composite_cohort(cfg)
        logger.info("Step cohort_composite: DONE  n_labelable=%s  composite_events=%s",
                    result.get("n_labelable"), result.get("composite_events"))
        return True
    except Exception:
        logger.error("Step cohort_composite: FAILED\n%s", traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Step 2: feature matrix
# ---------------------------------------------------------------------------

def _current_specs_hash(cfg: dict) -> str:
    """Compute the specs_hash that build_matrix WOULD produce for the current MODULES."""
    from vitaldb_aki.features.build_matrix import MODULES
    from common.hashing import hash_object
    all_specs = []
    for m in MODULES:
        all_specs.extend(m.SPECS)
    return hash_object([(s.name, s.fset, s.timing) for s in all_specs])


def step_matrix(cfg: dict, cache_dir: str, logger: logging.Logger, force: bool,
                workers: int = 12) -> bool:
    matrix_csv = os.path.join(cache_dir, "feature_matrix.csv")
    done_flag = os.path.join(cache_dir, "_matrix_build_done.json")

    # Check freshness: the matrix is stale if specs changed
    def _is_fresh() -> bool:
        if not os.path.exists(matrix_csv):
            return False
        if not os.path.exists(done_flag):
            return False
        try:
            with open(done_flag) as fh:
                d = json.load(fh)
            saved_hash = d.get("specs_hash", "")
            current_hash = _current_specs_hash(cfg)
            if saved_hash != current_hash:
                logger.info("Step matrix: specs_hash changed (%s -> %s) -- will rebuild",
                            saved_hash[:12], current_hash[:12])
                return False
            return True
        except Exception:
            return False

    if _is_fresh() and not force:
        logger.info("Step matrix: SKIP (matrix fresh, specs_hash matches)")
        return True

    if force:
        for f in (matrix_csv, done_flag):
            if os.path.exists(f):
                os.remove(f)

    logger.info("Step matrix: RUNNING (workers=%d) ...", workers)
    try:
        from vitaldb_aki.features.build_matrix import build_matrix
        summary = build_matrix(cfg, workers=workers)
        # Write the done marker with specs_hash for freshness checks
        with open(done_flag, "w") as fh:
            json.dump({"specs_hash": summary["specs_hash"],
                       "n_rows": summary["n_rows"],
                       "n_features": summary["n_features"],
                       "modules": summary["modules"]}, fh, indent=2)
        logger.info("Step matrix: DONE  n_rows=%s  n_features=%s  modules=%s",
                    summary["n_rows"], summary["n_features"], summary["modules"])
        return True
    except Exception:
        logger.error("Step matrix: FAILED\n%s", traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Step 3: harness (incremental-value per model x target)
# ---------------------------------------------------------------------------

ORGAN_TARGETS = [
    "organ_renal", "organ_hepatocellular", "organ_cholestatic",
    "organ_coagulation_plt", "organ_coagulation_inr",
    "organ_hypoperfusion", "organ_mortality",
]
MODELS = ["logreg", "gbm"]


def step_harness(cfg: dict, cache_dir: str, logger: logging.Logger,
                 force: bool) -> bool:
    """Run incremental-value harness for each (model, target) pair; skip if done."""
    all_ok = True
    targets = ["composite"] + ORGAN_TARGETS

    for model in MODELS:
        for target in targets:
            out = os.path.join(cache_dir, f"incremental_value_{target}_{model}.json")
            if os.path.exists(out) and not force:
                logger.info("Step harness [%s/%s]: SKIP (output exists)", model, target)
                continue
            if force and os.path.exists(out):
                os.remove(out)
            logger.info("Step harness [%s/%s]: RUNNING ...", model, target)
            try:
                from vitaldb_aki.models.run import run
                run(cfg, model_name=model, target=target)
                logger.info("Step harness [%s/%s]: DONE", model, target)
            except Exception:
                logger.error("Step harness [%s/%s]: FAILED\n%s",
                             model, target, traceback.format_exc())
                all_ok = False  # log and continue; some organs may not have enough events
    return all_ok


# ---------------------------------------------------------------------------
# Step 4: multitask
# ---------------------------------------------------------------------------

def step_multitask(cfg: dict, cache_dir: str, logger: logging.Logger, force: bool) -> bool:
    out = os.path.join(cache_dir, "multitask_results.json")
    if os.path.exists(out) and not force:
        logger.info("Step multitask: SKIP (output exists)")
        return True
    if force and os.path.exists(out):
        os.remove(out)
    logger.info("Step multitask: RUNNING ...")
    try:
        from vitaldb_aki.models.multitask import run_multitask
        run_multitask(cfg)
        logger.info("Step multitask: DONE")
        return True
    except Exception:
        logger.error("Step multitask: FAILED\n%s", traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Step 5: hypotension treatment analysis
# ---------------------------------------------------------------------------

def step_hypotension(cfg: dict, cache_dir: str, logger: logging.Logger, force: bool) -> bool:
    out = os.path.join(cache_dir, "hypotension_treatment_results.json")
    if os.path.exists(out) and not force:
        logger.info("Step hypotension: SKIP (output exists)")
        return True
    if force and os.path.exists(out):
        os.remove(out)
    logger.info("Step hypotension: RUNNING ...")
    try:
        from vitaldb_aki.analysis.hypotension_treatment import main as ht_main
        # Prefer the real matrix if available
        matrix_csv = os.path.join(cache_dir, "feature_matrix.csv")
        ht_main(matrix_path=matrix_csv if os.path.exists(matrix_csv) else None,
                cache_dir=cache_dir)
        logger.info("Step hypotension: DONE")
        return True
    except Exception:
        logger.error("Step hypotension: FAILED\n%s", traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Step 6: consolidate -- build RESULTS.md
# ---------------------------------------------------------------------------

def _load_json_safe(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def _fmt_auroc(v) -> str:
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.4f}"
    except Exception:
        return str(v)


def _fmt_delta(v) -> str:
    if v is None:
        return "N/A"
    try:
        f = float(v)
        return f"{f:+.4f}"
    except Exception:
        return str(v)


def step_consolidate(cfg: dict, cache_dir: str, logger: logging.Logger,
                     status: dict[str, str]) -> bool:
    """Always rebuild RESULTS.md from whatever cache files exist."""
    logger.info("Step consolidate: building RESULTS.md ...")

    lines: list[str] = []
    lines.append("# VitalDB AKI Study — Results Summary")
    lines.append("")
    lines.append(
        "> Auto-generated by `vitaldb_aki/run_all.py` from cached result files.  "
        "Do not edit by hand."
    )
    lines.append("")

    # ---- Cohort summary ----
    cohort_summ = _load_json_safe(os.path.join(cache_dir, "cohort_composite_summary.json"))
    if cohort_summ:
        lines.append("## Cohort")
        lines.append("")
        n = cohort_summ.get("n_labelable", "?")
        ev = cohort_summ.get("composite_events", "?")
        rate = cohort_summ.get("composite_rate", None)
        rate_s = f"{rate:.1%}" if rate is not None else "?"
        lines.append(f"- Labelable N = {n}, composite events = {ev} ({rate_s})")
        comps = cohort_summ.get("component_counts", {})
        if comps:
            lines.append("- Component event counts:")
            for comp, info in comps.items():
                lines.append(f"  - {comp}: {info.get('events','?')} / {info.get('labelable','?')} "
                             f"({info.get('rate',0):.1%})")
        lines.append("")

    # ---- Incremental value: composite outcome ----
    lines.append("## Incremental Value — Composite Outcome")
    lines.append("")
    for model in MODELS:
        iv = _load_json_safe(os.path.join(cache_dir, f"incremental_value_composite_{model}.json"))
        # Fall back to legacy names (without target prefix)
        if iv is None:
            iv = _load_json_safe(os.path.join(cache_dir, f"incremental_value_{model}.json"))
        if iv is None:
            lines.append(f"### {model.upper()}  _(not yet computed)_")
            lines.append("")
            continue
        lines.append(f"### {model.upper()}")
        lines.append("")
        lines.append("| Feature set | AUROC | AUPRC | Prevalence |")
        lines.append("|-------------|-------|-------|------------|")
        sets = iv.get("sets", {})
        for fset, info in sets.items():
            auroc = _fmt_auroc(info.get("auroc"))
            auprc = _fmt_auroc(info.get("auprc"))
            prev  = _fmt_auroc(info.get("prevalence"))
            lines.append(f"| {fset} | {auroc} | {auprc} | {prev} |")
        lines.append("")
        lines.append("**Incremental value contrasts:**")
        lines.append("")
        lines.append("| Contrast | ΔAUROC | DeLong p | 95% CI |")
        lines.append("|----------|--------|----------|--------|")
        for c in iv.get("incremental_value", []):
            contrast = c.get("contrast", "?")
            delta    = _fmt_delta(c.get("delta_auroc"))
            p        = _fmt_auroc(c.get("delong_p"))
            ci_raw   = c.get("delta_auroc_ci95", [None, None])
            ci_str   = (f"[{_fmt_delta(ci_raw[0])}, {_fmt_delta(ci_raw[1])}]"
                        if ci_raw and len(ci_raw) == 2 else "N/A")
            primary  = " (**primary**)" if c.get("primary") else ""
            lines.append(f"| {contrast}{primary} | {delta} | {p} | {ci_str} |")
        lines.append("")
        nc = iv.get("negative_control", {})
        if nc:
            lines.append(f"_Negative control (shuffled labels): "
                         f"AUROC = {_fmt_auroc(nc.get('auroc_shuffled'))}_")
            lines.append("")

    # ---- Incremental value: per-organ ----
    lines.append("## Incremental Value — Per-Organ Targets")
    lines.append("")
    for model in MODELS:
        lines.append(f"### {model.upper()}")
        lines.append("")
        lines.append("| Target | Standard AUROC | Comprehensive AUROC | PK AUROC | ΔAUROC (PK vs Comp) |")
        lines.append("|--------|---------------|---------------------|----------|---------------------|")
        for target in ORGAN_TARGETS:
            iv = _load_json_safe(os.path.join(cache_dir, f"incremental_value_{target}_{model}.json"))
            if iv is None:
                lines.append(f"| {target} | N/A | N/A | N/A | N/A |")
                continue
            sets = iv.get("sets", {})
            std  = _fmt_auroc(sets.get("standard",  {}).get("auroc"))
            comp = _fmt_auroc(sets.get("comprehensive", {}).get("auroc"))
            pk   = _fmt_auroc(sets.get("pk", {}).get("auroc"))
            # Find PK-vs-comprehensive delta
            delta_pk = "N/A"
            for c in iv.get("incremental_value", []):
                if "pk" in c.get("contrast", "") and "comprehensive" in c.get("contrast", ""):
                    delta_pk = _fmt_delta(c.get("delta_auroc"))
                    break
            lines.append(f"| {target} | {std} | {comp} | {pk} | {delta_pk} |")
        lines.append("")

    # ---- Multitask ----
    mt = _load_json_safe(os.path.join(cache_dir, "multitask_results.json"))
    if mt:
        lines.append("## Multi-task vs Single-task (§9 Tier-2)")
        lines.append("")
        lines.append(f"Feature set: {mt.get('fset','?')}  |  "
                     f"CV folds: {mt.get('n_splits','?')}  |  "
                     f"Seed: {mt.get('seed','?')}")
        lines.append("")
        lines.append("| Organ | N events | Single-task AUROC | Multi-task AUROC | Δ |")
        lines.append("|-------|----------|-------------------|-----------------|---|")
        for row in mt.get("table", []):
            organ  = row.get("organ", "?")
            n_ev   = row.get("n_events", "?")
            s_auc  = _fmt_auroc(row.get("auroc_single"))
            m_auc  = _fmt_auroc(row.get("auroc_multi"))
            delta  = _fmt_delta(row.get("delta"))
            lines.append(f"| {organ} | {n_ev} | {s_auc} | {m_auc} | {delta} |")
        lines.append("")
    else:
        lines.append("## Multi-task vs Single-task")
        lines.append("")
        lines.append("_(not yet computed)_")
        lines.append("")

    # ---- Hypotension ----
    ht = _load_json_safe(os.path.join(cache_dir, "hypotension_treatment_results.json"))
    if ht:
        lines.append("## Hypotension Treatment Modifiable-Risk Analysis")
        lines.append("")
        or_res = ht.get("iptw_or", {})
        lines.append(
            f"N = {ht.get('n_total','?')}  |  "
            f"Treated = {ht.get('n_treated','?')}  |  "
            f"Events = {ht.get('n_events','?')}"
        )
        lines.append("")
        lines.append(
            f"IPTW-adjusted OR = **{or_res.get('OR','?')}** "
            f"(95% CI [{or_res.get('CI_lower','?')}, {or_res.get('CI_upper','?')}])"
        )
        bal = ht.get("balance", {})
        lines.append(
            f"Max SMD before weighting: {bal.get('max_smd_pre','?')}  |  "
            f"after: {bal.get('max_smd_post','?')}"
        )
        lines.append("")
        lines.append(f"_{ht.get('interpretation','')}_")
        lines.append("")
    else:
        lines.append("## Hypotension Treatment Analysis")
        lines.append("")
        lines.append("_(not yet computed)_")
        lines.append("")

    # ---- AKI trajectory ----
    traj = _load_json_safe(os.path.join(cache_dir, "aki_trajectory_summary.json"))
    if traj:
        lines.append("## AKI Trajectory (supplementary)")
        lines.append("")
        lines.append(
            f"AKI+ N = {traj.get('n_aki_positive','?')}  |  "
            f"Transient = {traj.get('transient','?')}  |  "
            f"Persistent = {traj.get('persistent','?')}  |  "
            f"Indeterminate = {traj.get('indeterminate','?')}"
        )
        lines.append("")

    # ---- Deep feasibility ----
    deep_done = os.path.join(cache_dir, "_deep_done.txt")
    if os.path.exists(deep_done):
        lines.append("## Deep Waveform Feasibility (supplementary)")
        lines.append("")
        try:
            with open(deep_done) as fh:
                lines.append(fh.read().strip())
        except OSError:
            lines.append("_(deep feasibility run completed; see _deep_done.txt)_")
        lines.append("")

    # ---- Run status ----
    lines.append("## Pipeline Run Status")
    lines.append("")
    lines.append("| Step | Status |")
    lines.append("|------|--------|")
    for step in STEPS:
        st = status.get(step, "pending")
        lines.append(f"| {step} | {st} |")
    lines.append("")

    # Write RESULTS.md
    results_dir = os.path.join(_HERE, "docs")
    os.makedirs(results_dir, exist_ok=True)
    results_path = os.path.join(results_dir, "RESULTS.md")
    with open(results_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("Step consolidate: DONE  -> %s", results_path)
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idempotent VitalDB study runner.  Skips completed steps."
    )
    parser.add_argument(
        "--force", metavar="STEP", default=None,
        help=(
            "Force re-run a step: cohort_composite|matrix|harness|multitask|"
            "hypotension|consolidate|all"
        ),
    )
    parser.add_argument(
        "--workers", type=int, default=12,
        help="Parallel workers for feature extraction (default: 12)",
    )
    args = parser.parse_args(argv)
    force_step: str | None = args.force

    cfg = _load_cfg()
    cache_dir = cfg["data"]["cache_dir"]
    os.makedirs(cache_dir, exist_ok=True)

    logger = _setup_logging(cache_dir)
    logger.info("=" * 60)
    logger.info("run_all.py starting  (pid=%d  force=%s  workers=%d)",
                os.getpid(), force_step, args.workers)

    if not _acquire_lock(cache_dir, logger):
        return 1

    status = _load_status(cache_dir)

    def _should_force(step: str) -> bool:
        return force_step is not None and (force_step == "all" or force_step == step)

    try:
        # Step 0: INSPIRE auto-fetch (non-fatal)
        ok = step_inspire_autofetch(cfg, cache_dir, logger)
        status["inspire_autofetch"] = "done" if ok else "error"
        _save_status(cache_dir, status)

        # Step 1: cohort
        ok = step_cohort(cfg, cache_dir, logger, force=_should_force("cohort_composite"))
        status["cohort_composite"] = "done" if ok else "failed"
        _save_status(cache_dir, status)
        if not ok:
            logger.error("Cohort step failed -- cannot continue.")
            return 2

        # Step 2: matrix
        ok = step_matrix(cfg, cache_dir, logger, force=_should_force("matrix"),
                         workers=args.workers)
        status["matrix"] = "done" if ok else "failed"
        _save_status(cache_dir, status)
        if not ok:
            logger.error("Matrix step failed -- cannot run modeling steps.")
            # Still try consolidate so RESULTS.md reflects what we have.

        # Step 3: harness
        ok = step_harness(cfg, cache_dir, logger, force=_should_force("harness"))
        status["harness"] = "done" if ok else "partial"
        _save_status(cache_dir, status)

        # Step 4: multitask
        ok = step_multitask(cfg, cache_dir, logger, force=_should_force("multitask"))
        status["multitask"] = "done" if ok else "failed"
        _save_status(cache_dir, status)

        # Step 5: hypotension
        ok = step_hypotension(cfg, cache_dir, logger, force=_should_force("hypotension"))
        status["hypotension"] = "done" if ok else "failed"
        _save_status(cache_dir, status)

        # Step 6: consolidate (always)
        ok = step_consolidate(cfg, cache_dir, logger, status)
        status["consolidate"] = "done" if ok else "failed"
        _save_status(cache_dir, status)

        logger.info("run_all.py complete.  Status: %s", status)
        return 0

    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130
    except Exception:
        logger.error("Unexpected error:\n%s", traceback.format_exc())
        return 3
    finally:
        _release_lock(cache_dir)


if __name__ == "__main__":
    sys.exit(main())
