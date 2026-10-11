# GIMBAL Scenario Schema Reference

> **T5.1（M2 §4.3）**：本文件已改为**运行时从 plate `/api/m2` 读取**的提示。
> 静态结构参考已过时（M2 步骤 4 切换后 `api` → `call`、Meta 只有 `name`
> 必填、`meta.plate` 版本声明等）。组装场景时**先调 plate 拿当前 Schema**，
> 本文件只保留不变的语义规则（变量命名空间 / 模板约定 / 清洗规则）。

## 获取当前 Schema（权威源）

```bash
# 当前 M2 Schema（含全部类型定义与字段约束）
curl http://127.0.0.1:8765/api/m2

# 按构建身份取历史版本
curl http://127.0.0.1:8765/api/m2/<m2_hash>
```

响应的 `data.schema` 即 JSON Schema（`$defs` 含全部 M2 类型——
Scenario / Meta / Config / Step / Call / Request / Extract / Assign /
Assertion / RunOptions / SuiteGraph 等）。

## M2 关键变更（相对于本文件旧版）

- **`api` → `call`**：Step 的调用键从 `api` 改为 `call`，
  形态 `{"protocol": "http", "service": "...", "method": "...", "path": "..."}`
- **`step.endpoint`**：步骤可选锚点（plate 接口 id），系统前缀须在
  `meta.plate` 中声明版本
- **`meta.plate`**：`{系统: "<line>#<n>" | "working"}` 版本声明
- **Meta 只有 `name` 必填**：其余字段全有默认值
- **forbid**：未知字段直接拒绝（不是静默忽略）

## 语义规则（不变的部分）

### Two variable namespaces (static vs dynamic) — CRITICAL

GIMBAL resolves values in two distinct phases. Do not mix them.

1. **Static — `${var.x}` / `${auth.x.token}`**: substituted from `config.vars`
   / `config.users` **before the run starts**. Use ONLY for test inputs known
   ahead of time and constant for the whole run.

2. **Dynamic — scenario context via `extract` → `assign`**: a value produced
   by one step's response (`extract` `target` = a context variable) and
   injected into a later request **at runtime** (`assign` `source: $.x` →
   `target: $.request_body...`). Use for every value the business process
   *generates or mutates* as it runs.

**Hard rule:** any id created/changed during the flow is **dynamic**.
It MUST be wired through `extract`/`assign` and MUST NOT be placed in
`config.vars` or referenced as `${var.<that id>}`.

### Templating conventions

- `${var.<name>}`   — value from `config.vars`
- `${auth.<user>.token}` — bearer token for a user in `config.users`
- Captured `Authorization` / `Admin-Token` / `Cookie` → replace with
  `${auth.<user>.token}` (pick the user defined in `config.users`).

### Header sanitization

Keep only functional headers (typically just `Authorization`). **Delete** all
browser/transport noise:
`Host, Connection, Content-Length, Cookie, Origin, Referer, User-Agent,
Accept, Accept-Encoding, Accept-Language, sec-ch-ua*, Sec-Fetch-*`.

### Variable naming

Name **dynamic context variables** (extract targets, referenced by assign
`source: $.x`) after their semantic role, not the step:
`order_id`, `order_no`, `order_sub_id`, `finance_id_usd`, `audit_id`, etc.
Reuse the same name across producer and all consumers.

### Single-write rule (scenario scope)

A scenario-scope `target` may be written **only once** in the whole scenario.
If the same kind of value is captured at multiple points, use `scope: step`
for the transient one, or store under a **distinct name**.
