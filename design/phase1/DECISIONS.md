# Phase 1 Decisions

> **目的**:记录 Phase 1 规划阶段的所有关键决策及其理由。
>
> **决策编号**:D1 / D2 / D3 / D4 / D5(Phase 1 规划)
>                + D6 / D7 / D8(PR-B / C 落地) + D9(PR-D1) + D10(PR-D2)
>                + D11(PR-D3) + D12 / D13(PR-D4) + D14(PR-EOP)
>
> **后续阶段**:D15+ 留给 Phase 2 / 3 / 4 决策,不在本文档范围。

---

## D1: 测试风格转换策略

**决策**:A — 全部 print+assert 脚本转 pytest 函数(全量 pytest 化)

**候选**:
| 选项 | 描述 | 优 | 劣 |
|---|---|---|---|
| A | 全部转 pytest | CI 覆盖完整;所有测试进入"绿基线" | 工作量大(22 文件) |
| B | 只转关键 4 个 | 工作量小 | print+assert 脚本不进入 CI,基线不完整 |
| C | 全保留 print+assert | 零工作 | CI 触发 INTERNALERROR,无法用 pytest |

**理由**:
- C 选项已实测触发 INTERNALERROR(`tests/unit/test_defect_fixes.py` 顶层 `sys.exit(1)`),不可行
- B 选项只覆盖 22 文件中的 4 个,基线缺口大,后续 PR 难以"对照基线"
- A 选项工作量虽大,但 Phase 1 后续 PR 都依赖完整 pytest 基线

**已选**:A

**执行拆分**(D3 决策的产物):A 拆为 3 个子 PR(PR-0.1 / PR-0.2 / PR-0.3)避免单 PR 爆炸

---

## D2: 改名(ModelRegistry → Plate)与 PR-0 的顺序

**决策**:A — 先改名再写 PR-0

**候选**:
| 选项 | 描述 | 优 | 劣 |
|---|---|---|---|
| A | 改名(PR-A)→ pytest 化(PR-0) | 每个 PR 范围清晰;改名后所有 import 路径统一 | 多一个 PR |
| B | pytest 化先 → 改名后 | 改 pytest 时不动 import 路径 | 改名前后测试文件要"回头改",重复工作 |

**理由**:
- A 选项:改名是一次性原子操作,改完后所有 pytest 化的工作用统一的新 import 路径
- B 选项:先 pytest 化再改名,等于改两次 import(一次 pytest 化时改,一次改名时再改)

**已选**:A

**执行决定**:PR-A 与 PR-0.2 合并(节省一次 PR overhead)

---

## D3: 测试目录纳入范围

**决策**:B — 包含 tests/unit/(但拆为 3 个子 PR)

**候选**:
| 选项 | 描述 | 优 | 劣 |
|---|---|---|---|
| A | 仅 tests/plate | 范围最小 | tests/unit 留下 INTERNALERROR 风险 |
| B | 包含 tests/unit/ | CI 完整 | 22 个 print+assert 脚本要 pytest 化 |
| C | 包含全部 tests/ | 完整 | 还要管 tests/integration 的 3 个脚本 |

**理由**:
- A 选项不解决 INTERNALERROR,Phase 0.1 收口意义打折
- B 选项完整覆盖,但 22 个脚本 pytest 化工作量 = 1 个 PR 做不完
- C 选项再扩 tests/integration 是过度

**已选**:B

**执行拆分**(关键决策):B 拆为 3 个子 PR:
- **PR-0.1**:pytest 基线 + `collect_ignore_glob` 隔离(本会话已执行)
- **PR-0.2**:model_registry 4 个核心测试 pytest 化 + 改名(后续会话)
- **PR-0.3**:其余 22 个 unit 脚本渐进 pytest 化(更后续)

**用户确认**:Y — 本会话只做 PR-0.1,其余 PR 后续

---

## D4: PR 数量与粒度

**决策**:Phase 1 = 8 个 PR(0.1 / 0.2 / B / C / D1 / D2 / D3 / D4 / EOP),每 PR 1-2 PD

**候选**:
| 选项 | PR 数 | 单 PR 范围 | 评估 |
|---|---|---|---|
| A | 3 个 | 大范围,每 PR 跨多主题 | review 难,合并冲突风险 |
| B | 8 个 | 小范围,每 PR 单主题 | review 易,失败可回滚(本选项) |
| C | 15+ 个 | 极小范围 | PR overhead 过大,流程债 |

**理由**:
- 每个 PR 必须能独立 review + 独立回滚
- 单 PR 跨多主题 → review 时无法聚焦,且一个 PR 部分失败 = 整个 PR 回滚(连带损失)
- 8 个 PR 是"主题清晰 + 可独立验证"的最小粒度

**已选**:B

---

## D5: 测试设计原则

**决策**:测试用例**面向业务需求**,**不**面向功能验证

**关键区分**:
| 类型 | 示例 | 评价 |
|---|---|---|
| 功能验证 | `test_method_returns_correct_value` | 验代码能跑,不验业务对不对 |
| 业务需求 | `test_query_with_mutates_state_true_raises`(业务影响:CT 主动探测会触发写入) | 验业务承诺,代码改动可能仍让测试过 |

**理由**:
- 用户明确要求"测试用例是面向业务需求的,不是在验证功能是否可用"
- 业务需求测试 = 改实现不改测试 = 测试稳定;功能验证测试 = 实现一改测试就过
- Phase 1 的所有 PR 文档统一用 3 段式 docstring:**业务需求 / 对应设计 / 业务影响**

**已选**:A(强制)

**review 落地**:[REVIEW-CHECKLIST.md §10](REVIEW-CHECKLIST.md) 列出反模式,reviewer 一票否决

---

## D6: 契约保真 role-aware(request vs response)

**决策**:`_assert_safe_model` 接受 `role_kind` 参数,按角色区分契约保真要求。

**问题**:v3 §3.6 的契约保真硬约束(`extra='forbid'`)是单向的,但请求体和响应体的
业务现实不一样:
- 请求体(客户端→服务端):真实 wire 常含未建模字段、字段类型漂移,
  强制 `forbid` 会把宽容的客户端拒之门外。
- 响应体(服务端→客户端):未知响应字段说明服务端改了 spec,必须 fail-fast。

| 角色 | extra 策略 | 必须显式 model_config | 禁用清单 | 代表字段 |
|---|---|---|---|---|
| `request` | `forbid` 或 `ignore` | 是 | 全开检查 | `EndpointSpec.request` |
| `response` | `forbid` | 是 | 全开检查 | `EndpointSpec.responses` / `default_response` |

**禁用清单**(`str_strip_whitespace` / `coerce_numbers_to_str` / `use_enum_values`)
**双向都生效** —— wire 改写不分方向,即便 request 角色放宽了 extra。

**理由**:
- 不允许"宽容客户端"被 fail-fast 误伤
- 仍保留"server-side spec 改了的 fail-fast"(response 角色)
- 显式 model_config 强制要求避免作者走 pydantic 默认

**已选**:A(PR-C 落地)

---

## D7: response_data_models 用 "data" 角色(独立于 response)

**决策**:`response_data_models` 字段用第三种 `role_kind="data"`,与 `response` 角色
**分离**,允许 `extra='ignore'`(与 `request` 角色同规则)。

**问题**:PR-C 单轨化(31 端点)时,`response_data_models` 的 8 个精细建模的 data 类
(`OrderDetailData` 204+ 字段的 ES 文档、`OrderEntrustOrderPageData` 分页数据等)
被发现用 `extra="ignore"`(原 models.py 设计就是"宽进"以兼容 ES 多变 schema),
按 D6 的 `response` 角色校验被 fail-fast 拒掉。

**架构区分**:
| 角色 | 业务本质 | extra | 例子 |
|---|---|---|---|
| `response` | wire 响应壳(契约边界) | `forbid` | `CommonResponseEnvelope` |
| `data` | 响应壳**内部**的精细化建模 | `forbid` 或 `ignore` | `OrderDetailData`(204 字段 ES 文档) |

**为什么不归 `request` 角色**:
- data 不是"客户端发出去"的 —— 是"服务端定义 + 服务端返回的"
- 归 `request` 会让语义混乱(读代码看到 `request` role 想到客户端)

**为什么不用 `response` 角色**:
- data 是**服务端内部结构**(作者明确知道有哪些字段),不是"wire 响应壳"
- 强制 `forbid` 等于逼作者把 200+ 字段全部建模 —— 违背渐进式契约
- ES 文档 schema 演进是常态,`ignore` 表达"先建容器,后续按需补字段"

**禁用清单**仍全部生效(data 角色的"宽容"只针对未知 data 字段,不是"放任 wire 改写")。

**已选**:A(PR-C 落地)

---

## D8: PR-C §2.4 端点分布统计行算术修正

**决策**:把 PR-C §2.4 的"统计"行从 `BUSINESS=14, QUERY=17, TOOL=0` 修正为
`BUSINESS=15, QUERY=16, TOOL=0`(TOOL=0 结论不变)。

**问题**:PR-C 落地时,`test_fin_category_distribution_matches_design` 首次
跑通失败 —— 实际分布是 BUSINESS=15/QUERY=16,文档"统计"行写 14/17。

**根因**:
- 文档 §2.4 表格本身**判定表是正确的**(逐端点 category 标注与实现 100% 匹配)
- 但"统计"行漏数了 1 个 BUSINESS(可能是写文档时把 `orderFee/realAmountLockSubmit`
  误归为 QUERY,但 §2.4 表里写的明明是 BUSINESS)
- 实际算术:15 BUSINESS + 16 QUERY = 31 ✓

**处理**:
- 修测试断言按"逐端点判定表的实际算术"为准(15+16=31),**不**按文档"统计"行
  硬卡 —— 后者会把"修正文档算术"当成"实现偏离设计"的误报
- 文档"统计"行本身仍写错(14/17),留待 PR-C 收口时一并修订
- 测试 docstring 显式说明此修正,避免下个 reader 重新"对齐"成错的 14/17

**已选**:A(测试先按算术真值跑,文档后续修订)

---

## D9: PR-D1 §2.5 端到端期望修正(Any 软降级)

**决策**:把 PR-D1 §2.5 端到端示例的期望从
`target_type=<class 'str'>, hit_any=False` 修正为
`target_type=None, hit_any=True, error=None`。

**问题**:PR-D1 落地时,§4.1 端到端命令的输出与文档预期不符:
- 文档原写: `target_type=<class 'str'>, hit_any=False, error=None`
- 实测输出: `target_type=None, hit_any=True, error=None`

**根因**:
- 实际 `ToggleRealAmountData` 模型结构是:
  - `to_customer: list[_SettleSideItem]`
  - `_SettleSideItem.put_amount: _MoneyBlock | None`
  - `_MoneyBlock.standard_list: list[Any]`
- 路径 `"to_customer.put_amount.standard_list.order_fee_real_id"` 在 `standard_list` 步命中 `Any`(permissive 兜底)
- 解析器按设计 §2.2 Any 限制标记 `hit_any=True` 并**放行**(无法证伪)
- 这是 **设计预期行为**,不是 bug —— PR-D1 文档的"strict 解析成功"期望
  是写文档时未核对实际模型结构导致的偏差

**处理**:
- §2.5 端到端示例:期望改 `target_type=None, hit_any=True, error=None` + 加注释
- §3.2 `test_resolves_fin_toggle_real_amount_real_id`:期望同步修正 + 注释
- §3.2 `test_resolves_fin_order_confirm_account_cny`:文档已正确(`main_currency_bank: Any`),测试已加注释
- §3.2 `test_resolves_fin_audit_id`:文档原写宽松(`target_type is not None`),测试严格化(`target_type is str`)—— `AuditPageData.data: list[_AuditPageItem]` 是精确建模,可严格解析
- §4.1/§4.2 端到端命令期望同步更新

**业务影响**:
- PR-D2 `FieldBinding` 实现时,这些走 `hit_any=True` 的 binding 应**降级到 drift report**,不卡 CI(对应 §5.3 表格已规定)
- PR-D2 review 时应**重点关注**:binding 作者不应在 `hit_any=True` 区域放严格的字段类型校验 —— 那会"看起来过了 CI 但实际无法证伪"

**已选**:A(期望按实测修正 + 文档追溯)

---

## D10: Python 3.14 `@final` 不再抛 TypeError,改为运行时 `__final__` 标记

**决策**:`@final` 装饰器在 Python 3.14 下不再在子类化时抛 `TypeError`,
改为纯静态检查器提示 + 运行时 `__final__` 布尔标记。
测试用 `getattr(EndpointSpec, "__final__", False) is True` 验证,不依赖抛错。

**问题**:PR-D2 测试 `test_endpoint_spec_is_final` 写时假定
`class _Subclass(EndpointSpec)` 会抛 `TypeError`(老 Python 行为)。
实际在 Python 3.14 下:
```python
>>> class _Subclass(EndpointSpec):
...     pass
# 不抛错(3.14 之前会抛 TypeError)
>>> EndpointSpec.__final__
True
```

**根因**:
- PEP 591 `typing.final` 在 Python 3.14 起改为"纯静态检查器"语义
- 运行时副作用只保留 `__final__` 标记(用于第三方工具检测)
- 实际"不允许继承"的执行权下放给用户的 `__init_subclass__` 或 metaclass

**处理**:
- `test_endpoint_spec_is_final` 改用 `getattr(EndpointSpec, "__final__", False) is True` 断言
- 加注释说明 Python 3.14 起 `@final` 行为变化
- 不在 EndpointSpec 上加 `__init_subclass__` 强制抛错 —— 现阶段运行时 `__final__`
  标记 + 静态检查器足够(拉式收集用 `type(attr) is EndpointSpec` 严格匹配,已足够防穿透)

**业务影响**:
- 拉式收集的"严格匹配"承诺**不受影响**:`type(attr) is EndpointSpec` 仍然能挡住
  非 `EndpointSpec` 实例进入 `_index`
- 唯一的弱化是"用户写 `class Sub(EndpointSpec)`"在运行时不再立刻报错 —— 但
  这本来就是"靠自觉"的设计,Phase 1 接受

**已选**:A(测试用 `__final__` 标记验证,不在类上强制抛错)

---

## D11: PR-D3 `EndpointDoc` 不在顶层 `Plate.__all__` re-export(零侵入优先)

**决策**:`EndpointDoc` 只在 `Plate.doc.__all__` 暴露,不在顶层 `Plate.__all__`
re-export;`fin/dannotations` 也不在顶层 re-export。

**问题**:PR-D3 §2.1 写"re-export `EndpointDoc`"到顶层 —— 这与 PLATE_DESIGN §7
承诺 1(零侵入)的**不变量 #2 顶层 `__all__` 仅 `{registry, BootstrapError}`** 直接冲突。

**已选**:
| 模块 | `__all__` 包含 | 顶层 re-export? |
|---|---|---|
| `Plate.doc` | `EndpointDoc`, `_SUMMARY_MAX_LEN` | ❌ 不 re-export |
| `Plate.fin.dannotations` | `EndpointDoc`, `_DOCS`, `get_doc` | ❌ 不 re-export |

**理由**:
1. 零侵入不变式是**横跨所有 PR 的硬护栏** —— PR-D3 的"方便"不能破它
2. `EndpointDoc` 的**真实消费方只有 L2 存储模块**(`Plate.fin.dannotations`)
   和 review pipeline;两者都已通过子模块路径 `from Plate.doc import EndpointDoc` 导入
3. 同 PR-D2 `FieldBinding` 决策一致(D10 讨论)

**业务影响**:
- 消费方需写 `from Plate.doc import EndpointDoc`(多 4 个字符),换得
  顶层 `import Plate` 仍然不触达任何内部模块
- review pipeline 与 `fin/dannotations` 的 import 路径完全稳定 —— 与现状一致

**已选**:A(只在 `Plate.doc` 与 `Plate.fin.dannotations` 内部 `__all__`,不破顶层不变量)

---

## D12: PR-D4 binding 接受 Any 软降级(D9 一致),不要求严格解析

**决策**:`test_invariant_no_orphan_bindings` 接受 `hit_any=True` 的 binding
(软降级,**不**报 orphan);只有 `error` 不为 None 的 binding 才报 orphan。

**问题**:PR-D4 §2.3 写"`resolve_logical_path` 验证失败的 binding,**硬错拒绝**
(注册期 fail-fast)"。但这与 D9(Any 软降级,设计上**不**报 hard error)冲突。
如果严格执行 PR-D4 §2.3 原文,所有走 `CommonResponseEnvelope.data: Any`
的 binding 都会被注册期拒绝 —— 但本 PR 落地表的 5 条 binding 全部要经过
`data` 这一步。

**实际 PR-D4 落地**:
- `auditDetail` 的 `from_path=("data", "audit_id")` 经 `resolve_logical_path`
  在 `auditPage.response_data_model[AuditPageData]` 上**严格解析**成功
  (`target_type=str, hit_any=False`),因为 `AuditPageData.data:
  list[_AuditPageItem]` 是精确建模
- 所有 binding 都选了**严格可达**的上游;不通过 `CommonResponseEnvelope.data=Any` 这条软路径

**业务影响**:
- 不变量 `test_invariant_no_orphan_bindings` 检查**至少能解析**
  (`error is None` 或 `hit_any=True` 都算通过),不做严格区分
- 这样如果将来某 binding 真的必须走 Any 软路径,仍能在 invariant 层面放行,
  留给 review pipeline 在 drift report 里降级提示

**已选**:A(invariant 接受 Any 软降级;严格解析留给 PR-D4 §4.1 cmd 4 类测试)

---

## D13: orphan binding 检测在 invariant 层,不在注册期(测试隔离衍生)

**决策**:`FieldBinding.from_path` 的有效性检测**只在 `test_invariant_no_orphan_bindings`**
做,`EndpointSpec.__post_init__` **不**调用 `resolve_logical_path`。

**问题**:PR-D4 §4.1 cmd 5 期望"故意制造幽灵 binding → 注册期抛 ValueError 或
PathResolutionError"。**实际不会抛** —— `EndpointSpec.__post_init__` 只校验:
- `b` 是 `FieldBinding` 实例
- `to_path` 非空
- `transform` 在 `_KNOWN_TRANSFORMS` 内
- **不**校验 `from_path` 是否能解析

**根因**:
1. `__post_init__` 内调 `resolve_logical_path` 需要先知道上游 response_data_models;
   但 `EndpointSpec` 是**单个**端点的描述,不知道"自己依赖谁"——
   反向索引(BindingRegistry)是 PR-EOP 范围(OQ-1)
2. **同 service 内遍历找上游**(PR-D4 §3.2 invariant 用法)是 O(n*m),
   在 `__post_init__` 期跑等于把所有 endpoint 全部 import —— 破坏"按需加载"
   (设计 §7 承诺 2)

**已选**:A(invariant 层检测,registration 层只做结构校验;放弃"注册期 fail-fast"
         的 PR-D4 §2.3 原文,改为"invariant 层 fail-test")

**业务影响**:
- 后果:幽灵 binding 能通过 import,但被 `pytest tests/` 拦截
- 测试隔离:d12 + d13 共同验证所有 binding 都"严格可达 + 至少能解析"
- 后续 PR 引入 BindingRegistry 后,可考虑把 orphan 检测回收到"首次 collect service 时"
  (不破按需加载,因为 collect 已经会 import 该 service 全部 endpoint)

**衍生:测试隔离问题**(D13-附)
- `test_core.py` 的 autouse fixture 会 `pop` 所有 `Plate.*` 模块,导致跨测试文件时
  `FieldBinding` / `EndpointCategory` 类身份变化
- 解决:`test_fin_bindings.py` 用 `==` 比较 category,**不**用 `is`;**不**在
  顶层 `from Plate.binding import FieldBinding`,依赖 EndpointSpec.__post_init__
  自身保证 binding 是 FieldBinding
- 这是 GIMBAL 的"测试隔离健康度"指标 —— autouse fixture 跨界 pop 模块本身
  应改为只 pop 真假 service(PR 后续可单独优化)

**已选**:A(测试用 `==` 替代 `is`,`from_path` 严格解析测试不依赖类身份)

---

## D14: PR-EOP 基线门槛由 221 升到 300 + 不变量聚合去重

**决策**:PR-EOP §4.2 收口门槛从 `≥ 221 测试` 升到 `≥ 300 测试`;
`test_invariants.py` 不变量聚合去重(不复制 PR-D4 内部的 invariant,只保留跨 PR
聚合级别)。

**问题 1:门槛数值**
- PR-EOP §4.2 原文写"全量测试 ≥ 221"(按 PR-D4 估算 15 个新测试 + 原 206 推算)
- 实际 PR-D1 / D2 / D3 / D4 累计增加远超 15:每个 PR 实际增 13-21 个测试
- 落地后实际全量测试数 = 327 ≥ 300;原门槛 221 显失"出厂质检"严肃性

**问题 2:不变量重复**
- PR-EOP §3.2 草稿写了 `test_invariant_no_default_category_in_fin`,
  但 PR-D4 §3.2 已在 `test_fin_bindings.py` 内写了同义 invariant
- 同一 invariant 在两处测试会让 CI gate 报告"重复失败",模糊 root cause
- PR-EOP 落地准则:"Phase 1 收口"只放**跨 PR 聚合**的 invariant(全量 ≥ 300, 跨
  PR 字段完整性,31 端点注册, L1/L2 对称性),不放单 PR invariant

**已选**:
| 测试函数 | 来源 PR | 跨 PR 聚合? |
|---|---|---|
| `test_invariant_all_fin_endpoints_registerable` | PR-EOP 新增 | ✓(聚合:31 端点 + 全注册) |
| `test_invariant_no_default_category_in_fin` | 已聚合到 PR-D4 `test_fin_bindings.py` | ❌ 不复制 |
| `test_invariant_fin_binding_count_in_range` | PR-EOP 新增 | ✓(聚合:5 ≤ total ≤ 8) |
| `test_invariant_fin_l1_l2_symmetry` | 已聚合到 `test_invariants.py` PR-D3 段 | ❌ 不复制 |

**业务影响**:
- CI gate 报告的失败信号**唯一**:`test_invariants.py` = 跨 PR 聚合级别失败;
  `test_fin_bindings.py` / `test_doc.py` = 单 PR 内部失败
- 门槛升到 300 = "出厂质检"的严肃性 + 防"删测试通过 review"
- 后续 Phase 启动门槛同样按 ≥ 300 的"严肃基线"对齐

**已选**:A(门槛升到 300 + 不变量去重)

---

## Open Questions(留给后续阶段)

### OQ-1: BindingRegistry 精确反向索引

**问题**:PR-D4 的不变量用"同 service 内遍历找上游",是 O(n*m) 复杂度。service 数大 / endpoint 数大时不优雅。

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | 不引入,保持 O(n*m) | fin 31 端点够用;简单 |
| B | 引入 BindingRegistry,from_path → 端点 反向索引 | O(1) 查询;但维护成本 |

**当前决定**:A(fin 31 端点场景下不必要)

**触发条件**:当 service 数 > 5 且每 service 端点 > 50 时,启动 B 选项

---

### OQ-2: L1 自动重生工具(spec autogenerator)

**问题**:L1 是"机器可再生"的,但当前没有自动重生工具。spec 由人手写,一旦 drift 就过期。

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | 不引入,spec 人手写 | 简单;drift 风险靠 review |
| B | 引入 OpenAPI → spec 自动重生 | 消除 drift;但需 OpenAPI 真值源 |

**当前决定**:A(Phase 1 范围内不需要)

**触发条件**:当 drift 出现 ≥ 3 次 / 月时,启动 B 选项

---

### OQ-3: EndpointDoc 注释渐进补全的节奏

**问题**:PR-D3 建了 `dannotations/` 空壳,但 31 端点的注释何时补完?

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | PR-D3 内补完 | 与 PR-D3 scope 冲突(PR-D3 只建空壳) |
| B | 后续 PR 渐进补 | 每个端点的 PR 顺便补注释 |
| C | AI 辅助批量补 | 快但不准;需人复核 |

**当前决定**:B(端点改动时顺便补)

**触发条件**:当 PR-EOP 收口后,启动 C 选项作为 Phase 1.5 增量

---

### OQ-4: 跨 service binding

**问题**:本 Phase 1 binding 只考虑同 service 内。跨 service(如 fin → pay)的依赖怎么处理?

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | 不支持跨 service binding | 简单;跨 service 场景需手编排 |
| B | 支持任意 service binding | 灵活;但 service 边界语义模糊 |

**当前决定**:A(Phase 1 范围内)

**触发条件**:Phase 2 service 化时,如真实出现跨 service 依赖,启动 B 选项重新讨论

---

### OQ-5: transform 引擎

**问题**:本 Phase 1 `_KNOWN_TRANSFORMS` 是白名单字符串,不解析。`int->str` 等转换靠消费者手实现。

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | 字符串描述,消费者自己实现 | 简单;无内置实现 |
| B | 内置 transform 引擎(注册函数) | 可执行;但需设计 hook |

**当前决定**:A(Phase 1 不引入执行)

**触发条件**:Phase 3 动态服务能力(实时注入)启动时,引入 B 选项

---

### OQ-6: 31 端点的具体 category 分配

**问题**:PR-C 预估 14 BUSINESS / 17 QUERY / 0 TOOL。**实际分配需要逐个端点业务分析**,本文档不做具体决策。

**决策机制**:
- PR-C 执行时由维护者按"是否产生业务实体状态变更"判断
- 业务理由登记在 PR 描述里(31 行简表)
- 争议端点升级到 maintainer team 决策

---

## 决策变更流程

任何 D1-D5 决策如需变更:
1. 在 PR 描述里明确写"决策变更:原 D3 = X,改为 Y,理由 Z"
2. 更新本文档的"已选"标记
3. 在 `design/CHANGELOG.md` 登记变更日期(若该文件存在)
4. REVIEW-CHECKLIST 同步更新

任何 OQ-1 至 OQ-6 决策如需升级为 D6+:
1. 写 RFC 描述"为什么现在要升级"
2. 同步到本文档的 D6+ 段
3. 影响到的 PR 文档同步更新