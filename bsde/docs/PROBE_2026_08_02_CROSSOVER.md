# Is there a within-patient agent contrast hiding in VitalDB? No.

*Rule-41 feasibility probe, 2026-08-02, run before any registration and reported whatever it found.*

## Why it was worth asking

E220's post-hoc correction established that **the agent main effect is not identifiable** in a cohort where
each patient receives one agent: case-mean centring removes the agent effect along with the between-patient
differences it is confounded with, so only an agent-by-potency interaction is estimable, and that is null.
The design that would identify it is a **crossover** — the same patient under both agents. Kuizenga's
volunteers were exactly that, which is why that paper can state cross-agent potency at all.

Every Challenge A analysis here has used only the **single-agent** cases: 71 sevoflurane, 44 propofol. The
excluded remainder is not small, and it is not obviously useless:

| agent string | cases |
|---|---|
| sevoflurane | 71 |
| **propofol \| sevoflurane** | **58** |
| propofol | 44 |
| desflurane \| propofol | 38 |
| desflurane \| sevoflurane | 19 |
| desflurane | 15 |
| desflurane \| propofol \| sevoflurane | 5 |

A case labelled `propofol|sevoflurane` had both drugs in its record. If some of its windows are dominated by
one agent's potency and others by the other's, that case **is** a within-patient contrast.

## The answer, and it is unambiguous

Using the NSRI potency decomposition — each window's propofol share of total hypnotic potency,
`(Ce_prop/7.58) / (Ce_prop/7.58 + sevo/2.59)` — over the 58 propofol-plus-sevoflurane cases that have PK
tracks, the **within-case span** of that share is:

| quantile of the span | 10th | 25th | 50th | 75th | 90th | max |
|---|---|---|---|---|---|---|
| span (max − min) | 0.000 | 0.000 | **0.000** | 0.000 | 0.397 | 1.000 |

**Three quarters of these cases never change which agent dominates**, on the grid the features are computed
on. Requiring windows on both sides of a dominance threshold gives:

| threshold | cases |
|---|---|
| span ≤ 0.2 to ≥ 0.8 | **3** |
| span ≤ 0.3 to ≥ 0.7 | 4 |
| span ≤ 0.4 to ≥ 0.6 | 5 |

Loosening the threshold does not rescue it. At the strict threshold the within-patient alpha difference is
**+0.0058 [−0.1477, +0.0877]** on three cases, which is no information at all.

## Why the label and the data disagree

The agent string records that both drugs appeared somewhere in the case. The feature grid samples every
300 s from anaesthesia start, and propofol in a volatile case is typically a single induction bolus whose
effect-site concentration has largely decayed before the second or third grid point. So the label reflects
**induction propofol followed by maintenance volatile**, and the grid sees essentially only maintenance.
A denser grid over the first few minutes might recover a handful more cases; it would not change the order
of magnitude, and those windows would be at induction, where depth is changing fastest and least comparable.

## A correction made during the probe

The first pass computed a combined volatile potency using a **desflurane Ce50 of 5.17, which this project
has not verified from a primary source** — exactly the guess `mac_to_vol_pct_sevo` raises rather than make.
The numbers above come from a rerun that **excludes every desflurane case**, so no unverified constant
enters the result.

## Conclusion for the programme

**The within-patient agent contrast is not available in VitalDB and this route is closed.** The identified
Challenge A claim remains the within-case dose-tracking asymmetry; the between-agent claim needs a
crossover deposit, and the earlier deposit search established that no public one exists with both a
documented multi-agent contrast and enough channels.
