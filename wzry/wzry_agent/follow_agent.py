"""仅跟随队友蓝血条（PC 端决策）。"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .ally_detector import AllyBar, detect_ally_bars
from .ppo import ActionType

DESIGN_H = 1080


@dataclass
class FollowAgent:
  ally_bar_h_min: int = 33
  ally_bar_h_max: int = 36
  ally_bar_min_width: int = 80
  ally_bar_width_ratio: float = 3.0
  blue_hsv_low: tuple[int, int, int] = (90, 50, 50)
  blue_hsv_high: tuple[int, int, int] = (130, 255, 255)
  player_x_ratio: float = 0.5
  player_y_ratio: float = 0.55
  follow_max_dist_ratio: float = 1.0
  follow_close_dist: float = 15.0
  sticky_ms: int = 2000
  _step: int = field(default=0, init=False, repr=False)
  _last_follow_action: int = field(default=0, init=False, repr=False)
  _last_follow_rule: str = field(default="idle", init=False, repr=False)
  _last_follow_at: float = field(default=0.0, init=False, repr=False)
  _last_target: list | None = field(default=None, init=False, repr=False)

  @classmethod
  def from_config(cls, config) -> FollowAgent:
    f = dict(config.get("follow", default={}) or {})
    low = tuple(f.get("blue_hsv_low", [90, 50, 50]))
    high = tuple(f.get("blue_hsv_high", [130, 255, 255]))
    return cls(
      ally_bar_h_min=int(f.get("ally_bar_h_min", 33)),
      ally_bar_h_max=int(f.get("ally_bar_h_max", 36)),
      ally_bar_min_width=int(f.get("ally_bar_min_width", 80)),
      ally_bar_width_ratio=float(f.get("ally_bar_width_ratio", 3.0)),
      blue_hsv_low=(int(low[0]), int(low[1]), int(low[2])),
      blue_hsv_high=(int(high[0]), int(high[1]), int(high[2])),
      player_x_ratio=float(f.get("player_x_ratio", 0.5)),
      player_y_ratio=float(f.get("player_y_ratio", 0.55)),
      follow_max_dist_ratio=float(f.get("follow_max_dist_ratio", 1.0)),
      follow_close_dist=float(f.get("follow_close_dist", 15.0)),
      sticky_ms=int(f.get("sticky_ms", 2000)),
    )

  def _bar_height_range(self, frame_h: int) -> tuple[int, int]:
    scale = frame_h / DESIGN_H
    h_min = max(28, int(round(self.ally_bar_h_min * scale)))
    h_max = max(h_min + 2, int(round(self.ally_bar_h_max * scale)))
    return h_min, h_max

  def _min_bar_width(self, frame_w: int) -> int:
    scale = frame_w / 2400
    return max(50, int(round(self.ally_bar_min_width * scale)))

  def _sticky_follow(self, info: dict) -> tuple[int, dict] | None:
    if self._last_follow_action < 1:
      return None
    age_ms = (time.monotonic() - self._last_follow_at) * 1000
    if age_ms > self.sticky_ms:
      return None
    info["rule"] = "sticky"
    info["reason"] = f"hold_{self._last_follow_rule} age={age_ms:.0f}ms"
    if self._last_target:
      info["target"] = self._last_target
    return self._last_follow_action, info

  def decide(self, frame: NDArray[np.uint8]) -> tuple[int, dict]:
    self._step += 1
    info: dict = {"step": self._step}
    h, w = frame.shape[:2]
    h_min, h_max = self._bar_height_range(h)
    min_w = self._min_bar_width(w)
    bars = detect_ally_bars(
      frame,
      h_min=h_min,
      h_max=h_max,
      min_width=min_w,
      width_ratio=self.ally_bar_width_ratio,
      blue_low=self.blue_hsv_low,
      blue_high=self.blue_hsv_high,
    )
    info["ally_count"] = len(bars)
    info["bar_h"] = [h_min, h_max]
    info["allies"] = [
      {"x": b.x, "y": b.y, "w": b.w, "h": b.h, "cx": round(b.cx, 1), "cy": round(b.cy, 1)}
      for b in bars
    ]

    player_x = w * self.player_x_ratio
    player_y = h * self.player_y_ratio
    max_follow = max(w, h) * self.follow_max_dist_ratio
    info["player"] = [round(player_x, 1), round(player_y, 1)]

    if not bars:
      sticky = self._sticky_follow(info)
      if sticky:
        return sticky
      info["rule"] = "idle"
      info["reason"] = "no_ally"
      return int(ActionType.IDLE), info

    best: AllyBar | None = None
    best_dist = float("inf")
    for bar in bars:
      dist = math.hypot(bar.cx - player_x, bar.cy - player_y)
      if dist > max_follow:
        continue
      if dist < best_dist:
        best_dist = dist
        best = bar

    if best is None:
      sticky = self._sticky_follow(info)
      if sticky:
        return sticky
      info["rule"] = "idle"
      info["reason"] = f"no_valid_ally n={len(bars)} max={max_follow:.0f}"
      return int(ActionType.IDLE), info

    dx = best.cx - player_x
    dy = best.cy - player_y
    info["target"] = [best.x, best.y, best.w, best.h]
    info["follow_dist"] = round(best_dist, 1)

    if best_dist < self.follow_close_dist:
      if abs(dx) < 8 and abs(dy) < 8:
        dx = 12 if dx >= 0 else -12
        dy = 12 if dy >= 0 else -12
      info["rule"] = "follow_close"
    else:
      info["rule"] = "follow"

    info["reason"] = f"dx={dx:.0f} dy={dy:.0f} dist={best_dist:.0f}"
    action = self._vector_to_move(dx, dy)
    if action >= 1:
      self._last_follow_action = action
      self._last_follow_rule = str(info["rule"])
      self._last_follow_at = time.monotonic()
      self._last_target = info["target"]
    return action, info

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
