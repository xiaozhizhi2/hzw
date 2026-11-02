"""自选股列表持久化：JSON 文件存储。"""
from __future__ import annotations

import json
import os


def _default_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")


class Watchlist:
    """自选股列表，按添加顺序存储，代码为 'shXXXXXX' 形式。"""

    def __init__(self, path: str | None = None):
        self.path = path or _default_path()
        self.codes: list[str] = []
        self.load()

    def load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.codes = [c for c in data.get("codes", []) if isinstance(c, str)]
            except (OSError, ValueError):
                self.codes = []

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"codes": self.codes}, f, ensure_ascii=False, indent=2)

    def add(self, code: str) -> bool:
        if code in self.codes:
            return False
        self.codes.append(code)
        self.save()
        return True

    def remove(self, code: str) -> None:
        if code in self.codes:
            self.codes.remove(code)
            self.save()

    def __len__(self) -> int:
        return len(self.codes)