#!/usr/bin/env python3
"""启动 PC 桥接服务：手机 AutoJS 发截图，PC OpenCV 识别队友蓝条并返回移动方向。"""
from __future__ import annotations

import argparse

from wzry_agent.config import Config
from wzry_agent.follow_server import FollowPlayServer


def main() -> None:
  parser = argparse.ArgumentParser(description="王者荣耀 AutoJS+PC 桥接服务")
  parser.add_argument("--config", default=None, help="config.yaml 路径")
  args = parser.parse_args()
  config = Config.load(args.config)
  FollowPlayServer(config).run()


if __name__ == "__main__":
  main()
