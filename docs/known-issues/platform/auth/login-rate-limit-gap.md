# 登录/注册缺少应用层限流与 CI 安全门（P2 待排期）

> **模块**：`gimbal-platform/backend`（`app/routers/auth.py` × `app/core/config.py`）+ CI
> **状态**：**已落地**（2026-11-24 fix/core-wrapup 轮提前收口:限流中间件 + pip-audit/DAST 门;
> 生产注册开关同日早前已收口）
> **来源**：外部评估清单 P1-6（2026-11-24，对照部署位 `5ffdea06` 核实属实）

---

## 0. 事实（核实于 2026-11-24）

1. **应用层无登录/IP/账号限流**：全仓无 slowapi/limiter/滑动窗口实现
   （`app/` grep `rate.?limit|limiter` 零命中），nginx 配置亦无 `limit_req`。
   登录端点（bcrypt 验证 + JWT 签发）可被无成本高速重试。
2. **`REGISTRATION_OPEN` 默认 `True`**（`app/core/config.py:46`）：这是**首用户
   bootstrap 设计**而非缺陷——`auth.py:77` 允许首个真人永远注册
   （`if not first and not settings.REGISTRATION_OPEN`），
   `test_registration_and_secrets.py:63-67` 明确钉住该默认。
   **风险只在于部署位**：生产 `.env` 若不显式置 `false`，bootstrap 完成后
   注册面对所有访问者敞开。**2026-11-24 已处置**：生产 `.env` 置
   `REGISTRATION_OPEN=false`（库中 23 用户早已越过 bootstrap）。
3. **CI 无依赖/DAST 门**：`plate-ci.yml` 无 `npm audit` / `pip-audit` /
   DAST 步骤（2026-11-24 前端 `npm audit` 门已另批落地,Python 侧与 DAST 仍缺）。
4. 基础方向已正确：PyJWT + bcrypt + Fernet（`app/core/security.py`）,
   证据脱敏按值替换方向合理——**本条不重复登记已对的部分**,
   仅登记短秘密、跨进程登记与导出面的持续审计义务。

## 1. 为什么是 P2 而不是 P0/P1

- 登录爆破需要先抵达服务端口（当前部署为内网定位）,且 bcrypt 每次验证
  ~100ms 量级,天然抬高爆破成本——不是"常见路径上产生非预期业务结果"的 P0,
  也不是"触发条件明确、规避成本低"的 P1（限流中间件要动 auth 全链 + 测试面）。
- 注册开关的生产收口已完成（零代码）,剩余为工程性加固。

## 2. 排期建议（触发即重开本条）

按命中「触发修复的信号」第 5 条（安全审计）排期,建议拆两步：

1. **限流中间件**：登录/刷新/注册三端点按 IP+账号双键滑动窗口,
   复用现有错误码表风格（429 族新码进 `_codes.py` + 契约快照同步）。
2. **CI 安全门**：`pip-audit`（后端依赖）+ DAST 工具选型
   （与前端 `npm audit` 门同挂 plate-ci,分级别阈值）。

两步都动 auth 面,建议与下一次 auth 相关演进同批,不单独立轮。

## 修复记录（2026-11-24,fix/core-wrapup 轮 —— 用户裁定提前收口）

登记建议「与下次 auth 演进同批」;用户明确指示在收尾分支处理,排期提前。

**①限流中间件**(原登记措辞是方向;实现取端点内挂点,免读 body 的
middleware 复杂度 —— 语义等价且测试面更直接):

- `app/core/rate_limit.py`:进程内双键滑动窗(免锁:消费方全 async,
  窗口操作无 await 点;**进程内即权威** —— 单进程部署裁定使然,重启
  丢窗可接受)。IP 键取 `X-Real-IP`(nginx gimbal.conf 恒重写为
  `$remote_addr`,反代后不可伪造;直连后端端口可伪造头键 —— 部署约定
  nginx 为唯一入口,见模块 docstring);
- 接线:`login` / `register` 按 IP+账号双键(`login` 账号面 6/60s 防
  爆破、IP 面 30/60s 防喷洒;`register` 3/600s、10/600s 慢窗),
  `refresh` 仅 IP 面(body 是 token);**限流先于 bcrypt 验证** ——
  爆破预算耗尽后连哈希都不算;
- 429 族:数值码 **4291**(`_codes.py`,进契约快照 error-codes.json +
  前端 errorCodes.ts)+ `Retry-After` 头;拒绝不记窗(重试不推长封锁);
- 档位全走 settings(`AUTH_*_MAX/_WINDOW_S` 共 9 项,`AUTH_RATE_LIMIT_
  ENABLED=False` 整面旁路);conftest 全套件默认旁路(套件登录密度远超
  预算),专测 `test_auth_rate_limit.py` 8 用例(双键分账:换 IP 打同账号
  仍被账号面拦 = 防分布式爆破、拒绝不记窗、滑出语义注入 now 直打)。

**②CI 安全门**:

- `pip-audit` 进 plate-ci gate job(审 lock 精确版本,editable 跳过);
  首跑 OSV 面发现 21 条 advisory:certifi / opentelemetry-api 两个运行时
  补丁位随 lock 重生提钉(requirements.in 加下界),datamodel-code-
  generator 0.28.5 的 9 条 PYSEC(M2 生成器钉死,跨大版本升级是独立轮)
  另立登记 `datamodel-codegen-pysec-tail.md` + CI 显式 `--ignore-vuln`
  白名单指回该登记;
- `dast` job:ZAP baseline 被动扫描(后端 :18000 + 前端 vite preview
  :4173,空库 bootstrap + 一次性开发密钥);分钟级开销不进每次 push,
  `workflow_dispatch` 手动触发,阈值 = 仅 FAIL 级红(`-I` 吞 WARN 噪音)。
  **首次 dispatch 即其冒烟测试**(本机无 gh 凭证,触发面在用户侧)。
