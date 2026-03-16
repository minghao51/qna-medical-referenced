# Manual Scripts

This folder is for one-off verification helpers that are useful during development but are not part of the automated test suite.

- `verify_tracing_improvements.py` checks tracing metadata propagation against local indexed data and a live chat path.

If a script becomes part of the regular workflow, promote it into `tests/` or a supported CLI command.
