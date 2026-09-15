# 变量锁定(过程变量开关)设计

- 日期:2026-09-15
- 分支:feat/run-scheme-workbench
- 状态:设计定稿(三路系统扫描完成;运行期语义经两轮评审定为**纯编辑面锁**)

## 0. 决策记录

运行期语义两轮演化:

1. 初版选 A(锁定即共享侧赢,dispatcher 跳过行合入 + 告警)
2. 用户澄清平台根基语义:**「模板提供规范,用户可以自由调整」** — 共享变量是模板规范值,数据集是用户自由调整面,「行有值就行值」(row-wins)是根基语义,锁不应推翻它;若锁成运行期强制,用户侧配置就失去了意义
3. **定稿:纯编辑面锁** — 锁只作用于编辑面(展示/降噪/CSV),引擎零改动。代价(锁无强制力,遗留覆盖继续生效)由信息提示 + 恢复默认一键清理兜住,且与「用户可自由调整」语义一致:遗留覆盖只是一次尚在生效的用户调整,不是错误

## 1. 背景与动机

业务上存在两类共享变量:

- **过程变量**:驱动业务流程的定值(环境地址、租户标识、凭证引用等),通常不变,大多数数据集不需要调它们
- **业务变量**:按用例需要调值(金额、状态、边界值),数据集行覆盖正是为它们设计

现状没有这个区分,导致:

1. 数据集网格列宇宙 = 全部标量 `config.vars`(`DataSetEditor.varColumns`,声明序 + 引用扫描追加),每个数据集被迫面对所有变量 — 过程变量是纯噪音
2. CSV 模板携带固定列,Excel 用户易误改
3. 变量多时单变量选择器下拉冗长

**非目标**(定稿澄清):锁不解决「误覆盖有运行后果」— 那是 row-wins 根基语义的一部分,用户调整就是应当生效的。锁只做编辑面的默认姿态。

## 2. 语义

**开关**:共享变量侧(③ 配置步「共享变量」卡)每个 config 出身变量一个锁开关;打开 = 归类为过程变量。

| 面 | 锁定态(ON)行为 |
|---|---|
| **运行取值** | **引擎零改动,规则照旧**:行有覆盖 → 行值赢;无覆盖 → 继承共享侧基线(动态) |
| **数据集网格** | 锁定列**沉到底部**、灰化、默认不可编辑(锁图标 + 说明「过程变量 · 默认用共享侧配置」);引用徽标保留 |
| **数据集本地放开** | 数据集自己的元数据(`var_unlocks` 清单)把某锁定变量**仅在本数据集**放回可编辑列 — 不碰共享侧、不碰其他数据集 |
| **历史行覆盖** | **数据保留、继续生效**(它是一次用户调整),格子标信息提示「已锁定为过程变量,本数据集使用自有值」+ 「恢复默认」入口 |
| **恢复默认** | 按变量一键:**全覆盖撤销** — 清掉本数据集所有行里该变量的覆盖键 + 撤销本地放开 → 回到「锁定、继承共享侧值」的默认态 |
| **CSV 导出** | 不带未本地放开的锁定列 |
| **CSV 导入** | 锁定列(未本地放开)跳过 + 提示「N 列已锁定,已忽略」(区别于未知列报错);本地放开的列正常参与 |

**边界语义**:

- **共享侧值编辑不受锁影响** — 锁的是「数据集编辑面的默认姿态」,不是「共享侧声明」
- **两侧 ownership 互不影响**:锁声明归共享侧(`config.var_locks`,场景级);本地放开归数据集(`var_unlocks`,数据集级);数据集侧动作永不写场景级配置,反向亦然。存储层两侧本就独立(rows vs config.vars),本设计延续
- **仅 config 出身标量变量可锁**:结构化生成式(如 seq)本就不进 palette;extract 出身不进数据集配置面
- 引用面完全不动:`${var.x}` 解析、校验、VariableRegistryPanel、VarSelectorModal 均按名字工作

## 3. 数据模型

### 3.1 全局锁清单:`definition.config.var_locks: string[]`

- definition 纯 dict 透传,后端零模型改动;draft GET/PUT、场景复制自动携带
- plate `Config(BaseModel)`(`src/gimbal-plate/gimbal_plate/schema/scenario.py:47`)默认 `extra="ignore"` — var_locks 被 plate 静默忽略,不进 convert 产物/可执行导出(正确语义:可执行产物无编辑面概念)
- 引擎(dispatcher)不读此清单 — 锁对运行完全透明

### 3.2 数据集本地放开:`ComposerDataSet` 元数据 `var_unlocks: string[]`

- 存放:数据集模型新增一个 JSON 清单字段(后端有 run_schemes 独立表迁移先例);API wire(DataSet 详情/创建/更新)同步携带
- 前端 DataSetEditor 持有并随「保存数据集」一起落库

## 4. 改动落点

### 4.1 后端(仅存储与适配,零运行时改动)

1. **ComposerDataSet 模型**:`var_unlocks` 字段 + 迁移;data_set_store 创建/更新/读取携带;`_validate_rows` 不校验此清单(它只约束行键 ⊆ palette,palette 不因锁变化)
2. **`adaptation_ops.renameVar`**:锁名迁移扩到两份清单 — `config.var_locks` + 各数据集 `var_unlocks`(行键联动 `apply_to_rows` 已有)— 否则按名存储的清单陈旧,语义静默丢失
3. **测试**:var_unlocks 存储往返 / renameVar 两清单迁移 / 既有 dispatcher 行为回归(证明引擎未动,黄金等价与注入通路测试应原样通过,零修改)

### 4.2 前端

1. **types/plate.ts `ConfigView`**:加 `var_locks?: string[]`;数据集类型加 `var_unlocks?: string[]`
2. **CaseComposerConfig.vue**(③ 配置步共享变量卡):
   - 行级锁开关(c-kv-row)
   - **三处同步携带 var_locks**:`emitShape`(L404-420 逐字段重建白名单)、local 初始化(L329-339)、入向 watch(L422-439 stringify 回声守卫)— 漏任何一处 = emit 剥数据 + 守卫失灵引发重建/emit 互触递归(该文件 L396-403 注释记录过同型 bug)
3. **DataSetEditor.vue**:
   - `varColumns`(L437-469,L441 拼接处):锁定且未本地放开的列沉底
   - 可编辑集 = 未锁定 ∪ 本数据集 var_unlocks;锁定列格子默认只读 + 锁图标 + 说明
   - 本地放开/收回开关(列头或单变量视图;写本数据集 var_unlocks,不写场景)
   - 历史覆盖格信息提示(有覆盖的锁定格:「已锁定为过程变量,本数据集使用自有值」)
   - **恢复默认**按钮(锁定列头/单变量视图):清该变量全部行键 + 从 var_unlocks 撤销
   - TSV 粘贴对未放开锁定列拒写(`onCellPaste` L715-734)
4. **VariableDetailPanel.vue**:顶部「本地放开」开关;锁定态行值区只读 + 同款提示 + 恢复默认;基线卡保持可编辑(锁不约束共享侧)
5. **CSV 链**:
   - 列宇宙跟随可编辑集:导出排除未放开锁定列
   - 导入:`csv-dataset.ts` 加锁定列集 — 跳过写 key 并计数,返回提示信息,DataSetEditor 弹「N 列已锁定,已忽略」;与未知列报错路径分流(现状 L150-154)

### 4.3 扫描确认不用改的面

- **dispatcher / run_injection / run_materialize / plate_client**:引擎零感知(本设计核心收益)
- **schemes 工作台线**:方案的「数据」= 引用(datasetId + rowIndexes),无第二份变量配置面
- **RunDialog / RunPanelHost**:前端运行链零 vars 消费
- **VariableRegistryPanel / VarSelectorModal**:名字级推导/插入(可选加锁徽章,展示层)
- **var-registry.ts / tpl-refs.ts / draft-lint.ts / dataset-segments.ts / dataset-palette.ts / dataset-grid.ts**:纯投影/校验层
- **CaseDataSetsList.vue**:预览列 = 行键,不读 config.vars(默认不动)
- **注入物化 / AssertionRegistryEditor**:与 config.vars 零耦合
- **场景可执行导出链**:definition 整体透传,var_locks 由 plate Config 模型剥除 — 正确语义,前端零改动
- **场景 JSON 导入**:前端不存在该入口
- **data_set_store._validate_rows**:锁不删 var,palette 不变,存量行合法
- **ConstantPoolPanel / pool-var.ts / CaseComposer.onVarPromote / seedPoolVar**:共享侧声明通路,spread/??= 写法均保留 config 其它键
- **useSystemPrefill.mergeConfig**:仅作用于「config 全空的新建场景」首填,实际不可见(可顺手补,非必须)

## 5. 风险与约束(实现者必读)

1. **锁实现纯旁挂** — 绝不能「从 config.vars 删变量」或「值改结构化 dict」:palette(`_scalar_vars`)一缩,存量行数据下次 PUT 该数据集时 422 `undeclared_var`,且无存量清洗通路
2. **CaseComposerConfig 三处同步**(§4.2.2)— 该文件有回声守卫递归 bug 前科,改完必须跑其既有测试
3. **renameVar 双清单迁移**(§4.1.2)— var_locks 与 var_unlocks 都按名存储,都要随改名迁移
4. **var_unlocks 与 var_locks 的交叉态**:本地放开的变量随后被共享侧删除(不在 vars 了)→ 该放开项成为死配置,行为 = 列本就不存在,无运行影响;编辑器可静默忽略(dead-keys 提示条 L101-103 先例)
5. **CSV 导入提示分流**:锁定列跳过是提示不是报错;不要落进「未知列」error 路径

## 6. 测试面清单

**后端**:var_unlocks 存储往返 / renameVar 双清单迁移 / dispatcher 既有测试原样通过(引擎未动的回归证明)
**前端**:ConfigView 类型 / emitShape 携带 var_locks(往返)/ 网格沉底排序 / 可编辑集(锁定 ∪ 本地放开)/ 信息提示格 / 恢复默认(清行键 + 撤放开)/ CSV 导出排除 + 导入跳过提示(含旧模板带锁定列)/ 单变量面板放开开关与只读 / TSV 拒写
