"""Shared, dependency-light utilities for the HEEDB phenotype pipeline.

Everything in this package is importable with the Python standard library only,
so the integrity-critical machinery (hashing, config, firewall guard, run-once
locks, audit logging) can be exercised in CI without the heavy ML stack.
"""
