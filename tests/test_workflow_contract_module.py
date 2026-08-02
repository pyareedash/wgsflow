from pathlib import Path

import pytest

from wgsflow.workflow_contract import validate_workflow_sources


def test_current_workflow_sources_validate() -> None:
    validate_workflow_sources(Path.cwd())


def test_unsupported_placeholder_is_rejected(tmp_path: Path) -> None:
    rules = tmp_path / "workflow" / "rules"
    rules.mkdir(parents=True)
    (rules / "broken.smk").write_text(
        'rule broken:\n    output:\n        "x"\n    shell:\n        r"""echo {benchmark} > {output}"""\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="benchmark plumbing"):
        validate_workflow_sources(tmp_path)
