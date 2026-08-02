from pathlib import Path


def repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "workflow" / "Snakefile").is_file():
            return candidate
    raise FileNotFoundError("Run WGSFlow from inside the repository checkout")


def resolve_from_root(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path
