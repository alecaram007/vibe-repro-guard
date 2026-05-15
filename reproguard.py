#!/usr/bin/env python3
"""
Vibe Repro Guard v1.2.13

Deterministic replay guardrail for AI-assisted coding projects.
No external dependencies required (Python stdlib only).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ARTIFACT_CONTRACT = "reproguard.contract.json"
ARTIFACT_REPORT_JSON = "reproguard.report.json"
ARTIFACT_REPORT_MD = "reproguard.report.md"

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "advisory",
    "score_threshold": 85,
    "build_command": "",
    "test_command": "",
    "required_env": [],
    "runtime": {},
    "lockfiles": [],
    "replay_runs": 2,
    "redact_env_patterns": ["TOKEN", "SECRET", "PASSWORD", "API_KEY", "PRIVATE_KEY"],
    "fail_on_lockfile_drift": True,
    "require_declared_env_values": True,
}

CORE_ENV_KEYS = ["PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "TEMP", "TMP"]

DEFAULT_LOCKFILES_NODE = ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"]
DEFAULT_LOCKFILES_PYTHON = ["requirements.txt", "poetry.lock", "Pipfile.lock", "uv.lock"]
DEFAULT_LOCKFILES_PHP = ["composer.lock"]

NONDET_REGEXES = [
    (re.compile(r"\bDate\.now\s*\("), "JS Date.now"),
    (re.compile(r"\bnew\s+Date\s*\("), "JS new Date"),
    (re.compile(r"\bMath\.random\s*\("), "JS Math.random"),
    (re.compile(r"\bcrypto\.random"), "JS crypto random"),
    (re.compile(r"\bdatetime\.now\s*\("), "Python datetime.now"),
    (re.compile(r"\btime\.time\s*\("), "Python time.time"),
    (re.compile(r"\brandom\."), "Python random module"),
]

ENV_REGEXES = [
    re.compile(r"\bprocess\.env\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\b"),
    re.compile(r"\bprocess\.env\s*\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]"),
    re.compile(r"\bprocess\.env\?\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\b"),
    re.compile(r"\bprocess\.env\?\s*\.\s*\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]"),
    re.compile(r"\bos\.getenv\s*\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]"),
    re.compile(r"\bos\.environ\s*\.\s*get\s*\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]"),
    re.compile(r"\bos\.environ\s*\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]"),
]

ENV_EXEMPT = {
    "PATH",
    "HOME",
    "SHELL",
    "TERM",
    "PWD",
    "CI",
    "TZ",
    "LANG",
    "LC_ALL",
    "NODE_ENV",
    "PYTHONPATH",
    "PYTHONUNBUFFERED",
    "PYTHONDONTWRITEBYTECODE",
}

IGNORE_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    "dist",
    "build",
    "target",
    ARTIFACT_CONTRACT,
    ARTIFACT_REPORT_JSON,
    ARTIFACT_REPORT_MD,
}

DEFAULT_REDACTION_PATTERNS = ["TOKEN", "SECRET", "PASSWORD", "API_KEY", "PRIVATE_KEY"]

MAX_OUTPUT_CHARS = 12000

ZERO_TEST_OUTPUT_PATTERNS = [
    ("python-unittest", re.compile(r"\bRan\s+0\s+tests\b", re.IGNORECASE)),
    ("python-pytest", re.compile(r"\bcollected\s+0\s+items\b", re.IGNORECASE)),
    ("python-pytest", re.compile(r"\bno tests ran\b", re.IGNORECASE)),
    ("python-pytest", re.compile(r"\bno tests collected\b", re.IGNORECASE)),
    ("jest", re.compile(r"\bNo tests found\b", re.IGNORECASE)),
    ("vitest", re.compile(r"\bNo test files found\b", re.IGNORECASE)),
    ("mocha", re.compile(r"\b0\s+passing\b", re.IGNORECASE)),
]


class ConfigError(Exception):
    pass


def _strip_inline_comment(line: str) -> str:
    in_single = False
    in_double = False
    out = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
            continue
        if ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out)


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    return value


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """
    Minimal YAML parser for the expected config shape.
    Supports:
    - top-level scalars
    - top-level list blocks
    - top-level mapping blocks (one level deep)
    """
    root: Dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        original = lines[i]
        line = _strip_inline_comment(original).rstrip()
        i += 1
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent != 0:
            raise ConfigError(f"Invalid top-level indentation at line {i}: {original!r}")
        stripped = line.strip()
        key, sep, rest = stripped.partition(":")
        if not sep:
            raise ConfigError(f"Expected 'key: value' at line {i}: {original!r}")
        key = key.strip()
        rest = rest.strip()
        if rest:
            root[key] = _parse_scalar(rest)
            continue

        block: List[Tuple[int, str]] = []
        while i < len(lines):
            candidate = _strip_inline_comment(lines[i]).rstrip()
            if not candidate.strip():
                i += 1
                continue
            cand_indent = len(candidate) - len(candidate.lstrip(" "))
            if cand_indent <= indent:
                break
            block.append((cand_indent, candidate[cand_indent:]))
            i += 1

        if not block:
            root[key] = None
            continue

        block_is_list = all(item[1].lstrip().startswith("- ") for item in block)
        if block_is_list:
            values: List[Any] = []
            for _, content in block:
                c = content.lstrip()
                if not c.startswith("- "):
                    raise ConfigError(f"Invalid list item under key '{key}'")
                values.append(_parse_scalar(c[2:].strip()))
            root[key] = values
            continue

        child: Dict[str, Any] = {}
        for _, content in block:
            c = content.strip()
            c_key, c_sep, c_rest = c.partition(":")
            if not c_sep:
                raise ConfigError(f"Invalid mapping item under key '{key}': {content!r}")
            c_key = c_key.strip()
            c_rest = c_rest.strip()
            if c_rest == "":
                raise ConfigError(
                    f"Nested blocks beyond one level are not supported in key '{key}', item '{c_key}'"
                )
            child[c_key] = _parse_scalar(c_rest)
        root[key] = child
    return root


def is_safe_lockfile_path(value: str) -> bool:
    raw = value.strip()
    if not raw:
        return False
    normalized = raw.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        return False
    if normalized.startswith("//"):
        return False
    candidate = Path(normalized)
    if candidate.is_absolute():
        return False
    if any(part == ".." for part in normalized.split("/")):
        return False
    return True


def load_config(config_path: Path) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    cfg = dict(DEFAULT_CONFIG)

    if not config_path.exists():
        errors.append(f"Config file not found: {config_path}")
        return cfg, errors

    raw = config_path.read_text(encoding="utf-8")
    try:
        parsed = parse_simple_yaml(raw)
    except ConfigError as exc:
        errors.append(str(exc))
        return cfg, errors

    cfg.update(parsed)
    cfg["required_env"] = cfg.get("required_env") or []
    cfg["runtime"] = cfg.get("runtime") or {}
    cfg["lockfiles"] = cfg.get("lockfiles") or []
    cfg["redact_env_patterns"] = cfg.get("redact_env_patterns") or []

    mode = cfg.get("mode")
    if mode not in {"strict", "advisory"}:
        errors.append("mode must be 'strict' or 'advisory'")

    threshold = cfg.get("score_threshold")
    if not isinstance(threshold, int) or threshold < 0 or threshold > 100:
        errors.append("score_threshold must be an integer between 0 and 100")

    if not isinstance(cfg.get("build_command"), str):
        errors.append("build_command must be a string")
    if not isinstance(cfg.get("test_command"), str):
        errors.append("test_command must be a string")

    if not isinstance(cfg.get("required_env"), list) or not all(isinstance(x, str) for x in cfg["required_env"]):
        errors.append("required_env must be a list of strings")

    if not isinstance(cfg.get("runtime"), dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in cfg["runtime"].items()
    ):
        errors.append("runtime must be a map of runtime name -> version string")

    if not isinstance(cfg.get("lockfiles"), list) or not all(isinstance(x, str) for x in cfg["lockfiles"]):
        errors.append("lockfiles must be a list of strings")
    elif any(not is_safe_lockfile_path(lock) for lock in cfg["lockfiles"]):
        errors.append("lockfiles entries must be relative paths without '..' traversal")

    replay_runs = cfg.get("replay_runs")
    if not isinstance(replay_runs, int) or replay_runs < 2 or replay_runs > 10:
        errors.append("replay_runs must be an integer between 2 and 10")

    if not isinstance(cfg.get("redact_env_patterns"), list) or not all(
        isinstance(x, str) for x in cfg["redact_env_patterns"]
    ):
        errors.append("redact_env_patterns must be a list of strings")

    if not isinstance(cfg.get("fail_on_lockfile_drift"), bool):
        errors.append("fail_on_lockfile_drift must be a boolean")
    if not isinstance(cfg.get("require_declared_env_values"), bool):
        errors.append("require_declared_env_values must be a boolean")

    return cfg, errors


def run_capture(cmd: List[str], timeout_sec: int = 10) -> Dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return {
            "command": " ".join(cmd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "duration_sec": round(time.monotonic() - started, 3),
            "timed_out": False,
        }
    except FileNotFoundError:
        return {
            "command": " ".join(cmd),
            "exit_code": 127,
            "stdout": "",
            "stderr": "command not found",
            "duration_sec": round(time.monotonic() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(cmd),
            "exit_code": 124,
            "stdout": "",
            "stderr": "timeout",
            "duration_sec": round(time.monotonic() - started, 3),
            "timed_out": True,
        }


def run_shell(cmd: str, cwd: Path, env: Dict[str, str], timeout_sec: int = 300) -> Dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return {
            "command": cmd,
            "cwd": str(cwd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration_sec": round(time.monotonic() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "cwd": str(cwd),
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\n[reproguard] command timed out",
            "duration_sec": round(time.monotonic() - started, 3),
            "timed_out": True,
        }


def detect_project_type(root: Path) -> Dict[str, bool]:
    return {
        "node": (root / "package.json").exists(),
        "python": any((root / p).exists() for p in ("pyproject.toml", "requirements.txt", "setup.py")),
        "php": (root / "composer.json").exists(),
    }


def detect_versions() -> Dict[str, Any]:
    versions = {
        "python": run_capture([sys.executable, "--version"]),
        "python3": run_capture(["python3", "--version"]),
        "node": run_capture(["node", "--version"]),
        "npm": run_capture(["npm", "--version"]),
        "pnpm": run_capture(["pnpm", "--version"]),
        "yarn": run_capture(["yarn", "--version"]),
    }
    return versions


def detect_git_state(root: Path) -> Dict[str, Any]:
    is_repo = run_capture(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"])
    if is_repo.get("exit_code") != 0:
        return {"is_git_repo": False}

    commit = run_capture(["git", "-C", str(root), "rev-parse", "HEAD"])
    branch = run_capture(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"])
    status = run_capture(["git", "-C", str(root), "status", "--porcelain"])

    return {
        "is_git_repo": True,
        "commit": commit.get("stdout", ""),
        "branch": branch.get("stdout", ""),
        "dirty": bool((status.get("stdout") or "").strip()),
        "dirty_entries": (status.get("stdout") or "").splitlines()[:25],
    }


def is_semver_pinned(value: str) -> bool:
    return bool(re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?", value.strip()))


def normalize_version(value: str) -> str:
    return value.strip().lstrip("vV")


def extract_version_token(text: str) -> str:
    value = text.strip()
    if not value:
        return ""
    match = re.search(r"\b[vV]?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?)\b", value)
    if match:
        return normalize_version(match.group(1))
    parts = value.split()
    if not parts:
        return ""
    return normalize_version(parts[-1])


def read_small_text(path: Path, max_bytes: int = 400_000) -> Optional[str]:
    try:
        if path.stat().st_size > max_bytes:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def scan_source_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}:
            files.append(path)
    return files


def scan_env_usage(root: Path) -> Dict[str, Any]:
    referenced: Dict[str, List[str]] = {}
    for path in scan_source_files(root):
        text = read_small_text(path)
        if text is None:
            continue
        for regex in ENV_REGEXES:
            for match in regex.finditer(text):
                name = match.group(1)
                referenced.setdefault(name, []).append(str(path.relative_to(root)))
    return referenced


def is_test_file(path: Path) -> bool:
    p = path.as_posix().lower()
    return (
        "/test" in p
        or "/tests" in p
        or "__tests__" in p
        or path.name.lower().startswith("test")
        or path.name.lower().endswith("_test.py")
        or path.name.lower().endswith(".test.js")
        or path.name.lower().endswith(".spec.js")
    )


def scan_nondeterminism(root: Path) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for path in scan_source_files(root):
        if not is_test_file(path):
            continue
        text = read_small_text(path)
        if text is None:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if "mock" in lowered or "freeze" in lowered or "faker.seed" in lowered:
                continue
            for regex, label in NONDET_REGEXES:
                if regex.search(line):
                    findings.append(
                        {
                            "file": str(path.relative_to(root)),
                            "line": line_no,
                            "pattern": label,
                            "snippet": line.strip()[:180],
                        }
                    )
    return findings


def determine_expected_lockfiles(project_type: Dict[str, bool], config_lockfiles: List[str]) -> Tuple[List[str], bool]:
    if config_lockfiles:
        return config_lockfiles, True
    expected: List[str] = []
    if project_type["node"]:
        expected.extend(DEFAULT_LOCKFILES_NODE)
    if project_type["python"]:
        expected.extend(DEFAULT_LOCKFILES_PYTHON)
    if project_type.get("php"):
        expected.extend(DEFAULT_LOCKFILES_PHP)
    return expected, False


def resolve_default_commands(config: Dict[str, Any], project_type: Dict[str, bool]) -> Dict[str, str]:
    build_cmd = (config.get("build_command") or "").strip()
    test_cmd = (config.get("test_command") or "").strip()

    if not test_cmd:
        if project_type["node"]:
            test_cmd = "npm test"
        elif project_type["python"]:
            test_cmd = "python3 -m unittest discover"
    return {"build_command": build_cmd, "test_command": test_cmd}


def copy_workspace(src: Path, dst: Path) -> None:
    def _ignore(directory: str, names: List[str]) -> List[str]:
        ignored = []
        for name in names:
            if name in IGNORE_NAMES:
                ignored.append(name)
        return ignored

    for child in src.iterdir():
        if child.name in IGNORE_NAMES:
            continue
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target, ignore=_ignore)
        else:
            shutil.copy2(child, target)


def minimal_env(required_env: List[str]) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for key in CORE_ENV_KEYS:
        if key in os.environ:
            env[key] = os.environ[key]
    for key in required_env:
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def issue(
    issue_id: str,
    title: str,
    severity: str,
    phase: str,
    evidence: str,
    remediation: str,
    deduction: int,
) -> Dict[str, Any]:
    return {
        "id": issue_id,
        "title": title,
        "severity": severity,
        "phase": phase,
        "evidence": evidence,
        "remediation": remediation,
        "deduction": deduction,
    }


def apply_runtime_checks(
    cfg: Dict[str, Any],
    project_type: Dict[str, bool],
    versions: Dict[str, Any],
    issues: List[Dict[str, Any]],
) -> None:
    runtime = cfg.get("runtime", {})

    if project_type["python"] and "python" not in runtime:
        issues.append(
            issue(
                "runtime_missing_python",
                "Python runtime not declared",
                "high",
                "contract",
                "Python project detected but runtime.python is missing in reproguard.yaml",
                "Add runtime.python with an exact version (e.g. 3.12.3).",
                20,
            )
        )
    if project_type["node"] and "node" not in runtime:
        issues.append(
            issue(
                "runtime_missing_node",
                "Node runtime not declared",
                "high",
                "contract",
                "Node project detected but runtime.node is missing in reproguard.yaml",
                "Add runtime.node with an exact version (e.g. 20.12.2).",
                20,
            )
        )

    for key, declared in runtime.items():
        if not is_semver_pinned(str(declared)):
            issues.append(
                issue(
                    f"runtime_not_pinned_{key}",
                    f"Runtime {key} is not pinned",
                    "high",
                    "contract",
                    f"runtime.{key} is '{declared}' and is not exact semver",
                    "Use an exact version x.y.z to ensure deterministic replay.",
                    20,
                )
            )
        detected_info = versions.get(key)
        if not detected_info or detected_info.get("exit_code") != 0:
            continue
        detected_output = " ".join(
            part.strip()
            for part in [str(detected_info.get("stdout") or ""), str(detected_info.get("stderr") or "")]
            if part and part.strip()
        )
        detected = extract_version_token(detected_output)
        if not detected:
            continue
        declared_norm = normalize_version(str(declared))
        if detected and declared_norm and detected != declared_norm:
            issues.append(
                issue(
                    f"runtime_drift_{key}",
                    f"Runtime drift for {key}",
                    "high",
                    "contract",
                    f"Declared {key}={declared_norm}, current environment has {detected}",
                    f"Align runtime version using asdf/nvm/pyenv or update runtime.{key} to match expected target.",
                    20,
                )
            )


def apply_lockfile_checks(
    root: Path,
    expected_lockfiles: List[str],
    explicit_policy: bool,
    issues: List[Dict[str, Any]],
) -> None:
    if not expected_lockfiles:
        issues.append(
            issue(
                "lockfile_not_declared",
                "No lockfile policy declared",
                "medium",
                "contract",
                "No lockfiles provided and none inferred from project type.",
                "Add lockfiles to reproguard.yaml or include standard project lockfiles.",
                10,
            )
        )
        return

    if explicit_policy:
        missing = [lock for lock in expected_lockfiles if not (root / lock).exists()]
        if missing:
            issues.append(
                issue(
                    "lockfile_missing",
                    "Configured lockfile path is missing",
                    "critical",
                    "contract",
                    f"Missing configured lockfiles: {', '.join(missing)}",
                    "Create and commit all lockfiles declared in reproguard.yaml.",
                    30,
                )
            )
        return

    present = [lock for lock in expected_lockfiles if (root / lock).exists()]
    if not present:
        issues.append(
            issue(
                "lockfile_missing",
                "No expected lockfile found",
                "critical",
                "contract",
                f"Expected one of: {', '.join(expected_lockfiles)}",
                "Generate and commit a lockfile before relying on AI-generated changes.",
                30,
            )
        )


def apply_env_static_checks(
    referenced: Dict[str, List[str]],
    required_env: List[str],
    issues: List[Dict[str, Any]],
) -> None:
    required = {x.strip() for x in required_env if x.strip()}
    missing = sorted(name for name in referenced if name not in required and name not in ENV_EXEMPT)
    if not missing:
        return

    sample = []
    for env_name in missing[:5]:
        locs = ", ".join(referenced[env_name][:2])
        sample.append(f"{env_name} ({locs})")

    issues.append(
        issue(
            "env_not_declared",
            "Environment variables used but not declared",
            "medium",
            "contract",
            "Potential undeclared env vars: " + "; ".join(sample),
            "Add these variables to required_env to make replay requirements explicit.",
            10,
        )
    )


def apply_required_env_presence_checks(cfg: Dict[str, Any], issues: List[Dict[str, Any]]) -> None:
    if not cfg.get("require_declared_env_values", True):
        return
    missing = []
    for name in cfg.get("required_env", []):
        if not name:
            continue
        value = os.environ.get(name)
        if value is None or value == "":
            missing.append(name)
    if not missing:
        return
    issues.append(
        issue(
            "required_env_missing_values",
            "Required environment values are not set",
            "high",
            "baseline",
            "Missing or empty required variables in current environment: " + ", ".join(missing[:20]),
            "Export the missing variables before running deterministic replay.",
            20,
        )
    )


def apply_nondeterminism_static_checks(findings: List[Dict[str, Any]], issues: List[Dict[str, Any]]) -> None:
    if not findings:
        return
    sample = findings[0]
    issues.append(
        issue(
            "nondeterministic_test_signals",
            "Potential non-deterministic constructs in tests",
            "medium",
            "contract",
            f"Found {len(findings)} signals, e.g. {sample['file']}:{sample['line']} uses {sample['pattern']}",
            "Mock/freeze time/random sources or inject deterministic seeds in tests.",
            10,
        )
    )


def apply_git_state_checks(git_state: Dict[str, Any], issues: List[Dict[str, Any]]) -> None:
    if not git_state.get("is_git_repo"):
        return
    if git_state.get("dirty"):
        issues.append(
            issue(
                "git_dirty_workspace",
                "Git workspace has uncommitted changes",
                "low",
                "baseline",
                "Working tree is dirty; replay proof may not match a shareable commit state.",
                "Commit or stash relevant changes before final reproducibility validation.",
                5,
            )
        )


def score_issues(issues: List[Dict[str, Any]]) -> Tuple[int, Dict[str, int]]:
    score = 100
    totals = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for item in issues:
        sev = item.get("severity", "low")
        if sev in totals:
            totals[sev] += 1
        score -= int(item.get("deduction", 0))
    return max(0, score), totals


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_lockfiles(root: Path, lockfiles: List[str]) -> Dict[str, str]:
    snapshot: Dict[str, str] = {}
    for rel in lockfiles:
        path = root / rel
        if path.exists() and path.is_file():
            try:
                snapshot[rel] = sha256_file(path)
            except OSError:
                continue
    return snapshot


def diff_lockfile_snapshots(
    expected_lockfiles: List[str],
    before: Dict[str, str],
    after: Dict[str, str],
) -> Dict[str, List[str]]:
    created: List[str] = []
    changed: List[str] = []
    deleted: List[str] = []
    for rel in expected_lockfiles:
        has_before = rel in before
        has_after = rel in after
        if not has_before and has_after:
            created.append(rel)
        elif has_before and not has_after:
            deleted.append(rel)
        elif has_before and has_after and before[rel] != after[rel]:
            changed.append(rel)
    return {"created": created, "changed": changed, "deleted": deleted}


def truncate_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    remaining = len(text) - limit
    return text[:limit] + f"\n[reproguard] output truncated ({remaining} chars omitted)"


def detect_zero_test_signal(run_result: Dict[str, Any]) -> str:
    combined = "\n".join(
        [
            str(run_result.get("stdout") or ""),
            str(run_result.get("stderr") or ""),
        ]
    )
    for label, pattern in ZERO_TEST_OUTPUT_PATTERNS:
        if pattern.search(combined):
            return label
    return ""


def build_redaction_secrets(cfg: Dict[str, Any]) -> List[str]:
    patterns = [x.upper() for x in (cfg.get("redact_env_patterns") or []) if isinstance(x, str)]
    if not patterns:
        patterns = DEFAULT_REDACTION_PATTERNS
    required = {x.strip() for x in (cfg.get("required_env") or []) if isinstance(x, str)}
    secrets: List[str] = []
    for key, value in os.environ.items():
        if not value or len(value) < 3:
            continue
        key_upper = key.upper()
        if key in required or any(pattern in key_upper for pattern in patterns):
            secrets.append(value)
    # Longer secrets first to avoid partial masking collisions.
    return sorted(set(secrets), key=len, reverse=True)


def redact_text(text: str, secrets: List[str]) -> str:
    output = text
    for secret in secrets:
        output = output.replace(secret, "[REDACTED]")
    return output


def sanitize_run_result(run_result: Dict[str, Any], secrets: List[str]) -> Dict[str, Any]:
    raw_stdout = run_result.get("stdout") or ""
    raw_stderr = run_result.get("stderr") or ""
    combined = raw_stdout + raw_stderr
    run_result["stdout_hash"] = short_hash(combined)
    run_result["stdout"] = truncate_output(redact_text(raw_stdout, secrets))
    run_result["stderr"] = truncate_output(redact_text(raw_stderr, secrets))
    return run_result


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    meta = report["meta"]
    summary = report["summary"]

    lines.append("# ReproGuard Report")
    lines.append("")
    lines.append(f"- Project: `{meta['project_root']}`")
    lines.append(f"- Generated at: `{meta['generated_at']}`")
    lines.append(f"- Mode: `{summary['mode']}`")
    lines.append(f"- Score: **{summary['score']} / 100** (threshold: {summary['score_threshold']})")
    lines.append(f"- Replay status: `{summary['replay_status']}`")
    lines.append(f"- Exit code: `{summary['exit_code']}`")
    lines.append("")
    lines.append("## Issues")
    if report["issues"]:
        for item in report["issues"]:
            lines.append(
                f"- [{item['severity'].upper()}] `{item['id']}`: {item['title']} "
                f"(phase: {item['phase']}, -{item['deduction']})"
            )
            lines.append(f"  Evidence: {item['evidence']}")
            lines.append(f"  Remediation: {item['remediation']}")
    else:
        lines.append("- No issues detected.")
    lines.append("")
    lines.append("## Replay")
    replay = report["phases"]["replay"]
    lines.append(f"- Workspace: `{replay.get('workspace', 'n/a')}`")
    lines.append(f"- Build executed: `{bool(replay.get('build'))}`")
    test_runs = replay.get("test_runs") or []
    lines.append(f"- Test runs configured: `{replay.get('configured_test_runs', 0)}`")
    for item in test_runs:
        lines.append(
            f"- Run {item.get('index')} exit: `{item.get('exit_code')}` "
            f"hash: `{item.get('stdout_hash')}` duration: `{item.get('duration_sec')}s`"
        )
    if replay.get("lockfile_drift"):
        drift = replay["lockfile_drift"]
        lines.append(
            f"- Lockfile drift: created={len(drift.get('created', []))}, "
            f"changed={len(drift.get('changed', []))}, deleted={len(drift.get('deleted', []))}"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("- This report is generated in advisory/strict policy mode without external dependencies.")
    lines.append("- Use `reproguard.contract.json` for machine-readable reproducibility contract details.")
    return "\n".join(lines) + "\n"


def write_report_markdown(path: Path, report: Dict[str, Any]) -> None:
    path.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Vibe Repro Guard")
    parser.add_argument("--project-root", default=".", help="Project root path")
    parser.add_argument("--config", default="reproguard.yaml", help="Config file path (relative to project root)")
    parser.add_argument("--output-dir", default="", help="Directory for artifacts (default: project root)")
    parser.add_argument("--timeout-sec", type=int, default=300, help="Per-command timeout in seconds")
    parser.add_argument("--summary-json", action="store_true", help="Print summary as JSON to stdout")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    config_path = (root / args.config).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else root
    output_dir.mkdir(parents=True, exist_ok=True)

    started_at = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    git_state = detect_git_state(root)
    baseline = {
        "timestamp_utc": started_at,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "cwd": str(root),
        "git": git_state,
    }

    cfg, config_errors = load_config(config_path)
    project_type = detect_project_type(root)
    versions = detect_versions()
    resolved_cmds = resolve_default_commands(cfg, project_type)
    expected_lockfiles, explicit_lock_policy = determine_expected_lockfiles(project_type, cfg.get("lockfiles", []))

    issues: List[Dict[str, Any]] = []
    replay_data: Dict[str, Any] = {}

    contract = {
        "schema_version": "1.1",
        "generated_at": started_at,
        "project_root": str(root),
        "output_dir": str(output_dir),
        "config_path": str(config_path),
        "config": cfg,
        "config_errors": config_errors,
        "baseline": baseline,
        "project_type": project_type,
        "detected_versions": versions,
        "resolved_commands": resolved_cmds,
        "expected_lockfiles": expected_lockfiles,
        "explicit_lock_policy": explicit_lock_policy,
        "replay_runs": cfg.get("replay_runs"),
        "fail_on_lockfile_drift": cfg.get("fail_on_lockfile_drift"),
    }

    apply_git_state_checks(git_state, issues)

    if config_errors:
        issues.append(
            issue(
                "config_invalid",
                "Invalid reproguard.yaml configuration",
                "critical",
                "baseline",
                "; ".join(config_errors),
                "Fix config values to match the expected schema.",
                30,
            )
        )
    else:
        replay_runs = int(cfg.get("replay_runs", 2))
        fail_on_lockfile_drift = bool(cfg.get("fail_on_lockfile_drift", True))
        redaction_secrets = build_redaction_secrets(cfg)

        apply_required_env_presence_checks(cfg, issues)
        apply_runtime_checks(cfg, project_type, versions, issues)
        apply_lockfile_checks(root, expected_lockfiles, explicit_lock_policy, issues)

        referenced_env = scan_env_usage(root)
        apply_env_static_checks(referenced_env, cfg.get("required_env", []), issues)
        nondet_findings = scan_nondeterminism(root)
        apply_nondeterminism_static_checks(nondet_findings, issues)
        if not resolved_cmds["test_command"]:
            issues.append(
                issue(
                    "test_command_missing",
                    "No test command resolved",
                    "medium",
                    "contract",
                    "No test_command configured and no default detected from project type.",
                    "Define test_command in reproguard.yaml to verify deterministic replay.",
                    10,
                )
            )

        replay_failed = False
        with tempfile.TemporaryDirectory(prefix="reproguard-") as tmp_dir:
            tmp_root = Path(tmp_dir) / "workspace"
            tmp_root.mkdir(parents=True, exist_ok=True)
            copy_workspace(root, tmp_root)

            replay_data["workspace"] = str(tmp_root)
            replay_data["configured_test_runs"] = replay_runs
            primary_env = dict(os.environ)
            lock_snapshot_before = snapshot_lockfiles(tmp_root, expected_lockfiles)

            build_result = None
            if resolved_cmds["build_command"]:
                build_result = run_shell(
                    resolved_cmds["build_command"],
                    cwd=tmp_root,
                    env=primary_env,
                    timeout_sec=args.timeout_sec,
                )
                build_result = sanitize_run_result(build_result, redaction_secrets)
                replay_data["build"] = build_result
                if build_result["exit_code"] != 0:
                    replay_failed = True
                    issues.append(
                        issue(
                            "replay_build_failed",
                            "Build failed during replay",
                            "high",
                            "replay",
                            f"Build command exited with {build_result['exit_code']}",
                            "Fix build reproducibility and ensure required build dependencies are installed.",
                            20,
                        )
                    )

            test_runs: List[Dict[str, Any]] = []
            if resolved_cmds["test_command"]:
                for run_index in range(1, replay_runs + 1):
                    run_result = run_shell(
                        resolved_cmds["test_command"],
                        cwd=tmp_root,
                        env=primary_env,
                        timeout_sec=args.timeout_sec,
                    )
                    run_result = sanitize_run_result(run_result, redaction_secrets)
                    run_result["index"] = run_index
                    test_runs.append(run_result)

                replay_data["test_runs"] = test_runs
                if test_runs:
                    replay_data["test_run_1"] = test_runs[0]
                if len(test_runs) > 1:
                    replay_data["test_run_2"] = test_runs[1]

                first_run = test_runs[0]
                if first_run["exit_code"] != 0:
                    replay_failed = True
                    issues.append(
                        issue(
                            "replay_test_failed",
                            "Test command failed during replay",
                            "high",
                            "replay",
                            f"Test run 1 exited with {first_run['exit_code']}",
                            "Make tests deterministic and verify prerequisites are explicitly declared.",
                            20,
                        )
                    )
                else:
                    zero_test_signal = detect_zero_test_signal(first_run)
                    if zero_test_signal:
                        replay_failed = True
                        issues.append(
                            issue(
                                "test_runs_zero",
                                "Test command executed zero tests",
                                "high",
                                "replay",
                                f"Replay run completed but no tests were executed ({zero_test_signal}).",
                                "Update test_command to run the real suite and fail when zero tests are collected.",
                                20,
                            )
                        )

                exit_codes = {x["exit_code"] for x in test_runs}
                output_hashes = {x["stdout_hash"] for x in test_runs}
                if len(exit_codes) > 1:
                    replay_failed = True
                    exits = ", ".join(str(x["exit_code"]) for x in test_runs)
                    issues.append(
                        issue(
                            "nondeterministic_test_exit",
                            "Test exit behavior changed across replay runs",
                            "critical",
                            "replay",
                            f"Observed exit sequence across runs: [{exits}]",
                            "Remove hidden mutable state and stabilize test execution order.",
                            30,
                        )
                    )
                elif len(output_hashes) > 1:
                    replay_failed = True
                    hashes = ", ".join(x["stdout_hash"] for x in test_runs)
                    issues.append(
                        issue(
                            "nondeterministic_test_output",
                            "Test output changed across replay runs",
                            "high",
                            "replay",
                            f"All runs exited the same but produced different output hashes: [{hashes}]",
                            "Stabilize log output and remove non-deterministic sources (time/random/system ordering).",
                            20,
                        )
                    )

                minimized = minimal_env(cfg.get("required_env", []))
                tmp_root_min_env = Path(tmp_dir) / "workspace-min-env"
                tmp_root_min_env.mkdir(parents=True, exist_ok=True)
                copy_workspace(root, tmp_root_min_env)
                test_min_env = run_shell(
                    resolved_cmds["test_command"],
                    cwd=tmp_root_min_env,
                    env=minimized,
                    timeout_sec=args.timeout_sec,
                )
                replay_data["test_min_env"] = {
                    "command": test_min_env["command"],
                    "exit_code": test_min_env["exit_code"],
                    "duration_sec": test_min_env["duration_sec"],
                    "workspace": str(tmp_root_min_env),
                }

                if first_run["exit_code"] == 0 and test_min_env["exit_code"] != 0:
                    issues.append(
                        issue(
                            "hidden_env_dependency",
                            "Replay depends on undeclared environment variables",
                            "high",
                            "replay",
                            f"Primary test pass, minimal-env test failed with exit {test_min_env['exit_code']}",
                            "Declare all required variables in required_env and document safe defaults.",
                            20,
                        )
                    )

            lock_snapshot_after = snapshot_lockfiles(tmp_root, expected_lockfiles)
            lock_drift = diff_lockfile_snapshots(expected_lockfiles, lock_snapshot_before, lock_snapshot_after)
            if lock_drift["created"] or lock_drift["changed"] or lock_drift["deleted"]:
                replay_data["lockfile_drift"] = lock_drift
                evidence = (
                    f"created={lock_drift['created']}, changed={lock_drift['changed']}, "
                    f"deleted={lock_drift['deleted']}"
                )
                issues.append(
                    issue(
                        "lockfile_drift",
                        "Lockfile drift detected during replay",
                        "high",
                        "replay",
                        evidence,
                        "Commit deterministic lockfile updates or stabilize dependency install commands.",
                        20,
                    )
                )
                if fail_on_lockfile_drift:
                    replay_failed = True

        replay_data["status"] = "failed" if replay_failed else "passed"

    score, sev_totals = score_issues(issues)
    mode = cfg.get("mode", "advisory")
    threshold = int(cfg.get("score_threshold", 85))
    replay_status = replay_data.get("status", "failed" if config_errors else "passed")

    exit_code = 0
    if config_errors:
        exit_code = 40
    elif replay_status == "failed":
        exit_code = 20
    elif mode == "strict" and score < threshold:
        exit_code = 30

    report = {
        "meta": {
            "schema_version": "1.1",
            "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "project_root": str(root),
            "output_dir": str(output_dir),
            "tool": "vibe-repro-guard",
        },
        "summary": {
            "mode": mode,
            "score": score,
            "score_threshold": threshold,
            "replay_status": replay_status,
            "issue_totals": sev_totals,
            "exit_code": exit_code,
        },
        "issues": issues,
        "phases": {
            "baseline": baseline,
            "contract": {
                "project_type": project_type,
                "expected_lockfiles": expected_lockfiles,
                "resolved_commands": resolved_cmds,
                "config_errors": config_errors,
            },
            "replay": replay_data,
        },
    }

    write_json(output_dir / ARTIFACT_CONTRACT, contract)
    write_json(output_dir / ARTIFACT_REPORT_JSON, report)
    write_report_markdown(output_dir / ARTIFACT_REPORT_MD, report)

    print(
        f"[reproguard] score={score} mode={mode} threshold={threshold} "
        f"replay={replay_status} exit_code={exit_code}"
    )
    print(
        f"[reproguard] artifacts: "
        f"{output_dir / ARTIFACT_CONTRACT}, {output_dir / ARTIFACT_REPORT_JSON}, {output_dir / ARTIFACT_REPORT_MD}"
    )
    if args.summary_json:
        print(json.dumps(report["summary"], ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
