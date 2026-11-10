"""行情接口封装：实时行情、K线、分时。

A股/港股/美股数据源（腾讯）：
- 实时: https://qt.gtimg.cn/q=<code>
- K线: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=<code>,<period>,,,<count>,qfq
- 分时: https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=<code>

韩国（KRX）数据源（Naver，代码以 kr 开头，如 kr005930 / krKOSPI）：
- 实时: https://polling.finance.naver.com/api/realtime/domestic/{stock|index}/<codes>
- K线: https://fchart.stock.naver.com/sise.nhn?symbol=<code>&timeframe=<period>&count=<n>
- 分时: https://api.stock.naver.com/chart/domestic/{index|item}/<symbol>/minute
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
    """行情快照（A股 / 韩国）。"""

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
    """'600000' / 'sh600000' / 'kr005930' => 规范化代码；按代码段自动推导市场前缀。"""
    code = code.strip().lower()
    if re.fullmatch(r"(sh|sz|bj)\d{6}", code):
        return code
    # 韩国：kr + 6位代码，或 kr + KOSPI/KOSDAQ 指数
    if re.fullmatch(r"kr(\d{6}|kospi|kosdaq)", code):
        return code
    if code in ("kospi", "kosdaq"):
        return "kr" + code
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


def _fetch(url: str, encoding: str = "gbk") -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode(encoding, errors="ignore")


def _is_kr(code: str) -> bool:
    return code.lower().startswith("kr")


def _fetch_kr_quotes(codes: list[str]) -> dict[str, Quote]:
    """韩国（KRX）实时行情，Naver 接口支持批量拉取。"""
    stocks = [c[2:] for c in codes if c[2:].isdigit()]
    indices = [c[2:].upper() for c in codes if not c[2:].isdigit()]
    results: dict[str, Quote] = {}
    for kind, items in (("stock", stocks), ("index", indices)):
        if not items:
            continue
        url = (
            "https://polling.finance.naver.com/api/realtime/domestic/"
            f"{kind}/{','.join(items)}"
        )
        try:
            datas = json.loads(_fetch(url, "utf-8")).get("datas", [])
        except Exception:
            continue
        for d in datas:
            name = d.get("stockName", "")
            if kind == "index":
                # 指数用英文简称（KOSPI / KOSDAQ）更易读
                name = d.get("stockExchangeType", {}).get("nameEng") or name
            price = _f(d.get("closePriceRaw"))
            change = _f(d.get("compareToPreviousClosePriceRaw"))
            q = Quote(
                code="kr" + d.get("itemCode", "").lower(),
                name=name,
                price=price,
                prev_close=price - change,
                open=_f(d.get("openPriceRaw")),
                high=_f(d.get("highPriceRaw")),
                low=_f(d.get("lowPriceRaw")),
                change=change,
                change_pct=_f(d.get("fluctuationsRatioRaw")),
                volume=_f(d.get("accumulatedTradingVolumeRaw")),
                amount=_f(d.get("accumulatedTradingValueRaw")) / 10000.0,  # 万元
                time=re.sub(r"\D", "", d.get("localTradedAt", ""))[:14],
            )
            results[q.code] = q
    return results


def fetch_quotes(codes: list[str], retries: int = 2) -> dict[str, Quote]:
    """批量拉取实时行情，返回 {code: Quote}。网络异常时按批次重试。"""
    codes = [c.strip().lower() for c in codes]
    kr_codes = [c for c in codes if _is_kr(c)]
    results: dict[str, Quote] = _fetch_kr_quotes(kr_codes) if kr_codes else {}
    todo = [c for c in codes if not _is_kr(c)]
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
                # 行前缀 v_<market><code> 是权威市场标识，如 v_sh000300（指数与股票代码段相同，不能用代码段反推）
                key = line[2:].split("=", 1)[0].strip()
                if not key:
                    continue
                fields = line.split('="', 1)[1].rstrip('";').split("~")
                if len(fields) < 40:
                    continue
                q = Quote(
                    code=key,
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
    """日/周/月K，返回 [date, open, close, high, low, volume] 列表。"""
    if _is_kr(code):
        return _fetch_kr_kline(code, period, count)
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
    if _is_kr(code):
        return _fetch_kr_minute(code)
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


def _fetch_kr_kline(code: str, period: str, count: int) -> list[list]:
    """韩国日/周/月K（Naver fchart），返回 [date, open, close, high, low, volume]。"""
    url = (
        "https://fchart.stock.naver.com/sise.nhn"
        f"?symbol={code[2:].upper()}&timeframe={period}&count={count}&requestType=0"
    )
    text = _fetch(url, "euc-kr")
    data: list[list] = []
    for m in re.finditer(r'<item data="([^"]+)"', text):
        parts = m.group(1).split("|")
        if len(parts) < 6:
            continue
        d, open_, high, low, close, vol = parts[:6]
        data.append(
            [
                f"{d[:4]}-{d[4:6]}-{d[6:]}",
                float(open_),
                float(close),
                float(high),
                float(low),
                float(vol),
            ]
        )
    return data


def _fetch_kr_minute(code: str) -> tuple[str, list[list]]:
    """韩国当日分时（Naver），返回 (日期, [[时间HHMM, 价格, 成交量, 成交额, 均价], ...])。"""
    symbol = code[2:].upper()
    kind = "index" if symbol.isalpha() else "item"
    today = _dt.datetime.now().strftime("%Y%m%d")
    url = (
        f"https://api.stock.naver.com/chart/domestic/{kind}/{symbol}/minute"
        f"?startDateTime={today}0900&endDateTime={today}1530"
    )
    rows: list[list] = []
    cum_amt = cum_vol = 0.0
    for r in json.loads(_fetch(url, "utf-8")):
        price = _f(r.get("currentPrice"))
        vol = _f(r.get("accumulatedTradingVolume"))  # 该分钟成交量
        amt = price * vol
        cum_vol += vol
        cum_amt += amt
        rows.append(
            [r.get("localDateTime", "")[8:12], price, vol, amt, cum_amt / cum_vol if cum_vol else 0.0]
        )
    return today, rows


def now_str() -> str:
    return _dt.datetime.now().strftime("%H:%M:%S")


def _f(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0