# Phase 1 Review Checklist

> **目的**:为 Phase 1 的 7 个 PR 提供统一的 review 视角。reviewer 按本清单逐项检查,避免"个人偏好驱动的 review"。
>
> **使用方式**:每个 PR review 时,**逐项**过本清单;不通过的项必须 fix 或写理由说明。

---

## 0. 通用检查项(每个 PR 都过)

### 0.1 文件清单核查

- [ ] PR 范围文件**全部**修改(对照 PR 文档 §2.1 改动文件清单)
- [ ] 没有"夹带"清单外文件的修改(除非显式声明)
- [ ] 没有删除 PR 文档里说"保留"的文件

### 0.2 测试用例质量(面向业务需求)

**核心原则**:测试用例验证**业务承诺**,不是**代码能不能跑**。

- [ ] 每个测试的 docstring 包含 3 段:
  1. **业务需求**:这个测试保护什么业务承诺?
  2. **对应设计**:PLATE_DESIGN.md §X.Y
  3. **业务影响**:如果这个测试失败,生产会发生什么?
- [ ] 测试名能直接读出业务承诺(如 `test_query_with_mutates_state_true_raises` 而非 `test_validation`)
- [ ] **没有**"功能验证型"测试(如 `test_method_returns_correct_value` 这类只验代码不验业务的)
- [ ] **有**硬错误拒绝测试(每个 raise 路径都有对应 `pytest.raises` 测试)
- [ ] **有**业务不变量测试(对应业务承诺的 aggregate check)
- [ ] **没有**重复测试(同一业务承诺被多个测试覆盖)

### 0.3 frozen + @final 不变式

- [ ] 新增字段用 immutable 类型(`tuple` / `frozenset` / `Enum`,不用 `list` / `set` / `dict`)
- [ ] 新增字段有 `frozen` 测试(如 `test_xxx_field_is_frozen`)
- [ ] 没有试图通过 `object.__setattr__` 绕过 frozen(任何此类 hack 立即 reject)

### 0.4 收口验证

- [ ] 本 PR 的 `pytest tests/plate/test_xxx.py -v` 全过
- [ ] 全量 `pytest tests/` 不退步(测试数 ≥ 前一阶段)
- [ ] 故意制造错误的命令输出 `OK:`(证明断言真生效,不是死代码)

### 0.5 文档同步

- [ ] PR 文档状态从"待执行"改为"已合并"或"已完成"
- [ ] INDEX.md 的依赖图反映本 PR
- [ ] PLATE_DESIGN.md 的"待实现"标注(如适用)改为"已实现"

---

## 1. PR-0.1 (pytest 基线) review 重点

- [ ] `pyproject.toml` 的 `[tool.pytest.ini_options]` 包含 `testpaths` / `addopts` / `asyncio_mode`
- [ ] `tests/conftest.py` 集中 `sys.path` 注入,**不**在子目录 conftest 重复
- [ ] `collect_ignore_glob` 排除清单**正好** = 盘点结果(7 / 3 / 5),不多不少
- [ ] 5 个 sanity 测试**覆盖矩阵**对齐(零侵入 / 按需加载 / EndpointKey / BootstrapError / EndpointSpec)
- [ ] 没有"顺手改 model_registry"的代码改动(本 PR 严格只动测试基建)

---

## 2. PR-0.2 (改名 + model_registry pytest 化) review 重点

- [ ] 改名是 `git mv` 不是 `rm + add`(保历史)
- [ ] `__all__` 显式只含 `registry` + `BootstrapError`(零侵入承诺)
- [ ] 4 个 print+assert 脚本 pytest 化后,**测试名对齐**原文件名(如 `test_spec.py` 的测试在 pytest 化后仍有意义)
- [ ] `test_invariants.py` 新增的不变量是"聚合"而不是"重复"(不与单 endpoint 测试重叠)
- [ ] 旧 `tests/model_registry/` 目录**完全删除**(不留空目录)
- [ ] `pyproject.toml` 的 `testpaths` 移除 `tests/model_registry` 项

---

## 3. PR-B (EndpointCategory + mutates_state) review 重点

- [ ] `EndpointCategory` 用 `str, Enum`(可序列化)
- [ ] 默认值是 `BUSINESS` + `True`(不是 `None`,**不**是 `False`)
- [ ] `__post_init__` 用 `is False` 不用 `not`(防 None 滑过)
- [ ] `mutates_state=None` 的测试存在(防 None 滑过证明)
- [ ] 错误信息包含:`path`、`category.value`、`mutates_state` 实际值、设计章节引用
- [ ] 没有强制存量端点必须新标注(本 PR 不破 31 端点)

---

## 4. PR-C (fin 31 端点显式标注) review 重点

- [ ] 31 端点**逐个**有 category 判断(不是批量决策)
- [ ] 类目分布合理(14 BUSINESS / 17 QUERY / 0 TOOL 是预估,实际可能有 ±3 偏差)
- [ ] `mutates_state` 与 `category` 一致(BUSINESS=True / QUERY=False)
- [ ] 没有"标错类目"的硬错(本 PR 是推动标注,不是改业务)
- [ ] 每个端点的 category 判断有**业务理由**(可在 PR 描述里写 31 行简表)

---

## 5. PR-D1 (路径解析器) review 重点

- [ ] `Resolved` dataclass 是 `@final` + `frozen=True`
- [ ] `resolve_logical_path` 走真实 Pydantic 模型,不靠 `get_type_hints` 推测
- [ ] `_unwrap` 处理 `Optional[T]` / `list[T]` / `dict[str, V]` / `Annotated[T, ...]` / `Union[...]`
- [ ] 命中 `Any` 返回 `Resolved(field=None, kind=Any, degraded=True)`
- [ ] `kind` 枚举完整(`Scalar` / `List` / `Dict` / `Any`)
- [ ] **有**真实 fin 端点的 end-to-end 测试(不是只测 toy model)
- [ ] 错误信息包含:完整路径、当前解析位置、剩余路径段

---

## 6. PR-D2 (FieldBinding 落地) review 重点

- [ ] `FieldBinding` 是独立模块(`src/Plate/binding.py`),不在 spec.py 里
- [ ] 所有 list-like 字段是 `tuple`
- [ ] `_KNOWN_TRANSFORMS` 白名单完整覆盖 PR-D4 需要的 transform
- [ ] `to_path` 不能为空 tuple 的检查存在
- [ ] 未知 transform 的测试存在(防拼写错误)
- [ ] 没有把"自环检查"放在 `__post_init__`(留给 test_invariants 聚合)

---

## 7. PR-D3 (EndpointDoc L2 物理解耦) review 重点

- [ ] `EndpointDoc` 物理分离在 `src/Plate/doc.py`(不混在 spec.py)
- [ ] `summary` 长度上限 120 在 `__post_init__` 强校,**不**靠 review 人眼
- [ ] `dannotations/__init__.py` 暴露 `_DOCS` dict + `get_doc(path)` 函数
- [ ] `get_doc` 找不到返回 `None`(**不**抛 KeyError)
- [ ] L1/L2 对称性测试**只**检查"有 doc 无 spec 报错",不强制"有 spec 必有 doc"(本 PR 不强补)
- [ ] 没有试图把 `EndpointDoc` 嵌入 `EndpointSpec`(违反物理分离原则)

---

## 8. PR-D4 (首批 field_bindings 批量化) review 重点

- [ ] 每个 binding 标注有**端点对端点**分析记录(可在 PR 描述里写表格)
- [ ] `bindings` 引用真实路径(用 `resolve_logical_path` 验证)
- [ ] 没有"强凑假依赖"(独立 QUERY 端点如 login / dict 应 `bindings=()`)
- [ ] fin binding 总数在 [8, 15] 区间(过少 = 漏标;过多 = 强凑)
- [ ] `transform` 类型都在 `_KNOWN_TRANSFORMS` 白名单内
- [ ] orphan binding 测试覆盖所有 binding(每个 binding 至少有 1 个上游可解析)
- [ ] **没有**修改 binding 的上游/下游端点的"业务行为"(本 PR 只标 binding,不改 endpoint 本身)

---

## 9. PR-EOP (Phase 1 收口) review 重点

- [ ] CI gate 配置**最小化**(只加不变量必跑,不重写 CI)
- [ ] `test_invariants.py` 聚合了 Phase 1 所有 PR 的不变量(不重复)
- [ ] `test_eop_baseline.py` 检查**交付物存在性**(字段 / 模块 / 目录)
- [ ] 文档标注"待实现 → 已实现"是**最小化**改动(不动设计本身)
- [ ] **没有**借机加新 feature(本 PR 严格只做"验证 + 文档")
- [ ] Phase 2 启动条件清单已列出

---

## 10. 通用反模式(reviewer 一票否决)

| 反模式 | 例子 | 后果 |
|---|---|---|
| **功能验证型测试** | `test_method_returns_correct_value` | 不验证业务承诺,测试通过不代表业务对 |
| **跳过 frozen 检查** | `object.__setattr__(spec, 'category', 'X')` | 绕过不变式,frozen 形同虚设 |
| **静默吞错** | `try: ... except: pass` | 不变量破坏无任何信号 |
| **位置参数** | `EndpointSpec("POST", "/x", ...)` 假设参数顺序 | 加字段后所有调用断 |
| **混 L1/L2** | 把 summary 写进 `EndpointSpec` | L1 重生成冲掉 L2 |
| **借机重构** | "顺便"改 `core.py` 内部实现 | 本 PR scope creep,review 难 |
| **过度抽象** | 引入"通用 binding framework"支持未来 N 种 transform | 当前 YAGNI,后续可重构 |
| **测试名无业务含义** | `test_1`, `test_check_thing` | review 时无法判断覆盖了什么 |

---

## 11. Review 工作流建议

1. **第一遍**:对照 PR 文档 §2.1 文件清单,看 diff 范围是否一致(防 scope creep)
2. **第二遍**:对照本 checklist 的"该 PR 重点",逐项打勾
3. **第三遍**:跑 PR 文档 §4.1 的"收口验证"命令,确认所有命令真能跑通
4. **第四遍**:读 PR 文档 §5"与后续 PR 的衔接",确认本 PR 没留下需要后续 PR 擦的屁股

**任何一项不通过 = request changes,不通过口头"建议"绕过。**