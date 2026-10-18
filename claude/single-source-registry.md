# 单一真源台账(single-source-registry)

> 建立批:b2-12(归一方案 v1.0 §6.1 批2 交付物)。**本文是活文档索引,
> 不复制方案全表** —— 能力域完整表、禁止项与合并路径见
> `claude/external-definition-unification-design.md` v1.0 §6.1(唯一详表);
> 新增/变更能力域先改 §6.1,再同步本文索引行。

## 索引(按能力域 → 真源落点)

| 能力域 | 真源落点(代码/机制) | 批次 |
|---|---|---|
| 接口定义(sut/integration) | plate `systems/`(`ServiceDefinition.kind`;`Service/System/EndpointView` 透出) | 批1 |
| ref 类别判定(声明域) | plate `parse_ref`(抛 `invalid_ref`+reason);平台 `run_semantics.ref_category`(INVALID+reason);契约 fixture `tests/fixtures/ref-decl-domain.json` | 批1/2 |
| ref 类别判定(记录域) | 后端 `run_semantics.record_category` + 前端 `types/plate.ts plateRecordCategory`;共享样例 `frontend/src/types/__fixtures__/ref-record-domain.json` | 批2 |
| 双向绑定 / 声明域合法集 | plate 声明闸(`/convert` 必经);平台 `validate_meta_plate_refs` 仅预检映射 | 批1/2 |
| 错误承载(invalid_ref) | 错误码 `envelope.INVALID_REF`;reason 走 `ErrorPayload.details.reason`;状态码分域(取数 400/声明 422) | 批1 |
| `integration` 进 resolve | 仅追溯类(派发链/图台账);结果只写 `plate_pins` | 批1/2 |
| 平台读 plate 目录 | `plate_client` 唯一访问件(聚合行/扁平名/轻端点;轻端点保留严格失败语义;校验路径 `refresh=True`) | 批2 |
| sut 过滤唯一出口 | 别名创建 sut 派生点(`catalog_service_entries` 取 sut 子集)+ §3.4 展示面;`catalog_service_names` 恒全量 | 批2 |
| 别名 ↔ plate 系统 | `base_service`(external 显式必填+kind 校验;sut 派生);`patch_alias` 支持 external→plate 升级 | 批2 |
| carry 基名解析 | `service_names.resolve_base_with_aliases`(别名表优先 → 全量 derive_base 兜底;D-M) | 批2 |
| 执行追溯 | `plate_pins` + `integration@<shape_hash 聚合标识>`;`/healthz` 透出(git_head 失败 null) | 批1/2 |
| 执行记录下游解读 | 前端台账经 `plateRecordCategory`(integration 不字面比对);趋势签名只拼接 | 批2 |
| integration 无 draft 合入闸 | `tests/plate/test_no_integration_draft.py`(verify_all 第 1 步) | 批1 |

## 待收口(后续批次)

- §3.4 全部展示面断言与「不得过滤面」反向断言 → 批2 验收;
- `alias.kind` 双轨合并路径、`_bump` 技术债 → 见 v1.0 §6.1 对应行;
- C1-C12 清理(ext: 目录/登记面/审计/`_strip_ext_anchors` 等)→ 批3,
  完成后本文增补「已退役」注记并指向 ADR 0003。
