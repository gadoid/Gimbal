# mapping.json / samples.json — 中间产物规格

两份中间产物都是**可审查的判断边界**:脚本生成初稿,人(或模型)审阅修正后
才进入下一阶段。任何手工修改直接改 JSON,重跑下游脚本即可。

## 1. mapping.json

```json
{
  "endpoint": "https://test.21eline.com/newshopadmin-tidb/SyncLogorder/ajaxGetList.html",
  "baseline_url": "…完整含空参的模板URL…",
  "baseline_defaults": {"order_terminated_shutout_status": "1",
                        "bulk_query_type": "1", "bulk_query": "0"},
  "params": [
    {
      "param": "push_status",
      "response_field": "push_status",
      "cn_name": "推送状态",
      "category": "ENUM",
      "multi": true,
      "value_map": {"3": "推送成功", "fail": "推送失败", "0": "未推送"},
      "status": "TESTABLE",
      "source": {"auth": true, "hidden": false, "mapped_by": "same_name"}
    },
    {
      "param": "search_time[charge_pay_date]",
      "response_field": "charge_pay_date",
      "cn_name": "应付日期",
      "category": "DATE_RANGE",
      "granularity": "date",
      "status": "TESTABLE"
    },
    {
      "param": "wd",
      "response_fields": ["order_no", "bl_no"],
      "cn_name": "订单号/提单号",
      "category": "FUZZY",
      "status": "TESTABLE"
    }
  ]
}
```

字段说明:

- `param` — 请求参数名,原样(含 `search_time[...]` 括号)。
- `response_field` — 响应行内的对应字段;FUZZY 用复数 `response_fields`。
- `category` — 见下方分类学。
- `multi` — true 表示前端为多选,序列化为 `param[]=v1&param[]=v2`;
  v1 每用例仍只发一个值。
- `granularity` — DATE_RANGE 专用:`date`(daterange)或
  `datetime`(datetimerange,如"一融资产通过时间")。
- `value_map` — code→中文标签。查询侧标签→code 反查;断言侧 code→标签正查。
  注意混合风格:code 可能是数字(`12`)、字符串(`"fail"`)、或就是标签本身
  (`ship_company` 的 `COSCO`→`COSCO`,此时 value_map 为恒等映射)。
- `status` 取值:
  - `TESTABLE` — 进入采样与生成;覆盖率分母只算这一类。
  - `HIDDEN` — 表单容器 `display:none`(loop_dan、expect_fee_status、
    real_fee_status、other_remarks…),接口支持但产品未暴露,跳过并报告。
  - `EXCLUDED` — 非字段级过滤:`page`/`size`、`wd` 之外的批量类
    (`order_ids`、`bulk_*`、`batch_exchange_query`)。
  - `NO_AUTH` — 响应 `auth` 块中为 false 或缺失,当前账号不可查。
  - `UNMAPPED` — 脚本无法确定 response_field,**必须人工解决后才能继续**。
    已知同类:`sale`→`order_opt_sales`、`client`→`order_opt_client`、
    `ship_company`→`schedule_carrier`、`operator`→`order_opt_operation`、
    `service`→`order_opt_customers_service`、`release_status`→待确认。
    解决后写入 name-overrides.json 持久化。

### 分类学与各类策略

| category | 查询构造 | 行断言谓词(canonicalize 后) |
|---|---|---|
| ENUM | 采样标签→code,单值 | `row[f] == value_map[code]` |
| EXACT | 采样原值 | `canon(row[f]) == canon(q)` |
| FUZZY | 采样完整值(不截子串) | `any(q in canon(row[f]) for f in response_fields)` |
| DATE_RANGE(date) | `[d, d]` | `d <= parse_date(row[f]) <= d` |
| DATE_RANGE(datetime) | `[d 00:00:00, d 23:59:59]` | 同上,datetime 精度 |
| NULL_QUERY | `param=null` | v1 跳过;v2 断言 `row[f] in ("", None)` 且 count 反转直觉,单独设计 |

### canonicalize 规则(两侧共用)

1. 金额:剥 `$`、`￥`、`,`、前后空白 → 十进制字符串比较(`Decimal` 等值,
   避免 `7293.00` vs `7293.0` 误判)。
2. 枚举:比较一律落到**标签域**(display vs display);查询发送落到 code 域。
3. 日期:`YYYY-MM-DD` 与 `YYYY-MM-DD HH:MM:SS` 都 parse 成 datetime,
   date 粒度字段只比 date 部分。
4. 文本:strip 前后空白(样本数据里出现过 `' 银小忠'` 这种带前导空格的脏值,
   strip 后比较,但**采样时保留原值**入 samples.json 以便复现)。
5. 空值等价类:`""`、`null`、缺 key 视为同一"空",FUZZY/EXACT 断言前
   先要求非空。

## 2. samples.json

```json
{
  "scanned_rows": 100,
  "baseline_count": 540,
  "scan_ts": "2026-07-09T15:30:00+08:00",
  "fields": {
    "push_status": {
      "samples": [
        {"value": "未推送", "canon": "未推送", "query_code": "0",
         "order_id": "333509771481055232", "row_id": "333509792846840543"}
      ],
      "distinct_seen": 1,
      "status": "SAMPLED"
    },
    "loan_flag": {"samples": [], "status": "NO_SAMPLE", "scanned": 100}
  }
}
```

- 每字段最多 5 个**互异**样本;凑不满互异值时才允许重复值(不同 order_id)。
- `query_code` 已预先反查好,生成阶段直接用。
- `scan_ts` 用于时效判断:执行与采样间隔过长时提示重采。

## 3. 四断言的精确谓词

设 `B` = baseline_count,`R` = 本次响应,`anchor` = 该行样本的 row_id:

```
① count_shrinks   : R.count < B          (ENUM 且基数≤3 时放宽为 <=)
② anchor_present  : anchor ∈ {row.id for row in R.list}
                    (R.list 只取首页,size=5;若 R.count>5 且 anchor 不在首页,
                     允许按 anchor 精确查一次兜底——用 order_no 等唯一键)
③ rows_match      : ∀ row ∈ R.list[:5], predicate(category)(row)
④ negative        : 构造值查询(在样本值后缀 "_NOTEXIST_gimbal" 或
                    日期取 1970-01-01)→ R.count == 0
```

失败归因优先级:先看 ①(count==B → "过滤参数被后端忽略",最高价值发现),
再看 ②(数据漂移或过滤过严),最后 ③(过滤语义错误/映射表错误——
先怀疑 mapping,再怀疑接口)。

## 4. 覆盖率定义

```
覆盖率 = |有≥1个PASS行的字段| / |status==TESTABLE 的字段|
```

跳过类(HIDDEN/EXCLUDED/NO_AUTH/NULL_QUERY/NO_SAMPLE)不进分母,
但必须逐个列在报告的"未覆盖清单"中并注明原因。90% 不是硬门槛而是
提示阈值:低于它先检查 NO_SAMPLE 列表是否该造数,而不是降低断言强度。
