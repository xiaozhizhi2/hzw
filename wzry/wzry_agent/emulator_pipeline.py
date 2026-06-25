from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .config import Config
from .phone_executor import create_executor
from .ppo import ACTION_NAMES, NUM_ACTIONS, ActionDecision
from .rule_agent import RuleAgent
from .screenshot import ScreenshotCapture


@dataclass
class EmulatorResult:
  image_shape: tuple[int, int, int]
  decision: ActionDecision
  executed: bool = False
  debug: dict = field(default_factory=dict)


class EmulatorPipeline:
  """ADB 真机：截图 → 规则决策 → 操作。"""

  def __init__(self, config_path: str | None = None, config: Config | None = None) -> None:
    self.config = config or Config.load(config_path)
    self.screenshot = ScreenshotCapture(self.config)
    self.agent = RuleAgent.from_config(self.config)
    self.executor = create_executor(self.config)

  def run_once(self, image: np.ndarray | None = None, execute: bool = False) -> EmulatorResult:
    frame = image if image is not None else self.screenshot.capture()
    action_id, info = self.agent.decide(frame)
    decision = ActionDecision(
      action_id=action_id,
      action_name=ACTION_NAMES[action_id],
      confidence=1.0,
      value=0.0,
      logits=np.zeros(NUM_ACTIONS, dtype=np.float32),
      click_pos=None,
    )
    executed = self.executor.execute(decision) if execute else False
    return EmulatorResult(
      image_shape=frame.shape,
      decision=decision,
      executed=executed,
      debug={"pipeline": self.executor.mode, "rule": info},
    )

  def run_loop(self, interval_sec: float = 0.2, max_steps: int | None = None, execute: bool = True) -> None:
    step = 0
    try:
      while max_steps is None or step < max_steps:
        result = self.run_once(execute=execute)
        self._print_result(result)
        step += 1
        if interval_sec > 0:
          import time

          time.sleep(interval_sec)
    finally:
      self.executor.release_all()

  @staticmethod
  def _print_result(result: EmulatorResult) -> None:
    print("=" * 60)
    print(f"画面尺寸: {result.image_shape}")
    print(f"模式: {result.debug.get('pipeline')}")
    print("-" * 60)
    print("【规则决策 → 触控】")
    print(f"  动作: {result.decision.action_name} (id={result.decision.action_id})")
    print(f"  规则: {result.debug.get('rule')}")
    print(f"  已执行: {result.executed}")
    print("=" * 60)
