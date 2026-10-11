"""Load config/config.toml (falls back to config.example.toml)."""
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # repo root


def load_config(path: str | None = None) -> dict:
    candidates = [Path(path)] if path else [
        ROOT / "config" / "config.toml",
        ROOT / "config" / "config.example.toml",
    ]
    for p in candidates:
        if p.exists():
            with p.open("rb") as f:
                cfg = tomllib.load(f)
            cfg["_path"] = str(p)
            return cfg
    raise FileNotFoundError("No config found. Copy config/config.example.toml to config/config.toml")
