"""跟随指定队友名字（PC 端决策），支持多个队友，自动选择最近的。"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .name_detector import NameTarget, TeammateNameFinder
from .ppo import ActionType


@dataclass
class FollowAgent:
  teammate_names: list[str] = field(default_factory=list)
  player_x_ratio: float = 0.5
  player_y_ratio: float = 0.55
  follow_max_dist_ratio: float = 1.0
  follow_close_dist: float = 15.0
  sticky_ms: int = 2000
  _finder: TeammateNameFinder | None = field(default=None, init=False, repr=False)
  _step: int = field(default=0, init=False, repr=False)
  _last_follow_action: int = field(default=0, init=False, repr=False)
  _last_follow_rule: str = field(default="idle", init=False, repr=False)
  _last_follow_at: float = field(default=0.0, init=False, repr=False)
  _last_target: dict | None = field(default=None, init=False, repr=False)

  @classmethod
  def from_config(cls, config) -> FollowAgent:
    f = dict(config.get("follow", default={}) or {})
    # 支持两种配置格式兼容：旧的 teammate_name 或新的 teammate_names
    names = f.get("teammate_names") or [f.get("teammate_name", "")]
    if isinstance(names, str):
      names = [n.strip() for n in names.split(",") if n.strip()]
    agent = cls(
      teammate_names=list(names),
      player_x_ratio=float(f.get("player_x_ratio", 0.5)),
      player_y_ratio=float(f.get("player_y_ratio", 0.55)),
      follow_max_dist_ratio=float(f.get("follow_max_dist_ratio", 1.0)),
      follow_close_dist=float(f.get("follow_close_dist", 15.0)),
      sticky_ms=int(f.get("sticky_ms", 2000)),
    )
    agent._finder = TeammateNameFinder.from_config(config)
    return agent

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

  @staticmethod
  def _target_info(hit: NameTarget) -> dict:
    return {
      "x": hit.x,
      "y": hit.y,
      "w": hit.w,
      "h": hit.h,
      "cx": round(hit.cx, 1),
      "cy": round(hit.cy, 1),
      "follow_x": round(hit.follow_x, 1),
      "follow_y": round(hit.follow_y, 1),
      "text": hit.text,
      "score": round(hit.score, 3),
      "method": hit.method,
    }

  def decide(self, frame: NDArray[np.uint8]) -> tuple[int, dict]:
    self._step += 1
    info: dict = {
      "step": self._step,
      "teammate_names": self.teammate_names,
    }
    h, w = frame.shape[:2]
    player_x = w * self.player_x_ratio
    player_y = h * self.player_y_ratio
    max_follow = max(w, h) * self.follow_max_dist_ratio
    info["player"] = [round(player_x, 1), round(player_y, 1)]

    if not self.teammate_names or self._finder is None:
      info["rule"] = "idle"
      info["reason"] = "no_teammate_names"
      info["target_found"] = 0
      info["ally_count"] = 0
      return int(ActionType.IDLE), info

    # 查找所有匹配的队友
    targets = self._finder.find_all(frame)
    info["target_found"] = 1 if targets else 0
    info["ally_count"] = len(targets)

    if not targets:
      sticky = self._sticky_follow(info)
      if sticky:
        return sticky
      info["rule"] = "idle"
      info["reason"] = f"no_teammates_found:{self.teammate_names}"
      return int(ActionType.IDLE), info

    # 选择最近的队友
    best_target = None
    best_dist = float("inf")
    for target in targets:
      tx, ty = target.follow_x, target.follow_y
      dist = math.hypot(tx - player_x, ty - player_y)
      if dist < best_dist:
        best_dist = dist
        best_target = target

    hit = best_target
    info["target"] = self._target_info(hit)
    tx, ty = hit.follow_x, hit.follow_y
    dist = math.hypot(tx - player_x, ty - player_y)
    info["follow_dist"] = round(dist, 1)

    # 移除最大距离限制，即使很远也继续朝队友移动
    dx = tx - player_x
    dy = ty - player_y
    if dist < self.follow_close_dist:
      if abs(dx) < 8 and abs(dy) < 8:
        dx = 12 if dx >= 0 else -12
        dy = 12 if dy >= 0 else -12
      info["rule"] = "follow_close"
    else:
      info["rule"] = "follow"

    info["reason"] = (
      f"{hit.method} text={hit.text!r} score={hit.score:.2f} "
      f"dx={dx:.0f} dy={dy:.0f} dist={dist:.0f} "
      f"teammates={len(targets)}"
    )
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
