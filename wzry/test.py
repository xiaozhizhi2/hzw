import cv2
import numpy as np

def detect_teammate_bars(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None:
        print(f"错误：无法读取图片 {input_path}")
        return []

    img_h, img_w = img.shape[:2]
    img_result = img.copy()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # ===================== 参数区（适配2133×960）=====================
    # 1. 黑色血条外槽的阈值（越暗越容易被识别为槽）
    dark_threshold = 40  # 灰度值低于此值视为黑色槽背景
    # 2. 血条槽的尺寸筛选
    slot_min_w = 130
    slot_max_w = 220
    slot_min_h = 12
    slot_max_h = 22
    slot_min_ratio = 8   # 槽的宽高比（血条槽是很长的矩形）
    # 3. 内部蓝色填充要求
    blue_fill_min_ratio = 0.2  # 槽内蓝色像素占比至少20%，排除纯黑条
    lower_blue = np.array([90, 60, 130])
    upper_blue = np.array([130, 255, 255])
    # 4. 区域过滤
    exclude_top = 150
    exclude_bottom = 200
    # =================================================================

    # ---------- 第一步：定位黑色血条外槽 ----------
    # 提取深色区域（血条的黑色背景槽）
    _, dark_mask = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)

    # 形态学：横向膨胀，把断裂的黑槽连起来
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 2))
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel_h, iterations=2)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel_h, iterations=1)

    # 查找黑槽轮廓
    slot_contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bar_list = []
    for slot_cnt in slot_contours:
        x, y, w, h = cv2.boundingRect(slot_cnt)
        aspect_ratio = w / h

        # 形状过滤：不符合血条槽特征的直接排除
        if not (slot_min_w <= w <= slot_max_w and slot_min_h <= h <= slot_max_h):
            continue
        if aspect_ratio < slot_min_ratio:
            continue
        if y < exclude_top or y > img_h - exclude_bottom:
            continue

        # ---------- 第二步：在槽内验证蓝色填充 ----------
        roi_hsv = hsv[y:y+h, x:x+w]
        blue_mask = cv2.inRange(roi_hsv, lower_blue, upper_blue)
        blue_pixel_count = cv2.countNonZero(blue_mask)
        total_pixel = w * h
        fill_ratio = blue_pixel_count / total_pixel

        # 蓝色填充占比达标，才判定为队友血条
        if fill_ratio < blue_fill_min_ratio:
            continue

        # 计算蓝色填充的平均RGB
        roi_bgr = img[y:y+h, x:x+w]
        avg_bgr = cv2.mean(roi_bgr, mask=blue_mask)[:3]
        avg_rgb = (int(avg_bgr[2]), int(avg_bgr[1]), int(avg_bgr[0]))

        # 计算蓝色填充部分的实际宽度（当前血量宽度）
        # 找到最右侧的蓝色像素，得到当前血量宽度
        cols = np.max(blue_mask, axis=0)
        blue_cols = np.where(cols > 0)[0]
        if len(blue_cols) == 0:
            continue
        fill_width = blue_cols[-1] - blue_cols[0] + 1

        bar_info = {
            "slot_position_xy": (x, y),    # 整个血条槽的左上角
            "slot_width_px": w,            # 血条槽总宽度
            "slot_height_px": h,           # 血条槽高度
            "fill_width_px": fill_width,   # 当前血量填充宽度
            "avg_rgb": avg_rgb,
            "fill_ratio": round(fill_ratio, 3)
        }
        bar_list.append(bar_info)

    # 按y坐标从上到下排序
    bar_list.sort(key=lambda x: x["slot_position_xy"][1])

    # ---------- 绘制结果 ----------
    for idx, bar in enumerate(bar_list, 1):
        x, y = bar["slot_position_xy"]
        w, h = bar["slot_width_px"], bar["slot_height_px"]
        # 红色框住整个血条槽
        cv2.rectangle(img_result, (x, y), (x + w, y + h), (0, 0, 255), 2)
        label = f"Ally{idx} ({x},{y}) W:{w} H:{h}"
        cv2.putText(img_result, label, (x, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

    # 控制台输出
    print(f"共检测到 {len(bar_list)} 个队友蓝色血条：")
    for idx, bar in enumerate(bar_list, 1):
        print(f"\n【队友血条 {idx}】")
        print(f"  血条槽左上角: {bar['slot_position_xy']}")
        print(f"  槽总宽度: {bar['slot_width_px']} px")
        print(f"  槽高度: {bar['slot_height_px']} px")
        print(f"  当前血量填充宽度: {bar['fill_width_px']} px")
        print(f"  填充占比: {bar['fill_ratio']}")
        print(f"  填充平均RGB: {bar['avg_rgb']}")

    cv2.imwrite(output_path, img_result)
    print(f"\n结果图已保存到: {output_path}")

    return bar_list

if __name__ == "__main__":
    input_file = "play_00008_n0_idle.png"
    output_file = "play_00008_n0_idle_result.png"
    detect_teammate_bars(input_file, output_file)