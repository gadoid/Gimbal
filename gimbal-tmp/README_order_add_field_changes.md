# 变更说明：orderAdd / orderEntrust/orderAdd 接口字段适配

| 项目 | 内容 |
|---|---|
| 版本 | v2.0 |
| 日期 | 2026-07-13 |
| 作者 | codfish |
| 审核人 | 待定 |
| 适配基线 | `gimbal-tmp/Scenario_Test_14.json`（已应用） |
| 对比基线 | `gimbal-tmp/Scenario_Test_10.json`（未改动） |
| 变更范围 | `/api/order/order/orderAdd`、`/api/order/orderEntrust/orderAdd` |
| 原则 | 以**字段名（key）**为粒度，不绑定具体值；值由各用例根据本场景数据自行填入 |

---

## 一、变更速览

| 类型 | 数量 | 字段分布 |
|---|---|---|
| 新增字段 | 21 | 详见 §2.1 |
| 删除字段 | 3 | 详见 §2.2 |
| 值需修正的字段 | 3 | 详见 §2.3 |
| 顺序调整 | 0 | — |

> **识别要点**：本次只动 `request.body` 内的 JSON 结构；`api`、`strategy`、`request.headers` 不变。

---

## 二、字段级变更清单（按 key）

### 2.1 新增字段（21 个，按插入位置分组）

#### 组 P-A：`customer_name` 之后追加（3 个）

> 位置锚点：紧跟在 `customer_name` 之后、`service_id` 之前

| Key | 类型 | 说明 | 值来源建议 |
|---|---|---|---|
| `receive_time_limit` | string/number | 收货时限 | 用例变量或固定值（天） |
| `deposit_refund_day` | string/number | 保证金退款天数 | 业务约定天数 |
| `deposit_settlement_date` | string/number | 保证金结算日 | 业务约定日 |

#### 组 P-B：`policy_type` 之后、`service_items` 之前（8 个）

> 位置锚点：紧跟在 `policy_type` 之后、`service_items` 之前

| Key | 类型 | 说明 | 值来源建议 |
|---|---|---|---|
| `settle_type` | string | 结算类型代码 | 字典表（1=月结 等） |
| `settle_type_name` | string | 结算类型名 | 字典名（"月结"） |
| `product_id` | string | 结算产品 ID | 字典表 |
| `product_name` | string | 结算产品名 | 字典名 |
| `deposit_type` | string | 保证金类型代码 | 字典表（1=有） |
| `deposit_type_name` | string | 保证金类型名 | 字典名 |
| `period_delay_type` | string | 账期延长类型代码 | 字典表（2=不延长） |
| `period_delay_type_name` | string | 账期延长类型名 | 字典名 |

#### 组 P-C：`bl_no` 之后追加（1 个）

> 位置锚点：紧跟在 `bl_no` 之后、`etd` 之前

| Key | 类型 | 说明 | 值来源建议 |
|---|---|---|---|
| `track_bl_no` | string | 跟踪提单号 | 与 `bl_no` 同值（或独立跟踪号） |

#### 组 P-D：`track_atd` 之后追加（5 个，仅完整版 body）

> 位置锚点：紧跟在 `track_atd` 之后、`finance_date` 之前
> **适用判定**：body 中含 `fund_code` / `finance_date` 等完整业务字段时需补

| Key | 类型 | 说明 | 值来源建议 |
|---|---|---|---|
| `track_eta` | string | 预计到港时间戳 | 默认 `"0"`，回程后回填 |
| `track_ata` | string | 实际到港时间戳 | 默认 `"0"`，回程后回填 |
| `track_stcs` | string | 跟踪状态码 | 默认 `"0"` |
| `track_ship_name` | string \| null | 跟踪船名 | 默认 `null` |
| `track_voy` | string \| null | 跟踪航次 | 默认 `null` |

#### 组 P-E：顶层 `sys_upttime` 之后追加（3 个，仅完整版 body）

> 位置锚点：紧跟在顶层 `"sys_upttime"` 之后、`"reverse_status_name"` 之前
> 注意：与 `supplier[].sys_upttime` 区分（前者是顶层订单级，后者是供应商级）

| Key | 类型 | 说明 | 值来源建议 |
|---|---|---|---|
| `customer_put_date_desc` | string | 客户回款日期描述 | 默认 `""` |
| `deposit_refund_month` | number \| null | 保证金退款月数 | 默认 `null` |
| `payment_type` | string | 付款方式代码 | 字典表（0=空） |

#### 组 P-F：`m_delivery_type_name` 之后追加（1 个，仅完整版 body）

> 位置锚点：紧跟在 `m_delivery_type_name` 之后、`audit` 之前

| Key | 类型 | 说明 | 值来源建议 |
|---|---|---|---|
| `payment_type_name` | string | 付款方式名 | 默认 `"空"`，与 `payment_type` 对应 |

---

### 2.2 删除字段（3 个，仅出现在早期轻量版 body）

> **判定**：body 中若包含以下 key，请**整体删除整行**（含前面的换行符与尾部逗号）

| Key | 类型 | 原值（仅作参考） | 删除原因 |
|---|---|---|---|
| `pol_port_name` | string | `"QINGDAO,CHINA"` | 新接口契约无此字段 |
| `pod_port_name` | string | `"ANTING,CHINA"` | 新接口契约无此字段 |
| `del_port_name` | string | `"ANTING,CHINA"` | 新接口契约无此字段 |

> **识别提示**：同时存在 `pol_cn + pol_port_name + pol_country_id` 等成对字段时，`*_port_name` 是要删的；保留 `*_cn`（中文港口名）和 `*_country_*`（国家信息）。

---

### 2.3 值需修正的字段（3 个，body 头部位置）

> 适用所有 `orderAdd` 步骤。位置锚点：body 起始前 20 行内。

| Key | 旧值模式 | 修正方向 | 取值建议 |
|---|---|---|---|
| `customer_name` | 空字符串 `""` | 应有值 | 取自 `customer_id` 关联的客户主数据 |
| `operator_name` | 空字符串 `""` | 应有值 | 取自 `operator_id` 关联的用户主数据 |
| `main_sort` | 短横线分隔 `"A-B-C"` | 应使用半角逗号分隔 | 取自 `main_ids` 关联的主公司排序名 |

> **关联映射提示**：
> - `customer_name ← customer_id`
> - `operator_name ← operator_id`
> - `main_sort` 元素 ← `main_ids`（逗号分隔 ID 串）对应的主公司中文名

---

## 三、JSON 结构模板（不绑定具体值）

### 3.1 通用头部段（所有 `orderAdd` 步骤）

```jsonc
{
  "body": {
    "client_expand_name": "${extracted_or_var}",
    "client_expand_id":   "${extracted_or_var}",
    "m_delivery_type":    "${extracted_or_var}",
    "customer_id":        "${extracted_or_var}",

    "customer_name":      "<!== 头部修正：非空值，关联 customer_id ==!>",   // [MOD]
    "receive_time_limit": "<!== 新增 P-A ==!>",
    "deposit_refund_day": "<!== 新增 P-A ==!>",
    "deposit_settlement_date": "<!== 新增 P-A ==!>",

    "service_id":   "${extracted_or_var}",
    "service_name": "${extracted_or_var}",
    "operator_id":  "${extracted_or_var}",

    "operator_name": "<!== 头部修正：非空值，关联 operator_id ==!>",         // [MOD]
    "customer_contact_id":   "${extracted_or_var}",
    "customer_contact_name": "${extracted_or_var}",

    "main_sort":     "<!== 头部修正：半角逗号分隔，关联 main_ids ==!>",       // [MOD]
    "policy_id":     "${extracted_or_var}",
    "policy_name":   "${extracted_or_var}",
    "policy_type":   "${extracted_or_var}",

    "settle_type":            "<!== 新增 P-B ==!>",
    "settle_type_name":       "<!== 新增 P-B ==!>",
    "product_id":             "<!== 新增 P-B ==!>",
    "product_name":           "<!== 新增 P-B ==!>",
    "deposit_type":           "<!== 新增 P-B ==!>",
    "deposit_type_name":      "<!== 新增 P-B ==!>",
    "period_delay_type":      "<!== 新增 P-B ==!>",
    "period_delay_type_name": "<!== 新增 P-B ==!>",

    "service_items": ["${service_item_key}"],

    "business_type": "${extracted_or_var}",
    "trade_term":    "${extracted_or_var}",
    "carrier":       "${extracted_or_var}",
    "carrier_id":    "${extracted_or_var}",

    "bl_no":       "${var.bl_no}",
    "track_bl_no": "<!== 新增 P-C：与 bl_no 同值 ==!>",

    "etd": "${extracted_or_var}",
    "atd": "${extracted_or_var}"
    // ...其他业务字段...
  }
}
```

### 3.2 完整版 body 补齐段（仅当 body 含 `fund_code` / `finance_date` 时）

```jsonc
{
  "body": {
    // ... 头部与基础字段 ...

    "fund_code":     "${extracted_or_var}",
    "fund_name":     "${extracted_or_var}",

    "track_atd":       "${extracted_or_var}",
    "track_eta":       "<!== 新增 P-D ==!>",     // [NEW]
    "track_ata":       "<!== 新增 P-D ==!>",     // [NEW]
    "track_stcs":      "<!== 新增 P-D ==!>",     // [NEW]
    "track_ship_name": "<!== 新增 P-D ==!>",     // [NEW]
    "track_voy":       "<!== 新增 P-D ==!>",     // [NEW]

    "finance_date":    "${extracted_or_var}",

    // ... 折扣、状态、费用段 ...

    "financing_apply_amount_usd": "${extracted_or_var}",

    "sys_upttime":              "${extracted_or_var}",   // 顶层订单级
    "customer_put_date_desc":   "<!== 新增 P-E ==!>",   // [NEW]
    "deposit_refund_month":     "<!== 新增 P-E ==!>",   // [NEW]
    "payment_type":             "<!== 新增 P-E ==!>",   // [NEW]

    "reverse_status_name":          "${extracted_or_var}",
    "is_delayed_recovery_name":     "${extracted_or_var}",
    // ...
    "m_delivery_type_name": "${extracted_or_var}",

    "payment_type_name": "<!== 新增 P-F ==!>",          // [NEW]

    "audit": [],
    "enable": "${extracted_or_var}",
    // ...
    "action":  "check | submit",
    "order_file": []
  }
}
```

### 3.3 早期轻量版 body 删除段

```jsonc
{
  "body": {
    // ... 其他字段 ...

    "pol_cn":        "${...}",
    "pol_port_name": "<!== 删除（仅轻量版）==!>",      // [DELETE]
    "pol_country_id":   "${...}",
    "pol_country":      "${...}",
    "pol_country_cn":   "${...}",
    "pod_cn":        "${...}",
    "pod_port_name": "<!== 删除（仅轻量版）==!>",      // [DELETE]
    "del_cn":        "${...}",
    "del_port_name": "<!== 删除（仅轻量版）==!>",      // [DELETE]
    "country_id":    "${...}",
    "country_name_cn": "${...}",

    "action": "check | submit",
    "entrust_status": "${...}",
    "order_file": []
  }
}
```

---

## 四、键-职责速查表

| 字段分类 | 涉及 Key 数量 | 主要 Key |
|---|---|---|
| 客户/经办基础 | 3 | `customer_name`, `operator_name`, `main_sort` |
| 收货/保证金 | 3 | `receive_time_limit`, `deposit_refund_day`, `deposit_settlement_date` |
| 结算/产品/账期 | 8 | `settle_type*`, `product_*`, `deposit_type*`, `period_delay_type*` |
| 提单跟踪 | 1 | `track_bl_no` |
| 船舶跟踪链 | 5 | `track_eta`, `track_ata`, `track_stcs`, `track_ship_name`, `track_voy` |
| 付款方式 | 2 | `payment_type`, `payment_type_name` |
| 账期描述 | 2 | `customer_put_date_desc`, `deposit_refund_month` |
| 删除（冗余港口） | 3 | `pol_port_name`, `pod_port_name`, `del_port_name` |

---

## 五、识别辅助：哪些步骤需要打哪组补丁？

| 用例特征 | 需要打的补丁组 |
|---|---|
| body 含 `fund_code` + `finance_date` + `track_atd` | 头部修正 + P-A + P-B + P-C + P-D + P-E + P-F |
| body 含 `customer_category` + `customer_main_id` | 头部修正 + P-A + P-B + P-C + P-D + P-E + P-F |
| body 含 `entrust_status` 但**不**含 `fund_code` | 头部修正 + P-A + P-B + P-C + 删除 3 个 `*_port_name` |
| body 仅 5-10 个最小字段 | 头部修正 + P-A + P-B + P-C + 删除 3 个 `*_port_name` |

> **判别问句**（按优先级问）：
> 1. body 中有没有 `fund_code` / `track_atd` / `finance_date`？→ 有 → 完整版
> 2. body 中有没有 `pol_port_name`？→ 有 → 轻量版
> 3. 都没有 → 可能是另一类接口，请人工核对

---

## 六、不需要改的部分（明确边界）

- ❌ `api.path` 不变（`/api/order/order/orderAdd` 与 `/api/order/orderEntrust/orderAdd`）
- ❌ `api.method` 不变（POST）
- ❌ `api.headers` 不变
- ❌ `strategy` 内 `assertion` / `extract` / `assign` 不变（响应结构未变）
- ❌ 其他 `request.body` 内未在本文列出的字段

---

## 七、验证脚本（不依赖具体值）

```bash
python -X utf8 -c "
import json

NEW_KEYS_BY_GROUP = {
    'P-A': ['receive_time_limit', 'deposit_refund_day', 'deposit_settlement_date'],
    'P-B': ['settle_type', 'settle_type_name', 'product_id', 'product_name',
            'deposit_type', 'deposit_type_name',
            'period_delay_type', 'period_delay_type_name'],
    'P-C': ['track_bl_no'],
    'P-D': ['track_eta', 'track_ata', 'track_stcs', 'track_ship_name', 'track_voy'],
    'P-E': ['customer_put_date_desc', 'deposit_refund_month', 'payment_type'],
    'P-F': ['payment_type_name'],
}
FORBID = ['pol_port_name', 'pod_port_name', 'del_port_name']
HEAD_FIX = ['customer_name', 'operator_name', 'main_sort']

with open('gimbal-tmp/Scenario_Test_<your_case>.json', encoding='utf-8') as f:
    sc = json.load(f)

for i, step in enumerate(sc['steps']):
    if 'orderAdd' not in step['api']['path']:
        continue
    body = step['request']['body']
    is_full = all(k in body for k in ['fund_code', 'track_atd', 'finance_date'])
    is_light = 'pol_port_name' in body
    print(f'Step {i+1} ({step[\"api\"][\"path\"].rsplit(\"/\",1)[-1]})')
    print(f'  版型: {\"完整版\" if is_full else (\"轻量版\" if is_light else \"未识别\")}')

    # 检查 P-A / P-B / P-C（必加）
    for grp in ['P-A', 'P-B', 'P-C']:
        miss = [k for k in NEW_KEYS_BY_GROUP[grp] if k not in body]
        print(f'  {grp} 缺失: {miss or \"PASS\"}')

    # 检查 P-D / P-E / P-F（完整版才需要）
    if is_full:
        for grp in ['P-D', 'P-E', 'P-F']:
            miss = [k for k in NEW_KEYS_BY_GROUP[grp] if k not in body]
            print(f'  {grp} 缺失: {miss or \"PASS\"}')

    # 检查删除
    residual = [k for k in FORBID if k in body]
    print(f'  待删残留: {residual or \"PASS\"}')

    # 检查头部修正
    for k in HEAD_FIX:
        v = body.get(k)
        warn = []
        if k in ('customer_name', 'operator_name') and (v is None or v == ''):
            warn.append('空值')
        if k == 'main_sort' and isinstance(v, str) and '-' in v and ',' not in v:
            warn.append('短横线分隔')
        if warn:
            print(f'  头部修正 [{k}]: {warn}')
"
```

---

## 八、迁移清单模板（每个用例一张）

```markdown
## 用例：<用例名>
- 文件：gimbal-tmp/Scenario_Test_<N>.json
- 涉及 step：step_X (orderAdd), step_Y (orderEntrust/orderAdd)
- 触发接口变更的 step 数：N

### 适配动作
- [ ] 头部修正（3 个 key）
- [ ] P-A：插入 3 个 key
- [ ] P-B：插入 8 个 key
- [ ] P-C：插入 1 个 key
- [ ] P-D：插入 5 个 key（仅完整版）
- [ ] P-E：插入 3 个 key（仅完整版）
- [ ] P-F：插入 1 个 key（仅完整版）
- [ ] 删除 3 个 *_port_name key（仅轻量版）

### 验证
- [ ] JSON 语法校验通过
- [ ] 自检脚本输出全 PASS
- [ ] 跑通 step 5 → step 8 最短写入链路
- [ ] 跑完整 e2e 流程
```

---

## 九、变更影响等级

| 用例类型 | 是否受影响 | 优先级 |
|---|---|---|
| 已使用 `orderAdd` / `orderEntrust/orderAdd` 写入订单的 e2e | **必须适配** | P0 |
| 仅查询订单（`orderDetail`/`orderPage`）的用例 | 不受影响 | — |
| 对账/核销/付款链路用例 | **建议同步适配**（避免写入失败阻断） | P1 |
| 不涉及订单的用例（认证、字典等） | 不受影响 | — |

---

## 十、附：基线对比

| 文件 | 字节 | 说明 |
|---|---|---|
| `Scenario_Test_10.json` | 128 640 | 基线（未改动） |
| `Scenario_Test_14.json` | 133 355 | 已应用补丁 |
| 净增 | +4 715 | 21 新增 + 3 删除 + 3 修正 = 27 处变更 |

---

## 十一、变更历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-07-13 | 初版（含硬编码值） |
| v2.0 | 2026-07-13 | 移除硬编码值，改为"key + 锚点 + 值来源建议"形式；适配任意用例 |
