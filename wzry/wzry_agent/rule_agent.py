from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
from numpy.typing import NDArray

from .ppo import ACTION_NAMES, ActionType

# 战场区域（相对坐标 y0,y1,x0,x1），排除小地图和底部 UI
DEFAULT_FIELD_CROP = [0.10, 0.78, 0.12, 0.88]
# 自身绿色血条（左下）
DEFAULT_OWN_HP_CROP = [0.84, 0.98, 0.01, 0.28]


@dataclass
class AllyBar:
  cx: float
  cy: float
  fill: float


@dataclass
class RuleAgent:
  """规则决策：跟蓝条队友、定时 1 技能、见红放 2、自/队友血低于阈值放 3。"""

  skill1_interval_sec: float = 1.0
  low_hp_ratio: float = 0.5
  red_bar_pixels: int = 120
  field_crop: list[float] = field(default_factory=lambda: list(DEFAULT_FIELD_CROP))
  own_hp_crop: list[float] = field(default_factory=lambda: list(DEFAULT_OWN_HP_CROP))
  _last_skill1: float = field(default=0.0, init=False, repr=False)

  def reset_match(self) -> None:
    self._last_skill1 = 0.0

  def decide(self, frame: NDArray[np.uint8]) -> tuple[int, dict]:
    info: dict = {}
    own_hp = self._own_hp_ratio(frame)
    info["own_hp"] = round(own_hp, 3)

    ally_bars = self._ally_bars(frame)
    if ally_bars:
      min_ally = min(bar.fill for bar in ally_bars)
      info["min_ally_hp"] = round(min_ally, 3)
    else:
      info["min_ally_hp"] = None

    if own_hp < self.low_hp_ratio or (
      ally_bars and min(bar.fill for bar in ally_bars) < self.low_hp_ratio
    ):
      info["rule"] = "skill_3_low_hp"
      return int(ActionType.SKILL_3), info

    red_bar = self._has_red_bar(frame)
    info["red_bar"] = red_bar

    if red_bar:
      info["rule"] = "skill_2_enemy"
      return int(ActionType.SKILL_2), info

    now = time.monotonic()
    if now - self._last_skill1 >= self.skill1_interval_sec:
      self._last_skill1 = now
      info["rule"] = "skill_1_interval"
      return int(ActionType.SKILL_1), info

    move_id, follow = self._move_toward_nearest_ally(ally_bars, frame)
    info["rule"] = "follow_ally"
    info["follow"] = follow
    return move_id, info

  def _crop(self, frame: NDArray[np.uint8], box: list[float]) -> NDArray[np.uint8]:
    h, w = frame.shape[:2]
    y0, y1, x0, x1 = box
    return frame[int(h * y0) : int(h * y1), int(w * x0) : int(w * x1)]

  @staticmethod
  def _horizontal_fill_ratio(mask: NDArray[np.uint8]) -> float:
    """血条填充比例：有颜色的列数 / 总列数。"""
    if mask.size == 0 or mask.shape[1] == 0:
      return 1.0
    cols = np.any(mask > 0, axis=0)
    return float(np.count_nonzero(cols)) / float(mask.shape[1])

  def _own_hp_ratio(self, frame: NDArray[np.uint8]) -> float:
    roi = self._crop(frame, self.own_hp_crop)
    if roi.size == 0:
      return 1.0
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([35, 50, 50]), np.array([88, 255, 255]))
    return self._horizontal_fill_ratio(green)

  def _has_red_bar(self, frame: NDArray[np.uint8]) -> bool:
    roi = self._crop(frame, self.field_crop)
    if roi.size == 0:
      return False
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    low1 = cv2.inRange(hsv, np.array([0, 70, 70]), np.array([12, 255, 255]))
    low2 = cv2.inRange(hsv, np.array([168, 70, 70]), np.array([180, 255, 255]))
    mask = cv2.bitwise_or(low1, low2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return cv2.countNonZero(mask) >= self.red_bar_pixels

  def _ally_bars(self, frame: NDArray[np.uint8]) -> list[AllyBar]:
    roi = self._crop(frame, self.field_crop)
    if roi.size == 0:
      return []
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, np.array([95, 70, 70]), np.array([130, 255, 255]))
    mask = cv2.morphologyEx(blue, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    bars: list[AllyBar] = []
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in cnts:
      area = cv2.contourArea(cnt)
      if area < 60:
        continue
      x, y, bw, bh = cv2.boundingRect(cnt)
      if bw < bh * 1.5:
        continue
      strip = mask[y : y + bh, x : x + bw]
      fill = self._horizontal_fill_ratio(strip)
      bars.append(AllyBar(cx=x + bw * 0.5, cy=y + bh * 0.5, fill=fill))
    return bars

  def _move_toward_nearest_ally(
    self,
    ally_bars: list[AllyBar],
    frame: NDArray[np.uint8],
  ) -> tuple[int, dict]:
    roi = self._crop(frame, self.field_crop)
    if roi.size == 0 or not ally_bars:
      return int(ActionType.IDLE), {"target": None}

    rh, rw = roi.shape[:2]
    player = (rw * 0.5, rh * 0.82)

    best: AllyBar | None = None
    best_dist = float("inf")
    for bar in ally_bars:
      dist = math.hypot(bar.cx - player[0], bar.cy - player[1])
      if dist < 40:
        continue
      if dist < best_dist:
        best_dist = dist
        best = bar

    if best is None:
      return int(ActionType.IDLE), {"target": None}

    dx = best.cx - player[0]
    dy = best.cy - player[1]
    action_id = self._vector_to_move(dx, dy)
    return action_id, {
      "target": [round(best.cx, 1), round(best.cy, 1)],
      "dist": round(best_dist, 1),
      "ally_hp": round(best.fill, 3),
    }

  @staticmethod
  def _vector_to_move(dx: float, dy: float) -> int:
    if abs(dx) < 8 and abs(dy) < 8:
      return int(ActionType.IDLE)
    angle = math.atan2(dy, dx)
    sector = int(round(angle / (math.pi / 4))) % 8
    mapping = {
      0: ActionType.MOVE_RIGHT,
      1: ActionType.MOVE_DOWN_RIGHT,
      2: ActionType.MOVE_DOWN,
      3: ActionType.MOVE_DOWN_LEFT,
      4: ActionType.MOVE_LEFT,
      5: ActionType.MOVE_UP_LEFT,
      6: ActionType.MOVE_UP,
      7: ActionType.MOVE_UP_RIGHT,
    }
    return int(mapping[sector])

  @classmethod
  def from_config(cls, config) -> RuleAgent:
    rules = dict(config.get("rules", default={}) or {})
    low_hp = rules.get("low_hp_ratio", rules.get("short_hp_ratio", 0.5))
    return cls(
      skill1_interval_sec=float(rules.get("skill1_interval_sec", 1.0)),
      low_hp_ratio=float(low_hp),
      red_bar_pixels=int(rules.get("red_bar_pixels", 120)),
      field_crop=list(rules.get("field_crop", DEFAULT_FIELD_CROP)),
      own_hp_crop=list(rules.get("own_hp_crop", DEFAULT_OWN_HP_CROP)),
    )


def action_name(action_id: int) -> str:
  return ACTION_NAMES.get(action_id, "UNKNOWN")
