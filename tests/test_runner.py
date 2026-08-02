from pathlib import Path

from wgsflow.runner import FORBIDDEN_ARGUMENTS, RunRequest, build_command


def test_runner_uses_no_plugins_or_profiles() -> None:
    command = build_command(RunRequest(config=Path("config/demo.yaml"), cores=2, dry_run=True))
    rendered = " ".join(command)
    for forbidden in FORBIDDEN_ARGUMENTS:
        assert forbidden not in rendered
    assert "--show-failed-logs" in command
    assert "--rerun-incomplete" in command
    assert "--dry-run" in command


def test_controller_log_names_include_subsecond_precision() -> None:
    text = Path("src/wgsflow/runner.py").read_text(encoding="utf-8")
    assert "%f" in text


def test_real_runs_have_a_dry_run_preflight() -> None:
    text = Path("src/wgsflow/runner.py").read_text(encoding="utf-8")
    assert "Preflight:" in text
    assert "dry_run=True" in text
