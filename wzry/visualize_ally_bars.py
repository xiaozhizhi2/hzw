from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "debug_uploads"
OUTPUT_DIR = ROOT / "deal_uploads"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def detect_ally_health_bars(image_path: str | Path, output_path: str | Path) -> int:
  img = cv2.imread(str(image_path))
  if img is None:
    print(f"无法读取图片: {image_path}")
    return -1

  hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
  lower_blue = np.array([90, 50, 50])
  upper_blue = np.array([130, 255, 255])
  mask = cv2.inRange(hsv, lower_blue, upper_blue)

  kernel = np.ones((5, 5), np.uint8)
  mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
  mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

  contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

  count = 0
  for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    if 33 <= h <= 55:
      count += 1
      cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
      text = f"W:{w}, H:{h}"
      cv2.putText(img, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
      print(f"  血条 {count}: ({x},{y}) {w}x{h}")

  out = Path(output_path)
  out.parent.mkdir(parents=True, exist_ok=True)
  cv2.imwrite(str(out), img)
  if count == 0:
    print(f"  未检测到符合高度条件的队友血条 -> {out.name}")
  else:
    print(f"  共 {count} 个 -> {out.name}")
  return count


def process_upload_dir(
  input_dir: Path = INPUT_DIR,
  output_dir: Path = OUTPUT_DIR,
) -> None:
  if not input_dir.is_dir():
    print(f"输入目录不存在: {input_dir}")
    return

  files = sorted(
    p for p in input_dir.iterdir()
    if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
  )
  if not files:
    print(f"目录内无图片: {input_dir}")
    return

  output_dir.mkdir(parents=True, exist_ok=True)
  print(f"输入: {input_dir} ({len(files)} 张)")
  print(f"输出: {output_dir}\n")

  total_bars = 0
  for i, src in enumerate(files, 1):
    dst = output_dir / src.name
    print(f"[{i}/{len(files)}] {src.name}")
    n = detect_ally_health_bars(src, dst)
    if n > 0:
      total_bars += n
    print()

  print(f"完成: {len(files)} 张, 累计检出血条 {total_bars} 个")


if __name__ == "__main__":
  process_upload_dir()
