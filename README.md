# Vibe Repro Guard

Deterministic replay guardrail for AI-assisted coding projects.

[![CI](https://github.com/alecaram007/vibe-repro-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/alecaram007/vibe-repro-guard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

## Why this exists
AI can generate working code quickly, but reproducibility is often fragile.
Vibe Repro Guard turns each coding task into:

`produce -> deterministic replay proof -> reproducibility score -> prioritized fixes`

## Core capabilities
- Baseline fingerprint (platform, toolchain, git state).
- Repro contract generation from `reproguard.yaml`.
- Fresh-workspace replay for build and test commands.
- Multi-run determinism checks (`replay_runs`) for exit and output stability.
- Zero-test execution detection to prevent false replay passes.
- Hidden environment dependency detection.
- Lockfile drift detection (created/changed/deleted during replay).
- Secret redaction in stored logs (`[REDACTED]`).
- Machine-readable and human-readable artifacts.

## Quick Start
```bash
cp reproguard.yaml.example reproguard.yaml
./reproguard.sh
echo $?
```

## Configuration
`reproguard.yaml` example:

```yaml
mode: advisory # advisory | strict
score_threshold: 85 # 0..100
replay_runs: 3 # 2..10
fail_on_lockfile_drift: true
require_declared_env_values: true
build_command: "python3 -m compileall ."
test_command: "python3 -m unittest discover -s tests -p 'test_*.py'"
required_env:
  - API_TOKEN
redact_env_patterns:
  - TOKEN
  - SECRET
  - PASSWORD
runtime:
  python: "3.12.3"
  node: "20.12.2"
lockfiles:
  - requirements.txt
  - package-lock.json
```

## CLI
```bash
python3 reproguard.py --project-root . --config reproguard.yaml
python3 reproguard.py --output-dir ./artifacts --summary-json
```

## Artifacts
- `reproguard.contract.json`
- `reproguard.report.json`
- `reproguard.report.md`

## Exit Codes
- `0`: replay passed and policy satisfied
- `20`: replay failed
- `30`: strict policy failed (`score < threshold`)
- `40`: invalid configuration

## Local Dev
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

## Contributing
- Read [CONTRIBUTING.md](./CONTRIBUTING.md)
- Report bugs with [Bug Report](./.github/ISSUE_TEMPLATE/bug_report.md)
- Propose features with [Feature Request](./.github/ISSUE_TEMPLATE/feature_request.md)

## Growth
- Launch strategy: [docs/LAUNCH_PLAYBOOK.md](./docs/LAUNCH_PLAYBOOK.md)
