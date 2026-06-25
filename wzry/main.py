#!/usr/bin/env python3
"""实战循环：ADB 真机截图 → 规则决策 → 触控。"""
from __future__ import annotations

import argparse

from wzry_agent.emulator_pipeline import EmulatorPipeline


def main() -> None:
  parser = argparse.ArgumentParser(description="王者荣耀真机 ADB Agent")
  parser.add_argument("--config", default=None)
  parser.add_argument("--interval", type=float, default=0.2)
  parser.add_argument("--steps", type=int, default=None)
  parser.add_argument("--execute", action="store_true", help="真实触控")
  args = parser.parse_args()

  pipeline = EmulatorPipeline(config_path=args.config)
  pipeline.run_loop(interval_sec=args.interval, max_steps=args.steps, execute=args.execute)


if __name__ == "__main__":
  main()
