from __future__ import annotations

from typing import Any

from .config import Config
from .ppo import ActionDecision


class DryRunExecutor:
  """不执行触控，仅用于 PC 端 dry-run 训练。"""

  mode = "dry"

  def __init__(self, config: Config) -> None:
    del config

  def prepare(self) -> bool:
    return True

  def execute(self, decision: ActionDecision, *, step: int = 0) -> bool:
    del decision, step
    return False

  def release_all(self) -> None:
    return


def create_executor(config: Config) -> Any:
  mode = str(config.get("executor", "mode", default="dry")).lower()
  if mode == "adb":
    from .adb_executor import AdbExecutor

    return AdbExecutor(config)
  if mode == "click":
    from .click_executor import ClickExecutor

    return ClickExecutor(config)
  if mode == "keyboard":
    from .keyboard_executor import KeyboardExecutor

    return KeyboardExecutor(config)
  return DryRunExecutor(config)
