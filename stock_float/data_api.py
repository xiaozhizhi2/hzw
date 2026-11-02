"""腾讯行情接口封装：实时行情、K线、分时。

数据源均为公开免费接口：
- 实时: https://qt.gtimg.cn/q=<code>
- K线: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=<code>,<period>,,,<count>,qfq
- 分时: https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=<code>
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import urllib.request
from dataclasses import dataclass
from typing import Optional

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_PERIOD_KEYS = {
    "day": ("qfqday", "day"),
    "week": ("qfqweek", "week"),
    "month": ("qfqmonth", "month"),
}


@dataclass
class Quote:
    """A股实时行情快照。"""

    code: str
    name: str
    price: float
    prev_close: float
    open: float
    high: float
    low: float
    change: float
    change_pct: float
    volume: float  # 手
    amount: float  # 万元
    time: str  # yyyymmddHHMMSS

    @property
    def is_up(self) -> bool:
        return self.change >= 0

    @property
    def short_name(self) -> str:
        """ETF 类名称只取 'ETF' 前部分，避免悬浮球/表格溢出。"""
        return self.name.split("ETF", 1)[0].strip() if "ETF" in self.name else self.name


def normalize_code(code: str) -> Optional[str]:
    """'600000' / 'sh600000' => 'sh600000'；按代码段自动推导市场前缀。"""
    code = code.strip().lower()
    if re.fullmatch(r"(sh|sz|bj)\d{6}", code):
        return code
    if not re.fullmatch(r"\d{6}", code):
        return None
    if code.startswith(("6", "9")):
        return "sh" + code
    if code.startswith(("0", "3")):
        return "sz" + code
    if code.startswith(("4", "8")):
        return "bj" + code
    if code.startswith("5"):
        return "sh" + code  # 沪市基金/ETF（如 589800）
    if code.startswith("1"):
        return "sz" + code  # 深市基金/债券（如 159915）
    return None


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("gbk", errors="ignore")


def fetch_quotes(codes: list[str], retries: int = 2) -> dict[str, Quote]:
    """批量拉取实时行情，返回 {code: Quote}。网络异常时按批次重试。"""
    results: dict[str, Quote] = {}
    todo = list(codes)
    for _ in range(retries):
        failed: list[str] = []
        for i in range(0, len(todo), 60):
            chunk = todo[i : i + 60]
            try:
                raw = _fetch("https://qt.gtimg.cn/q=" + ",".join(chunk))
            except Exception:
                failed.extend(chunk)
                continue
            for line in raw.replace(";", "\n").splitlines():
                line = line.strip()
                if not line.startswith("v_"):
                    continue
                fields = line.split('="', 1)[1].rstrip('";').split("~")
                if len(fields) < 40:
                    continue
                q = Quote(
                    code=normalize_code(fields[2]) or fields[2],
                    name=fields[1],
                    price=_f(fields[3]),
                    prev_close=_f(fields[4]),
                    open=_f(fields[5]),
                    high=_f(fields[33]),
                    low=_f(fields[34]),
                    change=_f(fields[31]),
                    change_pct=_f(fields[32]),
                    volume=_f(fields[6]),
                    amount=_f(fields[37]),
                    time=fields[30],
                )
                results[q.code] = q
        todo = failed
        if not todo:
            break
    return results


def fetch_kline(code: str, period: str = "day", count: int = 320) -> list[list]:
    """日/周/月K（前复权），返回 [date, open, close, high, low, volume] 列表。"""
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={code},{period},,,{count},qfq"
    )
    payload = json.loads(_fetch(url))["data"]
    node = payload.get(code, {})
    keys = _PERIOD_KEYS.get(period, _PERIOD_KEYS["day"])
    rows = node.get(keys[0]) or node.get(keys[1]) or []
    data = []
    for r in rows:
        date, open_, close, high, low = r[0], r[1], r[2], r[3], r[4]
        vol = r[5] if len(r) > 5 else 0
        data.append([date, float(open_), float(close), float(high), float(low), float(vol)])
    return data


def fetch_minute(code: str) -> tuple[str, list[list]]:
    """当日分时，返回 (日期, [[时间HHMM, 价格, 成交量, 成交额, 均价], ...])。"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={code}"
    node = json.loads(_fetch(url))["data"][code]["data"]
    date = node.get("date", "")
    rows: list[list] = []
    cum_amt = cum_vol = 0.0
    for r in node.get("data", []):
        # 腾讯分时: [时间, 价格, 成交量(手), 成交额(元)]
        price, vol = float(r[1]), float(r[2])
        amt = float(r[3])
        cum_vol += vol
        cum_amt += amt
        avg = cum_amt / cum_vol if cum_vol else 0.0
        rows.append([r[0], price, vol, amt, avg])
    return date, rows


def now_str() -> str:
    return _dt.datetime.now().strftime("%H:%M:%S")


def _f(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0