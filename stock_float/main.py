"""A股看盘悬浮球入口。

运行：.venv\\Scripts\\python.exe main.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from float_ball import SIZE, FloatBall
from main_panel import MainPanel
from watchlist import Watchlist

MOD_ALT = 0x0001
WM_HOTKEY = 0x0312
HOTKEY_TOGGLE = 1  # Alt+D 显示/隐藏悬浮球
HOTKEY_CYCLE = 2   # Alt+S 切换自选股


class HotkeyFilter(QAbstractNativeEventFilter):
    """全局热键（RegisterHotKey）：焦点在其他应用时也生效。"""

    def __init__(self, on_toggle, on_cycle):
        super().__init__()
        self._on_toggle = on_toggle
        self._on_cycle = on_cycle

    def nativeEventFilter(self, event_type, message):
        if event_type == "windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_TOGGLE:
                    self._on_toggle()
                    return True
                if msg.wParam == HOTKEY_CYCLE:
                    self._on_cycle()
                    return True
        return False

DARK_QSS = """
* { font-family: 'Microsoft YaHei'; font-size: 13px; }
QMainWindow, QWidget { background: #1c2028; color: #e8eaed; }
QLineEdit, QTableWidget {
    background: #252a34; color: #e8eaed; border: 1px solid #3a4150;
    border-radius: 4px; padding: 4px 6px; selection-background-color:#3a4150;
}
QLineEdit:focus { border-color: #e0b64d; }
QPushButton {
    background: #2c3340; color: #e8eaed; border: 1px solid #3a4150;
    border-radius: 4px; padding: 4px 14px;
}
QPushButton:hover { background: #384158; }
QPushButton[quick="true"] { padding: 4px 8px; font-size: 12px; }
QTableWidget { gridline-color: transparent; alternate-background-color: #20242e; }
QTableWidget::item:selected { background: #384158; color: #fff; }
QHeaderView::section {
    background: #252a34; color: #9aa2b0; border: none;
    border-bottom: 1px solid #3a4150; padding: 5px;
}
QTabWidget::pane { border: 1px solid #3a4150; }
QTabBar::tab { background: #252a34; color: #9aa2b0; padding: 6px 18px; border: none; }
QTabBar::tab:selected { background: #384158; color: #ffd54f; }
QLabel { color: #c9ced6; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    app.setFont(QFont("Microsoft YaHei", 10))

    watchlist = Watchlist()
    panel = MainPanel(watchlist)
    ball = FloatBall()

    # 悬浮球 ↔ 面板联动
    panel_active: dict = {}

    def set_active(code: str | None) -> None:
        panel_active["code"] = code
        if code:
            q = panel._quotes.get(code)
            if q:
                ball.update_quote(q)

    ball.toggled.connect(lambda: panel.setVisible(not panel.isVisible()))
    ball.cycle.connect(panel.cycle_active)
    ball.quit_requested.connect(app.quit)

    panel.active_changed.connect(set_active)

    # 全局热键 Alt+D：显示/隐藏悬浮球；Alt+S：顺序切换自选股
    user32 = ctypes.windll.user32
    assert user32.RegisterHotKey(None, HOTKEY_TOGGLE, MOD_ALT, ord("D")) != 0, "Alt+D 注册失败"
    assert user32.RegisterHotKey(None, HOTKEY_CYCLE, MOD_ALT, ord("S")) != 0, "Alt+S 注册失败"
    hotkey_filter = HotkeyFilter(
        lambda: ball.setVisible(not ball.isVisible()),
        lambda: panel.cycle_active(1),
    )
    app.installNativeEventFilter(hotkey_filter)
    app.aboutToQuit.connect(
        lambda: (
            user32.UnregisterHotKey(None, HOTKEY_TOGGLE),
            user32.UnregisterHotKey(None, HOTKEY_CYCLE),
        )
    )

    # 初始布局：悬浮球贴右缘
    screen = app.primaryScreen().availableGeometry()
    ball.move(screen.right() - SIZE - 24, screen.height() // 2 - SIZE // 2)
    ball.show()

    panel.start()
    if len(watchlist.codes) == 0:
        panel.show()
    else:
        set_active(watchlist.codes[0])
        panel.loader.load(watchlist.codes[0])
        panel.active_changed.emit(watchlist.codes[0])

    app.aboutToQuit.connect(panel.shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())