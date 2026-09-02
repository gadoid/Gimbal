# Gimbal-Platform 后端认证/安全评审

> 评审范围: `src/gimbal-platform/backend/app/` 下认证 / 用户管理 / 凭据存储 / JWT / Fernet / 依赖注入 / 配置 路径
> 评审时间: 2026-09-02
> 评审人: AI 评审 (Claude Code)
> 评审方法: 逐文件精读真实实现,所有结论均给出 `file_path:line` 锚点

---

## 评审维度

1. 认证安全 (JWT 密钥、密码哈希、token 过期、refresh 流程)
2. 授权与越权 (IDOR、admin 检查位置、横向/纵向越权)
3. 凭据管理 (Fernet 密钥、明文泄漏、序列化返回)
4. 输入校验 (Pydantic、SQL 注入、路径遍历)
5. 错误处理 (错误码、信息泄漏、统一格式)
6. 配置与启动 (CORS、ephemeral 警告、debug)
7. 并发与状态 (token 失效、并发登录、状态机)

---

## 问题清单

### P0 — 关键 (Critical)

#### P0-1: `FERNET_KEY` 留空时静默生成临时密钥,重启即永久丢失全部已存凭据

- 位置: `src/gimbal-platform/backend/app/core/config.py:87-92`
- 严重度: P0
- 问题描述: `model_post_init` 在 `JWT_SECRET` / `FERNET_KEY` 为空时自动生成随机值并打 ephemeral 警告。**问题在于警告只出现在 stdout,任何把 stdout 忽略或部署到没有 stderr 重定向的环境(常见 systemd / Docker 默认),根本看不到这条 warning**。后果是:
  - FERNET_KEY ephemeral → **所有 AuthSession 行 `username_enc` / `password_enc` 永久不可解密** (不是单次 401,是真的丢密),前端"凭证管理"列表退化为占位符,无任何显式告警弹窗。
  - 重启 → 另一个随机密钥 → 数据库里的密文全部对应旧密钥 → `InvalidToken`。
- 证据:
  ```python
  # config.py:87-92
  self.JWT_SECRET_EPHEMERAL = not self.JWT_SECRET
  self.FERNET_KEY_EPHEMERAL = not self.FERNET_KEY
  if not self.JWT_SECRET:
      self.JWT_SECRET = secrets.token_urlsafe(48)
  if not self.FERNET_KEY:
      self.FERNET_KEY = _generate_fernet_key()
  ```
  而 `main.py:50-56` 的 warning 是 `logger.warning(...)`,依赖 loguru sink 配置。生产 sink 若只接 stdout/journald,警告可能淹没在启动噪声里;更糟的是容器日志被截断丢弃的场景。
- 影响: 凭据持久丢失 (DoS on credentials) + 看起来"刚启动就找不到密码"。
- 修复建议:
  1. **生产模式硬失败**: 加 `ENV: str = "dev"` 字段;非 dev 且 JWT_SECRET/FERNET_KEY 仍空 → `raise RuntimeError`。
  2. 提供 `app/secret_init.py` 脚本一键生成持久密钥并写 `.env`。
  3. 在 admin 登录页/健康检查端点暴露 ephemeral 状态 (admin 可见),而不是仅靠日志。

---

#### P0-2: `/api/auth/register` 公开开放,无 admin 开关、无注册开关、无速率限制

- 位置: `src/gimbal-platform/backend/app/routers/auth.py:51-83`
- 严重度: P0
- 问题描述: `POST /api/auth/register` 是完全公开、匿名可调用的;只要 FastAPI 进程在跑,任何拿到 URL 的人都可以注册账号。
  - 首次启动第一个人成为 admin (`is_admin = count == 0`),但**没有机制禁止继续注册**。
  - 与"内部测试平台"语境不匹配 (memory 中标注"内网测试平台"),但内网横向越权仍可注册 → 占用 `display_name` 资源池 (该字段兼作 scenario owner 标识,见 `_name_checks.py:1-9`) → 阻断合法用户正常使用。
  - 不存在速率限制 → 攻击者可批量刷账号、用尽 username / display_name。
- 证据:
  ```python
  # auth.py:51-83
  @router.post("/register", response_model=TokenOut, status_code=201)
  async def register(payload: RegisterIn, db: ...):
      payload.display_name = (payload.display_name or "").strip()
      await assert_name_available(...)
      count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
      is_admin = count == 0
      user = User(username=..., display_name=..., password_hash=..., is_admin=is_admin)
  ```
  - 全局 `main.py:100-108` 的 CORS 也允许 `localhost:5173` 调用此路径。
  - 没有 `REGISTRATION_OPEN` 之类的开关。
- 影响: 任意账号创建 / 资源池滥用 / 与"display_name = owner 标识"的提权保护正面对冲 (攻击者注册时只需锁定目标用户的 display_name 即可让该用户永远改不了名)。
- 修复建议:
  1. 加 `ALLOW_REGISTRATION: bool = False` 配置项;关闭时 `POST /register` 返回 403。
  2. 或要求"由 admin 邀请" (`POST /users` 已存在,作为唯一创建路径)。
  3. 加 IP+账号维度的速率限制 (slowapi / 自实现 token bucket)。

---

#### P0-3: `/api/auths/{id}/test` + `/api/auths/{id}?include_secrets=true` 形成"凭据自提"放大器,任何持有用户 bearer 的人可一次性导出全部明文

- 位置:
  - `src/gimbal-platform/backend/app/routers/auth_sessions.py:133-164` (`get_auth` with `include_secrets=true`)
  - `src/gimbal-platform/backend/app/routers/auth_sessions.py:210-227` (`test_auth`)
- 严重度: P0
- 问题描述: 任何拿到合法 user bearer token 的人,调用以下接口可瞬间拿到该用户**全部已存凭据的明文**:
  - `GET /api/auths/{id}?include_secrets=true` → 返回 `username + password` (明文)。
  - `POST /api/auths/{id}/test` → 把 `username + password` POST 到用户配置的 URL。
  - 而 `Bearer` token 默认前端持久化在 `localStorage` / `sessionStorage`,**配合 CORS `allow_methods=["*"]` 允许任意源方法**,浏览器 XSS / 第三方 SDK 嵌入 → 一次性掏空。
- 证据:
  ```python
  # auth_sessions.py:138-142
  async def get_auth(
      auth_id: int,
      user: CurrentUser,
      session: DbSession,
      include_secrets: bool = False,  # ← query 参数,任何人可加
  ) -> ...:
      a = await _get_owned(session, auth_id, user.id)
      if not include_secrets:
          return _to_out(a)  # 列表/普通详情: 密码打码
      # 严解密
      try:
          username = fernet_decrypt(a.username_enc)
          password = fernet_decrypt(a.password_enc)
      ...
  ```
  ```python
  # auth_sessions.py:219-225 — test 端点直接把明文凭据发到任意 URL
  username = fernet_decrypt(a.username_enc)
  password = fernet_decrypt(a.password_enc)
  ...
  ok, status_code, message = await auth_probe.probe(a.url, username, password)
  ```
  加上 `AuthSessionSecretsOut` (`schemas/auth_session.py:53-62`) 显式声明"明文 password 字段对外"。
- 影响:
  - **横向提权**: 拿到任意合法 user 的 bearer → 拿到该用户所有的 `display_name` 提权保护可能不适用 (display_name 已被该用户占用),但可凭用户名/密码直接登录到 `fin-tidb / test.21eline.com / track-test.21eline.com / GitHub` 等目标系统。
  - **SSRF/网络扫描**: `test_auth` 把任意 URL 调到任意目标 → 内部网探测。注册阶段就允许任意 URL (无 scheme/host 白名单)。
- 修复建议:
  1. `include_secrets` 改为要求二次确认 (输 admin 密码 / OTP) 或彻底删除该参数;前端需要明文 → 走服务端"代填"端点,不出明文给前端。
  2. `/auths/{id}/test` 加 URL 白名单 (仅允许已登记的目标域) + 限制 scheme 为 https + 拒绝私网 IP。
  3. 配合 P1-1 加速率限制与审计日志。

---

### P1 — 高 (High)

#### P1-1: 登录/刷新端点无任何速率限制与并发约束 → 暴力破解 / 凭据填充零成本

- 位置: `src/gimbal-platform/backend/app/routers/auth.py:87-134`
- 严重度: P1
- 问题描述:
  - `POST /api/auth/login` 没有任何限流、锁定、滑动窗口。
  - `POST /api/auth/refresh` 无限制 → 攻击者拿到任意 refresh token 后可无限刷新 14 天。
  - 失败统一返回 `"用户名或密码错误"` (good,不区分),但失败次数完全无追踪。
- 证据:
  ```python
  # auth.py:87-99
  @router.post("/login", response_model=TokenOut)
  async def login(payload: LoginIn, db: ...) -> TokenOut:
      user = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
      if user is None or not verify_password(payload.password, user.password_hash):
          raise HTTPException(401, detail=code_detail(BAD_CREDENTIALS, "用户名或密码错误"))
  ```
  没有 `request.client.host` 取 IP、没有计数器表、没有 slowapi 装饰器。
- 影响: bcrypt 计算开销能拉慢一些攻击,但足以应对现代 GPU 的字典攻击;refresh token 一旦泄漏等于给 14 天持久凭据。
- 修复建议:
  1. 在 `User` 表加 `failed_login_count` / `last_failed_at` / `locked_until` 字段;连续 5 次失败锁定 15 分钟。
  2. 按 IP 加滑动窗口 (e.g. 60 秒 ≤ 10 次)。
  3. `refresh` 端点对单 `jti` 单次有效 (token rotation) 或加短期 nonce。

---

#### P1-2: 无 token 黑名单/吊销机制,用户被禁用后存量 token 仍可用满自然过期窗口

- 位置: `src/gimbal-platform/backend/app/core/deps.py:18-32` (`get_current_user`)
- 严重度: P1
- 问题描述: `is_active=False` 的检查只在每次请求都查 DB 时生效 — **但**:
  - JWT 是无状态自验证的,客户端拿到 token 后即缓存;若是之前的有效 access token (60 分钟过期),在该窗口内旧 token 仍合法。
  - `refresh` 路径 (`auth.py:108-134`) 也仅校验签名 + 查 user,但不会追踪已签发的 token。
  - 没有 "登出" / "撤销全部会话" 端点,被盗 token 只能等自然过期 (最长 14 天 refresh + 60 分钟 access)。
- 证据:
  ```python
  # deps.py:18-32
  async def get_current_user(token, db):
      try:
          payload = decode_token(token)
      except ValueError as e:
          raise HTTPException(401, detail=str(e))
      if payload.get("type") != "access":
          raise HTTPException(401, detail="not an access token")
      user_id = int(payload["sub"])
      user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
      if not user or not user.is_active:
          raise HTTPException(401, detail="user not found or inactive")
      return user
  ```
  - 没有 `password_changed_at` 字段,无法"改密即吊销旧 token"。
  - 没有 `TokenBlacklist` 表 / Redis set。
- 影响: 用户被 admin 禁用 → 60 分钟内旧 token 仍可操作;密码泄露后用户改密码 → 旧 token 在剩余 access 窗口内仍可用。
- 修复建议:
  1. `User` 表加 `password_changed_at: datetime`;JWT 内加 `pwd_ver` (password version int) 字段;`get_current_user` 校验 token 的 `pwd_ver` 等于 user 当前值。
  2. 提供 `POST /api/auth/logout` + `POST /api/auth/logout-all` 端点,维护 `revoked_jti` 表 (SQLite 也行,体量不大)。
  3. 或 refresh 端点启用 rotation (每次 refresh 同时作废旧 refresh)。

---

#### P1-3: refresh token 无 rotation、无 reuse 检测 → refresh token 失窃 = 持续 14 天任意访问

- 位置: `src/gimbal-platform/backend/app/routers/auth.py:108-134`
- 严重度: P1
- 问题描述: `refresh` 路径:
  - 不维护"refresh 已用"集合。
  - 不强制 rotation (签发新 refresh 时旧的不作废)。
  - 没有"refresh 家族 (family) 概念",无法检测 token replay。
  - 即使 access token 60 分钟过期,refresh 是 14 天 → 一旦 refresh token 泄漏,攻击者可以**每天 1 次** 换新 access,持续两周。
- 证据:
  ```python
  # auth.py:108-134
  @router.post("/refresh", response_model=TokenOut)
  async def refresh(payload: RefreshIn, db: ...) -> TokenOut:
      try:
          data = decode_token(payload.refresh_token)
      except ValueError as e:
          raise HTTPException(401, detail=str(e))
      if data.get("type") != "refresh":
          raise HTTPException(401, detail="not a refresh token")
      user = (await db.execute(select(User).where(User.id == int(data["sub"]))).scalar_one_or_none()
      if user is None or not user.is_active:
          raise HTTPException(401, detail="user not found or inactive")
      return _token_out(user)  # 直接签新对,无旧 refresh 失效
  ```
  `core/security.py:51-60` 中 `create_refresh_token` 每次都给新 `jti`,但没人跟踪旧 jti。
- 影响: refresh token 泄漏 = 14 天持久访问;即使 access token 在 XSS 后被偷,攻击者甚至不需要偷 access,直接走 refresh 即可。
- 修复建议:
  1. 启用 refresh rotation: 每次 refresh 签发新对,把旧 refresh jti 标记 used。
  2. 检测 reuse: 如果一个 used jti 再次出现 → 该家族全部 revoke + 强制用户重新登录 (类似 OAuth 2.1 推荐做法)。
  3. 缩短 refresh 寿命到 7 天,且必须配合"近期活跃"判断 (否则 idle refresh token 也过期)。

---

#### P1-4: CORS `allow_methods=["*"]` + `allow_headers=["*"]` 过宽,搭配 Bearer token 仍有放大风险

- 位置: `src/gimbal-platform/backend/app/main.py:100-108`
- 严重度: P1
- 问题描述: 虽然 `allow_credentials=False` 防止了 cookie + `*` 组合的 wildcard 危机 (Starlette 会拒),但 `methods=["*"]` + `headers=["*"]` 仍允许任意源发起任意方法 + 任意 header。配合:
  - Bearer token 容易被 JS 读取 (`Authorization` header 不是 `Authorization` cookie,而 `Authorization` 通过 `localStorage` 持久化)。
  - 任意前端子域的 XSS 都能调 `Authorization` header (因为不是 `httpOnly` cookie 形式)。
  - `methods=["*"]` 包含 `DELETE` / `PATCH` 等 — 即使前端 5173 是白名单源,5173 上跑任意嵌入脚本/依赖被劫持,可直接 PATCH/DELETE。
- 证据:
  ```python
  # main.py:100-108
  app.add_middleware(
      CORSMiddleware,
      allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
      allow_credentials=False,
      allow_methods=["*"],   # 任意方法
      allow_headers=["*"],   # 任意 header
  )
  ```
- 影响: 任何"允许 origin 上的 XSS / 供应链投毒"都直接放大为后端全权。
- 修复建议:
  1. `allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` 白名单化。
  2. `allow_headers=["Authorization", "Content-Type"]` 收紧。
  3. 把 bearer 改成 `httpOnly` + `Secure` cookie + `SameSite=Lax` + 启用 CSRF token (CORS 配套改造)。
  4. 至少加 CSP 头 (FastAPI middleware)。

---

#### P1-5: 多个认证器把响应原文 `logger.debug` 到日志 → DEBUG 级别泄露 token / cookie / 凭证响应体

- 位置:
  - `src/gimbal-platform/backend/app/auth/authenticators/github.py:39` — `logger.debug("GitHub OAuth response: {}", data)` — `data` 含 `access_token`
  - `src/gimbal-platform/backend/app/auth/authenticators/wl.py:40` — `logger.debug("Response data: {}", data)`
  - `src/gimbal-platform/backend/app/auth/authenticators/yhr.py:36` — `logger.debug("Response headers: {}", headers)` — `headers` 含 `set-cookie`(就是 token)
- 严重度: P1
- 问题描述: 第三方认证响应 (含 token / cookie / 用户信息) 被 `logger.debug` 全量落盘。生产若 loguru sink 配置了 `DEBUG` 级或管道到日志聚合 → 凭据长期泄漏。
- 证据:
  ```python
  # github.py:25-39
  response = httpx.post(f"{auth.url}login/oauth/access_token",
      json={"client_id": auth.username, "client_secret": auth.password},
      headers={"Accept": "application/json", ...},
      timeout=30,
  )
  response.raise_for_status()
  data = response.json()
  logger.debug("GitHub OAuth response: {}", data)   # ← access_token 在 data['access_token']
  ```
  ```python
  # yhr.py:33-41
  headers = response.headers
  logger.debug("Response headers: {}", headers)    # ← 含 set-cookie
  ...
  cookie = headers.get("set-cookie")
  ...
  ```
  logger 全局配置若是 `LOGURU_LEVEL=DEBUG` 或默认 (DEBUG),则生产也会泄露。
- 影响: 日志聚合 → 凭据泄漏面扩大到所有有日志访问权限的运维。
- 修复建议:
  1. 删除 `logger.debug(... data)` 这种全量 dump;若必要,只记录 `ok` / `status` 等元数据。
  2. 关键字段 (token / cookie) 显式 redact 后再 log。
  3. `core/config.py` 加 `LOG_LEVEL: str = "INFO"`,生产强制 INFO+,启动检查。

---

#### P1-6: `/api/users` 列表暴露全用户信息给任意已登录成员 (含 username + display_name + is_active),可枚举

- 位置: `src/gimbal-platform/backend/app/routers/users.py:71-79`
- 严重度: P1
- 问题描述: 文档注释明确写 "List every user in the system (spec-1: no pagination, no admin gating)" — 即 spec 故意如此,但客观上:
  - 任意成员可枚举所有 username → 用于字典/撞库攻击的精准目标列表。
  - `display_name` 字段是 composer 资源归属标识 → 看到所有合法 display_name 让攻击者注册时**精确避开** (降低误占用他人资源池的副作用,但同时也让攻击者针对性撞用户名)。
  - `is_active` 暴露 → 可识别已停用账号,辅助侦察。
- 证据:
  ```python
  # users.py:71-79
  @router.get("", response_model=list[UserOut])
  async def list_users(
      user: CurrentUser,
      db: ...,
  ) -> list[UserOut]:
      """List every user in the system (spec-1: no pagination, no admin gating)."""
      rows = (await db.execute(select(User).order_by(User.id))).scalars().all()
      return [_user_out(u) for u in rows]
  ```
- 修复建议:
  1. 普通成员返回精简视图 (`id`, `display_name` only),完整字段仅 admin 可见。
  2. 加分页 + 搜索 (即使 spec 暂时不需要,也是 low-cost)。
  3. 至少 `is_active=False` 的用户对成员不可见 (避免停用账号被识别/锁状态可枚举)。

---

#### P1-7: 错误响应把底层 JWT/解码异常 `str(e)` 直接返回,可能泄漏密钥长度/签名细节

- 位置:
  - `src/gimbal-platform/backend/app/routers/auth.py:116-120` (`/refresh` 错误路径)
  - `src/gimbal-platform/backend/app/core/deps.py:24-25` (`get_current_user` 错误路径)
  - `src/gimbal-platform/backend/app/core/security.py:64-67` (`decode_token`)
- 严重度: P1
- 问题描述: `python-jose` 的 `JWTError` 在某些场景下会带详细原因 (签名不匹配 / claim 缺失 / 时间偏差等),直接 `str(e)` → HTTP body → 攻击者可据此区分"签名错" vs "过期" vs "claim 类型错",辅助精准伪造或重放。
- 证据:
  ```python
  # security.py:63-67
  def decode_token(token: str) -> dict[str, Any]:
      try:
          return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGO])
      except JWTError as e:
          raise ValueError(f"invalid token: {e}") from e   # ← 原 e 被嵌入 detail
  ```
  ```python
  # auth.py:113-120
  try:
      data = decode_token(payload.refresh_token)
  except ValueError as e:
      raise HTTPException(401, detail=str(e))   # ← 直接透传
  ```
- 影响: 信息泄漏辅助攻击;不致命,但属于纵深防御缺失。
- 修复建议: 统一映射成 `"invalid token"` (中文 "令牌无效"),DEBUG 级别入库;仅 401/403 区分状态码,detail 文案稳定。

---

### P2 — 中 (Medium)

#### P2-1: "首个注册用户成为 admin" 的并发竞争条件

- 位置: `src/gimbal-platform/backend/app/routers/auth.py:71-72`
- 严重度: P2
- 问题描述: 两个客户端几乎同时发起 `POST /register`,都可能读到 `count == 0` → 都建出 admin。SQLite 默认串行化,这点风险被压制 (WAL 模式仍可能);但若未来切 PostgreSQL/MySQL,竞争真会出现。
- 证据:
  ```python
  # auth.py:71-72
  count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
  is_admin = count == 0
  ```
- 修复建议: `BEGIN IMMEDIATE` 事务 / `SELECT ... FOR UPDATE` / 改用 bootstrap seed (`admin` 用户由部署脚本创建,非首注册)。

---

#### P2-2: 密码复杂度校验只查 "字母 + 数字",不拒字典词,无 HIBP / zxcvbn 强度评估

- 位置: `src/gimbal-platform/backend/app/schemas/auth.py:23-28`
- 严重度: P2
- 问题描述:
  ```python
  @field_validator("password")
  @classmethod
  def _password_complexity(cls, v: str) -> str:
      if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
          raise ValueError("password must contain at least one letter and one digit")
      return v
  ```
  `"Password1"` 合法,`"aaaaaaaa1"` 合法,"qwerty12345" 合法。bcrypt 自身算力是兜底,但**用户选择弱密码**仍是最大入侵面。
- 修复建议: 引入 `zxcvbn` 评分 ≥ 3 或对接 HIBP `range` API (K-anonymity)。也可加最小长度从 8 提到 12。

---

#### P2-3: passlib `CryptContext(schemes=["bcrypt"])` 默认 rounds 在不同 passlib 版本下不稳定,需显式 `bcrypt__rounds`

- 位置: `src/gimbal-platform/backend/app/core/security.py:14`
- 严重度: P2
- 问题描述:
  ```python
  _pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
  ```
  passlib 1.7.x 默认 rounds=12,但若 `bcrypt` 库升级 (>= 4.x) 与 passlib 出现兼容告警 (`(trapped) error reading bcrypt version`),可能会**降级到不安全的 rounds**,或某些场景直接抛异常导致登录全 500。
- 证据: 这是历史背景,本评审范围未实际触发,但 `passlib + bcrypt 4.x` 是已知 footgun。
- 修复建议:
  1. 显式 `CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")`。
  2. 考虑切到 `argon2-cffi` (OWASP 推荐) 或 `bcrypt` 直连。
  3. CI 加 "已知 hash 仍能 verify" 的烟雾测试。

---

#### P2-4: `_gen_random_password` 长度仅 12,无强度下限提示;`reset-password` 返回明文但前端可能写入浏览器历史/截图分发

- 位置: `src/gimbal-platform/backend/app/routers/users.py:57-61`, `users.py:226-233`
- 严重度: P2
- 问题描述:
  ```python
  def _gen_random_password(length: int = 12) -> str:
      alphabet = string.ascii_letters + string.digits
      rng = random.SystemRandom()
      return "".join(rng.choice(alphabet) for _ in range(length))
  ```
  - 62 字符集 × 12 位 → log2(62^12) ≈ 71 bit,数学强度 OK,但缺少大小写之外的特殊字符,降低了抗口令字典相关性。
  - reset 后明文返回,前端任何错误都可能:
    - 把明文密码存到 localStorage / clipboard / 浏览器历史 (前端 fetch / GET 参数缓存)。
    - 截图分享到 IM。
    - logger 前端 SDK (Sentry 等) 把响应体上报。
- 修复建议:
  1. 加入 2-3 个特殊字符 (强度提到 ~85 bit)。
  2. 长度 ≥ 16。
  3. 后端响应里加 `X-Content-Type-Options: nosniff` + 前端"一次性显示后强制改密"的强制流程,不让系统生成密码长期可用。

---

#### P2-5: 登录端点用 `username` 而非 `username + tenant`;`username` 字段已与 `display_name` 强冲突 (`_name_checks`),增加未来扩展摩擦

- 位置: `src/gimbal-platform/backend/app/routers/_name_checks.py:24-67`
- 严重度: P2
- 问题描述: `_name_checks.assert_name_available` 把 username 与 display_name 双向去重 (因 display_name 兼作资源 owner)。这把"账号身份"和"显示身份"绑死:
  - 改名 display_name 等于改名 username 资源池入口 → 触发 409 链路上的"账号身份"频繁漂移。
  - 后续若要做 `display_name` 可改 + 历史 alias 保留 (e.g. 老 scenario 仍指向旧 display_name),会与当前唯一约束打架。
- 影响: 不是当下漏洞,但结构性增加将来 `display_name` 修改、软删除、租户隔离场景的实现摩擦。
- 修复建议: 引入 `owner_alias` (永久不可改的字符串) 与 `display_name` (可改、用于 UI) 的拆分;短期维持现状时,在 `_name_checks` 加详细注释说明绑定原因。

---

#### P2-6: 健康检查 `/api/health` 仅返回 `{"status": "ok"}`,不暴露 ephemeral secret 状态,运维侧排障无信号

- 位置: `src/gimbal-platform/backend/app/main.py:130-132`
- 严重度: P2
- 问题描述:
  ```python
  @app.get("/api/health")
  async def health() -> dict:
      return {"status": "ok"}
  ```
  - 不返回 JWT_SECRET_EPHEMERAL / FERNET_KEY_EPHEMERAL / version / DB connectivity。
  - 与 P0-1 的 ephemeral 静默旋转问题正交:运维即便看到 200,也不知道密钥是不是临时生成的。
- 修复建议:
  1. `/api/health` 增字段:`ephemeral_jwt`、`ephemeral_fernet`、`db_ok`、`version`。
  2. 至少 `/api/health` (公开) 与 `/api/admin/health` (admin only,带 ephemeral 标记) 拆分,后者完整暴露。

---

#### P2-7: `models.User.password_hash` 字段长度 `String(256)` 够 bcrypt hash 但若以后切其他算法可能不够;无 `last_login_at` / `password_changed_at` 审计字段

- 位置: `src/gimbal-platform/backend/app/models/user.py:17-23`
- 严重度: P2
- 问题描述:
  - 没有 `last_login_at` / `last_login_ip` / `failed_login_count` / `password_changed_at`,无法做"异常登录告警"等风控。
  - 没有 `created_by_id` / `deleted_at`,用户生命周期审计缺失。
  - `String(256)` 对 bcrypt 是足够的 (60 字符),但若以后切 scrypt/argon2,pwd-hash 可能 > 96 字符,届时再迁移数据。
- 修复建议: 加审计字段 (即使是 nullable) 是低成本高收益。

---

#### P2-8: 没有全局异常处理 / `exception_handler`,未捕获异常可能返回 500 带堆栈

- 位置: `src/gimbal-platform/backend/app/main.py` (无自定义 handler)
- 严重度: P2
- 问题描述: FastAPI 默认 500 响应在 `debug=True` 模式下会泄漏 traceback;`main.py` 的 `uvicorn.run(..., reload=True)` 是 dev 默认。生产若忘记关 `debug`,会:
  - 把数据库表结构、文件路径、stack frames 暴露给请求方。
- 证据: `main.py:144` `uvicorn.run(..., reload=True)`;`core/config.py` 没有 DEBUG 开关。
- 修复建议:
  1. 加 `DEBUG: bool = False` 设置,生产关;启动时检查。
  2. 注册全局 `@app.exception_handler(Exception)` 返回统一 500 + 写日志,body 中不泄漏细节。
  3. 关掉 `uvicorn.run(reload=True)` 的硬编码,改为读 settings。

---

## 亮点 (做得好的地方)

1. **Bcrypt + 不可逆 hash 持久化密码** (`core/security.py:14-20`),无明文存储。
2. **凭据 Fernet 对称加密静态存储** (`models/auth_session.py:32-33`),DB dump 不直接暴露 `username_enc` / `password_enc`。
3. **`_safe_decrypt` 优雅降级** (`auth_sessions.py:46-58`),FERNET_KEY 旋转后旧行不致把整列表接口 500 掉。
4. **`AuthSession.apply_token` ASCII 控制字符拒绝 (CWE-93)** (`auth/schema.py:117-126`),阻止 token 中夹 `\r\n` 注入 HTTP 头。
5. **Owner-scoped + admin bypass 的唯一权威** (`routers/_ownership.py`),杜绝 `get_owned_execution` 类似的散落判断。
6. **`display_name` 唯一性 (含与 username 冲突检测)** (`_name_checks.py` + `auth.py:64-69`),关闭了"采用他人显示名接管其 scenario / data_set"的提权路径。
7. **不能降级/删除最后一个管理员** (`users.py:166-172`, `users.py:277-283`) — admin 死锁防护。
8. **member 改 `is_admin` / 改他人资料 / 重置他人密码均 403** (`users.py:148-159`, `users.py:220-224`) — 提权路径收紧。
9. **首次注册 + ephemeral 密钥 warning** (`main.py:44-56`) — 至少意识到 JWT/FERNET 静默旋转的风险。
10. **JWT 走 `Authorization: Bearer ...` 而非 cookie** (`deps.py:15` `OAuth2PasswordBearer(tokenUrl="/api/auth/login")`),天然 CSRF 免疫。
11. **`jti` + `iat` + `type=access|refresh` 区分** (`core/security.py:35-60`),refresh 不可当 access 用。
12. **测试登录用例密码 16+ 字符** (`tests/helpers.py:18`),测试种子就用强密码做榜样。
13. **`run_dispatcher` 在执行结束后 `purge_case_dir`** (`run_dispatcher.py:1145-1148`),降低 "case.json 含明文凭据" 留盘风险。
14. **`executions.py` `_CASE_STEM_RE` + 拒绝 `.`/`..`** (`executions.py:90-103`),关掉路径遍历。
15. **`get_owned_execution` 404/403 合并** (`deps.py:52-74`),执行所有权不泄漏。
16. **错误码字典 (auth + users 路由统一 `{code, msg}`)** (`_codes.py`),客户端可机器识别。
17. **`UserPublic` 与 `UserOut` 收敛为同一 schema** (`schemas/user.py:34`),避免双重演进漂移。
19. **账号字段约束收在 `UsernameField` / `PasswordField` / `DisplayNameField`** (`schemas/auth.py:11-13`),三处共用,收紧策略时一处改动。

---

## 总评

**整体安全等级: 中等偏下 (中等)**

- 主动安全 (加密存储、提权防护、提权收敛、CORS 默认收紧) 做得不错;
- 但**认证生命周期管理严重欠账** — 没有 token 撤销、没有 refresh rotation、没有速率限制、没有"注册开关"、没有 ephemeral 强制失败,是这个后端当前最薄弱的一环。
- 同时 `include_secrets` + `/test` + DEBUG 日志 dump 形成**凭据泄漏的放大链路**,任何 XSS / 凭据钓鱼都直接放大为第三方系统入侵。
- 在"内网测试平台"语境下,大部分 P1 可降为可接受风险,但 P0-1 (ephemeral 静默) 和 P0-3 (凭据自提放大器) 仍需优先处理,因为它们影响数据完整性与对外系统的访问安全。

**建议优先做的 3 项工作:**

1. **加 ephemeral 强制失败 + 注册开关 (P0-1 + P0-2)**: 把 dev/prod 环境区分开,生产强制 JWT_SECRET/FERNET_KEY 非空且 32+ 字节;加 `ALLOW_REGISTRATION` 开关 (默认 False,仅首部署时开)。这两条是低成本高收益的硬护栏,几分钟代码改动。

2. **收口凭据自提面 (P0-3 + P1-5)**: 删除 `?include_secrets=true` 路径或要求二次确认;删除 `github.py / wl.py / yhr.py` 三处 `logger.debug("...: {}", data/headers)`;加 URL 白名单 + scheme 限制给 `/test` 端点。这块是"凭据是否会从日志/响应里泄出去"的关键防线。

3. **实现 token 生命周期管理 (P1-2 + P1-3)**: 加 `password_changed_at` + JWT `pwd_ver` 字段做"改密即吊销";启用 refresh token rotation + reuse 检测,refresh 寿命从 14 天降到 7 天;补 `POST /api/auth/logout` 与 `/logout-all` 端点。这是把"被盗 token 还能用多久"从 14 天压缩到分钟级的根本措施。

---

*评审结束*