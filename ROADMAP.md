# Roadmap

## Shipped in 1.5.0
- `reproguard explain <issue-id>` command (with `--list`).
- `--version` flag and programmatic `reproguard.__version__`.
- `--sarif` output for GitHub Code Scanning and SARIF-aware tools.
- `docs/INTEGRATIONS.md` with snippets for GitHub Actions, GitLab CI, CircleCI, Buildkite, Jenkins, pre-commit, and Docker.

## Shipped in 1.4.0
- `reproguard init` zero-config onboarding (auto-detects project type, runtime, lockfiles, env vars).
- Official GitHub Action with `auto-init` and `score`/`replay-status`/`exit-code` outputs.
- Pre-commit hook definitions (`.pre-commit-hooks.yaml`).
- README rewrite with story-hook + comparison table.

## Shipped in 1.3.0
- Rust/Go/Ruby project type detection and default lockfile inference.
- Multi-language env-usage and non-determinism scanning (`.rs`, `.go`, `.rb`).
- Zero-test detection for `go test`, `cargo test`, `rspec`, `phpunit`.
- TypeScript/JSX test file recognition for non-determinism scans.
- Runtime drift alias mapping (`runtime.rust` → `rustc`, etc.).
- `issue_totals` in the Markdown report summary.

## v1.6
- `--phase` execution mode (`baseline`, `contract`, `replay`, `report`).
- Flaky-test confidence scoring (per-run variance metrics).
- Optional isolated environment replay profile (temp virtualenv / npm cache isolation).

## v2.0
- Multi-language plugin architecture for framework-specific checks.
- Policy packs (startup / enterprise / regulated environments).
- Historical trend mode for reproducibility regressions across commits.
