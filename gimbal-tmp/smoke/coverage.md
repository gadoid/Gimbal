# 查询字段校验覆盖报告 — https://test.21eline.com/newshopadmin-tidb/SyncLogorder/ajaxGetList.html

- 可测字段(分母): 6
- 有样本、已生成用例: 4 (4/6 = 66%)
- 用例行数: 5 (字段×互异样本)
- baseline_count: 540, 首页校验窗口 size=5

## 用户场景文件不写字段(skill 不 emit)

- `kind`
- `scenarioId`
- `meta.*`
- `config.{setup,teardown,services,users,vars,timePolicy,retry}`
- `resource`

## 覆盖明细(执行后回填 PASS/FAIL)

| 字段 | 中文名 | 类别 | 样本数 | ① | ② | ③ | ④ |
|---|---|---|---|---|---|---|---|
| `release_status` | 放款状态 | ENUM | 2 | | | | |
| `financing_status` | 融资状态 | ENUM | 1 | | | | |
| `sale` | 销售员 | FUZZY | 1 | | | | |
| `ship_company` | 船公司 | FUZZY | 1 | | | | |

## 跳过清单 (2)——数据缺口或被 --only 排除

- `search_time[charge_pay_date]` 应付日期: EXCLUDED_BY_USER(--only)
- `wd` 订单号/提单号: NO_SAMPLE(scanned=100)

## 不在分母的参数 (2)

- `page` [EXCLUDED] 
- `size` [EXCLUDED] 
