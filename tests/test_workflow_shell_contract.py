import re
from pathlib import Path

ALLOWED_SHELL_ROOTS = {
    "input",
    "output",
    "params",
    "log",
    "threads",
    "wildcards",
    "resources",
}


def shell_blocks() -> list[tuple[Path, str]]:
    blocks = []
    pattern = re.compile(r'shell:\s*r?"""(.*?)"""', re.DOTALL)
    for path in sorted(Path("workflow/rules").glob("*.smk")):
        text = path.read_text(encoding="utf-8")
        blocks.extend((path, block) for block in pattern.findall(text))
    return blocks


def test_shell_blocks_use_only_supported_snakemake_names() -> None:
    placeholder = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)")
    errors = []
    for path, block in shell_blocks():
        roots = set(placeholder.findall(block))
        unsupported = roots - ALLOWED_SHELL_ROOTS
        if unsupported:
            errors.append(f"{path}: {sorted(unsupported)}")
    assert not errors, "Unsupported shell placeholders:\n" + "\n".join(errors)


def test_mvp_has_no_benchmark_directives() -> None:
    for path in sorted(Path("workflow/rules").glob("*.smk")):
        text = path.read_text(encoding="utf-8")
        assert "benchmark:" not in text, f"Benchmark directive found in {path}"
        assert "{benchmark}" not in text, f"Benchmark placeholder found in {path}"



def test_rule_directives_are_not_empty() -> None:
    directive = re.compile(r"^(\s+)(input|output|params|log|resources|benchmark):\s*$")
    for path in sorted(Path("workflow/rules").glob("*.smk")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = directive.match(line)
            if not match:
                continue
            indent = len(match.group(1))
            assert index + 1 < len(lines), f"Empty directive at {path}:{index + 1}"
            next_line = lines[index + 1]
            next_indent = len(next_line) - len(next_line.lstrip())
            assert next_line.strip() and next_indent > indent, (
                f"Empty directive at {path}:{index + 1}: {match.group(2)}"
            )


def test_multiqc_does_not_scan_global_logs() -> None:
    text = Path("workflow/rules/report.smk").read_text(encoding="utf-8")
    assert "logs/rules" not in text
    assert "rules_log_dir" not in text



def test_shell_blocks_are_valid_bash() -> None:
    import subprocess

    placeholder = re.compile(r"(?<!\{)\{[^{}]+\}")
    errors = []
    for path, block in shell_blocks():
        rendered = placeholder.sub("VALUE", block)
        result = subprocess.run(
            ["bash", "-n"],
            input=rendered,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            errors.append(f"{path}: {result.stderr.strip()}")
    assert not errors, "Invalid Bash shell blocks:\n" + "\n".join(errors)


def test_bwa_index_files_are_declared_outputs() -> None:
    text = Path("workflow/rules/alignment.smk").read_text(encoding="utf-8")
    for suffix in (".amb", ".ann", ".bwt.2bit.64", ".pac", ".0123"):
        assert suffix in text
    assert "bwa-mem2.indexed" not in text
