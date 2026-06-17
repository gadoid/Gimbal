# 遗留问题：模板变量替换机制

> **模块**：[`gimbal.preprocessor`](../../modules/preprocessor.md) + [`gimbal.utils.jsonpath`](../../modules/utils.md)
> **状态**：已知未修复
> **适用范围**：仅**预处理阶段**的模板替换（`ScenarioPreprocessor._resolve_value` → `resolve_template` → `_get_nested`）。
> 已确认 [`gimbal.context.resolver`](../../modules/context.md) 中的 `SpecResolver` 没有任何外部调用方，**不在本登记范围内**。

---

## 0. 背景与现状

### 调用链

```
ScenarioPreprocessor.run()
  → _resolve_steps()
    → _resolve_api / _resolve_request / _resolve_strategy
      → _resolve_value()
        → resolve_template()             # 位于 gimbal/utils/jsonpath.py
          → _TEMPLATE_VAR_RE (regex)
          → _get_nested()                # 走点号路径 + dict.get / getattr
```

### 解析 root 构造（[_build_resolve_root](../../modules/preprocessor.md)）

```python
root["service"] = ...   # 浅拷贝 services
root["auth"]    = ...   # 浅拷贝 AuthRegistry.snapshot()
```

### 当前已支持的常见用法

- `${auth.codfish.token}` ✅
- `${service.orderApi.baseUrl}` ✅
- `${user_id}` ✅（整串单 `${}` 保留原类型）
- `"Bearer ${token}"` ✅（嵌入式字符串拼接）

### 决策记录

- **类型归一**：**不在本层处理**。下游 Pydantic schema 强转解决。
- **缺失变量策略**：当前是**静默**（返回 None 或保留原样），**不**采用 fail-fast。
- **演进节奏**：作为较早期版本，遗留至后续迭代。

---

## 1. P0（常见路径上的非预期结果）

### 1.1 `${}` 内部不支持 JSONPath 高级语法

**位置**：[`gimbal/utils/jsonpath.py:603-627`](../../src/gimbal/utils/jsonpath.py#L603-L627) `_get_nested`

**行为**：只支持点号路径 + `dict.get` / `getattr`。**不支持**：

- `[0]`、`[-1]`（下标）
- `[*]`（通配）
- `[?(@.x==1)]`（过滤）
- `$..field`（递归下降）

**触发场景**：`${data.items[0].id}`、`${users[?(@.role=='admin')].token}`

**实际后果**：直接静默返回 `None`，**无任何 warning**。在 `headers` / `body` 中表现为：

- header 路径里值变 None → 被 [scenario_preprocessor.py:284 的 None 过滤](../../src/gimbal/preprocessor/scenario_preprocessor.py#L284) 静默删除
- body 路径里值变 None → `{"id": null}` 直接发到下游

错误延迟到 HTTP 层（401 / 业务校验失败）才暴露。

**与文档的冲突**：[`gimbal/utils/jsonpath.py:38`](../../src/gimbal/utils/jsonpath.py#L38) 与 [`gimbal/context/resolver.py:38`](../../src/gimbal/context/resolver.py#L38) 注释均写"`${}` 内部默认 JSONPath，$ 可省略"，与实现矛盾。

### 1.2 嵌入式模板缺失变量时静默原样保留

**位置**：[`gimbal/utils/jsonpath.py:651-656`](../../src/gimbal/utils/jsonpath.py#L651-L656) `_replacer`

**行为**：
```python
if val is None:
    return match.group(0)   # 找不到保留原样
return str(val)
```

**触发场景**：`"Authorization": "Bearer ${auth.codfish.token}"` 中 `auth.codfish` 不存在

**实际后果**：最终 HTTP 请求带着**字面量字符串** `Bearer ${auth.codfish.token}` 发出，与"用户想保留字面 `${...}`"的合法场景**无法区分**。

### 1.3 headers / body 中"空字符串"与"变量未找到"被同等处理

**位置**：[`gimbal/preprocessor/scenario_preprocessor.py:279-284`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L279-L284)

**行为**：
```python
resolved_headers = {k: v for k, v in resolved_headers.items() if v is not None}
```

**触发场景**：
- 用户显式写 `"X-Tag": ""`（合法空串）→ **被删**
- 模板 `"X-Tag": "${missing}"` → 解析为 None → **被删**

两种情况完全不可区分。

**body 路径的反向问题**：[`scenario_preprocessor.py:304`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L304) 走 `_resolve_nested` 不过滤 None，导致 `body = {"id": "${missing}"}` 变成 `{"id": null}` 发出去——与 headers 的"静默删除"策略**不一致**。

### 1.4 整串单 `${}` 保留原类型，可能导致下游 schema 校验随机失败

**位置**：[`gimbal/utils/jsonpath.py:645-649`](../../src/gimbal/utils/jsonpath.py#L645-L649) `resolve_template`

**行为**：
- `"${user_id}"` → `int 42`（保留原类型）
- `"prefix-${user_id}"` → 强制 `str` 拼接
- `"${a}+${b}"` → 强制 `str` 拼接

**触发场景**：
- `api.path = "${service.order.path}"` 若 `path` 是 `int 42` 或 `dict` → Pydantic 校验抛错
- `body = {"page": "${page}"}` 中 `page=1`（int）→ 后端收到 `page=1` 而非 `page="1"`

**当前决策**：类型归一不在本层处理，由下游 schema 强转。**记录但暂不修**。

---

## 2. P1（触发条件明确、可控）

### 2.1 模板正则不支持嵌套 `${}`

**位置**：[`gimbal/utils/jsonpath.py:600`](../../src/gimbal/utils/jsonpath.py#L600) `_TEMPLATE_VAR_RE = re.compile(r"\$\{([^}]+)\}")`

**行为**：遇 `}` 就闭合。

**触发场景**：`"${${env}.token}"` → 第一对 `${${env` 匹配，`}` 闭合，剩下 `.token}` 是死字面量。

**实际后果**：不支持"内层先展开"的链式模板。

### 2.2 无转义机制

**行为**：字面量 `"status: ${ok}"` 会被当作模板去查 `${ok}`。`$${literal}`、`\${literal}` 都不会被识别为"保留字面量"。

**实际后果**：用户想在 payload / assertion 中保留字面 `${...}` 字符串时无解。

### 2.3 `_resolve_api` / `_resolve_request` / `_resolve_step` 重建对象丢失未声明字段

**位置**：
- [`scenario_preprocessor.py:286-293`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L286-L293)（Api）
- [`scenario_preprocessor.py:302-305`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L302-L305)（Request）
- [`scenario_preprocessor.py:263-270`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L263-L270)（Step）

**行为**：每处都是显式列出字段构造新对象，**未列出的字段全部丢失，无 warning**。

**实际后果**：后续给 `Api` / `Request` / `Step` 加新字段（label、tags、condition、metadata、trace_id…）时，preprocessor 维护成本与 schema 演进强耦合，且不会立刻报错。

### 2.4 `_resolve_strategy` 对未知 kind 静默原样返回

**位置**：[`scenario_preprocessor.py:346-347`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L346-L347)

**行为**：
```python
# 未知策略类型，原样返回
return strategy
```

**实际后果**：自定义 `Strategy` 子类里的 `${}` **永远不会被解析**——隐晦的 bug 源。

### 2.5 `_resolve_value` 缺失变量时返回 `None` 与"变量值真为 None"撞车

**位置**：[`scenario_preprocessor.py:364-368`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L364-L368)

**行为**：
```python
resolved = resolve_template(value, root)
if resolved is None:
    logger.warning("...")
    return value
```

**问题**：
- 嵌入式缺失（`_replacer` 内部走 `return match.group(0)`）→ **永不返回 None**，所以这条 warning 永远不触发
- 单变量缺失（路径不存在）→ 触发 warning，原样保留
- 单变量"存在但值是 None"→ 触发 warning，原样保留

三种"失败"行为不一致。

---

## 3. P2（结构性 / 风格性 / 可维护性）

### 3.1 整个机制无 fail-fast 钩子

- 认证失败 [`scenario_preprocessor.py:200-201`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L200-L201) 会 `raise`
- 模板解析阶段**没有同等的 fail 机制**，所有失败都退化到 warning 或静默

**实际后果**：模板拼错时不会在预处理阶段 fail，错误延迟到网络层。

### 3.2 没有任何针对模板替换的单测

`tests/unit/`、`tests/integration/`、`tests/e2e/` 下均**没有** `test_resolve_template.py` / `test_preprocessor_resolve.py`。整条解析链是手测的，**所有上述问题都没有回归保护**。

### 3.3 `_resolve_value` 对每个 string value 走两次正则

[`scenario_preprocessor.py:361-364`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L361-L364)：
```python
if not isinstance(value, str) or not is_template(value):  # 一次 search
    return value
resolved = resolve_template(value, root)                   # resolve_template 内部再走 fullmatch / sub
```

不是 bug，但 steps 数量大时浪费可观。

### 3.4 `context/template.py` 是空壳

[`gimbal/context/template.py`](../../src/gimbal/context/template.py) 仅有 1 行 docstring，无实现、无 `__all__`、无 TODO。

**实际后果**：原计划中的"统一模板引擎"从未落地，导致三处独立实现（`resolve_template`、`SpecResolver`、`_resolve_source_value`）做类似事情。

### 3.5 `channels` / `AuthRegistry` 的浅拷贝与可变引用

[`scenario_preprocessor.py:222-234`](../../src/gimbal/preprocessor/scenario_preprocessor.py#L222-L234)：
```python
root["service"] = dict(self._cfg.services)          # 浅拷贝
root["auth"]    = self._auth_registry.snapshot()    # 浅拷贝
```

`AuthSession` 是可变对象，**`token` 刷新后**下游自动可见（这是有意为之，注释有说明）。**仅限**单次预处理的同步流程。如果以后并发跑预处理或复用 preprocessor 实例，会成为竞态源。

### 3.6 `request.body` 与 `headers` 的 None 处理策略不一致

见 1.3，已经在 P0 列出。这条仅作"结构性问题"的交叉引用。

---

## 4. 触发修复的信号（"何时重开"）

满足任意一项即可重开本工单：

1. **用例命中**：实际场景里出现 `${items[0].id}`、`${${env}.x}`、`$${literal}` 等当前不支持的语法。
2. **CI 出现"静默错误"**：线上监控发现"模板变量名拼错导致 401/422 而非 fail-fast"类故障。
3. **schema 演进**：`Api` / `Request` / `Step` / `Strategy` 计划加新字段（label、tags、condition、metadata 等）—— 此时 2.3 必须先解。
4. **自定义 Strategy 注册**：用户开始注册自定义 `Strategy` 子类 —— 此时 2.4 必须先解。
5. **预处理性能问题**：steps 数量大、模板字段多，3.3 的双正则成为热点。

---

## 5. 修复记录

> 修改时在此追加，**不要删除历史条目**。格式：`### YYYY-MM-DD — 简述`。

<!-- 暂无 -->
