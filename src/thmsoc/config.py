"""Configuration helpers shared by thmsoc tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomli


def default_config_path() -> Path:
    """Return the configuration file used by a source or editable install."""
    return Path(__file__).resolve().parents[2] / "thmsoc_python_config.toml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the project TOML file, returning an empty mapping if it is absent."""
    config_path = Path(path) if path is not None else default_config_path()
    try:
        with config_path.open("rb") as stream:
            return tomli.load(stream)
    except FileNotFoundError:
        return {}
