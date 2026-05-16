# Launch drafts

Copy-paste-ready content for the public launch. Tweak before posting; these are starting points calibrated for each channel's voice.

> All drafts assume PyPI is live and the `v1.4.1` tag exists. Verify both before posting.

---

## Show HN

**Title (max ~80 chars):**

```
Show HN: ReproGuard – Catch "works on my laptop" before AI code hits CI
```

**Body:**

```
Hi HN, I'm the author of ReproGuard, an MIT-licensed CLI that runs your build & tests in a fresh tmp workspace, multiple times, and gives you a single 0-100 reproducibility score.

Why I built it: every AI coding tool (Claude, Cursor, Copilot) ships a "tests passed" green check before pushing. But the AI loves Date.now(), time.time(), undeclared env vars, and silent lockfile rewrites. My tests passed locally and broke in CI more times than I want to admit.

What it does, in one command:
- Replays your build/test in a clean tmp copy (no cached state)
- Runs the tests N times and hashes stdout+stderr (output drift = flaky)
- Re-runs with a minimized env (catches hidden env deps)
- Snapshots lockfile SHAs before/after (catches drift)
- Statically scans tests for non-determinism sources
- Detects "0 tests collected" in 9 runners (unittest, pytest, jest, vitest, mocha, go test, cargo test, rspec, phpunit)

Try it in 30 seconds:
  pip install vibe-repro-guard
  cd your-project
  reproguard init   # auto-detects Python/Node/Rust/Go/Ruby/PHP
  reproguard

Zero Python dependencies (stdlib only — one file). GitHub Action and pre-commit hook included.

Repo: https://github.com/alecaram007/vibe-repro-guard
50 tests across CI matrix (Linux/macOS × Python 3.10/3.11/3.12).

What I'd love feedback on:
1. Are there reproducibility failure modes I'm missing? I want to encode them.
2. Naming — "Vibe Repro Guard" is meme-adjacent. Worth keeping?
3. Best way to integrate with Cursor / Claude Code / Copilot CLI?
```

---

## X / Twitter (single tweet)

```
Built ReproGuard: one command that catches the "tests pass locally, break in CI" failures AI coding loves.

- Replays build/tests in fresh tmp workspace, N times
- Hashes stdout, snapshots lockfiles, scans for Date.now/time.Now/etc
- Score 0-100, GitHub Action included

MIT, stdlib only:
github.com/alecaram007/vibe-repro-guard
```

## X / Twitter (thread, 5 tweets)

**1/**
```
Every AI coding tool ships a green "tests passed" check.
But the AI loves Date.now(), undeclared env vars, and silent lockfile rewrites.
You ship. CI fails. Or worse — production fails.

I built ReproGuard for this.
```

**2/**
```
What it does, in one command:

→ Replays build/tests in a fresh tmp workspace
→ Runs N times, hashes output (drift = flaky)
→ Re-runs with minimized env (catches hidden env deps)
→ Snapshots lockfiles before/after (catches drift)
→ Detects 0-test-runs in 9 runners
```

**3/**
```
Output: a single 0-100 reproducibility score + a JSON report.
You wire it into CI with a one-line GitHub Action:

  - uses: alecaram007/vibe-repro-guard@v1.4.1
    with:
      auto-init: true

That's it.
```

**4/**
```
Zero-config onboarding: `reproguard init` scans your project, detects the language (Python/Node/Rust/Go/Ruby/PHP), runtime, lockfiles, env-var usages, and writes a tuned config for you.

Try it in 30 seconds:
  pip install vibe-repro-guard
  cd your-project
  reproguard init && reproguard
```

**5/**
```
MIT-licensed, Python stdlib only (one file, zero deps).
50 tests, CI matrix on Linux/macOS × Python 3.10/3.11/3.12.

Star the repo if this would have saved you a 3am incident:
github.com/alecaram007/vibe-repro-guard
```

---

## LinkedIn

```
We've all been there: the AI generated code, tests passed locally, you pushed, CI failed. Or worse — production broke at 3am.

I built ReproGuard, an open-source CLI (MIT) that catches the most common reproducibility failures in AI-assisted code before they hit your pipeline:

→ Multi-run determinism checks (catches flaky tests on the first try)
→ Lockfile drift detection (catches silent package-lock rewrites)
→ Hidden environment dependency detection (catches "works on my machine")
→ Static scan for time/random sources in tests
→ Zero-test execution detection across 9 test runners

It runs your build and tests in a fresh tmp workspace, multiple times, and gives you a single 0-100 reproducibility score plus a JSON report you can post in PR comments or upload as a CI artifact.

Zero Python dependencies (stdlib only). GitHub Action and pre-commit hook included.

  pip install vibe-repro-guard
  reproguard init && reproguard

If you ship AI-generated code, this is the kind of guardrail that pays for itself the first time it catches a flaky test in a PR instead of in production.

Link in comments. Feedback welcome — especially failure modes I might be missing.
```

---

## Reddit — r/programming

**Title:**
```
ReproGuard: catch "works on my laptop" before AI-generated code hits CI (MIT, stdlib only)
```

**Body:**
```
TL;DR: One Python file, zero deps. Runs your build/tests in a fresh tmp workspace N times, hashes the output, snapshots lockfiles before/after, scans tests for Date.now/time.Now/rand patterns. Score 0-100. GitHub Action included.

Repo: https://github.com/alecaram007/vibe-repro-guard

I wrote this after the Nth time an AI assistant produced "passing" code that broke on a clean checkout. The failure modes I see most:

1. Test uses time.time() / Date.now() → passes once, fails when log output diverges
2. Test reads process.env.X that's only in your shell
3. npm install during tests rewrites package-lock.json
4. Glob pattern in test_command stops matching anything, runner exits 0
5. AI uses datetime.utcnow() — DeprecationWarning in Python 3.12 fails a "no warnings" assertion

ReproGuard catches all five. Detection ID + remediation in the report.

Supported project types: Python, Node, Rust, Go, Ruby, PHP. Auto-detected via `reproguard init`.

Not affiliated with anything; built it for myself, made it MIT, would love patterns I'm missing.
```

---

## Reddit — r/Python

**Title:**
```
[Show & Tell] ReproGuard - deterministic replay guardrail for AI-generated Python code (stdlib only, MIT)
```

**Body:**
```
One file, no external Python deps. Tests it does in a tmp workspace clone of your project:

- replays build+test N times
- hashes stdout, fails on drift  
- snapshots requirements.txt / poetry.lock / Pipfile.lock / uv.lock before+after
- re-runs in a minimized env (catches hidden os.getenv reliance)
- scans test files for time.time / datetime.now / random.* / etc
- detects 0-tests-collected across unittest, pytest, ...

  pip install vibe-repro-guard
  cd your-project
  reproguard init  # auto-detects, writes config
  reproguard       # score 0-100

Works on Python 3.10/3.11/3.12 (CI matrix Linux+macOS). I'd love feedback on failure modes I'm missing.

https://github.com/alecaram007/vibe-repro-guard
```

---

## Awesome-list submission body (re-use across awesome-python, awesome-devtools, awesome-ai-tools)

**PR title:**
```
Add ReproGuard — deterministic replay guardrail for AI-generated code
```

**Diff line (markdown):**
```
- [ReproGuard](https://github.com/alecaram007/vibe-repro-guard) - Replays your build & tests in a fresh tmp workspace, detects flaky tests, lockfile drift, hidden env deps. MIT, Python stdlib only.
```

**PR description:**
```
Adds [ReproGuard](https://github.com/alecaram007/vibe-repro-guard), a deterministic replay guardrail tailored to AI-assisted ("vibe") coding workflows.

Why it fits this list:
- [Active]: weekly releases, latest v1.4.1.
- [Tested]: 50+ unit tests, CI matrix on Linux/macOS × Python 3.10/3.11/3.12.
- [License]: MIT.
- [Distinct value]: combines fresh-workspace replay + lockfile drift + hidden env detection + static non-determinism scan + zero-test detection across 9 runners. None of the listed alternatives cover all five.
- [Zero footprint]: single Python file, no third-party runtime deps.
- [Distribution]: PyPI package, GitHub Action, pre-commit hook.

Happy to adjust the entry text/location to match the list's conventions.
```

---

## Dev.to / Hashnode blog post outline

**Working title:** "I shipped AI-generated code that passed every test. It still broke in production. Here's the guardrail I built."

**Outline:**
1. The incident (concrete failure story; pick one from `docs/STORIES.md`).
2. Why "tests pass locally" is no longer enough (3 reasons, AI-coding specific).
3. What proper reproducibility checking looks like (5 layers: fresh workspace, multi-run, lockfile snapshot, minimized env, static scan).
4. Walkthrough: 60 seconds to onboard ReproGuard on a real project.
5. Showing the report (paste the actual `reproguard.report.md` output).
6. CI integration: one-line GitHub Action.
7. Future work: SARIF output, flaky-test confidence scoring, plugin architecture.
8. Call to action: star the repo, file the failure mode I missed, share your AI horror story.

Target length: 1200-1800 words. Include the JSON report excerpt and one terminal screenshot.
