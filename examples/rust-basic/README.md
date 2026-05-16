# Rust Basic Fixture

Minimal Rust library fixture for ReproGuard. Requires a local Rust toolchain.

## Run from repo root

```bash
python3 reproguard.py --project-root examples/rust-basic
```

## Expected outcome

- `replay=passed` when Rust toolchain matches `runtime.rust` in `reproguard.yaml`.
- `cargo test` runs two deterministic tests.
- Lockfile policy passes (`Cargo.lock` is committed).

## Notes

- Update `runtime.rust` to your target rustc version for strict pinning.
- For real projects, regenerate `Cargo.lock` with `cargo update` before committing.
