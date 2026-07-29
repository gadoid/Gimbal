# EndpointSpec V2 待启动项

> 状态：草稿（未启动）
> 最近修订：2026-07-29
> 影响范围：`gimbal_plate/schema/endpoint/**`
> 关联：[ENDPOINT_SPEC_V1.md](ENDPOINT_SPEC_V1.md) · [ROADMAP.md](ROADMAP.md) · [FILE_LAYOUT.md](FILE_LAYOUT.md) · [MIGRATION_PLAN.md](MIGRATION_PLAN.md) · [README.md](README.md)

---

## 0. 说明

本文档承载 V1 规格中已声明但本期未实装、推迟到二期评估的项目。来源是 [ENDPOINT_SPEC_V1.md §7.2](ENDPOINT_SPEC_V1.md) 与该文档 §2.3 关于 `version` 兼容分支的占位说明。

V1 本期不再维护"待实装"清单。所有推迟项以本文档为单点源；`ENDPOINT_SPEC_V1.md §7.2`、`ROADMAP.md §4` 末尾重复声明已删除，改为指向本文档。

实现前置已分别挂在每一条下；启动任一条之前须先解决其前置。

---

## 1. version 与兼容性

V1 `EndpointSpec.version` 默认 `"1.0.0"`，字符串自由（无 semver 校验）。V2 启动时需先决定以下两件事的边界，再立项实装：

- **version 格式严格度**：`x.y.z` 三段，还是允许 pre-release / build metadata（如 `1.2.0-rc.1`）。
- **跨 version 的兼容机制**：当 `version` 从 `1.x` 走到 `2.0.0`，旧 EndpointSpec 数据如何被新代码识别与转换——是否需要 `EndpointSpec.from_v1(...)` 之类的工厂、`schemaVersion` 顶层 discriminator、迁移脚本。

V1 §2.3 提到的 "Migrations 章节" 不在 V1 中实装；它属于本文档的课题范围（`version` 1.x → 2.0 兼容分支），不属于数据迁移。`plate` 不存在存量 yaml/json 使用方（[MIGRATION_PLAN.md §4](../MIGRATION_PLAN.md) 已声明），无历史内容需要搬迁。

实现前置：

1. 确认 `version` 形态学（semver 是否含 pre-release）。
2. 确认"跨 version 数据转换"是否有真实需求；若没有，本条降级为"只实装 semver 格式校验"，兼容分支保持"不做"。

---

## 2. 字段约束（从 V1 §7.2 迁移）

下列 5 条均为 V1 规格里 §4 / §5 已经声明、§7.2 表中归入"未实装"的字段约束。每条挂"为何推迟"与"实现前置"——前置不解决前不动代码。

### 2.1 `EndpointSpec.version` 符合 semver

- **V1 出处**：[ENDPOINT_SPEC_V1.md §2.2](ENDPOINT_SPEC_V1.md) 表格最后一行；§7.2 表第 1 行。
- **V1 现状**：`version: str = "1.0.0"`，接受任意非空字符串，未做格式校验。
- **实现前置**：
  1. 完成本文档 §1 第 1 步（决定 semver 是否含 pre-release）。
  2. 决定校验是 Pydantic `field_validator`（构造期）还是序列化期（`model_serializer`）。
  3. 锁测试：合法/非法各一组；序列化往返需保留合法 version。

### 2.2 `RequestSpec.body_type` / `model` / `schema_` 的互斥约束 — **已实装**

- **V1 出处**：[ENDPOINT_SPEC_V1.md §4.1](ENDPOINT_SPEC_V1.md)（两条约束）。
- **V1 现状（实装前）**：`RequestSpec(...)` 任意组合均接受，模型层不做互斥。
- **约束本意**：
  - 规则 A：`body_type="none"` 时 `model` 与 `schema_` 都应为 None。
  - 规则 B：`body_type ∈ {json, form, multipart, raw, binary}` 时 `model` 或 `schema_` 至少一个非空。
- **实装落点**：
  - `schema/endpoint/io_spec.py::RequestSpec._validate` —— Pydantic `model_validator(mode="after")`，构造期校验。
  - 规则 A：`body_type="none"` 且 `model is not None` → 拒；同条件 `schema_ is not None` → 拒。
  - 规则 B：`body_type != "none"` 且 `model is None and schema_ is None` → 拒。
  - **附带修复**：同时为 `RequestSpec` / `ResponseSpec` 的 `model_config` 启用 `populate_by_name=True`，使 Python 端可直接用 `schema_=...` 构造（修复 `extra="forbid"` + alias 组合下 Python 字段名被误拒的可用性 bug）。
- **决策拍板**：
  - Q1=a：规则 A 硬拒。
  - Q2=b：规则 B "非 None" 即可。
  - Q3=b：model 与 schema_ **不强制互斥**，可并存；语义上 model 优先（`json_schema()` / `validate_body()` 均先看 `model`），`schema_` 仅作序列化/展示补充。
  - Q-A=a2：空 dict `{}` 在规则 A 的"必须为空"上下文中视为合规（不视为"非空"）。
  - Q-B=b1：空 dict `{}` 在规则 B 的"非空"上下文中视为合规（类型非 None 即满足）。
- **`schema_` 字段别名桥接**：Python 构造端用 `schema_=...`（字段名），跨进程 JSON 形式用 `"schema"`（alias），pydantic `populate_by_name=True` 自动桥接。
- **V1 §4.1 对应"未实装"标记已翻为"已实装"**，并补全"model 与 schema_ 可并存 + model 优先"语义说明。
- **测试覆盖**（`tests/plate/test_schema_endpoint.py::TestRequestSpecBodyTypeValidation`）：
  - 规则 A 正向 / 反向（model / schema_ 各一组）。
  - 规则 B 正向（仅 model / 仅 schema_ / 并存 三种合法形态）。
  - 规则 B 反向（两者都 None 拒）。
  - 决策 Q-A a2 + Q-B b1 的边界用例（空 dict `{}` 通过校验）。

### 2.3 `ResponseSpec.assertable_fields` 路径必须在 `fields` 中存在 — **已实装**

- **V1 出处**：[ENDPOINT_SPEC_V1.md §4.2](ENDPOINT_SPEC_V1.md) 约束行；§7.2 表第 3 行。
- **V1 现状（实装前）**：`assertable_fields=['does.not.exist']` 接受，不与 `fields` 交叉校验。
- **实装落点**：
  - `plate/utils/path.py` —— `is_valid_path` / `normalize` / `last_segment` 三个纯函数。
  - `plate/utils/jsonpath.py` —— `gimbal/utils/jsonpath.py` 的同期拷贝，零依赖、互不引用。
  - `schema/endpoint/io_spec.py::ResponseSpec._validate` —— `assertable_fields[i]` 经 `normalize` 后与 `{fields[j].path 归一}` 求交，缺失项整体报一条 `ValueError`；空 `assertable_fields` / 空 `fields` 跳过校验。
  - V1 §4.2 / §4.3 对应"未实装"标记已翻为"已实装"。
- **`path` 语法决策（已拍板）**：
  - 风格：`JSONPath`，须以 `$` 领头（`$.field` / `$.a.b.c` / `$.items[0]` / `$['key with space']` 等）。
  - 双形态并存：构造期与查询期均接受 `"order_no"` 与 `"$.order_no"` 两种写法；内部归一到 `$.xxx` 形态做比对。`IOFieldBinding.path` 在内存中保留原值（不动写者），仅在校验时归一。
  - 与 `gimbal.utils.jsonpath` **不建立依赖**：两份实现同期拷贝、各自演进、不互引。
- **字段同名约定**：`name` 必须等于 `path` 的末段 `FIELD` 标识符（实现见 §2.4）；数组下标 / 通配 / 过滤 / 递归下降结尾时无末段标识符，`name` 不与之强约束。
- **测试覆盖**（`tests/plate/test_schema_endpoint.py`）：
  - 合法正向：JSONPath + 双形态并存写法。
  - 字段缺失：`assertable_fields=[$.missing]` 拒。
  - 空字段集 / 空 assertable：合法跳过。
  - 非法 path：`'$.['` / `'order no'` 拒。
  - 末段不一致：name ≠ path 末段拒。

### 2.4 `IOFieldBinding.name` 与 `path` 互斥 — **已实装**

- **V1 出处**：[ENDPOINT_SPEC_V1.md §4.3](ENDPOINT_SPEC_V1.md) 约束；§7.2 表第 4 行。
- **V1 现状（实装前）**：`IOFieldBinding(name='', path='')` 接受。
- **约束本意**：`name` 与 `path` 不可同时为空；同时，按 §2.3 决策，`name` 应等于 `path` 的末段。
- **实装落点**：
  - `schema/endpoint/io_spec.py::IOFieldBinding._validate` —— 复用 §2.3 的 `is_valid_path` / `last_segment`；`path` 非法直接拒；`path` 末段是 `FIELD` 时 `name` 必须等于该标识符。
  - 数组下标 / 通配 / 过滤 / 递归下降结尾时 `last_segment` 返回 `None`，`name` 与之不强约束。
- **测试覆盖**：
  - 短名 / JSONPath / 数组下标 / 嵌套字段 4 种 path 形态。
  - name 与末段一致 → 通过；不一致 → 拒。

### 2.5 `IOFieldBinding.enum` 成员一致性 — **已实装**

- **V1 出处**：[ENDPOINT_SPEC_V1.md §4.3](ENDPOINT_SPEC_V1.md) 约束；§7.2 表第 5 行。
- **V1 现状（实装前）**：`enum=['a','b']` 配 `default='z'` 接受，不校验。
- **约束本意**：`enum` 非空时，`default` / `example` 必须在 `enum` 中。
- **决策拍板**：
  - **Q1=b**：严格 `==`（Pythonic 默认）。理由：enum 的真实生效点是字符串传输阶段（前端会把 bool/int/float 统一转字符串），plate 不替用户管 Pythonic 类型互认语义。`True==1` / `1.0==1` 这种隐式互认在契约层不拦，交给业务执行时的字符串校验兜底。
  - **Q2=a**：`enum` 为 `None` 或 `[]` 视为"未声明可选值清单"，跳过校验（填空风格自由）。理由：`IOFieldBinding` 的 `enum` 字段本身不是必填项——文本字段 / 时间戳字段 / ID 字段本就没有"可选值清单"可言；强制 enum 必填会污染简洁写法。
  - **Q3=b**：enum 元素可以是任意 Python 值（含 list / dict 等可变容器），用 `==` 比对内容，不强制冻结。理由：enum 是声明不是配置，不应增加用户学习成本。
  - **Q4=a**：`default` 与 `example` 同等严格，都参与校验。理由：`example` 也会被前端拿去预填表单/展示示例，默认宽松会让"示例值不在选项里"的契约 bug 浮现。
  - **Q5=a**：构造期校验（`model_validator(mode="after")`），与 §2.2 / §2.3 / §2.4 风格一致。
  - **Q6=a**：enum 中允许重复元素，不去重。理由：V1 §4.3 未要求去重；重复 enum 是 LLM 生成的常见 bug 源但**不在本规范范围内**，留待后续如出现真实问题再扩规则。
- **实现细节**：`default` / `example` 字段值是 `None`（默认值）时跳过该项校验，避免 `default=None` 误拒。
- **实装落点**：`schema/endpoint/io_spec.py::IOFieldBinding._validate` —— 在 path 校验之后追加 enum 校验块。逐项遍历 `("default", self.default)` / `("example", self.example)`，任一不在 enum 中则抛 `ValueError`。
- **V1 §4.3 对应"未实装"标记已翻为"已实装"**，并补全上述决策语义说明。
- **测试覆盖**（`tests/plate/test_schema_endpoint.py::TestIOFieldBindingEnumValidation`，13 个用例）：
  - Q2 正向：`enum=None` / `enum=[]` 跳过校验（含 `default` / `example` 任意值）。
  - Q4 正向：enum 非空 + default / example 都在 enum 中 → 通过。
  - Q4 反向：default 不在 enum 拒；example 不在 enum 拒；双字段独立校验（default 通过不代表 example 通过）。
  - Q1=b 严格 `==`：bool/int 互认通过；float/int 互认通过；str/int 不互认拒。
  - Q3=b：enum 元素为 dict 时按内容 `==` 比对通过。
  - Q6=a：`enum=["A","A","B"]` 重复元素不拒。
  - `default=None` 默认值跳过校验。
  - 综合：`RequestSpec(fields=[IOFieldBinding(...)])` 嵌套校验透传。

---

## 3. 实现顺序建议（剩余项）

仅作启动参考；任何一条单独启动都必须先把该条的前置解决掉。§2.2 / §2.3 / §2.4 / §2.5 已实装，退出待办队列。

1. **§1 version 与兼容性** —— 单独立项，先定 version 形态，再决定 §2.1 是否并入同一 PR。
2. **§2.1 `version` semver 校验** —— 跟随 §1 决策启动。

---

## 4. 验收（同 V1 §8 风格；待启动时逐项打勾）

- [x] §2.3 启动：`assertable_fields` 路径一致性校验生效。
- [x] §2.4 启动：`name` / `path` 互斥生效。
- [x] §2.2 启动：`RequestSpec.body_type` / `model` / `schema_` 互斥生效。
- [x] §2.5 启动：`enum` 成员一致性生效。
- [ ] §1 启动：`version` 形态与兼容机制拍板（文档化）。
- [ ] §2.1 启动：`version` semver 校验生效。
- [x] V1 §4 / §5 中 path 相关约束行的"未实装"标记全部移除。
- [x] `tests/plate` 用例在 V2 实施范围内对应更新，回归通过。

---

## 5. 不做（继承 V1 §7.1）

V2 仍不引入 `FieldBinding` / `EndpointDoc` / `EndpointCategory` / `mutates_state` / `frozen dataclass` / `EndpointKey` / `Protocol hook` / `server` / `SDK` / `MCP` / C3 平台渲染视图。详见 [ENDPOINT_SPEC_V1.md §7.1](ENDPOINT_SPEC_V1.md)。
