from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from .config import Config


def resolve_adb_path(config: Config) -> str:
  configured = config.get("adb", "path", default=None)
  if configured and Path(configured).exists():
    return str(configured)

  found = shutil.which("adb")
  if found:
    return found

  candidates = [
    Path(os.environ.get("ANDROID_HOME", "")) / "platform-tools" / "adb.exe",
    Path(os.environ.get("ANDROID_SDK_ROOT", "")) / "platform-tools" / "adb.exe",
    Path(r"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe"),
    Path(r"D:\download\scrcpy\scrcpy-win64-v3.3.4\adb.exe"),
    Path(r"D:\Program Files\Tencent\GameAssist\Application") / "adb.exe",
  ]
  for base in Path(r"D:\Program Files\Tencent\GameAssist\Application").glob("*/adb.exe"):
    candidates.append(base)

  for path in candidates:
    if path and path.exists():
      return str(path)

  raise FileNotFoundError(
    "找不到 adb，请在 config.yaml 的 adb.path 填写，或安装 platform-tools 并加入 PATH"
  )


def list_devices(adb_path: str) -> list[tuple[str, str]]:
  result = subprocess.run(
    [adb_path, "devices", "-l"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="ignore",
    check=False,
  )
  devices: list[tuple[str, str]] = []
  for line in result.stdout.splitlines():
    line = line.strip()
    if not line or line.startswith("List of devices"):
      continue
    parts = line.split()
    if len(parts) >= 2 and parts[1] == "device":
      devices.append((parts[0], line))
  return devices


class AdbClient:
  """ADB 截图与 input 注入。"""

  def __init__(self, config: Config) -> None:
    self.config = config
    self.adb_path = resolve_adb_path(config)
    self.device = config.get("adb", "device", default=None)
    if not self.device:
      online = list_devices(self.adb_path)
      if not online:
        raise RuntimeError(
          "没有在线 ADB 设备。请手机开启 USB 调试并连接电脑，运行 train.py adb 检查。"
        )
      self.device = online[0][0]

  def _base_cmd(self) -> list[str]:
    cmd = [self.adb_path]
    if self.device:
      cmd.extend(["-s", self.device])
    return cmd

  def shell(self, *args: str, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    cmd = self._base_cmd() + ["shell", *args]
    return subprocess.run(
      cmd,
      capture_output=True,
      text=True,
      encoding="utf-8",
      errors="ignore",
      timeout=timeout,
      check=False,
    )

  def screencap(self) -> NDArray[np.uint8]:
    result = subprocess.run(
      self._base_cmd() + ["exec-out", "screencap", "-p"],
      capture_output=True,
      timeout=20.0,
      check=False,
    )
    if result.returncode != 0:
      err = result.stderr.decode("utf-8", errors="ignore")
      raise RuntimeError(f"ADB 截图失败: {err or result.returncode}")

    data = np.frombuffer(result.stdout, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
      raise RuntimeError("ADB 截图解码失败")
    return image

  def screen_size(self) -> tuple[int, int]:
    frame = self.screencap()
    h, w = frame.shape[:2]
    return w, h

  def tap(self, x: int, y: int) -> None:
    self.shell("input", "tap", str(int(x)), str(int(y)))

  def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
    self.shell(
      "input",
      "swipe",
      str(int(x1)),
      str(int(y1)),
      str(int(x2)),
      str(int(y2)),
      str(int(duration_ms)),
    )

  def keyevent(self, code: int) -> None:
    self.shell("input", "keyevent", str(int(code)))
