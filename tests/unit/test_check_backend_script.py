"""Shell-policy tests for ``scripts/check_backend.sh``.

The script is the single source of truth for backend commands, so its selection,
argument forwarding and exit behaviour are pinned here with a fake ``uv``/``bun``
on PATH. No test runs real pytest through the script.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_backend.sh"

FAST_MARKERS = (
    "not slow and not live_api and not live_openrouter and not e2e_real_apis "
    "and not deepeval and not network"
)
OFFLINE_MARKERS = (
    "not live_api and not live_openrouter and not e2e_real_apis and not deepeval and not network"
)


def _install_fake_tool(directory: Path, name: str, exit_code: int) -> Path:
    log = directory / f"{name}-calls.log"
    tool = directory / name
    tool.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$PWD" >> "{log}"\n'
        f'printf "%s\\n" "$@" >> "{log}"\n'
        f'printf -- "---\\n" >> "{log}"\n'
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)
    return log


def _run(
    tmp_path: Path,
    *args: str,
    tool: str = "uv",
    tool_exit: int = 0,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[tuple[str, list[str]]]]:
    log = _install_fake_tool(tmp_path, tool, tool_exit)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    env.pop("QNA_COVERAGE_FLOOR", None)
    if extra_env:
        env.update(extra_env)

    completed = subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    calls: list[tuple[str, list[str]]] = []
    if log.exists():
        for block in log.read_text(encoding="utf-8").split("---\n"):
            lines = [line for line in block.splitlines() if line]
            if lines:
                calls.append((lines[0], lines[1:]))
    return completed, calls


def test_help_lists_modes_without_running_tools(tmp_path: Path):
    completed, calls = _run(tmp_path, "help")
    assert completed.returncode == 0
    assert "Usage: bash scripts/check_backend.sh" in completed.stdout
    for mode in ("fast", "offline", "unit", "integration", "coverage", "lint", "smoke"):
        assert mode in completed.stdout
    assert calls == []


def test_fast_mode_uses_the_shared_marker_expression_and_no_coverage(tmp_path: Path):
    completed, calls = _run(tmp_path, "fast")
    assert completed.returncode == 0
    assert calls == [
        (str(REPO_ROOT), ["run", "--frozen", "python", "-m", "pytest", "-m", FAST_MARKERS])
    ]
    assert not any(argument.startswith("--cov") for argument in calls[0][1])


def test_offline_mode_includes_slow_tests(tmp_path: Path):
    _, calls = _run(tmp_path, "offline")
    assert calls[0][1][-2:] == ["-m", OFFLINE_MARKERS]


def test_unit_mode_limits_scope_and_uses_xdist(tmp_path: Path):
    _, calls = _run(tmp_path, "unit")
    argv = calls[0][1]
    assert argv[argv.index("tests/unit/")] == "tests/unit/"
    assert argv[argv.index("-n") + 1] == "auto"
    assert FAST_MARKERS in argv


def test_integration_mode_limits_scope(tmp_path: Path):
    _, calls = _run(tmp_path, "integration")
    argv = calls[0][1]
    assert argv[argv.index("tests/integration/")] == "tests/integration/"
    assert argv[-2:] == ["-m", FAST_MARKERS]


def test_coverage_mode_adds_project_coverage_and_floor(tmp_path: Path):
    _, calls = _run(tmp_path, "coverage")
    argv = calls[0][1]
    assert "--cov=src" in argv
    assert "--cov-report=term-missing:skip-covered" in argv
    assert "--cov-fail-under=80" in argv
    assert argv[-2:] != ["-m", OFFLINE_MARKERS]


def test_coverage_floor_can_be_overridden(tmp_path: Path):
    _, calls = _run(tmp_path, "coverage", extra_env={"QNA_COVERAGE_FLOOR": "90"})
    assert "--cov-fail-under=90" in calls[0][1]


def test_unknown_mode_fails_without_running_a_tool(tmp_path: Path):
    completed, calls = _run(tmp_path, "bogus")
    assert completed.returncode == 2
    assert "unknown mode: bogus" in completed.stderr
    assert calls == []


def test_extra_arguments_are_rejected_for_modes_that_take_none(tmp_path: Path):
    for mode in ("lint", "frontend-check", "frontend-test"):
        completed, calls = _run(tmp_path, mode, "--extra")
        assert completed.returncode == 2, mode
        assert calls == [], mode


def test_runner_exit_code_is_propagated(tmp_path: Path):
    completed, _ = _run(tmp_path, "fast", tool_exit=7)
    assert completed.returncode == 7


def test_pytest_arguments_are_forwarded_without_shell_resplitting(tmp_path: Path):
    _, calls = _run(tmp_path, "fast", "-k", "chunk or pdf", "tests/unit/config/test_settings.py")
    assert calls[0][1][-3:] == ["-k", "chunk or pdf", "tests/unit/config/test_settings.py"]


def test_lint_runs_read_only_checks_in_order(tmp_path: Path):
    completed, calls = _run(tmp_path, "lint")
    assert completed.returncode == 0
    assert [argv for _, argv in calls] == [
        ["run", "--frozen", "ruff", "check", "."],
        ["run", "--frozen", "ruff", "format", "--check", "."],
        ["run", "--frozen", "mypy", "src"],
        ["run", "--frozen", "lint-imports"],
        ["run", "--frozen", "bandit", "-r", "src/", "-ll"],
    ]
    flattened = [argument for _, argv in calls for argument in argv]
    assert "--fix" not in flattened
    assert "bandit-report.json" not in flattened


def test_smoke_mode_uses_the_smoke_marker(tmp_path: Path):
    _, calls = _run(tmp_path, "smoke")
    assert calls[0][1][-2:] == ["-m", "smoke"]


def test_frontend_modes_run_inside_the_frontend_package(tmp_path: Path):
    check_dir = tmp_path / "check"
    check_dir.mkdir()
    completed, calls = _run(check_dir, "frontend-check", tool="bun")
    assert completed.returncode == 0
    assert [argv for _, argv in calls] == [["run", "check"], ["run", "build"]]
    assert all(cwd.endswith(os.sep + "frontend") for cwd, _ in calls)

    test_dir = tmp_path / "test"
    test_dir.mkdir()
    completed, calls = _run(test_dir, "frontend-test", tool="bun")
    assert completed.returncode == 0
    assert [argv for _, argv in calls] == [["run", "test"]]
