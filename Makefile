# Convenience targets for the HEEDB EEG phenotype-discovery pipeline.
# The integrity core needs only the stdlib; everything else needs the sci stack.

PY ?= python3

.PHONY: help test test-integrity test-all demo validate install clean

help:
	@echo "make test-integrity  - stdlib-only firewall/hashing/guard tests (fast)"
	@echo "make test            - full test suite (needs numpy/sklearn/statsmodels)"
	@echo "make demo            - run the whole synthetic lifecycle end-to-end"
	@echo "make validate        - validate config.yaml against binding invariants"
	@echo "make install         - pip install -r requirements.txt"

test-integrity:
	$(PY) -m unittest tests.test_integrity -v

test test-all:
	$(PY) -m unittest discover -s tests -p 'test_*.py' -v

demo:
	$(PY) cli.py demo

validate:
	$(PY) cli.py validate

install:
	$(PY) -m pip install -r requirements.txt

clean:
	rm -rf artifacts/embeddings artifacts/features artifacts/qc \
	       artifacts/phase2 artifacts/logs artifacts/pass1_done.txt \
	       artifacts/phase1_report.json
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
