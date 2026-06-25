from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from .hud_parser import HudStats, parse_hud_stats

DEFAULT_RESULT_CROP = [0.28, 0.52, 0.32, 0.68]


def _crop(frame: NDArray[np.uint8], box: list[float]) -> NDArray[np.uint8]:
  h, w = frame.shape[:2]
  y0, y1, x0, x1 = box
  return frame[int(h * y0) : int(h * y1), int(w * x0) : int(w * x1)]


def is_game_started(stats: HudStats | None) -> bool:
  return stats is not None and stats.kills == 0 and stats.deaths == 0 and stats.assists == 0


def detect_match_result(frame: NDArray[np.uint8] | None, match_cfg: dict | None = None) -> str | None:
  """结算画面 OCR，返回 win / loss / None。"""
  if frame is None or frame.size == 0:
    return None
  cfg = match_cfg or {}
  crop = cfg.get("result_crop", DEFAULT_RESULT_CROP)
  if len(crop) != 4:
    crop = DEFAULT_RESULT_CROP
  roi = _crop(frame, [float(v) for v in crop])
  if roi.size == 0:
    return None

  try:
    import pytesseract

    up = cv2.resize(roi, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    text = pytesseract.image_to_string(gray, lang="chi_sim+eng", config="--psm 7")
  except Exception:
    return None

  compact = text.replace(" ", "").replace("\n", "")
  if "胜利" in compact:
    return "win"
  if "失败" in compact:
    return "loss"
  return None


def check_game_ready(frame: NDArray[np.uint8] | None, kda_cfg: dict | None = None) -> HudStats | None:
  return parse_hud_stats(frame, kda_cfg)
