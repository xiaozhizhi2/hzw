from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

SW_RESTORE = 9
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32


def _window_title(hwnd: int) -> str:
  length = user32.GetWindowTextLengthW(hwnd)
  if length == 0:
    return ""
  buf = ctypes.create_unicode_buffer(length + 1)
  user32.GetWindowTextW(hwnd, buf, length + 1)
  return buf.value


def find_emulator_window(
  titles: list[str] | None = None,
  *,
  min_width: int = 400,
  min_height: int = 300,
) -> tuple[int, str, int, int, int, int] | None:
  """返回 (hwnd, title, left, top, width, height)。"""
  keywords = titles or ["王者荣耀", "腾讯手游助手", "GameLoop", "手游助手"]
  matches: list[tuple[int, str, int, int, int, int]] = []

  def _callback(hwnd: int, _: int) -> bool:
    if not user32.IsWindowVisible(hwnd):
      return True
    title = _window_title(hwnd)
    if not title or not any(key in title for key in keywords):
      return True
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width < min_width or height < min_height:
      return True
    matches.append((hwnd, title, rect.left, rect.top, width, height))
    return True

  cb = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(_callback)
  user32.EnumWindows(cb, 0)
  if not matches:
    return None
  matches.sort(key=lambda item: item[4] * item[5], reverse=True)
  return matches[0]


def find_window_rect(
  titles: list[str] | None = None,
  *,
  min_width: int = 400,
  min_height: int = 300,
) -> tuple[str, int, int, int, int] | None:
  info = find_emulator_window(titles, min_width=min_width, min_height=min_height)
  if info is None:
    return None
  _, title, left, top, width, height = info
  return title, left, top, width, height


def is_foreground(hwnd: int) -> bool:
  return bool(hwnd) and user32.GetForegroundWindow() == hwnd


def _foreground_looks_wrong() -> bool:
  title = _window_title(user32.GetForegroundWindow()).lower()
  blocked = ("cursor", "visual studio", "code", "powershell", "cmd", "windows terminal")
  return any(token in title for token in blocked)


def focus_hwnd(hwnd: int, *, click_client: bool = False) -> bool:
  """强制把模拟器切到前台。按键必须发到前台窗口，否则会打进 Cursor 输入框。"""
  if not hwnd:
    return False

  user32.ShowWindow(hwnd, SW_RESTORE)

  # Windows 限制：模拟 Alt 可提升 SetForegroundWindow 成功率
  user32.keybd_event(VK_MENU, 0, 0, 0)
  user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

  fg = user32.GetForegroundWindow()
  fg_thread = user32.GetWindowThreadProcessId(fg, None)
  target_thread = user32.GetWindowThreadProcessId(hwnd, None)
  current_thread = ctypes.windll.kernel32.GetCurrentThreadId()

  attached_fg = False
  attached_self = False
  if fg_thread and fg_thread != target_thread:
    user32.AttachThreadInput(fg_thread, target_thread, True)
    attached_fg = True
  if current_thread != target_thread:
    user32.AttachThreadInput(current_thread, target_thread, True)
    attached_self = True

  user32.BringWindowToTop(hwnd)
  ok = bool(user32.SetForegroundWindow(hwnd))

  if attached_self:
    user32.AttachThreadInput(current_thread, target_thread, False)
  if attached_fg:
    user32.AttachThreadInput(fg_thread, target_thread, False)

  time.sleep(0.03)

  if click_client and ok:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    try:
      import pydirectinput

      pydirectinput.PAUSE = 0
      cx = rect.left + max(120, width // 2)
      cy = rect.top + max(120, height // 2)
      pydirectinput.click(cx, cy)
      time.sleep(0.02)
    except Exception:
      pass

  return ok and is_foreground(hwnd)


class EmulatorFocus:
  """缓存模拟器 hwnd，并在每次按键前确保焦点正确。"""

  def __init__(self, titles: list[str] | None = None) -> None:
    self.titles = titles
    self.hwnd: int | None = None
    self.title: str = ""

  def refresh(self) -> bool:
    info = find_emulator_window(self.titles)
    if info is None:
      self.hwnd = None
      self.title = ""
      return False
    self.hwnd, self.title, _, _, _, _ = info
    return True

  def ensure(self, *, click_client: bool = False) -> bool:
    if not self.hwnd or not user32.IsWindow(self.hwnd):
      if not self.refresh():
        return False
    assert self.hwnd is not None
    if is_foreground(self.hwnd) and not _foreground_looks_wrong():
      return True
    return focus_hwnd(self.hwnd, click_client=click_client)


def focus_window(titles: list[str] | None = None) -> bool:
  focus = EmulatorFocus(titles)
  if not focus.refresh():
    return False
  return focus.ensure(click_client=True)
