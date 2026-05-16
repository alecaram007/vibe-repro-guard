# 7 reproducibility bugs ReproGuard catches that other tools miss

These are the failure modes that lead to "the AI wrote it, the tests passed, then it broke in CI" — distilled from real-world AI-coding flows. For each, the symptom, the root cause, and the exact ReproGuard issue ID that surfaces it.

## 1. The "passed once, failed twice" test

**Symptom.** You re-run the same test command. It fails. Re-run again — passes. CI is now coin-flip flaky.

**Root cause.** A test creates a file at module-import time and asserts on its absence. First run: file doesn't exist, passes. Second run: file exists, fails.

**How ReproGuard catches it.** Multi-run replay (`replay_runs: 3`) in a fresh tmp workspace. Exit codes diverge across runs → `nondeterministic_test_exit` (critical, -30).

**Remediation in the report.** "Remove hidden mutable state and stabilize test execution order."

## 2. The hidden environment variable

**Symptom.** `npm test` passes on your machine, fails on a clean checkout for a teammate. Nobody knows why.

**Root cause.** Some test (or test setup) reads `process.env.SOMETHING` that's exported only in your shell.

**How ReproGuard catches it.** After the primary replay passes, ReproGuard re-runs the test command in a minimized-env subprocess (only `PATH`, `HOME`, `LANG`, plus declared `required_env`). If the test now fails → `hidden_env_dependency` (high, -20).

**Bonus.** A static scan of source files flags `process.env.X`, `os.getenv("X")`, `ENV["X"]`, `env::var("X")`, `os.Getenv("X")` that don't appear in your declared `required_env` → `env_not_declared` (medium, -10).

## 3. The silent lockfile rewrite

**Symptom.** `npm install` during your test runner mutates `package-lock.json` — but only on certain machines or transitive dep versions. The lockfile in git starts drifting between commits with no obvious reason.

**Root cause.** The test command implicitly runs `npm install --no-frozen-lockfile` somewhere.

**How ReproGuard catches it.** ReproGuard snapshots SHA-256 of every declared lockfile *before* and *after* replay. If anything changed → `lockfile_drift` (high, -20). With `fail_on_lockfile_drift: true` the replay also fails.

## 4. The zero-test green build

**Symptom.** CI is green. The badge says "passing." But nobody noticed that your `npm test` glob doesn't match any files anymore after a directory rename.

**Root cause.** Empty test discovery silently succeeds in jest/vitest/mocha (and in `pytest` it depends on flags; in `unittest discover` on Python 3.12.10+ exit code is 5 but earlier versions returned 0).

**How ReproGuard catches it.** After the test command, ReproGuard inspects stdout/stderr for known zero-test fingerprints across **9 runners**: unittest (`Ran 0 tests`), pytest (`collected 0 items`, `no tests ran`, `no tests collected`), jest (`No tests found`), vitest (`No test files found`), mocha (`0 passing`), go test (`no test files`, `no tests to run`), cargo test (`running 0 tests`), rspec (`0 examples, 0 failures`), phpunit (`No tests executed`). Match → `test_runs_zero` (high, -20), replay marked failed regardless of exit code.

## 5. The undeclared Python version

**Symptom.** Tests pass on your laptop (Python 3.11). CI uses 3.12. Code crashes because `datetime.utcnow()` now emits a `DeprecationWarning` that a test asserts shouldn't be raised.

**Root cause.** No explicit runtime pin. Different machines, different Python, different stdlib semantics.

**How ReproGuard catches it.** If `pyproject.toml` exists but `runtime.python` is not declared in `reproguard.yaml` → `runtime_missing_python` (high, -20). If declared but doesn't match what's running → `runtime_drift_python` (high, -20). Same logic for Node, Rust, Go, Ruby, PHP via alias mapping.

## 6. The flaky `time.time()` in a test

**Symptom.** Two test runs back-to-back produce slightly different log output but both pass. Debugging takes 40 minutes before you realize a test logs a timestamp.

**Root cause.** `time.time()` / `Date.now()` / `time.Now()` / `Time.now` / `SystemTime::now` in a test path.

**How ReproGuard catches it.** Two complementary checks:
1. **Static scan** of test files flags time/random sources → `nondeterministic_test_signals` (medium, -10).
2. **Output hash drift**: if exit codes match but `sha256(stdout+stderr)` diverges across runs → `nondeterministic_test_output` (high, -20).

## 7. The "AI added a secret to the logs"

**Symptom.** Your AI assistant generates a logger config that prints env vars on startup for "debugging." The CI logs leak a token. A bot scrapes it within minutes.

**Root cause.** Sensitive env values shown in logs.

**How ReproGuard catches it (defense in depth).** Before storing replay logs in the report, ReproGuard replaces any value of an env var matching `redact_env_patterns` (default: `TOKEN`, `SECRET`, `PASSWORD`, `API_KEY`, `PRIVATE_KEY`) or declared in `required_env` with `[REDACTED]`. The report you commit to PRs or upload as a CI artifact contains no secrets.

## How the score is calculated

ReproGuard starts at 100, subtracts the `deduction` listed for each issue (capped at 0). A score below the configured `score_threshold` (default `85`) is non-fatal in `advisory` mode and fatal in `strict` mode (exit code 30). Failed replay (any of the above replay-phase issues firing) returns exit code 20 regardless of mode.

| Issue ID | Severity | Deduction | Phase |
| --- | --- | --- | --- |
| `config_invalid` | critical | -30 | baseline |
| `nondeterministic_test_exit` | critical | -30 | replay |
| `lockfile_missing` | critical | -30 | contract |
| `replay_build_failed` | high | -20 | replay |
| `replay_test_failed` | high | -20 | replay |
| `test_runs_zero` | high | -20 | replay |
| `hidden_env_dependency` | high | -20 | replay |
| `lockfile_drift` | high | -20 | replay |
| `nondeterministic_test_output` | high | -20 | replay |
| `runtime_missing_*` / `runtime_drift_*` / `runtime_not_pinned_*` | high | -20 | contract |
| `required_env_missing_values` | high | -20 | baseline |
| `env_not_declared` | medium | -10 | contract |
| `nondeterministic_test_signals` | medium | -10 | contract |
| `lockfile_not_declared` | medium | -10 | contract |
| `test_command_missing` | medium | -10 | contract |
| `git_dirty_workspace` | low | -5 | baseline |
