# External API Failure Debugging

Status: [BLOCKED-ENV]

## Test-code fixes applied (in `tests/api/test_external_openapi.py`)

1. `deleteIpsecParameterEspGroup` / `deleteIpsecParameterIkeGroup` 400
   "referenced by other business objects": VPN 改为引用非本轮新建的
   ike/esp group（`_build_ipsec_request_body` VPN 段，`id != created_id`）。
2. `updateIPSecVPN` 400 `1 already exists!`: `_vpn_track_id` 复用同一
   eNetTrack，不再二次 `createNodeTrack`。
3. `updateSmartpathPath` 400 `Path ID is duplicated!`: 新增
   `created_smartpath_path_id`，create 取已占用最大值 +1，update 沿用同一 pathId。
4. `updateIpmNetwork` 400 `already exists!`: 记录 create 时的 body，
   update 复用同一 name 且 `id` 与路径 id 同源。
5. 级联用全零 UUID: `_build_kwargs` 仅在本轮 create 拿到真实 id 时替换
   path id，不再用 `00000000-...` 制造级联失败。

Baseline (2026-09-10 18:19): total=64, success=59, failed=5, skipped=0.

## Current blocker (environment / backend, not test code)

MGR 所有 node 相关端点挂起，约 60s 后由网关返回 408；非 node 端点正常。
`_build_context` 需要 `listNode`，导致每个 mgr_* 用例先等 60s 超时，套件无法推进。

Repro (2026-09-10 19:00):

```
# 挂起 -> (408)，约 60s
curl -v -m 70 "http://172.16.30.171:9205/mgr/v2/nodes"

# 同样挂起
curl -v -m 70 "http://172.16.30.171:9205/mgr/v2/config/nodes/ff52aea7-537c-4ecd-9e2b-6962edcb8e74/interfaces"
curl -v -m 70 "http://172.16.30.171:9205/mgr/v2/config/nodes/ff52aea7-537c-4ecd-9e2b-6962edcb8e74/enet-smartpaths/paths"
curl -v -m 70 "http://172.16.30.171:9205/mgr/v2/config/nodes/{nodeId}/customer-commands"
curl -v -m 70 "http://172.16.30.171:9205/mgr/v2/config/templates/nodes"
curl -v -m 70 "http://172.16.30.171:9205/enetxus/mgr/v2/config/nodes/ff52aea7-537c-4ecd-9e2b-6962edcb8e74/enet-tracks"

# 服务存活：约 125ms 返回 400
curl -v -m 20 "http://172.16.30.171:9205/mgr/v2/policies"
curl -v -m 20 "http://172.16.30.171:9205/mgr/v2/ipm-networks"
```

Header 无关：带/不带 `Permissionarn`、`OrganizationId: *` /
真实 org 均超时。

## Verification

后端 node 配置端点恢复后重新执行：

```
venv\Scripts\python.exe -u -m pytest --type=api tests/api/test_external_openapi.py \
  -m external_openapi -p no:cacheprovider -v -s -o addopts=""
```

然后确认 `logs/external_api_summary.json` 的 failed 是否由 5 下降、skipped=0。
