from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray


class ActionType(IntEnum):
  IDLE = 0
  MOVE_UP = 1
  MOVE_DOWN = 2
  MOVE_LEFT = 3
  MOVE_RIGHT = 4
  MOVE_UP_LEFT = 5
  MOVE_UP_RIGHT = 6
  MOVE_DOWN_LEFT = 7
  MOVE_DOWN_RIGHT = 8
  ATTACK = 9
  SKILL_1 = 10
  SKILL_2 = 11
  SKILL_3 = 12
  RECALL = 13
  HEAL = 14
  SUMMONER = 15


ACTION_NAMES = {item.value: item.name for item in ActionType}
NUM_ACTIONS = len(ActionType)


@dataclass
class ActionDecision:
  action_id: int
  action_name: str
  confidence: float
  value: float
  logits: NDArray[np.float32]
  click_pos: tuple[int, int] | None = None
