# CI Integrations

Copy-paste snippets for every major CI provider. All examples assume `reproguard.yaml` already exists at the repo root (run `reproguard init` once to generate it).

## GitHub Actions

The recommended path: use the official composite action.

```yaml
name: Reproducibility
on: [pull_request, push]
jobs:
  reproguard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: alecaram007/vibe-repro-guard@v1.5.0
        with:
          auto-init: true       # generate config on first run if missing
          # project-root: '.'
          # python-version: '3.12'
```

Outputs `score`, `replay-status`, `exit-code` for downstream steps:

```yaml
- name: Comment score on PR
  if: always()
  run: |
    echo "ReproGuard score: ${{ steps.repro.outputs.score }}"
```

### Code Scanning (SARIF upload)

```yaml
- name: Reproguard
  run: pip install git+https://github.com/alecaram007/vibe-repro-guard.git && reproguard --sarif --summary-json
- name: Upload SARIF to Code Scanning
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: reproguard.report.sarif.json
    category: reproguard
```

## GitLab CI

```yaml
reproguard:
  image: python:3.12-slim
  script:
    - pip install --quiet git+https://github.com/alecaram007/vibe-repro-guard.git
    - reproguard --summary-json
  artifacts:
    when: always
    paths:
      - reproguard.contract.json
      - reproguard.report.json
      - reproguard.report.md
    reports:
      # GitLab can render a custom report tab if you upload SARIF or convert
      # the JSON via `glab sast` — see GitLab docs for "Custom SAST report".
```

## CircleCI

```yaml
version: 2.1
jobs:
  reproguard:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run:
          name: Run ReproGuard
          command: |
            pip install --quiet git+https://github.com/alecaram007/vibe-repro-guard.git
            reproguard --summary-json
      - store_artifacts:
          path: reproguard.report.json
          destination: reproguard
      - store_artifacts:
          path: reproguard.report.md
          destination: reproguard

workflows:
  reproducibility:
    jobs:
      - reproguard
```

## Buildkite

```yaml
steps:
  - label: ":shield: ReproGuard"
    command: |
      pip install --quiet git+https://github.com/alecaram007/vibe-repro-guard.git
      reproguard --summary-json
    artifact_paths:
      - "reproguard.contract.json"
      - "reproguard.report.json"
      - "reproguard.report.md"
    plugins:
      - docker#v5.10.0:
          image: "python:3.12-slim"
```

## Jenkins (declarative)

```groovy
pipeline {
  agent { docker { image 'python:3.12-slim' } }
  stages {
    stage('ReproGuard') {
      steps {
        sh 'pip install --quiet git+https://github.com/alecaram007/vibe-repro-guard.git'
        sh 'reproguard --summary-json'
      }
      post {
        always {
          archiveArtifacts artifacts: 'reproguard.report.*,reproguard.contract.*', fingerprint: true
        }
      }
    }
  }
}
```

## Pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/alecaram007/vibe-repro-guard
    rev: v1.5.0
    hooks:
      - id: reproguard
        stages: [pre-push]
```

Run on demand:
```bash
pre-commit run --hook-stage pre-push reproguard --all-files
```

## Docker (any provider)

For providers that prefer a single container image:

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir git+https://github.com/alecaram007/vibe-repro-guard.git
WORKDIR /workspace
ENTRYPOINT ["reproguard"]
```

```bash
docker build -t reproguard .
docker run --rm -v "$PWD:/workspace" reproguard
```

## Choosing a mode

| Goal | Recommended mode | Threshold |
| --- | --- | --- |
| Surface reproducibility issues without blocking merges | `advisory` (default) | n/a |
| Block merges below a quality bar | `strict` | `85` |
| Gate release tags only | `strict` + run only on tag CI | `95` |

`strict` mode returns exit `30` when score drops below threshold; `advisory` returns `0`. Replay failures (exit `20`) are fatal in both modes.

## Reading the JSON report in scripts

```bash
SCORE=$(jq '.summary.score' reproguard.report.json)
STATUS=$(jq -r '.summary.replay_status' reproguard.report.json)
echo "$STATUS @ $SCORE"

# Fail the job if any critical issue is present (regardless of mode)
CRITICAL=$(jq '.summary.issue_totals.critical' reproguard.report.json)
if [ "$CRITICAL" -gt 0 ]; then
  exit 1
fi
```

## Looking up an unknown issue ID

In any CI log, if reproguard surfaces an issue ID you don't recognise:

```bash
reproguard explain <issue_id>
# e.g. reproguard explain hidden_env_dependency
```

`reproguard explain --list` enumerates everything reproguard can produce.
