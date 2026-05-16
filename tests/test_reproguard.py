import json
import os
import platform
import reproguard
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproguard.py"
REPORT_SCHEMA = ROOT / "docs" / "reproguard.report.schema.json"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_guard(project_root: Path, extra_env=None, output_dir: Optional[Path] = None, unset_env=None):
    env = dict(os.environ)
    if unset_env:
        for key in unset_env:
            env.pop(key, None)
    if extra_env:
        env.update(extra_env)
    cmd = ["python3", str(SCRIPT), "--project-root", str(project_root)]
    if output_dir is not None:
        cmd.extend(["--output-dir", str(output_dir)])
    proc = subprocess.run(
        cmd,
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
    )
    target = output_dir if output_dir is not None else project_root
    report_path = target / "reproguard.report.json"
    assert report_path.exists(), "report json missing"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return proc, report


def resolve_schema_ref(schema: dict, ref: str) -> dict:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise AssertionError(f"unsupported schema ref: {ref}")
    return schema["$defs"][ref[len(prefix) :]]


def assert_matches_schema_subset(testcase: unittest.TestCase, value, schema_node: dict, root_schema: dict, path: str = "$"):
    if "$ref" in schema_node:
        assert_matches_schema_subset(testcase, value, resolve_schema_ref(root_schema, schema_node["$ref"]), root_schema, path)
        return

    expected_type = schema_node.get("type")
    if expected_type is not None:
        allowed_types = expected_type if isinstance(expected_type, list) else [expected_type]
        testcase.assertTrue(any(json_type_matches(value, item) for item in allowed_types), f"{path} expected {expected_type}")

    if "const" in schema_node:
        testcase.assertEqual(value, schema_node["const"], path)
    if "enum" in schema_node:
        testcase.assertIn(value, schema_node["enum"], path)
    if "minimum" in schema_node and isinstance(value, (int, float)) and not isinstance(value, bool):
        testcase.assertGreaterEqual(value, schema_node["minimum"], path)
    if "maximum" in schema_node and isinstance(value, (int, float)) and not isinstance(value, bool):
        testcase.assertLessEqual(value, schema_node["maximum"], path)

    if isinstance(value, dict):
        required = schema_node.get("required", [])
        for key in required:
            testcase.assertIn(key, value, f"{path}.{key} missing")

        properties = schema_node.get("properties", {})
        additional = schema_node.get("additionalProperties", True)
        if additional is False:
            unexpected = sorted(set(value) - set(properties))
            testcase.assertEqual(unexpected, [], f"{path} has undocumented fields")

        for key, child in value.items():
            if key in properties:
                assert_matches_schema_subset(testcase, child, properties[key], root_schema, f"{path}.{key}")
            elif isinstance(additional, dict):
                assert_matches_schema_subset(testcase, child, additional, root_schema, f"{path}.{key}")
    elif isinstance(value, list) and "items" in schema_node:
        for index, item in enumerate(value):
            assert_matches_schema_subset(testcase, item, schema_node["items"], root_schema, f"{path}[{index}]")


def json_type_matches(value, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    raise AssertionError(f"unsupported json schema type: {expected_type}")


class ReproGuardTests(unittest.TestCase):
    def test_happy_path_python_strict(self):
        with tempfile.TemporaryDirectory(prefix="rg-happy-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "build.py", "print('build ok')\n")
            write(root / "tests.py", "print('tests ok')\n")
            config = textwrap.dedent(
                f"""
                mode: strict
                score_threshold: 85
                build_command: "python3 build.py"
                test_command: "python3 tests.py"
                required_env:
                  - API_TOKEN
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root, extra_env={"API_TOKEN": "x"})
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertGreaterEqual(report["summary"]["score"], 85)
            self.assertEqual(report["summary"]["replay_status"], "passed")

    def test_missing_lockfile_strict_failure(self):
        with tempfile.TemporaryDirectory(prefix="rg-lock-") as tmp:
            root = Path(tmp)
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: strict
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 30, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("lockfile_missing", issue_ids)

    def test_python_uv_lockfile_is_recognized_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-uv-lock-") as tmp:
            root = Path(tmp)
            write(root / "pyproject.toml", "[project]\nname='demo'\nversion='0.1.0'\n")
            write(root / "uv.lock", "version = 1\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertNotIn("lockfile_missing", issue_ids)

    def test_node_bun_lockfile_is_recognized_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-bun-lock-") as tmp:
            root = Path(tmp)
            write(root / "package.json", '{"name":"demo","version":"1.0.0"}\n')
            write(root / "bun.lockb", "lock\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                """
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  node: "20.12.2"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertNotIn("lockfile_missing", issue_ids)

    def test_php_composer_lockfile_is_recognized_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-composer-lock-") as tmp:
            root = Path(tmp)
            write(root / "composer.json", '{"name":"demo/project","require":{"php":"^8.2"}}\n')
            write(root / "composer.lock", '{"_readme":["lock"]}\n')
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                """
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertNotIn("lockfile_missing", issue_ids)

    def test_php_missing_composer_lockfile_detected_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-composer-missing-") as tmp:
            root = Path(tmp)
            write(root / "composer.json", '{"name":"demo/project","require":{"php":"^8.2"}}\n')
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                """
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("lockfile_missing", issue_ids)

    def test_runtime_drift_detected(self):
        with tempfile.TemporaryDirectory(prefix="rg-runtime-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                """
                mode: strict
                score_threshold: 99
                test_command: "python3 tests.py"
                runtime:
                  python: "0.0.1"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 30, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("runtime_drift_python", issue_ids)

    def test_hidden_env_dependency_detected(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(
                root / "tests.py",
                "import os, sys\nsys.exit(0 if os.getenv('SECRET_TOKEN') else 1)\n",
            )
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root, extra_env={"SECRET_TOKEN": "set"})
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("hidden_env_dependency", issue_ids)

    def test_nondeterminism_detected(self):
        with tempfile.TemporaryDirectory(prefix="rg-nondet-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(
                root / "tests.py",
                textwrap.dedent(
                    """
                    from pathlib import Path
                    import sys

                    p = Path("state.flag")
                    if p.exists():
                        sys.exit(1)
                    p.write_text("x", encoding="utf-8")
                    sys.exit(0)
                    """
                ).strip()
                + "\n",
            )
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 20, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("nondeterministic_test_exit", issue_ids)
            self.assertNotIn("hidden_env_dependency", issue_ids)

    def test_secret_redaction_in_report(self):
        with tempfile.TemporaryDirectory(prefix="rg-redact-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(
                root / "tests.py",
                "import os\nprint(os.getenv('SUPER_SECRET_TOKEN', 'none'))\n",
            )
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 80
                replay_runs: 2
                test_command: "python3 tests.py"
                required_env:
                  - SUPER_SECRET_TOKEN
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            secret_value = "my_ultra_secret_value_123"
            proc, report = run_guard(root, extra_env={"SUPER_SECRET_TOKEN": secret_value})
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            runs = report["phases"]["replay"]["test_runs"]
            self.assertTrue(runs, "test runs missing")
            self.assertNotIn(secret_value, runs[0]["stdout"])
            self.assertIn("[REDACTED]", runs[0]["stdout"])

    def test_scan_env_usage_detects_os_environ_get(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-scan-") as tmp:
            root = Path(tmp)
            write(
                root / "app.py",
                "import os\nvalue = os.environ.get('UNDECLARED_API_TOKEN')\nprint(value)\n",
            )
            referenced = reproguard.scan_env_usage(root)
            self.assertIn("UNDECLARED_API_TOKEN", referenced)
            self.assertIn("app.py", referenced["UNDECLARED_API_TOKEN"])

    def test_scan_env_usage_detects_process_env_optional_chain(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-optional-scan-") as tmp:
            root = Path(tmp)
            write(root / "app.js", "const token = process.env?.UNDECLARED_OPTIONAL_TOKEN || '';\n")
            referenced = reproguard.scan_env_usage(root)
            self.assertIn("UNDECLARED_OPTIONAL_TOKEN", referenced)
            self.assertIn("app.js", referenced["UNDECLARED_OPTIONAL_TOKEN"])

    def test_scan_env_usage_detects_lowercase_and_mixed_case_names(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-lowercase-scan-") as tmp:
            root = Path(tmp)
            write(
                root / "app.js",
                "const dbHost = process.env.db_host || process.env?.['Mixed_Case_Key'] || '';\n",
            )
            write(root / "app.py", "import os\nvalue = os.getenv('service_token')\nprint(value)\n")
            referenced = reproguard.scan_env_usage(root)
            self.assertIn("db_host", referenced)
            self.assertIn("Mixed_Case_Key", referenced)
            self.assertIn("service_token", referenced)
            self.assertIn("app.js", referenced["db_host"])
            self.assertIn("app.py", referenced["service_token"])

    def test_scan_env_usage_detects_whitespace_variants(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-whitespace-scan-") as tmp:
            root = Path(tmp)
            write(
                root / "app.js",
                "const token = process.env ['SPACED_JS_TOKEN'] || process.env?. [ 'SPACED_OPTIONAL_TOKEN' ];\n",
            )
            write(
                root / "app.py",
                "import os\nvalue = os.getenv ('spaced_py_token') or os.environ [ 'spaced_environ_token' ]\n",
            )
            referenced = reproguard.scan_env_usage(root)
            self.assertIn("SPACED_JS_TOKEN", referenced)
            self.assertIn("SPACED_OPTIONAL_TOKEN", referenced)
            self.assertIn("spaced_py_token", referenced)
            self.assertIn("spaced_environ_token", referenced)

    def test_env_not_declared_detected_for_os_environ_get(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-not-declared-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            write(root / "app.py", "import os\n_ = os.environ.get('UNDECLARED_API_TOKEN')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("env_not_declared", issue_ids)

    def test_env_not_declared_detected_for_process_env_optional_chain(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-optional-not-declared-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            write(root / "app.js", "const token = process.env?.UNDECLARED_OPTIONAL_TOKEN || '';\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("env_not_declared", issue_ids)

    def test_env_not_declared_detected_for_lowercase_os_getenv(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-lowercase-not-declared-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            write(root / "app.py", "import os\n_ = os.getenv('service_token')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("env_not_declared", issue_ids)
            issue_evidence = "\n".join(x["evidence"] for x in report["issues"])
            self.assertIn("service_token", issue_evidence)

    def test_env_not_declared_detected_for_whitespace_variants(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-whitespace-not-declared-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            write(
                root / "app.js",
                "const token = process.env ['SPACED_JS_TOKEN'] || process.env?. [ 'SPACED_OPTIONAL_TOKEN' ];\n",
            )
            write(root / "app.py", "import os\n_ = os.getenv ('spaced_py_token')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("env_not_declared", issue_ids)
            issue_evidence = "\n".join(x["evidence"] for x in report["issues"])
            self.assertIn("SPACED_JS_TOKEN", issue_evidence)
            self.assertIn("spaced_py_token", issue_evidence)

    def test_lockfile_drift_detected(self):
        with tempfile.TemporaryDirectory(prefix="rg-lock-drift-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "alpha==1.0.0\n")
            write(
                root / "tests.py",
                textwrap.dedent(
                    """
                    from pathlib import Path
                    p = Path("requirements.txt")
                    p.write_text(p.read_text(encoding="utf-8") + "beta==2.0.0\\n", encoding="utf-8")
                    print("ok")
                    """
                ).strip()
                + "\n",
            )
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                replay_runs: 2
                fail_on_lockfile_drift: true
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 20, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("lockfile_drift", issue_ids)

    def test_nondeterministic_output_detected(self):
        with tempfile.TemporaryDirectory(prefix="rg-output-drift-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "import time\nprint(time.time())\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                replay_runs: 3
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 20, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("nondeterministic_test_output", issue_ids)
            self.assertEqual(len(report["phases"]["replay"]["test_runs"]), 3)

    def test_output_dir_writes_artifacts(self):
        with tempfile.TemporaryDirectory(prefix="rg-outdir-") as tmp:
            root = Path(tmp)
            outdir = root / "artifacts"
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root, output_dir=outdir)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual(report["meta"]["output_dir"], str(outdir.resolve()))
            self.assertTrue((outdir / "reproguard.contract.json").exists())
            self.assertTrue((outdir / "reproguard.report.md").exists())

    def test_report_schema_documentation_matches_emitted_report(self):
        with tempfile.TemporaryDirectory(prefix="rg-report-schema-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")

            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

            schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
            assert_matches_schema_subset(self, report, schema, schema)
            self.assertEqual(report["meta"]["schema_version"], "1.1")
            self.assertEqual(
                schema["properties"]["meta"]["properties"]["schema_version"]["const"],
                report["meta"]["schema_version"],
            )

    def test_default_python_discovery_with_zero_tests_is_reported(self):
        with tempfile.TemporaryDirectory(prefix="rg-zero-tests-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 20, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("test_runs_zero", issue_ids)

    def test_zero_test_signal_detector_supports_pytest_output(self):
        signal = reproguard.detect_zero_test_signal(
            {
                "stdout": "================== test session starts ==================\ncollected 0 items\n",
                "stderr": "",
            }
        )
        self.assertEqual(signal, "python-pytest")

    def test_zero_test_signal_detector_supports_pytest_no_tests_ran_summary(self):
        signal = reproguard.detect_zero_test_signal(
            {
                "stdout": "========================= no tests ran in 0.10s =========================\n",
                "stderr": "",
            }
        )
        self.assertEqual(signal, "python-pytest")

    def test_zero_test_signal_detector_supports_vitest_no_files_output(self):
        signal = reproguard.detect_zero_test_signal(
            {
                "stdout": "",
                "stderr": "No test files found, exiting with code 0\n",
            }
        )
        self.assertEqual(signal, "vitest")

    def test_zero_test_signal_detector_supports_mocha_zero_passing_output(self):
        signal = reproguard.detect_zero_test_signal(
            {
                "stdout": "  0 passing (6ms)\n",
                "stderr": "",
            }
        )
        self.assertEqual(signal, "mocha")

    def test_required_env_missing_values_detected(self):
        with tempfile.TemporaryDirectory(prefix="rg-required-env-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: strict
                score_threshold: 95
                test_command: "python3 tests.py"
                required_env:
                  - MUST_EXIST_TOKEN
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root, unset_env=["MUST_EXIST_TOKEN"])
            self.assertEqual(proc.returncode, 30, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("required_env_missing_values", issue_ids)

    def test_required_env_empty_value_detected(self):
        with tempfile.TemporaryDirectory(prefix="rg-required-env-empty-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: strict
                score_threshold: 95
                test_command: "python3 tests.py"
                required_env:
                  - MUST_EXIST_TOKEN
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root, extra_env={"MUST_EXIST_TOKEN": ""})
            self.assertEqual(proc.returncode, 30, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("required_env_missing_values", issue_ids)

    def test_lockfile_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory(prefix="rg-lock-traversal-") as tmp:
            root = Path(tmp)
            write(root / "tests.py", "print('ok')\n")
            write(root.parent / "outside.lock", "x\n")
            config = textwrap.dedent(
                f"""
                mode: strict
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - ../outside.lock
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 40, proc.stderr + proc.stdout)
            errors = report["phases"]["contract"]["config_errors"]
            self.assertTrue(any("lockfiles entries must be relative paths" in msg for msg in errors))
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("config_invalid", issue_ids)

    def test_lockfile_windows_style_paths_rejected(self):
        with tempfile.TemporaryDirectory(prefix="rg-lock-windows-paths-") as tmp:
            root = Path(tmp)
            write(root / "tests.py", "print('ok')\n")
            invalid_paths = [
                "..\\outside.lock",
                "C:\\temp\\outside.lock",
                "\\\\server\\share\\outside.lock",
            ]
            for lock_value in invalid_paths:
                with self.subTest(lock_value=lock_value):
                    config = textwrap.dedent(
                        f"""
                        mode: strict
                        score_threshold: 95
                        test_command: "python3 tests.py"
                        runtime:
                          python: "{platform.python_version()}"
                        lockfiles:
                          - "{lock_value}"
                        """
                    ).strip()
                    write(root / "reproguard.yaml", config + "\n")
                    proc, report = run_guard(root)
                    self.assertEqual(proc.returncode, 40, proc.stderr + proc.stdout)
                    errors = report["phases"]["contract"]["config_errors"]
                    self.assertTrue(any("lockfiles entries must be relative paths" in msg for msg in errors))
                    issue_ids = {x["id"] for x in report["issues"]}
                    self.assertIn("config_invalid", issue_ids)

    def test_runtime_check_supports_version_from_stderr(self):
        cfg = {"runtime": {"python": "3.9.6"}}
        project_type = {"python": True, "node": False}
        versions = {
            "python": {
                "exit_code": 0,
                "stdout": "",
                "stderr": "Python 3.9.6",
            }
        }
        issues = []
        reproguard.apply_runtime_checks(cfg, project_type, versions, issues)
        issue_ids = {x["id"] for x in issues}
        self.assertNotIn("runtime_drift_python", issue_ids)

    def test_typescript_test_file_detected_for_nondeterminism(self):
        with tempfile.TemporaryDirectory(prefix="rg-ts-nondet-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            write(root / "app.test.ts", "test('x', () => { const t = Date.now(); });\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("nondeterministic_test_signals", issue_ids)

    def test_rust_cargo_lockfile_recognized_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-cargo-lock-") as tmp:
            root = Path(tmp)
            write(root / "Cargo.toml", "[package]\nname=\"demo\"\nversion=\"0.1.0\"\n")
            write(root / "Cargo.lock", "version = 3\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertNotIn("lockfile_missing", issue_ids)

    def test_rust_missing_cargo_lockfile_detected_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-cargo-missing-") as tmp:
            root = Path(tmp)
            write(root / "Cargo.toml", "[package]\nname=\"demo\"\nversion=\"0.1.0\"\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("lockfile_missing", issue_ids)

    def test_go_sum_lockfile_recognized_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-go-sum-") as tmp:
            root = Path(tmp)
            write(root / "go.mod", "module demo\n\ngo 1.22\n")
            write(root / "go.sum", "example.com/dep v1.0.0 h1:abc\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertNotIn("lockfile_missing", issue_ids)

    def test_go_missing_sum_lockfile_detected_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-go-missing-") as tmp:
            root = Path(tmp)
            write(root / "go.mod", "module demo\n\ngo 1.22\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("lockfile_missing", issue_ids)

    def test_ruby_gemfile_lock_recognized_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-ruby-lock-") as tmp:
            root = Path(tmp)
            write(root / "Gemfile", "source 'https://rubygems.org'\n")
            write(root / "Gemfile.lock", "DEPENDENCIES\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertNotIn("lockfile_missing", issue_ids)

    def test_ruby_missing_gemfile_lock_detected_by_default_policy(self):
        with tempfile.TemporaryDirectory(prefix="rg-ruby-missing-") as tmp:
            root = Path(tmp)
            write(root / "Gemfile", "source 'https://rubygems.org'\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("lockfile_missing", issue_ids)

    def test_scan_env_usage_detects_go_rust_ruby_patterns(self):
        with tempfile.TemporaryDirectory(prefix="rg-env-multi-lang-") as tmp:
            root = Path(tmp)
            write(root / "main.go", 'package main\nimport "os"\nvar x = os.Getenv("GO_TOKEN")\n')
            write(
                root / "main.rs",
                'use std::env;\nfn f() { let _v = env::var("RUST_TOKEN").unwrap(); }\n',
            )
            write(
                root / "main.rb",
                "puts ENV['RUBY_TOKEN']\nval = ENV.fetch('RUBY_FETCH_TOKEN')\n",
            )
            referenced = reproguard.scan_env_usage(root)
            self.assertIn("GO_TOKEN", referenced)
            self.assertIn("RUST_TOKEN", referenced)
            self.assertIn("RUBY_TOKEN", referenced)
            self.assertIn("RUBY_FETCH_TOKEN", referenced)

    def test_markdown_report_includes_issue_totals(self):
        with tempfile.TemporaryDirectory(prefix="rg-md-totals-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            md = (root / "reproguard.report.md").read_text(encoding="utf-8")
            self.assertIn("Issue totals:", md)
            self.assertIn("critical=", md)
            self.assertIn("high=", md)
            self.assertIn("medium=", md)
            self.assertIn("low=", md)

    def test_zero_test_signal_detector_supports_go_test_no_files(self):
        signal = reproguard.detect_zero_test_signal(
            {
                "stdout": "?       example.com/demo        [no test files]\n",
                "stderr": "",
            }
        )
        self.assertEqual(signal, "go-test")

    def test_zero_test_signal_detector_supports_cargo_test_running_zero(self):
        signal = reproguard.detect_zero_test_signal(
            {
                "stdout": "running 0 tests\n\ntest result: ok. 0 passed; 0 failed\n",
                "stderr": "",
            }
        )
        self.assertEqual(signal, "cargo-test")

    def test_zero_test_signal_detector_supports_rspec_zero_examples(self):
        signal = reproguard.detect_zero_test_signal(
            {
                "stdout": "Finished in 0.001 seconds\n0 examples, 0 failures\n",
                "stderr": "",
            }
        )
        self.assertEqual(signal, "rspec")

    def test_zero_test_signal_detector_supports_phpunit_no_tests_executed(self):
        signal = reproguard.detect_zero_test_signal(
            {
                "stdout": "No tests executed!\n",
                "stderr": "",
            }
        )
        self.assertEqual(signal, "phpunit")

    def test_rust_runtime_drift_detected_via_alias_mapping(self):
        cfg = {"runtime": {"rust": "1.78.0"}}
        project_type = {"python": False, "node": False, "rust": True}
        versions = {
            "rustc": {
                "exit_code": 0,
                "stdout": "rustc 1.79.0 (abc123 2024-06-13)",
                "stderr": "",
            }
        }
        issues = []
        reproguard.apply_runtime_checks(cfg, project_type, versions, issues)
        issue_ids = {x["id"] for x in issues}
        self.assertIn("runtime_drift_rust", issue_ids)

    def test_init_generates_config_for_python_project(self):
        with tempfile.TemporaryDirectory(prefix="rg-init-py-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "alpha==1.0\n")
            write(root / "app.py", "import os\nv = os.getenv('DEMO_TOKEN')\n")
            proc = subprocess.run(
                ["python3", str(SCRIPT), "init", "--project-root", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            cfg_path = root / "reproguard.yaml"
            self.assertTrue(cfg_path.exists())
            text = cfg_path.read_text(encoding="utf-8")
            self.assertIn("mode: advisory", text)
            self.assertIn("test_command:", text)
            self.assertIn("requirements.txt", text)
            self.assertIn("DEMO_TOKEN", text)
            # The generated config should produce a parseable load
            cfg, errors = reproguard.load_config(cfg_path)
            self.assertEqual(errors, [], f"unexpected config errors: {errors}")
            self.assertEqual(cfg["mode"], "advisory")

    def test_init_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory(prefix="rg-init-existing-") as tmp:
            root = Path(tmp)
            write(root / "reproguard.yaml", "mode: strict\n")
            proc = subprocess.run(
                ["python3", str(SCRIPT), "init", "--project-root", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 41, proc.stderr + proc.stdout)
            self.assertEqual(
                (root / "reproguard.yaml").read_text(encoding="utf-8"),
                "mode: strict\n",
            )

    def test_init_with_force_overwrites(self):
        with tempfile.TemporaryDirectory(prefix="rg-init-force-") as tmp:
            root = Path(tmp)
            write(root / "reproguard.yaml", "mode: strict\n")
            write(root / "package.json", '{"name":"demo","scripts":{"test":"echo ok"}}\n')
            proc = subprocess.run(
                ["python3", str(SCRIPT), "init", "--project-root", str(root), "--force"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = (root / "reproguard.yaml").read_text(encoding="utf-8")
            self.assertIn("npm test", text)
            self.assertNotEqual(text, "mode: strict\n")

    def test_zero_test_signal_wins_over_generic_replay_failure(self):
        # Reproduces a real CPython 3.12.x regression: `unittest discover`
        # returns exit code 5 (not 0) when zero tests are collected. The
        # zero-test signal must still be classified as `test_runs_zero`,
        # not the generic `replay_test_failed`.
        with tempfile.TemporaryDirectory(prefix="rg-zero-nonzero-exit-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(
                root / "fake_test_runner.sh",
                "#!/usr/bin/env bash\necho 'Ran 0 tests in 0.000s'\nexit 5\n",
            )
            os.chmod(root / "fake_test_runner.sh", 0o755)
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "bash fake_test_runner.sh"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 20, proc.stderr + proc.stdout)
            issue_ids = {x["id"] for x in report["issues"]}
            self.assertIn("test_runs_zero", issue_ids)
            self.assertNotIn("replay_test_failed", issue_ids)

    def test_version_flag_prints_version(self):
        proc = subprocess.run(
            ["python3", str(SCRIPT), "--version"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        combined = proc.stdout + proc.stderr
        self.assertIn("reproguard", combined.lower())
        self.assertIn(reproguard.__version__, combined)

    def test_explain_known_issue_returns_zero_and_describes(self):
        proc = subprocess.run(
            ["python3", str(SCRIPT), "explain", "lockfile_drift"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("lockfile_drift", proc.stdout)
        self.assertIn("WHAT IT MEANS", proc.stdout)
        self.assertIn("HOW TO FIX", proc.stdout)

    def test_explain_runtime_pattern_resolves_via_prefix(self):
        proc = subprocess.run(
            ["python3", str(SCRIPT), "explain", "runtime_drift_python"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("runtime_drift_python", proc.stdout)
        self.assertIn("python", proc.stdout.lower())

    def test_explain_unknown_issue_returns_42(self):
        proc = subprocess.run(
            ["python3", str(SCRIPT), "explain", "totally_made_up_id"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 42, proc.stderr + proc.stdout)
        self.assertIn("Unknown issue ID", proc.stdout)

    def test_explain_list_lists_all_known_ids(self):
        proc = subprocess.run(
            ["python3", str(SCRIPT), "explain", "--list"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        for known in ["lockfile_drift", "hidden_env_dependency", "test_runs_zero", "nondeterministic_test_exit"]:
            self.assertIn(known, proc.stdout)

    def test_sarif_flag_writes_well_formed_artifact(self):
        with tempfile.TemporaryDirectory(prefix="rg-sarif-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: advisory
                score_threshold: 85
                test_command: "python3 tests.py"
                runtime:
                  python: "{platform.python_version()}"
                lockfiles:
                  - requirements.txt
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc = subprocess.run(
                ["python3", str(SCRIPT), "--project-root", str(root), "--sarif"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            sarif_path = root / "reproguard.report.sarif.json"
            self.assertTrue(sarif_path.exists(), "SARIF artifact missing")
            sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
            self.assertEqual(sarif["version"], "2.1.0")
            self.assertEqual(len(sarif["runs"]), 1)
            run = sarif["runs"][0]
            self.assertEqual(run["tool"]["driver"]["name"], "vibe-repro-guard")
            self.assertEqual(run["tool"]["driver"]["version"], reproguard.__version__)
            self.assertIn("results", run)
            self.assertIn("rules", run["tool"]["driver"])

    def test_sarif_results_contain_issue_metadata(self):
        with tempfile.TemporaryDirectory(prefix="rg-sarif-issues-") as tmp:
            root = Path(tmp)
            # Intentionally omit lockfile so we get a `lockfile_missing` issue
            # and verify it appears in SARIF with severity mapped to "error".
            write(root / "package.json", '{"name":"demo"}\n')
            write(root / "tests.py", "print('ok')\n")
            config = textwrap.dedent(
                f"""
                mode: strict
                score_threshold: 95
                test_command: "python3 tests.py"
                runtime:
                  node: "20.12.2"
                lockfiles:
                  - package-lock.json
                """
            ).strip()
            write(root / "reproguard.yaml", config + "\n")
            proc = subprocess.run(
                ["python3", str(SCRIPT), "--project-root", str(root), "--sarif"],
                capture_output=True,
                text=True,
            )
            # strict + missing lockfile + runtime drift expected to fail policy
            self.assertNotEqual(proc.returncode, 40, proc.stderr + proc.stdout)
            sarif = json.loads((root / "reproguard.report.sarif.json").read_text(encoding="utf-8"))
            rule_ids = {r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
            result_rule_ids = {r["ruleId"] for r in sarif["runs"][0]["results"]}
            self.assertIn("lockfile_missing", rule_ids)
            self.assertIn("lockfile_missing", result_rule_ids)
            for result in sarif["runs"][0]["results"]:
                if result["ruleId"] == "lockfile_missing":
                    self.assertEqual(result["level"], "error")

    def test_lookup_explanation_returns_none_for_unknown(self):
        self.assertIsNone(reproguard.lookup_explanation("nope_not_a_real_id"))

    def test_lookup_explanation_resolves_runtime_prefix(self):
        info = reproguard.lookup_explanation("runtime_not_pinned_go")
        self.assertIsNotNone(info)
        assert info is not None  # for type narrowing
        self.assertEqual(info["severity"], "high")
        self.assertEqual(info["deduction"], 20)
        self.assertIn("go", info["title"].lower())

    def test_init_generates_runnable_config_end_to_end(self):
        with tempfile.TemporaryDirectory(prefix="rg-init-e2e-") as tmp:
            root = Path(tmp)
            write(root / "requirements.txt", "# lock marker\n")
            write(root / "tests.py", "print('ok')\n")
            init_proc = subprocess.run(
                ["python3", str(SCRIPT), "init", "--project-root", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_proc.returncode, 0, init_proc.stderr + init_proc.stdout)
            cfg_text = (root / "reproguard.yaml").read_text(encoding="utf-8")
            # Force a test command that we know runs successfully on any machine
            cfg_text = cfg_text.replace(
                "test_command: \"python3 -m unittest discover\"",
                "test_command: \"python3 tests.py\"",
            )
            (root / "reproguard.yaml").write_text(cfg_text, encoding="utf-8")
            proc, report = run_guard(root)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual(report["summary"]["replay_status"], "passed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
