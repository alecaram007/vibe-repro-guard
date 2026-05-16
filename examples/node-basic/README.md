# Node Basic Fixture

Minimal Node.js fixture for quick ReproGuard validation.

## Run

From repository root:

```bash
python3 reproguard.py --project-root examples/node-basic
```

Expected outcome:
- Replay runs pass.
- Lockfile policy passes (`package-lock.json`).
- Advisory mode returns exit code `0` even when runtime drift is reported on a different Node version.

## Notes

- Update `runtime.node` in `reproguard.yaml` to your target exact Node version for strict gating.
