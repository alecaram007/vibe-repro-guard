# ReproGuard Examples

Copy-paste fixtures for every supported project type. Each one is a complete, runnable minimal project with its own `reproguard.yaml` and a known-good replay outcome — designed so you can verify reproguard works in your environment in under a minute.

| Fixture | Toolchain required | Test runner |
| --- | --- | --- |
| [node-basic](./node-basic) | Node | `node` |
| [python-basic](./python-basic) | Python 3.10+ (stdlib only) | `unittest` |
| [rust-basic](./rust-basic) | Rust 1.78+ | `cargo test` |
| [go-basic](./go-basic) | Go 1.22+ | `go test` |
| [ruby-basic](./ruby-basic) | Ruby 3.x | `minitest` |

## Run any fixture

From repo root:

```bash
python3 reproguard.py --project-root examples/<fixture-name>
```

Or `cd` into the fixture and run `reproguard` if you've `pip install`-ed it.

## What "expected outcome" means

Each fixture is tuned so a fresh `reproguard` run produces:
- `replay=passed`
- Two deterministic test runs with identical output hashes
- A score of `100` when your local runtime matches the pinned version

If you see a `runtime_drift_*` issue, that's correct behavior — bump the `runtime.<lang>` field in the fixture's `reproguard.yaml` to your local version and re-run.

## Use these as templates

The fastest path to onboarding reproguard into your own project:

1. Copy the matching fixture into your repo as a reference.
2. From your project root, run `reproguard init` to auto-generate `reproguard.yaml`.
3. Compare the generated config with the fixture's; tweak as needed.
4. Commit `reproguard.yaml` and wire the [GitHub Action](../action.yml) into CI.
