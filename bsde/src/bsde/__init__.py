"""BSDE — Brain-State Discovery Engine.

An engine that takes a registered candidate brain-state measure and tries to kill it, emitting a standardized
SURVIVE / REVISE / REJECT report. The verifier is built before the search; feature generation at scale is
deferred until the verifier is trusted.

See docs/RESEARCH_PROGRAM_BRIEF.md (immutable investigator brief), docs/RESEARCH_STRATEGY.md, and README.md.
"""
__version__ = "0.1.0"
