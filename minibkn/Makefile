.PHONY: test test-cover test-integration test-at test-performance lint ci

PYTHON ?= python

test:
	$(PYTHON) -m pytest tests/unit -q

test-cover:
	mkdir -p test-result
	$(PYTHON) -m pytest tests/unit -q --cov=src/minibkn \
		--cov-report=term --cov-report=xml:test-result/coverage.xml \
		--cov-report=html:test-result/coverage-html

test-integration:
	$(PYTHON) -m pytest tests/integration -q

test-at:
	mkdir -p test-result
	$(PYTHON) -m pytest tests/integration -q --junitxml=test-result/junit.xml

test-performance:
	$(PYTHON) scripts/evaluate_performance.py --help

lint:
	$(PYTHON) -m ruff format --check src tests scripts
	$(PYTHON) -m ruff check src tests scripts
	$(PYTHON) -m mypy src/minibkn

ci: lint test-cover
