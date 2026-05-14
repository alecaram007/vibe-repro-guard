import json
import os
import platform
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reproguard.py"


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
