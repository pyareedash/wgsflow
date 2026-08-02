from __future__ import annotations

import re
from pathlib import Path

_ALLOWED_SHELL_ROOTS = {
    "input",
    "output",
    "params",
    "log",
    "threads",
    "wildcards",
    "resources",
}
_SHELL_BLOCK = re.compile(r'shell:\s*r?"""(.*?)"""', re.DOTALL)
_PLACEHOLDER = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)")
_DIRECTIVE = re.compile(r"^(\s+)(input|output|params|log|resources|benchmark):\s*$")


def validate_workflow_sources(root: Path) -> None:
    """Reject common Snakefile contract errors before invoking Snakemake."""
    errors: list[str] = []
    rules_dir = root / "workflow" / "rules"

    for path in sorted(rules_dir.glob("*.smk")):
        text = path.read_text(encoding="utf-8")

        if "benchmark:" in text or "{benchmark}" in text:
            errors.append(f"{path}: benchmark plumbing is intentionally disabled in the MVP")

        for block in _SHELL_BLOCK.findall(text):
            unsupported = set(_PLACEHOLDER.findall(block)) - _ALLOWED_SHELL_ROOTS
            if unsupported:
                names = ", ".join(sorted(unsupported))
                errors.append(f"{path}: unsupported shell placeholder root(s): {names}")

        lines = text.splitlines()
        for index, line in enumerate(lines):
            match = _DIRECTIVE.match(line)
            if not match:
                continue
            indent = len(match.group(1))
            if index + 1 >= len(lines):
                errors.append(f"{path}:{index + 1}: empty {match.group(2)} directive")
                continue
            next_line = lines[index + 1]
            next_indent = len(next_line) - len(next_line.lstrip())
            if not next_line.strip() or next_indent <= indent:
                errors.append(f"{path}:{index + 1}: empty {match.group(2)} directive")

    if errors:
        rendered = "\n".join(f"  - {error}" for error in errors)
        raise ValueError(f"Workflow source validation failed:\n{rendered}")
