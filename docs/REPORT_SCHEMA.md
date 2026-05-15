# ReproGuard Report Schema

`reproguard.report.json` is the stable machine-readable artifact for CI,
dashboards, and automation. The JSON Schema is versioned with the report
payload and lives at:

- [`docs/reproguard.report.schema.json`](./reproguard.report.schema.json)

## Compatibility

- Current schema version: `1.1`
- Schema version field: `meta.schema_version`
- Producers may add fields only with a future schema version.
- Consumers should reject unknown `meta.schema_version` values unless they have
  been explicitly tested.

## Required top-level fields

| Field | Type | Purpose |
| --- | --- | --- |
| `meta` | object | Artifact metadata, paths, timestamp, and tool identity. |
| `summary` | object | Policy mode, reproducibility score, replay status, issue totals, and exit code. |
| `issues` | array | Ordered list of detected reproducibility issues. |
| `phases` | object | Baseline, contract, and replay details used to produce the summary. |

## Issue object

Each item in `issues` has this required shape:

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | string | Stable issue identifier for automation rules. |
| `title` | string | Human-readable issue label. |
| `severity` | string | One of `critical`, `high`, `medium`, `low`. |
| `phase` | string | One of `baseline`, `contract`, `replay`. |
| `evidence` | string | Concrete observation from the guard run. |
| `remediation` | string | Suggested fix path. |
| `deduction` | integer | Score penalty applied to the run. |

## Replay details

`phases.replay` is populated after a valid config is loaded. If configuration
validation fails, the object may be empty and `summary.exit_code` is `40`.
Successful replay data can include command results, multi-run test output
hashes, minimal-env checks, and lockfile drift details.

Command result objects include redacted/truncated `stdout` and `stderr` fields
plus `stdout_hash` for deterministic comparisons without requiring consumers to
store full logs.
