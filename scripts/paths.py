"""Shared path helpers for scripts under scripts/<subdir>/."""
from pathlib import Path


def repo_root() -> Path:
    """Repository root (directory containing data_sources/)."""
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "data_sources").is_dir():
            return p
        p = p.parent
    raise RuntimeError("Repository root not found (expected data_sources/).")
