from __future__ import annotations

import gzip
import hashlib
import json
import random
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import TextIO

from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TransferSpeedColumn

from wgsflow.paths import repository_root

DNA = "ACGT"


def reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGTN", "TGCAN"))[::-1]


def alternate(base: str) -> str:
    return DNA[(DNA.index(base) + 1) % len(DNA)]


def write_pair(r1: TextIO, r2: TextIO, name: str, fragment: str, read_length: int) -> None:
    quality = "I" * read_length
    read1 = fragment[:read_length]
    read2 = reverse_complement(fragment[-read_length:])
    r1.write(f"@{name}/1\n{read1}\n+\n{quality}\n")
    r2.write(f"@{name}/2\n{read2}\n+\n{quality}\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_synthetic_dataset(
    output_dir: Path,
    *,
    force: bool = False,
    seed: int = 42,
    background_pairs: int = 28_000,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        if not force:
            raise FileExistsError(f"{output_dir} is not empty; pass --force to replace it")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    contig = "chrDemo"
    reference = "".join(rng.choice(DNA) for _ in range(250_000))
    snp_position = 60_001
    indel_anchor = 90_000
    indel_length = 3
    deletion_anchor = 150_001
    deletion_length = 1_000

    sample = list(reference)
    sample[snp_position - 1] = alternate(sample[snp_position - 1])
    # Apply deletions from highest to lowest coordinate so truth coordinates stay stable.
    del sample[deletion_anchor : deletion_anchor + deletion_length]
    del sample[indel_anchor : indel_anchor + indel_length]
    sample_sequence = "".join(sample)

    reference_path = output_dir / "reference.fa"
    with reference_path.open("w", encoding="utf-8") as handle:
        handle.write(f">{contig}\n")
        for start in range(0, len(reference), 60):
            handle.write(reference[start : start + 60] + "\n")

    read_length = 150
    fragment_length = 450
    r1_path = output_dir / "demo_R1.fastq.gz"
    r2_path = output_dir / "demo_R2.fastq.gz"
    with gzip.open(r1_path, "wt", encoding="ascii") as r1, gzip.open(
        r2_path, "wt", encoding="ascii"
    ) as r2:
        for index in range(background_pairs):
            start = rng.randint(0, len(sample_sequence) - fragment_length)
            write_pair(
                r1,
                r2,
                f"demo:{index}",
                sample_sequence[start : start + fragment_length],
                read_length,
            )

        breakpoint = deletion_anchor - indel_length
        for offset in range(-180, 181, 3):
            start = max(
                0,
                min(len(sample_sequence) - fragment_length, breakpoint - 100 + offset),
            )
            write_pair(
                r1,
                r2,
                f"breakpoint:{offset}",
                sample_sequence[start : start + fragment_length],
                read_length,
            )

    snp_ref = reference[snp_position - 1]
    small_ref = reference[indel_anchor - 1 : indel_anchor + indel_length]
    (output_dir / "truth.small.vcf").write_text(
        "##fileformat=VCFv4.2\n"
        f"##contig=<ID={contig},length={len(reference)}>\n"
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tdemo\n"
        f"{contig}\t{snp_position}\tdemo_snp\t{snp_ref}\t{alternate(snp_ref)}\t60\tPASS\t.\tGT\t1/1\n"
        f"{contig}\t{indel_anchor}\tdemo_indel\t{small_ref}\t{small_ref[0]}\t60\tPASS\t.\tGT\t1/1\n",
        encoding="utf-8",
    )

    sv_end = deletion_anchor + deletion_length
    sv_ref = reference[deletion_anchor - 1]
    (output_dir / "truth.sv.vcf").write_text(
        "##fileformat=VCFv4.2\n"
        f"##contig=<ID={contig},length={len(reference)}>\n"
        '##ALT=<ID=DEL,Description="Deletion">\n'
        '##INFO=<ID=END,Number=1,Type=Integer,Description="End">\n'
        '##INFO=<ID=SVTYPE,Number=1,Type=String,Description="Type">\n'
        '##INFO=<ID=SVLEN,Number=1,Type=Integer,Description="Length">\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tdemo\n"
        f"{contig}\t{deletion_anchor}\tdemo_del\t{sv_ref}\t<DEL>\t60\tPASS\t"
        f"END={sv_end};SVTYPE=DEL;SVLEN=-{deletion_length}\tGT\t1/1\n",
        encoding="utf-8",
    )

    manifest_files = sorted(path for path in output_dir.iterdir() if path.is_file())
    manifest = {
        "seed": seed,
        "reference_length": len(reference),
        "sample_length": len(sample_sequence),
        "read_pairs": background_pairs + 121,
        "truth": {
            "snp": {"position": snp_position},
            "small_deletion": {"anchor": indel_anchor, "length": indel_length},
            "structural_deletion": {"anchor": deletion_anchor, "length": deletion_length},
        },
        "files": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in manifest_files
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


QUICKSTART_URL = "https://storage.googleapis.com/deepvariant/quickstart-testdata"
QUICKSTART_FILES = (
    "NA12878_S1.chr20.10_10p1mb.bam",
    "NA12878_S1.chr20.10_10p1mb.bam.bai",
    "test_nist.b37_chr20_100kbp_at_10mb.vcf.gz",
    "test_nist.b37_chr20_100kbp_at_10mb.vcf.gz.tbi",
    "ucsc.hg19.chr20.unittest.fasta",
    "ucsc.hg19.chr20.unittest.fasta.fai",
)


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task(destination.name, total=None)

        def report(blocks: int, block_size: int, total_size: int) -> None:
            if total_size > 0:
                progress.update(task, total=total_size)
            progress.update(task, completed=min(blocks * block_size, max(total_size, 0)))

        urllib.request.urlretrieve(url, destination, reporthook=report)


def create_quickstart_dataset(output_dir: Path, *, force: bool = False) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        if not force:
            raise FileExistsError(f"{output_dir} is not empty; pass --force to replace it")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for name in QUICKSTART_FILES:
        download_file(f"{QUICKSTART_URL}/{name}", output_dir / name)

    bam = output_dir / "NA12878_S1.chr20.10_10p1mb.bam"
    namesort = output_dir / "NA12878.namesort.bam"
    subprocess.run(
        ["samtools", "sort", "-n", "-@", "2", "-o", str(namesort), str(bam)],
        check=True,
    )
    with (output_dir / "samtools-fastq.log").open("w", encoding="utf-8") as log:
        subprocess.run(
            [
                "samtools",
                "fastq",
                "-@",
                "2",
                "-c",
                "6",
                "-1",
                str(output_dir / "NA12878_R1.fastq.gz"),
                "-2",
                str(output_dir / "NA12878_R2.fastq.gz"),
                "-0",
                "/dev/null",
                "-s",
                "/dev/null",
                "-n",
                str(namesort),
            ],
            check=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    namesort.unlink(missing_ok=True)


def default_data_dir(name: str) -> Path:
    return repository_root() / "resources" / name
