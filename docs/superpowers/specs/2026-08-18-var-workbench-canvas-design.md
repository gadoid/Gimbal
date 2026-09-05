# 变量工作台迁移 — 步骤编辑页字段级策略下拉 (2026-08-18)

## 0. 背景与定案

#3 变量全局化把变量注册表面板放在 ③ 配置页。实际使用中变量的**生产与消费都发生在
④ 步骤编辑页**(Canvas):字段值来自变量、响应字段产出变量。本设计把注册表迁移到
Canvas,并以**字段级下拉菜单**收编全部变量动作。

讨论中沿引擎逐层核实的关键事实(全部锚定代码):

| 事实 | 锚点 |
|---|---|
| preprocess 在启动前一次性展开 `${var.x}`;查不到 → 整场景拒启 | scenario_preprocessor.py `_resolve_or_fail` |
| `root["var"]` 只装 config.vars + CLI vars + 数据集列;extract 产物不进(运行期才有) | preprocessor `_build_root` |
| config.vars **不播种**进 scenario context → assign `$.name` 查不到 config 变量 | preprocessor L246-299(无 context seed) |
| assign source `$.name`(SCENARIO scope)→ read_variable JSONPath 查 scenario context,extract 产物住这里;`$.` 开头免疫 preprocess | strategy/builtin/utils.py L96-104 |
| 引擎先把 request.body 播种 scratch;before_request 的 assign 写 `$.request_body.<path>`;发请求优先取 scratch body | statemachine/engine.py L175, L412 ("修复 B2") |
| extract `scope=step` 只写本 step scratch(step 结束清);`scope=scenario` promote 到 scenario context 跨步可见 | strategy/builtin/extract.py L60-70 |
| 同名变量二次 extract **静默覆盖**,仅审计标记 | context/channels.py promote_from L222-229 |
| plate kind 仅三种:extract/assign/assertion(无 Static/Dynamic 之分);策略菜单即此三项 | gimbal_plate/http/strategy_dim.py `_KIND_MODELS` |

**两个语域、两条通路**(本设计的全部正确性基础):

- **域 A 静态**: `${var.x}` — config.vars/数据集列;preprocess 启动前展开;可出现在
  path/headers/body/策略字段;查不到 = 场景拒启
- **域 B 动态**: `$.name` — extract 产出(scenario context);运行期 assign 注入
  request_body;唯一入口是 before_request 的 assign 策略

## 1. 范围

### 做(11 项,编号沿用讨论定案)

1. **VariableRegistryPanel 重写为紧凑列表**,挂 Canvas 右栏"step 信息"下方
   (col-info 240-300px):每行 `变量名 + 出身徽章(config 蓝/extract 绿) + 产出者步骤`;
   消费处降级为 hover title
2. **同名多产出提示**:行尾黄标"步骤 N、M 均产出,后者生效"
3. **未注册引用提示保留**(可能拼写错误/数据集列)
4. **FieldForm 字段行下拉菜单**(prop 门控)四项,详见 §2
5. **变量动作按出身分流**:菜单"引用共享变量"子列表只列 config/数据集出身(插文本);
   "注入响应变量"子列表只列 extract 出身且产出步 < 当前步(建 assign 策略)。
   FieldForm 旧 Ⓥ popover 被菜单第一项取代
6. **注入候选时序门控**:extract 变量产出步 ≥ 当前步 → 禁用 + 标"步骤 N 才产出"
   (after_request 产出 vs before_request 消费,同 step 不可用)
7. **headers 的 VarSelectorModal 分流**:extract 出身条目禁选 + 提示
   "响应变量不能进 headers(headers 无运行期注入通路),请在请求体字段上注入"
8. **addExtract scope 'step'→'scenario'**(降级 UI 的手动 extract 跨步消费当前必死)
9. **Ⓥ 死亡引用收口**(被 #5 分流顺势消灭:extract 变量不再可能被插成 `${var.x}`)
10. **checkVarRefs order 校验重定向**:原挂在 `${var.x}` 上的 order 前提错误(静态展开
    不参与时序)。改为挂在 **assign 的 `$.name` source** 上;`${var.x}` 保留
    dangling/missing_column。var-registry.ts 新增 assign source 收集函数
11. **CaseComposerConfig 摘除面板** + `steps` prop(纯减法;emitShape 回声守卫不动)

### 不做

- 拖拽变量到字段框(菜单选择已覆盖)
- headers 运行期注入(引擎无通路)
- StaticAssign 手打字面量入口(已有"+ 添加策略"下拉,不在字段菜单重复)
- var-registry 作用域模型改动(继续全局单列表)
- 引擎/plate/导出零改动

## 2. 字段下拉菜单(核心交互)

字段值输入框尾 **▾**,el-dropdown(trigger=click),prop `fieldActions?: boolean`
门控 — 仅 Canvas 请求体场景传,StrategyForm 复用 FieldForm 处不渲染。

```
字段 [________________________] ▾
      ├─ 引用共享变量 (Reference)    → 子列表: config/数据集出身 → 插入 ${var.x} 文本
      ├─ 从响应提取 (Extract)        → 快捷 extract 策略
      ├─ 注入响应变量 (DynamicAssign) → 子列表: extract 出身(产出步<当前步) → 建 assign 策略
      └─ 断言该字段 (Assertion)      → 快捷 assertion 策略
```

菜单措辞对齐 plate `_KIND_LABELS`(从响应提取变量/准备入参赋值/响应断言),
括号英文是用户提法的类型注记。

### 快捷生成的策略骨架

```ts
// Extract(从响应提取)
{ kind: 'extract',
  target: <字段名>,                    // 变量名 = 字段名
  expression: assertable 精确匹配 $.data.<字段> ?? $.<字段>,  // 兜底后策略卡展开引导改
  scope: 'scenario', required: true }

// DynamicAssign(注入响应变量)
{ kind: 'assign',
  source: '$.<变量名>',                // 域 B:scenario context,免疫 preprocess
  target: '$.request_body.<字段path>', // 字段 path 的 "$." 前缀替换为 "$.request_body."
  scope: 'scenario', required: true }

// Assertion(断言该字段)
{ kind: 'assertion',
  target: assertable 匹配 ?? $.data.<字段>, operator: 'exists', expected: null,
  message: '', soft: false }           // exists 起步,用户在策略卡改 operator/expected
```

策略创建后 `justAddedStrategyIdx` 指向新卡并展开(复用现有引导模式)。
策略区降级路径(strategyKinds 拉取失败)下,三种快捷生成仍可用 —
直接 push 上述骨架(不依赖 detail)。

### 子列表(引用/注入共用形态)

el-popover 列表,每行 `变量名 + 出身徽章 + 产出者`:
- 引用列表: config 出身(config.vars keys)+ 提示行"数据集列运行期注入,不在列表"
- 注入列表: 仅 extract 出身;产出步 < 当前步可选,≥ 当前步禁用灰显 + "步骤 N 才产出"
- 空列表就地提示"没有可用变量"

## 3. 组件与数据流

```
CaseComposer.vue (不变: definition/orchestration 容器)
└─ CaseComposerCanvas
   ├─ col-info
   │   ├─ step 信息(现有)
   │   └─ VariableRegistryPanel(迁入,紧凑形态)
   │       props: steps(=local), configVars(=draftStore.draft.definition.config.vars)
   ├─ 字段编辑器 FieldForm
   │   props: bindings, body, varEntries → 改为: fieldActions(门控)
   │   emits: fieldExtract(field), fieldAssign(field, varName), fieldAssert(field)
   │         varInsert(field, name)     [插 ${var.x} 文本,原 Ⓥ 行为]
   │   └─ quickExtract/quickAssign/quickAssert 在 Canvas 落地:
   │       push 策略到 currentStep.strategy + justAddedStrategyIdx 展开
   └─ VarSelectorModal(headers Ⓥ): 分流 #7
CaseComposerConfig: 摘 VariableRegistryPanel + steps prop(#11)
```

var-registry.ts 变更:
- 新增 `assignVarRefs(steps)`: 收集全部 assign.source 的 `$.name` 引用(带 step 位置)
- `checkVarRefs` order 分支重定向: assign source 引用产出步 ≥ 消费步的 extract 变量
  → order issue(时序锚点 = after_request 产出 / before_request 消费,严格小于);
  `${var.x}` 引用不再做 order 判定
- deriveVarRegistry 不动(面板同名提示由 entries 现推:多个 entry 同 name)

## 4. 测试(清单,实现后逐条落地)

**var-registry.test.ts 增补**
- T1 assignVarRefs 收集 `$.name` source(含位置),忽略 `${var.x}`/字面量
- T2 order: step2 assign source `$.x` 引用 step3 extract x → order issue;
  引用 step1 → 无 issue;同 step → issue
- T3 `${var.x}` 引用不再产生 order issue(仅 dangling/missing_column)

**Canvas(新 CaseComposerCanvas.test.ts,挂载级)**
- T4 菜单门控: fieldActions 未传 → 无 ▾;传 → 有
- T5 从响应提取: push extract{target=字段名, scope='scenario'},策略卡展开
- T6 注入: 选中 extract 变量 → push assign{source='$.<name>',
  target='$.request_body.a.b'}(嵌套 path 前缀替换正确)
- T7 注入候选: 当前 step=2,step2 产出的变量禁用标"步骤 2 才产出",step1 产出可选
- T8 断言: push assertion{target=assertable 匹配}
- T9 变量列表迁入: config vars + extract 均展示;同名双产出 → 黄标"后者生效"

**FieldForm.test.ts 增补**
- T10 菜单四项渲染;引用插 `${var.x}` 追加到现值尾(原 Ⓥ 行为保留) —— **2026-09-05 修订**:引用改为先清空再写入(整串替换,混排模板手编);测试同步重钉

**Config 回归**
- T11 面板摘除后 CaseComposerConfig 4 用例仍绿;模板不再含"变量注册表"

**VarSelectorModal**
- T12 extract 出身禁选 + 提示文案

**回归底线**: 16 files / 97 tests 全绿基础上只增不减;vite build 绿。
