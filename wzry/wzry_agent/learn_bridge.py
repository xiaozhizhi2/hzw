from __future__ import annotations

import base64
import json
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

import cv2
import numpy as np
from numpy.typing import NDArray


def detect_pc_ip() -> str:
  try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
      sock.connect(("8.8.8.8", 80))
      return sock.getsockname()[0]
  except OSError:
    return "127.0.0.1"


@dataclass(frozen=True)
class PhoneStep:
  """手机上报：截图 + 脚本阶段（wait/play），不含游戏语义。"""

  phase: str
  frame: NDArray[np.uint8] | None = None


class LearnBridge:
  """手机 POST 截图+阶段，PC OCR 判断并返回动作。"""

  def __init__(
    self,
    on_step: Callable[[PhoneStep], dict],
    *,
    host: str = "0.0.0.0",
    port: int = 9330,
    pc_host: str | None = None,
  ) -> None:
    self.on_step = on_step
    self.host = host
    self.port = port
    self.pc_host = pc_host or detect_pc_ip()
    self._httpd: ThreadingHTTPServer | None = None
    self._thread: threading.Thread | None = None
    self.step_count = 0

  @property
  def url(self) -> str:
    return f"http://{self.pc_host}:{self.port}/step"

  def start(self) -> None:
    if self._httpd is not None:
      return
    bridge = self

    class Handler(BaseHTTPRequestHandler):
      def log_message(self, format: str, *args) -> None:
        msg = format % args
        if " 500 " in msg or " 404 " in msg:
          print(f"[bridge] {self.address_string()} {msg}", flush=True)

      def do_POST(self) -> None:
        if self.path.split("?", 1)[0].rstrip("/") != "/step":
          self.send_error(404)
          return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
          payload = json.loads(raw.decode("utf-8"))
          # phase: wait=等开局截图轮询, play=对战中；兼容旧字段 event
          phase = payload.get("phase") or payload.get("event") or "play"
          phase = str(phase)
          if phase == "wait_start":
            phase = "wait"
          elif phase == "step":
            phase = "play"

          frame = None
          image_b64 = payload.get("image") or ""
          if image_b64:
            raw_img = base64.b64decode(image_b64)
            arr = np.frombuffer(raw_img, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
              raise ValueError("截图解码失败")

          step = PhoneStep(phase=phase, frame=frame)
          cmd = bridge.on_step(step)
          bridge.step_count += 1
          body = json.dumps(cmd, ensure_ascii=False).encode("utf-8")
          self.send_response(200)
          self.send_header("Content-Type", "application/json; charset=utf-8")
          self.send_header("Content-Length", str(len(body)))
          self.end_headers()
          self.wfile.write(body)
        except Exception as exc:
          err = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
          self.send_response(500)
          self.send_header("Content-Type", "application/json; charset=utf-8")
          self.send_header("Content-Length", str(len(err)))
          self.end_headers()
          self.wfile.write(err)

    self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
    self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
    self._thread.start()
    print(f"[bridge] 学习服务: {self.url}", flush=True)
    print("[bridge] 手机运行 autox/wzry_play_bridge.js", flush=True)

  def stop(self) -> None:
    if self._httpd is None:
      return
    self._httpd.shutdown()
    self._httpd.server_close()
    self._httpd = None
