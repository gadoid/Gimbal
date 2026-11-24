# 登录/注册缺少应用层限流与 CI 安全门（P2 待排期）

> **模块**：`gimbal-platform/backend`（`app/routers/auth.py` × `app/core/config.py`）+ CI
> **状态**：未修复（2026-11-24 登记为 P2 待排期；同日已收口生产注册开关）
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
