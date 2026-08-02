from __future__ import annotations

import datetime as dt
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from wgsflow.config import load_config
from wgsflow.notifications import send_completion_email
from wgsflow.paths import repository_root, resolve_from_root

console = Console()


@dataclass(frozen=True)
class RunRequest:
    config: Path
    cores: int = 4
    targets: tuple[str, ...] = ()
    dry_run: bool = False


FORBIDDEN_ARGUMENTS = (
    "--logger",
    "--workflow-profile",
    "--executor",
    "--software-deployment-method",
    "--default-storage-provider",
)


def build_command(request: RunRequest) -> list[str]:
    root = repository_root(request.config.parent)
    command = [
        "snakemake",
        "--snakefile",
        str(root / "workflow" / "Snakefile"),
        "--configfile",
        str(request.config.resolve()),
        "--cores",
        str(request.cores),
        "--printshellcmds",
        "--show-failed-logs",
        "--rerun-incomplete",
        "--latency-wait",
        "30",
        "--nocolor",
    ]
    if request.dry_run:
        command.append("--dry-run")
    command.extend(request.targets)
    return command


def run_workflow(request: RunRequest, *, create_report: bool = True) -> int:
    root = repository_root(request.config.parent)
    config = load_config(request.config)
    logs_dir = root / "logs" / "runs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    controller_log = logs_dir / f"{stamp}.log"
    command = build_command(request)

    if not request.dry_run:
        preflight = build_command(
            RunRequest(
                config=request.config,
                cores=request.cores,
                targets=request.targets,
                dry_run=True,
            )
        )
        console.print("[bold cyan]Preflight:[/bold cyan] validating the complete DAG")
        check = subprocess.run(
            preflight,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if check.returncode:
            controller_log.write_text(check.stdout + check.stderr, encoding="utf-8")
            console.print(check.stdout, end="")
            console.print(check.stderr, end="")
            console.print(f"[bold red]Preflight failed.[/bold red] Log: {controller_log}")
            return check.returncode

    console.print(f"[bold cyan]Command:[/bold cyan] {shlex.join(command)}")
    with controller_log.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_handle.write(line)
            log_handle.flush()
        return_code = process.wait()

    if not request.dry_run and return_code == 0 and create_report:
        report_error = create_snakemake_report(request.config)
        if report_error:
            console.print(f"[yellow]{report_error}[/yellow]")

    if not request.dry_run:
        notice = send_completion_email(
            config,
            succeeded=return_code == 0,
            controller_log=controller_log,
        )
        if notice:
            console.print(f"[yellow]{notice}[/yellow]")

    if return_code == 0:
        console.print(f"[bold green]Completed.[/bold green] Log: {controller_log}")
    else:
        console.print(f"[bold red]Failed.[/bold red] Log: {controller_log}")
    return return_code


def create_snakemake_report(config_path: Path) -> str | None:
    root = repository_root(config_path.parent)
    config = load_config(config_path)
    output_dir = resolve_from_root(config.output_dir, root)
    report_path = output_dir / "report" / "snakemake-report.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "snakemake",
        "--snakefile",
        str(root / "workflow" / "Snakefile"),
        "--configfile",
        str(config_path.resolve()),
        "--cores",
        "1",
        "--report",
        str(report_path),
        "--nocolor",
    ]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1:]
        return f"Analysis succeeded, but Snakemake report generation failed: {' '.join(detail)}"
    return None
