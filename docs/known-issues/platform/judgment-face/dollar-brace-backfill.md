# 阶段二待修：`${...}` 类值也补了 `default` / `required`（G）

> **模块**：`gimbal-platform/backend`（注入物化：偏离值 → `Assign` 策略）
> **状态**：**已裁定并落盘**（2026-11-24：改文档路线，行为维持现状；见 §3 顶部裁定行与文末[修复记录](#修复记录)）
> **来源**：`docs/implemented/specs/2026-09-12-architecture-convergence-design.md` §6.3 / §7（G）
> **适用范围**：`run_injection._assign_strategy` 对用户偏离值的兜底键注入。

---

## 0. 现状：代码与自己的 docstring 相反

`_assign_strategy` 把偏离值包成一个 `Assign` 策略字典，并按「该值会不会被引擎当**引用**解析」决定是否补兜底键：

```python
# src/gimbal-platform/backend/app/services/run_injection.py:66-70
st: dict[str, Any] = {"kind": "assign", "source": value, "target": target}
if _is_context_readable(value):
    st["default"] = value
    st["required"] = False
return st
```

而 `_is_context_readable` 对**两类**字符串都返回 `True`：

```python
# src/gimbal-platform/backend/app/services/run_injection.py:15-28
if source.startswith("$."):
    return True
return source.startswith("${") and source.endswith("}")
```

矛盾在**同一函数的 docstring** 里写得很清楚（`run_injection.py:44-51`）：

> **整串 `"${...}"` 类不可兜**（引擎语义所限，记录不兜；**不加键也不改行为**）……

「不加键」是错的：`if _is_context_readable(value)` 对 `${...}` 类**为真**，键确实加上了。「不改行为」由此也不成立——见 §1 第 3 条。

---

## 1. 缺陷：三类结局里，只有一类被改坏了

引擎侧链路（均已读源）：

1. 预处理**先于任何策略执行**整体跑一遍（`src/gimbal/core/scenario_runner.py:256-267`：`preprocessor.run()` 在 step 执行之前；`Assign.required` / `Assign.default` 的基座默认值见 `src/gimbal/schema/strategy.py:72-73`，即 `None` / `True`）；
2. `_resolve_strategy` 把 `Assign.source` 与 `Assign.default` **一并**过 `_resolve_or_fail`
   （`src/gimbal/preprocessor/scenario_preprocessor.py:417-429`）；
3. `_resolve_or_fail` 的判据是「路径**真不存在** → `ValueError`；**key 存在但值为 None** → 返回 `None`（合法值）」
   （`src/gimbal/preprocessor/scenario_preprocessor.py:450-462`）；
4. `AssignExecutor` 拿到 `value is None` 时：`default is not None` → 用 default；`elif required` → **FAILED**；否则**继续往下写**
   （`src/gimbal/strategy/builtin/assign.py:35-45`）。

于是 `${...}` 类值分三种情形：

| 情形 | 预处理结果 | 补键后（现状） | 不补键（docstring 声称的行为） |
| --- | --- | --- | --- |
| `config.vars` **无**同名变量 | 预处理器 `ValueError` | 同左（**比 Assign 早**，default 从未被读到） | 同左 |
| 变量存在，值为**非 null** | source/default 双双被改写成变量值 | 写入 vars 值 | 与补键无关，同样写入 vars 值 |
| 变量存在，值为 **null** | 两者都解析成 `None` | `default is None` → 不取；`required=False` → **静默写 null** | `required` 取默认 **True** → `Assign` **FAILED**（步骤显式失败） |

**第三行就是本条记录的全部要害**：补键把「变量存在但为 null」从**显式失败**变成了**静默写 null**。

**触发条件**：用户在断言条目的偏离值里填了整串 `${var}`，而该变量在 `config.vars` 里**存在且被显式赋成 null**（显式 null 在本仓库是**合法且有语义**的——见 `carry_binding` 的 NULL≠空约定，spec §4.3）。

**影响**：字段被写成 JSON null 并如实发到下游 —— 若用户的意图是「这个字段必须有个值」，错误会推迟到业务侧才暴露（422 / 业务校验失败），而不是在步骤层 FAILED。与既有一致的方向（「少 fail-fast」）一致，但对**显式 null** 这一合法形态是有害的一侧。

**范围边界**（都不是本条的问题，已读源确认）：

- 不带 `${}` 的普通字面量、dict、list、null：`_is_context_readable` 为假 ⇒ 不补键 ⇒ 基座字段全取默认，与补键无关；
- `$.` 类：**补键是有效的**，也是当初加它的原因（`run_injection.py:36-43` 解释了 `default` + `required: false` 如何把「JSONPath 读不到」从整步 FAILED 变成写字面量）。§3 的裁定**不应**顺手把 `$.` 类一起改掉。

---

## 2. 优先级：P1

按 README：**触发条件明确、可控、规避成本低**。

- 触发条件是具体的、可判定的（引用了一个值为 null 的变量）；
- 规避成本低（不要在偏离值里引用会为 null 的变量；或改用字面量）；
- 不是 P0：它不产生**非预期**的业务结果——null 会被如实写出，用户若要检测仍有下游断言可用；且需要用户先把变量显式赋 null。
- spec §6.3 的分级与此一致（G 标 P1）。

---

## 3. 待裁定

> **裁定已作（2026-11-24，用户拍板）**：结论 = **改文档（下方选项 2）**——行为维持现状（`${...}` 类继续补键；变量为 null 时静默写 null），docstring 与编辑器注记改为与行为一致；§3.3 的语义问题答 = **「引用了一个值为 null 的变量」不算「用户没填值」**——显式 null 是合法值（与 carry_binding NULL≠空 约定同向，spec §4.3），静默写 null 是裁定后的期望行为而非缺陷；要求「必须有值」的场合改用 `$.` 类引用或下游断言。下方决策清单保留为裁定前的历史；实装见文末[修复记录](#修复记录)。

> 原文见 spec §7：**G `${...}` 类补键** —— *改为只对 `$.` 类补键（与 docstring 对齐、恢复旧行为），还是接受「变量存在但为 null 时静默写 null」并改文档。*

留给维护者的决策（**本记录不下结论**）：

1. **改代码**：`if _is_context_readable(value)` 收窄为「仅 `$.` 前缀」⇒ `${...}` 类回到 `required=True` 默认，null 情形恢复为显式 FAILED；docstring 的「不加键也不改行为」随之成立。
2. **改文档**：接受现状，把 docstring（`run_injection.py:44-51`）与平台 API 文档里对应段落改成「`${...}` 类**也**补键；变量为 null 时静默写 null」，并把「不可兜」的结论收窄为「变量缺失时兜不住（预处理器先抛）」。
3. 无论选哪条，都要回答：**「引用了一个值为 null 的变量」在语义上算不算「用户没填值」**？如果算，静默写 null 反而更贴近本仓库 `carry_binding` 的 NULL≠空 约定；如果不算，就是本条记录描述的缺陷。

---

## 4. 何时重开

1. **出现 null 注入事故**：任何一次「字段被写成 null 而用户以为会被拦住」的复盘；
2. **H 落点裁定**（spec §7）或注入物化的任何新一轮改动；
3. **`config.vars` 的 null 语义变化**：若「显式 null」的约定被修订（spec §4.3），本条的取舍需要重算；
4. **`Assign` 基座默认值变化**：`src/gimbal/schema/strategy.py` 的 `required` / `default` 默认值若变动，本记录的三行表要重核。

---

## 修复记录

**2026-11-24 — 裁定落盘（改文档路线；`_assign_strategy` 代码零改动）**

- `run_injection._assign_strategy` docstring 重写：「不可兜」收窄为「变量缺失时兜不住（预处理器先抛 ValueError）」；三种情形逐条写明（缺失 → 预处理 `ValueError` / 非 null → 写 vars 值 / **null → `required:false` 静默写 null = 期望行为**）并记录裁定与理由（NULL≠空 约定同向）。
- 新增裁定钉 `tests/test_run_injection.py::test_template_null_var_writes_null_silently`（显式 null 变量 → 预处理解析成 None → Assign **PASSED** 且 target 落 null）；既有 `test_assign_shape_carries_literal_fallback_for_reference_shapes`（`${...}` 类补键形状）自此为契约钉。
- 编辑器 `AssertionRegistryEditor.vue` `valueRefNote` 的 `${...}` 分支补第三种结局文案（「变量恰好是 null → 把 null 原样写入字段」）；`ARE-5b` 断言同步（注记须含 null 结局、仍不得搬 `$.` 类「兜底」叙述）——「与后端同一份语义、两处必须同改」头注纪律履行。
- §1 三行表继续成立：「补键后（现状）」列 = 裁定后的期望列；「不补键」列降格为历史反事实。§4 重开条件不变。
- 范围边界遵守：`$.` 类补键未动（裁定明文不顺手改）。
