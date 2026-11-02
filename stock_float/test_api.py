"""临时脚本：验证腾讯行情接口，用后即删。"""
import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("gbk", errors="ignore")


quote = get("https://qt.gtimg.cn/q=sh600000")
print("QUOTE:", quote.strip()[:200])

k = get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600000,day,,,320,qfq")
data = json.loads(k)["data"]["sh600000"]
keys = [x for x in ("qfqday", "day", "qfqweek", "week") if x in data]
print("KLINE keys:", keys)
print("KLINE last:", data[keys[0]][-1] if keys else None)

m = get("https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh600000")
md = json.loads(m)["data"]["sh600000"]["data"]
print("MINUTE rows:", len(md["data"]), "date:", md.get("date"))
print("MINUTE last:", md["data"][-1])