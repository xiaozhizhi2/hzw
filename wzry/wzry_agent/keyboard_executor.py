from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .ppo import ActionDecision, ActionType
from .win_input import GameInput, foreground_title


@dataclass(frozen=True)
class KeyBinding:
  tap: str | None = None
  hold: tuple[str, ...] = ()


class KeyboardExecutor:
  """PPO 动作 → 键盘事件（SendInput）。"""

  def __init__(self, config: Config) -> None:
    self.config = config
    self.mode = "keyboard"
    self.tap_ms = int(config.get("keyboard", "tap_ms", default=100))
    self.hold_ms = int(config.get("keyboard", "hold_ms", default=400))
    titles = config.get("runtime", "window_titles", default=None)
    backend = str(config.get("keyboard", "backend", default="vk"))
    focus_policy = str(config.get("keyboard", "focus_policy", default="manual"))
    self._input = GameInput(
      titles,
      config=config,
      backend=backend,
      focus_policy=focus_policy,
    )
    self._bindings = self._load_bindings()

  def _load_bindings(self) -> dict[ActionType, KeyBinding]:
    raw = self.config.get("keyboard", "bindings", default={}) or {}
    defaults: dict[ActionType, KeyBinding] = {
      ActionType.IDLE: KeyBinding(),
      ActionType.MOVE_UP: KeyBinding(hold=("w",)),
      ActionType.MOVE_DOWN: KeyBinding(hold=("s",)),
      ActionType.MOVE_LEFT: KeyBinding(hold=("a",)),
      ActionType.MOVE_RIGHT: KeyBinding(hold=("d",)),
      ActionType.MOVE_UP_LEFT: KeyBinding(hold=("w", "a")),
      ActionType.MOVE_UP_RIGHT: KeyBinding(hold=("w", "d")),
      ActionType.MOVE_DOWN_LEFT: KeyBinding(hold=("s", "a")),
      ActionType.MOVE_DOWN_RIGHT: KeyBinding(hold=("s", "d")),
      ActionType.ATTACK: KeyBinding(tap="space"),
      ActionType.SKILL_1: KeyBinding(tap="j"),
      ActionType.SKILL_2: KeyBinding(tap="i"),
      ActionType.SKILL_3: KeyBinding(tap="o"),
      ActionType.RECALL: KeyBinding(tap="b"),
      ActionType.HEAL: KeyBinding(tap="f"),
      ActionType.SUMMONER: KeyBinding(tap="g"),
    }
    for name, spec in raw.items():
      try:
        action = ActionType[name.upper()]
      except KeyError:
        continue
      tap = spec.get("tap")
      hold = tuple(spec.get("hold", []))
      defaults[action] = KeyBinding(tap=tap, hold=hold)
    return defaults

  def prepare(self) -> bool:
    return self._input.prepare()

  def execute(self, decision: ActionDecision, *, step: int = 0) -> bool:
    del step
    binding = self._bindings.get(ActionType(decision.action_id), KeyBinding())
    if binding.tap is None and not binding.hold:
      return False
    if not self._input.ensure_ready():
      return False
    return self._apply(binding, decision.action_name)

  def _apply(self, binding: KeyBinding, action_name: str) -> bool:
    self._input.release_moves()
    if binding.hold:
      ok = self._input.hold(binding.hold, hold_ms=self.hold_ms)
      if ok:
        print(
          f"[按键] {action_name} hold={binding.hold} → 屏幕键位 前台={foreground_title()!r}",
          flush=True,
        )
      return ok
    if binding.tap:
      ok = self._input.tap(binding.tap, tap_ms=self.tap_ms)
      if ok:
        print(
          f"[按键] {action_name} tap={binding.tap} → 屏幕键位 前台={foreground_title()!r}",
          flush=True,
        )
      return ok
    return False

  def release_all(self) -> None:
    self._input.release_moves()
