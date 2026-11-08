"""Repository and database locations."""

from __future__ import annotations

import os
from pathlib import Path

def repo_root() -> Path:
    override = os.environ.get("SP15_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    # src/sp15_oasis/paths.py -> repository root
    return Path(__file__).resolve().parents[2]


def db_path() -> Path:
    override = os.environ.get("SP15_DB")
    if override:
        return Path(override).expanduser().resolve()
    return repo_root() / "data" / "sp15.sqlite"
