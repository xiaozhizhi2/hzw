# UI自动化测试菜单遍历套件计划

## Summary
在 `d:\cbc\enet-v2-web-global-register` 现有 Playwright 测试体系上新增一个 E2E 测试用例，进入已登录态后遍历当前账号可见且可点击的菜单项；测试过程中持续监听后端请求响应，只要捕获到后端响应状态码 `>= 400`，该测试立即判定失败。实现位置放在现有 `e2e/` 目录中，复用现成登录方案，不改业务代码。

## Current State Analysis
1. Playwright 已接入，测试目录和启动方式已就绪：
   - `d:\cbc\enet-v2-web-global-register\playwright.config.ts`
   - `d:\cbc\enet-v2-web-global-register\package.json`
   现状为 `testDir: './e2e'`，`npm run test:e2e` 执行 `playwright test`，并通过 `webServer` 自动启动前端。

2. 当前 E2E 只有一个简单冒烟用例：
   - `d:\cbc\enet-v2-web-global-register\e2e\vue.spec.ts`
   仅访问首页并校验标题，没有登录、菜单遍历、网络错误拦截能力。

3. 菜单不是静态写死，来自运行时动态路由：
   - `d:\cbc\enet-v2-web-global-register\src\layouts\BasicLayout\BasicLayout.vue`
   - `d:\cbc\enet-v2-web-global-register\src\hooks\useMenu.ts`
   - `d:\cbc\enet-v2-web-global-register\src\stores\router.ts`
   `BasicLayout` 把 `menus` 传给 `ProLayout`；`menus` 取自 `routerStore.addRoutes` 中 path 为 `/` 的 children，并过滤 `meta.hidden`。因此“可点击菜单”应以登录后渲染出的实际菜单为准。

4. 菜单可见性受权限守卫和配置接口影响：
   - `d:\cbc\enet-v2-web-global-register\src\router\guards\permission.ts`
   登录后会调用 `getConfiguration()`，再执行 `generateRoutes(permissions)` 动态挂载路由。因此测试必须先进入稳定已登录态，等待动态菜单加载完成。

5. 登录页已有测试选择器，但页面逻辑里登录实现被注释：
   - `d:\cbc\enet-v2-web-global-register\src\modules\app\pages\login.vue`
   页面提供了 `data-testid="login_name"`、`data-testid="login_password"`、`data-testid="login_signin"`，但实际登录逻辑注释掉了。仓库内另有一个示例测试：
   - `d:\cbc\enet-v2-web-global-register\src\modules\global-register\device\device.test.ts`
   这个文件直接点登录按钮后继续测试，说明当前项目里“已有现成登录方案”不在标准 Playwright 基础设施内，而更可能是依赖测试环境、预置态或团队已有约定。计划里将把登录步骤抽成单独前置方法并复用该现成方案。

## Assumptions & Decisions
1. 菜单覆盖范围：按用户确认，只覆盖“当前账号可见菜单”。不做静态路由全量补点。
2. 登录方式：复用用户已有现成方案；实现时把登录前置封装成单独 helper 或测试内前置步骤，避免散落在每个断言里。
3. 错误判定规则：以后端 HTTP 响应状态码 `>= 400` 为失败条件；判定发生在 Playwright 测试层，不改前端 `axios` 封装。
4. 套件形式：写成一个测试用例，放到 `e2e/` 下，与现有 Playwright 约定保持一致。
5. 遍历方式：优先以页面真实渲染出的菜单 DOM 为准，逐个展开、逐个点击；不直接依赖静态常量 `src/constants/menus.ts` 作为执行源。

## Proposed Changes
### 1. 新增菜单遍历测试文件
目标文件：`d:\cbc\enet-v2-web-global-register\e2e\menu-navigation.spec.ts`

实现内容：
1. 复用现成登录方案，进入已登录首页。
2. 在 `page` 上注册响应监听器，收集所有后端 `>= 400` 的响应：
   - 过滤前端静态资源请求。
   - 聚焦 `/api/` 或实际后端 base URL 请求。
   - 为每条失败请求记录：URL、方法、状态码、触发菜单路径。
3. 等待布局和菜单加载完成，再抓取当前页面真实可点击菜单项。
4. 逐个点击菜单：
   - 对有子菜单的父级先展开。
   - 只执行可见、可点击、非禁用菜单项。
   - 每次点击后等待路由完成和页面首轮请求稳定。
5. 若某次点击过程中累积到 `>=400` 响应，则在测试结束时报错并输出失败清单。
6. 对重复 URL 或重复菜单目标去重，避免同一路由被重复点击导致噪音。

原因：
- 该文件与现有 `e2e/` 目录结构一致。
- 单文件更符合“写到一个测试用例中”的要求。
- 网络监听放测试层，改动最小，隔离业务代码。

### 2. 按需要提取最小辅助函数
目标位置：优先内联在 `e2e\menu-navigation.spec.ts`；仅当代码明显失控时，再提取到 `e2e\helpers\*.ts`

候选辅助函数：
1. `login(page)`：复用现成登录前置。
2. `collectMenuTargets(page)`：读取当前展开层级中的可点击菜单项，并返回文本、定位器或 href 信息。
3. `clickMenuAndWait(page, target)`：执行点击并等待路由/请求稳定。
4. `recordFailedResponse(response, currentMenu)`：统一记录失败响应。

原因：
- 当前仓库没有成熟 `e2e/helpers` 结构，优先保持改动集中。
- 仅在一个用例内出现的逻辑，不额外抽象成公共模块。

### 3. 如有必要，微调现有冒烟测试文件
目标文件：`d:\cbc\enet-v2-web-global-register\e2e\vue.spec.ts`

可能变更：
- 保持不动；或把原始 smoke test 留存不变。
- 若现有文件命名影响阅读，可在实现阶段视情况仅做最小调整，例如保留 smoke test 同时新增新文件，不合并、不重构。

原因：
- 用户需求是增加套件，不是替换现有冒烟测试。
- 避免无关重构。

## Implementation Notes
1. 菜单来源判断依据：
   - 运行时真实菜单来自 `useMenu()`，其背后是 `routerStore.addRoutes`。
   - 但测试执行仍以 DOM 为准，因为需求明确是“点击所有可点击菜单”。

2. 菜单点击策略：
   - 先定位 `ProLayout` 渲染出的导航区域。
   - 递归处理父子级菜单，保证子菜单在点击前已展开。
   - 过滤外链、空链接、隐藏或禁用项。
   - 对已访问目标做去重，避免重复点击同一路由。

3. 网络错误采集策略：
   - 使用 `page.on('response', ...)`。
   - 只记录业务后端请求，不记录图片、字体、Vite HMR、source map 等静态资源。
   - 若项目存在已知允许失败的接口，只有在实现时确认仓库已有明确白名单约定，才加入白名单；否则全部按失败处理。

4. 稳定性控制：
   - 每次点击后等待 URL 变化或页面稳定，再检查本轮是否产生失败响应。
   - 对纯展开动作和真正跳转动作分开处理，避免把菜单展开误当成页面访问完成。

## Verification
1. 在项目 README 约定环境下执行：
   - 参考 `README.md`，优先按项目既有运行方式启动依赖。
   - 使用项目实际包管理方式执行 Playwright 测试。
2. 验证点：
   - 新测试能进入已登录态。
   - 能遍历当前账号可见菜单，而不是只点一级菜单。
   - 任一菜单触发后端响应 `>=400` 时，测试失败并输出失败接口信息。
   - 没有 `>=400` 时，测试通过。
3. 如仓库已有 lint/test 约定，可补充运行单个 E2E 文件进行验证，避免扩大执行范围。

## Files Grounded In Exploration
- `d:\cbc\enet-v2-web-global-register\playwright.config.ts`
- `d:\cbc\enet-v2-web-global-register\package.json`
- `d:\cbc\enet-v2-web-global-register\e2e\vue.spec.ts`
- `d:\cbc\enet-v2-web-global-register\src\layouts\BasicLayout\BasicLayout.vue`
- `d:\cbc\enet-v2-web-global-register\src\hooks\useMenu.ts`
- `d:\cbc\enet-v2-web-global-register\src\stores\router.ts`
- `d:\cbc\enet-v2-web-global-register\src\router\guards\permission.ts`
- `d:\cbc\enet-v2-web-global-register\src\modules\app\pages\login.vue`
- `d:\cbc\enet-v2-web-global-register\src\configs\settings.config.ts`
- `d:\cbc\enet-v2-web-global-register\src\modules\global-register\device\device.test.ts`
