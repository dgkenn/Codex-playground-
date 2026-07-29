# BSDE — Brain-State Discovery Engine

*Working name. Not a brand; any real name needs a trademark search the investigator commissions.*

## What this is

An engine that takes a **candidate brain-state measure** and tries to kill it.

A candidate is any function `(data, ch_names, sfreq, meta) -> scalar | vector`, registered together with a
declared physiological interpretation, a predicted direction, and the conditions under which it should be
considered refuted. The engine runs it through a layered verifier and emits a standardized
**SURVIVE / REVISE / REJECT** report.

**The verifier is built before the search.** The analogy driving this project is AI mathematics, which
succeeded by pairing massive parallel exploration with a *hard* verifier (a proof checker). EEG has no proof
checker. Building one is the asset. Generating features at scale before the verifier is trusted would be
industrialised p-hacking with a research vocabulary, and it is explicitly deferred.

**A verifier that never rejects is worthless.** The engine's primary acceptance test is therefore not that it
confirms a known-good measure but that **planted confounds are rejected with the correct reason** — see
`tests/test_verifier_rejects_planted_confounds.py`.

## Positioning

* **Anesthesia / perioperative EEG is the first application.** Domain credibility, prospective access,
  drug and infusion data, an existing comparator (BIS/PSI), and a controllable perturbation.
* **Covert consciousness is the scientific flagship, not the commercial wedge.** It is where the science is
  most important and where a false positive is most dangerous.
* **"Universal Consciousness Equation" is not the product.** UCE v1 survives here as *one frozen candidate
  biomarker* and a historical hypothesis — `src/bsde/candidates/uce_v1.py`, registered like any other
  candidate and held to the same bar.

## What is real here right now

| component | status |
|---|---|
| Investigator brief, saved verbatim and immutable | done — `docs/RESEARCH_PROGRAM_BRIEF.md` |
| Research strategy (Artifact 1), literature map (2), dataset registry (3), analysis plan (4) | done |
| Synthetic EEG with a known aperiodic exponent | done, tested |
| Aperiodic exponent/offset estimator | done, **validated against known ground truth** |
| Frozen UCE v1 + its mandatory one-feature baseline | done, tested |
| **E01 on 96 real recordings** | **done — UCE v1's two-region structure is redundant** |
| Candidate registry | done — `src/bsde/candidates/registry.py` |
| Verifier layers 1–4 | in progress |
| Streaming data layer | in progress |

### E01, the first real result

r(frontal exponent, posterior exponent) = **0.9326** on 96 recordings, implying PC1 variance-explained of
**96.6 %** against the 96.8 % reported in the brief's derivation, and **corr(UCE v1, z(mean exponent across
channels)) = 0.9952**. The frontal/posterior weighting carries essentially no information. This is the kind of
finding the engine must produce automatically rather than by hand.

## Non-negotiables

* Arousal, responsiveness, cognition, command-following, prognosis and injury severity are **never synonyms**.
* UCE v1 is frozen. Changes are new versions in new modules, evaluated independently. The hypothesis is never
  rewritten after seeing a test result.
* A failed active task is **indeterminate**, never "not conscious". The system must be permitted to abstain.
* **"Nothing survived" is a valid and reportable outcome.**
* No result is reported from a dataset whose licence and access terms are unverified.
* No protected patient data in this repository.

## Layout

```
docs/           RESEARCH_PROGRAM_BRIEF.md (immutable) | RESEARCH_STRATEGY.md | LITERATURE_MAP.md
                ANALYSIS_PLAN.md
data_registry/  DATASET_REGISTRY.csv | LICENSE_TABLE.csv
governance/     INVENTION_NOTEBOOK.md | SEARCH_LOG.jsonl
src/bsde/
  candidates/   registry.py (declaration format) | uce_v1.py (frozen) | spectral.py | complexity.py
  features/     aperiodic.py
  ingestion/    streaming adapters -- raw EEG never hits disk
  verifier/     layers 1-4 and the report
  experiments/  e01_frontal_posterior_redundancy.py
tests/          synthetic ground-truth tests + planted-confound acceptance tests
```

Run the suite: `cd bsde && python -m pytest tests/ -q`
