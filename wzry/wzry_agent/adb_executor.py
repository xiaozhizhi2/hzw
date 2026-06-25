from __future__ import annotations

import time
from typing import Any

from .adb_client import AdbClient
from .config import Config
from .phone_touch import PhoneTouchMixin
from .ppo import ActionDecision


class AdbExecutor(PhoneTouchMixin):
  """真机：ADB 截图 + input tap/swipe（可选）。"""

  def __init__(self, config: Config) -> None:
    self.config = config
    self.mode = "adb"
    self.adb = AdbClient(config)
    self._load_touch_config(config)

  def _ensure_screen(self) -> tuple[int, int]:
    if self._screen is None:
      self._screen = self.adb.screen_size()
      w, h = self._screen
      print(f"[ADB] 设备 {self.adb.device} 分辨率 {w}x{h}", flush=True)
    return self._screen

  def prepare(self) -> bool:
    try:
      self._screen = None
      self._ensure_screen()
      print(f"[ADB] 已连接 {self.adb.device}", flush=True)
      return True
    except Exception as exc:
      print(f"[ADB] 连接失败: {exc}", flush=True)
      return False

  def execute(self, decision: ActionDecision, *, step: int = 0) -> bool:
    del step
    plan = self._plan_action(decision)
    if not plan:
      return False
    if plan["kind"] == "tap":
      self.adb.tap(plan["x"], plan["y"])
      time.sleep(self.tap_ms / 1000.0)
      print(f"[ADB] {plan['name']} tap ({plan['x']},{plan['y']})", flush=True)
      return True
    self.adb.swipe(plan["x1"], plan["y1"], plan["x2"], plan["y2"], plan["duration"])
    print(
      f"[ADB] {plan['name']} swipe ({plan['x1']},{plan['y1']})→({plan['x2']},{plan['y2']})",
      flush=True,
    )
    return True

  def release_all(self) -> None:
    return
