"""
Configuration persistence for StarVisibility.

Saves and loads AppConfig as a JSON file.
JSON is human-readable and easy to edit manually when needed.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.models.domain import AppConfig
from src.utils.logging_utils import get_logger

log = get_logger("persistence")


def save_config(config: AppConfig, path: Path | str) -> None:
    """
    Serialise AppConfig to a JSON file.

    Parameters
    ----------
    config : AppConfig
    path   : destination file path (will overwrite if exists)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
    log.info("Configuration saved to %s", path)


def load_config(path: Path | str) -> AppConfig:
    """
    Load an AppConfig from a JSON file.

    Parameters
    ----------
    path : path to the JSON configuration file

    Returns
    -------
    AppConfig

    Raises
    ------
    FileNotFoundError : file not found
    ValueError        : JSON parse error or schema mismatch
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    try:
        config = AppConfig.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"Configuration file {path} has an unexpected structure: {exc}"
        ) from exc
    log.info("Configuration loaded from %s", path)
    return config
