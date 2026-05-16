# Go Basic Fixture

Minimal Go fixture for ReproGuard. Requires a local Go toolchain.

## Run from repo root

```bash
python3 reproguard.py --project-root examples/go-basic
```

## Expected outcome

- `replay=passed` when local Go matches `runtime.go` in `reproguard.yaml`.
- `go test ./...` runs two deterministic tests.
- Lockfile policy passes (`go.sum` is committed; this fixture has no external deps so it's intentionally empty).

## Notes

- Update `runtime.go` to your target Go version for strict pinning.
- For real projects, run `go mod tidy` before committing.
