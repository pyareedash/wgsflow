import gzip
import json
from pathlib import Path

from wgsflow.data import create_synthetic_dataset


def test_synthetic_dataset_contract(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    create_synthetic_dataset(output, background_pairs=20)
    assert (output / "reference.fa").stat().st_size > 0
    assert (output / "truth.small.vcf").read_text().count("\n") >= 6
    assert (output / "truth.sv.vcf").read_text().count("\n") >= 8
    with gzip.open(output / "demo_R1.fastq.gz", "rt") as handle:
        assert handle.readline().startswith("@demo:0/1")


def test_synthetic_truth_coordinates_match_manifest(tmp_path: Path) -> None:
    create_synthetic_dataset(tmp_path, background_pairs=20)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    small = (tmp_path / "truth.small.vcf").read_text(encoding="utf-8")
    sv = (tmp_path / "truth.sv.vcf").read_text(encoding="utf-8")
    assert f"\t{manifest['truth']['snp']['position']}\t" in small
    assert f"\t{manifest['truth']['small_deletion']['anchor']}\t" in small
    assert f"\t{manifest['truth']['structural_deletion']['anchor']}\t" in sv
