# Changelog

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
