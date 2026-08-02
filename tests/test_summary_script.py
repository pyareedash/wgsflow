import gzip
import runpy
from pathlib import Path
from types import SimpleNamespace


def _write_vcf(path: Path, line: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("##fileformat=VCFv4.2\n")
        handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        handle.write(line + "\n")


def test_summary_script_builds_all_outputs(tmp_path: Path) -> None:
    small = tmp_path / "small.vcf.gz"
    sv = tmp_path / "sv.vcf.gz"
    _write_vcf(small, "chr1\t10\t.\tA\tG\t60\tPASS\t.")
    _write_vcf(sv, "chr1\t20\t.\tA\t<DEL>\t60\tPASS\tEND=120;SVTYPE=DEL")

    coverage = tmp_path / "coverage.txt"
    coverage.write_text(
        "chrom\tlength\tbases\tmean\tmin\tmax\n"
        "total\t1000\t30000\t30\t0\t60\n",
        encoding="utf-8",
    )
    flagstat = tmp_path / "flagstat.txt"
    flagstat.write_text(
        "200 + 0 in total (QC-passed reads + QC-failed reads)\n"
        "198 + 0 mapped (99.00% : N/A)\n",
        encoding="utf-8",
    )

    output = SimpleNamespace(
        json=str(tmp_path / "report" / "summary.json"),
        tsv=str(tmp_path / "report" / "summary.tsv"),
        html=str(tmp_path / "report" / "dashboard.html"),
        small_tables=[str(tmp_path / "tables" / "sample.small.tsv")],
        sv_tables=[str(tmp_path / "tables" / "sample.sv.tsv")],
    )
    snakemake = SimpleNamespace(
        input=SimpleNamespace(
            small=[str(small)],
            sv=[str(sv)],
            coverage=[str(coverage)],
            flagstat=[str(flagstat)],
        ),
        output=output,
        params=SimpleNamespace(
            samples=["sample"],
            project="test",
            small_truth=None,
            sv_truth=None,
        ),
        log=[str(tmp_path / "logs" / "summary.log")],
    )

    runpy.run_path(
        "workflow/scripts/build_summary.py",
        init_globals={"snakemake": snakemake},
    )

    for path in (
        output.json,
        output.tsv,
        output.html,
        *output.small_tables,
        *output.sv_tables,
        snakemake.log[0],
    ):
        assert Path(path).stat().st_size > 0
