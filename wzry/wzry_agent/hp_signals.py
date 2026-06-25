"""进局/离局血条信号（与 wzry_play.js quickHpSignals 对齐）。"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

DEFAULT_FIELD_CROP = [0.10, 0.78, 0.12, 0.88]
DEFAULT_OWN_HP_CROP = [0.84, 0.98, 0.01, 0.28]
DEFAULT_BOTTOM_HP_CROP = [0.82, 0.97, 0.35, 0.72]


def _crop(frame: NDArray[np.uint8], box: list[float]) -> NDArray[np.uint8]:
  h, w = frame.shape[:2]
  y0, y1, x0, x1 = box
  return frame[int(h * y0) : int(h * y1), int(w * x0) : int(w * x1)]


def _count_color(
  roi: NDArray[np.uint8],
  low: tuple[int, int, int],
  high: tuple[int, int, int],
  step: int,
) -> int:
  if roi.size == 0:
    return 0
  hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
  mask = cv2.inRange(hsv, np.array(low), np.array(high))
  return int(np.count_nonzero(mask[::step, ::step]))


def hp_signals(frame: NDArray[np.uint8]) -> dict[str, int]:
  green_lo, green_hi = (35, 50, 50), (88, 255, 255)
  blue_lo, blue_hi = (90, 50, 50), (130, 255, 255)
  own = _count_color(_crop(frame, DEFAULT_OWN_HP_CROP), green_lo, green_hi, 5)
  bottom = _count_color(_crop(frame, DEFAULT_BOTTOM_HP_CROP), green_lo, green_hi, 5)
  green = _count_color(_crop(frame, DEFAULT_FIELD_CROP), green_lo, green_hi, 6)
  blue = _count_color(_crop(frame, DEFAULT_FIELD_CROP), blue_lo, blue_hi, 6)
  roi = _crop(frame, DEFAULT_FIELD_CROP)
  bright = 0
  if roi.size > 0:
    bright = int(np.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)))
  return {
    "own_px": own,
    "bottom_px": bottom,
    "green_px": green,
    "blue_px": blue,
    "bright": bright,
  }


def has_hp_bar(frame: NDArray[np.uint8]) -> bool:
  s = hp_signals(frame)
  if s["bright"] < 5:
    return False
  return (
    s["own_px"] >= 5
    or s["bottom_px"] >= 5
    or s["green_px"] >= 8
    or s["blue_px"] >= 8
  )


def in_game_fast(frame: NDArray[np.uint8]) -> bool:
  green_lo, green_hi = (35, 50, 50), (88, 255, 255)
  blue_lo, blue_hi = (90, 50, 50), (130, 255, 255)
  bottom = _count_color(_crop(frame, DEFAULT_BOTTOM_HP_CROP), green_lo, green_hi, 14)
  if bottom >= 4:
    return True
  blue = _count_color(_crop(frame, DEFAULT_FIELD_CROP), blue_lo, blue_hi, 20)
  return blue >= 6
