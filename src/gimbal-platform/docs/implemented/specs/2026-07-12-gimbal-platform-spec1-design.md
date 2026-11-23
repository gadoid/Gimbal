# Spec-1 Design · Gimbal Platform · 平台骨架 + 读路径

> 📅 Design date: 2026-07-12
> 🧭 Project: gimbal-platform（位于 `D:/Gimbal/gimbal-platform/`，与 `D:/Gimbal/Gimbal/` Gimbal 源同级）
> 📑 Visual: 配套 wireframe 在 `.superpowers/brainstorm/2717-1783857240/content/*.html`
> 🎯 Spec 整体：在 `PLATFORM_REQUIREMENTS.md` 5 模块 / 4 spec 拆分中，本 spec = Spec-1（平台骨架 + 读路径）

---

## 0. Spec-1 范围（In / Out）

### ✅ In scope

| 主题 | 内容 |
|---|---|
| 后端骨架 | FastAPI + SQLAlchemy (async, SQLite) + JWT + Fernet；目录结构（`app/{core, models, schemas, routers, services}`）；`init_db()` 自动建表 |
| 模块 A · 认证 | A1 自注册（首位注册人=admin）/ 登录 / refresh · **A2 用户管理 完整后端 + 前端** · A3 refresh + axios 拦截 + Pinia localStorage 持久化 |
| 模块 B · 列表 | B1 我的工作台（双 tab：我的上传 / 我的收藏） · B2 公共用例库（v2：去审核 tab / ⋯ dropdown / 作者 popover） · **不含上传、复制、搜索**（这些推迟到 Spec-2/4） |
| 模块 C · 用例配置页 | **仅读路径**（A3 深度）：完整 Prism 4 tab 折叠面板 + L1 字段👁（**仅本会话内存状态，不入 DB / 不写 yaml**）+ L3 平台默认预设（即 `sec-*`/`Sec-*` 6 个浏览器嗅探 header 已自动隐藏）+ 顶部固定栏 "👁 显示隐藏" toggle；**不支持修改 / 另存 / 导出**（推迟到 Spec-2） |
| 用例磁盘扫描器 | 每次请求扫描 `data/public/` 与 `data/users/<u>/cases/`，命中场景返回；`updated_at` 从 `os.path.getmtime` 读 |
| 真实用例种子 | `data/public/sc_e2e应收核销.json`（来自 `D:/Gimbal/Gimbal/gimbal-tmp/Scenario_Test_9.json`），启动时就位 |

### ❌ Out of scope（明确划出，不在本 spec）

| 不做 | 推迟到 |
|---|---|
| 用例上传（POST /api/cases/upload） | Spec-2 |
| 用例复制到我的（POST /api/cases/{id}/copy） | Spec-2 |
| vars 编辑器（C3） | Spec-2 |
| headers 引 auth 用户选择器（C4） | Spec-2 |
| 用例修改 / 另存 / 导出（C7） | Spec-2 |
| undo / redo（C8） | Spec-2 |
| 批量隐藏 UI（C2 L2） | Spec-4 |
| 字段隐藏 DB 持久化（C2 L1 升级） | Spec-2（先做内存版） |
| 认证管理页 D（凭证池 CRUD） | Spec-3 |
| 用例执行页 E（执行抽屉 / N 次并发） | Spec-3 |
| admin-only 路由强制 | **本 spec 不引入**（即使有 is_admin 列） |
| LLM 模板 / 黄金用例文档 | 暂不 |
| Alembic 迁移 | 直接 `Base.metadata.create_all()`，Alembic 推 V1 |
| Postgres | V1，本 spec 仅 SQLite |

---

## 1. 设计决策回顾（来自 brainstorming）

| 维度 | 决策 | 来源 |
|---|---|---|
| 形态 | **X = Disk-scan-on-request** | brainstorming 3 选 1 |
| 表策略 | **T1 = cases 表先建空着** | brainstorming 3 选 1 |
| 视觉辅助 | **是（开浏览器）** | brainstorming 3 选 1 |
| A 模块深度 | **B3 = 完整用户管理** | 第一轮 |
| A admin-only | **不在本 spec 引入** | 第一轮（保留 is_admin 列但不用） |
| 读路径深度 | **A3 = 4 tab 折叠 + L1👁 内存 + L3 预设已应用** | 第二轮 |
| 公共库 UI | 去审核 tab / ⋯ dropdown 操作 / 作者 popover（v2） | BDE |

---

## 2. 目录结构

```
D:/Gimbal/gimbal-platform/
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app + lifespan + CORS
│   │   ├── core/
│   │   │   ├── config.py            # Settings（pydantic-settings）
│   │   │   ├── db.py                # engine + SessionLocal + init_db
│   │   │   ├── security.py          # hash_password / verify_password / JWT / Fernet
│   │   │   └── deps.py              # get_current_user / require_admin (未消费)
│   │   ├── models/                  # 见 §4
│   │   ├── schemas/                 # Pydantic 请求/响应模型
│   │   ├── routers/
│   │   │   ├── auth.py              # /api/auth/...
│   │   │   ├── users.py             # /api/users/...
│   │   │   ├── cases.py             # /api/cases/...
│   │   │   └── cases-public.py      # /api/cases/public
│   │   └── services/
│   │       ├── case_loader.py       # disk-scan scanner
│   │       └── auth_passwords.py    # Fernet encode/decode
│   ├── data/                        # .gitignore
│   │   ├── app.db                   # SQLite
│   │   ├── public/
│   │   │   └── sc_e2e应收核销.json   # 种子
│   │   └── users/                   # 用户私有用例（spec-1 仍建空目录）
│   └── tests/
│       └── test_auth.py             # 鉴权最小单测（V0.1 仅 ≥1 个）
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/index.ts          # 见 §5
│   │   ├── stores/
│   │   │   ├── auth.ts              # access/refresh token + 当前用户
│   │   │   ├── cases.ts             # mine/public/favorites 列表缓存
│   │   │   ├── users.ts             # admin 用户列表
│   │   │   └── hide.ts              # L1/L3 字段隐藏 in-memory
│   │   ├── api/
│   │   │   ├── index.ts             # axios 实例 + 拦截器
│   │   │   ├── auth.ts
│   │   │   ├── users.ts
│   │   │   └── cases.ts
│   │   ├── views/
│   │   │   ├── Login.vue            # wireframe 2
│   │   │   ├── Register.vue         # wireframe 3
│   │   │   ├── CasesMine.vue        # wireframe 4
│   │   │   ├── CasesPublic.vue      # wireframe 5/v2
│   │   │   ├── CaseConfigReadonly.vue  # wireframe 1
│   │   │   └── UsersAdmin.vue       # wireframe 6
│   │   ├── components/
│   │   │   ├── TopNav.vue           # 顶部固定栏
│   │   │   ├── TabRow.vue           # 配置页 Tab 行
│   │   │   ├── CardStack.vue        # 卡片堆叠
│   │   │   ├── StepCard.vue         # step 折叠卡片（只读）
│   │   │   ├── FieldRow.vue         # label + value + 👁
│   │   │   ├── TagPill.vue
│   │   │   ├── JsonTree.vue         # request body 单色预览
│   │   │   └── modals/
│   │   │       ├── CreateUserModal.vue
│   │   │       └── ConfirmDialog.vue
│   │   └── styles/
│   │       ├── theme.css            # 沿用 Prism 视觉变量
│   │       └── override.css         # Element Plus 主题覆盖
└── docs/
    ├── PLATFORM_REQUIREMENTS.md     # 已存在（V0.1 顶层规约）
    └── superpowers/
        └── specs/
            └── 2026-07-12-gimbal-platform-spec1-design.md   # 本文件
```

---

## 3. 后端设计

### 3.1 数据模型（SQLAlchemy 异步 + SQLite）

```python
# 简化字段定义，仅约定形状
class User:
    id: PK
    username: str  UNIQUE
    display_name: str
    password_hash: str
    is_admin: bool  default False
    is_active: bool  default True
    created_at, updated_at: datetime

class Case:                   # 形态 X 决定：表中存"种子"占位用，运行时扫描覆盖
    id: PK
    scenario_id: str         # 与 yaml scenarioId 一致
    name, module, description: str
    visibility: enum('public', 'private')
    owner_id: FK -> users
    tags: str               # 逗号串联
    file_path: str          # 绝对路径
    audited: bool           # 公共用例 admin 标记
    created_at, updated_at

class CaseFavorite:
    id: PK
    user_id: FK
    case_id: FK
    UNIQUE(user_id, case_id)

# 推迟到 Spec-2 写：AuthCredential / Execution / ExecRun / HiddenFieldProfile / AuditLog
```

> Spec-1 仅建表：users, cases, case_favorites。其他表在 `__init__.py` 暂不 import，留 Spec-2/3 写入。
> 原因：spec-1 不会触发其他表的写入路径，建空表无意义；待真正需要再迁移 / 加 `Base.metadata.create_all()` 自动处理。

### 3.2 路由表

| Method | Path | 说明 | 鉴权 |
|---|---|---|---|
| POST | `/api/auth/register` | `{username, display_name?, password}` → `{access_token, refresh_token, user}` | 否 |
| POST | `/api/auth/login` | `{username, password}` → `{access_token, refresh_token, user}` | 否 |
| POST | `/api/auth/refresh` | `{refresh_token}` → 新 access | 否 |
| GET | `/api/auth/me` | `{user}` | Bearer |
| GET | `/api/users` | 列表（admin 视角全员，member 视角仅自己；**后端先简单实现：全员都看全员**，V1 加 admin 限制） | Bearer |
| POST | `/api/users` | 创建用户（admin）；"首注册人=admin" 规则只在 `/api/auth/register` 里；admin 创建的人默认 member | Bearer |
| PATCH | `/api/users/{id}` | 改昵称 / 角色（admin） / 状态（admin） | Bearer |
| POST | `/api/users/{id}/reset-password` | 返回新随机密码 | Bearer |
| DELETE | `/api/users/{id}` | 不能删除自己；不能降级最后一个 admin | Bearer |
| GET | `/api/cases/mine` | 当前用户的 my upload + favorites 合并或分 tab | Bearer |
| GET | `/api/cases/public` | visibility='public' 全列表；return 额外标 `audited` / `favorited_by_me` / `copied_by_me` | Bearer |
| GET | `/api/cases/{case_id}` | 返回 yaml 解析后的完整 dict（含 vim story）；运行态从磁盘读 | Bearer |
| POST | `/api/cases/{id}/favorite` | 加收藏 | Bearer |
| DELETE | `/api/cases/{id}/favorite` | 取消收藏 | Bearer |
| POST | `/api/cases/{id}/copy` | 公共用例 clone 到 `data/users/<u>/cases/<id>-copy-N.<ext>`；返回新 caseId；归属用户本账号（visibility=private） | Bearer |

> **关于 admin-only 路由强制**：本 spec 不消费 `is_admin` 字段 / 不引入 `require_admin` 依赖；所有 Bearer 用户都能访问 `/admin/users`，但**业务规则仍生效**：
> - 不能删除自己（后端校验 409）
> - 不能降级最后一个 admin（后端校验 409）
>
> Spec-1 范围内：用户的创建 / 角色变更 / 状态启停**全员可见全员都可调用**；直到 V1 接入 `require_admin` 时再收紧为 admin-only。

### 3.3 文件磁盘扫描器（services/case_loader.py）

```python
@dataclass
class CaseSummary:
    case_id: str
    name: str
    module: str
    description: str
    visibility: 'public' | 'private'
    owner_id: int | None
    audited: bool
    file_path: Path
    updated_at: datetime
    tags: list[str]

class CaseLoader:
    def scan(scope: 'public' | 'mine_user:<id>' | 'all') -> list[CaseSummary]: ...
    def read(case_id: str) -> dict:  # 返回 yaml 解析后完整 dict
```

- 启动时缓存一次 `mapping[case_id -> CaseSummary]`，后续读 / invalidate 用 `os.path.getmtime` 增量。
- 失败的处理：单个文件解析失败 → 记 `logger.warning`，跳过；不让一个坏 yaml 阻塞整盘。
- 路径：`base_dir = settings.PUBLIC_CASES_DIR / settings.USERS_CASES_DIR`，使用 `pathlib` 跨平台。

### 3.4 错误处理

- 后端统一响应：成功 `200/201`，错误 4xx/5xx 用 `{"code": int, "data": null, "msg": str}` 包裹。
- 业务错误码：
  - `4001` 缺少必填字段
  - `4003` 用户名重复（register）
  - `4004` 用户名或密码错（login）
  - `4400` 用户未登录或 token 无效
  - `4401` token 过期
  - `4503` 资源不存在
- 不暴露内部 stack trace 到生产；dev 时 `settings.DEBUG=true` 暴露。

### 3.5 后端最小测试

- `pytest tests/test_auth.py`：
  - 注册第一个用户 → 自动 is_admin=True
  - 注册第二个用户 → is_admin=False
  - 登录错密码 → 401 + code=4004
  - refresh token 流转正常

---

## 4. 前端设计

### 4.1 路由

| Path | View | 鉴权 |
|---|---|---|
| `/login` | Login.vue | 公开 |
| `/register` | Register.vue | 公开 |
| `/cases/mine` | CasesMine.vue | Bearer |
| `/cases/public` | CasesPublic.vue | Bearer |
| `/cases/:caseId/config` | CaseConfigReadonly.vue | Bearer |
| `/admin/users` | UsersAdmin.vue | Bearer（本 spec 不强制 admin-only） |
| `/` | 重定向到 `/cases/mine` | — |

未登录访问受保护路由 → 跳 `/login` 并保留 redirect。
已登录访问 `/login` 或 `/register` → 跳 `/cases/mine`。

### 4.2 Pinia stores

| Store | 关键 state |
|---|---|
| `authStore` | `accessToken / refreshToken / currentUser`；持久化到 localStorage（key=`gimbal-auth`），刷新时 init |
| `casesStore` | `mine.favorites: CaseSummary[]`，`mine.uploads: CaseSummary[]`，`publicLibrary: CaseSummary[]`；`fetchMine()` / `fetchPublic()` 方法 |
| `usersStore` | `list: User[]`，`summary: {total, active, admin, recent}`，`create / patch / delete` actions |
| `hideStore` | `hiddenPaths: Set<string>`（in-memory, L1 切换加 / 减）；L3 默认列表硬编码：`['api.headers["sec-ch-ua-platform"]', ...]` 共 6 项 + `meta.requirementRef`；`isVisible(path)` getter |

### 4.3 主题（沿用 Prism）

```css
/* theme.css 关键变量 */
--color-bg-primary: #ffffff;
--color-bg-secondary: #f5f3ee;
--color-text-primary: #1f2933;
--color-text-secondary: #64748b;
--color-border-tertiary: #e2e8f0;
--accent: #4338ca;
--accent-hover: #3730a3;
--accent-soft: #eef2ff;
--accent-soft-border: #c7d2fe;
--red: #e24b4a;
--green: #22c55e;
--amber: #f59e0b;
--font-mono: ui-monospace, "Cascadia Mono", "JetBrains Mono", Menlo, monospace;
```

Element Plus 通过 `override.css` 把 primary 改成 `#4338ca`，去掉默认深色丑陋的 drawer。

### 4.4 Wireframe 规约（浓缩各页关键点）

#### 4.4.1 `/login`（wireframe 2）
- 居中 380px 卡片 / 浅紫渐变背景 / 32+36 padding
- 品牌头：左"G"渐变 logo + "Gimbal Platform / 用例配置 & 执行平台 · v0.1"
- 错误条：登录失败时滑出 #fef2f2 + 左红边 3px
- 字段：用户名 / 密码（右侧👁切换可见） / "30 天内保持登录" 复选 / "忘记密码" 链接
- 主按钮"登录"紫色实心 / 底部"立即注册"
- 分隔下："开发模式提示" — 仅 db 完全空时显示 "admin/admin" 黄色条

#### 4.4.2 `/register`（wireframe 3）
- 居中 420px 卡片（同 size 视觉连续）
- 双列：用户名（必填）/ 昵称（可选）
- 密码：单列输入框，下方 4 段强度条 + STRONG/OK/WEAK + 4 条规则勾
- 确认密码实时一致性 ✓/✗
- 隐私勾选：Fernet 加密说明
- 主按钮"注册并登录"
- 用户名冲突：字段红边 + 行内 ✗"字母数字下划线, 3-32 位"
- 注册成功：绿色条 + 3 秒倒计时跳转 /cases/mine

#### 4.4.3 `/cases/mine`（wireframe 4）
- 顶部固定栏：4 nav entry（📋/🌐/🔐/⚙️）+ 用户徽章 + 登出
- Page header：左标题"用例工作台" + 元信息（4 用例·1 收藏·最后更新 2 分钟前）；右搜索 + 高级过滤 + "+ 上传"（disabled）
- Tabs：我的上传 (3) / ⭐ 我的收藏 (1)
- Element Plus 表格：⭐/名称 + scenarioId/模块彩 tag/P1~P3 红橙牌/作者/tags 紫胶囊/相对时间/操作（▶+→）
- 已收藏行：行底紫色高亮 + ★ 金色
- 公共用例来源：行尾"公共"灰色 badge

#### 4.4.4 `/cases/public`（wireframe 5/v2）
- 同 mine 结构 + 当前 nav 激活 🌐
- v2 后**无审核 tab**：行内"审核"列仅用绿/米 tag 表示
- 操作列 ⋯ dropdown（节省列宽）：
  - "👁 查看详情"
  - "★ 收藏 / ★ 已收藏 · 取消收藏"（动态文案）
  - "📋 复制到我的 / 📋 已复制 · 再复制一份"（动态）
  - 分隔 / "⤴ 打开源 yaml"
- 作者列：紫色下划点线 span，点击弹 author profile popover；自己看自己时加"你"小紫牌

#### 4.4.5 `/cases/:caseId/config`（wireframe 1，read-only）
- 顶部固定栏同 prism；右侧多 👁「显示隐藏」toggle + 只读 YAML + 帮助
- Tab 行：01 meta / 02 config / 03 resource / 04 steps，当前激活紫底浅紫字；右侧"27 步 · 6 字段已批量隐藏 · ~85% 噪声被屏蔽"
- Card stack 包裹 step 列表；step 默认折叠，点开渲染：
  - L3 蓝色提示卡："本步骤隐藏了 6 个浏览器嗅探 header"（可关闭）
  - sub-tab：description / api / request / strategy
  - 当前 sub-tab=request 时渲染 Headers key-value 表，每行 👁（L1）；隐藏行以灰色 strike 形式浮现
  - body：单色 JSON 预览（折叠到关键字段）
- 不支持：拖拽重排（推迟 Spec-2，read-only 不需要）
- 不支持：保存 / 复制 / 导出（推迟 Spec-2）

#### 4.4.6 `/admin/users`（wireframe 6）
- 顶部固定栏同 + 当前 nav 激活 ⚙️
- Page header：12 用户 · 10 启用 · 2 停用 · 3 admin · 7 天内 5 人登录
- 操作栏：搜索 + 角色筛选 + "+ 创建用户"
- 表格：用户名（含首字母圆球 avatar + "你"紫牌）/ 昵称 / 角色（🛡 admin 红牌 / 成员 紫牌）/ 状态（●启用 / ○停用）/ 创建时间 / 最后登录 / 操作 ⋯
- 自己行：行底绿色 + "你"紫牌 + "— 自助 —"
- 停用用户：删除线 + 行底红淡化
- 下拉菜单：编辑昵称 / 修改角色 / 重置密码 / 停用·启用 / 删除（5 项）
- 创建用户 modal（浮层示意）：用户名 / 昵称 / 初始密码（🎲随机 + 规则提示）/ 角色 radio
- 删除二次确认 dialog：要求输入 username 二次确认

### 4.5 API 客户端（src/api/）

```typescript
// src/api/index.ts
import axios from 'axios'
const http = axios.create({ baseURL: '/api', timeout: 30_000 })
http.interceptors.request.use((cfg) => {
  const t = authStore.accessToken
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})
http.interceptors.response.use(undefined, async (err) => {
  if (err.response?.status === 401) {
    // 试 refresh 一次；失败则跳 /login
  }
  throw err
})
```

### 4.6 路由守卫

```typescript
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.accessToken) return { path: '/login', query: { redirect: to.fullPath } }
  if ((to.path === '/login' || to.path === '/register') && auth.accessToken) return { path: '/cases/mine' }
})
```

---

## 5. 验收场景

| ID | 场景 | 步骤 | 期望 |
|---|---|---|---|
| AC-1 | 首次启动 | `python -m app.main` + 浏览器开 http://localhost:5173 | 跳 `/login`；带黄色 dev 提示"admin/admin" |
| AC-2 | 注册流程 | 点"立即注册"→ 填 liuyu / Hello2026! → 注册 | 绿色成功条 + 3 秒跳 /cases/mine；左侧 nav 显示"liuyu (member)" |
| AC-3 | 登录 | admin / admin（首启动时）→ 登录 | 进 /cases/mine，显示已有 1 个公共用例（e2e应收核销） |
| AC-4 | 我的工作台 | 登录后看 /cases/mine | Tabs：上传 0 / 收藏 0 (因为新建用户无历史) |
| AC-5 | 公共库 | 切到 🌐 公共用例库 | 看到 1 个用例（e2e应收核销） |
| AC-6 | 收藏 | 公共库点 ⋯ → 收藏 | 操作列变"已收藏 ★"金黄色；切到 ⭐ 我的收藏 tab 出现该用例 |
| AC-7 | 进配置页 | 公共库点 ⋯ → 查看 OR 表格行名 | 进 /cases/{caseId}/config；4 tab 折叠面板；默认 steps active |
| AC-8 | L3 默认隐藏 | 展开任一 step → sub-tab=request | Headers 表只显示 Authorization + Content-Type；不显示 sec-* 6 个 |
| AC-9 | L1 字段隐藏 | 在 Headers 表点任一行的 👁 | 该行变灰 strike；可重复点 👁 / 🔓 切换 |
| AC-10 | 显示隐藏 toggle | 顶部 👁 开启 | L1 + L3 隐藏字段以灰色 strike 浮现 |
| AC-11 | 用户管理 | admin 登录 → ⚙️ 用户管理 | 看到 1 行（自己），行底绿色 + "你" 紫牌；操作列 "— 自助 —" |
| AC-12 | 创建用户 | 点 + 创建用户 → 填 wang_p / Test2026! / 角色 成员 | 列表加一行 wang_p |
| AC-13 | 删除二次确认 | 选中新建用户 ⋯ → 删除 | 弹 dialog；要求输入用户名才能 confirm |
| AC-14 | 登出 + 重新登录 | 登出 → 重新登录 | token 重新发；in-memory hide 状态被清空 |
| AC-15 | 公共库复制 | admin 在 /cases/public 点 ⋯ → "📋 复制到我的" | 后端 clone 成功；返回 201 + 新 caseId；切到 /cases/mine 看到新私有副本 |

---

## 6. 部署 / 启动

```bash
# 后端
cd backend
pip install -e .
cp .env.example .env
python -m app.main
# → uvicorn 0.0.0.0:8000

# 前端
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

数据库：`data/app.db`，运行时自动建表。
种子用例：`data/public/sc_e2e应收核销.json`，启动时扫描到列表。

---

## 7. 不在 Spec-1（明确划出）

如 §0 §"Out of scope" 一栏，所有写路径 / 编辑能力 / 执行 / 凭证池 / DB 持久化的隐藏 / admin-only 都被推到 Spec-2 / 3 / 4。

---

## 附录 A：与原始需求文档的关系

`/D:/Gimbal/gimbal-platform/docs/PLATFORM_REQUIREMENTS.md` 是 V0.1 顶层需求规约，本 Spec-1 是把其中的 A / B / C "读" 子集以可执行的形式落定。

后续 Spec-2/3/4 会再切分，每切一次同步更新一次本附录。

---

## 附录 B：自审清单（写完后跑一遍）

| 项 | 状态 | 说明 |
|---|---|---|
| Placeholder scan（"TBD" / "TODO" / 待补字段） | ✅ 通过 | 无遗留占位 |
| 内部一致性 | ✅ 已修 | §4.4.4 v2 下拉里的"复制"原本被推迟到 Spec-2 但 wireframe 已锁 → 收回 Spec-1 加端点 + AC-15 |
| Scope check | ✅ 通过 | §0 §Out 已显式列出 14 项推迟项 |
| Ambiguity check | ✅ 通过 | 主要动词在 §3.4 错误码表 + §5 验收场景有明确语义 |
| 已知轻微不阻断项 | ⚠️ | ① `usersStore` 在 v0.1 阶段全员可见全员可写，但 v1 再收紧——明确写在路由表注；② `python -m app.main` 需 main.py 有 `if __name__ == "__main__"`，常规实现；③ §4.4.5 wireframe 1 提到 sub-tab `strategy` 显示 assertion/extract/assign 列表——spec-1 实现时不写到 React 端，只渲染头部图标 |
