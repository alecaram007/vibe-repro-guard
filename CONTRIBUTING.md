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

## Release process
1. Update `CHANGELOG.md` with a new `## X.Y.Z - YYYY-MM-DD` section.
2. Bump `version` in `pyproject.toml` and the docstring + `__version__` in `reproguard.py` to match.
3. Commit, push, tag with `vX.Y.Z`, push tag.
4. The release workflow will:
   - build a wheel + sdist,
   - verify the tag matches `pyproject.toml`,
   - create a GitHub Release with changelog notes for that version and the built artifacts attached.

## Distribution
Distribution is intentionally **git-only**. There is no PyPI package; users install with:

```bash
pip install git+https://github.com/alecaram007/vibe-repro-guard.git
# or
git clone https://github.com/alecaram007/vibe-repro-guard.git
```

Wheels and sdists are still built on every tagged release and attached to the GitHub Release for users who want to pin to a specific artifact hash.
