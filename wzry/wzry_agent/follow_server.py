"""AutoJS + PC：手机 POST 截图，PC OpenCV 识别并返回动作。"""

from __future__ import annotations

import time
from pathlib import Path

import cv2

from .config import Config
from .follow_agent import FollowAgent
from .hp_signals import has_hp_bar, hp_signals, in_game_fast
from .learn_bridge import LearnBridge, PhoneStep
from .ppo import ACTION_NAMES


class FollowPlayServer:
  def __init__(self, config: Config) -> None:
    self.config = config
    self.agent = FollowAgent.from_config(config)
    bridge = dict(config.get("bridge", default={}) or {})
    self.move_hold_ms = int(bridge.get("move_hold_ms", 400))
    self.log_every = int(bridge.get("log_every", 4))
    self.save_uploads = bool(bridge.get("save_uploads", False))
    self.save_every = max(1, int(bridge.get("save_every", 1)))
    self.save_max = int(bridge.get("save_max", 500))
    self._save_dir = config.resolve_path(str(bridge.get("save_dir", "debug_uploads")))
    self._save_count = 0
    self._hp_miss = 0
    self._logged_shape = False
    if self.save_uploads:
      self._save_dir.mkdir(parents=True, exist_ok=True)
      print(f"[bridge] 上传截图保存到 {self._save_dir}", flush=True)
    self._bridge = LearnBridge(
      self._on_step,
      host=str(bridge.get("host", "0.0.0.0")),
      port=int(bridge.get("port", 9330)),
      pc_host=bridge.get("pc_host"),
    )

  def _save_frame(
    self,
    frame,
    *,
    phase: str,
    ally_count: int | None = None,
    rule: str | None = None,
  ) -> Path | None:
    if not self.save_uploads:
      return None
    self._save_count += 1
    if self._save_count % self.save_every != 0:
      return None
    n_tag = "" if ally_count is None else f"_n{ally_count}"
    rule_tag = "" if not rule else f"_{rule}"
    name = f"{phase}_{self._save_count:05d}{n_tag}{rule_tag}.png"
    path = self._save_dir / name
    cv2.imwrite(str(path), frame)
    return path

  def _trim_saved(self) -> None:
    if self.save_max <= 0:
      return
    files = sorted(self._save_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    while len(files) > self.save_max:
      files.pop(0).unlink(missing_ok=True)
      files = sorted(self._save_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)

  def _maybe_save(
    self,
    step: PhoneStep,
    *,
    phase: str,
    ally_count: int | None = None,
    rule: str | None = None,
  ) -> None:
    if step.frame is None:
      return
    path = self._save_frame(
      step.frame,
      phase=phase,
      ally_count=ally_count,
      rule=rule,
    )
    if path is not None:
      self._trim_saved()
      if self._save_count <= 3 or self._save_count % self.log_every == 0:
        print(f"[save] {path.name}", flush=True)

  def run(self) -> None:
    self._bridge.start()
    print(f"[bridge] 手机脚本填 PC_HOST = {self._bridge.pc_host}", flush=True)
    print(f"[bridge] 端口 {self._bridge.port}，运行 autox/wzry_play_bridge.js", flush=True)
    print("[bridge] Ctrl+C 停止", flush=True)
    try:
      while True:
        time.sleep(0.5)
    except KeyboardInterrupt:
      print("[bridge] 停止", flush=True)
    finally:
      self._bridge.stop()

  def _on_step(self, step: PhoneStep) -> dict:
    if step.phase == "wait":
      return self._handle_wait(step)
    return self._handle_play(step)

  def _handle_wait(self, step: PhoneStep) -> dict:
    if step.frame is None:
      return {"ready": False, "hold_ms": self.move_hold_ms}
    ready = has_hp_bar(step.frame)
    sig = hp_signals(step.frame)
    if ready:
      self._hp_miss = 0
      print(f"[wait] 识别到血条 {sig}", flush=True)
    self._maybe_save(step, phase="wait", rule="ready" if ready else "wait")
    return {"ready": ready, "hold_ms": self.move_hold_ms, "signals": sig}

  def _handle_play(self, step: PhoneStep) -> dict:
    hold_ms = self.move_hold_ms
    if step.frame is None:
      return {"action_id": 0, "hold_ms": hold_ms, "rule": "idle", "in_game": True}

    in_game = in_game_fast(step.frame)
    if in_game:
      self._hp_miss = 0
    else:
      self._hp_miss += 1

    action_id, info = self.agent.decide(step.frame)
    rule = str(info.get("rule", "idle"))

    if not self._logged_shape and step.frame is not None:
      h, w = step.frame.shape[:2]
      print(f"[play] frame {w}x{h} barH={info.get('bar_h')}", flush=True)
      self._logged_shape = True

    if self.log_every > 0 and info.get("step", 0) % self.log_every == 0:
      allies = info.get("allies") or []
      ally_txt = ""
      if allies:
        a0 = allies[0]
        ally_txt = f" tgt=({a0.get('x')},{a0.get('y')},{a0.get('w')}x{a0.get('h')})"
      print(
        f"[play] step={info.get('step')} rule={rule} "
        f"act={ACTION_NAMES.get(action_id, action_id)} "
        f"n={info.get('ally_count')} barH={info.get('bar_h')}{ally_txt} "
        f"{info.get('reason', '')}",
        flush=True,
      )

    self._maybe_save(
      step,
      phase="play",
      ally_count=int(info.get("ally_count", 0)),
      rule=rule,
    )

    return {
      "action_id": action_id,
      "hold_ms": hold_ms,
      "rule": rule,
      "in_game": self._hp_miss < 3,
      "ally_count": info.get("ally_count", 0),
      "info": info,
    }
