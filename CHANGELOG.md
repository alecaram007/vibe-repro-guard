# Changelog

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
