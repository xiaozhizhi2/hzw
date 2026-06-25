#!/usr/bin/env python3
"""推理测试：ADB 截图 → 规则决策 → 触控。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from wzry_agent.emulator_pipeline import EmulatorPipeline


def main() -> None:
  parser = argparse.ArgumentParser(description="真机规则推理")
  parser.add_argument("--config", default=None)
  parser.add_argument("--image", default=None, help="测图；不指定则按 screenshot 配置截屏")
  parser.add_argument("--json", action="store_true")
  parser.add_argument("--execute", action="store_true")
  parser.add_argument("--loop", action="store_true")
  parser.add_argument("--interval", type=float, default=0.2)
  parser.add_argument("--steps", type=int, default=100)
  args = parser.parse_args()

  pipeline = EmulatorPipeline(config_path=args.config)

  if args.loop:
    pipeline.run_loop(interval_sec=args.interval, max_steps=args.steps, execute=args.execute)
    return

  image = None
  if args.image:
    image_path = Path(args.image)
    if not image_path.is_absolute():
      image_path = pipeline.config.root / image_path
    image = cv2.imread(str(image_path))
    if image is None:
      raise FileNotFoundError(image_path)

  result = pipeline.run_once(image=image, execute=args.execute)
  pipeline._print_result(result)

  if args.json:
    print(
      json.dumps(
        {
          "image_shape": list(result.image_shape),
          "decision": {
            "action_id": result.decision.action_id,
            "action_name": result.decision.action_name,
          },
          "rule": result.debug.get("rule"),
          "executed": result.executed,
        },
        ensure_ascii=False,
        indent=2,
      )
    )


if __name__ == "__main__":
  main()
