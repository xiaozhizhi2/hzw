"""批量检测 debug_uploads 截图，逻辑与 run_bridge.py 相同（FollowAgent + RapidOCR 名字）。"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from wzry_agent.config import Config
from wzry_agent.follow_agent import FollowAgent
from wzry_agent.ppo import ACTION_NAMES

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "debug_uploads"
DEFAULT_OUTPUT = ROOT / "deal_uploads"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def draw_result(
  img,
  *,
  found: bool,
  info: dict,
  action_id: int,
  teammate_name: str,
) -> None:
  h, w = img.shape[:2]
  player = info.get("player") or [w * 0.5, h * 0.55]
  px, py = int(player[0]), int(player[1])
  cv2.drawMarker(img, (px, py), (255, 200, 0), cv2.MARKER_CROSS, 20, 2)

  tgt = info.get("target")
  if tgt:
    x, y, bw, bh = int(tgt["x"]), int(tgt["y"]), int(tgt["w"]), int(tgt["h"])
    cv2.rectangle(img, (x, y), (x + bw, y + bh), (0, 0, 255), 2)
    fx, fy = int(tgt.get("follow_x", x + bw / 2)), int(tgt.get("follow_y", y + bh))
    cv2.circle(img, (fx, fy), 8, (0, 255, 0), 2)
    cv2.line(img, (px, py), (fx, fy), (0, 255, 0), 1)
    label = f"{tgt.get('text', '')} score={tgt.get('score', 0):.2f}"
    cv2.putText(img, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

  rule = info.get("rule", "idle")
  act = ACTION_NAMES.get(action_id, str(action_id))
  status = "OK" if found else "MISS"
  color = (0, 180, 0) if found else (0, 0, 220)
  header = f"{status} | follow={teammate_name!r} | rule={rule} | act={act}"
  cv2.rectangle(img, (0, 0), (w, 36), (0, 0, 0), -1)
  cv2.putText(img, header, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
  reason = str(info.get("reason", ""))[:120]
  if reason:
    cv2.putText(img, reason, (8, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)


def detect_one(agent: FollowAgent, input_path: Path, output_path: Path) -> dict:
  img = cv2.imread(str(input_path))
  if img is None:
    return {"file": input_path.name, "ok": False, "error": "read_failed"}

  # 每张图独立检测，不沿用上一帧 sticky
  agent._last_follow_action = 0
  agent._last_follow_at = 0.0
  agent._last_follow_rule = "idle"
  agent._last_target = None

  finder = agent._finder
  hit = finder.find(img) if finder else None
  action_id, info = agent.decide(img)
  found = hit is not None

  if hit is not None:
    info = dict(info)
    info["target"] = {
      "x": hit.x,
      "y": hit.y,
      "w": hit.w,
      "h": hit.h,
      "cx": hit.cx,
      "cy": hit.cy,
      "follow_x": hit.follow_x,
      "follow_y": hit.follow_y,
      "text": hit.text,
      "score": hit.score,
      "method": hit.method,
    }
    info["target_found"] = 1
  draw_result(
    img,
    found=found,
    info=info,
    action_id=action_id,
    teammate_name=agent.teammate_name,
  )
  output_path.parent.mkdir(parents=True, exist_ok=True)
  cv2.imwrite(str(output_path), img)

  tgt = info.get("target") or {}
  return {
    "file": input_path.name,
    "ok": found,
    "rule": info.get("rule") if found else "idle",
    "action": ACTION_NAMES.get(action_id, action_id) if found else "IDLE",
    "text": hit.text if hit else tgt.get("text"),
    "score": hit.score if hit else tgt.get("score"),
    "reason": info.get("reason") if found else f"name_not_found:{agent.teammate_name}",
  }


def process_dir(
  input_dir: Path,
  output_dir: Path,
  *,
  config_path: str | None = None,
) -> list[dict]:
  config = Config.load(config_path)
  agent = FollowAgent.from_config(config)
  name = agent.teammate_name
  if not name:
    raise SystemExit("config.yaml 中 follow.teammate_name 未配置")

  files = sorted(
    p for p in input_dir.iterdir()
    if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
  )
  if not files:
    print(f"目录内无图片: {input_dir}")
    return []

  print(f"跟随目标: {name!r}")
  print(f"输入: {input_dir} ({len(files)} 张)")
  print(f"输出: {output_dir}\n")

  results: list[dict] = []
  for i, src in enumerate(files, 1):
    dst = output_dir / src.name
    row = detect_one(agent, src, dst)
    results.append(row)
    mark = "OK" if row.get("ok") else "MISS"
    text = row.get("text") or "-"
    score = row.get("score")
    score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "-"
    print(f"[{i}/{len(files)}] {mark} {src.name} text={text!r} score={score_txt} rule={row.get('rule')}")

  ok = sum(1 for r in results if r.get("ok"))
  total = len(results)
  play = [r for r in results if r["file"].startswith("play_")]
  play_ok = sum(1 for r in play if r.get("ok"))
  wait = [r for r in results if r["file"].startswith("wait_")]
  wait_ok = sum(1 for r in wait if r.get("ok"))

  print("\n========== 识别统计 ==========")
  print(f"全部: {ok}/{total} = {100 * ok / total:.1f}%")
  if play:
    print(f"play_*: {play_ok}/{len(play)} = {100 * play_ok / len(play):.1f}%")
  if wait:
    print(f"wait_*: {wait_ok}/{len(wait)} = {100 * wait_ok / len(wait):.1f}%")
  print("==============================")
  return results


def main() -> None:
  parser = argparse.ArgumentParser(description="用 run_bridge 相同逻辑批量检测截图")
  parser.add_argument("--input", default=str(DEFAULT_INPUT), help="输入目录")
  parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出目录")
  parser.add_argument("--config", default=None, help="config.yaml 路径")
  args = parser.parse_args()
  process_dir(Path(args.input), Path(args.output), config_path=args.config)


if __name__ == "__main__":
  main()
