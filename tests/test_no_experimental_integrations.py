from pathlib import Path


def test_workflow_has_no_custom_plugins_or_hooks() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("workflow").rglob("*")
        if path.is_file() and path.suffix in {"", ".smk", ".py"}
    ).lower()
    forbidden = (
        "snakemake_logger_plugin",
        "onstart:",
        "onsuccess:",
        "onerror:",
        "--logger",
        "apptainer",
        "deepvariant",
        "jbrowse",
        "fastapi",
    )
    for token in forbidden:
        assert token not in text


def test_manifests_have_no_plugin_packages() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (Path("pixi.toml"), Path("pyproject.toml"))
    ).lower()
    for token in (
        "snakemake-logger-plugin",
        "snakemake-executor-plugin",
        "snakemake-storage-plugin",
        "snakemake-reporter-plugin",
    ):
        assert token not in text


def test_structural_variant_path_is_not_conditionally_removed() -> None:
    text = Path("workflow/Snakefile").read_text(encoding="utf-8")
    text += Path("workflow/rules/variants.smk").read_text(encoding="utf-8")
    assert "SV_ENABLED" not in text

