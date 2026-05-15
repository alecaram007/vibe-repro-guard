# Changelog

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
