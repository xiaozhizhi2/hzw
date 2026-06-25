from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from .config import Config


class ScreenshotCapture:
  """截图：ADB 真机 / 本地图片 / 屏幕。"""

  def __init__(self, config: Config) -> None:
    self.config = config
    self.source = config.get("screenshot", "source", default="file")
    self._adb = None

  def capture(self) -> NDArray[np.uint8]:
    if self.source == "file":
      return self._from_file()
    if self.source == "adb":
      return self._from_adb()
    if self.source == "screen":
      return self._from_screen()
    raise ValueError(f"不支持的截图来源: {self.source}（真机截图请用 autox/wzry.js）")

  def _from_file(self) -> NDArray[np.uint8]:
    image_path = self.config.resolve_path(
      self.config.get("screenshot", "test_image", default="image.png")
    )
    image = cv2.imread(str(image_path))
    if image is None:
      raise FileNotFoundError(f"无法读取截图: {image_path}")
    return image

  def _from_adb(self) -> NDArray[np.uint8]:
    if self._adb is None:
      from .adb_client import AdbClient

      self._adb = AdbClient(self.config)
    return self._adb.screencap()

  def _from_screen(self) -> NDArray[np.uint8]:
    try:
      import mss
    except ImportError as exc:
      raise ImportError("屏幕截图需要安装 mss: pip install mss") from exc

    region = self.config.get("screenshot", "region", default=None)
    with mss.mss() as sct:
      if region and len(region) == 4:
        left, top, width, height = [int(v) for v in region]
        monitor = {"left": left, "top": top, "width": width, "height": height}
      else:
        monitor = sct.monitors[1]
      frame = np.array(sct.grab(monitor))
      return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
