"""Loads layout-mapping configs (see ../layout_config.py) from JSON."""
from __future__ import annotations

import json
from pathlib import Path

from app.extractors.layout_config import LayoutConfig

_CONFIGS_DIR = Path(__file__).parent


def _load(name: str) -> LayoutConfig:
    with open(_CONFIGS_DIR / f"{name}.json") as f:
        return LayoutConfig.model_validate(json.load(f))


ABSA_CONFIG = _load("absa")
