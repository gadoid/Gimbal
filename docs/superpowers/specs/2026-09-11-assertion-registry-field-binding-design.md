# 断言管理注册表与测试数据字段绑定协议(spec v2)

**日期**: 2026-09-11
**状态**: 设计定稿待用户审 — 取代 `2026-09-10-dataset-driven-refactor-design.md` 的后续演进方向(该 spec 已实施部分不变,见 §0)
**分支**: feat/dataset-driven-refactor

---

## 0. 背景与取代关系

2026-09-10 spec 实施数据驱动重构(段网格 + 期望行级化 exp_* 提升链),终态 ab3636c1。实施后用户四轮重新定纲,核心转向:

- 期望通道从「exp_* 专用期望变量」整体迁移为「**断言管理注册表 + 数据集行绑定**」
- 数据集重定义为测试数据两层:**变量区(输入)+ 断言区(绑定矩阵)**
- 场景(用例)纯化:只描述业务过程,不再承载测试数据结构

已实施且保持不变:段网格 / 段下拉单选 / 置顶基线行 / TSV / CSV 值链 / 行详情 / 死键提示 / 期望列跳编排器。**期望列本身随 exp_* 退役退场**(§2/§7 迁移)。

## 1. 两件事与字段三面(用户定纲 2026-09-11)

**事 1 数据集改造**:只取模板,基于模板填充,支持直接向被测系统查询选择值(单变量面板取数,复用注册查询视图)。

**事 2 测试数据字段绑定协议** — 字段三面:

| 面 | 载体 | 说明 |
|---|---|---|
| 引用 | 编排器标记 → jsonpath + varName | 哪个字段、被哪个变量喂 |
| 值映射 | 数据集行(varName → 值) | 哪个值绑定到字段 |
| 策略注入 | 注册表条目 + 行绑定 | 值变动的断言 / 策略 |

裁定记录(2026-09-11 用户拍板):

- v1 只做断言策略,其他策略种类留协议位
- 负向用例 v1 直接失败(不建终止机制),后续改造
- 模板即地址:独立控制 = 拆模板(改场景);未模板化字段对数据集不可见(与直填退场一致)
- 注册表 = 场景级资产(同场景多数据集共享);覆写 + 追加两形态都要;行绑定 = 行内保留键 `__binds`,CSV v1 只导值

## 2. 场景纯化

- **exp_* 期望变量退役**:T2 期望提升链(编排器断言卡 expected → `${var.exp_*}`)整体退场;场景断言 expected 回归字面量(流程不变量)
- **合法保留**:引用输入变量的一致性断言(expected = `${var.x}`,如「回显金额 == 提交金额」)— 属过程描述,不在退役之列
- 场景 strategy 仍是**断言形状唯一事实源**;注册表只登记引用,不复制断言定义(§3)

## 3. 断言管理注册表(场景级)

**家**:场景文档平台侧新节 `assertion_registry`(与 orchestration 同级,**不入 gimbal definition/config — 引擎不感知**)。编辑入口 = 编排器配置区「断言管理」节;数据集侧只读消费。

条目形状:

```jsonc
{
  "id": "a1",
  "name": "下单返回码",
  "anchor": { "stepIndex": 0, "source": "body", "jsonpath": "$.amount", "varName": "amount" },
  "assert": { "stepIndex": 0, "target": "$.response_body.code", "operator": "eq", "defaultExpected": "0" },
  "mode": "override"
}
```

- **anchor = 溯源面**(编辑器联动建议用,执行不依赖);**assert = 执行面**(物化消费)
- **mode 两形态**:
  - `override`:覆写场景既有断言 — 匹配键 = stepIndex + target(同 target 多条时加 operator)
  - `append`:向步骤追加场景没有的断言
  - 负向行必须 override(场景 `code==0` 不变则两条断言同场必失败)
- **多对多合法**:一字段锚多条目(amount → $.code 和 $.msg);多字段锚同 target(amount 和 bl_no 都影响 $.code)
- **悬空检测**:stepIndex 越界 / override 匹配不到既有断言 → 死条目软提示(死键同款纪律)+ 跳编排器链接。步骤引用 = 索引(plate Step 无 id),场景编辑移位由载入检测兜底(v1 接受)
- 手工建条目合法(无 anchor 条目仍可被行绑定,联动建议缺席)

## 4. jsonpath 全字段解析能力(2026-09-11 用户提出,已验证可行)

现有三层机器:

1. **契约层**:declarations 自带 `path` = 权威 jsonpath(深路径 / 数组 `$[N]`,D1-D12 已铺)— 标记时优先取契约路径
2. **实例层**:dataset-segments `scanValue` 深扫 body/headers 建路径(数组 `[i]` / 深路径点连)— 现只报告含 `${var}` 的位置
3. **响应层**:plate 契约 `assertable`(仅响应侧,io_spec `DeclarationEntry`,§6 B3「断言面标记」)+ 前端 `assertablePaths()` 投影 — 断言面候选的契约钩子已在

**新增**:`fieldPathsOf(step)`(utils)— 全叶子路径报告,每叶子 `{source, path, varName?}`;模板引用为叶子属性;未声明字段兜底(有路径,无 description/ui_kind)。

编排器标记:

- **请求侧**:字段卡「加入断言管理」→ 自动带 jsonpath + varName(其模板引用);直填字段可标但无 varName(联动建议缺席)
- **响应侧**:断言面候选 = `assertable` 契约(B3 既有语义)
- FieldActionMenu.vue 为用户 WIP,实施时协调标记入口落点

## 5. 数据集侧 — 双区

**变量区**(现状保持):config.vars 列宇宙 + 段下拉单选 + 置顶基线行 + 三态格 + TSV/CSV 值链。期望列(exp_*)随 §7 迁移退场。

**断言区**(新增):行 × 注册表条目**绑定矩阵**:

- 列 = 场景注册表条目(名称 + target/operator 徽标;死条目标灰)
- 格 = 该行该条目的期望值:**空 = 不绑(跑场景默认);填值 = 绑定**
- 行绑定存储 = 行内保留键 `__binds: [{assertId, expected}]`(复制行带绑定);**不入死键扫描、不入 CSV 列宇宙**
- 联动建议:行覆写 var(如 amount)→ 锚 varName=amount 的条目格高亮提示可绑

CSV v1 只导值不导绑定(值链零破坏)。

## 6. 物化链(平台层,引擎零改动)

`materialize(行)` = 深拷贝场景 → vars 合并(行值键,不含 `__binds`)→ 绑定 patch:

- override:按 assert 匹配 strategy 断言 → expected = 绑定值
- append:`strategy.push({kind:'assertion', target, operator, expected: 绑定值})`

- 负向用例:下游步骤直接失败(v1 裁定);条目留「策略种类」协议位(负向终止 / extract 等 v2+)
- 旧 exp_* 物化路径(vars 合并含 exp_*)迁移期保留(§7)
- 执行 / 导出同源(黄金等价测试继续锁死)

## 7. 存量迁移(读兼容 + 惰性一键迁移)

- **读兼容**:场景含 `${var.exp_*}` 形态 → 数据集照旧可跑(旧物化路径保留)
- **一键迁移**(数据集编辑器 / 场景详情入口,手动触发):
  1. 断言 expected `${var.exp_*}` → 字面量(config.vars[exp_*] 基线值)
  2. 注册表自动补条目(override,defaultExpected = 基线值,anchor 空)
  3. 数据集行 exp_* 键 → `__binds: [{assertId, expected}]`
  4. config.vars 清除 exp_*
- 倾向手动触发(可审可控);不做升级全库自动扫

## 8. 编辑器 IA 汇总

- **变量优先双模式**(2026-09-11 用户确认 + 细化):「全部」= 变量网格(列 = config.vars 声明序,引用徽标 [步骤N·名],未引用标灰)/「单变量」= 独立渲染详情面板(基线 / 引用面 / 取数 / 行值)— 不为风格一致妥协
- 单变量面板取数 = ValueSourcePicker 复用(queryAlias = config.users 首键,修订 10/11 语义)
- 断言区 = 绑定矩阵(§5)
- 互跳:注册表条目 ↔ 编排器断言卡;断言区列头 ↔ 同

## 9. v1 边界与协议位

协议位(v2+,只留位不实现):其他策略种类 / 行级覆盖字段默认期望 / catch-all 值 / 位置寻址(数据集侧定向未模板化位置)/ 一键模板化(数据集编辑器代改场景)/ 绑定入 CSV。

## 10. 任务切分建议(供 writing-plans)

| # | 任务 | 层 |
|---|---|---|
| T1 | `fieldPathsOf` 全叶子扫描 utils + 测试 | 前端 |
| T2 | 注册表模型 + 断言管理节(CRUD + 悬空检测) | 前端 + 场景文档 |
| T3 | 编排器标记(FieldActionMenu 协调) | 前端 |
| T4 | 数据集断言区绑定矩阵 + `__binds` | 前端 |
| T5 | 物化链绑定 patch + 旧 exp_* 路径迁移期闸 | backend |
| T6 | 期望提升链退场 + exp_* 退役 | 前端 |
| T7 | 一键迁移工具 | 前端 |
| T8 | 2026-09-10 spec §8.4 取代标注 | 文档 |
