"""队友蓝血条检测（与 visualize_ally_bars.py 一致）。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class AllyBar:
  x: int
  y: int
  w: int
  h: int
  cx: float
  cy: float


def detect_ally_bars(
  frame: NDArray[np.uint8],
  *,
  h_min: int = 33,
  h_max: int = 36,
  min_width: int = 80,
  width_ratio: float = 3.0,
  blue_low: tuple[int, int, int] = (90, 50, 50),
  blue_high: tuple[int, int, int] = (130, 255, 255),
) -> list[AllyBar]:
  hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
  mask = cv2.inRange(hsv, np.array(blue_low), np.array(blue_high))
  kernel = np.ones((5, 5), np.uint8)
  mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
  mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

  bars: list[AllyBar] = []
  contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    if w <= width_ratio * h:
      continue
    if w < min_width:
      continue
    if not (h_min <= h <= h_max):
      continue
    bars.append(AllyBar(x=x, y=y, w=w, h=h, cx=x + w / 2, cy=y + h / 2))
  return bars
