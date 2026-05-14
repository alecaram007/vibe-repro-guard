# Contributing to Vibe Repro Guard

Thanks for helping improve reproducible AI coding workflows.

## Development Setup
1. Fork the repo.
2. Create a feature branch from `main`.
3. Run tests:
   ```bash
   python3 -m unittest discover -s tests -p "test_*.py" -v
   ```

## Contribution Rules
- Keep changes focused and small.
- Add or update tests for behavior changes.
- Preserve no-dependency policy for core runtime (`reproguard.py` uses stdlib only).
- Do not commit generated artifacts (`reproguard.report.*`).

## Pull Requests
- Use a clear title and short problem statement.
- Describe expected behavior before/after.
- Include command output for test runs.
- Link issue if available.

## Good First Issues
- Add framework-specific lockfile heuristics.
- Improve deterministic checks for flaky integration tests.
- Extend docs with real-world replay examples.
