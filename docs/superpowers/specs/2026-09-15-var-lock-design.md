# 变量锁定(过程变量开关)设计

- 日期:2026-09-15
- 分支:feat/run-scheme-workbench
- 状态:设计定稿(三路系统扫描已完成:前端消费面 / 后端生命周期 / schemes 线耦合)

## 1. 背景与动机

业务上存在两类共享变量:

- **过程变量**:驱动业务流程的定值(环境地址、租户标识、凭证引用等),运行期不变,用户不需要、也不应该在数据集侧调整
- **业务变量**:按用例需要调值(金额、状态、边界值),数据集行覆盖正是为它们设计

现状没有这个区分,导致:

1. 数据集网格列宇宙 = 全部标量 `config.vars`(`DataSetEditor.varColumns`,声明序 + 引用扫描追加),每个数据集被迫面对所有变量 — 过程变量是纯噪音
2. CSV 模板携带固定列,Excel 用户易误改
3. **误覆盖有真实运行后果**:dispatcher 行合入是 row-wins(`run_dispatcher._compose_scenario` L1273-1275),手滑改一格过程变量,整批 case 全偏 — 正确性问题,非展示问题

## 2. 语义

**开关**:共享变量侧(③ 配置步「共享变量」卡)每个 config 出身变量一个锁开关;打开 = 定为过程变量。

| 锁定态(开关 ON) | 行为 |
|---|---|
| 运行取值 | 共享侧 `config.vars` 值独占 — 数据集行覆盖**不生效**(dispatcher 跳过合入,共享侧赢) |
| 数据集网格 | 锁定列**沉到底部**、灰化、只读(锁图标);引用徽标保留 |
| 历史行覆盖 | **数据保留不清除**,格子标琥珀告警「已锁定,此覆盖运行期不生效,共享侧配置为准」;解锁即自动恢复生效 |
| CSV 导出 | 不带锁定列 |
| CSV 导入 | 锁定列跳过 + 提示「N 列已锁定,已忽略」(区别于未知列报错) |
| 单变量视图 | VariableDetailPanel 顶部同款开关,可解锁回归可配置集;锁定态行值区只读 + 同款告警 |

**边界语义**:

- **共享侧值编辑不受锁影响** — 锁的是「数据集行覆盖」,不是「共享侧声明」;在 ③ 配置步 / 单变量面板基线卡改值正是锁定的本意
- **解锁 = 完全回到现状**(历史覆盖自动恢复生效,因为它们从未被清除)
- **仅 config 出身标量变量可锁**:结构化生成式(如 seq)本就不进 palette;extract 出身不进数据集配置面,开关不适用
- 引用面完全不动:`${var.x}` 解析、校验(dangling/order/missing_column)、VariableRegistryPanel、VarSelectorModal 均按名字工作,与值来源正交

## 3. 数据模型

`definition.config.var_locks: string[]`(锁定变量名清单,vars 旁挂)。

**选型依据**(三方案比较后定此):

- definition 纯 dict 透传,后端零模型改动;draft GET/PUT、场景复制无字段白名单,自动跟随
- plate `Config(BaseModel)`(`src/gimbal-plate/gimbal_plate/schema/scenario.py:47`)无 `extra="forbid"` — pydantic v2 默认 `extra="ignore"`,var_locks 被 plate 静默忽略,**不进 convert 产物、不进可执行导出 JSON**(正确语义:可执行产物无行级展开,锁无意义)
- 备选被否:payload 顶层旁挂(assertion_registry 先例)需 ScenarioDraft 加字段且与「变量配置」概念分离;orchestration 内需改模型且与编排状态混叠

**硬约束:锁定实现绝不能是「从 config.vars 删变量」或「值改结构化 dict」** — palette(`data_set_store._scalar_vars`)一缩,存量行数据的锁定键在下次 PUT 该数据集时 422 `undeclared_var`(`_validate_rows`),且场景 PUT 不复核数据集、无存量清洗通路。锁必须纯旁挂。

## 4. 改动落点

### 4.1 后端

1. **`run_dispatcher._compose_scenario`**(唯一行为改动点):row-wins 循环(`for k, v in row_dict.items()`)跳过 `k ∈ cfg.get("var_locks")` 的键。preview/export 通路本就不合行,零牵连;convert 缓存键随合成结果自然变化
2. **`adaptation_ops.renameVar`**:锁名随改名迁移(`_apply_rename_var` 改 vars 键名处同步改 var_locks 清单)— 否则按名存储的锁陈旧,锁定语义静默丢失
3. 测试:
   - dispatcher 锁定跳过(新用例;注意 `_coerce_row_value` 的行值类型还原断言 `test_run_baseline.py:160-208` 建立在「行值参与合入」上,锁定用例须新增,不改旧断言)
   - 注入间接通路钉住:注入条目 value 为整串 `${var.locked}` 时引擎预处理用 vars 值改写 source(`run_injection.py:48-57`)— 锁定后恒为共享侧值,行为自洽,防被当 bug
   - 导出黄金等价回归(`test_export_overlay_equivalence.py`):约束 = compose/preview 两路对 var_locks 携带一致(deepcopy 透传),等价保持;后人不得把锁挪到只有一条通路看见的位置

### 4.2 前端

1. **types/plate.ts `ConfigView`**:加 `var_locks?: string[]`(平台扩展字段,plate 侧 extra=ignore 吸收,同 field_states 先例)
2. **CaseComposerConfig.vue**(③ 配置步共享变量卡):
   - 行级锁开关(c-kv-row)
   - **三处同步携带 var_locks**:`emitShape`(L404-420 逐字段重建白名单)、local 初始化(L329-339)、入向 watch(L422-439 stringify 回声守卫)— 漏任何一处 = emit 剥数据 + 守卫失灵引发重建/emit 互触递归(该文件 L396-403 注释记录过同型 bug)
3. **DataSetEditor.vue**:
   - `varColumns`(L437-469,L441 拼接处):锁定列沉底 + 列头锁徽章
   - 基线行 / 数据格对锁定列只读(L188-216、`onCellInput` L699-712);TSV 粘贴拒写(`onCellPaste` L715-734)
   - 历史覆盖格琥珀告警(`cellClass` L736-739 + 预览弹窗 L630-646;dead-keys 提示条 L101-103 是告警条先例)
4. **VariableDetailPanel.vue**:顶部同款锁开关(解锁回归);锁定态行值区(L97-111)只读 + 告警;基线卡(L24-42)保持可编辑
5. **CSV 链**:
   - 导出:`csvVarColumns`(DataSetEditor L506)排除锁定列
   - 导入:`csv-dataset.ts` 加锁定列集 — palette 内但锁定的列跳过写 key 并计数,`importDataSetCsv` 返回提示信息,DataSetEditor 弹「N 列已锁定,已忽略」;**与未知列报错路径分流**(现状 L150-154 对 palette 外列记 error)

### 4.3 扫描确认不用改的面

- **schemes 工作台线**:方案的「数据」= 引用(datasetId + rowIndexes),无第二份变量配置面;运行完全复用 dispatcher 同一合并点
- **RunDialog / RunPanelHost**:前端运行链零 vars 消费(变量覆盖在引擎层发生)
- **VariableRegistryPanel / VarSelectorModal**:名字级推导/插入,只读(可选加锁徽章,展示层)
- **var-registry.ts / tpl-refs.ts / draft-lint.ts / dataset-segments.ts / dataset-palette.ts / dataset-grid.ts**:纯投影/校验层,锁定语义在 DataSetEditor 层解决
- **CaseDataSetsList.vue**:预览列 = 行键,不读 config.vars(如需列表页也藏锁定列覆盖值另议,默认不动)
- **注入物化 / AssertionRegistryEditor**:与 config.vars 零耦合(间接通路已由测试钉住)
- **场景可执行导出链**(ScenarioExportMenu / scenario-draft store / previewPlateDraft):definition 整体透传,var_locks 由 plate Config 模型剥除 — 正确语义,前端零改动
- **场景 JSON 导入**:前端不存在该入口
- **data_set_store._validate_rows**:锁不删 var,palette 不变,存量行合法
- **ConstantPoolPanel / pool-var.ts / CaseComposer.onVarPromote / seedPoolVar**:共享侧声明通路,spread/??= 写法均保留 config 其它键
- **useSystemPrefill.mergeConfig**:会丢 var_locks 但仅作用于「config 全空的新建场景」首填,实际不可见(可顺手补,非必须)

## 5. 风险与约束(实现者必读)

1. **锁实现纯旁挂**(§3 硬约束)— palette 缩水 = 存量数据 422,无清洗通路
2. **黄金等价测试形状敏感**:`_compose_scenario` 恒写回 vars 的形状被 `test_export_overlay_equivalence.py:34` 钉死,var_locks 不得造成 compose/preview 两路 config 写形状差异
3. **renameVar 陈旧锁**:锁名必须随改名迁移(§4.1.2)
4. **`_coerce_row_value` 不再作用于锁定键**:共享侧值保持作者类型(int/bool/float),不经字符串还原 — 预期差异,新测试用例覆盖
5. **CaseComposerConfig 三处同步**(§4.2.2)— 该文件有回声守卫递归 bug 前科,改完必须跑其既有测试

## 6. 测试面清单

**后端**:dispatcher 锁定跳过 / 注入 `${var.locked}` 间接通路 / renameVar 锁迁移 / 导出等价回归
**前端**:ConfigView 类型 / emitShape 携带 var_locks(往返)/ 网格沉底排序 + 只读 / 告警格渲染 / CSV 导出排除 + 导入跳过提示(含旧模板带锁定列)/ 单变量面板开关与只读 / TSV 拒写
