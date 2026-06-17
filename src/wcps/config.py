"""Central configuration loading for WCPS.

All tunable behaviour lives in ``config.yaml`` at the project root. This module
locates the project root robustly (no fragile absolute paths) and exposes a
small, cached accessor plus path helpers.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    """Return the project root directory.

    Resolution order:
    1. ``WCPS_ROOT`` environment variable (useful for deployment), else
    2. walk upward from this file until a ``config.yaml`` is found, else
    3. fall back to three levels up from this file.
    """
    env = os.environ.get("WCPS_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config.yaml").exists():
            return parent
    return here.parents[2]


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Load and cache ``config.yaml`` as a plain dict."""
    cfg_path = project_root() / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at {cfg_path}. "
            "Copy/restore the default config to the project root."
        )
    with cfg_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def reload_config() -> dict[str, Any]:
    """Clear the cache and reload config (used by the app's refresh button)."""
    load_config.cache_clear()
    return load_config()


def path(key: str) -> Path:
    """Resolve a configured path key (under ``paths:``) to an absolute Path."""
    cfg = load_config()
    rel = cfg["paths"][key]
    return (project_root() / rel).resolve()


def ensure_data_dirs() -> None:
    """Create the standard data directories if they do not yet exist."""
    for key in (
        "raw_dir",
        "context_dir",
        "predictions_dir",
        "results_dir",
        "processed_dir",
    ):
        path(key).mkdir(parents=True, exist_ok=True)
