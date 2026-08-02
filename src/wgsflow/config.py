from __future__ import annotations

import csv
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from wgsflow.paths import repository_root, resolve_from_root
from wgsflow.workflow_contract import validate_workflow_sources


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreprocessingConfig(StrictModel):
    minimum_length: int = Field(default=50, ge=20, le=500)
    detect_adapter_for_pe: bool = True


class AlignmentConfig(StrictModel):
    platform: str = Field(default="ILLUMINA", pattern=r"^[A-Za-z0-9._-]+$")


class SmallVariantConfig(StrictModel):
    min_mapping_quality: int = Field(default=20, ge=0, le=60)
    min_base_quality: int = Field(default=20, ge=0, le=60)
    min_quality: float = Field(default=20, ge=0)


class StructuralVariantConfig(StrictModel):
    min_quality: float = Field(default=20, ge=0)


class TruthConfig(StrictModel):
    small_vcf: Path | None = None
    sv_vcf: Path | None = None


class EmailConfig(StrictModel):
    enabled: bool = False
    recipient: str | None = None
    starttls: bool = True

    @model_validator(mode="after")
    def recipient_required(self) -> EmailConfig:
        if self.enabled and (not self.recipient or "@" not in self.recipient):
            raise ValueError("A valid notifications.email.recipient is required")
        return self


class NotificationConfig(StrictModel):
    email: EmailConfig = Field(default_factory=EmailConfig)


class WorkflowConfig(StrictModel):
    project_name: str = Field(min_length=1)
    output_dir: Path = Path("results")
    samples: Path
    reference: Path
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    alignment: AlignmentConfig = Field(default_factory=AlignmentConfig)
    small_variants: SmallVariantConfig = Field(default_factory=SmallVariantConfig)
    structural_variants: StructuralVariantConfig = Field(default_factory=StructuralVariantConfig)
    truth: TruthConfig = Field(default_factory=TruthConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)


class Sample(StrictModel):
    sample: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    read1: Path
    read2: Path

    @model_validator(mode="after")
    def mates_are_distinct(self) -> Sample:
        if self.read1 == self.read2:
            raise ValueError(f"read1 and read2 are identical for {self.sample}")
        return self


def load_config(path: Path) -> WorkflowConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return WorkflowConfig.model_validate(payload)


def load_samples(path: Path) -> list[Sample]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"sample", "read1", "read2"}
        fields = set(reader.fieldnames or ())
        missing = required - fields
        if missing:
            columns = ", ".join(sorted(missing))
            raise ValueError(f"Sample sheet {path} is missing columns: {columns}")
        rows = list(reader)
    samples = [Sample.model_validate(row) for row in rows]
    if not samples:
        raise ValueError(f"No samples found in {path}")
    names = [sample.sample for sample in samples]
    if len(names) != len(set(names)):
        raise ValueError("Sample names must be unique")
    return samples


def validate_inputs(config_path: Path, *, require_files: bool = True) -> tuple[WorkflowConfig, list[Sample]]:
    root = repository_root(config_path.parent)
    validate_workflow_sources(root)
    config = load_config(config_path)
    sample_sheet = resolve_from_root(config.samples, root)
    samples = load_samples(sample_sheet)

    output_dir = resolve_from_root(config.output_dir, root).resolve()
    results_root = (root / "results").resolve()
    if output_dir == results_root or not output_dir.is_relative_to(results_root):
        raise ValueError("output_dir must be a dedicated subdirectory under results/")

    reference = resolve_from_root(config.reference, root).resolve()
    if reference.name.endswith(".gz"):
        raise ValueError("The MVP requires an uncompressed FASTA reference")

    required = [reference]
    for sample in samples:
        required.extend(
            (
                resolve_from_root(sample.read1, root).resolve(),
                resolve_from_root(sample.read2, root).resolve(),
            )
        )
    for truth in (config.truth.small_vcf, config.truth.sv_vcf):
        if truth is not None:
            required.append(resolve_from_root(truth, root).resolve())

    nested_inputs = [path for path in required if path.is_relative_to(output_dir)]
    if nested_inputs:
        rendered = "\n".join(f"  - {path}" for path in nested_inputs)
        raise ValueError(f"Input files must not be stored inside output_dir:\n{rendered}")

    if require_files:
        missing = [path for path in required if not path.is_file()]
        if missing:
            rendered = "\n".join(f"  - {path}" for path in missing)
            raise FileNotFoundError(f"Required inputs are missing:\n{rendered}")
        empty = [path for path in required if path.stat().st_size == 0]
        if empty:
            rendered = "\n".join(f"  - {path}" for path in empty)
            raise ValueError(f"Required inputs are empty:\n{rendered}")

    return config, samples
