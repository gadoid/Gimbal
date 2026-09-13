# 阶段二待修：`exists` 兜底的「属性洞」（Z1）

> **模块**：`gimbal-platform/backend`（判定面）+ 引擎写侧
> **状态**：**行为已收口**（阶段二 Task 6：收紧非 dict 宿主 + 写侧按同一判据拦截）；**公开承诺文本待用户过目**（见文末 [修复记录](#修复记录) §4）
> **来源**：`docs/superpowers/specs/2026-09-12-architecture-convergence-design.md` §6.3 / §7（Z1）
> **适用范围**：`run_injection._path_resolvable` 的 `exists` 兜底 —— dispatch 侧悬空判定与注入物化。
>
> 以下正文是**修复前**的记载（保留历史）。失效的行号已按符号改指；被裁定作废的
> 「待裁定」清单见 §3 顶部的指引与文末 [修复记录](#修复记录)。

---

## 0. 现状

判定面（spec v3.1 §2.1）由 `_path_resolvable` 给出，末句是一条**兜底**：

```python
# src/gimbal-platform/backend/app/services/run_injection.py（_path_resolvable 的兜底，修复前形态）
for form in (jsonpath, _template_path(jsonpath)):
    if form in universe:
        return True
return exists(body or {}, jsonpath)
```

`exists` 走 `_eval_nodes`，其 FIELD 分支对**非 dict** 的容器改用 `getattr`：

```python
# src/gimbal-platform/backend/app/services/jsonpath.py:381-389
else:
    # 修复 #32：显式 try/except 而非 hasattr（hasattr 会触发 __getattr__…）
    try:
        val = getattr(data, node.value)
    except AttributeError:
        return []
return _eval_nodes(val, rest)
```

于是「body 里某字段是**字符串**、条目路径继续往下写一段」时，`getattr` 命中的是 **str 的绑定方法**，结果非空 ⇒ `exists` 返回 `True`。

本会话实测（backend 目录下直接调用 `app.services.jsonpath`）：

```text
exists({'note':'hello'}, '$.note.replace') -> True
exists({'note':'hello'}, '$.note')         -> True
exists({'items':[]},     '$.items')        -> True      # 见 §4：这一条是「有意」的方向
set_value({'note':'hello'}, '$.note.replace', 'X') -> {'note': {'replace': 'X'}}
```

---

## 1. 缺陷

**机制**：`$.<str 字段>.<任意 str 属性名>`（`replace` / `upper` / `format` / `split` …）在后端一律判**活**，而前端判**死**（见下），且这个「活」会一路走到写侧把字符串**改形**。

**触发条件**（三条同时成立）：

1. 某步 `request.body` 的某个键是**字符串**（或任何有同名属性的非 dict 值）；
2. 某断言的条目 `path.jsonpath` 写的是 `$.<该键>.<str 属性名>`（如 `$.note.replace`）；
3. 该条目**绕过编辑器**被下发 —— 直接 `POST /api/runs` 带 `injectionEntryIds`，或脚本/其它客户端。

**为什么第 3 条是必须的**：编辑器侧判死（灰显、不可勾选），所以 UI 路径拦得住。前端 `pathResolvable`（`frontend/src/utils/assertion-registry.ts`）只做**两次成员测试**（`injectablePathSetOf` 的实例 / 模板两形态；**前缀扫描已随声明半物化退场**，见 `docs/adr/0003-retired-features-log.md` 第 10 行），而那一集合的 body 来源是 `fieldPathsOf`（`frontend/src/utils/dataset-segments.ts`）—— 它只把**标量**收成叶子（`$.note`），**永不产出** `$.note.replace`。

**影响**：条目通过悬空检测 → 被物化 → 请求体被**静默改形**。链如下：

1. `compose_injection_scenario` 把条目路径拼成注入目标
   （`run_injection.py:271-276`：`target = "$.request_body" + jp[1:]` ⇒ `$.request_body.note.replace`）；
2. 引擎 `Assign` 写该目标：`write_scratch` → `StepScratch.set`（`src/gimbal/context/step.py:37-54`）→ `set_value`；
3. `_set_at` 的 FIELD 分支遇非 dict **静默换成空 dict**
   （`src/gimbal/utils/jsonpath.py:449-454`：`if not isinstance(data, dict): data = {}`）；
4. 结果：`note` 从 `"hello"` 变成 `{"replace": <注入值>}` —— 原字段整体丢失，下游收到一个类型不同的请求体。

即：**不是**「注入没生效」，而是「把用户的字段换成了另一种类型」。这正是 README 对 P0 的定义（静默错误 / 类型错乱）。

---

## 2. 优先级：P0（候选）

- **后果属于 P0 类**：静默的类型错乱 + 字段内容丢失，且没有任何一步报错。
- **触发面窄于典型 P0**：编辑器判死 ⇒ 只有非 UI 下发路径能命中。spec §6.3 因此写作「P0 候选」。
- 结论：**按后果定级 P0**，但修复前必须先做 §3 的裁定 —— 因为修法方向（收紧）与既有承诺冲突，见下。

---

## 3. 待裁定

> 原文见 spec §7：**Z1 `exists` 属性洞** —— *修它意味着**收紧**判定面（与可注入面 spec §5.2「只放宽不收紧」承诺相左）⇒ 需要显式裁定与 spec 修订。*

**裁定已作（2026-09-13），本节保留为修复前的决策清单**：结论 = **收紧 + 写侧拦截，两者都做**（不是二选一；spec §4.2 / §4.3），实装与残留见文末 [修复记录](#修复记录)。下面第 2 条要求的承诺修订稿**已写好但未落盘**（待用户过目，见修复记录 §4）。

留给维护者的决策（**本记录不下结论**）：

1. **收紧 or 保留？** 收紧 = 让 `exists` 兜底不再穿过非 dict 值（例如兜底前先判 `isinstance(data, dict)`，或把兜底改为「精确存在性」而非「属性可达性」）。保留 = 接受该洞，改为在**写侧**拦截（物化前判目标路径的类型）。
2. **若选收紧**：spec `2026-09-12-injectable-path-surface-design.md:105` 的承诺「只放宽、不收紧 —— 没有任何路径会变得更严，不会出现『原本能跑的条目突然被判死』」必须**修订**（该条是对用户的公开承诺，见同文件 `:104` 的存量条目后果说明），并在发布说明里写明哪一类路径将新判死。
3. **若选保留**：必须给出写侧防线（否则「越界/改形」仍是静默的），并明确该洞是「已知且接受」。

**相关的既有事实**（供裁定参考，不是结论）：

- 兜底对**空容器**的宽容（`body={"items":[]}` 的 `$.items` → True）是**有意保留**的行为，方向是「少判死」，spec 明文容许（`run_injection.py:166-168`）。收紧时**不要把这一类一起收掉** —— 它与属性洞是两件事。
- 前端 `registryIssues` 与后端 `entry_issues` 是两份实现（H 项的结构证据；spec §7 H 待裁定），本洞是「同一契约两语言各写一版」的下游后果之一。

---

## 4. 何时重开

1. **非 UI 下发被真实使用**：出现脚本 / 第三方客户端调 `POST /api/runs` 带 `injectionEntryIds` 的场景；
2. **H 落点裁定**（spec §7）—— 判定面收为单一定义那一轮，本洞必须一并处理；
3. **spec 修订**：`injectable-path-surface-design.md` §5.2 的「只放宽不收紧」被任何原因修订时；
4. **审计发现改形报文**：任何一次「请求体类型与编辑器所见不一致」的故障复盘指向注入路径。

---

## 修复记录

**阶段二 Task 6（Z1：收紧 `exists` 兜底 + 写侧拦截）**，提交 `a4d49b2`（行为）与
`9cf5e5f` / `9c472f6` / `181c3b2`（复核整改三轮）。
裁定 = **两者都做**：判定侧收紧 **+** 写侧按**同一判据**拦截（spec §4.2 / §4.3）——
正文 §3 的「收紧 or 保留」二选一清单由此作废。

### 1. 现在是什么

- **判定侧**（`run_injection._path_resolvable`）：两次成员测试之后，兜底**先过两道闸** ——
  `if not isinstance(body, dict): return False`（非 dict 宿主不再走 `getattr` 的**属性可达性**），
  再过 `_host_conflict(body, _body_target(jsonpath))`（宿主容器不称职 / 形状写不进去）。两闸都过才落回
  `exists(body, jsonpath)`。⇒ `exists({'note':'hello'}, '$.note.replace')` 这类**不再判活**，
  条目在 `entry_issues` 里得到**既有的** `path-unresolvable`（skip + 告警）——**不新错误码、不 500**。
- **写侧**（`compose_injection_scenario`）：物化前用**同一个** `_host_conflict` 判据；命中即**不落 Assign**
  并告警（「目标 … 不可安全物化」）。判定与写侧共用判据、共用 `_body_target` 拼出的 `target`
  （该函数 docstring 明文「判定与物化共用（Z1）」），两侧不可能分叉。
- **空容器宽容按裁定保留**（spec §4.2 的「唯一保留项」）：`body={"items":[]}` 的 `$.items` **仍判活** ——
  空容器的宿主**就是 dict**，与「非 dict 宿主」是两件事，收紧**没有**把这一类一起收掉。
- **触发面**：收紧后**编辑器本就判死**（前端 `fieldPathsOf` 只产标量叶子，永不产出 `$.note.replace`），
  故只有**绕过 UI 的下发**（直接 `POST /api/runs` 带 `injectionEntryIds`、脚本或其它客户端）会命中 ——
  而后果已从「请求体被静默改形」变成「该条目被判悬空并跳过（带告警）」。

### 2. 正文被作废的陈述

1. **§0 的兜底代码**：`return exists(body or {}, jsonpath)` → 现在是两道闸之下的 `return exists(body, jsonpath)`
   （顺带：兜底不再用 `or {}` —— §5 的显式判别）。片段保留为**修复前形态**，行号已改按符号指。
2. **§2「P0（候选）」** → 该后果**已不可达**；P0 的定级依据（静默类型错乱）**已消除**而不是转移：
   写侧那道闸是结构性的（同一判据），判定侧将来若再放宽也拦得住。
3. **§1 第 3 条的前端解释**：`pathResolvable` 现在只做两次成员测试（**前缀扫描已随声明半物化退场**，
   `docs/adr/0003-retired-features-log.md` 第 10 行）；「前端判死」的结论不变（`fieldPathsOf` 只产标量
   叶子这一点没变）。
4. **§3 的「本记录不下结论」** → 已下结论（见上），清单保留为历史。

### 3. 本条关闭

正文 §4 的重开条件：第 1 条（非 UI 下发被真实使用）与第 4 条（审计发现改形报文）针对的**是那个洞**，
现已不可达 ⇒ 不再适用于本条；若将来出现**新的**改形路径，按新记录处理。第 2 条（H 落点裁定）与
第 3 条（spec 修订）仍然有效，且第 3 条**正在办理**（见下）。

### 4. 外溢：公开承诺文本**尚未**落盘（待用户过目）

正文 §3 第 2 条要求的承诺修订 ——
`docs/superpowers/specs/2026-09-12-injectable-path-surface-design.md` §5.2 的「只放宽、不收紧」——
**修订稿已写好但未提交**：改的是**对用户的公开承诺**，须用户过目后再落盘（阶段二 Task 9 的第 12 项；
措辞见 `.superpowers/sdd/2026-09-13-judgment-surface-convergence/task-9-report.md` §2）。
⇒ 本记录的状态因此写作「行为已收口，**承诺文本待过目**」，不写成彻底关闭。
