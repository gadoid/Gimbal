# V3 阶段 6 一致性对照报告

> 日期:2026-08-04
> 对照对象:[PLATE_V3_DESIGN.md](PLATE_V3_DESIGN.md) v1.0(2026-08-04 定稿)

## 1. schema 层不变性(§2)

| 文档要求 | 现状 | 结果 |
|---|---|---|
| `schema/endpoint/` 不为被测系统开子类 | 5 个文件 mtime 仍为 7月 28~30,未动 | ✓ |
| `schema/interface/` 不为被测系统开子类 | 8 个文件 mtime 7月 28,仅 `scenario.py` 在 V3 阶段 3 加 `system` 字段(2026-08-04) | ⚠️ 见注 1 |
| 现有字段语义不变 | 0 个字段被删除,0 个字段被改名 | ✓ |

**注 1**:`scenario.py` 的 `Meta` 类新增 `system: str = ""` 字段,默认值空串,向后兼容。这是 V3 §3 第三条"该系统的 Meta 默认模板"必须携带 system 信息的必要补丁;不动现有 11 个字段。

## 2. 被测系统目录(§3)

| 系统 | endpoints | models | defaults | ALL_ENDPOINTS |
|---|---|---|---|---|
| `fin` | 2 文件(`settlement_create_order.py` / `account_query_balance.py`) | `models.py`(3 个 body 类) | `defaults.py`(META + CONFIG) | 长度 2,全部 `system="fin"` |

`mall` 系统按计划**不做**(决策记录:阶段 5 跳过)。

## 3. 消费者层(§4)

| 文档要求 | 现状 | 结果 |
|---|---|---|
| `export/gimbal.py` 实装 | 已实装(完全迁移自 `case/exporter.py`) | ✓ |
| `export/platform.py` 不存在 | 不存在 | ✓(按计划延后) |
| `export/apidoc.py` 不存在 | 不存在 | ✓ |
| `export/mcp.py` 不存在 | 不存在 | ✓ |
| `export/mock.py` 不存在 | 不存在 | ✓ |
| `case/exporter.py` 作为 deprecated re-export 保留 | 已改为 5 行 re-export,从 `export.gimbal` 导入 | ✓ |
| 双路径 import 指向同一类对象 | `EndpointCaseExporter is` 测试通过 | ✓ |

## 4. 新系统接入路径(§5)验证

未实际接入第二个系统(阶段 5 跳过),但 `fin` 的接入路径已走通:
1. ✓ 建 `systems/fin/` 目录
2. ✓ 在 `endpoint/<id>.py` 实例化并注册接口(每接口一文件)
3. ✓ 在 `models.py` 补充具体 body 类,通过 `RequestSpec.model` / `ResponseSpec.model` 组合挂载
4. ✓ 在 `defaults.py` 给出 `META_TEMPLATE` / `CONFIG_TEMPLATE`

## 5. 自治守卫

| 检查 | 结果 |
|---|---|
| `grep -rn "from gimbal\." src/gimbal-plate/` | 0 命中 |
| plate 内反向依赖 gimbal | 无 |

## 6. 测试状态

| 测试集 | 数量 | 状态 |
|---|---|---|
| `tests/plate` | 160 | 全绿(原 150 + V3 阶段 0 新增 10) |
| `tests/unit` | 196 | 195 pass + 1 pre-existing fail(`test_bootstrap_generator.py::test_generator_has_7_kinds` 期望 7 kinds,实际 9,与 V3 无关) |

## 7. 总结

| 维度 | 状态 |
|---|---|
| 文档要求覆盖 | 100%(除阶段 5 决策不做外,其余 6 阶段全部完成) |
| 代码 vs 文档一致性 | ✓ |
| 回归测试 | ✓(160 plate + 195 unit,无新增 fail) |
| 反向依赖 | ✓(0 命中) |
| 扩展点(§6) | 暂未实装(`extensions` 字段按决策延后) |
