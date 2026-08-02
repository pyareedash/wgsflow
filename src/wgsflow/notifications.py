from __future__ import annotations

import json
import os
import smtplib
from collections import deque
from email.message import EmailMessage
from pathlib import Path

from wgsflow.config import WorkflowConfig
from wgsflow.paths import repository_root, resolve_from_root


def _tail(path: Path, lines: int = 80) -> list[str]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=lines))


def send_completion_email(
    config: WorkflowConfig,
    *,
    succeeded: bool,
    controller_log: Path,
) -> str | None:
    """Send a best-effort notification without changing the workflow exit status."""
    settings = config.notifications.email
    if not settings.enabled:
        return None

    try:
        host = os.getenv("WGSFLOW_SMTP_HOST")
        user = os.getenv("WGSFLOW_SMTP_USER")
        password = os.getenv("WGSFLOW_SMTP_PASSWORD")
        sender = os.getenv("WGSFLOW_EMAIL_FROM") or user
        port = int(os.getenv("WGSFLOW_SMTP_PORT", "587"))
        if not host or not sender or not settings.recipient:
            return "Email skipped: required SMTP environment variables are missing"

        status = "succeeded" if succeeded else "failed"
        root = repository_root(controller_log.parent)
        summary_path = resolve_from_root(config.output_dir, root) / "report" / "summary.json"
        summary = None
        if succeeded and summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                summary = None

        body = [
            f"Project: {config.project_name}",
            f"Status: {status}",
            f"Controller log: {controller_log}",
        ]
        if summary:
            for sample in summary.get("samples", []):
                body.extend(
                    (
                        "",
                        f"Sample: {sample.get('sample')}",
                        f"Mean depth: {sample.get('mean_depth')}",
                        f"Mapping rate: {sample.get('mapping_rate')}",
                        f"Small variants: {sample.get('small_variants')}",
                        f"Structural variants: {sample.get('structural_variants')}",
                    )
                )
        if not succeeded and controller_log.exists():
            body.extend(("", "Last controller-log lines:", *_tail(controller_log)))

        message = EmailMessage()
        message["Subject"] = f"WGSFlow {status}: {config.project_name}"
        message["From"] = sender
        message["To"] = settings.recipient
        message.set_content("\n".join(line.rstrip("\n") for line in body))

        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if settings.starttls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(message)
    except Exception as exc:  # Notification failures must never mask analysis status.
        return f"Email notification failed: {exc}"
    return None
