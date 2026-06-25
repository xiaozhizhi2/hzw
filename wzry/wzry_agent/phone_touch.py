from __future__ import annotations

from .config import Config
from .ppo import ActionDecision, ActionType

DEFAULT_POINTS: dict[str, list[float]] = {
  "attack": [0.907, 0.608],
  "skill_1": [0.755, 0.583],
  "skill_2": [0.694, 0.552],
  "skill_3": [0.795, 0.595],
  "heal": [0.620, 0.570],
  "summoner": [0.670, 0.580],
  "recall": [0.059, 0.537],
}

ACTION_POINT: dict[ActionType, str | None] = {
  ActionType.IDLE: None,
  ActionType.MOVE_UP: None,
  ActionType.MOVE_DOWN: None,
  ActionType.MOVE_LEFT: None,
  ActionType.MOVE_RIGHT: None,
  ActionType.MOVE_UP_LEFT: None,
  ActionType.MOVE_UP_RIGHT: None,
  ActionType.MOVE_DOWN_LEFT: None,
  ActionType.MOVE_DOWN_RIGHT: None,
  ActionType.ATTACK: "attack",
  ActionType.SKILL_1: "skill_1",
  ActionType.SKILL_2: "skill_2",
  ActionType.SKILL_3: "skill_3",
  ActionType.RECALL: "recall",
  ActionType.HEAL: "heal",
  ActionType.SUMMONER: "summoner",
}

MOVE_VECTOR: dict[ActionType, tuple[float, float]] = {
  ActionType.MOVE_UP: (0.0, -1.0),
  ActionType.MOVE_DOWN: (0.0, 1.0),
  ActionType.MOVE_LEFT: (-1.0, 0.0),
  ActionType.MOVE_RIGHT: (1.0, 0.0),
  ActionType.MOVE_UP_LEFT: (-0.7, -0.7),
  ActionType.MOVE_UP_RIGHT: (0.7, -0.7),
  ActionType.MOVE_DOWN_LEFT: (-0.7, 0.7),
  ActionType.MOVE_DOWN_RIGHT: (0.7, 0.7),
}


class PhoneTouchMixin:
  def _load_touch_config(self, config: Config) -> None:
    self.tap_ms = int(config.get("touch", "tap_ms", default=150))
    self.swipe_ms = int(config.get("touch", "swipe_ms", default=350))
    center = config.get("touch", "joystick_center", default=[0.12, 0.78])
    self.joystick_center = (float(center[0]), float(center[1]))
    self.swipe_radius = float(config.get("touch", "swipe_radius", default=0.08))
    self.skill_hold_ms = int(config.get("touch", "skill_hold_ms", default=120))
    self.skill_swipe_ms = int(config.get("touch", "skill_swipe_ms", default=500))
    self.skill_drag = config.get("touch", "skill_drag", default=[-0.18, -0.14])
    self.skill_mode = str(config.get("touch", "skill_mode", default="wheel")).lower()
    raw = config.get("touch", "points", default={}) or {}
    self.points = {**DEFAULT_POINTS, **raw}
    self._screen: tuple[int, int] | None = None

  SKILL_ACTIONS = {
    ActionType.SKILL_1,
    ActionType.SKILL_2,
    ActionType.SKILL_3,
    ActionType.HEAL,
    ActionType.SUMMONER,
  }

  def _to_px(self, norm: list[float]) -> tuple[int, int]:
    w, h = self._ensure_screen()
    return int(norm[0] * w), int(norm[1] * h)

  def _plan_action(self, decision: ActionDecision) -> dict | None:
    action = ActionType(decision.action_id)
    if action == ActionType.IDLE:
      return None
    if action in MOVE_VECTOR:
      w, h = self._ensure_screen()
      cx, cy = self._to_px([self.joystick_center[0], self.joystick_center[1]])
      radius = int(min(w, h) * self.swipe_radius)
      vx, vy = MOVE_VECTOR[action]
      return {
        "kind": "swipe",
        "name": decision.action_name,
        "x1": cx,
        "y1": cy,
        "x2": cx + int(vx * radius),
        "y2": cy + int(vy * radius),
        "duration": self.swipe_ms,
      }
    point_name = ACTION_POINT.get(action)
    if not point_name:
      return None
    norm = self.points.get(point_name)
    if not norm:
      return None
    x, y = self._to_px(norm)
    if action in self.SKILL_ACTIONS:
      w, h = self._ensure_screen()
      if self.skill_mode == "assist":
        return {"kind": "tap", "name": decision.action_name, "x": x, "y": y}
      dx = int(float(self.skill_drag[0]) * w)
      dy = int(float(self.skill_drag[1]) * h)
      return {
        "kind": "cast",
        "name": decision.action_name,
        "x1": x,
        "y1": y,
        "x2": x + dx,
        "y2": y + dy,
        "duration": self.skill_swipe_ms,
      }
    return {"kind": "tap", "name": decision.action_name, "x": x, "y": y}
