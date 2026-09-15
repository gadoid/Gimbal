# fin SUT 请求面孪生生成器 设计

> 定位:被测系统(fin)「数字孪生」的第一代 —— **请求面全量生成 + 取数活性**。
> 行为面(流转/联动/时序)零代码逆向,由场景用例显式承载(已拍板,见 §2)。

Date: 2026-09-15
代码基线: `D:\fin-test\api\Application`(ThinkPHP 3.x,模块化)
Schema 基线: `D:\fin-test\fin_test_struct.sql`(304 表,Navicat 仅结构,TiDB 8.5.4)
+ `D:\fin-test\fin_test_search.csv`(6391 列 information_schema 导出)

## 1. 背景与分层

现有 fin endpoint 定义 26 个,全部 curl 抓包手工构建,边际成本小时级、覆盖率「挑着建」。
本生成器把边际成本降到分钟级、覆盖率推到全量(Order 模块 8 Controller 估 100+ 方法)。

孪生四层与本 spec 的边界:

| 层 | 内容 | 归属 |
|---|---|---|
| ① 接口标本 | 路由/字段面/中文名/类型/枚举/默认值/state | **本 spec**(4 源静态生成) |
| ② 取数活性 | value_source 挂查询视图,值运行时实时拉 | **本 spec**(同名匹配 + 外键线索) |
| ③ 响应面 | ResponseSpec 形状/children 行形/断言面 | 实跑渐进积累(生成期留空,标 needs_capture) |
| ④ 行为面 | 流转/状态机/联动校验/副作用时序 | **场景用例是唯一载体**,不做代码逆向 |

## 2. 核心裁决(会话已拍板,不再讨论)

1. **默认 carry 姿态**:本接口不处理的字段一律 carry(只携带、不承诺语义)。
2. **可空值 carry 白名单判据**:
   `可空值 carry = 不被 Service 读取 && 不被 Validator 必填校验`。
   - 被 Service 读取 → form 候选(人工确认一小撮驱动字段);
   - 被 Validator 必填(present/require)但不被读 → carry 且**必须**挂 value_source
     (同现有手建模式:`policy_name` carry + customer_policy 视图);
   - 落库列 NOT NULL 无默认 → 第三判据,并入「必须保证有值」集合。
3. **行为面零逆向**:「调 A 后 B 应怎样」是场景用例的语言,不是代码逆向的语言。
4. **手建优先**:生成器不覆盖已存在的 endpoint 定义,只报告碰撞。
5. **响应面照抄现状**:responses 只有 200 空壳,与现有手建一致。

## 3. 四源清单(全部已实证)

| 源 | 路径 | 供 给 |
|---|---|---|
| S1 Controller | `Application/*/Controller/*.class.php` | 路由面:模块/控制器/方法 → path |
| S2 Validator | `Application/*/Validator/*.class.php` | `$xxxRules`(键/必填三档/范围/enum/行注释中文名,含被注释字段)+ 命令式 check* 方法(读取标记) |
| S3 Service+Enum | `Application/*/Service/*.class.php` + `Common/Enum/*.class.php`(30+) | 读取树(getData*/直接下标/isset-empty 分支/跨类调用链)+ Enum 常量(value↔中文全集)+ getDataString 第三参默认值 |
| S4 Schema | `fin_test_struct.sql` + `fin_test_search.csv` | 列注释中文名(193 列全覆盖实证)+ COLUMN_TYPE 类型/长度 + NOT NULL/DEFAULT + 外键关联线索(注释「关联sys_user」式) |

底层机制(已读实现,钉死不臆测):
- `getRequestParam()` = `I("param.")` 优先,空则 `php://input` JSON —— 键面权威 = JSON body;
- `paramVerification` 委托 FangStarNet/php-validator(`ValidatorUntil::validatorData`),
  present/require/exist 三档语义以该库实现为准(Task 0 读库钉死)。

## 4. 管线(五阶段,产物落 gimbal-tmp/,模式同 gimbal-query-field-verify)

```
S1..S4 ──▶ Stage1 路由发现 ──▶ Stage2 键面+读取标记 ──▶ Stage3 语义富化
                                                        │
        Stage5 装订 EndpointSpec ◀── Stage4 state 赋值 + value_source 匹配
```

- **Stage1 路由发现**:Controller 公有方法 → 接口清单(module/controller/action → path/method)。
  Task 0 先实证 `/api/...` URL 前缀 → 模块的路由映射(Application 下同时有 Api/ 与业务模块);
  排除清单(Corn/Event/Script 非接口、Base 类、下划线前置方法)显式化。
- **Stage2 键面抽取**:S2 活跃规则键 ∪ S3 读取树键 = 键集;每键带
  `{read: bool, required: bool, defaults: [...]}` 标记。PHP 解析用 AST(php-parser 类),
  不用正则(注释/字符串/变量内插会骗过正则)。
- **Stage3 语义富化**:中文名多源合并优先级
  `Validator 注释 > DB COMMENT > Enum 注释 > _name 派生规则(id 字段注释+「名称」)`;
  enum ← Enum 类(全集,优于抓包)∪ `in:` 规则;范围 ← `length_max` 等 + COLUMN_TYPE;
  默认值 ← getDataString 第三参 ∪ COLUMN_DEFAULT。
- **Stage4 state 赋值 + value_source**:按 §2 判据产 state;value_source 同名匹配
  (平台查询视图列名 == 字段名,外键线索辅助),多视图同名命中 → 消歧队列人工确认,
  不自动挂错。children 行形不完整 → 标 `needs_capture`,容器全 carry(天然满足整传一致性校验)。
- **Stage5 装订**:生成 `EndpointSpec` Python 文件,文件头带
  `来源: 代码生成 | 基线: fin-test@<commit> + schema@<导出日期>` + needs_capture 清单。

## 5. 生成物规范

- 目录:`gimbal_plate/systems/fin/endpoint/`(与手建同目录,命名 `{module}_{controller}_{action}.py` 沿现有约定);
- id:`fin.{controller_snake}.{action_snake}`(同现有 `fin.order_entrust.order_add`);
- 碰撞:同 id 已存在 → 跳过 + 报告(手建优先,不合并不覆盖);
- 头注释必含:生成时间/代码基线/schema 基线/needs_capture 字段清单/碰撞报告指针。

## 6. 安全约束

- **生成期零 HTTP**:生成器只读代码与 schema,不对 SUT 发任何请求;
- **首跑真值由人发起**:写接口无 check 档 → needs_capture 标警示,
  生成流程内置安全序(只读接口先跑;无 check 档写接口人工评估后才跑);
- schema/代码均在本地文件,无凭证入库。

## 7. 不做什么

- 响应面结构推导(PHP 无类型,returnSuccess($data) 形状不可靠)→ 实跑积累;
- 行为/状态机/联动校验抽取 → 场景用例承载;
- 生产库/生产代码触碰 → 测试环境唯一基线。

## 8. 验收(生成器质量的直接度量)

**以 26 个手建 endpoint 为 ground truth**:生成器带对照模式
(碰撞接口照常生成到 gimbal-tmp 不落盘,不违反 §5 手建优先),
与手建做结构化 diff(键集/中文名/enum/state/value_source),差异报告按
「生成器对/手建对/双方各有理」三分类。目标:键集召回 100%,语义字段
(name/description/enum/default)一致率 ≥90%,state 分歧全部可解释。
另对全量新接口抽查 5 个人工复核。

## 9. 开放问题(实施中裁决,进 ledger)

- value_source 消歧队列的交互形态(报告文件 vs 平台 UI)—— 首版报告文件即可;
- Enum 类 ↔ 请求字段的自动匹配置信度阈值;
- Api 模块与业务模块的路由实证结果若与预期不符,Stage1 的映射表如何兜底。
