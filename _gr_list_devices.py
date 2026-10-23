import requests
import sys

sys.stdout.reconfigure(encoding="utf-8")
h = {
    "Permissionarn": '[{"region":"*","accountId":"*","isName":true,"resource":"*"}]',
    "OrganizationId": "*",
}
r = requests.get(
    "http://172.16.30.170:9220/enetxus/gr/v2/devices?pageNum=1&pageSize=500",
    headers=h,
    verify=False,
    timeout=60,
)
print("status", r.status_code)
d = r.json()
print("total", d.get("total"))
for x in d.get("rows", []):
    print(
        repr(x.get("deviceSn")),
        "|",
        repr(x.get("deviceType")),
        "|",
        repr(x.get("model")),
        "|",
        repr(x.get("osType")),
        "|",
        repr(x.get("state")),
    )