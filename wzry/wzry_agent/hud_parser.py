from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

# 顶部比分条：剑(击杀) 骷髅(死亡) 拳头(助攻)
DEFAULT_KDA_CROP = [0.03, 0.12, 0.38, 0.62]

KDA_SLASH_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)")
KDA_SPACE_PATTERN = re.compile(r"(\d+)\D+(\d+)\D+(\d+)")


@dataclass(frozen=True)
class HudStats:
  kills: int
  deaths: int
  assists: int

  def __str__(self) -> str:
    return f"{self.kills}/{self.deaths}/{self.assists}"


def _crop(frame: NDArray[np.uint8], box: list[float]) -> NDArray[np.uint8]:
  h, w = frame.shape[:2]
  y0, y1, x0, x1 = box
  return frame[int(h * y0) : int(h * y1), int(w * x0) : int(w * x1)]


def _preprocess_digits(roi: NDArray[np.uint8]) -> NDArray[np.uint8]:
  up = cv2.resize(roi, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
  gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
  gray = cv2.equalizeHist(gray)
  _, mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
  mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
  return mask


def _ocr_text(mask: NDArray[np.uint8], *, psm: str = "7") -> str:
  try:
    import pytesseract
  except ImportError:
    return ""
  cfg = f"--psm {psm} -c tessedit_char_whitelist=0123456789/ "
  return pytesseract.image_to_string(mask, config=cfg)


def _first_int(text: str) -> int | None:
  match = re.search(r"\d+", text.replace("\n", " "))
  return int(match.group()) if match else None


def _ocr_one_digit(roi: NDArray[np.uint8]) -> int | None:
  if roi.size == 0:
    return None
  mask = _preprocess_digits(roi)
  for img in (mask, cv2.bitwise_not(mask)):
    val = _first_int(_ocr_text(img, psm="8"))
    if val is not None:
      return val
  return None


def _parse_kda_triple(roi: NDArray[np.uint8]) -> tuple[int, int, int] | None:
  """剑 / 骷髅 / 拳头 三个数字分栏 OCR。"""
  if roi.size == 0:
    return None
  h, w = roi.shape[:2]
  slots: list[int | None] = []
  for i in range(3):
    x0 = int(w * (0.08 + i * 0.31))
    x1 = int(w * (0.36 + i * 0.31))
    slot = roi[:, x0:x1]
    slots.append(_ocr_one_digit(slot))
  if all(v is not None for v in slots):
    return int(slots[0]), int(slots[1]), int(slots[2])

  mask = _preprocess_digits(roi)
  for img in (mask, cv2.bitwise_not(mask)):
    text = " ".join(_ocr_text(img).replace("\n", " ").split())
    match = KDA_SLASH_PATTERN.search(text) or KDA_SPACE_PATTERN.search(text)
    if match:
      return int(match.group(1)), int(match.group(2)), int(match.group(3))
  return None


def parse_hud_stats(
  frame: NDArray[np.uint8] | None,
  reward_cfg: dict | None = None,
) -> HudStats | None:
  """击杀/死亡/助攻：顶部比分条（剑/骷髅/拳头图标旁数字）。"""
  if frame is None or frame.size == 0:
    return None
  cfg = reward_cfg or {}

  kda_crop = cfg.get("kda_crop", DEFAULT_KDA_CROP)
  if len(kda_crop) != 4:
    kda_crop = DEFAULT_KDA_CROP
  kda_roi = _crop(frame, [float(v) for v in kda_crop])
  kda = _parse_kda_triple(kda_roi)
  if not kda:
    return None

  return HudStats(kills=kda[0], deaths=kda[1], assists=kda[2])
