"""Verifier layer 2's named gap: correcting for the size of the search space, not merely reporting it.

WHY THIS EXISTS. The programme's constraints require reporting how many candidates were searched, and
`search_space_size()` is printed at the top of every experiment. **Reporting a number and correcting for it
are different things**, and §9.22 recorded the second half as missing: "`search_space_size` is reported
everywhere but nothing corrects for it." An experiment that scores 18 candidates and reports the best one's
interval has done 18 tests and priced one.

WHY NOT BONFERRONI, AND THIS IS THE WHOLE DESIGN DECISION. These candidates are not independent tests. E01
measured `uce_v1` against `whole_head_exponent` at a rank correlation of **0.9952** on real EEG; E13's
redundancy work found more of the same; several are explicitly registered with "is redundant with X" as a
failure condition. Dividing alpha by 18 would price 18 independent looks that were never taken, and the
resulting threshold would reject real effects to guard against a multiplicity that does not exist at that
size. **The effective number of independent tests is a property of the data and should be measured, not
assumed.**

WHAT IS IMPLEMENTED. Three procedures, each with a different contract, so a caller states which guarantee
they want rather than getting whichever one was convenient:

  `holm`                   controls the family-wise error rate under ANY dependence. The safe default when
                           no null distribution is available. Conservative here, deliberately.
  `benjamini_hochberg`     controls the false discovery rate under independence or positive dependence.
                           The right tool when the question is "which of these are worth following up".
  `westfall_young_maxt`    controls the FWER while USING the observed correlation between candidates,
                           via the permutation distribution of the maximum statistic. Needs a null matrix
                           — one row per permutation, one column per candidate, all candidates permuted
                           TOGETHER under the same relabelling, which is what carries the correlation.

**The together-ness is the load-bearing detail.** If each candidate is permuted under its own independent
relabelling, the columns of the null matrix become independent and the procedure silently degenerates to
something close to Bonferroni — the correlation it exists to exploit is destroyed by the sampling. A caller
that builds the null matrix wrongly gets a valid-looking answer that is simply the conservative one, which
is the failure mode this docstring exists to prevent. `effective_tests` is reported alongside so the
degeneration is visible: if it comes back equal to the number of candidates, the null was built wrong or the
candidates really are independent, and either way the caller should know which.

WHAT THIS DOES NOT DO. It does not decide what counts as a family. That is a judgement about the experiment
— all candidates in one report, or only the ones sharing a contrast — and hiding it inside a function would
make an important choice invisible. The caller passes the family.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np


def holm(pvalues: Sequence[float], names: Optional[Sequence[str]] = None) -> Dict[str, float]:
    """Holm-Bonferroni step-down adjusted p-values. Controls FWER under arbitrary dependence.

    Adjusted values are enforced monotone non-decreasing in the sorted order, which is what makes the
    step-down valid: without that a later, larger raw p could receive a smaller adjusted p.
    """
    p = np.asarray(list(pvalues), float)
    n = p.size
    if n == 0:
        return {}
    names = list(names) if names is not None else [str(i) for i in range(n)]
    order = np.argsort(p)
    adj = np.empty(n, float)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (n - rank) * p[i])
        adj[i] = min(1.0, running)
    return {names[i]: float(adj[i]) for i in range(n)}


def benjamini_hochberg(pvalues: Sequence[float],
                       names: Optional[Sequence[str]] = None) -> Dict[str, float]:
    """Benjamini-Hochberg adjusted p-values (q-values). Controls FDR under independence or positive
    dependence — which is the relevant case here, since redundant candidates are positively correlated.

    Enforced monotone non-increasing from the largest p downward, the standard step-up form.
    """
    p = np.asarray(list(pvalues), float)
    n = p.size
    if n == 0:
        return {}
    names = list(names) if names is not None else [str(i) for i in range(n)]
    order = np.argsort(p)[::-1]                      # largest first
    adj = np.empty(n, float)
    running = 1.0
    for rank, i in enumerate(order):
        k = n - rank                                 # 1-based rank of this p in ascending order
        running = min(running, p[i] * n / k)
        adj[i] = min(1.0, running)
    return {names[i]: float(adj[i]) for i in range(n)}


def westfall_young_maxt(observed: Sequence[float], null_matrix: np.ndarray,
                        names: Optional[Sequence[str]] = None,
                        larger_is_stronger: bool = True) -> Dict[str, object]:
    """Step-down max-T adjusted p-values, using the correlation the permutations actually carry.

    `null_matrix` is (n_permutations, n_candidates) and **every row must come from ONE relabelling applied
    to ALL candidates** — see the module docstring for why that is the whole point.

    `observed` is the same statistic per candidate. `larger_is_stronger=True` means a bigger value is more
    evidence, which for a discrimination statistic means the caller should pass |AUC - 0.5| rather than AUC,
    so that a candidate firing opposite to its declared direction is not rewarded.

    Returns adjusted p-values, the raw per-candidate permutation p-values, and `effective_tests` — the
    Bonferroni-equivalent number of independent tests implied by the max-statistic distribution. That last
    number is what makes the correlation visible: 18 correlated candidates that behave like 4 independent
    ones will report about 4.
    """
    obs = np.asarray(list(observed), float)
    null = np.asarray(null_matrix, float)
    if null.ndim != 2 or null.shape[1] != obs.size:
        raise ValueError(f"null_matrix must be (n_perm, {obs.size}); got {null.shape}")
    n = obs.size
    names = list(names) if names is not None else [str(i) for i in range(n)]
    if not larger_is_stronger:
        obs, null = -obs, -null
    n_perm = null.shape[0]

    raw = np.array([(1.0 + np.sum(null[:, j] >= obs[j])) / (1.0 + n_perm) for j in range(n)])

    # Step-down: candidates from strongest to weakest, each compared against the max over the candidates
    # not yet rejected. Enforced monotone, as Holm is, and for the same reason.
    order = np.argsort(-obs)
    adj = np.empty(n, float)
    running = 0.0
    for rank, j in enumerate(order):
        remaining = order[rank:]
        m = null[:, remaining].max(axis=1)
        p = (1.0 + np.sum(m >= obs[j])) / (1.0 + n_perm)
        running = max(running, p)
        adj[j] = min(1.0, running)

    # Bonferroni-equivalent count: the alpha that the max-statistic distribution assigns at the 5 % point,
    # against the per-test alpha that would produce it. Reported, never used to adjust anything.
    max_null = null.max(axis=1)
    q95_max = float(np.quantile(max_null, 0.95))
    per_test_tail = np.mean([np.mean(null[:, j] >= q95_max) for j in range(n)])
    eff = float(0.05 / per_test_tail) if per_test_tail > 0 else float(n)

    return {"adjusted": {names[j]: float(adj[j]) for j in range(n)},
            "raw": {names[j]: float(raw[j]) for j in range(n)},
            "effective_tests": min(float(n), max(1.0, eff)),
            "n_candidates": int(n), "n_permutations": int(n_perm)}


def report(observed: Dict[str, float], null_matrix: Optional[np.ndarray] = None,
           pvalues: Optional[Dict[str, float]] = None, alpha: float = 0.05) -> List[str]:
    """A printable block. Names the guarantee for each column rather than presenting one adjusted number.

    Prints the search-space size first, because that is the fact the constraint asks for, and the
    corrections second, because they are what it is for.
    """
    names = list(observed)
    lines = [f"MULTIPLICITY — {len(names)} candidates in this family, alpha = {alpha}"]
    if pvalues is None and null_matrix is None:
        lines.append("   no p-values and no null matrix supplied — NOTHING is corrected, and this line is")
        lines.append("   here so that absence is visible rather than inferred from a missing section.")
        return lines
    if pvalues is not None:
        p = [pvalues[k] for k in names]
        h, b = holm(p, names), benjamini_hochberg(p, names)
        lines.append(f"   {'candidate':26s} {'raw p':>9s} {'Holm (FWER)':>13s} {'BH (FDR)':>10s}")
        for k in sorted(names, key=lambda z: pvalues[z]):
            lines.append(f"   {k:26s} {pvalues[k]:9.4f} {h[k]:13.4f} {b[k]:10.4f}")
    if null_matrix is not None:
        wy = westfall_young_maxt([observed[k] for k in names], null_matrix, names)
        lines.append(f"   Westfall-Young max-T, which uses the observed correlation between candidates:")
        lines.append(f"   {'candidate':26s} {'raw p':>9s} {'WY adjusted':>13s}")
        for k in sorted(names, key=lambda z: wy["adjusted"][z]):
            lines.append(f"   {k:26s} {wy['raw'][k]:9.4f} {wy['adjusted'][k]:13.4f}")
        lines.append(f"   effective independent tests: {wy['effective_tests']:.1f} of "
                     f"{wy['n_candidates']} candidates")
        lines.append("   (a value close to the candidate count means either the candidates really are")
        lines.append("    independent or the null matrix was built with per-candidate relabellings, which")
        lines.append("    destroys the correlation this procedure exists to use)")
    return lines
