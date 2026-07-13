# 查询字段校验覆盖报告 — https://fin-tidb.21eflag.com/newshopadmin-tidb/OrderSettlement/ajaxGetList.html

- 可测字段(分母): 16
- 有样本、已生成用例: 14 (14/16 = 87%)
- 用例行数: 36 (字段×互异样本)
- baseline_count: 23033, 首页校验窗口 size=5

## 用户场景文件不写字段(skill 不 emit)

- `kind`
- `scenarioId`
- `meta.*`
- `config.{setup,teardown,services,users,vars,timePolicy,retry}`
- `resource`

## 覆盖明细(执行后回填 PASS/FAIL)

| 字段 | 中文名 | 类别 | 样本数 | ① | ② | ③ | ④ |
|---|---|---|---|---|---|---|---|
| `wd` | 模糊搜索(订单号/提单号/工作号等) | FUZZY | 3 | | | | |
| `work_no` | 工作号 | FUZZY | 1 | | | | |
| `order_customer_real` | 客户(实际) | FUZZY | 3 | | | | |
| `booking_agent_bp` | 订舱代理BP | FUZZY | 3 | | | | |
| `booking_agent_bp_real` | 订舱代理BP(实际) | FUZZY | 3 | | | | |
| `order_business_no` | 业务单号 | FUZZY | 3 | | | | |
| `ship_company` | 船公司 | ENUM | 3 | | | | |
| `service_types` | 服务类型(多选) | ENUM | 3 | | | | |
| `order_remarks` | 订单备注 | ENUM | 1 | | | | |
| `sale` | 销售员 | ENUM | 3 | | | | |
| `client` | 客户(委托方) | ENUM | 1 | | | | |
| `operator` | 操作员(多选) | ENUM | 3 | | | | |
| `search_time[charge_pay_date]` | 应付日期 | DATE_RANGE | 3 | | | | |
| `search_time[charge_rec_date]` | 应收日期 | DATE_RANGE | 3 | | | | |

## 跳过清单 (2)——数据缺口或被 --only 排除

- `search_company` 模糊-委托公司: NO_SAMPLE(scanned=15)
- `booking_mbl_delivery_mode` MBL放单方式: NO_SAMPLE(scanned=15)

## 不在分母的参数 (6)

- `page` [EXCLUDED] 
- `size` [EXCLUDED] 
- `bulk_query_type` [EXCLUDED] 
- `bulk_shutout_status` [EXCLUDED] 
- `bulk_query` [EXCLUDED] 
- `batch_exchange_query` [EXCLUDED] 
