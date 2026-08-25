# 认证功能改造:配置页用户卡片 + 认证管理页 UI 重整 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 场景编排配置页新增"用户认证"卡片(手动配置 + 凭证池快照导入,导出携带用户信息),认证管理页三按钮同行 + 测试弹框改为 认证中→认证成功/失败 状态主视觉式。

**Architecture:** 凭证池按需解密(`GET /api/auths/{id}?include_secrets=true`)→ 快照 `{url, username, password, token_type, expires_in}` 写入场景 `config.users`(plate 契约已有,导出/执行链路零改动)。probe 认证器同步调用丢线程池修事件循环阻塞。前端新增 UsersCard 组件 + Auths.vue 弹框状态机。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2(后端);Vue 3 + Element Plus + Pinia + vitest(前端)。

**Spec:** `src/gimbal-platform/docs/superpowers/specs/2026-08-25-auth-users-card-and-auths-page-design.md`

## Global Constraints

- 明文密码策略仅限内网测试环境(spec §后端 include_secrets 节);认证管理列表仍不返回/不展示密码。
- 不动 gimbal 主仓 `src/gimbal/**`;不动 plate 契约(`gimbal-plate/**` 只读)。
- 快照形状固定 5 字段:`{url, username, password, token_type, expires_in}`(与 run_dispatcher 注入器写入形状一致)。
- alias 校验规则与认证管理一致:`/^[A-Za-z0-9_-]{1,64}$/`。
- 后端测试:在 `src/gimbal-platform/backend` 下 `python -m pytest <file> -v`(asyncio_mode=auto,无需装饰器;环境已就绪)。
- 前端测试:在 `src/gimbal-platform/frontend` 下 `npm run test -- <path>`;类型检查 `npm run typecheck`。
- 提交信息沿用仓库约定:`feat(platform): …` / `feat(frontend): …` / `fix(platform): …`,结尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- Windows Git Bash 环境;文件路径用正斜杠。

---

### Task 1: 后端 — `GET /api/auths/{id}` 支持 `include_secrets`

**Files:**
- Modify: `src/gimbal-platform/backend/app/schemas/auth_session.py`(文件末尾追加)
- Modify: `src/gimbal-platform/backend/app/routers/auth_sessions.py:131-139`(detail 端点)与 imports(31-36 行)
- Test: `src/gimbal-platform/backend/tests/test_auth_sessions.py`(文件末尾追加)

**Interfaces:**
- Consumes: 现有 `_get_owned`、`fernet_decrypt`、`AuthSessionOut`。
- Produces: `GET /api/auths/{id}?include_secrets=true` → 200,JSON = AuthSessionOut 全字段 + `password: str`(明文);密文不可解密 → 422 `{"detail": "加密凭据已损坏或密钥已轮换，请先在认证管理重新编辑保存"}`;跨 owner → 404(现有行为)。后续前端 Task 3 依赖此契约。

- [ ] **Step 1: 写失败测试**

在 `tests/test_auth_sessions.py` 末尾(`test_endpoints_require_auth` 之后)追加:

```python
# ── GET detail + include_secrets(2026-08-25 认证改造设计)─────────
async def test_detail_without_secrets_keeps_password_masked(client: AsyncClient) -> None:
    """不带 include_secrets 的详情:行为与改造前一致,不泄露明文。"""
    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "s3cret"},
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}", headers=auth)
    assert r.status_code == 200
    assert "password" not in r.json()
    assert r.json()["password_masked"] == "<REDACTED>"


async def test_detail_with_secrets_returns_plaintext(client: AsyncClient) -> None:
    """include_secrets=true:附解密后的明文 password(内网测试环境策略)。"""
    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={
            "alias": "qa1",
            "url": "https://x",
            "username": "alice_user",
            "password": "s3cret",
        },
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "alice_user"
    assert body["password"] == "s3cret"


async def test_detail_with_secrets_cross_owner_404(client: AsyncClient) -> None:
    a_auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=a_auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    b_auth = await register_and_login(client, "bob", "bobpass456")
    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=b_auth)
    assert r.status_code == 404


async def test_detail_with_secrets_rotation_422(
    client: AsyncClient, monkeypatch
) -> None:
    """FERNET_KEY 轮换后的旧密文:严解密失败 → 422(带人话指引)。

    快照拷贝会把返回值当真值写进场景导出产物,所以这里不能像列表
    _safe_decrypt 那样降级为占位符 — 必须显式失败。
    """
    from app.routers import auth_sessions as router_mod

    def boom(_s: str) -> str:
        raise ValueError("key rotated")

    monkeypatch.setattr(router_mod, "fernet_decrypt", boom)

    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    r = await client.get(f"/api/auths/{aid}?include_secrets=true", headers=auth)
    assert r.status_code == 422
    assert "重新编辑保存" in r.json()["detail"]
```

- [ ] **Step 2: 运行确认失败**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_auth_sessions.py -v -k "secrets"
```
预期:`test_detail_with_secrets_returns_plaintext` 与 `test_detail_with_secrets_rotation_422` FAIL(响应无 password / 状态 200 而非 422);其余两个新用例 PASS(现状行为)。

- [ ] **Step 3: 最小实现**

`schemas/auth_session.py` 末尾(TestResult 之后)追加:

```python
class AuthSessionSecretsOut(AuthSessionOut):
    """include_secrets=true 时的详情视图 — 附解密后的明文 password。

    仅限内网测试环境的策略放宽(2026-08-25 认证改造设计):场景配置页
    "从凭证池导入"需要把明文快照拷进 config.users(导出在前端本地拼装,
    明文必须过客户端)。列表接口行为不变,不带密。
    """

    password: str
```

`routers/auth_sessions.py`:imports(31-36 行)加入 `AuthSessionSecretsOut`:

```python
from ..schemas.auth_session import (
    AuthSessionCreateIn,
    AuthSessionOut,
    AuthSessionPatchIn,
    AuthSessionSecretsOut,
    TestResult,
)
```

替换 detail 端点(131-139 行)为:

```python
# ── detail ─────────────────────────────────────────────────────
@router.get("/{auth_id}", response_model=AuthSessionSecretsOut | AuthSessionOut)
async def get_auth(
    auth_id: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    session: DbSession,
    include_secrets: bool = False,
) -> AuthSessionOut | AuthSessionSecretsOut:
    a = await _get_owned(session, auth_id, user.id)
    if not include_secrets:
        return _to_out(a)
    # 严解密:密钥轮换后的旧密文不可恢复。快照拷贝会把返回值当真值写进
    # 场景导出产物,不能像列表 _safe_decrypt 那样降级为占位符 — 显式 422。
    try:
        username = fernet_decrypt(a.username_enc)
        password = fernet_decrypt(a.password_enc)
    except ValueError as e:
        logger.warning("auth.get include_secrets: fernet decrypt failed: {}", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="加密凭据已损坏或密钥已轮换，请先在认证管理重新编辑保存",
        )
    return AuthSessionSecretsOut(
        id=a.id,
        alias=a.alias,
        url=a.url,
        username=username,
        password=password,
        token_type=a.token_type,
        expires_in=a.expires_in,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )
```

- [ ] **Step 4: 运行确认通过**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_auth_sessions.py -v
```
预期:新增 4 用例全 PASS;`test_test_endpoint_*` 2 个仍红(c5cab10 遗留,Task 2 修),其余绿。

- [ ] **Step 5: 提交**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/schemas/auth_session.py src/gimbal-platform/backend/app/routers/auth_sessions.py src/gimbal-platform/backend/tests/test_auth_sessions.py && git commit -m "feat(platform): /auths/{id} include_secrets 按需解密 — 快照拷贝供场景配置页

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 后端 — probe 下线程执行 + 红测试收口

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/auth_probe.py:34-36`(authenticate 调用)
- Test: `src/gimbal-platform/backend/tests/test_auth_sessions.py:200-276`(两个红测试重写)

**Interfaces:**
- Consumes: 无新依赖(`asyncio` 标准库)。
- Produces: `auth_probe.probe` 签名/返回值不变 `(ok, status_code, message)`;行为变化 = 认证器在线程池执行,事件循环不再被同步 `httpx.post`(最长 30s)阻塞。

- [ ] **Step 1: 重写两个红测试(即为失败测试 — 现 mock 方式与实现不符)**

`auth_probe.probe` 内部经 `get_authenticator("https://…")` 走 `HTTPSAuthenticator.authenticate`,其用**同步** `httpx.post`(见 `app/auth/authenticators/http_basic.py:16`)。将 `test_test_endpoint_returns_token_preview`(201-238 行)与 `test_test_endpoint_4xx_returns_failure`(241-276 行)整体替换为:

```python
# ── /test endpoint ──────────────────────────────────────────────
async def test_test_endpoint_returns_token_preview(
    client: AsyncClient, monkeypatch
) -> None:
    """Mock 同步 httpx.post(probe 经 to_thread 调认证器)验证 token 提取。"""
    import httpx

    req = httpx.Request("POST", "https://x")

    def fake_post(*a: object, **kw: object) -> httpx.Response:
        return httpx.Response(
            200, json={"access_token": "fake-token-abcdef123456"}, request=req
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    r = await client.post(f"/api/auths/{aid}/test", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["status_code"] == 200
    assert "fake-token" in body["message"]


async def test_test_endpoint_4xx_returns_failure(
    client: AsyncClient, monkeypatch
) -> None:
    """401 → raise_for_status 抛 HTTPStatusError → ok=False、status_code=None。

    迁移后 probe 失败路径不再透传 4xx 码(auth_probe.py 失败分支恒 None),
    前端弹框仅在 status_code 非空时显示 HTTP badge。
    """
    import httpx

    req = httpx.Request("POST", "https://x")

    def fake_post(*a: object, **kw: object) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad creds"}, request=req)

    monkeypatch.setattr(httpx, "post", fake_post)

    auth = await register_and_login(client)
    r = await client.post(
        "/api/auths",
        headers=auth,
        json={"alias": "qa1", "url": "https://x", "username": "u", "password": "p"},
    )
    aid = r.json()["id"]

    r = await client.post(f"/api/auths/{aid}/test", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["status_code"] is None
    assert "网络/认证错误" in body["message"]
```

- [ ] **Step 2: 运行确认失败**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_auth_sessions.py -v -k "test_endpoint"
```
预期:token_preview 用例可能已过(未加 to_thread 时同步调用同样命中 monkeypatch 的 httpx.post)——这没关系;本任务的实质变更是 Step 3 的线程池修复,4xx 用例断言的是既有迁移后行为。若 4xx 用例 FAIL 则说明 probe 行为与理解不符,停下来核查 `auth_probe.py` 后再继续。

- [ ] **Step 3: probe 下线程实现**

`app/services/auth_probe.py`:顶部 import 区(`from app.auth import …` 之后)加:

```python
import asyncio
```

将 34-36 行的:

```python
    try:
        # 3. 执行认证(authenticator 内部会调 apply_token 写入 token)
        authenticator.authenticate(auth, tag="probe")
```

改为:

```python
    try:
        # 3. 执行认证(authenticator 内部会调 apply_token 写入 token)。
        #    认证器是同步 httpx.post(最长 30s)— 直接在事件循环里跑会把
        #    整个后端卡住(测试弹框"认证中"期间所有请求停摆),丢线程池执行。
        await asyncio.to_thread(authenticator.authenticate, auth, "probe")
```

- [ ] **Step 4: 全套后端测试确认绿**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/ -q
```
预期:全部 PASS、无失败(原套件 247 个中 2 个红测试已收口 + Task 1 新增 4 个 = 251 全绿;数量以实际运行为准,关键是零失败零豁免)。

- [ ] **Step 5: 提交**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/services/auth_probe.py src/gimbal-platform/backend/tests/test_auth_sessions.py && git commit -m "fix(platform): auth probe 下线程执行修事件循环阻塞 + test_test_endpoint 红测试收口

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 前端 — API `get` + store `fetchDetail` + `UserAuthView` 类型

**Files:**
- Modify: `src/gimbal-platform/frontend/src/api/auth_sessions.ts`(末尾追加)
- Modify: `src/gimbal-platform/frontend/src/stores/auth_sessions.ts`(import、action、return、头注释)
- Modify: `src/gimbal-platform/frontend/src/types/plate.ts:292-301`
- Test: `src/gimbal-platform/frontend/src/stores/__tests__/auth_sessions.test.ts`(追加用例)

**Interfaces:**
- Consumes: Task 1 的后端契约(`?include_secrets=true` → 含 `password`)。
- Produces(Task 4/5 依赖):
  - `api/auth_sessions.ts`:`interface AuthSessionSecrets extends AuthSession { password: string }`;`get(id: number, includeSecrets?: boolean): Promise<AuthSession | AuthSessionSecrets>`
  - `stores/auth_sessions.ts`:`fetchDetail(id: number, includeSecrets?: boolean): Promise<AuthSession | AuthSessionSecrets>`(直通,不落 store 状态)
  - `types/plate.ts`:`interface UserAuthView { url?; username?; password?; token_type?; expires_in? }`(全可选,兼容导入/历史 payload);`ConfigView.users: Record<string, UserAuthView>`

- [ ] **Step 1: 写失败测试**

`stores/__tests__/auth_sessions.test.ts` 的 `describe` 内(`testConnection` 用例后)追加:

```ts
  it('fetchDetail 直通 api.get;includeSecrets 明文不落 store 状态', async () => {
    const secrets = { ...sample, password: 's3cret' }
    const getSpy = vi.spyOn(api, 'get').mockResolvedValue(secrets)
    const s = useAuthSessionsStore()
    const r = await s.fetchDetail(1, true)
    expect(r).toEqual(secrets)
    expect(getSpy).toHaveBeenCalledWith(1, true)
    expect(JSON.stringify(s.$state)).not.toContain('s3cret')
  })
```

- [ ] **Step 2: 运行确认失败**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test -- src/stores/__tests__/auth_sessions.test.ts
```
预期:FAIL — `api.get` 不是函数(store 尚无 fetchDetail)。

- [ ] **Step 3: 最小实现**

`api/auth_sessions.ts` 末尾追加:

```ts
export interface AuthSessionSecrets extends AuthSession {
  password: string
}

/** 详情;includeSecrets=true 时后端附解密明文密码(内网测试环境策略,
 *  2026-08-25 认证改造设计 — 供场景配置页快照拷贝)。 */
export function get(
  id: number,
  includeSecrets = false,
): Promise<AuthSession | AuthSessionSecrets> {
  return http
    .get<AuthSession | AuthSessionSecrets>(`/auths/${id}`, {
      params: includeSecrets ? { include_secrets: true } : undefined,
    })
    .then((r) => r.data)
}
```

`stores/auth_sessions.ts`:
1. import type 增加 `AuthSessionSecrets`:

```ts
import type {
  AuthSession,
  AuthSessionCreateIn,
  AuthSessionPatchIn,
  AuthSessionSecrets,
  TestResult,
} from '@/api/auth_sessions'
```

2. `testConnection`(56-58 行)之后追加:

```ts
  /** 按需取详情;includeSecrets 时为一次性快照直通 — 明文不落 store 状态。 */
  async function fetchDetail(
    id: number,
    includeSecrets = false,
  ): Promise<AuthSession | AuthSessionSecrets> {
    return await authSessionsApi.get(id, includeSecrets)
  }
```

3. `return { … }` 中 `testConnection,` 之后加一行 `fetchDetail,`。
4. 头注释第 5-6 行 "The store does NOT cache plaintext passwords; passwords are write-only from the UI and never returned by the backend." 改为:

```ts
 * The store does NOT cache plaintext passwords; passwords are write-only
 * from the UI — except fetchDetail(includeSecrets), a pass-through used by
 * the composer users-card snapshot copy (plaintext never lands in state).
```

`types/plate.ts` — 292-301 行的 `ConfigView` 前追加类型、并收紧 users 字段:

```ts
/** 场景级认证用户快照(plate AuthSession 的配置字段子集,
 *  与 run_dispatcher 执行注入写入形状一致)。字段可选:
 *  兼容导入/历史 payload 的不完整 users。 */
export interface UserAuthView {
  url?: string
  username?: string
  password?: string
  token_type?: string
  expires_in?: number
}
```

`ConfigView` 内 `users: Record<string, unknown>` 改为 `users: Record<string, UserAuthView>`。

- [ ] **Step 4: 运行确认通过 + 类型影响面核验**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test -- src/stores/__tests__/auth_sessions.test.ts && npm run typecheck
```
预期:测试 PASS;`vue-tsc --noEmit` 无错误(users 消费点已核仅:plate.ts 类型、CaseComposer 默认 `users: {}`、CaseComposerConfig 3 处透传、RunDialog 提示文案 — 全部兼容收紧)。

- [ ] **Step 5: 提交**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/api/auth_sessions.ts src/gimbal-platform/frontend/src/stores/auth_sessions.ts src/gimbal-platform/frontend/src/types/plate.ts src/gimbal-platform/frontend/src/stores/__tests__/auth_sessions.test.ts && git commit -m "feat(frontend): auth_sessions get/fetchDetail(include_secrets) + UserAuthView 类型收紧

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 前端 — UsersCard 组件 + 挂载进配置页

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/composer/UsersCard.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue`(模板 services 卡后挂载 + import + 头注释 + 一条样式)
- Test: Create `src/gimbal-platform/frontend/src/components/composer/__tests__/UsersCard.test.ts`;Modify `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerConfig.test.ts`(追加集成用例)

**Interfaces:**
- Consumes: Task 3 的 `UserAuthView`、`get`/`list`(api/auth_sessions);全局 composer.css(`.c-card/.c-card-head/.c-empty/.c-add` 等,main.ts 已全局引入)。
- Produces: `UsersCard` 组件 — `props: { modelValue: Record<string, UserAuthView> }`,`emits: 'update:modelValue': [Record<string, UserAuthView>]`(整体替换式 emit)。CaseComposerConfig 以 `<UsersCard v-model="local.users" />` 挂载。

- [ ] **Step 1: 写失败测试(组件 + 集成)**

新建 `components/composer/__tests__/UsersCard.test.ts`:

```ts
/**
 * UsersCard.vue — ③ 配置页用户认证卡(2026-08-25 认证改造)。
 *
 * 覆盖:已有 users 明文渲染、手动添加/删除 emit 快照、凭证池导入
 * (已存在 alias 置灰、明文快照写入、422 跳过该条继续)。
 * api/auth_sessions 全 mock — 不碰网络。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import UsersCard from '@/components/composer/UsersCard.vue'
import { list, get } from '@/api/auth_sessions'
import type { UserAuthView } from '@/types/plate'

vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(),
  get: vi.fn(),
}))

const poolA = {
  id: 1, alias: 'pool-a', url: 'https://a/auth', username: 'ua',
  token_type: 'Bearer', expires_in: 3600,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
}
const poolB = {
  id: 2, alias: 'pool-b', url: 'https://b/auth', username: 'ub',
  token_type: 'Basic', expires_in: 60,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(list).mockResolvedValue([poolA, poolB] as any)
  vi.mocked(get).mockImplementation((id: number) =>
    Promise.resolve(
      id === 1 ? { ...poolA, password: 'plain-pw-1' } : { ...poolB, password: 'plain-pw-2' },
    ) as any,
  )
})

function mountCard(initial: Record<string, UserAuthView>) {
  const users = ref<Record<string, UserAuthView>>(initial)
  const Parent = defineComponent({
    setup() {
      return () => h(UsersCard, {
        modelValue: users.value,
        'onUpdate:modelValue': (v: Record<string, UserAuthView>) => { users.value = v },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] }, attachTo: document.body })
  return { w, users }
}

const flush = () => new Promise((r) => setTimeout(r, 0))

function setInput(placeholderPrefix: string, value: string) {
  const el = [...document.querySelectorAll('.el-dialog input')]
    .find((i) => (i as HTMLInputElement).placeholder.startsWith(placeholderPrefix)) as HTMLInputElement
  el.value = value
  el.dispatchEvent(new Event('input'))
}

function clickDialogButton(text: string) {
  ;([...document.querySelectorAll('.el-dialog__footer button')]
    .find((b) => b.textContent!.includes(text)) as HTMLElement).click()
}

describe('UsersCard — 渲染与手动 CRUD', () => {
  it('已有 users 明文渲染(alias/url/username/password 列)', () => {
    const { w } = mountCard({
      qa1: { url: 'https://x/auth', username: 'alice', password: 'plain-pw', token_type: 'Bearer', expires_in: 3600 },
    })
    expect(w.text()).toContain('qa1')
    expect(w.text()).toContain('plain-pw')
    w.unmount()
  })

  it('手动添加用户 → emit 5 字段快照', async () => {
    const { w, users } = mountCard({})
    await w.findAll('button').filter((b) => b.text().includes('添加用户'))[0].trigger('click')
    await flush()
    setInput('例 qa1', 'new-user')
    setInput('https://target', 'https://y/login')
    setInput('登录用户名', 'u1')
    setInput('登录密码', 'p1')
    await flush()
    clickDialogButton('添加')
    await flushPromises()
    expect(users.value['new-user']).toEqual({
      url: 'https://y/login', username: 'u1', password: 'p1',
      token_type: 'Bearer', expires_in: 7200,
    })
    w.unmount()
  })

  it('alias 冲突时手动添加被拒(不静默覆盖)', async () => {
    const { w, users } = mountCard({
      qa1: { url: 'https://x', username: 'a', password: 'p', token_type: 'Bearer', expires_in: 60 },
    })
    await w.findAll('button').filter((b) => b.text().includes('添加用户'))[0].trigger('click')
    await flush()
    setInput('例 qa1', 'qa1')
    setInput('https://target', 'https://y')
    setInput('登录用户名', 'u2')
    setInput('登录密码', 'p2')
    await flush()
    clickDialogButton('添加')
    await flushPromises()
    expect(users.value['qa1'].username).toBe('a') // 未被覆盖
    w.unmount()
  })

  it('删除用户 → emit 移除后的字典', async () => {
    const { w, users } = mountCard({
      qa1: { url: 'https://x', username: 'a', password: 'p' },
      qa2: { url: 'https://y', username: 'b', password: 'q' },
    })
    await w.findAll('button').filter((b) => b.text() === '删除')[0].trigger('click')
    await flush()
    expect(users.value['qa1']).toBeUndefined()
    expect(users.value['qa2']).toBeTruthy()
    w.unmount()
  })
})

describe('UsersCard — 凭证池导入', () => {
  it('已存在 alias 置灰;导入写入明文快照', async () => {
    const { w, users } = mountCard({
      'pool-b': { url: 'https://old', username: 'old', password: 'old' },
    })
    await w.findAll('button').filter((b) => b.text().includes('从凭证池导入'))[0].trigger('click')
    await flushPromises()
    const items = [...document.querySelectorAll('.pool-item')] as HTMLElement[]
    const taken = items.find((el) => el.textContent!.includes('pool-b'))!
    expect(taken.classList.contains('disabled')).toBe(true)
    const fresh = items.find((el) => el.textContent!.includes('pool-a'))!
    expect(fresh.classList.contains('disabled')).toBe(false)
    fresh.click()
    await flush()
    clickDialogButton('导入')
    await flushPromises()
    expect(users.value['pool-a']).toEqual({
      url: 'https://a/auth', username: 'ua', password: 'plain-pw-1',
      token_type: 'Bearer', expires_in: 3600,
    })
    expect(users.value['pool-b'].username).toBe('old') // 已存在未被覆盖
    w.unmount()
  })

  it('单条 422 → 跳过该条、其余继续导入', async () => {
    vi.mocked(get).mockImplementation((id: number) =>
      id === 1
        ? Promise.reject(new Error('加密凭据已损坏或密钥已轮换，请先在认证管理重新编辑保存'))
        : Promise.resolve({ ...poolB, password: 'plain-pw-2' } as any),
    )
    const { w, users } = mountCard({})
    await w.findAll('button').filter((b) => b.text().includes('从凭证池导入'))[0].trigger('click')
    await flushPromises()
    ;([...document.querySelectorAll('.pool-item')] as HTMLElement[])
      .filter((el) => !el.classList.contains('disabled'))
      .forEach((el) => el.click())
    await flush()
    clickDialogButton('导入')
    await flushPromises()
    expect(users.value['pool-a']).toBeUndefined()
    expect(users.value['pool-b']).toMatchObject({ password: 'plain-pw-2' })
    w.unmount()
  })
})
```

`CaseComposerConfig.test.ts` 末尾追加(文件顶部 import 区补 `import UsersCard from '@/components/composer/UsersCard.vue'`):

```ts
describe('CaseComposerConfig — 用户认证卡(2026-08-25)', () => {
  it('UsersCard 挂载;users 变更经 v-model 上抛父 config', async () => {
    const { w, config } = mountWithParent(makeConfig())
    expect(w.text()).toContain('用户认证')
    const card = w.findComponent(UsersCard)
    expect(card.exists()).toBe(true)
    card.vm.$emit('update:modelValue', {
      qa1: { url: 'https://x', username: 'u', password: 'p', token_type: 'Bearer', expires_in: 3600 },
    })
    await flush()
    expect(config.value.users.qa1?.username).toBe('u')
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test -- src/components/composer/__tests__/UsersCard.test.ts src/components/composer/__tests__/CaseComposerConfig.test.ts
```
预期:FAIL — 找不到 `@/components/composer/UsersCard.vue`。

- [ ] **Step 3: 实现 UsersCard.vue**

新建 `src/gimbal-platform/frontend/src/components/composer/UsersCard.vue`:

```vue
<!--
  UsersCard.vue — ③ 配置页第 7 张卡:用户认证 (config.users)
  手动配置(字段对齐认证管理)或从凭证池导入快照;
  快照随场景导出,执行期由 Config.users 解析 ${auth.<alias>.*}。
  样式走 composer.css 共享层(.c-card/.c-card-head/.c-empty/.c-add)。
-->
<template>
  <div class="c-card users-card">
    <div class="c-card-head">
      <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      <div>
        <h3>用户认证 (users)</h3>
        <p class="c-head-desc">
          此处用户信息将随场景导出,并可在步骤 header 中以
          <code class="c-code">${auth.&lt;alias&gt;.*}</code> 引用(内网测试环境,密码明文保存)
        </p>
      </div>
    </div>

    <div v-if="!rows.length" class="c-empty">
      <p>还没有用户认证 — 手动添加或从凭证池导入</p>
    </div>
    <el-table v-else :data="rows" size="small" class="users-table">
      <el-table-column label="alias" min-width="110">
        <template #default="{ row }">
          <code class="alias">{{ row.alias }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="user.url" label="url" min-width="180" show-overflow-tooltip />
      <el-table-column prop="user.username" label="username" min-width="110" />
      <el-table-column label="password" min-width="120">
        <template #default="{ row }">
          <code class="pw">{{ row.user.password ?? '—' }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="user.token_type" label="token_type" width="100" />
      <el-table-column label="expires_in" width="90">
        <template #default="{ row }">{{ fmtExpires(row.user.expires_in) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" align="center">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row.alias)">编辑</el-button>
          <el-button link type="danger" size="small" @click="removeUser(row.alias)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="users-actions">
      <button type="button" class="c-add" @click="openCreate">+ 添加用户</button>
      <button type="button" class="c-add" @click="openImport">从凭证池导入</button>
    </div>

    <!-- ── 手动新增 / 编辑(字段与认证管理一致;差异:password 明文)── -->
    <el-dialog
      v-model="formOpen"
      :title="editingAlias ? '编辑用户' : '+ 添加用户'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" @submit.prevent>
        <el-form-item label="alias" prop="alias" required>
          <el-input v-model="form.alias" :disabled="!!editingAlias"
            placeholder="例 qa1 / staging-codfish（users 的 key，${auth.<alias>.*} 引用它）" />
        </el-form-item>
        <el-form-item label="登录 URL" prop="url" required>
          <el-input v-model="form.url" placeholder="https://target/auth/login" />
        </el-form-item>
        <el-form-item label="username" prop="username" required>
          <el-input v-model="form.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="password" prop="password" required>
          <el-input v-model="form.password" type="text"
            placeholder="登录密码（内网测试环境，明文保存于场景）" />
        </el-form-item>
        <el-form-item label="token_type">
          <el-select v-model="form.token_type" style="width:100%">
            <el-option label="Bearer" value="Bearer" />
            <el-option label="Basic" value="Basic" />
            <el-option label="Cookie" value="Cookie" />
            <el-option label="Authorization（整段头）" value="Authorization" />
          </el-select>
        </el-form-item>
        <el-form-item label="expires_in（秒）">
          <el-input-number v-model="form.expires_in" :min="0" :max="86400" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formOpen = false">取消</el-button>
        <el-button type="primary" @click="submitForm">{{ editingAlias ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>

    <!-- ── 凭证池导入(快照拷贝:导入的是当前值副本,池后续修改不影响)── -->
    <el-dialog v-model="importOpen" title="从凭证池导入" width="640px">
      <p class="import-hint">
        选择要快照到本场景的凭证 — 导入后与凭证池解耦;凭证池更新不会同步,如需刷新请删除该行后重新导入。
      </p>
      <div v-loading="poolLoading" class="pool-list">
        <div
          v-for="row in pool"
          :key="row.id"
          class="pool-item"
          :class="{ disabled: isTaken(row.alias), selected: isSelected(row.id) }"
          :title="isTaken(row.alias) ? '场景中已存在，如需刷新请先删除该行' : undefined"
          @click="toggleSel(row)"
        >
          <code class="alias">{{ row.alias }}</code>
          <span class="pool-user">{{ row.username }}</span>
          <span class="pool-url">{{ row.url }}</span>
          <span v-if="isTaken(row.alias)" class="taken">已存在</span>
        </div>
        <p v-if="!poolLoading && !pool.length" class="c-empty">凭证池为空 — 先到「认证管理」添加</p>
      </div>
      <template #footer>
        <el-button @click="importOpen = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedIds.length" :loading="importing" @click="submitImport">
          导入{{ selectedIds.length ? ` (${selectedIds.length})` : '' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { list as listAuths, get as getAuth } from '@/api/auth_sessions'
import type { AuthSession } from '@/api/auth_sessions'
import type { UserAuthView } from '@/types/plate'

const props = defineProps<{ modelValue: Record<string, UserAuthView> }>()
const emit = defineEmits<{ 'update:modelValue': [Record<string, UserAuthView>] }>()

/** 整体替换式 emit — 与 CaseComposerConfig 的 local.users v-model 管道一致 */
function setUsers(next: Record<string, UserAuthView>) {
  emit('update:modelValue', next)
}

const rows = computed(() =>
  Object.entries(props.modelValue || {}).map(([alias, user]) => ({ alias, user })),
)

function removeUser(alias: string) {
  const next = { ...props.modelValue }
  delete next[alias]
  setUsers(next)
}

function fmtExpires(s?: number): string {
  if (s === undefined || s === null) return '—'
  if (s >= 3600) return `${Math.round(s / 3600)}h`
  if (s >= 60) return `${Math.round(s / 60)}m`
  return `${s}s`
}

// ── 手动表单(字段/校验对齐 Auths.vue;差异:password 明文输入框)──
const formOpen = ref(false)
const editingAlias = ref<string | null>(null)
const formRef = ref<FormInstance | null>(null)
const form = reactive({
  alias: '', url: '', username: '', password: '',
  token_type: 'Bearer', expires_in: 7200,
})

const formRules = {
  alias: [
    { required: true, message: '请输入 alias', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_-]{1,64}$/, message: '1-64 位字母数字下划线连字符', trigger: 'blur' },
  ],
  url: [{ required: true, message: '请输入登录 URL', trigger: 'blur' }],
  username: [{ required: true, message: '请输入 username', trigger: 'blur' }],
  password: [{ required: true, message: '请输入 password', trigger: 'blur' }],
}

function openCreate() {
  editingAlias.value = null
  Object.assign(form, {
    alias: '', url: '', username: '', password: '',
    token_type: 'Bearer', expires_in: 7200,
  })
  formOpen.value = true
}

function openEdit(alias: string) {
  const u = props.modelValue[alias] || {}
  editingAlias.value = alias
  Object.assign(form, {
    alias,
    url: u.url ?? '',
    username: u.username ?? '',
    password: u.password ?? '',
    token_type: u.token_type ?? 'Bearer',
    expires_in: u.expires_in ?? 7200,
  })
  formOpen.value = true
}

async function submitForm() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (!editingAlias.value && form.alias in (props.modelValue || {})) {
    ElMessage.warning(`alias ${form.alias} 已存在 — 不做覆盖,如需刷新请先删除该行`)
    return
  }
  setUsers({
    ...props.modelValue,
    [form.alias]: {
      url: form.url,
      username: form.username,
      password: form.password,
      token_type: form.token_type,
      expires_in: form.expires_in,
    },
  })
  formOpen.value = false
}

// ── 凭证池导入(快照拷贝;单条 422 → 提示并跳过,其余继续)──
const importOpen = ref(false)
const poolLoading = ref(false)
const importing = ref(false)
const pool = ref<AuthSession[]>([])
const selectedIds = ref<number[]>([])

function isTaken(alias: string): boolean {
  return alias in (props.modelValue || {})
}
function isSelected(id: number): boolean {
  return selectedIds.value.includes(id)
}
function toggleSel(row: AuthSession) {
  if (isTaken(row.alias)) return
  selectedIds.value = isSelected(row.id)
    ? selectedIds.value.filter((i) => i !== row.id)
    : [...selectedIds.value, row.id]
}

async function openImport() {
  importOpen.value = true
  poolLoading.value = true
  selectedIds.value = []
  try {
    pool.value = await listAuths()
  } catch (e) {
    ElMessage.error(`凭证池加载失败：${(e as Error).message}`)
    importOpen.value = false
  } finally {
    poolLoading.value = false
  }
}

async function submitImport() {
  importing.value = true
  let imported = 0
  const next = { ...props.modelValue }
  for (const row of pool.value.filter((p) => isSelected(p.id))) {
    try {
      const detail = (await getAuth(row.id, true)) as {
        url: string; username: string; password: string
        token_type: string; expires_in: number
      }
      next[row.alias] = {
        url: detail.url,
        username: detail.username,
        password: detail.password,
        token_type: detail.token_type,
        expires_in: detail.expires_in,
      }
      imported++
    } catch (e) {
      ElMessage.warning(`${row.alias} 导入失败：${(e as Error).message}（已跳过）`)
    }
  }
  importing.value = false
  if (imported > 0) {
    setUsers(next)
    ElMessage.success(`已导入 ${imported} 条用户快照`)
  }
  importOpen.value = false
}
</script>

<style scoped>
.users-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.users-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--c-accent-soft, #f1f5f9);
}

.alias {
  padding: 2px 6px;
  color: var(--c-accent, #4338ca);
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  background: var(--c-accent-soft, #eef2ff);
  border-radius: 4px;
}

.pw {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.import-hint {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--c-text-secondary, #64748b);
}

.pool-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}

.pool-item {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  cursor: pointer;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  transition: all 0.15s;
}

.pool-item:hover:not(.disabled) {
  border-color: var(--c-accent, #4338ca);
}

.pool-item.selected {
  border-color: var(--c-accent, #4338ca);
  background: var(--c-accent-soft, #eef2ff);
}

.pool-item.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.pool-user {
  min-width: 90px;
  font-size: 12px;
}

.pool-url {
  flex: 1;
  overflow: hidden;
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.taken {
  flex-shrink: 0;
  padding: 1px 8px;
  font-size: 10.5px;
  color: #854d0e;
  background: #fef9c3;
  border-radius: 4px;
}
</style>
```

- [ ] **Step 4: 挂载进 CaseComposerConfig.vue**

1. 模板:services 卡(`+ 添加服务` 按钮所在 `</div>` 之后、导出注释 `<!--` 之前)插入:

```html
    <!-- 用户认证(2026-08-25):场景级 users 快照 — 手动配置或凭证池导入 -->
    <UsersCard v-model="local.users" />
```

2. script import 区(`import { parseJson } …` 之后)加:

```ts
import UsersCard from './UsersCard.vue'
```

3. 头注释第 3 行 `6 个子区块:` 改为 `7 个子区块:`,并在列表尾加 ` / 用户认证`。
4. scoped style 里 `.vars-card, .svc-card { grid-column: 1 / -1; }` 一行改为:

```css
.vars-card, .svc-card, .users-card { grid-column: 1 / -1; }
```

- [ ] **Step 5: 运行确认通过**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test -- src/components/composer/__tests__/UsersCard.test.ts src/components/composer/__tests__/CaseComposerConfig.test.ts && npm run typecheck
```
预期:全 PASS,typecheck 无错误。

- [ ] **Step 6: 提交**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/components/composer/UsersCard.vue src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue src/gimbal-platform/frontend/src/components/composer/__tests__/UsersCard.test.ts src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerConfig.test.ts && git commit -m "feat(frontend): 配置页用户认证卡 — 手动配置/凭证池快照导入,明文随导出

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 前端 — 画布 auth 引用徽章 union 修正

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue:735-736`(authAliases computed)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`(末尾追加 describe)

**Interfaces:**
- Consumes: `draftStore`(同文件 631 行已定义)、`auths`(553 行)。
- Produces: `authAliases` 语义变更 = 凭证池 alias ∪ `draftStore.draft.definition.config.users` keys(类型不变 `ComputedRef<string[]>`)。

- [ ] **Step 1: 写失败测试**

`CaseComposerCanvas.test.ts` 末尾追加(该文件已有 `mkStep`/`mountCanvas`/`flushPromises`/`useScenarioDraftStore` 等,直接使用):

```ts
describe('CaseComposerCanvas — auth 引用徽章 union(2026-08-25)', () => {
  it('引用场景本地用户(仅 config.users 有)不标悬空', async () => {
    const draft = useScenarioDraftStore()
    ;(draft.draft as any).definition.config.users = {
      'local-user-1': { url: 'https://x', username: 'u', password: 'p', token_type: 'Bearer', expires_in: 3600 },
    }
    const s0 = mkStep({
      api: {
        kind: 'api', service: 'fin', method: 'POST', path: '/order',
        headers: { Authorization: '${auth.local-user-1.token}' },
        view_hints: { endpoint_id: 'ep-1' },
      },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const chips = w.findAll('.ref-chip')
    expect(chips.length).toBeGreaterThan(0)
    expect(chips[0].classes()).not.toContain('dangling')
    w.unmount()
  })

  it('引用两边都没有的 alias 仍标悬空', async () => {
    const s0 = mkStep({
      api: {
        kind: 'api', service: 'fin', method: 'POST', path: '/order',
        headers: { Authorization: '${auth.ghost.token}' },
        view_hints: { endpoint_id: 'ep-1' },
      },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const chip = w.findAll('.ref-chip').find((c) => c.text().includes('ghost'))
    expect(chip).toBeTruthy()
    expect(chip!.classes()).toContain('dangling')
    w.unmount()
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test -- src/components/composer/__tests__/CaseComposerCanvas.test.ts
```
预期:第一个用例 FAIL(徽章 dangling — 只查凭证池);第二个 PASS。

- [ ] **Step 3: 实现 union**

`CaseComposerCanvas.vue` 735-736 行:

```ts
/** 模板里 refStatus 的第二参:已知 alias 列表 */
const authAliases = computed(() => auths.value.map((a) => a.alias))
```

改为:

```ts
/** 模板里 refStatus 的第二参:已知 alias 集合 = 凭证池 ∪ 草稿 config.users
 *  (③ 用户认证快照 — 场景本地用户执行期由 Config.users 解析,不能误标悬空) */
const authAliases = computed(() => {
  const localUsers = Object.keys(draftStore.draft?.definition?.config?.users ?? {})
  return [...new Set([...auths.value.map((a) => a.alias), ...localUsers])]
})
```

- [ ] **Step 4: 运行确认通过**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test -- src/components/composer/__tests__/CaseComposerCanvas.test.ts
```
预期:全 PASS(含既有用例无回归)。

- [ ] **Step 5: 提交**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts && git commit -m "fix(frontend): auth 引用徽章悬空判定 union 凭证池与场景 config.users

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 前端 — 认证管理页(按钮同行 + 测试弹框状态机)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/Auths.vue:68`(操作列宽)、`136-161`(测试弹框)、`330-346`(runTest)、style(追加弹框样式)
- Test: Create `src/gimbal-platform/frontend/src/views/__tests__/Auths.test.ts`

**Interfaces:**
- Consumes: 现有 store `testConnection`。
- Produces: 无对外接口变化(纯 UI);弹框状态机 `testPhase: 'testing' | 'success' | 'fail'`。

- [ ] **Step 1: 写失败测试**

新建 `src/gimbal-platform/frontend/src/views/__tests__/Auths.test.ts`:

```ts
/**
 * Auths.vue — 测试弹框状态流(2026-08-25 认证改造)。
 *
 * 锁死:开弹框即"认证中"(修复历史 bug — 标题三元把 null 折叠成
 * "连通失败",在途假失败);返回后切 认证成功/认证失败 终态;
 * 失败详情默认展开。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import Auths from '@/views/Auths.vue'
import * as api from '@/api/auth_sessions'
import type { AuthSession } from '@/api/auth_sessions'

const sample: AuthSession = {
  id: 1, alias: 'qa1', url: 'https://x/auth', username: 'u',
  token_type: 'Bearer', expires_in: 3600,
  created_at: '', updated_at: '', password_masked: '<REDACTED>',
}

function mountPage() {
  return mount(Auths, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(api, 'list').mockResolvedValue([sample])
})

describe('Auths — 测试弹框状态流', () => {
  it('认证中 → 认证成功(在途不出现"连通失败"/"认证失败")', async () => {
    let resolve!: (v: { ok: boolean; status_code: number | null; message: string }) => void
    vi.spyOn(api, 'testConnection').mockImplementation(
      () => new Promise((r) => { resolve = r }),
    )
    const w = mountPage()
    await flushPromises()
    await w.findAll('button').filter((b) => b.text() === '测试')[0].trigger('click')

    expect(document.body.textContent).toContain('认证中')
    expect(document.body.textContent).not.toContain('连通失败')
    expect(document.body.textContent).not.toContain('认证失败')

    resolve({ ok: true, status_code: 200, message: '连通成功,已提取 token(前 12 字符:abc…)' })
    await flushPromises()
    expect(document.body.textContent).toContain('认证成功')
    expect(document.body.textContent).toContain('HTTP 200')
    w.unmount()
  })

  it('认证中 → 认证失败 + 详情默认展开', async () => {
    vi.spyOn(api, 'testConnection').mockResolvedValue({
      ok: false, status_code: null, message: '网络/认证错误: HTTPStatusError: 401',
    })
    const w = mountPage()
    await flushPromises()
    await w.findAll('button').filter((b) => b.text() === '测试')[0].trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('认证失败')
    expect(document.body.textContent).toContain('网络/认证错误: HTTPStatusError: 401')
    w.unmount()
  })

  it('请求异常 → 认证失败终态(不悬挂在认证中)', async () => {
    vi.spyOn(api, 'testConnection').mockRejectedValue(new Error('Network Error'))
    const w = mountPage()
    await flushPromises()
    await w.findAll('button').filter((b) => b.text() === '测试')[0].trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('认证失败')
    expect(document.body.textContent).toContain('Network Error')
    w.unmount()
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test -- src/views/__tests__/Auths.test.ts
```
预期:FAIL — 现弹框在途标题"连通失败"、无"认证中"字样。

- [ ] **Step 3: 实现 Auths.vue 三处修改**

1. **操作列同行**(68 行):`width="140"` → `width="200"`。

2. **测试弹框重建**(136-161 行整块替换):

```html
    <!-- ── Test result dialog(状态主视觉式)────────────── -->
    <el-dialog v-model="testOpen" title="认证测试" width="460px">
      <div v-if="testTarget" class="test-hero">
        <div class="test-sub">{{ testTarget.alias }} · {{ testTarget.url }}</div>

        <div v-if="testPhase === 'testing'" class="test-state testing">
          <span class="test-icon spinner" />
          <span class="test-word">认证中…</span>
        </div>

        <template v-else-if="testResult">
          <div class="test-state" :class="testPhase">
            <span class="test-icon">{{ testPhase === 'success' ? '✓' : '✗' }}</span>
            <span class="test-word">{{ testPhase === 'success' ? '认证成功' : '认证失败' }}</span>
            <span v-if="testResult.status_code != null" class="test-code">
              HTTP {{ testResult.status_code }}
            </span>
          </div>
          <button class="detail-toggle" @click="testDetailOpen = !testDetailOpen">
            {{ testDetailOpen ? '▾' : '▸' }} 详情
          </button>
          <code v-if="testDetailOpen" class="mono detail">{{ testResult.message }}</code>
        </template>
      </div>
      <template #footer>
        <el-button v-if="testPhase !== 'testing' && testTarget" @click="runTest(testTarget)">
          重新测试
        </el-button>
        <el-button type="primary" @click="testOpen = false">关闭</el-button>
      </template>
    </el-dialog>
```

3. **runTest 状态机**(330-346 行的 `// ── test ──` 区块替换):

```ts
// ── test ───────────────────────────────────────────────────────
// 状态机:开弹框即 testing(修复历史 bug — 标题三元把 null 折叠成
// "连通失败",在途假失败);返回/异常切终态。失败详情默认展开。
const testOpen = ref(false)
const testPhase = ref<'testing' | 'success' | 'fail'>('testing')
const testResult = ref<TestResult | null>(null)
const testTarget = ref<AuthSession | null>(null)
const testDetailOpen = ref(true)

async function runTest(row: AuthSession) {
  testTarget.value = row
  testResult.value = null
  testPhase.value = 'testing'
  testDetailOpen.value = true
  testOpen.value = true
  try {
    testResult.value = await store.testConnection(row.id)
    testPhase.value = testResult.value.ok ? 'success' : 'fail'
    // 成功默认收起(信息就一行 token 预览);失败保持展开直接看到原因
    if (testPhase.value === 'success') testDetailOpen.value = false
  } catch (e) {
    testResult.value = {
      ok: false,
      status_code: null,
      message: (e as Error).message || '请求失败',
    }
    testPhase.value = 'fail'
  }
}
```

4. **样式**(`<style scoped>` 的 `.text-ok/.text-fail` 两行替换为):

```css
/* 测试弹框 — 状态主视觉式 */
.test-hero { text-align: center; }

.test-sub {
  margin-bottom: 18px;
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.test-state {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  margin: 6px 0 14px;
}

.test-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  font-size: 20px;
  font-weight: 700;
  border-radius: 50%;
}

.testing .test-icon {
  border: 3px solid #e2e8f0;
  border-top-color: #6366f1;
  animation: test-spin 0.9s linear infinite;
}

.success .test-icon { color: #166534; background: #dcfce7; }
.fail .test-icon { color: #991b1b; background: #fef2f2; }

.test-word { font-size: 16px; font-weight: 600; }
.testing .test-word { color: var(--color-text-secondary); }
.success .test-word { color: #166534; }
.fail .test-word { color: #991b1b; }

.test-code {
  padding: 2px 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  background: #f1f5f9;
  border-radius: 4px;
}

.detail-toggle {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 12px;
}

@keyframes test-spin { to { transform: rotate(360deg); } }
```

(`.detail` 样式 513-520 行保留复用。)

- [ ] **Step 4: 运行确认通过**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test -- src/views/__tests__/Auths.test.ts && npm run typecheck
```
预期:3 用例全 PASS,typecheck 无错误。

- [ ] **Step 5: 提交**

```bash
cd d:/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/views/Auths.vue src/gimbal-platform/frontend/src/views/__tests__/Auths.test.ts && git commit -m "feat(frontend): 认证管理页 — 操作列同行 + 测试弹框状态机(认证中→成功/失败)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: 收尾验证(spec §测试策略 完成标准)

**Files:** 无新改动(只读验证;若失败回对应 Task 修)。

- [ ] **Step 1: 后端全套**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/ -q
```
预期:全绿。

- [ ] **Step 2: 前端全套 + 类型检查**

```bash
cd d:/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run test && npm run typecheck
```
预期:全绿、无类型错误。

- [ ] **Step 3: 手工冒烟(可选但建议)**

启动前后端(`npm run dev` + 后端 uvicorn),验证:配置页 ③ 出现"用户认证"卡、凭证池导入落快照、导出 JSON 含 `config.users` 明文;认证管理页三按钮一行、测试弹框 认证中→终态、重新测试按钮;画布引用场景本地用户无悬空徽章。

- [ ] **Step 4: 汇报**

无新提交(验证任务);如发现回归,回到对应 Task 修复并追加 fix 提交。
