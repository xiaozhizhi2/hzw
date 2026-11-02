"""可拖拽的圆形悬浮球：置顶显示自选股现价与涨跌幅。"""
from __future__ import annotations

import json
import math
import os
import random

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QMenu, QWidget

from data_api import Quote

SIZE = 88
UP = "#e0453c"
DOWN = "#00a860"
FLAT = "#8a919e"
EPS_CHANGE = 0.0005  # 涨跌额平盘判定阈值（以分为最小单位，仅排除 0 附近误差）
DEFAULT_OPACITY = 50  # 默认透明度（%）
DEFAULT_BORDER = True  # 默认显示边框
DEFAULT_EFFECT = True  # 默认显示涨跌特效（涨=烟花 跌=雨）


def _config_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _load_config() -> dict:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "opacity": int(data.get("opacity", DEFAULT_OPACITY)),
            "border": bool(data.get("border", DEFAULT_BORDER)),
            "effect": bool(data.get("effect", DEFAULT_EFFECT)),
        }
    except (OSError, ValueError, TypeError):
        return {
            "opacity": DEFAULT_OPACITY,
            "border": DEFAULT_BORDER,
            "effect": DEFAULT_EFFECT,
        }


def _save_config(cfg: dict) -> None:
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


class FloatBall(QWidget):
    """悬浮球。左键单击开/关面板，拖拽移动，滚轮切换自选股，右键菜单。"""

    toggled = Signal()
    cycle = Signal(int)  # +1 下一只 / -1 上一只
    quit_requested = Signal()

    def __init__(self):
        super().__init__(None)
        self._quote: Quote | None = None
        self._pressed, self._moved = False, False
        self._dragging = False
        self._drag_pos = QPoint()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(SIZE, SIZE)
        cfg = _load_config()
        self._show_border = cfg["border"]
        self._opacity = cfg["opacity"]
        self._show_fx = cfg["effect"]
        # 特效粒子状态
        self._fx_dir = 0  # 0=无 1=涨(烟花) -1=跌(雨)
        self._fx_burst = 0
        self._particles_fx: list[dict] = []
        self._particles_rain: list[dict] = []
        # 跳动状态：基准位置、上次涨跌幅、弹跳参数
        self._base_pos: QPoint | None = None
        self._last_pct: float | None = None
        self._jump_amp = 0.0  # 本次弹跳幅度（0=不跳）
        self._jump_t = 0  # 弹跳帧计数

        self._menu = QMenu(self)
        act_open = self._menu.addAction("打开/隐藏面板")
        act_open.triggered.connect(self.toggled.emit)
        self._menu.addSeparator()

        # 边框设置：可勾选
        self._act_border = self._menu.addAction("显示边框")
        self._act_border.setCheckable(True)
        self._act_border.setChecked(self._show_border)
        self._act_border.toggled.connect(self.toggle_border)
        self._menu.addSeparator()

        # 特效设置：可勾选（涨=烟花 跌=雨）
        self._act_fx = self._menu.addAction("涨跌特效")
        self._act_fx.setCheckable(True)
        self._act_fx.setChecked(self._show_fx)
        self._act_fx.toggled.connect(self.toggle_fx)
        self._menu.addSeparator()

        # 透明度设置：子菜单，可勾选
        self._menu_opacity = self._menu.addMenu("透明度")
        self._opacity_values = (30, 40, 50, 60, 70, 80, 90)
        self._opacity_actions = {}
        for v in self._opacity_values:
            act = self._menu_opacity.addAction(f"{v}%")
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, val=v: self.apply_opacity(val))
            self._opacity_actions[v] = act

        self._menu.addSeparator()
        act_quit = self._menu.addAction("退出")
        act_quit.triggered.connect(self.quit_requested.emit)
        self._menu.setStyleSheet(
            "QMenu{background:#252a34;color:#e8eaed;border:1px solid #3a4150;"
            "font-family:'Microsoft YaHei';font-size:12px;}"
            "QMenu::item{padding:6px 18px;}"
            "QMenu::item:selected{background:#3a4150;}"
        )
        self.apply_opacity(self._opacity)

        # 特效动画定时器（约 30ms/帧）
        self._fx_timer = QTimer(self)
        self._fx_timer.setInterval(30)
        self._fx_timer.timeout.connect(self.step_fx)
        self._fx_timer.start()

    def apply_opacity(self, value: int) -> None:
        """设置悬浮球透明度（30-100%），同步菜单勾选并持久化。"""
        value = max(30, min(100, value))
        self._opacity = value
        self.setWindowOpacity(value / 100.0)
        self._persist()
        for v, act in self._opacity_actions.items():
            act.setChecked(v == value)

    def toggle_border(self, checked: bool) -> None:
        """切换悬浮球边框显示，并持久化。"""
        self._show_border = checked
        self._persist()
        self.update()

    def toggle_fx(self, checked: bool) -> None:
        """切换涨跌特效（涨=烟花 跌=雨），并持久化。"""
        self._show_fx = checked
        self._persist()
        if not checked:
            self._particles_fx.clear()
            self._particles_rain.clear()
        self.update()

    def _persist(self) -> None:
        """把透明度/边框/特效设置写入配置文件。"""
        _save_config(
            {
                "opacity": self._opacity,
                "border": self._show_border,
                "effect": self._show_fx,
            }
        )

    # ------- 涨跌特效粒子引擎 -------
    def step_fx(self) -> None:
        """推进粒子动画：涨=持续烟花，跌=持续下雨。"""
        self._step_jump()
        if not self._quote or not self._show_fx:
            if self._particles_fx or self._particles_rain:
                self._particles_fx.clear()
                self._particles_rain.clear()
                self.update()
            return
        # 涨=烟花 跌=雨 平盘(±EPS_CHANGE 内)=无特效
        change = self._quote.change
        if change > EPS_CHANGE:
            direction = 1
        elif change < -EPS_CHANGE:
            direction = -1
        else:
            direction = 0
        if direction != self._fx_dir:
            self._fx_dir = direction
            self._fx_burst = 0
            self._particles_fx.clear()
            self._particles_rain.clear()
        if direction == 0:
            return
        dt = self._fx_timer.interval()
        h = self.height()
        if direction > 0:
            # 涨：持续放烟花
            self._fx_burst += dt
            if self._fx_burst >= 550:
                self._fx_burst = 0
                self._spawn_firework()
        else:
            # 跌：持续下雨
            for _ in range(random.randint(1, 2)):
                self._particles_rain.append(self._new_drop())
        alive = []
        for fp in self._particles_fx:
            fp["x"] += fp["vx"]
            fp["y"] += fp["vy"]
            fp["vy"] += 0.4  # 重力
            fp["life"] -= dt
            if fp["life"] > 0:
                alive.append(fp)
        self._particles_fx = alive
        alive = []
        for rp in self._particles_rain:
            rp["y"] += rp["speed"] * dt / 30.0
            rp["speed"] *= 1.01
            rp["life"] -= dt
            if rp["life"] > 0 and rp["y"] < h + 4:
                alive.append(rp)
        self._particles_rain = alive
        if self._particles_fx or self._particles_rain:
            self.update()

    def _step_jump(self) -> None:
        """两次刷新间隔涨跌幅变化超 1% 时弹跳一次，幅度随差值增大、逐渐衰减。"""
        if self._dragging:
            return  # 拖拽中不弹跳，避免抢占鼠标移动位置
        if self._base_pos is None:
            self._base_pos = self.pos()
        if self._jump_amp <= 0.0:
            if self.pos() != self._base_pos:
                self.move(self._base_pos)
            return
        self._jump_t += 1
        offset = math.sin(self._jump_t * 0.5) * self._jump_amp
        self._jump_amp *= 0.85  # 阻尼衰减
        if self._jump_amp < 0.15:
            self._jump_amp = 0.0
        self.move(self._base_pos.x(), self._base_pos.y() + int(round(offset)))

    def _spawn_firework(self) -> None:
        """在球内随机位置放一波烟花粒子。"""
        cx = self.width() * random.uniform(0.30, 0.70)
        cy = self.height() * random.uniform(0.28, 0.55)
        colors = ("#ffd166", "#ff8c42", "#ff5e5e", "#ffb347", "#ffffff")
        for _ in range(random.randint(12, 16)):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(0.8, 2.8)
            self._particles_fx.append(
                {
                    "x": cx, "y": cy,
                    "vx": math.cos(ang) * spd,
                    "vy": math.sin(ang) * spd,
                    "life": random.randint(320, 600),
                    "max_life": 600,
                    "r": random.uniform(1.2, 2.4),
                    "color": random.choice(colors),
                }
            )

    def _new_drop(self) -> dict:
        """生成一滴雨。"""
        return {
            "x": random.uniform(4, self.width() - 4),
            "y": random.uniform(-8, 2),
            "speed": random.uniform(2.0, 4.0),
            "len": random.uniform(5, 10),
            "life": random.randint(300, 700),
            "max_life": 700,
            "color": random.choice(("#7fd4ff", "#5cb8ff", "#4ecdc4")),
        }

    def _draw_fx(self, p: QPainter) -> None:
        """绘制烟花/雨滴粒子，透明度随生命衰减。"""
        for fp in self._particles_fx:
            t = max(0.0, fp["life"] / fp["max_life"])
            c = QColor(fp["color"])
            c.setAlpha(int(235 * t))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            r = fp["r"] * (0.5 + 0.5 * t)
            p.drawEllipse(QPointF(fp["x"], fp["y"]), r, r)
        for rp in self._particles_rain:
            t = max(0.0, rp["life"] / rp["max_life"])
            c = QColor(rp["color"])
            c.setAlpha(int(220 * t))
            p.setPen(QPen(c, 1))
            p.drawLine(
                QPointF(rp["x"], rp["y"]),
                QPointF(rp["x"], rp["y"] + rp["len"]),
            )

    def update_quote(self, quote: Quote) -> None:
        # 与上一次刷新相比，涨跌幅变化超 1% 时触发一次弹跳
        prev_pct = self._last_pct
        self._last_pct = quote.change_pct
        if prev_pct is not None:
            delta = abs(quote.change_pct - prev_pct)
            if delta > 1.0:
                self._jump_amp = min(16.0, (delta - 1.0) * 2.0)
                self._jump_t = 0
        self._quote = quote
        self.setToolTip(
            f"{quote.name} {quote.code}\n"
            f"现价 {quote.price:.2f}  涨跌 {quote.change:+.2f} ({quote.change_pct:+.2f}%)\n"
            f"今开 {quote.open:.2f}  最高 {quote.high:.2f}  最低 {quote.low:.2f}"
        )
        self.update()

    # ------- 拖拽 / 点击 -------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed, self._moved = True, False
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._pressed and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._moved = True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            if not self._moved:
                self.toggled.emit()
            else:
                # 拖拽结束：以当前位置为跳动基准
                self._base_pos = self.pos()
                self._jump_t = 0
                self._jump_amp = 0.0
        self._moved = False
        self._dragging = False

    def wheelEvent(self, event):
        self.cycle.emit(1 if event.angleDelta().y() > 0 else -1)

    def contextMenuEvent(self, event):
        self._menu.exec(event.globalPos())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        ball_fill = QColor(30, 34, 43, 245)
        change = self._quote.change if self._quote else 0.0
        # 涨=红 跌=绿 平盘=暗白
        color = UP if change > 0 else DOWN if change < 0 else FLAT
        if self._show_border:
            border_pen = QPen(QColor(color), 2)
        else:
            # 与填充同色的描边：盖住抗锯齿过渡带，边框关闭时不再有浅色残边
            border_pen = QPen(ball_fill, 2)
        if not self._quote:
            p.setPen(border_pen)
            p.setBrush(ball_fill)
            p.drawEllipse(rect)
            p.setPen(QColor("#e8eaed"))
            p.setFont(QFont("Microsoft YaHei", 9))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "看盘")
            p.end()
            return

        p.setPen(border_pen)
        p.setBrush(ball_fill)
        p.drawEllipse(rect)

        font_small = QFont("Microsoft YaHei", 7)
        font_big = QFont("Microsoft YaHei", 10, QFont.Weight.Bold)

        p.setFont(font_small)
        p.setPen(QColor("#e8eaed"))
        p.drawText(rect.adjusted(2, 6, -2, -rect.height() // 2),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   self._quote.short_name)

        p.setFont(font_big)
        p.setPen(QColor(color))
        p.drawText(rect.adjusted(2, rect.height() // 2 - 13, -2, -rect.height() // 2 + 10),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   f"{self._quote.price:.2f}")

        p.setFont(font_small)
        p.setPen(QColor("#c9ced6"))
        p.drawText(rect.adjusted(2, rect.height() - 26, -2, -8),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   f"{self._quote.change_pct:+.2f}%")
        self._draw_face(p)
        self._draw_fx(p)
        p.end()

    def _draw_face(self, p: QPainter) -> None:
        """按涨跌画表情。涨=正向月牙(∪ 笑)，跌=反向月牙(∩ 哭)，平盘=横杠。"""
        if not self._quote:
            return
        change = self._quote.change
        rect = self.rect().adjusted(3, 3, -3, -3)
        cx = rect.center().x()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if abs(change) <= EPS_CHANGE:
            # 平盘：两条横杠代表眼睛，一条横杠代表嘴巴
            pen = QPen(QColor("#b8bfc7"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            for dx in (-14, 14):
                p.drawLine(QPointF(cx + dx - 3.5, 26.5), QPointF(cx + dx + 3.5, 26.5))
            p.drawLine(QPointF(cx - 6, 53.5), QPointF(cx + 6, 53.5))
            return
        if change > 0:
            # 正向月牙（∪ 笑）：嘴角上扬；180° 起画，拱形在下(过 270°)
            start, span, color = 180 * 16, 150 * 16, QColor("#ffd54f")
        else:
            # 反向月牙（∩ 哭）：嘴角下撇；0° 起画，拱形在上(过 90°)
            start, span, color = 0 * 16, 150 * 16, QColor("#7fd4ff")
        pen = QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        # 眼睛：两枚小月牙（位于名称下方、价格上方）
        for dx in (-14, 14):
            p.drawArc(QRectF(cx + dx - 3.5, 23.5, 7, 7), start, span)
        # 嘴巴：一枚大月牙
        p.drawArc(QRectF(cx - 6.5, 50, 13, 6), start, span)