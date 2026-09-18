from pathlib import Path
import yaml
from .schema import AppConfig


def load_config(path: str | Path = "config/config.example.yaml") -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)
