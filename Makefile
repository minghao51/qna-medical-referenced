# Thin wrapper around scripts/check_backend.sh; the script is the source of truth.
# Use `make help` (or the script directly) for mode descriptions.

SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help test test-offline unit integration coverage lint smoke frontend-check frontend-test

help:
	@bash scripts/check_backend.sh help

test:
	@bash scripts/check_backend.sh fast

test-offline:
	@bash scripts/check_backend.sh offline

unit:
	@bash scripts/check_backend.sh unit

integration:
	@bash scripts/check_backend.sh integration

coverage:
	@bash scripts/check_backend.sh coverage

lint:
	@bash scripts/check_backend.sh lint

smoke:
	@bash scripts/check_backend.sh smoke

frontend-check:
	@bash scripts/check_backend.sh frontend-check

frontend-test:
	@bash scripts/check_backend.sh frontend-test
