# Vibe Repro Guard

**Catch "works on my laptop" before it hits production.**
A deterministic replay guardrail for AI-generated code — finds flaky tests, lockfile drift, and hidden env dependencies in one command.

[![CI](https://github.com/alecaram007/vibe-repro-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/alecaram007/vibe-repro-guard/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/vibe-repro-guard.svg)](https://pypi.org/project/vibe-repro-guard/)
[![Downloads](https://img.shields.io/pypi/dm/vibe-repro-guard.svg)](https://pypi.org/project/vibe-repro-guard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/deps-stdlib%20only-blueviolet)](./pyproject.toml)

## The 60-second pitch

You paste AI-generated code. Tests pass. You push.

Then one of these things happens:
- CI fails because the AI used `time.time()` in a test.
- A teammate's machine breaks because of an undeclared env var.
- A lockfile silently drifted and `npm install` produces different output than yesterday.
- Tests pass once but fail when run twice (state pollution).

ReproGuard runs your build & test commands **multiple times in a fresh tmp workspace**, hashes the output, snapshots lockfiles before/after, and gives you a single number: a **reproducibility score 0-100**.

## 30-second start (zero config)

```bash
pip install vibe-repro-guard
cd your-project
reproguard init        # auto-detects language, runtime, lockfiles, env vars
reproguard             # runs the guard
```

Output:
```
[reproguard] score=92 mode=advisory threshold=85 replay=passed exit_code=0
[reproguard] artifacts: reproguard.contract.json, reproguard.report.json, reproguard.report.md
```

`reproguard init` works on Python, Node, Rust, Go, Ruby, PHP — no manual YAML required.

## How it compares

| Capability | `pytest --count` | `act` (GH Actions local) | Docker | ReproGuard |
| --- | --- | --- | --- | --- |
| Multi-run determinism check | yes | no | no | yes |
| Fresh-workspace isolation | no | partial | yes | yes |
| Lockfile drift detection | no | no | no | yes |
| Hidden env dependency detection | no | no | no | yes |
| Runtime version drift | no | no | no | yes |
| Static non-determinism scan | no | no | no | yes |
| Zero-test execution detection | no | no | no | yes |
| Score + machine-readable report | no | no | no | yes |
| Zero dependencies / one file | no | no | no | yes |

## Use cases

- **Pre-PR check** in vibe-coding workflows (Cursor / Claude Code / Copilot CLI).
- **CI gate** in advisory mode (score in PR comment) or strict mode (block merge).
- **Pre-release** before tagging — proves the release branch replays cleanly.
- **Triaging "flaky tests"** — gets you concrete evidence of which signal is non-deterministic.

## Use it in CI (GitHub Action)

```yaml
- uses: alecaram007/vibe-repro-guard@v1
  with:
    project-root: .
    auto-init: true          # generates config on first run
```

The action exposes `score`, `replay-status`, and `exit-code` outputs you can branch on.

## Use it as a pre-commit hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/alecaram007/vibe-repro-guard
    rev: v1.4.0
    hooks:
      - id: reproguard
        stages: [pre-push]
```

## Supported project types

Auto-detected from manifest files; lockfile policy is inferred when not declared explicitly:

| Language | Manifest | Default lockfile(s) | Test command default |
| --- | --- | --- | --- |
| Python | `pyproject.toml`, `requirements.txt`, `setup.py` | `requirements.txt`, `poetry.lock`, `Pipfile.lock`, `uv.lock` | `pytest` or `unittest discover` |
| Node | `package.json` | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb` | `npm test` |
| PHP | `composer.json` | `composer.lock` | `vendor/bin/phpunit` |
| Rust | `Cargo.toml` | `Cargo.lock` | `cargo test` |
| Go | `go.mod` | `go.sum` | `go test ./...` |
| Ruby | `Gemfile` | `Gemfile.lock` | `bundle exec rspec` |

## Core capabilities

- **Baseline fingerprint** — platform, toolchain, git state.
- **Repro contract** — generated from `reproguard.yaml` (or `reproguard init`).
- **Fresh-workspace replay** — build & test in a clean tmp copy.
- **Multi-run determinism** — `replay_runs` (2-10) for exit-code and output-hash stability.
- **Zero-test execution detection** — supports unittest, pytest, jest, vitest, mocha, `go test`, `cargo test`, rspec, phpunit.
- **Hidden environment dependency detection** — re-runs tests with a minimized env to catch silent reliance on shell variables.
- **Lockfile drift** — created/changed/deleted during replay.
- **Static non-determinism scan** — flags `Date.now`, `time.Now`, `Math.random`, `rand::*`, `Time.now`, etc. in test files.
- **Secret redaction** — `[REDACTED]` in stored logs based on `redact_env_patterns`.
- **Machine + human readable** — JSON contract, JSON report, Markdown report.

## Configuration

The auto-generated `reproguard.yaml` looks like this:

```yaml
mode: advisory             # advisory | strict
score_threshold: 85        # 0..100, only enforced in strict
replay_runs: 3             # 2..10
fail_on_lockfile_drift: true
require_declared_env_values: true
build_command: "python3 -m compileall ."
test_command: "pytest"
required_env:
  - API_TOKEN
redact_env_patterns:
  - TOKEN
  - SECRET
  - PASSWORD
runtime:
  python: "3.12.3"
lockfiles:
  - requirements.txt
```

## CLI

```bash
reproguard init                              # auto-generate reproguard.yaml
reproguard init --force                      # overwrite existing config
reproguard                                   # run the guard
reproguard --project-root . --output-dir ./artifacts --summary-json
reproguard --sarif                           # also emit SARIF for GitHub Code Scanning
reproguard --phase baseline                  # fingerprint only (fast pre-flight)
reproguard --phase contract                  # baseline + static checks (no replay)
reproguard --version                         # print version and exit
reproguard explain lockfile_drift            # explain what an issue ID means
reproguard explain --list                    # list all known issue IDs
reproguard doctor                            # check the local environment
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0`  | replay passed and policy satisfied |
| `20` | replay failed (test failure, output drift, zero tests, lockfile drift, ...) |
| `30` | strict policy failed (`score < threshold`) |
| `40` | invalid configuration |
| `41` | `init` precondition not met (existing config without `--force`) |
| `42` | `explain` invoked with an unknown issue ID |

## Artifacts

Each run writes three files (default: project root, configurable with `--output-dir`):

- `reproguard.contract.json` — full input snapshot (config, baseline, detected versions, expected lockfiles).
- `reproguard.report.json` — stable schema ([schema](./docs/reproguard.report.schema.json), [docs](./docs/REPORT_SCHEMA.md)).
- `reproguard.report.md` — human-readable summary with score, issue totals, and replay details.

## Local development

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
make smoke    # one-shot self-check on this repo
```

## Examples

Copy-paste fixtures for every supported language ([index](./examples/README.md)):

- [examples/python-basic](./examples/python-basic) — Python (stdlib `unittest`)
- [examples/node-basic](./examples/node-basic) — Node.js
- [examples/rust-basic](./examples/rust-basic) — Rust (`cargo test`)
- [examples/go-basic](./examples/go-basic) — Go (`go test`)
- [examples/ruby-basic](./examples/ruby-basic) — Ruby (`minitest`)

Each fixture is a complete minimal project tuned for a clean `replay=passed` run, so you can verify reproguard works in your environment in under a minute.

## Deeper dives

- [7 reproducibility bugs ReproGuard catches](./docs/STORIES.md) — concrete failure scenarios with exact issue IDs and remediation.
- [CI Integrations](./docs/INTEGRATIONS.md) — copy-paste snippets for GitHub Actions, GitLab CI, CircleCI, Buildkite, Jenkins, pre-commit, Docker.
- [Report schema](./docs/REPORT_SCHEMA.md) — stable JSON contract for CI integrations.
- [Roadmap](./ROADMAP.md) — what's shipped, what's next.

## Contributing

- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [Bug Report](./.github/ISSUE_TEMPLATE/bug_report.md)
- [Feature Request](./.github/ISSUE_TEMPLATE/feature_request.md)

## Growth

- Launch strategy: [docs/LAUNCH_PLAYBOOK.md](./docs/LAUNCH_PLAYBOOK.md)
- Ready-to-post launch drafts (HN, X, LinkedIn, Reddit, awesome-list PRs): [docs/LAUNCH_DRAFTS.md](./docs/LAUNCH_DRAFTS.md)
- Roadmap: [ROADMAP.md](./ROADMAP.md)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=alecaram007/vibe-repro-guard&type=Date)](https://star-history.com/#alecaram007/vibe-repro-guard&Date)

## Author

Built and maintained by **[Alessandro Caramazza](https://alessandrocaramazza.it)** — informatico in Sicilia. Software su misura, automazioni, gestionali e bot per PMI.

- 🌐 [alessandrocaramazza.it](https://alessandrocaramazza.it)
- 💬 [WhatsApp](https://wa.me/393519006821)
- 📧 [alessandro.caramazza@gmail.com](mailto:alessandro.caramazza@gmail.com)

