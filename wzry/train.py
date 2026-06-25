#!/usr/bin/env python3
"""王者荣耀规则 Agent（识别逻辑在手机 autox/wzry_play.js）。"""

from __future__ import annotations

import argparse


def _log(msg: str) -> None:
  print(msg, flush=True)


def cmd_check(_: argparse.Namespace) -> None:
  from check_hardware import main as hardware_main

  hardware_main()


def cmd_play(_: argparse.Namespace) -> None:
  _log("识别与规则决策已在手机端执行，PC 无需启动服务。")
  _log("请用 VS Code AutoX 直接运行: autox/wzry_play.js")
  _log("参数可在 wzry_play.js 顶部 CFG / RULE 中修改。")


def main() -> None:
  parser = argparse.ArgumentParser(description="王者荣耀规则 Agent")
  parser.add_argument("--config", default=None)
  sub = parser.add_subparsers(dest="command", required=True)

  sub.add_parser("check", help="检查环境").set_defaults(func=cmd_check)

  p_play = sub.add_parser("play", help="说明：规则打局在手机端运行")
  p_play.set_defaults(func=cmd_play)

  args = parser.parse_args()
  args.func(args)


if __name__ == "__main__":
  main()
