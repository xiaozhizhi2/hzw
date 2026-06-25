from __future__ import annotations

import time
from typing import Any

from .config import Config
from .ppo import ActionDecision, ActionType
from .window_focus import focus_window


# 腾讯手游助手默认键位布局（相对截图区域 0~1）
DEFAULT_POINTS: dict[str, list[float]] = {
  "move_up": [0.115, 0.74],
  "move_down": [0.115, 0.88],
  "move_left": [0.085, 0.81],
  "move_right": [0.145, 0.81],
  "attack": [0.860, 0.73],
  "skill_1": [0.795, 0.58],
  "skill_2": [0.860, 0.48],
  "skill_3": [0.795, 0.38],
  "heal": [0.735, 0.64],
  "summoner": [0.735, 0.42],
  "recall": [0.055, 0.52],
}

ACTION_POINTS: dict[ActionType, str | tuple[str, ...]] = {
  ActionType.MOVE_UP: "move_up",
  ActionType.MOVE_DOWN: "move_down",
  ActionType.MOVE_LEFT: "move_left",
  ActionType.MOVE_RIGHT: "move_right",
  ActionType.MOVE_UP_LEFT: ("move_up", "move_left"),
  ActionType.MOVE_UP_RIGHT: ("move_up", "move_right"),
  ActionType.MOVE_DOWN_LEFT: ("move_down", "move_left"),
  ActionType.MOVE_DOWN_RIGHT: ("move_down", "move_right"),
  ActionType.ATTACK: "attack",
  ActionType.SKILL_1: "skill_1",
  ActionType.SKILL_2: "skill_2",
  ActionType.SKILL_3: "skill_3",
  ActionType.RECALL: "recall",
  ActionType.HEAL: "heal",
  ActionType.SUMMONER: "summoner",
}


class ClickExecutor:
  """直接点击屏幕上的 WASD / 技能按钮（模拟器键盘注入无效时用）。"""

  def __init__(self, config: Config) -> None:
    self.config = config
    self.mode = "click"
    self.tap_ms = int(config.get("click", "tap_ms", default=80))
    self.hold_ms = int(config.get("click", "hold_ms", default=250))
    titles = config.get("runtime", "window_titles", default=None)
    self._titles = titles
    raw_points = config.get("click", "points", default={}) or {}
    self._points = {**DEFAULT_POINTS, **raw_points}

  def _region(self) -> tuple[int, int, int, int]:
    region = self.config.get("screenshot", "region", default=None)
    if not region or len(region) != 4:
      raise RuntimeError("请先在 config.yaml 配置 screenshot.region")
    return int(region[0]), int(region[1]), int(region[2]), int(region[3])

  def _to_screen(self, norm: list[float]) -> tuple[int, int]:
    left, top, width, height = self._region()
    x = int(left + float(norm[0]) * width)
    y = int(top + float(norm[1]) * height)
    return x, y

  def _resolve_xy(self, action: ActionType) -> tuple[int, int] | None:
    spec = ACTION_POINTS.get(action)
    if spec is None:
      return None
    if isinstance(spec, str):
      norm = self._points.get(spec)
      if not norm:
        return None
      return self._to_screen(norm)
    xs: list[float] = []
    ys: list[float] = []
    for name in spec:
      norm = self._points.get(name)
      if not norm:
        return None
      xs.append(norm[0])
      ys.append(norm[1])
    return self._to_screen([sum(xs) / len(xs), sum(ys) / len(ys)])

  @staticmethod
  def _backend():
    import pydirectinput

    pydirectinput.PAUSE = 0
    pydirectinput.FAILSAFE = False
    return pydirectinput

  def prepare(self) -> bool:
    if not focus_window(self._titles):
      print("[点击] 未找到模拟器窗口", flush=True)
      return False
    left, top, width, height = self._region()
    cx, cy = int(left + width * 0.5), int(top + height * 0.5)
    pdi = self._backend()
    pdi.click(cx, cy)
    time.sleep(0.1)
    print(f"[点击] 已聚焦并点击游戏中心 ({cx}, {cy})", flush=True)
    return True

  def execute(self, decision: ActionDecision, *, step: int = 0) -> bool:
    action = ActionType(decision.action_id)
    if action == ActionType.IDLE:
      return False
    xy = self._resolve_xy(action)
    if xy is None:
      return False
    if step % 32 == 0:
      focus_window(self._titles)
    x, y = xy
    pdi = self._backend()
    is_move = action.name.startswith("MOVE_")
    if is_move:
      pdi.moveTo(x, y)
      pdi.mouseDown()
      time.sleep(self.hold_ms / 1000.0)
      pdi.mouseUp()
      print(f"[点击] {decision.action_name} hold@({x},{y})", flush=True)
    else:
      pdi.click(x, y)
      time.sleep(self.tap_ms / 1000.0)
      print(f"[点击] {decision.action_name} tap@({x},{y})", flush=True)
    return True

  def release_all(self) -> None:
    try:
      self._backend().mouseUp()
    except Exception:
      pass


def create_executor(config: Config) -> ClickExecutor | Any:
  mode = str(config.get("executor", "mode", default="keyboard")).lower()
  if mode == "keyboard":
    from .keyboard_executor import KeyboardExecutor

    return KeyboardExecutor(config)
  return ClickExecutor(config)
