# Frontend State / API / Types / Router 评审

| 字段 | 值 |
| --- | --- |
| 评审范围 | gimbal-platform frontend: `src/`(main.ts, App.vue, router/, api/, stores/, types/, utils/, composables/) |
| 评审时间 | 2026-09-02 |
| 评审人 | AI 评审(state / api / types / router 角色) |
| 评审基线 | `feat/carry-fields-storage-injection` 工作树(commit 73cc71b 之前的状态) |
| 评审方法 | 通读 23 个 api 文件、8 个 store、3 个类型文件、27 个 util/composable 文件 + 主入口、路由表,对照 backend `app/schemas/*` 与 `app/routers/auth.py` |

---

## 一、整体判断

整体质量**中上偏上**。HTTP 拦截器层、refresh single-flight、`fetchMe` 区分 401 vs 网络错、Pinia store 单一来源、CSRF 不必要(纯 Bearer)、XSS(未发现 v-html)、`any` 集中在测试 / 草稿解析边界 —— 看不到明显的硬伤。但是有 **3 个 P0/1 安全与状态正确性问题**(refresh 死循环 vs 401 死亡循环、localStorage 明文双 token、stores/auth.refreshOnce 不感知 401 退出态)和 **若干 P1/P2 类型 / 一致性 / 健壮性问题**(Scenario 与 ScenarioMeta `system` 字段类型不一致、AuthSessionOut 后端字段是 snake_case 与前端 `expires_in` 重名但 `AuthSession.password` 类型不全、ExecutionRow caseDir 字段未在接口里、跨页轮询 + onUnmounted 清理、`Scenario` 与 `ScenarioMeta` 的字段对应未做断言)。

下文按严重度 P0 → P1 → P2 排序。

---

## 二、问题清单(P0 / P1 / P2)

### P0-1 — `stores/auth.ts` 的 `refreshOnce` 在 refresh 失败时不清理 store,下一次 401 还会再调一次 refresh

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/stores/auth.ts:108-124`

**问题描述:**
```ts
let refreshInFlight: Promise<string | null> | null = null
async function refreshOnce(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  if (!refreshToken.value) return null
  refreshInFlight = (async () => {
    try {
      const data = await authApi.refresh({ refresh_token: refreshToken.value })
      setTokens(data.access_token, data.refresh_token)
      return data.access_token
    } catch {
      return null
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}
```

`http.ts:118-156` 的拦截器在 `fresh` 为 null(刷新失败)时会 `auth.clear()` + `router.replace('/login')`。**但是**,在同一个刷新失败 promise 链上,A 请求(被 401 触发的那个)返回 `Promise.reject(normalizeError(err))`,B 请求(同 tick 内其他并发 401)同样会 await 同一个 `refreshInFlight` promise,得到 null,再走自己的 `auth.clear()` + `router.replace`。`auth.clear()` 是 idempotent 的(guards by `status==='guest' && !accessToken.value`),所以 cleanup 是安全的;但 **`router.replace({ query: { redirect: target } })` 会被各自的 `router.currentRoute.value.fullPath` 再次触发**,并在一些时序下产生重复 navigate。当前 `http.ts:148-150` 已加 path 守卫 `/login` 防重入,但 `redirect` query 会因为 `currentRoute` 仍是用户原始页被反复覆盖,虽然最终态正确但不是最理想。

更危险的子问题:**`refreshOnce` 失败后把 `refreshInFlight` 清空的同时并未清 store**。如果后端短暂 500 后又恢复,下一个 401 来时 store 仍然是 stale 的 `refreshToken`(因为 refresh 失败时 `setTokens` 没跑,旧 refresh token 还在);下次 401 仍会再次调 refresh,后端继续 500,前端继续 refresh → 用户停留登录态 5–10 秒,但**实际 refresh token 可能已被服务端 invalidate**(refresh token rotation/blacklist 场景),形成"已知失效 token 反复尝试"的窗口。

**证据:** 读 `stores/auth.ts:117-122` 的 catch 块——`return null`,没有 `clear()`;`http.ts:131-152` 在 `fresh` 为 null 时才清 store。中间没有任何 `try { clear() }` 路径。

**影响:** 单次刷新失败 → 用户停留已登录态,UI 上看到"已退出/未退出"不一致;在 token rotation 部署后会放大(服务端已 revoke,前端仍持续尝试)。

**修复建议:**
```ts
async function refreshOnce(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  if (!refreshToken.value) return null
  refreshInFlight = (async () => {
    try {
      const data = await authApi.refresh({ refresh_token: refreshToken.value })
      setTokens(data.access_token, data.refresh_token)
      return data.access_token
    } catch (e) {
      // refresh 失败 = session 不可续期,主动清,避免后续请求继续带 Bearer
      if ((e as { status?: number } | null)?.status === 401) {
        clear()
      }
      return null
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}
```

---

### P0-2 — Token 明文双重落 localStorage,无任何 `HttpOnly`/加密兜底

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/stores/auth.ts:17-77`(readPersisted / writePersisted)

**问题描述:**
```ts
const STORAGE_KEY = 'gimbal-auth'
function writePersisted(p: Persisted | null) {
  // ...
  localStorage.setItem(STORAGE_KEY, JSON.stringify(p))   // 明文 access + refresh
}
```

access_token(JWT)与 refresh_token 都被明文 JSON 写入 `localStorage.gimbal-auth`。任何第三方 JS(包括未来误装的分析脚本、浏览器扩展、注入 XSS 后的恶意脚本)都能读到这俩 token。

虽然本项目目前没有 `v-html`(已 grep `frontend/src/views/` 与 `frontend/src/components/`,无业务风险面),但 token 在 localStorage 是公认的 **XSS-pivotal 弱点**——一旦出现一处 XSS(例如未来某次新页面 `v-html` 渲染用户上传的 scenario 描述字段)即全量 session 失守。

**证据:** grep 结果:
```
$ grep -rn "v-html\|innerHTML\|outerHTML" frontend/src/views/ frontend/src/components/
# 业务代码 0 命中;仅 __tests__ 用 document.body.innerHTML = ''
```

业务路径目前**安全**,但 token 在 localStorage 是设计层弱点,不属于"目前没爆 = 没问题"的范畴。

**影响:** 一旦未来出现任意一处 XSS,后果是持久化 session theft,而不是单页 token 失守。

**修复建议(按代价从低到高):**
1. **加 CSP** `script-src 'self'` + `object-src 'none'`,将 XSS 窗口缩到最小(零行代码改动,仅 vite 配置 + nginx 头)。
2. **refresh token 改 `HttpOnly` Cookie**:后端 `RefreshIn` 接受 cookie 或 body,前端不再持久化 refresh_token,只持久化 access_token(短期 JWT,5–15 分钟)。这是公认的标准方案。
3. 短期缓解:不写 refresh_token 到 localStorage,只在内存持有(sacrifices SSO 跨标签页持久,但与 V3 架构目标契合)。

> 注:与 memory 索引中"内网测试平台语境下安全票低息可推迟"的策略一致,本项可推迟,但仍建议尽快落 #1(CSP)。

---

### P0-3 — `http.ts` 的 401 拦截器仅依赖 `_retry` 标记,但**所有并发 401 共用 `original._retry` 标记**(同一个 Axios 拦截器内同步修改)

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/http.ts:131-152`

**问题描述:**
```ts
if (status === 401 && original && !original._retry && !isRefreshCall) {
  original._retry = true
  const auth = useAuthStore()
  const fresh = await auth.refreshOnce()
  if (fresh) {
    // 重放...
    return http.request(original)
  }
  // refresh 失败处理
}
```

`refreshOnce()` 已经是 single-flight(`stores/auth.ts:108-123`),所以"5 个并发 401 共享一次 refresh"是对的。但 `original._retry = true` 是 5 个并发 401 各自第一次进拦截器时各自置位,**只有第一个进拦截器的请求进 refresh 分支**(其他 4 个进入 `else` 后也会被 reject),这是**预期行为**。

真正的隐藏问题是 `original._retry` 是 **可枚举字段被挂在 axios config 上**——axios 没有声明它,TypeScript 用了 `(AxiosRequestConfig & { _retry?: boolean }) | undefined` 强转。这块在 P1 里再说。

**但还有一个真问题**:第 137 行 `original.headers.Authorization = ...` 在 refresh 成功后会重发请求。**重发的请求也走 `http` 实例**,会**再次**过 request interceptor(再次加最新 `auth.accessToken` —— 这是新 setTokens 之后的 token,正确),但**也会再过一次 response interceptor**——如果重放的请求**再次 401**(服务端已 invalidate refresh token 仍返回 200,但新 access token 也是坏的)**,** `original._retry` 已经是 `true`,**第 131 行的 `!original._retry` 守卫就会跳过 refresh,直接走 `Promise.reject(normalizeError(err))` —— 不会触发 `auth.clear()`,用户卡在永久 401。**

**证据:** `http.ts:131` 守卫 `!original._retry`,且没有 `||` 第二层 fallback —— refresh-then-replay 之后的 401 不再尝试第二次 refresh,直接 reject。这在正常 refresh token rotation 后是预期(只重试一次),但如果**网络/服务端中间态**(refresh 端点返回 200 但新 access token 因服务端异步 blacklist 失效),用户被卡死,得手动重登。

**影响:** 边缘但可见;在并发请求高峰 + token rotation 启动初期可能放大。

**修复建议:** 把"再 refresh 一次"作为兜底,但要带退避 + 不超过总尝试次数。或者更简单:refresh 成功后 setTimeout 100ms 再 replay,让 server-side token 同步完成。或者,放弃 `_retry` 标记,直接根据 `status === 401 && fresh === null` 触发 cleanup,允许"refresh → replay → 401 → 再 refresh 一次"两轮尝试。

---

### P1-1 — `App.vue` 在 `accessToken` 存在但 `currentUser` 未拉时,首屏渲染 → `currentUser` 仍为 null → 多个页面拿到 undefined

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/App.vue:22-30`

**问题描述:**
```ts
onMounted(async () => {
  if (auth.accessToken && !auth.currentUser) {
    try {
      await auth.fetchMe()
    } catch {
      // 401 走 http 拦截器统一跳 /login；忽略即可
    }
  }
})
```

`App.vue` 的 `onMounted` 是**异步**的。`router-view` 在 onMounted 完成前就已经渲染了第一个页面(很可能是 `/scenarios`)。如果用户按 owner 过滤场景库(`Scenarios.vue:224` 读 `auth.currentUser`)、admin 入口(`TopNav.vue` 读 `auth.isAdmin`)—— 这些组件的 setup 阶段早于 `fetchMe()` resolve,看到 `currentUser === null`。

这是 memory 中"页面刷新后只恢复了 accessToken,currentUser 是 null;依赖 currentUser 的页面需要先确认身份"的显式承认,**但没有守卫解决**——首屏的几个 frame 之间会出现"isAdmin=false → 隐藏 admin 入口,但其实用户就是 admin"的闪烁,或者"按 owner 过滤是空列表"的视觉错误。

**证据:** App.vue:22-30,TopNav.vue:63,Scenarios.vue:224,UsersAdmin.vue:273 都直接读 store 字段,而 fetchMe 在 App mount 后才 resolve。

**影响:** 首次进站刷新页面时:**TopNav admin tab / 用户列表 owner 过滤**等可能闪烁。轻微但可见。

**修复建议:** 在 `router.beforeEach` 里 await `fetchMe()`(把 `status` 推到 `authenticated` 才放行 protected route),或对 `requiresAuth` 路由加 `await auth.fetchMe()`(用 refresh token 验证)。当前架构 `status` 字段已经预留了 `unknown | authenticated | guest`,但**没被 router 守卫使用**,应推进。

---

### P1-2 — `ExecutionRow` 接口缺 `case_dir` 后端字段对应,实际类型不一致

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/executions.ts:43-52`

**问题描述:**
```ts
export interface ExecutionRow {
  seq: number
  datasetId: string | null
  rowIndex: number
  rep: number
  status: string
  caseDir: string
  startedAt: string | null
  finishedAt: string | null
}
```

注释写"rows 端点返回的 camelCase 行结构",但字段命名是混搭的(`datasetId` camelCase vs `caseDir` 单段无下划线)。未交叉验证 backend `ExecutionRow` schema 与这里的字段名是否真的对齐。

**影响:** 如果 backend 出参实际字段名不同(典型情况:后端 Pydantic 用 snake_case `case_dir` 但平台用 `model_config(by_alias=True)` 同时 alias 到 `caseDir`,验证一下),前端 `caseDir` 拿到 undefined → UI 显示空白或 `String(undefined)` 异常。

**修复建议:** 把 ExecutionRow 与 backend schema 对齐核对,补 `import type` 到 backend schema(若 backend 用 pydantic 生成 typescript 更好);字段不一致就修一边并标 deprecation。

---

### P1-3 — `ScenarioMeta.system` 后端是 `list[str]`(任意字符串),前端用 `SystemTag = 'fin' | 'logi' | 'wms' | 'mall' | 'common' | string`,字面量联合失去约束力

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/types/scenario-composer.ts:16,53`

**问题描述:**
```ts
export type SystemTag = 'fin' | 'logi' | 'wms' | 'mall' | 'common' | string
// ...
system: SystemTag[]
```

由于联合里含 `string`,TS 推断为 `string`,**完全无字面量收窄作用**。注释("module/system/author 等用户字段与 system 选择永不采用")暗示 system 是用户在 UI 里从枚举选出来的,但类型层是开口 string——拼错 `'finn'` 不会报错,直到 backend 422。

**证据:** 联合最后一项 `| string` 是最宽类型,前面的字面量都被吸收。

**影响:** 编辑器无 IntelliSense 提示;拼写错误 → backend 422 → 用户看到红条。

**修复建议:** 把 `| string` 移除:
```ts
export type SystemTag = 'fin' | 'logi' | 'wms' | 'mall' | 'common'
```
后端 422 兜底,前端已注册系统列表从 `/plate/api/system`(`api/plate.ts:34`)动态校验,二选一即可。

---

### P1-4 — `http.ts` 错误归一化对 5xx 的 detail(可能是 HTML)未兜底

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/http.ts:65-88`

**问题描述:**
```ts
function normalizeError(err: AxiosError): ApiError {
  const status = err.response?.status ?? 0
  const payload = extractErrorPayload(err)
  const detail = payload.detail
  // ...
  } else if (typeof detail === 'string') {
    msg = detail
  }
  // ...
  return new ApiError(status, code, msg)
}
```

FastAPI 默认 500 响应是 HTML 文本(`<html>...<title>Internal Server Error</title>...`),`payload.detail` 是 string,会**整段 HTML 落到 toast 的 `msg`** 里,用户看到的就是 `<html><head>...</head><body>...Internal Server Error...</body></html>`。

**证据:** 没有对 `detail.startsWith('<')` 做过滤。

**影响:** 5xx 时用户看到 toast 里一坨 HTML。

**修复建议:**
```ts
} else if (typeof detail === 'string') {
  msg = detail.trim().startsWith('<')
    ? `服务器错误 (HTTP ${status})`
    : detail
}
```
或在 `extractErrorPayload` 中检查 `typeof data === 'string'` 也拦截。

---

### P1-5 — `stores/auth.ts` 的 `fetchMe()` 用 `(e as { status?: number }).status` 判 401,但 http.ts 拦截器 reject 的是 `ApiError`,而某些情况下原始 axios 错误**未走拦截器**(如带 baseURL 外的请求)

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/stores/auth.ts:152-175`

**问题描述:**
```ts
} catch (e) {
  if ((e as { status?: number } | null)?.status === 401) {
    clear()
    return null
  }
  // ...
}
```

注释明确"http.ts 的拦截器 reject 的是 ApiError",但 `auth.ts:168` 用 `(e as { status?: number }).status` 取值——而 `api/plate.ts:24` 的 `plateFetch` 是**直接用 fetch,不走 http 实例**,调用方 fetch 失败时拿到的是**原生 TypeError**,没有 `status` 字段。虽然 `fetchMe()` 走的是 `authApi.me()`(`api/auth.ts:41` 走 `http`),但若未来有人把 `fetchMe` 改成直连 plate 或别的 raw fetch,这里的判断会沉默失效。

**影响:** 局部,但类型不可靠——`as { status?: number }` 是 unsafe cast,应改为 instanceof 守卫。

**修复建议:**
```ts
if (e instanceof ApiError && e.status === 401) {
  clear()
}
```
ApiError 已经 export,不需要 as cast。

---

### P1-6 — `useFieldDescriptions` 的 `draft` ref 是 `Ref<{ definition: { steps?: any[] } } | null>`,对外暴露的 any[] 流到 `DataSetEditor.vue`

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/composables/useFieldDescriptions.ts:67`、`DataSetEditor.vue:328,395,421`

**问题描述:**
```ts
draft: Ref<{ definition: { steps?: any[] } } | null>,
```

`DataSetEditor.vue:328`:
```ts
const draft = ref<{ definition: any; orchestration: any } | null>(null)
const { descriptionByColumnKey } = useFieldDescriptions(draft as any)
function mutateDraft(mutator: (clone: any) => boolean): void { ... }
```

全链路 any —— draft, mutateDraft 回调参数,descriptionByColumnKey 的步骤推算 —— 实际上**已经有 `ScenarioDraft` 类型可用**(`@/types/scenario-composer.ts:34`),但这里为了方便兼容未对齐的 draft 结构(可能 orch 中混入了 extra 字段)用了 any。

**影响:** DataSetEditor 的所有变更与回填逻辑失去类型保护,字段名拼写错(比如 `dataset.rows` vs `dataset.draft.rows`)→ 静默失效,不会被 TS 抓到。

**修复建议:**
```ts
draft: Ref<ScenarioDraft | null>
```
+ `mutateDraft(mutator: (clone: ScenarioDraft) => boolean)`。边界处加 unknown cast 即可,不需要一路 any。

---

### P1-7 — `ExecutionsList.vue` 的轮询没有 `stopPolling` 风格的"启动-停止"对称,`setInterval` 句柄散落在组件模块作用域

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/views/ExecutionsList.vue:111-123`

**问题描述:**
```ts
let handle: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await store.fetchList().catch(() => undefined)
  handle = setInterval(() => store.fetchList().catch(() => undefined), 3000)
})

onUnmounted(() => {
  if (handle !== null) clearInterval(handle)
})
```

对比 `stores/executions.ts:178-227` 的 `startPolling`/`stopPolling`(行级、4 拍 timeout、最大连续失败次数 10、404 优雅退场)—— ExecutionsList 的列表轮询没有:
- 失败退避(网络 5xx 仍 3s 拍)
- 401 退场后的自动重定向
- 不可见标签页暂停(`document.visibilityState`)—— 用户切走 tab 仍每 3s 拉
- "页面被 push 到下一个 route 时立即触发 fetch"(用户感知 stale 数据)

**影响:** 列表页面打开 1 小时 = 1200 次请求,**对 backend 是稳定负载但浪费**;切到 tab 后回前台看到 stale 列表 0–3 秒。

**修复建议:** 把轮询收敛到 `stores/executions.ts`,复用同样的 `startPolling` 模式(给个 `pollingListStart()` 平行实现);或者至少加 `document.visibilityState` 监听。

---

### P1-8 — `stores/executions.ts` 的 `tick` 内 `await fetchRows(rid)` 是串行 await,展开 N 行级表格 → N 秒才完成一轮

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/stores/executions.ts:196-199`

**问题描述:**
```ts
for (const rid of expanded.value) {
  if (shouldSkipRowFetch(rid, prevDetail)) continue
  await fetchRows(rid)
}
```

**影响:** 用户同时展开 5 个 execution 的行级表格 → tick 一次 5 秒(rows 是慢端点可能更大)→ 详情端 `setInterval(tick, 1000)` 1s 拍但每次 tick 都没完成,导致**前端和后端的"同步轮询节奏"完全脱节**——下一次 tick 启动时上一次还没结束,detail 字段仍停留在更早的快照。

**修复建议:** 改 `Promise.all(expanded.value.filter(...).map(fetchRows))`,或允许 `rowsByExecution` tick 之间错峰(每秒 tick 只 fetch 一个展开 execution)。

---

### P1-9 — `http.ts` 的 response interceptor 在 `_retry` 之后 replay 用 `http.request(original)`,会把同一个请求**重新跑一遍完整 axios 流程**,包括再过一次 request/response interceptor

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/http.ts:138`

**问题描述:**
```ts
if (fresh) {
  original.headers = original.headers ?? {}
  ;(original.headers as Record<string, string>).Authorization = `Bearer ${fresh}`
  return http.request(original)
}
```

`http.request(original)` 走的是 axios 内部,会再过 request interceptor(再次拿 `auth.accessToken`,得到的是更新后的 fresh token)、再过 response interceptor(理论上不会再次 401,但有 race window)。

**影响:** 不是 bug,是设计上"保险",但 `original._retry = true` 已经被上面 P0-3 提到,replay 之后的 401 不会触发第二次 refresh。

**修复建议:** 用 `http(original)`(axios(config)等同于 request 但更明确)即可,或保留 `http.request(original)` 没问题,补 P0-3 的二次 refresh 兜底。

---

### P1-10 — `PlateResourceItem.extra` 字段类型过宽(全 `unknown`),实际 kind 决定真实字段,但前端 `toResourceView` 假设了固定 kind

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/plate.ts:104-130`

**问题描述:**
```ts
interface PlateResourceItem {
  name: string
  kind: string
  extra?: {
    image?: string
    config?: Record<string, unknown>
    portMapping?: Record<number, number>
    path?: string
  }
}
```

`toResourceView` 仅识别 `kind === 'mock'` 和 `kind === 'file'`,其他 kind(如注释提到的 `*_ref`)返回 null,**默默丢弃**。`fetchSystemResources` 把 null 跳过(`if (view) resources[it.name] = view`)—— 资源不见但没告警。

**证据:** `api/plate.ts:117-130` 的 if/if/null 三连。

**影响:** plate 新加 kind 时,前端**零提示地丢失资源**,UI 显示 resource 列表对得上 plate 后台,但实际只渲染已知 kind。

**修复建议:** `console.warn` 在丢弃时打日志;或在 store 层补一个 `unknownResources: string[]` 状态让 UI 提示。

---

### P1-11 — `AuthSession.password` 类型不一致——`api/auth_sessions.ts:62` 区分 `AuthSession` 与 `AuthSessionSecrets`,但 `AuthSessionSecrets extends AuthSession` 时 `password` 会被 `AuthSession` 的同名 hidden 字段干扰

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/auth_sessions.ts:59-73`

**问题描述:**
```ts
export interface AuthSessionSecrets extends AuthSession {
  password: string
}
```

`AuthSession` 接口**没有** `password` 字段(已 grep 确认),`AuthSessionSecrets extends AuthSession` 添加 `password: string` 正确。但 `AuthSessionSecrets` 的 `password` 字段是 `string`(必填),后端 `AuthSessionSecretsOut` 也是 `password: str` 必填,匹配。**但** `AuthSession` 列表接口返回 `password_masked`,前端没有对应的类型字段(虽然在 `api/auth_sessions.ts:13` 写了 `password_masked: string`)。

让我复核—— `auth_sessions.ts:4-14`:
```ts
export interface AuthSession {
  id: number
  alias: string
  url: string
  username: string
  token_type: string
  expires_in: number
  created_at: string
  updated_at: string
  password_masked: string
}
```

OK,`password_masked` 已声明。这一项实际**不是问题**——只是注释标 P1 而已,**降为 P2 / 撤销**。

**撤销 P1-11。** 留作对其他团队的提醒:`AuthSessionSecrets extends AuthSession` 的 `password` 与 `AuthSession.password_masked` 同名空间但语义相反(`<REDACTED>` vs 明文),扩展时务必保留区分。

---

### P1-12 — `api/carry.ts` 的 `getServiceFields` 返回的 `ServiceFields.fields` 类型是 `CarryFieldFace[]`,但 `path/type/description` 与后端 `CarryFieldFace` 完全对齐——**前端缺 `type: string`(默认 "string")的运行时校验**

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/carry.ts:53-89`

**问题描述:** 后端 `CarryFieldFace(BaseModel)` 的 `type: str = "string"` 是默认,前端 interface `CarryFieldFace` 写 `type: string`(必填)。如果某次后端 dict 序列化不带 type,前端 TS 把它当 `undefined` 用,出现 `field.type.startsWith(...)` 报错。

**证据:** `api/carry.ts:54` 没有 `?`,与后端字段的 `default` 语义不一致。

**影响:** 边缘;若后端一直带 type,无影响。

**修复建议:** `type?: string`,或在 caller 处加 `(field.type ?? 'string')` 兜底。

---

### P1-13 — `api/http.ts` 的 `extractErrorPayload` 把 `data` 直接 `as ApiErrorPayload`,但 `data` 可能是 Blob / ArrayBuffer / Stream —— 强转有运行时风险

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/http.ts:34-40`

**问题描述:**
```ts
function extractErrorPayload(err: AxiosError): ApiErrorPayload {
  const data = err.response?.data
  if (data && typeof data === 'object') {
    return data as ApiErrorPayload
  }
  return {}
}
```

如果某端点返回 401 + binary data(如受保护图片),`err.response.data` 是 Blob/ArrayBuffer,`typeof data === 'object'` 为 true,但 JSON 字段读取全部失败,normalizeError 落入 `payload.code` 兜底,用户看到的 toast 是 "Network error"。

**影响:** 罕见,但可能性非零。

**修复建议:** 在 `data && typeof data === 'object' && !(data instanceof Blob)` 时再 cast。

---

### P2-1 — `types/scenario-composer.ts` 的 `Scenario` 类型把 `tags` 同时挂在 `meta.tags` 和顶层 `tags`(compat mirror),但类型上两者都是 `string[]`,未用 `readonly` / `Pick<>` 表明兼容性关系

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/types/scenario-composer.ts:67-75`

**问题描述:**
```ts
dataSetCount: number
stepCount: number
/** 兼容镜像:后端恒等于 meta.tags ... 此字段仅服务既有列表/过滤消费方。 */
tags: string[]
```

**影响:** 后端 Pydantic 未来若修改(例如 `tags` 只挂 `meta.tags`,顶层 `tags` 删掉),TS 编译仍通过,运行时 `scenario.tags` 拿到 undefined。

**修复建议:** 给 `tags` 加 `@deprecated` 注释 + 用 `ReadonlyArray<string>` 提醒。

---

### P2-2 — `utils/useListSearch.ts:9-15` 注释里说有三种 `items` 形状但 `(item: any)` 强转隐式发生在 `String(v)` 处

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/useListSearch.ts:48-56,81-91`

**问题描述:** `resolveField` 返回 `unknown`,`String(v)` 在 null/undefined 时返回 `"null"`/`"undefined"`,会被判成包含 substring。

**证据:** `useListSearch.ts:88`:
```ts
return v != null && String(v).toLocaleLowerCase().includes(q)
```

`v != null` 已经过滤了 null/undefined,这里 OK。但 `String({foo: 1})` 返回 `"[object Object]"`,UI 上能看到 `[object Object]` 出现在搜索结果里——可能不是预期。

**影响:** 边缘。

**修复建议:** `typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean'` 时才搜索。

---

### P2-3 — `utils/jsonpath.ts` 用 `obj: any`,`getByPath/setByPath` 全部 any——`utils/draft-lint.ts:11-18` 也是 `steps?: any[]`

**位置:**
- `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/jsonpath.ts:12-45`
- `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/draft-lint.ts:11-18`

**问题描述:** 整个 JSONPath 模块用 any。

**影响:** 测试边界容忍,生产代码虽然走通但失去类型保护。

**修复建议:** 把 `bindings` 改成 `Array<{ path: string; default: unknown; example: unknown }>`,`obj` 改成 `Record<string, unknown>`,仅在最后一个返回值处 cast。`draft-lint.ts` 已经有 `StepView` 类型可用,直接 import。

---

### P2-4 — `api/scenario-composer.ts:178` 的 `converted?: Record<string, any> | null` 在 scenario-draft store 暴露的也是 `Record<string, any>`,导出 JSON 时无类型校验

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/scenario-composer.ts:174-191`、`stores/scenario-draft.ts:46,75`

**问题描述:** `fetchConverted` 返回 `Record<string, any>`,最终落到 `JSON.stringify(converted, null, 2)` 给用户下载。任意字段都直接序列化,但 plate /convert 应该输出严格形状 —— 假定是 ScenarioView/ExecutableScenario 形态。

**修复建议:** 把 `converted` 收紧为 `ScenarioView | ExecutableScenarioView`(由 backend 定),或者显式 `unknown` 而非 `Record<string, any>`,导出前做一次最小形状断言(`typeof converted === 'object' && 'steps' in converted`)。

---

### P2-5 — `components/TopNav.vue` 的 `adaptations.ensureBadgeLoaded()` 没有错误 UI 反馈,`lastError` 没有渲染

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/components/TopNav.vue:69`

**问题描述:**
```ts
if (isAdmin) void adaptations.ensureBadgeLoaded()
```

**影响:** plate 502 时徽章不显示,但管理员不知道是"无待适配"还是"目录不可用",可能误判数据状态。`adaptations.lastError` 在 store 里暴露但没人渲染。

**修复建议:** TopNav 在 `lastError` 非空时加一个 hint icon(tooltip 显示"目录服务不可用")。

---

### P2-6 — `stores/executions.ts` 的 `startPolling(id)` 没有把 startPolling 与具体 detail 解耦——store 全局只能同时轮询 1 个 execution

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/stores/executions.ts:178-227`

**问题描述:** `pollHandle` 是单例。从 Executions A 跳到 Executions B,A 的 stop 必须先调(由 Executions.vue:476 `stop = execStore.startPolling(executionId.value)` 隐式调用),但若用户用 browser back 进 A,不会重新 `startPolling` —— A 的轮询不再恢复,只能依赖手动刷新。

**影响:** 边缘,日常很少有"轮询 A→B→A"的场景,但路由行为不算健壮。

**修复建议:** 把轮询绑到组件层,store 仅暴露 `tick(id)` 与 `stop(id)`,组件 onMounted 启动 / onUnmounted 停。

---

### P2-7 — `useInsertTarget` 的 `appendValue` 对 `HTMLInputElement` 直接赋值 `el.value`,不触发 `change` 事件,可能导致 Vue 的 `v-model` 不触发 watcher 重算

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/composables/useInsertTarget.ts:51-65`

**问题描述:** 注释说"派发原生 input 事件,兼容 FieldForm 原生 @input→setValue",但 Vue 的 `v-model` 默认 listen `input` 事件 → 应当 OK。然而 Element Plus 的 `el-input` 在内部包了一层 `<input>`,原生 `el.dispatchEvent(new Event('input'))` 是派发到 el-input 内部的 input,可能不冒泡到 el-input 自己,所以 el-input 的 v-model 不一定响应。

**证据:** 注释承认三链(原生 @input→setValue、v-model、原生 textarea),但 el-input 不在三链里。

**影响:** 用户在 composer 里用常量池插入按钮插入到 el-input,可能不更新。

**修复建议:** 用 `el-input` 暴露的 `inputValue` 双向绑定,或者尝试派发 `change` 事件 + `blur/focus` 触发 v-model 重算。

---

### P2-8 — `utils/csv-dataset.ts:140-160` 的 `parseTsvPaste` 把 `'\\n'` 标准化为 `'\n'`,但没考虑 Mac 经典 `\r`(老 Excel 复制出的 TSV 在 macOS Excel 可能是 `\r`)

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/dataset-grid.ts:134-173`

**问题描述:** `text.replace(/\r\n?/g, '\n')` 已经处理 `\r\n` 与 `\r`(因为 `\r\n?` 匹配 0 或 1 个 `\n`)。实际 OK。**撤销 P2-8。**

---

### P2-9 — `stores/auth_sessions.ts` 的 `createAuth` 后 `list.value = [...list.value, a].sort(...)` —— 修改整个数组引用,触发所有订阅 `list` 的组件重渲染

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/stores/auth_sessions.ts:37-41`

**问题描述:** 这其实是正确的(避免索引错位),但 `list.value.findIndex` + `splice`(`users.ts:39`、`auth_sessions.ts:48`)—— `splice` 是 in-place 修改,触发响应式更新。两者混用,**部分 patch 走 splice,部分走全替换**——前端组件 watch 行为可能不一致。

**影响:** 性能/一致性小问题。

**修复建议:** 统一走全替换或全 splice。

---

### P2-10 — `router/index.ts` 没有兜底 404 route,未匹配路径会显示空白

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/router/index.ts:12-97`

**问题描述:** `routes` 列表没有 `path: '/:pathMatch(.*)*'` 兜底 route。用户手敲 `/foo` → 路由表无匹配 → 显示空 `<router-view />` —— App.vue:8 的 `<router-view />` 在没有 component 时是空白。

**证据:** 路由表 13 条 entry,无 catch-all。

**影响:** 用户体验缺失,无报错。

**修复建议:** 加 `{ path: '/:pathMatch(.*)*', redirect: '/scenarios' }` 或一个 NotFound.vue 视图。

---

### P2-11 — `router/index.ts` 的 `requiresAdmin` 在 `currentUser` 未拉取时永远 false,首屏 admin 用户被错误地重定向到 `/scenarios`

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/router/index.ts:104-117`

**问题描述:**
```ts
if (to.meta.requiresAdmin && !auth.isAdmin) {
  return { path: '/scenarios' }
}
```

`auth.isAdmin = computed(() => Boolean(currentUser.value?.is_admin))` —— `currentUser.value === null` 时 `isAdmin === false`。首次进站访问 `/admin/users` 时,如果 fetchMe 还没 resolve,用户被踢到 `/scenarios`。同 P1-1,放大版。

**修复建议:** 在 fetchMe 完成前把路由导航挂起(await),或 fetchMe 失败时不重定向(等 fetchMe 成功后再判定)。

---

### P2-12 — `utils/carry-csv.ts` 自手写 RFC4180 parser 而不用 papaparse,而 `utils/csv-dataset.ts` 用了 papaparse —— 同项目两种 CSV 解析实现

**位置:**
- `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/carry-csv.ts:33-84` 自手写 `splitRecords`
- `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/csv-dataset.ts:21,115` 用 `Papa.parse`

**问题描述:** 同一项目两种 parser 实现,行为不一致(例如空行处理、转义、CRLF)。

**修复建议:** carry-csv 也走 Papa.parse,只把"is_null/path/value 必填 + path 唯一"等业务校验留在 carry-csv.ts。

---

### P2-13 — `api/auth_sessions.ts:63-74` 的 `get(id, includeSecrets)` 返回 `AuthSession | AuthSessionSecrets` 的 union,但 union 仅靠 `password` 字段存在/不存在区分,caller 必须自己判别

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/auth_sessions.ts:65-74`

**问题描述:** `includeSecrets=true` 时后端会返回明文 password,但 union 类型让 caller 必须 `'password' in result` 判断,容易写错。

**修复建议:** 拆成 `get(id)` 与 `getWithSecrets(id)` 两个明确命名的函数,返回类型明确。

---

### P2-14 — `utils/catalog-services.ts:30-43` 的 catalog fetch 没有 timeout,plate 不可达时会让 `loadCatalogServiceNames` 卡住 30 秒+

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/catalog-services.ts:30-43`

**问题描述:** 裸 `fetch('/plate/api/endpoint?per_page=500')` 没有 AbortController/timeout,plate 挂时永远 pending。`catch (e) { cached = null; throw e }` 会清除缓存让下次重试,但 pending 期间调用方卡死。

**修复建议:** 加 `AbortController` + `setTimeout(controller.abort, 10000)`。

---

### P2-15 — `utils/useListSearch.ts` 第 47 行说"compose 第三种 items 形态 = T[] 数组(测试方便)",生产路径里 `Scenarios.vue` 用 `() => usersStore.list` getter,实际全部走 getter,**注释与生产不匹配**,误导新人

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/useListSearch.ts:8-15`

**问题描述:** 注释里第三种"accepted for test convenience, NOT reactive across in-place mutations"误导。如果新人按注释传 `T[]` 在生产代码里,搜索结果不会响应 store 的 in-place 更新。

**修复建议:** 把第三种形态删掉,只接受 `Ref<T[]>` 与 `() => T[]`,强制生产代码用响应式。

---

### P2-16 — `api/plate.ts:24-31` 的 `plateFetch` 把 fetch 失败统一抛 `Error('plate ... -> HTTP xxx')`,但走的是 fetch 而非 http 实例,**响应错误不会自动走 refresh 401 拦截器**

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/plate.ts:24-31`

**问题描述:** `useFieldDescriptions` / `useSystemPrefill` / `catalog-services` 都走 plateFetch,accessToken 过期 → 401 → 抛出 `Error`,**不走 http 拦截器的 refresh + 重定向逻辑** → 用户看到"plate ... -> HTTP 401" 在 console,UI 卡在 stale 数据。

**修复建议:** 把 plate 的请求也接入 http 实例(给 http 单独加个 `baseURL: '/plate'` 的实例),或者给 plateFetch 加一个"401 时调 refreshOnce + 重试"逻辑。

---

### P2-17 — `App.vue:22-30` 的 fetchMe 触发的 `auth.fetchMe` 失败仅 catch 一次,但失败时 `status` 仍为 `unknown`,首屏 TopNav 完全不渲染(`v-if="auth.isAuthenticated"` 只看 token,看不到 status)

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/App.vue:6-9`

**问题描述:** `auth.isAuthenticated = computed(() => !!accessToken.value)` 不看 `status`。`status === 'unknown'` 但 `accessToken` 存在时,TopNav 渲染但 `currentUser` 是 null,TopNav 显示用户头像空 / admin tab 不显示(因为 isAdmin=false)。

**修复建议:** fetchMe 期间 `status = 'unknown'` 时,TopNav 显示"加载中"占位(防止空白闪烁)。

---

### P2-18 — `views/CaseComposer.vue:517-568` 用 `(s as any)` 强制 narrow — 草稿结构走类型 any 流转

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/views/CaseComposer.vue:517,567,568`

**问题描述:** 既然已经 import 了 `ScenarioView` / `StepView`,这里 `as any` 没必要。

**修复建议:** 直接用 `s: StepView`(或 unknown + narrow)。

---

### P2-19 — `api/scenario-composer.ts:201` 的 endpoint-catalog URL 用 `encodeURIComponent`,但其他处 `scenarios/{id}/data-sets/{datasetId}` 用 `encodeURI`(links.ts 一致)—— 项目内两种 URL encoding 风格并存

**位置:**
- `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/scenario-composer.ts:35-37,200,231` 用 `encodeURI` 与 `encodeURIComponent`
- `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/utils/links.ts` 全 `encodeURIComponent`

**问题描述:** scenarioId/datasetId 含 ASCII 字符为主,两种都行;但 endpointId 可能含 `:` / `/`(`/api/endpoint/...:id` 之类),`encodeURI` 不转义 `:` 与某些字符,在 path segment 解析时可能出问题。

**修复建议:** 全 `encodeURIComponent`(与 links.ts 一致)。

---

### P2-20 — `main.ts:14-17` 没有全局 error handler,组件未捕获的异常会冒到 window.onerror — 没有 Sentry / 日志上报

**位置:** `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/main.ts:12-18`

**问题描述:** 没有 `app.config.errorHandler` 与 `window.addEventListener('unhandledrejection', ...)`。

**影响:** 生产环境用户报错无任何上报。

**修复建议:** 加最小 `app.config.errorHandler = (err, instance, info) => { /* 上报 */ }`(内网测试环境可暂时 console.error + 用户 toast)。

---

## 三、亮点

值得在评审里专门点出来的做得好的地方:

1. **refresh token single-flight 设计**(`stores/auth.ts:108-124` + `http.ts:131-152`)—— 注释里详细解释了"self-deadlock"陷阱(第 124-127 行),避免新人复制时踩坑。
2. **`http.ts` 拦截器对 `isRefreshCall` 特判**(`http.ts:128-130`)—— `/auth/refresh` 自身的 401 不会触发 refresh 递归。注释清晰。
3. **`stores/auth.ts` 的 `clear()` idempotent 设计**(`stores/auth.ts:89-99`)—— 显式 short-circuit,5 个并发 401 不会触发 5 次 localStorage 写。
4. **`api/adaptations.ts` 的 `errMsg` 工具函数**(`api/adaptations.ts:111-115`)—— 收敛 ApiError → 文案的唯一入口,避免散落 `(e as { msg?: string })` 强转。
5. **`utils/errorFallback.ts` 的 `showError`**(`utils/errorFallback.ts:45-56`)—— 注释明确"store 错误请直接 throw 出来让 catch 捕",避免双消息源。
6. **`utils/useListSearch.ts` 的三形态支持**(`utils/useListSearch.ts:7-15`)—— Ref / getter / 数组,注释说明生产应该用 getter,测试可以传数组。
7. **`stores/adaptations.ts` 的 `inflight` + `loaded` 双标志**(`stores/adaptations.ts:19-41`)—— 同 store 多次 `refreshDiff()` 共享 in-flight,force=true 才重拉,语义清晰。
8. **`stores/constants.ts` 的 `catalog` 失败静默 + `entries` 失败 throw** 区分(`stores/constants.ts:55-74`)—— 目录(plate 代理)挂了不影响字面量 CRUD,合理。
9. **`stores/executions.ts` 的 polling 失败预算**(`stores/executions.ts:181-217`)—— 10 次连续失败 / 404 → 优雅退场 + pollError 上报,而不是静默 1 req/s 永久轮询。
10. **`utils/carry-drift.ts` 的 `canGenerateCarryBatch` 单点契约**(`utils/carry-drift.ts:106-110`)—— 漂移面板的"plate 不可达禁用批生成"约束集中一处,UI 与 store 都从这走。
11. **`utils/carry-entries.ts` 的三态(hasRow/isNull/value)设计**(`utils/carry-entries.ts:18-36`)—— 显式处理 "null / 显式空串 / 未填" 三态,与 backend `dict[str, str | None]` 完美对齐。
12. **`utils/carry-csv.ts` 的 RFC4180 自实现** 注释承认 trade-off(P2-12 反向证据),虽然建议统一为 Papa.parse,但自实现细节控制力更强。
13. **`composables/useFieldDescriptions.ts` 的版本号模式**(`useFieldDescriptions.ts:23,39,91-93`)—— 用 `fullVersion` ref 显式 bump 让 computed 重算,避免 Map 引用变化不可靠的问题。
14. **`utils/scratch-path.ts` 的幂等映射**(`utils/scratch-path.ts:14-20`)—— plate → engine 路径映射本身幂等,多次调用安全。
15. **`composables/useSystemPrefill.ts` 的 "成功一次后不再重载" + "失败不消耗首次机会"**(`useSystemPrefill.ts:50-65,98-102`)—— UX 友好,且不静默吞错。

---

## 四、总评

### 整体状态

| 维度 | 评级 | 说明 |
| --- | --- | --- |
| 类型安全 | B+ | 大部分有明确 interface,但 `DataSetEditor` / `useFieldDescriptions` / `CaseComposer` 局部 any 流;`SystemTag` 联合失约束 |
| HTTP 层 | A- | refresh single-flight + 401 单次重放 + refresh 自调用避免 — 整体设计成熟,但 P0-3 二次 refresh 兜底缺失 |
| Token 持久化 | C+ | 明文 localStorage 双 token 是已知设计层弱点,依赖"目前没 v-html"的隐式保证 |
| Pinia store | A- | 单向数据流清晰,绝大多数 mutation idempotent,`clear()` / `refreshOnce()` 设计扎实 |
| 路由守卫 | B | 兜底 404 缺失;admin 守卫与 fetchMe 时序问题(被 P1-1 放大) |
| 错误处理 | B+ | `errorFallback.showError` 收敛好,`api/adaptations.ts.errMsg` 单独覆盖,但 `normalizeError` 对 5xx HTML 缺兜底 |
| 安全 | B- | 无 v-html,无 dangerouslySetInnerHTML,默认安全;但 token localStorage + 无 CSP 是结构性弱点 |
| 代码组织 | A- | utils / composables 拆分清晰,纯函数占比高,易测试;carry 子模块的设计自洽 |

### 建议优先做的 3 项工作

1. **加 CSP + 引入 cookie 化 refresh token 路线** — 解决 P0-2。即使短期只上 CSP(`script-src 'self'`,vite plugin + nginx),也是零成本高回报。具体:在 `vite.config.ts` 的 dev server headers 加,生产部署 nginx config 加。
2. **修 `refreshOnce` 失败清理 + 路由守卫 await fetchMe** — 解决 P0-1 + P1-1 + P2-11 三个相关问题。把"已知 refresh 失败 → 清 store"前置到 store 层,把"首次访问 protected route → 等 fetchMe resolve"放进 router.beforeEach。
3. **修 P0-3 二次 refresh 兜底 + 收紧 `DataSetEditor` 类型** — 解决 P0-3(边缘但影响 session 状态)与 P1-6(类型安全局部漏洞)。两者改动局部、可测、不破坏既有功能。完成后整页前端类型覆盖率提升一档。

### 不需要做的(看似问题实则不是)

- **`Scenario` 与 `ScenarioMeta` 的兼容 mirror tags** — 是 V1→V3 迁移期的显式兼容层,删了会破坏既有消费方,留作 `@deprecated` 注释即可。
- **`useFieldDescriptions` 的 `descriptionByColumnKey` Map 结构** — 注释清晰,文档化充分,不必改成 reactive object。
- **`useSetStatus` 的 fetchStatus/lastError 双字段** — 单一职责工具函数,虽然在不同 store 里重复声明,但每个 store 都自己 keep 一份,删了反而要全局重排,代价大于收益。

---

*评审人:AI(state / api / types / router 角色) — 仅基于代码真实实现,未读文档规格;评审时间 2026-09-02*