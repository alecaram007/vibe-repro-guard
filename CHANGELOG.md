# Changelog

## 1.4.0 - 2026-05-16
- Added `reproguard init` subcommand that auto-generates `reproguard.yaml` by scanning the project (project type, runtime versions, lockfiles, env-var references). Eliminates the manual-YAML onboarding step.
- Added an official GitHub Action (`action.yml`) with `auto-init` support, `score`/`replay-status`/`exit-code` outputs, and automatic artifact upload.
- Added pre-commit hook definitions (`.pre-commit-hooks.yaml`) so projects can wire reproguard into `pre-commit` for the `pre-push` stage.
- Added exit code `41` for `init` precondition failures (existing config without `--force`, missing project root).
- Rewrote README with a story-hook opening, side-by-side comparison table vs `pytest --count`, `act`, and Docker, plus copy-paste CI/pre-commit snippets.
- Added 4 regression tests for the `init` command (50 tests total).

## 1.3.0 - 2026-05-16
- Added Rust, Go, and Ruby project type detection (`Cargo.toml`, `go.mod`, `Gemfile`).
- Added default lockfile inference for Rust (`Cargo.lock`), Go (`go.sum`), and Ruby (`Gemfile.lock`).
- Extended env-usage scanning to recognise Go (`os.Getenv`), Rust (`env::var` / `std::env::var`), and Ruby (`ENV[...]`, `ENV.fetch(...)`).
- Extended non-determinism scanning for Go (`time.Now`, `math/rand`), Rust (`SystemTime::now`, `rand`), and Ruby (`Time.now`, `SecureRandom`).
- Extended zero-test signal detection to cover `go test` (`no test files`, `no tests to run`), `cargo test` (`running 0 tests`), `rspec` (`0 examples, 0 failures`), and `phpunit` (`No tests executed`).
- Extended `is_test_file` to recognise TypeScript and JSX test suffixes (`.test.ts`, `.spec.ts`, `.test.tsx`, `.spec.tsx`, `.test.mjs`, `.spec.mjs`, `.test.cjs`, `.spec.cjs`) plus `_test.go` and `_spec.rb`.
- Added runtime drift detection for Rust/Go/Ruby/PHP via an alias mapping (e.g. `runtime.rust` → `rustc --version`).
- Added `issue_totals` line to the Markdown report summary so reviewers see severity counts without parsing JSON.
- Fixed `datetime.utcnow()` deprecation warning on Python 3.12+ by switching to timezone-aware UTC.
- Made `make smoke` operate inside a temporary directory so it no longer leaves `reproguard.yaml` or artifacts in the repo root.
- Added 14 regression tests for the new behaviour (46 tests total).

## 1.2.13 - 2026-05-15
- Added a versioned JSON Schema for `reproguard.report.json`.
- Documented report compatibility rules and required machine-readable fields.
- Linked report schema docs from the README artifacts section.
- Added regression coverage to keep report schema docs aligned with emitted reports.

## 1.2.12 - 2026-05-15
- Added a ready-to-run Node.js fixture at `examples/node-basic` for onboarding and reproducibility demos.
- Documented fixture usage in the main README under a new `Examples` section.
- Verified fixture with a real guard execution (`replay=passed`, exit code `0`).

## 1.2.11 - 2026-05-15
- Fixed a zero-test replay gap where valid empty-suite outputs were not recognized in some runners.
- Expanded `test_runs_zero` output detection patterns to cover:
  - `pytest` summaries (`no tests ran`, `no tests collected`)
  - `vitest` empty-suite output (`No test files found`)
  - `mocha` empty-suite output (`0 passing`)
- Added regression coverage for all new zero-test signal patterns.

## 1.2.10 - 2026-05-15
- Fixed a false-positive replay pass when the test command executed zero tests (e.g. `Ran 0 tests`, `collected 0 items`).
- Added a new replay issue: `test_runs_zero` (high severity) that fails replay for empty suites.
- Added regression coverage for end-to-end zero-test detection and pytest-style zero-collection signals.

## 1.2.9 - 2026-05-15
- Fixed env usage scanning to detect syntax variants with whitespace, including:
  - `process.env ['VAR']`
  - `process.env?. [ 'VAR' ]`
  - `os.getenv ('var')`
  - `os.environ [ 'var' ]`
- Added regression coverage for whitespace-based env scanning and `env_not_declared` detection flow.

## 1.2.8 - 2026-05-15
- Fixed env usage scanning to detect lowercase and mixed-case variable names in:
  - `process.env.name`
  - `process.env?.['name']`
  - `os.getenv('name')`
  - `os.environ.get('name')`
  - `os.environ['name']`
- Added regression coverage for lowercase/mixed-case env scanning and `env_not_declared` detection flow.

## 1.2.7 - 2026-05-15
- Fixed env usage scanning to detect JavaScript optional chaining patterns:
  - `process.env?.VAR`
  - `process.env?.["VAR"]`
- Added regression coverage for optional-chaining env detection in both scanner and end-to-end guard flow.

## 1.2.6 - 2026-05-15
- Added PHP project detection via `composer.json` for default lockfile inference.
- Added default lockfile heuristic for PHP projects (`composer.lock`), reducing false-positive `lockfile_not_declared`.
- Added regression coverage for Composer lockfile inferred-present and inferred-missing scenarios.

## 1.2.5 - 2026-05-15
- Fixed false-positive `lockfile_missing` for Python projects that use `uv.lock` as the only lockfile.
- Fixed false-positive `lockfile_missing` for Node projects that use `bun.lockb` as the lockfile.
- Added regression coverage for both default-lockfile inference cases.

## 1.2.4 - 2026-05-15
- Fixed lockfile path validation to reject Windows-style traversal (`..\\...`) and absolute paths (`C:\\...`, UNC `\\\\...`) across platforms.
- Added regression coverage for unsafe Windows-style lockfile path entries.

## 1.2.3 - 2026-05-15
- Fixed env usage scanning to detect `os.environ.get("VAR")` access patterns.
- Added regression coverage for `scan_env_usage` with `os.environ.get(...)`.

## 1.2.2 - 2026-05-14
- Fixed `required_env_missing_values` checks to treat empty environment values as missing.
- Rejected unsafe `lockfiles` entries with absolute paths or `..` traversal in config validation.
- Added regression tests for both cases (`required_env` empty values and lockfile path traversal).

## 1.2.1 - 2026-05-14
- Fixed false-positive `hidden_env_dependency` by running minimal-env replay in a fresh workspace.
- Fixed runtime drift parsing when version output is emitted on `stderr` (legacy Python behavior).
- Added regression tests for both edge cases.

## 1.2.0 - 2026-05-14
- Added `--output-dir` for custom artifact destinations.
- Added `--summary-json` for CI-friendly summary output.
- Added `require_declared_env_values` config and baseline check.
- Added warning when no test command can be resolved.
- Added community and GitHub collaboration assets:
  - CI workflow
  - Issue templates
  - PR template
  - Contributing / Security / Code of Conduct
  - Packaging metadata (`pyproject.toml`)

## 1.1.0 - 2026-05-14
- Multi-run replay checks with deterministic output hashing.
- Lockfile drift detection and optional fail-on-drift policy.
- Secret redaction in report logs.
- Git baseline metadata.

## 1.0.0 - 2026-05-14
- Initial release:
  - Baseline / contract / replay / report workflow
  - Score engine
  - JSON + Markdown artifacts
  - Strict/advisory policy modes
