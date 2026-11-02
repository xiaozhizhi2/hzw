"""K线 / 分时图：基于 QtCharts，深色看盘风格，A股红涨绿跌。"""
from __future__ import annotations

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QCategoryAxis,
    QCandlestickSeries,
    QCandlestickSet,
    QChart,
    QChartView,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QFont, QPainter

BG = QColor("#1c2028")
GRID = QColor(255, 255, 255, 26)
UP = QColor("#e0453c")     # 涨 红
DOWN = QColor("#00a860")   # 跌 绿


def _common_chart(title: str = "") -> QChart:
    chart = QChart()
    chart.setTitle(title)
    chart.setBackgroundBrush(BG)
    chart.setPlotAreaBackgroundBrush(BG)
    chart.setPlotAreaBackgroundVisible(True)
    chart.setMargins(QMargins(8, 8, 8, 8))
    chart.legend().hide()
    chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
    chart.setTitleFont(QFont("Microsoft YaHei", 10))
    return chart


class KLineChart(QChartView):
    """K线图：蜡烛图 + 成交量 + MA5/10/20。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chart = _common_chart()
        self.setChart(self._chart)
        self._chart.setMinimumHeight(320)

    def set_data(self, rows: list[list]) -> None:
        """rows: [[date, open, close, high, low, volume], ...]"""
        chart = _common_chart()
        if not rows:
            chart.setTitle("暂无K线数据")
            self.setChart(chart)
            return

        candles = QCandlestickSeries()
        candles.setIncreasingColor(UP)
        candles.setDecreasingColor(DOWN)
        candles.setBodyWidth(0.5)
        candles.setBodyOutlineVisible(False)

        vols = QCandlestickSeries()
        vols.setIncreasingColor(QColor("#b3543f"))
        vols.setDecreasingColor(QColor("#2f7d55"))
        vols.setBodyWidth(0.35)
        vols.setBodyOutlineVisible(False)

        dates: list[str] = []
        for i, r in enumerate(rows):
            date, o, c, h, l, v = r
            candles.append(QCandlestickSet(o, h, l, c, float(i)))
            vols.append(QCandlestickSet(v, v, v, v, float(i)))
            dates.append(date)

        closes = [float(r[2]) for r in rows]
        ma_series = self._ma_series(closes, [5, 10, 20])
        name_color = {5: "#ffd54f", 10: "#4fc3f7", 20: "#ce93d8"}

        axis_x = QBarCategoryAxis()
        axis_x.append(dates)
        axis_x.setLabelsVisible(False)
        axis_x.setGridLineVisible(False)

        axis_y = QValueAxis()
        axis_y.setLabelFormat("%.2f")
        axis_y.setGridLineColor(GRID)
        axis_y.setLineVisible(False)
        axis_y.setLabelsColor(QColor("#8a919e"))

        axis_y2 = QValueAxis()
        axis_y2.setLabelFormat("%.0f")
        axis_y2.setGridLineVisible(False)
        axis_y2.setLineVisible(False)
        axis_y2.setLabelsColor(QColor("#6a707a"))

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        chart.addAxis(axis_y2, Qt.AlignmentFlag.AlignRight)

        for s in (candles, vols):
            chart.addSeries(s)
            s.attachAxis(axis_x)
            s.attachAxis(axis_y)
        vols.detachAxis(axis_y)
        vols.attachAxis(axis_y2)

        for n, series in ma_series.items():
            chart.addSeries(series)
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)
            series.setColor(QColor(name_color[n]))
            series.setName(f"MA{n}")

        chart.legend().setVisible(True)
        chart.legend().setLabelColor(QColor("#b7bdca"))
        chart.legend().setFont(QFont("Microsoft YaHei", 8))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setChart(chart)

    @staticmethod
    def _ma_series(closes: list[float], windows: list[int]) -> dict[int, QLineSeries]:
        out: dict[int, QLineSeries] = {}
        for n in windows:
            s = QLineSeries()
            total = 0.0
            for i, c in enumerate(closes):
                total += c
                if i >= n:
                    total -= closes[i - n]
                if i >= n - 1:
                    s.append(float(i), total / min(n, i + 1))
            out[n] = s
        return out


class MinuteChart(QChartView):
    """当日分时图：价格线 + 均价线。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chart = _common_chart()
        self.setChart(self._chart)
        self._chart.setMinimumHeight(320)

    def set_data(self, date: str, rows: list[list]) -> None:
        """rows: [[时间HHMM, 价格, 成交量, 成交额, 均价], ...]"""
        chart = _common_chart(f"分时 {date}" if rows else "暂无分时数据")
        if not rows:
            self.setChart(chart)
            return

        price = QLineSeries()
        avg = QLineSeries()
        times: list[str] = []
        for i, r in enumerate(rows):
            price.append(float(i), r[1])
            if r[4] > 0:
                avg.append(float(i), r[4])
            times.append(f"{r[0][:2]}:{r[0][2:]}")

        axis_x = QCategoryAxis()
        axis_x.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)
        axis_x.setGridLineVisible(False)
        axis_x.setLabelsColor(QColor("#8a919e"))
        step = max(1, len(times) // 6)
        for i in range(0, len(times), step):
            axis_x.append(times[i], float(i))
        axis_x.append(times[-1], float(len(times) - 1))

        axis_y = QValueAxis()
        axis_y.setLabelFormat("%.2f")
        axis_y.setGridLineColor(GRID)
        axis_y.setLineVisible(False)
        axis_y.setLabelsColor(QColor("#8a919e"))

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        for s, color in ((price, "#ffd54f"), (avg, "#4fc3f7")):
            chart.addSeries(s)
            s.setColor(QColor(color))
            s.setName("价格" if s is price else "均价")
            s.attachAxis(axis_x)
            s.attachAxis(axis_y)
        chart.legend().setVisible(True)
        chart.legend().setLabelColor(QColor("#b7bdca"))
        chart.legend().setFont(QFont("Microsoft YaHei", 8))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setChart(chart)