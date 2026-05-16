# Python Basic Fixture

Minimal Python fixture for ReproGuard. Uses stdlib `unittest` so it runs on any Python 3.10+ without dependencies.

## Run from repo root

```bash
python3 reproguard.py --project-root examples/python-basic
```

## Expected outcome

- `replay=passed`, exit code `0` (adjust `runtime.python` in `reproguard.yaml` if your local Python differs).
- Two deterministic replay runs with identical output hashes.

## Notes

- Update `runtime.python` to your target version for strict pinning.
- Swap the test command in `reproguard.yaml` for `pytest`, `nox`, or your real suite when wiring this into a real project.
