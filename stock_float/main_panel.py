"""主面板：自选股列表 + 分时/K线图表。网络请求在后台线程，不卡界面。"""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import data_api
from charts import KLineChart, MinuteChart
from float_ball import EPS_CHANGE
from watchlist import Watchlist

PERIODS = [("day", "日K"), ("week", "周K"), ("month", "月K")]
QUICK = [("上证指数", "sh000001"), ("深证成指", "sz399001"),
         ("创业板指", "sz399006"), ("沪深300", "sh000300")]

COLOR_UP = QColor("#e0453c")
COLOR_DOWN = QColor("#00a860")
COLOR_TEXT = QColor("#e8eaed")


class QuotePoller(QThread):
    """周期拉取自选股实时行情。"""

    quotes_ready = Signal(dict)

    def __init__(self, provider, interval_ms: int = 4000):
        super().__init__()
        self._provider = provider
        self._interval = interval_ms
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self):
        while not self._stop:
            try:
                codes = self._provider()
                if codes:
                    quotes = data_api.fetch_quotes(codes)
                    if quotes and not self._stop:
                        self.quotes_ready.emit(quotes)
            except Exception:
                pass
            self.msleep(self._interval)


class ChartLoader(QThread):
    """跟进当前选中股票，后台拉取分时与日/周/月K线。"""

    minute_ready = Signal(str, list)   # 日期, 行
    kline_ready = Signal(str, list)    # period, 行

    def __init__(self):
        super().__init__()
        self._wanted: str | None = None
        self._loaded: str | None = None
        self._stop = False

    def load(self, code: str) -> None:
        self._wanted = code
        if not self.isRunning():
            self.start()

    def stop(self) -> None:
        self._stop = True

    def run(self):
        while not self._stop:
            code = self._wanted
            if code and code != self._loaded:
                self._loaded = code
                try:
                    date, rows = data_api.fetch_minute(code)
                    if not self._stop:
                        self.minute_ready.emit(date, rows)
                    for period, _ in PERIODS:
                        rows = data_api.fetch_kline(code, period, 160)
                        if not self._stop:
                            self.kline_ready.emit(period, rows)
                except Exception:
                    pass
            self.msleep(500)


class MainPanel(QMainWindow):
    """看盘主窗口。"""

    active_changed = Signal(str)  # 当前选中股票代码变更

    def __init__(self, watchlist: Watchlist):
        super().__init__(None)
        self.watchlist = watchlist
        self._rows: dict[str, int] = {}   # code -> 表格行
        self._active: str | None = watchlist.codes[0] if watchlist.codes else None
        self._quotes: dict[str, data_api.Quote] = {}

        self.poller = QuotePoller(lambda: list(self.watchlist.codes))
        self.loader = ChartLoader()

        self.setWindowTitle("A股看盘")
        self.setMinimumSize(880, 620)
        self._build_ui()

        self.poller.quotes_ready.connect(self.on_quotes)
        self.loader.minute_ready.connect(self._on_minute)
        self.loader.kline_ready.connect(self._on_kline)
        self._tabs.currentChanged.connect(self._on_tab)

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        # 顶部：搜索添加 + 快捷指数
        top = QHBoxLayout()
        lbl = QLabel("代码/名称搜索：")
        top.addWidget(lbl)
        self._search = QLineEdit()
        self._search.setPlaceholderText("输入代码：600000 / sh600000 / kr005930 / krKOSPI，回车添加")
        self._search.returnPressed.connect(self._on_add)
        top.addWidget(self._search, 1)
        btn = QPushButton("添加")
        btn.clicked.connect(self._on_add)
        top.addWidget(btn)
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self._on_delete)
        top.addWidget(del_btn)
        for name, code in QUICK:
            q = QPushButton(name)
            q.setProperty("quick", True)
            q.clicked.connect(lambda _=False, c=code: self._add_direct(c))
            top.addWidget(q)
        v.addLayout(top)

        # 中部：表格 + 图表
        mid = QHBoxLayout()
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["名称", "代码", "现价", "涨跌", "涨跌幅"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_menu)
        self._table.cellClicked.connect(self._on_row_clicked)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setMaximumWidth(420)
        mid.addWidget(self._table)

        self._tabs = QTabWidget()
        self._minute_chart = MinuteChart()
        self._tabs.addTab(self._minute_chart, "分时")
        self._kline_charts: dict[str, KLineChart] = {}
        for period, name in PERIODS:
            chart = KLineChart()
            self._kline_charts[period] = chart
            self._tabs.addTab(chart, name)
        mid.addWidget(self._tabs, 1)
        v.addLayout(mid, 1)

        self._status = QLabel("就绪")
        self._status.setStyleSheet("color:#8a919e;")
        v.addWidget(self._status)

    # ---------------- 操作 ----------------
    def _on_add(self) -> None:
        text = self._search.text().strip()
        if not text:
            return
        self._search.clear()
        self._add_direct(data_api.normalize_code(text), display=text)

    def _add_direct(self, code: str | None, display: str = "") -> None:
        if not code:
            self._status.setText(f"无效代码：{display or '?'}")
            return
        if code in self.watchlist.codes:
            self._status.setText(f"{code} 已在自选中")
            return
        self.watchlist.add(code)
        self._status.setText(f"已添加 {code}")

    def _on_delete(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            self._status.setText("请先点击表格选中要删除的行")
            return
        code = next((c for c, r in self._rows.items() if r == row), None)
        if code:
            self._remove_code(code)
            self._status.setText(f"已删除 {code}")

    def _remove_code(self, code: str) -> None:
        self.watchlist.remove(code)
        row = self._rows.pop(code, None)
        if row is not None:
            self._table.removeRow(row)
            self._rebuild_row_index()
        if self._active == code:
            self.set_active(self.watchlist.codes[0] if self.watchlist.codes else None)

    # ---------------- 数据刷新 ----------------
    def on_quotes(self, quotes: dict[str, data_api.Quote]) -> None:
        self._quotes = quotes
        for code, q in quotes.items():
            self._upsert_row(code, q)
        if self._active:
            wall = quotes.get(self._active)
            if wall:
                self.active_changed.emit(self._active)

    def _upsert_row(self, code: str, q: data_api.Quote) -> None:
        row = self._rows.get(code)
        if row is None:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._rows[code] = row
            for col in range(5):
                self._table.setItem(row, col, QTableWidgetItem(""))
        # 涨/跌/平三态：涨红、跌绿、平盘用文本白
        color = COLOR_UP if q.change > EPS_CHANGE \
            else COLOR_DOWN if q.change < -EPS_CHANGE else COLOR_TEXT
        vals = [q.short_name, q.code, f"{q.price:.2f}", f"{q.change:+.2f}", f"{q.change_pct:+.2f}%"]
        for col, text in enumerate(vals):
            item = self._table.item(row, col)
            item.setText(text)
            item.setForeground(color if col >= 2 else COLOR_TEXT)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    # ---------------- 选中股票 ----------------
    def set_active(self, code: str | None) -> None:
        if code == self._active:
            return
        self._active = code
        if code:
            self.loader.load(code)
        if code and code in self._rows:
            self._table.selectRow(self._rows[code])
            self._table.scrollToItem(self._table.item(self._rows[code], 0))

    def _on_row_clicked(self, row: int, _col: int) -> None:
        for code, r in self._rows.items():
            if r == row:
                self.set_active(code)
                break

    def cycle_active(self, delta: int) -> None:
        codes = self.watchlist.codes
        if not codes:
            return
        if self._active in codes:
            i = codes.index(self._active)
        else:
            i = -1
        self.set_active(codes[(i + delta) % len(codes)])

    # ---------------- 图表 ----------------
    def _on_minute(self, date: str, rows: list) -> None:
        self._minute_chart.set_data(date, rows)

    def _on_kline(self, period: str, rows: list) -> None:
        if period in self._kline_charts:
            self._kline_charts[period].set_data(rows)

    def _on_tab(self, index: int) -> None:
        if self._active:
            self.loader.load(self._active)  # 切页时确保数据已就绪

    # ---------------- 右键菜单 ----------------
    def _on_table_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        code = next((c for c, r in self._rows.items() if r == row), None)
        if not code:
            return
        menu = self._table.createStandardContextMenu()
        act = menu.addAction(f"移除 {code}")
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen is act:
            self._remove_code(code)

    def _rebuild_row_index(self) -> None:
        self._rows = {}
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 1)
            if item:
                self._rows[item.text()] = r

    def update_status(self, text: str) -> None:
        self._status.setText(text)

    def start(self) -> None:
        self.poller.start()
        if self._active:
            self.loader.load(self._active)

    def shutdown(self) -> None:
        self.poller.stop()
        self.loader.stop()

    def closeEvent(self, event):
        event.ignore()
        self.hide()