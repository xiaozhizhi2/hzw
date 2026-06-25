from __future__ import annotations

import time

from .config import Config
from .learn_bridge import LearnBridge, PhoneStep
from .match_flow import check_game_ready, detect_match_result, is_game_started
from .rule_agent import RuleAgent, action_name


class RulePlayServer:
  """手机截图 + 规则决策，循环打局。"""

  def __init__(self, config: Config) -> None:
    self.config = config
    self.agent = RuleAgent.from_config(config)
    bridge_host = str(config.get("bridge", "host", default="0.0.0.0"))
    bridge_port = int(config.get("bridge", "port", default=9330))
    pc_host = config.get("bridge", "pc_host", default=None)
    self.move_hold_ms = int(config.get("bridge", "move_hold_ms", default=400))
    self.match_cfg = dict(config.get("match", default={}) or {})
    self.kda_confirm = int(self.match_cfg.get("kda_confirm_frames", 2))
    self.result_confirm = int(self.match_cfg.get("result_confirm_frames", 2))
    self._bridge = LearnBridge(
      self._on_step,
      host=bridge_host,
      port=bridge_port,
      pc_host=str(pc_host) if pc_host else None,
    )

  def run(self, *, log_every: int = 16) -> None:
    self._log_every = log_every
    self._bridge.start()
    print(f"[bridge] 手机 PC_HOST 填: {self._bridge.pc_host}", flush=True)
    print("[bridge] 规则决策运行中，Ctrl+C 停止", flush=True)
    try:
      while True:
        time.sleep(0.5)
    except KeyboardInterrupt:
      print("[bridge] 收到停止信号", flush=True)
    finally:
      self._bridge.stop()

  def _on_step(self, step: PhoneStep) -> dict:
    phase = step.phase

    if phase == "wait":
      return self._handle_wait(step)

    if phase != "play":
      return {"action_id": 0, "hold_ms": self.move_hold_ms}

    if step.frame is None:
      return {"action_id": 0, "hold_ms": self.move_hold_ms}

    if getattr(self, "_pending_play_start", False):
      self._pending_play_start = False
      self._match_count = getattr(self, "_match_count", 0) + 1
      self._playing_steps = 0
      self._result_streak = 0
      self._pending_result = None
      self._kda_zero_streak = 0
      self.agent.reset_match()
      print(f"[对局 {self._match_count}] 开始", flush=True)

    frame = step.frame
    action_id, info = self.agent.decide(frame)
    self._playing_steps = getattr(self, "_playing_steps", 0) + 1

    detected = detect_match_result(frame, self.match_cfg)
    if detected:
      self._result_streak = getattr(self, "_result_streak", 0) + 1
      self._pending_result = detected
    else:
      self._result_streak = 0

    game_end = False
    end_result = None
    if self._result_streak >= self.result_confirm and self._pending_result:
      game_end = True
      end_result = self._pending_result
      print(
        f"[对局 {self._match_count}] 结束 ({end_result})",
        flush=True,
      )
      self._pending_result = None
      self._result_streak = 0

    if self._log_every > 0 and self._playing_steps % self._log_every == 0:
      print(
        f"[对局 {getattr(self, '_match_count', 0)} 步 {self._playing_steps}] "
        f"规则={info.get('rule')} 动作={action_name(action_id)} "
        f"详情={info}",
        flush=True,
      )

    body = {
      "action_id": action_id,
      "hold_ms": self.move_hold_ms,
      "game_end": game_end,
      "rule": info.get("rule"),
    }
    if end_result:
      body["result"] = end_result
    return body

  def _handle_wait(self, step: PhoneStep) -> dict:
    if step.frame is None:
      return {"ready": False, "hud": "?"}
    kda_cfg = {"kda_crop": self.match_cfg.get("kda_crop", [0.03, 0.12, 0.38, 0.62])}
    stats = check_game_ready(step.frame, kda_cfg)
    streak = getattr(self, "_kda_zero_streak", 0)
    if is_game_started(stats):
      streak += 1
    else:
      streak = 0
    self._kda_zero_streak = streak
    ready = streak >= self.kda_confirm
    if ready:
      self._pending_play_start = True
    hud = str(stats) if stats else "?"
    return {"ready": ready, "hud": hud}
