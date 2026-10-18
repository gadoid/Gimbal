# 批1 一页纸小设计 · 外部定义归一 plate(按 v1.0 重写 · 草案)

> 日期:2026-10-18　依据:《外部定义归一 plate 改造方案》**v1.0 定稿**(`claude/external-definition-unification-design.md`);代码基线 `03d46b4c`;执行序 = 实施计划 v1.1 §3(b1-1…b1-11)
> 状态:**草案 —— 待 owner 评审定稿后开批1**。重写自 v0.8.1 版:被 v1.0 取代的细则(照常 release / `ext:` 内联 / 漂移处置 / 形态匹配器 / base_service 派生)已剔除;仍有效结论(kind 不进执行产物、signer 留执行侧、line 豁免 common)由本稿承接并标注。
> 范围:**仅 plate 侧**(§3.1 全部);平台侧在批2,清理在批3,活体在批4。

---

## 1. `kind` 字段(b1-1)

- `ServiceDefinition` 增 `kind: Literal["sut", "integration"] = "sut"`;模型保持 `extra="forbid"`;
- **不进执行产物**:case.json / call 投影零变化;release 冻结原始 dict,新发版构件自然含 kind、旧构件无 kind 回读走缺省 `sut`(存量哈希不变);
- 同批更正 `service_definition.py` docstring「M2 不可变域」→ 与 `schema/__init__.py` 的 M1 归类一致;**不升任何代际**。

## 2. 三视图与列表行(b1-2 / b1-3)

- `ServiceView.kind` 显式字段;`SystemView.kind` 派生(系统内服务 kind 的共同值,不一致时为 `None` —— 不一致由 check 规则 1 拦,合法树中视图恒有值;`None` 在声明闸按「非 integration」处理,fail-safe);
- `EndpointView.kind`:经 `registry.system_of_service` → 系统内服务定义取 kind;`ServiceDetailView` 经 `extra` 自动透出;
- `/api/endpoint`(全局与系统作用域)与 `/api/service` 行带 `kind`,**全量不过滤**;分页行为维持现状(无分页)。

## 3. `parse_ref` 与 reason(b1-4)

- 新类别:`ref == "integration"` → `("integration", None, None)`;
- `ReleaseReadError` 增可选属性 `reason`(`None | "record_value" | "malformed"`);
- 抛出:`integration@` 前缀 → `invalid_ref` + `record_value`;现有「`#` 后非数字 / 空线名」抛出补 `reason="malformed"`;**返回值形状不变**(调用方 `_registry`/`reproject`/`resolve_effective`/diff 零改动);裸线保留 line-kind(取数域);
- 线名禁用 `integration`:挂 check 系统树区(frontmatter `line != "integration"`,与规则 2 同区)——`parse_ref` 已把该词保留,禁写防的是「取数域不可达的线」;
- 注:门禁③只扫平台 src,plate 侧 `startswith("integration@")` 写法不受门禁约束。

## 4. 重投影与 `_needs_root`(b1-5)

- `reproject`:类别 `integration` → `snaps[system] = None`(同 working),投影取 working 注册表;
- `_needs_root`:判据改为 `parse_ref` 类别 ∉ {working, integration}(否则含 integration 声明的 convert 在无构件根时 503)。

## 5. 声明闸(b1-6,`routes_grammar.py:1350-1370`)

逐系统对 `meta_plate` 声明取 `parse_ref` 类别:

| 类别 | 处理 |
|---|---|
| `working` | 通过 |
| `integration` | 查系统 kind:非 integration → **422 双向绑定违例**(码 `invalid_ref`、无 reason,message 指明系统实 kind 与声明不匹配 —— 不新增 ErrorCode/reason 类别,绑定违例不是形状问题) |
| `revision` | 通过(存在性由装载路径兜) |
| `line`(裸线) | **422 `invalid_ref` + `missing_revision`**(对齐拒,消除「平台拒、plate 收」双口径) |
| 抛出(invalid_ref) | 422 按 reason 映射文案(`record_value` →「`integration@…` 是执行记录值,声明只能写 `integration`」) |

`ext:` 豁免保留(删除归 C12,批3)。

## 6. 错误承载(b1-7)

- `_read_error` 增可选参数 `decl_domain=False`;`reason` 非 None 时 `details={"reason": …}` 转发(**一行主体改动**);
- `_READ_ERROR_HTTP` 的 `invalid_ref` 行状态码**不动**(取数域 400);`decl_domain=True` 时 `invalid_ref` 用 **422**(D-O:resolve 出口);其余码(`release_not_found` 404 等)两域同形不变;
- `/convert`:现有 `except ReprojectError` 处扩捕 `ReleaseReadError` → **422**(码沿 `_READ_ERROR_HTTP` 映射、reason 透传)—— 修掉现状落 500 的路径;
- 取数路由 `_read_error(e)` 调用点零改动。

## 7. resolve 分流(b1-8)

- 遍历 `meta_plate`:类别 `integration` → **不调 `resolve_effective`**,直接 `{"effective": f"integration@{标识}", "available": [], "changed_endpoints": []}`(`resolve_effective` 开头即拒非 revision,`read.py:365-368`,必须前置分流);
- 入参 `integration@…` → 按 §5 的 422 `record_value` 出。

## 8. 定义标识(b1-9)

- `dialect/canonical.py` 增 `integration_system_hash(endpoints) -> str`:输入 `[(ep.id, shape_hash(ep))]` 按 id 排序 → 规范序列化(`_sorted_dicts` + 紧凑 JSON)→ sha256;数行,不新增模块;
- lifespan:对注册表内 **kind=integration** 系统计算并存 `app.state.integration_definitions = {system: hash}`(sut 系统不算);
- `/healthz` 响应增:`"integration_definitions": {…}`、`"git_head": <sha>|null`(**HEAD 读取失败返回 `null`,不报错不阻断**);沿 `m2_pool` 先例。

## 9. plate check 四规则(b1-10,挂 `validate_system_tree` 系统树区)

1. 系统内所有服务 kind 一致(**error**);
2. kind=integration 不得声明版本线字段(frontmatter;含 `line != "integration"` 线名禁用)(**error**);
3. integration 系统不得有 `review: draft` 块(**warning**,起草常态;合入闸见 §10);
4. integration 系统端点不得声明 `query_views`(**error**)。
- `common` 无 line、标缺省 `sut`,规则对其零触发(line 豁免 common 的既有结论不变)。

## 10. tests/plate(b1-11)

- **无 draft 合入闸**:`test_no_integration_draft.py` 扫 `systems/` —— kind=integration 系统存在 draft 块即 fail;随 `verify_all` 第 1 步运行;
- `/healthz` 断言并入 `test_http_health.py`(integration_definitions / git_head 形状;无 integration 系统时空 dict + null);
- 正反例清单 = 实施计划批1 验收逐项:代际未变、列表反向断言、四规则、parse_ref reason(**返回值形状不变 + `?ref=<line>` 路由不回归**)、裸线对齐拒、resolve 前置分流、`_needs_root`、状态码分域(取数 400 带 reason / convert 422 / resolve 422)、**错误码集合不变**、双向绑定、标识透出、标识稳定性(改 description/ui_kind 不变;改声明/binding/增删端点必变)。

## 11. 契约 fixture(`tests/fixtures/ref-decl-domain.json`,两侧测试各自读取)

```json
{
  "valid":  [{"ref": "working", "category": "WORKING"},
             {"ref": "integration", "category": "INTEGRATION"},
             {"ref": "1.0#3", "category": "PIN"}],
  "invalid": [{"ref": "integration@abc123", "reason": "record_value"},
              {"ref": "1.0#x", "reason": "malformed"}],
  "declaration_only": [{"ref": "1.0", "plate_parse": "line", "declaration_reason": "missing_revision"}]
}
```

- `declaration_only`:裸线 plate 取数域合法(line)、声明域拒(`missing_revision`)—— 两侧各自按所处域断言;纯字符串分类,不触真实 registry;
- plate 测试直读本文件;backend 测试回溯仓库根读同一文件(运行目录不同,`verify_all.sh:48/51`);**分类器/生产代码不读 fixture**。

## 12. 提交序列

b1-1…b1-11 各一提交(信息格式见实施计划 §3);批1 验收门通过后合入并打 tag `ext-unify-b1-done`。
