from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    raw: dict[str, Any]
    root: Path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        root = Path(__file__).resolve().parent.parent
        config_path = Path(path) if path else root / "config.yaml"
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls(raw=raw, root=root)

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def resolve_path(self, relative: str) -> Path:
        return self.root / relative
