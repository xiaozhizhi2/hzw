from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from .config import Config
from .click_executor import DEFAULT_POINTS
from .window_focus import (
  EmulatorFocus,
  _window_title,
  focus_hwnd,
  is_foreground,
)

user32 = ctypes.windll.user32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

BLOCKED_FOREGROUND = ("cursor", "visual studio", "code", "powershell", "cmd", "windows terminal")

VK_MAP: dict[str, int] = {
  "w": 0x57,
  "a": 0x41,
  "s": 0x53,
  "d": 0x44,
  "space": 0x20,
  "j": 0x4A,
  "i": 0x49,
  "o": 0x4F,
  "b": 0x42,
  "f": 0x46,
  "g": 0x47,
}

KEY_OVERLAY: dict[str, str] = {
  "w": "move_up",
  "s": "move_down",
  "a": "move_left",
  "d": "move_right",
  "space": "attack",
  "j": "skill_1",
  "i": "skill_2",
  "o": "skill_3",
  "b": "recall",
  "f": "heal",
  "g": "summoner",
}


class _KEYBDINPUT(ctypes.Structure):
  _fields_ = [
    ("wVk", wintypes.WORD),
    ("wScan", wintypes.WORD),
    ("dwFlags", wintypes.DWORD),
    ("time", wintypes.DWORD),
    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
  ]


class _INPUTUNION(ctypes.Union):
  _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
  _anonymous_ = ("u",)
  _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def foreground_title() -> str:
  return _window_title(user32.GetForegroundWindow())


def _foreground_blocked() -> bool:
  title = foreground_title().lower()
  return any(token in title for token in BLOCKED_FOREGROUND)


def _pdi():
  import pydirectinput

  pydirectinput.PAUSE = 0
  pydirectinput.FAILSAFE = False
  return pydirectinput


def _send_vk(vk: int, *, key_up: bool = False) -> None:
  extra = ctypes.c_ulong(0)
  flags = KEYEVENTF_KEYUP if key_up else 0
  scan = user32.MapVirtualKeyW(vk, 0) & 0xFF
  inp = _INPUT(
    type=INPUT_KEYBOARD,
    ki=_KEYBDINPUT(vk, scan, flags, 0, ctypes.pointer(extra)),
  )
  user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


class GameInput:
  """
  键盘动作注入。
  - overlay: 点击屏幕上的 WASD/JIO 键位（手游助手屏蔽 SendInput 时用这个）
  - vk: SendInput 虚拟键（仅部分环境有效）
  """

  def __init__(
    self,
    titles: list[str] | None = None,
    *,
    config: Config | None = None,
    backend: str = "overlay",
    focus_policy: str = "manual",
  ) -> None:
    self.titles = titles
    self.config = config
    self.backend = backend
    self.focus_policy = focus_policy
    self.focus = EmulatorFocus(titles)
    self.parent_hwnd: int | None = None
    raw = (config.get("keyboard", "overlay_points", default={}) if config else {}) or {}
    self._points = {**DEFAULT_POINTS, **raw}

  def refresh(self) -> bool:
    if not self.focus.refresh():
      return False
    self.parent_hwnd = self.focus.hwnd
    return bool(self.parent_hwnd)

  def _region(self) -> tuple[int, int, int, int]:
    if not self.config:
      raise RuntimeError("overlay 模式需要 Config")
    region = self.config.get("screenshot", "region", default=None)
    if not region or len(region) != 4:
      raise RuntimeError("请配置 screenshot.region")
    return int(region[0]), int(region[1]), int(region[2]), int(region[3])

  def _xy_for_key(self, key: str) -> tuple[int, int]:
    name = KEY_OVERLAY.get(key.lower())
    if not name:
      raise KeyError(key)
    norm = self._points[name]
    left, top, width, height = self._region()
    return int(left + norm[0] * width), int(top + norm[1] * height)

  def _xy_for_keys(self, keys: tuple[str, ...]) -> tuple[int, int]:
    xs: list[float] = []
    ys: list[float] = []
    for key in keys:
      name = KEY_OVERLAY[key.lower()]
      norm = self._points[name]
      xs.append(norm[0])
      ys.append(norm[1])
    left, top, width, height = self._region()
    return int(left + (sum(xs) / len(xs)) * width), int(top + (sum(ys) / len(ys)) * height)

  def prepare(self) -> bool:
    if not self.refresh():
      print("[键盘] 未找到模拟器窗口", flush=True)
      return False
    if self.backend == "overlay":
      print(
        "[键盘] overlay 模式：点击屏幕键位模拟 WASD/JIO（手游助手不接受程序发键）",
        flush=True,
      )
    if self.focus_policy == "manual":
      print(f"[键盘] 当前前台: {foreground_title()!r}", flush=True)
      return True
    assert self.parent_hwnd is not None
    focus_hwnd(self.parent_hwnd, click_client=False)
    return is_foreground(self.parent_hwnd) and not _foreground_blocked()

  def ensure_ready(self) -> bool:
    if self.focus_policy == "manual":
      if _foreground_blocked():
        print(f"[键盘] 请先点回游戏，当前前台: {foreground_title()!r}", flush=True)
        return False
      return True
    if not self.parent_hwnd or not user32.IsWindow(self.parent_hwnd):
      if not self.refresh():
        return False
    assert self.parent_hwnd is not None
    if is_foreground(self.parent_hwnd) and not _foreground_blocked():
      return True
    focus_hwnd(self.parent_hwnd, click_client=False)
    return is_foreground(self.parent_hwnd)

  def tap(self, key: str, *, tap_ms: int = 100) -> bool:
    if not self.ensure_ready():
      return False
    if self.backend == "overlay":
      x, y = self._xy_for_key(key)
      pdi = _pdi()
      pdi.click(x, y)
      time.sleep(tap_ms / 1000.0)
      return True
    vk = VK_MAP.get(key.lower())
    if vk is None:
      return False
    _send_vk(vk, key_up=False)
    time.sleep(tap_ms / 1000.0)
    _send_vk(vk, key_up=True)
    return True

  def hold(self, keys: tuple[str, ...], *, hold_ms: int = 400) -> bool:
    if not self.ensure_ready():
      return False
    if self.backend == "overlay":
      x, y = self._xy_for_keys(keys)
      pdi = _pdi()
      pdi.moveTo(x, y)
      pdi.mouseDown()
      time.sleep(hold_ms / 1000.0)
      pdi.mouseUp()
      return True
    for key in keys:
      vk = VK_MAP.get(key.lower())
      if vk:
        _send_vk(vk, key_up=False)
    time.sleep(hold_ms / 1000.0)
    for key in keys:
      vk = VK_MAP.get(key.lower())
      if vk:
        _send_vk(vk, key_up=True)
    return True

  def release_moves(self) -> None:
    try:
      _pdi().mouseUp()
    except Exception:
      pass
    for key in ("w", "a", "s", "d"):
      vk = VK_MAP.get(key)
      if vk:
        _send_vk(vk, key_up=True)
