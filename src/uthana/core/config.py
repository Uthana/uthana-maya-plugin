"""Configuration management for Uthana Maya plugin.

Platform-agnostic config persistence using JSON.
Shared config file with the Blender plugin at ~/.cache/uthana/config.json.
"""

import json

from .constants import CACHE_DIR, CONFIG_PATH
from .logger import logger
from .types import OperationResult, UthanaConfig


def ensure_cache_directory() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> UthanaConfig:
    if not CONFIG_PATH.exists():
        return get_default_config()

    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f) or {}
        return UthanaConfig.from_dict(data)
    except Exception as e:
        logger.warning("Failed to load config: %s, using defaults", e)
        return get_default_config()


def save_config(config: UthanaConfig) -> OperationResult:
    try:
        ensure_cache_directory()
        with open(CONFIG_PATH, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
        return OperationResult(success=True, message="Config saved successfully")
    except Exception as e:
        return OperationResult(success=False, message=f"Failed to save config: {str(e)}")


def get_default_config() -> UthanaConfig:
    return UthanaConfig()
