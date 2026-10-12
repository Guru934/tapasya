"""Load config with documented precedence order.

Precedence (highest first):
  1. Explicit --config argument
  2. TAPASYA_CONFIG environment variable
  3. User config at ~/.config/tapasya/config.toml
  4. Repository config at config/config.toml
  5. Repository example at config/config.example.toml
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # repo root


def load_config(path: str | None = None) -> dict:
    candidates = []
    if path:
        candidates.append(Path(path))
    else:
        env_path = os.environ.get("TAPASYA_CONFIG")
        if env_path:
            candidates.append(Path(env_path))
        candidates.append(Path.home() / ".config" / "tapasya" / "config.toml")
        candidates.append(ROOT / "config" / "config.toml")
        candidates.append(ROOT / "config" / "config.example.toml")

    for p in candidates:
        if p.exists():
            with p.open("rb") as f:
                cfg = tomllib.load(f)
            cfg["_path"] = str(p)
            return cfg
    raise FileNotFoundError(
        "No config found. Checked: "
        + ", ".join(str(p) for p in candidates)
        + ". Set TAPASYA_CONFIG or create ~/.config/tapasya/config.toml"
    )
