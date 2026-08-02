from __future__ import annotations

import http.server
import json
import shutil
import socketserver
import webbrowser
from functools import partial
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from wgsflow import __version__
from wgsflow.config import validate_inputs
from wgsflow.data import create_quickstart_dataset, create_synthetic_dataset, default_data_dir
from wgsflow.paths import repository_root, resolve_from_root
from wgsflow.runner import RunRequest, create_snakemake_report, run_workflow

app = typer.Typer(no_args_is_help=True, help="Dependable FASTQ-to-variants WGS workflow.")
data_app = typer.Typer(no_args_is_help=True, help="Prepare public or synthetic test data.")
app.add_typer(data_app, name="data")
console = Console()
DEFAULT_CONFIG = Path("config/demo.yaml")


@app.callback()
def callback() -> None:
    """WGSFlow MVP."""


@app.command()
def version() -> None:
    console.print(__version__)


@app.command()
def validate(
    config: Annotated[Path, typer.Option("--config", "-c", exists=True, dir_okay=False)] = DEFAULT_CONFIG,
) -> None:
    workflow, samples = validate_inputs(config)
    console.print(
        f"[green]Valid configuration:[/green] {workflow.project_name}; "
        f"{len(samples)} sample(s)"
    )


@app.command()
def doctor(
    config: Annotated[Path, typer.Option("--config", "-c", exists=True, dir_okay=False)] = DEFAULT_CONFIG,
) -> None:
    root = repository_root()
    tools = (
        "snakemake",
        "fastqc",
        "fastp",
        "bwa-mem2",
        "samtools",
        "bcftools",
        "delly",
        "mosdepth",
        "multiqc",
    )
    table = Table(title="WGSFlow doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Location")
    missing = False
    for tool in tools:
        location = shutil.which(tool)
        missing |= location is None
        table.add_row(tool, "OK" if location else "MISSING", location or "-")
    console.print(table)

    try:
        validate_inputs(config)
        console.print("[green]Configuration and inputs are valid.[/green]")
    except Exception as exc:
        console.print(f"[red]Input validation failed:[/red] {exc}")
        missing = True

    if str(root).startswith("/mnt/"):
        console.print(
            "[yellow]WSL performance warning:[/yellow] the repository is under /mnt/. "
            "BAM sorting and filesystem-heavy steps are usually faster under ~/projects/."
        )
    if missing:
        raise typer.Exit(1)


@app.command("dry-run")
def dry_run(
    config: Annotated[Path, typer.Option("--config", "-c", exists=True, dir_okay=False)] = DEFAULT_CONFIG,
    cores: Annotated[int, typer.Option("--cores", "-j", min=1)] = 4,
) -> None:
    validate_inputs(config)
    code = run_workflow(RunRequest(config=config, cores=cores, dry_run=True))
    if code:
        raise typer.Exit(code)


@app.command()
def run(
    config: Annotated[Path, typer.Option("--config", "-c", exists=True, dir_okay=False)] = DEFAULT_CONFIG,
    cores: Annotated[int, typer.Option("--cores", "-j", min=1)] = 4,
    target: Annotated[list[str] | None, typer.Option("--target")] = None,
    no_report: Annotated[bool, typer.Option("--no-report")] = False,
) -> None:
    validate_inputs(config)
    code = run_workflow(
        RunRequest(config=config, cores=cores, targets=tuple(target or ())),
        create_report=not no_report,
    )
    if code:
        raise typer.Exit(code)


@app.command()
def report(
    config: Annotated[Path, typer.Option("--config", "-c", exists=True, dir_okay=False)] = DEFAULT_CONFIG,
) -> None:
    validate_inputs(config)
    error = create_snakemake_report(config)
    if error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1)
    console.print("[green]Snakemake report created.[/green]")


@app.command()
def status(
    config: Annotated[Path, typer.Option("--config", "-c", exists=True, dir_okay=False)] = DEFAULT_CONFIG,
) -> None:
    """Show the latest completed sample summary."""
    root = repository_root()
    workflow, _ = validate_inputs(config, require_files=False)
    summary_path = resolve_from_root(workflow.output_dir, root) / "report" / "summary.json"
    if not summary_path.exists():
        raise typer.BadParameter("No completed summary found; run the workflow first")
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    table = Table(title=payload.get("project", workflow.project_name))
    for column in ("Sample", "Depth", "Mapped %", "Small variants", "SVs"):
        table.add_column(column)
    for sample in payload.get("samples", []):
        depth = sample.get("mean_depth")
        mapped = sample.get("mapping_rate")
        table.add_row(
            str(sample.get("sample")),
            f"{depth:.2f}x" if isinstance(depth, (int, float)) else "NA",
            f"{mapped:.2f}%" if isinstance(mapped, (int, float)) else "NA",
            str(sample.get("small_variants", 0)),
            str(sample.get("structural_variants", 0)),
        )
    console.print(table)


@app.command()
def serve(
    config: Annotated[Path, typer.Option("--config", "-c", exists=True, dir_okay=False)] = DEFAULT_CONFIG,
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8000,
    open_browser: Annotated[bool, typer.Option("--open/--no-open")] = False,
) -> None:
    root = repository_root()
    workflow, _ = validate_inputs(config, require_files=False)
    output_dir = resolve_from_root(workflow.output_dir, root)
    dashboard = output_dir / "report" / "dashboard.html"
    if not dashboard.exists():
        raise typer.BadParameter(f"Run the workflow first; {dashboard} is missing")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(output_dir))
    url = f"http://127.0.0.1:{port}/report/dashboard.html"
    console.print(f"Serving results at [bold]{url}[/bold]. Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            console.print("\nStopped.")


@app.command()
def clean(
    config: Annotated[Path, typer.Option("--config", "-c", exists=True, dir_okay=False)] = DEFAULT_CONFIG,
    yes: Annotated[bool, typer.Option("--yes")] = False,
    data: Annotated[bool, typer.Option("--data", help="Also remove generated/downloaded data.")] = False,
) -> None:
    root = repository_root()
    workflow, _ = validate_inputs(config, require_files=False)
    if not yes and not typer.confirm("Delete outputs, logs, and Snakemake metadata?"):
        raise typer.Abort()
    run_key = Path(workflow.output_dir).name or "wgsflow"
    targets = [
        resolve_from_root(workflow.output_dir, root),
        root / "logs" / run_key,
        root / ".snakemake",
    ]
    if data:
        targets.extend((root / "resources" / "demo", root / "resources" / "quickstart"))
    for path in targets:
        if path.exists():
            shutil.rmtree(path)
            console.print(f"Removed {path}")


@data_app.command("synthetic")
def synthetic(
    force: Annotated[bool, typer.Option("--force")] = False,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    destination = output or default_data_dir("demo")
    create_synthetic_dataset(destination, force=force)
    console.print(f"[green]Created synthetic truth dataset:[/green] {destination}")


@data_app.command("quickstart")
def quickstart(
    force: Annotated[bool, typer.Option("--force")] = False,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    destination = output or default_data_dir("quickstart")
    if shutil.which("samtools") is None:
        raise typer.BadParameter("samtools is required; run through `pixi run`")
    create_quickstart_dataset(destination, force=force)
    console.print(f"[green]Created NA12878 quick-start FASTQs:[/green] {destination}")


if __name__ == "__main__":
    app()
