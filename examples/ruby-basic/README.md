# Ruby Basic Fixture

Minimal Ruby fixture for ReproGuard. Requires a local Ruby toolchain (uses stdlib `minitest`, no gems to install).

## Run from repo root

```bash
python3 reproguard.py --project-root examples/ruby-basic
```

## Expected outcome

- `replay=passed` when local Ruby matches `runtime.ruby` in `reproguard.yaml`.
- Two deterministic minitest assertions.
- Lockfile policy passes (`Gemfile.lock` committed, dependency-free).

## Notes

- Update `runtime.ruby` to your target version.
- For real projects with gems, run `bundle install` before committing the lockfile.
