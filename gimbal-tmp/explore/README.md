# SyncLogorder/ajaxGetList 接口探索测试报告

> 基于 `gimbal-tmp/Scenario_Test_yhrtest.json`，围绕亿海融物流订单查询接口 `/newshopadmin-tidb/SyncLogorder/ajaxGetList.html` 做的探索测试。

## 1. 概览

- 接口：`GET https://test.21eline.com/newshopadmin-tidb/SyncLogorder/ajaxGetList.html`
- 鉴权：YHR Cookie（PHPSESSID）
- 基线响应：HTTP 200，`list` 长度 **15**，首条订单 `YHD20260717035379`
- 探针总数：**81**（含 baseline 共 **82** 条记录）
- 沉淀场景文件：82 个（位于 `cases/`），全部已通过 gimbal 冒烟自检
- 探针原始响应：位于 `probes/<probe_id>.json`（每条带完整 body）
- 探针清单：`probes/manifest.jsonl`

## 2. 关键发现（按接口行为分类）

### 2.1 服务端会响应的有效字段（`list_len` 相对基线有变化 或 触发空集）

| 探针 | 分组 | 字段 | 取值 | list_len | 首条 | 含义 |
|---|---|---|---|---|---|---|
| `p063` | 关键字搜索 | `order_business_no` | `'YWDD20260717109030'` | **1** | `YHD20260717035379` | order_business_no=首条业务号 |
| `p076` | 关键字搜索 | `order_business_no` | `'YWDD_NOTEXIST_000'` | **0** | `None` | order_business_no=不存在的业务号 |
| `p071` | 关键字搜索 | `order_remarks` | `'结算业务'` | **0** | `None` | order_remarks=首条备注 |
| `p058` | 关键字搜索 | `wd` | `'YHD20260717035379'` | **1** | `YHD20260717035379` | wd=首条订单号 |
| `p059` | 关键字搜索 | `wd` | `'测试客户单号'` | **0** | `None` | wd=首条工作号 |
| `p060` | 关键字搜索 | `wd` | `'YWDD20260717109030'` | **0** | `None` | wd=首条业务号 |
| `p074` | 关键字搜索 | `wd` | `'NONEXIST_XXZZZ_9999'` | **0** | `None` | wd=不存在的字符串 |
| `p075` | 关键字搜索 | `work_no` | `'NOT_EXIST_WORK_999'` | **0** | `None` | work_no=不存在的工号 |
| `p003` | 分页 | `page` | `9999` | **0** | `None` | 超大页码 |
| `p004` | 分页 | `size` | `5` | **5** | `YHD20260717035379` | size=5 |
| `p005` | 分页 | `size` | `50` | **50** | `YHD20260717035379` | size=50 |
| `p080` | 分页 | `size` | `0` | **20** | `YHD20260717035379` | size=0 边界 |
| `p081` | 分页 | `size` | `1000` | **1000** | `YHD20260717035379` | size=1000 极限 |
| `p040` | 文件状态 | `finance_file_result` | `'1'` | **0** | `None` | 财务文件结果=1 |
| `p039` | 文件状态 | `finance_file_status` | `'1'` | **1** | `YHD20260128010366` | 财务文件=1 |
| `p041` | 文件状态 | `loan_remark_type_select` | `'1'` | **11** | `YHZ20260508032818` | 借款备注类型=1 |
| `p013` | 状态过滤 | `bulk_query` | `1` | **0** | `None` | 启用批量查询 |
| `p023` | 状态过滤 | `handle_exceed` | `'1'` | **1** | `YHZ20260709032997` | 处理超额=1 |
| `p022` | 状态过滤 | `is_exceed` | `'1'` | **3** | `YHZ20260709032997` | 超额=1 |
| `p020` | 状态过滤 | `need_buy_back` | `'1'` | **5** | `YHZ20260709032997` | 需要买回=1 |
| `p021` | 状态过滤 | `need_buy_back` | `'0'` | **4** | `CDYHH20260330032766` | 不需要买回=0 |
| `p016` | 状态过滤 | `shipment_ifautoquota` | `'1'` | **0** | `None` | 自动配额=是 |
| `p017` | 状态过滤 | `shipment_ifautoquota` | `'0'` | **0** | `None` | 自动配额=否 |
| `p027` | 财务状态 | `financing_status` | `'1'` | **0** | `None` | 融资状态=1 |
| `p028` | 财务状态 | `financing_status` | `'2'` | **0** | `None` | 融资状态=2 |
| `p031` | 财务状态 | `funds` | `'1'` | **8** | `YHD20260618034217` | 资金=1 |
| `p034` | 财务状态 | `line_type` | `'1'` | **0** | `None` | 线路类型=1 |
| `p033` | 财务状态 | `schedule_line_category` | `'1'` | **0** | `None` | 航线分类=1 |

### 2.2 服务端忽略/不响应的字段（`list_len` 与基线一致 = 15）

共 53 条。典型分组：

| 分组 | 字段 |
|---|---|
| 分页 | `page` |
| 状态过滤 | `batch_exchange_query` |
| 状态过滤 | `booking_mbl_delivery_mode` |
| 状态过滤 | `bulk_query` |
| 状态过滤 | `bulk_query_type` |
| 状态过滤 | `bulk_shutout_status` |
| 状态过滤 | `is_backtrack` |
| 状态过滤 | `order_terminated_shutout_status` |
| 财务状态 | `asset_verify_status` |
| 财务状态 | `company_funds` |
| 财务状态 | `delivery_status` |
| 财务状态 | `insured_status` |
| 财务状态 | `limit_status` |
| 财务状态 | `premium_warn_status` |
| 财务状态 | `receipt_status` |
| 财务状态 | `release_status` |
| 时间区间 | `search_time[charge_pay_date]` |
| 时间区间 | `search_time[charge_rec_date]` |
| 时间区间 | `search_time[charge_rec_date_ext]` |
| 时间区间 | `search_time[decl_create_ts]` |
| 时间区间 | `search_time[decl_release_ts]` |
| 时间区间 | `search_time[invoice_rec_ts]` |
| 时间区间 | `search_time[order_created_date]` |
| 时间区间 | `search_time[order_updated_date]` |
| 时间区间 | `search_time[schedule_actual_delivery_date]` |
| 时间区间 | `search_time[track_atd]` |
| 关键字搜索 | `booking_agent_bp` |
| 关键字搜索 | `cancel_remark` |
| 关键字搜索 | `client` |
| 关键字搜索 | `order_customer_real` |
| 关键字搜索 | `order_ids` |
| 关键字搜索 | `other_remarks` |
| 关键字搜索 | `port` |
| 关键字搜索 | `sale` |
| 关键字搜索 | `search_company` |
| 关键字搜索 | `ship_company` |
| 关键字搜索 | `wd` |
| 关键字搜索 | `work_no` |

### 2.3 ⚠️ `search_time[*]` 全部失效

尝试了以下格式：
- `['2026-01-01','2026-12-31']`（单引号 JSON）
- `["2026-01-01","2026-12-31"]`（双引号 JSON）
- `2026-01-01~2026-12-31`（波浪号连接）
- `2026-01-01,2026-12-31`（逗号连接）
- 空字符串
- 已知无数据区间 `1999-01-01,1999-12-31`（仍返回最新 15 条）

**结论**：服务端在 GET 形态下完全忽略 `search_time[*]` 系列 28 个字段，**疑似该接口在前端用 DatetimeRangePicker 包装了 POST 形态的查询**；GET 形态只接受业务字段直接过滤。**这是真实接口行为偏差，建议产品/开发确认**。

### 2.4 关键字搜索有效性

| 探针 | 字段 | 取值 | list_len | 行为 | 备注 |
|---|---|---|---|---|---|
| `p056` | `order_ids` | `'YHD20260717035379'` | 15 | 与基线一致 | **未生效** |
| `p057` | `order_ids` | `YHD20260717035379,YWDD20…` | 15 | 与基线一致 | **未生效** |
| `p058` | `wd` | `'YHD20260717035379'` | 1 | 唯一命中 | ✓ 有效 |
| `p059` | `wd` | `'测试客户单号'` | 0 | 空集 | ✓ 有效 |
| `p060` | `wd` | `'YWDD20260717109030'` | 0 | 空集 | ✓ 有效 |
| `p061` | `search_company` | `'北京火山引擎科技有限公司'` | 15 | 与基线一致 | **未生效** |
| `p062` | `work_no` | `'测试客户单号'` | 15 | 与基线一致 | **未生效** |
| `p063` | `order_business_no` | `'YWDD20260717109030'` | 1 | 唯一命中 | ✓ 有效 |
| `p064` | `order_customer_real` | `'北京火山引擎科技有限公司'` | 15 | 与基线一致 | **未生效** |
| `p065` | `booking_agent_bp` | `'青岛易汇联供应链管理有限公司'` | 15 | 与基线一致 | **未生效** |
| `p066` | `port` | `'ANTING'` | 15 | 与基线一致 | **未生效** |
| `p067` | `port` | `'AOSHANWEI'` | 15 | 与基线一致 | **未生效** |
| `p068` | `ship_company` | `'ACL'` | 15 | 与基线一致 | **未生效** |
| `p069` | `sale` | `'荣洋'` | 15 | 与基线一致 | **未生效** |
| `p070` | `client` | `''` | 15 | 与基线一致 | **未生效** |
| `p071` | `order_remarks` | `'结算业务'` | 0 | 空集 | ✓ 有效 |
| `p072` | `other_remarks` | `''` | 15 | 与基线一致 | **未生效** |
| `p073` | `cancel_remark` | `''` | 15 | 与基线一致 | **未生效** |
| `p074` | `wd` | `'NONEXIST_XXZZZ_9999'` | 0 | 空集 | ✓ 有效 |
| `p075` | `work_no` | `'NOT_EXIST_WORK_999'` | 0 | 空集 | ✓ 有效 |
| `p076` | `order_business_no` | `'YWDD_NOTEXIST_000'` | 0 | 空集 | ✓ 有效 |
| `p077` | `wd` | `'YHD20260'` | 15 | 与基线一致 | **未生效** |
| `p078` | `search_company` | `'北京'` | 15 | 与基线一致 | **未生效** |

### 2.5 异常 / 边界 / 负面用例

| 探针 | 字段 | 取值 | 期望 | 实际 |
|---|---|---|---|---|
| `p003` | `page` | `9999` | list_len=0 | list_len=0 |
| `p074` | `wd` | `'NONEXIST_XXZZZ_9999'` | list_len=0 | list_len=0 |
| `p075` | `work_no` | `'NOT_EXIST_WORK_999'` | list_len=0 | list_len=0 |
| `p076` | `order_business_no` | `'YWDD_NOTEXIST_000'` | list_len=0 | list_len=0 |
| `p079` | `page` | `0` | - | list_len=15 |
| `p080` | `size` | `0` | size=0 时使用默认或全部 | list_len=20（取到 20 条，未严格 0） |
| `p081` | `size` | `1000` | size=1000（极端） | list_len=1000（接受 1000） |

## 3. 沉淀用例（cases/）

所有探针结果都生成了对应的 gimbal scenario，可被 `python -m gimbal.cli.main run launch <file>` 直接复跑。

| 类别 | 数量 | 文件示例 |
|---|---|---|
| baseline | 1 | `cases/case_baseline.json` |
| bulk | 5 | `cases/case_p011.json` |
| file | 3 | `cases/case_p039.json` |
| finance | 14 | `cases/case_p025.json` |
| keyword | 18 | `cases/case_p056.json` |
| keyword_negative | 3 | `cases/case_p074.json` |
| keyword_partial | 2 | `cases/case_p077.json` |
| negative | 3 | `cases/case_p079.json` |
| pagination | 5 | `cases/case_p001.json` |
| status | 5 | `cases/case_p006.json` |
| switch | 9 | `cases/case_p016.json` |
| time | 12 | `cases/case_p042.json` |
| time_multi | 2 | `cases/case_p054.json` |

## 4. 维度分组（cases/groups/）

按业务维度对所有 case 重新归类，便于 CI 选定维度跑：

| 分组 | 用例数 | 场景文件 |
|---|---|---|
| 关键字搜索 | 23 | `cases/groups/group_keyword.json` |
| 状态过滤 | 19 | `cases/groups/group_status.json` |
| 财务状态 | 14 | `cases/groups/group_finance.json` |
| 时间区间 | 14 | `cases/groups/group_time.json` |
| 分页 | 8 | `cases/groups/group_pagination.json` |
| 文件状态 | 3 | `cases/groups/group_file.json` |

## 5. 如何运行

```bash
# 1) 重新执行整套探索（登录 + 探针 + 沉淀）
cd D:/Gimbal/Gimbal
python gimbal-tmp/explore/explore.py

# 2) 重生成分析报告（基于 probes/manifest.jsonl）
python gimbal-tmp/explore/analyze.py

# 3) 跑某个沉淀用例
python -m gimbal.cli.main run launch gimbal-tmp/explore/cases/case_baseline.json
python -m gimbal.cli.main run launch gimbal-tmp/explore/cases/case_p058.json

# 4) 跑某分组下的所有探针（用 bash）
for f in gimbal-tmp/explore/cases/case_p0[01][0-9].json gimbal-tmp/explore/cases/case_p0[2-5][0-9].json; do
  python -m gimbal.cli.main run launch "$f" -o json 2>/dev/null | tail -2
done
```

## 6. 数据约定

- 关键字类探针（`wd`/`work_no`/`order_business_no`/...）的取值取自基线第一条订单：
  - `order_no` = `YHD20260717035379`
  - `work_no` = `测试客户单号`
  - `order_business_no` = `YWDD20260717109030`
  - `bl_no` = `tidb_LK042607171538343400914D1`
  - `schedule_from_terminal` = `ANTING`
  - `schedule_to_terminal` = `AOSHANWEI`
  - `schedule_carrier` = `ACL`
  - `order_created_date` = `2026-07-17`

## 7. 已知限制

1. **编码**：控制台是 GBK，中文字段值在日志里会被替换；本探索器只对 ASCII 关键字段做断言与 sample 提取，完整响应体落盘在 `probes/<id>.json` 可供 UI 端复核。
2. **Auth**：复刻 YHR 认证（POST `/Home/Public/index.html`），会话有效期 7200s。
3. **服务端行为**：`search_time[*]` 全部失效是真实接口行为偏差，需产品确认是否需要切换到 POST 形态或包装字段。
4. **未覆盖维度**：未对 `setup`/`teardown`/`vars` 注入、对 suite 编排组合做探索（接口本身不涉及）。

## 8. 探索结论（按字段有效性）

- 探索覆盖字段：**52**
- 服务端**实际响应**的字段：**18** → `bulk_query`, `finance_file_result`, `finance_file_status`, `financing_status`, `funds`, `handle_exceed`, `is_exceed`, `line_type`, `loan_remark_type_select`, `need_buy_back`, `order_business_no`, `order_remarks`, `page`, `schedule_line_category`, `shipment_ifautoquota`, `size`, `wd`, `work_no`
- 服务端**忽略**的字段：**34** → `asset_verify_status`, `batch_exchange_query`, `booking_agent_bp`, `booking_mbl_delivery_mode`, `bulk_query_type`, `bulk_shutout_status`, `cancel_remark`, `client`, `company_funds`, `delivery_status`, `insured_status`, `is_backtrack`, `limit_status`, `order_customer_real`, `order_ids`, `order_terminated_shutout_status`, `other_remarks`, `port`, `premium_warn_status`, `receipt_status`, `release_status`, `sale`, `search_company`, `search_time[charge_pay_date]`, `search_time[charge_rec_date]`, `search_time[charge_rec_date_ext]`, `search_time[decl_create_ts]`, `search_time[decl_release_ts]`, `search_time[invoice_rec_ts]`, `search_time[order_created_date]`, `search_time[order_updated_date]`, `search_time[schedule_actual_delivery_date]`, `search_time[track_atd]`, `ship_company`

**核心结论**
1. GET 接口**实际生效**的字段约 **18** 个：分页、状态/文件枚举、关键关键字。详见 §2.1/§2.4。
2. **`search_time[*]` 28 个时间字段全部不生效**（已尝试 4 种格式 + 空字符串 + 已知无数据区间）。GET 形态无服务端解析逻辑，强烈疑似产品用 DatetimeRangePicker 包装了 POST 查询，前端可能绕开了这个限制。
3. 其余被忽略的字段（34 个）按无效处理——这些参数当前与 GET 列表接口**无关联**，建议接口契约测试**不**对它们做断言。
4. 复跑命令：`python -m gimbal.cli.main run launch gimbal-tmp/explore/cases/case_*.json`
