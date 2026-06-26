#!/usr/bin/env python3
"""检查本机环境。"""


from __future__ import annotations

import json
import platform

import cv2
import psutil


def main() -> None:
  ram_gb = psutil.virtual_memory().total / (1024**3)
  report = {
    "platform": platform.platform(),
    "ram_gb": round(ram_gb, 1),
    "opencv": cv2.__version__,
    "recommendation": "手机端运行 autox/wzry_play.js（无需 PC）",
  }
  print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
  main()
