"""Centralized resource registry for TraveLis backend.

Loads and exposes provider-specific mappings and shared country registries.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

_RESOURCES_DIR = files("core.providers.resources")

COUNTRY_REGISTRY_PATH = Path(_RESOURCES_DIR.joinpath("country_registry.json"))
TUI_FILTERS_PATH = Path(_RESOURCES_DIR.joinpath("tui_filters.json"))
WAKACJEPL_FILTERS_PATH = Path(_RESOURCES_DIR.joinpath("wakacjepl_filters.json"))

with COUNTRY_REGISTRY_PATH.open("r", encoding="utf-8") as f:
    country_registry: dict[str, Any] = json.load(f)

with TUI_FILTERS_PATH.open("r", encoding="utf-8") as f:
    tui_filters: dict[str, Any] = json.load(f)

with WAKACJEPL_FILTERS_PATH.open("r", encoding="utf-8") as f:
    wakacjepl_filters: dict[str, Any] = json.load(f)

__all__ = [
    "COUNTRY_REGISTRY_PATH",
    "TUI_FILTERS_PATH",
    "WAKACJEPL_FILTERS_PATH",
    "country_registry",
    "tui_filters",
    "wakacjepl_filters",
]
