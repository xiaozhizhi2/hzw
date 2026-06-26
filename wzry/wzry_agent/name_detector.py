"""按队友名字定位（RapidOCR，不需要名字模板）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import cv2
import numpy as np
from numpy.typing import NDArray

DESIGN_H = 1080
DEFAULT_FIELD_CROP = [0.08, 0.78, 0.02, 0.98]


@dataclass(frozen=True)
class NameTarget:
  x: int
  y: int
  w: int
  h: int
  cx: float
  cy: float
  follow_x: float
  follow_y: float
  text: str
  score: float
  method: str


@dataclass
class TeammateNameFinder:
  teammate_names: list[str] = field(default_factory=list)
  field_crop: list[float] = field(default_factory=lambda: list(DEFAULT_FIELD_CROP))
  ocr_min_score: float = 0.4
  name_below_offset: int = 48
  _ocr: object | None = field(default=None, init=False, repr=False)

  def __post_init__(self) -> None:
    # 清理所有队友名字
    self.teammate_names = [name.strip() for name in self.teammate_names if name.strip()]

  @classmethod
  def from_config(cls, config) -> TeammateNameFinder:
    f = dict(config.get("follow", default={}) or {})
    # 支持两种配置格式兼容：旧的 teammate_name 或新的 teammate_names
    names = f.get("teammate_names") or [f.get("teammate_name", "")]
    if isinstance(names, str):
      # 如果是字符串，按逗号分割
      names = [n.strip() for n in names.split(",") if n.strip()]
    return cls(
      teammate_names=list(names),
      field_crop=list(f.get("field_crop", DEFAULT_FIELD_CROP)),
      ocr_min_score=float(f.get("ocr_min_score", 0.4)),
      name_below_offset=int(f.get("name_below_offset", 48)),
    )

  def _get_ocr(self):
    if self._ocr is not None:
      return self._ocr
    try:
      from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
      raise RuntimeError(
        "需要安装 rapidocr-onnxruntime: pip install rapidocr-onnxruntime"
      ) from exc
    # 使用更快的配置
    self._ocr = RapidOCR(use_textline=True, use_angle_cls=False, use_gpu=False)
    return self._ocr

  def find_all(self, frame: NDArray[np.uint8]) -> list[NameTarget]:
    """查找所有匹配的队友，返回列表"""
    if not self.teammate_names:
      return []
    return self._match_all_names(frame)

  def find(self, frame: NDArray[np.uint8]) -> NameTarget | None:
    """查找最优的队友，返回最佳匹配的单个队友（保留向后兼容）"""
    targets = self.find_all(frame)
    if not targets:
      return None
    # 返回得分最高的
    return max(targets, key=lambda t: t.score)

  def _crop_field(self, frame: NDArray[np.uint8]) -> tuple[NDArray[np.uint8], int, int]:
    h, w = frame.shape[:2]
    y0, y1, x0, x1 = self.field_crop
    roi = frame[int(h * y0) : int(h * y1), int(w * x0) : int(w * x1)]
    return roi, int(w * x0), int(h * y0)

  def _below_offset(self, frame_h: int) -> int:
    return max(20, int(round(self.name_below_offset * frame_h / DESIGN_H)))

  def _to_target(
    self,
    frame: NDArray[np.uint8],
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    score: float,
  ) -> NameTarget:
    fh, _ = frame.shape[:2]
    cx = x + w / 2
    cy = y + h / 2
    off = self._below_offset(fh)
    return NameTarget(
      x=x,
      y=y,
      w=w,
      h=h,
      cx=cx,
      cy=cy,
      follow_x=cx,
      follow_y=cy + off,
      text=text,
      score=score,
      method="ocr",
    )

  @staticmethod
  def _clean_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text))

  def _name_score(self, line: str, target_name: str) -> float:
    """计算与指定名字的匹配分数 - 更快的版本"""
    line = self._clean_text(line)
    if not line or not target_name:
      return 0.0
    # 快速检查是否包含
    if target_name in line:
      return 1.0
    # 快速检查前几个字符
    if len(target_name) <= len(line) and line.startswith(target_name[0]):
      # 只在第一个字符匹配时才计算完整相似度
      ratio = SequenceMatcher(None, target_name, line).ratio()
      return ratio
    return 0.0

  def _best_name_score(self, line: str) -> tuple[float, str]:
    """返回最佳匹配分数和对应的队友名字"""
    best_score = 0.0
    best_name = ""
    for name in self.teammate_names:
      score = self._name_score(line, name)
      if score > best_score:
        best_score = score
        best_name = name
    return best_score, best_name

  def _match_all_names(self, frame: NDArray[np.uint8]) -> list[NameTarget]:
    roi, ox, oy = self._crop_field(frame)
    if roi.size == 0:
      return []

    ocr = self._get_ocr()
    # 使用更快的配置
    result, _ = ocr(roi, text_score_thresh=self.ocr_min_score)
    if not result:
      return []

    targets: list[NameTarget] = []
    seen_positions = set()  # 防止重复检测同一位置

    for box, raw_text, det_score in result:
      text = self._clean_text(raw_text)
      if not text:
        continue
      try:
        det = float(det_score)
      except (TypeError, ValueError):
        det = 0.0
      
      name_score, matched_name = self._best_name_score(text)
      if name_score < self.ocr_min_score:
        continue
      combined = name_score * 0.7 + min(det, 1.0) * 0.3

      xs = [float(p[0]) for p in box]
      ys = [float(p[1]) for p in box]
      x0, y0 = int(min(xs)), int(min(ys))
      bw = max(1, int(max(xs) - min(xs)))
      bh = max(1, int(max(ys) - min(ys)))
      
      # 检查是否已经有相近位置的目标
      pos_key = (x0 // 50, y0 // 50)  # 50像素网格去重
      if pos_key in seen_positions:
        continue
      seen_positions.add(pos_key)
      
      target = self._to_target(frame, ox + x0, oy + y0, bw, bh, matched_name, combined)
      targets.append(target)

    return targets
