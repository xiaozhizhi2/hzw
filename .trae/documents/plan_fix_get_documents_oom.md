# 修复 get_documents.py 生成 HTML 时的 Java 内存失败计划

## Summary
当前 [get_documents.py](file:///d:/cbc/enet-swagger-frontend/get_documents.py) 在为 `dev` 分支批量生成 HTML 文档时，`enet-eagle-cloud` 项目触发 Java Runtime native memory 分配失败，导致最终只成功处理 10/12 个项目。最小且稳妥的方案是：保留现有串行生成流程，在 HTML 生成命令中增加可配置 JVM 参数，并同步更新旧版 shell 脚本 [get_document.sh](file:///d:/cbc/enet-swagger-frontend/get_document.sh) 以保持行为一致；不引入并行，不改前端，不调整 YAML 过滤逻辑。

## Current State Analysis

### 1. 主工作流当前实现
- [get_documents.py](file:///d:/cbc/enet-swagger-frontend/get_documents.py) 是当前 Python 主入口。
- 它会：
  1. 在 `document_branches/{branch}` 下 clone 或 update 文档仓库。
  2. 遍历 `PROJECT_MAP` 串行处理每个项目。
  3. 对 `enet-manager` 调用 `merge_api_specs.py` 合并多个 YAML。
  4. 调用 `java -jar ... generate -g html2` 生成 HTML。
  5. 复制对应 YAML 到 `yaml_documents/{branch}/{project}.yaml`。
- 当前生成本身就是串行，不存在并行生成导致内存叠加的问题。

### 2. HTML 生成调用点
- [get_documents.py](file:///d:/cbc/enet-swagger-frontend/get_documents.py) 的 `generate_html(...)` 使用：
  - `java -jar <jar> generate -i <yaml> -g html2 -o <dir>`
- [get_document.sh](file:///d:/cbc/enet-swagger-frontend/get_document.sh#L113-L118) 也使用相同的 `html2` 生成方式。
- [generate_html_api_docs.py](file:///d:/cbc/enet-swagger-frontend/generate_html_api_docs.py) 虽然也会调 openapi-generator，但它用的是 `-g html`，且不是本次批处理主链路。

### 3. 失败证据
- [hs_err_pid8188.log](file:///d:/cbc/enet-swagger-frontend/hs_err_pid8188.log#L1-L30) 明确显示：
  - `There is insufficient memory for the Java Runtime Environment to continue.`
  - `Native memory allocation (malloc) failed`
  - 出错命令就是 openapi-generator 针对 `enet-eagle-cloud` 的 `html2` 生成。
- [hs_err_pid8188.log](file:///d:/cbc/enet-swagger-frontend/hs_err_pid8188.log#L11-L18) 还给出 JVM 官方建议：
  - 减少 `-Xmx/-Xms`
  - 减少 Java 线程
  - 减少线程栈大小 `-Xss`
- 这说明最直接的问题在 JVM 运行参数，而不是 Python 逻辑或前端。

### 4. 文档与实现现状
- [README_YAML_TOOLS.md](file:///d:/cbc/enet-swagger-frontend/README_YAML_TOOLS.md) 说明当前主流程确实是 `get_documents.py`。
- [get_document.sh](file:///d:/cbc/enet-swagger-frontend/get_document.sh) 仍然保留旧工作流，若不一起改，后续仍会复现同类 OOM。
- `merge_api_specs.py` 在 README 中被引用，但当前目录下未搜索到该文件，说明它可能缺失或未提交；不过本次 OOM 修复不需要依赖这个问题先解决。

## Proposed Changes

### 1. 修改 [get_documents.py](file:///d:/cbc/enet-swagger-frontend/get_documents.py)
**目标**：让 HTML 生成命令支持显式 JVM 参数，降低 native memory / compiler thread 压力。

**修改点**：
- 在 `generate_html(...)` 周边增加 JVM 参数常量或参数构造逻辑。
- 将当前：
  - `java -jar ...`
  改为：
  - `java <JVM参数> -jar ...`
- 方案保持最小，不改调用结构，不改输出目录，不改项目遍历顺序。

**建议参数方向**：
- 限制最大堆内存，例如显式 `-Xms` / `-Xmx`
- 限制线程栈，例如 `-Xss`
- 关闭或降低编译器线程/分层编译压力，例如减少 JIT 编译带来的 native memory 占用

**为什么这样改**：
- 错误根因直接来自 JVM native memory。
- 当前脚本已经串行，所以先调 JVM 参数比改调度逻辑更对症。

### 2. 同步修改 [get_document.sh](file:///d:/cbc/enet-swagger-frontend/get_document.sh)
**目标**：让旧 shell 脚本和 Python 主脚本保持一致，避免两个入口行为分叉。

**修改点**：
- 把 [get_document.sh#L113-L118](file:///d:/cbc/enet-swagger-frontend/get_document.sh#L113-L118) 的 `java -jar` 命令同步加上相同 JVM 参数。

**为什么要改**：
- 当前 shell 脚本仍可被使用。
- 如果只修 Python，不修 shell，问题会在旧入口重复出现。

### 3. 可选的小幅增强：在 [get_documents.py](file:///d:/cbc/enet-swagger-frontend/get_documents.py) 中保留/强化分批能力
**目标**：不改变默认逻辑，但让超大项目可更容易单独生成。

**当前状态**：
- 脚本已经支持 `--projects`。
- 这已经足够作为分批执行入口。

**计划处理方式**：
- 不新增复杂功能。
- 仅在代码注释或输出中保留这个能力的可用性，不做额外架构改造。

## Assumptions & Decisions
- 决定保持 `html2`，因为主工作流与旧 shell 脚本当前都在使用它。
- 决定不把 [generate_html_api_docs.py](file:///d:/cbc/enet-swagger-frontend/generate_html_api_docs.py) 并入主工作流，因为那会扩大改动范围，并引入 `html` / `html2` 行为差异。
- 决定不做并行生成，因为当前问题是 OOM，不是吞吐量不足。
- 决定不改前端代码，因为报错完全发生在离线生成链路，与前端启动/运行无关。
- 默认认为 `merge_api_specs.py` 缺失问题不是本次修复主线；若执行阶段发现 `enet-manager` 因缺文件失败，再单独处理。

## Verification Steps
1. 运行目标命令，复现修复效果：
   - `python get_documents.py dev`
2. 重点验证 `enet-eagle-cloud`：
   - 不再出现 [hs_err_pid8188.log](file:///d:/cbc/enet-swagger-frontend/hs_err_pid8188.log) 同类 native memory OOM。
3. 检查结果目录：
   - `html_documents/dev/enet-eagle-cloud/` 已生成
   - `yaml_documents/dev/enet-eagle-cloud.yaml` 已导出
4. 若全量仍压力大，再验证分批命令：
   - `python get_documents.py dev --projects enet-eagle-cloud`
5. 若需要保持旧入口可用，再验证 shell 版本行为一致：
   - [get_document.sh](file:///d:/cbc/enet-swagger-frontend/get_document.sh) 对应命令可正常完成同项目生成
