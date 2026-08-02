from pathlib import Path

import pytest

from wgsflow.config import load_config, load_samples, validate_inputs


def test_demo_config_parses() -> None:
    config = load_config(Path("config/demo.yaml"))
    assert config.project_name
    assert config.structural_variants.min_quality == 20


def test_demo_samples_parse() -> None:
    samples = load_samples(Path("config/demo.samples.tsv"))
    assert [sample.sample for sample in samples] == ["demo"]


def test_bundled_configs_use_distinct_output_directories() -> None:
    demo = load_config(Path("config/demo.yaml"))
    quickstart = load_config(Path("config/quickstart.yaml"))
    assert demo.output_dir != quickstart.output_dir


def test_sample_sheet_requires_expected_columns(tmp_path: Path) -> None:
    sheet = tmp_path / "samples.tsv"
    sheet.write_text("sample\tread1\nS1\ta.fastq.gz\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_samples(sheet)


def test_output_directory_must_be_under_results(tmp_path: Path) -> None:
    # Build a minimal repository so this test reaches output-path validation.
    root = tmp_path / "repo"
    (root / "workflow" / "rules").mkdir(parents=True)
    (root / "workflow" / "Snakefile").write_text("rule all:\n    input: []\n")
    (root / "config").mkdir()
    (root / "resources").mkdir()
    (root / "config" / "samples.tsv").write_text(
        "sample\tread1\tread2\nS1\treads_R1.fastq.gz\treads_R2.fastq.gz\n",
        encoding="utf-8",
    )
    config = root / "config" / "bad.yaml"
    config.write_text(
        "project_name: bad\n"
        "output_dir: .\n"
        "samples: config/samples.tsv\n"
        "reference: resources/reference.fa\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="under results"):
        validate_inputs(config, require_files=False)
