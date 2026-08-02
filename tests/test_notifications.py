from pathlib import Path

from wgsflow.config import WorkflowConfig
from wgsflow.notifications import send_completion_email


def test_invalid_smtp_configuration_never_raises(monkeypatch, tmp_path: Path) -> None:
    config = WorkflowConfig.model_validate(
        {
            "project_name": "test",
            "output_dir": "results/test",
            "samples": "config/demo.samples.tsv",
            "reference": "resources/demo/reference.fa",
            "notifications": {
                "email": {
                    "enabled": True,
                    "recipient": "test@example.org",
                }
            },
        }
    )
    monkeypatch.setenv("WGSFLOW_SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("WGSFLOW_EMAIL_FROM", "wgsflow@example.org")
    monkeypatch.setenv("WGSFLOW_SMTP_PORT", "not-an-integer")
    warning = send_completion_email(
        config,
        succeeded=False,
        controller_log=tmp_path / "missing.log",
    )
    assert warning is not None
    assert "failed" in warning.lower()
